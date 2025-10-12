# VoidBloom Quick Reference Card 🚀

**Last Updated**: October 7, 2025

---

## ⚡ Quick Commands

### Start Everything

```powershell
# Terminal 1: Start Backend API
python start_api.py

# Terminal 2: Start Frontend Dashboard
cd dashboard
npm run dev
```

### Validation & Testing

```powershell
# Validate system health
python scripts/testing/validate_system.py

# Run feature store examples
python examples/feature_store_example.py

# Run reliability examples
python examples/reliability_example.py
```

---

## 🌐 URLs

| Service | URL | Description |
|---------|-----|-------------|
| **Dashboard** | http://localhost:5173/ | React frontend UI |
| **API Docs** | http://127.0.0.1:8001/docs | Swagger interactive API documentation |
| **Health Check** | http://127.0.0.1:8001/health | API health status |
| **SLA Status** | http://127.0.0.1:8001/api/sla/status | Data source SLA metrics |
| **Anomalies** | http://127.0.0.1:8001/api/anomalies | Recent anomaly alerts |

---

## 📝 Key Files

| File | Purpose |
|------|---------|
| `start_api.py` | Start dashboard API server |
| `scripts/testing/validate_system.py` | Validate system health |
| `requirements.txt` | Python dependencies |
| `.env` | API keys configuration |
| `src/api/dashboard_api.py` | REST API with 15 endpoints |
| `src/core/feature_store.py` | Unified feature storage |
| `src/services/reliability.py` | SLA monitoring & circuit breakers |

---

## 🔑 API Endpoints Cheat Sheet

### Monitoring
```
GET  /health                             # API health
GET  /api/sla/status                     # SLA metrics
GET  /api/sla/circuit-breakers           # Circuit breaker states
GET  /api/sla/health                     # Overall system health
```

### Anomaly Detection
```
GET  /api/anomalies                      # Get anomaly alerts
POST /api/anomalies/{id}/acknowledge     # Dismiss alert
```

### Analytics
```
GET  /api/confidence/gem-score/{token}   # GemScore with confidence
GET  /api/confidence/liquidity/{token}   # Liquidity with confidence
GET  /api/correlation/matrix             # Cross-token correlations
GET  /api/orderflow/{token}              # Order book depth
GET  /api/sentiment/trend/{token}        # Twitter sentiment
```

### Feature Store
```
GET  /api/features/{token}               # All features for token
GET  /api/features/schema                # Feature store schema
```

---

## 🐛 Common Issues & Fixes

### Issue: ModuleNotFoundError: No module named 'src'

**Fix**: Use `python start_api.py` instead of `python src/api/dashboard_api.py`

---

### Issue: ImportError or dependency errors

**Fix**: 
```powershell
pip install -r requirements.txt
```

---

### Issue: API returns 401 Unauthorized

**Fix**: Add API keys to `.env` file
```env
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
TWITTER_BEARER_TOKEN=your_token
```

---

### Issue: Frontend can't connect to API

**Fix**: Ensure backend is running
```powershell
# Check if running
curl http://127.0.0.1:8001/health

# If not running, start it
python start_api.py
```

---

### Issue: Circuit breaker stuck OPEN

**Fix**: Wait for timeout (30-120s) or check API for errors
```powershell
# View circuit breaker status
curl http://127.0.0.1:8001/api/sla/circuit-breakers
```

---

## 🎓 Feature Store API

### Register a Feature
```python
from src.core.feature_store import FeatureStore, FeatureCategory, FeatureType, FeatureMetadata

store = FeatureStore()
metadata = FeatureMetadata(
    name="my_score",
    feature_type=FeatureType.NUMERIC,
    category=FeatureCategory.SCORING,
    description="My custom score"
)
store.register_feature(metadata)
```

### Write a Feature Value
```python
# write_feature(feature_name, value, token_symbol, confidence=1.0)
store.write_feature("my_score", 85.5, "LINK", confidence=0.9)
```

### Read a Feature Value
```python
value = store.read_feature("my_score", "LINK")
print(f"Value: {value.value}, Confidence: {value.confidence}")
```

### Read Feature History
```python
history = store.read_feature_history("my_score", "LINK", limit=10)
for value in history:
    print(f"{value.timestamp}: {value.value}")
```

---

## 📊 SLA Monitor API

### Record a Request
```python
from src.services.sla_monitor import SLAMonitor

monitor = SLAMonitor("my_service")
monitor.record_request(latency_ms=150.0, success=True)
```

### Get Metrics
```python
metrics = monitor.get_metrics()
print(f"p95 latency: {metrics.latency_p95}ms")
print(f"Success rate: {metrics.success_rate * 100}%")
```

---

## 🔧 Circuit Breaker API

### Use Circuit Breaker
```python
from src.services.circuit_breaker import CircuitBreaker, CircuitState

breaker = CircuitBreaker("my_api")

if breaker.state == CircuitState.OPEN:
    print("Circuit is open, failing fast")
else:
    try:
        # Make API call
        result = breaker.call(my_api_function, arg1, arg2)
    except Exception as e:
        print(f"Call failed: {e}")
```

---

## 📈 Performance Tips

### Cache Hits
- First request: ~500ms (API call)
- Subsequent requests: ~50ms (cache hit)
- **10× speedup** with caching

### Circuit Breakers
- Fail-fast: <10ms (when OPEN)
- Normal: API latency (100-1500ms)
- **30× faster** failure handling

### Feature Store
- In-memory reads: <1ms
- With persistence: <5ms
- Time-series queries: <20ms

---

## 🎯 System Status at a Glance

Run this to check everything:
```powershell
python scripts/testing/validate_system.py
```

Expected output:
```
Imports              ✅ PASS
Feature Store        ✅ PASS
SLA Monitor          ✅ PASS
Circuit Breaker      ✅ PASS

Results: 4/4 tests passed

🎉 All systems operational! Ready for production.
```

---

## 📚 Full Documentation

- `INSTALLATION_SUCCESS.md` - Installation guide
- `DEPLOYMENT_GUIDE.md` - Production deployment
- `docs/ROADMAP_COMPLETION_SUMMARY.md` - Implementation details
- `docs/FEATURE_STORE_IMPLEMENTATION.md` - Feature store architecture
- `docs/RELIABILITY_IMPLEMENTATION.md` - SLA/circuit breaker design

---

## 🎉 Success Indicators

✅ `python scripts/testing/validate_system.py` passes 4/4 tests  
✅ `python start_api.py` starts without errors  
✅ http://127.0.0.1:8001/health returns `{"status":"ok"}`  
✅ http://127.0.0.1:8001/docs shows 15+ endpoints  
✅ `cd dashboard && npm run dev` starts frontend  
✅ http://localhost:5173/ loads dashboard UI

**If all green ✅ → You're ready to trade! 🚀**

---

**Need Help?** Run `python scripts/testing/validate_system.py` to diagnose issues.
