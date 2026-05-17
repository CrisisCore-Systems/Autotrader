# Package Metadata CI Propagation Investigation

## Goal

Determine why CI dependency lane license artifacts still report `autotrader 0.1.0` as `UNKNOWN` after PR #163, while local validation reported `Proprietary`.

## Baseline Evidence

- PR #163 (metadata-only) merged cleanly.
- Post-merge lane report run `25987503091` succeeded.
- Lane artifacts still showed `autotrader 0.1.0` as `UNKNOWN` in:
  - broker
  - market-data
  - mlops
  - runtime
- Validation evidence is documented in `pass_017_package_metadata_cleanup_validation.md`.

## Working Hypothesis

The lane license workflow installs lane requirements but may not install the local checked-out project package before running `pip-licenses`.

If true, `pip-licenses` in CI can resolve package metadata differently than local editable-install validation.

## Investigation Question

Should the lane report workflow explicitly install the local project package before license generation, for example:

`python -m pip install --no-deps -e .`

## Investigation Plan

1. Inspect the current workflow install sequence and confirm whether local project install is absent.
2. Reproduce CI-like behavior locally without editable install and compare `pip-licenses` output for `autotrader`.
3. Reproduce with explicit editable install and compare output.
4. Decide whether explicit local project install is the minimal, correct fix for metadata propagation.
5. Document recommendation before any workflow patch.

## Boundaries

No workflow edits in this pass.
No dependency file edits.
No `pyproject.toml` edits.
No license policy changes.
No runtime or trading behavior changes.
