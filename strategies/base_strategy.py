from core.protocols import TradingStrategy, ParameterizedStrategy

class BaseStrategy(TradingStrategy, ParameterizedStrategy):
    """Abstract base class for all strategies"""
    
    @classmethod
    def required_parameters(cls) -> dict:
        return {}
    
    def get_parameters(self) -> dict:
        return {k: getattr(self, k) for k in self.required_parameters()}