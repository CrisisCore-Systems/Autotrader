# Research Log

## 2026-05-19 - AUD/USD v1 Conclusion

### Scope

- Strategy family: tick-native microstructure v1
- Symbol: `AUD/USD`
- Surviving pocket before closure: long-only `12-14` UTC ignition window

### Evidence

- `12-14` long-only calibrated ridge: fitness `-0.7293`, `2` fills, localized but still subcritical.
- `12-16` long-only extension: activity increased, expectancy degraded.
- Full-day unconstrained long-only tick probe: fitness `-1.2968`, baseline net return `-0.9208`, stress net return `-0.1880`, `4` fills.
- Best full-day candidate remained on the same local surface: `fast_ema_len=10`, `slow_ema_len=23`, `imbalance_cutoff=0.82`, `imbalance_velocity_lookback=20`, `imbalance_velocity_threshold=0.14`.

### Interpretation

Removing the session boundary increased participation but materially worsened economics.
There is no hidden continuous intraday AUD/USD long edge under the current tick-level admission and exit physics.
The only observable edge is a localized `12-14` UTC ignition pocket, and that pocket remains non-deployable under v1.

### Decision

- Freeze `AUD/USD` v1 as real but subcritical.
- Do not treat `--bar-frequency` as a continuation of the current model.
- If bar-level research is pursued, treat it as a new model phase with explicit changes to admission behavior, objectives, and validation criteria.

### Next Defensible Branches

1. Move research effort to a different asset or regime where the current architecture shows stronger transfer.
2. Run one final narrow spread-relaxation audit only if the goal is to falsify admission sensitivity without new code.
3. Start a separate bar/meso-timescale model v2 only with a new hypothesis and new validation plan.

### Artifacts

- `reports/eval_audusd_long.json`
- `reports/eval_audusd_long_1216.json`
- `reports/eval_audusd_long_calibration_winner.json`
- `reports/raw_audusd_long_full_day_probe.json`
- `/memories/repo/audusd_us_open_ignition_asymmetry_map.md`
- `/memories/repo/audusd_us_open_window_long_extension.md`
- `/memories/repo/audusd_us_open_ignition_long_micro_calibration.md`
- `/memories/repo/audusd_long_full_day_tick_probe.md`

## 2026-05-19 - BTC/USD Phase 1 Transfer Falsification

### Scope

- Strategy family: tick-native microstructure v1
- Symbol: `BTC/USD` on Dukascopy CFD feed
- Window: `12-14` UTC US open ignition slice
- Directional checks: `long`, `short`, and `both`

### Evidence

- All three directional passes were rejected.
- Best normalized result: `best_fitness=-50.0`, `matched_orders=0`, `baseline_net_return=0.0`, `stress_net_return=0.0`.
- Aggregate telemetry: `dominant_kill_gate=spread`, `spread_rejection_pct=50.0741`, `imbalance_rejection_pct=49.3772`.
- Side detail: the short-side report still identified spread as the dominant local gate, while the long-side path produced no viable execution activity.

### Interpretation

The first-pass crypto transfer thesis was falsified.
Compressed nominal crypto pricing did not bypass the existing admission chokehold.
Under the current relative spread-admission logic, the pipeline remains overbound and shuts off participation before the momentum signal can translate into fills.

### Decision

- Freeze `BTC/USD` v1 as a structural rejection under the current admission physics.
- Treat this as evidence that the failure mode is not specific to one FX pair.
- Do not pursue shorter bars or wider temporal freedom as a continuation of the same model without changing admission logic.

### Next Defensible Branches

1. Replace the current relative spread gate with an explicit absolute spread or fee-aware admission model in a new research phase.
2. Introduce bar-frequency work only as part of a new model specification, not as a flag-level extension of v1.
3. Keep raw tick v1 archived as a completed boundary-mapping phase rather than continuing the same parameter search.

### Artifacts

- `reports/eval_btcusd_long.json`
- `reports/eval_btcusd_short.json`
- `reports/eval_btcusd_both.json`
- `/memories/repo/btcusd_us_open_ignition_asymmetry_map.md`