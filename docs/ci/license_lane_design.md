# CI License Lane Design

## Trigger

frozendict reports LGPLv3 through yfinance, which is currently runtime-declared.

## Problem

The current security-scan license job treats all installed dependencies as one policy surface.

## Design decision

Split license validation into dependency lanes before modifying dependency declarations or allow-lists.

## Proposed CI lanes

| Lane | Install source | Purpose | License posture |
|---|---|---|---|
| runtime | requirements-runtime.txt or core pyproject deps | core application/runtime | strict |
| broker | broker extra or broker requirements | IBKR / exchange connectivity | strict |
| optional-market-data | market-data extra | yfinance/provider enrichment | separately governed |
| mlops | mlops requirements | dvc/scmrepo/data tooling | separately governed |
| dev | requirements-dev.txt | tests/scanners/build tooling | separately governed |

## Governance stance

- Runtime lane stays strict.
- Optional market data gets separate governance.
- DVC / MLOps tooling gets separate governance.
- LGPLv3 is not added to the global allow-list.
- yfinance is not moved yet.

## Implementation sequence

1. Document current dependency ownership.
2. Add lane-specific requirements files or pyproject extras.
3. Add CI license jobs per lane.
4. Keep runtime strict.
5. Decide whether optional market data lane accepts exact LGPLv3 expression.
6. Only then move yfinance.

## Planning outputs

- Lane ownership matrix for runtime, broker, optional-market-data, mlops, and dev.
- CI job blueprint mapping each lane to install source and allow-list policy.
- Governance sign-off criteria for copyleft-family expressions in non-runtime lanes.

## Boundary

No dependency movement, workflow change, broker code, strategy code, execution behavior, live ports, order sizing, or trading automation changed in this planning step.
