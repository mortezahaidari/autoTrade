# Initialize strategies package
from .base_strategy import BaseStrategy
from .strategy_factory import StrategyFactory, StrategyConfig
from .core.trend import (
    BollingerBandsStrategy,
    MACrossoverStrategy
)
from .core.mean_reversion import (
    RSIStrategy,
    StochasticOscillatorStrategy
)

__all__ = [
    'BaseStrategy',
    'StrategyFactory',
    'StrategyConfig',
    'BollingerBandsStrategy',
    'MACrossoverStrategy',
    'RSIStrategy',
    'StochasticOscillatorStrategy'
]