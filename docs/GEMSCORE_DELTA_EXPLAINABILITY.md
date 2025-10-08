# GemScore Delta Explainability

## Overview

The GemScore Delta Explainability feature provides detailed insights into **what features contributed most to GemScore changes** between successive token scans. This enables operators to understand:

- Which features are driving score increases or decreases
- The magnitude of each feature's impact on the overall score
- Time-series trends in feature importance
- Natural language explanations of score changes

## Architecture

### Core Components

1. **`ScoreExplainer`** (`src/core/score_explainer.py`)
   - Computes deltas between GemScore snapshots
   - Identifies top positive and negative contributors
   - Generates human-readable narratives

2. **`GemScoreSnapshot`**
   - Complete snapshot of a GemScore calculation
   - Includes timestamp, score, features, and contributions
   - Stored in FeatureStore for historical comparison

3. **`ScoreDelta`**
   - Represents a change between two snapshots
   - Contains sorted lists of feature deltas
   - Provides summary and narrative generation

4. **`FeatureDelta`**
   - Tracks individual feature changes
   - Includes value changes, contribution changes, and percent changes
   - Associated with feature weight in scoring formula

### Integration Points

- **Pipeline**: `HiddenGemScanner` automatically stores snapshots when computing GemScore
- **FeatureStore**: Provides snapshot storage and delta computation methods
- **Dashboard API**: Exposes REST endpoints for querying deltas

## Usage

### Automatic Tracking in Pipeline

When a `FeatureStore` is provided to `HiddenGemScanner`, delta explainability is automatically enabled:

```python
from src.core.pipeline import HiddenGemScanner
from src.core.feature_store import FeatureStore
from src.core.clients import CoinGeckoClient

# Initialize with feature store
feature_store = FeatureStore()
scanner = HiddenGemScanner(
    coin_client=CoinGeckoClient(),
    feature_store=feature_store,
)

# Run scan - snapshots are automatically stored
result = scanner.scan(token_config)

# Delta computation happens automatically and is logged
```

### Manual Delta Computation

```python
from src.core.score_explainer import ScoreExplainer, create_snapshot_from_result
from src.core.scoring import compute_gem_score

# Compute scores at two different times
features_t1 = {...}
score_t1 = compute_gem_score(features_t1)

features_t2 = {...}
score_t2 = compute_gem_score(features_t2)

# Create snapshots
explainer = ScoreExplainer()
snapshot_t1 = explainer.create_snapshot("ETH", score_t1, features_t1, timestamp=1000.0)
snapshot_t2 = explainer.create_snapshot("ETH", score_t2, features_t2, timestamp=2000.0)

# Compute delta
delta = explainer.compute_delta(snapshot_t1, snapshot_t2)

# Access results
print(f"Score changed by {delta.delta_score:.2f} points")
print(f"Top positive contributor: {delta.top_positive_contributors[0].feature_name}")
print(f"\nNarrative:\n{delta.get_narrative()}")
```

### Using FeatureStore

```python
from src.core.feature_store import FeatureStore

store = FeatureStore()

# Snapshots are stored automatically by scanner
# Or manually:
store.write_snapshot(snapshot)

# Read latest snapshot
current = store.read_snapshot("ETH")

# Get historical snapshots
history = store.read_snapshot_history("ETH", limit=10)

# Compute delta (compares current to previous)
delta = store.compute_score_delta("ETH")

if delta:
    summary = delta.get_summary(top_n=5)
    print(f"Score change: {summary['score_change']['delta']}")
    print(f"Top contributors: {summary['top_positive_contributors']}")
```

## API Endpoints

### Get Current Delta

**GET** `/api/gemscore/delta/{token_symbol}`

Returns the most recent score change with top contributors.

**Response:**
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
  ],
  "top_negative_contributors": [...]
}
```

### Get Delta Narrative

**GET** `/api/gemscore/delta/{token_symbol}/narrative`

Returns a human-readable explanation of the score change.

**Response:**
```json
{
  "token": "ETH",
  "narrative": "GemScore for ETH increased by 5.80 points (+8.0%) from 72.50 to 78.30 over 1.5 hours.\n\nKey positive drivers:\n  1. SentimentScore: +50.0% (+3.75 points)\n  2. OnchainActivity: +20.0% (+2.10 points)",
  "timestamp": 1699564800.0
}
```

### Get Detailed Explanation

**GET** `/api/gemscore/delta/{token_symbol}/detailed?threshold=0.01`

Returns comprehensive delta with all significant changes.

**Parameters:**
- `threshold`: Minimum contribution change in points (default: 0.01)

**Response:**
```json
{
  "overview": {
    "score_changed": 5.8,
    "percent_change": 8.0,
    "time_elapsed_hours": 1.5,
    "direction": "increase"
  },
  "significant_changes": [
    {
      "feature": "SentimentScore",
      "value_change": {
        "previous": 0.5,
        "current": 0.75,
        "delta": 0.25,
        "percent": 50.0
      },
      "contribution_change": {
        "previous": 7.5,
        "current": 11.25,
        "delta": 3.75
      },
      "weight": 0.15,
      "impact": "positive"
    }
  ],
  "narrative": "..."
}
```

### Get Score History

**GET** `/api/gemscore/history/{token_symbol}?limit=10`

Returns historical snapshots for a token.

### Get Delta Series

**GET** `/api/gemscore/deltas/{token_symbol}/series?limit=5`

Returns a series of deltas showing trend over time.

## Data Models

### GemScoreSnapshot

```python
@dataclass
class GemScoreSnapshot:
    token_symbol: str
    timestamp: float
    score: float
    confidence: float
    features: Dict[str, float]  # Raw feature values (0-1)
    contributions: Dict[str, float]  # Feature contributions to score
    metadata: Dict[str, object]
