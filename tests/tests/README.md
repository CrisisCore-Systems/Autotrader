# AutoTrader Testing Suite

Comprehensive testing infrastructure for the AutoTrader cryptocurrency trading platform.

## 📋 Overview

This testing suite provides complete coverage of:
- **API Integration**: 30+ tests for all 15 REST endpoints
- **Core Services**: 50+ unit tests for business logic
- **Enhanced Modules**: 40+ tests for reliability infrastructure
- **E2E Workflows**: 30+ tests for complete data flows
- **Performance**: 40+ performance and load tests

**Total**: 190+ test cases across 2,100+ lines of test code

## 🚀 Quick Start

### Run All Tests
```powershell
# Using PowerShell script
.\run_tests.ps1

# Using Python script
python run_tests.py

# Using pytest directly
pytest tests/ -v
```

### Run Specific Test Categories
```powershell
# API integration tests only
pytest tests/test_api_integration.py -v

# Core services tests only
pytest tests/test_core_services.py -v

# Performance tests only
pytest tests/test_performance.py -v -m performance
```

### Run with Coverage
```powershell
pytest tests/ --cov=src --cov-report=html --cov-report=term
```

## 📁 Test Structure

```
tests/
├── __init__.py                    # Package initialization
├── test_api_integration.py        # API endpoint tests (390 lines)
├── test_core_services.py          # Business logic tests (380 lines)
├── test_enhanced_modules.py       # Reliability tests (450 lines)
├── test_e2e_workflows.py          # End-to-end tests (420 lines)
├── test_performance.py            # Performance tests (470 lines)
└── README.md                      # This file
```

## 🧪 Test Categories

### 1. API Integration Tests (`test_api_integration.py`)
Tests all REST API endpoints with fixtures for dependency mocking.

**Coverage**:
- ✅ GET /api/tokens (list & filters)
- ✅ GET /api/tokens/{address} (detail)
- ✅ POST /api/scan (trigger scan)
- ✅ GET /api/anomalies (anomaly detection)
- ✅ GET /api/confidence (confidence intervals)
- ✅ GET /api/sla/status (SLA monitoring)
- ✅ POST /api/sla/register (SLA registration)
- ✅ GET /api/analytics/summary (analytics)
- ✅ GET /api/analytics/correlation (correlations)
- ✅ GET /api/analytics/trends (trend analysis)
- ✅ GET /api/features (feature list)
- ✅ POST /api/features (create feature)
- ✅ GET /api/features/{id} (feature detail)
- ✅ PUT /api/features/{id} (update feature)
- ✅ DELETE /api/features/{id} (delete feature)

**Test Types**:
- Happy path scenarios
- Error handling (404, 422, 400)
- Edge cases (empty results, large batches)
- CORS validation
- Concurrent request handling

### 2. Core Services Tests (`test_core_services.py`)
Unit tests for core business logic components.

**Test Classes**:
- `TestSentimentAnalyzer`: LLM integration, batch analysis, narrative extraction
- `TestFeatureEngineering`: Momentum, liquidity, social, safety features
- `TestFeatureStore`: CRUD operations, filtering, importance tracking
- `TestReliabilityServices`: SLA registry, circuit breakers, cache policies
- `TestContractSafety`: Safety scoring, verification, risk identification
- `TestNewsAggregation`: News fetching, filtering, sentiment extraction

### 3. Enhanced Modules Tests (`test_enhanced_modules.py`)
Tests for enhanced reliability and data source integrations.

**Test Classes**:
- `TestSLAMonitor`: Registration, metrics recording, breach detection, latency percentiles
- `TestCircuitBreaker`: State transitions (closed → open → half-open), failure thresholds
- `TestCachePolicy`: TTL expiration, hit rate tracking, eviction
- `TestAdaptiveCachePolicy`: Dynamic TTL adjustment, LRU eviction
- `TestOrderFlowClients`: Multi-exchange data, order imbalance calculations
- `TestTwitterClient`: Tweet fetching, sentiment analysis, rate limiting
- `TestFeatureTransforms`: Log, standardization, min-max scaling, outlier handling
- `TestBacktestInfrastructure`: Scenario creation, backtest execution, metrics

### 4. E2E Workflow Tests (`test_e2e_workflows.py`)
End-to-end integration tests for complete workflows.

**Test Classes**:
- `TestCompleteTokenScan`: Full scanning pipeline with filtering and error recovery
- `TestFeatureExtractionPipeline`: Feature extraction, storage, batch processing
- `TestScoringWorkflow`: Composite scoring, ranking, confidence filtering
- `TestAlertWorkflow`: Alert generation, notification, deduplication, rate limiting
- `TestBatchProcessing`: Multi-chain scanning, scheduled workflows, parallel processing
- `TestErrorRecovery`: Retry logic, fallback sources, graceful degradation, checkpoints

### 5. Performance Tests (`test_performance.py`)
Performance benchmarks, load tests, and stress scenarios.

