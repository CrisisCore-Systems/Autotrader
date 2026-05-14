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

## Candidate Scarcity / No-Trade State

- Consecutive scan-only blocks: `4`
- Blocked ticker: `SPCE`
- Current alternate eligible ticker: `none`
- Closest visible alternate candidate: `TLRY`, with gap `10.08%` in range but volume `2.40x` below the `>=2.5x` rule
- Other near-eligibility examples: `INTR` at `9.42%` gap / `2.16x` volume, `COMP` at `9.88%` gap / `2.10x` volume, `CGC` at `9.42%` gap / `3.54x` volume
- Why `TLRY` is not currently eligible: recent diagnostics show `volume_outside_sweet_spot`; its latest visible setup clears the gap filter but does not clear the `>=2.5x` volume threshold
- Root cause classification: threshold strictness plus ticker-universe scarcity
- Not the root cause: signal ordering, because no alternate fully eligible ticker is present to reorder toward
- Not the root cause: cooldown behavior, because cooldown is correctly suppressing repeat `SPCE` exposure after the closed loss
- Paper session currently eligible: `no`
- What must change before another fenced paper session is eligible: at least one ticker other than the blocked `SPCE` must clear both the `10-15%` gap filter and the `>=2.5x` volume rule during a future scan

## Threshold Sensitivity Audit

- Audit mode: read-only scan-only, no trader run, no `execute_signal`, no paper-trade writes, baseline changed `NONE`
- Variant tested: `current`, gap `10-15`, volume `>=2.5x`
- Variant tested: `candidate`, gap `10-15`, volume `>=2.4x`
- Variant tested: `candidate`, gap `10-15`, volume `>=2.25x`
- Variant tested: `candidate`, gap `10-15`, volume `>=2.0x`
- Correction: the earlier read-only sweep changed the wrong config key; the verified live scan threshold is `signals.runner_vwap.paper_scan.volume_min_mult`
- Verified result at `>=2.5x`: signals before cooldown `SPCE` only, eligible after cooldown `none`, blocked ticker `SPCE`, paper session allowed `false`
- Verified result at `>=2.4x`: signals before cooldown `SPCE`, `TLRY`; eligible after cooldown `TLRY`; cooldown decision `prefer_alternate`
- Verified result at `>=2.25x`: same as `>=2.4x`, with `TLRY` still admitted as the alternate
- Verified result at `>=2.0x`: same as `>=2.4x`, with `TLRY` still the only alternate admitted
- Current signal details at baseline `>=2.5x`: `SPCE`, gap `11.52%`, volume `8.81x`, score `7.0`
- Alternate admitted once volume relaxes to `>=2.4x`: `TLRY`, gap `10.08%`, volume `2.40x`, score `5.0`
- Reintroduced gap9_vol2-style noise at any tested threshold: `none visible`, because `COMP`, `INTR`, and `CGC` still did not enter the live signal list
- Decision: a relaxed-volume follow-up is technically viable at `>=2.4x`, but it would be admitting a marginal `TLRY` setup rather than a higher-score alternate

## Signal Scarcity Root Cause

- Audit mode: read-only only, git clean before/after, baseline changed `NONE`
- Effective scan universe is larger than the visible active list: `26` raw tickers merged from the active list plus config ticker sources, with `16` passing universe screening
- Why only `SPCE` surfaces at the current `>=2.5x` rule: it is the only screened ticker whose current historical setup clears both the `10-15%` gap filter and the `>=2.5x` volume filter
- Why `TLRY` does not surface at the current rule: its closest qualifying setup is `2026-01-09`, gap `10.08%`, volume `2.40x`; it misses only the current volume floor
- Why `COMP` does not surface: closest setup is gap `9.88%`, volume `2.10x`; it misses the gap floor before volume can matter
- Why `INTR` does not surface: closest setup is gap `9.42%`, volume `2.16x`; it misses the gap floor
- Why `CGC` does not surface: closest setup is gap `9.42%`, volume `3.54x`; volume is strong, but the setup still fails on gap
- Other screened names mostly fail on gap or have no visible 90-day candidate in the target window: `EVGO`, `ACHR`, `NIO`, `BBAI`, `NVAX`, and `OGI` fail gap; `SENS`, `CLOV`, `AMC`, and `RSKD` showed no visible `10-15%` gap candidate in the inspected window; `ADT` is blocklisted
- Ten raw-universe names never reach scan logic because they are screened out earlier, predominantly on exchange eligibility
- Root cause classification: current no-trade state is caused by entry-threshold scarcity inside the merged universe, not by cooldown behavior, signal ordering, historical processed-state suppression, or baseline contamination
- Practical next move: if the goal is to keep the stricter quality bar, remain scan-only and wait for new market data; if the goal is to force an alternate-selection trial, `>=2.4x` is the smallest verified relaxation and it currently selects `TLRY`

## Interpretation

The first isolated paper session established the initial fenced state with an active `SPCE` trade.
The post-fix proof run confirmed the repaired live cooldown path behaves correctly when that trade closes and no alternate ticker is available.
The cooldown mechanism is now behaving correctly.
There is currently no non-blocked eligible ticker.
No fenced paper session is eligible.
The only available signal was repeat `SPCE`.
Cooldown correctly suppressed repeat exposure again.
Continue scan-only checks until a non-blocked eligible ticker appears.
The current starvation state is best explained by strict entry thresholds on a sparse ticker universe rather than by cooldown or ordering defects.
The corrected threshold audit shows that lowering the live volume filter to `>=2.4x` would admit `TLRY` as an alternate, while `COMP`, `INTR`, and `CGC` remain excluded on gap.
Trade-quality validation is still pending because the experiment has only one completed trade and no alternate-selection case has occurred yet.

## Status

The trader has now completed a live fenced cooldown proof run for this experiment.
Do not merge this branch into baseline.