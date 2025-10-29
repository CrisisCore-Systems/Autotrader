"""
Configuration management for intelligent exit system.

Implements a 3-layer configuration system:
1. Default configuration (hardcoded)
2. YAML file overrides (user configuration)
3. Per-position overrides (runtime)

Example:
    >>> config = ExitConfigManager.from_yaml('configs/intelligent_exits.yaml')
    >>> tier1_threshold = config.get('tier1', 'profit_threshold_pct')
    >>> 5.0
"""

import copy
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


# Default configuration - all values have safe defaults
DEFAULT_CONFIG = {
    "tier1": {
        "enabled": True,
        "profit_threshold_pct": 5.0,
        "exit_percentage": 30.0,
        "time_window_start": "15:50",  # 3:50 PM ET
        "time_window_end": "15:55",    # 3:55 PM ET
        "min_trading_days": 1,
        "max_trading_days": 1,
        "min_shares_remaining": 5,
        "min_position_size": 10,
    },
    "tier2": {
        "enabled": True,
        "profit_threshold_min_pct": 8.0,
        "profit_threshold_max_pct": 10.0,
        "exit_percentage": 40.0,
        "min_trading_days": 2,  # Day 2+ only (avoid PDT)
        "volume_spike_threshold": 2.0,
        "max_spread_pct": 2.0,
        "cooldown_minutes": 30,
        "min_shares_remaining": 5,
        "min_position_size": 10,
    },
    "tier3": {
        "enabled": False,  # Not implemented yet
        "trail_stop_pct": 3.0,
        "activate_after": "tier1_or_tier2",
    },
    "monitoring": {
        "poll_interval_seconds": 300,  # 5 minutes
        "max_positions_per_cycle": 20,
        "api_timeout_seconds": 10,
        "max_retries": 3,
        "circuit_breaker_threshold": 3,
        "enable_caching": True,
        "cache_ttl_seconds": 60,
    },
    "safety": {
        "max_exits_per_cycle": 3,
        "min_position_size_shares": 10,
        "max_daily_exits": 10,
        "require_volume_confirmation": True,
        "dry_run_mode": False,
    },
    "adjustments": {
        "enabled": False,  # Disabled by default for backward compatibility
        "volatility": {
            "enabled": True,
            "vix_low_threshold": 15,
            "vix_normal_threshold": 20,
            "vix_high_threshold": 30,
            "tier1_adjustment_low": 0.5,
            "tier1_adjustment_normal": 0.0,
            "tier1_adjustment_high": -1.0,
            "tier1_adjustment_extreme": -2.0,
            "tier2_adjustment_low": 1.0,
            "tier2_adjustment_normal": 0.0,
            "tier2_adjustment_high": -1.5,
            "tier2_adjustment_extreme": -3.0,
            "cache_ttl_seconds": 300,
            "fallback_vix": 20.0,
        },
        "time_decay": {
            "enabled": True,
            "market_open": "09:30",
            "market_close": "16:00",
            "tier1_max_decay_pct": -1.5,
            "tier2_max_decay_pct": -2.0,
        },
        "regime": {
            "enabled": True,
            "spy_symbol": "SPY",
            "short_window": 20,
            "long_window": 50,
            "sideways_threshold_pct": 0.5,
            "tier1_adjustment_bull": -0.5,
            "tier1_adjustment_bear": 1.0,
            "tier1_adjustment_sideways": 0.0,
            "tier2_adjustment_bull": -1.0,
            "tier2_adjustment_bear": 1.5,
            "tier2_adjustment_sideways": 0.0,
            "cache_ttl_hours": 24,
            "fallback_regime": "SIDEWAYS",
        },
        "symbol_learning": {
            "enabled": True,
            "min_exits_for_adjustment": 5,
            "win_rate_threshold": 0.60,
            "adjustment_magnitude_pct": 0.5,
            "persistence_enabled": True,
            "persistence_file": "reports/symbol_adjustments.json",
            "save_interval_seconds": 300,
            "max_symbols_tracked": 500,
        },
        "combination": {
            "tier1_min_target_pct": 2.0,
            "tier1_max_target_pct": 8.0,
            "tier2_min_target_pct": 5.0,
            "tier2_max_target_pct": 15.0,
            "round_to_decimal_places": 1,
        },
    },
    "vix_provider": {
        "provider_type": "fallback",  # "alpaca", "mock", or "fallback"
        "alpaca": {
            "base_url": "https://paper-api.alpaca.markets",
        },
        "mock": {
            "fixed_vix": 20.0,
        },
        "fallback": {
            "primary_provider": "alpaca",
            "default_vix": 20.0,
        },
    },
    "regime_detector": {
        "detector_type": "spy",  # "spy" or "mock"
        "spy": {
            "price_provider": "alpaca",
            "symbol": "SPY",
            "short_window": 20,
            "long_window": 50,
            "sideways_threshold_pct": 0.5,
            "cache_ttl_hours": 24,
        },
        "mock": {
            "fixed_regime": "SIDEWAYS",  # "BULL", "BEAR", or "SIDEWAYS"
        },
    },
}


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


