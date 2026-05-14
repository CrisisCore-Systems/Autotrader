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

## Status

Scaffold created only.
The trader has not been run for this experiment yet.
Do not merge this branch into baseline.