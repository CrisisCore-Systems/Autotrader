# gap10_vol2_5 Experiment Summary

- Experiment name: `gap10_vol2_5`
- Base config: `configs/pennyhunter.yaml`
- Experiment config: `configs/pennyhunter_experiment_gap10_vol2_5.yaml`
- Goal: test a tighter post-rejection variant after `gap9_vol2`.
- Scan thresholds: `10-15%` gap, `>=2.5x` volume
- Concurrency cap: unchanged from baseline (`1` position)
- Mode: scan-only comparison completed, no paper session run yet
- Baseline contamination: `NONE`

## Scan-Only Comparison

### baseline

- Signal count: `1`
- Candidate tickers: `SPCE`
- Candidate details: `SPCE 2026-04-06 | gap 10.16% | vol 6.25x | score 7.0`
- Near misses: `12`

### gap9_vol2

- Signal count: `5`
- Candidate tickers: `SPCE, COMP, INTR, TLRY, CGC`
- Candidate details:
  - `SPCE 2026-04-06 | gap 10.16% | vol 6.25x | score 7.0`
  - `COMP 2026-04-08 | gap 9.88% | vol 2.10x | score 5.0`
  - `INTR 2026-04-08 | gap 9.42% | vol 2.16x | score 5.0`
  - `TLRY 2026-01-09 | gap 10.08% | vol 2.51x | score 5.5`
  - `CGC 2026-04-23 | gap 9.42% | vol 3.54x | score 6.5`
- Near misses: `8`

### gap10_vol2_5

- Signal count: `2`
- Candidate tickers: `SPCE, TLRY`
- Candidate details:
  - `SPCE 2026-04-06 | gap 10.16% | vol 6.25x | score 7.0`
  - `TLRY 2026-01-09 | gap 10.08% | vol 2.51x | score 5.5`
- Near misses: `11`

## Initial Read

`gap10_vol2_5` is cleaner than `gap9_vol2` on the scan-only gate.
It reduced candidate count from `5` to `2` and removed the weaker marginal setups (`COMP`, `INTR`, `CGC`) while preserving the two cleanest candidates from the looser experiment (`SPCE`, `TLRY`).

Compared with baseline, the new variant is still looser because it adds `TLRY` on top of the baseline `SPCE` candidate, but it is materially tighter than the rejected `gap9_vol2` branch.

## Decision

Scan-only result is clean enough to create the experiment and allow a later isolated paper session.
No paper session has been run yet.

## Next Step

If resumed, run the first paper/simulated session only against the fenced `gap10_vol2_5` output paths and keep baseline isolated.