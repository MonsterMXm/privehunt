import numpy as np
import logging
from typing import Dict
from transformers import pipeline
from config.settings import Config

logger = logging.getLogger(__name__)

class AIAnalyzer:
    def __init__(self, exchange_manager):
        self.exchange_manager = exchange_manager
        try:
            self.sentiment_analyzer = pipeline(
                "text-classification", 
                model=Config.AI_MODEL_NAME,
                device='cpu'
              )
            
        except Exception as e:
            logger.error(f"Failed to load AI model: {e}")
            raise

    async def analyze_sentiment(self, text: str) -> float:
        try:
            result = self.sentiment_analyzer(text[:512])
            return {'NEGATIVE': -1, 'NEUTRAL': 0, 'POSITIVE': 1}[result[0]['label']] * result[0]['score']
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return 0.0

    async def predict_trend(self, symbol: str) -> Dict:
        try:
            async with self.exchange_manager.get_exchange('binance', 'spot') as exchange:
                ohlcv = await exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
                closes = np.array([x[4] for x in ohlcv])
                
                sma_short = np.mean(closes[-10:])
                sma_long = np.mean(closes[-50:])
                
                direction = "up" if sma_short > sma_long else "down"
                confidence = abs(sma_short - sma_long) / np.mean(closes)
                
                return {
                    "direction": direction,
                    "confidence": min(confidence, 0.99),
                    "price_target": sma_short * 1.05 if direction == "up" else sma_short * 0.95
                }
        except Exception as e:
            logger.error(f"Trend prediction error: {e}")
            return {"direction": "neutral", "confidence": 0, "price_target": 0}
