# CI Gating and Branch Protection Setup Guide

## Overview

This repository uses GitHub Actions to automatically run tests and enforce quality standards on all pull requests. This document explains how the CI gating works and how to configure branch protection rules to block PRs that don't meet quality standards.

## Current CI Workflows

### ci.yml - Main CI Pipeline

Located at `.github/workflows/ci.yml`, this is the primary CI workflow that runs on every push to `main`/`develop` and on all pull requests.

#### Jobs

1. **test** - Runs the full test suite with coverage across multiple Python versions
   - Matrix strategy: Python 3.11, 3.12, 3.13
   - Installs dependencies from requirements.txt and requirements-dev.txt
   - Initializes test databases (if script exists)
   - Runs pytest with coverage reporting
   - Enforces 80% minimum code coverage threshold
   - Uploads coverage to Codecov (Python 3.11 only)

2. **lint** - Runs code quality checks
   - Runs black for code formatting
   - Runs isort for import sorting
   - Runs flake8 for linting
   - Runs mypy for type checking

3. **security** - Runs security scans
   - Runs Bandit for Python security issues
   - Runs pip-audit for dependency vulnerabilities
   - Runs safety check for known vulnerabilities
   - Runs Semgrep for additional security patterns

4. **quality-gate** - Final gate that checks all previous jobs
   - Requires test, lint, and security jobs to pass
   - Fails if any job fails
   - Generates a summary of results
   - This is the job that should be required for PR merging

### tests-and-coverage.yml (Legacy)

The original test workflow is maintained for backward compatibility. New features should use `ci.yml`.

### integration.yml - Integration Tests

Located at `.github/workflows/integration.yml`, this workflow runs integration tests.

#### Triggers
- Pull requests to main branch
- Daily scheduled runs at 2 AM UTC

#### Jobs

1. **integration** - Runs integration tests
   - Runs tests in tests/integration/ directory (if exists)
   - Runs broker integration tests
   - Uploads test results as artifacts

### performance.yml - Performance Tests

Located at `.github/workflows/performance.yml`, this workflow runs performance tests when triggered.

#### Triggers
- Pull requests labeled with `performance`

#### Jobs

1. **performance** - Runs performance benchmarks
   - Runs pytest-benchmark tests
   - Starts API and runs load tests with Locust (if available)
   - Uploads performance results

### security-scan.yml - Comprehensive Security Scanning

Located at `.github/workflows/security-scan.yml`, this workflow provides comprehensive security scanning.

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
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests with coverage
pytest --cov=src --cov-report=term --cov-report=html --cov-fail-under=80

# View coverage report
open htmlcov/index.html  # On macOS
# or
xdg-open htmlcov/index.html  # On Linux
```

### Running Individual CI Checks Locally

```bash
# Format checking
black --check src/ tests/

# Import sorting
isort --check-only src/ tests/

# Linting
flake8 src/ tests/ --max-line-length=120

# Type checking
mypy src/ --ignore-missing-imports --exclude "src/legacy/"

# Security scanning
bandit -r src/ -f json -o bandit-report.json
pip-audit --requirement requirements.txt --desc
safety check
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

- Run black locally: `black --check src/ tests/`
- Run isort locally: `isort --check-only src/ tests/`
- Run flake8 locally: `flake8 src/ tests/ --max-line-length=120`
- Run mypy locally: `mypy src/ --ignore-missing-imports --exclude "src/legacy/"`

## Quality Gate Status

The quality gate ensures:
- ✅ All tests pass (Python 3.11, 3.12, 3.13)
- ✅ Coverage meets threshold (≥80%)
- ✅ Code formatting is consistent (black)
- ✅ Import sorting is correct (isort)
- ✅ Code passes linting (flake8)
- ✅ Type checking passes (mypy)
- ✅ Security scans pass (bandit, pip-audit, safety, semgrep)

When all checks pass, you'll see: **✅ Quality gate passed**

When checks fail, you'll see: **❌ Quality gate failed** with details about which job failed.

## CI/CD Pipeline Features

### Implemented Features
- ✅ Multi-version Python testing (3.11, 3.12, 3.13)
- ✅ Automated code coverage reporting with Codecov
- ✅ Code formatting and linting checks
- ✅ Type checking with mypy
- ✅ Security scanning (Bandit, pip-audit, safety, Semgrep)
- ✅ Integration tests (scheduled and on-demand)
- ✅ Performance tests (on-demand with label trigger)
- ✅ Dependency caching for faster builds
- ✅ Workflow concurrency control
- ✅ Comprehensive security scanning (secrets, vulnerabilities, SBOM)

### CI Optimization
- **Caching**: pip packages are cached to speed up builds
- **Concurrency**: In-progress runs are cancelled when new commits are pushed
- **Matrix builds**: Tests run in parallel across Python versions
- **Conditional jobs**: Performance tests only run when labeled

### Coverage Reporting
- Coverage reports are uploaded to Codecov for tracking trends
- XML and terminal reports generated for each test run
- 80% minimum coverage threshold enforced
- Coverage data available as workflow artifacts

## CI Skip for Documentation Changes

For documentation-only changes that don't require full CI:

Add `[skip ci]` to commit message:
```bash
git commit -m "docs: update README [skip ci]"
```

## Future Enhancements

Consider adding:
- ✅ Integration tests for end-to-end workflows (IMPLEMENTED)
- ✅ Performance benchmarking tests (IMPLEMENTED)
- ✅ Security scanning (IMPLEMENTED via security-scan.yml)
- Mutation testing to verify test quality
- Automatic coverage trend reports
- Deployment workflows for staging/production
- Docker image building and publishing