@dataclass
class ExitConfig:
    """
    Validated configuration for intelligent exits.
    
    Attributes:
        config: Full configuration dictionary
        source: Configuration source ('default', 'yaml', or path)
    """
    config: Dict[str, Any]
    source: str = "default"
    
    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get configuration value by path.
        
        Args:
            *keys: Path to configuration value (e.g., 'tier1', 'profit_threshold_pct')
            default: Default value if path not found
            
        Returns:
            Configuration value or default
            
        Example:
            >>> config.get('tier1', 'profit_threshold_pct')
            5.0
            >>> config.get('tier1', 'nonexistent', default=0)
            0
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def get_tier_config(self, tier: str) -> Dict[str, Any]:
        """Get configuration for specific tier."""
        return self.config.get(tier, {})
    
    def is_tier_enabled(self, tier: str) -> bool:
        """Check if tier is enabled."""
        return self.get(tier, 'enabled', default=False)
    
    def is_adjustments_enabled(self) -> bool:
        """Check if intelligent adjustments are enabled."""
        return self.get('adjustments', 'enabled', default=False)
    
    def get_adjustment_config(self) -> Dict[str, Any]:
        """Get full adjustment configuration."""
        return self.config.get('adjustments', {})
    
    def get_volatility_config(self) -> Dict[str, Any]:
        """Get volatility adjustment configuration."""
        return self.get('adjustments', 'volatility', default={})
    
    def get_time_decay_config(self) -> Dict[str, Any]:
        """Get time decay adjustment configuration."""
        return self.get('adjustments', 'time_decay', default={})
    
    def get_regime_config(self) -> Dict[str, Any]:
        """Get regime adjustment configuration."""
        return self.get('adjustments', 'regime', default={})
    
    def get_symbol_learning_config(self) -> Dict[str, Any]:
        """Get symbol learning configuration."""
        return self.get('adjustments', 'symbol_learning', default={})
    
    def get_vix_provider_config(self) -> Dict[str, Any]:
        """Get VIX provider configuration."""
        return self.config.get('vix_provider', {})
    
    def get_regime_detector_config(self) -> Dict[str, Any]:
        """Get regime detector configuration."""
        return self.config.get('regime_detector', {})


