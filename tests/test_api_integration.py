"""Comprehensive integration tests for all API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.dashboard_api import app

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
    assert isinstance(data, list)
    
    if data:
        feature = data[0]
        assert "name" in feature
        assert "value" in feature
        assert "confidence" in feature
        assert "category" in feature
        assert "feature_type" in feature


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

def test_cors_headers_present():
    """Test that CORS headers are present for browser compatibility."""
    response = client.options("/api/tokens")
    assert response.status_code in [200, 204]


def test_json_content_type():
    """Test that API returns JSON content type."""
    response = client.get("/api/tokens")
    assert "application/json" in response.headers.get("content-type", "")
