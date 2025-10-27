"""
Tests for configuration validation with adjustment settings.

Tests:
- VIX threshold validation
- Adjustment range validation
- SMA window validation
- Cache TTL validation
- Target bounds validation
- Provider type validation
"""

import pytest
import tempfile
from pathlib import Path

from src.bouncehunter.exits.config import (
    ExitConfigManager,
    ConfigValidationError,
)


class TestVolatilityConfigValidation:
    """Test validation of volatility adjustment configuration."""
    
    def test_vix_thresholds_must_be_ordered(self):
        """Test that VIX thresholds must be: low < normal < high."""
        yaml_content = """
adjustments:
  volatility:
    vix_low_threshold: 25
    vix_normal_threshold: 20
    vix_high_threshold: 30
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "VIX thresholds must be ordered" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_vix_thresholds_must_be_positive(self):
        """Test that VIX thresholds must be 0-100."""
        yaml_content = """
adjustments:
  volatility:
    vix_low_threshold: -5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "vix_low_threshold must be 0-100" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_adjustment_ranges_validated(self):
        """Test that volatility adjustments must be -10 to +10."""
        yaml_content = """
adjustments:
  volatility:
    tier1_adjustment_low: 15.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "tier1_adjustment_low must be -10 to +10" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_cache_ttl_must_be_non_negative(self):
        """Test that cache TTL must be >= 0."""
        yaml_content = """
adjustments:
  volatility:
    cache_ttl_seconds: -100
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "cache_ttl_seconds must be >= 0" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_fallback_vix_must_be_valid(self):
        """Test that fallback VIX must be 0-100."""
        yaml_content = """
adjustments:
  volatility:
    fallback_vix: 150
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "fallback_vix must be 0-100" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestTimeDecayConfigValidation:
    """Test validation of time decay configuration."""
    
    def test_decay_must_be_non_positive(self):
        """Test that time decay adjustments must be <= 0."""
        yaml_content = """
adjustments:
  time_decay:
    tier1_max_decay_pct: 2.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "tier1_max_decay_pct must be -10 to 0" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_decay_within_range(self):
        """Test that decay must be within -10 to 0."""
        yaml_content = """
adjustments:
  time_decay:
    tier2_max_decay_pct: -15.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "tier2_max_decay_pct must be -10 to 0" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestRegimeConfigValidation:
    """Test validation of regime adjustment configuration."""
    
    def test_sma_windows_must_be_ordered(self):
        """Test that short_window must be < long_window."""
        yaml_content = """
adjustments:
  regime:
    short_window: 50
    long_window: 20
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "short_window must be < long_window" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_sma_windows_must_be_positive(self):
        """Test that SMA windows must be >= 1."""
        yaml_content = """
adjustments:
  regime:
    short_window: 0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "short_window must be >= 1" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_sideways_threshold_must_be_valid(self):
        """Test that sideways threshold must be 0-10."""
        yaml_content = """
adjustments:
  regime:
    sideways_threshold_pct: 15.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "sideways_threshold_pct must be 0-10" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_regime_adjustments_must_be_in_range(self):
        """Test that regime adjustments must be -10 to +10."""
        yaml_content = """
adjustments:
  regime:
    tier2_adjustment_bull: -12.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "tier2_adjustment_bull must be -10 to +10" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestSymbolLearningConfigValidation:
    """Test validation of symbol learning configuration."""
    
    def test_min_exits_must_be_positive(self):
        """Test that min_exits_for_adjustment must be >= 1."""
        yaml_content = """
adjustments:
  symbol_learning:
    min_exits_for_adjustment: 0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "min_exits_for_adjustment must be >= 1" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_win_rate_threshold_must_be_valid_probability(self):
        """Test that win_rate_threshold must be 0.0-1.0."""
        yaml_content = """
adjustments:
  symbol_learning:
    win_rate_threshold: 1.5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "win_rate_threshold must be 0.0-1.0" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_adjustment_magnitude_must_be_reasonable(self):
        """Test that adjustment_magnitude_pct must be 0-5."""
        yaml_content = """
adjustments:
  symbol_learning:
    adjustment_magnitude_pct: 8.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "adjustment_magnitude_pct must be 0-5" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_max_symbols_must_be_positive(self):
        """Test that max_symbols_tracked must be >= 1."""
        yaml_content = """
adjustments:
  symbol_learning:
    max_symbols_tracked: 0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "max_symbols_tracked must be >= 1" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestCombinationConfigValidation:
    """Test validation of combination/bounds configuration."""
    
    def test_tier1_bounds_must_be_ordered(self):
        """Test that tier1_max must be > tier1_min."""
        yaml_content = """
