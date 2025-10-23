"""Tests for health and observability API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_health_freshness_endpoint():
    """Test /api/health/freshness endpoint returns freshness data."""
    response = client.get("/api/health/freshness")
    assert response.status_code == 200
    
    data = response.json()
    assert "sources" in data
    assert "timestamp" in data
    
    # Check required sources are present
    sources = data["sources"]
    assert "coingecko" in sources
    assert "dexscreener" in sources
    assert "blockscout" in sources
    assert "ethereum_rpc" in sources
    
    # Check source data structure
    for source_name, source_data in sources.items():
        assert "display_name" in source_data
        assert "last_success_at" in source_data
        assert "data_age_seconds" in source_data
        assert "freshness_level" in source_data
        assert "is_free" in source_data
        assert "error_rate" in source_data
        assert source_data["freshness_level"] in ["fresh", "recent", "stale", "outdated"]


def test_health_sla_endpoint():
    """Test /api/health/sla endpoint returns SLA metrics."""
    response = client.get("/api/health/sla")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # Each SLA entry should have required fields
    for sla_entry in data:
        assert "source_name" in sla_entry
        assert "status" in sla_entry
        assert sla_entry["status"] in ["HEALTHY", "DEGRADED", "FAILED"]


def test_health_circuit_breakers_endpoint():
    """Test /api/health/circuit-breakers endpoint."""
    response = client.get("/api/health/circuit-breakers")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # Each circuit breaker should have required fields
    for cb_entry in data:
        assert "breaker_name" in cb_entry
        assert "state" in cb_entry
        assert "failure_count" in cb_entry
        assert cb_entry["state"] in ["CLOSED", "OPEN", "HALF_OPEN"]


def test_health_overview_endpoint():
    """Test /api/health/overview endpoint returns system health."""
    response = client.get("/api/health/overview")
    assert response.status_code == 200
    
    data = response.json()
    assert "overall_status" in data
    assert data["overall_status"] in ["HEALTHY", "DEGRADED", "FAILED"]
    assert "healthy_sources" in data
    assert "degraded_sources" in data
    assert "failed_sources" in data
    assert "circuit_breakers" in data
    assert "cache_stats" in data


def test_health_rate_limits_endpoint():
    """Test /api/health/rate-limits endpoint."""
    response = client.get("/api/health/rate-limits")
    assert response.status_code == 200
    
    data = response.json()
    assert "rate_limits" in data
    assert "timestamp" in data
    
    rate_limits = data["rate_limits"]
    assert "coingecko" in rate_limits
    
    # Check rate limit data structure
    for source_name, limit_data in rate_limits.items():
        assert "name" in limit_data
        assert "is_free" in limit_data
        assert "limit_per_minute" in limit_data
        assert "estimated_usage" in limit_data
        assert "status" in limit_data


def test_health_queues_endpoint():
    """Test /api/health/queues endpoint."""
    response = client.get("/api/health/queues")
    assert response.status_code == 200
    
    data = response.json()
    assert "queues" in data
    assert "timestamp" in data
    
    queues = data["queues"]
    
    # Check queue data structure
    for queue_name, queue_data in queues.items():
        assert "name" in queue_data
        assert "pending_jobs" in queue_data
        assert "active_workers" in queue_data
        assert "completed_today" in queue_data
        assert "avg_processing_time_ms" in queue_data
        assert "status" in queue_data


def test_health_security_endpoint():
    """Test /api/health/security endpoint."""
    response = client.get("/api/health/security")
    assert response.status_code == 200
    
    data = response.json()
    assert "checks" in data
    assert "overall_status" in data
    assert "timestamp" in data
    
    checks = data["checks"]
    assert "ibkr_fa_scrubbing" in checks
    assert "dependency_scan" in checks
    assert "api_key_validation" in checks
    
    # Check security check structure
    for check_name, check_data in checks.items():
        assert "name" in check_data
        assert "status" in check_data
        assert "last_check" in check_data
        assert "description" in check_data


def test_health_endpoints_rate_limiting():
    """Test that health endpoints respect rate limits."""
    # Health endpoints have 60 req/min rate limit
    # Make multiple requests quickly
    for i in range(5):
        response = client.get("/api/health/freshness")
        assert response.status_code == 200
    
    # Should still work within rate limit
    response = client.get("/api/health/freshness")
    assert response.status_code == 200
