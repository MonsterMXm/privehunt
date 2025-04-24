import logging
from typing import Dict, List, Optional
from config.settings import Config

logger = logging.getLogger(__name__)

class TradingStrategies:
    @staticmethod
    async def triangular_arbitrage(symbols: List[str]) -> Optional[Dict]:
        try:
            if len(symbols) != 3:
                return None
                
            prices = {}
            for symbol in symbols:
                symbol_prices = await exchange_manager.get_prices(symbol)
                if not symbol_prices or 'binance_spot' not in symbol_prices:
                    return None
                prices[symbol] = symbol_prices['binance_spot']['ask']
            
            rate1 = prices[symbols[0]]
            rate2 = prices[symbols[1]]
            rate3 = prices[symbols[2]]
            
            effective_rate = rate1 * rate2 / rate3
            profit = (effective_rate - 1) * 100 - Config.COMMISSION * 3
            
            if profit >= Config.MIN_PROFIT:
                return {
                    'symbols': symbols,
                    'profit': profit,
                    'path': f"{symbols[0]} -> {symbols[1]} -> {symbols[2]}"
                }
            return None
        except Exception as e:
            logger.error(f"Triangular arbitrage error: {e}")
            return None
        
    @staticmethod
    async def funding_rate_arbitrage() -> Optional[Dict]:
        try:
            async with exchange_manager.get_exchange('binance', 'futures') as binance_futures:
                rates = await binance_futures.fetch_funding_rates()
                
                opportunities = []
                for symbol, rate in rates.items():
                    if abs(rate['fundingRate']) > 0.0005:
                        opportunities.append({
                            'symbol': symbol,
                            'rate': rate['fundingRate'],
                            'nextFunding': rate['nextFundingTime']
                        })
                
                return opportunities if opportunities else None
        except Exception as e:
            logger.error(f"Funding rate arbitrage error: {e}")
            return None
        
    @staticmethod
    async def statistical_arbitrage(pair1: str, pair2: str) -> Optional[Dict]:
        try:
            async with exchange_manager.get_exchange('binance', 'spot') as exchange:
                ohlcv1 = await exchange.fetch_ohlcv(pair1, timeframe='1h', limit=100)
                ohlcv2 = await exchange.fetch_ohlcv(pair2, timeframe='1h', limit=100)
                
                closes1 = np.array([x[4] for x in ohlcv1])
                closes2 = np.array([x[4] for x in ohlcv2])
                
                ratio = closes1 / closes2
                mean = np.mean(ratio)
                std = np.std(ratio)
                
                current_ratio = ratio[-1]
                z_score = (current_ratio - mean) / std
                
                if abs(z_score) > 2.0:
                    return {
                        'pair1': pair1,
                        'pair2': pair2,
                        'z_score': z_score,
                        'current_ratio': current_ratio,
                        'mean_ratio': mean,
                        'std_dev': std
                    }
                return None
        except Exception as e:
            logger.error(f"Statistical arbitrage error: {e}")
            return None