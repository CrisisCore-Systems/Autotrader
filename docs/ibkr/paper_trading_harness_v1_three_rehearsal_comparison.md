# IBKR Paper Trading Harness v1 Three-Rehearsal Comparison

## Purpose

Compare rehearsals 001, 002, and 003 to verify stable operation across varied inputs.

## Rehearsal Summary

| Rehearsal | Signal ID | Symbol | Side | Client ID | Status |
|---|---|---|---|---|---|
| 001 | sim-v1-001 | SNDL | BUY | 90 | submitted (broker connected) |
| 002 | sim-v1-001 | SNDL | BUY | 91 | submitted (broker connected) |
| 003 | sim-v1-003 | AAPL | SELL | 94 | preflight+dry-run only (no broker submit) |

## Boundary Drift Check

All three rehearsals stayed within v1 rails:

| Constraint | 001 | 002 | 003 |
|---|---|---|---|
| Paper port 7497 | ✓ | ✓ | ✓ |
| Localhost only | ✓ | ✓ | ✓ |
| Paper-only flag | ✓ | ✓ | ✓ |
| Fixtures passed | ✓ | ✓ | ✓ |
| Max notional <= 5 | ✓ | ✓ | ✓ |
| Limit order only | ✓ | ✓ | ✓ |
| One order max | ✓ | ✓ | ✓ |
| One manual trigger | ✓ | ✓ | ✓ |
| No retry loop | ✓ | ✓ | ✓ |

## Signal Diversity Verification

- Rehearsal 001/002: Same BUY signal on SNDL at $1.0 limit
- Rehearsal 003: Different SELL signal on AAPL at $1.0 limit

The third rehearsal proves the harness handles varied signals correctly while maintaining identical boundary checks.

## Status Artifact Comparison

Three status artifacts preserved:

| Artifact | Type |
|---|---|
| `reports/ibkr/paper_trading_harness_v1_status.submit.json` | broker submit/cancel |
| `reports/ibkr/paper_trading_harness_v1_status.submit_002.json` | broker submit/cancel |
| `reports/ibkr/paper_trading_harness_v1_status.varied_dry_run_003.json` | preflight + dry-run only (no broker submit) |

## Conclusion

Three paper harness rehearsals completed with no boundary drift:

- **Submit/cancel proof**: 2 successful broker executions (sim-v1-001)
- **Varied-signal preflight proof**: 1 dry-run validation (sim-v1-003, AAPL SELL)

Varied-signal broker submit/cancel proof **not yet demonstrated**.

**No paper-to-live promotion authorized.** The invariant remains: live trading forbidden unless every live gate passes.