"""
Unit tests for Tier-2 exit logic (momentum spike detection).

Test Coverage:
- Day counting (Day 1 blocked, Day 2+ allowed)
- Profit range validation (8-10% window)
- Volume spike detection (2x average threshold)
- Cooldown enforcement (30 min between attempts)
- Execution logic (dry-run, real broker, errors)
- Edge cases (already executed, insufficient shares, no price provider)

Author: PennyHunter Pro
Date: 2025-10-20
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List

from src.bouncehunter.exits.tier2 import Tier2Exit, EASTERN
from src.bouncehunter.data.price_provider import Quote, Bar

# Test fixtures
EASTERN = ZoneInfo("America/New_York")


# Default Tier-2 configuration
DEFAULT_TIER2_CONFIG = {
    'min_trading_days': 2,
    'profit_threshold_min': 8.0,
    'profit_threshold_max': 10.0,
    'exit_percent': 40.0,
    'min_shares_remaining': 10,
    'volume_lookback_bars': 30,
    'volume_spike_multiplier': 2.0,
    'cooldown_minutes': 30,
}


class MockBroker:
    """Mock broker for testing order execution."""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.orders = []
    
    def submit_order(self, ticker, qty, side, order_type):
        """Simulate order submission."""
        if self.should_fail:
            raise Exception("Mock broker failure")
        
        order = {
            'id': f'ORDER_{len(self.orders) + 1}',
            'ticker': ticker,
            'qty': qty,
            'side': side,
            'order_type': order_type,
            'filled_qty': qty,
            'filled_avg_price': 10.90,  # Mock fill price
        }
        
        self.orders.append(order)
        return order


class MockPriceProvider:
    """Mock price provider for testing bar data."""
    
    def __init__(self, bars: List[Bar] = None):
        self.bars = bars or []
    
    def get_bars(self, ticker, timeframe, limit, end_time):
        """Return mock bar data."""
        return self.bars


@pytest.fixture
def config():
    """Create test configuration."""
    return DEFAULT_TIER2_CONFIG.copy()


@pytest.fixture
def position():
    """Create test position (Day 2, after Tier-1 already executed)."""
    return {
        'ticker': 'INTR',
        'entry_date': '2025-10-19',  # Day before current_time
        'entry_time': '09:35:00',
        'entry_price': 10.0,
        'shares': 70,  # After Tier-1 sold 30 shares
        'exit_tiers': {
            'tier1': {
                'timestamp': '2025-10-19 15:52:00',
                'shares_sold': 30,
                'exit_price': 10.50,
            }
        }
    }


@pytest.fixture
def current_time():
    """Current time (Oct 20, 2025 @ 10:00 ET = Day 2)."""
    return datetime(2025, 10, 20, 10, 0, 0, tzinfo=EASTERN)


@pytest.fixture
def quote_in_range():
    """Quote with 9% profit (in 8-10% range)."""
    return Quote(
        ticker='INTR',
        price=10.90,  # 9% profit from 10.0 entry
        bid=10.89,
        ask=10.91,
        timestamp=datetime(2025, 10, 20, 10, 0, 0, tzinfo=EASTERN),
    )


@pytest.fixture
def bars_with_spike():
    """Bar data showing volume spike (current 2x average)."""
    # 29 bars with normal volume ~1000
    normal_bars = [
        Bar(
            ticker='INTR',
            timestamp=datetime(2025, 10, 20, 9, 30 + i, 0, tzinfo=EASTERN),
            open=10.80,
            high=10.85,
            low=10.75,
            close=10.82,
            volume=1000,
        )
        for i in range(29)
    ]
    
    # Current bar with 2x volume spike
    spike_bar = Bar(
        ticker='INTR',
        timestamp=datetime(2025, 10, 20, 9, 59, 0, tzinfo=EASTERN),
        open=10.85,
        high=10.92,
        low=10.84,
        close=10.90,
        volume=2000,  # 2x average
    )
    
    return normal_bars + [spike_bar]


@pytest.fixture
def bars_no_spike():
    """Bar data with no volume spike (all normal volume)."""
    return [
        Bar(
            ticker='INTR',
            timestamp=datetime(2025, 10, 20, 9, 30 + i, 0, tzinfo=EASTERN),
            open=10.80,
            high=10.85,
            low=10.75,
            close=10.82,
            volume=1000,
        )
        for i in range(30)
    ]


# ============================================================================
# Day Counting Tests
# ============================================================================

class TestTier2DayCounting:
    """Test trading day counting logic."""
    
    def test_entry_day_is_day_1(self, config, position, current_time):
        """Entry day should be Day 1."""
        tier2 = Tier2Exit(config)
        
        # Same day as entry (Oct 19)
        entry_day_time = datetime(2025, 10, 19, 10, 0, 0, tzinfo=EASTERN)
        
        day = tier2.count_trading_days(position, entry_day_time)
        
        assert day == 1
    
    def test_next_day_is_day_2(self, config, position, current_time):
        """Next day after entry should be Day 2."""
        tier2 = Tier2Exit(config)
        
        # Oct 20 (day after Oct 19 entry)
        day = tier2.count_trading_days(position, current_time)
        
        assert day == 2
    
    def test_three_days_later(self, config, position):
        """Three days after entry should be Day 4."""
        tier2 = Tier2Exit(config)
        
        # Oct 22 (3 days after Oct 19 entry)
        day_4_time = datetime(2025, 10, 22, 10, 0, 0, tzinfo=EASTERN)
        
        day = tier2.count_trading_days(position, day_4_time)
        
        assert day == 4
    
    def test_invalid_date_defaults_to_day_1(self, config):
        """Invalid entry date should default to Day 1."""
        tier2 = Tier2Exit(config)
        
        bad_position = {
            'entry_date': 'INVALID',
            'entry_time': 'BAD_TIME',
        }
        
        current = datetime(2025, 10, 20, 10, 0, 0, tzinfo=EASTERN)
        day = tier2.count_trading_days(bad_position, current)
        
        assert day == 1


# ============================================================================
# Profit Range Tests
# ============================================================================

class TestTier2ProfitRange:
    """Test profit range validation (8-10%)."""
    
    def test_profit_in_range_allowed(self, config, position, current_time, bars_with_spike):
        """Profit in 8-10% range should allow execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        quote = Quote('INTR', 10.90, 10.89, 10.91, current_time)  # 9% profit
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "profit 9.00%" in reason
    
    def test_profit_below_range_blocked(self, config, position, current_time, bars_with_spike):
        """Profit below 8% should block execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        quote = Quote('INTR', 10.70, 10.69, 10.71, current_time)  # 7% profit
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is False
        assert "Profit 7.00% < 8.0%" in reason
        assert tier2.get_stats()['profit_range_misses'] == 1
    
    def test_profit_above_range_blocked(self, config, position, current_time, bars_with_spike):
        """Profit above 10% should block execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        quote = Quote('INTR', 11.20, 11.19, 11.21, current_time)  # 12% profit
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is False
        assert "Profit 12.00% > 10.0%" in reason
        assert tier2.get_stats()['profit_range_misses'] == 1
    
    def test_profit_at_min_threshold(self, config, position, current_time, bars_with_spike):
        """Profit exactly at 8% should allow execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        quote = Quote('INTR', 10.80, 10.79, 10.81, current_time)  # 8% profit
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "profit 8.00%" in reason
    
    def test_profit_at_max_threshold(self, config, position, current_time, bars_with_spike):
        """Profit exactly at 10% should allow execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        quote = Quote('INTR', 11.00, 10.99, 11.01, current_time)  # 10% profit
        
        should_exec, reason = tier2.should_execute(position, quote, current_time)
        
        assert should_exec is True
        assert "profit 10.00%" in reason


