"""
Tests for configuration loading with adjustment settings.

Tests:
- Loading adjustment configuration from YAML
- Backward compatibility (adjustments disabled by default)
- Helper methods for accessing adjustment configs
- VIX provider and regime detector config loading
"""

import pytest
import tempfile
from pathlib import Path

from src.bouncehunter.exits.config import (
    ExitConfig,
    ExitConfigManager,
    ConfigValidationError,
)


class TestConfigAdjustmentLoading:
    """Test loading adjustment configuration from YAML."""
    
    def test_default_adjustments_disabled(self):
        """Test that adjustments are disabled by default (backward compatibility)."""
        config = ExitConfigManager.from_default()
        
        assert config.is_adjustments_enabled() is False
        assert config.get('adjustments', 'enabled') is False
    
    def test_load_adjustments_from_yaml(self):
        """Test loading adjustments configuration from YAML."""
        yaml_content = """
adjustments:
  enabled: true
  volatility:
    vix_low_threshold: 12
    tier1_adjustment_low: 0.8
  time_decay:
    tier1_max_decay_pct: -2.0
  regime:
    tier1_adjustment_bull: -0.7
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            assert config.is_adjustments_enabled() is True
            assert config.get('adjustments', 'volatility', 'vix_low_threshold') == 12
            assert config.get('adjustments', 'volatility', 'tier1_adjustment_low') == 0.8
            assert config.get('adjustments', 'time_decay', 'tier1_max_decay_pct') == -2.0
            assert config.get('adjustments', 'regime', 'tier1_adjustment_bull') == -0.7
        finally:
            Path(temp_path).unlink()
    
    def test_adjustment_helper_methods(self):
        """Test helper methods for accessing adjustment configs."""
        yaml_content = """
adjustments:
  enabled: true
  volatility:
    enabled: true
    vix_low_threshold: 15
  time_decay:
    enabled: false
    market_open: "09:35"
  regime:
    spy_symbol: "QQQ"
  symbol_learning:
    min_exits_for_adjustment: 8
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            # Test helper methods
            assert config.is_adjustments_enabled() is True
            
            vol_config = config.get_volatility_config()
            assert vol_config['enabled'] is True
            assert vol_config['vix_low_threshold'] == 15
            
            time_config = config.get_time_decay_config()
            assert time_config['enabled'] is False
            assert time_config['market_open'] == "09:35"
            
            regime_config = config.get_regime_config()
            assert regime_config['spy_symbol'] == "QQQ"
            
            learning_config = config.get_symbol_learning_config()
            assert learning_config['min_exits_for_adjustment'] == 8
        finally:
            Path(temp_path).unlink()
    
    def test_vix_provider_config_loading(self):
        """Test loading VIX provider configuration."""
        yaml_content = """
vix_provider:
  provider_type: "mock"
  mock:
    fixed_vix: 25.0
  fallback:
    default_vix: 22.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            vix_config = config.get_vix_provider_config()
            assert vix_config['provider_type'] == "mock"
            assert vix_config['mock']['fixed_vix'] == 25.0
            assert vix_config['fallback']['default_vix'] == 22.0
        finally:
            Path(temp_path).unlink()
    
    def test_regime_detector_config_loading(self):
        """Test loading regime detector configuration."""
        yaml_content = """
regime_detector:
  detector_type: "mock"
  mock:
    fixed_regime: "BULL"
  spy:
    short_window: 10
    long_window: 30
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            detector_config = config.get_regime_detector_config()
            assert detector_config['detector_type'] == "mock"
            assert detector_config['mock']['fixed_regime'] == "BULL"
            assert detector_config['spy']['short_window'] == 10
            assert detector_config['spy']['long_window'] == 30
        finally:
            Path(temp_path).unlink()
    
    def test_partial_adjustment_config(self):
        """Test that partial adjustment config merges with defaults."""
        yaml_content = """
adjustments:
  enabled: true
  volatility:
    vix_low_threshold: 12
    # Other volatility settings use defaults
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            # Custom setting
            assert config.get('adjustments', 'volatility', 'vix_low_threshold') == 12
            
            # Default settings preserved
            assert config.get('adjustments', 'volatility', 'vix_normal_threshold') == 20
            assert config.get('adjustments', 'volatility', 'cache_ttl_seconds') == 300
            assert config.get('adjustments', 'time_decay', 'market_open') == "09:30"
        finally:
            Path(temp_path).unlink()
    
    def test_backward_compatibility_without_adjustments(self):
        """Test that old configs without adjustments section still work."""
        yaml_content = """
tier1:
  enabled: true
  profit_threshold_pct: 6.0
tier2:
  enabled: true
  profit_threshold_min_pct: 9.0
