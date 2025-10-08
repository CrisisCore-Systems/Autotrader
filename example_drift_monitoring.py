"""
Example: Drift Monitor MVP Usage

Demonstrates baseline creation, feature drift, prediction drift, and statistical tests.
"""

import numpy as np
from pathlib import Path
from datetime import datetime

from src.monitoring.drift_monitor import DriftMonitor, Baseline, DriftDetector
from src.core.logging_config import get_logger

logger = get_logger(__name__)


def example_baseline_creation():
    """Example 1: Create and save a baseline."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Baseline Creation")
    print("="*60)
    
    # Generate synthetic historical data (replace with real data)
    print("\n📊 Generating baseline from 1000 historical samples...")
    
    baseline_features = {
        "gem_score": np.random.normal(60, 15, 1000).clip(0, 100),
        "liquidity_usd": np.random.lognormal(10, 2, 1000),
        "holder_count": np.random.poisson(500, 1000),
        "safety_score": np.random.beta(5, 2, 1000)
    }
    
    baseline_predictions = np.random.normal(65, 20, 1000).clip(0, 100).tolist()
    
    baseline = Baseline(
        features=baseline_features,
        predictions=baseline_predictions,
        performance_metrics={
            "accuracy": 0.85,
            "avg_confidence": 0.78
        },
        metadata={
            "created_at": datetime.utcnow().isoformat(),
            "model_version": "v1.2.0",
            "sample_size": 1000,
            "data_period": "30 days"
        }
    )
    
    # Save baseline
    baseline_path = Path("artifacts/baselines/example_baseline.json")
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline.save(str(baseline_path))
    
    print(f"\n✅ Baseline created and saved:")
    print(f"   Path: {baseline_path}")
    print(f"   Features: {list(baseline_features.keys())}")
    print(f"   Samples: {len(baseline_predictions)}")
    print(f"   Statistics:")
    for feature, values in baseline_features.items():
        print(f"      {feature}: mean={np.mean(values):.2f}, std={np.std(values):.2f}")
    
    return baseline


def example_feature_drift_no_drift(baseline: Baseline):
    """Example 2: Feature drift detection - No drift scenario."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Feature Drift - No Drift")
    print("="*60)
    
    monitor = DriftMonitor()
    
    # Generate current data with similar distribution
    print("\n📊 Testing with similar distribution (no drift expected)...")
    
    current_features = {
        "gem_score": np.random.normal(60, 15, 200).clip(0, 100),
        "liquidity_usd": np.random.lognormal(10, 2, 200),
        "holder_count": np.random.poisson(500, 200),
        "safety_score": np.random.beta(5, 2, 200)
    }
    
    drift_report = monitor.detect_feature_drift(baseline, current_features)
    
    print(f"\n{'⚠️ DRIFT DETECTED' if drift_report.drift_detected else '✅ NO DRIFT'}")
    print(f"\nFeature analysis:")
    
    for feature, result in drift_report.feature_drift.items():
        status = "🔴 DRIFT" if result.drift_detected else "🟢 STABLE"
        print(f"\n   {feature}: {status}")
        print(f"      KS statistic: {result.ks_statistic:.3f} (p={result.ks_p_value:.4f})")
        print(f"      PSI: {result.psi:.3f} ({'HIGH' if result.psi > 0.2 else 'MEDIUM' if result.psi > 0.1 else 'LOW'})")


