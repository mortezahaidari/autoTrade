import pandas as pd
import numpy as np


import logging

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class MACDStrategy:
    def __init__(self, short_window=12, long_window=26, signal_window=9):
        self.short_window = short_window
        self.long_window = long_window
        self.signal_window = signal_window

    def generate_signals(self, data):
        data['Short_EMA'] = data['close'].ewm(span=self.short_window, adjust=False).mean()
        data['Long_EMA'] = data['close'].ewm(span=self.long_window, adjust=False).mean()
        data['MACD'] = data['Short_EMA'] - data['Long_EMA']
        data['Signal_Line'] = data['MACD'].ewm(span=self.signal_window, adjust=False).mean()

        # Log only the MACD, Signal Line, and signal
        latest_macd = data['MACD'].iloc[-1]
        latest_signal_line = data['Signal_Line'].iloc[-1]
        if latest_macd > latest_signal_line:
            logger.info(f"✅ MACD Strategy: Strong Buy Signal (MACD={latest_macd:.2f}, Signal Line={latest_signal_line:.2f})")
            return 'strong_buy'
        elif latest_macd < latest_signal_line:
            logger.info(f"✅ MACD Strategy: Strong Sell Signal (MACD={latest_macd:.2f}, Signal Line={latest_signal_line:.2f})")
            return 'strong_sell'
        else:
            logger.info(f"✅ MACD Strategy: Neutral Signal (MACD={latest_macd:.2f}, Signal Line={latest_signal_line:.2f})")
            return 'neutral'