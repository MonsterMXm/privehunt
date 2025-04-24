import logging
from typing import List, Dict, Optional
import json
from datetime import datetime
from config.settings import Config
from database.db_manager import db
from exchanges.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class PositionManager:
    def __init__(self, exchange_manager = ExchangeManager):
        self.exchange_manager = exchange_manager

    async def get_open_positions(self, user_id: int) -> List[Dict]:
        """Получение всех открытых позиций пользователя"""
        try:
            # Получаем позиции из базы данных
            db_positions = await db.fetch(
                "SELECT position_id, symbol, exchange, direction, amount, entry_price, entry_time "
                "FROM positions WHERE user_id = ? AND status = 'open'",
                (user_id,)
            )
            
            if not db_positions:
                return []

            positions = []
            for pos in db_positions:
                position_id, symbol, exchange, direction, amount, entry_price, entry_time = pos
                
                # Получаем текущую цену
                try:
                    async with self.exchange_manager.get_exchange(exchange) as ex:
                        ticker = await ex.fetch_ticker(symbol)
                        current_price = ticker['last']
                        
                        # Рассчитываем PnL
                        pnl = None
                        if entry_price and current_price:
                            if direction == 'long':
                                pnl = (current_price - entry_price) * amount
                            else:
                                pnl = (entry_price - current_price) * amount
                                
                        positions.append({
                            'position_id': position_id,
                            'symbol': symbol,
                            'exchange': exchange,
                            'direction': direction,
                            'amount': amount,
                            'entry_price': entry_price,
                            'entry_time': entry_time,
                            'current_price': current_price,
                            'pnl': pnl,
                            'pnl_percent': (pnl / (entry_price * amount) * 100 if pnl and entry_price else None)
                        })
                except Exception as e:
                    logger.error(f"Error getting price for {symbol}: {e}")
                    continue
                    
            return positions
        except Exception as e:
            logger.error(f"Error in get_open_positions: {e}", exc_info=True)
            return []

    async def close_position(self, user_id: int, position_id: int) -> bool:
        """Закрытие позиции по ID"""
        try:
            # Получаем данные позиции
            position_data = await db.fetch(
                "SELECT symbol, exchange, direction, amount FROM positions "
                "WHERE position_id = ? AND user_id = ? AND status = 'open'",
                (position_id, user_id)
            )
            
            if not position_data:
                logger.error(f"Position {position_id} not found or already closed")
                return False
                
            symbol, exchange, direction, amount = position_data[0]
            
            # Создаем ордер на закрытие
            side = 'sell' if direction == 'long' else 'buy'
            order_result = None
            
            try:
                async with self.exchange_manager.get_exchange(exchange) as ex:
                    # Получаем API ключи пользователя
                    user_data = await db.fetch(
                        "SELECT api_keys FROM users WHERE user_id = ?",
                        (user_id,)
                    )
                    
                    if user_data and user_data[0][0]:
                        api_keys = json.loads(user_data[0][0])
                        if exchange in api_keys:
                            ex.apiKey = api_keys[exchange]['key']
                            ex.secret = api_keys[exchange]['secret']
                    
                    order_result = await ex.create_order(
                        symbol=symbol,
                        type='market',
                        side=side,
                        amount=amount
                    )
                    
                    if order_result:
                        # Обновляем статус позиции в БД
                        await db.execute(
                            "UPDATE positions SET status = 'closed', exit_price = ?, exit_time = ? "
                            "WHERE position_id = ?",
                            (order_result['price'], datetime.now(), position_id)
                        )
                        return True
            except Exception as e:
                logger.error(f"Error closing position on exchange: {e}")
                return False
                
            return False
        except Exception as e:
            logger.error(f"Error in close_position: {e}", exc_info=True)
            return False

    @staticmethod
    async def create_position(
        user_id: int,
        symbol: str,
        exchange: str,
        direction: str,
        amount: float,
        entry_price: float
    ) -> Optional[int]:
        """Создание новой позиции в базе данных"""
        try:
            position_id = await db.execute(
                "INSERT INTO positions (user_id, symbol, exchange, direction, amount, entry_price, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'open')",
                (user_id, symbol, exchange, direction, amount, entry_price)
            )
            return position_id
        except Exception as e:
            logger.error(f"Error creating position: {e}")
            return None
