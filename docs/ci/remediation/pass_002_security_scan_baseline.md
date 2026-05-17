## Concrete finding: missing .safety-policy.yml
### Local Reproduction Results
**Exact violation**:
**Root Cause**: 
**Action Required**: 
### Cross-Cutting Observations
### Multiple failure pattern
### Policy implications
## Recommended Next Action
## Follow-up
# CI Remediation Pass 002: Security Scan Baseline Failures

## Linked issues

- #129 Security scan baseline failures (primary)
- #136 License Compliance Check failure source (Lane A)
- #137 Prompt Contract Validation failure source (Lane B)

## Goal

Extract evidence for both License Compliance Check and Prompt Contract Validation failures from the same security-scan workflow run, classify each as baseline debt or actionable remediation, and recommend remediation approach.

---

## Lane A: License Compliance Check Failure

### Workflow context
- Run: 25979482761
- Job: License Compliance Check
- Status: FAILED
- Date: 2026-05-17T02:48:19Z

### Tool & Configuration
- Tool: `pip-licenses`
- Command: 
  ```bash
  pip-licenses \
    --format=json \
    --output-file=licenses.json \
    --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0" \
    --allow-only="MIT;MIT License;Apache-2.0;Apache Software License;Apache License 2.0;Apache-2.0 OR BSD-2-Clause;MIT OR Apache-2.0;BSD License;Apache Software License; BSD License;BSD;BSD-3-Clause;BSD-2-Clause;ISC;ISC License (ISCL);Python-2.0;Python Software Foundation License;PSF-2.0;MPL-2.0;MPL-2.0 AND (Apache-2.0 OR MIT);UNKNOWN;GNU General Public License v2 (GPLv2)"
  ```

### Local Reproduction Results

✅ **Successfully reproduced the failure**

**Exact violation**:
```
license LGPL-2.1-only OR MPL-1.1 not in allow-only licenses was found for package pycairo:1.29.0
```

