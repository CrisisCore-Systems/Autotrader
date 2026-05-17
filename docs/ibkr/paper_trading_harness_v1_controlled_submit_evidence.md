# IBKR Paper Trading Harness v1 Controlled Submit Evidence

## Purpose

Record the first controlled submit rehearsal for IBKR paper harness v1 as a bounded, manual, paper-only validation event.

## Run Classification

- Type: controlled submit rehearsal
- Scope: single manual paper-order attempt
- Mode: harness v1 only
- Date: 2026-05-17 (UTC)
- Evidence artifact: `reports/ibkr/paper_trading_harness_v1_status.submit.json`

## Command Executed

```powershell
python scripts/run_ibkr_paper_trading_harness_v1.py `
  --paper-only `
  --ibkr-host 127.0.0.1 `
  --ibkr-port 7497 `
  --ibkr-client-id 90 `
  --max-order-notional 5 `
  --cancel-after-seconds 5 `
  --submit-paper-order `
  --i-understand-this-submits-a-paper-order YES_PAPER_ORDER_ONLY `
  --status-output reports/ibkr/paper_trading_harness_v1_status.submit.json
```

## Controlled Submit Result

- `fixtures_passed = true`
- `accepted_signal_id = sim-v1-001`
- `order_submission_attempted = true`
- `connected = true`
- `submitted = true`
- `cancel_attempted = true`
- `cancelled = true`
- `order_id = 1`
- `order_status = submitted`

## End-to-End Path Proven

The rehearsal successfully executed the bounded path:

1. Preflight guard stack passed.
2. Local paper endpoint connected.
3. One constrained paper limit order submitted.
4. Cancel attempted after configured delay.
5. Disconnect recorded.
6. Status artifact written and preserved.

## Boundary Integrity Confirmation

- Paper port `7497` only.
- No `7496` listener detected during pre-check.
- No obvious strategy runner process detected during pre-check.
- One manual submit trigger only.
- One paper order only.
- No retry loop.
- Artifact preserved for evidence.

## Safety Interpretation

This confirms the v1 harness can move one simulated signal through a fully bounded paper-only execution path without escalating to strategy automation, multi-order behavior, or live routing.

## Explicit Non-Expansion Statement

This evidence does not authorize:

- strategy automation,
- repeated or looped submissions,
- increased notional limits,
- live account routing,
- live port usage.

## Next Safe Milestones

1. IBKR paper harness v1 status review and operator quickstart.
2. Paper harness v1 second controlled rehearsal.

Both milestones must preserve the same manual trigger, one-order cap, and paper-only guardrails.
