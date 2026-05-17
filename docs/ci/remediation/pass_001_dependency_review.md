# CI Remediation Pass 001: Dependency Review

## Linked issue

#124

## Goal

Identify the source of the Dependency Review failure and classify it as baseline debt or a regression introduced by PRs #120/#121.

## Evidence captured

### Workflow run context
- Workflow: `security-scan.yml` (GitHub Actions)
- Run ID: 25979482761
- Run URL: https://github.com/CrisisCore-Systems/Autotrader/actions/runs/25979482761
- Commit SHA: 89a4e34f353698606f20e12e82ce528e9e1acd0a (HEAD of main after PR #122/#123 merges)
- Status: Completed
- Event: Push to main
- Created: 2026-05-17T02:47:02Z

### Failing checks
1. **Python Dependency Audit**: FAILED
2. **License Compliance Check**: FAILED
3. **Prompt Contract Validation**: FAILED
4. **Dependency Review**: SKIPPED (not run, not failed)

### Python Dependency Audit findings
**Result**: Zero vulnerabilities found

Artifact: `pip-audit-results.json`
- Tool: `pip-audit` v2.10.0
- Python version: 3.11.15
- Dependencies scanned: 269
- Vulnerabilities found: 0
- Fixes available: 0

Sample output (all dependencies clean):
```json
{
  "dependencies": [
    {"name": "fastapi", "version": "0.136.1", "vulns": []},
    {"name": "pydantic", "version": "2.12.3", "vulns": []},
    {"name": "sqlalchemy", "version": "2.0.35", "vulns": []},
    ... (266 more dependencies, all with empty vulns arrays)
  ],
  "fixes": []
}
```

### Dependency Review check status
- **Result**: SKIPPED
- **Reason**: Dependency Review is a GitHub native check that runs under specific conditions (typically on pull requests or when dependencies are modified)
- **Impact**: This check did not contribute to the main branch failure

## PR scope verification

### PR #120: "IBKR single-signal paper trading harness v0"
**Files changed**:
- `.gitignore`
- `docs/ibkr/pre_transmit_safety_checkpoint_v0.md`
- `scripts/run_ibkr_simulated_signal_paper_harness.py`

**Dependency manifests touched**: NO ✓

### PR #121: "IBKR batch simulated signal rejection audit v0"
**Files changed**:
- `.gitignore`
- `fixtures/ibkr/simulated_signal_batch_001.json`
- `scripts/run_ibkr_simulated_signal_batch_audit.py`

**Dependency manifests touched**: NO ✓

### Manifest files verified as unmodified
- ✓ `requirements.txt`
- ✓ `pyproject.toml`
- ✓ `poetry.lock`
- ✓ `package.json`
- ✓ `package-lock.json`
- ✓ `Dockerfile`
- ✓ `.github/dependabot.yml`
- ✓ All `Pipfile` variants

## Classification

### Baseline vs regression analysis
- **pip-audit result**: ZERO vulnerabilities found (both PRs and main branch clean)
- **PR #120 impact on dependencies**: None (changed gitignore, docs, scripts only)
- **PR #121 impact on dependencies**: None (changed gitignore, fixtures, scripts only)
- **Dependency Review status**: Skipped (not applicable to main branch push, only PR events)

### Failure classification: **BASELINE NOISE**

**Reasoning**:
1. Python Dependency Audit job **fails** but reports **zero vulnerabilities**
2. No actual security issue exists in the dependency tree
3. Neither PR #120 nor PR #121 modified any dependency manifests
4. The failure is not a regression from these PRs
5. The failure is not related to actual package vulnerabilities
6. The failure appears to be infrastructure-related (check configuration or CI job exit logic)

## Decision

**Classification**: Baseline infrastructure debt, not a package security issue

**Action required on #124**:
1. Investigate Python Dependency Audit job failure reason despite zero vulnerabilities
2. Verify if job exit code is misconfigured
3. Check if License Compliance Check or Prompt Contract Validation are the actual root causes
4. Consider separating these three checks into individual triage items if root causes differ

## Follow-up issue needed

**Yes** — but scope narrowing required

**Create sub-ticket**:
- Root cause of "Python Dependency Audit FAILED" despite zero vulnerabilities (likely job configuration, not actual vulnerability)
- Separate triage for "License Compliance Check" failure
- Separate triage for "Prompt Contract Validation" failure
- Keep "Dependency Review" as skipped status reference

**Recommendation**: Do NOT treat this as a package security debt. The failure is CI infrastructure, not package management.
