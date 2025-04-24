import logging
from typing import Dict, Optional
from config.settings import Config
from exchanges.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class LiquidityAnalyzer:
     def __init__(self, exchange_manager):
         self.exchange_manager = exchange_manager

     async def get_liquidity_score(self, symbol: str, exchange: str) -> float:
        try:
            async with self.exchange_manager.get_exchange(exchange, 'spot') as ex:
                orderbook = await ex.fetch_order_book(symbol, limit=10)
                
                bid_volume = sum(x[1] for x in orderbook['bids'])
                ask_volume = sum(x[1] for x in orderbook['asks'])
                
                avg_volume = (bid_volume + ask_volume) / 2
                price = (orderbook['bids'][0][0] + orderbook['asks'][0][0]) / 2
                liquidity_score = (avg_volume * price) / 1000000
                
                return liquidity_score
        except Exception as e:
            logger.error(f"Liquidity check error: {e}")
            return 0.0
