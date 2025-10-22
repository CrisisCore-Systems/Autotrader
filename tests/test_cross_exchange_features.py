"""Unit tests for cross-exchange feature engineering."""

from __future__ import annotations

import numpy as np
import pytest

from src.features.cross_exchange_features import (
    CrossExchangeFeatureExtractor,
    CrossExchangeFeatures,
)


@pytest.fixture
def feature_extractor() -> CrossExchangeFeatureExtractor:
    """Create a feature extractor instance for testing."""
    return CrossExchangeFeatureExtractor(lookback_window=10, price_history_size=100)


@pytest.fixture
def sample_order_books() -> dict[str, dict]:
    """Create sample order books from multiple exchanges."""
    return {
        "binance": {
            "best_bid": 100.0,
            "best_ask": 100.5,
            "bid_size": 10.0,
            "ask_size": 12.0,
            "timestamp": 1000.0,
        },
        "coinbase": {
            "best_bid": 99.8,
            "best_ask": 100.3,
            "bid_size": 8.0,
            "ask_size": 9.0,
            "timestamp": 1000.0,
        },
        "kraken": {
            "best_bid": 100.2,
            "best_ask": 100.7,
            "bid_size": 15.0,
            "ask_size": 14.0,
            "timestamp": 1000.0,
        },
    }


def test_feature_extractor_initialization() -> None:
    """Test that feature extractor initializes with correct defaults."""
    extractor = CrossExchangeFeatureExtractor()
    assert extractor.lookback_window == 100
    assert extractor.price_history_size == 1000
    assert len(extractor.price_history) == 0


def test_update_adds_price_history(feature_extractor: CrossExchangeFeatureExtractor) -> None:
    """Test that update method adds data to price history."""
    feature_extractor.update("binance", 100.0, 10.0, 1000.0)
    
    assert "binance" in feature_extractor.price_history
    assert len(feature_extractor.price_history["binance"]) == 1
    assert feature_extractor.price_history["binance"][0] == 100.0
    assert feature_extractor.volume_history["binance"][0] == 10.0
    assert feature_extractor.timestamp_history["binance"][0] == 1000.0


def test_update_trims_to_max_size(feature_extractor: CrossExchangeFeatureExtractor) -> None:
    """Test that price history is trimmed to max size."""
    # Add more data than max size
    for i in range(150):
        feature_extractor.update("binance", 100.0 + i * 0.1, 10.0, 1000.0 + i)
    
    assert len(feature_extractor.price_history["binance"]) == 100
    # Should keep the most recent 100
    assert feature_extractor.price_history["binance"][0] == 100.0 + 50 * 0.1


def test_extract_features_requires_multiple_exchanges(
    feature_extractor: CrossExchangeFeatureExtractor,
) -> None:
    """Test that feature extraction requires at least 2 exchanges."""
    single_book = {
        "binance": {
            "best_bid": 100.0,
            "best_ask": 100.5,
            "bid_size": 10.0,
            "ask_size": 12.0,
            "timestamp": 1000.0,
        }
    }
    
    features = feature_extractor.extract_features(single_book, [])
    assert features is None


