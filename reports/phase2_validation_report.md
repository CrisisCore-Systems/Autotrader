# Phase 2 Validation Report
Generated: 2026-05-13T18:12:52.643869
Deployment Date: 2025-10-20

## Summary
- Completed trades: 3
- Active trades: 0
- Recent rejected signals: 0
- Recent scan near misses: 12
- Unique signal dates: 3
- Unique signal setups: 3
- Tracked audit sessions: 9
- Latest session status: Latest session cleared previously observed blockers.
- Wins / Losses: 1 / 2
- Win rate: 33.3%
- 95% confidence interval: 6.1% to 79.2%
- Profit factor: 1.02
- Average return: 0.00%
- Total P&L: $0.20
- Max drawdown: $-4.91
- Milestone status: No milestone reached yet

## Regime Breakdown
| Regime | Trades | Wins | Losses | Win Rate | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| UNKNOWN | 1 | 0 | 1 | 0.0% | $-4.85 |
| risk_on | 2 | 1 | 1 | 50.0% | $5.05 |

## Ticker Breakdown
| Ticker | Trades | Wins | Losses | Win Rate | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| INTR | 1 | 0 | 1 | 0.0% | $-4.85 |
| SPCE | 2 | 1 | 1 | 50.0% | $5.05 |

## Signal Setup Breakdown
| Setup | Trades | Wins | Losses | Win Rate | Total P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| INTR@2025-10-20 | 1 | 0 | 1 | 0.0% | $-4.85 |
| SPCE@2026-03-31 | 1 | 1 | 0 | 100.0% | $9.96 |
| SPCE@2026-04-06 | 1 | 0 | 1 | 0.0% | $-4.91 |

## Losing Trades
| Ticker | Exit Time | Regime | P&L | Return % | Gap % | Vol Mult |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| INTR | 2026-05-13T00:00:00-04:00 | UNKNOWN | $-4.85 | -5.00% | 12.6% | 0.0x |
| SPCE | 2026-05-13T00:00:00-04:00 | risk_on | $-4.91 | -5.00% | 10.2% | 6.2x |

## Recent Rejected Signals
No rejected signals recorded in the latest paper-trading session.

## Recent Scan Near Misses
| Ticker | Date | Reason | Gap % | Vol Mult | Target |
| --- | --- | --- | ---: | ---: | --- |
| EVGO | 2026-04-08 | gap_outside_sweet_spot | 7.8% | 1.1x | 10-15 |
| SPCE | 2026-04-08 | volume_outside_sweet_spot | 10.2% | 1.2x | 4-10x or >=15x |
| ACHR | 2026-04-08 | gap_outside_sweet_spot | 7.9% | 1.0x | 10-15 |
| NIO | 2026-02-05 | gap_outside_sweet_spot | 7.7% | 2.7x | 10-15 |
| BBAI | 2026-04-08 | gap_outside_sweet_spot | 9.3% | 0.9x | 10-15 |
| ADT | 2026-05-13 | blocklisted | 1.0% | 0.6x | N/A |
| COMP | 2026-04-08 | gap_outside_sweet_spot | 9.9% | 2.1x | 10-15 |
| NVAX | 2026-04-08 | gap_outside_sweet_spot | 7.4% | 1.0x | 10-15 |
| INTR | 2026-04-08 | gap_outside_sweet_spot | 9.4% | 2.2x | 10-15 |
| TLRY | 2026-01-09 | volume_outside_sweet_spot | 10.1% | 2.5x | 4-10x or >=15x |
| CGC | 2026-04-23 | gap_outside_sweet_spot | 9.4% | 3.5x | 10-15 |
| OGI | 2026-03-05 | gap_outside_sweet_spot | 7.9% | 2.4x | 10-15 |

### Near Miss Counts By Reason
| Reason | Count | Latest Example |
| --- | ---: | --- |
| gap_outside_sweet_spot | 9 | OGI (2026-03-05) |
| volume_outside_sweet_spot | 2 | TLRY (2026-01-09) |
| blocklisted | 1 | ADT (2026-05-13) |

## Session Audit Trend
- Tracked audit sessions: 9
- Sessions with rejected signals: 3
- Sessions with scan near misses: 1
- Sessions with executed trades: 6
- Total rejected signals across tracked sessions: 3
- Total scan near misses across tracked sessions: 12
- Dominant blocker: cash_runway (3 occurrences; latest reason: Only 1.8 months runway (need 6.0))
- Latest session interpretation: Latest session cleared previously observed blockers.

### Trend By Stage
| Stage | Count |
| --- | ---: |
| advanced_quality_gate | 3 |

### Trend By Check
| Check | Count | Latest Reason |
| --- | ---: | --- |
| cash_runway | 3 | Only 1.8 months runway (need 6.0) |
