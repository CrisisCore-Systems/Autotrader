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


def test_compute_gem_score_handles_missing_features() -> None:
    """Test that missing features are treated as 0."""
    minimal_features = {
        "SentimentScore": 0.5,
        "Recency": 0.9,
        "DataCompleteness": 0.85,
    }
    result = compute_gem_score(minimal_features)
    assert 0 <= result.score <= 100
    # Score should be relatively low due to missing features
    assert result.score < 50


def test_compute_gem_score_clamps_out_of_range_values() -> None:
    """Test that values outside [0, 1] are clamped."""
    features = build_base_features()
    features["SentimentScore"] = 1.5  # > 1
    features["AccumulationScore"] = -0.5  # < 0
    result = compute_gem_score(features)
    # Should not crash and should produce valid score
    assert 0 <= result.score <= 100


def test_compute_confidence_returns_expected_range() -> None:
    """Test that confidence is calculated correctly."""
    from src.core.scoring import compute_confidence
    
    features = {
        "Recency": 0.9,
        "DataCompleteness": 0.8,
    }
    confidence = compute_confidence(features)
    assert 0 <= confidence <= 100
    # With high recency and completeness, confidence should be high
    assert confidence > 75


def test_should_flag_asset_requires_sufficient_signals() -> None:
    """Test that at least 3 positive signals are required."""
    features = build_base_features()
    # Set only 2 signals high
    features["AccumulationScore"] = 0.7
    features["NarrativeMomentum"] = 0.7
    features["OnchainActivity"] = 0.3  # Low
    result = compute_gem_score(features)
    flag, debug = should_flag_asset(result, features)
    assert debug["signals"] == 2
    assert flag is False


def test_should_flag_asset_debug_info_complete() -> None:
    """Test that debug info contains all expected fields."""
    features = build_base_features()
    result = compute_gem_score(features)
    flag, debug = should_flag_asset(result, features)
    
    assert "safety_pass" in debug
    assert "signals" in debug
    assert "score" in debug
    assert "confidence" in debug
    assert isinstance(debug["safety_pass"], bool)
    assert isinstance(debug["signals"], int)


def test_gem_score_contributions_sum_to_score() -> None:
    """Test that feature contributions sum to approximately the score."""
    features = build_base_features()
    result = compute_gem_score(features)
    
    total_contribution = sum(result.contributions.values())
    # Should be close to score/100 (since score is 0-100 scale)
    assert abs(total_contribution * 100 - result.score) < 0.1


def test_gem_score_with_all_zeros() -> None:
    """Test gem score with all zero features."""
    features = {k: 0.0 for k in build_base_features().keys()}
    result = compute_gem_score(features)
    assert result.score == 0.0
    assert all(v == 0.0 for v in result.contributions.values())


def test_gem_score_with_all_ones() -> None:
    """Test gem score with all maximum features."""
    features = {k: 1.0 for k in build_base_features().keys()}
    result = compute_gem_score(features)
    assert abs(result.score - 100.0) < 0.01  # Allow small floating point error
