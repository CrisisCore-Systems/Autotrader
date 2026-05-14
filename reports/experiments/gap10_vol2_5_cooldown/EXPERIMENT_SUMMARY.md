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

## Interpretation

This is a valid first-run artifact, not a cooldown proof yet.
The cooldown rule becomes meaningful on the next isolated session after `SPCE` closes and a repeat-ticker decision is possible.

## Status

The trader has now completed the first isolated paper session for this experiment.
Do not merge this branch into baseline.