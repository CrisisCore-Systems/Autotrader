"""Test BounceHunter model caching system."""

print("=" * 80)
print("BounceHunter Model Caching Test Guide")
print("=" * 80)
print()

print("🎯 FEATURE: Model Persistence & Caching")
print("-" * 80)
print("""
The BounceHunter now includes:
✅ Model serialization (pickle)
✅ Disk-based caching with versioning
✅ Automatic staleness detection
✅ Incremental training support
✅ Config change detection
✅ Cache management APIs
""")

print()
print("📊 PERFORMANCE BENEFITS")
print("-" * 80)
print("""
First Scan (Cold):    ~30-60 seconds  (Downloads data + trains model)
Cached Scan (Warm):   ~5-10 seconds   (Loads from disk)
Incremental Update:   ~15-30 seconds  (Adds new tickers only)

Cache Location: ./model_cache/
Cache Lifetime: 24 hours (configurable)
Storage Format: Pickle (binary)
""")

print()
print("=" * 80)
print("TEST 1: First Scan (Cold Cache)")
print("=" * 80)
print("""
$json = @'
{
  "tickers": ["AAPL", "MSFT", "GOOGL"]
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/scan' `
    -Method POST `
    -Body $json `
    -ContentType 'application/json' | ConvertTo-Json -Depth 5

Expected Output:
- Training from scratch
- Downloads 7 years of data
- Trains logistic regression model
- Saves to cache: ./model_cache/bouncehunter_<hash>.pkl
- Returns: cache_info.cached = false (first run)
""")

print()
print("=" * 80)
print("TEST 2: Second Scan (Warm Cache)")
print("=" * 80)
print("""
# Run the SAME command again immediately:
$json = @'
{
  "tickers": ["AAPL", "MSFT", "GOOGL"]
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/scan' `
    -Method POST `
    -Body $json `
    -ContentType 'application/json' | ConvertTo-Json -Depth 5

Expected Output:
- Loads from cache (MUCH FASTER!)
- Skips data download
- Skips training
- Returns: cache_info.cached = true, age_hours = 0.XX
- Response time: ~5-10 seconds vs ~30-60 seconds
""")

print()
print("=" * 80)
print("TEST 3: Cache Information")
print("=" * 80)
print("""
# Check cache status
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/info' `
    -Method GET | ConvertTo-Json -Depth 5

Returns:
{
  "cached": true,
  "version": "1.0",
  "created_at": "2025-10-29T01:45:00",
  "last_updated": "2025-10-29T01:45:00",
  "age_hours": 0.5,
  "is_stale": false,
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "training_samples": 632,
  "model_hash": "a1b2c3d4e5f6g7h8",
  "performance_metrics": {}
}
""")

print()
print("=" * 80)
print("TEST 4: List All Cached Models")
print("=" * 80)
print("""
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/list' `
    -Method GET | ConvertTo-Json -Depth 5

Returns:
{
  "total_models": 2,
  "models": [
    {
      "version": "1.0",
      "created_at": "2025-10-29T01:45:00",
      "last_updated": "2025-10-29T01:45:00",
      "tickers": ["AAPL", "MSFT", "GOOGL"],
      "training_samples": 632,
      "config_hash": "abc123",
      "model_hash": "xyz789"
    },
    ...
  ]
}
""")

print()
print("=" * 80)
print("TEST 5: Force Refresh (Ignore Cache)")
print("=" * 80)
print("""
# Force retraining even if cache exists
$json = @'
{
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "force_refresh": true
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/scan' `
    -Method POST `
    -Body $json `
    -ContentType 'application/json' | ConvertTo-Json -Depth 5

Use Cases:
- Get latest data immediately
- Config changed significantly
- Debugging training issues
- Suspecting stale cache
""")

print()
print("=" * 80)
print("TEST 6: Incremental Training")
print("=" * 80)
print("""
# Add new tickers without full retraining
$json = @'
{
  "new_tickers": ["TSLA", "AMD", "NVDA"]
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/train/incremental' `
    -Method POST `
    -Body $json `
    -ContentType 'application/json' | ConvertTo-Json -Depth 5

How It Works:
1. Loads existing cached model + data
2. Downloads data for new tickers only
3. Merges new samples with existing training data
4. Retrains model on combined dataset
5. Saves updated model to cache

Benefits:
- Faster than full retraining
- Preserves existing ticker data
- Cumulative learning
- No data loss
""")

