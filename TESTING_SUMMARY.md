# Testing Summary

## Overview
Comprehensive test coverage for artifact provenance, glossary generation, retention policies, and core system functionality.

## Test Suites

### 1. Provenance & Glossary Tests (`test_provenance_glossary.py`)
**Status:** ✅ All 4 tests passing

**Coverage:**
- **Provenance Tracking** - Validates artifact registration, lineage tracking, checksum generation
- **Pipeline Integration** - Tests end-to-end tracking through market data → features → GemScore
- **Glossary Generation** - Verifies term registration, search, categorization
- **Export Functionality** - Tests JSON and Markdown exports for both provenance and glossary

**Key Validations:**
- 5 artifacts tracked with full lineage graph
- 4 transformations recorded with parent-child relationships
- 24 pre-loaded glossary terms across 9 categories
- Export formats working correctly

### 2. Minimal Test Suite (`test_minimal_suite.py`)
**Status:** ✅ All 4 tests passing

**Coverage:**
- **Schema Validation** - Ensures MarketSnapshot, contract reports, and GemScore results have valid structures
- **Backtest Data Integrity** - Validates historical data quality, returns calculation, drawdown analysis
- **Feature Validation** - Tests feature completeness, normalization ranges, GemScore calculation
- **Edge Case Handling** - Tests empty series, NaN values, extreme values, zero liquidity

**Key Metrics (Latest Run):**
- 30 clean backtest data points
- Volatility: 0.0138
- Max drawdown: -2.15%
- Cumulative returns: 1.2773
- 12 features with 100% completeness
- GemScore: 39.02, Confidence: 0.00%

### 3. Artifact Retention Tests (`test_artifact_retention.py`)
**Status:** ✅ All 5 tests passing

**Coverage:**
- **Artifact Classification** - Tests automatic classification into 5 levels (CRITICAL, IMPORTANT, STANDARD, TRANSIENT, EPHEMERAL)
- **Retention Policies** - Validates retention periods for each classification level
- **Lifecycle Management** - Tests tier transitions (HOT → WARM → COLD → DELETED)
- **Automated Lifecycle** - Validates automatic transition triggers based on age
- **Export and Cleanup** - Tests lifecycle reporting and artifact deletion

**Key Validations:**
- GemScore/Reports classified as IMPORTANT (730d retention)
- Production data classified as STANDARD (180d retention)
- Features classified as TRANSIENT (30d retention)
- Automatic tier transitions working correctly
- Cleanup removes deleted artifacts from tracker

## Test Execution

### Run All Tests
```powershell
# Provenance and glossary
python test_provenance_glossary.py

# Minimal core tests
python test_minimal_suite.py

# Retention policies
python test_artifact_retention.py
```

### Run Individual Tests
```powershell
# Just one test file
python test_minimal_suite.py
```

## Retention Policy Configuration

### Classification Levels
| Level | Hot Tier | Warm Tier | Cold Tier | Total | Archive |
|-------|----------|-----------|-----------|-------|---------|
| **CRITICAL** | 90d | 365d | Indefinite | ∞ | Yes |
| **IMPORTANT** | 30d | 180d | 520d | 730d (~2yr) | Yes |
| **STANDARD** | 7d | 60d | 113d | 180d (~6mo) | Yes |
| **TRANSIENT** | 1d | 7d | 22d | 30d | No |
| **EPHEMERAL** | 0d | 0d | 1d | 1d | No |

### Automatic Classification Rules

**CRITICAL:**
- GemScore results with score > 90
- Production artifacts tagged "production"
- Model artifacts (trained models)

**IMPORTANT:**
- GemScore results (score ≤ 90)
- Analysis reports
- Contract reports
- Summary reports

**STANDARD:**
- Market snapshots (production)
- Price series (production)
- Backtest results

**TRANSIENT:**
- Feature vectors
- Market snapshots (non-production)
- Price series (non-production)

**EPHEMERAL:**
- Raw data
- Temporary artifacts
- Debugging artifacts

## Integration with Provenance System

The retention policy system integrates seamlessly with the provenance tracker:

```python
from src.core.provenance import get_provenance_tracker
from src.core.artifact_retention import get_policy_manager

# Track an artifact
tracker = get_provenance_tracker()
artifact_id = tracker.register_artifact(...)

# Register for lifecycle management
manager = get_policy_manager()
record = tracker.get_record(artifact_id)
manager.register_artifact(artifact_id, record)

# Run lifecycle management
stats = manager.run_lifecycle_management(tracker)

# Clean up expired artifacts
deleted_count = manager.cleanup_deleted_artifacts(tracker)
```

## Continuous Integration

These tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    python test_provenance_glossary.py
    python test_minimal_suite.py
    python test_artifact_retention.py
```

## Test Coverage Summary

**Total Tests:** 13  
**Passing:** 13 (100%)  
**Failing:** 0  

**Module Coverage:**
- ✅ Provenance tracking (src/core/provenance.py)
- ✅ Glossary generation (src/core/glossary.py)
- ✅ Pipeline integration (src/core/provenance_tracking.py)
- ✅ Artifact retention (src/core/artifact_retention.py)
- ✅ Schema validation (MarketSnapshot, reports, GemScore)
- ✅ Backtest data integrity
- ✅ Feature validation and normalization

## Next Steps

### Recommended Enhancements
1. **Performance Tests** - Add tests for large-scale artifact management (1000+ artifacts)
2. **Concurrency Tests** - Test thread-safe access to provenance tracker
3. **Database Integration** - Add tests for SQLite persistence layer
4. **API Tests** - Add tests for REST API endpoints if/when implemented
5. **Load Tests** - Validate system behavior under high artifact creation rates

### Monitoring Integration
Consider adding test metrics to observability dashboard:
- Test execution time trends
- Test coverage percentage
- Artifact lifecycle statistics
- Retention policy effectiveness metrics

## Troubleshooting

### Common Issues

**Datetime Timezone Errors:**
- Ensure all datetime objects use timezone-aware timestamps
- The artifact_retention module handles both aware and naive datetimes

**Import Errors:**
- Verify PYTHONPATH includes project root
- Check that all dependencies are installed: `pip install -r requirements.txt`

**Test Data Issues:**
- Minimal tests use synthetic data generation
- Backtest tests require clean time-series data
- Feature tests validate normalization to [0,1] range

### Debug Mode
Run tests with verbose output:
```powershell
python -v test_minimal_suite.py
```

## Documentation Links

- [Provenance & Glossary Guide](PROVENANCE_GLOSSARY_GUIDE.md)
- [Provenance Quick Reference](PROVENANCE_QUICK_REF.md)
- [Testing Quick Reference](TESTING_QUICK_REF.md)
- [Architecture Overview](ARCHITECTURE.md)
