# gap10_vol2_4_cooldown_confirmed_v2 Experiment Summary

- Experiment name: gap10_vol2_4_cooldown_confirmed_v2
- Base experiment: configs/pennyhunter_experiment_gap10_vol2_4_cooldown_confirmed.yaml
- Experiment config: configs/pennyhunter_experiment_gap10_vol2_4_cooldown_confirmed_v2.yaml
- Goal: add upstream scan freshness filtering while keeping downstream entry confirmation enabled.
- Scan thresholds: 10-15% gap, >=2.4x volume
- Ticker cooldown: enabled
- Concurrency cap: unchanged from base experiment
- Upstream scan freshness:
  - only_recent_signals: true
  - max_signal_age_days: 2
- Entry confirmation:
  - enabled: true
  - max_signal_age_days: 2
  - require_green_confirmation_bar: false
  - reject_stop_hit_before_confirmation: false
- Mode: isolated scan-only dry check
- Trader run: not run
- execute_signal: not called

## Fenced Output Paths

- reports/experiments/gap10_vol2_4_cooldown_confirmed_v2/pennyhunter_paper_trades.json
- reports/experiments/gap10_vol2_4_cooldown_confirmed_v2/pennyhunter_cumulative_history.json
- reports/experiments/gap10_vol2_4_cooldown_confirmed_v2/pennyhunter_memory.db
- reports/experiments/gap10_vol2_4_cooldown_confirmed_v2/bouncehunter_agent.db
- reports/experiments/gap10_vol2_4_cooldown_confirmed_v2/phase2_validation_report.json
- reports/experiments/gap10_vol2_4_cooldown_confirmed_v2/phase2_validation_report.md
- reports/experiments/gap10_vol2_4_cooldown_confirmed_v2/EXPERIMENT_SUMMARY.md

## Dry Check Status

- Git status before dry check: clean
- Scanned universe size: 26
- Signals before scan freshness: SPCE, TLRY
- Signals rejected by scan freshness:
  - SPCE (2026-04-06): signal age 38d exceeds max 2d
  - TLRY (2026-01-09): signal age 125d exceeds max 2d
- Signals after scan freshness: none
- Cooldown decisions: none
- Entry confirmation decisions: none
- Any trade remains eligible: false
- baseline_changed: NONE
- Final git status: untracked scaffold files only

### Interpretation

- Upstream scan freshness filtered stale historical candidates before cooldown and entry confirmation.
- No trade candidate remains eligible in this scan-only state.
- Keep this branch in scan-only monitoring until at least one candidate survives scan freshness.