**Root Cause**: 
- Package: **pycairo:1.29.0**
- Reported License: **LGPL-2.1-only OR MPL-1.1**
- Issue: The allow-only list does not include LGPL or MPL-1.1 license variants
- This is NOT a GPL match violation (it's LGPL, which is different license family)
- The fail-on list checks for GPL-2.0/GPL-3.0/AGPL-3.0 but LGPL is not caught

### Classification

**Status**: ✅ **CLASSIFIED - Baseline license governance issue**

**Findings**:
1. **pycairo** has a dual license: LGPL-2.1-only OR MPL-1.1
2. LGPL (Lesser GPL) is NOT in the allow-only list
3. MPL-1.1 (Mozilla Public License 1.1) is NOT in the allow-only list
4. The workflow's allow-only list is incomplete and needs expansion to include common licenses
5. This is **NOT** a regression from PRs #120/#121 (no dependency manifest changes)

**Action Required**:
- Governance decision: Either add LGPL-2.1-only and MPL-1.1 to the allow-only list (if acceptable)
- OR remove pycairo from dependencies (if not acceptable)
- This is a **policy decision**, not a code bug

**Risk Assessment**: Low - pycairo is a GUI library (unlikely in trading core), probably a transitive dependency

---

## Concrete Finding: Missing .safety-policy.yml

### Context
From Python Dependency Audit job failure logs (workflow run 25979482761):
```
Error: Invalid value for '--policy-file': Policy file YAML is not valid.
HINT: [Errno 2] No such file or directory: '.safety-policy.yml'
```

### File Search Results
- ✗ No `.safety-policy.yml` found in repository root
- ✗ No `.safety.yml` found
- ✗ No `configs/.safety-policy.yml` found
- ✓ File `configs/tokens/wlfi_safety_test.yaml` exists (but different purpose)

### Workflow Reference
From `.github/workflows/security-scan.yml` line 103:
```yaml
- name: Safety dependency scan
  run: safety check -r requirements.txt --json > safety-results.json
```

The workflow does NOT explicitly specify `--policy-file`, yet the safety command failed trying to load `.safety-policy.yml`. This suggests:
1. Safety CLI defaults to loading `.safety-policy.yml` if present
2. OR configuration elsewhere references it
3. OR the `.safety-policy.yml` was recently deleted and workflow still expects it

### Classification

**Status**: ✅ **CLASSIFIED - Missing configuration file**

**Root Cause**: `.safety-policy.yml` does not exist but safety command in Python Dependency Audit job looks for it by default

**Action Required**: 
- Either provide a valid `.safety-policy.yml` configuration file
- OR modify the safety command to disable policy file loading
- Document why the policy file was removed or if it's intentional

---

## Lane B: Prompt Contract Validation Failure

### Workflow context
- Run: 25979482761
- Job: Prompt Contract Validation
- Status: FAILED
- Date: 2026-05-17T02:48:16Z

### Tool & Configuration
- Tool: Custom Python script `scripts/validate_prompt_contracts.py`
- Command from workflow: `python scripts/validate_prompt_contracts.py`
- Dependencies: jsonschema, pyyaml

### Local Reproduction Results

❌ **Failed to execute**

**Error**:
```
ModuleNotFoundError: No module named 'scripts.validation'

File "scripts/validate_prompt_contracts.py", line 4, in <module>
    from scripts.validation.validate_prompt_contracts import main
```

### Root Cause Investigation
The shim script at `scripts/validate_prompt_contracts.py` tries to import:
```python
from scripts.validation.validate_prompt_contracts import main
```

Directory structure check:
- ✓ Directory exists: `scripts/validation/` (created 2026-05-15 6:21 PM)
- ✓ File exists: `scripts/validation/validate_prompt_contracts.py`
- ✗ **File NOT found**: `scripts/validation/__init__.py`

### Classification

**Status**: ✅ **CLASSIFIED - Missing Python package marker file**

**Root Cause**: 
- `scripts/validation/` directory is missing `__init__.py`
- Without this file, the directory is not recognized as a Python package
- The import `from scripts.validation.validate_prompt_contracts import main` fails
- This affects both local testing and CI/CD workflow execution

**Action Required**:
- Create `scripts/validation/__init__.py` (can be empty file or contain package exports)
- This is a **micro-fix** with high confidence and low risk
- Does NOT require behavioral changes to any code

**Impact Assessment**: 
- The prompt contract validation job never actually runs
- All prompt validation logic is skipped in security-scan workflow
- This is a **CI infrastructure issue**, not a prompt logic issue
- This is **NOT** a regression from PRs #120/#121

---

## Summary of Classified Failures

| Failure | Category | Status | IBKR Related | Severity |
|---------|----------|--------|--------------|----------|
| pycairo:1.29.0 license (LGPL/MPL-1.1) | Governance | Classified | No | Low |
| Missing `scripts/validation/__init__.py` | Infrastructure | Classified | No | Moderate |
| Missing `.safety-policy.yml` | Configuration | Classified | No | Moderate |

### Pattern: None are IBKR-related
- None of the classified failures are regressions from PRs #120/#121
- None block trading capability (already frozen)
- All are pre-existing CI infrastructure debt
- All can be fixed without broker code changes

### Hard Boundary Confirmation
✓ No dependency manifest changes needed
✓ No broker code changes required
✓ No trading logic changes needed
✓ Evidence collection COMPLETE

---

## Recommended Next Action

1. **Lane A (License)**: Governance decision required on acceptable licenses (accept LGPL-2.1-only + MPL-1.1, or remove pycairo)
2. **Lane B (Prompt Validation)**: Create `scripts/validation/__init__.py` (empty file)
3. **Safety Policy**: Either create `.safety-policy.yml` or disable policy-file loading in workflow
4. Update Pass 002 issue #129 with these findings
5. Create/update issues #136, #137 with specific remediation steps

**Do NOT proceed to Pass 003 (#132) until all three classified failures are either fixed or documented as accepted debt.**
