import pandas as pd
import numpy as np
from pydantic import Field
from strategies.strategy_factory import StrategyFactory, StrategyParameters
from strategies.base_strategy import BaseStrategy


@StrategyFactory.register("bollinger_bands", "2.1.0")  # Ensure it's registered correctly
class BollingerBandsStrategy(BaseStrategy):
    """Bollinger Bands Trading Strategy"""

    class Parameters(StrategyParameters):
        """Defines valid parameters for Bollinger Bands strategy."""
        window: int = Field(20, gt=5, le=100, description="Rolling window size for moving average.")
        num_std: float = Field(2.0, gt=1.0, le=3.0, description="Number of standard deviations for bands.")

    def __init__(self, window=20, num_std=2.0):
        """
        Initializes the Bollinger Bands strategy with specified parameters.

        Args:
            window (int): Moving average window size.
            num_std (float): Number of standard deviations for upper/lower bands.
        """
        self.window = window
        self.num_std = num_std

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generates buy/sell/hold signals based on Bollinger Bands.

        Args:
            data (pd.DataFrame): Market data with 'high', 'low', and 'close' columns.

        Returns:
            pd.Series: Trading signals ('buy', 'sell', or 'hold').
        """
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        rolling_mean = typical_price.rolling(window=self.window).mean()
        rolling_std = typical_price.rolling(window=self.window).std()

        upper_band = rolling_mean + (rolling_std * self.num_std)
        lower_band = rolling_mean - (rolling_std * self.num_std)

        signals = pd.Series(index=data.index, dtype='object')
        signals[:] = 'hold'

        signals[data['close'] > upper_band] = 'sell'
        signals[data['close'] < lower_band] = 'buy'

        return signals
