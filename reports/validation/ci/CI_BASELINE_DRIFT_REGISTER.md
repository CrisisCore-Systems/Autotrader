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

## dependency-triage (2026-05-15)
- Runtime dependency triage applied: FastAPI/Starlette upgraded and MLflow/Prefect moved out of runtime requirements.

---

## Trivy Terraform Config Baseline Drift

Status: Accepted temporary CI baseline drift.

The Trivy filesystem vulnerability/secret scan remains blocking.

The Trivy config scan is currently advisory because it reports pre-existing Terraform IaC findings that require infrastructure review rather than workflow repair.

Known findings:
- `terraform/main.tf`
  - `AWS-0052`: ALB does not drop invalid headers.
  - `AWS-0053`: Load balancer is publicly exposed.
- `terraform/modules/networking/main.tf`
  - `AWS-0104`: unrestricted `0.0.0.0/0` egress across load balancer, ECS task, RDS, and Redis security groups.
  - Additional HIGH networking findings reported by Trivy.

Required follow-up:
- Decide whether public ALB exposure is intentional.
- Add `drop_invalid_header_fields = true` where appropriate.
- Replace unrestricted egress with minimum required destinations where feasible.
- Re-enable config scan as blocking after Terraform review.

Expiry:
- Re-evaluate before any production infrastructure deployment.
- Current local evidence:
	- `pip-audit -r requirements.txt`: 1 remaining vulnerability (`diskcache`, `CVE-2025-69872`)
	- `safety check -r requirements.txt`: 0 vulnerabilities
- Accepted temporary risk: `diskcache` advisory has no published fixed version.
- Mitigation: keep DVC/cache paths non-world-writable in runner/runtime environments and avoid untrusted writes to cache directories.
- Expiry: 2026-06-30 (re-evaluate weekly and remove acceptance when an upstream fix is available).

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
