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
        onchain_metrics={"active_wallets": 450, "net_inflows": 20000.0, "unlock_pressure": 0.1},
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
