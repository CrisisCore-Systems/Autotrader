# Next PennyHunter Experiment Design

## Proposed Experiment

- Proposed name: `gap10_vol2_4_cooldown_confirmed`
- Base branch to extend: `gap10_vol2_4_cooldown`
- Keep unchanged:
  - gap range `10-15%`
  - live scan volume threshold `>=2.4x`
  - ticker cooldown `enabled`
  - one-position cap unchanged
- New objective: keep the mechanically valid cooldown behavior, but add a pre-execution confirmation layer that rejects stale or weakly confirmed entries before `execute_signal`.

## Current Signal Surface

The current `scan_for_signals()` / `execute_signal()` path already exposes enough data for a first confirmation experiment without adding a new data provider.

Current signal objects include:

- `ticker`
- `signal_type`
- `price` (current bar close used as entry proxy)
- `gap_pct`
- `vol_spike`
- `score`
- `components`
- `date`
- `hist`

Current `hist` contents come from `yf.Ticker(...).history(period='90d')`, which means the runner already has daily OHLCV bars for each candidate across the lookback window.

Implication:

- Daily-bar confirmation logic is implementable now.
- Intraday confirmation logic is not fully implementable in the current paper runner without new intraday bar wiring.

## Implementable Confirmation Checks

Implementable now with existing signal data:

- Green confirmation bar after gap.
  - Can be derived from daily OHLC in `hist`.
  - Example rule: require a post-gap bar with `Close > Open` and optionally `Close > prior Close`.
- Reject stale signal dates older than a configured limit.
  - Can be derived from `signal['date']` relative to current evaluation date.
- Reject setups where historical path already hit stop before valid entry confirmation.
  - Can be evaluated by replaying bars after `signal['date']` inside `hist` until confirmation occurs.

Not fully implementable in the current paper runner without additional intraday bar wiring:

- VWAP reclaim confirmation.
  - The scorer currently hardcodes `vwap_reclaim=True`, but the paper runner does not attach real intraday VWAP state to the signal.
  - The repo has a VWAP engine, but that engine is not currently fed by the signal object used in this experiment path.
- Current or historical entry above opening range high.
  - Opening range high is intraday structure and is not present in the current daily OHLCV bars.

## Smallest First Confirmation Gate

Recommended smallest first gate:

- `stale_signal_date` as a hard reject

Reasoning:

- It is fully implementable with current signal fields.
- It directly addresses a failure pattern already visible in the rejected summaries.
- It is the lowest-risk structural change because it does not require intraday logic or broad rewiring of the execution path.
- It can be combined cleanly with cooldown and the current one-position cap.

Recommended first threshold to evaluate:

- `max_signal_age_days: 10`

Why `10` days first:

- It is tight enough to reject clearly stale setups.
- It is loose enough to test whether the branch is surviving on recent candidates or on long-delayed historical artifacts.
- It avoids immediately hardcoding an ultra-tight value like `1-3` days before the branch is audited.

## How This Would Have Affected SPCE And TLRY

What is directly visible from existing experiment artifacts:

- `TLRY` losses were taken from a signal dated `2026-01-09`.
- `SPCE` losses in the tighter branches were taken from signal dates such as `2026-04-06` and `2026-03-31`.

Implications:

- A `max_signal_age_days` rule would have rejected the `TLRY` loss immediately.
- A sufficiently tight age rule would also have rejected the observed `SPCE` entries, which is useful information rather than a drawback because it tests whether the current branch is relying on stale historical setups at all.
- From the summaries alone, green-bar confirmation and stop-before-confirmation cannot be proven or disproven for those specific losses without replaying the stored daily bars, but the current signal object already contains the `hist` data needed to evaluate them in code.

Practical interpretation:

- The stale-date gate is the only candidate rule whose likely impact is already visible from existing artifacts without additional replay.
- It is therefore the cleanest first confirmation gate to test before adding more complex confirmation logic.

## Recommended Confirmation Layer Design

Design the confirmation layer as two classes of checks:

- Hard rejects
  - stale signal date
  - stop-hit-before-confirmation
- Positive confirmations
  - green confirmation bar
  - future VWAP reclaim
  - future opening-range-high reclaim

Execution rule for the first confirmed experiment:

- reject immediately if any hard reject triggers
- otherwise require at least one enabled positive confirmation rule to pass

For the first version of `gap10_vol2_4_cooldown_confirmed`, recommend:

- enable `stale_signal_date`
- enable `green_confirmation_bar`
- enable `stop_hit_before_confirmation`
- keep `vwap_reclaim` disabled until intraday data is wired into the paper runner
- keep `opening_range_high` disabled until intraday data is wired into the paper runner

## Proposed Config Shape

Do not create this config yet. This is the proposed YAML shape only.

```yaml
experiments:
  ticker_cooldown:
    enabled: true
    mode: next_session_prefer_alternate

  entry_confirmation:
    enabled: true
    require_any_positive_rule: 1

    stale_signal_date:
      enabled: true
      max_age_days: 10

    green_confirmation_bar:
      enabled: true
      lookahead_bars: 3
      require_close_above_open: true
      require_close_above_signal_close: true

    stop_hit_before_confirmation:
      enabled: true
      source_rule: green_confirmation_bar
      stop_buffer_pct: 0.0

    vwap_reclaim:
      enabled: false

    opening_range_high:
      enabled: false
```

Runner behavior implied by this shape:

- The scan still finds candidates exactly as `gap10_vol2_4_cooldown` does now.
- Cooldown still runs after scanning.
- Before `execute_signal`, the confirmation layer evaluates the surviving candidate.
- If the candidate is stale, reject it.
- If the candidate would have hit stop before confirmation, reject it.
- If no enabled positive confirmation rule passes, reject it.

## Proposed Fenced Output Paths

Do not create these yet. These are the proposed fenced paths only.

- `reports/experiments/gap10_vol2_4_cooldown_confirmed/pennyhunter_paper_trades.json`
- `reports/experiments/gap10_vol2_4_cooldown_confirmed/pennyhunter_cumulative_history.json`
- `reports/experiments/gap10_vol2_4_cooldown_confirmed/pennyhunter_memory.db`
- `reports/experiments/gap10_vol2_4_cooldown_confirmed/bouncehunter_agent.db`
- `reports/experiments/gap10_vol2_4_cooldown_confirmed/phase2_validation_report.json`
- `reports/experiments/gap10_vol2_4_cooldown_confirmed/phase2_validation_report.md`
- `reports/experiments/gap10_vol2_4_cooldown_confirmed/EXPERIMENT_SUMMARY.md`

## Recommendation

- The next structural experiment should be `gap10_vol2_4_cooldown_confirmed`.
- The smallest first confirmation gate should be `stale_signal_date`, because it is directly supported by existing signal fields and directly addresses a failure already visible in the rejected artifacts.
- The first confirmed-entry branch should also prepare to add `green_confirmation_bar` and `stop_hit_before_confirmation`, because those are the strongest additional checks implementable from the already attached daily `hist` data.
- Do not test another threshold change first.
- Do not wire intraday VWAP or opening-range-high logic into this next branch until the daily-bar confirmation experiment is specified and audited.