"""Tests for GemScore delta explainability."""

import time
from typing import Dict

import pytest

from src.core.scoring import GemScoreResult, compute_gem_score
from src.core.score_explainer import (
    ScoreExplainer,
    GemScoreSnapshot,
    ScoreDelta,
    FeatureDelta,
    create_snapshot_from_result,
)


def create_test_features(overrides: Dict[str, float] | None = None) -> Dict[str, float]:
    """Create test feature set with optional overrides."""
    features = {
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
    
    if overrides:
        features.update(overrides)
    
    return features


class TestScoreExplainer:
    """Test ScoreExplainer functionality."""
    
    def test_create_snapshot(self):
        """Test snapshot creation."""
        features = create_test_features()
        gem_score = compute_gem_score(features)
        
        explainer = ScoreExplainer()
        snapshot = explainer.create_snapshot(
            token_symbol="TEST",
            gem_score_result=gem_score,
            features=features,
            timestamp=1000.0,
        )
        
        assert snapshot.token_symbol == "TEST"
        assert snapshot.timestamp == 1000.0
        assert snapshot.score == gem_score.score
        assert snapshot.confidence == gem_score.confidence
        assert snapshot.features == features
        assert snapshot.contributions == gem_score.contributions
    
    def test_create_snapshot_from_result_helper(self):
        """Test convenience helper for snapshot creation."""
        features = create_test_features()
        gem_score = compute_gem_score(features)
        
        snapshot = create_snapshot_from_result(
            token_symbol="TEST",
            gem_score_result=gem_score,
            features=features,
        )
        
        assert snapshot.token_symbol == "TEST"
        assert snapshot.score == gem_score.score
        assert abs(snapshot.timestamp - time.time()) < 1.0  # Should be close to now
    
    def test_compute_delta_positive_change(self):
        """Test delta computation with positive score change."""
        # Create previous snapshot with lower scores
        prev_features = create_test_features({
            "SentimentScore": 0.5,
            "AccumulationScore": 0.6,
        })
        prev_score = compute_gem_score(prev_features)
        
        # Create current snapshot with higher scores
        curr_features = create_test_features({
            "SentimentScore": 0.8,
            "AccumulationScore": 0.9,
        })
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        
        assert delta.token_symbol == "TEST"
        assert delta.delta_score > 0  # Score increased
        assert delta.percent_change > 0
        assert delta.time_delta_hours == (2000.0 - 1000.0) / 3600.0
        
        # Check that positive contributors include SentimentScore and AccumulationScore
        positive_names = [fd.feature_name for fd in delta.top_positive_contributors]
        assert "SentimentScore" in positive_names
        assert "AccumulationScore" in positive_names
    
    def test_compute_delta_negative_change(self):
        """Test delta computation with negative score change."""
        # Create previous snapshot with higher scores
        prev_features = create_test_features({
            "SentimentScore": 0.9,
            "LiquidityDepth": 0.8,
        })
        prev_score = compute_gem_score(prev_features)
        
        # Create current snapshot with lower scores
        curr_features = create_test_features({
            "SentimentScore": 0.4,
            "LiquidityDepth": 0.3,
        })
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        
        assert delta.delta_score < 0  # Score decreased
        assert delta.percent_change < 0
        
        # Check that negative contributors include SentimentScore and LiquidityDepth
        negative_names = [fd.feature_name for fd in delta.top_negative_contributors]
        assert "SentimentScore" in negative_names
        assert "LiquidityDepth" in negative_names
    
    def test_compute_delta_mixed_changes(self):
        """Test delta with both positive and negative feature changes."""
        # Some features increase, some decrease
        prev_features = create_test_features({
            "SentimentScore": 0.5,
            "LiquidityDepth": 0.8,
            "OnchainActivity": 0.7,
        })
        prev_score = compute_gem_score(prev_features)
        
        curr_features = create_test_features({
            "SentimentScore": 0.9,  # Increased
            "LiquidityDepth": 0.3,  # Decreased
            "OnchainActivity": 0.7,  # Unchanged
        })
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        
        # Should have both positive and negative contributors
        assert len(delta.top_positive_contributors) > 0
        assert len(delta.top_negative_contributors) > 0
        
        # SentimentScore should be top positive contributor
        assert delta.top_positive_contributors[0].feature_name == "SentimentScore"
        
        # LiquidityDepth should be in negative contributors
        negative_names = [fd.feature_name for fd in delta.top_negative_contributors]
        assert "LiquidityDepth" in negative_names
    
    def test_delta_summary(self):
        """Test delta summary generation."""
        prev_features = create_test_features({"SentimentScore": 0.5})
        prev_score = compute_gem_score(prev_features)
        
        curr_features = create_test_features({"SentimentScore": 0.9})
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        summary = delta.get_summary(top_n=3)
        
        assert "token" in summary
        assert summary["token"] == "TEST"
        assert "score_change" in summary
        assert "time_delta_hours" in summary
        assert "top_positive_contributors" in summary
        assert "top_negative_contributors" in summary
        
        # Should have at most 3 contributors each
        assert len(summary["top_positive_contributors"]) <= 3
        assert len(summary["top_negative_contributors"]) <= 3
    
    def test_delta_narrative(self):
        """Test narrative generation."""
        prev_features = create_test_features({"SentimentScore": 0.5})
        prev_score = compute_gem_score(prev_features)
        
        curr_features = create_test_features({"SentimentScore": 0.9})
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        narrative = delta.get_narrative()
        
        assert isinstance(narrative, str)
        assert len(narrative) > 0
        assert "TEST" in narrative
        assert "GemScore" in narrative
        # Should mention direction of change
        assert "increased" in narrative or "decreased" in narrative
    
    def test_explain_score_change(self):
        """Test detailed score change explanation."""
        prev_features = create_test_features({"SentimentScore": 0.5})
        prev_score = compute_gem_score(prev_features)
        
        curr_features = create_test_features({"SentimentScore": 0.9})
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        explanation = explainer.explain_score_change(delta, threshold=0.01)
        
        assert "overview" in explanation
        assert "significant_changes" in explanation
        assert "narrative" in explanation
        
        assert explanation["overview"]["direction"] in ["increase", "decrease"]
        assert isinstance(explanation["significant_changes"], list)
    
    def test_find_most_impactful_features(self):
        """Test finding most impactful features."""
        prev_features = create_test_features({
            "SentimentScore": 0.3,
            "AccumulationScore": 0.4,
            "LiquidityDepth": 0.9,
        })
        prev_score = compute_gem_score(prev_features)
        
        curr_features = create_test_features({
            "SentimentScore": 0.9,  # Large increase
            "AccumulationScore": 0.8,  # Medium increase
            "LiquidityDepth": 0.2,  # Large decrease
        })
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        positive, negative = explainer.find_most_impactful_features(delta, top_n=3)
        
        assert isinstance(positive, list)
        assert isinstance(negative, list)
        assert len(positive) <= 3
        assert len(negative) <= 3
        
        # Should include the features we changed
        assert "SentimentScore" in positive or "AccumulationScore" in positive
        assert "LiquidityDepth" in negative
    
    def test_token_symbol_mismatch_error(self):
        """Test that mismatched token symbols raise an error."""
        features = create_test_features()
        score = compute_gem_score(features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TOKEN_A", score, features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TOKEN_B", score, features, timestamp=2000.0
        )
        
        with pytest.raises(ValueError, match="Token symbol mismatch"):
            explainer.compute_delta(prev_snapshot, curr_snapshot)
    
    def test_zero_division_handling(self):
        """Test that zero values are handled correctly in percent change."""
        # Feature going from 0 to positive
        prev_features = create_test_features({"SentimentScore": 0.0})
        prev_score = compute_gem_score(prev_features)
        
        curr_features = create_test_features({"SentimentScore": 0.5})
        curr_score = compute_gem_score(curr_features)
        
        explainer = ScoreExplainer()
        prev_snapshot = explainer.create_snapshot(
            "TEST", prev_score, prev_features, timestamp=1000.0
        )
        curr_snapshot = explainer.create_snapshot(
            "TEST", curr_score, curr_features, timestamp=2000.0
        )
        
        delta = explainer.compute_delta(prev_snapshot, curr_snapshot)
        
        # Should not raise division by zero
        sentiment_delta = next(
            fd for fd in delta.feature_deltas
            if fd.feature_name == "SentimentScore"
        )
        
        # Percent change should be 100% (from 0 to positive)
        assert sentiment_delta.percent_change == 100.0


class TestFeatureDelta:
    """Test FeatureDelta data class."""
    
    def test_feature_delta_creation(self):
        """Test FeatureDelta instantiation."""
        fd = FeatureDelta(
            feature_name="TestFeature",
            previous_value=0.5,
            current_value=0.7,
            delta_value=0.2,
            previous_contribution=0.05,
            current_contribution=0.07,
            delta_contribution=0.02,
            percent_change=40.0,
            weight=0.1,
        )
        
        assert fd.feature_name == "TestFeature"
        assert fd.delta_value == 0.2
        assert fd.delta_contribution == 0.02
        assert fd.percent_change == 40.0


class TestGemScoreSnapshot:
    """Test GemScoreSnapshot data class."""
    
    def test_snapshot_creation(self):
        """Test snapshot instantiation."""
        features = create_test_features()
        contributions = {"TestFeature": 0.05}
        
        snapshot = GemScoreSnapshot(
            token_symbol="TEST",
            timestamp=1000.0,
            score=75.0,
            confidence=85.0,
            features=features,
            contributions=contributions,
            metadata={"test": "value"},
        )
        
        assert snapshot.token_symbol == "TEST"
        assert snapshot.timestamp == 1000.0
        assert snapshot.score == 75.0
        assert snapshot.confidence == 85.0
        assert snapshot.features == features
        assert snapshot.contributions == contributions
        assert snapshot.metadata == {"test": "value"}


class TestIntegrationWithScoring:
    """Test integration with actual scoring module."""
    
    def test_end_to_end_workflow(self):
        """Test complete workflow from scoring to delta explanation."""
        # Scan 1: Initial state
        features_t1 = create_test_features()
        score_t1 = compute_gem_score(features_t1)
        
        # Scan 2: Some changes after 1 hour
        features_t2 = create_test_features({
            "SentimentScore": 0.9,
            "OnchainActivity": 0.5,
        })
        score_t2 = compute_gem_score(features_t2)
        
        # Create snapshots
        explainer = ScoreExplainer()
        snapshot_t1 = create_snapshot_from_result("BTC", score_t1, features_t1, timestamp=1000.0)
        snapshot_t2 = create_snapshot_from_result("BTC", score_t2, features_t2, timestamp=4600.0)
        
        # Compute delta
        delta = explainer.compute_delta(snapshot_t1, snapshot_t2)
        
        # Verify results
        assert delta.token_symbol == "BTC"
        assert delta.previous_score == score_t1.score
        assert delta.current_score == score_t2.score
        assert delta.time_delta_hours == 1.0
        
        # Get summary and narrative
        summary = delta.get_summary()
        narrative = delta.get_narrative()
        
        assert summary["token"] == "BTC"
        assert "BTC" in narrative
        assert len(summary["top_positive_contributors"]) > 0
        
        # Verify explanation
        explanation = explainer.explain_score_change(delta)
        assert explanation["overview"]["direction"] in ["increase", "decrease"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
