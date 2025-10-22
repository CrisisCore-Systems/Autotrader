# CI Gating and Branch Protection Setup Guide

## Overview

This repository uses GitHub Actions to automatically run tests and enforce quality standards on all pull requests. This document explains how the CI gating works and how to configure branch protection rules to block PRs that don't meet quality standards.

## Current CI Workflows

### tests-and-coverage.yml

Located at `.github/workflows/tests-and-coverage.yml`, this workflow runs on every push to `main` and on all pull requests.

#### Jobs

1. **test** - Runs the full test suite with coverage
   - Installs Python 3.11 and dependencies
   - Runs pytest with coverage reporting
   - Enforces 80% minimum code coverage threshold
   - Uploads coverage reports as artifacts

2. **lint** - Runs code quality checks
   - Runs ruff for code style checking
   - Runs mypy for type checking
   - Runs pylint with minimum score of 8.0

3. **quality-gate** - Final gate that checks all previous jobs
   - Requires both `test` and `lint` jobs to pass
   - Fails if either job fails
   - This is the job that should be required for PR merging

## Setting Up Branch Protection

To ensure PRs are blocked unless tests pass, configure branch protection rules for the `main` branch:

### Step 1: Navigate to Branch Protection Settings

1. Go to your repository on GitHub
2. Click **Settings** → **Branches**
3. Click **Add branch protection rule**
4. Set **Branch name pattern** to `main`

### Step 2: Configure Required Status Checks

Enable the following settings:

- ✅ **Require status checks to pass before merging**
  - ✅ **Require branches to be up to date before merging**
  - Add required status checks:
    - `test` - Core test suite
    - `lint` - Code quality checks
    - `quality-gate` - Overall quality gate

### Step 3: Additional Recommended Settings

- ✅ **Require pull request reviews before merging**
  - Required approving reviews: 1 (or more)
- ✅ **Dismiss stale pull request approvals when new commits are pushed**
- ✅ **Require review from Code Owners** (optional)
- ✅ **Require linear history** (optional, recommended)
- ✅ **Include administrators** - Apply rules to admins too

### Step 4: Save Changes

Click **Create** or **Save changes** to enable branch protection.

## Test Coverage Requirements

The CI enforces a **minimum 80% code coverage** threshold:

- Tests must cover at least 80% of lines in the `src/` directory
- Coverage is calculated by pytest-cov
- The build fails if coverage drops below this threshold
- Coverage reports are available as artifacts on each workflow run

## Running Tests Locally

Before pushing code, run tests locally to catch issues early:

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest --cov=src --cov-report=term --cov-report=html

# View coverage report
open htmlcov/index.html  # On macOS
# or
xdg-open htmlcov/index.html  # On Linux
```

## Core Module Test Coverage

The following core modules have comprehensive test coverage:

### Features Module (`src/core/features.py`)
- ✅ Time series feature computation
- ✅ Feature normalization with edge cases (None, NaN, Inf)
- ✅ Feature vector building and merging
- ✅ Missing data handling
- ✅ Unlock risk penalties

**Test file:** `tests/test_features.py` (16 tests)

### Scoring Module (`src/core/scoring.py`)
- ✅ GemScore calculation
- ✅ Confidence computation
- ✅ Asset flagging logic
- ✅ Edge cases (missing features, out-of-range values)
- ✅ Safety and signal thresholds

**Test file:** `tests/test_scoring.py` (11 tests)

### Reliability Services (`src/services/reliability.py`)
- ✅ Circuit breaker patterns
- ✅ Caching behavior
- ✅ SLA monitoring
- ✅ Health check endpoints
- ✅ System recovery

**Test file:** `tests/test_reliability_services.py` (9 tests)

## Continuous Improvement

### Adding New Tests

When adding new functionality:

1. **Write tests first** (TDD approach recommended)
2. Ensure new tests cover edge cases
3. Maintain or improve coverage percentage
4. Run tests locally before pushing

### Test Organization

```
tests/
├── test_features.py          # Feature engineering tests
├── test_scoring.py           # Scoring logic tests
├── test_reliability_services.py  # Reliability pattern tests
├── conftest.py              # Shared fixtures
└── fixtures/                # Test data fixtures
```

### Coverage Monitoring

Track coverage trends over time:

```bash
# Generate coverage report
pytest --cov=src --cov-report=term-missing

# Look for missing coverage areas
pytest --cov=src --cov-report=term-missing | grep "TOTAL"
```

## Troubleshooting

### Tests Failing Locally But Pass in CI

- Check Python version (CI uses 3.11)
- Verify dependencies are up to date: `pip install -r requirements.txt`
- Check for environment-specific issues

### Coverage Below Threshold

- Identify uncovered lines: `pytest --cov=src --cov-report=term-missing`
- Add tests for critical paths first
- Consider excluding test utilities from coverage

### Lint Failures

- Run ruff locally: `ruff check src/`
- Run mypy locally: `mypy src/ --strict --ignore-missing-imports`
- Run pylint locally: `pylint src/ --fail-under=8.0`

## Quality Gate Status

The quality gate ensures:
- ✅ All tests pass
- ✅ Coverage meets threshold (≥80%)
- ✅ Code style checks pass (ruff)
- ✅ Type checking passes (mypy)
- ✅ Code quality score meets threshold (pylint ≥8.0)

When all checks pass, you'll see: **✅ Quality gate passed**

When checks fail, you'll see: **❌ Quality gate failed** with details about which job failed.

## Future Enhancements

Consider adding:
- Integration tests for end-to-end workflows
- Performance benchmarking tests
- Security scanning (already exists in `security-scan.yml`)
- Mutation testing to verify test quality
- Automatic coverage trend reports
