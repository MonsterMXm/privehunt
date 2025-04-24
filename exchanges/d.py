import asyncio
import logging
import ccxt
import contextlib
from typing import Dict, Optional
from ccxt.async_support import (binance, kucoin, bybit, okx)
from config.settings import Config

logger = logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self):
        self.exchanges = {
            'binance': {'spot': binance(), 'futures': binance({'options': {'defaultType': 'future'}})},
            'bybit': {'spot': bybit(), 'futures': bybit({'options': {'defaultType': 'future'}})},
            'okx': {'spot': okx(), 'futures': okx({'options': {'defaultType': 'future'}})},
            'kucoin': {'spot': kucoin(), 'futures': kucoin({'options': {'defaultType': 'future'}})}
            'bingx': {'spot': ccxt.bingx(), 'futures': ccxt.bingx({'options': {'defaultType': 'future'}})}
        }
        self.active_connections = set()

    @contextlib.asynccontextmanager
    async def get_exchange(self, exchange: str, ex_type: str):
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
                            'volume': ticker['baseVolume'],
                            'type': ex_type
                        }
                        break
                    except Exception as e:
                        if attempt == Config.MAX_RETRIES - 1:
                            logger.error(f"Error getting price from {ex_name} ({ex_type}): {e}")
                        await asyncio.sleep(Config.RETRY_DELAY)
        return prices

    async def create_order(self, exchange: str, symbol: str, order_type: str, 
                         side: str, amount: float, price: float = None, 
                         params: Dict = None, leverage: int = None) -> Optional[Dict]:
        try:
            ex_type = 'futures' if ':USDT' in symbol else 'spot'
            if ex_type not in self.exchanges.get(exchange, {}):
                return None
                
            if price and (amount * price) < Config.MIN_ORDER_SIZE:
                logger.warning(f"Order size too small: {amount * price} < {Config.MIN_ORDER_SIZE}")
                return None
                
            async with self.get_exchange(exchange, ex_type) as exchange_instance:
                for attempt in range(Config.MAX_RETRIES):
                    try:
                        if side == 'buy':
                            balance = await exchange_instance.fetch_balance()
                            if balance['free'].get('USDT', 0) < amount * (price or 1):
                                logger.warning("Insufficient USDT balance")
                                return None
                                
                        return await exchange_instance.create_order(
                            symbol, order_type, side, amount, price, params
                        )
                    except ccxt.InsufficientFunds as e:
                        logger.error(f"Insufficient funds: {e}")
                        return None
                    except ccxt.NetworkError as e:
                        if attempt == Config.MAX_RETRIES - 1:
                            logger.error(f"Network error on {exchange}: {e}")
                            return None
                        await asyncio.sleep(Config.RETRY_DELAY)
                    except Exception as e:
                        logger.error(f"Order error on {exchange}: {e}")
                        return None
        except Exception as e:
            logger.error(f"Exchange error: {e}")
            return None

    async def close_all(self):
        for exchange in list(self.active_connections):
            try:
                await exchange.close()
                self.active_connections.discard(exchange)
            except Exception as e:
                logger.error(f"Error closing exchange: {e}")
                async def get_trader_positions(self, exchange: str, trader_id: str) -> list:
    """Получение сделок трейдера для копирования"""
    async with self.get_exchange(exchange, 'futures') as ex:
        try:
            # Для BingX/Bybit используем их API для копирования
            if exchange == 'bingx':
                return await ex.fetch_positions(trader_id)
            elif exchange == 'bybit':
                return await ex.fetch_trader_orders(trader_id)
            else:
                logger.warning(f"Copy trading not supported for {exchange}")
                return []
        except Exception as e:
            logger.error(f"Error fetching trader data: {e}")
            return []

async def copy_position(self, source_ex: str, target_ex: str, position: dict):
    """Копирование позиции между биржами"""
    symbol = position['symbol']
    amount = position['amount']
    direction = position['side']
    
    async with self.get_exchange(target_ex, 'futures') as ex:
        try:
            return await ex.create_order(
                symbol=symbol,
                type='market',
                side=direction,
                amount=amount,
                params={'copy_trade': True}
            )
        except Exception as e:
            logger.error(f"Copy trade failed: {e}")
            return None
