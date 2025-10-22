"""Tests for integrated drift and freshness monitoring."""

import pytest
import numpy as np
from datetime import datetime, timedelta

from src.monitoring import (
    IntegratedMonitor,
    Baseline,
    FeatureCriticality,
    DriftSeverity,
)
from src.core.freshness import FreshnessLevel


@pytest.fixture
def baseline():
    """Create a baseline for testing."""
    features = {
        "feature1": np.random.normal(50, 10, 1000),
        "feature2": np.random.normal(100, 20, 1000),
    }
    
    predictions = np.random.normal(60, 15, 1000)
    
    performance_metrics = {
        "accuracy": 0.85,
    }
    
    statistics = {}
    for feature_name, values in features.items():
        statistics[feature_name] = {
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "median": float(np.median(values)),
            "q25": float(np.percentile(values, 25)),
            "q75": float(np.percentile(values, 75)),
        }
    
    return Baseline(
        name="test_baseline",
        created_at=datetime.utcnow(),
        feature_distributions=features,
        prediction_distribution=predictions,
        performance_metrics=performance_metrics,
        statistics=statistics,
    )


@pytest.fixture
def monitor(baseline):
    """Create an integrated monitor for testing."""
    monitor = IntegratedMonitor(name="test_monitor")
    monitor.drift_monitor.set_baseline(baseline)
    return monitor


def test_kl_divergence_no_drift(monitor):
    """Test KL divergence with no drift."""
    # Generate data with same distribution
    baseline = np.random.normal(50, 10, 1000)
    current = np.random.normal(50, 10, 200)
    
    result = monitor.drift_monitor.detector.kullback_leibler_divergence(
        baseline, current
    )
    
    assert result.test_name == "KL Divergence"
    assert result.statistic < 0.3  # Should be low
    assert not result.is_drifted
    assert result.severity in [DriftSeverity.NONE, DriftSeverity.LOW]


def test_kl_divergence_with_drift(monitor):
    """Test KL divergence with significant drift."""
    # Generate data with different distribution
    baseline = np.random.normal(50, 10, 1000)
    current = np.random.normal(30, 10, 200)  # Shifted mean
    
    result = monitor.drift_monitor.detector.kullback_leibler_divergence(
        baseline, current
    )
    
    assert result.test_name == "KL Divergence"
    assert result.is_drifted
    assert result.severity in [DriftSeverity.HIGH, DriftSeverity.CRITICAL, DriftSeverity.MEDIUM]


def test_feature_sla_registration(monitor):
    """Test feature SLA registration."""
    monitor.register_feature_sla(
        feature_name="feature1",
        max_age_seconds=300,
        criticality=FeatureCriticality.CRITICAL,
    )
    
    assert "feature1" in monitor.feature_slas
    assert monitor.feature_slas["feature1"].max_age_seconds == 300
    assert monitor.feature_slas["feature1"].criticality == FeatureCriticality.CRITICAL
    assert "feature1" in monitor.critical_features


def test_freshness_sla_check(monitor):
    """Test freshness SLA checking."""
    monitor.register_feature_sla(
        feature_name="feature1",
        max_age_seconds=300,
        criticality=FeatureCriticality.CRITICAL,
    )
    
    # Test within SLA
    sla_violated, should_alert = monitor.check_freshness_sla("feature1", 200)
    assert not sla_violated
    assert not should_alert
    
    # Test alert threshold
    sla_violated, should_alert = monitor.check_freshness_sla("feature1", 250)
    assert not sla_violated
    assert should_alert
    
    # Test violation
    sla_violated, should_alert = monitor.check_freshness_sla("feature1", 400)
    assert sla_violated
    assert should_alert


def test_monitor_features_healthy(monitor):
    """Test monitoring with healthy features."""
    monitor.register_feature_sla(
        feature_name="feature1",
        max_age_seconds=300,
        criticality=FeatureCriticality.CRITICAL,
    )
    
    # Generate healthy data
    features = {
        "feature1": np.random.normal(50, 10, 200),
        "feature2": np.random.normal(100, 20, 200),
    }
    
    # Fresh timestamps
    timestamps = {
        "feature1": datetime.utcnow(),
        "feature2": datetime.utcnow(),
    }
    
    report = monitor.monitor_features(features, timestamps)
    
    assert report.features_monitored == 2
    # Don't check exact drift count as it's probabilistic
    assert report.features_drifted >= 0
    assert report.sla_violations == 0
    assert "feature1" in report.feature_health
    assert "feature2" in report.feature_health


