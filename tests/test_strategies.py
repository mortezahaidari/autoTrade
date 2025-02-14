import pytest
from src.strategies.sma_crossover import SMACrossover
import pandas as pd
from src.strategies.bollinger_band_strategy import BollingerBandsStrategy

import unittest

def test_sma_crossover():
    data = pd.DataFrame({
        'close': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    })
    strategy = SMACrossover(short_window=2, long_window=5)
    signal = strategy.generate_signal(data)
    assert signal in ["buy", "sell", None]



class TestBollingerBandsStrategy(unittest.TestCase):
    def test_generate_signals(self):
        data = ...  # Mock data
        strategy = BollingerBandsStrategy()
        signal = strategy.generate_signals(data)
        self.assertIn(signal, ['buy', 'sell', 'neutral'])   