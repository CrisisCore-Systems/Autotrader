"""Plugin strategy loader using Python entry points.

Allows loading custom strategies via:
- Entry points (autotrader.strategies group)
- Direct module import
- Plugin discovery

Example entry point in pyproject.toml:
    [project.entry-points."autotrader.strategies"]
    my_strategy = "my_package.strategies:MyStrategy"
"""

from __future__ import annotations

import importlib
import logging
from importlib.metadata import entry_points
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


# Strategy API versioning
# Format: MAJOR.MINOR (semantic versioning)
# - MAJOR: Breaking changes to strategy interface
# - MINOR: Backward-compatible additions
STRATEGY_API_VERSION = "1.0"
STRATEGY_API_MAJOR_VERSION = 1


class StrategyAPIVersionError(Exception):
    """Raised when strategy API version is incompatible."""
    pass


class StrategyError(Exception):
    """Raised when strategy loading fails."""
    pass


class StrategyRegistry:
    """Registry for strategy plugins."""
    
    def __init__(self):
        """Initialize strategy registry."""
        self._strategies: dict[str, Type] = {}
        self._loaded = False
    
    def discover(self) -> None:
        """Discover and load strategies from entry points."""
        if self._loaded:
            return
        
        try:
            # Load strategies from entry points
            eps = entry_points()
            
            # Handle different Python versions
            if hasattr(eps, 'select'):
                # Python 3.10+
                strategy_eps = eps.select(group='autotrader.strategies')
            else:
                # Python 3.9
                strategy_eps = eps.get('autotrader.strategies', [])
            
            for ep in strategy_eps:
                try:
                    strategy_class = ep.load()
                    self.register(ep.name, strategy_class)
                    logger.info(f"✅ Loaded strategy plugin: {ep.name}")
                except Exception as e:
                    logger.warning(f"Failed to load strategy {ep.name}: {e}")
            
            self._loaded = True
            logger.info(f"✅ Discovered {len(self._strategies)} strategy plugin(s)")
        
        except Exception as e:
            logger.warning(f"Strategy discovery failed: {e}")
            self._loaded = True  # Mark as loaded to avoid repeated attempts
    
    def register(self, name: str, strategy_class: Type) -> None:
        """Register a strategy class.
        
        Args:
            name: Strategy name
            strategy_class: Strategy class to register
        """
        if name in self._strategies:
            logger.warning(f"Strategy {name} already registered, overwriting")
        
        self._strategies[name] = strategy_class
        logger.debug(f"Registered strategy: {name} -> {strategy_class}")
    
    def get(self, name: str) -> Type:
        """Get strategy class by name.
        
        Args:
            name: Strategy name
            
        Returns:
            Strategy class
            
        Raises:
            StrategyError: If strategy not found
        """
        if not self._loaded:
            self.discover()
        
        if name not in self._strategies:
            raise StrategyError(f"Strategy not found: {name}. Available: {self.list_strategies()}")
        
        return self._strategies[name]
    
    def list_strategies(self) -> list[str]:
        """List all registered strategies.
        
        Returns:
            List of strategy names
        """
        if not self._loaded:
            self.discover()
        
        return sorted(self._strategies.keys())
    
    def clear(self) -> None:
        """Clear registry (useful for testing)."""
        self._strategies.clear()
        self._loaded = False


# Global registry instance
_registry = StrategyRegistry()


def load_strategy(
    strategy_name: str,
    module_path: str | None = None,
) -> Type:
    """Load strategy by name or module path.
    
    Priority:
    1. Direct module path (if provided)
    2. Entry point lookup
    3. Built-in strategies
    
    Args:
        strategy_name: Name of strategy or module path
        module_path: Optional explicit module path (e.g., "mypackage.strategies:MyStrategy")
        
    Returns:
        Strategy class
        
    Raises:
        StrategyError: If strategy cannot be loaded
        
    Examples:
        # Load from entry point
        strategy = load_strategy("momentum")
        
        # Load from explicit module path
        strategy = load_strategy("custom", "mypackage.strategies:CustomStrategy")
    """
    # Option 1: Explicit module path
    if module_path:
        return _load_from_module_path(module_path)
    
    # Option 2: Entry point lookup
    try:
        return _registry.get(strategy_name)
    except StrategyError:
        pass
    
    # Option 3: Try built-in strategies
    try:
        return _load_builtin_strategy(strategy_name)
    except Exception:
        pass
    
    # Failed all options
    available = _registry.list_strategies()
    raise StrategyError(
        f"Strategy '{strategy_name}' not found. "
        f"Available strategies: {', '.join(available) if available else 'none'}"
    )


def _load_from_module_path(module_path: str) -> Type:
    """Load strategy from module path.
    
    Args:
        module_path: Module path in format "module.path:ClassName"
        
    Returns:
        Strategy class
        
    Raises:
        StrategyError: If loading fails
    """
    try:
        if ':' not in module_path:
            raise StrategyError(f"Invalid module path format: {module_path}. Use 'module.path:ClassName'")
        
        module_name, class_name = module_path.split(':', 1)
        
        # Import module
        module = importlib.import_module(module_name)
        
        # Get class
        strategy_class = getattr(module, class_name)
        
        logger.info(f"✅ Loaded strategy from module path: {module_path}")
        return strategy_class
    
    except Exception as e:
        raise StrategyError(f"Failed to load strategy from {module_path}: {e}") from e


