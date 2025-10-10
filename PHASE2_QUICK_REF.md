# Phase 2 Quick Reference Guide

## 🎯 Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Phase 2 Demo

```bash
cd Autotrader
python examples/phase2_example.py
```

## 📊 Common Operations

### 1. Multi-Exchange Streaming

```python
from src.microstructure.multi_exchange_stream import *

# Create streams
binance = BinanceOrderBookStream("BTC/USDT", depth=20)
bybit = BybitOrderBookStream("BTC/USDT:USDT", depth=20)
coinbase = CoinbaseOrderBookStream("BTC/USD", depth=20)

# Aggregate
aggregator = MultiExchangeAggregator({
    "binance": binance,
    "bybit": bybit,
    "coinbase": coinbase,
})

# Start (async)
await aggregator.start_all()

# Get data
books = aggregator.get_best_bid_ask()
arbs = aggregator.get_arbitrage_opportunities(min_profit_bps=5.0)
```

### 2. Extract Cross-Exchange Features

```python
from src.features.cross_exchange_features import CrossExchangeFeatureExtractor

extractor = CrossExchangeFeatureExtractor()

# Update history
extractor.update("binance", mid_price, volume, timestamp)

# Extract features
features = extractor.extract_features(books, arb_opportunities)

# Convert to dict for ML
feature_dict = extractor.to_dict(features)
```

### 3. Train LightGBM Model

```python
from src.models.lightgbm_pipeline import LightGBMPipeline

pipeline = LightGBMPipeline(model_dir=Path("models/primary"))

# Prepare data
X, y = pipeline.prepare_features(df, feature_columns, "is_gem")

# Train
metrics = pipeline.train(X, y, num_boost_round=1000)

# Predict
predictions = pipeline.predict(X_test)
```

### 4. Apply Meta-Labeling

```python
from src.models.meta_labeling import MetaLabeler, MetaLabelingConfig

config = MetaLabelingConfig(
    primary_threshold=0.5,
    meta_threshold=0.7,
)

meta = MetaLabeler(primary_model, meta_dir, config)

# Train
meta.train_meta_model(X_train, y_train)

# Predict with filtering
primary_probs, meta_probs, final_preds = meta.predict_with_meta(X_test)
```

### 5. Detect Anomalies with Spectral Residual

```python
from src.models.spectral_residual import SpectralResidualDetector

detector = SpectralResidualDetector(window_size=20, threshold_multiplier=3.0)

# Detect anomalies
detections = detector.detect(time_series, timestamps)

# Detect bursts
bursts = detector.detect_bursts(time_series, min_duration=3)
```

### 6. Walk-Forward Validation

```python
from src.models.walk_forward import WalkForwardOptimizer
from datetime import timedelta

optimizer = WalkForwardOptimizer(
    train_window_size=timedelta(days=30),
    test_window_size=timedelta(days=7),
    step_size=timedelta(days=7),
)

# Run
results = optimizer.run_optimization(df, feature_columns, "is_gem", "timestamp")

# Get metrics
agg_metrics = optimizer.get_aggregate_metrics()
```

### 7. Hyperparameter Optimization

```python
from src.models.hyperparameter_optimization import HyperparameterOptimizer

optimizer = HyperparameterOptimizer(
    study_name="gem_detector",
    storage_dir=Path("optuna_studies"),
    n_trials=100,
)

# Optimize
best_params = optimizer.optimize_lightgbm(
    X_train, y_train,
    X_val, y_val,
    metric="f1",
)
```

## 🔧 Configuration Templates

### LightGBM Parameters

```python
params = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "max_depth": -1,
    "min_child_samples": 20,
    "scale_pos_weight": 10.0,  # For imbalanced data
    "is_unbalance": True,
    "verbosity": -1,
    "seed": 42,
}
```

### Meta-Labeling Config

```python
config = MetaLabelingConfig(
    primary_threshold=0.5,    # Standard
    meta_threshold=0.7,       # Conservative (reduce FPs)
    min_confidence_gap=0.2,   # Min gap for certainty
)
```

### Walk-Forward Windows

```python
# Conservative (more training data)
train_window=timedelta(days=90)
test_window=timedelta(days=7)
step_size=timedelta(days=7)

# Aggressive (recent data)
train_window=timedelta(days=30)
test_window=timedelta(days=7)
step_size=timedelta(days=3)

# Expanding (all history)
expanding_window=True
```

## 📈 Feature Engineering

### Cross-Exchange Features