# No adjustments section - should use defaults
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            # Tier configs loaded
            assert config.get('tier1', 'profit_threshold_pct') == 6.0
            assert config.get('tier2', 'profit_threshold_min_pct') == 9.0
            
            # Adjustments disabled by default
            assert config.is_adjustments_enabled() is False
            
            # Default adjustment config available
            assert config.get('adjustments', 'volatility', 'vix_low_threshold') == 15
            assert config.get('adjustments', 'regime', 'spy_symbol') == "SPY"
        finally:
            Path(temp_path).unlink()
    
    def test_get_adjustment_config_method(self):
        """Test getting full adjustment config at once."""
        yaml_content = """
adjustments:
  enabled: true
  volatility:
    vix_low_threshold: 18
  time_decay:
    tier1_max_decay_pct: -1.2
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            
            adjustment_config = config.get_adjustment_config()
            
            assert adjustment_config['enabled'] is True
            assert adjustment_config['volatility']['vix_low_threshold'] == 18
            assert adjustment_config['time_decay']['tier1_max_decay_pct'] == -1.2
            
            # Defaults preserved
            assert adjustment_config['regime']['spy_symbol'] == "SPY"
        finally:
            Path(temp_path).unlink()


class TestConfigProductionTemplates:
    """Test that production config templates are valid."""
    
    def test_load_intelligent_exits_template(self):
        """Test loading the main intelligent_exits.yaml template."""
        config_path = "configs/intelligent_exits.yaml"
        
        # Skip if file doesn't exist (CI environment)
        if not Path(config_path).exists():
            pytest.skip(f"Config template not found: {config_path}")
        
        config = ExitConfigManager.from_yaml(config_path)
        
        # Should load successfully
        assert config is not None
        assert config.source == config_path
        
        # Adjustments enabled in production template
        assert config.is_adjustments_enabled() is True
        
        # Check tier configs
        assert config.is_tier_enabled('tier1') is True
        assert config.is_tier_enabled('tier2') is True
    
    def test_load_paper_trading_template(self):
        """Test loading the paper_trading_adjustments.yaml template."""
        config_path = "configs/paper_trading_adjustments.yaml"
        
        if not Path(config_path).exists():
            pytest.skip(f"Config template not found: {config_path}")
        
        config = ExitConfigManager.from_yaml(config_path)
        
        assert config is not None
        assert config.is_adjustments_enabled() is True
        
        # Paper trading should have DEBUG logging
        logging_level = config.get('logging', 'level', default='INFO')
        assert logging_level == 'DEBUG'
    
    def test_load_live_trading_template(self):
        """Test loading the live_trading_adjustments.yaml template."""
        config_path = "configs/live_trading_adjustments.yaml"
        
        if not Path(config_path).exists():
            pytest.skip(f"Config template not found: {config_path}")
        
        config = ExitConfigManager.from_yaml(config_path)
        
        assert config is not None
        assert config.is_adjustments_enabled() is True
        
        # Live should have INFO logging (not DEBUG)
        logging_level = config.get('logging', 'level', default='DEBUG')
        assert logging_level == 'INFO'
        
        # Live should have tighter safety limits
        max_exits = config.get('safety', 'max_exits_per_cycle', default=10)
        assert max_exits <= 3  # Conservative for live


class TestConfigAdjustmentMerging:
    """Test merging adjustment configs with position overrides."""
    
    def test_position_override_adjustments(self):
        """Test that position overrides can modify adjustment settings."""
        base_config = ExitConfigManager.from_default()
        
        position = {
            'ticker': 'AAPL',
            'exit_config_override': {
                'adjustments': {
                    'enabled': True,
                    'volatility': {
                        'tier1_adjustment_low': 1.0,
                    }
                }
            }
        }
        
        overridden = ExitConfigManager.apply_position_overrides(base_config, position)
        
        # Override applied
        assert overridden.is_adjustments_enabled() is True
        assert overridden.get('adjustments', 'volatility', 'tier1_adjustment_low') == 1.0
        
        # Other defaults preserved
        assert overridden.get('adjustments', 'volatility', 'vix_low_threshold') == 15
    
    def test_position_can_disable_adjustments(self):
        """Test that a position can disable adjustments even if globally enabled."""
        yaml_content = """
adjustments:
  enabled: true
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = ExitConfigManager.from_yaml(temp_path)
            assert config.is_adjustments_enabled() is True
            
            # Position disables adjustments
            position = {
                'ticker': 'TSLA',
                'exit_config_override': {
                    'adjustments': {'enabled': False}
                }
            }
            
            overridden = ExitConfigManager.apply_position_overrides(config, position)
            assert overridden.is_adjustments_enabled() is False
        finally:
            Path(temp_path).unlink()
