# Package Metadata CI Propagation Fix

## Goal

Ensure dependency lane license reports see the checked-out local `autotrader` package metadata before generating `pip-licenses` artifacts.

## Trigger

After PR #163 added explicit package metadata, local validation reported `autotrader` as `Proprietary`, but CI lane artifacts from run `25987503091` still reported `autotrader 0.1.0` as `UNKNOWN`.

## Fix

Add an explicit local project metadata install step to `dependency-lane-license-report.yml`:

`python -m pip install --no-deps -e .`

## Why this is narrow

The step installs the checked-out package metadata without installing dependencies. It does not move dependencies, change manifests, replace security scanning, or alter runtime behavior.

## Expected result

Future lane license artifacts should report:

`autotrader 0.1.0 Proprietary`

instead of:

`autotrader 0.1.0 UNKNOWN`

## Boundary

No requirements.txt changes.
No pyproject.toml changes.
No dependency movement.
No license allow-list changes.
No security-scan.yml replacement.
No runtime behavior changes.
No trading behavior changes.
