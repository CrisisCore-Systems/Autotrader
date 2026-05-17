# Dependency Lane Inventory

## Purpose

Classify dependencies by policy lane before changing license policy again.

## Evidence sources

- Manifest declarations: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`
- Resolver evidence (no install): `pip install --dry-run -r requirements.txt`
- Local environment graph snapshot: `reports/validation/ci/dependency_lane_inventory_pipdeptree.txt`
- Prior CI license-scan evidence for expression mismatches and package versions

## Lane definitions

- Runtime execution: Required for core app runtime and service execution.
- Broker/exchange integration: Broker APIs and exchange client stacks used for execution and market connectivity.
- Optional market data providers: External data providers that can be isolated from core execution.
- Research/backtesting: Analytics and experimentation libraries not strictly required for live execution.
- Data science / MLOps: DVC/model/data lifecycle tooling.
- CI/dev tooling: Test, lint, validation, and developer tooling.
- Documentation/build tooling: Docs and build-only packages.
- Unknown / needs classification: Not enough evidence or policy owner needed.

## Inventory table

| Package | Version | Lane | Direct/Transitive | Parent | Declared In | License Signal | Decision |
|---|---:|---|---|---|---|---|---|
| yfinance | >=0.2.38 (resolves 1.3.0) | Optional market data providers | Direct | none | requirements.txt / pyproject.toml | pulls frozendict LGPLv3 | isolate/review |
| frozendict | 2.4.7 | Optional market data providers | Transitive | yfinance | via yfinance | GNU Lesser General Public License v3 (LGPLv3) | do not globally allow |
| dvc[s3] | 3.51.0 | Data science / MLOps | Direct | none | requirements.txt / pyproject.toml | transitive non-permissive expressions previously surfaced in CI | keep separate lane governance |
| scmrepo | 3.6.2 | Data science / MLOps | Transitive | dvc | via dvc[s3] | parent of pygit2 chain | keep separate lane governance |
| pygit2 | 1.19.2 | Data science / MLOps | Transitive | scmrepo | via dvc[s3] -> scmrepo | GPLv2 with linking exception (accepted exact token previously) | keep exact-token policy only |
| zc.lockfile | 4.0 | Data science / MLOps | Transitive | dvc | via dvc[s3] | Zope Public License (accepted exact token previously) | keep exact-token policy only |
| aiohttp | >=3.8.0 (resolves 3.13.5) | Broker/exchange integration | Direct and transitive | direct + ccxt transitive | pyproject.toml / requirements.txt | Apache-2.0 AND MIT expression previously required exact token | already governed exact token |
| certifi | local 2025.10.5 (CI has reported 2026.4.22) | Runtime execution | Transitive | requests/httpx/aiohttp stack | transitive via runtime HTTP clients | Mozilla Public License 2.0 (MPL 2.0) exact token previously added | already governed exact token |
| regex | 2026.5.9 | Runtime execution | Transitive | nltk | via requirements runtime stack | Apache-2.0 AND CNRI-Python expression previously required exact token | already governed exact token |
| greenlet | 3.5.0 | Runtime execution | Transitive | SQLAlchemy | via SQLAlchemy | no new CI thorn yet | monitor |
| SQLAlchemy | >=2.0.35,<2.0.36 (resolves 2.0.35) | Runtime execution | Direct | none | requirements.txt | no new CI thorn yet | runtime-approved lane |
| ib_insync | >=0.9.86 (local 0.9.86) | Broker/exchange integration | Direct | none | requirements.txt | no new CI thorn yet | runtime-approved lane |
| ibapi | not found in manifests | Unknown / needs classification | Unknown | Unknown | not declared in scanned manifests | none observed | clarify if used indirectly |
| ccxt (Binance/Kraken support path) | 4.5.12 | Broker/exchange integration | Direct | none | requirements.txt | dependency surface for exchange adapters | runtime-approved lane, monitor licenses |

## Preliminary conclusions

1. `frozendict` is not an isolated tooling artifact; it enters via runtime-declared `yfinance`.
2. `dvc[s3]` and its chain (`scmrepo`, `pygit2`, `zc.lockfile`) should remain in a separate Data science / MLOps governance lane and not drive blanket runtime policy expansion.
3. Runtime and optional data-provider lanes must be split before any new copyleft-family allow-list action.

## Next decision checkpoint

Before any license allow-list change:

1. Decide whether `yfinance` stays in runtime lane, moves to optional lane, or is replaced.
2. Define CI jobs per lane (runtime vs optional-data vs mlops/dev).
3. Re-run lane-specific license scans and make explicit risk sign-off per lane.

## Boundary

- No trading capability expansion.
- No broker execution changes.
- No strategy automation changes.
- No live ports changes.
- No dependency upgrades.
- No LGPLv3 allow-list patch in this pass.
