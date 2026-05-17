# Dependency Lane License Dry-Run Reports

## Goal

Generate license reports per dependency lane in CI without enforcing policy yet.

## Workflow added

`dependency-lane-license-report.yml`

## What it does

For each lane mirror file in a matrix job:

1. Set up Python 3.13
2. Install lane dependencies in isolation
3. Install `pip-licenses`
4. Generate a JSON license report
5. Upload the report as a workflow artifact

## Lanes observed

- requirements-runtime.txt
- requirements-broker.txt
- requirements-market-data.txt
- requirements-mlops.txt

## Output artifacts

- `dependency-lane-license-report-runtime`
- `dependency-lane-license-report-broker`
- `dependency-lane-license-report-market-data`
- `dependency-lane-license-report-mlops`

## Enforcement posture

Observation only.

This workflow does not enforce lane-specific license policy and does not fail builds based on license classification.

## Boundary

No requirements.txt edits.
No pyproject.toml edits.
No dependency movement.
No LGPLv3 allow-list patch.
No security-scan.yml replacement.
No runtime behavior changes.
No trading behavior changes.
