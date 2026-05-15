# PennyHunter Experiment Postmortem

## Scope

- Reviewed rejected experiment summaries only:
  - `gap9_vol2`
  - `gap10_vol2_5`
  - `gap10_vol2_5_cooldown`
  - `gap10_vol2_4_cooldown`
- This is a read-only synthesis. No baseline files, trader runs, or memory DB changes were used.

## Rejected Branches

- `gap9_vol2`: rejected because loosening thresholds increased setup availability but degraded trade quality; final sample finished `2W / 4L`, `33.3%` win rate.
- `gap10_vol2_5`: rejected because tighter thresholds removed weaker names but still failed the early gate at `1W / 2L`, `33.3%` win rate.
- `gap10_vol2_5_cooldown`: not a merge candidate because it proved cooldown mechanics only; it remained structurally starved at `>=2.5x` and did not produce enough alternate-selection data to validate trade quality.
- `gap10_vol2_4_cooldown`: rejected because cooldown worked mechanically, but the live trade sample still failed on trade quality at `0W / 2L`; even a target on the next trade would only yield `1W / 2L = 33.3%`, so the branch can no longer clear the early gate.

## Why Each Failed

- `gap9_vol2` failed because lower gap and volume thresholds admitted more marginal names and more weak entries.
- `gap10_vol2_5` failed because threshold tightening alone did not solve repeat-entry or entry-quality problems; the branch still recycled similar setups without enough confirmation.
- `gap10_vol2_5_cooldown` failed as a production candidate because it became too sparse at `>=2.5x`; cooldown itself worked, but the branch mostly produced `SPCE` only and often no trade after blocking repeats.
- `gap10_vol2_4_cooldown` failed because lowering volume to `>=2.4x` successfully admitted `TLRY` as an alternate, but the added alternate did not improve outcomes; both completed trades still stopped out.

## What Worked Structurally

- Fenced-path experiment discipline worked: isolated outputs, clean baseline audits, and no baseline contamination.
- Memory outcome recording was repaired and made idempotent, removing replay-driven distortion from experiment interpretation.
- Tighter gap filtering did remove `gap9_vol2` noise such as `COMP`, `INTR`, and `CGC` from live candidate lists.
- Cooldown worked mechanically once implemented correctly:
  - it blocked repeat `SPCE` when no alternate existed
  - it preferred `TLRY` over repeat `SPCE` when both were present under the `>=2.4x` variant
- The structural lesson is clear: ticker cooldown solves repeat-exposure control, but it does not solve entry quality by itself.

## Repeated Failure Patterns

- Most completed losses exited at `STOP`, clustered tightly around the planned risk unit rather than showing random oversized slippage.
- Relaxing thresholds increased candidate count, but did not improve signal quality enough to lift win rate.
- Tightening thresholds reduced noise, but still left trades entering too early or without enough confirmation.
- Cooldown prevented one repeat-entry defect, but the alternate admitted by the relaxed branch was still low quality.
- The summaries repeatedly point to acceptable structural filtering but weak trade timing after a candidate is admitted.

## Loss Clustering

- Losses cluster around both `SPCE` and `TLRY`, with `SPCE` showing up repeatedly across the tighter branches and `TLRY` failing once admitted.
- `gap9_vol2` also lost on `INTR` and `CGC`, which reinforces that broader threshold loosening exposed lower-quality tickers as well.
- Across the tighter/cooldown branches, `SPCE` is the dominant recurring ticker and `TLRY` is the key alternate that still failed once traded.

## Diagnostic Read

- Entry timing: likely a primary problem. Multiple branches found candidates that were structurally eligible but still stopped out quickly.
- Gap threshold: not the next lever. Moving from `9%` to `10%` removed noise, but the tighter variants still lost.
- Volume threshold: not the next lever. Lowering from `2.5x` to `2.4x` changed availability, not quality.
- Lack of confirmation: strongly implicated. The system appears to enter on historically qualified setups without requiring enough additional proof that momentum actually held.
- Stale signal dates: implicated, especially for `TLRY`. The branch admitted a setup dated `2026-01-09`, which is materially older than the surrounding `SPCE` examples and should be treated with more skepticism.
- Ticker quality: also implicated. `SPCE` repeats frequently and remains volatile enough to generate scans and repeated stop-outs; `TLRY` was admitted as the mechanically correct alternate, but still did not demonstrate trade quality.

## Recommended Next Experiment

- Do not test another threshold-loosening branch next.
- Keep the cooldown lesson, but move the next experiment to an entry-confirmation filter layered on top of the tighter `10-15%` gap logic.
- The strongest next structural direction to evaluate is a pre-execution confirmation gate that rejects technically eligible but weakly confirmed entries.

## Recommended Filters To Evaluate

- Require VWAP reclaim confirmation before entry.
- Require a green confirmation bar after the gap rather than entering immediately on eligibility.
- Require current price above opening range high before execution.
- Reject stale historical signal dates beyond a configured age window.
- Block immediate entry if the historical path already implies the stop or target would have been hit before the planned execution point.

## Recommendation

- Next research should focus on entry-quality filters, not additional gap or volume loosening.
- The best next experiment to design is a `10-15%` gap branch with cooldown retained and a new confirmation layer before trade execution.
- Do not create that config yet; the next step should be to specify and audit the confirmation rule set first.