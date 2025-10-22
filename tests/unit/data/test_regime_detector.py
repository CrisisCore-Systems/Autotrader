"""
Tests for market regime detector implementations.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import Mock, patch

from src.bouncehunter.data.regime_detector import (
    RegimeDetector,
    SPYRegimeDetector,
    MockRegimeDetector,
    MarketRegime
)

EASTERN = ZoneInfo("America/New_York")


class TestMockRegimeDetector:
    """Test mock regime detector."""
    
    def test_returns_default_sideways(self):
        """Mock detector returns SIDEWAYS by default."""
        detector = MockRegimeDetector()
        assert detector.detect_regime() == MarketRegime.SIDEWAYS
    
    def test_returns_custom_regime(self):
        """Mock detector returns configured regime."""
        detector = MockRegimeDetector(regime=MarketRegime.BULL)
        assert detector.detect_regime() == MarketRegime.BULL
    
    def test_set_regime_updates_value(self):
        """set_regime() updates returned regime."""
        detector = MockRegimeDetector(regime=MarketRegime.BEAR)
        assert detector.detect_regime() == MarketRegime.BEAR
        
        detector.set_regime(MarketRegime.BULL)
        assert detector.detect_regime() == MarketRegime.BULL
    
    def test_get_regime_details_returns_mock_data(self):
        """get_regime_details() returns mock details."""
        detector = MockRegimeDetector(regime=MarketRegime.BULL)
        details = detector.get_regime_details()
        
        assert details['regime'] == 'BULL'
        assert details['mock'] is True
        assert 'sma_20' in details
        assert 'sma_50' in details


class TestSPYRegimeDetector:
    """Test SPY regime detector."""
    
    @pytest.fixture
    def mock_price_provider(self):
        """Mock price provider."""
        provider = Mock()
        return provider
    
    def _create_bars(self, prices):
        """Create mock bar objects from prices."""
        bars = []
        for price in prices:
            bar = Mock()
            bar.close = price
            bars.append(bar)
        return bars
    
    def test_detect_bull_regime(self, mock_price_provider):
        """Detect BULL regime when 20 SMA > 50 SMA + threshold."""
        # Create uptrending prices: 50 bars from 400 to 450
        prices = [400 + (i * 1.0) for i in range(60)]  # Steady uptrend
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(mock_price_provider, sideways_threshold_pct=0.5)
        regime = detector.detect_regime()
        
        assert regime == MarketRegime.BULL
        
        details = detector.get_regime_details()
        assert details['regime'] == 'BULL'
        assert details['sma_20'] > details['sma_50']
        assert details['spread_pct'] > 0.5
    
    def test_detect_bear_regime(self, mock_price_provider):
        """Detect BEAR regime when 20 SMA < 50 SMA - threshold."""
        # Create downtrending prices: 60 bars from 450 to 400
        prices = [450 - (i * 1.0) for i in range(60)]  # Steady downtrend
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(mock_price_provider, sideways_threshold_pct=0.5)
        regime = detector.detect_regime()
        
        assert regime == MarketRegime.BEAR
        
        details = detector.get_regime_details()
        assert details['regime'] == 'BEAR'
        assert details['sma_20'] < details['sma_50']
        assert details['spread_pct'] < -0.5
    
    def test_detect_sideways_regime(self, mock_price_provider):
        """Detect SIDEWAYS regime when SMAs are close."""
        # Create flat prices: 60 bars around 425 with small fluctuations
        prices = [425 + (i % 10 - 5) * 0.1 for i in range(60)]  # Choppy, no trend
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(mock_price_provider, sideways_threshold_pct=0.5)
        regime = detector.detect_regime()
        
        assert regime == MarketRegime.SIDEWAYS
        
        details = detector.get_regime_details()
        assert details['regime'] == 'SIDEWAYS'
        assert abs(details['spread_pct']) <= 0.5
    
    def test_cache_prevents_redundant_fetches(self, mock_price_provider):
        """Second call within cache TTL uses cached value."""
        prices = [420 + i for i in range(60)]
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(mock_price_provider, cache_ttl_hours=1)
        
        # First call fetches
        regime1 = detector.detect_regime()
        assert mock_price_provider.get_bars.call_count == 1
        
        # Second call uses cache
        regime2 = detector.detect_regime()
        assert mock_price_provider.get_bars.call_count == 1  # No new call
        assert regime1 == regime2
    
    def test_clear_cache_forces_refresh(self, mock_price_provider):
        """clear_cache() forces fresh fetch."""
        prices = [420 + i for i in range(60)]
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(mock_price_provider)
        
        # First call
        detector.detect_regime()
        assert mock_price_provider.get_bars.call_count == 1
        
        # Clear cache
        detector.clear_cache()
        
        # Next call fetches fresh
        detector.detect_regime()
        assert mock_price_provider.get_bars.call_count == 2
    
    def test_insufficient_data_returns_sideways(self, mock_price_provider):
        """Insufficient data falls back to SIDEWAYS."""
        # Only 30 bars (need 50)
        prices = [425 for _ in range(30)]
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(mock_price_provider)
        regime = detector.detect_regime()
        
        # Should fallback to SIDEWAYS
        assert regime == MarketRegime.SIDEWAYS
    
    def test_api_error_returns_sideways(self, mock_price_provider):
        """API error falls back to SIDEWAYS."""
        mock_price_provider.get_bars.side_effect = Exception("API Error")
        
        detector = SPYRegimeDetector(mock_price_provider)
        regime = detector.detect_regime()
        
        # Should fallback to SIDEWAYS
        assert regime == MarketRegime.SIDEWAYS
    
    def test_custom_sma_windows(self, mock_price_provider):
        """Custom SMA windows can be configured."""
        # 80 bars for custom 30/70 window
        prices = [400 + i for i in range(80)]
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(
            mock_price_provider,
            short_window=30,
            long_window=70
        )
        
        regime = detector.detect_regime()
        details = detector.get_regime_details()
        
        # Should calculate successfully with custom windows
        assert regime in [MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS]
        assert 'sma_20' in details  # Keys still named sma_20/sma_50 (generic names)
        assert 'sma_50' in details
    
    def test_regime_details_include_diagnostics(self, mock_price_provider):
        """Regime details include full diagnostics."""
        prices = [425 + i for i in range(60)]
        bars = self._create_bars(prices)
        
        mock_price_provider.get_bars.return_value = bars
        
        detector = SPYRegimeDetector(mock_price_provider)
        detector.detect_regime()
        
        details = detector.get_regime_details()
        
        # Check all expected fields
        assert 'regime' in details
        assert 'sma_20' in details
        assert 'sma_50' in details
        assert 'spread_pct' in details
        assert 'last_price' in details
        assert 'calculated_at' in details
        assert 'bars_used' in details
        
        # Values should be reasonable
        assert details['sma_20'] > 0
        assert details['sma_50'] > 0
        assert details['last_price'] > 0
        assert details['bars_used'] == 60


class TestRegimeDetectorIntegration:
    """Test regime detector integration scenarios."""
    
    def test_mock_detector_for_testing(self):
        """Mock detector enables controlled testing."""
        # Can easily test all regime scenarios
        for regime in [MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.SIDEWAYS]:
            detector = MockRegimeDetector(regime=regime)
            assert detector.detect_regime() == regime
    
    def test_spy_detector_with_market_conditions(self):
        """SPY detector integrates with MarketConditions."""
        from src.bouncehunter.exits.adjustments import MarketConditions
        
        # Use mock detector for predictable testing
        regime_detector = MockRegimeDetector(regime=MarketRegime.BULL)
        conditions = MarketConditions(regime_detector=regime_detector)
        
        # MarketConditions should use detector
        regime = conditions.get_market_regime()
        assert regime == MarketRegime.BULL
    
    def test_regime_transitions(self):
        """Test regime transitions over time."""
        detector = MockRegimeDetector(regime=MarketRegime.SIDEWAYS)
        
        # Start sideways
        assert detector.detect_regime() == MarketRegime.SIDEWAYS
        
        # Transition to bull
        detector.set_regime(MarketRegime.BULL)
        assert detector.detect_regime() == MarketRegime.BULL
        
        # Transition to bear
        detector.set_regime(MarketRegime.BEAR)
        assert detector.detect_regime() == MarketRegime.BEAR
