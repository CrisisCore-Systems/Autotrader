# Dependency Lane Implementation Plan

## Trigger

The CI license scan surfaced `frozendict` LGPLv3 through `yfinance`, which is currently runtime-declared.

## Goal

Separate dependency installation and license validation into clear lanes before moving dependencies or changing CI workflow behavior.

## Proposed files

| File | Purpose | Notes |
|---|---|---|
| requirements-runtime.txt | core runtime dependencies | strict license policy |
| requirements-broker.txt | IBKR / exchange connectivity | strict license policy |
| requirements-market-data.txt | optional market data providers | separate governance |
| requirements-mlops.txt | DVC / data tooling | separate governance |
| requirements-dev.txt | test / lint / CI tooling | separate governance |

## Candidate dependency movements

| Package | Current source | Target lane | Reason |
|---|---|---|---|
| yfinance | requirements.txt / pyproject.toml | market-data | optional enrichment, pulls frozendict |
| frozendict | transitive via yfinance | market-data | LGPLv3 signal |
| dvc[s3] | requirements.txt / pyproject.toml | mlops | data tooling |
| scmrepo | transitive via dvc | mlops | DVC dependency |
| pygit2 | transitive via scmrepo | mlops | license-governed dependency |
| zc.lockfile | transitive via dvc | mlops | license-governed dependency |
| ib_insync | TBD | broker | IBKR connectivity |
| ccxt | TBD | broker | exchange connectivity |
| aiohttp | TBD | broker/runtime | async connectivity |

## CI job design

| Job | Installs | License posture |
|---|---|---|
| license-runtime | requirements-runtime.txt | strict |
| license-broker | requirements-broker.txt | strict |
| license-market-data | requirements-market-data.txt | separately governed |
| license-mlops | requirements-mlops.txt | separately governed |
| license-dev | requirements-dev.txt | separately governed |

## Implementation sequence

1. Add requirement lane files without deleting existing manifests.
2. Populate files with copied dependency groups.
3. Add CI dry-run jobs for lane license scans.
4. Compare results against current security-scan.
5. Only after parity, migrate primary security-scan to lane jobs.
6. Only after lane jobs are stable, decide frozendict LGPLv3 handling in market-data lane.

## Non-goals

- No dependency upgrades
- No runtime behavior changes
- No broker execution changes
- No strategy automation changes
- No LGPLv3 global allow-list patch

## Boundary

This plan does not change dependency manifests, workflows, broker code, strategy code, execution behavior, live ports, order sizing, or trading automation.
