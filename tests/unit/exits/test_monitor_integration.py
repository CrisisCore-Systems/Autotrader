"""
Integration tests for PositionMonitor with Tier-1 and Tier-2.

These tests verify the complete monitoring cycle with both exit strategies,
circuit breaker functionality, retry logic, and error handling.
"""
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest

from src.bouncehunter.exits.monitor import PositionMonitor
from src.bouncehunter.data.price_provider import Quote


EASTERN = ZoneInfo("America/New_York")


class MockExitConfig:
    """Mock ExitConfig for testing."""
    
    def __init__(self, config_dict):
        self.config = config_dict
        self.source = "test"
    
    def get(self, *keys, default=None):
        """Get config value by path."""
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def get_tier_config(self, tier):
        """Get tier configuration."""
        return self.config.get(tier, {})
    
    def is_tier_enabled(self, tier):
        """Check if tier is enabled."""
        return tier in self.config and bool(self.config[tier])


@pytest.fixture
def mock_broker():
    """Create mock broker."""
    broker = Mock()
    broker.submit_order.return_value = {'order_id': 'ORDER123', 'status': 'filled'}
    return broker


@pytest.fixture
def mock_price_provider():
    """Create mock price provider."""
    provider = Mock()
    return provider


@pytest.fixture
def mock_position_store():
    """Create mock position store."""
    store = Mock()
    return store


@pytest.fixture
def exit_config():
    """Create exit configuration with both tiers enabled."""
    config_dict = {
        'tier1': {
            'profit_target_pct': 5.0,
            'position_pct': 50.0,
            'min_shares': 10,
            'time_window_start': '09:30',
            'time_window_end': '16:00',
            'min_trading_days': 1,
            'max_trading_days': 1,
            'cooldown_minutes': 15,
            'min_shares_remaining': 5
        },
        'tier2': {
            'profit_target_min_pct': 8.0,
            'profit_target_max_pct': 10.0,
            'position_pct': 40.0,
            'volume_spike_threshold': 2.0,
            'min_shares': 10,
            'cooldown_minutes': 30,
            'min_trading_days': 2,
            'max_trading_days': 99,
            'min_shares_remaining': 5
        }
    }
    return MockExitConfig(config_dict)


@pytest.fixture
def position_day1():
    """Create Day 1 position (Tier-1 eligible)."""
    return {
        'ticker': 'TEST',
        'shares': 100,
        'entry_price': 10.00,
        'entry_date': '2025-10-20',  # Today
        'entry_time': '10:00:00',
        'exit_tiers': {}
    }


@pytest.fixture
def position_day2():
    """Create Day 2 position (Tier-2 eligible)."""
    return {
        'ticker': 'TEST',
        'shares': 100,
        'entry_price': 10.00,
        'entry_date': '2025-10-19',  # Yesterday
        'entry_time': '10:00:00',
        'exit_tiers': {}
    }


@pytest.fixture
def quote_tier1():
    """Create quote at 5% profit (Tier-1 eligible)."""
    return Quote(
        ticker='TEST',
        price=10.50,
        bid=10.49,
        ask=10.51,
        timestamp=datetime.now(EASTERN)
    )


@pytest.fixture
def quote_tier2():
    """Create quote at 9% profit (Tier-2 eligible)."""
    return Quote(
        ticker='TEST',
        price=10.90,
        bid=10.89,
        ask=10.91,
        timestamp=datetime.now(EASTERN)
    )


@pytest.fixture
def bars_with_spike():
    """Create bars showing volume spike."""
    base_volume = 50000
    bars = []
    for _ in range(29):
        bar = Mock()
        bar.volume = base_volume
        bar.close = 10.0
        bar.high = 10.1
        bar.low = 9.9
        bars.append(bar)
    # Add spike bar
    spike_bar = Mock()
    spike_bar.volume = base_volume * 2.5
    spike_bar.close = 10.5
    spike_bar.high = 10.6
    spike_bar.low = 10.4
    bars.append(spike_bar)
    return bars


