"""Tests for GemScore delta explainability integration with FeatureStore."""

import time

import pytest

from src.core.feature_store import FeatureStore, FeatureMetadata, FeatureType, FeatureCategory
from src.core.scoring import compute_gem_score
from src.core.score_explainer import create_snapshot_from_result


def create_test_features(overrides: dict | None = None) -> dict[str, float]:
    """Create test feature set."""
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


class TestFeatureStoreSnapshots:
    """Test snapshot storage in FeatureStore."""
    
    def test_write_and_read_snapshot(self):
        """Test writing and reading snapshots."""
        store = FeatureStore(enable_validation=False)
        
        # Create snapshot
        features = create_test_features()
        score = compute_gem_score(features)
        snapshot = create_snapshot_from_result("TEST", score, features, timestamp=1000.0)
        
        # Write snapshot
        store.write_snapshot(snapshot)
        
        # Read snapshot
        retrieved = store.read_snapshot("TEST")
        
        assert retrieved is not None
        assert retrieved.token_symbol == "TEST"
        assert retrieved.score == snapshot.score
        assert retrieved.timestamp == snapshot.timestamp
    
    def test_read_snapshot_returns_latest(self):
        """Test that read_snapshot returns the latest snapshot."""
        store = FeatureStore(enable_validation=False)
        
        # Write multiple snapshots
        for i in range(3):
            features = create_test_features({"SentimentScore": 0.5 + i * 0.1})
            score = compute_gem_score(features)
            snapshot = create_snapshot_from_result("TEST", score, features, timestamp=1000.0 + i * 100)
            store.write_snapshot(snapshot)
        
        # Read latest
        latest = store.read_snapshot("TEST")
        
        assert latest is not None
        assert latest.timestamp == 1200.0  # Last one
    
    def test_read_snapshot_with_timestamp(self):
        """Test point-in-time snapshot retrieval."""
        store = FeatureStore(enable_validation=False)
        
        # Write snapshots at different times
        for i in range(3):
            features = create_test_features()
            score = compute_gem_score(features)
            snapshot = create_snapshot_from_result("TEST", score, features, timestamp=1000.0 + i * 100)
            store.write_snapshot(snapshot)
        
        # Read snapshot at specific time
        snapshot = store.read_snapshot("TEST", timestamp=1150.0)
        
        assert snapshot is not None
        assert snapshot.timestamp <= 1150.0
        assert snapshot.timestamp == 1100.0  # Should be second snapshot
    
    def test_read_snapshot_history(self):
        """Test reading snapshot history."""
        store = FeatureStore(enable_validation=False)
        
        # Write 5 snapshots
        for i in range(5):
            features = create_test_features()
            score = compute_gem_score(features)
            snapshot = create_snapshot_from_result("TEST", score, features, timestamp=1000.0 + i * 100)
            store.write_snapshot(snapshot)
        
        # Read history
        history = store.read_snapshot_history("TEST")
        
        assert len(history) == 5
        assert history[0].timestamp > history[-1].timestamp  # Sorted descending
    
    def test_read_snapshot_history_with_limit(self):
        """Test reading snapshot history with limit."""
        store = FeatureStore(enable_validation=False)
        
        # Write 5 snapshots
        for i in range(5):
            features = create_test_features()
            score = compute_gem_score(features)
            snapshot = create_snapshot_from_result("TEST", score, features, timestamp=1000.0 + i * 100)
            store.write_snapshot(snapshot)
        
        # Read with limit
        history = store.read_snapshot_history("TEST", limit=3)
        
        assert len(history) == 3
        assert history[0].timestamp == 1400.0  # Latest
    
    def test_read_snapshot_history_with_time_range(self):
        """Test reading snapshot history with time range."""
        store = FeatureStore(enable_validation=False)
        
        # Write 5 snapshots
        for i in range(5):
            features = create_test_features()
            score = compute_gem_score(features)
            snapshot = create_snapshot_from_result("TEST", score, features, timestamp=1000.0 + i * 100)
            store.write_snapshot(snapshot)
        
        # Read with time range
        history = store.read_snapshot_history(
            "TEST",
            start_time=1100.0,
            end_time=1300.0,
        )
        
        assert len(history) == 3  # 1100, 1200, 1300
        assert all(1100.0 <= s.timestamp <= 1300.0 for s in history)
    
    def test_compute_score_delta(self):
        """Test computing score delta."""
        store = FeatureStore(enable_validation=False)
        
        # Write two snapshots with different scores
        features_1 = create_test_features({"SentimentScore": 0.5})
        score_1 = compute_gem_score(features_1)
        snapshot_1 = create_snapshot_from_result("TEST", score_1, features_1, timestamp=1000.0)
        store.write_snapshot(snapshot_1)
        
        features_2 = create_test_features({"SentimentScore": 0.9})
        score_2 = compute_gem_score(features_2)
        snapshot_2 = create_snapshot_from_result("TEST", score_2, features_2, timestamp=2000.0)
        store.write_snapshot(snapshot_2)
        
        # Compute delta
        delta = store.compute_score_delta("TEST")
        
        assert delta is not None
        assert delta.token_symbol == "TEST"
        assert delta.current_score == score_2.score
        assert delta.previous_score == score_1.score
        assert delta.delta_score > 0  # Score increased
    
    def test_compute_score_delta_with_explicit_current(self):
        """Test computing delta with explicit current snapshot."""
        store = FeatureStore(enable_validation=False)
        
        # Write previous snapshot
        features_1 = create_test_features({"SentimentScore": 0.5})
        score_1 = compute_gem_score(features_1)
        snapshot_1 = create_snapshot_from_result("TEST", score_1, features_1, timestamp=1000.0)
        store.write_snapshot(snapshot_1)
        
        # Create current snapshot (not written yet)
        features_2 = create_test_features({"SentimentScore": 0.9})
        score_2 = compute_gem_score(features_2)
        snapshot_2 = create_snapshot_from_result("TEST", score_2, features_2, timestamp=2000.0)
        
        # Compute delta with explicit current
        delta = store.compute_score_delta("TEST", current_snapshot=snapshot_2)
        
        assert delta is not None
        assert delta.current_score == score_2.score
        assert delta.previous_score == score_1.score
    
    def test_compute_score_delta_insufficient_history(self):
        """Test that delta returns None with insufficient history."""
        store = FeatureStore(enable_validation=False)
        
        # Write only one snapshot
        features = create_test_features()
        score = compute_gem_score(features)
        snapshot = create_snapshot_from_result("TEST", score, features, timestamp=1000.0)
        store.write_snapshot(snapshot)
        
        # Try to compute delta
        delta = store.compute_score_delta("TEST")
        
        assert delta is None  # Not enough history
    
    def test_compute_score_delta_no_snapshots(self):
        """Test that delta returns None with no snapshots."""
        store = FeatureStore(enable_validation=False)
        
        delta = store.compute_score_delta("NONEXISTENT")
        
        assert delta is None
    
    def test_clear_old_snapshots(self):
        """Test clearing old snapshot data."""
        store = FeatureStore(enable_validation=False)
        
        # Write snapshots at different times
        current_time = time.time()
        
        # Old snapshot (should be cleared)
        features = create_test_features()
        score = compute_gem_score(features)
        snapshot_old = create_snapshot_from_result("TEST", score, features, timestamp=current_time - 7200)  # 2 hours ago
        store.write_snapshot(snapshot_old)
        
        # Recent snapshot (should be kept)
        snapshot_new = create_snapshot_from_result("TEST", score, features, timestamp=current_time - 1800)  # 30 min ago
        store.write_snapshot(snapshot_new)
        
        # Clear data older than 1 hour
        cleared = store.clear_old_data(max_age_seconds=3600)
        
        assert cleared == 1  # One snapshot cleared
        
        # Verify only recent snapshot remains
        history = store.read_snapshot_history("TEST")
        assert len(history) == 1
        assert abs(history[0].timestamp - (current_time - 1800)) < 1.0
    
    def test_get_stats_includes_snapshots(self):
        """Test that stats include snapshot counts."""
        store = FeatureStore(enable_validation=False)
        
        # Write snapshots for multiple tokens
        for token in ["TOKEN1", "TOKEN2"]:
            for i in range(3):
                features = create_test_features()
                score = compute_gem_score(features)
                snapshot = create_snapshot_from_result(token, score, features, timestamp=1000.0 + i * 100)
                store.write_snapshot(snapshot)
        
        # Get stats
        stats = store.get_stats()
        
        assert "total_snapshots" in stats
        assert stats["total_snapshots"] == 6  # 3 per token, 2 tokens


