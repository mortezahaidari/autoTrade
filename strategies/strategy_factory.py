from __future__ import annotations
import logging
import inspect
import threading
from dataclasses import dataclass, field
from typing import (
    Type, Dict, Any, Optional, ClassVar, Tuple,
    Protocol, runtime_checkable, Generic, TypeVar
)
from pydantic import BaseModel, ValidationError, Field
from functools import lru_cache
import importlib.util
from pathlib import Path
import json

logger = logging.getLogger(__name__)


# --------------------------
# Protocol Definitions
# --------------------------
@runtime_checkable
class TradingStrategy(Protocol):
    @classmethod
    def required_parameters(cls) -> Dict[str, type]:
        ...
    
    def generate_signals(self, data: Any) -> Any:
        ...

@runtime_checkable
class ParameterizedStrategy(Protocol):
    def get_parameters(self) -> Dict[str, Any]:
        ...

T = TypeVar('T', bound=TradingStrategy)

# --------------------------
# Custom Exceptions
# --------------------------
class StrategyError(Exception):
    """Base exception for strategy-related errors"""

class StrategyCreationError(StrategyError):
    """Error during strategy instantiation"""

class InvalidParameterError(StrategyError):
    """Invalid strategy parameters"""

class DependencyResolutionError(StrategyError):
    """Error resolving strategy dependencies"""

# --------------------------
# Core Data Models
# --------------------------
class StrategyParameters(BaseModel):
    """Base model for strategy parameter validation"""
    class Config:
        extra = 'forbid'
        validate_assignment = True
        frozen = True # makes instances hashable

class BollingerBandsParameters(StrategyParameters):
    """Bollinger Bands specific parameters"""
    window: int = Field(20, gt=5, le=100)
    num_std: float = Field(2.0, gt=1.0, le=3.0)

class ATRFilterParameters(StrategyParameters):
    """ATR Filter specific parameters"""
    period: int = Field(14, gt=5, le=50)
    threshold: float = Field(1.5, ge=0.5, le=5.0)            


@dataclass(frozen=True)
class StrategyConfig:
    """Correct field ordering for dataclass"""
    name: str                   # Required field (no default)
    parameters: StrategyParameters  # Required field (no default)
    version: str = "1.0.0"      # Optional field (has default)
    dependencies: Dict[str, 'StrategyConfig'] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'version': self.version,
            'parameters': self.parameters.dict(),
            'dependencies': {k: v.to_dict() for k, v in (self.dependencies or {}).items()},
            'enabled': self.enabled
        }
    
    def to_json(self) -> str:
        """Serialize config to JSON string for caching"""
        return json.dumps({
            'name': self.name,
            'version': self.version,
            'parameters': self.parameters.dict(),
            'dependencies': {k: v.to_dict() for k, v in self.dependencies.items()},
            'enabled': self.enabled
        }, sort_keys=True)    

