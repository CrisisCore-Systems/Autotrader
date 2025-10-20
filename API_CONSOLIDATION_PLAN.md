# API Consolidation Plan

**Status:** PLANNED (Not Yet Implemented)  
**Estimated Effort:** 5-7 days  
**Priority:** Medium (Deferred after completing 9 critical improvements)  
**Created:** October 18, 2025

---

## 🎯 Executive Summary

AutoTrader currently has **3 separate FastAPI applications** serving **40+ endpoints** across different modules. This creates:
- ❌ **Port conflicts** when running multiple services
- ❌ **Inconsistent API paths** (some use `/api/`, others don't)
- ❌ **Duplicated middleware** (CORS, logging, rate limiting)
- ❌ **Complex deployment** (3 separate processes to manage)
- ❌ **Fragmented documentation** (no unified OpenAPI spec)

**Goal:** Consolidate into a single unified API with versioned endpoints (`/api/v1/`) following REST best practices.

---

## 📊 Current API Landscape

### 1. **src/api/main.py** (Scanner API - **NEW**, Rate Limited)
```
Port: 8000 (assumed)
Endpoints: 4 total
├── GET  /                         (60/min) - Root status
├── GET  /health                   (120/min) - Health check
├── GET  /api/tokens/              (30/min) - List tokens
└── GET  /api/tokens/{symbol}      (10/min) - Token detail scan
```

**Status:** ✅ Latest code with slowapi rate limiting  
**Lines:** 87  
**Features:** Strict env validation, CORS, rate limiting  
**Dependencies:** Routes imported from `src/api/routes/tokens.py`

---

### 2. **src/api/dashboard_api.py** (Dashboard API - LARGEST)
```
Port: 8001 (assumed)
Endpoints: 21 total
├── GET  /                              - Root
├── GET  /api/tokens                    - Token list (duplicates main.py)
├── GET  /api/tokens/{symbol}           - Token detail (duplicates main.py)
├── GET  /api/anomalies                 - Anomaly alerts
├── POST /api/anomalies/{id}/acknowledge - Acknowledge alert
├── GET  /api/confidence/gem-score/{symbol} - Confidence interval
├── GET  /api/confidence/liquidity/{symbol} - Liquidity confidence
├── GET  /api/sla/status                - SLA monitoring
├── GET  /api/sla/circuit-breakers      - Circuit breaker status
├── GET  /api/sla/health                - SLA health
├── GET  /api/correlation/matrix        - Token correlations
├── GET  /api/orderflow/{symbol}        - Order flow snapshot
├── GET  /api/sentiment/trend/{symbol}  - Sentiment trend
├── GET  /api/features/{symbol}         - Feature store data
├── GET  /api/features/schema           - Feature schema
├── GET  /api/gemscore/delta/{symbol}   - Gem score delta
├── GET  /api/gemscore/delta/{symbol}/narrative - Delta narrative
├── GET  /api/gemscore/delta/{symbol}/detailed - Detailed delta
├── GET  /api/gemscore/history/{symbol} - Score history
├── GET  /api/gemscore/deltas/{symbol}/series - Delta series
└── GET  /api/summary/{symbol}          - Token summary
```

**Status:** ⚠️ Production code, NO rate limiting  
**Lines:** 1,217  
**Features:** Prometheus instrumentation, startup/shutdown events, detailed Pydantic models  
**Dependencies:** `FeatureStore`, `HiddenGemScanner`, `SLA_REGISTRY`, `CIRCUIT_REGISTRY`

---

### 3. **src/microstructure/api.py** (Microstructure Detection API)
```
Port: 8002 (assumed)
Endpoints: 6 total
├── GET  /                      - Root info
├── GET  /health                - Health check
├── POST /api/v1/signals        - Submit detection signal
├── GET  /api/v1/signals        - Query signals
├── GET  /api/v1/metrics        - Detection metrics
└── GET  /metrics               - Prometheus metrics
```

**Status:** ⚠️ Production code, NO rate limiting  
**Lines:** 382  
**Features:** Prometheus metrics, background signal processing, in-memory signal storage  
**Dependencies:** `DetectionSignal`, Prometheus client

---

## 🔄 Proposed Unified Structure

```
src/api/
├── main.py                     # Main FastAPI app with consolidated setup
├── dependencies.py             # Shared dependencies (rate limiter, auth, etc.)
├── middleware.py               # Consolidated middleware (CORS, logging, Prometheus)
├── config.py                   # API configuration and env validation
├── v1/
│   ├── __init__.py
│   ├── routers/
│   │   ├── tokens.py           # GET /api/v1/tokens (from main.py + dashboard)
│   │   ├── anomalies.py        # GET/POST /api/v1/anomalies
│   │   ├── analytics.py        # GET /api/v1/analytics/* (correlations, sentiment, etc.)
│   │   ├── features.py         # GET /api/v1/features/* (feature store)
│   │   ├── gemscore.py         # GET /api/v1/gemscore/* (score tracking)
│   │   ├── monitoring.py       # GET /api/v1/monitoring/* (SLA, circuit breakers)
│   │   ├── microstructure.py   # POST/GET /api/v1/signals, /api/v1/metrics
│   │   └── health.py           # GET /api/v1/health (unified health)
│   ├── schemas/
│   │   ├── tokens.py           # TokenResponse, TokenDetail, etc.
│   │   ├── anomalies.py        # AnomalyAlert, AcknowledgeRequest
│   │   ├── analytics.py        # ConfidenceInterval, Correlation, etc.
│   │   ├── features.py         # FeatureResponse, FeatureSchema
│   │   ├── gemscore.py         # GemScoreDelta, GemScoreHistory
│   │   ├── monitoring.py       # SLAStatus, CircuitBreakerStatus
│   │   └── microstructure.py   # SignalRequest, SignalResponse
│   └── services/
│       ├── token_scanner.py    # Business logic for token scanning
│       ├── anomaly_detector.py # Anomaly detection logic
│       ├── feature_store.py    # Feature store integration
│       └── microstructure.py   # Microstructure detection logic
└── legacy/
    ├── dashboard_api.py        # Keep for backward compatibility (deprecated)
    └── microstructure_api.py   # Keep for backward compatibility (deprecated)
```

---

## 🛠️ Implementation Phases

### **Phase 1: Foundation (Days 1-2)**
**Goal:** Set up unified API structure without breaking existing functionality

**Tasks:**
1. ✅ Create `src/api/v1/` directory structure
2. ✅ Create `src/api/config.py` with consolidated env validation
3. ✅ Create `src/api/dependencies.py` with rate limiter setup
4. ✅ Create `src/api/middleware.py` with CORS + Prometheus
5. ✅ Update `src/api/main.py` to include all routers under `/api/v1/`

**Deliverables:**
- New directory structure
- Unified configuration
- Single FastAPI app instance

**Testing:**
- Verify new API starts without errors
- Confirm env validation works
- Test rate limiting on root endpoints

---

### **Phase 2: Token & Scanner Migration (Day 3)**
**Goal:** Consolidate token scanning endpoints (highest priority)

**Tasks:**
1. ✅ Create `src/api/v1/schemas/tokens.py` with unified Pydantic models
2. ✅ Merge token endpoints from `main.py` + `dashboard_api.py`:
   - `GET /api/v1/tokens` (list with pagination)
   - `GET /api/v1/tokens/{symbol}` (detailed scan)
3. ✅ Apply rate limits: 30/min for list, 10/min for detail
4. ✅ Add deprecation warnings to old endpoints in `dashboard_api.py`
5. ✅ Update dashboard frontend to use new endpoints

**Deliverables:**
- `src/api/v1/routers/tokens.py` (consolidated)
- Backward compatibility maintained
- Dashboard consuming new endpoints

**Testing:**
- Verify token list returns correct data
- Verify token detail scan works
- Confirm rate limiting (10/min, 30/min)
- Test pagination
- Ensure old endpoints still work with deprecation headers

---

### **Phase 3: Analytics & Monitoring (Day 4)**
**Goal:** Migrate analytics and monitoring endpoints

**Tasks:**
1. ✅ Create `src/api/v1/routers/analytics.py`:
   - `GET /api/v1/analytics/confidence/gem-score/{symbol}`
   - `GET /api/v1/analytics/confidence/liquidity/{symbol}`
   - `GET /api/v1/analytics/correlation/matrix`
   - `GET /api/v1/analytics/orderflow/{symbol}`
   - `GET /api/v1/analytics/sentiment/{symbol}`
2. ✅ Create `src/api/v1/routers/monitoring.py`:
   - `GET /api/v1/monitoring/sla/status`
   - `GET /api/v1/monitoring/sla/circuit-breakers`
   - `GET /api/v1/monitoring/health`
3. ✅ Create `src/api/v1/routers/anomalies.py`:
   - `GET /api/v1/anomalies`
   - `POST /api/v1/anomalies/{id}/acknowledge`
4. ✅ Apply rate limits (30/min for analytics, 60/min for monitoring)

**Deliverables:**
- 3 new routers with 12 endpoints
- Rate limiting applied
- OpenAPI tags organized

**Testing:**
- Test each analytics endpoint
- Verify monitoring endpoints
- Confirm anomaly detection alerts
- Test acknowledgment workflow

---

### **Phase 4: Feature Store & Gemscore (Day 5)**
**Goal:** Migrate feature engineering and scoring endpoints

**Tasks:**
1. ✅ Create `src/api/v1/routers/features.py`:
   - `GET /api/v1/features/{symbol}`
   - `GET /api/v1/features/schema`
2. ✅ Create `src/api/v1/routers/gemscore.py`:
   - `GET /api/v1/gemscore/{symbol}/delta`
   - `GET /api/v1/gemscore/{symbol}/delta/narrative`
   - `GET /api/v1/gemscore/{symbol}/delta/detailed`
   - `GET /api/v1/gemscore/{symbol}/history`
   - `GET /api/v1/gemscore/{symbol}/deltas/series`
3. ✅ Apply rate limits (10/min for expensive operations)

**Deliverables:**
- 2 new routers with 7 endpoints
- Feature store integration
- Gemscore tracking consolidated

**Testing:**
- Verify feature retrieval
- Test schema endpoint
- Confirm gemscore calculations
- Test historical data retrieval

---

### **Phase 5: Microstructure Integration (Day 6)**
**Goal:** Integrate microstructure detection API

**Tasks:**
1. ✅ Create `src/api/v1/routers/microstructure.py`:
   - `POST /api/v1/signals` (submit detection)
   - `GET /api/v1/signals` (query signals)
   - `GET /api/v1/signals/metrics` (detection metrics)
2. ✅ Migrate Prometheus metrics to unified middleware
3. ✅ Consolidate signal storage (use shared in-memory or Redis)
4. ✅ Apply rate limits (10/min for signal submission)

**Deliverables:**
- Microstructure router integrated
- Prometheus metrics unified
- Signal processing consolidated

**Testing:**
- Submit test signals
- Query signal history
- Verify metrics collection
- Test rate limiting on submissions

---

### **Phase 6: Cleanup & Documentation (Day 7)**
**Goal:** Finalize consolidation and document changes

**Tasks:**
1. ✅ Add deprecation notices to old APIs (301 redirects where possible)
2. ✅ Update `docker-compose.yml` to run single API service
3. ✅ Generate unified OpenAPI spec at `/api/v1/openapi.json`
4. ✅ Create API migration guide for consumers
5. ✅ Update `README.md` with new API structure
6. ✅ Create `API_CONSOLIDATION_COMPLETE.md` documentation
7. ✅ Update Prometheus scrape configs
8. ✅ Archive old API files to `src/api/legacy/`

**Deliverables:**
- Unified API running on single port
- Complete OpenAPI documentation
- Migration guide for API consumers
- Updated deployment configuration

**Testing:**
- Full regression test suite
- Load testing on consolidated API
- Verify all 40+ endpoints functional
- Confirm Prometheus metrics working
- Test backward compatibility redirects

---

## 🔍 Technical Considerations

### **Rate Limiting Strategy**
```python
# Apply different limits based on operation cost
RATE_LIMITS = {
    "expensive_scan": "10/minute",      # Full token scans, signal submissions
    "moderate_query": "30/minute",      # Token lists, analytics queries
    "light_operation": "60/minute",     # Monitoring, health checks
    "health_check": "120/minute",       # High limit for monitoring tools
}
```

### **Backward Compatibility**
- Keep old API files in `src/api/legacy/` for 6 months
- Add `Deprecation` headers to legacy endpoints
- Return 301 redirects where possible
- Document migration path in API responses

### **Middleware Order**
```python
1. CORS (allow all origins for now)
2. Rate Limiting (slowapi)
3. Request Logging (structlog)
4. Prometheus Instrumentation
5. Error Handling (unified exception handlers)
```

### **Configuration Consolidation**
```python
# src/api/config.py
class APIConfig(BaseSettings):
    # Required keys (strict validation)
    GROQ_API_KEY: str
    ETHERSCAN_API_KEY: str
    
    # Optional keys (with defaults)
    COINGECKO_API_KEY: Optional[str] = None
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    
    # API settings
    API_V1_PREFIX: str = "/api/v1"
    API_TITLE: str = "AutoTrader Unified API"
    API_VERSION: str = "1.0.0"
    
    # Rate limiting
    RATE_LIMIT_STORAGE: str = "memory"  # "memory" or "redis"
    
    class Config:
        env_file = ".env"
```

---

## 📋 API Endpoint Mapping

### **Before → After**

#### **Token Endpoints**
| Old Endpoint | New Endpoint | Rate Limit | Notes |
|-------------|--------------|------------|-------|
| `GET /api/tokens/` (main.py) | `GET /api/v1/tokens` | 30/min | Merged with dashboard version |
| `GET /api/tokens` (dashboard) | `GET /api/v1/tokens` | 30/min | Same endpoint, unified response |
| `GET /api/tokens/{symbol}` (main) | `GET /api/v1/tokens/{symbol}` | 10/min | Keep stricter rate limit |
| `GET /api/tokens/{symbol}` (dashboard) | `GET /api/v1/tokens/{symbol}` | 10/min | Merged logic |

#### **Analytics Endpoints**
| Old Endpoint | New Endpoint | Rate Limit | Notes |
|-------------|--------------|------------|-------|
| `GET /api/confidence/gem-score/{s}` | `GET /api/v1/analytics/confidence/gem-score/{s}` | 30/min | Grouped under analytics |
| `GET /api/confidence/liquidity/{s}` | `GET /api/v1/analytics/confidence/liquidity/{s}` | 30/min | Grouped under analytics |
| `GET /api/correlation/matrix` | `GET /api/v1/analytics/correlation/matrix` | 30/min | Grouped under analytics |
| `GET /api/orderflow/{s}` | `GET /api/v1/analytics/orderflow/{s}` | 30/min | Grouped under analytics |
| `GET /api/sentiment/trend/{s}` | `GET /api/v1/analytics/sentiment/{s}` | 30/min | Simplified path |

#### **Monitoring Endpoints**
| Old Endpoint | New Endpoint | Rate Limit | Notes |
|-------------|--------------|------------|-------|
| `GET /api/sla/status` | `GET /api/v1/monitoring/sla/status` | 60/min | Grouped under monitoring |
| `GET /api/sla/circuit-breakers` | `GET /api/v1/monitoring/sla/circuit-breakers` | 60/min | Grouped under monitoring |
| `GET /api/sla/health` | `GET /api/v1/monitoring/health` | 120/min | Simplified path |
| `GET /health` (all 3 APIs) | `GET /api/v1/health` | 120/min | Unified health check |

#### **Feature Store Endpoints**
| Old Endpoint | New Endpoint | Rate Limit | Notes |
|-------------|--------------|------------|-------|
| `GET /api/features/{s}` | `GET /api/v1/features/{s}` | 30/min | Versioned |
| `GET /api/features/schema` | `GET /api/v1/features/schema` | 60/min | Versioned |

#### **Gemscore Endpoints**
| Old Endpoint | New Endpoint | Rate Limit | Notes |
|-------------|--------------|------------|-------|
| `GET /api/gemscore/delta/{s}` | `GET /api/v1/gemscore/{s}/delta` | 30/min | RESTful path |
| `GET /api/gemscore/delta/{s}/narrative` | `GET /api/v1/gemscore/{s}/delta/narrative` | 30/min | RESTful path |
| `GET /api/gemscore/delta/{s}/detailed` | `GET /api/v1/gemscore/{s}/delta/detailed` | 30/min | RESTful path |
| `GET /api/gemscore/history/{s}` | `GET /api/v1/gemscore/{s}/history` | 30/min | RESTful path |
| `GET /api/gemscore/deltas/{s}/series` | `GET /api/v1/gemscore/{s}/deltas/series` | 30/min | RESTful path |

#### **Anomaly Endpoints**
| Old Endpoint | New Endpoint | Rate Limit | Notes |
|-------------|--------------|------------|-------|
| `GET /api/anomalies` | `GET /api/v1/anomalies` | 30/min | Versioned |
| `POST /api/anomalies/{id}/acknowledge` | `POST /api/v1/anomalies/{id}/acknowledge` | 30/min | Versioned |

#### **Microstructure Endpoints**
| Old Endpoint | New Endpoint | Rate Limit | Notes |
|-------------|--------------|------------|-------|
| `POST /api/v1/signals` | `POST /api/v1/signals` | 10/min | Already versioned! Keep as-is |
| `GET /api/v1/signals` | `GET /api/v1/signals` | 30/min | Already versioned! Keep as-is |
| `GET /api/v1/metrics` | `GET /api/v1/signals/metrics` | 60/min | Nest under signals |

---

## 🚨 Breaking Changes

### **Minimal Breaking Changes (By Design)**
✅ Most endpoints get versioned prefix `/api/v1/` but maintain structure  
✅ Old endpoints kept in legacy mode with deprecation headers  
✅ 301 redirects where possible  

### **Actual Breaking Changes**
⚠️ **Port Consolidation:** All APIs now run on **single port** (8000)
- **Impact:** Update docker-compose, nginx configs, client SDKs
- **Mitigation:** Document new port in migration guide

⚠️ **Health Endpoint Unification:** 3 separate `/health` endpoints → 1 unified
- **Impact:** Monitoring tools may need reconfiguration
- **Mitigation:** Old health endpoints redirect to new one

⚠️ **Prometheus Metrics Path:** Multiple `/metrics` endpoints → 1 unified at `/metrics`
- **Impact:** Update Prometheus scrape configs
- **Mitigation:** Document in `prometheus.yml` example

---

## 📦 Deployment Changes

### **Before**
```yaml
# docker-compose.yml
services:
  api-main:
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
  
  api-dashboard:
    command: uvicorn src.api.dashboard_api:app --host 0.0.0.0 --port 8001
  
  api-microstructure:
    command: uvicorn src.microstructure.api:app --host 0.0.0.0 --port 8002
```

### **After**
```yaml
# docker-compose.yml
services:
  api:
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - ETHERSCAN_API_KEY=${ETHERSCAN_API_KEY}
      - COINGECKO_API_KEY=${COINGECKO_API_KEY}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - postgres
```

**Benefits:**
- ✅ Single service to manage
- ✅ Simplified networking (no port conflicts)
- ✅ Easier load balancing (scale single service)
- ✅ Reduced memory footprint (shared app instance)

---

## 🧪 Testing Strategy

### **Unit Tests**
- Test each router independently
- Mock external dependencies (FeatureStore, HiddenGemScanner)
- Verify rate limiting per endpoint
- Test Pydantic validation

### **Integration Tests**
- Test API startup/shutdown lifecycle
- Verify middleware chain works
- Test Prometheus metrics collection
- Confirm database connections

### **Regression Tests**
- Test all 40+ endpoints return expected data
- Verify backward compatibility redirects
- Confirm error handling consistent

### **Load Tests**
- Simulate 1000 req/min across all endpoints
- Verify rate limiting prevents abuse
- Check memory usage under load
- Confirm no memory leaks

---

## 📚 Documentation Deliverables

1. **API_CONSOLIDATION_COMPLETE.md** - Completion summary (like this doc)
2. **MIGRATION_GUIDE.md** - Guide for API consumers updating their code
3. **API_REFERENCE.md** - Complete endpoint reference with examples
4. **OPENAPI_SPEC.json** - Auto-generated OpenAPI 3.0 specification
5. **README.md updates** - Update main README with new API info
6. **CHANGELOG.md entry** - Document breaking changes

---

## ✅ Success Criteria

- [ ] Single FastAPI application running on port 8000
- [ ] All 40+ endpoints functional and tested
- [ ] Rate limiting applied to all endpoints
- [ ] Unified OpenAPI documentation generated
- [ ] Old APIs deprecated with 301 redirects
- [ ] Docker compose simplified to single API service
- [ ] Prometheus metrics consolidated
- [ ] Zero data loss during migration
- [ ] API response times ≤ 200ms (p95)
- [ ] Test coverage ≥ 75% for new code
- [ ] Migration guide published
- [ ] All stakeholders notified of changes

---

## 🔮 Future Enhancements (Post-Consolidation)

1. **Authentication & Authorization**
   - JWT token-based auth
   - API key management
   - Role-based access control (RBAC)

2. **Advanced Rate Limiting**
   - Redis-backed distributed rate limiting
   - Per-user rate limits (not just per-IP)
   - Burst allowances for premium users

3. **API Versioning**
   - `/api/v2/` for breaking changes
   - Deprecation timeline for v1 endpoints

4. **GraphQL Endpoint**
   - Single `/graphql` endpoint
   - Client-side query optimization

5. **WebSocket Support**
   - Real-time token updates
   - Live anomaly alerts
   - Streaming analytics

---

## 📞 Stakeholder Communication

### **Internal Team**
- **Developers:** Share this plan, get feedback on timeline
- **DevOps:** Review deployment changes, update CI/CD
- **QA:** Review testing strategy, assign test scenarios

### **External Consumers**
- **Dashboard Frontend:** Update API client library
- **Third-Party Integrations:** Send migration guide 30 days before
- **Mobile Apps:** Update API endpoints, test backward compatibility

---

## 🛑 Risks & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking existing integrations | High | Medium | Keep old APIs for 6 months, use 301 redirects |
| Performance regression | Medium | Low | Load test before deployment, rollback plan |
| Data inconsistencies | High | Low | Extensive regression testing, staged rollout |
| Rate limiting too strict | Medium | Medium | Monitor 429 errors, adjust limits based on metrics |
| Extended downtime | High | Low | Blue-green deployment, health checks |

---

## 📅 Rollout Plan

### **Stage 1: Development (Days 1-7)**
- Implement consolidation per phases above
- Unit test each router
- Integration test full API

### **Stage 2: Staging Deployment (Day 8)**
- Deploy to staging environment
- Run full regression test suite
- Load test with production-like traffic
- Monitor for 24 hours

### **Stage 3: Production Rollout (Day 9)**
- **Blue-Green Deployment:**
  1. Deploy new API to "green" environment
  2. Route 10% traffic to green (canary)
  3. Monitor error rates, latency for 2 hours
  4. If successful, route 50% traffic
  5. Monitor for 4 hours
  6. Route 100% traffic to green
  7. Keep blue environment for 24h rollback window

### **Stage 4: Monitoring (Days 10-14)**
- 24/7 monitoring of error rates
- Track 429 rate limit responses
- Monitor API latency (p50, p95, p99)
- Gather user feedback

### **Stage 5: Decommission Old APIs (Day 30)**
- Remove old API services from docker-compose
- Delete legacy code (keep in git history)
- Archive documentation

---

## 💰 Cost-Benefit Analysis

### **Costs**
- 👨‍💻 **7 days developer time**
- 🧪 **2 days QA time**
- 📚 **1 day documentation**
- 🚀 **1 day deployment + monitoring**
- **Total:** ~11 days effort

### **Benefits**
- ✅ **50% reduction in deployment complexity** (3 services → 1)
- ✅ **Unified rate limiting** prevents API abuse
- ✅ **Consistent API structure** improves developer experience
- ✅ **Single OpenAPI spec** simplifies integration
- ✅ **Reduced memory footprint** (3 FastAPI apps → 1)
- ✅ **Easier scaling** (scale single service vs. 3)
- ✅ **Simplified monitoring** (1 health check vs. 3)
- ✅ **Foundation for future features** (auth, GraphQL, WebSockets)

**ROI:** High - Long-term maintainability gains outweigh upfront cost

---

## 🎓 Lessons Learned (Pre-Implementation)

### **Why We're Doing This**
1. **Organic Growth:** APIs evolved separately as features were added
2. **No Initial Versioning:** APIs created without version strategy
3. **Duplicated Logic:** Token scanning implemented twice
4. **Port Management:** Running multiple services causes deployment headaches

### **What We'll Prevent**
1. ✅ No more duplicate endpoints
2. ✅ Clear API versioning strategy from day 1
3. ✅ Consistent middleware across all endpoints
4. ✅ Single source of truth for API configuration

---

## 📖 References

- [FastAPI Best Practices](https://fastapi.tiangolo.com/tutorial/)
- [API Versioning Strategies](https://www.troyhunt.com/your-api-versioning-is-wrong/)
- [Rate Limiting Best Practices](https://github.com/slowapi/slowapi)
- [OpenAPI 3.0 Specification](https://swagger.io/specification/)
- [REST API Design Guidelines](https://restfulapi.net/)

---

## 🤝 Approval & Sign-Off

**Created By:** GitHub Copilot + User  
**Reviewed By:** [Pending]  
**Approved By:** [Pending]  
**Target Start Date:** [TBD]  
**Target Completion Date:** [TBD]  

---

**Status:** ⏸️ DEFERRED - Awaiting scheduling after completion of 9 critical improvements

This plan will be revisited when ready to dedicate a full sprint to API consolidation.
