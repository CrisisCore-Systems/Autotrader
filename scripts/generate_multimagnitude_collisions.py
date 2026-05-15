"""
Multi-magnitude collision generator for gate_threshold sweep validation.

Injects three simultaneous BTC/ETH signal pairs at distinct timestamps, each
carrying a different mean_correlation value that sits in a different gate-threshold
band.  corr_regime is intentionally set to "neutral_correlation" so the only
gating trigger is the numerical mean_correlation >= correlation_gating_threshold
comparison — this causes gated_signals_count to step down as the threshold rises.

Expected step-down for our 4-threshold grid [0.70, 0.75, 0.80, 0.85]:
  threshold=0.70 → 3 gated  (A=0.72 ≥ 0.70, B=0.77 ≥ 0.70, C=0.82 ≥ 0.70)
  threshold=0.75 → 2 gated  (B=0.77 ≥ 0.75, C=0.82 ≥ 0.75)
  threshold=0.80 → 1 gated  (C=0.82 ≥ 0.80)
  threshold=0.85 → 0 gated  (none ≥ 0.85)

Usage:
    python scripts/generate_multimagnitude_collisions.py
    python scripts/generate_multimagnitude_collisions.py --features-dir data/crypto/features --output-dir reports/crypto/multimag_collision_data
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Collision spec: (mean_correlation, description)
# corr_regime is always "neutral_correlation" so gating fires ONLY via
# the numerical threshold comparison, giving threshold-dependent step-down.
# ---------------------------------------------------------------------------
COLLISION_SPECS = [
    (0.72, "band_A"),   # gated only when threshold <= 0.72  → threshold=0.70
    (0.77, "band_B"),   # gated when threshold <= 0.77       → threshold=0.70, 0.75
    (0.82, "band_C"),   # gated when threshold <= 0.82       → threshold=0.70, 0.75, 0.80
]

# Minimum bar separation between injected collisions (avoids cooldown overlap)
MIN_BAR_GAP = 20


@dataclass(frozen=True)
class CostModel:
    fee_bps_per_side: float = 2.0
    slippage_bps_total: float = 2.0

    @property
    def fee_total_frac(self) -> float:
        return (2.0 * self.fee_bps_per_side) / 10_000.0

    @property
    def slippage_total_frac(self) -> float:
        return self.slippage_bps_total / 10_000.0


def _add_labels(df: pd.DataFrame, horizon_bars: int, cost: CostModel) -> pd.DataFrame:
    out = df.copy()
    out["future_close"] = out["close"].shift(-horizon_bars)
    out["gross_edge"] = (out["future_close"] - out["close"]) / out["close"]
    out["net_edge"] = (
        out["gross_edge"] - cost.fee_total_frac - cost.slippage_total_frac
    )
    out["tradeable_long"] = (out["net_edge"] > 0.0).astype(int)
    out["signal_candidate"] = out["tradeable_long"]
    out["direction_long"] = (out["gross_edge"] > 0.0).astype(int)
    return out.dropna().reset_index(drop=True)


def _find_candidate_timestamps(
    btc: pd.DataFrame,
    eth: pd.DataFrame,
    n: int,
    min_gap: int,
) -> list[pd.Timestamp]:
    """
    Deterministically choose `n` well-spaced timestamps from the common BTC/ETH
    timeline, independent of current signal state.
    """
    btc_ts = pd.to_datetime(btc["timestamp"], errors="coerce")
    eth_ts = pd.to_datetime(eth["timestamp"], errors="coerce")
    common = sorted(set(btc_ts.dropna()) & set(eth_ts.dropna()))

    if len(common) < (n + 2):
        return []

    # Avoid head/tail where shifted horizon labels may be dropped.
    common = common[20:-20] if len(common) > 60 else common
    if len(common) < n:
        return []

    selected: list[pd.Timestamp] = []
    step = max(min_gap, len(common) // (n + 1))
    cursor = step
    while len(selected) < n and cursor < len(common):
        ts = common[cursor]
        if not selected or (ts - selected[-1]) >= pd.Timedelta(minutes=15 * min_gap):
            selected.append(ts)
        cursor += step

    return selected[:n]


def generate(features_dir: Path, output_dir: Path) -> Path:
    btc_path = features_dir / "kraken_BTC_USD_15m_features.parquet"
    eth_path = features_dir / "kraken_ETH_USD_15m_features.parquet"

    if not btc_path.exists():
        raise FileNotFoundError(f"BTC features not found: {btc_path}")
    if not eth_path.exists():
        raise FileNotFoundError(f"ETH features not found: {eth_path}")

    print("Loading feature parquets...")
    btc = pd.read_parquet(btc_path)
    eth = pd.read_parquet(eth_path)
    print(f"  BTC {btc.shape}  ETH {eth.shape}")

    # Pick deterministic collision bars from the shared BTC/ETH timeline
    collision_ts_list = _find_candidate_timestamps(
        btc, eth, n=len(COLLISION_SPECS), min_gap=MIN_BAR_GAP
    )
    if len(collision_ts_list) < len(COLLISION_SPECS):
        raise RuntimeError(
            f"Could not locate {len(COLLISION_SPECS)} usable collision timestamps "
            f"(found {len(collision_ts_list)}). "
            "Try a larger features dataset."
        )

    print(f"\nInjecting {len(COLLISION_SPECS)} multi-magnitude collisions:")
    # Work on RAW feature frames. Pipeline will recompute labels/signals from these,
    # so we must force the raw signal ingredients to satisfy build_signal_mask.
    for df_raw, label in [(btc, "BTC"), (eth, "ETH")]:
        for col, default in [("mean_correlation", 0.0), ("corr_regime", "neutral_correlation")]:
            if col not in df_raw.columns:
                df_raw[col] = default
        for col, default in [("breakout_up", 0), ("volume_intensity", 0.0), ("momentum_4", 0.0), ("baseline_score", 0.0)]:
            if col not in df_raw.columns:
                df_raw[col] = default

    for (mean_corr, band), ts in zip(COLLISION_SPECS, collision_ts_list):
        print(f"  {band}: mean_correlation={mean_corr}  timestamp={ts}")
        for df_raw in [btc, eth]:
            mask = pd.to_datetime(df_raw["timestamp"], errors="coerce") == ts
            df_raw.loc[mask, "mean_correlation"] = mean_corr
            df_raw.loc[mask, "corr_regime"] = "neutral_correlation"
            # Force signal mask true at this bar for both assets:
            # breakout_up=1, volume_intensity>=2.0, and momentum_4>0 so baseline_score>=0.002.
            df_raw.loc[mask, "breakout_up"] = 1
            df_raw.loc[mask, "volume_intensity"] = 3.0
            df_raw.loc[mask, "momentum_4"] = 0.01
            df_raw.loc[mask, "baseline_score"] = 0.03

    output_dir.mkdir(parents=True, exist_ok=True)
    btc_out = output_dir / "kraken_BTC_USD_15m_features.parquet"
    eth_out = output_dir / "kraken_ETH_USD_15m_features.parquet"
    btc.to_parquet(btc_out)
    eth.to_parquet(eth_out)

    print(f"\nMulti-magnitude collision data written to: {output_dir}")
    print(f"  {btc_out.name}")
    print(f"  {eth_out.name}")
    print(
        "\nExpected gated_signals_count by threshold:"
        "\n  0.70 → 3   0.75 → 2   0.80 → 1   0.85 → 0"
    )

    # Write regime parquets so hydrate_backtest_regime_frame picks up the
    # injected mean_correlation values instead of resetting them to 0.0.
    # Format mirrors what regime-classify produces:
    #   columns: timestamp, mean_correlation, corr_regime
    regime_dir = output_dir / "regime"
    regime_dir.mkdir(parents=True, exist_ok=True)

    for df_raw, sym_safe in [(btc, "BTCUSD"), (eth, "ETHUSD")]:
        regime_df = df_raw[["timestamp", "mean_correlation", "corr_regime"]].copy()
        regime_df["mean_correlation"] = regime_df["mean_correlation"].fillna(0.0)
        regime_df["corr_regime"] = regime_df["corr_regime"].fillna("neutral_correlation")
        regime_path = regime_dir / f"kraken_{sym_safe}_regime.parquet"
        regime_df.to_parquet(regime_path, index=False)

    print(f"\nRegime parquets written to: {regime_dir}")
    print(f"  kraken_BTCUSD_regime.parquet  kraken_ETHUSD_regime.parquet")
    print(
        "\nExpected gated_signals_count by threshold:"
        "\n  0.70 → 3   0.75 → 2   0.80 → 1   0.85 → 0"
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate multi-magnitude collision dataset for gate_threshold sweep"
    )
    parser.add_argument(
        "--features-dir",
        type=Path,
        default=Path("data/crypto/features"),
        help="Directory containing kraken_*_features.parquet files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/crypto/multimag_collision_data"),
        help="Output directory for injected parquet files",
    )
    args = parser.parse_args()
    try:
        generate(features_dir=args.features_dir, output_dir=args.output_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
