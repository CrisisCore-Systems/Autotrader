# Optional Market Data Dependency Decision

## Trigger

License Compliance surfaced frozendict 2.4.7 under GNU Lesser General Public License v3 (LGPLv3).

## Provenance

yfinance is directly declared and pulls frozendict transitively.

## Decision

Decision: move yfinance to optional market-data lane.

## Rationale

Market data enrichment should not force LGPLv3 into the core runtime execution policy. The project should separate broker/runtime execution dependencies from optional data-provider dependencies.

This decision keeps runtime governance strict while preserving optional data-provider flexibility.

## Decision options considered

- Option A: Keep yfinance as runtime dependency and explicitly accept frozendict LGPLv3 in runtime policy.
- Option B: Move yfinance behind optional extras / optional market-data lane.
- Option C: Replace yfinance with another provider.
- Option D: Remove yfinance until needed.
- Option E: Split CI license checks so optional market-data dependencies are governed separately.

## Selected direction

- Do not accept LGPLv3 globally.
- Do not remove yfinance blindly.
- Move yfinance into an optional market-data lane or optional extras group.
- License-scan runtime core separately from optional providers.

## Implementation options

1. dependency extras
2. separate requirements-market-data.txt
3. separate CI license lane
4. provider abstraction

## Follow-up checkpoints

1. Define how optional market-data dependencies are enabled in local/dev/prod workflows.
2. Add a CI lane that scans optional market-data dependencies separately from runtime core.
3. Re-run license scans and ensure runtime lane remains free of optional provider license spillover.
4. Revisit provider replacement only if optional-lane governance is not acceptable.

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, dependency upgrades, or trading automation changed.
