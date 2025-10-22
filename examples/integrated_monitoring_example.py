"""
Example: Integrated Data Drift and Freshness Monitoring

Demonstrates the complete monitoring system with:
- Data drift detection (KL divergence, KS test, PSI)
- Data freshness tracking
- SLA enforcement for critical features
- Comprehensive reporting
"""

import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

from src.monitoring import (
    IntegratedMonitor,
    Baseline,
    FeatureCriticality,
)
from src.core.logging_config import get_logger

logger = get_logger(__name__)


def create_sample_baseline() -> Baseline:
    """Create a sample baseline for demonstration."""
    print("\n" + "="*60)
    print("STEP 1: Creating Baseline")
    print("="*60)
    
    # Generate synthetic historical data
    print("\n📊 Generating baseline from 1000 historical samples...")
    
    features = {
        "gem_score": np.random.normal(60, 15, 1000).clip(0, 100),
        "liquidity_usd": np.random.lognormal(10, 2, 1000),
        "holder_count": np.random.poisson(500, 1000),
        "safety_score": np.random.beta(5, 2, 1000),
        "price_volatility": np.random.gamma(2, 2, 1000),
    }
    
    predictions = np.random.normal(65, 20, 1000).clip(0, 100)
    
    performance_metrics = {
        "accuracy": 0.85,
        "avg_confidence": 0.78,
        "precision": 0.82,
        "recall": 0.79,
    }
    
    # Calculate statistics
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
    
    baseline = Baseline(
        name="production_baseline_v1",
        created_at=datetime.utcnow(),
        feature_distributions=features,
        prediction_distribution=predictions,
        performance_metrics=performance_metrics,
        statistics=statistics,
    )
    
    print(f"\n✅ Baseline created:")
    print(f"   Features: {list(features.keys())}")
    print(f"   Samples: {len(predictions)}")
    print(f"   Performance: accuracy={performance_metrics['accuracy']:.3f}")
    
    return baseline


def setup_monitoring(baseline: Baseline) -> IntegratedMonitor:
    """Set up integrated monitoring with SLAs."""
    print("\n" + "="*60)
    print("STEP 2: Setting up Integrated Monitoring")
    print("="*60)
    
    # Create monitor
    monitor = IntegratedMonitor(name="production_monitor")
    monitor.drift_monitor.set_baseline(baseline)
    
    # Register SLAs for critical features
    print("\n📋 Registering feature SLAs...")
    
    # Critical features - must be fresh
    monitor.register_feature_sla(
        feature_name="gem_score",
        max_age_seconds=300,  # 5 minutes
        criticality=FeatureCriticality.CRITICAL,
    )
    print("   ✓ gem_score: CRITICAL (max age: 5 min)")
    
    monitor.register_feature_sla(
        feature_name="liquidity_usd",
        max_age_seconds=300,  # 5 minutes
        criticality=FeatureCriticality.CRITICAL,
    )
    print("   ✓ liquidity_usd: CRITICAL (max age: 5 min)")
    
    # Important features
    monitor.register_feature_sla(
        feature_name="safety_score",
        max_age_seconds=600,  # 10 minutes
        criticality=FeatureCriticality.IMPORTANT,
    )
    print("   ✓ safety_score: IMPORTANT (max age: 10 min)")
    
    # Standard features
    monitor.register_feature_sla(
        feature_name="holder_count",
        max_age_seconds=3600,  # 1 hour
        criticality=FeatureCriticality.STANDARD,
    )
    print("   ✓ holder_count: STANDARD (max age: 1 hour)")
    
    monitor.register_feature_sla(
        feature_name="price_volatility",
        max_age_seconds=3600,  # 1 hour
        criticality=FeatureCriticality.STANDARD,
    )
    print("   ✓ price_volatility: STANDARD (max age: 1 hour)")
    
    print(f"\n✅ Monitoring configured:")
    print(f"   Critical features: {len(monitor.critical_features)}")
    print(f"   Total SLAs: {len(monitor.feature_slas)}")
    
    return monitor


def scenario_healthy_system(monitor: IntegratedMonitor):
    """Scenario 1: Healthy system with no drift or staleness."""
    print("\n" + "="*60)
    print("SCENARIO 1: Healthy System")
    print("="*60)
    
    print("\n📊 Simulating fresh data with no drift...")
    
    # Generate current data similar to baseline
    current_features = {
        "gem_score": np.random.normal(60, 15, 200).clip(0, 100),
        "liquidity_usd": np.random.lognormal(10, 2, 200),
        "holder_count": np.random.poisson(500, 200),
        "safety_score": np.random.beta(5, 2, 200),
        "price_volatility": np.random.gamma(2, 2, 200),
    }
    
    # All features are fresh (just now)
    feature_timestamps = {
        name: datetime.utcnow() 
        for name in current_features.keys()
    }
    
    # Run monitoring
    report = monitor.monitor_features(current_features, feature_timestamps)
    
    # Display results
    print(f"\n{'='*60}")
    print("MONITORING REPORT")
    print(f"{'='*60}")
    print(f"\nStatus: {monitor._determine_overall_status(report)}")
    print(f"Features monitored: {report.features_monitored}")
    print(f"Features drifted: {report.features_drifted}")
    print(f"Features stale: {report.features_stale}")
    print(f"SLA violations: {report.sla_violations}")
    
    if report.recommendations:
        print("\n💡 Recommendations:")
        for rec in report.recommendations:
            print(f"   - {rec}")
    else:
        print("\n✅ All systems healthy - no recommendations")


