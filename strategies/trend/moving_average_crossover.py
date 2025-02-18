import pandas as pd
import numpy as np
import logging
from pydantic import Field
from strategies.strategy_factory import StrategyFactory, StrategyParameters
from strategies.base_strategy import BaseStrategy


# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@StrategyFactory.register("moving_average_crossover", "1.0.0")  # Register with StrategyFactory
class MovingAverageCrossoverStrategy(BaseStrategy):
    """Moving Average Crossover Strategy with RSI filtering."""

    class Parameters(StrategyParameters):
        """Defines valid parameters for Moving Average Crossover strategy."""
        short_window: int = Field(50, gt=5, le=100, description="Short moving average window.")
        long_window: int = Field(200, gt=50, le=300, description="Long moving average window.")
        rsi_period: int = Field(14, gt=5, le=50, description="Period for calculating RSI.")
        rsi_threshold: int = Field(30, ge=10, le=50, description="RSI threshold for buy/sell signals.")

    def __init__(self, short_window=50, long_window=200, rsi_period=14, rsi_threshold=30):
        """
        Initializes the Moving Average Crossover Strategy.

        Args:
            short_window (int): Short moving average window.
            long_window (int): Long moving average window.
            rsi_period (int): RSI calculation period.
            rsi_threshold (int): Threshold for RSI-based filtering.
        """
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_period = rsi_period
        self.rsi_threshold = rsi_threshold

    def compute_rsi(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Computes the Relative Strength Index (RSI).

        Args:
            data (pd.DataFrame): Market data with 'close' prices.

        Returns:
            pd.DataFrame: Data with an added 'RSI' column.
        """
        delta = data['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.rsi_period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))
        return data

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generates trading signals based on Moving Average Crossover and RSI.

        Args:
            data (pd.DataFrame): Market data with 'close' prices.

        Returns:
            pd.Series: Trading signals ('buy', 'sell', or 'neutral').
        """
        if 'close' not in data.columns:
            logger.error("❌ 'close' column not found in data.")
            return pd.Series('neutral', index=data.index)

        # Compute Moving Averages
        data['Short_MA'] = data['close'].rolling(window=self.short_window, min_periods=1).mean()
        data['Long_MA'] = data['close'].rolling(window=self.long_window, min_periods=1).mean()

        # Compute RSI
        data = self.compute_rsi(data)

        # Initialize signals
        signals = pd.Series(index=data.index, dtype='object')
        signals[:] = 'neutral'

        # Generate signals based on MA crossover and RSI
        signals[(data['Short_MA'] > data['Long_MA']) & (data['RSI'] > self.rsi_threshold)] = 'buy'
        signals[(data['Short_MA'] < data['Long_MA']) & (data['RSI'] < (100 - self.rsi_threshold))] = 'sell'

        # Log latest values
        latest_short_ma = data['Short_MA'].iloc[-1]
        latest_long_ma = data['Long_MA'].iloc[-1]
        latest_rsi = data['RSI'].iloc[-1]
        latest_signal = signals.iloc[-1]

        logger.info(f"✅ Moving Average Crossover Strategy: {latest_signal.upper()} "
                    f"(Short MA={latest_short_ma:.2f}, Long MA={latest_long_ma:.2f}, RSI={latest_rsi:.2f})")

        return signals
