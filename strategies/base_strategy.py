from abc import ABC, abstractmethod
import pandas as pd

class BaseStrategy(ABC):
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate trading signals from OHLCV data"""
        pass

    @property
    @abstractmethod
    def params(self) -> dict:
        """Return strategy parameters"""
        pass

    def version(self) -> str:
        return "1.0"