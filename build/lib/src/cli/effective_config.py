"""Effective configuration printer for debugging.

Shows merged configuration from all sources with origin metadata.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

logger = logging.getLogger(__name__)


class ConfigSource(Enum):
    """Source of a configuration value."""
    DEFAULT = "default"
    FILE = "file"
    ENV = "env"
    CLI = "cli"


@dataclass
class ConfigValue:
    """A configuration value with metadata."""
    value: Any
    source: ConfigSource
    origin: str  # File path, env var name, or CLI flag
    override_chain: List[str] = field(default_factory=list)


class EffectiveConfigBuilder:
    """Builds effective configuration with origin tracking."""
    
    def __init__(self):
        """Initialize config builder."""
        self._config: Dict[str, ConfigValue] = {}
        self._sensitive_keys = {
            "api_key", "api_secret", "token", "password", "secret",
            "private_key", "auth", "credentials"
        }
    
    def add_defaults(self, defaults: Dict[str, Any]) -> None:
        """Add default configuration values.
        
        Args:
            defaults: Default configuration dictionary
        """
        self._add_dict(defaults, ConfigSource.DEFAULT, "defaults")
    
    def add_from_file(self, file_path: Path) -> None:
        """Add configuration from YAML file.
        
        Args:
            file_path: Path to YAML configuration file
        """
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
            
            if data:
                self._add_dict(data, ConfigSource.FILE, str(file_path))
                logger.info(f"✅ Loaded config from file: {file_path}")
        
        except Exception as e:
            logger.warning(f"Failed to load config from {file_path}: {e}")
    
    def add_from_env(self, prefix: str = "AUTOTRADER_") -> None:
        """Add configuration from environment variables.
        
        Args:
            prefix: Prefix for environment variables
        """
        for key, value in os.environ.items():
            if key.startswith(prefix):
                # Convert AUTOTRADER_SCANNER__LIQUIDITY to scanner.liquidity
                config_key = key[len(prefix):].lower().replace("__", ".")
                
                # Try to parse as JSON for complex values
                try:
                    parsed_value = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    parsed_value = value
                
                self._set_value(
                    config_key,
                    parsed_value,
                    ConfigSource.ENV,
                    key
                )
        
        logger.info(f"✅ Loaded config from environment variables (prefix: {prefix})")
    
    def add_from_cli(self, cli_args: Dict[str, Any]) -> None:
        """Add configuration from CLI arguments.
        
        Args:
            cli_args: Dictionary of CLI arguments
        """
        for key, value in cli_args.items():
            if value is not None:  # Only add explicitly set values
                self._set_value(
                    key,
                    value,
                    ConfigSource.CLI,
                    f"--{key.replace('_', '-')}"
                )
        
        logger.info("✅ Loaded config from CLI arguments")
    
    def _add_dict(
        self,
        data: Dict[str, Any],
        source: ConfigSource,
        origin: str,
        prefix: str = "",
    ) -> None:
        """Recursively add dictionary values.
        
        Args:
            data: Dictionary to add
            source: Source of configuration
            origin: Origin identifier
            prefix: Key prefix for nested values
        """
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recurse for nested dictionaries
                self._add_dict(value, source, origin, full_key)
            else:
                self._set_value(full_key, value, source, origin)
    
    def _set_value(
        self,
        key: str,
        value: Any,
        source: ConfigSource,
        origin: str,
    ) -> None:
        """Set a configuration value.
        
        Args:
            key: Configuration key (dot-separated)
            value: Configuration value
            source: Source of configuration
            origin: Origin identifier
        """
        if key in self._config:
            # Value being overridden
            existing = self._config[key]
            override_chain = existing.override_chain + [
                f"{existing.source.value}:{existing.origin}"
            ]
        else:
            override_chain = []
        
        self._config[key] = ConfigValue(
            value=value,
            source=source,
            origin=origin,
            override_chain=override_chain,
        )
    
    def get_effective_config(self) -> Dict[str, Any]:
        """Get effective configuration (values only).
        
        Returns:
            Dictionary of effective configuration values
        """
        result = {}
        
        for key, config_value in self._config.items():
            # Rebuild nested structure
            self._set_nested_value(result, key, config_value.value)
        
        return result
    
    def get_effective_config_with_metadata(
        self,
        sanitize: bool = True,
    ) -> Dict[str, Any]:
        """Get effective configuration with metadata.
        
        Args:
            sanitize: Whether to sanitize sensitive values
        
        Returns:
            Dictionary with values and metadata
        """
        result = {}
        
        for key, config_value in self._config.items():
            value = config_value.value
            
            # Sanitize sensitive values
            if sanitize and self._is_sensitive_key(key):
                value = "***REDACTED***"
            
            result[key] = {
                "value": value,
                "source": config_value.source.value,
                "origin": config_value.origin,
                "overrides": config_value.override_chain,
            }
        
        return result
    
    def _set_nested_value(
        self,
        target: Dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        """Set a value in nested dictionary structure.
        
        Args:
            target: Target dictionary
            key: Dot-separated key
            value: Value to set
        """
        parts = key.split('.')
        current = target
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if key contains sensitive information.
        
        Args:
            key: Configuration key
        
        Returns:
            True if key is sensitive
        """
        key_lower = key.lower()
        return any(sensitive in key_lower for sensitive in self._sensitive_keys)
    
    def print_effective_config(
        self,
        include_metadata: bool = True,
        sanitize: bool = True,
        format: str = "yaml",
    ) -> None:
        """Print effective configuration.
        
        Args:
            include_metadata: Whether to include metadata
            sanitize: Whether to sanitize sensitive values
            format: Output format ("yaml" or "json")
        """
        print("\n" + "=" * 80)
        print("EFFECTIVE CONFIGURATION")
        print("=" * 80)
        
        if include_metadata:
            data = self.get_effective_config_with_metadata(sanitize)
            
            print("\nConfiguration precedence: default < file < env < cli")
            print(f"Total settings: {len(data)}")
            print("\n" + "-" * 80)
            
            # Group by source
            by_source: Dict[str, List[str]] = {}
            for key, meta in data.items():
                source = meta["source"]
                by_source.setdefault(source, []).append(key)
            
            print("\nSettings by source:")
            for source in ["default", "file", "env", "cli"]:
                count = len(by_source.get(source, []))
                print(f"  {source:10s}: {count:3d} setting(s)")
            
            print("\n" + "-" * 80)
            print("\nDetailed configuration:\n")
            
            # Print each setting with metadata
            for key in sorted(data.keys()):
                meta = data[key]
                print(f"{key}:")
                print(f"  value: {meta['value']}")
                print(f"  source: {meta['source']} ({meta['origin']})")
                if meta['overrides']:
                    print(f"  overrides: {' -> '.join(meta['overrides'])}")
                print()
        
        else:
            # Just print values
            data = self.get_effective_config()
            
            if format == "json":
                print(json.dumps(data, indent=2))
            else:  # yaml
                print(yaml.dump(data, default_flow_style=False, sort_keys=True))
        
        print("=" * 80 + "\n")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary.
        
        Returns:
            Summary dictionary
        """
        by_source: Dict[str, int] = {}
        overridden_count = 0
        
        for config_value in self._config.values():
            source = config_value.source.value
            by_source[source] = by_source.get(source, 0) + 1
            
            if config_value.override_chain:
                overridden_count += 1
        
        return {
            "total_settings": len(self._config),
            "by_source": by_source,
            "overridden": overridden_count,
        }


def print_effective_config(
    config_file: Optional[Path] = None,
    cli_args: Optional[Dict[str, Any]] = None,
    env_prefix: str = "AUTOTRADER_",
    include_metadata: bool = True,
    sanitize: bool = True,
) -> None:
    """Print effective configuration from all sources.
    
    Args:
        config_file: Path to configuration file
        cli_args: CLI arguments dictionary
        env_prefix: Environment variable prefix
        include_metadata: Whether to include metadata
        sanitize: Whether to sanitize sensitive values
    """
    builder = EffectiveConfigBuilder()
    
    # Load defaults (would come from your actual defaults)
    defaults = {
        "scanner": {
            "liquidity_threshold": 50000,
            "max_results": 100,
        },
        "alerts": {
            "enabled": False,
        },
    }
    builder.add_defaults(defaults)
    
    # Load from file
    if config_file and config_file.exists():
        builder.add_from_file(config_file)
    
    # Load from environment
    builder.add_from_env(env_prefix)
    
    # Load from CLI
    if cli_args:
        builder.add_from_cli(cli_args)
    
    # Print
    builder.print_effective_config(include_metadata, sanitize)


if __name__ == "__main__":
    # Test the config builder
    import sys
    
    # Create test config file
    test_config = Path("/tmp/test_config.yaml")
    with open(test_config, "w") as f:
        yaml.dump({
            "scanner": {
                "liquidity_threshold": 75000,
                "max_results": 50,
            },
            "api_key": "secret123",
        }, f)
    
    # Set test env var
    os.environ["AUTOTRADER_ALERTS__ENABLED"] = "true"
    os.environ["AUTOTRADER_API_KEY"] = "env_secret"
    
    # Test CLI args
    cli_args = {
        "max_results": 25,
        "output": "results.json",
    }
    
    print_effective_config(
        config_file=test_config,
        cli_args=cli_args,
        include_metadata=True,
        sanitize=True,
    )
    
    # Cleanup
    test_config.unlink(missing_ok=True)
