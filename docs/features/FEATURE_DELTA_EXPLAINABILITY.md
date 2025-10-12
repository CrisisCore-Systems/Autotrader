# ✨ NEW: GemScore Delta Explainability

## What Changed?

Your GemScore now comes with **explainability**! See exactly which features contributed most to score changes between scans.

## Quick Example

```python
from src.core.feature_store import FeatureStore
from src.core.pipeline import HiddenGemScanner

# Enable delta tracking
store = FeatureStore()
scanner = HiddenGemScanner(
    coin_client=coin_client,
    feature_store=store,  # 👈 Add this
)

# Run scans as normal
result = scanner.scan(token_config)

# Get delta explanation
delta = store.compute_score_delta("ETH")
print(delta.get_narrative())
```

**Output:**
```
GemScore for ETH increased by 5.80 points (+8.0%) from 72.50 to 78.30 over 1.5 hours.

Key positive drivers:
  1. SentimentScore: +50.0% (+3.75 points)
  2. OnchainActivity: +20.0% (+2.10 points)
```

## New API Endpoints

```bash
# Get latest delta
GET /api/gemscore/delta/{symbol}

# Get human-readable narrative  
GET /api/gemscore/delta/{symbol}/narrative

# Get detailed breakdown
GET /api/gemscore/delta/{symbol}/detailed

# Get historical deltas
GET /api/gemscore/deltas/{symbol}/series?limit=5
```

## Documentation

- **Full Guide**: [GEMSCORE_DELTA_EXPLAINABILITY.md](../GEMSCORE_DELTA_EXPLAINABILITY.md)
- **Quick Ref**: [GEMSCORE_DELTA_QUICK_REF.md](../GEMSCORE_DELTA_QUICK_REF.md)
- **Examples**: [delta_explainability_example.py](https://github.com/CrisisCore-Systems/Autotrader/blob/main/examples/delta_explainability_example.py)

## Features

✅ **Automatic Tracking** - Works seamlessly with existing scans  
✅ **Top Contributors** - See which features drove score changes  
✅ **Natural Language** - Human-readable explanations  
✅ **Time Series** - Analyze trends over multiple scans  
✅ **REST API** - Query deltas from dashboard  
✅ **Zero Config** - Optional feature, no breaking changes  

## Test It

```bash
# Run tests
pytest tests/test_score_explainer*.py -v

# Try examples
python examples/delta_explainability_example.py
```

**All 28 tests passing ✅**

---

*No changes needed to your existing code - just add `feature_store` parameter to enable!*
