import pandas as pd
import logging

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class StochasticOscillatorStrategy:
    def __init__(self, k_period=14, d_period=3, oversold=20, overbought=80):
        self.k_period = k_period
        self.d_period = d_period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signals(self, data):
        # Calculate %K and %D
        data['Lowest Low'] = data['low'].rolling(window=self.k_period).min()
        data['Highest High'] = data['high'].rolling(window=self.k_period).max()
        data['%K'] = 100 * ((data['close'] - data['Lowest Low']) / (data['Highest High'] - data['Lowest Low']))
        data['%D'] = data['%K'].rolling(window=self.d_period).mean()

        # Log only the %K, %D, and signal
        latest_k = data['%K'].iloc[-1]
        latest_d = data['%D'].iloc[-1]
        logger.info(f"✅ Stochastic Oscillator: %K={latest_k:.2f}, %D={latest_d:.2f}")

        # Determine signal based on %K and %D
        if latest_k < self.oversold and latest_d < self.oversold:
            logger.info(f"✅ Stochastic Oscillator: Strong Buy Signal (%K={latest_k:.2f}, %D={latest_d:.2f} - Oversold)")
            return 'strong_buy'
        elif latest_k > self.overbought and latest_d > self.overbought:
            logger.info(f"✅ Stochastic Oscillator: Strong Sell Signal (%K={latest_k:.2f}, %D={latest_d:.2f} - Overbought)")
            return 'strong_sell'
        else:
            logger.info(f"✅ Stochastic Oscillator: Neutral Signal (%K={latest_k:.2f}, %D={latest_d:.2f} - Neutral)")
            return 'neutral'