"""
End-to-End Workflow Tests

Tests complete workflows from data ingestion through analysis to output.
Validates the full pipeline integration and data flow.

Run with: pytest tests/test_e2e_workflows.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ===== Complete Token Scanning Workflow =====

class TestCompleteTokenScan:
    """Test end-to-end token scanning workflow"""

    @pytest.fixture
    def mock_all_services(self):
        """Mock all external services for E2E test"""
        with patch("src.core.pipeline.EtherscanClient") as mock_etherscan, \
             patch("src.core.pipeline.DexScreenerClient") as mock_dex, \
             patch("src.core.sentiment.SentimentAnalyzer") as mock_sentiment, \
             patch("src.core.safety.SafetyAnalyzer") as mock_safety:

            # Mock Etherscan
            etherscan_inst = Mock()
            etherscan_inst.get_token_info.return_value = {
                "name": "Test Token",
                "symbol": "TEST",
                "total_supply": "1000000"
            }
            mock_etherscan.return_value = etherscan_inst

            # Mock DexScreener
            dex_inst = Mock()
            dex_inst.get_pair_data.return_value = {
                "liquidity": 100000,
                "volume_24h": 50000,
                "price_usd": 1.5
            }
            mock_dex.return_value = dex_inst

            # Mock Sentiment
            sentiment_inst = Mock()
            sentiment_inst.analyze.return_value = {
                "score": 0.75,
                "label": "positive"
            }
            mock_sentiment.return_value = sentiment_inst

            # Mock Safety
            safety_inst = Mock()
            safety_inst.analyze.return_value = {
                "safety_score": 85.5,
                "risks": []
            }
            mock_safety.return_value = safety_inst

            yield {
                "etherscan": mock_etherscan,
                "dex": mock_dex,
                "sentiment": mock_sentiment,
                "safety": mock_safety
            }

    def test_full_scan_workflow(self, mock_all_services):
        """Test complete token scanning from start to finish"""
        from src.core.pipeline import TokenScanner

        scanner = TokenScanner()
        result = scanner.scan(chain="ethereum", min_liquidity=10000, limit=10)

        assert "tokens" in result
        assert "total_scanned" in result

    def test_scan_with_filtering(self, mock_all_services):
        """Test scan with quality filters applied"""
        from src.core.pipeline import TokenScanner

        scanner = TokenScanner()
        result = scanner.scan(
            chain="ethereum",
            min_liquidity=50000,
            min_holders=100,
            min_safety_score=70
        )

        # All returned tokens should meet criteria
        for token in result.get("tokens", []):
            assert token.get("liquidity_usd", 0) >= 50000

    def test_scan_error_recovery(self, mock_all_services):
        """Test scan continues despite individual token errors"""
        from src.core.pipeline import TokenScanner

        # Make one token fail
        mock_all_services["etherscan"].return_value.get_token_info.side_effect = [
            {"name": "Token1", "symbol": "TK1"},
            Exception("API Error"),
            {"name": "Token3", "symbol": "TK3"}
        ]

        scanner = TokenScanner()
        result = scanner.scan(chain="ethereum", limit=3)

        # Should still return successful tokens
        assert len(result.get("tokens", [])) >= 1

    def test_scan_artifact_generation(self, mock_all_services):
        """Test artifact generation from scan results"""
        from src.core.pipeline import TokenScanner

        scanner = TokenScanner()
        result = scanner.scan(chain="ethereum", limit=5, generate_artifact=True)

        assert "artifact_path" in result or "report" in result


# ===== Feature Extraction Pipeline =====

class TestFeatureExtractionPipeline:
    """Test feature extraction end-to-end"""

    def test_extract_all_features(self):
        """Test extracting all feature categories"""
        from src.core.pipeline import extract_features

        token_data = {
            "address": "0x123",
            "price": 1.5,
            "volume_24h": 100000,
            "liquidity": 500000,
            "holders": 1000,
            "creation_time": datetime.now() - timedelta(days=30)
        }

        features = extract_features(token_data)

        # Should have features from multiple categories
        assert len(features) > 5
        assert any("momentum" in k.lower() for k in features.keys())

    def test_feature_pipeline_with_missing_data(self):
        """Test feature extraction handles missing data"""
        from src.core.pipeline import extract_features

        incomplete_data = {
            "address": "0x123",
            "price": 1.5
            # Missing other fields
        }

        features = extract_features(incomplete_data)

        # Should still return features with defaults
        assert isinstance(features, dict)

    def test_feature_storage(self):
        """Test storing features to feature store"""
        from src.core.pipeline import extract_and_store_features
        from src.services.feature_store import FeatureStore

        with patch.object(FeatureStore, "store_features") as mock_store:
            token_data = {"address": "0x123", "price": 1.5}
            extract_and_store_features(token_data)

            mock_store.assert_called_once()

    def test_batch_feature_extraction(self):
        """Test extracting features for multiple tokens"""
        from src.core.pipeline import batch_extract_features

        tokens = [
            {"address": "0x123", "price": 1.5},
            {"address": "0x456", "price": 2.0},
            {"address": "0x789", "price": 0.5}
        ]

        results = batch_extract_features(tokens)

        assert len(results) == 3
        assert all("features" in r for r in results)


# ===== Scoring and Ranking Workflow =====

class TestScoringWorkflow:
    """Test scoring and ranking pipeline"""

    def test_calculate_composite_score(self):
        """Test calculating composite score from features"""
        from src.core.scoring import calculate_composite_score

        features = {
            "momentum_score": 0.8,
            "liquidity_score": 0.7,
            "safety_score": 0.9,
            "social_score": 0.6
        }

        score = calculate_composite_score(features)

        assert 0 <= score <= 1

    def test_rank_tokens_by_score(self):
        """Test ranking tokens by composite score"""
        from src.core.scoring import rank_tokens

        tokens = [
            {"address": "0x123", "score": 0.9},
            {"address": "0x456", "score": 0.7},
            {"address": "0x789", "score": 0.8}
        ]

        ranked = rank_tokens(tokens)

        # Should be sorted by score descending
        assert ranked[0]["score"] >= ranked[1]["score"]
        assert ranked[1]["score"] >= ranked[2]["score"]

    def test_filter_by_confidence(self):
        """Test filtering tokens by confidence threshold"""
        from src.core.scoring import filter_by_confidence

        tokens = [
            {"address": "0x123", "score": 0.9, "confidence": 0.85},
            {"address": "0x456", "score": 0.8, "confidence": 0.60},
            {"address": "0x789", "score": 0.7, "confidence": 0.90}
        ]

        filtered = filter_by_confidence(tokens, min_confidence=0.75)

        assert len(filtered) == 2  # Only 2 meet threshold

    def test_generate_recommendations(self):
        """Test generating investment recommendations"""
        from src.core.scoring import generate_recommendations

        tokens = [
            {"address": "0x123", "score": 0.9, "risk": "low"},
            {"address": "0x456", "score": 0.7, "risk": "high"}
        ]

        recommendations = generate_recommendations(tokens, risk_tolerance="medium")

        assert len(recommendations) > 0
        assert all("recommendation" in r for r in recommendations)


# ===== Alert Generation Workflow =====

class TestAlertWorkflow:
    """Test alert generation and delivery"""

    def test_generate_anomaly_alert(self):
        """Test generating alert for detected anomaly"""
        from src.alerts.generator import generate_anomaly_alert

        anomaly = {
            "token": "0x123",
            "type": "volume_spike",
            "severity": "high",
            "timestamp": datetime.now().isoformat()
        }

        alert = generate_anomaly_alert(anomaly)

        assert alert["type"] == "anomaly"
        assert alert["severity"] == "high"

    def test_send_alert_notification(self):
        """Test sending alert via notification channel"""
        from src.alerts.notifier import send_alert

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200

            alert = {
                "type": "price_change",
                "message": "BTC price up 10%",
                "severity": "medium"
            }

            result = send_alert(alert, channel="webhook")

            assert result["sent"] is True
            mock_post.assert_called_once()

    def test_alert_deduplication(self):
        """Test alerts are deduplicated"""
        from src.alerts.notifier import AlertNotifier

        notifier = AlertNotifier()

        alert = {"type": "test", "message": "Test alert"}

        # Send same alert twice
        notifier.send(alert)
        result = notifier.send(alert)

        # Second send should be deduplicated
        assert result["deduplicated"] is True

    def test_alert_rate_limiting(self):
        """Test alert rate limiting"""
        from src.alerts.notifier import AlertNotifier

        notifier = AlertNotifier(max_per_hour=2)

        alert = {"type": "test", "message": "Test alert"}

        # Send multiple alerts
        results = [notifier.send(alert) for _ in range(5)]

        # Some should be rate limited
        assert any(r.get("rate_limited") for r in results)


# ===== Batch Processing Workflow =====

class TestBatchProcessing:
    """Test batch processing workflows"""

    def test_batch_scan_multiple_chains(self):
        """Test scanning multiple chains in batch"""
        from src.core.pipeline import batch_scan_chains

        with patch("src.core.pipeline.TokenScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value = {
                "tokens": [{"address": "0x123"}],
                "total_scanned": 1
            }

            results = batch_scan_chains(["ethereum", "bsc", "polygon"])

            assert len(results) == 3
            assert all("tokens" in r for r in results)

    def test_batch_update_features(self):
        """Test batch updating features for all tokens"""
        from src.core.pipeline import batch_update_features

        tokens = ["0x123", "0x456", "0x789"]

        with patch("src.core.pipeline.extract_features") as mock_extract:
            mock_extract.return_value = {"momentum": 0.8}

            results = batch_update_features(tokens)

            assert len(results) == len(tokens)

    def test_scheduled_scan_workflow(self):
        """Test scheduled scanning workflow"""
        from src.core.pipeline import run_scheduled_scan

        with patch("src.core.pipeline.TokenScanner") as mock_scanner:
            mock_scanner.return_value.scan.return_value = {"tokens": []}

            result = run_scheduled_scan(interval="1h")

            assert result["status"] == "completed" or "scan_id" in result

    def test_parallel_processing(self):
        """Test parallel processing of tokens"""
        from src.core.pipeline import process_tokens_parallel
        from concurrent.futures import ThreadPoolExecutor

        tokens = [{"address": f"0x{i}"} for i in range(10)]

        results = process_tokens_parallel(tokens, max_workers=4)

        assert len(results) == len(tokens)


# ===== Error Recovery Workflow =====

class TestErrorRecovery:
    """Test error handling and recovery"""

    def test_retry_on_network_error(self):
        """Test retrying on network failures"""
        from src.core.pipeline import fetch_with_retry

        with patch("requests.get") as mock_get:
            # Fail twice, then succeed
            mock_get.side_effect = [
                Exception("Network error"),
                Exception("Timeout"),
                Mock(status_code=200, json=lambda: {"data": "success"})
            ]

            result = fetch_with_retry("https://api.example.com", max_retries=3)

            assert result["data"] == "success"
            assert mock_get.call_count == 3

    def test_fallback_data_source(self):
        """Test falling back to alternative data source"""
        from src.core.pipeline import fetch_with_fallback

        with patch("src.core.pipeline.primary_source") as mock_primary, \
             patch("src.core.pipeline.fallback_source") as mock_fallback:

            mock_primary.side_effect = Exception("Primary failed")
            mock_fallback.return_value = {"data": "fallback"}

            result = fetch_with_fallback("token_data")

            assert result["data"] == "fallback"

    def test_graceful_degradation(self):
        """Test system operates in degraded mode"""
        from src.core.pipeline import TokenScanner

        with patch("src.core.sentiment.SentimentAnalyzer") as mock_sentiment:
            mock_sentiment.side_effect = Exception("Sentiment API down")

            scanner = TokenScanner()
            result = scanner.scan(chain="ethereum", limit=5)

            # Should still return results without sentiment
            assert "tokens" in result

    def test_checkpoint_recovery(self):
        """Test resuming from checkpoint after failure"""
        from src.core.pipeline import resume_from_checkpoint

        checkpoint_data = {
            "last_processed": "0x456",
            "total_processed": 50,
            "remaining": ["0x789", "0xabc"]
        }

        with patch("src.core.pipeline.load_checkpoint") as mock_load:
            mock_load.return_value = checkpoint_data

            result = resume_from_checkpoint("scan_123")

            assert result["resumed"] is True
            assert result["last_processed"] == "0x456"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
