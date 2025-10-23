"""Unit tests for feature engineering helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import pandas as pd
import pytest

from src.core.features import (
    MarketSnapshot,
    build_feature_vector,
    compute_time_series_features,
    merge_feature_vectors,
    normalize_feature,
)


def test_compute_time_series_features_handles_sparse_series() -> None:
    now = datetime.now(timezone.utc)
    prices = pd.Series(
        [1.0, 1.05, 1.02, 1.08],
        index=[now - timedelta(hours=i * 6) for i in range(4)][::-1],
    )

    metrics = compute_time_series_features(prices)

    assert set(metrics) == {"rsi", "macd", "volatility"}
    assert 0.0 <= metrics["rsi"] <= 1.0


def test_compute_time_series_features_returns_defaults_for_empty_series() -> None:
    metrics = compute_time_series_features(pd.Series(dtype=float))
    assert metrics == {"rsi": 0.5, "macd": 0.0, "volatility": 0.0}


def test_normalize_feature_requires_positive_denominator() -> None:
    with pytest.raises(ValueError):
        normalize_feature(1.0, max_value=0)


def test_build_feature_vector_merges_sources() -> None:
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=datetime.now(timezone.utc),
        price=1.0,
        volume_24h=1000.0,
        liquidity_usd=150000.0,
        holders=1200,
        onchain_metrics={
            "active_wallets": 450,
            "net_inflows": 20000.0,
            "unlock_pressure": 0.1,
            "upcoming_unlock_risk": 0.0,
        },
        narratives=["growth"],
    )
    vector = build_feature_vector(
        snapshot,
        price_features={"rsi": 0.6, "macd": 0.02, "volatility": 0.15},
        narrative_embedding_score=0.7,
        contract_metrics={"score": 0.8},
        narrative_momentum=0.65,
    )

    assert vector["SentimentScore"] == 0.7
    assert 0 <= vector["LiquidityDepth"] <= 1
    assert vector["ContractSafety"] == 0.8
    assert "UpcomingUnlockRisk" in vector


def test_merge_feature_vectors_average_values() -> None:
    vectors = [
        {"SentimentScore": 0.4, "LiquidityDepth": 0.5},
        {"SentimentScore": 0.6, "LiquidityDepth": 0.3},
    ]

    merged = merge_feature_vectors(vectors)
    assert merged == {"SentimentScore": 0.5, "LiquidityDepth": 0.4}


def test_merge_feature_vectors_handles_empty_list() -> None:
    """Test that empty list returns empty dict."""
    merged = merge_feature_vectors([])
    assert merged == {}


def test_merge_feature_vectors_handles_single_vector() -> None:
    """Test that single vector is returned as-is."""
    vectors = [{"SentimentScore": 0.5, "LiquidityDepth": 0.3}]
    merged = merge_feature_vectors(vectors)
    assert merged == {"SentimentScore": 0.5, "LiquidityDepth": 0.3}


def test_merge_feature_vectors_handles_missing_keys() -> None:
    """Test that vectors with different keys are merged correctly."""
    vectors = [
        {"SentimentScore": 0.4, "LiquidityDepth": 0.5},
        {"SentimentScore": 0.6, "NewFeature": 0.8},
    ]
    merged = merge_feature_vectors(vectors)
    # LiquidityDepth appears in 1 vector, NewFeature in 1 vector
    assert merged["SentimentScore"] == 0.5
    assert merged["LiquidityDepth"] == 0.25  # (0.5 + 0.0) / 2
    assert merged["NewFeature"] == 0.4  # (0.0 + 0.8) / 2


def test_normalize_feature_handles_none() -> None:
    """Test that None returns default value."""
    result = normalize_feature(None, default=0.5, max_value=100)
    assert result == 0.5


def test_normalize_feature_handles_inf() -> None:
    """Test that infinity returns default value."""
    result = normalize_feature(float("inf"), default=0.5, max_value=100)
    assert result == 0.5


def test_normalize_feature_handles_nan() -> None:
    """Test that NaN returns default value."""
    result = normalize_feature(float("nan"), default=0.5, max_value=100)
    assert result == 0.5


def test_normalize_feature_clamps_to_range() -> None:
    """Test that values are clamped to [0, 1]."""
    # Value > max_value should be clamped to 1
    result = normalize_feature(200.0, max_value=100.0)
    assert result == 1.0
    
    # Negative values should be clamped to 0
    result = normalize_feature(-50.0, max_value=100.0)
    assert result == 0.0


def test_build_feature_vector_handles_missing_onchain_metrics() -> None:
    """Test that missing onchain metrics are handled gracefully."""
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=datetime.now(timezone.utc),
        price=1.0,
        volume_24h=1000.0,
        liquidity_usd=150000.0,
        holders=1200,
        onchain_metrics={},  # Empty metrics
        narratives=["growth"],
    )
    vector = build_feature_vector(
        snapshot,
        price_features={"rsi": 0.6, "macd": 0.02, "volatility": 0.15},
        narrative_embedding_score=0.7,
        contract_metrics={"score": 0.8},
        narrative_momentum=0.65,
    )
    
    # Should not crash and should use defaults
    assert "OnchainActivity" in vector
    assert "AccumulationScore" in vector
    assert vector["OnchainActivity"] == 0.0
    assert vector["AccumulationScore"] == 0.0


def test_build_feature_vector_applies_unlock_risk_penalty() -> None:
    """Test that high upcoming unlock risk reduces tokenomics score."""
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=datetime.now(timezone.utc),
        price=1.0,
        volume_24h=1000.0,
        liquidity_usd=150000.0,
        holders=1200,
        onchain_metrics={
            "unlock_pressure": 0.1,
            "upcoming_unlock_risk": 0.6,  # High unlock risk
        },
        narratives=["growth"],
    )
    vector = build_feature_vector(
        snapshot,
        price_features={"rsi": 0.6, "macd": 0.02, "volatility": 0.15},
        narrative_embedding_score=0.7,
        contract_metrics={"score": 0.8},
        narrative_momentum=0.65,
    )
    
    # TokenomicsRisk should be capped at 0.4 due to high unlock risk
    assert vector["TokenomicsRisk"] <= 0.4


def test_compute_time_series_features_with_single_price() -> None:
    """Test that a single price point returns defaults."""
    prices = pd.Series([1.0], index=[datetime.now(timezone.utc)])
    metrics = compute_time_series_features(prices)
    # Single point can't compute meaningful stats
    assert 0.0 <= metrics["rsi"] <= 1.0
    assert metrics["volatility"] == 0.0


def test_market_snapshot_price_usd_alias() -> None:
    """Test that price_usd property works correctly."""
    snapshot = MarketSnapshot(
        symbol="TEST",
        timestamp=datetime.now(timezone.utc),
        price=123.45,
        volume_24h=1000.0,
        liquidity_usd=150000.0,
        holders=1200,
        onchain_metrics={},
        narratives=[],
    )
    assert snapshot.price_usd == snapshot.price
    assert snapshot.price_usd == 123.45
