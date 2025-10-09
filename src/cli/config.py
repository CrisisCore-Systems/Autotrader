"""Configuration resolution with YAML, argparse, and environment variable support.

This module provides configuration loading and merging from multiple sources
with explicit precedence rules.

Configuration Precedence (highest to lowest):
---------------------------------------------
1. CLI Arguments - Explicit command-line flags (--option value)
2. Environment Variables - AUTOTRADER_* prefixed variables
3. YAML Configuration File - File specified via --config

This means:
- CLI arguments ALWAYS override environment variables and file settings
- Environment variables override file settings but not CLI arguments
- File settings are used only if not specified in CLI or environment

Example:
    config.yaml: log_level: INFO
    Environment: AUTOTRADER_LOG_LEVEL=WARNING
    CLI: --log-level DEBUG
    Result: DEBUG (CLI wins)

Features:
- YAML configuration loading
- Merging YAML defaults with argparse CLI arguments
- Environment variable overrides (AUTOTRADER_ prefix)
- JSON schema validation for outputs
- Deep dictionary merging for nested configs
"""

from __future__ import annotations

import json
import logging
import os
from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration resolution fails."""
    pass


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load configuration from YAML file.
    
    Args:
        config_path: Path to YAML configuration file
        
    Returns:
        Dictionary with configuration values
        
    Raises:
        ConfigError: If file cannot be loaded or parsed
    """
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")
    
    try:
        with config_path.open('r') as f:
            config = yaml.safe_load(f)
        
        if config is None:
            logger.warning(f"Empty configuration file: {config_path}")
            return {}
        
        if not isinstance(config, dict):
            raise ConfigError(f"Configuration must be a dictionary, got {type(config)}")
        
        logger.info(f"✅ Loaded configuration from {config_path}")
        return config
    
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse YAML configuration: {e}") from e
    except Exception as e:
        raise ConfigError(f"Failed to load configuration: {e}") from e


