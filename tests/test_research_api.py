"""Tests for Research workspace API endpoints."""

from __future__ import annotations

import time
from datetime import datetime

from src.core.freshness import FreshnessLevel, FreshnessTracker, get_freshness_tracker


class TestFreshnessTracker:
    """Test the freshness tracking system."""
    
    def test_record_update(self):
        """Test recording data updates."""
        tracker = FreshnessTracker()
        tracker.record_update("coingecko")
        
        freshness = tracker.get_freshness("coingecko")
        assert freshness.source_name == "coingecko"
        assert freshness.freshness_level == FreshnessLevel.FRESH
        assert freshness.is_free is True
    
    def test_freshness_classification(self):
        """Test freshness level classification."""
        tracker = FreshnessTracker()
        
        # Fresh data (< 5 minutes)
        tracker.record_update("source1", datetime.utcnow())
        freshness = tracker.get_freshness("source1")
        assert freshness.freshness_level == FreshnessLevel.FRESH
        
        # Recent data (1 hour ago)
        from datetime import timedelta
        tracker.record_update("source2", datetime.utcnow() - timedelta(minutes=30))
        freshness = tracker.get_freshness("source2")
        assert freshness.freshness_level == FreshnessLevel.RECENT
        
        # Stale data (12 hours ago)
        tracker.record_update("source3", datetime.utcnow() - timedelta(hours=12))
        freshness = tracker.get_freshness("source3")
        assert freshness.freshness_level == FreshnessLevel.STALE
        
        # Outdated data (2 days ago)
        tracker.record_update("source4", datetime.utcnow() - timedelta(days=2))
        freshness = tracker.get_freshness("source4")
        assert freshness.freshness_level == FreshnessLevel.OUTDATED
    
    def test_freshness_serialization(self):
        """Test freshness data serialization."""
        tracker = FreshnessTracker()
        tracker.record_update("coingecko")
        
        freshness = tracker.get_freshness("coingecko", is_free=True, update_frequency_seconds=300)
        data = freshness.to_dict()
        
        assert "source_name" in data
        assert "last_updated" in data
        assert "data_age_seconds" in data
        assert "freshness_level" in data
        assert "is_free" in data
        assert data["is_free"] is True
        assert data["freshness_level"] == "fresh"
    
    def test_get_all_freshness(self):
        """Test getting freshness for all sources."""
        tracker = FreshnessTracker()
        tracker.record_update("coingecko")
        tracker.record_update("dexscreener")
        tracker.record_update("blockscout")
        
        all_freshness = tracker.get_all_freshness()
        assert len(all_freshness) == 3
        assert "coingecko" in all_freshness
        assert "dexscreener" in all_freshness
        assert "blockscout" in all_freshness
    
    def test_global_tracker(self):
        """Test global freshness tracker."""
        tracker = get_freshness_tracker()
        assert tracker is not None
        assert isinstance(tracker, FreshnessTracker)
        
        # Should return same instance
        tracker2 = get_freshness_tracker()
        assert tracker is tracker2


