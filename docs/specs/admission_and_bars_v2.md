# Admission And Bars V2

## Purpose

This document defines Phase 2 of the microstructure research stack:

- replace relative spread z-score admission with deterministic absolute admission physics
- add a non-lookahead bar resampling layer for meso-timescale research
- keep Phase 1 raw tick results archived as boundary-mapping evidence rather than extending the same model family

The design goal is not to make v1 look better. The goal is to define a new model contract that can be falsified cleanly.

## Why Phase 2 Exists

Phase 1 established two boundary conditions:

- `AUD/USD` produced only a localized long-only `12-14` UTC pocket that remained subcritical and degraded when the time window expanded.
- `BTC/USD` produced zero fills across `long`, `short`, and `both`, with spread as the dominant kill gate.

The shared lesson is that the current relative spread-admission logic is overbinding across assets and time regimes. Adding minute bars without changing admission physics would be infrastructure drift.

## Scope

Phase 2 covers two architectural changes:

1. absolute spread admission
2. bar-based feature construction on `1m`, `5m`, and `15m` windows

Phase 2 does not assume that either change improves results. It only creates a coherent model surface that can be tested without inheriting the main v1 failure mode.

## Non-Goals

- do not preserve backward-identical v1 behavior when Phase 2 flags are enabled
- do not silently mix tick-mode and bar-mode features in the same evaluation path
- do not infer economic viability from fill count alone
- do not introduce any bar construction that reads future ticks or future bar closes

## Model Statement

Phase 2 introduces a meso-timescale research mode with explicit economic admission.

At a high level:

- raw ticks remain the source of truth
- bars are derived from ticks in a causally safe way
- admission decisions are based on absolute friction thresholds rather than rolling relative rarity
- execution remains quote-aware, but feature generation can operate on bars

## Admission Physics

### Problem With V1

Phase 1 used a relative spread filter that treated locally unusual spread states as execution vetoes. That couples admission to the recent distribution of spreads instead of to an explicit cost budget.

This fails in two ways:

- compressed nominal spreads do not guarantee that the gate opens when the distribution itself is tight and unstable
- temporary micro-liquidity expansions during valid momentum events can be classified as statistical anomalies and blocked even when the absolute transaction cost is acceptable

### V2 Principle

Admission should be governed by direct transaction friction, not by spread rarity.

For any quote at time `t`:

$$
\text{mid}_t = \frac{\text{bid}_t + \text{ask}_t}{2}
$$

$$
\text{spread\_bps}_t = \frac{\text{ask}_t - \text{bid}_t}{\text{mid}_t} \times 10{,}000
$$

An entry signal passes the spread gate if and only if:

$$
\text{spread\_bps}_t \le \text{max\_spread\_bps}
$$

### Fee-Aware Extension

Phase 2 should allow optional fee-aware admission so the gate can reflect all immediate one-way or round-trip friction components.

Example:

$$
\text{effective\_friction\_bps} = \text{spread\_bps}_t + \text{fee\_bps} + \text{slippage\_budget\_bps}
$$

Optional stricter rule:

$$
\text{effective\_friction\_bps} \le \text{max\_friction\_bps}
$$

The minimum viable Phase 2 implementation only requires `max_spread_bps`. Fee-aware friction can be added as a second step if the CLI is designed for it from the start.

## CLI Contract

Phase 2 adds explicit admission flags rather than overloading the current spread threshold semantics.

### New Flags

```bash
--spread-mode absolute
--max-spread-bps 0.5
--variable-fee-tier 0.0005
--bar-frequency 1m
```

### Expected Semantics

- `--spread-mode`
  - allowed values: `relative`, `absolute`
  - default in v1-compatible paths remains `relative`
  - Phase 2 research runs should explicitly set `absolute`
- `--max-spread-bps`
  - hard admission ceiling in basis points
  - required when `--spread-mode absolute`
- `--variable-fee-tier`
  - optional transaction fee parameter for fee-aware variants
  - stored in outputs even if not yet used in the first implementation slice
- `--bar-frequency`
  - allowed values: `1m`, `5m`, `15m`
  - omitted means raw tick mode

### Compatibility Rule

If `--bar-frequency` is set, the pipeline must switch into bar-mode feature generation. It must not continue computing the current tick-native rolling state while only changing evaluation cadence.

## Data Model

### Source Of Truth

Raw tick data remains canonical. Bars are derived artifacts.

Each bar is constructed only from ticks whose timestamps fall within that bar interval.

### Bar Schema

Each output bar should contain at minimum:

- `bar_start_ts`
- `bar_end_ts`
- `open_bid`
- `open_ask`
- `high_bid`
- `high_ask`
- `low_bid`
- `low_ask`
- `close_bid`
- `close_ask`
- `mid_open`
- `mid_high`
- `mid_low`
- `mid_close`
- `tick_count`
- `volume_proxy` or tick activity proxy if true size is unavailable
- `ofi_bar`
- `spread_bps_open`
- `spread_bps_close`
- `spread_bps_mean`
- `spread_bps_max`

The exact schema can expand later, but these fields are sufficient for Phase 2 experimentation.

## Bar Construction

### Core Rule

Bars must be right-labeled and only become visible after the interval closes.

For a `1m` bar covering `[12:00:00, 12:00:59.999...]`:

- the bar is built from ticks inside that interval only
- features derived from that bar can be consumed no earlier than the first decision point after `12:01:00`

This avoids lookahead leakage from partially completed intervals.

### Order Flow Imbalance Aggregation

Phase 2 replaces tick-level rolling imbalance velocity with bar-level imbalance accumulation.

For bar `j`:

$$
\text{OFI}_{j} = \sum_{k \in j} \Delta B_k - \sum_{k \in j} \Delta A_k
$$

