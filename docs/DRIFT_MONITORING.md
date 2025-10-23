# Data Drift and Freshness Monitoring

## Overview

The AutoTrader platform includes comprehensive data drift and freshness monitoring to ensure model performance and data quality. This document describes the monitoring capabilities and how to use them.

## Features

### 1. Data Drift Detection

Detects when feature distributions change over time using multiple statistical tests:

- **KL Divergence**: Measures how one probability distribution diverges from a reference distribution
- **Kolmogorov-Smirnov (KS) Test**: Tests if two samples come from the same distribution
- **Population Stability Index (PSI)**: Measures shift in feature distributions
- **Chi-Square Test**: Tests for categorical distribution differences

### 2. Data Freshness Tracking

Monitors the age of data from various sources and classifies freshness:

- **FRESH**: < 5 minutes old
- **RECENT**: < 1 hour old
- **STALE**: < 24 hours old
- **OUTDATED**: > 24 hours old

### 3. SLA Enforcement

Enforces Service Level Agreements for data freshness with three criticality levels:

- **CRITICAL**: Must meet strict SLAs (e.g., 5 minutes for price data)
- **IMPORTANT**: Should meet SLAs (e.g., 10 minutes for safety scores)
- **STANDARD**: Best effort monitoring (e.g., 1 hour for historical data)

### 4. Dashboard & Reporting

- Real-time monitoring dashboard (React component)
- REST API endpoints for programmatic access
- Historical reports and trend analysis
- Automated recommendations

## Quick Start

### 1. Basic Drift Detection

```python
from src.monitoring import DriftMonitor, Baseline
import numpy as np

# Create a baseline from historical data
monitor = DriftMonitor(name="production_monitor")
baseline = monitor.create_baseline(
    name="baseline_v1",
    features={
        "gem_score": np.random.normal(60, 15, 1000),
        "liquidity": np.random.lognormal(10, 2, 1000),
    },
    predictions=np.random.normal(65, 20, 1000),
    performance_metrics={"accuracy": 0.85},
)

# Detect drift in new data
current_data = np.random.normal(50, 15, 200)  # Shifted distribution
report = monitor.detect_feature_drift("gem_score", current_data)

if report.drift_detected:
    print(f"Drift detected! Severity: {report.severity}")
    for stat in report.statistics:
        print(f"  {stat.test_name}: {stat.statistic:.4f}")
```

### 2. Integrated Monitoring with SLAs

```python
from src.monitoring import IntegratedMonitor, FeatureCriticality

# Create integrated monitor
monitor = IntegratedMonitor(name="production_monitor")
monitor.drift_monitor.set_baseline(baseline)

# Register SLAs for critical features
monitor.register_feature_sla(
    feature_name="gem_score",
    max_age_seconds=300,  # 5 minutes
    criticality=FeatureCriticality.CRITICAL,
)

monitor.register_feature_sla(
    feature_name="liquidity",
    max_age_seconds=600,  # 10 minutes
    criticality=FeatureCriticality.IMPORTANT,
)

# Monitor features
features = {
    "gem_score": current_gem_scores,
    "liquidity": current_liquidity,
}

report = monitor.monitor_features(features, feature_timestamps)

print(f"Status: {monitor._determine_overall_status(report)}")
print(f"Features drifted: {report.features_drifted}/{report.features_monitored}")
print(f"SLA violations: {report.sla_violations}")
```

### 3. Using the API

#### Get Monitoring Summary

```bash
curl http://localhost:8000/api/monitoring/summary
```

Response:
```json
{
  "timestamp": "2025-10-22T12:00:00Z",
  "status": "healthy",
  "features_monitored": 5,
  "features_drifted": 0,
  "features_stale": 0,
  "sla_violations": 0,
  "critical_features": 2,
  "recommendations": []
}
```

#### Get Feature Health

```bash
curl http://localhost:8000/api/monitoring/features/gem_score
```

Response:
```json
{
  "feature_name": "gem_score",
  "drift_detected": false,
  "drift_severity": "none",
  "freshness_level": "fresh",
  "data_age_seconds": 120.5,
  "sla_violated": false,
  "last_updated": "2025-10-22T11:58:00Z"
}
```

#### Register Feature SLA

```bash
curl -X POST http://localhost:8000/api/monitoring/sla/register \
  -H "Content-Type: application/json" \
  -d '{
    "feature_name": "gem_score",
    "max_age_seconds": 300,
    "criticality": "critical"
  }'
```

### 4. Dashboard UI

The React dashboard component provides real-time visualization:

```tsx
import { DriftMonitoring } from './components/DriftMonitoring';

function App() {
  return (
    <div>
      <DriftMonitoring />
    </div>
  );
}
```

Features:
- Real-time status overview
- Per-feature health metrics
- Drift severity indicators
- Data freshness visualization
- SLA violation alerts
- Auto-refresh capability

## Statistical Tests

### KL Divergence

Kullback-Leibler divergence measures how much one probability distribution differs from another:

- **Range**: 0 to ∞
- **Thresholds**:
  - < 0.05: Minimal drift
  - 0.05-0.1: Low drift
  - 0.1-0.3: Medium drift
  - 0.3-0.5: High drift
  - \> 0.5: Critical drift

### Population Stability Index (PSI)

Measures the shift in population distribution:

- **Range**: 0 to ∞
- **Thresholds**:
  - < 0.1: No significant change
  - 0.1-0.2: Moderate shift (monitor)
  - \> 0.2: Significant shift (action needed)

