# gap9_vol2 Experiment Summary

- Experiment name: `gap9_vol2`
- Config: `configs/pennyhunter_experiment_gap9_vol2.yaml`
- Baseline config: `configs/pennyhunter.yaml`
- Hypothesis: lower gap floor and volume threshold increases valid setup availability without degrading validation quality.
- Current status: final post-repair continuation completed; experiment rejected.
- Completed trades: `6`
- Wins: `2`
- Losses: `4`
- Win rate: `33.3%`
- Net closed P&L: `+$0.30`
- Active trades: `0`
- Baseline contamination: `NONE`
- Ticker counts: `CGC=1, COMP=1, INTR=1, SPCE=2, TLRY=1`
- Repeated ticker count: `1`
- Unique signal setup count: `6`
- Ejected tickers: `NONE` after memory repair
- Near misses: `12`
- Memory recording: idempotent via `recorded_outcomes` and deterministic outcome keys
- Future run validity: post-repair experiment runs are valid only after this repair point

## Final Continuation Result

The `gap9_vol2 post-repair continuation` used the active `CGC` trade as the clean continuation point.
`CGC` closed at `STOP` for realized P&L `-$4.94`, which moved the fenced experiment to `6` completed trades, `2` wins, `4` losses, `33.3%` win rate, and `+$0.30` net closed P&L.
No new active positions remain after the continuation, repeated ticker count remained `1`, unique signal setup count finished at `6`, near misses finished at `12`, and repaired memory logic still shows no ejected tickers.

## Milestone Summary

The experiment reached the first 5 completed-trade milestone, but it failed the initial validation gate.
The completed set finished at 2 wins, 3 losses, a 40.0% win rate, and `$5.24` net closed P&L.
Result: the looser `9-15%` gap and `>=2x` volume scan did increase setup availability, but the first milestone does not support merging this variant into baseline.
The final post-repair continuation did not recover trade quality preservation: the fenced sample finished at `6` completed trades, `2` wins, `4` losses, `33.3%` win rate, and `+$0.30` net closed P&L.

## Loss Pattern Summary

- All four completed losses exited via `STOP`.
- Losing tickers were `SPCE`, `INTR`, `TLRY`, and `CGC`.
- Loss sizes remained tightly clustered near the risk target: about `$-4.91`, `$-4.89`, `$-4.59`, and `$-4.94`.
- The final sample confirms the relaxed scan increased setup availability, but failed to preserve trade quality.

## Win Pattern Summary

- Both completed wins exited via `TARGET`.
- Winning tickers were `SPCE` and `COMP`.
- Win sizes were materially larger than each individual loss: about `$9.96` and `$9.67`.
- Net P&L remained slightly positive only because average win size stayed roughly double average loss size.

## Discrepancy Audit

Visible paper-trade data shows `SPCE` appears `2` times in the experiment trade report, but the experimental memory DB reports `SPCE` with more total trades and an ejection reason based on `4` trades (`1W/3L`).

This was confirmed as a counting bug, not a separate internal outcome model.

Evidence:

- The visible completed trade set contains `SPCE=2`, `COMP=1`, `INTR=1`, `TLRY=1`.
- The experimental memory DB currently shows inflated totals such as `SPCE total_trades=9`, `COMP total_trades=3`, and `INTR total_trades=2`.
- In `examples/runners/run_pennyhunter_paper.py`, `save_results()` iterates over every closed trade in `self.trades_log` and calls `record_trade_outcome()` on every save.
- That means previously closed trades are recorded into `ticker_stats` again on later sessions, inflating totals and eventually triggering auto-ejection from replayed history rather than unique completed trades.
- The ejection reason is also stale once a ticker is already ejected, so the stored `1W/3L` reason no longer matches the inflated current totals shown in `ticker_stats`.

Fix and repair status:

- The replay bug was fixed by making memory outcome recording idempotent with `recorded_outcomes` and deterministic outcome keys.
- The experimental `pennyhunter_memory.db` was rebuilt from visible completed trades in `reports/experiments/gap9_vol2/pennyhunter_paper_trades.json`.
- Repaired `ticker_stats` now match visible completed trade counts: `COMP=1`, `INTR=1`, `SPCE=2`, `TLRY=1`.
- Repaired `SPCE` stats are `2` completed trades, `1W / 1L`, `+$5.05`.
- The previous `SPCE` auto-ejection was invalid and was caused by replayed closed trades being counted repeatedly.
- After repair, `SPCE` is not validly ejected.

Conclusion: the discrepancy is resolved for the fenced experiment DB, and future gap9_vol2 sessions are valid only after this repair point.

## Decision

Reject `gap9_vol2` and do not merge into baseline.

## Next Recommended Action

Keep the rejection recorded as final for this experiment variant. The reason is clear: setup availability increased, but trade-quality preservation failed.