def example_feature_drift_with_drift(baseline: Baseline):
    """Example 3: Feature drift detection - Drift detected."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Feature Drift - Drift Detected")
    print("="*60)
    
    monitor = DriftMonitor()
    
    # Generate current data with SHIFTED distributions
    print("\n📊 Testing with shifted distributions (drift expected)...")
    
    current_features = {
        "gem_score": np.random.normal(40, 15, 200).clip(0, 100),  # Lower mean
        "liquidity_usd": np.random.lognormal(8, 2, 200),  # Lower liquidity
        "holder_count": np.random.poisson(300, 200),  # Fewer holders
        "safety_score": np.random.beta(2, 5, 200)  # Lower safety (flipped params)
    }
    
    drift_report = monitor.detect_feature_drift(baseline, current_features)
    
    print(f"\n{'⚠️ DRIFT DETECTED' if drift_report.drift_detected else '✅ NO DRIFT'}")
    
    if drift_report.drift_detected:
        drifted_features = [f for f, r in drift_report.feature_drift.items() if r.drift_detected]
        print(f"\n🔴 {len(drifted_features)}/{len(drift_report.feature_drift)} features drifted:")
        
        for feature in drifted_features:
            result = drift_report.feature_drift[feature]
            print(f"\n   {feature}:")
            print(f"      KS statistic: {result.ks_statistic:.3f} (p={result.ks_p_value:.4f})")
            print(f"      PSI: {result.psi:.3f}")
            
            # Statistical interpretation
            if result.ks_p_value < 0.01:
                print(f"      ⚠️ STRONG evidence of drift (p < 0.01)")
            elif result.ks_p_value < 0.05:
                print(f"      ⚠️ Significant drift detected (p < 0.05)")


def example_prediction_drift(baseline: Baseline):
    """Example 4: Prediction drift detection."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Prediction Drift Detection")
    print("="*60)
    
    monitor = DriftMonitor()
    
    # Test 1: No drift
    print("\n1️⃣ Normal predictions (no drift):")
    normal_predictions = np.random.normal(65, 20, 200).clip(0, 100).tolist()
    
    report1 = monitor.detect_prediction_drift(baseline, normal_predictions)
    print(f"   Drift detected: {report1.drift_detected}")
    print(f"   KS statistic: {report1.prediction_drift.ks_statistic:.3f}")
    print(f"   PSI: {report1.prediction_drift.psi:.3f}")
    
    # Test 2: Drift
    print("\n2️⃣ Shifted predictions (drift expected):")
    drifted_predictions = np.random.normal(45, 25, 200).clip(0, 100).tolist()
    
    report2 = monitor.detect_prediction_drift(baseline, drifted_predictions)
    print(f"   Drift detected: {report2.drift_detected}")
    print(f"   KS statistic: {report2.prediction_drift.ks_statistic:.3f}")
    print(f"   PSI: {report2.prediction_drift.psi:.3f}")
    
    if report2.drift_detected:
        print(f"\n   ⚠️ ACTION REQUIRED:")
        print(f"      - Model predictions have shifted significantly")
        print(f"      - Investigate: data quality, feature drift, concept drift")
        print(f"      - Consider: model retraining, threshold adjustment")


def example_performance_drift(baseline: Baseline):
    """Example 5: Performance drift detection."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Performance Drift Detection")
    print("="*60)
    
    monitor = DriftMonitor()
    
    # Current performance metrics
    current_metrics = {
        "accuracy": 0.70,  # Dropped from 0.85
        "avg_confidence": 0.60  # Dropped from 0.78
    }
    
    print(f"\n📊 Baseline metrics:")
    for key, value in baseline.performance_metrics.items():
        print(f"   {key}: {value:.3f}")
    
    print(f"\n📊 Current metrics:")
    for key, value in current_metrics.items():
        print(f"   {key}: {value:.3f}")
    
    # Detect drift with 10% threshold
    report = monitor.detect_performance_drift(baseline, current_metrics, threshold=0.10)
    
    if report.performance_drift:
        print(f"\n⚠️ PERFORMANCE DRIFT DETECTED")
        for metric, diff in report.performance_drift.items():
            print(f"   {metric}: {diff:+.1%}")
            if abs(diff) > 0.15:
                print(f"      🔴 CRITICAL degradation")
            elif abs(diff) > 0.10:
                print(f"      ⚠️ Significant degradation")


def example_statistical_tests():
    """Example 6: Low-level statistical tests."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Statistical Tests")
    print("="*60)
    
    detector = DriftDetector()
    
    # KS Test
    print("\n1️⃣ Kolmogorov-Smirnov Test:")
    baseline_data = np.random.normal(60, 15, 1000)
    current_data = np.random.normal(50, 15, 200)  # Shifted mean
    
    ks_result = detector.kolmogorov_smirnov_test(baseline_data, current_data)
    print(f"   KS statistic: {ks_result.ks_statistic:.4f}")
    print(f"   P-value: {ks_result.ks_p_value:.4f}")
    print(f"   Drift: {ks_result.drift_detected}")
    print(f"   Interpretation: {'Distributions differ significantly' if ks_result.drift_detected else 'No significant difference'}")
    
    # PSI
    print("\n2️⃣ Population Stability Index:")
    psi_result = detector.population_stability_index(baseline_data, current_data)
    print(f"   PSI: {psi_result.psi:.4f}")
    print(f"   Drift: {psi_result.drift_detected}")
    
    if psi_result.psi < 0.1:
        print(f"   Interpretation: No significant change")
    elif psi_result.psi < 0.2:
        print(f"   Interpretation: Moderate shift (monitor)")
    else:
        print(f"   Interpretation: Significant shift (action needed)")
    
    # Chi-square (categorical)
    print("\n3️⃣ Chi-Square Test (categorical data):")
    baseline_cat = ["A"] * 400 + ["B"] * 400 + ["C"] * 200
    current_cat = ["A"] * 100 + ["B"] * 50 + ["C"] * 50  # Different distribution
    
    chi_result = detector.chi_square_test(baseline_cat, current_cat)
    print(f"   Chi-square: {chi_result.chi_square:.4f}")
    print(f"   P-value: {chi_result.chi_square_p_value:.4f}")
    print(f"   Drift: {chi_result.drift_detected}")