class TestMonitorTier1Integration:
    """Test Tier-1 exit integration."""
    
    def test_tier1_executes_when_criteria_met(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config,
        position_day1,
        quote_tier1
    ):
        """Test Tier-1 executes when profit target reached."""
        # No datetime mocking needed - test runs in real time
        
        # Setup
        mock_position_store.get_active_positions.return_value = [position_day1]
        mock_price_provider.get_quote.return_value = quote_tier1
        
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False  # Disable adjustments for this test
        )
        
        # Execute
        monitor.run_monitoring_cycle()
        
        # Verify
        stats = monitor.get_stats()
        assert stats['tier1_exits'] == 1
        assert stats['tier2_exits'] == 0
        assert stats['positions_processed'] == 1
        assert stats['errors'] == 0
        
        # Verify broker was called
        mock_broker.submit_order.assert_called_once()
        order_call = mock_broker.submit_order.call_args[1]
        assert order_call['ticker'] == 'TEST'
        assert order_call['shares'] == 50  # 50% of 100
        assert order_call['side'] == 'sell'


class TestMonitorTier2Integration:
    """Test Tier-2 exit integration."""
    
    def test_tier2_executes_when_criteria_met(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config,
        position_day2,
        quote_tier2,
        bars_with_spike
    ):
        """Test Tier-2 executes when momentum spike detected."""
        # Setup
        mock_position_store.get_active_positions.return_value = [position_day2]
        mock_price_provider.get_quote.return_value = quote_tier2
        mock_price_provider.get_bars.return_value = bars_with_spike
        
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        # Execute
        monitor.run_monitoring_cycle()
        
        # Verify
        stats = monitor.get_stats()
        assert stats['tier1_exits'] == 0
        assert stats['tier2_exits'] == 1
        assert stats['positions_processed'] == 1
        assert stats['errors'] == 0
        
        # Verify broker was called
        mock_broker.submit_order.assert_called_once()
        order_call = mock_broker.submit_order.call_args[1]
        assert order_call['ticker'] == 'TEST'
        assert order_call['shares'] == 40  # 40% of 100
        assert order_call['side'] == 'sell'


class TestMonitorSequentialExits:
    """Test sequential Tier-1 then Tier-2 exits."""
    
    def test_tier1_then_tier2_sequence(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config,
        position_day1,
        quote_tier1,
        quote_tier2,
        bars_with_spike
    ):
        """Test Tier-1 executes, then Tier-2 on Day 2+."""
        # Setup monitor
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        # Cycle 1: Tier-1 exit on Day 1
        mock_position_store.get_active_positions.return_value = [position_day1]
        mock_price_provider.get_quote.return_value = quote_tier1
        
        monitor.run_monitoring_cycle()
        
        # Verify Tier-1 executed
        stats = monitor.get_stats()
        assert stats['tier1_exits'] == 1
        assert stats['tier2_exits'] == 0
        
        # Simulate position update after Tier-1
        position_after_tier1 = {
            'ticker': 'TEST',
            'shares': 50,  # 50% sold in Tier-1
            'entry_price': 10.00,
            'entry_date': '2025-10-19',  # Yesterday = Day 2 today
            'entry_time': '10:00:00',
            'exit_tiers': {
                'tier1': {
                    'executed': True,
                    'exit_price': 10.50,
                    'shares_sold': 50,
                    'timestamp': datetime.now(EASTERN).isoformat()
                }
            }
        }
        
        # Cycle 2: Tier-2 exit on Day 2 with spike
        mock_position_store.get_active_positions.return_value = [position_after_tier1]
        mock_price_provider.get_quote.return_value = quote_tier2
        mock_price_provider.get_bars.return_value = bars_with_spike
        
        monitor.run_monitoring_cycle()
        
        # Verify both tiers executed
        stats = monitor.get_stats()
        assert stats['tier1_exits'] == 1
        assert stats['tier2_exits'] == 1
        assert stats['positions_processed'] == 2  # 2 cycles
        
        # Verify broker called twice
        assert mock_broker.submit_order.call_count == 2


class TestMonitorCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_triggers_after_consecutive_errors(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config
    ):
        """Test circuit breaker activates after 3 consecutive errors."""
        # Setup: make position store fail
        mock_position_store.get_active_positions.side_effect = Exception("API Error")
        
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        # Execute 3 failing cycles
        for _ in range(3):
            monitor.run_monitoring_cycle()
        
        # Verify circuit breaker triggered
        stats = monitor.get_stats()
        assert stats['errors'] == 3
        assert stats['circuit_breaker_trips'] == 1
        assert stats['circuit_breaker_active'] is True
        assert stats['consecutive_errors'] == 3
    
    def test_circuit_breaker_blocks_monitoring(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config
    ):
        """Test circuit breaker blocks monitoring cycles."""
        # Setup: fail 3 times to trigger breaker
        mock_position_store.get_active_positions.side_effect = Exception("API Error")
        
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        for _ in range(3):
            monitor.run_monitoring_cycle()
        
        # Verify breaker active
        assert monitor.get_stats()['circuit_breaker_active'] is True
        
        # Fix the error
        mock_position_store.get_active_positions.side_effect = None
        mock_position_store.get_active_positions.return_value = []
        
        # Try another cycle immediately (should be blocked)
        monitor.run_monitoring_cycle()
        
        # Verify monitoring was skipped (cycles_run doesn't increment)
        stats = monitor.get_stats()
        assert stats['cycles_run'] == 3  # Still 3, not 4