def scenario_drift_detected(monitor: IntegratedMonitor):
    """Scenario 2: Drift detected in some features."""
    print("\n" + "="*60)
    print("SCENARIO 2: Drift Detected")
    print("="*60)
    
    print("\n📊 Simulating data with drift in some features...")
    
    # Generate current data with drift
    current_features = {
        "gem_score": np.random.normal(40, 15, 200).clip(0, 100),  # DRIFTED
        "liquidity_usd": np.random.lognormal(8, 2, 200),  # DRIFTED
        "holder_count": np.random.poisson(500, 200),  # No drift
        "safety_score": np.random.beta(5, 2, 200),  # No drift
        "price_volatility": np.random.gamma(2, 2, 200),  # No drift
    }
    
    # All features are fresh
    feature_timestamps = {
        name: datetime.utcnow() 
        for name in current_features.keys()
    }
    
    # Run monitoring
    report = monitor.monitor_features(current_features, feature_timestamps)
    
    # Display results
    print(f"\n{'='*60}")
    print("MONITORING REPORT")
    print(f"{'='*60}")
    print(f"\nStatus: {monitor._determine_overall_status(report)}")
    print(f"Features monitored: {report.features_monitored}")
    print(f"Features drifted: {report.features_drifted} ⚠️")
    print(f"Features stale: {report.features_stale}")
    print(f"SLA violations: {report.sla_violations}")
    
    # Show which features drifted
    print("\n🔴 Features with drift:")
    for name, health in report.feature_health.items():
        if health.drift_detected:
            print(f"   - {name}: {health.drift_severity.value.upper()}")
    
    if report.recommendations:
        print("\n💡 Recommendations:")
        for rec in report.recommendations:
            print(f"   - {rec}")


def scenario_stale_data(monitor: IntegratedMonitor):
    """Scenario 3: Stale data with SLA violations."""
    print("\n" + "="*60)
    print("SCENARIO 3: Stale Data & SLA Violations")
    print("="*60)
    
    print("\n📊 Simulating stale data with SLA violations...")
    
    # Generate current data without drift
    current_features = {
        "gem_score": np.random.normal(60, 15, 200).clip(0, 100),
        "liquidity_usd": np.random.lognormal(10, 2, 200),
        "holder_count": np.random.poisson(500, 200),
        "safety_score": np.random.beta(5, 2, 200),
        "price_volatility": np.random.gamma(2, 2, 200),
    }
    
    # Some features are stale
    now = datetime.utcnow()
    feature_timestamps = {
        "gem_score": now - timedelta(minutes=10),  # 10 min old - VIOLATION (SLA: 5 min)
        "liquidity_usd": now - timedelta(minutes=8),  # 8 min old - VIOLATION (SLA: 5 min)
        "holder_count": now - timedelta(hours=2),  # 2 hours old - VIOLATION (SLA: 1 hour)
        "safety_score": now - timedelta(minutes=5),  # 5 min old - OK (SLA: 10 min)
        "price_volatility": now - timedelta(minutes=30),  # 30 min old - OK (SLA: 1 hour)
    }
    
    # Run monitoring
    report = monitor.monitor_features(current_features, feature_timestamps)
    
    # Display results
    print(f"\n{'='*60}")
    print("MONITORING REPORT")
    print(f"{'='*60}")
    print(f"\nStatus: {monitor._determine_overall_status(report)}")
    print(f"Features monitored: {report.features_monitored}")
    print(f"Features drifted: {report.features_drifted}")
    print(f"Features stale: {report.features_stale} ⚠️")
    print(f"SLA violations: {report.sla_violations} 🔴")
    
    # Show feature health
    print("\n📋 Feature Health:")
    for name, health in report.feature_health.items():
        status = "🔴" if health.sla_violated else "🟢"
        age_str = f"{health.data_age_seconds:.0f}s"
        if health.data_age_seconds >= 60:
            age_str = f"{health.data_age_seconds/60:.1f}m"
        if health.data_age_seconds >= 3600:
            age_str = f"{health.data_age_seconds/3600:.1f}h"
        
        criticality = ""
        if name in monitor.critical_features:
            criticality = " [CRITICAL]"
        
        print(f"   {status} {name}{criticality}: {health.freshness_level.value.upper()} (age: {age_str})")
    
    if report.recommendations:
        print("\n💡 Recommendations:")
        for rec in report.recommendations:
            print(f"   - {rec}")


