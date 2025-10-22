"""
Tests for Trading API endpoints.

Tests the new trading endpoints added for BounceHunter/PennyHunter:
- Market regime detection
- Phase 2 validation progress
- Trading signals queue
- Paper order placement
- Positions tracking
- Orders tracking
- Broker status
- Trade validation
"""

import pytest
from fastapi.testclient import TestClient
from src.api.dashboard_api import app


client = TestClient(app)


def test_get_market_regime():
    """Test GET /api/trading/regime endpoint."""
    response = client.get("/api/trading/regime")
    assert response.status_code == 200
    
    data = response.json()
    assert "regime" in data
    assert "spy_price" in data
    assert "vix_level" in data
    assert "allow_penny_trading" in data
    assert data["regime"] in ["risk_on", "risk_off", "neutral"]


def test_get_phase2_progress():
    """Test GET /api/trading/phase2-progress endpoint."""
    response = client.get("/api/trading/phase2-progress")
    assert response.status_code == 200
    
    data = response.json()
    assert "phase" in data
    assert "status" in data
    assert "trades_completed" in data
    assert "trades_target" in data
    assert "win_rate" in data
    assert "progress_pct" in data
    
    # Validate numeric ranges
    assert 0 <= data["progress_pct"] <= 100
    assert 0 <= data["win_rate"] <= 100
    assert data["trades_target"] == 20  # Phase 2 target


def test_get_trading_signals_default():
    """Test GET /api/trading/signals with default parameters."""
    response = client.get("/api/trading/signals")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # If signals exist, validate structure
    if len(data) > 0:
        signal = data[0]
        assert "ticker" in signal
        assert "quality_score" in signal
        assert "entry_price" in signal
        assert "stop_price" in signal
        assert "target_price" in signal
        assert "risk_reward" in signal
        
        # Quality score should be >= 5.5 (default threshold)
        assert signal["quality_score"] >= 5.5


def test_get_trading_signals_with_filters():
    """Test GET /api/trading/signals with custom quality threshold."""
    response = client.get("/api/trading/signals?min_quality=7.0&include_filters=true")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # All signals should meet quality threshold
    for signal in data:
        assert signal["quality_score"] >= 7.0
        assert "filter_results" in signal


def test_place_paper_order_requires_confirmation():
    """Test POST /api/trading/paper-order requires two-step confirmation."""
    order_data = {
        "ticker": "TEST",
        "quantity": 100,
        "entry_price": 10.0,
        "stop_price": 9.0,
        "target_price": 12.0,
        "confirmed": False
    }
    
    response = client.post("/api/trading/paper-order", json=order_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "confirmation_required"
    assert "order_preview" in data
    
    preview = data["order_preview"]
    assert preview["ticker"] == "TEST"
    assert preview["quantity"] == 100
    assert "risk_amount" in preview
    assert "profit_target" in preview
    assert "risk_reward_ratio" in preview


def test_place_paper_order_with_confirmation():
    """Test POST /api/trading/paper-order with confirmed=True."""
    order_data = {
        "ticker": "TEST",
        "quantity": 100,
        "entry_price": 10.0,
        "stop_price": 9.0,
        "target_price": 12.0,
        "confirmed": True
    }
    
    response = client.post("/api/trading/paper-order", json=order_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert "entry_order_id" in data
    assert "stop_order_id" in data
    assert "target_order_id" in data


def test_place_paper_order_validation():
    """Test POST /api/trading/paper-order validates required fields."""
    # Missing required fields
    order_data = {
        "ticker": "TEST",
        "quantity": 100
    }
    
    response = client.post("/api/trading/paper-order", json=order_data)
    assert response.status_code == 400


def test_get_positions():
    """Test GET /api/trading/positions endpoint."""
    response = client.get("/api/trading/positions")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    
    # If positions exist, validate structure
    if len(data) > 0:
        position = data[0]
        assert "ticker" in position
        assert "shares" in position
        assert "avg_price" in position
        assert "current_price" in position
        assert "market_value" in position
        assert "unrealized_pnl" in position
        assert "unrealized_pnl_pct" in position
        assert "exposure_pct" in position


def test_get_orders_default():
    """Test GET /api/trading/orders endpoint."""
    response = client.get("/api/trading/orders")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)


def test_get_orders_with_filter():
    """Test GET /api/trading/orders with status filter."""
    response = client.get("/api/trading/orders?status_filter=filled&limit=10")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 10
    
    # All orders should be filled
    for order in data:
        assert order["status"].lower() == "filled"


def test_get_broker_status():
    """Test GET /api/trading/broker-status endpoint."""
    response = client.get("/api/trading/broker-status")
    assert response.status_code == 200
    
    data = response.json()
    
    # Should have all broker types
    assert "paper" in data
    assert "alpaca" in data
    assert "questrade" in data
    assert "ibkr" in data
    
    # Paper broker should always be available
    paper = data["paper"]
    assert paper["connected"] is True
    assert paper["status"] == "online"
    assert "account_value" in paper
    assert "cash" in paper


def test_mark_trade_for_validation():
    """Test POST /api/trading/validate endpoint."""
    validation_data = {
        "ticker": "TEST",
        "outcome": "win",
        "pnl": 100.0,
        "notes": "Test trade validation"
    }
    
    response = client.post("/api/trading/validate", json=validation_data)
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "success"
    assert data["ticker"] == "TEST"


def test_mark_trade_validation_requires_fields():
    """Test POST /api/trading/validate validates required fields."""
    # Missing outcome
    validation_data = {
        "ticker": "TEST",
        "pnl": 100.0
    }
    
    response = client.post("/api/trading/validate", json=validation_data)
    assert response.status_code == 400


def test_trading_endpoints_response_times():
    """Test that trading endpoints respond within acceptable time."""
    import time
    
    endpoints = [
        "/api/trading/regime",
        "/api/trading/phase2-progress",
        "/api/trading/signals",
        "/api/trading/positions",
        "/api/trading/orders",
        "/api/trading/broker-status",
    ]
    
    for endpoint in endpoints:
        start = time.time()
        response = client.get(endpoint)
        elapsed = time.time() - start
        
        assert response.status_code == 200
        # Should respond within 5 seconds
        assert elapsed < 5.0, f"{endpoint} took {elapsed:.2f}s"


def test_trading_signals_quality_filtering():
    """Test that signals queue properly filters by quality score."""
    # Get signals with very high threshold
    response = client.get("/api/trading/signals?min_quality=9.0")
    assert response.status_code == 200
    
    high_quality = response.json()
    
    # Get signals with low threshold
    response = client.get("/api/trading/signals?min_quality=5.0")
    assert response.status_code == 200
    
    low_quality = response.json()
    
    # Low threshold should return more or equal signals
    assert len(low_quality) >= len(high_quality)


def test_phase2_progress_status_transitions():
    """Test Phase 2 progress status logic."""
    response = client.get("/api/trading/phase2-progress")
    assert response.status_code == 200
    
    data = response.json()
    status = data["status"]
    trades = data["trades_completed"]
    win_rate = data["win_rate"]
    target = data["trades_target"]
    target_min = data["win_rate_target_min"]
    
    # Validate status logic
    if trades < target:
        assert status == "in_progress"
    elif win_rate >= target_min:
        assert status == "success"
    else:
        assert status == "needs_review"