def _load_builtin_strategy(name: str) -> Type:
    """Load built-in strategy.
    
    Args:
        name: Strategy name
        
    Returns:
        Strategy class
        
    Raises:
        StrategyError: If not found
    """
    builtin_strategies = {
        'default': 'src.core.pipeline:HiddenGemScanner',
        'momentum': 'src.strategies.momentum:MomentumStrategy',
        'mean_reversion': 'src.strategies.mean_reversion:MeanReversionStrategy',
    }
    
    if name not in builtin_strategies:
        raise StrategyError(f"Built-in strategy not found: {name}")
    
    module_path = builtin_strategies[name]
    return _load_from_module_path(module_path)


def register_strategy(name: str, strategy_class: Type) -> None:
    """Register a strategy programmatically.
    
    Args:
        name: Strategy name
        strategy_class: Strategy class
        
    Example:
        register_strategy("my_strategy", MyStrategy)
    """
    _registry.register(name, strategy_class)


def list_strategies() -> list[str]:
    """List all available strategies.
    
    Returns:
        List of strategy names
    """
    return _registry.list_strategies()


def discover_strategies() -> None:
    """Force discovery of strategy plugins."""
    _registry.discover()


def get_registry() -> StrategyRegistry:
    """Get global strategy registry.
    
    Returns:
        Global StrategyRegistry instance
    """
    return _registry


def validate_strategy_interface(strategy_class: Type) -> bool:
    """Validate that strategy class implements required interface.
    
    Args:
        strategy_class: Strategy class to validate
        
    Returns:
        True if valid
        
    Raises:
        StrategyError: If validation fails
        StrategyAPIVersionError: If API version is incompatible
    """
    # Check API version compatibility
    _validate_strategy_api_version(strategy_class)
    
    required_methods = ['scan', 'scan_with_tree']
    
    for method_name in required_methods:
        if not hasattr(strategy_class, method_name):
            raise StrategyError(
                f"Strategy {strategy_class.__name__} missing required method: {method_name}"
            )
        
        method = getattr(strategy_class, method_name)
        if not callable(method):
            raise StrategyError(
                f"Strategy {strategy_class.__name__}.{method_name} is not callable"
            )
    
    logger.debug(f"✅ Strategy interface validation passed: {strategy_class.__name__}")
    return True


def _validate_strategy_api_version(strategy_class: Type) -> None:
    """Validate strategy API version compatibility.
    
    Args:
        strategy_class: Strategy class to validate
        
    Raises:
        StrategyAPIVersionError: If API version is incompatible
    """
    # Check if strategy declares API version
    if not hasattr(strategy_class, 'STRATEGY_API_VERSION'):
        logger.warning(
            f"Strategy {strategy_class.__name__} does not declare STRATEGY_API_VERSION. "
            f"Assuming compatibility with current version {STRATEGY_API_VERSION}. "
            f"Please add STRATEGY_API_VERSION = '{STRATEGY_API_VERSION}' to your strategy class."
        )
        return
    
    strategy_version = strategy_class.STRATEGY_API_VERSION
    
    # Parse version
    try:
        if isinstance(strategy_version, str):
            parts = strategy_version.split('.')
            strategy_major = int(parts[0])
        elif isinstance(strategy_version, (int, float)):
            strategy_major = int(strategy_version)
        else:
            raise ValueError(f"Invalid version format: {strategy_version}")
    except (ValueError, IndexError) as e:
        raise StrategyAPIVersionError(
            f"Strategy {strategy_class.__name__} has invalid STRATEGY_API_VERSION: {strategy_version}. "
            f"Expected format: 'MAJOR.MINOR' (e.g., '1.0')"
        ) from e
    
    # Check major version compatibility
    if strategy_major != STRATEGY_API_MAJOR_VERSION:
        raise StrategyAPIVersionError(
            f"Strategy {strategy_class.__name__} requires API version {strategy_version}, "
            f"but AutoTrader uses API version {STRATEGY_API_VERSION}. "
            f"Major version mismatch (strategy: {strategy_major}, core: {STRATEGY_API_MAJOR_VERSION}). "
            f"Please update your strategy or use a compatible AutoTrader version."
        )
    
    logger.debug(
        f"✅ Strategy API version check passed: {strategy_class.__name__} "
        f"(strategy: {strategy_version}, core: {STRATEGY_API_VERSION})"
    )


def create_strategy_instance(
    strategy_name: str,
    module_path: str | None = None,
    **kwargs: Any,
) -> Any:
    """Load strategy and create instance.
    
    Args:
        strategy_name: Name of strategy
        module_path: Optional explicit module path
        **kwargs: Arguments to pass to strategy constructor
        
    Returns:
        Strategy instance
        
    Raises:
        StrategyError: If loading or instantiation fails
        
    Example:
        strategy = create_strategy_instance(
            "momentum",
            lookback_days=30,
            threshold=0.05,
        )
    """
    strategy_class = load_strategy(strategy_name, module_path)
    
    # Validate interface
    validate_strategy_interface(strategy_class)
    
    try:
        # Create instance
        instance = strategy_class(**kwargs)
        logger.info(f"✅ Created strategy instance: {strategy_name}")
        return instance
    except Exception as e:
        raise StrategyError(f"Failed to instantiate strategy {strategy_name}: {e}") from e
