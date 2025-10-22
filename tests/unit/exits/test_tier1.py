"""
Unit tests for Tier-1 exit logic.

Tests day counting, time window validation, profit thresholds, order execution.
"""

import pytest
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from src.bouncehunter.exits.tier1 import Tier1Exit, EASTERN
from src.bouncehunter.data.price_provider import Quote


class MockBroker:
    """Mock broker for testing."""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.orders = []
    
    def submit_order(self, symbol, qty, side, type, time_in_force):
        """Mock order submission."""
        if self.should_fail:
            raise Exception("Broker error: market closed")
        
        order = {
            'id': f'ORDER_{len(self.orders) + 1}',
            'symbol': symbol,
            'qty': qty,
            'side': side,
            'type': type,
            'time_in_force': time_in_force,
            'filled_qty': qty,
            'filled_avg_price': 10.50,
            'status': 'filled'
        }
        
        self.orders.append(order)
        return order


class TestTier1DayCounting:
    """Test trading day counting logic."""
    
    @pytest.fixture
    def config(self):
        """Default Tier-1 config."""
        return {
            'enabled': True,
            'profit_threshold_pct': 5.0,
            'exit_percentage': 30.0,
            'time_window_start': '15:50',
            'time_window_end': '15:55',
            'min_trading_days': 1,
            'max_trading_days': 1,
            'min_shares_remaining': 5
        }
    
    def test_entry_day_is_day_1(self, config):
        """Test that entry day counts as Day 1."""
        tier1 = Tier1Exit(config)
        
        entry_time = datetime(2025, 10, 20, 9, 35, tzinfo=EASTERN)
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        
        position = {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00'
        }
        
        days = tier1.count_trading_days(position, current_time)
        assert days == 1
    
    def test_next_day_is_day_2(self, config):
        """Test that next calendar day is Day 2."""
        tier1 = Tier1Exit(config)
        
        entry_time = datetime(2025, 10, 20, 9, 35, tzinfo=EASTERN)
        current_time = datetime(2025, 10, 21, 10, 30, tzinfo=EASTERN)
        
        position = {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00'
        }
        
        days = tier1.count_trading_days(position, current_time)
        assert days == 2
    
    def test_three_days_later(self, config):
        """Test Day 3+ counting."""
        tier1 = Tier1Exit(config)
        
        position = {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00'
        }
        
        current_time = datetime(2025, 10, 23, 14, 00, tzinfo=EASTERN)
        days = tier1.count_trading_days(position, current_time)
        assert days == 4  # Oct 20, 21, 22, 23 = 4 days
    
    def test_invalid_date_defaults_to_day_1(self, config):
        """Test that invalid entry date safely defaults to Day 1."""
        tier1 = Tier1Exit(config)
        
        position = {
            'ticker': 'TEST',
            'entry_date': 'INVALID',
            'entry_time': 'INVALID'
        }
        
        days = tier1.count_trading_days(position)
        assert days == 1


