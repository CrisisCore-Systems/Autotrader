# VoidBloom Deployment Guide

**Version**: 2.0.0  
**Last Updated**: October 7, 2025

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- Python 3.10+ installed
- Node.js 18+ installed
- Git repository cloned
- API keys ready (see Configuration section)

### 1. Install Backend Dependencies

```powershell
# Navigate to project root
cd c:\Users\kay\Documents\Projects\AutoTrader\Autotrader

# Install Python dependencies
pip install -r requirements.txt

# Verify installation
python -c "from src.core.feature_store import FeatureStore; print('✅ Backend ready')"
```

### 2. Configure API Keys

Create `.env` file in project root:

```env
# Required: CEX APIs (Binance)
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

# Optional: Additional CEX (Bybit)
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret

# Required: Twitter API v2
TWITTER_BEARER_TOKEN=your_twitter_bearer_token

# Optional: Groq AI (for narratives)
GROQ_API_KEY=your_groq_api_key

# Optional: Etherscan (for contract verification)
ETHERSCAN_API_KEY=your_etherscan_api_key
```

**API Key Acquisition**:
- **Binance**: https://www.binance.com/en/my/settings/api-management
- **Twitter**: https://developer.twitter.com/en/portal/dashboard
- **Groq**: https://console.groq.com/keys
- **Etherscan**: https://etherscan.io/myapikey

### 3. Start Backend API

```powershell
# Start enhanced dashboard API
python src/api/dashboard_api.py

# Verify API is running
# Open browser: http://127.0.0.1:8001/docs (Swagger UI)
# Or test health: curl http://127.0.0.1:8001/health
```

**Expected Output**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001 (Press CTRL+C to quit)
```

### 4. Start Frontend Dashboard

```powershell
# Navigate to dashboard folder
cd dashboard

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

**Expected Output**:
```
  VITE v4.5.0  ready in 500 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### 5. Access Dashboard

Open browser: **http://localhost:5173/**

You should see:
- SLA Dashboard showing data source health
- Anomaly Alerts showing recent detections
- Token list with gem scores

---

## 📋 Detailed Setup

### Backend Architecture

```
src/
├── api/
│   └── dashboard_api.py          # REST API (15 endpoints)
├── core/
│   ├── feature_store.py          # Unified feature storage
│   ├── orderflow_clients.py      # CEX/DEX clients
│   └── twitter_client.py         # Twitter API v2
├── services/
│   ├── feature_engineering.py    # Feature transforms
│   ├── orderflow.py              # Multi-exchange aggregation
│   ├── twitter.py                # Sentiment analysis
│   ├── reliability.py            # SLA + circuit breakers
│   ├── sla_monitor.py            # SLA tracking
│   ├── circuit_breaker.py        # Failure handling
│   └── cache_policy.py           # Adaptive caching
```

### Frontend Architecture

```
dashboard/
├── src/
│   ├── components/
│   │   ├── SLADashboard.tsx      # Real-time SLA monitoring
│   │   ├── AnomalyAlerts.tsx     # Anomaly detection UI
│   │   ├── TokenList.tsx         # Token grid view
│   │   └── TokenDetail.tsx       # Detailed token view
│   ├── api.ts                    # API client
│   ├── types.ts                  # TypeScript interfaces
│   └── App.tsx                   # Main application
├── package.json
└── vite.config.ts
```

---

## 🔧 Configuration

### SLA Thresholds

Edit `src/services/reliability.py`:

```python
# Default SLA thresholds
SLA_DEFAULTS = {
    "binance": {"p50": 200, "p95": 500, "p99": 1000},  # ms
    "bybit": {"p50": 250, "p95": 600, "p99": 1200},
    "dexscreener": {"p50": 300, "p95": 800, "p99": 1500},
    "twitter": {"p50": 500, "p95": 1500, "p99": 3000},
    "coingecko": {"p50": 400, "p95": 1000, "p99": 2000},
}
```

### Circuit Breaker Tuning

Edit `src/services/circuit_breaker.py`:

```python
# Failure thresholds
failure_threshold: int = 5      # Open after 5 failures
timeout: float = 60.0           # Wait 60s before retry (HALF_OPEN)
recovery_threshold: int = 3     # Close after 3 successes
```

### Cache TTL Policy

Edit `src/services/cache_policy.py`:

```python
# Default TTLs by data type
DEFAULT_TTLS = {
    CachePolicy.MARKET_DATA: 60.0,      # 1 minute
    CachePolicy.ORDERBOOK: 10.0,        # 10 seconds
    CachePolicy.SOCIAL: 300.0,          # 5 minutes
    CachePolicy.ONCHAIN: 60.0,          # 1 minute
    CachePolicy.AGGREGATED: 30.0,       # 30 seconds
}
```

### Feature Store Schema

No configuration needed - schema is auto-registered on first write.

View schema: `GET /api/features/schema`

---

## 🧪 Testing

### 1. Backend Health Check

```powershell
# Test API health
curl http://127.0.0.1:8001/health