**Test Classes**:
- `TestAPIPerformance`: Response times, throughput, sustained load
- `TestConcurrentRequests`: Concurrent reads/writes, high concurrency (50+ threads)
- `TestMemoryUsage`: Memory stability, large dataset handling, leak detection
- `TestStoragePerformance`: Feature store read/write performance, batch operations
- `TestCachePerformance`: Cache hit/miss times, throughput, adaptive efficiency
- `TestCircuitBreakerPerformance`: Overhead measurement, behavior under load
- `TestScanningPerformance`: Scan speed, parallel vs sequential comparison
- `TestFeatureExtractionPerformance`: Extraction speed, batch processing
- `TestStressScenarios`: Sustained high load, memory leak detection

## 🏷️ Test Markers

Tests are marked for selective execution:

```python
@pytest.mark.unit          # Fast unit tests
@pytest.mark.integration   # Integration tests with external deps
@pytest.mark.performance   # Performance benchmarks
@pytest.mark.slow          # Long-running tests (>5 seconds)
```

**Run by marker**:
```powershell
pytest -m unit              # Run only unit tests
pytest -m "not slow"        # Skip slow tests
pytest -m performance       # Run only performance tests
pytest -m "integration and not slow"  # Fast integration tests
```

## 📊 Coverage Reports

### Generate Coverage
```powershell
# HTML report (opens in browser)
pytest tests/ --cov=src --cov-report=html
start htmlcov/index.html

# Terminal report
pytest tests/ --cov=src --cov-report=term-missing

# XML report (for CI/CD)
pytest tests/ --cov=src --cov-report=xml
```

### Coverage Goals
- **Overall**: >80% code coverage
- **Core modules**: >90% coverage
- **API endpoints**: 100% coverage
- **Critical paths**: 100% coverage

## 🔧 Configuration

Test configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
    "performance: marks tests as performance tests",
]
addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
    "--disable-warnings",
]

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "*/migrations/*", "*/__pycache__/*"]

[tool.coverage.report]
precision = 2
skip_empty = true
show_missing = true
```

## 🛠️ Writing New Tests

### Test Template
```python
import pytest
from unittest.mock import Mock, patch

class TestNewFeature:
    """Test suite for new feature"""

    @pytest.fixture
    def setup_data(self):
        """Setup test data"""
        return {"key": "value"}

    def test_feature_happy_path(self, setup_data):
        """Test normal operation"""
        result = my_function(setup_data)
        assert result == expected

    def test_feature_error_handling(self):
        """Test error cases"""
        with pytest.raises(ValueError):
            my_function(invalid_input)

    @pytest.mark.slow
    def test_feature_performance(self):
        """Test performance characteristics"""
        import time
        start = time.time()
        my_function()
        assert (time.time() - start) < 1.0
```

### Best Practices
1. **Use descriptive test names**: `test_scan_with_filters_returns_correct_count`
2. **One assertion per test**: Focus each test on a single behavior
3. **Use fixtures**: Share setup code with pytest fixtures
4. **Mock external dependencies**: Isolate unit tests from APIs, databases
5. **Mark slow tests**: Use `@pytest.mark.slow` for tests >5 seconds
6. **Test edge cases**: Empty inputs, None values, extreme values
7. **Check error paths**: Ensure errors are handled gracefully

## 🐛 Debugging Tests

### Run with verbose output
```powershell
pytest tests/test_api_integration.py -vv
```

### Run specific test
```powershell
pytest tests/test_api_integration.py::test_get_tokens_list -v
```

### Show print statements
```powershell
pytest tests/ -s
```

### Drop into debugger on failure
```powershell
pytest tests/ --pdb
```

### Show local variables on failure
```powershell
pytest tests/ -l
```

## 📈 CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3
```

### Run in Docker
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["pytest", "tests/", "-v"]
```

## 📚 Dependencies

Required packages for testing:
```
pytest>=8.0.0
pytest-cov>=4.1.0
pytest-asyncio>=0.23.0
pytest-mock>=3.12.0
fastapi>=0.109.0
httpx>=0.26.0
psutil>=5.9.0
```

Install with:
```powershell
pip install pytest pytest-cov pytest-asyncio pytest-mock fastapi httpx psutil
```

## 🎯 Next Steps

1. **Run the full suite**: `.\run_tests.ps1 --all`
2. **Check coverage**: `pytest --cov=src --cov-report=html`
3. **Add new tests**: Follow the template above
4. **Integrate with CI**: Add to GitHub Actions or similar
5. **Monitor performance**: Track test execution times

## 📞 Support

For issues or questions:
- Check test output for detailed error messages
- Review test documentation in each test file
- Consult `TESTING_QUICK_REF.md` for common commands
- See `TESTING_SUITE_COMPLETE.md` for implementation details

---

**Total Test Count**: 190+ tests  
**Total Lines of Code**: 2,100+ lines  
**Coverage Target**: >80%  
**Last Updated**: 2024
