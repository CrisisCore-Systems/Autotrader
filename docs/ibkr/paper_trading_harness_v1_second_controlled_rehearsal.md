# IBKR Paper Trading Harness v1 Second Controlled Rehearsal

## Purpose

Record the second controlled rehearsal for IBKR paper harness v1 as a bounded, manual, paper-only validation event.

## Run Classification

- Type: second controlled rehearsal
- Scope: one manual paper-order attempt
- Mode: harness v1 only
- Date: 2026-05-17 (UTC)
- Client ID: `91`

## Evidence Artifact

- Preserved artifact: `reports/ibkr/paper_trading_harness_v1_status.submit_002.json`

## Command Executed

```powershell
python scripts/run_ibkr_paper_trading_harness_v1.py `
  --paper-only `
  --ibkr-host 127.0.0.1 `
  --ibkr-port 7497 `
  --ibkr-client-id 91 `
  --max-order-notional 5 `
  --cancel-after-seconds 5 `
  --submit-paper-order `
  --i-understand-this-submits-a-paper-order YES_PAPER_ORDER_ONLY `
  --status-output reports/ibkr/paper_trading_harness_v1_status.submit_002.json
```

## Observed Result

- `fixtures_passed = true`
- `accepted_signal_id = sim-v1-001`
- `order_submission_attempted = true`
- `connected = true`
- `submitted = true`
- `cancel_attempted = true`
- `cancelled = true`
- `order_id = 1`
- `order_status = submitted`
- `errors = []`

## End-to-End Path Confirmed

The bounded v1 path completed in sequence:

1. Preflight accepted simulated signal `sim-v1-001`.
2. Connected to IBKR paper endpoint.
3. Submitted one constrained paper limit order.
4. Attempted cancel after configured delay.
5. Cancel succeeded.
6. Disconnect completed.
7. Status artifact written and preserved.

## Boundary Confirmation

- Paper port `7497` only.
- No `7496` listener shown during preflight.
- No obvious strategy process shown during preflight.
- One manual trigger only.
- One paper order only.
- No retry loop.
- Artifact preserved.

## Non-Expansion Statement

This rehearsal does not authorize:

- autonomous strategy execution,
- repeated submission loops,
- higher notional caps,
- live routing,
- live port usage.

## Next Milestone

IBKR paper harness v1 dual-run review.

The dual-run review determines readiness for a third controlled rehearsal with varied fixture input. It does not authorize autonomous strategy execution.
