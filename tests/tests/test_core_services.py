"""
Core Services Unit Tests

Tests core business logic components including sentiment analysis,
feature engineering, reliability services, and feature store operations.

Run with: pytest tests/test_core_services.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ===== Sentiment Analyzer Tests =====

class TestSentimentAnalyzer:
    """Test suite for sentiment analysis functionality"""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client for sentiment analysis"""
        with patch("src.core.sentiment.get_llm_client") as mock:
            client = Mock()
            client.chat.completions.create.return_value = Mock(
                choices=[Mock(message=Mock(content="Positive sentiment detected. Bullish indicators."))]
            )
            mock.return_value = client
            yield mock

    @pytest.fixture
    def sentiment_analyzer(self, mock_llm_client):
        """Create sentiment analyzer instance"""
        from src.core.sentiment import SentimentAnalyzer
        return SentimentAnalyzer()

    def test_analyze_single_text(self, sentiment_analyzer):
        """Test analyzing single text for sentiment"""
        result = sentiment_analyzer.analyze("Bitcoin reaches new all-time high!")
        assert result is not None
        assert "sentiment" in result or "score" in result

    def test_analyze_batch_texts(self, sentiment_analyzer):
        """Test analyzing multiple texts in batch"""
        texts = [
            "Market is bullish today",
            "Major correction expected",
            "Neutral trading volume"
        ]
        results = sentiment_analyzer.analyze_batch(texts)
        assert len(results) == 3

    def test_sentiment_score_range(self, sentiment_analyzer):
        """Test sentiment scores are in valid range"""
        result = sentiment_analyzer.analyze("Test text")
        if "score" in result:
            assert -1.0 <= result["score"] <= 1.0

    def test_narrative_extraction(self, sentiment_analyzer):
        """Test extracting narrative themes"""
        text = "DeFi revolution continues with new protocols launching daily"
        result = sentiment_analyzer.extract_narrative(text)
        assert result is not None

    def test_empty_text_handling(self, sentiment_analyzer):
        """Test handling of empty text"""
        result = sentiment_analyzer.analyze("")
        assert result is not None  # Should handle gracefully

    def test_llm_error_handling(self, sentiment_analyzer, mock_llm_client):
        """Test handling LLM API errors"""
        mock_llm_client.return_value.chat.completions.create.side_effect = Exception("API Error")
        result = sentiment_analyzer.analyze("Test text")
        # Should handle error and return default/fallback


# ===== Feature Engineering Tests =====

class TestFeatureEngineering:
    """Test suite for feature engineering"""

    @pytest.fixture
    def sample_token_data(self):
        """Sample token data for feature extraction"""
        return {
            "address": "0x123",
            "price": 1.5,
            "volume_24h": 100000,
            "liquidity": 500000,
            "holders": 1000,
            "price_change_24h": 5.2,
            "creation_time": datetime.now() - timedelta(days=30)
        }

    def test_calculate_momentum_features(self, sample_token_data):
        """Test momentum feature calculation"""
        from src.core.features import calculate_momentum_features
        features = calculate_momentum_features(sample_token_data)
        assert "volume_momentum" in features or "price_momentum" in features

    def test_calculate_liquidity_features(self, sample_token_data):
        """Test liquidity feature calculation"""
        from src.core.features import calculate_liquidity_features
        features = calculate_liquidity_features(sample_token_data)
        assert "liquidity_ratio" in features or "volume_to_liquidity" in features

    def test_calculate_social_features(self, sample_token_data):
        """Test social feature calculation"""
        from src.core.features import calculate_social_features
        social_data = {"twitter_followers": 10000, "telegram_members": 5000}
        features = calculate_social_features(sample_token_data, social_data)
        assert isinstance(features, dict)

    def test_calculate_safety_features(self, sample_token_data):
        """Test safety feature calculation"""
        from src.core.features import calculate_safety_features
        features = calculate_safety_features(sample_token_data)
        assert "holder_concentration" in features or "contract_verified" in features

    def test_feature_normalization(self):
        """Test feature value normalization"""
        from src.core.features import normalize_features
        features = {"volume": 1000000, "price": 0.5, "holders": 500}
        normalized = normalize_features(features)
        assert all(0 <= v <= 1 for v in normalized.values() if isinstance(v, (int, float)))

    def test_feature_scaling(self):
        """Test feature scaling"""
        from src.core.features import scale_features
        features = [100, 200, 300, 400, 500]
        scaled = scale_features(features)
        assert len(scaled) == len(features)

    def test_handle_missing_features(self, sample_token_data):
        """Test handling of missing feature data"""
        incomplete_data = {"address": "0x123", "price": 1.0}
        from src.core.features import calculate_all_features
        features = calculate_all_features(incomplete_data)
        assert isinstance(features, dict)


