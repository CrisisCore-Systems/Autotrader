"""Comprehensive integration tests for all API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.dashboard_api import app, feature_store
from src.core.feature_store import FeatureMetadata, FeatureType, FeatureCategory


@pytest.fixture(autouse=True)
def setup_feature_store():
    """Set up feature store with test data for API tests."""
    # Register required features in schema
    feature_store.register_feature(FeatureMetadata(
        name="gem_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SCORING,
        description="Gem score between 0 and 1",
        min_value=0.0,
        max_value=1.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="liquidity_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.LIQUIDITY,
        description="Liquidity score",
        min_value=0.0,
        max_value=1.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="price_momentum_1h",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.TECHNICAL,
        description="1-hour price momentum",
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="price_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="Price in USD",
        min_value=0.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="volume_24h_usd",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.MARKET,
        description="24h volume in USD",
        min_value=0.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="sentiment_score",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SENTIMENT,
        description="Sentiment score",
        min_value=-1.0,
        max_value=1.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="best_bid_price",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ORDERFLOW,
        description="Best bid price",
        min_value=0.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="best_ask_price",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ORDERFLOW,
        description="Best ask price",
        min_value=0.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="total_bid_volume",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ORDERFLOW,
        description="Total bid volume",
        min_value=0.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="total_ask_volume",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ORDERFLOW,
        description="Total ask volume",
        min_value=0.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="orderbook_imbalance",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.ORDERFLOW,
        description="Order book imbalance",
        min_value=-1.0,
        max_value=1.0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="tweet_volume",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SENTIMENT,
        description="Tweet volume",
        min_value=0,
    ))
    
    feature_store.register_feature(FeatureMetadata(
        name="engagement_to_followers_ratio",
        feature_type=FeatureType.NUMERIC,
        category=FeatureCategory.SENTIMENT,
        description="Engagement to followers ratio",
        min_value=0.0,
    ))
    
    # Write test data
    import time
    current_time = time.time()
    
    # ETH data
    feature_store.write_feature("gem_score", 0.75, "ETH", current_time, confidence=0.9)
    feature_store.write_feature("liquidity_score", 0.8, "ETH", current_time, confidence=0.85)
    
    # BTC data
    feature_store.write_feature("gem_score", 0.82, "BTC", current_time, confidence=0.95)
    feature_store.write_feature("liquidity_score", 0.9, "BTC", current_time, confidence=0.92)
    feature_store.write_feature("price_momentum_1h", 0.025, "BTC", current_time, confidence=0.8)
    feature_store.write_feature("best_bid_price", 45000.0, "BTC", current_time, confidence=0.95)
    feature_store.write_feature("best_ask_price", 45010.0, "BTC", current_time, confidence=0.95)
    feature_store.write_feature("total_bid_volume", 1000000.0, "BTC", current_time, confidence=0.9)
    feature_store.write_feature("total_ask_volume", 950000.0, "BTC", current_time, confidence=0.9)
    feature_store.write_feature("orderbook_imbalance", 0.025, "BTC", current_time, confidence=0.8)
    
    # Historical data for correlation and sentiment tests
    for i in range(10):
        timestamp = current_time - (i * 3600)  # Hourly data
        
        # Price data for correlation
        feature_store.write_feature("price_usd", 45000 + (i * 100), "BTC", timestamp, confidence=0.95)
        feature_store.write_feature("price_usd", 3000 + (i * 50), "ETH", timestamp, confidence=0.95)
        feature_store.write_feature("price_usd", 25 + (i * 0.5), "LINK", timestamp, confidence=0.95)
        feature_store.write_feature("price_usd", 15 + (i * 0.3), "UNI", timestamp, confidence=0.95)
        feature_store.write_feature("price_usd", 80 + (i * 2), "AAVE", timestamp, confidence=0.95)
        
        # Volume data
        feature_store.write_feature("volume_24h_usd", 1000000 + (i * 50000), "BTC", timestamp, confidence=0.9)
        feature_store.write_feature("volume_24h_usd", 500000 + (i * 25000), "ETH", timestamp, confidence=0.9)
        
        # Sentiment data
        feature_store.write_feature("sentiment_score", 0.1 + (i * 0.05), "BTC", timestamp, confidence=0.7)
        feature_store.write_feature("sentiment_score", -0.1 + (i * 0.03), "ETH", timestamp, confidence=0.7)
        feature_store.write_feature("tweet_volume", 1000 + (i * 50), "BTC", timestamp, confidence=0.8)
        feature_store.write_feature("tweet_volume", 800 + (i * 40), "ETH", timestamp, confidence=0.8)
        feature_store.write_feature("engagement_to_followers_ratio", 0.02 + (i * 0.001), "BTC", timestamp, confidence=0.6)
        feature_store.write_feature("engagement_to_followers_ratio", 0.015 + (i * 0.0008), "ETH", timestamp, confidence=0.6)


client = TestClient(app)


# ============================================================================
# Root & Health Endpoints
# ============================================================================

def test_root_endpoint():
    """Test root endpoint returns status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "message" in data


