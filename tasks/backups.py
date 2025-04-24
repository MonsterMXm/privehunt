import logging
from datetime import datetime
import os

logger = logging.getLogger(__name__)

async def backup_database():
    try:
        os.makedirs("backup", exist_ok=True)
        backup_file = f"backup/arbitrage_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        with open(backup_file, 'wb') as f:
            with open('arbitrage_bot.db', 'rb') as original:
                f.write(original.read())
        logger.info(f"Database backup created: {backup_file}")
    except Exception as e:
        logger.error(f"Backup error: {e}")