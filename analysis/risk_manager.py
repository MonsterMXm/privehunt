import numpy as np
import logging
from typing import Dict
from config.settings import Config
from exchanges.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, exchange_manager: ExchangeManager):
         self.exchange_manager = exchange_manager
         
    async def validate_opportunity(self, opportunity: Dict) -> bool:
        try:
            if opportunity['volume'] < 10000:
                logger.info(f"Low volume for {opportunity['symbol']}")
                return False
                
            if opportunity['profit'] > 5.0:
                logger.warning(f"Suspicious high profit for {opportunity['symbol']}")
                return False
                
            volatility = await self.calculate_volatility(opportunity['symbol'])
            if volatility > 10.0:
                logger.info(f"High volatility for {opportunity['symbol']}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Opportunity validation error: {e}")
            return False

    async def calculate_volatility(self, symbol: str, period: str = '1h') -> float:
        try:
            async with self.exchange_manager.get_exchange('binance', 'spot') as exchange:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe=period, limit=24)
                closes = [x[4] for x in ohlcv]
                returns = np.diff(closes) / closes[:-1]
                return np.std(returns) * 100 * np.sqrt(24)
        except Exception as e:
            logger.error(f"Volatility calc error: {e}")
            return 0.0
