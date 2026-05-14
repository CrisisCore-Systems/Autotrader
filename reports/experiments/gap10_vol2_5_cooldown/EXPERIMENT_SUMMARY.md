# gap10_vol2_5_cooldown Experiment Summary

- Experiment name: `gap10_vol2_5_cooldown`
- Base experiment: `configs/pennyhunter_experiment_gap10_vol2_5.yaml`
- Experiment config: `configs/pennyhunter_experiment_gap10_vol2_5_cooldown.yaml`
- Goal: test whether ticker cooldown improves trade quality by preventing immediate same-ticker re-entry after a close.
- Scan thresholds: `10-15%` gap, `>=2.5x` volume
- Concurrency cap: unchanged from baseline (`1` position)
- Mode: isolated paper validation only
- Baseline contamination: `NONE`

## Cooldown Rule

- If a ticker closes, block re-entry into that same ticker for the next isolated session when another eligible ticker exists.
- Prefer a different eligible ticker over the recently closed ticker.
- If no other eligible ticker exists, allow no trade rather than forcing repeat exposure.
- Cooldown decisions are recorded in the fenced paper report and cumulative history session marker under `cooldown_decisions`.

## Fenced Output Paths

- `reports/experiments/gap10_vol2_5_cooldown/pennyhunter_paper_trades.json`
- `reports/experiments/gap10_vol2_5_cooldown/pennyhunter_cumulative_history.json`
- `reports/experiments/gap10_vol2_5_cooldown/pennyhunter_memory.db`
- `reports/experiments/gap10_vol2_5_cooldown/bouncehunter_agent.db`
- `reports/experiments/gap10_vol2_5_cooldown/phase2_validation_report.json`
- `reports/experiments/gap10_vol2_5_cooldown/phase2_validation_report.md`
- `reports/experiments/gap10_vol2_5_cooldown/EXPERIMENT_SUMMARY.md`

## First Isolated Paper Session

- Signals found: `SPCE`
- Trade opened: `SPCE`
- SPCE details: `32` shares at `$3.07`, signal date `2026-04-06`, status `active`
- Skipped candidates: `none`
- cooldown_decisions: `none`
- Cooldown did not trigger because there was no prior closed trade in the fenced cooldown experiment history.
- Active trades: `1`
- Completed trades: `0`
- Wins: `0`
- Losses: `0`
- Win rate: `0.0%`
- Net closed P&L: `$0.00`
- Near misses: `12`
- Ejected tickers: `none`
- Baseline contamination: `NONE`
- Status: active paper validation, cooldown not yet exercised

## Post-Fix Cooldown Proof Run

- SPCE closed at `STOP`
- Realized P&L: `-$4.91`
- Signals found before cooldown: `SPCE`
- Eligible signals after cooldown: `none`
- Trade opened after cooldown: `none`
- Cooldown decision recorded:
	- `decision`: `skip_repeat_without_alternative`
	- `reason`: `repeat_ticker_suppressed_no_alternate`
- Active trades: `0`
- Completed trades: `1`
- Wins: `0`
- Losses: `1`
- Win rate: `0.0%`
- Net closed P&L: `-$4.91`
- Near misses: `12`
- Ejected tickers: `none`
- Baseline contamination: `NONE`
- Status: cooldown mechanism proven in live fenced path, trade-quality validation still pending

## Scan-Only Cooldown Checkpoint

- Git status before scan: `clean`
- Signals before cooldown: `SPCE`
- Eligible signals after cooldown: `none`
- Cooldown decision: `skip_repeat_without_alternative`
- Reason: `repeat_ticker_suppressed_no_alternate`
- Blocked ticker: `SPCE`
- Trade would be allowed: `false`
- Baseline files touched: `no`
- Final git status: `clean`

## Repeated Scan-Only Cooldown Block

- Git status before scan: `clean`
- Signals before cooldown: `SPCE`
- Eligible signals after cooldown: `none`
- Cooldown decision: `skip_repeat_without_alternative`
- Reason: `repeat_ticker_suppressed_no_alternate`
- Blocked ticker: `SPCE`
- Trade would be allowed: `false`
- Baseline changed: `NONE`
- Final git status: `clean`

## Interpretation

The first isolated paper session established the initial fenced state with an active `SPCE` trade.
The post-fix proof run confirmed the repaired live cooldown path behaves correctly when that trade closes and no alternate ticker is available.
The cooldown mechanism is now behaving correctly.
There is currently no non-blocked eligible ticker.
No fenced paper session is eligible.
The only available signal was repeat `SPCE`.
Cooldown correctly suppressed repeat exposure again.
Continue scan-only checks until a non-blocked eligible ticker appears.
Trade-quality validation is still pending because the experiment has only one completed trade and no alternate-selection case has occurred yet.

## Status

The trader has now completed a live fenced cooldown proof run for this experiment.
Do not merge this branch into baseline.