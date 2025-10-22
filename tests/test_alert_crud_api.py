"""Tests for Alert CRUD API endpoints."""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from src.api.dashboard_api import app, alert_storage
from src.alerts.models import AlertRuleModel, AlertInboxItem, AlertSeverity, AlertStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_rule():
    """Create a sample alert rule."""
    return {
        "id": "test_rule_1",
        "description": "High GemScore Alert",
        "enabled": True,
        "condition": {
            "metric": "gem_score",
            "operator": "gte",
            "threshold": 70
        },
        "where": {
            "safety_ok": True
        },
        "severity": "high",
        "channels": ["telegram", "slack"],
        "suppression_duration": 3600,
        "tags": ["gemscore", "high-priority"],
        "version": "v2"
    }


@pytest.fixture
def sample_alert():
    """Create a sample alert."""
    return {
        "id": "alert_1",
        "rule_id": "test_rule_1",
        "token_symbol": "ETH",
        "message": "GemScore threshold exceeded",
        "severity": "high",
        "status": "pending",
        "metadata": {"score": 75, "confidence": 0.85},
        "labels": ["urgent"],
        "provenance_links": {
            "coingecko": "https://coingecko.com/eth"
        }
    }


@pytest.fixture(autouse=True)
def cleanup_db():
    """Clean up database after each test."""
    yield
    # Clean up test data
    try:
        # Clean up alerts first (foreign key constraint)
        for alert in alert_storage.list_alerts(limit=1000):
            alert_storage.conn.execute("DELETE FROM alerts_inbox WHERE id = ?", (alert.id,))
        alert_storage.conn.commit()
        
        # Clean up rules
        for rule in alert_storage.list_rules():
            alert_storage.delete_rule(rule.id)
    except:
        pass


def test_create_alert_rule(client, sample_rule):
    """Test creating a new alert rule."""
    response = client.post("/api/alerts/rules", json=sample_rule)
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == sample_rule["id"]
    assert data["description"] == sample_rule["description"]
    assert data["severity"] == sample_rule["severity"]
    assert data["enabled"] is True


def test_list_alert_rules(client, sample_rule):
    """Test listing alert rules."""
    # Create a rule first
    client.post("/api/alerts/rules", json=sample_rule)
    
    response = client.get("/api/alerts/rules")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) >= 1
    assert any(r["id"] == sample_rule["id"] for r in data)