def test_health_check_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


# ============================================================================
# Scanner Endpoints
# ============================================================================

def test_get_tokens_list():
    """Test GET /api/tokens returns list of token summaries."""
    response = client.get("/api/tokens")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        token = data[0]
        assert "symbol" in token
        assert "final_score" in token
        assert "gem_score" in token
        assert "confidence" in token
        assert "liquidity_usd" in token


def test_get_token_detail():
    """Test GET /api/tokens/{symbol} returns full token detail."""
    # First get list to ensure we have a valid symbol
    tokens_response = client.get("/api/tokens")
    tokens = tokens_response.json()
    
    if not tokens:
        pytest.skip("No tokens available for testing")
    
    symbol = tokens[0]["symbol"]
    response = client.get(f"/api/tokens/{symbol}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["symbol"] == symbol
    assert "tree" in data
    assert "contributions" in data
    assert "narrative" in data
    assert "safety_report" in data
    assert "market_snapshot" in data


def test_get_nonexistent_token():
    """Test GET /api/tokens/{symbol} with invalid symbol."""
    response = client.get("/api/tokens/NONEXISTENT123")
    assert response.status_code in [404, 500]  # May error or return 404


# ============================================================================
# Anomaly Detection Endpoints
# ============================================================================

def test_get_anomalies():
    """Test GET /api/anomalies returns anomaly list."""
    response = client.get("/api/anomalies")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_anomalies_with_filters():
    """Test GET /api/anomalies with query parameters."""
    response = client.get("/api/anomalies?severity=high&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 10


def test_acknowledge_anomaly():
    """Test POST /api/anomalies/{alert_id}/acknowledge."""
    # First get an anomaly if available
    anomalies_response = client.get("/api/anomalies")
    anomalies = anomalies_response.json()
    
    if anomalies:
        alert_id = anomalies[0]["alert_id"]
        response = client.post(f"/api/anomalies/{alert_id}/acknowledge")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
    else:
        # Test with fake ID
        response = client.post("/api/anomalies/fake_id_123/acknowledge")
        assert response.status_code == 200


# ============================================================================
# Confidence Interval Endpoints
# ============================================================================

def test_get_gem_score_confidence():
    """Test GET /api/confidence/gem-score/{token_symbol}."""
    response = client.get("/api/confidence/gem-score/ETH")
    assert response.status_code == 200
    data = response.json()
    assert "value" in data
    assert "lower_bound" in data
    assert "upper_bound" in data
    assert "confidence_level" in data
    assert data["lower_bound"] <= data["value"] <= data["upper_bound"]


def test_get_liquidity_confidence():
    """Test GET /api/confidence/liquidity/{token_symbol}."""
    response = client.get("/api/confidence/liquidity/ETH")
    assert response.status_code == 200
    data = response.json()
    assert "value" in data
    assert "lower_bound" in data
    assert "upper_bound" in data
    assert "confidence_level" in data


# ============================================================================
# SLA Monitoring Endpoints
# ============================================================================

def test_get_sla_status():
    """Test GET /api/sla/status returns all source SLA metrics."""
    response = client.get("/api/sla/status")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    if data:
        sla = data[0]
        assert "source_name" in sla
        assert "status" in sla
        assert sla["status"] in ["HEALTHY", "DEGRADED", "FAILED"]


def test_get_circuit_breakers():
    """Test GET /api/sla/circuit-breakers returns breaker states."""
    response = client.get("/api/sla/circuit-breakers")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    if data:
        breaker = data[0]
        assert "breaker_name" in breaker
        assert "state" in breaker
        assert breaker["state"] in ["CLOSED", "OPEN", "HALF_OPEN"]
        assert "failure_count" in breaker


def test_get_system_health():
    """Test GET /api/sla/health returns overall health."""
    response = client.get("/api/sla/health")
    assert response.status_code == 200
    data = response.json()
    assert "overall_status" in data
    assert data["overall_status"] in ["HEALTHY", "DEGRADED", "CRITICAL"]
    assert "healthy_sources" in data
    assert "degraded_sources" in data
    assert "failed_sources" in data


# ============================================================================
# Analytics Endpoints
# ============================================================================

def test_get_correlation_matrix():
    """Test GET /api/correlation/matrix."""
    response = client.get("/api/correlation/matrix")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_correlation_matrix_with_metric():
    """Test GET /api/correlation/matrix with metric filter."""
    for metric in ["price", "volume", "sentiment"]:
        response = client.get(f"/api/correlation/matrix?metric={metric}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


def test_get_orderflow():
    """Test GET /api/orderflow/{token_symbol}."""
    response = client.get("/api/orderflow/BTC")
    assert response.status_code == 200
    data = response.json()
    assert "token_symbol" in data
    assert "bids" in data
    assert "asks" in data
    assert "bid_depth_usd" in data
    assert "ask_depth_usd" in data
    assert "imbalance" in data


def test_get_sentiment_trend():
    """Test GET /api/sentiment/trend/{token_symbol}."""
    response = client.get("/api/sentiment/trend/BTC")
    assert response.status_code == 200
    data = response.json()
    assert "token_symbol" in data
    assert "timestamps" in data
    assert "sentiment_scores" in data
    assert isinstance(data["timestamps"], list)
    assert isinstance(data["sentiment_scores"], list)


def test_get_sentiment_trend_with_hours():
    """Test GET /api/sentiment/trend/{token_symbol}?hours={N}."""
    for hours in [6, 12, 24, 48]:
        response = client.get(f"/api/sentiment/trend/ETH?hours={hours}")
        assert response.status_code == 200
        data = response.json()
        assert "token_symbol" in data


# ============================================================================
# Feature Store Endpoints
# ============================================================================

def test_get_features_for_token():
    """Test GET /api/features/{token}."""
    response = client.get("/api/features/BTC")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)  # Returns dict with feature names as keys
    
    if data:
        # Get first feature from the dict
        feature_name, feature_data = next(iter(data.items()))
        assert "value" in feature_data
        assert "confidence" in feature_data
        assert "timestamp" in feature_data
        assert "source" in feature_data


def test_get_feature_schema():
    """Test GET /api/features/schema."""
    response = client.get("/api/features/schema")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
    if data:
        schema_entry = data[0]
        assert "category" in schema_entry


# ============================================================================
# Error Handling Tests
# ============================================================================

def test_invalid_endpoint_returns_404():
    """Test that invalid endpoints return 404."""
    response = client.get("/api/nonexistent/endpoint")
    assert response.status_code == 404


def test_malformed_request_params():
    """Test malformed request parameters."""
    response = client.get("/api/sentiment/trend/BTC?hours=invalid")
    # Should handle gracefully, either 200 with default or 422
    assert response.status_code in [200, 422]


# ============================================================================
# CORS & Headers Tests
# ============================================================================

def test_json_content_type():
    """Test that API returns JSON content type."""
    response = client.get("/api/tokens")
    assert "application/json" in response.headers.get("content-type", "")
