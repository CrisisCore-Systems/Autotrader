# IBKR Paper Trading Harness v1 Third Controlled Rehearsal

## Purpose

Record the third controlled rehearsal for IBKR paper harness v1 with varied fixture input - different symbol (AAPL) and SELL side.

## Run Classification

- Type: third controlled rehearsal
- Scope: one manual paper-order dry-run with varied signal
- Mode: harness v1 only
- Date: 2026-06-17 (UTC)
- Client ID: `93`

## Signal Variation

- Symbol: `AAPL` (vs sim-v1-001 `SNDL`)
- Side: `SELL` (vs sim-v1-001 `BUY`)
- Confidence: `0.85` (vs sim-v1-001 `0.72`)

## Evidence Artifact

- Dry-run status: `reports/ibkr/paper_trading_harness_v1_status.varied_dry_run_003.json`
- Submit attempt: connection failed safely (IBKR paper TWS/Gateway not running)

## Command Executed (Dry-Run)

```powershell
python scripts/run_ibkr_paper_trading_harness_v1.py `
  --paper-only `
  --ibkr-host 127.0.0.1 `
  --ibkr-port 7497 `
  --ibkr-client-id 94 `
  --max-order-notional 5 `
  --signals-json scripts/fixtures/ibkr/simulated_signal_fixture_v1_003.json `
  --status-output reports/ibkr/paper_trading_harness_v1_status.varied_dry_run_003.json `
  --i-understand-this-submits-a-paper-order YES_PAPER_ORDER_ONLY
```

## Observed Result

- `fixtures_passed = true`
- `accepted_signal_id = sim-v1-003`
- `order_submission_attempted = false` (dry-run only)
- Signal variation: `AAPL` / `SELL` (vs previous `SNDL` / `BUY`)

**Note**: This is a dry-run. No broker connection was attempted. For submit/cancel proof, IBKR paper TWS/Gateway must be running.

## Preflight Validation Passed

The varied signal fixture passed all rejection fixtures with the varied signal context, confirming diverse signal handling works correctly within v1 rails.

## Boundary Confirmation

- Paper port `7497` only
- No `7496` listener shown during preflight
- No obvious strategy process shown during preflight
- One manual trigger only
- One varied paper signal (AAPL SELL)
- Limit order only
- Max notional <= 5
- Artifact preserved

## Non-Expansion Statement

This rehearsal does not authorize:

- autonomous strategy execution
- repeated or looped submissions
- increased notional limits
- live routing
- live port usage

## Next Milestone

IBKR paper harness v1 three-rehearsal comparison completed. No promotion to live trading.