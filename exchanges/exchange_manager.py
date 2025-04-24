import asyncio
import logging
import ccxt
import contextlib
from typing import Dict, List, Optional, Tuple
from ccxt.async_support import (binance, bybit, bingx, kucoin, okx)
from config.settings import Config

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self):
        """Инициализация подключений к биржам"""
        self.exchanges = {
            'binance': {
                'spot': binance({'enableRateLimit': True}),
                'futures': binance({
                    'options': {
                        'defaultType': 'future',
                        'adjustForTimeDifference': True
                    }
                })
            },
            'bybit': {
                'spot': bybit({'enableRateLimit': True}),
                'futures': bybit({
                    'options': {
                        'defaultType': 'contract',
                        'leverage': 10  # Default leverage
                    }
                })
            },
            'bingx': {
                'spot': bingx({'enableRateLimit': True}),
                'futures': bingx({
                    'options': {
                        'defaultType': 'swap',
                        'adjustForTimeDifference': True
                    }
                })
            },
            'kucoin': {
                'spot': kucoin({'enableRateLimit': True}),
                'futures': kucoin({
                    'options': {
                        'defaultType': 'futures',
                        'leverage': 3
                    }
                })
            },
            'okx': {
                'spot': okx({'enableRateLimit': True}),
                'futures': okx({
                    'options': {
                        'defaultType': 'futures',
                        'leverage': 5
                    }
                })
            }
        }
        self.active_connections = set()

    @contextlib.asynccontextmanager
    async def get_exchange(self, exchange: str, ex_type: str = 'spot'):
        """Контекстный менеджер для безопасной работы с биржей"""
        if exchange not in self.exchanges or ex_type not in self.exchanges[exchange]:
            raise ValueError(f"Exchange {exchange} {ex_type} not configured")
            
        ex = self.exchanges[exchange][ex_type]
        self.active_connections.add(ex)
        try:
            yield ex
        finally:
            try:
                await ex.close()
                self.active_connections.discard(ex)
            except Exception as e:
                logger.error(f"Error closing exchange: {e}")

    async def get_prices(self, symbol: str) -> Dict[str, Dict]:
        """Получение цен на всех биржах"""
        prices = {}
        for ex_name, ex_types in self.exchanges.items():
            ex_type = 'futures' if ':USDT' in symbol else 'spot'
            if ex_type not in ex_types:
                continue
                
            async with self.get_exchange(ex_name, ex_type) as exchange:
                for attempt in range(Config.MAX_RETRIES):
                    try:
                        ticker = await exchange.fetch_ticker(symbol)
                        prices[f"{ex_name}_{ex_type}"] = {
                            'bid': ticker['bid'],
                            'ask': ticker['ask'],
                            'last': ticker['last'],
                            'volume': ticker['baseVolume'],
                            'type': ex_type
                        }
                        break
                    except Exception as e:
                        if attempt == Config.MAX_RETRIES - 1:
                            logger.error(f"Error getting price from {ex_name} ({ex_type}): {e}")
                        await asyncio.sleep(Config.RETRY_DELAY)

        return prices

    async def create_order(
        self,
        exchange: str,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict] = None,
        leverage: Optional[int] = None
    ) -> Optional[Dict]:
        """Создание ордера с поддержкой плеча"""
        ex_type = 'futures' if ':USDT' in symbol else 'spot'
        
        try:
            async with self.get_exchange(exchange, ex_type) as ex:
                # Установка плеча для фьючерсов
                if leverage and ex_type == 'futures':
                    await ex.set_leverage(leverage, symbol)
                
                # Проверка баланса
                if side == 'buy':
                    balance = await ex.fetch_balance()
                    usdt_balance = balance['total'].get('USDT', 0)
                    required = amount * (price or 1)
                    if usdt_balance < required:
                        logger.warning(f"Insufficient USDT balance: {usdt_balance} < {required}")
                        return None
                
                # Создание ордера
                params = params or {}
                if ex_type == 'futures':
                    params['timeInForce'] = 'GTC'
                
                return await ex.create_order(
                    symbol=symbol,
                    type=order_type,
                    side=side,
                    amount=amount,
                    price=price,
                    params=params
                )
        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds: {e}")
            return None
        except ccxt.NetworkError as e:
            logger.error(f"Network error: {e}")
            return None
        except Exception as e:
            logger.error(f"Order error: {e}")
            return None

    async def find_arbitrage(self, symbol: str, threshold: float = 0.5) -> Dict[str, Dict]:
        """Поиск арбитражных возможностей"""
        prices = await self.get_prices(symbol)
        opportunities = {}
        
        for ex1, data1 in prices.items():
            for ex2, data2 in prices.items():
                if ex1 == ex2:
                    continue
                    
                spread = data1['bid'] - data2['ask']
                if spread > threshold and data1['volume'] > Config.MIN_ARBITRAGE_VOLUME:
                    opportunities[f"{ex1}-{ex2}"] = {
                        'buy_at': ex2,
                        'sell_at': ex1,
                        'spread': spread,
                        'volume': min(data1['volume'], data2['volume'])
                    }
        
        return opportunities

    async def copy_trade(
        self,
        source_exchange: str,
        target_exchange: str,
        trader_id: str,
        risk_percent: float = 1.0
    ) -> List[Dict]:
        """Копирование сделок трейдера"""
        results = []
        async with self.get_exchange(source_exchange, 'futures') as source_ex:
            try:
                # Получаем позиции трейдера (зависит от API биржи)
                if source_exchange == 'bingx':
                    positions = await source_ex.fetch_positions(trader_id)
                elif source_exchange == 'bybit':
                    positions = await source_ex.fetch_trader_orders(trader_id)
                else:
                    logger.error(f"Copy trading not supported for {source_exchange}")
                    return []
                
                # Копируем позиции
                for pos in positions:
                    symbol = pos['symbol']
                    amount = pos['amount']
                    side = pos['side']
                    
                    # Рассчитываем сумму с учетом риска
                    balance = await self.get_balance(target_exchange)
                    risk_amount = balance * risk_percent / 100
                    
                    if amount * pos['entryPrice'] > risk_amount:
                        amount = risk_amount / pos['entryPrice']
                    
                    # Создаем ордер
                    order = await self.create_order(
                        exchange=target_exchange,
                        symbol=symbol,
                        order_type='market',
                        side=side,
                        amount=amount,
                        leverage=pos.get('leverage', 1)
                    )
                    if order:
                        results.append(order)
                        
            except Exception as e:
                logger.error(f"Copy trade error: {e}")
                
        return results

    async def get_balance(self, exchange: str, ex_type: str = 'spot') -> float:
        """Получение баланса USDT"""
        async with self.get_exchange(exchange, ex_type) as ex:
            balance = await ex.fetch_balance()
            return balance['total'].get('USDT', 0)

    async def get_market_data(self, symbol: str, timeframe: str = '1h', limit: int = 100) -> Dict:
        """Сбор рыночных данных для анализа"""
        data = {}
        for ex_name in self.exchanges:
            async with self.get_exchange(ex_name, 'spot') as ex:
                try:
                    ohlcv = await ex.fetch_ohlcv(symbol, timeframe, limit)
                    data[ex_name] = {
                        'ohlcv': ohlcv,
                        'volume': sum(x[5] for x in ohlcv),
                        'spread': (ohlcv[-1][2] - ohlcv[-1][3]) / ohlcv[-1][2] * 100
                    }
                except Exception as e:
                    logger.error(f"Error getting data from {ex_name}: {e}")
        return data

    async def set_leverage(self, exchange: str, symbol: str, leverage: int) -> bool:
        """Установка уровня плеча"""
        if exchange not in self.exchanges or 'futures' not in self.exchanges[exchange]:
            return False
            
        try:
            async with self.get_exchange(exchange, 'futures') as ex:
                await ex.set_leverage(leverage, symbol)
                return True
        except Exception as e:
            logger.error(f"Leverage setting error: {e}")
            return False

    async def close_all_positions(self, exchange: str) -> List[Dict]:
        """Закрытие всех позиций на бирже"""
        results = []
        async with self.get_exchange(exchange, 'futures') as ex:
            try:
                positions = await ex.fetch_positions()
                for pos in positions:
                    if pos['contracts'] > 0:
                        order = await ex.create_order(
                            symbol=pos['symbol'],
                            type='market',
                            side='sell' if pos['side'] == 'long' else 'buy',
                            amount=abs(pos['contracts']),
                            params={'reduceOnly': True}
                        )
                        results.append(order)
            except Exception as e:
                logger.error(f"Position closing error: {e}")
        return results

    async def close_all(self):
        """Закрытие всех соединений"""
        for exchange in list(self.active_connections):
            try:
                await exchange.close()
                self.active_connections.discard(exchange)
            except Exception as e:
                logger.error(f"Error closing exchange: {e}")