# --------------------------
# Strategy Factory Implementation
# --------------------------
class StrategyFactory(Generic[T]):
    """Advanced strategy factory with parameter model support"""
    
    _registry: ClassVar[Dict[str, Tuple[Type[T], Type[StrategyParameters]]]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _cache_size: ClassVar[int] = 100

    @classmethod
    def is_strategy_registered(cls, name: str, version: str) -> bool:
        """Check if a strategy is registered with the factory"""
        key = f"{name}@{version}"
        with cls._lock:
            return key in cls._registry

    @classmethod
    @lru_cache(maxsize=_cache_size)
    def create_strategy(cls, config_json: str) -> T:
        """Create strategy instance with JSON-serialized config"""
        
        try:
            config = StrategyConfig(**json.loads(config_json))
            strategy_class, param_model = cls._resolve_strategy_class(config.name, config.version)
            validated_params = param_model(**config.parameters.dict())
            dependencies = cls._resolve_dependencies(config.dependencies)
            
            return strategy_class(
                **validated_params.dict(),
                **dependencies
            )
        
        except json.JSONDecodeError as je:
            logger.error(f"Invalid config JSON: {je}")
            raise StrategyCreationError("Invalid configuration format") from je
        
        except ValidationError as ve:
            logger.error(f"Parameter validation failed: {ve}")
            raise InvalidParameterError(f"Invalid parameters for {config.name}") from ve

    @classmethod
    def get_strategy_type(cls, name: str, version: str) -> Tuple[Type[T], Type[StrategyParameters]]:
        """Get strategy class and its parameter model"""
        key = f"{name}@{version}"
        if key not in cls._registry:
            raise StrategyError(f"Strategy {key} not registered")
        return cls._registry[key]

    @classmethod
    def register(cls, name: str, version: str = "1.0.0"):
        """Decorator for strategy registration"""
        def decorator(strategy_class: Type[T]):
            # Auto-detect parameter model
            param_model = getattr(strategy_class, 'Parameters', StrategyParameters)
            
            with cls._lock:
                key = f"{name}@{version}"
                if key in cls._registry:
                    raise ValueError(f"Strategy {key} already registered")
                
                if not issubclass(param_model, StrategyParameters):
                    raise TypeError("Parameter model must inherit from StrategyParameters")
                
                cls._registry[key] = (strategy_class, param_model)
                logger.info(f"Registered strategy: {key}")
                return strategy_class
        return decorator

    @classmethod
    def _resolve_strategy_class(cls, name: str, version: str) -> Tuple[Type[T], Type[StrategyParameters]]:
        """Resolve strategy class and its parameter model"""
        key = f"{name}@{version}"
        if key not in cls._registry:
            raise StrategyError(f"Strategy {key} not registered")
        
        strategy_class, param_model = cls._registry[key]
        
        if not issubclass(strategy_class, TradingStrategy):
            raise TypeError(f"{strategy_class.__name__} doesn't implement TradingStrategy protocol")
        
        return strategy_class, param_model

    @classmethod
    def _validate_parameters(cls, param_model: Type[StrategyParameters], params: StrategyParameters) -> StrategyParameters:
        """Validate parameters against strategy requirements"""
        return param_model(**params.dict())

    @classmethod
    def _resolve_dependencies(cls, dependencies: Dict[str, StrategyConfig]) -> Dict[str, T]:
        """Resolve and validate strategy dependencies"""
        resolved = {}
        for dep_name, dep_config in (dependencies or {}).items():
            if not dep_config.enabled:
                logger.warning(f"Dependency {dep_name} is disabled")
                continue
                
            dep_instance = cls.create(dep_config)
            if not isinstance(dep_instance, TradingStrategy):
                raise DependencyResolutionError(f"Dependency {dep_name} is not a valid strategy")
            
            resolved[dep_name] = dep_instance
        return resolved

    @classmethod
    def discover_strategies(cls, plugin_dir: Path):
        """Discover strategies from plugin directory"""
        for path in plugin_dir.glob("**/*_strategy.py"):
            module_name = path.stem
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            logger.info(f"Discovered strategies from {path}")

    @classmethod
    def get_registered_strategies(cls) -> Dict[str, Type[T]]:
        """Get thread-safe copy of registered strategies"""
        with cls._lock:
            return cls._registry.copy()

# --------------------------
# Strategy Base Class
# --------------------------
class BaseStrategy(TradingStrategy, ParameterizedStrategy):
    """Abstract base strategy with parameter management"""
    
    @classmethod
    def required_parameters(cls) -> Dict[str, type]:
        return {}
    
    @classmethod
    def parameter_model(cls) -> Type[StrategyParameters]:
        class DynamicParameters(StrategyParameters):
            pass
        
        for param, param_type in cls.required_parameters().items():
            DynamicParameters.__fields__[param] = (param_type, ...)
        
        return DynamicParameters

    def get_parameters(self) -> Dict[str, Any]:
        return {field: getattr(self, field) for field in self.required_parameters()}
    
