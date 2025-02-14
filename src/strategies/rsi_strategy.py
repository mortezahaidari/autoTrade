import logging
import pandas as pd

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class RSIStrategy:
    def __init__(self, period=14, oversold=30, overbought=70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data):
        if "close" not in data.columns:
            return None

        # Calculate RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.period).mean()
        rs = gain / loss
        data['RSI'] = 100 - (100 / (1 + rs))

        # Generate signals for each row
        signals = pd.Series('neutral', index=data.index)
        signals[data['RSI'] < self.oversold] = 'strong_buy'  # Oversold condition
        signals[data['RSI'] > self.overbought] = 'strong_sell'  # Overbought condition
        signals = signals.replace({'strong_buy': 'buy', 'strong_sell': 'sell'})

       
        # Log the signals
        logger.info(f"RSI Values:\n{data['RSI'].tail()}")
        logger.info(f"RSI Signals:\n{signals.tail()}")
        logger.info(f"Data length: {len(data)}, RSI Period: {self.period}")


        return signals