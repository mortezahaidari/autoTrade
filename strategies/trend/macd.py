import pandas as pd
import numpy as np
import logging
from pydantic import Field
from strategies.strategy_factory import StrategyFactory, StrategyParameters
from strategies.base_strategy import BaseStrategy


# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@StrategyFactory.register("macd", "1.0.0")  # Register MACD strategy with the factory
class MACDStrategy(BaseStrategy):
    """MACD (Moving Average Convergence Divergence) Trading Strategy."""

    class Parameters(StrategyParameters):
        """Defines valid parameters for MACD strategy."""
        short_window: int = Field(12, gt=5, le=50, description="Short EMA window for MACD calculation.")
        long_window: int = Field(26, gt=10, le=100, description="Long EMA window for MACD calculation.")
        signal_window: int = Field(9, gt=3, le=30, description="Signal line EMA window.")

    def __init__(self, short_window=12, long_window=26, signal_window=9):
        """
        Initializes the MACD strategy with specified parameters.

        Args:
            short_window (int): Short EMA window for MACD.
            long_window (int): Long EMA window for MACD.
            signal_window (int): Signal line EMA window.
        """
        self.short_window = short_window
        self.long_window = long_window
        self.signal_window = signal_window

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generates buy/sell/hold signals based on MACD crossover strategy.

        Args:
            data (pd.DataFrame): Market data with 'close' price column.

        Returns:
            pd.Series: Trading signals ('strong_buy', 'strong_sell', or 'neutral').
        """
        data['Short_EMA'] = data['close'].ewm(span=self.short_window, adjust=False).mean()
        data['Long_EMA'] = data['close'].ewm(span=self.long_window, adjust=False).mean()
        data['MACD'] = data['Short_EMA'] - data['Long_EMA']
        data['Signal_Line'] = data['MACD'].ewm(span=self.signal_window, adjust=False).mean()

        signals = pd.Series(index=data.index, dtype='object')
        signals[:] = 'neutral'

        signals[data['MACD'] > data['Signal_Line']] = 'strong_buy'
        signals[data['MACD'] < data['Signal_Line']] = 'strong_sell'

        # Logging only the latest signal
        latest_macd = data['MACD'].iloc[-1]
        latest_signal_line = data['Signal_Line'].iloc[-1]
        latest_signal = signals.iloc[-1]

        logger.info(f"✅ MACD Strategy: {latest_signal.upper()} (MACD={latest_macd:.2f}, Signal Line={latest_signal_line:.2f})")

        return signals

