# CI Failure Triage 2026-05-17

## Goal

Identify which failures are baseline, stale, dependency related, or introduced by recent IBKR safety work.

## Checks reviewed

| Check | Status | Likely cause | Related to IBKR PRs | Action |
|---|---|---|---|---|
| Codacy Static Code Analysis | FAILURE | Existing static analysis backlog or repo-wide rules drift | No (scope-only docs/scripts/fixtures in PRs #120/#121) | Capture failing rules and open baseline issue |
| Validation Pipeline/Data Pipeline Validation | FAILURE | Baseline data/validation pipeline instability not touched by IBKR safety files | No | Link failing job log and assign pipeline owner |
| security-scan/Dependency Review | FAILURE | Dependency gate policy/noise versus repository dependency graph | No dependency manifests changed in PRs #120/#121 | Trace exact dependency violation and classify as baseline or actionable |
| security-scan/License Compliance Check | FAILURE | License policy baseline mismatch | No | Export offending package list and open compliance issue |
| security-scan/Prompt Contract Validation | FAILURE | Prompt contract baseline rule failure | No | Record failing contract and owner |
| security-scan/Python Dependency Audit | FAILURE | Baseline Python vulnerability findings | No dependency manifest changes | Export advisory list and severity triage |
| tests-and-coverage/lint | FAILURE | Existing lint debt outside scoped files | Likely no | Capture top failing modules and create debt ticket |
| CI Pipeline/lint | FAILURE | Existing lint debt in broader repository | Likely no | Compare against baseline branch and classify unchanged failures |
| notebook-validation/notebook-summary | FAILURE | Existing notebook metadata/state issue | No | Capture failing notebook and define cleanup path |
| tests-and-coverage/quality-gate | FAILURE | Aggregated downstream failures, not a direct IBKR signal | Likely no | Treat as meta-gate; track root failing checks |
| CI Pipeline/quality-gate | FAILURE | Aggregated gate over failing jobs | Likely no | Track as dependent on underlying failures |
| CI Pipeline/security | FAILURE | Aggregated security stage includes known failing checks | Likely no | Resolve underlying security-scan failures first |
| tests-and-coverage/test (3.11) | FAILURE | Baseline test instability/regression outside scoped files | Likely no | Capture failing tests and owner |
| CI Pipeline/test (3.11) | FAILURE | Same baseline test instability in parallel workflow | Likely no | De-duplicate with tests-and-coverage failure tracking |
| notebook-validation/validate-notebooks (3.11) | FAILURE | Existing notebook execution/lint issue | No | Record failing notebook cells and issue link |
| notebook-validation/validate-notebooks (3.13) | FAILURE | Existing notebook execution/lint issue on py3.13 | No | Record env-specific failure details |

## Classification

### Baseline failures

- Codacy Static Code Analysis
- Validation Pipeline/Data Pipeline Validation
- tests-and-coverage/lint
- CI Pipeline/lint
- tests-and-coverage/test (3.11)
- CI Pipeline/test (3.11)
- notebook-validation/notebook-summary
- notebook-validation/validate-notebooks (3.11)
- notebook-validation/validate-notebooks (3.13)
- tests-and-coverage/quality-gate
- CI Pipeline/quality-gate
- CI Pipeline/security

### Dependency review failures

- security-scan/Dependency Review
- security-scan/Python Dependency Audit

### Security scan failures

- security-scan/License Compliance Check
- security-scan/Prompt Contract Validation
- security-scan/Dependency Review
- security-scan/Python Dependency Audit

### Test failures

- tests-and-coverage/test (3.11)
- CI Pipeline/test (3.11)

### Unknown / needs logs

- Validation Pipeline/Data Pipeline Validation (needs failing step trace)
- notebook-validation/notebook-summary (needs notebook metadata diff)

## Merge policy impact

No further trading capability work until:
- dependency review source is identified
- security scan failures are classified
- failing checks are linked to issues or fixed

## Ownership and next triage actions

- Assign dependency owner for Dependency Review and Python Dependency Audit.
- Assign security owner for License Compliance and Prompt Contract failures.
- Assign notebook owner for notebook-summary and validate-notebooks failures.
- Assign CI owner for quality-gate and aggregated security failures.
- Create issue links for each unresolved baseline failure and update this register.