class TestMonitorRetryLogic:
    """Test retry logic with exponential backoff."""
    
    def test_retry_succeeds_on_second_attempt(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config,
        position_day1,
        quote_tier1
    ):
        """Test retry logic succeeds after transient failure."""
        # Setup: fail once, then succeed
        mock_position_store.get_active_positions.side_effect = [
            Exception("Transient error"),
            [position_day1]
        ]
        mock_price_provider.get_quote.return_value = quote_tier1
        
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        # Execute
        monitor.run_monitoring_cycle()
        
        # Verify retry occurred and succeeded
        stats = monitor.get_stats()
        assert stats['retries_performed'] == 1
        assert stats['errors'] == 0  # No error because retry succeeded
        assert stats['tier1_exits'] == 1  # Exit still executed
    
    def test_retry_exhausted_after_max_attempts(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config
    ):
        """Test retry gives up after 3 attempts."""
        # Setup: always fail
        mock_position_store.get_active_positions.side_effect = Exception("Persistent error")
        
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        # Execute
        monitor.run_monitoring_cycle()
        
        # Verify retries exhausted
        stats = monitor.get_stats()
        assert stats['retries_performed'] == 3  # 3 retry attempts
        assert stats['errors'] == 1  # 1 error recorded
        assert stats['consecutive_errors'] == 1


class TestMonitorDryRun:
    """Test dry-run mode."""
    
    def test_dry_run_logs_but_no_execution(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        position_day1,
        quote_tier1
    ):
        """Test dry-run mode prevents actual execution."""
        # Setup with dry_run=True
        config_dict = {
            'tier1': {
                'profit_target_pct': 5.0,
                'position_pct': 50.0,
                'min_shares': 10,
                'time_window_start': '09:30',
                'time_window_end': '16:00',
                'min_trading_days': 1,
                'max_trading_days': 1,
                'cooldown_minutes': 15,
                'min_shares_remaining': 5
            }
        }
        config = MockExitConfig(config_dict)
        config.dry_run = True
        
        mock_position_store.get_active_positions.return_value = [position_day1]
        mock_price_provider.get_quote.return_value = quote_tier1
        
        monitor = PositionMonitor(
            config=config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        # Execute
        monitor.run_monitoring_cycle()
        
        # Verify stats updated but broker NOT called
        stats = monitor.get_stats()
        assert stats['tier1_exits'] == 1
        mock_broker.submit_order.assert_not_called()


class TestMonitorErrorRecovery:
    """Test error recovery and isolation."""
    
    def test_single_position_error_does_not_stop_others(
        self,
        mock_broker,
        mock_price_provider,
        mock_position_store,
        exit_config,
        position_day1,
        quote_tier1
    ):
        """Test that error in one position doesn't stop processing others."""
        # Create two positions
        position2 = {
            'ticker': 'TEST2',
            'shares': 200,
            'entry_price': 20.00,
            'entry_date': '2025-10-20',  # Today
            'entry_time': '10:00:00',
            'exit_tiers': {}
        }
        
        quote2 = Quote(
            ticker='TEST2',
            price=21.00,  # 5% profit
            bid=20.99,
            ask=21.01,
            timestamp=datetime.now(EASTERN)
        )
        
        mock_position_store.get_active_positions.return_value = [position_day1, position2]
        
        # Make first quote fail, second succeed
        mock_price_provider.get_quote.side_effect = [
            Exception("Quote fetch failed"),
            quote2
        ]
        
        monitor = PositionMonitor(
            config=exit_config,
            position_store=mock_position_store,
            price_provider=mock_price_provider,
            broker=mock_broker,
            enable_adjustments=False
        )
        
        # Execute
        monitor.run_monitoring_cycle()
        
        # Verify second position still processed
        stats = monitor.get_stats()
        assert stats['tier1_exits'] == 1  # Only position2 exited
        assert stats['positions_processed'] == 2  # Both attempted
        assert stats['errors'] == 0  # Position-level errors don't increment global error count
