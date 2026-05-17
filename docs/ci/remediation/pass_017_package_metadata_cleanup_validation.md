# Package Metadata Cleanup Validation

## Goal

Validate whether PR #163 caused the internal utotrader package to stop reporting as UNKNOWN in dependency lane license reports.

## Source run

- Workflow: dependency-lane-license-report.yml
- Run ID: 25987503091
- Head SHA: e419283b0943fe58bdac10436e2f87c6e41b2505
- Result: success

## Expected result

utotrader 0.1.0 should report:

Proprietary

## Observed result

| Lane | Package | Version | License |
|---|---|---:|---|
| broker | autotrader | 0.1.0 | UNKNOWN |
| market-data | autotrader | 0.1.0 | UNKNOWN |
| mlops | autotrader | 0.1.0 | UNKNOWN |
| runtime | autotrader | 0.1.0 | UNKNOWN |

## Interpretation

The package metadata change in PR #163 was clean and metadata-only, but the dependency lane license report artifacts still show utotrader as UNKNOWN.

This means the CI license-report path does not yet reflect the local editable-install validation result, or the lane report workflow is resolving package metadata differently than the local validation command.

## Next investigation target

Determine why local pip-licenses sees utotrader as Proprietary while CI lane artifacts still report UNKNOWN.

Potential causes to inspect:

1. The lane report workflow may not install the local project package from the checked-out repository.
2. pip-licenses may be reading a different installed distribution context in CI.
3. The package metadata format may not be interpreted consistently across local and CI install paths.
4. The workflow may need an explicit metadata-only install step such as python -m pip install --no-deps -e . before generating lane reports.

## Boundary

No requirements.txt changes.
No pyproject.toml changes.
No workflow changes.
No dependency movement.
No license allow-list changes.
No runtime behavior changes.
No trading behavior changes.
No artifact JSON files committed.
No unrelated test files committed.
