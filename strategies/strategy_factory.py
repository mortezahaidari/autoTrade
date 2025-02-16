from __future__ import annotations
import logging
import inspect
import threading
from dataclasses import dataclass, field
from typing import (
    Type, Dict, Any, Optional, ClassVar,
    Protocol, runtime_checkable, Generic, TypeVar
)
from pydantic import BaseModel, ValidationError
from functools import lru_cache
import importlib.util
from pathlib import Path

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

# --------------------------
# Strategy Factory Implementation
# --------------------------
class StrategyFactory(Generic[T]):
    """Advanced strategy factory with plugin support and validation"""
    
    _registry: ClassVar[Dict[str, Type[T]]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _cache_size: ClassVar[int] = 100

    @classmethod
    @lru_cache(maxsize=_cache_size)
    def create(cls, config: StrategyConfig) -> T:
        """Create strategy instance with caching and validation"""
        try:
            strategy_class = cls._resolve_strategy_class(config.name, config.version)
            validated_params = cls._validate_parameters(strategy_class, config.parameters)
            dependencies = cls._resolve_dependencies(config.dependencies)
            
            return strategy_class(
                **validated_params.dict(),
                **dependencies
            )
        except ValidationError as ve:
            logger.error(f"Parameter validation failed: {ve.json()}")
            raise InvalidParameterError(f"Invalid parameters for {config.name}") from ve
        except Exception as exc:
            logger.error(f"Strategy creation failed for {config.name}", exc_info=True)
            raise StrategyCreationError(f"Failed to create {config.name}") from exc

    @classmethod
    def _resolve_strategy_class(cls, name: str, version: str) -> Type[T]:
        """Resolve strategy class with version checking"""
        with cls._lock:
            strategy_class = cls._registry.get(f"{name}@{version}")
            if not strategy_class:
                raise StrategyError(f"Strategy {name} version {version} not registered")
            
            if not issubclass(strategy_class, TradingStrategy):
                raise TypeError(f"{strategy_class.__name__} doesn't implement TradingStrategy protocol")
            
            return strategy_class

    @classmethod
    def _validate_parameters(cls, strategy_class: Type[T], params: StrategyParameters) -> StrategyParameters:
        """Validate parameters against strategy requirements"""
        if not issubclass(strategy_class, ParameterizedStrategy):
            return params
        
        param_model = strategy_class.parameter_model()
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
    def register(cls, name: str, version: str = "1.0.0"):
        """Decorator for strategy registration with versioning"""
        def decorator(strategy_class: Type[T]):
            with cls._lock:
                full_name = f"{name}@{version}"
                if full_name in cls._registry:
                    raise ValueError(f"Strategy {full_name} already registered")
                
                if not inspect.isclass(strategy_class) or not issubclass(strategy_class, TradingStrategy):
                    raise TypeError("Registered class must implement TradingStrategy protocol")
                
                cls._registry[full_name] = strategy_class
                logger.info(f"Registered strategy: {full_name}")
                return strategy_class
            return decorator

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