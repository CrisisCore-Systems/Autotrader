# Metrics Registry

Complete reference for all metrics tracked by AutoTrader.

!!! tip "Auto-Generated"
    This page is automatically generated from `config/metrics_registry.yaml`.

## Overview

AutoTrader tracks **20 metrics** across 9 categories.

## Categories

- [alerting](#alerting): 3 metrics
- [api](#api): 2 metrics
- [business](#business): 1 metrics
- [cache](#cache): 3 metrics
- [data_quality](#data_quality): 1 metrics
- [errors](#errors): 1 metrics
- [monitoring](#monitoring): 3 metrics
- [performance](#performance): 2 metrics
- [validation](#validation): 4 metrics

## alerting

### `active_alerts`

**Type**: 📊 Gauge

Current number of active alerts

**Labels**:

- `severity`

**Unit**: count

**Example**:

```
active_alerts{severity="warning"}
```

### `alerts_fired_total`

**Type**: 🔢 Counter

Total number of alerts fired

**Labels**:

- `rule_name`
- `severity`
- `channel`

**Unit**: count

**Example**:

```
alerts_fired_total{rule_name="high_gem_score",severity="info",channel="slack"}
```

### `alerts_suppressed_total`

**Type**: 🔢 Counter

Total number of suppressed alerts

**Labels**:

- `rule_name`
- `reason`

**Unit**: count

**Example**:

```
alerts_suppressed_total{rule_name="price_spike",reason="cooldown"}
```

## api

### `api_request_duration_seconds`

**Type**: 📈 Histogram

Duration of API requests

**Labels**:

- `endpoint`
- `method`

**Unit**: seconds

**Buckets**: `[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0]`

**Example**:

```
api_request_duration_seconds{endpoint="/scan",method="POST"}
```

### `api_requests_total`

**Type**: 🔢 Counter

Total number of API requests

**Labels**:

- `endpoint`
- `method`
- `status_code`

**Unit**: count

**Example**:

```
api_requests_total{endpoint="/scan",method="POST",status_code="200"}
```

## business

### `tokens_scanned_total`

**Type**: 🔢 Counter

Total number of tokens scanned

**Labels**:

- `strategy`
- `result`

**Unit**: count

**Example**:

```
tokens_scanned_total{strategy="momentum",result="gem"}
```

## cache

### `cache_hits_total`

**Type**: 🔢 Counter

Total number of cache hits

**Labels**:

- `cache_name`

**Unit**: count

**Example**:

```
cache_hits_total{cache_name="price_data"}
```

### `cache_misses_total`

**Type**: 🔢 Counter

Total number of cache misses

**Labels**:

- `cache_name`

**Unit**: count

**Example**:

```
cache_misses_total{cache_name="price_data"}
```

### `cache_size_bytes`

**Type**: 📊 Gauge

Current cache size in bytes

**Labels**:

- `cache_name`

**Unit**: bytes

**Example**:

```
cache_size_bytes{cache_name="price_data"}
```

## data_quality

### `feature_freshness_seconds`

**Type**: 📈 Histogram

Age of feature data in seconds

**Labels**:

- `feature_name`

**Unit**: seconds

**Buckets**: `[1, 5, 10, 30, 60, 300, 600, 1800, 3600]`

**Example**:

```
feature_freshness_seconds{feature_name="price"}
```

## errors

### `scan_errors_total`

**Type**: 🔢 Counter

Total number of scan errors

**Labels**:

- `error_type`
- `strategy`

**Unit**: count

**Example**:

```
scan_errors_total{error_type="api_timeout",strategy="default"}
```

## monitoring

### `drift_detections_total`

**Type**: 🔢 Counter

Total number of drift detections

**Labels**:

- `feature_name`
- `drift_type`
- `severity`

**Unit**: count

**Example**:

```
drift_detections_total{feature_name="price",drift_type="distribution",severity="high"}
```

### `drift_score`

**Type**: 📊 Gauge

Current drift score for a metric

**Labels**:

- `metric_name`

**Unit**: score

**Example**:

```
drift_score{metric_name="gem_score"}
```

### `prediction_distribution`

**Type**: 📈 Histogram

Distribution of model predictions

**Labels**:

- `model_name`

**Unit**: probability

**Buckets**: `[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]`

**Example**:

```
prediction_distribution{model_name="gem_scorer"}
```

## performance

### `feature_write_duration_seconds`

**Type**: 📈 Histogram

Duration of feature write operations

**Labels**:

- `feature_name`

**Unit**: seconds

**Buckets**: `[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]`

**Example**:

```
feature_write_duration_seconds{feature_name="sentiment"}
```

### `scan_duration_seconds`

**Type**: 📈 Histogram

Duration of scan operations

**Labels**:

- `strategy`
- `outcome`

**Unit**: seconds

**Buckets**: `[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]`

**Example**:

```
scan_duration_seconds{strategy="momentum",outcome="success"}
```

## validation

### `feature_validation_failures_total`

**Type**: 🔢 Counter

Total number of feature validation failures

**Labels**:

- `feature_name`
- `validation_type`
- `severity`

**Unit**: count

**Example**:

```
feature_validation_failures_total{feature_name="price",validation_type="range",severity="error"}
```

### `feature_validation_success_total`

**Type**: 🔢 Counter

Total number of successful feature validations

**Labels**:

- `feature_name`

**Unit**: count

**Example**:

```
feature_validation_success_total{feature_name="price"}
```

### `feature_validation_warnings_total`

**Type**: 🔢 Counter

Total number of feature validation warnings

**Labels**:

- `feature_name`
- `validation_type`

**Unit**: count

**Example**:

```
feature_validation_warnings_total{feature_name="volume",validation_type="outlier"}
```

### `feature_value_distribution`

**Type**: 📈 Histogram

Distribution of feature values

**Labels**:

- `feature_name`
- `category`

**Unit**: value

**Buckets**: `[0, 10, 25, 50, 75, 90, 100]`

**Example**:

```
feature_value_distribution{feature_name="gem_score",category="crypto"}
```
