# IBKR Paper Trading Harness v1 Phase 1 Closeout

## Phase 1 Closeout Verdict

### Controlled paper submit/cancel path
- Demonstrated **twice** (rehearsal 001, rehearsal 002)
- Both used sim-v1-001 (SNDL BUY)
- Artifacts: `paper_trading_harness_v1_status.submit.json`, `paper_trading_harness_v1_status.submit_002.json`

### Varied signal handling (preflight + dry-run)
- Demonstrated through preflight + dry-run (rehearsal 003)
- Used sim-v1-003 (AAPL SELL)
- Artifact: `paper_trading_harness_v1_status.varied_dry_run_003.json`

### Varied signal broker submit/cancel
- **Not yet demonstrated** (rehearsal 003 was dry-run only)

## Status Artifacts Preserved

| Artifact | Signal | Side | Purpose |
|---|---|---|---|
| `paper_trading_harness_v1_status.submit.json` | sim-v1-001 | BUY | First controlled submit |
| `paper_trading_harness_v1_status.submit_002.json` | sim-v1-001 | BUY | Second controlled submit |
| `paper_trading_harness_v1_status.varied_dry_run_003.json` | sim-v1-003 | SELL | Varied signal dry-run proof |

## Forbidden Actions (Confirmed)

- **Live trading**: Forbidden. Live port 7496 remains blocked.
- **Autonomous strategy execution**: Forbidden.
- **Paper-to-live promotion**: Not authorized.

## Decision

Proceed to Phase 2 **only as strategy-fed paper execution**.

The harness has proven bounded paper execution twice, and varied-signal preflight handling once. The next milestone requires explicit promotion documentation before any live trading is considered.

## Caution on sim-v1-003 Fixture

Treat sim-v1-003 (AAPL SELL) as a preflight/dry-run fixture only. A SELL order:

- May imply closing an existing position
- May open a short position
- Has margin/permission implications
- Can mutate paper-account state unexpectedly

For full varied controlled-submit proof in future rehearsals, use a fixture that avoids short-side ambiguity:

- BUY side
- STK
- LMT
- Whole share
- Notional <= 5
- Paper-only flag
- Localhost
- Port 7497
- One order
- Immediate cancel

No market opinion. Just plumbing proof.