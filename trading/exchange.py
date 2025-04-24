class ExchangeManager:
       def __init__(self):
           self.exchanges = {}

       async def get_exchange(self, exchange_name: str):
           import ccxt
           return getattr(ccxt, exchange_name)()