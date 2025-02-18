from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    STRATEGY: str = "bollinger_bands"
    RISK_PCT: float = 0.02
    MAX_LEVERAGE: int = 10
    
    class Config:
        env_file = ".env"

# Define your strategy configuration here (instead of as an attribute on StrategyConfig)
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

""" Configuration Validation"""
from strategies.strategy_factory import StrategyFactory, StrategyConfig
from strategies.strategy_factory import BollingerBandsParameters, ATRFilterParameters

# Use the global STRATEGY_CONFIG variable
if not StrategyFactory.is_strategy_registered(
    STRATEGY_CONFIG['dependencies']['volatility_filter']['name'],
    STRATEGY_CONFIG['dependencies']['volatility_filter']['version']
):
    raise RuntimeError("Dependency strategy 'atr_filter' not registered")

# Create the dependency strategy (atr_filter in this case)
volatility_filter_config = StrategyConfig(
    name="atr_filter",  # Name of the dependency strategy
    version="1.2.0",    # Version
    parameters=ATRFilterParameters(period=14, threshold=1.5),  # Parameters for atr_filter
)
volatility_filter = StrategyFactory.create_strategy(volatility_filter_config)

# Create the main strategy (bollinger_bands in this case)
bollinger_bands_config = StrategyConfig(
    name="bollinger_bands",  # Main strategy
    version="2.1.0",         # Version
    parameters=BollingerBandsParameters(window=20, num_std=2.0),  # Parameters for bollinger_bands
    dependencies={
        "volatility_filter": volatility_filter_config  # Attach the created dependency here
    }
)
bollinger_bands_strategy = StrategyFactory.create_strategy(bollinger_bands_config)

# Now you can use the created strategy instances
signals = bollinger_bands_strategy.generate_signals(data)
print(f"Generated signals: {signals}")
