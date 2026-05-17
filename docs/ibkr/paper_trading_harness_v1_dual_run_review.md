# IBKR Paper Trading Harness v1 Dual-Run Review

## Purpose

Review the first two controlled IBKR paper harness v1 rehearsals and decide whether a third controlled rehearsal with varied fixture input is allowed.

This review does not authorize autonomous strategy execution.

## Reviewed checkpoints

| Rehearsal | Evidence doc | Artifact | Client ID | Result |
|---|---|---|---:|---|
| 001 | paper_trading_harness_v1_controlled_submit_evidence.md | reports/ibkr/paper_trading_harness_v1_status.submit.json | 90 | success |
| 002 | paper_trading_harness_v1_second_controlled_rehearsal.md | reports/ibkr/paper_trading_harness_v1_status.submit_002.json | 91 | success |

## Shared successful fields

Both rehearsals recorded:

- `fixtures_passed = true`
- `accepted_signal_id = sim-v1-001`
- `order_submission_attempted = true`
- `connected = true`
- `submitted = true`
- `cancel_attempted = true`
- `cancelled = true`
- `order_status = submitted`

## Boundary confirmation

Both rehearsals remained inside the v1 rails:

- Paper port `7497` only
- Localhost only
- One manual trigger
- One simulated signal
- One capped paper order
- Limit order only
- Cancel attempted
- No retry loop
- No strategy automation
- No live routing
- No live port usage

## Stability assessment

The harness has now demonstrated repeatable controlled paper execution across two manual rehearsals.

The repeated success indicates the v1 guardrails, preflight validation, paper connection path, submit path, cancel path, and status artifact path are functioning as intended under the same fixture input.

## Remaining limitation

Both successful rehearsals used the same simulated signal fixture:

`sim-v1-001`

This proves repeatability of the harness path, not diversity of signal handling.

## Go / no-go decision

Go for one third controlled rehearsal with varied fixture input.

## Third rehearsal allowed scope

The third rehearsal may vary the simulated fixture while preserving all rails:

- Paper-only
- Port `7497`
- Localhost
- One manual trigger
- One signal
- One capped paper order
- Limit order only
- Max notional `<= 5`
- Immediate cancel path
- Status artifact preserved

## Still forbidden

- Autonomous strategy execution
- Live routing
- Live port `7496`
- Market orders
- Multi-order loops
- Retry loops
- Increased notional
- Background execution
- Any paper-to-live escalation

## Next milestone

IBKR paper harness v1 varied-fixture rehearsal plan.

That milestone should define a safe alternate simulated signal fixture before any third controlled submit is attempted.
