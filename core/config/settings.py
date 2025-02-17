# config.py

# Core Trading Configuration
SYMBOL = "BTC/USDT"
TRADING_MODE = "spot"  # spot or margin
PRIMARY_TIMEFRAME = "4h"
TIMEFRAMES = ["15m", "1h", "4h"]

# Strategy Configuration
STRATEGY_NAME = "combined"
STRATEGY_PARAMS = {
    'rsi_period': 14,
    'ema_short': 20,
    'ema_long': 50,
    'bollinger_period': 20
}

# In core/config/settings.py
STRATEGY_CONFIG = {
    "name": "bollinger_bands",
    "version": "2.1.0",
    "parameters": {
        "window": 20,
        "num_std": 2.0
    },
    "dependencies": {
        "volatility_filter": {
            "name": "atr_filter",
            "version": "1.2.0",
            "parameters": {
                "period": 14,
                "threshold": 1.5
            }
        }
    }
}


# Risk Management
RISK_PERCENTAGE = 0.02
MAX_POSITION_SIZE = 0.1
STOP_LOSS_PCT = 0.05
TAKE_PROFIT_PCT = 0.10

# Machine Learning
MODEL_TIMEFRAME = "4h"
MODEL_TRAINING_WINDOW = 1000
AUTO_RETRAIN = True
REQUIRE_ML = False

# Monitoring & Metrics
METRICS_ENABLED = True
METRICS_PORT = 9100
LOOP_INTERVAL = 60  # seconds
ERROR_RETRY_DELAY = 10

# Exchange Settings
API_RATE_LIMIT = 10  # requests per second
DRY_RUN = True  # test mode without real orders


from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    STRATEGY: str = "bollinger_bands"
    RISK_PCT: float = 0.02
    MAX_LEVERAGE: int = 10
    
    class Config:
        env_file = ".env"