def scenario_combined_issues(monitor: IntegratedMonitor):
    """Scenario 4: Both drift and staleness."""
    print("\n" + "="*60)
    print("SCENARIO 4: Combined Issues (Drift + Staleness)")
    print("="*60)
    
    print("\n📊 Simulating both drift and stale data...")
    
    # Generate data with drift
    current_features = {
        "gem_score": np.random.normal(45, 18, 200).clip(0, 100),  # DRIFTED
        "liquidity_usd": np.random.lognormal(9, 2.5, 200),  # DRIFTED
        "holder_count": np.random.poisson(300, 200),  # DRIFTED
        "safety_score": np.random.beta(3, 3, 200),  # DRIFTED
        "price_volatility": np.random.gamma(3, 3, 200),  # DRIFTED
    }
    
    # All features are stale
    now = datetime.utcnow()
    feature_timestamps = {
        "gem_score": now - timedelta(minutes=20),  # STALE + VIOLATION
        "liquidity_usd": now - timedelta(minutes=15),  # STALE + VIOLATION
        "holder_count": now - timedelta(hours=3),  # STALE + VIOLATION
        "safety_score": now - timedelta(minutes=25),  # STALE + VIOLATION
        "price_volatility": now - timedelta(hours=2),  # STALE + VIOLATION
    }
    
    # Run monitoring
    report = monitor.monitor_features(current_features, feature_timestamps)
    
    # Display results
    print(f"\n{'='*60}")
    print("MONITORING REPORT - CRITICAL SYSTEM STATE")
    print(f"{'='*60}")
    print(f"\nStatus: {monitor._determine_overall_status(report)} ⚠️⚠️⚠️")
    print(f"Features monitored: {report.features_monitored}")
    print(f"Features drifted: {report.features_drifted} 🔴")
    print(f"Features stale: {report.features_stale} 🔴")
    print(f"SLA violations: {report.sla_violations} 🔴")
    
    # Critical feature violations
    critical_violations = [
        name for name, health in report.feature_health.items()
        if name in monitor.critical_features and health.sla_violated
    ]
    
    if critical_violations:
        print(f"\n⚠️ CRITICAL FEATURE VIOLATIONS: {len(critical_violations)}")
        for name in critical_violations:
            health = report.feature_health[name]
            print(f"   🔴 {name}: {health.drift_severity.value.upper()} drift, "
                  f"{health.freshness_level.value.upper()} ({health.data_age_seconds:.0f}s old)")
    
    if report.recommendations:
        print("\n💡 URGENT RECOMMENDATIONS:")
        for rec in report.recommendations:
            print(f"   ⚠️ {rec}")


def save_monitoring_artifacts(monitor: IntegratedMonitor):
    """Save monitoring artifacts for review."""
    print("\n" + "="*60)
    print("Saving Monitoring Artifacts")
    print("="*60)
    
    artifacts_dir = Path("artifacts/monitoring")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Save latest report
    if monitor.reports:
        latest_report = monitor.reports[-1]
        report_path = artifacts_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        monitor.save_report(latest_report, report_path)
        print(f"\n✅ Report saved: {report_path}")
    
    # Save baseline
    if monitor.drift_monitor.baseline:
        baseline_path = artifacts_dir / "baseline.json"
        monitor.drift_monitor.baseline.save(baseline_path)
        print(f"✅ Baseline saved: {baseline_path}")
    
    # Print summary
    summary = monitor.get_summary()
    print(f"\n📊 Monitoring Summary:")
    print(f"   Total reports: {summary['total_reports']}")
    print(f"   Current status: {summary['current_status']}")
    print(f"   Features monitored: {summary.get('features_monitored', 0)}")
    print(f"   Critical features: {summary['critical_features']}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("INTEGRATED DATA DRIFT & FRESHNESS MONITORING")
    print("="*60)
    
    # Create baseline
    baseline = create_sample_baseline()
    
    # Setup monitoring with SLAs
    monitor = setup_monitoring(baseline)
    
    # Run scenarios
    scenario_healthy_system(monitor)
    scenario_drift_detected(monitor)
    scenario_stale_data(monitor)
    scenario_combined_issues(monitor)
    
    # Save artifacts
    save_monitoring_artifacts(monitor)
    
    print("\n" + "="*60)
    print("✅ All scenarios completed!")
    print("="*60)
    print("\n💡 Next steps:")
    print("   1. Integrate with production data pipeline")
    print("   2. Set up automated monitoring schedule")
    print("   3. Connect to alerting system")
    print("   4. View reports in dashboard UI")
    print("   5. Configure feature SLAs based on business requirements")