# Expected: {"status":"ok"}
```

### 2. Feature Store Example

```powershell
# Run comprehensive examples
python examples/feature_store_example.py

# Expected: 7 examples showing basic usage, time-series, vectors, etc.
```

### 3. Reliability Example

```powershell
# Test SLA monitoring + circuit breakers
python examples/reliability_example.py

# Expected: Latency tracking, circuit breaker state transitions, cache hits
```

### 4. Order Flow Example

```powershell
# Test CEX/DEX order flow
python examples/orderflow_example.py

# Expected: Binance/Bybit/Dex order book snapshots, aggregated view
```

### 5. Twitter Example

```powershell
# Test Twitter API v2 + sentiment
python examples/twitter_example.py

# Expected: Tweet search, sentiment analysis, engagement metrics
```

### 6. Frontend Component Tests

```powershell
cd dashboard
npm run build

# Expected: Build success, no TypeScript errors
```

---

## 📊 Monitoring

### SLA Dashboard

Access: `http://localhost:5173/` → SLA Dashboard tab

**Metrics**:
- **Latency**: p50, p95, p99 response times
- **Success Rate**: % of successful requests
- **Uptime**: % availability
- **Circuit Breakers**: CLOSED (healthy), OPEN (failing), HALF_OPEN (recovering)

**Color Coding**:
- 🟢 Green: All metrics healthy
- 🟡 Yellow: Degraded performance (p95 > target)
- 🔴 Red: Failed (success rate < 95% OR circuit OPEN)

### Anomaly Alerts

Access: `http://localhost:5173/` → Anomaly Alerts tab

**Alert Types**:
- 📈 **Price Spike**: >10% price change in <1h
- 📊 **Volume Surge**: >3× average volume
- 💧 **Liquidity Drain**: >30% liquidity decrease
- 💬 **Sentiment Shift**: Large sentiment change + high engagement

**Severity Levels**:
- 🔴 Critical: Immediate action required
- 🟠 High: Monitor closely
- 🟡 Medium: Investigate when possible
- 🔵 Low: Informational

### API Endpoints

**Health**: `GET /health`  
**All Anomalies**: `GET /api/anomalies?severity=high&limit=20`  
**SLA Status**: `GET /api/sla/status`  
**Circuit Breakers**: `GET /api/sla/circuit-breakers`  
**Feature Schema**: `GET /api/features/schema`

---

## 🐛 Troubleshooting

### Issue: Backend API won't start

**Symptoms**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```powershell
pip install -r requirements.txt
```

---

### Issue: Frontend build fails

**Symptoms**: `Cannot find module 'vite'`

**Solution**:
```powershell
cd dashboard
rm -rf node_modules package-lock.json
npm install
```

---

### Issue: CORS errors in browser

**Symptoms**: `Access to fetch at 'http://127.0.0.1:8001/api/...' from origin 'http://localhost:5173' has been blocked`

**Solution**: 
- Ensure backend API is running on port 8001
- Check `allow_origins` in `dashboard_api.py` includes `http://localhost:5173`

---

### Issue: API returns 401 Unauthorized

**Symptoms**: `{"detail":"Unauthorized"}`

**Solution**:
- Verify API keys in `.env` file
- Check Binance/Twitter API key permissions
- Ensure API keys are not expired

---

### Issue: Circuit breaker stuck in OPEN state

**Symptoms**: SLA Dashboard shows red circuit breaker, requests fail immediately

**Solution**:
```powershell
# Reset circuit breaker manually
curl -X POST http://127.0.0.1:8001/api/sla/circuit-breakers/binance/reset

# Or restart API
# CTRL+C to stop
python src/api/dashboard_api.py
```