| Feature | Range | Good Value | Bad Value |
|---------|-------|------------|-----------|
| `price_dispersion` | 0-0.01 | > 0.002 | < 0.0005 |
| `max_price_spread_bps` | 0-100 | > 20 | < 5 |
| `best_arb_opportunity_bps` | 0-50 | > 10 | < 3 |
| `arb_opportunity_count` | 0-10 | > 3 | 0 |
| `price_sync_correlation` | 0-1 | < 0.8 | > 0.95 |
| `volume_concentration` | 0-1 | < 0.4 | > 0.8 |

### Feature Importance Rules

1. **Top 3 most important** → Monitor closely
2. **CV importance > 0.5** → Unstable, consider removing
3. **Mean importance < 10** → Consider removing
4. **New features** → Compare to existing top features

## 🚨 Troubleshooting

### WebSocket Disconnections

```python
# Increase reconnect delays
stream = BybitOrderBookStream(
    symbol="BTC/USDT:USDT",
    reconnect_delay=2.0,
    max_reconnect_delay=120.0,
)
```

### Insufficient Training Data

```python
# Check samples before training
if len(X_train) < 1000:
    logger.warning("Insufficient samples", n=len(X_train))
    # Reduce walk-forward window size
```

### Poor Model Performance

```python
# 1. Check class balance
positive_rate = y.mean()
if positive_rate < 0.05:
    # Increase scale_pos_weight
    params["scale_pos_weight"] = 20.0

# 2. Check feature distributions
X.describe()  # Look for inf, NaN, outliers

# 3. Try different boosting
params["boosting_type"] = "dart"  # Or "goss"
```

### Optuna Memory Issues

```python
# Reduce parallel jobs
optimizer = HyperparameterOptimizer(
    n_trials=50,
    n_jobs=1,  # Instead of 4
)

# Or use timeout
optimizer = HyperparameterOptimizer(
    timeout=3600,  # 1 hour max
)
```

## 📊 Performance Tuning

### Speed Optimizations

```python
# 1. Reduce feature extraction frequency
if update_count % 5 == 0:  # Every 5 updates instead of every
    features = extractor.extract_features(books, arbs)

# 2. Batch predictions
predictions = pipeline.predict(X_batch)  # Not row-by-row

# 3. Cache spectral residual detector
detector = SpectralResidualDetector()  # Reuse instance
```

### Memory Optimizations

```python
# 1. Limit history buffer size
extractor = CrossExchangeFeatureExtractor(
    price_history_size=500,  # Instead of 1000
)

# 2. Clear old predictions
if len(predictions_list) > 1000:
    predictions_list = predictions_list[-500:]

# 3. Use float32 instead of float64
X = X.astype(np.float32)
```

## 🧪 Testing Commands

```bash
# Unit tests
pytest tests/test_cross_exchange_features.py -v
pytest tests/test_lightgbm_pipeline.py -v
pytest tests/test_meta_labeling.py -v
pytest tests/test_spectral_residual.py -v
pytest tests/test_walk_forward.py -v

# Integration test
pytest tests/test_phase2_integration.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific test
pytest tests/test_lightgbm_pipeline.py::test_train -v
```

## 📁 File Locations

```
Autotrader/
├── src/
│   ├── microstructure/
│   │   └── multi_exchange_stream.py      # Exchange streaming
│   ├── features/
│   │   └── cross_exchange_features.py    # Feature engineering
│   └── models/
│       ├── lightgbm_pipeline.py          # LightGBM training
│       ├── meta_labeling.py              # Meta-labeling
│       ├── spectral_residual.py          # Anomaly detection
│       ├── walk_forward.py               # Backtesting
│       └── hyperparameter_optimization.py # Optuna
├── examples/
│   └── phase2_example.py                 # Demo script
├── docs/
│   └── PHASE2_IMPLEMENTATION.md          # Full documentation
└── models/                               # Saved models
    ├── primary/
    ├── meta_labeling/
    └── walk_forward_results/
```

## 🔗 Useful Links

- [LightGBM Documentation](https://lightgbm.readthedocs.io/)
- [Optuna Documentation](https://optuna.readthedocs.io/)
- [CCXT Documentation](https://docs.ccxt.com/)
- [Spectral Residual Paper](https://arxiv.org/abs/1906.03821)

## 💡 Tips & Best Practices

1. **Always validate on OOS data** - Never use test data for training
2. **Monitor feature drift** - Re-extract features periodically
3. **Retrain models weekly** - Markets change quickly
4. **Use meta-labeling conservatively** - Start with high threshold
5. **Log everything** - Helps debug production issues
6. **Version your models** - Keep track of which version is deployed
7. **Test on historical data** - Before deploying to production
8. **Set up alerts** - For model performance degradation

---

**Quick Reference Version**: 1.0  
**Last Updated**: 2025-10-10  
**For Full Documentation**: See `docs/PHASE2_IMPLEMENTATION.md`