class ExitConfigManager:
    """
    Manages loading, merging, and validation of exit configuration.
    
    Implements a layered configuration system with validation.
    """
    
    @staticmethod
    def from_default() -> ExitConfig:
        """
        Create config from defaults only.
        
        Returns:
            ExitConfig with default values
        """
        config_copy = copy.deepcopy(DEFAULT_CONFIG)
        ExitConfigManager._validate_config(config_copy)
        return ExitConfig(config=config_copy, source="default")
    
    @staticmethod
    def from_yaml(yaml_path: str) -> ExitConfig:
        """
        Load configuration from YAML file, merging with defaults.
        
        Args:
            yaml_path: Path to YAML configuration file
            
        Returns:
            ExitConfig with merged configuration
            
        Raises:
            ConfigValidationError: If configuration is invalid
            FileNotFoundError: If YAML file not found
            
        Example:
            >>> config = ExitConfigManager.from_yaml('configs/intelligent_exits.yaml')
        """
        config = copy.deepcopy(DEFAULT_CONFIG)
        
        yaml_file = Path(yaml_path)
        if not yaml_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {yaml_path}")
        
        with open(yaml_file, 'r') as f:
            user_config = yaml.safe_load(f) or {}
        
        # Deep merge user config into defaults
        config = ExitConfigManager._deep_merge(config, user_config)
        
        # Validate merged config
        ExitConfigManager._validate_config(config)
        
        return ExitConfig(config=config, source=str(yaml_path))
    
    @staticmethod
    def apply_position_overrides(config: ExitConfig, position: Dict[str, Any]) -> ExitConfig:
        """
        Apply position-specific configuration overrides.
        
        Args:
            config: Base configuration
            position: Position dictionary with optional 'exit_config_override'
            
        Returns:
            New ExitConfig with overrides applied
            
        Example:
            >>> position = {'ticker': 'INTR', 'exit_config_override': {
            ...     'tier1': {'profit_threshold_pct': 4.0}
            ... }}
            >>> pos_config = ExitConfigManager.apply_position_overrides(config, position)
        """
        if 'exit_config_override' not in position:
            return config
        
        config_copy = copy.deepcopy(config.config)
        overrides = position['exit_config_override']
        
        merged = ExitConfigManager._deep_merge(config_copy, overrides)
        ExitConfigManager._validate_config(merged)
        
        return ExitConfig(config=merged, source=f"position_{position.get('ticker', 'unknown')}")
    
    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary
            
        Returns:
            Merged dictionary
        """
        result = copy.deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ExitConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def _validate_config(config: Dict) -> None:
        """
        Validate configuration for logical consistency.
        
        Args:
            config: Configuration dictionary to validate
            
        Raises:
            ConfigValidationError: If validation fails
        """
        # Tier percentages check
        tier1_pct = config.get('tier1', {}).get('exit_percentage', 0)
        tier2_pct = config.get('tier2', {}).get('exit_percentage', 0)
        total_exit_pct = tier1_pct + tier2_pct
        
        if total_exit_pct > 100:
            raise ConfigValidationError(
                f"Total exit percentage ({total_exit_pct}%) exceeds 100%. "
                f"Tier-1: {tier1_pct}%, Tier-2: {tier2_pct}%"
            )
        
        # Profit threshold ordering
        tier1_threshold = config.get('tier1', {}).get('profit_threshold_pct', 0)
        tier2_min = config.get('tier2', {}).get('profit_threshold_min_pct', 0)
        tier2_max = config.get('tier2', {}).get('profit_threshold_max_pct', 0)
        
        if tier2_min <= tier1_threshold:
            raise ConfigValidationError(
                f"Tier-2 minimum threshold ({tier2_min}%) must be greater than "
                f"Tier-1 threshold ({tier1_threshold}%)"
            )
        
        if tier2_max <= tier2_min:
            raise ConfigValidationError(
                f"Tier-2 maximum threshold ({tier2_max}%) must be greater than "
                f"minimum ({tier2_min}%)"
            )
        
        # Time window validation
        time_start = config.get('tier1', {}).get('time_window_start', '15:50')
        time_end = config.get('tier1', {}).get('time_window_end', '15:55')
        
        if time_start >= time_end:
            raise ConfigValidationError(
                f"Tier-1 time window invalid: start ({time_start}) >= end ({time_end})"
            )
        
        # Positive value checks
        for tier in ['tier1', 'tier2']:
            tier_config = config.get(tier, {})
            
            if tier_config.get('min_shares_remaining', 5) < 0:
                raise ConfigValidationError(f"{tier}.min_shares_remaining must be >= 0")
            
            if tier_config.get('min_position_size', 10) < 1:
                raise ConfigValidationError(f"{tier}.min_position_size must be >= 1")
            
            if tier_config.get('exit_percentage', 30) < 0 or tier_config.get('exit_percentage', 30) > 100:
                raise ConfigValidationError(f"{tier}.exit_percentage must be 0-100")
        
        # Monitoring parameters
        monitoring = config.get('monitoring', {})
        
        if monitoring.get('poll_interval_seconds', 300) < 60:
            raise ConfigValidationError("poll_interval_seconds must be >= 60 (1 minute minimum)")
        
        if monitoring.get('max_retries', 3) < 1:
            raise ConfigValidationError("max_retries must be >= 1")
        
        if monitoring.get('circuit_breaker_threshold', 3) < 1:
            raise ConfigValidationError("circuit_breaker_threshold must be >= 1")
        
        # Adjustment configuration validation
        if 'adjustments' in config:
            ExitConfigManager._validate_adjustment_config(config['adjustments'])
        
        # VIX provider validation
        if 'vix_provider' in config:
            ExitConfigManager._validate_vix_provider_config(config['vix_provider'])
        
        # Regime detector validation
        if 'regime_detector' in config:
            ExitConfigManager._validate_regime_detector_config(config['regime_detector'])
    
    @staticmethod
    @staticmethod
    def _validate_volatility_config(vol: Dict) -> None:
        """Validate volatility configuration section."""
        # VIX thresholds
        vix_low = vol.get('vix_low_threshold', 15)
        vix_normal = vol.get('vix_normal_threshold', 20)
        vix_high = vol.get('vix_high_threshold', 30)
        
        if not (0 < vix_low < 100):
            raise ConfigValidationError(f"vix_low_threshold must be 0-100, got {vix_low}")
        if not (0 < vix_normal < 100):
            raise ConfigValidationError(f"vix_normal_threshold must be 0-100, got {vix_normal}")
        if not (0 < vix_high < 100):
            raise ConfigValidationError(f"vix_high_threshold must be 0-100, got {vix_high}")
        
        if not (vix_low < vix_normal < vix_high):
            raise ConfigValidationError(
                f"VIX thresholds must be ordered: low < normal < high. "
                f"Got low={vix_low}, normal={vix_normal}, high={vix_high}"
            )
        
        # Adjustment ranges (should be reasonable: -10% to +10%)
        adjustment_keys = [
            'tier1_adjustment_low', 'tier1_adjustment_normal', 'tier1_adjustment_high',
            'tier1_adjustment_extreme', 'tier2_adjustment_low', 'tier2_adjustment_normal',
            'tier2_adjustment_high', 'tier2_adjustment_extreme'
        ]
        for key in adjustment_keys:
            value = vol.get(key, 0.0)
            if not (-10.0 <= value <= 10.0):
                raise ConfigValidationError(f"volatility.{key} must be -10 to +10, got {value}")
        
        # Cache TTL
        cache_ttl = vol.get('cache_ttl_seconds', 300)
        if cache_ttl < 0:
            raise ConfigValidationError(f"cache_ttl_seconds must be >= 0, got {cache_ttl}")
        
        # Fallback VIX
        fallback_vix = vol.get('fallback_vix', 20.0)
        if not (0 < fallback_vix < 100):
            raise ConfigValidationError(f"fallback_vix must be 0-100, got {fallback_vix}")
    
    @staticmethod
    def _validate_time_decay_config(time_decay: Dict) -> None:
        """Validate time decay configuration section."""
        # Decay percentages (negative or zero, within reasonable range)
        for key in ['tier1_max_decay_pct', 'tier2_max_decay_pct']:
            value = time_decay.get(key, 0.0)
            if not (-10.0 <= value <= 0.0):
                raise ConfigValidationError(f"time_decay.{key} must be -10 to 0, got {value}")
    
    @staticmethod
    def _validate_regime_config(regime: Dict) -> None:
        """Validate regime configuration section."""
        # SMA windows
        short_window = regime.get('short_window', 20)
        long_window = regime.get('long_window', 50)
        
        if short_window < 1:
            raise ConfigValidationError(f"short_window must be >= 1, got {short_window}")
        if long_window < 1:
            raise ConfigValidationError(f"long_window must be >= 1, got {long_window}")
        if short_window >= long_window:
            raise ConfigValidationError(
                f"short_window must be < long_window. Got short={short_window}, long={long_window}"
            )
        
        # Sideways threshold
        sideways_threshold = regime.get('sideways_threshold_pct', 0.5)
        if not (0.0 <= sideways_threshold <= 10.0):
            raise ConfigValidationError(f"sideways_threshold_pct must be 0-10, got {sideways_threshold}")
        
        # Adjustment ranges
        adjustment_keys = [
            'tier1_adjustment_bull', 'tier1_adjustment_bear', 'tier1_adjustment_sideways',
            'tier2_adjustment_bull', 'tier2_adjustment_bear', 'tier2_adjustment_sideways'
        ]
        for key in adjustment_keys:
            value = regime.get(key, 0.0)
            if not (-10.0 <= value <= 10.0):
                raise ConfigValidationError(f"regime.{key} must be -10 to +10, got {value}")
        
        # Cache TTL
        cache_ttl = regime.get('cache_ttl_hours', 24)
        if cache_ttl < 0:
            raise ConfigValidationError(f"cache_ttl_hours must be >= 0, got {cache_ttl}")
    
    @staticmethod
    def _validate_symbol_learning_config(learning: Dict) -> None:
        """Validate symbol learning configuration section."""
        # Min exits threshold
        min_exits = learning.get('min_exits_for_adjustment', 5)
        if min_exits < 1:
            raise ConfigValidationError(f"min_exits_for_adjustment must be >= 1, got {min_exits}")
        
        # Win rate threshold
        win_rate = learning.get('win_rate_threshold', 0.60)
        if not (0.0 <= win_rate <= 1.0):
            raise ConfigValidationError(f"win_rate_threshold must be 0.0-1.0, got {win_rate}")
        
        # Adjustment magnitude
        magnitude = learning.get('adjustment_magnitude_pct', 0.5)
        if not (0.0 <= magnitude <= 5.0):
            raise ConfigValidationError(f"adjustment_magnitude_pct must be 0-5, got {magnitude}")
        
        # Save interval
        save_interval = learning.get('save_interval_seconds', 300)
        if save_interval < 0:
            raise ConfigValidationError(f"save_interval_seconds must be >= 0, got {save_interval}")
        
        # Max symbols
        max_symbols = learning.get('max_symbols_tracked', 500)
        if max_symbols < 1:
            raise ConfigValidationError(f"max_symbols_tracked must be >= 1, got {max_symbols}")
    
    @staticmethod
    def _validate_combination_config(combo: Dict) -> None:
        """Validate combination configuration section."""
        # Tier1 bounds
        tier1_min = combo.get('tier1_min_target_pct', 2.0)
        tier1_max = combo.get('tier1_max_target_pct', 8.0)
        
        if tier1_min < 0:
            raise ConfigValidationError(f"tier1_min_target_pct must be >= 0, got {tier1_min}")
        if tier1_max <= tier1_min:
            raise ConfigValidationError(
                f"tier1_max_target_pct must be > tier1_min_target_pct. "
                f"Got min={tier1_min}, max={tier1_max}"
            )
        
        # Tier2 bounds
        tier2_min = combo.get('tier2_min_target_pct', 5.0)
        tier2_max = combo.get('tier2_max_target_pct', 15.0)
        
        if tier2_min < 0:
            raise ConfigValidationError(f"tier2_min_target_pct must be >= 0, got {tier2_min}")
        if tier2_max <= tier2_min:
            raise ConfigValidationError(
                f"tier2_max_target_pct must be > tier2_min_target_pct. "
                f"Got min={tier2_min}, max={tier2_max}"
            )
        
        # Tier2 min should be >= Tier1 min (logical ordering)
        if tier2_min < tier1_min:
            raise ConfigValidationError(
                f"tier2_min_target_pct should be >= tier1_min_target_pct. "
                f"Got tier1_min={tier1_min}, tier2_min={tier2_min}"
            )
        
        # Rounding decimal places
        decimal_places = combo.get('round_to_decimal_places', 1)
        if not (0 <= decimal_places <= 4):
            raise ConfigValidationError(f"round_to_decimal_places must be 0-4, got {decimal_places}")
    
    @staticmethod
    def _validate_adjustment_config(adj_config: Dict) -> None:
        """
        Validate adjustment configuration.
        
        Args:
            adj_config: Adjustment configuration dictionary
            
        Raises:
            ConfigValidationError: If adjustment config is invalid
        """
        # Validate each section if present
        if 'volatility' in adj_config:
            ExitConfigManager._validate_volatility_config(adj_config['volatility'])
        
        if 'time_decay' in adj_config:
            ExitConfigManager._validate_time_decay_config(adj_config['time_decay'])
        
        if 'regime' in adj_config:
            ExitConfigManager._validate_regime_config(adj_config['regime'])
        
        if 'symbol_learning' in adj_config:
            ExitConfigManager._validate_symbol_learning_config(adj_config['symbol_learning'])
        
        if 'combination' in adj_config:
            ExitConfigManager._validate_combination_config(adj_config['combination'])
    
    @staticmethod
    def _validate_vix_provider_config(vix_config: Dict) -> None:
        """
        Validate VIX provider configuration.
        
        Args:
            vix_config: VIX provider configuration
            
        Raises:
            ConfigValidationError: If VIX config is invalid
        """
        provider_type = vix_config.get('provider_type', 'fallback')
        
        if provider_type not in ['alpaca', 'mock', 'fallback']:
            raise ConfigValidationError(
                f"vix_provider.provider_type must be 'alpaca', 'mock', or 'fallback'. "
                f"Got '{provider_type}'"
            )
        
        # Validate mock provider settings
        if 'mock' in vix_config:
            fixed_vix = vix_config['mock'].get('fixed_vix', 20.0)
            if not (0 < fixed_vix < 100):
                raise ConfigValidationError(
                    f"vix_provider.mock.fixed_vix must be 0-100, got {fixed_vix}"
                )
        
        # Validate fallback settings
        if 'fallback' in vix_config:
            fallback = vix_config['fallback']
            
            primary = fallback.get('primary_provider', 'alpaca')
            if primary not in ['alpaca', 'mock']:
                raise ConfigValidationError(
                    f"vix_provider.fallback.primary_provider must be 'alpaca' or 'mock'. "
                    f"Got '{primary}'"
                )
            
            default_vix = fallback.get('default_vix', 20.0)
            if not (0 < default_vix < 100):
                raise ConfigValidationError(
                    f"vix_provider.fallback.default_vix must be 0-100, got {default_vix}"
                )
    
    @staticmethod
    def _validate_regime_detector_config(detector_config: Dict) -> None:
        """
        Validate regime detector configuration.
        
        Args:
            detector_config: Regime detector configuration
            
        Raises:
            ConfigValidationError: If detector config is invalid
        """
        detector_type = detector_config.get('detector_type', 'spy')
        
        if detector_type not in ['spy', 'mock']:
            raise ConfigValidationError(
                f"regime_detector.detector_type must be 'spy' or 'mock'. "
                f"Got '{detector_type}'"
            )
        
        # Validate SPY detector settings
        if 'spy' in detector_config:
            spy = detector_config['spy']
            
            short_window = spy.get('short_window', 20)
            long_window = spy.get('long_window', 50)
            
            if short_window < 1:
                raise ConfigValidationError(
                    f"regime_detector.spy.short_window must be >= 1, got {short_window}"
                )
            if long_window < 1:
                raise ConfigValidationError(
                    f"regime_detector.spy.long_window must be >= 1, got {long_window}"
                )
            if short_window >= long_window:
                raise ConfigValidationError(
                    f"regime_detector.spy.short_window must be < long_window. "
                    f"Got short={short_window}, long={long_window}"
                )
            
            sideways_threshold = spy.get('sideways_threshold_pct', 0.5)
            if not (0.0 <= sideways_threshold <= 10.0):
                raise ConfigValidationError(
                    f"regime_detector.spy.sideways_threshold_pct must be 0-10, got {sideways_threshold}"
                )
            
            cache_ttl = spy.get('cache_ttl_hours', 24)
            if cache_ttl < 0:
                raise ConfigValidationError(
                    f"regime_detector.spy.cache_ttl_hours must be >= 0, got {cache_ttl}"
                )
        
        # Validate mock detector settings
        if 'mock' in detector_config:
            fixed_regime = detector_config['mock'].get('fixed_regime', 'SIDEWAYS')
            if fixed_regime not in ['BULL', 'BEAR', 'SIDEWAYS']:
                raise ConfigValidationError(
                    f"regime_detector.mock.fixed_regime must be 'BULL', 'BEAR', or 'SIDEWAYS'. "
                    f"Got '{fixed_regime}'"
                )