```

### ScoreDelta

```python
@dataclass
class ScoreDelta:
    token_symbol: str
    previous_score: float
    current_score: float
    delta_score: float
    percent_change: float
    previous_timestamp: float
    current_timestamp: float
    time_delta_hours: float
    feature_deltas: List[FeatureDelta]
    top_positive_contributors: List[FeatureDelta]
    top_negative_contributors: List[FeatureDelta]
    metadata: Dict[str, object]
```

### FeatureDelta

```python
@dataclass
class FeatureDelta:
    feature_name: str
    previous_value: float
    current_value: float
    delta_value: float
    previous_contribution: float
    current_contribution: float
    delta_contribution: float
    percent_change: float
    weight: float
```

## Example Output

### Console Logs

When delta explainability is enabled in the pipeline, you'll see logs like:

```
INFO gem_score_delta token_symbol=ETH delta_score=5.8 percent_change=8.0 time_delta_hours=1.5 
     top_positive=['SentimentScore', 'OnchainActivity', 'NarrativeMomentum'] 
     top_negative=['LiquidityDepth']
```

### Narrative Output

```
GemScore for ETH increased by 5.80 points (+8.0%) from 72.50 to 78.30 over 1.5 hours.

Key positive drivers:
  1. SentimentScore: +50.0% (+3.75 points)
  2. OnchainActivity: +20.0% (+2.10 points)
  3. NarrativeMomentum: +15.0% (+0.95 points)

Key negative drivers:
  1. LiquidityDepth: -10.0% (-0.50 points)
```

## Configuration

### Feature Weights

Delta explainability uses the same weights as the GemScore formula:

```python
WEIGHTS = {
    "SentimentScore": 0.15,
    "AccumulationScore": 0.20,
    "OnchainActivity": 0.15,
    "LiquidityDepth": 0.10,
    "TokenomicsRisk": 0.12,
    "ContractSafety": 0.12,
    "NarrativeMomentum": 0.08,
    "CommunityGrowth": 0.08,
}
```

You can provide custom weights to `ScoreExplainer`:

```python
custom_weights = {...}
explainer = ScoreExplainer(weights=custom_weights)
```

### Snapshot Retention

Control how long snapshots are kept:

```python
# Clear snapshots older than 24 hours
store.clear_old_data(max_age_seconds=86400)
```

## Performance Considerations

- **Storage**: Each snapshot stores ~10 feature values per token
- **Computation**: Delta computation is O(n) where n = number of features
- **Memory**: In-memory storage by default; configure `storage_path` for persistence

### Best Practices

1. **Limit History**: Keep only recent snapshots (e.g., last 100 per token)
2. **Batch Cleanup**: Periodically clear old data
3. **Selective Tracking**: Only track deltas for tokens of interest
4. **Async Logging**: Delta computation is fast but logging should be async in production

## Testing

Run the test suite:

```bash
# Core explainability tests
pytest tests/test_score_explainer.py -v

# Integration tests with FeatureStore
pytest tests/test_score_explainer_integration.py -v

# Run both
pytest tests/test_score_explainer*.py -v
```

## Troubleshooting

### No Delta Available

**Problem**: API returns "Insufficient history to compute delta"

**Solution**: Ensure at least 2 snapshots exist for the token:
```python
history = store.read_snapshot_history("TOKEN", limit=10)
print(f"Found {len(history)} snapshots")
```

### Large Delta Changes

**Problem**: Delta shows unexpectedly large changes

**Solution**: Check time between snapshots:
```python
delta = store.compute_score_delta("TOKEN")
print(f"Time delta: {delta.time_delta_hours} hours")
```

### Missing Features

**Problem**: Some features not appearing in delta

**Solution**: Features with weight=0 or no change won't appear in significant_changes. Use `threshold=0.0` for all changes:
```python
explanation = explainer.explain_score_change(delta, threshold=0.0)
```

## Future Enhancements

Potential improvements:

1. **Trend Analysis**: Detect patterns in feature importance over time
2. **Anomaly Detection**: Flag unusual score changes
3. **Visualization**: Generate charts showing feature contributions
4. **Alerts**: Trigger notifications on significant deltas
5. **ML Integration**: Use deltas to train predictive models
6. **Comparative Analysis**: Compare deltas across multiple tokens

## References

- Core Module: `src/core/score_explainer.py`
- Integration: `src/core/pipeline.py`
- Storage: `src/core/feature_store.py`
- API: `src/api/dashboard_api.py`
- Tests: `tests/test_score_explainer*.py`