def get_env_overrides(prefix: str = "AUTOTRADER_") -> dict[str, Any]:
    """Extract configuration overrides from environment variables.
    
    Supports the following patterns:
    - AUTOTRADER_LOG_LEVEL=DEBUG → log_level: DEBUG
    - AUTOTRADER_OUTPUT_DIR=/tmp/results → output_dir: /tmp/results
    - AUTOTRADER_SCANNER_LIQUIDITY_THRESHOLD=50000 → scanner.liquidity_threshold: 50000
    
    Args:
        prefix: Environment variable prefix (default: AUTOTRADER_)
        
    Returns:
        Dictionary with configuration overrides
    """
    overrides: dict[str, Any] = {}
    
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        
        # Remove prefix and convert to lowercase
        config_key = key[len(prefix):].lower()
        
        # Handle nested keys (e.g., SCANNER_LIQUIDITY_THRESHOLD)
        if "_" in config_key:
            parts = config_key.split("_")
            current = overrides
            
            # Navigate/create nested structure
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the final value
            final_key = parts[-1]
            current[final_key] = _parse_env_value(value)
        else:
            overrides[config_key] = _parse_env_value(value)
    
    if overrides:
        logger.info(f"✅ Applied {len(overrides)} environment variable override(s)")
        logger.debug(f"Environment overrides: {overrides}")
    
    return overrides


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value to appropriate type.
    
    Attempts to parse as:
    1. Boolean (true/false, yes/no, 1/0)
    2. Integer
    3. Float
    4. JSON (for lists/dicts)
    5. String (fallback)
    
    Args:
        value: String value from environment variable
        
    Returns:
        Parsed value in appropriate type
    """
    # Boolean parsing
    if value.lower() in ('true', 'yes', '1'):
        return True
    if value.lower() in ('false', 'no', '0'):
        return False
    
    # Numeric parsing
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    
    # JSON parsing (for lists/dicts)
    if value.startswith(('[', '{')):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    
    # Return as string
    return value


def merge_configs(
    yaml_config: dict[str, Any],
    cli_args: Namespace,
    env_overrides: dict[str, Any],
) -> dict[str, Any]:
    """Merge configuration from multiple sources.
    
    Priority order (highest to lowest):
    1. CLI arguments (from argparse)
    2. Environment variables (AUTOTRADER_ prefix)
    3. YAML configuration file
    
    Args:
        yaml_config: Configuration from YAML file
        cli_args: Parsed CLI arguments
        env_overrides: Environment variable overrides
        
    Returns:
        Merged configuration dictionary
    """
    # Start with YAML config as base
    config = yaml_config.copy()
    
    # Apply environment overrides
    config = _deep_merge(config, env_overrides)
    
    # Apply CLI arguments (highest priority)
    # Only override if CLI argument was explicitly provided
    cli_dict = vars(cli_args)
    for key, value in cli_dict.items():
        # Skip None values (not provided)
        if value is None:
            continue
        
        # Skip default values for specific flags
        if key == 'config' and value is None:
            continue
        
        config[key] = value
    
    logger.debug(f"Merged configuration: {config}")
    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Dictionary with override values
        
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def validate_output_schema(data: dict[str, Any], schema_path: Path) -> bool:
    """Validate output data against JSON schema.
    
    Args:
        data: Output data to validate
        schema_path: Path to JSON schema file
        
    Returns:
        True if validation passes
        
    Raises:
        ConfigError: If validation fails
    """
    if not schema_path.exists():
        logger.warning(f"Schema file not found: {schema_path}")
        return True  # Skip validation if schema missing
    
    try:
        with schema_path.open('r') as f:
            schema = json.load(f)
        
        # Try to import jsonschema (optional dependency)
        try:
            import jsonschema
            jsonschema.validate(instance=data, schema=schema)
            logger.info("✅ Output validation passed")
            return True
        except ImportError:
            logger.warning("jsonschema not installed, skipping validation")
            return True
        except jsonschema.ValidationError as e:
            raise ConfigError(f"Output validation failed: {e.message}") from e
    
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON schema: {e}") from e
    except Exception as e:
        raise ConfigError(f"Schema validation error: {e}") from e


def resolve_config(
    cli_args: Namespace,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Resolve final configuration from all sources.
    
    This is the main entry point for configuration resolution.
    
    Args:
        cli_args: Parsed CLI arguments
        config_path: Optional path to YAML config (overrides --config arg)
        
    Returns:
        Final merged configuration dictionary
        
    Raises:
        ConfigError: If configuration resolution fails
    """
    # Determine config file path
    if config_path is None and hasattr(cli_args, 'config') and cli_args.config:
        config_path = Path(cli_args.config)
    
    # Load YAML config
    yaml_config = {}
    if config_path:
        yaml_config = load_yaml_config(config_path)
    
    # Get environment overrides
    env_overrides = get_env_overrides()
    
    # Merge all sources
    final_config = merge_configs(yaml_config, cli_args, env_overrides)
    
    logger.info("✅ Configuration resolution complete")
    return final_config


def print_config(config: dict[str, Any], mask_secrets: bool = True) -> None:
    """Pretty-print configuration for debugging.
    
    Args:
        config: Configuration dictionary
        mask_secrets: If True, mask sensitive values (keys containing 'key', 'token', 'secret')
    """
    def _mask_value(key: str, value: Any) -> Any:
        if not mask_secrets:
            return value
        
        sensitive_keys = ('key', 'token', 'secret', 'password', 'credential')
        if any(k in key.lower() for k in sensitive_keys):
            return '***MASKED***'
        
        return value
    
    def _format_dict(d: dict[str, Any], indent: int = 0) -> str:
        lines = []
        for key, value in sorted(d.items()):
            prefix = "  " * indent
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(_format_dict(value, indent + 1))
            else:
                masked_value = _mask_value(key, value)
                lines.append(f"{prefix}{key}: {masked_value}")
        return "\n".join(lines)
    
    print("\n" + "=" * 60)
    print("CONFIGURATION")
    print("=" * 60)
    print(_format_dict(config))
    print("=" * 60 + "\n")
