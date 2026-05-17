# Lane License Policy Draft

## Purpose

Define non-enforcing license policy expectations per dependency lane before CI gates are introduced.

## Current state

Dependency lane reporting is operational and reliable.

- Runtime lane reports successfully
- Broker lane reports successfully
- Market-data lane reports successfully
- MLOps lane reports successfully
- Internal autotrader package metadata now reports Proprietary across all four lanes

Checkpoint: package-metadata-ci-propagation-v0

## Policy posture by lane

| Lane | Posture | Rationale |
|---|---|---|
| runtime | strict | Core execution path should avoid unresolved, unknown, or copyleft-sensitive licenses unless explicitly accepted |
| broker | strict | Broker and exchange connectivity touches execution infrastructure and should remain tightly governed |
| market-data | separately governed | Optional enrichment providers may carry different license risk and should not contaminate runtime policy |
| mlops | separately governed | Data science and DVC tooling often carries broader license surface and should be governed apart from runtime |
| dev/tooling | separately governed | Test, lint, scan, and build tooling should be visible but not treated as runtime exposure |

## Draft license handling

### Strict lanes

Runtime and broker lanes should prefer:

- MIT
- BSD-family
- Apache-2.0
- ISC
- Python-2.0
- clearly documented internal/proprietary metadata

Strict lanes should flag for review:

- UNKNOWN
- GPL
- LGPL
- AGPL
- MPL
- Zope
- CNRI
- complex OR / AND expressions
- license expressions with linking exceptions

### Separately governed lanes

Market-data, MLOps, and dev/tooling lanes may contain broader license families, but every sensitive expression must be classified before enforcement.

## Known sensitive findings

| Lane | Package | License | Draft action |
|---|---|---|---|
| market-data | frozendict | LGPLv3 | legal/governance review before gate |
| mlops | pygit2 | GPLv2 with linking exception | document exception handling |
| mlops | zc.lockfile | Zope Public License | classify before gate |
| mlops | grandalf | GPLv2 | review before enforcement |
| runtime | regex | Apache-2.0 AND CNRI-Python | classify CNRI handling |
| all lanes | autotrader | Proprietary | accepted internal metadata |

## Rollout plan

### Phase 1: Observe

Generate lane reports and classify findings.

Status: active.

### Phase 2: Document

Record lane-specific policy expectations and known sensitive packages.

Status: this document.

### Phase 3: Warn

Introduce non-blocking CI summaries that surface policy violations without failing builds.

### Phase 4: Gate strict lanes

Enable enforcement for runtime and broker lanes first.

### Phase 5: Gate separately governed lanes

Only after explicit acceptance/rejection records exist for market-data, MLOps, and dev/tooling.

## Non-enforcement statement

This document does not enable any CI gate.

It does not modify license allow-lists.

It does not change dependency installation behavior.

It does not move dependencies between lanes.

## Boundary

No requirements.txt changes.
No pyproject.toml changes.
No workflow changes.
No dependency movement.
No license allow-list changes.
No runtime behavior changes.
No trading behavior changes.
No artifact JSON files committed.