def test_extract_features_calculates_price_dispersion(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test that price dispersion is calculated correctly."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    assert features.price_dispersion >= 0.0
    # Price dispersion should be small for closely aligned prices
    assert features.price_dispersion < 0.01


def test_extract_features_calculates_spreads(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test that price spreads are calculated correctly in basis points."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    assert features.max_price_spread_bps > 0
    assert features.min_price_spread_bps <= features.max_price_spread_bps


def test_extract_features_handles_arbitrage_opportunities(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test arbitrage opportunity feature extraction."""
    arb_opportunities = [
        {"profit_bps": 50.0, "buy_exchange": "coinbase", "sell_exchange": "binance"},
        {"profit_bps": 30.0, "buy_exchange": "coinbase", "sell_exchange": "kraken"},
    ]
    
    features = feature_extractor.extract_features(sample_order_books, arb_opportunities)
    
    assert features is not None
    assert features.arb_opportunity_count == 2
    assert features.best_arb_opportunity_bps == 50.0
    assert features.avg_arb_profit_bps == 40.0


def test_extract_features_handles_no_arbitrage(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test feature extraction with no arbitrage opportunities."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    assert features.arb_opportunity_count == 0
    assert features.best_arb_opportunity_bps == 0.0
    assert features.avg_arb_profit_bps == 0.0


def test_extract_features_calculates_volume_concentration(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test volume concentration (Herfindahl index) calculation."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    # Volume concentration should be between 1/n and 1
    assert 1.0 / len(sample_order_books) <= features.volume_concentration <= 1.0


def test_extract_features_identifies_dominant_exchange(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test that dominant exchange is identified correctly by volume."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    # Kraken has highest total volume (15 + 14 = 29)
    assert features.dominant_exchange == "kraken"


def test_extract_features_calculates_depth_imbalance(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test depth imbalance ratio calculation."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    assert features.depth_imbalance_ratio >= 1.0


def test_extract_features_with_price_history(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test feature extraction with historical price data for correlation."""
    # Add price history for exchanges
    for i in range(50):
        feature_extractor.update("binance", 100.0 + i * 0.1, 10.0, 1000.0 + i)
        feature_extractor.update("coinbase", 100.0 + i * 0.1 + np.random.randn() * 0.05, 8.0, 1000.0 + i)
    
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    # Correlation should be calculated
    assert -1.0 <= features.price_sync_correlation <= 1.0
    assert features.lead_lag_coefficient >= 0.0


def test_extract_features_returns_all_required_fields(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test that extracted features contain all required fields."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    assert isinstance(features, CrossExchangeFeatures)
    
    # Check all fields are present
    assert hasattr(features, "price_dispersion")
    assert hasattr(features, "max_price_spread_bps")
    assert hasattr(features, "min_price_spread_bps")
    assert hasattr(features, "price_entropy")
    assert hasattr(features, "best_arb_opportunity_bps")
    assert hasattr(features, "arb_opportunity_count")
    assert hasattr(features, "avg_arb_profit_bps")
    assert hasattr(features, "vw_price_dispersion")
    assert hasattr(features, "volume_concentration")
    assert hasattr(features, "price_sync_correlation")
    assert hasattr(features, "lead_lag_coefficient")
    assert hasattr(features, "dominant_exchange")
    assert hasattr(features, "depth_imbalance_ratio")
    assert hasattr(features, "consolidated_spread_bps")
    assert hasattr(features, "cross_exchange_vol_ratio")
    assert hasattr(features, "vol_dispersion")
    assert hasattr(features, "timestamp")


def test_to_dict_converts_features_correctly(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test that to_dict method converts features to dictionary correctly."""
    features = feature_extractor.extract_features(sample_order_books, [])
    assert features is not None
    
    feature_dict = feature_extractor.to_dict(features)
    
    assert isinstance(feature_dict, dict)
    assert "price_dispersion" in feature_dict
    assert "max_price_spread_bps" in feature_dict
    assert "arb_opportunity_count" in feature_dict
    # All values should be numeric
    assert all(isinstance(v, (int, float)) for v in feature_dict.values())


def test_extract_features_handles_zero_volume(
    feature_extractor: CrossExchangeFeatureExtractor,
) -> None:
    """Test that feature extraction handles zero volume gracefully."""
    zero_volume_books = {
        "binance": {
            "best_bid": 100.0,
            "best_ask": 100.5,
            "bid_size": 0.0,
            "ask_size": 0.0,
            "timestamp": 1000.0,
        },
        "coinbase": {
            "best_bid": 99.8,
            "best_ask": 100.3,
            "bid_size": 0.0,
            "ask_size": 0.0,
            "timestamp": 1000.0,
        },
    }
    
    features = feature_extractor.extract_features(zero_volume_books, [])
    
    assert features is not None
    # Should handle zero volume without errors
    assert features.volume_concentration >= 0.0


def test_extract_features_calculates_entropy(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test that price entropy is calculated correctly."""
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    assert features.price_entropy >= 0.0
    # Entropy should be positive for multiple exchanges with different prices
    assert features.price_entropy > 0.0


def test_extract_features_with_volatility_history(
    feature_extractor: CrossExchangeFeatureExtractor,
    sample_order_books: dict[str, dict],
) -> None:
    """Test volatility features with historical data."""
    # Add varying price history to calculate volatility
    for i in range(50):
        feature_extractor.update("binance", 100.0 + np.random.randn(), 10.0, 1000.0 + i)
        feature_extractor.update("coinbase", 100.0 + np.random.randn() * 2, 8.0, 1000.0 + i)
    
    features = feature_extractor.extract_features(sample_order_books, [])
    
    assert features is not None
    assert features.cross_exchange_vol_ratio >= 1.0
    assert features.vol_dispersion >= 0.0
