# Core Trading Configuration
TRADING = {
    "SYMBOL": "BTC/USDT",
    "MODE": "spot",  # spot or margin
    "TIMEFRAMES": ["15m", "1h", "4h"],
    "PRIMARY_TIMEFRAME": "4h"
}

# Risk Management Configuration
RISK_MANAGEMENT = {
    "RISK_PERCENTAGE": 0.02,
    "MAX_POSITION_SIZE": 0.1,
    "STOP_LOSS": 0.05,
    "TAKE_PROFIT": 0.10
}

# Strategy Configuration
STRATEGY_CONFIG = {
    "bollinger_bands": {
        "version": "2.1.0",
        "params": {
            "window": 20,
            "num_std": 2.0
        },
        "dependencies": {
            "volatility_filter": "atr_filter@1.2.0"
        }
    },
    "atr_filter": {
        "version": "1.2.0",
        "params": {
            "period": 14,
            "threshold": 1.5
        }
    }
}

# Exchange Configuration
EXCHANGE = {
    "RATE_LIMIT": 10,
    "DRY_RUN": True
}

# Machine Learning Configuration
ML = {
    "MODEL_TIMEFRAME": "4h",
    "TRAINING_WINDOW": 1000,
    "AUTO_RETRAIN": True,
    "REQUIRE_ML": False
}