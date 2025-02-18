from typing import Protocol, Dict, Any
from abc import abstractmethod

class TradingStrategy(Protocol):
    """Protocol defining required methods for trading strategies"""
    
    @abstractmethod
    def generate_signals(self, data: Any) -> Any:
        """Generate trading signals from market data"""
        ...

class ParameterizedStrategy(Protocol):
    """Protocol for strategies with configurable parameters"""
    
    @abstractmethod
    def get_parameters(self) -> Dict[str, Any]:
        """Get current strategy parameters"""
        ...