print()
print("=" * 80)
print("TEST 7: Custom Cache Age")
print("=" * 80)
print("""
# Use cache only if less than 12 hours old
$json = @'
{
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "max_cache_age_hours": 12
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/scan' `
    -Method POST `
    -Body $json `
    -ContentType 'application/json' | ConvertTo-Json -Depth 5

Use Cases:
- Intraday trading: 1-4 hours
- Daily scanning: 24 hours (default)
- Weekly analysis: 168 hours (7 days)
""")

print()
print("=" * 80)
print("TEST 8: Clear Cache")
print("=" * 80)
print("""
# Clear ALL cached models
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/clear' `
    -Method DELETE | ConvertTo-Json -Depth 5

# Clear models older than 7 days
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/cache/clear?older_than_days=7' `
    -Method DELETE | ConvertTo-Json -Depth 5

Returns:
{
  "cleared": 2,
  "message": "Cleared 2 cached model(s)"
}
""")

print()
print("=" * 80)
print("TEST 9: Disable Caching")
print("=" * 80)
print("""
# Always train fresh (no cache)
$json = @'
{
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "use_cache": false
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/bouncehunter/scan' `
    -Method POST `
    -Body $json `
    -ContentType 'application/json' | ConvertTo-Json -Depth 5

Use Cases:
- Testing/debugging
- Need guaranteed fresh data
- One-off scans
- Benchmarking performance
""")

print()
print("=" * 80)
print("CACHE INTERNALS")
print("=" * 80)
print("""
File Structure:
├── model_cache/
│   ├── bouncehunter_abc123.pkl       (Model + artifacts)
│   ├── bouncehunter_abc123_meta.pkl  (Metadata only)
│   ├── bouncehunter_xyz789.pkl
│   └── bouncehunter_xyz789_meta.pkl

Cache Key (Config Hash):
- Computed from: tickers, start date, thresholds, hyperparameters
- Changes trigger new cache entry
- Multiple configs can coexist

Model Versioning:
- Version field in metadata
- Model hash for integrity checking
- Config hash for compatibility
- Timestamp for staleness detection

What Gets Cached:
✅ Trained ML model (CalibratedClassifierCV)
✅ Training dataset (DataFrame)
✅ Artifacts (historical data per ticker)
✅ VIX cache (market regime data)
✅ Metadata (timestamps, hashes, metrics)

What Doesn't Get Cached:
❌ Live scan results (always fresh)
❌ Current prices (fetched on demand)
❌ Signal calculations (computed real-time)
""")

print()
print("=" * 80)
print("BEST PRACTICES")
print("=" * 80)
print("""
1. ✅ Development: use_cache=true, max_age=1 hour
   - Fast iteration
   - Fresh enough for testing

2. ✅ Production: use_cache=true, max_age=24 hours
   - Fast API responses
   - Daily model refresh
   - Balance speed & freshness

3. ✅ Research: use_cache=false
   - Guaranteed reproducibility
   - Full control over training

4. ✅ Adding Tickers: Use incremental training
   - Faster than full retrain
   - Preserves existing work

5. ✅ Major Config Changes: force_refresh=true
   - Ensures model matches new params
   - Invalidates stale cache

6. ✅ Disk Space Management:
   - Monitor ./model_cache/ size
   - Clear old models periodically
   - Each model ~5-50 MB depending on tickers
""")

print()
print("=" * 80)
print("TROUBLESHOOTING")
print("=" * 80)
print("""
Q: Cache not loading?
A: Check config_hash matches. Config changes invalidate cache.

Q: Scans still slow with cache?
A: Check cache_info.cached in response. May be stale or missing.

Q: Models growing too large?
A: Reduce ticker count or clear old caches periodically.

Q: Want to force fresh data?
A: Use force_refresh=true or disable caching.

Q: Incremental training failing?
A: Requires existing cache. Run full scan first.

Q: How to reset everything?
A: DELETE /cache/clear then scan with force_refresh=true
""")

print()
print("=" * 80)
print("🚀 Model caching is now live! Start testing with commands above.")
print("=" * 80)
