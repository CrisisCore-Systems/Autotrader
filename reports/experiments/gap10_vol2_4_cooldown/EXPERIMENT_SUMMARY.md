# gap10_vol2_4_cooldown Experiment Summary

- Experiment name: `gap10_vol2_4_cooldown`
- Base experiment: `configs/pennyhunter_experiment_gap10_vol2_5_cooldown.yaml`
- Experiment config: `configs/pennyhunter_experiment_gap10_vol2_4_cooldown.yaml`
- Goal: test whether lowering the live scan volume threshold from `>=2.5x` to `>=2.4x` admits `TLRY` as a non-blocked alternate without reintroducing rejected gap9_vol2 noise.
- Scan thresholds: `10-15%` gap, `>=2.4x` volume
- Ticker cooldown: `enabled`
- Concurrency cap: unchanged from baseline (`1` position)
- Mode: isolated paper validation only
- Baseline contamination: `NONE`

## Fenced Output Paths

- `reports/experiments/gap10_vol2_4_cooldown/pennyhunter_paper_trades.json`
- `reports/experiments/gap10_vol2_4_cooldown/pennyhunter_cumulative_history.json`
- `reports/experiments/gap10_vol2_4_cooldown/pennyhunter_memory.db`
- `reports/experiments/gap10_vol2_4_cooldown/bouncehunter_agent.db`
- `reports/experiments/gap10_vol2_4_cooldown/phase2_validation_report.json`
- `reports/experiments/gap10_vol2_4_cooldown/phase2_validation_report.md`
- `reports/experiments/gap10_vol2_4_cooldown/EXPERIMENT_SUMMARY.md`

## Scan-Only Scaffold Status

- Git status before scaffold: `clean`
- Trader run: `not run`
- `execute_signal`: `not called`
- Baseline files touched: `NONE`
- Initial expectation: `TLRY` should appear once the live scan volume floor is reduced to `>=2.4x`, while `COMP`, `INTR`, and `CGC` should remain excluded on gap.

## Scan-Only Comparison

- Comparison mode: read-only only, no trader run, no `execute_signal`, baseline changed `NONE`
- Reference config `gap10_vol2_5_cooldown`: signals before cooldown `SPCE`; eligible after cooldown `none`; cooldown decision `skip_repeat_without_alternative`; `TLRY` absent; `COMP`, `INTR`, and `CGC` absent; paper session eligible `false`
- Fresh scaffold config `gap10_vol2_4_cooldown`: signals before cooldown `SPCE`, `TLRY`; eligible after cooldown `SPCE`, `TLRY`; cooldown decisions `none`, because the new fenced history is empty and has no prior closed ticker to block; paper session eligible `true`
- Matched-state control using the existing cooldown fenced history for both configs: `gap10_vol2_4_cooldown` produces signals before cooldown `SPCE`, `TLRY`; eligible after cooldown `TLRY`; cooldown decision `prefer_alternate`; paper session eligible `true`
- `TLRY` result: appears at `>=2.4x` and becomes the non-blocked alternate once the same closed-`SPCE` cooldown state is applied
- Noise check: `COMP`, `INTR`, and `CGC` do not reappear in either the fresh scaffold comparison or the matched-state control
- Interpretation: the new scaffold is clean, and the only material behavior change from lowering the live volume floor to `>=2.4x` is that `TLRY` becomes available as the alternate under cooldown

## First Isolated Paper Session

- Signals found before cooldown: `SPCE`, `TLRY`
- Eligible signals after cooldown: `SPCE`, `TLRY`
- Cooldown decisions: `none`
- Why cooldown did not trigger: no prior closed trade exists in this fresh fenced experiment
- Trade opened: `SPCE`
- SPCE details: `32` shares at `$3.07`, signal date `2026-04-06`, status `active`
- Skipped candidate: `TLRY`
- Active trades: `1`
- Completed trades: `0`
- Wins: `0`
- Losses: `0`
- Win rate: `0.0%`
- Net closed P&L: `$0.00`
- Near misses: `11`
- Ejected tickers: `none`
- Baseline changed: `NONE`
- Status: active paper validation, cooldown not exercised yet

## Status

- Git status before comparison: `clean`
- Git status after first paper session: only fenced experiment artifacts are untracked until committed
- This was the first fenced paper session for `gap10_vol2_4_cooldown`.
- Do not merge this branch into baseline.