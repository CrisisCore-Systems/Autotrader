"""
Unit tests for intelligent adjustment logic.

Tests market conditions analysis, dynamic adjustments, and symbol learning.
"""

import pytest
from datetime import datetime, time
from zoneinfo import ZoneInfo

from src.bouncehunter.exits.adjustments import (
    MarketConditions,
    AdjustmentCalculator,
    SymbolLearner,
    MarketRegime,
    VolatilityLevel,
    TimeOfDayPeriod
)


EASTERN = ZoneInfo("America/New_York")


class TestMarketConditions:
    """Test market conditions analysis."""
    
    def test_volatility_classification_low(self):
        """Test low volatility classification (VIX < 15)."""
        conditions = MarketConditions()
        assert conditions.get_volatility_level(12.0) == VolatilityLevel.LOW
        assert conditions.get_volatility_level(14.9) == VolatilityLevel.LOW
    
    def test_volatility_classification_normal(self):
        """Test normal volatility classification (VIX 15-20)."""
        conditions = MarketConditions()
        assert conditions.get_volatility_level(15.0) == VolatilityLevel.NORMAL
        assert conditions.get_volatility_level(17.5) == VolatilityLevel.NORMAL
        assert conditions.get_volatility_level(19.9) == VolatilityLevel.NORMAL
    
    def test_volatility_classification_high(self):
        """Test high volatility classification (VIX 20-30)."""
        conditions = MarketConditions()
        assert conditions.get_volatility_level(20.0) == VolatilityLevel.HIGH
        assert conditions.get_volatility_level(25.0) == VolatilityLevel.HIGH
        assert conditions.get_volatility_level(29.9) == VolatilityLevel.HIGH
    
    def test_volatility_classification_extreme(self):
        """Test extreme volatility classification (VIX > 30)."""
        conditions = MarketConditions()
        assert conditions.get_volatility_level(30.0) == VolatilityLevel.EXTREME
        assert conditions.get_volatility_level(45.0) == VolatilityLevel.EXTREME
    
    def test_time_period_open(self):
        """Test market open period (09:30-10:00)."""
        conditions = MarketConditions()
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 9, 30, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.OPEN
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 9, 45, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.OPEN
    
    def test_time_period_morning(self):
        """Test morning period (10:00-11:30)."""
        conditions = MarketConditions()
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 10, 0, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.MORNING
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 11, 0, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.MORNING
    
    def test_time_period_midday(self):
        """Test midday period (11:30-14:00)."""
        conditions = MarketConditions()
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 11, 30, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.MIDDAY
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 13, 0, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.MIDDAY
    
    def test_time_period_afternoon(self):
        """Test afternoon period (14:00-15:30)."""
        conditions = MarketConditions()
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 14, 0, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.AFTERNOON
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 15, 0, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.AFTERNOON
    
    def test_time_period_close(self):
        """Test market close period (15:30-16:00)."""
        conditions = MarketConditions()
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 15, 30, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.CLOSE
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 15, 45, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.CLOSE
    
    def test_time_period_outside_market_hours(self):
        """Test time outside market hours defaults to MIDDAY."""
        conditions = MarketConditions()
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 8, 0, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.MIDDAY
        assert conditions.get_time_period(
            datetime(2025, 10, 20, 18, 0, 0, tzinfo=EASTERN)
        ) == TimeOfDayPeriod.MIDDAY
    
    def test_market_regime_setting(self):
        """Test market regime can be set and retrieved."""
        conditions = MarketConditions()
        
        conditions.set_market_regime(MarketRegime.BULL)
        assert conditions.get_market_regime() == MarketRegime.BULL
        
        conditions.set_market_regime(MarketRegime.BEAR)
        assert conditions.get_market_regime() == MarketRegime.BEAR


