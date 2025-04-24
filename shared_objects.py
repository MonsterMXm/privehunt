from database.db_manager import db
from exchanges.exchange_manager import ExchangeManager
from analysis.analyzer import AIAnalyzer

exchange_manager = ExchangeManager()
ai_analyzer = AIAnalyzer(exchange_manager)
