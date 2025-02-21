# Initialize strategies package
from strategies.base_strategy import BaseStrategy
from strategies.strategy_factory import StrategyFactory, StrategyConfig
from strategies.trend.moving_average_crossover import  MovingAverageCrossoverStrategy
from strategies.trend.bollinger_band import BollingerBandsStrategy 
from strategies.mean_reversion.rsi import RSIStrategy
from strategies.mean_reversion.stochastic_oscillator import StochasticOscillatorStrategy
from strategies.volatility.atr_filter import ATRFilterStrategy

__all__ = [
    'BaseStrategy',
    'ATRFilterStrategy'
    'StrategyFactory',
    'StrategyConfig',
    'BollingerBandsStrategy',
    'MovingAverageCrossoverStrategy',
    'RSIStrategy',
    'StochasticOscillatorStrategy'
]