# Dependency Lane Dry Run Jobs

## Goal

Add CI dry-run validation for dependency lane mirror files without replacing the existing security scan or changing runtime behavior.

## Workflow added

.github/workflows/dependency-lane-dry-run.yml

## Lanes validated

- requirements-runtime.txt
- requirements-broker.txt
- requirements-market-data.txt
- requirements-mlops.txt

## Behavior

Each lane runs in its own GitHub Actions matrix job:

1. Checkout repository
2. Set up Python 3.13
3. Upgrade pip/setuptools/wheel
4. Install the lane requirement file
5. Run pip check

## Scope

This workflow is additive only.

It does not replace security-scan.yml.
It does not move dependencies.
It does not change 
equirements.txt.
It does not change pyproject.toml.

## Boundary

No broker code changed.
No strategy code changed.
No execution behavior changed.
No trading automation changed.
No dependency upgrades were introduced.