class TestAdjustmentCalculator:
    """Test adjustment calculation logic."""
    
    @pytest.fixture
    def market_conditions(self):
        """Create market conditions instance."""
        return MarketConditions()
    
    @pytest.fixture
    def calculator(self, market_conditions):
        """Create adjustment calculator."""
        return AdjustmentCalculator(market_conditions)
    
    def test_tier1_baseline_no_adjustments(self, calculator):
        """Test Tier-1 baseline with all adjustments disabled."""
        calc_disabled = AdjustmentCalculator(
            MarketConditions(),
            enable_volatility_adjustments=False,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        adjusted, details = calc_disabled.adjust_tier1_target(5.0)
        
        assert adjusted == 5.0
        assert details['volatility_adjustment'] == 0.0
        assert details['time_adjustment'] == 0.0
        assert details['regime_adjustment'] == 0.0
    
    def test_tier1_low_volatility_adjustment(self, calculator):
        """Test Tier-1 increases target in low volatility."""
        adjusted, details = calculator.adjust_tier1_target(
            base_target=5.0,
            current_vix=12.0
        )
        
        # Low vol adds +1.0%
        assert details['volatility_adjustment'] == 1.0
        assert adjusted >= 6.0  # Base 5.0 + vol 1.0 = 6.0
    
    def test_tier1_high_volatility_adjustment(self, calculator):
        """Test Tier-1 decreases target in high volatility."""
        # Disable other adjustments to isolate volatility
        calc_vol_only = AdjustmentCalculator(
            MarketConditions(),
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        adjusted, details = calc_vol_only.adjust_tier1_target(
            base_target=5.0,
            current_vix=25.0
        )
        
        # High vol subtracts -1.0%
        assert details['volatility_adjustment'] == -1.0
        assert adjusted == 4.0  # Base 5.0 + vol -1.0 = 4.0
    
    def test_tier1_extreme_volatility_adjustment(self, calculator):
        """Test Tier-1 significantly decreases target in extreme volatility."""
        # Disable other adjustments to isolate volatility
        calc_vol_only = AdjustmentCalculator(
            MarketConditions(),
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        adjusted, details = calc_vol_only.adjust_tier1_target(
            base_target=5.0,
            current_vix=35.0
        )
        
        # Extreme vol subtracts -2.0%
        assert details['volatility_adjustment'] == -2.0
        assert adjusted == 3.0  # Base 5.0 + vol -2.0 = 3.0
    
    def test_tier1_open_period_adjustment(self, calculator):
        """Test Tier-1 tightens target during market open."""
        adjusted, details = calculator.adjust_tier1_target(
            base_target=5.0,
            current_time=datetime(2025, 10, 20, 9, 45, 0, tzinfo=EASTERN)
        )
        
        # Open period subtracts -0.5%
        assert details['time_adjustment'] == -0.5
    
    def test_tier1_midday_adjustment(self, calculator):
        """Test Tier-1 relaxes target during midday."""
        adjusted, details = calculator.adjust_tier1_target(
            base_target=5.0,
            current_time=datetime(2025, 10, 20, 12, 0, 0, tzinfo=EASTERN)
        )
        
        # Midday adds +0.5%
        assert details['time_adjustment'] == 0.5
    
    def test_tier1_bull_market_adjustment(self, market_conditions, calculator):
        """Test Tier-1 increases target in bull market."""
        market_conditions.set_market_regime(MarketRegime.BULL)
        
        adjusted, details = calculator.adjust_tier1_target(base_target=5.0)
        
        # Bull market adds +1.0%
        assert details['regime_adjustment'] == 1.0
    
    def test_tier1_bear_market_adjustment(self, market_conditions, calculator):
        """Test Tier-1 decreases target in bear market."""
        market_conditions.set_market_regime(MarketRegime.BEAR)
        
        adjusted, details = calculator.adjust_tier1_target(base_target=5.0)
        
        # Bear market subtracts -1.5%
        assert details['regime_adjustment'] == -1.5
    
    def test_tier1_combined_adjustments(self, market_conditions, calculator):
        """Test Tier-1 with multiple adjustments combined."""
        market_conditions.set_market_regime(MarketRegime.BULL)
        
        adjusted, details = calculator.adjust_tier1_target(
            base_target=5.0,
            current_time=datetime(2025, 10, 20, 12, 0, 0, tzinfo=EASTERN),  # Midday +0.5
            current_vix=12.0  # Low vol +1.0
        )
        
        # Base 5.0 + vol +1.0 + time +0.5 + regime +1.0 = 7.5
        assert adjusted == 7.5
        assert details['volatility_adjustment'] == 1.0
        assert details['time_adjustment'] == 0.5
        assert details['regime_adjustment'] == 1.0
    
    def test_tier1_floor_cap_enforcement(self, calculator):
        """Test Tier-1 enforces min 2% and max 10% bounds."""
        # Test floor
        adjusted_low, _ = calculator.adjust_tier1_target(
            base_target=5.0,
            current_vix=40.0  # Extreme vol -2%
        )
        # Would be 5 - 2 = 3, but floor is 2
        assert adjusted_low >= 2.0
        
        # Test cap
        adjusted_high, _ = calculator.adjust_tier1_target(
            base_target=9.0,
            current_vix=10.0  # Low vol +1%
        )
        # Would be 9 + 1 = 10
        assert adjusted_high <= 10.0
    
    def test_tier2_low_volatility_adjustment(self, calculator):
        """Test Tier-2 increases range in low volatility."""
        # Disable other adjustments to isolate volatility
        calc_vol_only = AdjustmentCalculator(
            MarketConditions(),
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        (min_adj, max_adj), details = calc_vol_only.adjust_tier2_target(
            base_min=8.0,
            base_max=10.0,
            current_vix=12.0
        )
        
        # Low vol adds +1.0% to both
        assert details['volatility_adjustment'] == 1.0
        assert min_adj == 9.0
        assert max_adj == 11.0
    
    def test_tier2_extreme_volatility_adjustment(self, calculator):
        """Test Tier-2 tightens range in extreme volatility."""
        # Disable other adjustments to isolate volatility
        calc_vol_only = AdjustmentCalculator(
            MarketConditions(),
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        (min_adj, max_adj), details = calc_vol_only.adjust_tier2_target(
            base_min=8.0,
            base_max=10.0,
            current_vix=35.0
        )
        
        # Extreme vol subtracts -2.0% from both
        assert details['volatility_adjustment'] == -2.0
        assert min_adj == 6.0
        assert max_adj == 8.0
    
    def test_tier2_bull_market_adjustment(self, market_conditions, calculator):
        """Test Tier-2 increases range in bull market."""
        market_conditions.set_market_regime(MarketRegime.BULL)
        
        # Disable other adjustments to isolate regime
        calc_regime_only = AdjustmentCalculator(
            market_conditions,
            enable_volatility_adjustments=False,
            enable_time_adjustments=False,
            enable_regime_adjustments=True
        )
        
        (min_adj, max_adj), details = calc_regime_only.adjust_tier2_target(
            base_min=8.0,
            base_max=10.0
        )
        
        # Bull market adds +2.0%
        assert details['regime_adjustment'] == 2.0
        assert min_adj == 10.0
        assert max_adj == 12.0
    
    def test_tier2_bear_market_adjustment(self, market_conditions, calculator):
        """Test Tier-2 decreases range in bear market."""
        market_conditions.set_market_regime(MarketRegime.BEAR)
        
        # Disable other adjustments to isolate regime
        calc_regime_only = AdjustmentCalculator(
            market_conditions,
            enable_volatility_adjustments=False,
            enable_time_adjustments=False,
            enable_regime_adjustments=True
        )
        
        (min_adj, max_adj), details = calc_regime_only.adjust_tier2_target(
            base_min=8.0,
            base_max=10.0
        )
        
        # Bear market subtracts -2.0%
        assert details['regime_adjustment'] == -2.0
        assert min_adj == 6.0
        assert max_adj == 8.0
    
    def test_tier2_range_validation(self, calculator):
        """Test Tier-2 maintains valid range (min < max)."""
        # Disable other adjustments to isolate volatility
        calc_vol_only = AdjustmentCalculator(
            MarketConditions(),
            enable_volatility_adjustments=True,
            enable_time_adjustments=False,
            enable_regime_adjustments=False
        )
        
        (min_adj, max_adj), details = calc_vol_only.adjust_tier2_target(
            base_min=10.0,
            base_max=11.0,
            current_vix=40.0  # Extreme vol -2%
        )
        
        # Extreme vol reduces range: 10-2=8, 11-2=9
        assert max_adj > min_adj  # Min < max enforced
        assert min_adj == 8.0
        assert max_adj == 9.0  # Note: spread enforcement happens after, final is 8-10
    
    def test_position_size_low_volatility(self, calculator):
        """Test position size increases in low volatility."""
        adjusted, details = calculator.adjust_position_size(
            base_pct=50.0,
            current_vix=12.0
        )
        
        # Low vol adds +5%
        assert details['volatility_adjustment'] == 5.0
        assert adjusted == 55.0
    
    def test_position_size_extreme_volatility(self, calculator):
        """Test position size decreases in extreme volatility."""
        adjusted, details = calculator.adjust_position_size(
            base_pct=50.0,
            current_vix=35.0
        )
        
        # Extreme vol subtracts -10%
        assert details['volatility_adjustment'] == -10.0
        assert adjusted == 40.0
    
    def test_position_size_bounds(self, calculator):
        """Test position size enforces 20-60% bounds."""
        # Test floor
        adjusted_low, _ = calculator.adjust_position_size(
            base_pct=25.0,
            current_vix=40.0  # Extreme vol -10%
        )
        assert adjusted_low >= 20.0
        
        # Test cap
        adjusted_high, _ = calculator.adjust_position_size(
            base_pct=58.0,
            current_vix=10.0  # Low vol +5%
        )
        assert adjusted_high <= 60.0


class TestSymbolLearner:
    """Test symbol-specific learning."""
    
    @pytest.fixture
    def learner(self):
        """Create symbol learner instance."""
        return SymbolLearner()
    
    def test_new_symbol_no_data(self, learner):
        """Test new symbol returns no adjustment."""
        adjustment = learner.get_symbol_adjustment('INTR')
        
        assert adjustment['has_data'] is False
        assert adjustment['tier1_adjustment'] == 0.0
        assert adjustment['tier2_adjustment'] == 0.0
    
    def test_insufficient_sample_size(self, learner):
        """Test insufficient sample (<5) returns no adjustment."""
        # Record 3 exits
        for i in range(3):
            learner.record_exit('INTR', 10.0, 10.50, 1, 'tier1', 5.0)
        
        adjustment = learner.get_symbol_adjustment('INTR')
        
        assert adjustment['has_data'] is True
        assert adjustment['insufficient_sample'] is True
        assert adjustment['tier1_adjustment'] == 0.0
    
    def test_runner_detection(self, learner):
        """Test runner detection (high tier2 exits)."""
        # Record 10 exits, 7 tier2 (70% runner score)
        for i in range(7):
            learner.record_exit('INTR', 10.0, 10.90, 2, 'tier2', 9.0)
        for i in range(3):
            learner.record_exit('INTR', 10.0, 10.50, 1, 'tier1', 5.0)
        
        adjustment = learner.get_symbol_adjustment('INTR')
        
        assert adjustment['runner_score'] == 0.7
        assert adjustment['best_exit_tier'] == 'tier2'
        assert adjustment['tier1_adjustment'] == 1.0  # Increase target
        assert adjustment['tier2_adjustment'] == 1.0
        assert 'Runner detected' in adjustment['recommendation']
    
    def test_fader_detection(self, learner):
        """Test fader detection (high tier1 exits)."""
        # Record 10 exits, 8 tier1 (20% runner score)
        for i in range(8):
            learner.record_exit('INTR', 10.0, 10.50, 1, 'tier1', 5.0)
        for i in range(2):
            learner.record_exit('INTR', 10.0, 10.90, 2, 'tier2', 9.0)
        
        adjustment = learner.get_symbol_adjustment('INTR')
        
        assert adjustment['runner_score'] == 0.2
        assert adjustment['best_exit_tier'] == 'tier1'
        assert adjustment['tier1_adjustment'] == -0.5  # Decrease target
        assert adjustment['tier2_adjustment'] == -1.0
        assert 'Fader detected' in adjustment['recommendation']
    
    def test_mixed_pattern(self, learner):
        """Test mixed pattern (balanced exits)."""
        # Record 10 exits, 5 tier1, 5 tier2 (50% runner score)
        for i in range(5):
            learner.record_exit('INTR', 10.0, 10.50, 1, 'tier1', 5.0)
        for i in range(5):
            learner.record_exit('INTR', 10.0, 10.90, 2, 'tier2', 9.0)
        
        adjustment = learner.get_symbol_adjustment('INTR')
        
        assert adjustment['runner_score'] == 0.5
        assert adjustment['best_exit_tier'] == 'mixed'
        assert adjustment['tier1_adjustment'] == 0.0
        assert adjustment['tier2_adjustment'] == 0.0
        assert 'Mixed pattern' in adjustment['recommendation']
    
    def test_stats_tracking(self, learner):
        """Test statistics are tracked correctly."""
        learner.record_exit('INTR', 10.0, 10.50, 1, 'tier1', 5.0)
        learner.record_exit('INTR', 10.0, 10.90, 2, 'tier2', 9.0)
        
        stats = learner.get_stats('INTR')
        
        assert stats['total_exits'] == 2
        assert stats['tier1_exits'] == 1
        assert stats['tier2_exits'] == 1
        assert stats['avg_hold_days'] == 1.5  # (1 + 2) / 2
        assert stats['avg_profit_pct'] == 7.0  # (5 + 9) / 2
    
    def test_global_stats(self, learner):
        """Test global statistics across all symbols."""
        learner.record_exit('INTR', 10.0, 10.50, 1, 'tier1', 5.0)
        learner.record_exit('TEST', 20.0, 21.00, 1, 'tier1', 5.0)
        
        stats = learner.get_stats()
        
        assert stats['total_symbols'] == 2
        assert 'INTR' in stats['symbols']
        assert 'TEST' in stats['symbols']
