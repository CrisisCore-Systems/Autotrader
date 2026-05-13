# AutoTrader Status

Last updated: 2026-05-13

This is the canonical status document for the repository. Use this file for current launch posture, validation state, and near-term priorities. Treat older completion summaries and phase writeups as historical records unless they explicitly override a narrower subsystem detail.

## Current Truth

AutoTrader is a substantial trading platform with real infrastructure, but it is not a finished trading product.

- Core system: mostly built
- Trading validation: incomplete
- Production scaling: not done
- Reinforcement learning: infrastructure built, not validated
- Documentation: strong but fragmented
- Dependency maintenance: active but backed up
- MVP product layer: still open

## Launch Posture

| Launch lane | Status | Notes |
|-------------|--------|-------|
| Local developer demo | Ready | Package structure, scripts, docs, scanners, and dashboards exist. |
| Solo operator paper trading | Conditional | Core workflows exist, but trading validation and some operational checks remain incomplete. |
| Public beta or hosted product | Not ready | Auth, product services, and deployment hardening are incomplete. |
| Live-money autonomous trading | Not ready | Current validation and operational controls do not support a live-money readiness claim. |

## What Is Working

- Hidden-gem crypto scanner backend and supporting dashboard flows are implemented.
- BounceHunter and PennyHunter strategy infrastructure exists with paper workflows.
- Broker abstractions exist for paper trading, Alpaca, Questrade, and IBKR.
- Risk management has a strong base: liquidity, slippage, runway, sector, and volume filters plus regime detection.
- Observability is one of the strongest subsystems: structured logging, metrics, tracing, and provenance are present.
- CI runs test, lint, type-check, and security gates across supported Python versions.
- Packaging and developer workflow are mostly configured.
- Phase 2.5 memory and auto-ejector modules are developed.
- RL infrastructure exists, but it remains in a validation phase rather than an operational one.

## What Is Only Partially Proven

- Phase 2 paper-trading validation is still the main proof gap.
- Dashboard exists, but modernization and real-time polish are still open.
- Database works locally, but SQLite remains a scaling limit.
- Deployment automation is partial; staging, canary, rollback, and HA are missing.
- Integration and performance testing are not yet complete enough for stronger launch claims.
- RL training, optimization, and paper-trading validation are incomplete.
- Product-facing MVP services remain mostly roadmap or issue-driven work.

## Critical Gaps Before Stronger Claims

1. Complete Phase 2 validation with a meaningful trade sample, not isolated snapshots.
2. Produce a validation report with win rate, confidence interval, profit factor, Sharpe, drawdown, and loss analysis.
3. Wire Phase 2.5 memory hooks into live paper-trading flow and prove ticker ejection behavior with real outcomes.
4. Define a hard gate for any live-capital use.
5. Reduce documentation contradiction by routing readers here first.

## Current Maturity Read

- Core capability coverage is high enough to treat the repository as usable engineering foundation.
- Production maturity is materially lower than subsystem completion claims in older docs.
- The most defensible public label today is: internal alpha / paper-trading beta candidate.

## Now / Next / Later

### Now

- Finish Phase 2 paper validation.
- Create and maintain one validation report for the current strategy.
- Integrate Phase 2.5 memory hooks into the live paper loop.
- Triage stale dependency PRs and merge safe patch-level updates.

### Next

- Consolidate contradictory docs and archive superseded status snapshots.
- Plan PostgreSQL migration and backup/restore testing.
- Add staging, rollback, and runtime kill-switch controls.
- Modernize the dashboard once the backend truth layer is stable.

### Later

- Expand product services such as auth, strategy CRUD, and richer execution services.
- Validate RL against fixed baselines before any production positioning.
- Pursue HA, multi-user hosting, and broader commercial packaging only after trading proof is in place.

## Reader Guidance

- For execution priorities, see `ROADMAP_NOW_NEXT_LATER.md`.
- For repository maturity context, see `docs/MATURITY_ASSESSMENT.md`.
- For roadmap context, see `docs/STRATEGIC_ROADMAP.md`.
- For current feature inventory, see `docs/FEATURE_STATUS.md`.
- For historical Phase 2.5 implementation notes, see `docs/phases/PHASE_2.5_TODO.md` and related phase docs.

If another document claims the overall repository is production-ready, treat that claim as subsystem-scoped or outdated unless it cites current end-to-end validation.