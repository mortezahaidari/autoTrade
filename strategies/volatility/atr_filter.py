import numpy as np
import pandas as pd
from pydantic import Field
from strategies.strategy_factory import StrategyConfig, StrategyParameters
from strategies.strategy_factory import StrategyFactory  # Ensure this is first
from strategies.base_strategy import BaseStrategy

print(StrategyFactory.register)  # Debugging check ✅

@StrategyFactory.register("atr_filter", "1.2.0")  # ✅ Registering ATR filter
class ATRFilterStrategy(BaseStrategy):
    """ATR (Average True Range) Filter Strategy
    
    This strategy calculates the ATR (a measure of volatility) and generates 
    trading signals based on whether the closing price exceeds a specified 
    threshold of the ATR.
    
    - **Buy Signal:** If the closing price is greater than ATR * threshold.
    - **Sell Signal:** If the closing price is less than ATR * threshold * -1.
    - **Hold:** Default state when no buy/sell condition is met.

    Attributes:
        period (int): The number of periods for ATR calculation (default: 14).
        threshold (float): The multiplier applied to ATR for generating signals.
    """

    class Parameters(StrategyParameters):
        """Defines the expected parameters for ATR Filter Strategy."""
        period: int = Field(14, gt=5, le=50, description="ATR calculation window size.")
        threshold: float = Field(1.5, ge=0.5, le=5.0, description="Multiplier for ATR threshold.")

    def __init__(self, period=14, threshold=1.5):
        """
        Initializes the ATRFilterStrategy with a specific ATR period and threshold.

        Args:
            period (int): The number of periods to use for ATR calculation.
            threshold (float): The multiplier applied to ATR to determine buy/sell signals.
        """
        self.period = period
        self.threshold = threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generates buy/sell/hold signals based on ATR volatility.

        ATR (Average True Range) is used to measure volatility. The trading signals 
        are generated based on whether the closing price moves beyond a multiple 
        of the ATR.

        Args:
            data (pd.DataFrame): A DataFrame containing 'high', 'low', and 'close' prices.

        Returns:
            pd.Series: A Pandas Series containing trading signals ('buy', 'sell', or 'hold').

        Raises:
            ValueError: If input DataFrame does not contain required columns.
        """
        required_columns = {'high', 'low', 'close'}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Data must contain columns: {required_columns}")

        # Calculate True Range (TR), which represents market volatility
        high_low = data['high'] - data['low']  # High - Low of current candle
        high_close = np.abs(data['high'] - data['close'].shift(1))  # High - Previous Close
        low_close = np.abs(data['low'] - data['close'].shift(1))  # Low - Previous Close

        # True Range is the max of these three values
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))

        # Compute ATR as the rolling mean of True Range over the specified period
        atr = true_range.rolling(window=self.period).mean()

        # Initialize signals as "hold"
        signals = pd.Series(index=data.index, dtype='object')
        signals[:] = 'hold'

        # Buy Signal: Close price breaks above ATR threshold
        signals[data['close'] > (atr * self.threshold)] = 'buy'

        # Sell Signal: Close price drops below ATR threshold (negative multiplier)
        signals[data['close'] < (atr * self.threshold * -1)] = 'sell'

        return signals
