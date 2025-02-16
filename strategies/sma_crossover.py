import pandas as pd
import logging

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class SMACrossoverStrategy:
    def __init__(self, short_window=10, long_window=50, trading_mode="spot"):
        self.short_window = short_window
        self.long_window = long_window
        self.trading_mode = trading_mode

    def generate_signals(self, data):
        # Calculate SMAs
        data["SMA_Short"] = data["close"].rolling(window=self.short_window, min_periods=1).mean()
        data["SMA_Long"] = data["close"].rolling(window=self.long_window, min_periods=1).mean()

        # Log only the SMAs and signal
        latest_short_sma = data["SMA_Short"].iloc[-1]
        latest_long_sma = data["SMA_Long"].iloc[-1]
        logger.info(f"✅ SMA Crossover: Short SMA={latest_short_sma:.2f}, Long SMA={latest_long_sma:.2f}")

        # Determine signal based on SMA crossover
        if latest_short_sma > latest_long_sma:
            logger.info(f"✅ SMA Crossover: Strong Buy Signal (Short SMA crossed above Long SMA)")
            return 'strong_buy'
        elif latest_short_sma < latest_long_sma:
            logger.info(f"✅ SMA Crossover: Strong Sell Signal (Short SMA crossed below Long SMA)")
            return 'strong_sell'
        else:
            logger.info(f"✅ SMA Crossover: Neutral Signal")
            return 'neutral'