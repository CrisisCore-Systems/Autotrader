# 📚 AutoTrader Documentation Index

**Last Updated:** October 20, 2025  
**Status:** Phase 2 Validation In Progress (2/20 trades)

---
**Note:** Legacy quick-reference documents now live in [`docs/legacy/`](docs/legacy/README.md).

## 🎯 Quick Navigation

### **🚀 START HERE (New Users)**

**Essential Reading** (5 minutes):
1. [`QUICK_REFERENCE.md`](docs/legacy/QUICK_REFERENCE.md) - 30-second overview
2. [`README.md`](README.md) - Main project overview
3. [`DAILY_SCHEDULE.md`](docs/legacy/DAILY_SCHEDULE.md) - Visual workflow guide

### **📊 For Operators (Daily Trading)**

**Daily Operations** (30 minutes/day):
1. [`TRADING_WORKFLOW_EXPLAINED.md`](docs/legacy/TRADING_WORKFLOW_EXPLAINED.md) - Complete workflow explanation
2. [`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md) - Daily operations manual
3. [`PHASE2_VALIDATION_PLAN.md`](docs/legacy/PHASE2_VALIDATION_PLAN.md) - Current validation plan
4. [`NEXT_STEPS.md`](docs/legacy/NEXT_STEPS.md) - Action items and priorities

**Data & Verification**:
5. [`DATA_FRESHNESS.md`](docs/legacy/DATA_FRESHNESS.md) - Proof of fresh data every run
6. [`PROJECT_STATUS.md`](docs/legacy/PROJECT_STATUS.md) - Comprehensive status report

**Understanding the System**:
7. [`SCAN_VS_TRADE_MODES.md`](docs/legacy/SCAN_VS_TRADE_MODES.md) - How system knows scanning vs trading
8. [`MODE_SELECTION_CHEATSHEET.md`](docs/legacy/MODE_SELECTION_CHEATSHEET.md) - Which script to run when

### **🔧 For Developers**

**Technical Documentation**:
1. [`docs/BROKER_INTEGRATION.md`](docs/BROKER_INTEGRATION.md) - Broker architecture
2. [`docs/AGENTIC_ARCHITECTURE.md`](docs/AGENTIC_ARCHITECTURE.md) - Agent design
3. [`docs/PENNYHUNTER_GUIDE.md`](docs/PENNYHUNTER_GUIDE.md) - Trading strategy details

**Historical Context**:
4. [`PROJECT_IMPROVEMENTS_SUMMARY.md`](docs/legacy/PROJECT_IMPROVEMENTS_SUMMARY.md) - All 10 improvements overview
5. [`IMPROVEMENTS_COMPLETED.md`](docs/legacy/IMPROVEMENTS_COMPLETED.md) - Detailed technical documentation

### **Specific Topics**

#### **Testing**
- [`TESTING_REPORT.md`](docs/legacy/TESTING_REPORT.md) - Current test coverage (9%), broken tests, recommendations

#### **API**
- [`RATE_LIMITING_COMPLETE.md`](docs/legacy/RATE_LIMITING_COMPLETE.md) - API rate limiting implementation
- [`API_CONSOLIDATION_PLAN.md`](docs/legacy/API_CONSOLIDATION_PLAN.md) - Future API unification plan (7-day roadmap)

#### **Database**
- [`migrations/versions/001_initial_schema.py`](migrations/versions/001_initial_schema.py) - Database schema (9 tables)
- [`migrations/README`](migrations/README) - Alembic usage guide

#### **Setup & Configuration**
- [`.env.example`](.env.example) - Required environment variables
- [`SETUP_COMPLETE.md`](docs/legacy/SETUP_COMPLETE.md) - Initial setup guide

---

## 📊 Project Status Dashboard

| Area | Status | Coverage/Metric | Priority |
|------|--------|-----------------|----------|
| **Security** | 🟢 Good | 2 non-critical vulnerabilities | Monitor |
| **Testing** | 🟡 Needs Work | 9% coverage (target: 75%) | High |
| **API Protection** | 🟢 Complete | Rate limiting on all endpoints | Maintained |
| **Database** | 🟢 Good | Alembic migrations + 9 tables | Maintained |
| **Branding** | 🟢 Complete | 100% AutoTrader consistency | Complete |
| **Documentation** | 🟢 Excellent | 50+ pages created | Maintained |
| **API Architecture** | 🟡 Planned | 3 APIs → 1 unified (deferred) | Medium |

---

## 🎯 Implementation Checklist

### ✅ Completed (9/10)
- [x] Security updates (dependencies)
- [x] Infrastructure cleanup (CI config)
- [x] Docker fixes (worker module)
- [x] Configuration hardening (env validation)
- [x] Database migrations (Alembic)
- [x] Branding consistency (VoidBloom → AutoTrader)
- [x] Testing coverage analysis (9% baseline)
- [x] API rate limiting (slowapi)
- [x] API consolidation planning (15-page roadmap)

### ⏸️ Deferred (1/10)
- [ ] API consolidation implementation (7-day sprint required)

---

## 🚀 Next Steps (Priority Order)

### **Immediate**
1. Fix 6 broken test modules (import errors)
2. Address 12 deprecation warnings
3. Add API endpoint tests

### **Short-Term (1-2 Weeks)**
4. Implement integration tests
5. Increase coverage 9% → 30%
6. Set up CI coverage enforcement

### **Medium-Term (1 Month)**
7. Schedule API consolidation sprint
8. Implement authentication
9. Add Redis-backed rate limiting

### **Long-Term (3 Months)**
10. Achieve 75% test coverage
11. Add GraphQL endpoint
12. WebSocket support

---

## 📖 Key Documents by Audience

### **For Developers**
- [`TESTING_REPORT.md`](docs/legacy/TESTING_REPORT.md) - What tests exist, what's broken
- [`API_CONSOLIDATION_PLAN.md`](docs/legacy/API_CONSOLIDATION_PLAN.md) - Future API architecture
- [`migrations/`](migrations/) - Database schema and migrations

### **For DevOps**
- [`docker-compose.yml`](docker-compose.yml) - Container orchestration
- [`RATE_LIMITING_COMPLETE.md`](docs/legacy/RATE_LIMITING_COMPLETE.md) - API rate limiting config
- [`.env.example`](.env.example) - Required environment variables

### **For Product/Management**
- [`PROJECT_IMPROVEMENTS_SUMMARY.md`](docs/legacy/PROJECT_IMPROVEMENTS_SUMMARY.md) - High-level overview
- [`README.md`](README.md) - Project description and features

### **For QA/Testing**
- [`TESTING_REPORT.md`](docs/legacy/TESTING_REPORT.md) - Test coverage analysis
- [`tests/`](tests/) - Test suite location
- [`htmlcov/index.html`](htmlcov/index.html) - Coverage report (after running tests)

---

## 🔍 Finding Specific Information

### **"How do I set up the project?"**
→ [`README.md`](README.md) → Setup section

### **"What's the API rate limit?"**
→ [`RATE_LIMITING_COMPLETE.md`](docs/legacy/RATE_LIMITING_COMPLETE.md)

### **"What database tables exist?"**
→ [`migrations/versions/001_initial_schema.py`](migrations/versions/001_initial_schema.py)

### **"What tests are broken?"**
→ [`TESTING_REPORT.md`](docs/legacy/TESTING_REPORT.md) → "Broken Test Modules" section

### **"When will APIs be consolidated?"**
→ [`API_CONSOLIDATION_PLAN.md`](docs/legacy/API_CONSOLIDATION_PLAN.md)

### **"What changed recently?"**
→ [`IMPROVEMENTS_COMPLETED.md`](docs/legacy/IMPROVEMENTS_COMPLETED.md)

### **"What security vulnerabilities exist?"**
→ [`IMPROVEMENTS_COMPLETED.md`](docs/legacy/IMPROVEMENTS_COMPLETED.md) → Security Updates section

---

## 📅 Documentation Maintenance Schedule

| Document | Update Frequency | Owner |
|----------|------------------|-------|
| `README.md` | As features change | Product |
| `TESTING_REPORT.md` | Weekly (after test runs) | QA |
| `RATE_LIMITING_COMPLETE.md` | When limits change | DevOps |
| `API_CONSOLIDATION_PLAN.md` | Before implementation sprint | Lead Dev |
| `PROJECT_IMPROVEMENTS_SUMMARY.md` | After major milestones | Team Lead |
| `IMPROVEMENTS_COMPLETED.md` | When improvements made | Developers |

---

## 🆘 Common Questions

**Q: Why are there 3 separate API files?**  
A: Legacy growth - they evolved separately. See [`API_CONSOLIDATION_PLAN.md`](docs/legacy/API_CONSOLIDATION_PLAN.md) for unification plan.

**Q: How do I run tests?**  
A: `pytest tests/ -v --cov=src --cov-report=html` - See [`TESTING_REPORT.md`](docs/legacy/TESTING_REPORT.md)

**Q: Why is coverage only 9%?**  
A: Baseline established recently. Target is 75%. See [`TESTING_REPORT.md`](docs/legacy/TESTING_REPORT.md) for roadmap.

**Q: What does "VoidBloom" mean?**  
A: Old project name, now 100% replaced with "AutoTrader" - See improvement #7

**Q: Can I run all APIs at once?**  
A: Yes, but they use different ports. Future plan consolidates to one - See [`API_CONSOLIDATION_PLAN.md`](docs/legacy/API_CONSOLIDATION_PLAN.md)

**Q: What are the rate limits?**  
A:
- Token scans: 10/minute
- Token lists: 30/minute
- Root: 60/minute
- Health: 120/minute

Full details in [`RATE_LIMITING_COMPLETE.md`](docs/legacy/RATE_LIMITING_COMPLETE.md)

---

## 🎓 Learning Resources

### **Understanding the Codebase**
1. Read [`README.md`](README.md) for high-level overview
2. Review [`migrations/versions/001_initial_schema.py`](migrations/versions/001_initial_schema.py) for data model
3. Explore [`src/api/main.py`](src/api/main.py) for API structure
4. Check [`tests/`](tests/) for usage examples

### **Contributing**
1. Read [`PROJECT_IMPROVEMENTS_SUMMARY.md`](docs/legacy/PROJECT_IMPROVEMENTS_SUMMARY.md) to understand recent changes
2. Review [`TESTING_REPORT.md`](docs/legacy/TESTING_REPORT.md) for test expectations
3. Follow patterns in [`src/api/main.py`](src/api/main.py) (rate limiting, env validation)

### **Troubleshooting**
1. Check [`IMPROVEMENTS_COMPLETED.md`](docs/legacy/IMPROVEMENTS_COMPLETED.md) for known issues
2. Review environment variables in [`.env.example`](.env.example)
3. Verify Docker setup in [`docker-compose.yml`](docker-compose.yml)

---

**This index is automatically updated when documentation changes.**

---

## 📊 Documentation Stats

- **Total Documentation Files:** 10+
- **Total Pages:** 50+ pages
- **Last Major Update:** October 18, 2025
- **Coverage:** All major system areas documented
- **Maintenance Status:** 🟢 Active

---

*For questions or suggestions about documentation, please create an issue or reach out to the team.*
