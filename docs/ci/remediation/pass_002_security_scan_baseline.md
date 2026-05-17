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
  ```
  pip-licenses \
    --format=json \
    --output-file=licenses.json \
    --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0" \
    --allow-only="MIT;MIT License;Apache-2.0;Apache Software License;Apache License 2.0;Apache-2.0 OR BSD-2-Clause;MIT OR Apache-2.0;BSD License;Apache Software License; BSD License;BSD;BSD-3-Clause;BSD-2-Clause;ISC;ISC License (ISCL);Python-2.0;Python Software Foundation License;PSF-2.0;MPL-2.0;MPL-2.0 AND (Apache-2.0 OR MIT);UNKNOWN;GNU General Public License v2 (GPLv2)"
  ```

### Key Observation
The `--allow-only` list contains many variants of the same license (e.g., "MIT License", "MIT" as separate items) and includes:
- "UNKNOWN" license (indicating undetected/unspecified licenses are allowed)
- "GNU General Public License v2 (GPLv2)" (explicitly allowed despite GPL being in deny list)
- Multiple license string variants (spacing, naming differences)

### Failure Classification
**Evidence**: Workflow run 25979482761 shows License Compliance Check failed, but:
- pip-audit found zero vulnerabilities
- Dependency audit passed (despite safety policy file issue)
- No artifact evidence available (check failed before upload)

**Root cause candidates**:
1. Unknown license detection in dependencies (UNKNOWN is allowed but may not be matching correctly)
2. License name mismatch in allow-only list vs. actual package metadata
3. Inconsistent license string formatting between pip-licenses and package metadata
4. Safety policy file missing (.safety-policy.yml referenced in Python Dependency Audit step)

### Classification
**Status**: Cannot fully classify without license report artifact

**Recommended action**: Regenerate the license check locally to capture the exact violation:
```bash
pip install -r requirements.txt
pip-licenses --format=json --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0"
```

Then identify:
- Which package(s) violated the allow-only list
- What license string was reported by pip-licenses
- Whether it's a baseline unknown license or an actual GPL variant

---

## Lane B: Prompt Contract Validation Failure

### Workflow context
- Run: 25979482761
- Job: Prompt Contract Validation
- Status: FAILED
- Date: 2026-05-17T02:48:16Z

### Tool & Configuration
- Tool: Custom Python script `scripts/validate_prompt_contracts.py` (inferred from workflow)
- Command: (needs extraction from workflow file)
- Dependencies: jsonschema, pyyaml

### Failure Detection
Prompt Contract Validation step appears in the same run with FAILED status, but detailed log extraction did not yield specific violation text (logs may be sparse or output to stderr not captured in selected context).

### Known from workflow
From the workflow file, the job runs:
```yaml
- name: Install dependencies
  run: pip install jsonschema pyyaml
- name: Validate prompt contracts
  run: python scripts/validate_prompt_contracts.py --config configs/prompts.yaml
```

### Classification
**Status**: Evidence insufficient for full classification

**Next step required**: Extract full logs from Prompt Contract Validation job step to identify:
- The exact validation rule or schema that failed
- Which prompt/configuration file triggered the violation
- Whether the failure is schema version, config syntax, or content-related

---

## Cross-Cutting Observations

### Multiple failure pattern
Same workflow run shows:
- Python Dependency Audit: FAILED (exit code 2 from safety, missing .safety-policy.yml)
- License Compliance Check: FAILED (unknown root cause from pip-licenses)
- Prompt Contract Validation: FAILED (unknown root cause from validation script)
- Trivy Filesystem & Config scans: SUCCESS
- All other checks: SUCCESS

### Policy implications
The failures suggest:
1. **Lane A** (License Check): Allowlist configuration may be too restrictive or have formatting issues
2. **Lane B** (Prompt Validation): Likely unrelated to IBKR work (new governance check)
3. **Shared root**: Missing configuration files or schema version mismatches

### Hard Boundary Confirmation
✓ No dependency manifest changes needed for investigation  
✓ No broker code changes required  
✓ No trading logic changes needed  
✓ Evidence-only collection in progress  

---

## Recommended Next Action

1. **Lane A**: Rerun license check locally and capture exact violation message
2. **Lane B**: Extract full logs from Prompt Contract Validation to identify schema/config issue
3. **Both lanes**: Do NOT patch until root cause is clearly named
4. **Continue**: #132 Test/lint workflow failures (next pass)

## Follow-up
Link evidence findings to #136 and #137 once complete.
