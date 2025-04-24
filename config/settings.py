import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    ADMIN_IDS = {1327614730}  # Ваш Telegram ID
    BOT_VERSION = "1.0"
    CRYPTO_PANIC_API = os.getenv("CRYPTO_PANIC_API_KEY")
    VIP_PRICE = 50  # $ в месяц
    FREE_SIGNALS = 3
    MIN_PROFIT = 0.3  # Минимальный процент прибыли
    COMMISSION = 0.2  # Общая комиссия
    DEFAULT_LEVERAGE = 10  # Плечо по умолчанию для фьючерсов
    AI_MODEL_NAME = "finiteautomata/bertweet-base-sentiment-analysis"
    EXCHANGES = ["binance", "bybit", "bingx"]
    MIN_ORDER_SIZE = 10  # Минимальный размер ордера в USDT
    MAX_ORDER_SIZE = 10000  # Максимальный размер ордера в USDT
    MIN_ARBITRAGE_VOLUME = 1000 #Минимальный объем для арбитража (USDT)
    MAX_RETRIES = 3  # Максимальное количество попыток для API запросов
    RETRY_DELAY = 1.5  # Задержка между попытками в секундах
    MAX_LEVERAGE = {
        'binance': 20,
        'bybit': 100,
        'bingx': 50,
        'kucoin': 10,
        'okx': 5
        }
    
    TRADING_PAIRS = [
        "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
        "ADA/USDT", "DOGE/USDT", "DOT/USDT", "SHIB/USDT", "MATIC/USDT",
        "AVAX/USDT", "LINK/USDT", "ATOM/USDT", "UNI/USDT", "XLM/USDT",
        "LTC/USDT", "ICP/USDT", "FIL/USDT", "ETC/USDT", "XMR/USDT",
        "SAND/USDT", "MANA/USDT", "GALA/USDT", "APE/USDT", "AXS/USDT",
        "BTC/USDT:USDT", "ETH/USDT:USDT", "BNB/USDT:USDT", "SOL/USDT:USDT"
    ]
