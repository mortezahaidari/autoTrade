import numpy as np

def calculate_atr(data, period=14):
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    true_range = np.maximum.reduce([high_low, high_close, low_close])
    return true_range.rolling(window=period).mean()