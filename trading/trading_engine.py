import ccxt
import logging
import json
import numpy as np
from datetime import datetime
from typing import Dict, Optional, List
from config.settings import Config
from database.db_manager import db
from analysis.analyzer import AIAnalyzer
from analysis.risk_manager import RiskManager
from analysis.liquidity import LiquidityAnalyzer
from strategies.arbitrage import ArbitrageEngine

logger = logging.getLogger(__name__)

class TradingEngine:
    def __init__(self, exchange_manager):
        self.exchange_manager = exchange_manager
        self.ai = AIAnalyzer(self.exchange_manager)
        self.risk_manager = RiskManager(exchange_manager)
        self.liquidity_analyzer = LiquidityAnalyzer(exchange_manager)
        self.arbitrage_engine = ArbitrageEngine(exchange_manager)
    def _create_default_exchange_manager(self):
        from .exchange import ExchangeManager
        return ExchangeManager()

    async def get_user_settings(self, user_id: int) -> dict:
        """Получаем настройки пользователя"""
        user_data = await db.fetch(
            "SELECT api_keys, risk_level, auto_trading, trading_strategy FROM users WHERE user_id = ?",
            (user_id,)
        )
        return {
            'api_keys': json.loads(user_data[0][0]) if user_data[0][0] else {},
            'risk_level': user_data[0][1],
            'auto_trading': user_data[0][2],
            'strategy': user_data[0][3]
        }

    async def initialize_exchange(self, user_id: int, exchange_name: str, symbol: str):
        """Инициализация подключения к бирже"""
        try:
            settings = await self.get_user_settings(user_id)
            api_keys = settings['api_keys']
            
            if exchange_name not in api_keys:
                raise ValueError(f"API keys for {exchange_name} not configured")

            exchange_class = getattr(ccxt, exchange_name)
            return exchange_class({
                'apiKey': api_keys[exchange_name]['key'],
                'secret': api_keys[exchange_name]['secret'],
                'enableRateLimit': True,
                'options': {'defaultType': 'future'} if ':USDT' in symbol else {}
            })
        except Exception as e:
            logger.error(f"Exchange init error: {e}")
            raise

    async def execute_trade(self, user_id: int, exchange: str, symbol: str, 
                          side: str, amount: float, order_type: str = 'market',
                          price: float = None, params: dict = None) -> Dict:
        """Выполнение торговой операции"""
        try:
            ex = await self.initialize_exchange(user_id, exchange, symbol)
            
            # Проверка баланса для ордеров на покупку
            if side == 'buy':
                balance = await ex.fetch_balance()
                usdt_balance = balance['free'].get('USDT', 0)
                required_amount = amount * (price or 1)
                if usdt_balance < required_amount:
                    raise ValueError(f"Insufficient USDT balance. Need {required_amount}, have {usdt_balance}")

            # Создание ордера
            order = await ex.create_order(
                symbol,
                order_type,
                side,
                amount,
                price,
                params or {}
            )
            
            return {
                'status': 'filled',
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'amount': amount,
                'price': order['price'],
                'timestamp': order['timestamp']
            }
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return {'status': 'error', 'message': str(e)}

    async def analyze_market(self, symbol: str) -> Optional[Dict]:
        """Полный анализ рынка для символа"""
        try:
            # 1. Проверка ликвидности
            liquidity = await self.liquidity_analyzer.get_liquidity_score(symbol, 'binance')
            if liquidity < 1.0:
                return None

            # 2. AI анализ тренда
            trend = await self.ai.predict_trend(symbol)
            if trend['confidence'] < 0.7:
                return None

            # 3. Поиск арбитражных возможностей
            opportunity = await self.arbitrage_engine.find_opportunities(symbol)
            if not opportunity:
                return None

            # 4. Проверка рисков
            if not await self.risk_manager.validate_opportunity(opportunity):
                return None

            return {
                'symbol': symbol,
                'opportunity': opportunity,
                'trend': trend,
                'liquidity': liquidity
            }
        except Exception as e:
            logger.error(f"Market analysis error for {symbol}: {e}")
            return None

    async def auto_trade(self, user_id: int):
        """Основной цикл автоматической торговли"""
        try:
            settings = await self.get_user_settings(user_id)
            if not settings['auto_trading'] or not settings['api_keys']:
                return

            logger.info(f"Starting auto trading for user {user_id}")
            
            for symbol in Config.TRADING_PAIRS:
                try:
                    analysis = await self.analyze_market(symbol)
                    if not analysis:
                        continue

                    opportunity = analysis['opportunity']
                    risk_multiplier = {1: 0.5, 2: 1.0, 3: 1.5}.get(settings['risk_level'], 1.0)
                    
                    # Расчет объема позиции
                    max_amount = min(
                        opportunity['volume'] * 0.01 * risk_multiplier,
                        Config.MAX_ORDER_SIZE / opportunity['buy_price']
                    )

                    if max_amount * opportunity['buy_price'] < Config.MIN_ORDER_SIZE:
                        continue

                    # Параметры ордера
                    params = {
                        'leverage': Config.DEFAULT_LEVERAGE,
                        'stopLoss': {
                            'price': opportunity['buy_price'] * (1 - (0.01 * risk_multiplier)),
                            'type': 'limit'
                        },
                        'takeProfit': {
                            'price': opportunity['sell_price'] * (1 + (0.02 * risk_multiplier)),
                            'type': 'limit'
                        }
                    }

                    # Выполнение сделки
                    trade_result = await self.execute_trade(
                        user_id,
                        opportunity['buy_exchange'].split('_')[0],
                        opportunity['symbol'],
                        'buy',
                        max_amount,
                        params=params
                    )

                    if trade_result['status'] == 'filled':
                        # Логирование сделки
                        await db.execute(
                            '''INSERT INTO trades 
                            (user_id, symbol, exchange, amount, entry_price,
                             type, direction, leverage, stop_loss, take_profit, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (user_id, symbol,
                             f"{opportunity['buy_exchange']}->{opportunity['sell_exchange']}",
                             max_amount, trade_result['price'],
                             'futures' if ':USDT' in symbol else 'spot',
                             'long',
                             params['leverage'],
                             params['stopLoss']['price'],
                             params['takeProfit']['price'],
                             'open')
                        )
                        
                        logger.info(f"Trade executed for user {user_id}: {symbol}")
                except Exception as e:
                    logger.error(f"Error processing {symbol} for user {user_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Auto trading error for user {user_id}: {e}")