adjustments:
  combination:
    tier1_min_target_pct: 5.0
    tier1_max_target_pct: 3.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "tier1_max_target_pct must be > tier1_min_target_pct" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_tier2_bounds_must_be_ordered(self):
        """Test that tier2_max must be > tier2_min."""
        yaml_content = """
adjustments:
  combination:
    tier2_min_target_pct: 12.0
    tier2_max_target_pct: 8.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "tier2_max_target_pct must be > tier2_min_target_pct" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_tier2_min_should_be_greater_than_tier1_min(self):
        """Test logical ordering: tier2_min >= tier1_min."""
        yaml_content = """
adjustments:
  combination:
    tier1_min_target_pct: 5.0
    tier2_min_target_pct: 3.0
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "tier2_min_target_pct should be >= tier1_min_target_pct" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_rounding_decimal_places_must_be_valid(self):
        """Test that rounding must be 0-4 decimal places."""
        yaml_content = """
adjustments:
  combination:
    round_to_decimal_places: 5
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "round_to_decimal_places must be 0-4" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestVIXProviderConfigValidation:
    """Test validation of VIX provider configuration."""
    
    def test_provider_type_must_be_valid(self):
        """Test that provider_type must be alpaca, mock, or fallback."""
        yaml_content = """
vix_provider:
  provider_type: "invalid"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "provider_type must be 'alpaca', 'mock', or 'fallback'" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_mock_fixed_vix_must_be_valid(self):
        """Test that mock.fixed_vix must be 0-100."""
        yaml_content = """
vix_provider:
  mock:
    fixed_vix: 150
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "fixed_vix must be 0-100" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_fallback_primary_provider_must_be_valid(self):
        """Test that fallback.primary_provider must be alpaca or mock."""
        yaml_content = """
vix_provider:
  fallback:
    primary_provider: "yahoo"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "primary_provider must be 'alpaca' or 'mock'" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestRegimeDetectorConfigValidation:
    """Test validation of regime detector configuration."""
    
    def test_detector_type_must_be_valid(self):
        """Test that detector_type must be spy or mock."""
        yaml_content = """
regime_detector:
  detector_type: "custom"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "detector_type must be 'spy' or 'mock'" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_spy_windows_must_be_ordered(self):
        """Test that SPY short_window must be < long_window."""
        yaml_content = """
regime_detector:
  spy:
    short_window: 100
    long_window: 50
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "short_window must be < long_window" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()
    
    def test_mock_fixed_regime_must_be_valid(self):
        """Test that mock.fixed_regime must be BULL, BEAR, or SIDEWAYS."""
        yaml_content = """
regime_detector:
  mock:
    fixed_regime: "INVALID"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                ExitConfigManager.from_yaml(temp_path)
            assert "fixed_regime must be 'BULL', 'BEAR', or 'SIDEWAYS'" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()


class TestValidConfigurationPasses:
    """Test that valid configurations pass validation."""
    
    def test_production_config_passes_validation(self):
        """Test that production template passes validation."""
        yaml_content = """
adjustments:
  enabled: true
  volatility:
    vix_low_threshold: 15
    vix_normal_threshold: 20
    vix_high_threshold: 30
    tier1_adjustment_low: 0.5
    tier1_adjustment_high: -1.0
  time_decay:
    tier1_max_decay_pct: -1.5
  regime:
    short_window: 20
    long_window: 50
    tier1_adjustment_bull: -0.5
  symbol_learning:
    min_exits_for_adjustment: 5
  combination:
    tier1_min_target_pct: 2.0
    tier1_max_target_pct: 8.0
    tier2_min_target_pct: 5.0
    tier2_max_target_pct: 15.0

vix_provider:
  provider_type: "fallback"
  fallback:
    primary_provider: "alpaca"
    default_vix: 20.0

regime_detector:
  detector_type: "spy"
  spy:
    short_window: 20
    long_window: 50
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            # Should not raise
            config = ExitConfigManager.from_yaml(temp_path)
            assert config is not None
            assert config.is_adjustments_enabled() is True
        finally:
            Path(temp_path).unlink()
