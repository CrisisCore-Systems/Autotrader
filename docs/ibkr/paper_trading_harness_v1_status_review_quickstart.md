# IBKR Paper Trading Harness v1 Status Review and Operator Quickstart

## Purpose

Provide a repeatable operator guide for reading harness status artifacts and running bounded v1 commands safely.

Scope remains paper-only and manual-trigger only.

## 1) How to Read the Status Artifact

Primary artifact paths used by v1 runs:

- Dry-run: `reports/ibkr/paper_trading_harness_v1_status.local.json`
- Controlled submit: `reports/ibkr/paper_trading_harness_v1_status.submit.json`

Review with:

```powershell
Get-Content reports/ibkr/paper_trading_harness_v1_status.local.json
Get-Content reports/ibkr/paper_trading_harness_v1_status.submit.json
```

Read these top-level blocks first:

- `constraints`: confirms guardrails (paper-only, localhost, port 7497, LMT, STK, one-order cap).
- `request`: confirms actual run flags and operator intent.
- `result`: primary pass/fail and execution outcomes.
- `events`: sequence evidence (accept, connect, submit, cancel, disconnect).
- `errors`: explicit failure reasons when present.

## 2) Required Safe-Result Fields

Minimum safe baseline for any run:

- `fixtures_passed = true`
- `accepted_signal_id = sim-v1-001`
- `errors = []` or only non-fatal diagnostics

Dry-run expected:

- `order_submission_attempted = false`
- `connected = false`
- `submitted = false`

Controlled submit expected:

- `order_submission_attempted = true`
- `connected = true` (or captured connection error)
- `submitted = true` (or captured submit error)
- `cancel_attempted = true` if submit succeeded
- `cancelled = true` preferred for rehearsal completion

## 3) Dry-Run Command

```powershell
python scripts/run_ibkr_paper_trading_harness_v1.py `
  --paper-only `
  --i-understand-this-submits-a-paper-order YES_PAPER_ORDER_ONLY `
  --status-output reports/ibkr/paper_trading_harness_v1_status.local.json
```

## 4) Controlled-Submit Command

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

## 5) Stop Conditions

Stop immediately and do not proceed to another run if any of the following occurs:

- Host is not local (`127.0.0.1` or `localhost`).
- Port is not `7497`.
- Confirmation phrase mismatch.
- Preflight rejects the valid signal.
- Unexpected multi-order behavior is observed.
- Artifact cannot be written.

## 6) What Must Not Be Retried

Do not repeatedly rerun controlled submit attempts in a loop.

Specifically do not retry blindly after:

- Connection failure,
- Submit failure,
- Cancel failure,
- Any boundary mismatch.

Classify once from artifact evidence, resolve root cause, then schedule a separate controlled rehearsal window.

## 7) What Evidence to Preserve

Preserve the following for each controlled rehearsal:

- Full status artifact JSON.
- Command used (exact flags).
- Timestamp and operator context.
- Key result fields (`fixtures_passed`, `accepted_signal_id`, `order_submission_attempted`, `connected`, `submitted`, `cancel_attempted`, `cancelled`, `order_id`, `order_status`).
- Boundary confirmation notes (paper-only, no live routing, no loops).

## Boundary Reminder

This quickstart does not authorize strategy automation, repeated submissions, higher notional caps, live routing, live ports, or autonomous strategy feed integration.
