import json
import logging
from typing import Dict
from config.settings import Config
from exchanges.exchange_manager import ExchangeManager
from database.db_manager import db

logger = logging.getLogger(__name__)

class AutoStrategies:
    def __init__(self, exchange_manager: ExchangeManager):
         self.exchange_manager = exchange_manager
         
    async def grid_trading(self, user_id: int, symbol: str, lower: float, upper: float, grids: int = 5):
        try:
            prices = await self.exchange_manager.get_prices(symbol)
            if 'binance_spot' not in prices:
                return {"status": "error", "message": "Не удалось получить цены"}
                
            current_price = prices['binance_spot']['ask']
            grid_step = (upper - lower) / grids
            orders = []
            
            for i in range(1, grids+1):
                price = lower + i * grid_step
                if price < current_price:
                    order = await self.exchange_manager.create_order(
                        'binance',
                        symbol,
                        'limit',
                        'sell',
                        0.01,
                        price
                    )
                    if order:
                        orders.append(order)
            
            await db.execute(
                "INSERT INTO strategies (user_id, symbol, type, params) VALUES (?, ?, ?, ?)",
                (user_id, symbol, 'grid', json.dumps({"lower": lower, "upper": upper, "grids": grids}))
            )
            return {
                "status": "activated",
                "orders": len(orders),
                "price_range": f"{lower}-{upper}"
            }
        except Exception as e:
            logger.error(f"Grid trading error: {e}")
            return {"status": "error", "message": str(e)}

    async def check_strategies(self):
        try:
            strategies = await db.fetch(
                "SELECT strategy_id, user_id, symbol, type, params FROM strategies WHERE is_active = TRUE"
            )
            
            for strat in strategies:
                strat_id, user_id, symbol, strat_type, params = strat
                try:
                    params = json.loads(params)
                    
                    if strat_type == 'grid':
                        prices = await self.exchange_manager.get_prices(symbol)
                        if 'binance_spot' not in prices:
                            continue
                            
                        current_price = prices['binance_spot']['ask']
                        grid_step = (params['upper'] - params['lower']) / params['grids']
                        active_grids = int((current_price - params['lower']) / grid_step)
                        
                        if active_grids <= 1:
                            await self.grid_trading(
                                user_id, symbol, 
                                params['lower'], 
                                params['upper'], 
                                params['grids'])
                except Exception as e:
                    logger.error(f"Strategy check error: {e}")
                    continue
        except Exception as e:
            logger.error(f"Strategies monitoring error: {e}")
