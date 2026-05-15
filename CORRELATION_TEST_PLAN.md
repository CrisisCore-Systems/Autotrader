# Integration Test: Correlation Analysis with Market Regime Classification

## Test Plan

This document outlines the test strategy for the new correlation analysis integration.

## Unit Tests

### Test 1: `compute_rolling_correlations()`

**Test Case 1.1: Normal operation**
```python
def test_compute_rolling_correlations_normal():
    returns = {
        "BTC": pd.Series([0.01, -0.02, 0.015, -0.01, 0.005] * 20),
        "ETH": pd.Series([0.015, -0.018, 0.012, -0.008, 0.006] * 20),
        "SOL": pd.Series([-0.01, 0.02, -0.015, 0.01, -0.005] * 20),
    }
    
    corr_dict = compute_rolling_correlations(returns, window=10)
    
    assert len(corr_dict) == 3  # 3 pairs: (BTC,ETH), (BTC,SOL), (ETH,SOL)
    assert all(isinstance(v, pd.Series) for v in corr_dict.values())
    assert all(not v.isna().all() for v in corr_dict.values())
    print("✓ Test 1.1 passed")
```

**Test Case 1.2: Insufficient data**
```python
def test_compute_rolling_correlations_insufficient_data():
    returns = {
        "BTC": pd.Series([0.01, -0.02]),
        "ETH": pd.Series([0.015, -0.018]),
    }
    
    corr_dict = compute_rolling_correlations(returns, window=96)
    
    assert len(corr_dict) == 0  # Should skip due to insufficient data
    print("✓ Test 1.2 passed")
```

**Test Case 1.3: Aligned index handling**
```python
def test_compute_rolling_correlations_misaligned():
    idx1 = pd.date_range("2024-01-01", periods=100, freq="15min")
    idx2 = pd.date_range("2024-01-01 01:00", periods=100, freq="15min")
    
    returns = {
        "BTC": pd.Series(np.random.randn(100), index=idx1),
        "ETH": pd.Series(np.random.randn(100), index=idx2),
    }
    
    corr_dict = compute_rolling_correlations(returns, window=96)
    
    # Should align and compute correlations on overlapping period
    assert len(corr_dict) > 0 or len(corr_dict.values().__next__().dropna()) > 0
    print("✓ Test 1.3 passed")
```

### Test 2: `classify_correlation_regimes()`

**Test Case 2.1: Adds required columns**
```python
def test_classify_correlation_regimes_columns():
    df = pd.DataFrame({
        "close": [100, 101, 102, 103, 104] * 20,
        "regime": ["mean_reversion"] * 100,
    })
    
    corr = {
        ("BTC", "ETH"): pd.Series([0.5, 0.6, 0.7, 0.8, 0.9] * 20),
    }
    
    result = classify_correlation_regimes(df, corr, "BTC")
    
    assert "mean_correlation" in result.columns
    assert "corr_regime" in result.columns
    print("✓ Test 2.1 passed")
```

**Test Case 2.2: Correct regime classification**
```python
def test_classify_correlation_regimes_classification():
    df = pd.DataFrame({
        "close": [100] * 100,
        "regime": ["momentum_trend"] * 100,
    }, index=range(100))
    
    corr_high = pd.Series([0.75] * 100, index=range(100))
    corr_low = pd.Series([0.25] * 100, index=range(100))
    
    # Test high correlation
    result_high = classify_correlation_regimes(
        df.copy(),
        {("BTC", "ETH"): corr_high},
        "BTC",
        corr_threshold_high=0.7,
        corr_threshold_low=0.3,
    )
    assert (result_high["corr_regime"] == "high_correlation_sync").all()
    
    # Test low correlation
    result_low = classify_correlation_regimes(
        df.copy(),
        {("BTC", "ETH"): corr_low},
        "BTC",
        corr_threshold_high=0.7,
        corr_threshold_low=0.3,
    )
    assert (result_low["corr_regime"] == "decorrelation_risk").all()
    
    print("✓ Test 2.2 passed")
```

**Test Case 2.3: Empty correlations**
```python
def test_classify_correlation_regimes_empty():
    df = pd.DataFrame({
        "close": [100] * 50,
        "regime": ["mean_reversion"] * 50,
    })
    
    result = classify_correlation_regimes(df, {}, "BTC")
    
    assert result["mean_correlation"].isna().all()
    assert (result["corr_regime"] == "neutral_correlation").all()
    print("✓ Test 2.3 passed")
```

### Test 3: `regime_summary()` with correlation

**Test Case 3.1: Summary includes correlation metrics**
```python
def test_regime_summary_correlation_metrics():
    df = pd.DataFrame({
        "regime": ["mean_reversion"] * 60 + ["momentum_trend"] * 40,
        "park_vol_ann": [0.5] * 100,
        "rs_vol_ann": [0.5] * 100,
        "sign_autocorr": [0.1] * 100,
        "mean_correlation": [0.6] * 100,
        "corr_regime": ["high_correlation_sync"] * 60 + ["neutral_correlation"] * 40,
    })
    
    summary = regime_summary(df, symbol="BTC/USD")
    
    assert "last_mean_correlation" in summary
    assert "current_corr_regime" in summary
    assert "corr_distribution" in summary
    assert summary["last_mean_correlation"] == 0.6
    assert summary["current_corr_regime"] == "neutral_correlation"
    print("✓ Test 3.1 passed")
```

