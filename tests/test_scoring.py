"""Tests for scoring utilities."""

from __future__ import annotations

from src.core.scoring import GemScoreResult, compute_gem_score, should_flag_asset


def build_base_features() -> dict[str, float]:
    return {
        "SentimentScore": 0.7,
        "AccumulationScore": 0.8,
        "OnchainActivity": 0.75,
        "LiquidityDepth": 0.65,
        "TokenomicsRisk": 0.9,
        "ContractSafety": 0.85,
        "NarrativeMomentum": 0.7,
        "CommunityGrowth": 0.6,
        "Recency": 0.9,
        "DataCompleteness": 0.85,
    }


def test_compute_gem_score_returns_expected_range() -> None:
    result = compute_gem_score(build_base_features())
    assert isinstance(result, GemScoreResult)
    assert 0 <= result.score <= 100
    assert 0 <= result.confidence <= 100


def test_should_flag_asset_requires_safety_and_signal_confirmation() -> None:
    features = build_base_features()
    result = compute_gem_score(features)
    flag, debug = should_flag_asset(result, features)
    assert flag is True
    assert debug["signals"] >= 3


def test_should_flag_asset_blocks_low_safety() -> None:
    features = build_base_features()
    features["ContractSafety"] = 0.2
    result = compute_gem_score(features)
    flag, _ = should_flag_asset(result, features)
    assert flag is False