# ===== Feature Store Tests =====

class TestFeatureStore:
    """Test suite for feature store operations"""

    @pytest.fixture
    def feature_store(self):
        """Create feature store instance"""
        from src.services.feature_store import FeatureStore
        return FeatureStore()

    @pytest.fixture
    def sample_feature(self):
        """Sample feature definition"""
        return {
            "feature_id": "momentum_1",
            "name": "Volume Change 24h",
            "category": "momentum",
            "formula": "volume_24h / volume_24h_ago",
            "importance": 0.8,
            "enabled": True
        }

    def test_create_feature(self, feature_store, sample_feature):
        """Test creating new feature"""
        result = feature_store.create_feature(sample_feature)
        assert result["feature_id"] == "momentum_1"

    def test_get_feature(self, feature_store, sample_feature):
        """Test retrieving feature by ID"""
        feature_store.create_feature(sample_feature)
        feature = feature_store.get_feature("momentum_1")
        assert feature["name"] == "Volume Change 24h"

    def test_update_feature(self, feature_store, sample_feature):
        """Test updating existing feature"""
        feature_store.create_feature(sample_feature)
        updated = feature_store.update_feature("momentum_1", {"importance": 0.9})
        assert updated["importance"] == 0.9

    def test_delete_feature(self, feature_store, sample_feature):
        """Test deleting feature"""
        feature_store.create_feature(sample_feature)
        result = feature_store.delete_feature("momentum_1")
        assert result is True

    def test_list_features_by_category(self, feature_store, sample_feature):
        """Test listing features by category"""
        feature_store.create_feature(sample_feature)
        features = feature_store.list_features(category="momentum")
        assert len(features) > 0

    def test_get_feature_importance(self, feature_store, sample_feature):
        """Test retrieving feature importance scores"""
        feature_store.create_feature(sample_feature)
        importance = feature_store.get_feature_importance()
        assert isinstance(importance, dict)

    def test_enable_disable_feature(self, feature_store, sample_feature):
        """Test enabling/disabling features"""
        feature_store.create_feature(sample_feature)
        feature_store.disable_feature("momentum_1")
        feature = feature_store.get_feature("momentum_1")
        assert feature["enabled"] is False


# ===== Reliability Services Tests =====