# ============================================================================
# Volume Spike Tests
# ============================================================================

class TestTier2VolumeSpike:
    """Test volume spike detection logic."""
    
    def test_volume_spike_detected(self, config, position, current_time, quote_in_range, bars_with_spike):
        """Volume spike (2x average) should be detected."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is True
        assert "Volume spike detected" in reason
        assert tier2.get_stats()['volume_spikes_detected'] == 1
    
    def test_no_spike_blocked(self, config, position, current_time, quote_in_range, bars_no_spike):
        """No volume spike should block execution."""
        price_provider = MockPriceProvider(bars_no_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "No spike" in reason
    
    def test_insufficient_bars_blocked(self, config, position, current_time, quote_in_range):
        """Insufficient bar data should block execution."""
        # Only 1 bar (need at least 2)
        single_bar = [
            Bar('INTR', datetime(2025, 10, 20, 9, 30, 0, tzinfo=EASTERN),
                10.80, 10.85, 10.75, 10.82, 1000)
        ]
        
        price_provider = MockPriceProvider(single_bar)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "Insufficient bar data" in reason
    
    def test_no_price_provider_blocked(self, config, position, current_time, quote_in_range):
        """No price provider should block execution."""
        tier2 = Tier2Exit(config, price_provider=None)
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "No price provider" in reason
    
    def test_price_provider_error_blocked(self, config, position, current_time, quote_in_range):
        """Price provider error should block execution."""
        class FailingPriceProvider:
            def get_bars(self, ticker, timeframe, limit, end_time):
                raise Exception("API failure")
        
        tier2 = Tier2Exit(config, price_provider=FailingPriceProvider())
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "Bar fetch error" in reason


# ============================================================================
# Cooldown Tests
# ============================================================================

class TestTier2Cooldown:
    """Test cooldown enforcement logic."""
    
    def test_no_previous_attempt_allowed(self, config, position, current_time, quote_in_range, bars_with_spike):
        """No previous attempt should allow execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Remove any tier2_last_attempt
        position['exit_tiers'].pop('tier2_last_attempt', None)
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is True
        assert "cooldown OK" in reason
    
    def test_cooldown_active_blocked(self, config, position, current_time, quote_in_range, bars_with_spike):
        """Within cooldown window should block execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Set last attempt 15 min ago (< 30 min cooldown)
        last_attempt = current_time - timedelta(minutes=15)
        position['exit_tiers']['tier2_last_attempt'] = last_attempt.isoformat()
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "Cooldown active" in reason
        assert "15.0 min remaining" in reason
        assert tier2.get_stats()['cooldown_blocks'] == 1
    
    def test_cooldown_elapsed_allowed(self, config, position, current_time, quote_in_range, bars_with_spike):
        """After cooldown elapsed should allow execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Set last attempt 45 min ago (> 30 min cooldown)
        last_attempt = current_time - timedelta(minutes=45)
        position['exit_tiers']['tier2_last_attempt'] = last_attempt.isoformat()
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is True
        # Just check it succeeded - final reason includes all criteria
        assert "Day 2" in reason
    
    def test_invalid_last_attempt_allowed(self, config, position, current_time, quote_in_range, bars_with_spike):
        """Invalid last_attempt timestamp should default to allowing execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Set invalid timestamp
        position['exit_tiers']['tier2_last_attempt'] = 'INVALID_TIMESTAMP'
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is True


# ============================================================================
# Day Validation Tests
# ============================================================================

class TestTier2DayValidation:
    """Test Day 2+ enforcement."""
    
    def test_day_1_blocked(self, config, current_time, quote_in_range, bars_with_spike):
        """Day 1 positions should be blocked (Tier-1 only)."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Day 1 position (entry same as current day)
        day1_position = {
            'ticker': 'INTR',
            'entry_date': '2025-10-20',  # Same as current_time
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 100,
            'exit_tiers': {}
        }
        
        should_exec, reason = tier2.should_execute(day1_position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "Day 1 < 2" in reason
    
    def test_day_2_allowed(self, config, position, current_time, quote_in_range, bars_with_spike):
        """Day 2 positions should be allowed."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is True
        assert "Day 2" in reason
    
    def test_day_3_allowed(self, config, current_time, quote_in_range, bars_with_spike):
        """Day 3+ positions should be allowed."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Day 3 position (entry 2 days before current)
        day3_position = {
            'ticker': 'INTR',
            'entry_date': '2025-10-18',  # 2 days before Oct 20
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 70,
            'exit_tiers': {}
        }
        
        day3_time = datetime(2025, 10, 20, 10, 0, 0, tzinfo=EASTERN)
        
        should_exec, reason = tier2.should_execute(day3_position, quote_in_range, day3_time)
        
        assert should_exec is True
        assert "Day 3" in reason


# ============================================================================
# Execution Logic Tests
# ============================================================================

class TestTier2ExecutionLogic:
    """Test order execution logic."""
    
    def test_dry_run_execution(self, config, position, quote_in_range):
        """Dry-run mode should simulate execution."""
        tier2 = Tier2Exit(config)
        
        result = tier2.execute_exit(position, quote_in_range, dry_run=True)
        
        assert result['status'] == 'success'
        assert result['shares_to_sell'] == 28  # 40% of 70
        assert result['shares_sold'] == 28
        assert result['exit_price'] == 10.90
        assert result['order_id'] == 'DRY_RUN_TIER2'
        assert tier2.get_stats()['tier2_exits'] == 1
    
    def test_real_execution_success(self, config, position, quote_in_range):
        """Real execution should submit order via broker."""
        broker = MockBroker()
        tier2 = Tier2Exit(config, broker=broker)
        
        result = tier2.execute_exit(position, quote_in_range, dry_run=False)
        
        assert result['status'] == 'success'
        assert result['shares_to_sell'] == 28
        assert result['shares_sold'] == 28
        assert result['order_id'] == 'ORDER_1'
        assert len(broker.orders) == 1
        assert broker.orders[0]['ticker'] == 'INTR'
        assert broker.orders[0]['qty'] == 28
        assert broker.orders[0]['side'] == 'sell'
        assert tier2.get_stats()['tier2_exits'] == 1
    
    def test_execution_without_broker_errors(self, config, position, quote_in_range):
        """Execution without broker should return error."""
        tier2 = Tier2Exit(config, broker=None)
        
        result = tier2.execute_exit(position, quote_in_range, dry_run=False)
        
        assert result['status'] == 'error'
        assert 'No broker configured' in result['error']
    
    def test_broker_error_handled(self, config, position, quote_in_range):
        """Broker errors should be handled gracefully."""
        failing_broker = MockBroker(should_fail=True)
        tier2 = Tier2Exit(config, broker=failing_broker)
        
        result = tier2.execute_exit(position, quote_in_range, dry_run=False)
        
        assert result['status'] == 'error'
        assert 'Mock broker failure' in result['error']
    
    def test_calculates_correct_share_quantity(self, config, quote_in_range):
        """Should calculate 40% of position for exit."""
        tier2 = Tier2Exit(config)
        
        # 100 shares → 40% = 40 shares
        position_100 = {
            'ticker': 'INTR',
            'shares': 100,
            'entry_price': 10.0,
            'exit_tiers': {}
        }
        
        result = tier2.execute_exit(position_100, quote_in_range, dry_run=True)
        
        assert result['shares_to_sell'] == 40


# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestTier2EdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_already_executed_blocked(self, config, position, current_time, quote_in_range, bars_with_spike):
        """Already executed Tier-2 should block re-execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Mark Tier-2 already executed
        position['exit_tiers']['tier2'] = {
            'timestamp': '2025-10-20 09:30:00',
            'shares_sold': 28,
            'exit_price': 10.85,
        }
        
        should_exec, reason = tier2.should_execute(position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "Tier-2 already executed" in reason
    
    def test_insufficient_shares_remaining_blocked(self, config, current_time, quote_in_range, bars_with_spike):
        """Insufficient shares remaining should block execution."""
        price_provider = MockPriceProvider(bars_with_spike)
        tier2 = Tier2Exit(config, price_provider=price_provider)
        
        # Only 15 shares, 40% exit = 6 shares, leaving 9 (< 10 min_shares_remaining)
        small_position = {
            'ticker': 'INTR',
            'entry_date': '2025-10-19',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 15,  # After selling 6 shares (40%), only 9 remain
            'exit_tiers': {}
        }
        
        should_exec, reason = tier2.should_execute(small_position, quote_in_range, current_time)
        
        assert should_exec is False
        assert "shares remaining < " in reason
    
    def test_get_stats_returns_copy(self, config):
        """get_stats should return copy (not reference to internal state)."""
        tier2 = Tier2Exit(config)
        
        stats1 = tier2.get_stats()
        stats1['tier2_exits'] = 999
        
        stats2 = tier2.get_stats()
        
        # Original stats should be unchanged
        assert stats2['tier2_exits'] == 0