class TestTier1TimeWindow:
    """Test time window validation."""
    
    @pytest.fixture
    def config(self):
        """Default Tier-1 config."""
        return {
            'profit_threshold_pct': 5.0,
            'exit_percentage': 30.0,
            'time_window_start': '15:50',
            'time_window_end': '15:55',
            'min_trading_days': 1,
            'max_trading_days': 1,
            'min_shares_remaining': 5
        }
    
    @pytest.fixture
    def position(self):
        """Sample position on Day 1."""
        return {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 100,
            'exit_tiers': {}
        }
    
    def test_within_time_window(self, config, position):
        """Test execution allowed within time window."""
        tier1 = Tier1Exit(config)
        
        # 15:52 ET - within 15:50-15:55 window
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is True
        assert "time window OK" in reason
    
    def test_before_time_window(self, config, position):
        """Test execution blocked before time window."""
        tier1 = Tier1Exit(config)
        
        # 14:00 ET - before 15:50
        current_time = datetime(2025, 10, 20, 14, 0, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is False
        assert "Outside time window" in reason
    
    def test_after_time_window(self, config, position):
        """Test execution blocked after time window."""
        tier1 = Tier1Exit(config)
        
        # 16:00 ET - after 15:55
        current_time = datetime(2025, 10, 20, 16, 0, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is False
        assert "Outside time window" in reason
    
    def test_exactly_at_window_start(self, config, position):
        """Test execution allowed at window start."""
        tier1 = Tier1Exit(config)
        
        # Exactly 15:50
        current_time = datetime(2025, 10, 20, 15, 50, 0, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is True
    
    def test_exactly_at_window_end(self, config, position):
        """Test execution allowed at window end."""
        tier1 = Tier1Exit(config)
        
        # Exactly 15:55
        current_time = datetime(2025, 10, 20, 15, 55, 0, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is True


class TestTier1ProfitThreshold:
    """Test profit threshold validation."""
    
    @pytest.fixture
    def config(self):
        """Config with 5% profit threshold."""
        return {
            'profit_threshold_pct': 5.0,
            'exit_percentage': 30.0,
            'time_window_start': '15:50',
            'time_window_end': '15:55',
            'min_trading_days': 1,
            'max_trading_days': 1,
            'min_shares_remaining': 5
        }
    
    @pytest.fixture
    def position(self):
        """Sample position."""
        return {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 100,
            'exit_tiers': {}
        }
    
    def test_profit_above_threshold(self, config, position):
        """Test execution allowed when profit >= threshold."""
        tier1 = Tier1Exit(config)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        # Entry: $10.00, Current: $10.60 → +6% (above 5% threshold)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is True
        assert "profit 6.00%" in reason
    
    def test_profit_exactly_at_threshold(self, config, position):
        """Test execution allowed when profit exactly at threshold."""
        tier1 = Tier1Exit(config)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        # Entry: $10.00, Current: $10.50 → exactly +5%
        quote = Quote('TEST', 10.50, 10.49, 10.51, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is True
    
    def test_profit_below_threshold(self, config, position):
        """Test execution blocked when profit < threshold."""
        tier1 = Tier1Exit(config)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        # Entry: $10.00, Current: $10.30 → +3% (below 5% threshold)
        quote = Quote('TEST', 10.30, 10.29, 10.31, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is False
        assert "Profit 3.00% < threshold 5.0%" in reason
    
    def test_negative_profit_blocked(self, config, position):
        """Test execution blocked on negative profit."""
        tier1 = Tier1Exit(config)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        # Entry: $10.00, Current: $9.50 → -5%
        quote = Quote('TEST', 9.50, 9.49, 9.51, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is False
        assert "Profit -5.00% < threshold" in reason


class TestTier1ExecutionLogic:
    """Test order execution logic."""
    
    @pytest.fixture
    def config(self):
        """Default config."""
        return {
            'profit_threshold_pct': 5.0,
            'exit_percentage': 30.0,
            'time_window_start': '15:50',
            'time_window_end': '15:55',
            'min_trading_days': 1,
            'max_trading_days': 1,
            'min_shares_remaining': 5
        }
    
    @pytest.fixture
    def position(self):
        """Sample position."""
        return {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 100,
            'exit_tiers': {}
        }
    
    def test_dry_run_execution(self, config, position):
        """Test dry-run execution (no broker needed)."""
        tier1 = Tier1Exit(config)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        result = tier1.execute_exit(position, quote, dry_run=True)
        
        assert result['status'] == 'success_dry_run'
        assert result['ticker'] == 'TEST'
        assert result['shares_to_sell'] == 30  # 30% of 100
        assert result['exit_price'] == 10.60
        assert result['order_id'] == 'DRY_RUN'
        assert tier1.execution_count == 1
    
    def test_real_execution_success(self, config, position):
        """Test real order execution with mock broker."""
        mock_broker = MockBroker()
        tier1 = Tier1Exit(config, broker=mock_broker)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        result = tier1.execute_exit(position, quote, dry_run=False)
        
        assert result['status'] == 'success'
        assert result['shares_to_sell'] == 30
        assert result['order_id'] == 'ORDER_1'
        assert result['filled_qty'] == 30
        assert len(mock_broker.orders) == 1
        assert tier1.execution_count == 1
    
    def test_execution_without_broker(self, config, position):
        """Test execution fails without broker."""
        tier1 = Tier1Exit(config, broker=None)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        result = tier1.execute_exit(position, quote, dry_run=False)
        
        assert result['status'] == 'error'
        assert 'No broker configured' in result['error']
    
    def test_execution_broker_error(self, config, position):
        """Test execution handles broker errors."""
        mock_broker = MockBroker(should_fail=True)
        tier1 = Tier1Exit(config, broker=mock_broker)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        result = tier1.execute_exit(position, quote, dry_run=False)
        
        assert result['status'] == 'error'
        assert 'market closed' in result['error']
    
    def test_calculates_correct_share_quantity(self, config, position):
        """Test share quantity calculation."""
        tier1 = Tier1Exit(config)
        
        # 30% of 100 = 30 shares
        position['shares'] = 100
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        result = tier1.execute_exit(position, quote, dry_run=True)
        assert result['shares_to_sell'] == 30
        
        # 30% of 50 = 15 shares
        position['shares'] = 50
        result = tier1.execute_exit(position, quote, dry_run=True)
        assert result['shares_to_sell'] == 15


class TestTier1EdgeCases:
    """Test edge cases and validation."""
    
    @pytest.fixture
    def config(self):
        """Default config."""
        return {
            'profit_threshold_pct': 5.0,
            'exit_percentage': 30.0,
            'time_window_start': '15:50',
            'time_window_end': '15:55',
            'min_trading_days': 1,
            'max_trading_days': 1,
            'min_shares_remaining': 5
        }
    
    def test_already_executed(self, config):
        """Test execution blocked if tier1 already executed."""
        tier1 = Tier1Exit(config)
        
        position = {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 100,
            'exit_tiers': {
                'tier1': {
                    'executed': True,
                    'exit_price': 10.50,
                    'timestamp': '2025-10-20T15:52:00'
                }
            }
        }
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.80, 10.79, 10.81, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is False
        assert "already executed" in reason
    
    def test_day_2_blocked(self, config):
        """Test execution blocked on Day 2."""
        tier1 = Tier1Exit(config)
        
        position = {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 100,
            'exit_tiers': {}
        }
        
        # Oct 21 = Day 2
        current_time = datetime(2025, 10, 21, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is False
        assert "Past Day 1 window" in reason
    
    def test_insufficient_shares_remaining(self, config):
        """Test execution blocked if would leave too few shares."""
        tier1 = Tier1Exit(config)
        
        position = {
            'ticker': 'TEST',
            'entry_date': '2025-10-20',
            'entry_time': '09:35:00',
            'entry_price': 10.0,
            'shares': 10,  # 30% = 3 shares, leaving 7 (OK)
            'exit_tiers': {}
        }
        
        # But if we only have 6 shares total...
        position['shares'] = 6  # 30% = 1 share, leaving 5 (exactly minimum)
        
        current_time = datetime(2025, 10, 20, 15, 52, tzinfo=EASTERN)
        quote = Quote('TEST', 10.60, 10.59, 10.61, current_time)
        
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        # Should still work (5 remaining == 5 minimum)
        assert should_exec is True
        
        # Now test with 5 shares (30% = 1, leaving 4 < 5 minimum)
        position['shares'] = 5
        should_exec, reason = tier1.should_execute(position, quote, current_time)
        assert should_exec is False
        assert "Would leave 4 < min 5 shares" in reason


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
