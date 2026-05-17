# CI License Policy Split Decision

## Purpose

Decide whether license compliance should treat runtime dependencies, development tools, CI tools, and optional data providers as one policy surface or separate policy lanes.

## Current trigger

The current license failure is:

- Package: frozendict
- Version: 2.4.7
- License expression: GNU Lesser General Public License v3 (LGPLv3)
- Dependency path: yfinance -> frozendict

This differs from prior exact-string normalization fixes because the expression is copyleft-family and the parent dependency is runtime-declared.

## Core questions

1. Is yfinance required for runtime trading behavior?
2. Can yfinance be optional, dev only, or isolated behind an extras group?
3. Should LGPLv3 be allowed for runtime dependencies?
4. Should CI have separate license gates for runtime, dev, and tooling dependencies?
5. Should DVC and data science tooling be scanned separately from broker execution code?

## Dependency lanes proposal

Define explicit policy lanes and scan each lane independently.

- Runtime lane:
  Dependencies required for broker execution, order routing, risk checks, live signal evaluation, and production services.
- Optional data-provider lane:
  Integrations used for enrichment, analytics, or fallback data that are not required for core live execution.
- Dev and tooling lane:
  Linters, test frameworks, docs tooling, notebooks, CI helpers, and local developer utilities.
- Data science and MLOps lane:
  DVC stack, experiment tracking, model lifecycle, and research workflows that are not required for broker execution at runtime.

## Decision stance (this document)

- Do not allow LGPLv3 globally.
- Do not add `GNU Lesser General Public License v3 (LGPLv3)` to the current unified allow-list at this stage.
- Do not remove yfinance blindly.
- First classify dependencies into lanes and implement lane-specific license checks.
- After lane split is active, decide one of the following with explicit risk sign-off:
  - Isolate yfinance/frozendict outside runtime lane, or
  - Accept exact frozendict expression only for the lane where it is required, with documented runtime risk decision.

## Evaluation matrix

Use this matrix for final governance sign-off.

- Runtime-critical + copyleft-family license:
  Highest review threshold. Requires explicit legal and product-risk acceptance.
- Runtime-optional + copyleft-family license:
  Prefer isolation into optional lane; avoid global policy expansion.
- Dev/tooling-only + copyleft-family license:
  Evaluate in tooling lane; do not automatically propagate to runtime allow-list.

## Near-term implementation plan

1. Inventory direct dependencies into lane manifests (runtime, optional, dev/tooling, data-science).
2. Add separate CI license jobs per lane.
3. Keep runtime lane strict and aligned to broker-execution risk profile.
4. Re-run scan and confirm whether frozendict remains only in non-runtime lanes or remains runtime-bound.
5. Make explicit governance call on yfinance/frozendict based on lane results.

## Non-goals and hard boundary

- No trading capability expansion.
- No broker execution changes.
- No strategy automation changes.
- No live port changes.
- No dependency upgrades.
- No LGPLv3 allow-list patch until lane split decision is implemented and approved.
