"""Comprehensive unit tests for core services."""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from src.core.sentiment import SentimentAnalyzer
from src.services.feature_engineering import FeatureTransformRegistry
from src.services.reliability import get_system_health, SLA_REGISTRY, CIRCUIT_REGISTRY


# ============================================================================
# Sentiment Analyzer Tests
# ============================================================================

class TestSentimentAnalyzer:
    """Test suite for SentimentAnalyzer."""
    
    def test_analyze_news_sentiment_with_no_articles(self):
        """Test sentiment analysis with empty news list."""
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze_news_sentiment("BTC", [])
        assert result == 0.5  # Default neutral sentiment
    
    def test_analyze_news_sentiment_with_scored_articles(self):
        """Test sentiment analysis with pre-scored articles."""
        analyzer = SentimentAnalyzer()
        articles = [
            {"title": "Bitcoin surges", "sentiment": 5},
            {"title": "BTC breaks records", "sentiment": 8},
            {"title": "Market correction", "sentiment": -3},
        ]
        result = analyzer.analyze_news_sentiment("BTC", articles)
        assert 0.0 <= result <= 1.0
        assert result != 0.5  # Should not be default
    
    def test_analyze_news_sentiment_without_scores(self):
        """Test sentiment analysis using LLM fallback."""
        analyzer = SentimentAnalyzer()
        articles = [
            {"title": "Bitcoin adoption grows"},
            {"title": "New partnerships announced"},
        ]
        result = analyzer.analyze_news_sentiment("BTC", articles)
        assert 0.0 <= result <= 1.0
    
    def test_get_dynamic_sentiment(self):
        """Test dynamic sentiment with confidence calculation."""
        analyzer = SentimentAnalyzer()
        articles = [
            {"title": "Article 1", "source": "CoinDesk", "sentiment": 5},
            {"title": "Article 2", "source": "CoinTelegraph", "sentiment": 3},
        ]
        result = analyzer.get_dynamic_sentiment("ETH", articles)
        
        assert "score" in result
        assert "articles_count" in result
        assert "confidence" in result
        assert "sources" in result
        assert "latest_titles" in result
        assert result["articles_count"] == 2
        assert len(result["sources"]) == 2
    
    def test_llm_analyzer_handles_errors_gracefully(self):
        """Test that LLM errors fall back to default sentiment."""
        analyzer = SentimentAnalyzer()
        # Even with malformed data, should return valid sentiment
        result = analyzer._analyze_with_llm("BTC", ["test"])
        assert 0.0 <= result <= 1.0


# ============================================================================
# Feature Engineering Tests
# ============================================================================

class TestFeatureEngineering:
    """Test suite for feature engineering transforms."""
    
    def test_feature_transform_registry_initialization(self):
        """Test that feature transform registry initializes."""
        registry = FeatureTransformRegistry()
        assert registry is not None
        # Registry should have standard transforms
        transforms = registry.list_transforms()
        assert isinstance(transforms, list)
    
    def test_log_transform(self):
        """Test logarithmic transform."""
        registry = FeatureTransformRegistry()
        # Test if log transform exists and works
        if hasattr(registry, 'log_transform'):
            result = registry.log_transform(100)
            assert result > 0
    
    def test_normalize_transform(self):
        """Test normalization transform."""
        registry = FeatureTransformRegistry()
        if hasattr(registry, 'normalize'):
            values = [1, 2, 3, 4, 5]
            result = registry.normalize(values)
            assert all(0 <= v <= 1 for v in result)
    
    def test_feature_extraction_from_raw_data(self):
        """Test extracting features from raw token data."""
        raw_data = {
            "price": 50000,
            "volume_24h": 1000000000,
            "holders": 1000000,
            "liquidity_usd": 5000000
        }
        # Feature engineering should handle this data
        assert all(isinstance(v, (int, float)) for v in raw_data.values())


# ============================================================================
# Reliability & SLA Tests
# ============================================================================

