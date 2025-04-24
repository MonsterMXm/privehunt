import logging
from aiogram.exceptions import TelegramAPIError
from config.settings import Config
from database.db_manager import db
from typing import Dict

logger = logging.getLogger(__name__)

async def notify_users(opportunity: Dict):
    try:
        text = (
            f"🔔 Новая арбитражная возможность!\n\n"
            f"Пара: {opportunity['symbol']}\n"
            f"Прибыль: {opportunity['profit']:.2f}%\n"
            f"Купить на: {opportunity['buy_exchange']}\n"
            f"Продать на: {opportunity['sell_exchange']}\n\n"
            f"Используйте /check {opportunity['symbol']} для деталей"
        )
        
        vip_users = await db.fetch(
            "SELECT user_id FROM users WHERE vip_until > datetime('now')"
        )
        for (user_id,) in vip_users:
            try:
                await bot.send_message(user_id, text)
            except TelegramAPIError:
                continue
        
        free_users = await db.fetch(
            "SELECT user_id FROM users WHERE free_signals > 0 AND (vip_until IS NULL OR vip_until <= datetime('now'))"
        )
        for (user_id,) in free_users:
            try:
                await bot.send_message(user_id, text)
                await db.execute(
                    "UPDATE users SET free_signals = free_signals - 1 WHERE user_id = ?",
                    (user_id,)
                )
            except TelegramAPIError:
                continue
    except Exception as e:
        logger.error(f"Notification error: {e}")
