import pandas as pd
import numpy as np
from base_strategy import BaseStrategy

class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, window=20, num_std=2):
        self.window = window
        self.num_std = num_std
        
    @property
    def params(self) -> dict:
        return {
            'window': self.window,
            'num_std': self.num_std
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
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