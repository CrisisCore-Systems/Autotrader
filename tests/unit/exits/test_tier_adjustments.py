"""
Tests for Tier-1 and Tier-2 exit integration with adjustment calculator.

This module tests that tier executors correctly use AdjustmentCalculator
to dynamically adjust profit targets based on market conditions.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock, MagicMock

from src.bouncehunter.exits.tier1 import Tier1Exit
from src.bouncehunter.exits.tier2 import Tier2Exit
from src.bouncehunter.exits.adjustments import (
    MarketConditions,
    AdjustmentCalculator,
    MarketRegime,
    VolatilityLevel
)
from src.bouncehunter.data.price_provider import Quote

EASTERN = ZoneInfo("America/New_York")


# ============================================================================
# Tier-1 Adjustment Integration Tests
# ============================================================================

class TestTier1AdjustmentIntegration:
    """Test Tier-1 exit with adjustment calculator."""
    
    @pytest.fixture
    def base_config(self):
        """Base Tier-1 configuration."""
        return {
            'profit_threshold_pct': 5.0,
            'min_trading_days': 1,
            'max_trading_days': 1,
            'time_window_start': '15:50',
            'time_window_end': '15:55',
            'exit_percentage': 30.0,
            'min_shares_remaining': 5
        }
    
    @pytest.fixture
    def position(self):
        """Test position on Day 1."""
        return {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 100,
            'exit_tiers': {}
        }
    
    def test_tier1_without_adjustment_calculator(self, base_config, position):
        """Tier-1 should work without adjustment calculator (backward compatible)."""
        tier1 = Tier1Exit(base_config)
        
        # Quote at 5.2% profit
        quote = Quote('TEST', 10.52, 10.51, 10.53, datetime.now(EASTERN))
        
        # At 3:52 PM ET (within window)
        current_time = datetime(2025, 10, 20, 15, 52, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "5.20%" in reason
        assert "5.00%" in reason  # Base threshold used
    
    def test_tier1_with_bull_market_adjustment(self, base_config, position):
        """Bull market should increase Tier-1 target."""
        # Setup adjustment calculator
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BULL)
        
        calculator = AdjustmentCalculator(
            conditions,
            enable_volatility_adjustments=False,
            enable_time_adjustments=False,
            enable_regime_adjustments=True  # Only regime
        )
        
        tier1 = Tier1Exit(base_config, adjustment_calculator=calculator)
        
        # Quote at 5.2% profit (would pass base 5%, but not adjusted 6%)
        quote = Quote('TEST', 10.52, 10.51, 10.53, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 15, 52, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        
        # Should NOT execute (5.2% < 6.0% adjusted target)
        assert should_exec is False
        assert "5.20%" in reason
        assert "6.00%" in reason  # Adjusted target
        
        # Quote at 6.1% profit (passes adjusted threshold)
        quote = Quote('TEST', 10.61, 10.60, 10.62, datetime.now(EASTERN))
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "6.10%" in reason
        assert "6.00%" in reason
        assert "regime=+1.00%" in reason  # Shows adjustment detail
    
    def test_tier1_with_high_volatility_adjustment(self, base_config, position):
        """High volatility should decrease Tier-1 target."""
        conditions = MarketConditions()
        
        calculator = AdjustmentCalculator(
            conditions,
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        tier1 = Tier1Exit(base_config, adjustment_calculator=calculator)
        
        # Quote at 4.1% profit (would fail base 5%, but passes adjusted 4%)
        quote = Quote('TEST', 10.41, 10.40, 10.42, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 15, 52, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier1.should_execute(
            position, quote, current_time
        )
        
        # Provide VIX=25 (high volatility) via calculator
        # We need to mock the VIX fetch
        conditions._cached_vix = 25.0
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "4.10%" in reason
        assert "4.00%" in reason  # Adjusted target (5.0 - 1.0)
        assert "vol=-1.00%" in reason
    
    def test_tier1_adjustment_logged(self, base_config, position, caplog):
        """Adjustment details should be logged at DEBUG level."""
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BEAR)
        
        calculator = AdjustmentCalculator(conditions)
        tier1 = Tier1Exit(base_config, adjustment_calculator=calculator)
        
        quote = Quote('TEST', 10.50, 10.49, 10.51, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 15, 52, 0, tzinfo=EASTERN)
        
        with caplog.at_level('DEBUG'):
            should_exec, reason = tier1.should_execute(position, quote, current_time)
        
        # Check debug log contains adjustment info
        assert any("Tier-1 target adjusted" in record.message for record in caplog.records)


# ============================================================================
# Tier-2 Adjustment Integration Tests
# ============================================================================

class TestTier2AdjustmentIntegration:
    """Test Tier-2 exit with adjustment calculator."""
    
    @pytest.fixture
    def base_config(self):
        """Base Tier-2 configuration."""
        return {
            'profit_threshold_min': 8.0,
            'profit_threshold_max': 10.0,
            'min_trading_days': 2,
            'volume_lookback_days': 20,
            'volume_spike_threshold': 2.0,
            'cooldown_minutes': 30,
            'exit_percent': 40.0,
            'min_shares_remaining': 10
        }
    
    @pytest.fixture
    def position(self):
        """Test position on Day 2."""
        return {
            'ticker': 'TEST',
            'entry_date': '2025-10-18',  # 2 days ago
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 70,  # After Tier-1 exit
            'exit_tiers': {
                'tier1': {
                    'executed': True,
                    'timestamp': '2025-10-18 15:52:00'
                }
            }
        }
    
    @pytest.fixture
    def mock_price_provider(self):
        """Mock price provider with volume data."""
        provider = Mock()
        
        # Return bars with 2x volume spike
        bars = [Mock(volume=50000) for _ in range(20)]  # Avg = 50k
        bars[-1].volume = 100000  # Current = 100k (2x spike)
        
        provider.get_bars.return_value = bars
        
        return provider
    
    def test_tier2_without_adjustment_calculator(self, base_config, position, mock_price_provider):
        """Tier-2 should work without adjustment calculator (backward compatible)."""
        tier2 = Tier2Exit(base_config, price_provider=mock_price_provider)
        
        # Quote at 9% profit (in 8-10% range)
        quote = Quote('TEST', 10.90, 10.89, 10.91, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 10, 30, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "9.00%" in reason
        assert "8.00-10.00%" in reason  # Base range
    
    def test_tier2_with_bull_market_adjustment(self, base_config, position, mock_price_provider):
        """Bull market should increase Tier-2 range (10-12%)."""
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BULL)
        
        calculator = AdjustmentCalculator(
            conditions,
            enable_volatility_adjustments=False,
            enable_time_adjustments=False,
            enable_regime_adjustments=True
        )
        
        tier2 = Tier2Exit(
            base_config,
            price_provider=mock_price_provider,
            adjustment_calculator=calculator
        )
        
        # Quote at 9% profit (in base 8-10%, but BELOW adjusted 10-12%)
        quote = Quote('TEST', 10.90, 10.89, 10.91, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 10, 30, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        # Should NOT execute (9% < 10% adjusted min)
        assert should_exec is False
        assert "9.00%" in reason
        assert "10.00%" in reason  # Adjusted min
        
        # Quote at 11% profit (in adjusted 10-12% range)
        quote = Quote('TEST', 11.10, 11.09, 11.11, datetime.now(EASTERN))
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "11.00%" in reason  # (11.10 - 10.0) / 10.0 * 100 = 11.0%
        assert "10.00-12.00%" in reason  # Adjusted range
        assert "regime=+2.00%" in reason
    
    def test_tier2_with_bear_market_adjustment(self, base_config, position, mock_price_provider):
        """Bear market should decrease Tier-2 range (6-8%)."""
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BEAR)
        
        calculator = AdjustmentCalculator(
            conditions,
            enable_volatility_adjustments=False,
            enable_time_adjustments=False,
            enable_regime_adjustments=True
        )
        
        tier2 = Tier2Exit(
            base_config,
            price_provider=mock_price_provider,
            adjustment_calculator=calculator
        )
        
        # Quote at 7% profit (below base 8-10%, but IN adjusted 6-8%)
        quote = Quote('TEST', 10.70, 10.69, 10.71, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 10, 30, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "7.00%" in reason
        assert "6.00-8.00%" in reason  # Adjusted range
        assert "regime=-2.00%" in reason
    
    def test_tier2_with_extreme_volatility_adjustment(self, base_config, position, mock_price_provider):
        """Extreme volatility should tighten Tier-2 range."""
        conditions = MarketConditions()
        conditions._cached_vix = 35.0  # Extreme
        
        calculator = AdjustmentCalculator(
            conditions,
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        tier2 = Tier2Exit(
            base_config,
            price_provider=mock_price_provider,
            adjustment_calculator=calculator
        )
        
        # Quote at 6.5% profit (below base 8%, but IN adjusted 6-8%)
        quote = Quote('TEST', 10.65, 10.64, 10.66, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 10, 30, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "6.50%" in reason
        assert "6.00-8.00%" in reason  # Adjusted range (8-2, 10-2)
        assert "vol=-2.00%" in reason
    
    def test_tier2_combined_adjustments(self, base_config, position, mock_price_provider):
        """Test combined volatility + regime adjustments."""
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BULL)
        conditions._cached_vix = 12.0  # Low volatility
        
        calculator = AdjustmentCalculator(
            conditions,
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=True
        )
        
        tier2 = Tier2Exit(
            base_config,
            price_provider=mock_price_provider,
            adjustment_calculator=calculator
        )
        
        # Combined: bull +2%, low vol +1% = +3% total
        # Base 8-10% → Adjusted 11-13%
        
        # Quote at 12% profit (in adjusted range)
        quote = Quote('TEST', 11.20, 11.19, 11.21, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 10, 30, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "12.00%" in reason
        assert "11.00-13.00%" in reason  # Adjusted range
        assert "vol=+1.00%" in reason
        assert "regime=+2.00%" in reason
    
    def test_tier2_adjustment_logged(self, base_config, position, mock_price_provider, caplog):
        """Adjustment details should be logged at DEBUG level."""
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BULL)
        
        calculator = AdjustmentCalculator(conditions)
        tier2 = Tier2Exit(
            base_config,
            price_provider=mock_price_provider,
            adjustment_calculator=calculator
        )
        
        quote = Quote('TEST', 11.00, 10.99, 11.01, datetime.now(EASTERN))
        current_time = datetime(2025, 10, 20, 10, 30, 0, tzinfo=EASTERN)
        
        with caplog.at_level('DEBUG'):
            should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        # Check debug log contains adjustment info
        assert any("Tier-2 range adjusted" in record.message for record in caplog.records)


# ============================================================================
# Integration Tests
# ============================================================================

class TestTierAdjustmentIntegration:
    """Test full integration of tiers with adjustments."""
    
    def test_tier1_and_tier2_use_same_conditions(self):
        """Both tiers should share the same MarketConditions instance."""
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BULL)
        
        calculator = AdjustmentCalculator(conditions)
        
        config1 = {'profit_threshold_pct': 5.0, 'min_trading_days': 1, 'max_trading_days': 1,
                   'time_window_start': '15:50', 'time_window_end': '15:55',
                   'exit_percentage': 30.0, 'min_shares_remaining': 5}
        config2 = {'profit_threshold_min': 8.0, 'profit_threshold_max': 10.0,
                   'min_trading_days': 2, 'volume_lookback_days': 20,
                   'volume_spike_threshold': 2.0, 'cooldown_minutes': 30,
                   'exit_percent': 40.0, 'min_shares_remaining': 10}
        
        tier1 = Tier1Exit(config1, adjustment_calculator=calculator)
        tier2 = Tier2Exit(config2, adjustment_calculator=calculator)
        
        # Both should see the same regime
        assert tier1.adjustment_calculator.market_conditions.get_market_regime() == MarketRegime.BULL
        assert tier2.adjustment_calculator.market_conditions.get_market_regime() == MarketRegime.BULL
        
        # Updating regime affects both
        conditions.set_market_regime(MarketRegime.BEAR)
        
        assert tier1.adjustment_calculator.market_conditions.get_market_regime() == MarketRegime.BEAR
        assert tier2.adjustment_calculator.market_conditions.get_market_regime() == MarketRegime.BEAR
    
    def test_adjustments_can_be_disabled_per_tier(self):
        """Each tier can have its own adjustment calculator configuration."""
        conditions = MarketConditions()
        conditions.set_market_regime(MarketRegime.BULL)
        
        # Tier-1: All adjustments enabled
        calc1 = AdjustmentCalculator(conditions)
        
        # Tier-2: Only volatility adjustments
        calc2 = AdjustmentCalculator(
            conditions,
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        config1 = {'profit_threshold_pct': 5.0, 'min_trading_days': 1, 'max_trading_days': 1,
                   'time_window_start': '15:50', 'time_window_end': '15:55',
                   'exit_percentage': 30.0, 'min_shares_remaining': 5}
        config2 = {'profit_threshold_min': 8.0, 'profit_threshold_max': 10.0,
                   'min_trading_days': 2, 'volume_lookback_days': 20,
                   'volume_spike_threshold': 2.0, 'cooldown_minutes': 30,
                   'exit_percent': 40.0, 'min_shares_remaining': 10}
        
        tier1 = Tier1Exit(config1, adjustment_calculator=calc1)
        tier2 = Tier2Exit(config2, adjustment_calculator=calc2)
        
        # Test Tier-1 uses regime adjustment
        target1, details1 = tier1.adjustment_calculator.adjust_tier1_target(5.0)
        assert details1['regime_adjustment'] == 1.0  # Bull market
        
        # Test Tier-2 does NOT use regime adjustment
        (min2, max2), details2 = tier2.adjustment_calculator.adjust_tier2_target(8.0, 10.0)
        assert details2['regime_adjustment'] == 0.0  # Disabled
