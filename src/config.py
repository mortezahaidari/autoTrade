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

STRATEGY_CONFIG = {
    "name": "combined",
    "params": {
        "threshold": 0.7
    },
    "dependencies": {
        "trend": {
            "name": "moving_average_crossover",
            "params": {"short_window": 50, "long_window": 200}
        },
        "momentum": {
            "name": "rsi", 
            "params": {"period": 14}
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