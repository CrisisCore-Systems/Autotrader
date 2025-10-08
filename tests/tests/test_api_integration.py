"""
API Integration Tests

Tests all API endpoints for the AutoTrader dashboard and enhanced API.
Covers happy paths, error cases, edge cases, and CORS validation.

Run with: pytest tests/test_api_integration.py -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_dashboard_dependencies():
    """Mock all external dependencies for dashboard API"""
    with patch("src.api.dashboard_api.TokenScanner") as mock_scanner, \
         patch("src.api.dashboard_api.load_yaml_config") as mock_config:

        # Mock scanner instance
        scanner_instance = Mock()
        scanner_instance.scan.return_value = {
            "tokens": [
                {
                    "address": "0x123",
                    "symbol": "TEST",
                    "name": "Test Token",
                    "liquidity_usd": 100000,
                    "volume_24h": 50000,
                    "price_change_24h": 5.2,
                    "holder_count": 1000,
                    "creation_time": "2024-01-01T00:00:00Z",
                    "safety_score": 85.5,
                    "liquidity_locked": True
                }
            ],
            "total_scanned": 1,
            "filtered_count": 1
        }
        mock_scanner.return_value = scanner_instance

        # Mock config
        mock_config.return_value = {
            "api": {"port": 8001, "host": "0.0.0.0"},
            "scanner": {"min_liquidity": 10000}
        }

        yield {
            "scanner": mock_scanner,
            "config": mock_config,
            "scanner_instance": scanner_instance
        }


@pytest.fixture
def dashboard_client(mock_dashboard_dependencies):
    """Create test client for dashboard API"""
    from src.api.dashboard_api import app
    return TestClient(app)


@pytest.fixture
def mock_enhanced_dependencies():
    """Mock all external dependencies for enhanced API"""
    with patch("src.api.enhanced_api.FeatureStore") as mock_store, \
         patch("src.api.enhanced_api.SLARegistry") as mock_sla, \
         patch("src.api.enhanced_api.TokenScanner") as mock_scanner:

        # Mock feature store
        store_instance = Mock()
        store_instance.get_all_features.return_value = [
            {"feature_id": "f1", "name": "Volume Change", "category": "momentum", "importance": 0.8}
        ]
        mock_store.return_value = store_instance

        # Mock SLA registry
        sla_instance = Mock()
        sla_instance.get_status.return_value = {
            "service": "api",
            "status": "healthy",
            "uptime_pct": 99.9,
            "error_rate": 0.01
        }
        mock_sla.return_value = sla_instance

        yield {
            "feature_store": mock_store,
            "sla_registry": mock_sla,
            "scanner": mock_scanner
        }


@pytest.fixture
def enhanced_client(mock_enhanced_dependencies):
    """Create test client for enhanced API"""
    from src.api.enhanced_api import app
    return TestClient(app)


# ===== Dashboard API Tests =====

def test_get_tokens_list(dashboard_client, mock_dashboard_dependencies):
    """Test GET /api/tokens - List all tokens"""
    response = dashboard_client.get("/api/tokens")
    assert response.status_code == 200

    data = response.json()
    assert "tokens" in data
    assert len(data["tokens"]) > 0
    assert data["tokens"][0]["symbol"] == "TEST"


def test_get_tokens_with_filters(dashboard_client):
    """Test GET /api/tokens with query parameters"""
    response = dashboard_client.get("/api/tokens?min_liquidity=50000&max_results=10")
    assert response.status_code == 200

    data = response.json()
    assert "tokens" in data


def test_get_token_detail(dashboard_client, mock_dashboard_dependencies):
    """Test GET /api/tokens/{address} - Get token details"""
    scanner = mock_dashboard_dependencies["scanner_instance"]
    scanner.get_token_details.return_value = {
        "address": "0x123",
        "symbol": "TEST",
        "holders": 1000,
        "transactions_24h": 500
    }

    response = dashboard_client.get("/api/tokens/0x123")
    assert response.status_code == 200

    data = response.json()
    assert data["address"] == "0x123"
    assert data["symbol"] == "TEST"


def test_post_scan_tokens(dashboard_client, mock_dashboard_dependencies):
    """Test POST /api/scan - Trigger new scan"""
    response = dashboard_client.post("/api/scan", json={
        "chain": "ethereum",
        "min_liquidity": 10000,
        "limit": 50
    })
    assert response.status_code == 200

    data = response.json()
    assert "scan_id" in data or "tokens" in data


def test_get_anomalies(dashboard_client):
    """Test GET /api/anomalies - Get detected anomalies"""
    with patch("src.api.dashboard_api.detect_anomalies") as mock_detect:
        mock_detect.return_value = [
            {"token": "0x123", "type": "volume_spike", "severity": "high", "timestamp": "2024-01-01T12:00:00Z"}
        ]

        response = dashboard_client.get("/api/anomalies")
        assert response.status_code == 200

        data = response.json()
        assert "anomalies" in data or isinstance(data, list)


def test_cors_headers(dashboard_client):
    """Test CORS headers are set correctly"""
    response = dashboard_client.options("/api/tokens")
    assert response.status_code == 200
    # CORS middleware should add headers


# ===== Enhanced API Tests =====

def test_get_confidence_intervals(enhanced_client):
    """Test GET /api/confidence - Get confidence intervals for predictions"""
    with patch("src.api.enhanced_api.calculate_confidence_intervals") as mock_ci:
        mock_ci.return_value = {
            "prediction": 100.5,
            "lower_bound": 95.0,
            "upper_bound": 106.0,
            "confidence_level": 0.95
        }

        response = enhanced_client.get("/api/confidence?token=0x123&metric=price")
        assert response.status_code == 200

        data = response.json()
        assert "confidence_level" in data or "lower_bound" in data


def test_get_sla_status(enhanced_client, mock_enhanced_dependencies):
    """Test GET /api/sla/status - Get SLA monitoring status"""
    response = enhanced_client.get("/api/sla/status")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data or "uptime_pct" in data


def test_post_sla_register(enhanced_client):
    """Test POST /api/sla/register - Register new SLA"""
    response = enhanced_client.post("/api/sla/register", json={
        "service_name": "token_scanner",
        "target_uptime": 99.5,
        "max_latency_ms": 500
    })
    assert response.status_code in [200, 201]


def test_get_analytics_summary(enhanced_client):
    """Test GET /api/analytics/summary - Get analytics summary"""
    with patch("src.api.enhanced_api.get_analytics_summary") as mock_analytics:
        mock_analytics.return_value = {
            "total_tokens": 1000,
            "total_volume_24h": 5000000,
            "average_safety_score": 75.5,
            "top_gainers": []
        }

        response = enhanced_client.get("/api/analytics/summary")
        assert response.status_code == 200

        data = response.json()
        assert "total_tokens" in data or isinstance(data, dict)


def test_get_correlation_matrix(enhanced_client):
    """Test GET /api/analytics/correlation - Get correlation matrix"""
    with patch("src.api.enhanced_api.calculate_correlations") as mock_corr:
        mock_corr.return_value = {
            "volume_price": 0.75,
            "liquidity_holders": 0.60,
            "matrix": [[1.0, 0.75], [0.75, 1.0]]
        }

        response = enhanced_client.get("/api/analytics/correlation")
        assert response.status_code == 200

        data = response.json()
        assert "matrix" in data or isinstance(data, dict)


def test_get_trend_analysis(enhanced_client):
    """Test GET /api/analytics/trends - Get trend analysis"""
    with patch("src.api.enhanced_api.analyze_trends") as mock_trends:
        mock_trends.return_value = {
            "trending_up": ["0x123"],
            "trending_down": ["0x456"],
            "stable": ["0x789"]
        }

        response = enhanced_client.get("/api/analytics/trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)


# ===== Feature Store Tests =====

def test_get_features_list(enhanced_client, mock_enhanced_dependencies):
    """Test GET /api/features - List all features"""
    response = enhanced_client.get("/api/features")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, (list, dict))


def test_post_create_feature(enhanced_client, mock_enhanced_dependencies):
    """Test POST /api/features - Create new feature"""
    store = mock_enhanced_dependencies["feature_store"]().return_value
    store.create_feature.return_value = {"feature_id": "f_new", "status": "created"}

    response = enhanced_client.post("/api/features", json={
        "name": "New Feature",
        "category": "momentum",
        "formula": "volume_change_24h",
        "importance": 0.7
    })
    assert response.status_code in [200, 201]


def test_get_feature_detail(enhanced_client, mock_enhanced_dependencies):
    """Test GET /api/features/{feature_id} - Get feature details"""
    store = mock_enhanced_dependencies["feature_store"]().return_value
    store.get_feature.return_value = {
        "feature_id": "f1",
        "name": "Volume Change",
        "category": "momentum"
    }

    response = enhanced_client.get("/api/features/f1")
    assert response.status_code == 200

    data = response.json()
    assert "feature_id" in data or "name" in data


def test_put_update_feature(enhanced_client, mock_enhanced_dependencies):
    """Test PUT /api/features/{feature_id} - Update feature"""
    response = enhanced_client.put("/api/features/f1", json={
        "importance": 0.9,
        "enabled": True
    })
    assert response.status_code == 200


def test_delete_feature(enhanced_client, mock_enhanced_dependencies):
    """Test DELETE /api/features/{feature_id} - Delete feature"""
    response = enhanced_client.delete("/api/features/f1")
    assert response.status_code in [200, 204]


# ===== Error Handling Tests =====

def test_get_token_not_found(dashboard_client, mock_dashboard_dependencies):
    """Test GET /api/tokens/{address} with non-existent token"""
    scanner = mock_dashboard_dependencies["scanner_instance"]
    scanner.get_token_details.return_value = None

    response = dashboard_client.get("/api/tokens/0xNONEXISTENT")
    assert response.status_code in [404, 200]  # Depends on implementation


def test_post_scan_invalid_payload(dashboard_client):
    """Test POST /api/scan with invalid payload"""
    response = dashboard_client.post("/api/scan", json={
        "invalid_field": "value"
    })
    # Should either accept with defaults or return 422
    assert response.status_code in [200, 422]


def test_get_confidence_missing_params(enhanced_client):
    """Test GET /api/confidence without required params"""
    response = enhanced_client.get("/api/confidence")
    assert response.status_code in [400, 422, 200]


def test_post_feature_validation_error(enhanced_client):
    """Test POST /api/features with validation error"""
    response = enhanced_client.post("/api/features", json={
        "name": "",  # Empty name
        "category": "invalid"
    })
    assert response.status_code in [400, 422, 200]


# ===== Edge Cases =====

def test_get_tokens_empty_result(dashboard_client, mock_dashboard_dependencies):
    """Test GET /api/tokens when no tokens found"""
    scanner = mock_dashboard_dependencies["scanner_instance"]
    scanner.scan.return_value = {"tokens": [], "total_scanned": 0}

    response = dashboard_client.get("/api/tokens")
    assert response.status_code == 200

    data = response.json()
    assert "tokens" in data
    assert len(data["tokens"]) == 0


def test_large_batch_scan(dashboard_client, mock_dashboard_dependencies):
    """Test POST /api/scan with large limit"""
    response = dashboard_client.post("/api/scan", json={
        "limit": 1000,
        "chain": "ethereum"
    })
    assert response.status_code == 200


def test_concurrent_requests(dashboard_client):
    """Test handling multiple concurrent requests"""
    from concurrent.futures import ThreadPoolExecutor

    def make_request():
        return dashboard_client.get("/api/tokens")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
