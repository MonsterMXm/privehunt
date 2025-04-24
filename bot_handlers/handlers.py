from aiogram import Router, Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandObject
from aiogram.exceptions import TelegramAPIError
import logging
import json
import numpy as np
from datetime import datetime, timedelta
from config.settings import Config
from database.db_manager import db
from exchanges.exchange_manager import ExchangeManager
from analysis.analyzer import AIAnalyzer
from strategies.auto_strategies import AutoStrategies
from trading.position_manager import PositionManager
from trading.trading_engine import TradingEngine

logger = logging.getLogger(__name__)

# Инициализация сервисов
exchange_manager = ExchangeManager()
trading_engine = TradingEngine(exchange_manager)
analyzer = AIAnalyzer(exchange_manager)
position_manager = PositionManager()
auto_strategies = AutoStrategies(exchange_manager)

router = Router()

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

async def get_user_status(user_id: int) -> dict:
    """Получение статуса пользователя"""
    user_data = await db.fetch(
        "SELECT vip_until, auto_trading, free_signals FROM users WHERE user_id = ?",
        (user_id,)
    )
    if not user_data:
        return None
    
    return {
        'is_vip': user_data[0][0] and datetime.now() < datetime.fromisoformat(user_data[0][0]),
        'auto_trading': user_data[0][1],
        'free_signals': user_data[0][2]
    }

