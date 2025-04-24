import logging
from typing import Dict, Optional
from config.settings import Config
from exchanges.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class ArbitrageEngine:
    def __init__(self, exchange_manager: ExchangeManager):
         self.exchange_manager = exchange_manager
         
    async def find_opportunities(self, symbol: str) -> Optional[Dict]:
        try:
            prices = await self.exchange_manager.get_prices(symbol)
            if len(prices) < 2:
                return None
                
            prices = {k: v for k, v in prices.items() if v['volume'] > 0}
            if len(prices) < 2:
                return None
                
            best_bid = max(prices.items(), key=lambda x: x[1]['bid'])
            best_ask = min(prices.items(), key=lambda x: x[1]['ask'])
            
            spread = (best_bid[1]['bid'] - best_ask[1]['ask']) / best_ask[1]['ask'] * 100
            profit = spread - Config.COMMISSION
            
            if profit >= Config.MIN_PROFIT:
                return {
                    'symbol': symbol,
                    'buy_exchange': best_ask[0],
                    'sell_exchange': best_bid[0],
                    'buy_price': best_ask[1]['ask'],
                    'sell_price': best_bid[1]['bid'],
                    'profit': profit,
                    'volume': min(best_ask[1]['volume'], best_bid[1]['volume'])
                }
            return None
        except Exception as e:
            logger.error(f"Arbitrage search error for {symbol}: {e}")
            return None
