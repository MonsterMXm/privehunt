import sqlite3
import logging
import json
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('arbitrage_bot.db', check_same_thread=False)
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                api_keys TEXT DEFAULT '{}',
                vip_until DATETIME DEFAULT NULL,
                free_signals INTEGER DEFAULT 3,
                total_profit REAL DEFAULT 0.0,
                is_admin BOOLEAN DEFAULT FALSE,
                risk_level INTEGER DEFAULT 2,
                auto_trading BOOLEAN DEFAULT FALSE,
                trading_strategy TEXT DEFAULT 'arbitrage'
            );
            
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                exchange TEXT,
                amount REAL,
                entry_price REAL,
                exit_price REAL,
                profit REAL,
                type TEXT CHECK(type IN ('spot', 'futures')),
                direction TEXT CHECK(direction IN ('long', 'short')),
                leverage INTEGER,
                stop_loss REAL,
                take_profit REAL,
                status TEXT CHECK(status IN ('open', 'closed', 'canceled')),
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            
            CREATE TABLE IF NOT EXISTS strategies (
                strategy_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                type TEXT,
                params TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            );
            
            CREATE TABLE IF NOT EXISTS market_data (
                exchange TEXT,
                symbol TEXT,
                bid REAL,
                ask REAL,
                volume REAL,
                last_updated DATETIME,
                PRIMARY KEY (exchange, symbol)
            );
            ''')

    async def execute(self, query: str, params: tuple = ()):
        try:
            with self.conn:
                return self.conn.execute(query, params)
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise

    async def fetch(self, query: str, params: tuple = ()):
        try:
            with self.conn:
                cursor = self.conn.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Database fetch error: {e}")
            raise

    async def get_user_api_keys(self, user_id: int) -> dict:
        """Получение API ключей пользователя"""
        result = await self.fetch(
            "SELECT api_keys FROM users WHERE user_id = ?",
            (user_id,)
        )
        return json.loads(result[0][0]) if result and result[0][0] else {}

    async def update_api_keys(self, user_id: int, api_keys: dict) -> bool:
        """Обновление API ключей пользователя"""
        await self.execute(
            "UPDATE users SET api_keys = ? WHERE user_id = ?",
            (json.dumps(api_keys), user_id)

        )
        return True

db = Database()