---

### Issue: Feature store returns empty results

**Symptoms**: `GET /api/features/{token}` returns `{"features":[]}`

**Solution**:
- Features are written on-demand by scanner/services
- Run scanner to populate features:
  ```powershell
  python main.py  # Main scanner
  ```
- Or manually populate via feature store:
  ```python
  from src.core.feature_store import feature_store
  feature_store.write_feature("liquidity_score", "LINK", 85.5)
  ```

---

## 🔐 Security

### Production Hardening

Before deploying to production:

1. **Replace CORS wildcard**:
   ```python
   # dashboard_api.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://yourdomain.com"],  # Specific domains only
       allow_credentials=True,
       allow_methods=["GET", "POST"],
       allow_headers=["*"],
   )
   ```

2. **Add API authentication**:
   ```python
   from fastapi.security import HTTPBearer
   
   security = HTTPBearer()
   
   @app.get("/api/secure-endpoint")
   async def secure_endpoint(credentials: HTTPBearer = Depends(security)):
       # Verify token
       pass
   ```

3. **Rate limiting**:
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   
   @app.get("/api/limited-endpoint")
   @limiter.limit("5/minute")
   async def limited_endpoint(request: Request):
       pass
   ```

4. **HTTPS only**:
   ```python
   # Deploy behind reverse proxy (Nginx, Caddy)
   # Force HTTPS redirects
   ```

5. **Environment variables**:
   ```powershell
   # Never commit .env to git
   echo ".env" >> .gitignore
   
   # Use secrets manager in production (AWS Secrets Manager, Azure Key Vault)
   ```

---

## 📈 Performance Optimization

### Cache Warmup

Pre-populate cache for frequently accessed tokens:

```python
from src.services.cache_policy import cache_manager

# Warmup top 10 tokens
tokens = ["LINK", "UNI", "AAVE", "PEPE", "DOGE", "SHIB", "MATIC", "ARB", "OP", "APE"]
for token in tokens:
    # Trigger API calls to populate cache
    pass
```

### Database Backend

For production, replace in-memory storage with Redis:

```python
# feature_store.py
import redis

class FeatureStore:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379, db=0)
    
    def write_feature(self, name, entity_id, value):
        key = f"feature:{name}:{entity_id}"
        self.redis.setex(key, 3600, json.dumps(value))  # 1 hour TTL
```

### Load Balancing

For high traffic, run multiple API instances:

```yaml
# docker-compose.yml
services:
  api:
    image: voidbloom-api:latest
    deploy:
      replicas: 3
    ports:
      - "8001-8003:8001"
```

---

## 📚 Additional Resources

### Documentation

- `docs/ROADMAP_COMPLETION_SUMMARY.md` - Full implementation details
- `docs/FEATURE_STORE_IMPLEMENTATION.md` - Feature store architecture
- `docs/RELIABILITY_IMPLEMENTATION.md` - SLA/circuit breaker design
- `docs/signal_coverage_audit.md` - Signal coverage analysis
- `docs/QUICKSTART_NEW_SIGNALS.md` - Adding new data sources

### Examples

- `examples/feature_store_example.py` - 7 comprehensive examples
- `examples/reliability_example.py` - SLA monitoring demo
- `examples/orderflow_example.py` - CEX/DEX integration
- `examples/twitter_example.py` - Twitter sentiment analysis

### API Documentation

Swagger UI: `http://127.0.0.1:8001/docs`  
ReDoc: `http://127.0.0.1:8001/redoc`

---

## 🎉 You're Ready!

Your VoidBloom Hidden Gem Scanner is now fully operational with:

- ✅ Real-time data from 4+ sources (Binance, Bybit, Dexscreener, Twitter)
- ✅ Enterprise-grade reliability (SLA monitoring, circuit breakers, caching)
- ✅ Unified feature management (9 categories, versioning, time-series)
- ✅ Advanced dashboard (anomaly detection, confidence intervals, correlations)

**Start scanning**: `python main.py`  
**Monitor health**: `http://localhost:5173/`  
**API docs**: `http://127.0.0.1:8001/docs`

---

**Questions?** Check `docs/` folder or file an issue on GitHub.

**Happy Scanning!** 🚀
