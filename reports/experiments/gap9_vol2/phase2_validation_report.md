# Phase 2 Validation Report
Generated: 2026-05-13T19:36:18.304440
Deployment Date: 2025-10-20

## Summary
- Completed trades: 5
- Active trades: 1
- Recent rejected signals: 0
- Recent scan near misses: 11
- Unique signal dates: 5
- Unique signal setups: 6
- Tracked audit sessions: 6
- Latest session status: Latest session cleared previously observed blockers.
- Wins / Losses: 2 / 3
- Win rate: 40.0%
- 95% confidence interval: 11.8% to 76.9%
- Profit factor: 1.36
- Average return: 1.00%
- Total P&L: $5.24
- Max drawdown: $-9.48
- Milestone status: ❌ Initial Validation FAILED (2/5 wins = 40.0% vs 60% target)

## Regime Breakdown
| Regime | Trades | Wins | Losses | Win Rate | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| risk_on | 5 | 2 | 3 | 40.0% | $5.24 |

## Ticker Breakdown
| Ticker | Trades | Wins | Losses | Win Rate | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| COMP | 1 | 1 | 0 | 100.0% | $9.67 |
| INTR | 1 | 0 | 1 | 0.0% | $-4.89 |
| SPCE | 2 | 1 | 1 | 50.0% | $5.05 |
| TLRY | 1 | 0 | 1 | 0.0% | $-4.59 |

## Signal Setup Breakdown
| Setup | Trades | Wins | Losses | Win Rate | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| COMP@2026-04-08 | 1 | 1 | 0 | 100.0% | $9.67 |
| INTR@2026-04-08 | 1 | 0 | 1 | 0.0% | $-4.89 |
| SPCE@2026-03-31 | 1 | 1 | 0 | 100.0% | $9.96 |
| SPCE@2026-04-06 | 1 | 0 | 1 | 0.0% | $-4.91 |
| TLRY@2026-01-09 | 1 | 0 | 1 | 0.0% | $-4.59 |

## Losing Trades
| Ticker | Exit Time | Regime | P&L | Return % | Gap % | Vol Mult |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| SPCE | 2026-05-13T00:00:00-04:00 | risk_on | $-4.91 | -5.00% | 10.2% | 6.2x |
| INTR | 2026-05-13T00:00:00-04:00 | risk_on | $-4.89 | -5.00% | 9.4% | 2.2x |
| TLRY | 2026-05-13T00:00:00-04:00 | risk_on | $-4.59 | -5.00% | 10.1% | 2.5x |

## Recent Rejected Signals
No rejected signals recorded in the latest paper-trading session.

## Recent Scan Near Misses
| Ticker | Date | Reason | Gap % | Vol Mult | Target |
| --- | --- | --- | ---: | ---: | --- |
| EVGO | 2026-04-08 | gap_outside_sweet_spot | 7.8% | 1.1x | 9-15 |
| SPCE | 2026-04-08 | volume_outside_sweet_spot | 10.2% | 1.2x | >= 2.0x |
| ACHR | 2026-04-08 | gap_outside_sweet_spot | 7.9% | 1.0x | 9-15 |
| NIO | 2026-02-05 | gap_outside_sweet_spot | 7.7% | 2.7x | 9-15 |
| BBAI | 2026-04-08 | volume_outside_sweet_spot | 9.3% | 0.9x | >= 2.0x |
| ADT | 2026-05-13 | blocklisted | 1.0% | 0.6x | N/A |
| COMP | 2026-04-08 | already_processed | 9.9% | 2.1x | N/A |
| NVAX | 2026-04-08 | gap_outside_sweet_spot | 7.4% | 1.0x | 9-15 |
| INTR | 2026-04-08 | already_processed | 9.4% | 2.2x | N/A |
| TLRY | 2026-01-09 | already_processed | 10.1% | 2.5x | N/A |
| OGI | 2026-03-05 | gap_outside_sweet_spot | 7.9% | 2.4x | 9-15 |

### Near Miss Counts By Reason
| Reason | Count | Latest Example |
| --- | ---: | --- |
| gap_outside_sweet_spot | 5 | OGI (2026-03-05) |
| already_processed | 3 | TLRY (2026-01-09) |
| volume_outside_sweet_spot | 2 | BBAI (2026-04-08) |
| blocklisted | 1 | ADT (2026-05-13) |

## Session Audit Trend
- Tracked audit sessions: 6
- Sessions with rejected signals: 0
- Sessions with scan near misses: 6
- Sessions with executed trades: 6
- Total rejected signals across tracked sessions: 0
- Total scan near misses across tracked sessions: 54
- Latest session interpretation: Latest session cleared previously observed blockers.