class TestReliabilityServices:
    """Test suite for reliability infrastructure"""

    def test_sla_registry_registration(self):
        """Test SLA service registration"""
        from src.services.reliability import SLARegistry
        registry = SLARegistry()
        registry.register("test_service", target_uptime=99.9, max_latency_ms=500)
        status = registry.get_status("test_service")
        assert status["service"] == "test_service"

    def test_sla_metric_recording(self):
        """Test recording SLA metrics"""
        from src.services.reliability import SLARegistry
        registry = SLARegistry()
        registry.register("test_service")
        registry.record_request("test_service", latency_ms=250, success=True)
        status = registry.get_status("test_service")
        assert status["total_requests"] >= 1

    def test_circuit_breaker_open_close(self):
        """Test circuit breaker state transitions"""
        from src.services.reliability import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=3, timeout=5)

        # Should be closed initially
        assert breaker.state == "closed"

        # Trigger failures
        for _ in range(3):
            breaker.record_failure()

        # Should open after threshold
        assert breaker.state == "open"

    def test_circuit_breaker_half_open(self):
        """Test circuit breaker half-open state"""
        from src.services.reliability import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=2, timeout=0.1)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == "open"

        # Wait for timeout
        import time
        time.sleep(0.2)

        # Should allow one test request
        assert breaker.can_request() is True

    def test_cache_policy_basic(self):
        """Test basic cache policy operations"""
        from src.services.reliability import CachePolicy
        cache = CachePolicy(ttl_seconds=60)

        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration"""
        from src.services.reliability import CachePolicy
        cache = CachePolicy(ttl_seconds=0.1)

        cache.set("key1", "value1")
        import time
        time.sleep(0.2)

        # Should be expired
        assert cache.get("key1") is None

    def test_adaptive_cache_policy(self):
        """Test adaptive cache policy"""
        from src.services.reliability import AdaptiveCachePolicy
        cache = AdaptiveCachePolicy(base_ttl=60)

        # Frequently accessed items should have longer TTL
        for _ in range(10):
            cache.get("hot_key")

        # Check TTL was adjusted
        assert cache.get_ttl("hot_key") > 60


# ===== Contract Safety Tests =====

class TestContractSafety:
    """Test suite for contract safety analysis"""

    @pytest.fixture
    def sample_contract_data(self):
        """Sample contract data for safety checks"""
        return {
            "address": "0x123",
            "verified": True,
            "has_proxy": False,
            "has_mint_function": False,
            "ownership_renounced": True,
            "liquidity_locked": True,
            "holder_count": 1000,
            "top_holder_pct": 5.0
        }

    def test_calculate_safety_score(self, sample_contract_data):
        """Test overall safety score calculation"""
        from src.core.safety import calculate_safety_score
        score = calculate_safety_score(sample_contract_data)
        assert 0 <= score <= 100

    def test_check_contract_verification(self, sample_contract_data):
        """Test contract verification check"""
        from src.core.safety import check_verification
        result = check_verification(sample_contract_data)
        assert result["verified"] is True

    def test_check_ownership_concentration(self, sample_contract_data):
        """Test ownership concentration analysis"""
        from src.core.safety import check_ownership_concentration
        result = check_ownership_concentration(sample_contract_data)
        assert "top_holder_pct" in result

    def test_check_liquidity_locked(self, sample_contract_data):
        """Test liquidity lock verification"""
        from src.core.safety import check_liquidity_lock
        result = check_liquidity_lock(sample_contract_data)
        assert result["locked"] is True

    def test_identify_risks(self, sample_contract_data):
        """Test risk identification"""
        from src.core.safety import identify_risks
        risks = identify_risks(sample_contract_data)
        assert isinstance(risks, list)

    def test_high_risk_contract(self):
        """Test detection of high-risk contract"""
        from src.core.safety import calculate_safety_score
        risky_contract = {
            "verified": False,
            "has_mint_function": True,
            "ownership_renounced": False,
            "liquidity_locked": False,
            "top_holder_pct": 50.0
        }
        score = calculate_safety_score(risky_contract)
        assert score < 50  # Should be low score


# ===== News Aggregation Tests =====

class TestNewsAggregation:
    """Test suite for news aggregation"""

    def test_fetch_crypto_news(self):
        """Test fetching crypto news"""
        from src.services.news import fetch_crypto_news
        with patch("requests.get") as mock_get:
            mock_get.return_value.json.return_value = {
                "articles": [{"title": "BTC hits new high", "source": "CryptoNews"}]
            }
            news = fetch_crypto_news(limit=10)
            assert len(news) > 0

    def test_filter_relevant_news(self):
        """Test filtering news by relevance"""
        from src.services.news import filter_relevant_news
        articles = [
            {"title": "Bitcoin price surge", "relevance_score": 0.9},
            {"title": "Weather report", "relevance_score": 0.1}
        ]
        filtered = filter_relevant_news(articles, min_relevance=0.5)
        assert len(filtered) == 1

    def test_extract_news_sentiment(self):
        """Test extracting sentiment from news"""
        from src.services.news import extract_sentiment
        article = {"title": "Major crypto exchange hacked", "content": "Security breach reported"}
        sentiment = extract_sentiment(article)
        assert "score" in sentiment or "label" in sentiment


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