Where:

- `Delta B_k` is the bid-side size or quote-improvement contribution at tick `k`
- `Delta A_k` is the ask-side size or quote-improvement contribution at tick `k`

If only quote-based proxies are available, Phase 2 should document the exact approximation used and keep it fixed across experiments.

### Derived Bar Features

The first implementation slice should support:

- bar-level OFI
- OFI rolling average
- OFI velocity across bars
- bar EMA fast
- bar EMA slow
- bar trend separation in bps
- bar spread statistics
- optional realized range or ATR-style bar volatility

### Missing Tick Handling

If a bar interval has no ticks:

- do not fabricate price movement
- mark the interval explicitly as empty or carry forward only the fields required by downstream code
- ensure feature logic distinguishes between a flat bar and an empty bar

## No-Lookahead Contract

Phase 2 is only valid if every bar-based feature obeys causal availability.

### Hard Rules

1. a bar cannot be used until its close time has passed
2. rolling indicators at bar `j` may only use bars `<= j`
3. trade execution timestamps cannot be snapped backward to the bar open after the bar close is known
4. labels, exits, and diagnostics must be computed from post-entry information only

### Execution Timing Rule

If a signal is generated from closed bar `j`, the earliest eligible execution point is the first tick or synthetic decision point after `bar_end_j`.

This preserves the causal order:

1. bar closes
2. features update
3. signal decision occurs
4. execution is attempted on the next available quote

## Pipeline Changes

### `pipeline.py`

Add a bar-construction layer that can:

- ingest tick quotes in time order
- aggregate them into `1m`, `5m`, or `15m` bars
- emit finalized bars only after close
- compute Phase 2 bar features from finalized bars

The recommended architecture is:

- `TickToBarAggregator`
- `BarFeatureState`
- `generate_signal_from_bar()`

This should remain separate from the current tick-native path to avoid partial behavior mixing.

### `train.py`

Training must accept new parameters and persist them into raw winner outputs:

- `spread_mode`
- `max_spread_bps`
- `variable_fee_tier`
- `bar_frequency`

Training must also report Phase 2 diagnostics separately from v1 diagnostics so the experiments are comparable but not conflated.

### `validate.py`

Validation must forward the new flags and expose them in normalized reports.

Normalized reports should include:

- `spread_mode`
- `max_spread_bps`
- `bar_frequency`
- bar-mode versus tick-mode identifier
- admission rejection percentages under the new physics

## Engine Interaction

Phase 2 does not require a fully bar-native execution engine.

The preferred design is:

- features may be bar-derived
- execution remains quote-aware against the next eligible quote after the signal

This avoids turning the backtest into a naive candle-close fill model.

## Research Modes

Phase 2 creates three distinct modes that must remain explicit:

1. `tick-relative-v1`
2. `tick-absolute-v2`
3. `bar-absolute-v2`

The system should never infer these modes implicitly from partial flag combinations. Outputs should label the mode directly.

## Recommended Implementation Order

### Slice 1: Absolute Admission On Raw Ticks

Goal:

- isolate whether the relative spread gate was the dominant failure mode

Changes:

- add `spread_mode`
- add `max_spread_bps`
- thread parameters through trainer and validator
- expose new diagnostics

Validation target:

- rerun the smallest discriminating Phase 1 surfaces with absolute admission before adding bars

### Slice 2: Bar Aggregation Without New Strategy Logic

Goal:

- prove that bars are built causally and consumed without lookahead

Changes:

- add `TickToBarAggregator`
- add finalized bar emission tests
- add bar schema persistence or introspection utilities if needed

Validation target:

- unit tests for bar boundaries, empty intervals, and no-lookahead execution timing

### Slice 3: Bar-Based Feature Path

Goal:

- move OFI, EMA, and trend state into bar space

Changes:

- add `BarFeatureState`
- add bar-specific signal generation
- keep outputs directly comparable with prior validation artifacts

Validation target:

- focused research runs on `1m`, then `5m`, before `15m`

## Testing Requirements

Phase 2 is not valid without explicit tests for causality and gate semantics.

Minimum required tests:

- absolute spread gate admits when `spread_bps <= max_spread_bps`
- absolute spread gate rejects when `spread_bps > max_spread_bps`
- CLI rejects `--spread-mode absolute` without `--max-spread-bps`
- bar aggregator closes intervals correctly on boundary timestamps
- bar aggregator does not leak future ticks into earlier bars
- signal generated from bar `j` cannot execute before `bar_end_j`
- empty bar handling does not fabricate volume, OFI, or price range

## Output And Artifact Requirements

Every Phase 2 artifact should record:

- model mode
- spread mode
- max spread bps
- fee tier if set
- bar frequency if set
- feature family identifier
- causal execution rule used

This is required to avoid blending v1 and v2 findings in later analysis.

## Open Questions

- should `variable_fee_tier` represent one-way fees or round-trip fees?
- should slippage budget remain implicit in execution or become an explicit admission parameter?
- should empty bars be emitted as explicit records or skipped from the feature stream?
- should OFI in bar space use quote-size deltas only, or should it support trade prints when available?

These questions do not block Slice 1. They matter most once the bar path is implemented.

## Decision Standard

Phase 2 should only continue if each slice produces a cleaner and more falsifiable model surface than Phase 1.

Success for this specification does not mean positive returns. Success means:

- explicit admission physics
- causal bar construction
- reproducible mode labeling
- no ambiguity about what changed between research phases

## Initial Recommendation

Begin with `tick-absolute-v2` before implementing `bar-absolute-v2`.

That is the cheapest discriminating path because it tests the admission-physics thesis directly while holding the rest of the execution stack fixed.