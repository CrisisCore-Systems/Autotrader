# Lane License Warning Reporter

## Goal

Add a warning-only CI summary layer for dependency lane license reports.

## Behavior

The reporter:

- reads the generated lane license JSON report
- detects review-sensitive license markers
- groups findings by dependency lane
- writes a readable Markdown warning summary
- appends the summary to the GitHub Actions job summary
- exits successfully even when warnings are found

## Warning categories

- UNKNOWN
- GPL
- LGPL
- AGPL
- MPL
- Zope
- CNRI
- complex AND / OR expressions
- linking-exception expressions

## Files added or changed

- scripts/ci/lane_license_warning_report.py
- .github/workflows/dependency-lane-license-report.yml

## Enforcement posture

Warning-only.

This does not introduce a CI gate.

This does not fail builds based on license findings.

## Boundary

No requirements.txt changes.
No pyproject.toml changes.
No dependency movement.
No license allow-list changes.
No security-scan.yml replacement.
No runtime behavior changes.
No trading behavior changes.