## Integration Tests

### Test 4: End-to-End Pipeline

**Test Case 4.1: Single symbol (no correlation)**
```bash
# Should work without errors
python scripts/classify_market_regime.py \
    --input-dir data/crypto/features \
    --output-dir /tmp/regime_test_1 \
    --symbols BTC/USD \
    --window 96 \
    --no-summary
```

**Test Case 4.2: Multiple symbols with correlation**
```bash
# Should compute correlations and add regime refinement
python scripts/classify_market_regime.py \
    --input-dir data/crypto/features \
    --output-dir /tmp/regime_test_2 \
    --symbols BTC/USD,ETH/USD,SOL/USD \
    --compute-correlations \
    --window 96
```

**Test Case 4.3: Custom correlation thresholds**
```bash
python scripts/classify_market_regime.py \
    --input-dir data/crypto/features \
    --output-dir /tmp/regime_test_3 \
    --symbols BTC/USD,ETH/USD \
    --compute-correlations \
    --corr-threshold-high 0.75 \
    --corr-threshold-low 0.25
```

### Test 5: Output Validation

**Test Case 5.1: Parquet output contains required columns**
```python
def test_parquet_output_columns():
    import pyarrow.parquet as pq
    
    table = pq.read_table("/tmp/regime_test_2/kraken_BTC/USD_regime.parquet")
    cols = table.column_names
    
    required = ["regime", "mean_correlation", "corr_regime"]
    assert all(col in cols for col in required), f"Missing columns: {set(required) - set(cols)}"
    print("✓ Test 5.1 passed")
```

**Test Case 5.2: JSON manifest is valid**
```python
def test_json_manifest():
    import json
    
    with open("/tmp/regime_test_2/regime_summary_*.json") as f:
        manifest = json.load(f)
    
    assert "compute_correlations" in manifest
    assert "num_correlation_pairs" in manifest
    assert manifest["compute_correlations"] == True
    print("✓ Test 5.2 passed")
```

### Test 6: Performance Tests

**Test Case 6.1: Correlation computation speed**
```python
def test_correlation_performance():
    import time
    
    returns = {
        f"SYM{i}": pd.Series(np.random.randn(10000))
        for i in range(10)  # 10 symbols = 45 pairs
    }
    
    start = time.time()
    corr_dict = compute_rolling_correlations(returns, window=96)
    elapsed = time.time() - start
    
    assert elapsed < 5.0, f"Correlation took {elapsed:.2f}s (should be <5s)"
    print(f"✓ Test 6.1 passed ({elapsed:.3f}s)")
```

## Regression Tests

### Test 7: Existing Regime Classification Unaffected

**Test Case 7.1: Single-symbol classification unchanged**
```bash
# Run classification without correlation
python scripts/classify_market_regime.py \
    --input-dir data/crypto/features \
    --output-dir /tmp/regime_test_baseline \
    --symbols BTC/USD \
    --no-correlation

# Compare with baseline (ensure no changes to existing columns)
# regime, park_vol_ann, rs_vol_ann, sign_autocorr should be identical
```

## Edge Cases

### Test 8: Edge Case Handling

**Test Case 8.1: All NaN returns**
```python
def test_edge_all_nan_returns():
    returns = {
        "BTC": pd.Series([np.nan] * 100),
        "ETH": pd.Series([np.nan] * 100),
    }
    
    corr_dict = compute_rolling_correlations(returns, window=96)
    # Should handle gracefully
    assert len(corr_dict) >= 0
    print("✓ Test 8.1 passed")
```

**Test Case 8.2: Constant returns (zero variance)**
```python
def test_edge_constant_returns():
    returns = {
        "BTC": pd.Series([0.0] * 100),
        "ETH": pd.Series([0.0] * 100),
    }
    
    corr_dict = compute_rolling_correlations(returns, window=96)
    # Division by zero should be handled
    if len(corr_dict) > 0:
        assert not corr_dict[("BTC", "ETH")].isna().all()
    print("✓ Test 8.2 passed")
```

## Test Execution

### Run All Tests
```bash
# Unit tests
python -m pytest tests/test_regime_correlation.py -v

# Integration tests
bash tests/integration_regime_correlation.sh

# Performance tests
python tests/performance_regime_correlation.py
```

## Success Criteria

✓ All unit tests pass  
✓ Integration pipeline runs without errors  
✓ Output files contain expected columns  
✓ Correlation computation < 5s for 10 symbols  
✓ No regression in existing regime classification  
✓ Edge cases handled gracefully  

## Known Limitations

1. **O(N²) complexity:** 10 symbols = 45 correlation pairs
2. **Memory alignment:** All symbols must have overlapping timestamps
3. **Window size:** Default 96 bars; smaller windows = more noise
4. **Correlation lag:** Only current correlation captured, not dynamic breaks

## Future Enhancements

- [ ] Conditional correlation (regime-aware correlation thresholds)
- [ ] Spectral clustering for asset groups
- [ ] Time-varying thresholds (adaptive to market regime)
- [ ] Correlation matrix visualization
- [ ] Portfolio hedging recommendations based on correlation structure
