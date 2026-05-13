# AutoTrader Roadmap: Now / Next / Later

Last updated: 2026-05-13

This roadmap separates immediate repository work from longer-horizon platform ambitions. Use it with `STATUS.md`: status says what is true now, this file says what should happen next.

## Now

These items should move before any broader production or product narrative.

### 1. Prove the trading loop

- Complete Phase 2 paper-trading validation to a meaningful sample size.
- Publish one validation report with win rate, confidence interval, profit factor, Sharpe, drawdown, average return, and losing-trade analysis.
- Define a hard gate for any live-capital use.

### 2. Wire the learning loop that already exists

- Connect Phase 2.5 memory hooks to scanner signal logging.
- Update ticker performance automatically from paper-trade outcomes.
- Run dry ejection reviews after the first 5 to 10 trades to confirm that the ejection logic behaves sensibly.

### 3. Clean the truth surface

- Keep `STATUS.md` as the repository-wide source of truth.
- Relabel or archive high-traffic docs that make broader readiness claims than the current evidence supports.
- Reduce duplicate status pages that drift out of sync.

### 4. Clear low-risk maintenance debt

- Triage stale dependency PRs.
- Merge safe patch-level updates in small batches.
- Remove tracked generated artifacts and keep ignore rules enforced.

## Next

These items make sense once the trading proof and status surface are stable.

### 1. Harden operations

- Create a PostgreSQL migration plan.
- Add backup and restore testing.
- Introduce staging, rollback, and operator kill-switch controls.
- Add broker disconnect, failed job, and stale-data alerts.

### 2. Improve product reliability

- Expand integration tests around broker workflows and critical paths.
- Add performance tests for the main API and trading workflows.
- Modernize the dashboard with real-time updates only after the backend truth layer is stable.

### 3. Consolidate architecture guidance

- Publish one architecture map for `src`, `autotrader`, `pipeline`, `dashboard`, `backtest`, and orchestration layers.
- Mark legacy or subsystem-scoped documents more aggressively.

## Later

These items are legitimate, but they should not outrank validation and operational safety.

### 1. Productize

- Add auth and multi-user controls.
- Add strategy CRUD and richer user-facing services.
- Build a stronger hosted-product shell only after core operator workflows are proven.

### 2. Scale infrastructure

- Move beyond single-instance deployment.
- Add HA, canary deployment, and automated rollback.
- Revisit larger-scale market-data ambitions only if real usage requires them.

### 3. Advance research systems

- Validate RL against fixed baselines before any stronger positioning.
- Expand portfolio optimization only after live or paper evidence shows incremental value.
- Extend asset-class coverage only after the current loop is stable.

## Decision Rule

If a proposed task does not improve one of these first:

- trading proof,
- operational safety,
- status accuracy, or
- maintainability,

then it is probably `Next` or `Later`, not `Now`.