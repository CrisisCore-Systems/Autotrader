# Smoke Tests

Quick validation tests for rapid feedback during development.

## Available Scripts

### ibkr_smoke_test.py
Fast smoke test for IBKR connection and basic functionality.

**Usage:**
```bash
python scripts/testing/smoke/ibkr_smoke_test.py
```

**Description:**
- Validates IBKR connection in under 30 seconds
- Tests basic account access
- Verifies order placement capability
- Ideal for quick checks during development

**Prerequisites:**
- TWS running on port 7497
- Paper trading account configured
- API settings enabled

## When to Use Smoke Tests

- Before starting development sessions
- After configuration changes
- Quick validation before running full test suites
- CI/CD pipeline pre-checks

For comprehensive testing, use the manual integration tests in `scripts/testing/manual_integration/`.
