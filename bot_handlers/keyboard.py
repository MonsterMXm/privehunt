from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config.settings import Config

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("💰 Купить VIP", callback_data="buy_vip"),
        InlineKeyboardButton("📊 Лидерборд", callback_data="leaderboard"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        InlineKeyboardButton("📈 Анализ рынка", callback_data="market_analysis"),
        InlineKeyboardButton("📊 Мои позиции", callback_data="my_positions"),
        InlineKeyboardButton("🔄 Авто-трейдинг", callback_data="auto_trading"),
        InlineKeyboardButton("🧠 AI Анализ", callback_data="ai_analysis")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_settings_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🔑 API Ключи", callback_data="api_keys"),
        InlineKeyboardButton("📉 Уровень риска", callback_data="risk_level"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")
    ]
    keyboard.add(*buttons)
    return keyboard

def get_risk_level_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=3)
    buttons = [
        InlineKeyboardButton("1", callback_data="set_risk_1"),
        InlineKeyboardButton("2", callback_data="set_risk_2"),
        InlineKeyboardButton("3", callback_data="set_risk_3"),
        InlineKeyboardButton("🔙 Назад", callback_data="settings")
    ]
    keyboard.add(*buttons)
    return keyboard