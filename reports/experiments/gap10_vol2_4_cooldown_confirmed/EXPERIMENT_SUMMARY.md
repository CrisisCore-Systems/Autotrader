# gap10_vol2_4_cooldown_confirmed Experiment Summary

- Experiment name: gap10_vol2_4_cooldown_confirmed
- Base experiment: configs/pennyhunter_experiment_gap10_vol2_4_cooldown.yaml
- Experiment config: configs/pennyhunter_experiment_gap10_vol2_4_cooldown_confirmed.yaml
- Goal: add confirmed-entry stale signal rejection on top of the proven cooldown scaffold without changing gap or volume thresholds.
- Scan thresholds: 10-15% gap, >=2.4x volume
- Ticker cooldown: enabled
- Concurrency cap: unchanged from base experiment
- Entry confirmation:
  - enabled: true
  - max_signal_age_days: 2
  - require_green_confirmation_bar: false
  - reject_stop_hit_before_confirmation: false
- Mode: isolated scan-only dry confirmation check
- Trader run: not run
- execute_signal: not called

## Fenced Output Paths

- reports/experiments/gap10_vol2_4_cooldown_confirmed/pennyhunter_paper_trades.json
- reports/experiments/gap10_vol2_4_cooldown_confirmed/pennyhunter_cumulative_history.json
- reports/experiments/gap10_vol2_4_cooldown_confirmed/pennyhunter_memory.db
- reports/experiments/gap10_vol2_4_cooldown_confirmed/bouncehunter_agent.db
- reports/experiments/gap10_vol2_4_cooldown_confirmed/phase2_validation_report.json
- reports/experiments/gap10_vol2_4_cooldown_confirmed/phase2_validation_report.md
- reports/experiments/gap10_vol2_4_cooldown_confirmed/EXPERIMENT_SUMMARY.md

## Dry Check Status

- Check type: scan-only dry confirmation
- Trader run: not run
- execute_signal: not called
- Signals before cooldown: SPCE, TLRY
- Eligible after cooldown: SPCE, TLRY
- Cooldown decisions: none
- Signals rejected by entry_confirmation: SPCE, TLRY
- Rejection reasons:
  - SPCE: signal age 38d exceeds max 2d
  - TLRY: signal age 125d exceeds max 2d
- Any trade remains eligible after entry_confirmation: false
- Eligible after entry_confirmation: none
- baseline_changed: NONE
- Git status after dry check: untracked scaffold files only