def create_main_keyboard() -> InlineKeyboardMarkup:
    """Создание основной клавиатуры"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("💰 Купить VIP", callback_data="buy_vip"),
        InlineKeyboardButton("📊 Лидерборд", callback_data="leaderboard"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        InlineKeyboardButton("📈 Анализ рынка", callback_data="market_analysis"),
        InlineKeyboardButton("📊 Мои позиции", callback_data="my_positions"),
        InlineKeyboardButton("🤖 Автоторговля", callback_data="auto_trading"),
        InlineKeyboardButton("🧠 AI Анализ", callback_data="ai_analysis"),
        InlineKeyboardButton("💳 Баланс", callback_data="balance"),
        InlineKeyboardButton("📜 История сделок", callback_data="trades"),
        InlineKeyboardButton("🔄 Обновить меню", callback_data="refresh_menu")
    ]
    keyboard.add(*buttons)
    return keyboard

# ==================== КОМАНДЫ БОТА ====================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    try:
        # Проверка и создание пользователя в БД
        user_exists = await db.fetch(
            "SELECT 1 FROM users WHERE user_id = ?",
            (message.from_user.id,))
        
        if not user_exists:
            await db.execute(
                "INSERT INTO users (user_id, api_keys, vip_until, free_signals, total_profit, is_admin, risk_level, auto_trading, trading_strategy) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (message.from_user.id, '{}', None, Config.FREE_SIGNALS, 0.0, False, 2, False, 'arbitrage'))
        
        # Получение данных пользователя
        status = await get_user_status(message.from_user.id)
        
        # Отправка приветственного сообщения
        await message.answer(
            f"🚀 Добро пожаловать, {message.from_user.full_name}!\n\n"
            f"🔹 Ваш статус: {'VIP' if status['is_vip'] else 'Обычный'}\n"
            f"🔹 Автоторговля: {'🟢 ВКЛ' if status['auto_trading'] else '🔴 ВЫКЛ'}\n"
            f"🔹 Доступно сигналов: {status['free_signals']}\n\n"
            "Используйте кнопки ниже для управления ботом:",
            reply_markup=create_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка в команде start: {e}")
        await message.answer("⚠️ Произошла ошибка при запуске бота. Пожалуйста, попробуйте позже.")

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = (
        "📋 Список доступных команд:\n\n"
        "Основные команды:\n"
        "/start - Запуск бота\n"
        "/help - Справка по командам\n"
        "/menu - Главное меню\n\n"
        "Торговые команды:\n"
        "/ai_scan [пара] - AI анализ торговой пары\n"
        "/strategy list - Список стратегий\n"
        "/strategy activate <тип> <пара> [параметры] - Активировать стратегию\n"
        "/strategy deactivate <id> - Деактивировать стратегию\n"
        "/positions - Мои позиции\n"
        "/close [id] - Закрыть позицию\n\n"
        "Баланс и API:\n"
        "/balance - Баланс на биржах\n"
        "/add_api <биржа> <key> <secret> - Добавить API ключи\n\n"
        "Автоторговля:\n"
        "/autotrade on - Включить автоторговлю\n"
        "/autotrade off - Выключить автоторговлю\n"
        "/autotrade strategy <название> - Изменить стратегию\n"
        "/trades - История сделок\n\n"
        "VIP функции:\n"
        "/vip - Информация о VIP статусе\n"
        "/pay_vip - Оплата VIP подписки"
    )
    await message.answer(help_text)

@router.message(Command("menu"))
async def cmd_menu(message: types.Message):
    """Обработчик команды /menu"""
    await cmd_start(message)

@router.message(Command("ai_scan"))
async def cmd_ai_scan(message: types.Message, command: CommandObject):
    """AI анализ торговой пары"""
    try:
        if not command.args:
            return await message.answer("ℹ️ Используйте: /ai_scan BTC/USDT")
        
        symbol = command.args.strip().upper()
        
        if symbol not in Config.TRADING_PAIRS:
            return await message.answer(
                f"⚠️ Пара {symbol} не поддерживается\n\n"
                f"Доступные пары:\n{', '.join(Config.TRADING_PAIRS[:10])}\n..."
            )
        
        await message.answer("🔍 Анализируем рынок...")
        trend = await analyzer.predict_trend(symbol)
        
        report = (
            f"🧠 AI Анализ для {symbol}\n\n"
            f"📊 Тренд: {trend['direction'].upper()}\n"
            f"📈 Уверенность: {trend['confidence']:.0%}\n"
            f"🎯 Цель: {trend['price_target']:.2f} USDT\n\n"
            f"📉 Поддержка: {trend['support']:.2f}\n"
            f"📈 Сопротивление: {trend['resistance']:.2f}\n\n"
            f"🔄 Обновлено: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Открыть график", url=f"https://www.tradingview.com/chart/?symbol={symbol.replace('/', '')}")],
            [InlineKeyboardButton(text="🤖 Автоторговля", callback_data=f"auto_{symbol}")]
        ])
        
        await message.answer(report, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка AI анализа: {e}")
        await message.answer("⚠️ Ошибка анализа. Попробуйте позже")

@router.message(Command("strategy"))
async def cmd_strategy(message: types.Message, command: CommandObject):
    """Управление торговыми стратегиями"""
    try:
        if not command.args:
            return await message.answer(
                "📊 Управление стратегиями\n\n"
                "Доступные команды:\n"
                "/strategy list - Список стратегий\n"
                "/strategy activate <тип> <пара> [параметры] - Активировать\n"
                "/strategy deactivate <id> - Деактивировать\n\n"
                "Примеры:\n"
                "/strategy activate grid BTC/USDT 50000 60000\n"
                "/strategy activate rsi ETH/USDT 30 70"
            )
        
        args = command.args.split()
        subcommand = args[0].lower()
        
        if subcommand == "list":
            strategies = await db.fetch(
                "SELECT strategy_id, strategy_type, symbol, params FROM strategies WHERE user_id = ?",
                (message.from_user.id,))
            
            if not strategies:
                return await message.answer("ℹ️ У вас нет активных стратегий")
            
            response = "📊 Ваши активные стратегии:\n\n"
            for strat in strategies:
                params = json.loads(strat[3])
                response += (
                    f"🔹 ID: {strat[0]}\n"
                    f"Тип: {strat[1]}\n"
                    f"Пара: {strat[2]}\n"
                    f"Параметры: {params}\n\n"
                )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"❌ Удалить {strat[0]}", callback_data=f"del_strat_{strat[0]}") for strat in strategies]
            ])
            
            await message.answer(response, reply_markup=keyboard)
            
        elif subcommand == "activate":
            if len(args) < 3:
                return await message.answer("ℹ️ Формат: /strategy activate <тип> <пара> [параметры]")
            
            strategy_type = args[1].lower()
            symbol = args[2].upper()
            
            if strategy_type == "grid":
                if len(args) != 5:
                    return await message.answer("ℹ️ Для grid стратегии укажите: /strategy activate grid BTC/USDT 50000 60000")
                
                try:
                    lower = float(args[3])
                    upper = float(args[4])
                    
                    result = await auto_strategies.grid_trading(
                        user_id=message.from_user.id,
                        symbol=symbol,
                        lower=lower,
                        upper=upper
                    )
                    
                    if result['status'] == 'activated':
                        await message.answer(
                            f"✅ Сеточная стратегия активирована для {symbol}\n"
                            f"Диапазон: {lower} - {upper} USDT\n"
                            f"Количество ордеров: {result.get('grids', 5)}"
                        )
                    else:
                        await message.answer(f"⚠️ Ошибка: {result['message']}")
                except ValueError:
                    await message.answer("⚠️ Неверные параметры. Используйте числа для цен")
            
            elif strategy_type == "rsi":
                if len(args) != 5:
                    return await message.answer("ℹ️ Для RSI стратегии укажите: /strategy activate rsi BTC/USDT 30 70")
                
                try:
                    oversold = int(args[3])
                    overbought = int(args[4])
                    
                    await db.execute(
                        "INSERT INTO strategies (user_id, strategy_type, symbol, params) VALUES (?, ?, ?, ?)",
                        (message.from_user.id, 'rsi', symbol, json.dumps({
                            'oversold': oversold,
                            'overbought': overbought
                        })))
                    
                    await message.answer(
                        f"✅ RSI стратегия активирована для {symbol}\n"
                        f"Уровни: oversold={oversold}, overbought={overbought}"
                    )
                except ValueError:
                    await message.answer("⚠️ Неверные параметры. Используйте целые числа для уровней RSI")
            
            else:
                await message.answer("⚠️ Неподдерживаемый тип стратегии. Доступно: grid, rsi")
                
        elif subcommand == "deactivate":
            if len(args) != 2:
                return await message.answer("ℹ️ Формат: /strategy deactivate <id>")
            
            try:
                strategy_id = int(args[1])
                await db.execute(
                    "DELETE FROM strategies WHERE user_id = ? AND strategy_id = ?",
                    (message.from_user.id, strategy_id))
                
                await message.answer(f"✅ Стратегия #{strategy_id} деактивирована")
            except ValueError:
                await message.answer("⚠️ Неверный ID стратегии. Используйте число")
        
        else:
            await message.answer("⚠️ Неизвестная подкоманда. Используйте: list, activate, deactivate")
            
    except Exception as e:
        logger.error(f"Ошибка в команде strategy: {e}")
        await message.answer("⚠️ Ошибка обработки стратегии. Попробуйте позже")

@router.message(Command("positions"))
async def cmd_positions(message: types.Message):
    """Просмотр открытых позиций"""
    try:
        positions = await position_manager.get_open_positions(message.from_user.id)
        
        if not positions:
            return await message.answer("ℹ️ У вас нет открытых позиций")
        
        response = "📊 Ваши открытые позиции:\n\n"
        for pos in positions:
            response += (
                f"🔹 #{pos['position_id']} {pos['symbol']}\n"
                f"Тип: {'Лонг' if pos['direction'] == 'long' else 'Шорт'}\n"
                f"Объем: {pos['amount']:.4f}\n"
                f"Цена входа: {pos['entry_price']:.2f}\n"
                f"Текущая цена: {pos['current_price']:.2f}\n"
                f"P&L: {pos['pnl']:.2f} USDT ({pos['pnl_percent']:.2f}%)\n\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_positions")]
        ])
        
        await message.answer(response, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка получения позиций: {e}")
        await message.answer("⚠️ Ошибка получения позиций. Попробуйте позже")

@router.message(Command("close"))
async def cmd_close(message: types.Message):
    """Закрытие позиции"""
    try:
        args = message.text.split()
        
        if len(args) != 2:
            return await message.answer(
                "ℹ️ Формат команды:\n"
                "/close <id_позиции>\n\n"
                "Пример:\n"
                "/close 5"
            )
        
        try:
            position_id = int(args[1])
            success = await position_manager.close_position(message.from_user.id, position_id)
            
            if success:
                await message.answer(f"✅ Позиция #{position_id} закрыта")
            else:
                await message.answer(f"⚠️ Не удалось закрыть позицию #{position_id}")
        except ValueError:
            await message.answer("⚠️ Неверный ID позиции. Используйте число")
            
    except Exception as e:
        logger.error(f"Ошибка закрытия позиции: {e}")
        await message.answer("⚠️ Ошибка закрытия позиции. Попробуйте позже")

@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    """Просмотр баланса на биржах"""
    try:
        user_data = await db.fetch(
            "SELECT api_keys FROM users WHERE user_id = ?",
            (message.from_user.id,))
        
        if not user_data or not user_data[0][0]:
            return await message.answer(
                "ℹ️ API ключи не настроены\n\n"
                "Используйте /add_api для добавления ключей бирж"
            )
        
        api_keys = json.loads(user_data[0][0])
        if not api_keys:
            return await message.answer("ℹ️ API ключи не настроены")
        
        await message.answer("🔄 Запрашиваю балансы...")
        
        balances = {}
        for exchange_name in api_keys:
            try:
                async with exchange_manager.get_exchange(exchange_name) as exchange:
                    exchange.apiKey = api_keys[exchange_name]['key']
                    exchange.secret = api_keys[exchange_name]['secret']
                    
                    balance = await exchange.fetch_balance()
                    usdt_balance = balance['total'].get('USDT', 0)
                    balances[exchange_name] = usdt_balance
            except Exception as e:
                logger.error(f"Ошибка получения баланса {exchange_name}: {e}")
                balances[exchange_name] = "Ошибка"
        
        response = "💰 Ваши балансы:\n\n"
        for exchange, balance in balances.items():
            response += f"{exchange.upper()}: {balance if isinstance(balance, str) else f'{balance:.2f} USDT'}\n"
        
        response += "\n🔄 Обновлено: " + datetime.now().strftime("%H:%M %d.%m.%Y")
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_balance")]
        ])
        
        await message.answer(response, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка получения балансов: {e}")
        await message.answer("⚠️ Ошибка получения балансов. Попробуйте позже")

@router.message(Command("add_api"))
async def cmd_add_api(message: types.Message):
    """Добавление API ключей биржи"""
    try:
        args = message.text.split()
        
        if len(args) != 4:
            return await message.answer(
                "ℹ️ Формат команды:\n"
                "/add_api <биржа> <api_key> <api_secret>\n\n"
                "Пример:\n"
                "/add_api binance d1a2b3c4d5 e6f7g8h9i0\n\n"
                "Поддерживаемые биржи: binance, bybit, kucoin, okx"
            )
        
        exchange = args[1].lower()
        api_key = args[2]
        api_secret = args[3]
        
        if exchange not in ['binance', 'bybit', 'kucoin', 'okx']:
            return await message.answer(
                "⚠️ Неподдерживаемая биржа\n\n"
                "Доступные: binance, bybit, kucoin, okx"
            )
        
        user_data = await db.fetch(
            "SELECT api_keys FROM users WHERE user_id = ?",
            (message.from_user.id,))
        
        current_keys = json.loads(user_data[0][0]) if user_data and user_data[0][0] else {}
        current_keys[exchange] = {
            'key': api_key,
            'secret': api_secret
        }
        
        await db.execute(
            "UPDATE users SET api_keys = ? WHERE user_id = ?",
            (json.dumps(current_keys), message.from_user.id))
        
        await message.answer(
            f"✅ API ключи для {exchange.upper()} добавлены\n\n"
            "Рекомендации по безопасности:\n"
            "• Ограничьте права ключей\n"
            "• Включите IP-фильтрацию\n"
            "• Никому не передавайте ключи"
        )
    except Exception as e:
        logger.error(f"Ошибка добавления API: {e}")
        await message.answer(
            "⚠️ Ошибка добавления API ключей\n\n"
            "Проверьте:\n"
            "1. Правильность ввода\n"
            "2. Поддержку биржи\n"
            "3. Попробуйте снова"
        )

@router.message(Command("autotrade"))
async def cmd_autotrade(message: types.Message):
    """Управление автоторговлей"""
    try:
        args = message.text.split()
        
        if len(args) < 2:
            user_data = await db.fetch(
                "SELECT auto_trading, trading_strategy FROM users WHERE user_id = ?",
                (message.from_user.id,))
            
            if not user_data:
                return await message.answer("ℹ️ Профиль не найден. Используйте /start")
            
            status = "🟢 ВКЛ" if user_data[0][0] else "🔴 ВЫКЛ"
            strategy = user_data[0][1] or 'не выбрана'
            
            return await message.answer(
                f"🤖 Статус автоторговли\n\n"
                f"Состояние: {status}\n"
                f"Стратегия: {strategy}\n\n"
                "Команды:\n"
                "/autotrade on - Включить\n"
                "/autotrade off - Выключить\n"
                "/autotrade strategy <название> - Изменить стратегию\n\n"
                "Доступные стратегии:\n"
                "- arbitrage (арбитраж)\n"
                "- trend (тренд)\n"
                "- scalping (скальпинг)"
            )
        
        subcommand = args[1].lower()
        
        if subcommand == "on":
            await db.execute(
                "UPDATE users SET auto_trading = TRUE WHERE user_id = ?",
                (message.from_user.id,))
            await message.answer(
                "✅ Автоторговля включена\n\n"
                "Бот будет автоматически:\n"
                "• Анализировать рынок\n"
                "• Открывать/закрывать позиции\n"
                "• Управлять рисками"
            )
            
        elif subcommand == "off":
            await db.execute(
                "UPDATE users SET auto_trading = FALSE WHERE user_id = ?",
                (message.from_user.id,))
            await message.answer(
                "🛑 Автоторговля выключена\n\n"
                "Текущие позиции остаются открытыми"
            )
            
        elif subcommand == "strategy" and len(args) > 2:
            strategy = args[2].lower()
            
            if strategy not in ['arbitrage', 'trend', 'scalping']:
                return await message.answer(
                    "⚠️ Неподдерживаемая стратегия\n\n"
                    "Доступные:\n"
                    "- arbitrage\n"
                    "- trend\n"
                    "- scalping"
                )
            
            await db.execute(
                "UPDATE users SET trading_strategy = ? WHERE user_id = ?",
                (strategy, message.from_user.id))
            
            await message.answer(f"✅ Стратегия изменена на: {strategy}")
            
        else:
            await message.answer(
                "⚠️ Неизвестная команда\n\n"
                "Используйте:\n"
                "/autotrade on\n"
                "/autotrade off\n"
                "/autotrade strategy <название>"
            )
            
    except Exception as e:
        logger.error(f"Ошибка управления автоторговлей: {e}")
        await message.answer("⚠️ Ошибка обработки команды. Попробуйте позже")

@router.message(Command("trades"))
async def cmd_trades(message: types.Message):
    """История сделок"""
    try:
        trades = await db.fetch(
            "SELECT trade_id, symbol, amount, entry_price, exit_price, profit, status, timestamp "
            "FROM trades WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10",
            (message.from_user.id,))
        
        if not trades:
            return await message.answer("ℹ️ История сделок пуста")
        
        response = "📜 Последние 10 сделок:\n\n"
        for trade in trades:
            response += (
                f"🔹 #{trade[0]} {trade[1]}\n"
                f"Объем: {trade[2]:.4f}\n"
                f"Вход: {trade[3]:.2f}\n"
                f"Выход: {trade[4]:.2f if trade[4] else '-'}\n"
                f"Прибыль: {trade[5]:.2f if trade[5] else '-'}\n"
                f"Статус: {'закрыта' if trade[6] == 'closed' else 'открыта'}\n"
                f"Время: {trade[7][:16]}\n\n"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_trades")]
        ])
        
        await message.answer(response, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка получения сделок: {e}")
        await message.answer("⚠️ Ошибка получения истории сделок. Попробуйте позже")

@router.message(Command("vip"))
async def cmd_vip(message: types.Message):
    """Информация о VIP статусе"""
    try:
        user_data = await db.fetch(
            "SELECT vip_until FROM users WHERE user_id = ?",
            (message.from_user.id,))
        
        if not user_data:
            return await message.answer("ℹ️ Профиль не найден. Используйте /start")
        
        vip_until = user_data[0][0]
        is_vip = vip_until and datetime.now() < datetime.fromisoformat(vip_until)
        
        if is_vip:
            days_left = (datetime.fromisoformat(vip_until) - datetime.now()).days
            response = (
                f"💎 Ваш VIP статус активен\n\n"
                f"Действует до: {vip_until[:10]}\n"
                f"Осталось дней: {days_left}\n\n"
                "Преимущества VIP:\n"
                "• Неограниченные сигналы\n"
                "• Приоритетные стратегии\n"
                "• Персональная поддержка"
            )
        else:
            response = (
                "🔒 У вас нет VIP подписки\n\n"
                f"Стоимость: {Config.VIP_PRICE} USDT/месяц\n\n"
                "Преимущества:\n"
                "• Неограниченные сигналы\n"
                "• Приоритетные стратегии\n"
                "• Персональная поддержка\n\n"
                "Для оплаты используйте /pay_vip"
            )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить VIP", callback_data="pay_vip")]
        ]) if not is_vip else None
        
        await message.answer(response, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка проверки VIP: {e}")
        await message.answer("⚠️ Ошибка проверки статуса. Попробуйте позже")

@router.message(Command("pay_vip"))
async def cmd_pay_vip(message: types.Message):
    """Оплата VIP подписки"""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить 1 месяц", callback_data="vip_1_month")],
            [InlineKeyboardButton(text="💎 Оплатить 3 месяца (-15%)", callback_data="vip_3_months")],
            [InlineKeyboardButton(text="👑 Оплатить 12 месяцев (-30%)", callback_data="vip_12_months")]
        ])
        
        await message.answer(
            f"💎 VIP подписка\n\n"
            f"1 месяц: {Config.VIP_PRICE} USDT\n"
            f"3 месяца: {Config.VIP_PRICE * 3 * 0.85:.2f} USDT (-15%)\n"
            f"12 месяцев: {Config.VIP_PRICE * 12 * 0.7:.2f} USDT (-30%)\n\n"
            "Выберите вариант оплаты:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка оплаты VIP: {e}")
        await message.answer("⚠️ Ошибка формирования оплаты. Попробуйте позже")


# ==================== CALLBACK ОБРАБОТЧИКИ ====================

@router.callback_query(F.data == "refresh_menu")
async def callback_refresh_menu(callback: types.CallbackQuery):
    """Обновление главного меню"""
    try:
        await callback.answer("Меню обновлено")
        await cmd_start(callback.message)
    except Exception as e:
        logger.error(f"Ошибка обновления меню: {e}")
        await callback.message.answer("⚠️ Ошибка обновления")

@router.callback_query(F.data.startswith("del_strat_"))
async def callback_delete_strategy(callback: types.CallbackQuery):
    """Удаление стратегии"""
    try:
        strat_id = int(callback.data.split("_")[2])
        await db.execute(
            "DELETE FROM strategies WHERE user_id = ? AND strategy_id = ?",
            (callback.from_user.id, strat_id))
        
        await callback.answer(f"Стратегия #{strat_id} удалена")
        await callback.message.edit_text(
            text=f"✅ Стратегия #{strat_id} успешно удалена",
            reply_markup=None
        )
    except Exception as e:
        logger.error(f"Ошибка удаления стратегии: {e}")
        await callback.answer("⚠️ Ошибка удаления")

@router.callback_query(F.data == "buy_vip")
async def callback_buy_vip(callback: types.CallbackQuery):
    """Обработка кнопки покупки VIP"""
    try:
        await callback.answer()
        await cmd_pay_vip(callback.message)
    except Exception as e:
        logger.error(f"Ошибка callback buy_vip: {e}")
        await callback.message.answer("⚠️ Ошибка обработки запроса")

@router.callback_query(F.data.startswith("vip_"))
async def callback_pay_vip(callback: types.CallbackQuery):
    """Обработка выбора VIP подписки"""
    try:
        await callback.answer()
        
        plan = callback.data.split('_')[1]
        months = int(plan.split('_')[0])
        
        price = Config.VIP_PRICE * months
        if months == 3:
            price *= 0.85
        elif months == 12:
            price *= 0.7
        
        # Здесь должна быть логика оплаты (например, генерация счета)
        # Для примера просто сохраняем подписку
        vip_until = (datetime.now() + timedelta(days=30*months)).isoformat()
        await db.execute(
            "UPDATE users SET vip_until = ? WHERE user_id = ?",
            (vip_until, callback.from_user.id))
        
        await callback.message.answer(
            f"✅ VIP подписка активирована на {months} месяцев\n\n"
            f"Действует до: {vip_until[:10]}\n"
            "Теперь вам доступны все VIP функции!"
        )
    except Exception as e:
        logger.error(f"Ошибка callback pay_vip: {e}")
        await callback.message.answer("⚠️ Ошибка активации подписки")

@router.callback_query(F.data == "refresh_positions")
async def callback_refresh_positions(callback: types.CallbackQuery):
    """Обновление списка позиций"""
    try:
        await callback.answer("Обновление...")
        await cmd_positions(callback.message)
    except Exception as e:
        logger.error(f"Ошибка обновления позиций: {e}")
        await callback.message.answer("⚠️ Ошибка обновления")

@router.callback_query(F.data == "refresh_balance")
async def callback_refresh_balance(callback: types.CallbackQuery):
    """Обновление балансов"""
    try:
        await callback.answer("Обновление...")
        await cmd_balance(callback.message)
    except Exception as e:
        logger.error(f"Ошибка обновления балансов: {e}")
        await callback.message.answer("⚠️ Ошибка обновления")

@router.callback_query(F.data == "refresh_trades")
async def callback_refresh_trades(callback: types.CallbackQuery):
    """Обновление истории сделок"""
    try:
        await callback.answer("Обновление...")
        await cmd_trades(callback.message)
    except Exception as e:
        logger.error(f"Ошибка обновления сделок: {e}")
        await callback.message.answer("⚠️ Ошибка обновления")

@router.callback_query(F.data == "market_analysis")
async def callback_market_analysis(callback: types.CallbackQuery):
    """Анализ рынка"""
    try:
        await callback.answer()
        await message.answer(
            "📈 Текущая рыночная ситуация:\n\n"
            "BTC/USDT: +2.3% за сутки\n"
            "ETH/USDT: +1.1% за сутки\n"
            "Общий объем: $42.5B\n\n"
            "Рекомендация: нейтральный рынок"
        )
    except Exception as e:
        logger.error(f"Ошибка анализа рынка: {e}")
        await callback.message.answer("⚠️ Ошибка анализа")

@router.callback_query(F.data == "leaderboard")
async def callback_leaderboard(callback: types.CallbackQuery):
    """Топ пользователей по прибыли"""
    try:
        await callback.answer()
        top_users = await db.fetch(
            "SELECT user_id, total_profit FROM users ORDER BY total_profit DESC LIMIT 10"
        )
        response = "🏆 Топ пользователей:\n\n"
        for i, (user_id, profit) in enumerate(top_users, 1):
            user = await callback.message.bot.get_chat(user_id)
            name = user.full_name if user else f"ID {user_id}"
            response += f"{i}. {name}: {profit:.2f} USDT\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="leaderboard")]
        ])
        
        await callback.message.answer(response, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка leaderboard: {e}")
        await callback.message.answer("⚠️ Ошибка загрузки топа")

@router.callback_query(F.data == "settings")
async def callback_settings(callback: types.CallbackQuery):
    """Настройки пользователя"""
    try:
        await callback.answer()
        user_data = await db.fetch(
            "SELECT risk_level, auto_trading, trading_strategy FROM users WHERE user_id = ?",
            (callback.from_user.id,)
        )
        
        if not user_data:
            return await callback.message.answer("ℹ️ Профиль не найден. Используйте /start")
        
        risk_level = user_data[0][0]
        auto_trading = "🟢 ВКЛ" if user_data[0][1] else "🔴 ВЫКЛ"
        strategy = user_data[0][2] or "не выбрана"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📉 Уровень риска", callback_data="set_risk"),
                InlineKeyboardButton(text="🤖 Автоторговля", callback_data="toggle_auto")
            ],
            [
                InlineKeyboardButton(text="📈 Стратегия", callback_data="set_strategy"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="menu")
            ]
        ])
        
        await callback.message.answer(
            f"⚙️ Ваши настройки:\n\n"
            f"• Уровень риска: {risk_level}/5\n"
            f"• Автоторговля: {auto_trading}\n"
            f"• Стратегия: {strategy}\n\n"
            "Измените параметры:",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка настроек: {e}")
        await callback.message.answer("⚠️ Ошибка загрузки настроек")

@router.callback_query(F.data == "my_positions")
async def callback_my_positions(callback: types.CallbackQuery):
    """Мои позиции (аналогично /positions)"""
    try:
        await callback.answer()
        await cmd_positions(callback.message)
    except Exception as e:
        logger.error(f"Ошибка позиций: {e}")
        await callback.message.answer("⚠️ Ошибка загрузки позиций")

@router.callback_query(F.data == "auto_trading")
async def callback_auto_trading(callback: types.CallbackQuery):
    """Управление автоторговлей (аналогично /autotrade)"""
    try:
        await callback.answer()
        await cmd_autotrade(callback.message)
    except Exception as e:
        logger.error(f"Ошибка автоторговли: {e}")
        await callback.message.answer("⚠️ Ошибка загрузки настроек")

@router.callback_query(F.data == "ai_analysis")
async def callback_ai_analysis(callback: types.CallbackQuery):
    """AI анализ (аналогично /ai_scan)"""
    try:
        await callback.answer()
        await callback.message.answer(
            "🔍 Введите пару для анализа, например:\n"
            "<code>BTC/USDT</code>\n\n"
            "Доступные пары: " + ", ".join(Config.TRADING_PAIRS[:5]) + "..."
        )
    except Exception as e:
        logger.error(f"Ошибка AI анализа: {e}")
        await callback.message.answer("⚠️ Ошибка запуска анализа")

# Дополнительные обработчики для настроек
@router.callback_query(F.data == "toggle_auto")
async def callback_toggle_auto(callback: types.CallbackQuery):
    """Переключение автоторговли"""
    try:
        await callback.answer()
        user_data = await db.fetch(
            "SELECT auto_trading FROM users WHERE user_id = ?",
            (callback.from_user.id,))
        
        new_status = not user_data[0][0]
        await db.execute(
            "UPDATE users SET auto_trading = ? WHERE user_id = ?",
            (new_status, callback.from_user.id))
        
        status = "🟢 ВКЛЮЧЕНА" if new_status else "🔴 ВЫКЛЮЧЕНА"
        await callback.message.answer(f"Автоторговля: {status}")
        await callback_settings(callback)  # Обновляем меню
    except Exception as e:
        logger.error(f"Ошибка переключения автоторговли: {e}")
        await callback.message.answer("⚠️ Ошибка изменения настроек")

@router.callback_query(F.data == "set_risk")
async def callback_set_risk(callback: types.CallbackQuery):
    """Изменение уровня риска"""
    try:
        await callback.answer()
        keyboard = InlineKeyboardMarkup(row_width=5)
        buttons = [
            InlineKeyboardButton(text=str(i), callback_data=f"risk_{i}") 
            for i in range(1, 6)
        ]
        keyboard.add(*buttons)
        await callback.message.answer("📉 Выберите уровень риска (1-5):", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка выбора риска: {e}")
        await callback.message.answer("⚠️ Ошибка настройки риска")

@router.callback_query(F.data.startswith("risk_"))
async def callback_save_risk(callback: types.CallbackQuery):
    """Сохранение уровня риска"""
    try:
        risk_level = int(callback.data.split("_")[1])
        await db.execute(
            "UPDATE users SET risk_level = ? WHERE user_id = ?",
            (risk_level, callback.from_user.id))
        
        await callback.answer(f"Уровень риска: {risk_level}")
        await callback_settings(callback)  # Возврат в меню
    except Exception as e:
        logger.error(f"Ошибка сохранения риска: {e}")
        await callback.message.answer("⚠️ Ошибка сохранения")

# ==================== ОБРАБОТЧИКИ ОШИБОК ====================

@router.errors()
async def errors_handler(update: types.Update, exception: Exception):
    """Глобальный обработчик ошибок"""
    logger.error(f"Ошибка обработки update {update}: {exception}")
    
    if isinstance(update, types.Message) and update.from_user:
        try:
            await update.answer(
                "⚠️ Произошла ошибка обработки запроса\n"
                "Попробуйте позже или обратитесь в поддержку"
            )
        except:
            pass
    
    return True