class TestAPIFilters:
    """Test API endpoint filters (without full FastAPI test client)."""
    
    def test_filter_logic_score(self):
        """Test score filtering logic."""
        tokens = [
            {"symbol": "A", "final_score": 0.8, "confidence": 0.9, "liquidity_usd": 1000000, "flagged": False},
            {"symbol": "B", "final_score": 0.5, "confidence": 0.7, "liquidity_usd": 500000, "flagged": False},
            {"symbol": "C", "final_score": 0.3, "confidence": 0.6, "liquidity_usd": 100000, "flagged": True},
        ]
        
        # Filter by min score
        min_score = 0.6
        filtered = [t for t in tokens if t["final_score"] >= min_score]
        assert len(filtered) == 1
        assert filtered[0]["symbol"] == "A"
    
    def test_filter_logic_confidence(self):
        """Test confidence filtering logic."""
        tokens = [
            {"symbol": "A", "final_score": 0.8, "confidence": 0.9, "liquidity_usd": 1000000, "flagged": False},
            {"symbol": "B", "final_score": 0.5, "confidence": 0.7, "liquidity_usd": 500000, "flagged": False},
            {"symbol": "C", "final_score": 0.3, "confidence": 0.6, "liquidity_usd": 100000, "flagged": True},
        ]
        
        # Filter by min confidence
        min_confidence = 0.8
        filtered = [t for t in tokens if t["confidence"] >= min_confidence]
        assert len(filtered) == 1
        assert filtered[0]["symbol"] == "A"
    
    def test_filter_logic_liquidity(self):
        """Test liquidity filtering logic."""
        tokens = [
            {"symbol": "A", "final_score": 0.8, "confidence": 0.9, "liquidity_usd": 1000000, "flagged": False},
            {"symbol": "B", "final_score": 0.5, "confidence": 0.7, "liquidity_usd": 500000, "flagged": False},
            {"symbol": "C", "final_score": 0.3, "confidence": 0.6, "liquidity_usd": 100000, "flagged": True},
        ]
        
        # Filter by min liquidity
        min_liquidity = 400000
        filtered = [t for t in tokens if t["liquidity_usd"] >= min_liquidity]
        assert len(filtered) == 2
        assert filtered[0]["symbol"] == "A"
        assert filtered[1]["symbol"] == "B"
    
    def test_filter_logic_safety(self):
        """Test safety filtering logic."""
        tokens = [
            {"symbol": "A", "final_score": 0.8, "confidence": 0.9, "liquidity_usd": 1000000, "flagged": False},
            {"symbol": "B", "final_score": 0.5, "confidence": 0.7, "liquidity_usd": 500000, "flagged": False},
            {"symbol": "C", "final_score": 0.3, "confidence": 0.6, "liquidity_usd": 100000, "flagged": True},
        ]
        
        # Filter for safe tokens
        filtered_safe = [t for t in tokens if not t["flagged"]]
        assert len(filtered_safe) == 2
        
        # Filter for flagged tokens
        filtered_flagged = [t for t in tokens if t["flagged"]]
        assert len(filtered_flagged) == 1
        assert filtered_flagged[0]["symbol"] == "C"
    
    def test_filter_logic_time_window(self):
        """Test time window filtering logic."""
        now = datetime.utcnow()
        from datetime import timedelta
        
        tokens = [
            {"symbol": "A", "updated_at": now.isoformat() + "Z"},
            {"symbol": "B", "updated_at": (now - timedelta(hours=2)).isoformat() + "Z"},
            {"symbol": "C", "updated_at": (now - timedelta(hours=25)).isoformat() + "Z"},
        ]
        
        # Filter by time window (24 hours)
        time_window_hours = 24
        filtered = []
        for t in tokens:
            updated_at = datetime.fromisoformat(t["updated_at"].replace('Z', '+00:00'))
            age_hours = (now - updated_at.replace(tzinfo=None)).total_seconds() / 3600
            if age_hours <= time_window_hours:
                filtered.append(t)
        
        assert len(filtered) == 2
        assert filtered[0]["symbol"] == "A"
        assert filtered[1]["symbol"] == "B"


class TestProvenanceIntegration:
    """Test provenance integration."""
    
    def test_provenance_data_structure(self):
        """Test provenance data structure."""
        provenance = {
            "artifact_id": "token_LINK_123456",
            "data_sources": ["coingecko", "dexscreener", "blockscout"],
            "pipeline_version": "2.0.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "clickable_links": {
                "coingecko": "https://www.coingecko.com/en/coins/chainlink",
                "dexscreener": "https://dexscreener.com/ethereum/0x514910771AF9Ca656af840dff83E8264EcF986CA",
                "blockscout": "https://eth.blockscout.com/token/0x514910771AF9Ca656af840dff83E8264EcF986CA",
            }
        }
        
        assert "artifact_id" in provenance
        assert "data_sources" in provenance
        assert len(provenance["data_sources"]) == 3
        assert "clickable_links" in provenance
        assert len(provenance["clickable_links"]) == 3
    
    def test_evidence_panel_structure(self):
        """Test evidence panel data structure."""
        panel = {
            "title": "Price & Volume Analysis",
            "confidence": 0.95,
            "freshness": "fresh",
            "source": "coingecko",
            "is_free": True,
            "data": {
                "price": 15.42,
                "volume_24h": 250000000,
            }
        }
        
        assert "title" in panel
        assert "confidence" in panel
        assert "freshness" in panel
        assert "source" in panel
        assert "is_free" in panel
        assert panel["is_free"] is True
        assert "data" in panel


if __name__ == "__main__":
    # Run basic tests
    print("Running freshness tracker tests...")
    test = TestFreshnessTracker()
    test.test_record_update()
    test.test_freshness_classification()
    test.test_freshness_serialization()
    test.test_get_all_freshness()
    test.test_global_tracker()
    print("✓ All freshness tracker tests passed")
    
    print("\nRunning API filter tests...")
    test2 = TestAPIFilters()
    test2.test_filter_logic_score()
    test2.test_filter_logic_confidence()
    test2.test_filter_logic_liquidity()
    test2.test_filter_logic_safety()
    test2.test_filter_logic_time_window()
    print("✓ All API filter tests passed")
    
    print("\nRunning provenance integration tests...")
    test3 = TestProvenanceIntegration()
    test3.test_provenance_data_structure()
    test3.test_evidence_panel_structure()
    print("✓ All provenance integration tests passed")
    
    print("\n✅ All tests passed!")