def example_comprehensive_drift_check(baseline: Baseline):
    """Example 7: Comprehensive drift check."""
    print("\n" + "="*60)
    print("EXAMPLE 7: Comprehensive Drift Check")
    print("="*60)
    
    monitor = DriftMonitor()
    
    # Generate current data with mixed drift
    current_features = {
        "gem_score": np.random.normal(50, 15, 200).clip(0, 100),  # Drifted
        "liquidity_usd": np.random.lognormal(10, 2, 200),  # No drift
        "holder_count": np.random.poisson(300, 200),  # Drifted
        "safety_score": np.random.beta(5, 2, 200)  # No drift
    }
    
    current_predictions = np.random.normal(55, 22, 200).clip(0, 100).tolist()
    
    current_performance = {
        "accuracy": 0.82,  # Slight drop
        "avg_confidence": 0.75  # Slight drop
    }
    
    # Full drift detection
    print("\n🔍 Running comprehensive drift analysis...")
    
    report = monitor.detect_drift(
        baseline=baseline,
        current_features=current_features,
        current_predictions=current_predictions,
        current_performance=current_performance
    )
    
    print(f"\n{'='*60}")
    print(f"DRIFT REPORT - {report.timestamp}")
    print(f"{'='*60}")
    
    print(f"\nOverall Status: {'⚠️ DRIFT DETECTED' if report.drift_detected else '✅ NO DRIFT'}")
    
    # Feature drift summary
    print(f"\n📊 Feature Drift:")
    drifted = [f for f, r in report.feature_drift.items() if r.drift_detected]
    stable = [f for f, r in report.feature_drift.items() if not r.drift_detected]
    
    print(f"   Drifted: {len(drifted)}/{len(report.feature_drift)}")
    for feature in drifted:
        result = report.feature_drift[feature]
        print(f"      🔴 {feature}: KS={result.ks_statistic:.3f}, PSI={result.psi:.3f}")
    
    print(f"   Stable: {len(stable)}/{len(report.feature_drift)}")
    for feature in stable:
        print(f"      🟢 {feature}")
    
    # Prediction drift
    print(f"\n🎯 Prediction Drift:")
    pred = report.prediction_drift
    if pred.drift_detected:
        print(f"   🔴 DRIFT: KS={pred.ks_statistic:.3f}, PSI={pred.psi:.3f}")
    else:
        print(f"   🟢 STABLE: KS={pred.ks_statistic:.3f}, PSI={pred.psi:.3f}")
    
    # Performance drift
    if report.performance_drift:
        print(f"\n📉 Performance Drift:")
        for metric, diff in report.performance_drift.items():
            icon = "🔴" if abs(diff) > 0.10 else "🟡"
            print(f"   {icon} {metric}: {diff:+.1%}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if len(drifted) > len(report.feature_drift) / 2:
        print("   ⚠️ CRITICAL: Majority of features drifted - consider model retraining")
    elif drifted:
        print("   ⚠️ Monitor closely - some features drifted")
    
    if pred.drift_detected:
        print("   ⚠️ Prediction distribution shifted - validate model performance")
    
    if report.performance_drift and any(abs(d) > 0.10 for d in report.performance_drift.values()):
        print("   ⚠️ Performance degraded - retrain or tune model")


def example_baseline_reload():
    """Example 8: Load saved baseline."""
    print("\n" + "="*60)
    print("EXAMPLE 8: Load Saved Baseline")
    print("="*60)
    
    baseline_path = "artifacts/baselines/example_baseline.json"
    
    if Path(baseline_path).exists():
        baseline = Baseline.load(baseline_path)
        
        print(f"\n✅ Baseline loaded from {baseline_path}")
        print(f"\nMetadata:")
        for key, value in baseline.metadata.items():
            print(f"   {key}: {value}")
        
        print(f"\nFeatures: {list(baseline.features.keys())}")
        print(f"Predictions: {len(baseline.predictions)} samples")
        
        return baseline
    else:
        print(f"\n❌ Baseline not found at {baseline_path}")
        return None


if __name__ == "__main__":
    print("📊 Drift Monitor MVP Examples")
    print("="*60)
    
    # Create baseline
    baseline = example_baseline_creation()
    
    # Run detection examples
    example_feature_drift_no_drift(baseline)
    example_feature_drift_with_drift(baseline)
    example_prediction_drift(baseline)
    example_performance_drift(baseline)
    example_statistical_tests()
    example_comprehensive_drift_check(baseline)
    example_baseline_reload()
    
    print("\n" + "="*60)
    print("✅ All examples completed!")
    print("="*60)
    print("\n💡 Next steps:")
    print("   1. Replace synthetic data with real production data")
    print("   2. Set up automated daily drift checks")
    print("   3. Integrate with alert engine for notifications")
    print("   4. Create visualizations for drift reports")
