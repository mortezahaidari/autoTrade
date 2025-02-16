import pandas as pd
import numpy as np
import logging

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class MovingAverageCrossoverStrategy:
    def __init__(self, short_window=50, long_window=200, rsi_period=14, rsi_threshold=30):
        """
        Initialize the Moving Average Crossover Strategy.

        :param short_window: Window size for the short moving average.
        :param long_window: Window size for the long moving average.
        :param rsi_period: Period for calculating RSI.
        :param rsi_threshold: Threshold for RSI to generate buy/sell signals.
        """
        self.short_window = short_window
        self.long_window = long_window
        self.rsi_period = rsi_period
        self.rsi_threshold = rsi_threshold

    def compute_rsi(self, data):
        """
        Compute the Relative Strength Index (RSI).

        :param data: DataFrame containing 'close' prices.
        :return: DataFrame with 'RSI' column added.
        """
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        data['RSI'] = rsi
        return data

    def generate_signals(self, data):
        """
        Generate trading signals based on Moving Average Crossover and RSI.

        :param data: DataFrame containing 'close' prices.
        :return: Signal ('buy', 'sell', or 'neutral').
        """
        # Validate input data
        if 'close' not in data.columns:
            logger.error("❌ 'close' column not found in data.")
            return 'neutral'

        # Compute Moving Averages
        data['Short_MA'] = data['close'].rolling(window=self.short_window, min_periods=1).mean()
        data['Long_MA'] = data['close'].rolling(window=self.long_window, min_periods=1).mean()

        # Compute RSI
        data = self.compute_rsi(data)

        # Get the latest values
        latest_short_ma = data['Short_MA'].iloc[-1]
        latest_long_ma = data['Long_MA'].iloc[-1]
        latest_rsi = data['RSI'].iloc[-1]

        # Log the latest values
        logger.debug(f"Short MA: {latest_short_ma:.2f}, Long MA: {latest_long_ma:.2f}, RSI: {latest_rsi:.2f}")

        # Generate signals
        if pd.isna(latest_short_ma) or pd.isna(latest_long_ma) or pd.isna(latest_rsi):
            logger.warning("❌ Missing values in Moving Averages or RSI. Cannot generate signal.")
            return 'neutral'

        if latest_short_ma > latest_long_ma and latest_rsi > self.rsi_threshold:
            logger.info(f"✅ Moving Average Crossover Strategy: Buy Signal (Short MA={latest_short_ma:.2f}, Long MA={latest_long_ma:.2f}, RSI={latest_rsi:.2f})")
            return 'buy'
        elif latest_short_ma < latest_long_ma and latest_rsi < (100 - self.rsi_threshold):
            logger.info(f"✅ Moving Average Crossover Strategy: Sell Signal (Short MA={latest_short_ma:.2f}, Long MA={latest_long_ma:.2f}, RSI={latest_rsi:.2f})")
            return 'sell'
        else:
            logger.info(f"✅ Moving Average Crossover Strategy: No Signal (Short MA={latest_short_ma:.2f}, Long MA={latest_long_ma:.2f}, RSI={latest_rsi:.2f})")
            return 'neutral'