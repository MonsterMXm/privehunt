import logging
from typing import List, Dict, Optional
from config.settings import Config

logger = logging.getLogger(__name__)

class PositionManager:
    @staticmethod
    async def check_open_positions(user_id: int) -> List[Dict]:
        try:
            positions = await db.fetch(
                "SELECT symbol, type, direction, amount, entry_price FROM trades "
                "WHERE user_id = ? AND status = 'open'",
                (user_id,)
            )
            return [dict(zip(['symbol', 'type', 'direction', 'amount', 'entry_price'], row)) 
                    for row in positions]
        except Exception as e:
            logger.error(f"Position check error: {e}")
            return []

    @staticmethod
    async def close_position(user_id: int, trade_id: int) -> bool:
        try:
            trade_data = await db.fetch(
                "SELECT symbol, exchange, amount, direction FROM trades "
                "WHERE trade_id = ? AND user_id = ? AND status = 'open'",
                (trade_id, user_id)
            )
            
            if not trade_data:
                return False
                
            symbol, exchange, amount, direction = trade_data[0]
            
            ex_name = exchange.split('_')[0]
            side = 'sell' if direction == 'long' else 'buy'
            result = await exchange_manager.create_order(
                ex_name,
                symbol,
                'market',
                side,
                amount
            )
            
            if result:
                await db.execute(
                    "UPDATE trades SET status = 'closed', exit_price = ? "
                    "WHERE trade_id = ?",
                    (result['price'], trade_id)
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Position close error: {e}")
            return False