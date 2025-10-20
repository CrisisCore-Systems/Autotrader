# 🚀 AutoTrader - Next Steps Checklist

## ✅ Completed Today (October 18, 2025)

- [x] Updated dependencies (pymongo, fastapi, nltk, requests, scikit-learn)
- [x] Ran pip-audit security scan
- [x] Removed duplicate `ci/github-actions.yml`
- [x] Fixed Docker Compose worker module reference
- [x] Added strict environment variable validation
- [x] Updated API branding (VoidBloom → AutoTrader in main.py)

---

## 📋 Immediate Actions (This Week)

### Day 1-2: Database Migrations
```bash
# Install Alembic
pip install alembic

# Initialize migrations
cd c:\Users\kay\Documents\Projects\AutoTrader\Autotrader
alembic init migrations

# Configure alembic.ini
# Update sqlalchemy.url = postgresql://crisiscore:password@localhost/autotrader

# Create first migration
alembic revision --autogenerate -m "Initial schema from schema_versioning"

# Review and apply
alembic upgrade head
```

**Files to Create:**
- `migrations/versions/001_initial_schema.py`
- Update `alembic.ini` with database connection

---

### Day 3-4: Branding Consistency

**Search & Replace (PowerShell):**
```powershell
# Find all instances
Get-ChildItem -Recurse -Include *.md,*.yml,*.yaml,*.py | Select-String "VoidBloom" -List

# Manual replacements needed in:
# - README.md (multiple instances)
# - infra/docker-compose.yml (POSTGRES_DB: voidbloom)
# - docs/*.md files
# - Any remaining API titles
```

**Key Changes:**
- `POSTGRES_DB: voidbloom` → `POSTGRES_DB: autotrader`
- "VoidBloom / CrisisCore" → "AutoTrader"
- Verify all FastAPI app titles

---

### Day 5: Test Coverage Audit

```bash
# Run full test suite
cd c:\Users\kay\Documents\Projects\AutoTrader\Autotrader
pytest --cov=src --cov-report=html --cov-report=term-missing -v

# Review HTML report
start htmlcov/index.html

# Update README.md with actual numbers
# - Replace "21 tests passing" with real count
# - Add coverage badge if desired
```

---

## 🔧 Quick Wins (1-2 hours each)

### Rate Limiting
```bash
pip install slowapi

# Add to src/api/main.py:
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add to scan endpoint:
@app.post("/api/v1/scan")
@limiter.limit("10/minute")
async def scan_token(...):
    ...
```

### Documentation Quick Fixes
```bash
# Create KNOWN_ISSUES.md
# Update README.md:
# - Remove or clarify "100% FREE" claims
# - Update "Production Ready" status to "Beta" or "Production-Ready (with limitations)"
# - Document which features require API keys vs which are truly free
```

---

## 📊 Validation Checklist

Before marking any item complete, verify:

- [ ] Change documented in git commit
- [ ] Tests pass after change
- [ ] No new errors in logs
- [ ] Documentation updated
- [ ] Reviewed by second pair of eyes (if available)

---

## 🔄 Ongoing Maintenance

### Weekly
- [ ] Run `pip-audit` to check for new vulnerabilities
- [ ] Review security scan results in GitHub Actions
- [ ] Check test coverage hasn't dropped below 80%

### Monthly
- [ ] Update dependencies (`pip list --outdated`)
- [ ] Review and close stale issues/TODOs
- [ ] Audit documentation accuracy

---

## 🚨 Blockers & Dependencies

### API Consolidation (Complex)
**Estimated Effort:** 5-7 days  
**Requires:**
1. Design unified API structure
2. Map all existing endpoints
3. Implement versioning strategy
4. Migrate clients
5. Deprecation plan for old endpoints

**Recommendation:** Schedule dedicated sprint, not a quick fix

---

## 📞 Help & Resources

### If Stuck
1. Check `.github/workflows/` for CI/CD patterns
2. Review `infra/docker-compose.yml` for service architecture
3. Examine `src/core/schema_versioning.py` for database patterns
4. Read `IMPROVEMENTS_COMPLETED.md` for context

### External Resources
- Alembic Docs: https://alembic.sqlalchemy.org/
- FastAPI Versioning: https://fastapi.tiangolo.com/advanced/path-operation-advanced-configuration/
- SlowAPI (Rate Limiting): https://slowapi.readthedocs.io/

---

## ✨ Success Criteria

Project is "cleaned up" when:
- [x] All known security vulnerabilities fixed or documented
- [x] No duplicate/conflicting CI configs
- [x] Docker Compose starts without errors
- [x] API fails fast on misconfiguration
- [ ] Database migrations in place
- [ ] Consistent branding throughout
- [ ] Accurate test coverage documented
- [ ] Rate limiting enforced
- [ ] Single unified API (or clear deprecation plan)
- [ ] Documentation matches reality

**Current Progress: 4/10 ✅**

---

**Last Updated:** October 18, 2025  
**Next Review:** October 25, 2025
