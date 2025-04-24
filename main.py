import platform
import asyncio
import logging
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.settings import Config
from database.db_manager import Database
from exchanges.exchange_manager import ExchangeManager
from tasks.monitoring import monitor_markets
from tasks.backups import backup_database
from bot_handlers.handlers import router
from aiogram.fsm.storage.memory import MemoryStorage
from trading.position_manager import PositionManager
# Настройка цикла событий для Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Конфигурация логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация основных компонентов
bot = Bot(token=Config.TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)
exchange_manager = ExchangeManager()
position_manager = PositionManager(exchange_manager)
scheduler = AsyncIOScheduler()
db = Database()

async def on_startup():
    """Функция инициализации при запуске бота"""
    try:
        # Настройка периодических задач
        scheduler.add_job(monitor_markets, 'interval', minutes=1, args=[exchange_manager])
        scheduler.add_job(backup_database, 'interval', hours=6)
        scheduler.start()
        
        # Уведомление администраторов
        for admin_id in Config.ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    "🤖 Бот успешно запущен\n\n"
                    f"Версия: {Config.BOT_VERSION}\n"
                    f"Мониторинг {len(Config.TRADING_PAIRS)} пар\n"
                    "Статус: все системы работают нормально"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")

async def on_shutdown():
    """Функция завершения работы"""
    try:
        await exchange_manager.close_all()
        await bot.get_session.close()
        scheduler.shutdown()
        logger.info("Бот успешно завершил работу")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")

async def main():
    """Основная функция запуска бота"""
    await on_startup()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка в работе бота: {e}")
    finally:
        await on_shutdown()

if __name__ == '__main__':
    asyncio.run(main())
