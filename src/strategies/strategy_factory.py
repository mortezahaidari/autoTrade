from strategies.bollinger_band_strategy import BollingerBandsStrategy
from strategies.rsi_strategy import RSIStrategy
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.moving_average_crossover_strategy import MovingAverageCrossoverStrategy
from strategies.macd_strategy import MACDStrategy
from strategies.stochastic_oscillator import StochasticOscillatorStrategy
from strategies.combined_signal import CombinedStrategy


class StrategyFactory:
    """
    Factory class to create and return the desired strategy.
    """
    @staticmethod
    def get_strategy(strategy_name, **kwargs):
        if strategy_name == "sma_crossover":
            return SMACrossoverStrategy(**kwargs)
        elif strategy_name == "rsi":
            return RSIStrategy(**kwargs)
        elif strategy_name == "bollinger_bands":
            return BollingerBandsStrategy(**kwargs)
        elif strategy_name == "moving_average_crossover":
            return MovingAverageCrossoverStrategy(**kwargs)
        elif strategy_name == "macd":
            return MACDStrategy(**kwargs)
        elif strategy_name == "stochastic_oscillator":
            return StochasticOscillatorStrategy(**kwargs)
        elif strategy_name == "combined":
            return CombinedStrategy(**kwargs)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        

        