### Kolmogorov-Smirnov Test

Tests whether two samples come from the same distribution:

- **Range**: 0 to 1
- **Uses p-value**: < 0.05 indicates significant difference
- **Severity based on KS statistic**:
  - < 0.1: Low
  - 0.1-0.2: Medium
  - 0.2-0.3: High
  - \> 0.3: Critical

## Best Practices

### 1. Baseline Creation

- Use at least 1000 samples for stable statistics
- Update baselines periodically (e.g., monthly)
- Keep multiple baselines for different time periods
- Document baseline metadata (date, data sources, conditions)

### 2. SLA Configuration

- Set realistic freshness requirements based on feature usage
- Mark truly critical features as CRITICAL (sparing use)
- Use tiered SLAs (CRITICAL, IMPORTANT, STANDARD)
- Set alert thresholds at 80% of max age for early warning

### 3. Monitoring Frequency

- Run drift checks at least daily
- Increase frequency for critical features
- Monitor continuously in production if possible
- Archive historical reports for trend analysis

### 4. Responding to Drift

When drift is detected:

1. **Investigate root cause**
   - Data quality issues?
   - Distribution shift in population?
   - Concept drift (business logic change)?

2. **Assess impact**
   - Check model performance metrics
   - Review recent predictions
   - Validate against ground truth

3. **Take action**
   - Minor drift: Monitor closely
   - Moderate drift: Update features or retrain
   - Severe drift: Retrain model immediately

### 5. Responding to SLA Violations

When SLA is violated:

1. **CRITICAL features**: Immediate action required
   - Check data pipeline health
   - Investigate data source issues
   - Alert on-call engineers

2. **IMPORTANT features**: Action within hours
   - Review data refresh schedule
   - Check for intermittent failures

3. **STANDARD features**: Monitor and fix in batch
   - Aggregate violations
   - Address during maintenance window

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   IntegratedMonitor                      │
│                                                          │
│  ┌──────────────────┐      ┌────────────────────────┐  │
│  │  DriftMonitor    │      │  FreshnessTracker      │  │
│  │                  │      │                        │  │
│  │  - KL Divergence │      │  - Data age tracking  │  │
│  │  - KS Test       │      │  - Freshness levels   │  │
│  │  - PSI           │      │  - Timestamps         │  │
│  │  - Chi-square    │      └────────────────────────┘  │
│  └──────────────────┘                                   │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │             SLA Manager                         │    │
│  │  - Feature criticality                          │    │
│  │  - Freshness thresholds                         │    │
│  │  - Violation tracking                           │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                         │
                         ↓
              ┌──────────────────────┐
              │  Monitoring Reports   │
              │  - Drift status       │
              │  - Freshness status   │
              │  - SLA compliance     │
              │  - Recommendations    │
              └──────────────────────┘
                         │
          ┌──────────────┴─────────────────┐
          ↓                                  ↓
  ┌──────────────┐                  ┌──────────────┐
  │  REST API    │                  │  Dashboard    │
  │  /monitoring │                  │  UI Component │
  └──────────────┘                  └──────────────┘
```

## Examples

See `examples/integrated_monitoring_example.py` for a comprehensive demonstration of:

- Baseline creation
- SLA registration
- Healthy system monitoring
- Drift detection scenarios
- Stale data scenarios
- Combined issues
- Report generation

Run the example:

```bash
python examples/integrated_monitoring_example.py
```

## API Reference

### REST Endpoints

- `GET /api/monitoring/summary` - Get monitoring summary
- `GET /api/monitoring/details` - Get detailed report
- `GET /api/monitoring/features` - List monitored features
- `GET /api/monitoring/features/{feature_name}` - Get feature health
- `POST /api/monitoring/sla/register` - Register feature SLA
- `GET /api/monitoring/sla/list` - List all SLAs
- `GET /api/monitoring/history?limit=10` - Get monitoring history

### Python API

See module documentation:
- `src.monitoring.drift_monitor` - Core drift detection
- `src.monitoring.integrated_monitor` - Integrated monitoring
- `src.core.freshness` - Freshness tracking

## Troubleshooting

### High False Positive Rate

If drift is detected too frequently:
- Increase sample size for baseline (>1000)
- Adjust p-value threshold (default: 0.05)
- Adjust PSI threshold (default: 0.2)
- Use multiple test agreement (require 2+ tests to agree)

### Missed Drift Events

If drift is not detected when expected:
- Check baseline is representative
- Ensure sufficient current sample size
- Review statistical thresholds
- Validate feature distributions

### Performance Issues

For large-scale monitoring:
- Run drift checks asynchronously
- Sample data for statistical tests
- Cache baseline statistics
- Use batch monitoring for non-critical features

## Contributing

To extend the monitoring system:

1. Add new statistical tests in `DriftDetector`
2. Extend freshness classifications in `FreshnessLevel`
3. Add new criticality levels in `FeatureCriticality`
4. Create custom alert handlers
5. Add visualization components

## References

- [Population Stability Index](https://en.wikipedia.org/wiki/Population_stability_index)
- [Kullback-Leibler Divergence](https://en.wikipedia.org/wiki/Kullback%E2%80%93Leibler_divergence)
- [Kolmogorov-Smirnov Test](https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test)
- [Data Drift in ML](https://www.evidentlyai.com/blog/ml-monitoring-data-drift)
