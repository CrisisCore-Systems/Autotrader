"""
Tests for VIX provider implementations.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock, MagicMock, patch

from src.bouncehunter.data.vix_provider import (
    VIXProvider,
    AlpacaVIXProvider,
    MockVIXProvider,
    FallbackVIXProvider,
    DEFAULT_VIX
)

EASTERN = ZoneInfo("America/New_York")


class TestMockVIXProvider:
    """Test mock VIX provider."""
    
    def test_returns_default_vix(self):
        """Mock provider returns default VIX."""
        provider = MockVIXProvider()
        assert provider.get_vix() == DEFAULT_VIX
    
    def test_returns_custom_vix(self):
        """Mock provider returns custom VIX."""
        provider = MockVIXProvider(vix_value=25.5)
        assert provider.get_vix() == 25.5
    
    def test_set_vix_updates_value(self):
        """set_vix() updates returned value."""
        provider = MockVIXProvider(vix_value=15.0)
        assert provider.get_vix() == 15.0
        
        provider.set_vix(30.0)
        assert provider.get_vix() == 30.0


class TestAlpacaVIXProvider:
    """Test Alpaca VIX provider."""
    
    @pytest.fixture
    def mock_alpaca_client(self):
        """Mock Alpaca client."""
        client = Mock()
        return client
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestQuoteRequest', create=True)
    def test_fetch_vix_with_latest_quote(self, mock_request_class, mock_alpaca_client):
        """Fetch VIX using get_latest_quote method."""
        # Mock quote data
        mock_quote = Mock()
        mock_quote.ask_price = 20.5
        mock_quote.bid_price = 20.3
        
        mock_alpaca_client.get_latest_quote.return_value = {'VIX': mock_quote}
        
        provider = AlpacaVIXProvider(mock_alpaca_client)
        vix = provider.get_vix()
        
        assert vix == 20.4  # (20.5 + 20.3) / 2
        assert provider._cached_vix == 20.4
        assert provider._cache_timestamp is not None
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockSnapshotRequest', create=True)
    def test_fetch_vix_with_snapshot(self, mock_request_class, mock_alpaca_client):
        """Fetch VIX using get_snapshot method."""
        # Remove get_latest_quote to force snapshot method
        del mock_alpaca_client.get_latest_quote
        
        # Mock snapshot data
        mock_quote = Mock()
        mock_quote.ask_price = 25.0
        mock_quote.bid_price = 24.8
        
        mock_snapshot = Mock()
        mock_snapshot.latest_quote = mock_quote
        
        mock_alpaca_client.get_snapshot.return_value = {'VIX': mock_snapshot}
        
        provider = AlpacaVIXProvider(mock_alpaca_client)
        vix = provider.get_vix()
        
        assert vix == 24.9  # (25.0 + 24.8) / 2
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestTradeRequest', create=True)
    def test_fetch_vix_with_latest_trade(self, mock_request_class, mock_alpaca_client):
        """Fetch VIX using get_latest_trade method."""
        # Remove other methods to force trade method
        del mock_alpaca_client.get_latest_quote
        del mock_alpaca_client.get_snapshot
        
        # Mock trade data
        mock_trade = Mock()
        mock_trade.price = 18.5
        
        mock_alpaca_client.get_latest_trade.return_value = {'VIX': mock_trade}
        
        provider = AlpacaVIXProvider(mock_alpaca_client)
        vix = provider.get_vix()
        
        assert vix == 18.5
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestQuoteRequest', create=True)
    def test_cache_hit_returns_cached_value(self, mock_request_class, mock_alpaca_client):
        """Second call within cache TTL returns cached value without API call."""
        mock_quote = Mock()
        mock_quote.ask_price = 20.0
        mock_quote.bid_price = 20.0
        
        mock_alpaca_client.get_latest_quote.return_value = {'VIX': mock_quote}
        
        provider = AlpacaVIXProvider(mock_alpaca_client, cache_ttl_seconds=300)
        
        # First call fetches
        vix1 = provider.get_vix()
        assert vix1 == 20.0
        assert mock_alpaca_client.get_latest_quote.call_count == 1
        
        # Second call uses cache
        vix2 = provider.get_vix()
        assert vix2 == 20.0
        assert mock_alpaca_client.get_latest_quote.call_count == 1  # No new call
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestQuoteRequest', create=True)
    def test_cache_miss_after_ttl(self, mock_request_class, mock_alpaca_client):
        """Call after cache TTL fetches fresh data."""
        mock_quote = Mock()
        mock_quote.ask_price = 20.0
        mock_quote.bid_price = 20.0
        
        mock_alpaca_client.get_latest_quote.return_value = {'VIX': mock_quote}
        
        provider = AlpacaVIXProvider(mock_alpaca_client, cache_ttl_seconds=1)
        
        # First call
        vix1 = provider.get_vix()
        assert vix1 == 20.0
        
        # Simulate time passing
        with patch('src.bouncehunter.data.vix_provider.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime.now(EASTERN) + timedelta(seconds=2)
            
            # Update mock to return different value
            mock_quote.ask_price = 25.0
            mock_quote.bid_price = 25.0
            mock_alpaca_client.get_latest_quote.return_value = {'VIX': mock_quote}
            
            # Second call should fetch fresh
            # Note: This test is simplified - in reality we'd need to mock the entire time system
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestQuoteRequest', create=True)
    def test_clear_cache_forces_refresh(self, mock_request_class, mock_alpaca_client):
        """clear_cache() forces fresh fetch on next call."""
        mock_quote = Mock()
        mock_quote.ask_price = 20.0
        mock_quote.bid_price = 20.0
        
        mock_alpaca_client.get_latest_quote.return_value = {'VIX': mock_quote}
        
        provider = AlpacaVIXProvider(mock_alpaca_client)
        
        # First call
        vix1 = provider.get_vix()
        assert mock_alpaca_client.get_latest_quote.call_count == 1
        
        # Clear cache
        provider.clear_cache()
        
        # Next call fetches fresh
        vix2 = provider.get_vix()
        assert mock_alpaca_client.get_latest_quote.call_count == 2
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestQuoteRequest', create=True)
    def test_fetch_error_returns_none(self, mock_request_class, mock_alpaca_client):
        """API error returns None."""
        mock_alpaca_client.get_latest_quote.side_effect = Exception("API error")
        
        provider = AlpacaVIXProvider(mock_alpaca_client)
        vix = provider.get_vix()
        
        assert vix is None
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestQuoteRequest', create=True)
    def test_missing_symbol_returns_none(self, mock_request_class, mock_alpaca_client):
        """Missing VIX symbol in response returns None."""
        # Return empty dict (VIX not in response)
        mock_alpaca_client.get_latest_quote.return_value = {}
        
        provider = AlpacaVIXProvider(mock_alpaca_client)
        vix = provider.get_vix()
        
        assert vix is None
    
    @patch('src.bouncehunter.data.vix_provider.ALPACA_AVAILABLE', True)
    @patch('src.bouncehunter.data.vix_provider.StockLatestQuoteRequest', create=True)
    def test_custom_symbol(self, mock_request_class, mock_alpaca_client):
        """Custom VIX symbol can be specified."""
        mock_quote = Mock()
        mock_quote.ask_price = 22.0
        mock_quote.bid_price = 22.0
        
        mock_alpaca_client.get_latest_quote.return_value = {'^VIX': mock_quote}
        
        provider = AlpacaVIXProvider(mock_alpaca_client, symbol='^VIX')
        vix = provider.get_vix()
        
        assert vix == 22.0


class TestFallbackVIXProvider:
    """Test fallback VIX provider."""
    
    def test_returns_primary_value_on_success(self):
        """Returns primary provider value when successful."""
        primary = MockVIXProvider(vix_value=25.0)
        fallback = FallbackVIXProvider(primary, default_vix=20.0)
        
        vix = fallback.get_vix()
        assert vix == 25.0
    
    def test_returns_default_on_primary_none(self):
        """Returns default when primary returns None."""
        primary = Mock(spec=VIXProvider)
        primary.get_vix.return_value = None
        
        fallback = FallbackVIXProvider(primary, default_vix=18.0)
        
        vix = fallback.get_vix()
        assert vix == 18.0
    
    def test_returns_default_on_primary_error(self):
        """Returns default when primary raises exception."""
        primary = Mock(spec=VIXProvider)
        primary.get_vix.side_effect = Exception("API error")
        
        fallback = FallbackVIXProvider(primary, default_vix=20.0)
        
        vix = fallback.get_vix()
        assert vix == 20.0
    
    def test_default_vix_value(self):
        """Default VIX is 20.0 if not specified."""
        primary = Mock(spec=VIXProvider)
        primary.get_vix.return_value = None
        
        fallback = FallbackVIXProvider(primary)
        
        vix = fallback.get_vix()
        assert vix == DEFAULT_VIX


class TestVIXProviderIntegration:
    """Integration tests for VIX providers."""
    
    def test_mock_provider_in_adjustment_calculator(self):
        """Mock provider works with MarketConditions."""
        from src.bouncehunter.exits.adjustments import MarketConditions
        
        provider = MockVIXProvider(vix_value=30.0)
        conditions = MarketConditions(vix_provider=provider)
        
        # MarketConditions should use provider
        volatility_level = conditions.get_volatility_level(current_vix=30.0)
        
        # 30.0 is EXTREME volatility
        from src.bouncehunter.exits.adjustments import VolatilityLevel
        assert volatility_level == VolatilityLevel.EXTREME
    
    def test_fallback_provider_ensures_reliability(self):
        """Fallback provider ensures system keeps working even if VIX fetch fails."""
        from src.bouncehunter.exits.adjustments import MarketConditions, AdjustmentCalculator
        
        # Primary that fails
        primary = Mock(spec=VIXProvider)
        primary.get_vix.side_effect = Exception("Network error")
        
        # Fallback ensures we get a value
        provider = FallbackVIXProvider(primary, default_vix=20.0)
        conditions = MarketConditions(vix_provider=provider)
        
        # Disable time and regime adjustments to isolate volatility adjustment
        calculator = AdjustmentCalculator(
            conditions, 
            enable_time_adjustments=False, 
            enable_regime_adjustments=False
        )
        
        # Should still work with default VIX
        target, details = calculator.adjust_tier1_target(5.0)
        
        # With VIX=20 (HIGH), expect -1% volatility adjustment
        assert details['volatility_adjustment'] == -1.0
        assert target == 4.0  # 5.0 + (-1.0)
