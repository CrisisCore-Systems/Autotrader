"""
Unit tests for exit configuration management.

Tests config loading, validation, merging, and overrides.
"""

import pytest
import tempfile
import yaml
import copy
from pathlib import Path

from src.bouncehunter.exits.config import (
    ExitConfig,
    ExitConfigManager,
    ConfigValidationError,
    DEFAULT_CONFIG
)


class TestExitConfig:
    """Test ExitConfig dataclass."""
    
    def test_get_with_single_key(self):
        """Test get() with single key."""
        config = ExitConfig(DEFAULT_CONFIG)
        
        tier1 = config.get('tier1')
        assert tier1 is not None
        assert 'enabled' in tier1
        
        tier2 = config.get('tier2')
        assert tier2 is not None
        assert 'enabled' in tier2
    
    def test_get_with_nested_keys(self):
        """Test get() with nested keys."""
        config = ExitConfig(DEFAULT_CONFIG)
        
        assert config.get('tier1', 'enabled') is True
        assert config.get('tier1', 'profit_threshold_pct') == 5.0
        assert config.get('tier2', 'profit_threshold_min_pct') == 8.0
        assert config.get('tier2', 'profit_threshold_max_pct') == 10.0
    
    def test_get_tier_config(self):
        """Test get_tier_config() helper."""
        config = ExitConfig(DEFAULT_CONFIG)
        
        tier1 = config.get_tier_config('tier1')
        assert tier1['enabled'] is True
        assert tier1['profit_threshold_pct'] == 5.0
        
        tier2 = config.get_tier_config('tier2')
        assert tier2['profit_threshold_min_pct'] == 8.0
        assert tier2['profit_threshold_max_pct'] == 10.0
    
    def test_is_tier_enabled(self):
        """Test is_tier_enabled() helper."""
        config = ExitConfig(DEFAULT_CONFIG)
        
        assert config.is_tier_enabled('tier1') is True
        assert config.is_tier_enabled('tier2') is True
        assert config.is_tier_enabled('tier3') is False  # Disabled by default


class TestExitConfigManager:
    """Test ExitConfigManager."""
    
    def test_from_default(self):
        """Test creating config from defaults."""
        config = ExitConfigManager.from_default()
        
        assert isinstance(config, ExitConfig)
        assert config.get('tier1', 'enabled') is True
        assert config.get('tier1', 'profit_threshold_pct') == 5.0
    
    def test_from_yaml_with_valid_file(self):
        """Test loading config from YAML file."""
        # Create temp YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                'tier1': {
                    'profit_threshold_pct': 7.0  # Override default
                }
            }, f)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            # Check override applied
            assert config.get('tier1', 'profit_threshold_pct') == 7.0
            
            # Check defaults preserved
            assert config.get('tier1', 'enabled') is True
            assert config.get('tier1', 'exit_percentage') == 30.0
        finally:
            Path(temp_path).unlink()
    
    def test_from_yaml_with_missing_file(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            ExitConfigManager.from_yaml('nonexistent.yaml')
    
    def test_apply_position_overrides(self):
        """Test applying per-position overrides."""
        base_config = ExitConfigManager.from_default()
        
        position = {
            'ticker': 'TEST',
            'exit_config_override': {
                'tier1': {
                    'profit_threshold_pct': 3.0  # Lower than default 5.0
                }
            }
        }
        
        config = ExitConfigManager.apply_position_overrides(base_config, position)
        
        # Check override applied
        assert config.get('tier1', 'profit_threshold_pct') == 3.0
        
        # Check other values preserved
        assert config.get('tier1', 'enabled') is True
        assert config.get('tier2', 'profit_threshold_min_pct') == 8.0
    
    def test_deep_merge(self):
        """Test deep dictionary merge."""
        base = {
            'a': 1,
            'b': {
                'c': 2,
                'd': 3
            }
        }
        
        override = {
            'b': {
                'c': 99  # Override nested value
            },
            'e': 4  # Add new key
        }
        
        result = ExitConfigManager._deep_merge(base.copy(), override)
        
        assert result['a'] == 1
        assert result['b']['c'] == 99  # Overridden
        assert result['b']['d'] == 3   # Preserved
        assert result['e'] == 4        # Added


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_valid_default_config(self):
        """Test that default config passes validation."""
        # Should not raise
        config = ExitConfigManager.from_default()
        assert config is not None
    
    def test_total_percentage_exceeds_100(self):
        """Test validation catches total exit % > 100%."""
        invalid_config = copy.deepcopy(DEFAULT_CONFIG)
        invalid_config['tier1']['exit_percentage'] = 60
        invalid_config['tier2']['exit_percentage'] = 50
        # Total: 60 + 50 = 110%
        
        with pytest.raises(ConfigValidationError, match="Total exit percentage"):
            ExitConfigManager._validate_config(invalid_config)
    
    def test_tier2_threshold_less_than_tier1(self):
        """Test validation catches tier-2 threshold < tier-1."""
        invalid_config = copy.deepcopy(DEFAULT_CONFIG)
        invalid_config['tier1']['profit_threshold_pct'] = 10.0
        invalid_config['tier2']['profit_threshold_min_pct'] = 5.0  # Less than tier-1
        
        with pytest.raises(ConfigValidationError, match="Tier-2 minimum threshold"):
            ExitConfigManager._validate_config(invalid_config)
    
    def test_invalid_time_window(self):
        """Test validation catches invalid time windows."""
        invalid_config = copy.deepcopy(DEFAULT_CONFIG)
        invalid_config['tier1']['time_window_start'] = '16:00'  # Start after end
        invalid_config['tier1']['time_window_end'] = '15:55'
        
        with pytest.raises(ConfigValidationError, match="time window"):
            ExitConfigManager._validate_config(invalid_config)
    
    def test_negative_exit_percentage(self):
        """Test validation catches invalid exit percentages."""
        invalid_config = copy.deepcopy(DEFAULT_CONFIG)
        invalid_config['tier1']['exit_percentage'] = -5.0
        
        with pytest.raises(ConfigValidationError, match="exit_percentage must be 0-100"):
            ExitConfigManager._validate_config(invalid_config)
    
    def test_percentage_out_of_range(self):
        """Test validation catches percentages out of 0-100 range."""
        invalid_config = copy.deepcopy(DEFAULT_CONFIG)
        invalid_config['tier1']['exit_percentage'] = 150
        
        with pytest.raises(ConfigValidationError, match="Total exit percentage"):
            ExitConfigManager._validate_config(invalid_config)
    
    def test_minimum_parameter_violation(self):
        """Test validation catches values below minimums."""
        invalid_config = copy.deepcopy(DEFAULT_CONFIG)
        invalid_config['monitoring']['poll_interval_seconds'] = 30  # Below minimum 60
        
        with pytest.raises(ConfigValidationError, match="poll_interval_seconds must be >= 60"):
            ExitConfigManager._validate_config(invalid_config)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
