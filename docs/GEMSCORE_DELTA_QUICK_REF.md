# GemScore Delta Explainability - Quick Reference

## What is it?

Shows which features contributed most to GemScore changes between scans.

## Key Features

✅ **Automatic tracking** when FeatureStore is enabled  
✅ **Top contributors** (positive and negative)  
✅ **Human-readable narratives**  
✅ **REST API endpoints**  
✅ **Historical trend analysis**

## Quick Start

### 1. Enable in Scanner

```python
from src.core.pipeline import HiddenGemScanner
from src.core.feature_store import FeatureStore

store = FeatureStore()
scanner = HiddenGemScanner(
    coin_client=coin_client,
    feature_store=store,  # Enable delta tracking
)
```

### 2. Scan Token

```python
result = scanner.scan(token_config)
# Delta automatically computed and logged
```

### 3. Query Delta via API

```bash
# Get latest delta
curl http://localhost:8000/api/gemscore/delta/ETH

# Get narrative explanation
curl http://localhost:8000/api/gemscore/delta/ETH/narrative

# Get detailed breakdown
curl http://localhost:8000/api/gemscore/delta/ETH/detailed

# Get historical series
curl http://localhost:8000/api/gemscore/deltas/ETH/series?limit=5
```

## API Endpoints

| Endpoint | Description | Example |
|----------|-------------|---------|
| `/api/gemscore/delta/{symbol}` | Current delta summary | Top 5 contributors |
| `/api/gemscore/delta/{symbol}/narrative` | Human-readable explanation | "ETH increased by 5.8 points..." |
| `/api/gemscore/delta/{symbol}/detailed` | Full breakdown | All significant changes |
| `/api/gemscore/history/{symbol}` | Historical snapshots | Last 10 scores |
| `/api/gemscore/deltas/{symbol}/series` | Delta time series | Trend analysis |

## Response Format

### Delta Summary

```json
{
  "token": "ETH",
  "score_change": {
    "previous": 72.5,
    "current": 78.3,
    "delta": 5.8,
    "percent_change": 8.0
  },
  "time_delta_hours": 1.5,
  "top_positive_contributors": [
    {
      "feature": "SentimentScore",
      "value_change": 0.25,
      "percent_change": 50.0,
      "contribution_impact": 3.75
    }
  ]
}
```

### Narrative

```json
{
  "token": "ETH",
  "narrative": "GemScore for ETH increased by 5.80 points (+8.0%) from 72.50 to 78.30 over 1.5 hours.\n\nKey positive drivers:\n  1. SentimentScore: +50.0% (+3.75 points)\n  2. OnchainActivity: +20.0% (+2.10 points)"
}
```

## Programmatic Usage

### Get Delta

```python
from src.core.feature_store import FeatureStore

store = FeatureStore()

# Get latest delta
delta = store.compute_score_delta("ETH")

if delta:
    print(f"Score changed: {delta.delta_score:+.2f} points")
    print(f"Top contributor: {delta.top_positive_contributors[0].feature_name}")
    print(f"\n{delta.get_narrative()}")
```

### Access History

```python
# Get last 10 snapshots
history = store.read_snapshot_history("ETH", limit=10)

# Iterate through changes
for i in range(len(history) - 1):
    current = history[i]
    previous = history[i + 1]
    
    delta = explainer.compute_delta(previous, current)
    print(f"At {current.timestamp}: {delta.delta_score:+.2f}")
```

## Common Use Cases

### 1. Monitor Score Changes

```python
# Check if score increased significantly
if delta and delta.delta_score > 5.0:
    print(f"⚠️ Large increase: {delta.delta_score:.2f}")
    print(f"Driven by: {delta.top_positive_contributors[0].feature_name}")
```

### 2. Alert on Negative Trends

```python
# Alert if sentiment is declining
for fd in delta.top_negative_contributors:
    if fd.feature_name == "SentimentScore" and fd.delta_contribution < -2.0:
        send_alert(f"Sentiment declining for {delta.token_symbol}")
```

### 3. Track Feature Importance

```python
# Which features change most frequently?
feature_changes = {}
for snapshot in history:
    for feature, value in snapshot.features.items():
        if feature not in feature_changes:
            feature_changes[feature] = []
        feature_changes[feature].append(value)

# Analyze volatility
for feature, values in feature_changes.items():
    volatility = np.std(values)
    print(f"{feature}: {volatility:.3f}")
```

## Feature Weights

| Feature | Weight | Impact |
|---------|--------|--------|
| AccumulationScore | 0.20 | Highest |
| SentimentScore | 0.15 | High |
| OnchainActivity | 0.15 | High |
| TokenomicsRisk | 0.12 | Medium |
| ContractSafety | 0.12 | Medium |
| LiquidityDepth | 0.10 | Medium |
| NarrativeMomentum | 0.08 | Lower |
| CommunityGrowth | 0.08 | Lower |

## Interpretation Guide

### Contribution Impact

- **> +5 points**: Major positive driver
- **+2 to +5 points**: Significant positive impact
- **+0.5 to +2 points**: Moderate positive impact
- **-0.5 to +0.5 points**: Minimal impact
- **-0.5 to -2 points**: Moderate negative impact
- **-2 to -5 points**: Significant negative impact
- **< -5 points**: Major negative driver

### Percent Change

- **> +50%**: Large increase
- **+20% to +50%**: Moderate increase
- **+5% to +20%**: Small increase
- **-5% to +5%**: Stable
- **-20% to -5%**: Small decrease
- **-50% to -20%**: Moderate decrease
- **< -50%**: Large decrease

## Troubleshooting

### "Insufficient history"

**Cause**: Less than 2 snapshots available  
**Fix**: Wait for more scans or check `store.read_snapshot_history("TOKEN")`

### "No snapshots found"

**Cause**: Token hasn't been scanned with FeatureStore enabled  
**Fix**: Ensure `feature_store` is passed to scanner

### Large time gaps

**Cause**: Scans too infrequent  
**Fix**: Increase scan frequency or use `time_delta_hours` to normalize

## Best Practices

✅ **Regular Scans**: Run scans at consistent intervals  
✅ **Retention Policy**: Clear old data periodically  
✅ **Threshold Tuning**: Adjust `threshold` parameter for relevance  
✅ **Combine with Alerts**: Trigger notifications on significant changes  
✅ **Log Review**: Monitor delta logs for patterns

## Performance Tips

- **In-memory storage**: Default is fast but not persistent
- **Disk persistence**: Set `storage_path` for durability
- **Cleanup**: Use `clear_old_data(86400)` to keep last 24h
- **Limit queries**: Use `limit` parameter in history requests

## Testing

```bash
# Run explainability tests
pytest tests/test_score_explainer.py -v

# Run integration tests
pytest tests/test_score_explainer_integration.py -v
```

## Documentation

Full documentation: `docs/GEMSCORE_DELTA_EXPLAINABILITY.md`

## Support

- Module: `src/core/score_explainer.py`
- API: `src/api/dashboard_api.py`
- Tests: `tests/test_score_explainer*.py`