class TestEndToEndIntegration:
    """Test end-to-end integration with pipeline."""
    
    def test_multiple_scans_with_deltas(self):
        """Test tracking multiple scans and computing deltas."""
        store = FeatureStore(enable_validation=False)
        
        token = "ETH"
        
        # Simulate 5 scans over time
        scan_results = []
        for i in range(5):
            features = create_test_features({
                "SentimentScore": 0.5 + i * 0.05,
                "OnchainActivity": 0.7 - i * 0.02,
            })
            score = compute_gem_score(features)
            snapshot = create_snapshot_from_result(
                token, score, features, timestamp=1000.0 + i * 3600
            )
            store.write_snapshot(snapshot)
            scan_results.append((features, score, snapshot))
        
        # Verify we can get deltas between consecutive scans
        for i in range(1, 5):
            current_snapshot = scan_results[i][2]
            delta = store.compute_score_delta(token, current_snapshot)
            
            assert delta is not None
            assert delta.token_symbol == token
            assert delta.time_delta_hours == 1.0
            
            # Verify narrative generation works
            narrative = delta.get_narrative()
            assert token in narrative
            assert len(narrative) > 0
    
    def test_feature_importance_tracking(self):
        """Test tracking which features are most important over time."""
        store = FeatureStore(enable_validation=False)
        
        token = "BTC"
        
        # Scan 1: Low sentiment
        features_1 = create_test_features({"SentimentScore": 0.3, "AccumulationScore": 0.7})
        score_1 = compute_gem_score(features_1)
        snapshot_1 = create_snapshot_from_result(token, score_1, features_1, timestamp=1000.0)
        store.write_snapshot(snapshot_1)
        
        # Scan 2: High sentiment becomes most important
        features_2 = create_test_features({"SentimentScore": 0.9, "AccumulationScore": 0.7})
        score_2 = compute_gem_score(features_2)
        snapshot_2 = create_snapshot_from_result(token, score_2, features_2, timestamp=2000.0)
        store.write_snapshot(snapshot_2)
        
        # Compute delta
        delta = store.compute_score_delta(token)
        
        # SentimentScore should be top positive contributor
        assert len(delta.top_positive_contributors) > 0
        assert delta.top_positive_contributors[0].feature_name == "SentimentScore"
        
        # Verify the contribution change is correct
        sentiment_delta = delta.top_positive_contributors[0]
        assert sentiment_delta.delta_value > 0
        assert sentiment_delta.percent_change > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
