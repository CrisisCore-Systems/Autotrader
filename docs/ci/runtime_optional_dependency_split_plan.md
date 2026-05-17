# Runtime vs Optional Dependency Split Plan

## Trigger

`yfinance` pulls `frozendict`, which reports `GNU Lesser General Public License v3 (LGPLv3)`.

## Problem

The current dependency and license scan model treats all dependencies as one policy surface.

## Decision

Separate dependency lanes before modifying license policy.

## Proposed lanes

| Lane | Purpose | Example packages | License posture |
|---|---|---|---|
| Core runtime | Required application/runtime behavior | fastapi, pydantic, SQLAlchemy, requests | strict |
| Broker/exchange | Trading and market connectivity | ib_insync, aiohttp, ccxt | strict |
| Optional market data | Enrichment/provider data not required for core execution | yfinance, frozendict | separate governance |
| Research/backtesting | Offline analysis and experimentation | pandas, matplotlib, plotly, nltk | separate governance |
| Data science / MLOps | Data/versioning and experiment tooling | dvc, scmrepo, pygit2, zc.lockfile | separate governance |
| CI/dev tooling | Tests, scanners, and validation tooling | pytest, bandit, pip-audit, gitleaks | separate governance |

## Implementation options

1. Split requirements files by lane.
2. Use pyproject optional extras to represent non-runtime lanes.
3. Add separate CI license jobs per lane.
4. Keep current runtime scan strict.
5. Add optional-provider scan with explicit accepted-risk notes.

## Recommended implementation

Start with documentation and CI lane design before moving dependencies.

Recommended policy direction:

- Do not add LGPLv3 to the main runtime allow-list.
- Move yfinance into an optional market-data dependency lane.
- Create a separate license check for optional market-data dependencies.
- Keep broker/runtime execution policy stricter than optional enrichment policy.

## Phased execution plan

1. Define lane manifests (runtime, broker, optional market data, research, mlops, ci/dev).
2. Prototype CI license jobs per lane without changing runtime dependency behavior.
3. Validate which current packages appear in multiple lanes and resolve ownership.
4. Only then plan dependency declaration refactors in requirements/pyproject.

## Boundary

No broker code, strategy code, execution behavior, live ports, order sizing, dependency upgrades, or trading automation changed.