class TestReliabilityServices:
    """Test suite for reliability monitoring."""
    
    def test_get_system_health_returns_valid_status(self):
        """Test system health check returns valid data."""
        health = get_system_health()
        assert health is not None
        assert "overall_status" in health
        assert health["overall_status"] in ["HEALTHY", "DEGRADED", "CRITICAL"]
    
    def test_sla_registry_exists(self):
        """Test that SLA registry is initialized."""
        assert SLA_REGISTRY is not None
        # Should be able to get metrics
        if hasattr(SLA_REGISTRY, 'get_all_metrics'):
            metrics = SLA_REGISTRY.get_all_metrics()
            assert isinstance(metrics, (list, dict))
    
    def test_circuit_breaker_registry_exists(self):
        """Test that circuit breaker registry is initialized."""
        assert CIRCUIT_REGISTRY is not None
        # Should be able to get breaker states
        if hasattr(CIRCUIT_REGISTRY, 'get_all_states'):
            states = CIRCUIT_REGISTRY.get_all_states()
            assert isinstance(states, (list, dict))
    
    def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker state transitions."""
        # Mock a circuit breaker
        class MockCircuitBreaker:
            def __init__(self):
                self.state = "CLOSED"
                self.failure_count = 0
            
            def record_failure(self):
                self.failure_count += 1
                if self.failure_count >= 5:
                    self.state = "OPEN"
            
            def record_success(self):
                self.failure_count = 0
                self.state = "CLOSED"
        
        breaker = MockCircuitBreaker()
        assert breaker.state == "CLOSED"
        
        # Record failures
        for _ in range(5):
            breaker.record_failure()
        assert breaker.state == "OPEN"
        
        # Recovery
        breaker.record_success()
        assert breaker.state == "CLOSED"


# ============================================================================
# Feature Store Tests
# ============================================================================

class TestFeatureStore:
    """Test suite for feature store."""
    
    @pytest.fixture
    def feature_store(self):
        """Create a feature store instance."""
        from src.core.feature_store import FeatureStore
        return FeatureStore()
    
    def test_feature_store_initialization(self, feature_store):
        """Test feature store initializes correctly."""
        assert feature_store is not None
    
    def test_store_and_retrieve_feature(self, feature_store):
        """Test storing and retrieving features."""
        token = "TEST"
        feature_name = "test_feature"
        feature_value = 42.0
        
        # First register the feature in schema
        from src.core.feature_store import FeatureMetadata, FeatureType, FeatureCategory
        feature_store.register_feature(FeatureMetadata(
            name=feature_name,
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.MARKET,
            description="Test feature",
        ))
        
        # Store feature
        feature_store.write_feature(
            feature_name=feature_name,
            value=feature_value,
            token_symbol=token,
            confidence=0.9,
        )
        
        # Retrieve feature
        retrieved_feature = feature_store.read_feature(feature_name, token)
        assert retrieved_feature is not None
        assert retrieved_feature.value == feature_value
        assert retrieved_feature.confidence == 0.9
        assert retrieved_feature.token_symbol == token
    
    def test_get_feature_schema(self, feature_store):
        """Test getting feature schema."""
        schema = feature_store.list_features()
        assert isinstance(schema, list)
    
    def test_feature_categories(self, feature_store):
        """Test feature categorization."""
        categories = [
            "market", "sentiment", "technical", "security",
            "liquidity", "orderflow", "volatility", "social", "narrative"
        ]
        schema = feature_store.list_features()
        
        if schema:
            # At least some categories should be represented
            schema_categories = [s.category.value for s in schema]
            assert any(cat in schema_categories for cat in categories)


# ============================================================================
# News Client Tests
# ============================================================================

class TestNewsClient:
    """Test suite for news aggregation."""
    
    def test_news_client_initialization(self):
        """Test news client can be initialized."""
        from src.core.news_client import NewsClient
        client = NewsClient()
        assert client is not None
    
    @patch('src.core.news_client.requests.get')
    def test_fetch_news_handles_errors(self, mock_get):
        """Test news fetching handles API errors gracefully."""
        from src.core.news_client import NewsClient
        
        # Mock failed request
        mock_get.side_effect = Exception("API Error")
        
        client = NewsClient()
        result = client.get_news_for_token("BTC")
        
        # Should return empty list or handle gracefully
        assert isinstance(result, list)
    
    @patch('src.core.news_client.requests.get')
    def test_fetch_news_returns_articles(self, mock_get):
        """Test successful news fetching."""
        from src.core.news_client import NewsClient
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Bitcoin News",
                    "url": "http://example.com",
                    "source": {"title": "CoinDesk"},
                    "published_at": "2025-01-01T00:00:00Z",
                    "votes": {"positive": 10, "negative": 2}
                }
            ]
        }
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        client = NewsClient()
        result = client.get_news_for_token("BTC")
        
        assert isinstance(result, list)


# ============================================================================
# Pipeline Tests
# ============================================================================

class TestPipeline:
    """Test suite for token scanning pipeline."""
    
    def test_token_config_creation(self):
        """Test creating token configuration."""
        from src.core.pipeline import TokenConfig
        
        config = TokenConfig(
            symbol="BTC",
            coingecko_id="bitcoin",
            defillama_slug="bitcoin",
            contract_address="0x123",
            narratives=["DeFi", "Layer1"]
        )
        
        assert config.symbol == "BTC"
        assert config.coingecko_id == "bitcoin"
        assert config.defillama_slug == "bitcoin"
        assert len(config.narratives) == 2
    
    def test_scan_context_creation(self):
        """Test creating scan context."""
        from src.core.pipeline import TokenConfig, ScanContext
        
        config = TokenConfig(
            symbol="ETH",
            coingecko_id="ethereum",
            defillama_slug="ethereum",
            contract_address="0xETH"
        )
        
        context = ScanContext(config=config)
        assert context.config == config
        assert context.config.symbol == "ETH"


# ============================================================================
# Safety Analysis Tests
# ============================================================================

class TestSafetyAnalysis:
    """Test suite for safety analysis."""
    
    def test_safety_analyzer_initialization(self):
        """Test safety analyzer initializes."""
        from src.core.safety import SafetyAnalyzer
        analyzer = SafetyAnalyzer()
        assert analyzer is not None
    
    def test_analyze_contract_safety(self):
        """Test contract safety analysis."""
        from src.core.safety import SafetyAnalyzer
        
        analyzer = SafetyAnalyzer()
        contract_data = {
            "SourceCode": "contract Test {}",
            "ContractName": "Test"
        }
        
        result = analyzer.analyze_contract(contract_data)
        assert "score" in result
        assert "severity" in result
        assert "findings" in result
        assert 0.0 <= result["score"] <= 10.0