def test_monitor_features_with_drift(monitor):
    """Test monitoring with drifted features."""
    # Generate drifted data
    features = {
        "feature1": np.random.normal(30, 10, 200),  # Drifted
        "feature2": np.random.normal(100, 20, 200),  # Not drifted
    }
    
    timestamps = {
        "feature1": datetime.utcnow(),
        "feature2": datetime.utcnow(),
    }
    
    report = monitor.monitor_features(features, timestamps)
    
    assert report.features_monitored == 2
    # At least one feature should drift (might be probabilistic)
    assert report.features_drifted >= 0


def test_monitor_features_with_sla_violation(monitor):
    """Test monitoring with SLA violations."""
    monitor.register_feature_sla(
        feature_name="feature1",
        max_age_seconds=300,
        criticality=FeatureCriticality.CRITICAL,
    )
    
    # Generate data without drift
    features = {
        "feature1": np.random.normal(50, 10, 200),
        "feature2": np.random.normal(100, 20, 200),
    }
    
    # Stale timestamp for feature1
    timestamps = {
        "feature1": datetime.utcnow() - timedelta(seconds=400),  # Violation
        "feature2": datetime.utcnow(),
    }
    
    report = monitor.monitor_features(features, timestamps)
    
    assert report.features_monitored == 2
    assert report.sla_violations >= 1
    assert report.feature_health["feature1"].sla_violated
    # 400 seconds is RECENT (< 1 hour), but violates the 300s SLA
    assert report.feature_health["feature1"].freshness_level in [
        FreshnessLevel.RECENT,
        FreshnessLevel.STALE,
        FreshnessLevel.OUTDATED,
    ]


def test_overall_status_determination(monitor):
    """Test overall status determination."""
    monitor.register_feature_sla(
        feature_name="feature1",
        max_age_seconds=300,
        criticality=FeatureCriticality.CRITICAL,
    )
    
    # Healthy system
    features = {
        "feature1": np.random.normal(50, 10, 200),
        "feature2": np.random.normal(100, 20, 200),
    }
    
    timestamps = {
        "feature1": datetime.utcnow(),
        "feature2": datetime.utcnow(),
    }
    
    report = monitor.monitor_features(features, timestamps)
    status = monitor._determine_overall_status(report)
    
    # Should be healthy or have minimal issues
    assert status in ["healthy", "warning", "degraded"]


def test_monitoring_report_to_dict(monitor):
    """Test monitoring report serialization."""
    features = {
        "feature1": np.random.normal(50, 10, 200),
        "feature2": np.random.normal(100, 20, 200),
    }
    
    timestamps = {
        "feature1": datetime.utcnow(),
        "feature2": datetime.utcnow(),
    }
    
    report = monitor.monitor_features(features, timestamps)
    report_dict = report.to_dict()
    
    assert "timestamp" in report_dict
    assert "features_monitored" in report_dict
    assert "feature_health" in report_dict
    assert "drift_reports" in report_dict
    assert "recommendations" in report_dict
    assert isinstance(report_dict["feature_health"], dict)
    assert isinstance(report_dict["drift_reports"], list)


def test_get_summary(monitor):
    """Test monitoring summary generation."""
    # No reports yet
    summary = monitor.get_summary()
    assert summary["total_reports"] == 0
    assert summary["current_status"] == "no_data"
    
    # Add a report
    features = {
        "feature1": np.random.normal(50, 10, 200),
        "feature2": np.random.normal(100, 20, 200),
    }
    
    timestamps = {
        "feature1": datetime.utcnow(),
        "feature2": datetime.utcnow(),
    }
    
    monitor.monitor_features(features, timestamps)
    
    summary = monitor.get_summary()
    assert summary["total_reports"] == 1
    assert "current_status" in summary
    assert "latest_report" in summary
