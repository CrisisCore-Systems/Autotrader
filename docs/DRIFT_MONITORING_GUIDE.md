# Drift Monitoring MVP - Comprehensive Guide

## 📊 Overview

Drift Monitoring MVP provides statistical methods to detect data and model drift:

- **Feature Drift Detection**: Monitor input feature distributions
- **Prediction Drift Detection**: Track model output distribution shifts
- **Performance Drift Detection**: Monitor accuracy/confidence degradation
- **Statistical Tests**: KS test, PSI, Chi-square
- **Baseline Management**: Save/load reference distributions

## 📚 Table of Contents

- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
- [Statistical Methods](#statistical-methods)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Integration](#integration)

## 🚀 Quick Start

### Basic Drift Detection

```python
from src.monitoring.drift_monitor import DriftMonitor, Baseline
import numpy as np

# Create monitor
monitor = DriftMonitor()

# Create baseline from historical data
baseline_features = {
    "gem_score": np.random.normal(60, 15, 1000),
    "liquidity_usd": np.random.lognormal(10, 2, 1000)
}
baseline_predictions = np.random.normal(65, 20, 1000).tolist()

baseline = Baseline(
    features=baseline_features,
    predictions=baseline_predictions
)

# Save baseline
baseline.save("artifacts/baselines/baseline.json")

# Detect drift on new data
current_features = {
    "gem_score": np.random.normal(50, 15, 200),  # Shifted mean
    "liquidity_usd": np.random.lognormal(9, 2, 200)
}

drift_report = monitor.detect_feature_drift(baseline, current_features)

if drift_report.drift_detected:
    print("⚠️ Drift detected!")
    for feature, result in drift_report.feature_drift.items():
        if result.drift_detected:
            print(f"  {feature}: KS={result.ks_statistic:.3f}, PSI={result.psi:.3f}")
```

## 🧠 Core Concepts

### 1. Baseline

A baseline captures reference distributions for comparison:

```python
from src.monitoring.drift_monitor import Baseline

baseline = Baseline(
    features={
        "feature1": [1.0, 2.0, 3.0, ...],  # numpy array or list
        "feature2": [10, 20, 30, ...]
    },
    predictions=[0.5, 0.7, 0.9, ...],  # Model outputs
    performance_metrics={
        "accuracy": 0.85,
        "precision": 0.82,
        "recall": 0.88
    },
    metadata={
        "created_at": "2024-01-15",
        "model_version": "v1.2",
        "sample_size": 1000
    }
)

# Persist baseline
baseline.save("baselines/production_baseline.json")

# Load later
baseline = Baseline.load("baselines/production_baseline.json")
```

### 2. Drift Types

#### Feature Drift

Input feature distributions change:

```python
# Example: Market conditions shift
# Baseline: gem_score ~ N(60, 15)
# Current:  gem_score ~ N(40, 15)  <- Lower mean

drift_report = monitor.detect_feature_drift(baseline, current_features)
```

#### Prediction Drift

Model output distribution shifts:

```python
# Example: Model behavior changes
# Baseline: predictions ~ N(65, 20)
# Current:  predictions ~ N(45, 25)  <- Different distribution

drift_report = monitor.detect_prediction_drift(baseline, current_predictions)
```

#### Performance Drift

Model accuracy/confidence degrades:

```python
# Example: Model performance drops
current_metrics = {
    "accuracy": 0.70,  # Was 0.85
    "confidence": 0.55  # Was 0.75
}

drift_report = monitor.detect_performance_drift(baseline, current_metrics)
```

### 3. Statistical Tests

Three complementary methods:

| Test | Use Case | Range | Threshold |
|------|----------|-------|-----------|
| **KS Test** | Continuous features | p-value: 0-1 | p < 0.05 = drift |
| **PSI** | Distribution shift | 0-∞ | >0.2 = high drift |
| **Chi-square** | Categorical features | p-value: 0-1 | p < 0.05 = drift |

## 📐 Statistical Methods

### Kolmogorov-Smirnov (KS) Test

Tests if two continuous distributions differ:

```python
from src.monitoring.drift_monitor import DriftDetector

detector = DriftDetector()

baseline_data = np.random.normal(60, 15, 1000)
current_data = np.random.normal(50, 15, 200)  # Shifted

result = detector.kolmogorov_smirnov_test(baseline_data, current_data)

print(f"KS Statistic: {result.ks_statistic:.3f}")
print(f"P-value: {result.ks_p_value:.4f}")
print(f"Drift: {result.drift_detected}")
```

**Interpretation**:
- KS statistic: Maximum distance between CDFs (0 to 1)
- P-value < 0.05: Significant difference (drift detected)
- Higher KS statistic = more drift

### Population Stability Index (PSI)

Measures distribution shift using binning:

```python
result = detector.population_stability_index(baseline_data, current_data)

print(f"PSI: {result.psi:.3f}")
print(f"Drift: {result.drift_detected}")
```

**PSI Thresholds**:
- < 0.1: No significant change
- 0.1 - 0.2: Moderate shift (monitor)
- > 0.2: Significant shift (action needed)

**Formula**:
```
PSI = Σ (current_pct - baseline_pct) * ln(current_pct / baseline_pct)
```

### Chi-Square Test

For categorical features:

```python
baseline_categorical = ["A", "B", "A", "C", "B", ...]
current_categorical = ["A", "A", "C", "C", "A", ...]

result = detector.chi_square_test(baseline_categorical, current_categorical)

print(f"Chi-square: {result.chi_square:.3f}")
print(f"P-value: {result.chi_square_p_value:.4f}")
```

## 📖 API Reference

### DriftDetector

Low-level statistical tests:

```python
from src.monitoring.drift_monitor import DriftDetector

detector = DriftDetector(
    ks_threshold=0.05,      # KS test p-value threshold
    psi_threshold=0.2,      # PSI threshold
    chi_square_threshold=0.05  # Chi-square p-value threshold
)

# Individual tests
ks_result = detector.kolmogorov_smirnov_test(baseline, current)
psi_result = detector.population_stability_index(baseline, current)
chi_result = detector.chi_square_test(baseline_cat, current_cat)
```

### DriftMonitor

High-level drift detection:

```python
from src.monitoring.drift_monitor import DriftMonitor

monitor = DriftMonitor(
    ks_threshold=0.05,
    psi_threshold=0.2
)

# Feature drift
feature_report = monitor.detect_feature_drift(
    baseline: Baseline,
    current_features: Dict[str, np.ndarray]
) -> DriftReport

# Prediction drift
pred_report = monitor.detect_prediction_drift(
    baseline: Baseline,
    current_predictions: List[float]
) -> DriftReport

# Performance drift
perf_report = monitor.detect_performance_drift(
    baseline: Baseline,
    current_metrics: Dict[str, float],
    threshold: float = 0.1
) -> DriftReport

# Comprehensive drift
full_report = monitor.detect_drift(
    baseline: Baseline,
    current_features: Dict[str, np.ndarray],
    current_predictions: Optional[List[float]] = None,
    current_performance: Optional[Dict[str, float]] = None
) -> DriftReport
```

### DriftReport

Result object:

```python
class DriftReport:
    timestamp: datetime
    drift_detected: bool
    feature_drift: Dict[str, DriftStatistics]
    prediction_drift: Optional[DriftStatistics]
    performance_drift: Optional[Dict[str, float]]
    
    def to_dict(self) -> Dict
    def summary(self) -> str
```

### DriftStatistics

Per-feature statistics:

```python
class DriftStatistics:
    feature_name: str
    drift_detected: bool
    ks_statistic: float
    ks_p_value: float
    psi: float
    chi_square: Optional[float]
    chi_square_p_value: Optional[float]
```

## 💡 Examples

### Example 1: Complete Monitoring Pipeline

```python
from src.monitoring.drift_monitor import DriftMonitor, Baseline
import numpy as np
from pathlib import Path

# 1. Create baseline from production data
print("Creating baseline...")
historical_data = load_production_data(days=30)

baseline = Baseline(
    features={
        "gem_score": historical_data["gem_score"].values,
        "liquidity_usd": historical_data["liquidity_usd"].values,
        "holder_count": historical_data["holder_count"].values,
        "safety_score": historical_data["safety_score"].values
    },
    predictions=historical_data["predictions"].tolist(),
    performance_metrics={
        "accuracy": 0.85,
        "avg_confidence": 0.78
    },
    metadata={
        "created_at": datetime.utcnow().isoformat(),
        "sample_size": len(historical_data),
        "model_version": "v1.2.0"
    }
)

baseline_path = Path("artifacts/baselines/production_baseline.json")
baseline.save(str(baseline_path))
print(f"✅ Baseline saved: {baseline_path}")

# 2. Daily drift check
print("\nRunning daily drift check...")
monitor = DriftMonitor()
today_data = load_production_data(days=1)

current_features = {
    "gem_score": today_data["gem_score"].values,
    "liquidity_usd": today_data["liquidity_usd"].values,
    "holder_count": today_data["holder_count"].values,
    "safety_score": today_data["safety_score"].values
}

current_predictions = today_data["predictions"].tolist()

drift_report = monitor.detect_drift(
    baseline=baseline,
    current_features=current_features,
    current_predictions=current_predictions
)

# 3. Handle drift
if drift_report.drift_detected:
    print("⚠️ DRIFT DETECTED")
    
    # Log details
    for feature, stats in drift_report.feature_drift.items():
        if stats.drift_detected:
            logger.warning(
                "feature_drift_detected",
                feature=feature,
                ks_statistic=stats.ks_statistic,
                psi=stats.psi
            )
    
    # Send alert
    alert_manager.evaluate({
        "drift_ks_statistic": max(s.ks_statistic for s in drift_report.feature_drift.values()),
        "drift_psi_score": max(s.psi for s in drift_report.feature_drift.values())
    })
    
    # Trigger retraining pipeline
    if should_retrain(drift_report):
        trigger_retraining(drift_report)
else:
    print("✅ No drift detected")
```

### Example 2: Automated Baseline Updates

```python
from datetime import datetime, timedelta

class BaselineManager:
    def __init__(self, baseline_path: str, update_interval_days: int = 30):
        self.baseline_path = baseline_path
        self.update_interval_days = update_interval_days
        self.baseline = Baseline.load(baseline_path)
        
    def should_update_baseline(self) -> bool:
        """Check if baseline needs updating."""
        created_at = datetime.fromisoformat(self.baseline.metadata["created_at"])
        age_days = (datetime.utcnow() - created_at).days
        return age_days >= self.update_interval_days
    
    def update_baseline(self, new_data: Dict):
        """Update baseline with recent production data."""
        new_baseline = Baseline(
            features={
                k: np.array(v) for k, v in new_data["features"].items()
            },
            predictions=new_data["predictions"],
            performance_metrics=new_data["performance"],
            metadata={
                "created_at": datetime.utcnow().isoformat(),
                "sample_size": len(new_data["predictions"]),
                "previous_baseline": self.baseline_path
            }
        )
        
        # Archive old baseline
        archive_path = self.baseline_path.replace(".json", f"_archived_{datetime.utcnow().date()}.json")
        self.baseline.save(archive_path)
        
        # Save new baseline
        new_baseline.save(self.baseline_path)
        self.baseline = new_baseline
        
        logger.info("baseline_updated", path=self.baseline_path)

# Usage
manager = BaselineManager("artifacts/baselines/production_baseline.json")

if manager.should_update_baseline():
    recent_data = load_production_data(days=30)
    manager.update_baseline(recent_data)
```

### Example 3: Multi-Model Drift Monitoring

```python
class MultiModelDriftMonitor:
    def __init__(self):
        self.monitor = DriftMonitor()
        self.baselines = {}
        self.drift_history = []
    
    def add_model(self, model_name: str, baseline_path: str):
        """Register a model for monitoring."""
        self.baselines[model_name] = Baseline.load(baseline_path)
    
    def check_all_models(self, current_data: Dict[str, Dict]) -> Dict[str, DriftReport]:
        """Check drift for all registered models."""
        reports = {}
        
        for model_name, baseline in self.baselines.items():
            data = current_data.get(model_name)
            if data:
                report = self.monitor.detect_drift(
                    baseline=baseline,
                    current_features=data["features"],
                    current_predictions=data["predictions"]
                )
                reports[model_name] = report
                
                if report.drift_detected:
                    logger.warning(
                        "model_drift_detected",
                        model=model_name,
                        features_drifted=sum(1 for s in report.feature_drift.values() if s.drift_detected)
                    )
        
        return reports
    
    def get_drift_summary(self) -> str:
        """Generate summary of drift status."""
        summary = []
        for model_name, baseline in self.baselines.items():
            summary.append(f"{model_name}: Last checked {baseline.metadata.get('last_check', 'N/A')}")
        return "\n".join(summary)

# Usage
multi_monitor = MultiModelDriftMonitor()
multi_monitor.add_model("gem_scorer", "baselines/gem_scorer_baseline.json")
multi_monitor.add_model("safety_analyzer", "baselines/safety_baseline.json")

current_data = {
    "gem_scorer": {"features": {...}, "predictions": [...]},
    "safety_analyzer": {"features": {...}, "predictions": [...]}
}

reports = multi_monitor.check_all_models(current_data)
```

### Example 4: Drift-Triggered Retraining

```python
def should_retrain(drift_report: DriftReport) -> bool:
    """Determine if model should be retrained based on drift."""
    
    # Count features with drift
    drifted_features = sum(
        1 for stats in drift_report.feature_drift.values()
        if stats.drift_detected
    )
    
    # High PSI indicates significant shift
    max_psi = max(
        stats.psi for stats in drift_report.feature_drift.values()
    )
    
    # Prediction drift is concerning
    prediction_drift = (
        drift_report.prediction_drift and
        drift_report.prediction_drift.drift_detected
    )
    
    # Retrain if:
    # - More than 50% of features drifted
    # - Any feature has PSI > 0.3
    # - Prediction distribution shifted
    return (
        drifted_features > len(drift_report.feature_drift) / 2 or
        max_psi > 0.3 or
        prediction_drift
    )

# Automated retraining pipeline
if should_retrain(drift_report):
    logger.info("triggering_retraining", reason="drift_detected")
    
    # 1. Prepare retraining dataset
    training_data = prepare_retraining_data(days=90)
    
    # 2. Retrain model
    new_model = retrain_model(training_data)
    
    # 3. Validate new model
    validation_metrics = validate_model(new_model)
    
    # 4. Deploy if better
    if validation_metrics["accuracy"] > baseline.performance_metrics["accuracy"]:
        deploy_model(new_model)
        
        # 5. Create new baseline
        new_baseline = create_baseline_from_model(new_model)
        new_baseline.save("baselines/production_baseline.json")
```

## 🎯 Best Practices

### 1. Baseline Creation

✅ **DO**:
```python
# Use sufficient data (1000+ samples)
baseline = Baseline(
    features={k: v for k, v in data.items()},
    predictions=predictions,
    metadata={
        "sample_size": len(predictions),
        "time_period": "30 days",
        "data_quality_checked": True
    }
)

# Version your baselines
baseline.save(f"baselines/baseline_{version}_{date}.json")
```

❌ **DON'T**:
```python
# Too few samples
baseline = Baseline(features={...}, predictions=[1, 2, 3])

# No metadata
baseline = Baseline(features={...}, predictions=[...])
```

### 2. Monitoring Frequency

```python
# Different frequencies for different drift types

# Feature drift: Daily
schedule_daily(lambda: monitor.detect_feature_drift(...))

# Prediction drift: Hourly (if high volume)
schedule_hourly(lambda: monitor.detect_prediction_drift(...))

# Performance drift: After each batch
after_batch(lambda: monitor.detect_performance_drift(...))
```

### 3. Threshold Tuning

```python
# Start conservative, adjust based on false positive rate
monitor = DriftMonitor(
    ks_threshold=0.05,  # Standard
    psi_threshold=0.2   # Standard
)

# For sensitive applications
sensitive_monitor = DriftMonitor(
    ks_threshold=0.01,  # Stricter
    psi_threshold=0.15
)

# For exploratory analysis
exploratory_monitor = DriftMonitor(
    ks_threshold=0.10,  # More lenient
    psi_threshold=0.25
)
```

### 4. Handling Drift

```python
def handle_drift(drift_report: DriftReport):
    """Comprehensive drift handling."""
    
    if not drift_report.drift_detected:
        return
    
    # 1. Log detailed information
    logger.warning("drift_detected", report=drift_report.to_dict())
    
    # 2. Alert stakeholders
    send_drift_alert(drift_report)
    
    # 3. Analyze root cause
    root_cause = analyze_drift_cause(drift_report)
    
    # 4. Take action based on severity
    severity = calculate_drift_severity(drift_report)
    
    if severity == "critical":
        # Immediate action: disable model or switch to fallback
        switch_to_fallback_model()
    elif severity == "high":
        # Trigger retraining
        queue_retraining_job(priority="high")
    elif severity == "medium":
        # Monitor closely
        increase_monitoring_frequency()
    else:
        # Just log and track
        track_drift_trend(drift_report)
```

### 5. Visualization

```python
import matplotlib.pyplot as plt

def visualize_drift_report(drift_report: DriftReport):
    """Create comprehensive drift visualization."""
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # KS statistics
    features = list(drift_report.feature_drift.keys())
    ks_stats = [drift_report.feature_drift[f].ks_statistic for f in features]
    colors = ['red' if drift_report.feature_drift[f].drift_detected else 'green' 
              for f in features]
    
    axes[0, 0].bar(features, ks_stats, color=colors, alpha=0.7)
    axes[0, 0].axhline(y=0.1, color='orange', linestyle='--')
    axes[0, 0].set_title('KS Test Results')
    axes[0, 0].set_ylabel('KS Statistic')
    
    # PSI scores
    psi_scores = [drift_report.feature_drift[f].psi for f in features]
    axes[0, 1].bar(features, psi_scores, color=colors, alpha=0.7)
    axes[0, 1].axhline(y=0.1, color='yellow', linestyle='--')
    axes[0, 1].axhline(y=0.2, color='orange', linestyle='--')
    axes[0, 1].set_title('Population Stability Index')
    axes[0, 1].set_ylabel('PSI Score')
    
    # Distribution comparison (example feature)
    # Add your distribution plots here
    
    plt.tight_layout()
    plt.savefig('drift_report.png')
    return fig
```

## 🔗 Integration

### With Alert Engine v2

```python
from src.services.alerting_v2 import AlertManager, AlertCondition, CompoundCondition

# Create drift alerts
drift_alert_condition = CompoundCondition(
    operator="OR",
    conditions=[
        AlertCondition("drift_ks_statistic", "gt", 0.3),
        AlertCondition("drift_psi_score", "gt", 0.2)
    ]
)

drift_rule = AlertRule(
    id="feature_drift",
    condition=drift_alert_condition,
    severity="high",
    message="Feature drift detected: KS={drift_ks_statistic:.3f}, PSI={drift_psi_score:.3f}"
)

alert_manager.add_rule(drift_rule)

# Evaluate on drift detection
drift_metrics = extract_drift_metrics(drift_report)
alerts = alert_manager.evaluate(drift_metrics)
```

### With Prometheus Metrics

```python
from src.core.metrics import Gauge

# Drift metrics
DRIFT_SCORE = Gauge(
    'drift_score',
    'Current drift score',
    ['feature', 'metric_type']
)

DRIFT_DETECTION = Gauge(
    'drift_detected',
    'Whether drift is detected (0/1)',
    ['model']
)

# Update metrics
for feature, stats in drift_report.feature_drift.items():
    DRIFT_SCORE.labels(feature=feature, metric_type='ks').set(stats.ks_statistic)
    DRIFT_SCORE.labels(feature=feature, metric_type='psi').set(stats.psi)

DRIFT_DETECTION.labels(model='gem_scorer').set(1 if drift_report.drift_detected else 0)
```

### With MLflow

```python
import mlflow

# Log drift metrics
with mlflow.start_run():
    # Log drift statistics
    for feature, stats in drift_report.feature_drift.items():
        mlflow.log_metric(f"drift_ks_{feature}", stats.ks_statistic)
        mlflow.log_metric(f"drift_psi_{feature}", stats.psi)
    
    # Log drift report
    mlflow.log_dict(drift_report.to_dict(), "drift_report.json")
    
    # Log baseline
    mlflow.log_artifact(baseline_path)
```

## 📊 Metrics

Drift Monitor exposes Prometheus metrics:

```
# Drift detections
drift_detections_total{model="gem_scorer", type="feature"} 12

# Current drift scores
drift_score{feature="gem_score", metric="ks"} 0.245
drift_score{feature="gem_score", metric="psi"} 0.18

# Prediction distribution
prediction_distribution{model="gem_scorer", percentile="p50"} 65.2
```

## 🐛 Troubleshooting

### No Drift Detected (False Negative)

```python
# Check thresholds
monitor = DriftMonitor(
    ks_threshold=0.01,  # More sensitive
    psi_threshold=0.10
)

# Verify baseline quality
print(f"Baseline samples: {len(baseline.predictions)}")
print(f"Current samples: {len(current_predictions)}")
```

### Too Many Alerts (False Positive)

```python
# Adjust thresholds
monitor = DriftMonitor(
    ks_threshold=0.10,  # Less sensitive
    psi_threshold=0.25
)

# Add minimum sample size
if len(current_predictions) < 100:
    print("Insufficient samples for reliable drift detection")
    return
```

### Baseline Issues

```python
# Validate baseline
def validate_baseline(baseline: Baseline) -> bool:
    # Check sample size
    if len(baseline.predictions) < 1000:
        print("Warning: Small baseline size")
        return False
    
    # Check feature completeness
    required_features = ["gem_score", "liquidity_usd", "safety_score"]
    missing = set(required_features) - set(baseline.features.keys())
    if missing:
        print(f"Missing features: {missing}")
        return False
    
    # Check for NaN/inf
    for feature, values in baseline.features.items():
        if np.any(np.isnan(values)) or np.any(np.isinf(values)):
            print(f"Invalid values in {feature}")
            return False
    
    return True
```

## 📚 Additional Resources

- [Alert Engine v2 Guide](ALERTING_V2_GUIDE.md)
- [Observability Guide](OBSERVABILITY_GUIDE.md)
- [Jupyter Notebook Demo](../notebooks/hidden_gem_scanner.ipynb)
- [Statistical Tests Reference](https://docs.scipy.org/doc/scipy/reference/stats.html)

## 🚀 What's Next?

- **Multivariate Drift**: Detect drift across multiple features simultaneously
- **Concept Drift**: Monitor relationship between features and targets
- **Adaptive Baselines**: Automatically update baselines with exponential decay
- **Drift Explainability**: Explain why drift occurred
- **Custom Tests**: User-defined drift detection methods
