# AutoTrader Testing Quick Reference

Quick command reference for the AutoTrader testing suite.

## 🚀 Quick Commands

### Run Tests
```powershell
# All tests
.\run_tests.ps1
pytest tests/ -v

# Specific test file
pytest tests/test_api_integration.py -v
.\run_tests.ps1 -Api

# Specific test
pytest tests/test_api_integration.py::test_get_tokens_list -v
.\run_tests.ps1 -Test "test_get_tokens_list"
```

### By Category
```powershell
# Unit tests only
pytest -m unit -v
.\run_tests.ps1 -Unit

# Integration tests
pytest -m integration -v
.\run_tests.ps1 -Integration

# Performance tests
pytest -m performance -v
.\run_tests.ps1 -Performance

# Skip slow tests
pytest -m "not slow" -v
.\run_tests.ps1 -Fast
```

### With Coverage
```powershell
# Terminal report
pytest --cov=src --cov-report=term-missing
.\run_tests.ps1 -Coverage

# HTML report (auto-opens in browser)
pytest --cov=src --cov-report=html
.\run_tests.ps1 -Html

# Both reports
pytest --cov=src --cov-report=html --cov-report=term
.\run_tests.ps1 -Coverage -Html
```

### Parallel Execution
```powershell
# Run with 4 workers
pytest tests/ -n 4
.\run_tests.ps1 -Parallel 4

# Auto-detect CPU count
pytest tests/ -n auto
```

## 📁 Test Files

| File | Description | Count |
|------|-------------|-------|
| `test_api_integration.py` | API endpoint tests | 30+ |
| `test_core_services.py` | Business logic tests | 50+ |
| `test_enhanced_modules.py` | Reliability tests | 40+ |
| `test_e2e_workflows.py` | End-to-end tests | 30+ |
| `test_performance.py` | Performance tests | 40+ |

## 🏷️ Test Markers

| Marker | Description | Usage |
|--------|-------------|-------|
| `unit` | Fast unit tests | `pytest -m unit` |
| `integration` | Integration tests | `pytest -m integration` |
| `performance` | Performance benchmarks | `pytest -m performance` |
| `slow` | Long-running tests | `pytest -m "not slow"` to skip |

## 🔍 Useful Options

### Verbosity
```powershell
pytest -v          # Verbose
pytest -vv         # Very verbose
pytest -q          # Quiet
pytest -s          # Show print statements
```

### Output Control
```powershell
pytest --tb=short  # Short traceback
pytest --tb=no     # No traceback
pytest -l          # Show local variables on failure
pytest --pdb       # Drop into debugger on failure
```

### Test Selection
```powershell
pytest -k "test_get"                    # Run tests matching pattern
pytest tests/test_api_integration.py::TestClass::test_method
pytest --lf                             # Run last failed
pytest --ff                             # Run failures first
pytest --sw                             # Stop on first failure
```

### Performance
```powershell
pytest --durations=10                   # Show 10 slowest tests
pytest --durations=0                    # Show all test durations
pytest -n auto                          # Parallel (auto workers)
```

## 📊 Coverage Commands

### Generate Reports
```powershell
# HTML (opens in browser)
pytest --cov=src --cov-report=html
start htmlcov/index.html

# Terminal with missing lines
pytest --cov=src --cov-report=term-missing

# XML (for CI/CD)
pytest --cov=src --cov-report=xml

# JSON (for tools)
pytest --cov=src --cov-report=json
```

### Coverage Options
```powershell
# Specific module
pytest --cov=src.core --cov-report=term

# Exclude paths
pytest --cov=src --cov-report=term --cov-config=.coveragerc

# Minimum coverage threshold
pytest --cov=src --cov-fail-under=80
```

## 🎯 Common Scenarios

### Development Workflow
```powershell
# Quick check (fast tests only)
pytest -m "not slow" -v

# Full validation before commit
pytest tests/ --cov=src --cov-report=term

# Debug failing test
pytest tests/test_api_integration.py::test_name -vv --pdb
```

### CI/CD Pipeline
```powershell
# Full suite with coverage
pytest tests/ --cov=src --cov-report=xml --cov-report=term

# Parallel execution
pytest tests/ -n auto --maxfail=5

# Generate JUnit XML
pytest tests/ --junitxml=test-results.xml
```

### Performance Testing
```powershell
# Run performance suite
pytest -m performance -v

# With profiling
pytest -m performance --profile

# Show slowest tests
pytest --durations=20
```

## 🐛 Debugging

### Common Issues

**Import errors**:
```powershell
# Ensure dependencies installed
pip install -r requirements.txt
pip install pytest pytest-cov pytest-asyncio
```

**Test not found**:
```powershell
# List all tests
pytest --collect-only

# Check test discovery
pytest -v --collect-only tests/
```

**Coverage not working**:
```powershell
# Install coverage plugin
pip install pytest-cov

# Check .coveragerc or pyproject.toml config
pytest --cov=src --cov-config=pyproject.toml
```

### Debug Workflow
```powershell
# 1. Run failing test with verbose output
pytest tests/test_file.py::test_name -vv

# 2. Show locals on failure
pytest tests/test_file.py::test_name -vv -l

# 3. Drop into debugger
pytest tests/test_file.py::test_name --pdb

# 4. Add print debugging
pytest tests/test_file.py::test_name -s
```

## 📈 Monitoring

### Test Statistics
```powershell
# Count tests
pytest --collect-only | grep "<Function"

# Show test durations
pytest --durations=0

# Test distribution by marker
pytest --markers
```

### Coverage Trends
```powershell
# Generate coverage badge
coverage-badge -o coverage.svg

# Coverage history (with pytest-cov-history)
pytest --cov=src --cov-report=html
```

## 🔧 Configuration

### pyproject.toml
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: slow tests",
    "integration: integration tests",
    "unit: unit tests",
    "performance: performance tests",
]
addopts = ["-v", "--tb=short"]

[tool.coverage.run]
source = ["src"]
omit = ["tests/*"]
```

### Command Line Config
```powershell
# Use custom config file
pytest -c custom_pytest.ini

# Override settings
pytest --override-ini="addopts=-v --tb=long"
```

## 📚 Resources

- **Full Documentation**: `tests/README.md`
- **Implementation Details**: `../milestones/TESTING_SUITE_COMPLETE.md`
- **Test Files**: `tests/test_*.py`
- **pytest Docs**: https://docs.pytest.org/

## 🎓 Tips

1. **Run fast tests frequently**: `pytest -m "not slow"`
2. **Use coverage to find gaps**: `pytest --cov=src --cov-report=term-missing`
3. **Mark slow tests**: Add `@pytest.mark.slow` decorator
4. **Parallelize when possible**: `pytest -n auto`
5. **Debug with pdb**: `pytest --pdb` drops into debugger on failure
6. **Check test count**: `pytest --collect-only | wc -l`
7. **Monitor performance**: `pytest --durations=10`

---

**Quick Help**: `.\run_tests.ps1 -Help` or `python run_tests.py --help`  
**Full Docs**: See `tests/README.md`  
**Test Count**: 190+ tests across 5 files