def test_get_alert_rule(client, sample_rule):
    """Test getting a specific alert rule."""
    # Create a rule first
    client.post("/api/alerts/rules", json=sample_rule)
    
    response = client.get(f"/api/alerts/rules/{sample_rule['id']}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == sample_rule["id"]
    assert data["description"] == sample_rule["description"]


def test_get_nonexistent_alert_rule(client):
    """Test getting a non-existent alert rule."""
    response = client.get("/api/alerts/rules/nonexistent_rule")
    assert response.status_code == 404


def test_update_alert_rule(client, sample_rule):
    """Test updating an alert rule."""
    # Create a rule first
    client.post("/api/alerts/rules", json=sample_rule)
    
    updates = {
        "description": "Updated description",
        "enabled": False,
        "severity": "critical"
    }
    
    response = client.put(f"/api/alerts/rules/{sample_rule['id']}", json=updates)
    assert response.status_code == 200
    
    data = response.json()
    assert data["description"] == updates["description"]
    assert data["enabled"] is False
    assert data["severity"] == updates["severity"]


def test_update_nonexistent_alert_rule(client):
    """Test updating a non-existent alert rule."""
    updates = {"description": "New description"}
    response = client.put("/api/alerts/rules/nonexistent_rule", json=updates)
    assert response.status_code == 404


def test_delete_alert_rule(client, sample_rule):
    """Test deleting an alert rule."""
    # Create a rule first
    client.post("/api/alerts/rules", json=sample_rule)
    
    response = client.delete(f"/api/alerts/rules/{sample_rule['id']}")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "deleted"
    assert data["rule_id"] == sample_rule["id"]
    
    # Verify it's gone
    response = client.get(f"/api/alerts/rules/{sample_rule['id']}")
    assert response.status_code == 404


def test_delete_nonexistent_alert_rule(client):
    """Test deleting a non-existent alert rule."""
    response = client.delete("/api/alerts/rules/nonexistent_rule")
    assert response.status_code == 404


def test_list_inbox_alerts(client, sample_rule, sample_alert):
    """Test listing inbox alerts."""
    # Create rule and alert
    client.post("/api/alerts/rules", json=sample_rule)
    alert_storage.create_alert(AlertInboxItem.from_dict(sample_alert))
    
    response = client.get("/api/alerts/inbox")
    assert response.status_code == 200
    
    data = response.json()
    assert "alerts" in data
    assert "total" in data
    assert len(data["alerts"]) >= 1


def test_list_inbox_alerts_with_filters(client, sample_rule, sample_alert):
    """Test listing inbox alerts with filters."""
    # Create rule and alert
    client.post("/api/alerts/rules", json=sample_rule)
    alert_storage.create_alert(AlertInboxItem.from_dict(sample_alert))
    
    # Filter by status
    response = client.get("/api/alerts/inbox?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert all(alert["status"] == "pending" for alert in data["alerts"])
    
    # Filter by severity
    response = client.get("/api/alerts/inbox?severity=high")
    assert response.status_code == 200
    data = response.json()
    assert all(alert["severity"] == "high" for alert in data["alerts"])


def test_acknowledge_alert(client, sample_rule, sample_alert):
    """Test acknowledging an alert."""
    # Create rule and alert
    client.post("/api/alerts/rules", json=sample_rule)
    alert_storage.create_alert(AlertInboxItem.from_dict(sample_alert))
    
    response = client.post(f"/api/alerts/inbox/{sample_alert['id']}/acknowledge")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "acknowledged"
    assert data["acknowledged_at"] is not None


def test_acknowledge_nonexistent_alert(client):
    """Test acknowledging a non-existent alert."""
    response = client.post("/api/alerts/inbox/nonexistent_alert/acknowledge")
    assert response.status_code == 404


def test_snooze_alert(client, sample_rule, sample_alert):
    """Test snoozing an alert."""
    # Create rule and alert
    client.post("/api/alerts/rules", json=sample_rule)
    alert_storage.create_alert(AlertInboxItem.from_dict(sample_alert))
    
    response = client.post(
        f"/api/alerts/inbox/{sample_alert['id']}/snooze?duration_seconds=1800"
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "snoozed"
    assert data["snoozed_until"] is not None


def test_update_alert_labels(client, sample_rule, sample_alert):
    """Test updating alert labels."""
    # Create rule and alert
    client.post("/api/alerts/rules", json=sample_rule)
    alert_storage.create_alert(AlertInboxItem.from_dict(sample_alert))
    
    new_labels = ["reviewed", "escalated", "high-priority"]
    response = client.put(
        f"/api/alerts/inbox/{sample_alert['id']}/labels",
        json=new_labels
    )
    assert response.status_code == 200
    
    data = response.json()
    assert set(data["labels"]) == set(new_labels)


def test_get_delivery_analytics(client):
    """Test getting delivery analytics."""
    response = client.get("/api/alerts/analytics/delivery")
    assert response.status_code == 200
    
    data = response.json()
    assert "average_delivery_latency_ms" in data
    assert "total_deliveries" in data
    assert "dedupe_rate" in data


def test_get_alert_performance(client, sample_rule, sample_alert):
    """Test getting alert performance metrics."""
    # Create rule and alert
    client.post("/api/alerts/rules", json=sample_rule)
    alert_storage.create_alert(AlertInboxItem.from_dict(sample_alert))
    
    response = client.get("/api/alerts/analytics/performance")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_alerts" in data
    assert "alerts_by_severity" in data
    assert "alerts_by_rule" in data
    assert "acknowledgement_rate" in data
    assert "average_delivery_latency_ms" in data
    assert "dedupe_rate" in data
    assert data["total_alerts"] >= 1


def test_list_enabled_rules_only(client, sample_rule):
    """Test listing only enabled rules."""
    # Create enabled rule
    client.post("/api/alerts/rules", json=sample_rule)
    
    # Create disabled rule
    disabled_rule = sample_rule.copy()
    disabled_rule["id"] = "disabled_rule"
    disabled_rule["enabled"] = False
    client.post("/api/alerts/rules", json=disabled_rule)
    
    # List all rules
    response = client.get("/api/alerts/rules")
    assert response.status_code == 200
    all_rules = response.json()
    assert len(all_rules) >= 2
    
    # List only enabled rules
    response = client.get("/api/alerts/rules?enabled_only=true")
    assert response.status_code == 200
    enabled_rules = response.json()
    assert all(rule["enabled"] for rule in enabled_rules)
    assert len(enabled_rules) < len(all_rules)


def test_create_rule_auto_id(client):
    """Test creating a rule without ID (auto-generated)."""
    rule_data = {
        "description": "Auto ID Rule",
        "severity": "info",
        "channels": ["email"],
        "condition": {
            "metric": "confidence",
            "operator": "gte",
            "threshold": 0.8
        }
    }
    
    response = client.post("/api/alerts/rules", json=rule_data)
    assert response.status_code == 200
    
    data = response.json()
    assert "id" in data
    assert data["id"].startswith("rule_")


def test_pagination(client, sample_rule, sample_alert):
    """Test inbox alert pagination."""
    # Create rule
    client.post("/api/alerts/rules", json=sample_rule)
    
    # Create multiple alerts
    for i in range(5):
        alert = sample_alert.copy()
        alert["id"] = f"alert_{i}"
        alert_storage.create_alert(AlertInboxItem.from_dict(alert))
    
    # Test first page
    response = client.get("/api/alerts/inbox?limit=2&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["alerts"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0
    
    # Test second page
    response = client.get("/api/alerts/inbox?limit=2&offset=2")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 2
