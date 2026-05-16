# CI Baseline Drift Register

Validator/intake work: clean locally, not implicated in CI failures.

---

## CI Pipeline
- Black formatting drift in `src/security/prompt_validator.py` and `tests/test_prompt_validator.py`
- Existing mlflow CVE from pip-audit

## tests-and-coverage
- Ruff unused imports in unrelated files

## Validation Pipeline
- DVC remote config drift: remote 's3cache' does not exist

## notebook-validation
- Notebook lint drift
- Missing `notebooks/example_analysis.ipynb`
- Import path failure: No module named src.core

## security-scan
- Missing SARIF outputs
- TruffleHog base/head same-commit failure
- pip-audit uses unsupported --fix-dry-run flag
- Existing high vulnerabilities from Grype
- scripts import path failure in alert/prompt validation jobs

---

## Repair Order

Fix in separate PR-sized commits, in this order:

1. Formatter/linter drift
2. Import path failures
3. DVC remote handling
4. Notebook workflow
5. Security workflow flags and SARIF handling
6. Existing dependency vulnerabilities

---

## Truth Posture

```
Backtest proof exists.
Paper-trade intake exists.
Paper-trade validator passes locally.
CI is red from baseline drift.
Paper-trade validation is pending.
Live capital remains blocked.
```
