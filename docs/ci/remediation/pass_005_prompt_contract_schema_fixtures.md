# CI Remediation Pass 005: Prompt Contract Schema Fixtures

## Trigger

After adding `scripts/validation/__init__.py`, Prompt Contract Validation moved past import failure and began validating real contract fixtures.

## Current failure

- Workflow run: 25983234951
- Exact failing script: `python scripts/validate_prompt_contracts.py`
- Missing fixture/schema:
  - `tests/fixtures/prompt_outputs/contract_safety.schema_golden.json`
  - `tests/fixtures/prompt_outputs/narrative_analyzer.schema_golden.json`
  - `tests/fixtures/prompt_outputs/onchain_activity.schema_golden.json`
  - `tests/fixtures/prompt_outputs/technical_pattern.schema_golden.json`
- Missing required properties:
  - `[contract_safety] Schema validation failed: 'safety_score' is a required property`
  - `[narrative_analyzer] Schema validation failed: '1.0.0' was expected` (fixture had `v1.0.0`)

## Fix applied

- Added:
  - `tests/fixtures/prompt_outputs/contract_safety.schema_golden.json`
  - `tests/fixtures/prompt_outputs/narrative_analyzer.schema_golden.json`
  - `tests/fixtures/prompt_outputs/onchain_activity.schema_golden.json`
  - `tests/fixtures/prompt_outputs/technical_pattern.schema_golden.json`
- Updated:
  - `tests/fixtures/prompt_outputs/contract_safety_golden.json` (aligned with `contract_safety.json` required fields including `safety_score`)
  - `tests/fixtures/prompt_outputs/narrative_analyzer_golden.json` (set `schema_version` to `1.0.0` to match canonical schema const)

## Classification

CI contract fixture/schema debt, not broker/trading regression.

## Boundary

No broker code, strategy code, execution behavior, live ports, order sizing, or trading automation changed.
