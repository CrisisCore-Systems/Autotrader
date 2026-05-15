"""
Market Regime Classifier — Dynamic Regime-Switching Metadata Layer

Classifies each OHLCV bar into one of three market regimes using
Parkinson volatility, Rogers-Satchell volatility, and return sign-autocorrelation.

Regime IDs
----------
mean_reversion  – Low volatility, range-bound, negative or neutral return autocorrelation.
                  Favours tight horizons + wider stops (price pulls back to mean).
momentum_trend  – Elevated volatility, breakout structure, positive autocorrelation.
                  Favours compressed horizons + strict entries.
liquidity_void  – Extreme volatility spike or very thin volume (flash crash / gap-down).
                  Trading suspended; cooldown enforced.

Usage (standalone)
------------------
    python scripts/classify_market_regime.py
    python scripts/classify_market_regime.py --symbols BTC/USD --window 96
    python scripts/classify_market_regime.py --input-dir data/crypto/features \
        --output-dir data/crypto/regime --summary

Integration
-----------
    from scripts.classify_market_regime import classify_regimes, load_regime_config

Can also be wired in as a subcommand via crypto_data_pipeline.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGIME_LABELS: tuple[str, ...] = ("mean_reversion", "momentum_trend", "liquidity_void")
_DEFAULT_WINDOW = 96          # 96 × 15-min bars = 24 h
_DEFAULT_BARS_PER_YEAR = 35040  # 365 × 24 × 4  (15-min bars)

# ---------------------------------------------------------------------------
# Volatility estimators
# ---------------------------------------------------------------------------


def parkinson_variance_bar(high: pd.Series, low: pd.Series) -> pd.Series:
    """Per-bar Parkinson variance.

    sigma_P^2 = ln(H/L)^2 / (4 * ln 2)

    Strictly positive; requires H > L (enforced by clipping).
    """
    h = high.clip(lower=1e-12)
    l_ = low.clip(lower=1e-12)
    # Guard against H == L (zero-range bars — rare but possible in low-liquidity periods)
    safe_ratio = (h / l_).clip(lower=1.0 + 1e-12)
    log_hl = np.log(safe_ratio)
    return (log_hl ** 2) / (4.0 * np.log(2.0))


def rogers_satchell_variance_bar(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.Series:
    """Per-bar Rogers-Satchell variance.

    sigma_RS^2 = ln(H/C) * ln(H/O) + ln(L/C) * ln(L/O)

    Handles drift (trending assets) better than Parkinson.
    Clipped to zero because H/L near-equality can yield tiny negatives.
    """
    eps = 1e-12
    h = high.clip(lower=eps)
    l_ = low.clip(lower=eps)
    c = close.clip(lower=eps)
    o = open_.clip(lower=eps)
    rs = np.log(h / c) * np.log(h / o) + np.log(l_ / c) * np.log(l_ / o)
    return rs.clip(lower=0.0)


def rolling_annualised_vol(
    variance_series: pd.Series,
    window: int,
    bars_per_year: int,
) -> pd.Series:
    """Rolling annualised volatility from a per-bar variance series."""
    return np.sqrt(variance_series.rolling(window, min_periods=window // 2).mean() * bars_per_year)


# ---------------------------------------------------------------------------
# Return sign-autocorrelation (fast proxy, no scipy needed)
# ---------------------------------------------------------------------------


def rolling_sign_autocorr(ret: pd.Series, window: int) -> pd.Series:
    """Rolling sign-autocorrelation.

    mean(sign(r_t) * sign(r_{t-1})) over the rolling window.
      > 0 → returns tend to continue   (momentum / trend)
      < 0 → returns tend to reverse    (mean reversion)
      ≈ 0 → no directional persistence (mixed / void)
    """
    sign_t = np.sign(ret)
    sign_lag1 = sign_t.shift(1)
    product = sign_t * sign_lag1
    return product.rolling(window, min_periods=window // 2).mean()


# ---------------------------------------------------------------------------
# Timeframe inference
# ---------------------------------------------------------------------------


def infer_timeframe_min(df: pd.DataFrame) -> int:
    """Infer bar duration in minutes from a timestamp column or index."""
    ts = None
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
    elif isinstance(df.index, pd.DatetimeIndex):
        ts = df.index.to_series()

    if ts is not None and len(ts) >= 2:
        median_diff_s = float(ts.diff().dt.total_seconds().dropna().median())
        if median_diff_s > 0:
            return max(1, round(median_diff_s / 60))
    return 15  # sensible fallback for the pipeline default


# ---------------------------------------------------------------------------
# Core classification
# ---------------------------------------------------------------------------


def classify_regimes(
    df: pd.DataFrame,
    *,
    window: int = _DEFAULT_WINDOW,
    park_void_pct: float = 95.0,
    park_trend_pct: float = 70.0,
    rs_trend_pct: float = 70.0,
    min_volume_intensity: float = 0.15,
    bars_per_year: int | None = None,
) -> pd.DataFrame:
    """Classify each bar into a market regime.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: open, high, low, close.
        Optional (used when available): volume_intensity, ret_1.
    window : int
        Rolling lookback in bars (default 96 = 24 h for 15-min bars).
    park_void_pct : float
        Expanding-quantile percentile above which Parkinson vol triggers
        a *liquidity_void* classification (default 95).
    park_trend_pct : float
        Expanding-quantile percentile above which Parkinson vol, together
        with positive sign-autocorrelation, triggers *momentum_trend*
        (default 70).
    rs_trend_pct : float
        Same threshold for the Rogers-Satchell estimator (default 70).
    min_volume_intensity : float
        Volume relative to 24 h average below which a high-Parkinson-vol
        bar is classified as *liquidity_void* rather than trend (default 0.15).
    bars_per_year : int | None
        Override for annualisation; inferred from timestamps if None.

    Returns
    -------
    pd.DataFrame
        Input dataframe plus columns:
          park_var, rs_var, park_vol_roll, rs_vol_roll,
          park_vol_ann, rs_vol_ann, sign_autocorr,
          park_void_threshold, park_trend_threshold, rs_trend_threshold,
          regime
    """
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"classify_regimes: missing columns {missing}")

    out = df.copy()

    # Infer bars_per_year from timestamp if not supplied
    if bars_per_year is None:
        tf_min = infer_timeframe_min(out)
        bars_per_year = max(1, round(365 * 24 * 60 / tf_min))

    # --- Volatility --------------------------------------------------------
    park_var = parkinson_variance_bar(out["high"], out["low"])
    rs_var = rogers_satchell_variance_bar(out["open"], out["high"], out["low"], out["close"])

    out["park_var"] = park_var
    out["rs_var"] = rs_var

    park_roll = park_var.rolling(window, min_periods=window // 2).mean()
    rs_roll = rs_var.rolling(window, min_periods=window // 2).mean()

    out["park_vol_roll"] = park_roll
    out["rs_vol_roll"] = rs_roll
    out["park_vol_ann"] = rolling_annualised_vol(park_var, window, bars_per_year)
    out["rs_vol_ann"] = rolling_annualised_vol(rs_var, window, bars_per_year)

    # --- Return sign-autocorrelation ---------------------------------------
    if "ret_1" in out.columns:
        ret_series = out["ret_1"]
    else:
        ret_series = out["close"].pct_change(1)
    out["sign_autocorr"] = rolling_sign_autocorr(ret_series, window)

    # --- Expanding-quantile thresholds (adapts to each asset's history) ---
    out["park_void_threshold"] = park_roll.expanding(min_periods=window).quantile(
        park_void_pct / 100.0
    )
    out["park_trend_threshold"] = park_roll.expanding(min_periods=window).quantile(
        park_trend_pct / 100.0
    )
    out["rs_trend_threshold"] = rs_roll.expanding(min_periods=window).quantile(
        rs_trend_pct / 100.0
    )

    # Fill early NaNs in thresholds with the first valid value
    out["park_void_threshold"] = out["park_void_threshold"].ffill().bfill()
    out["park_trend_threshold"] = out["park_trend_threshold"].ffill().bfill()
    out["rs_trend_threshold"] = out["rs_trend_threshold"].ffill().bfill()

    # --- Volume intensity --------------------------------------------------
    if "volume_intensity" in out.columns:
        vol_intensity = out["volume_intensity"].fillna(1.0)
    else:
        vol_intensity = pd.Series(1.0, index=out.index)

    # --- Regime assignment (priority: void > trend > mean_reversion) ------
    regime = pd.Series("mean_reversion", index=out.index, dtype="object")

    is_high_park = park_roll >= out["park_trend_threshold"]
    is_high_rs = rs_roll >= out["rs_trend_threshold"]
    is_trending = out["sign_autocorr"] > 0.0

    # momentum_trend: elevated vol + trending return structure
    momentum_mask = (is_high_park | is_high_rs) & is_trending
    regime[momentum_mask] = "momentum_trend"

    # liquidity_void: extreme vol spike OR elevated vol + thin volume
    void_extreme = park_roll >= out["park_void_threshold"]
    void_thin_vol = is_high_park & (vol_intensity < min_volume_intensity)
    void_mask = void_extreme | void_thin_vol
    regime[void_mask] = "liquidity_void"

    out["regime"] = regime
    return out


# ---------------------------------------------------------------------------
# Regime config loader
# ---------------------------------------------------------------------------


def load_regime_config(config_path: Path) -> dict[str, Any]:
    """Load regime-specific execution profiles from crypto_strategy.yaml.

    Returns dict keyed by regime label, e.g.:
      {
        "mean_reversion":  {"horizon_bars": 8, ...},
        "momentum_trend":  {"horizon_bars": 4, ...},
        "liquidity_void":  {"horizon_bars": 16, ...},
      }
    Falls back to empty dict if "regimes" section is absent.
    """
    import yaml  # local import so this file is importable without pyyaml at module load

    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return raw.get("regimes", {})


def resolve_regime_policy(
    regime: str,
    regime_config: dict[str, Any],
    base_horizon_bars: int,
    base_score_threshold: float,
    base_cooldown_bars: int,
) -> dict[str, Any]:
    """Merge base policy with regime override, returning the active policy dict."""
    override = regime_config.get(regime, {})
    return {
        "horizon_bars": int(override.get("horizon_bars", base_horizon_bars)),
        "signal_score_threshold": float(
            override.get("signal_score_threshold", base_score_threshold)
        ),
        "cooldown_bars": int(override.get("cooldown_bars", base_cooldown_bars)),
        "regime": regime,
    }


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------


def regime_summary(df: pd.DataFrame, symbol: str = "") -> dict[str, Any]:
    """Compute counts, percentages, and current (latest) regime."""
    counts = df["regime"].value_counts().to_dict()
    total = len(df)
    current_regime = str(df["regime"].iloc[-1]) if total > 0 else "unknown"
    last_park_ann = float(df["park_vol_ann"].iloc[-1]) if "park_vol_ann" in df.columns else float("nan")
    last_rs_ann = float(df["rs_vol_ann"].iloc[-1]) if "rs_vol_ann" in df.columns else float("nan")
    last_sign_autocorr = float(df["sign_autocorr"].iloc[-1]) if "sign_autocorr" in df.columns else float("nan")

    return {
        "symbol": symbol,
        "total_bars": total,
        "current_regime": current_regime,
        "last_park_vol_ann": round(last_park_ann, 4),
        "last_rs_vol_ann": round(last_rs_ann, 4),
        "last_sign_autocorr": round(last_sign_autocorr, 4),
        "distribution": {
            label: {
                "count": counts.get(label, 0),
                "pct": round(counts.get(label, 0) / max(1, total) * 100, 1),
            }
            for label in REGIME_LABELS
        },
    }


def print_regime_table(summaries: list[dict[str, Any]]) -> None:
    hdr = (
        f"  {'Symbol':<12} {'Current Regime':<18} "
        f"{'Park Vol%':>10} {'RS Vol%':>10} {'SignAC':>8} "
        f"{'MR%':>6} {'MT%':>6} {'LV%':>6}"
    )
    print("\nMarket Weather Report")
    print(hdr)
    print("  " + "-" * 84)
    for s in summaries:
        dist = s.get("distribution", {})
        mr_pct = dist.get("mean_reversion", {}).get("pct", 0.0)
        mt_pct = dist.get("momentum_trend", {}).get("pct", 0.0)
        lv_pct = dist.get("liquidity_void", {}).get("pct", 0.0)
        pv = s.get("last_park_vol_ann", float("nan"))
        rv = s.get("last_rs_vol_ann", float("nan"))
        sa = s.get("last_sign_autocorr", float("nan"))
        print(
            f"  {s.get('symbol', ''):<12} {s.get('current_regime', ''):<18} "
            f"{pv*100:>9.1f}% {rv*100:>9.1f}% {sa:>8.3f} "
            f"{mr_pct:>5.1f}% {mt_pct:>5.1f}% {lv_pct:>5.1f}%"
        )
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="classify_market_regime",
        description="Classify OHLCV bars into market regimes (mean_reversion / momentum_trend / liquidity_void).",
    )
    p.add_argument(
        "--input-dir",
        default="data/crypto/features",
        help="Directory containing kraken_*_features.parquet files.",
    )
    p.add_argument(
        "--output-dir",
        default="data/crypto/regime",
        help="Directory to write regime parquets and summary JSON.",
    )
    p.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbol filter, e.g. BTC/USD,ETH/USD. Empty = all found.",
    )
    p.add_argument(
        "--window",
        type=int,
        default=_DEFAULT_WINDOW,
        help="Rolling window in bars for vol/autocorr (default 96 = 24 h at 15-min).",
    )
    p.add_argument(
        "--park-void-pct",
        type=float,
        default=95.0,
        help="Expanding-quantile percentile for liquidity-void threshold (default 95).",
    )
    p.add_argument(
        "--park-trend-pct",
        type=float,
        default=70.0,
        help="Expanding-quantile percentile for momentum-trend threshold (default 70).",
    )
    p.add_argument(
        "--min-volume-intensity",
        type=float,
        default=0.15,
        help="Volume-intensity floor below which a high-vol bar becomes liquidity_void.",
    )
    p.add_argument(
        "--summary",
        action="store_true",
        default=True,
        help="Print regime summary table to stdout (default on).",
    )
    p.add_argument(
        "--no-summary",
        dest="summary",
        action="store_false",
        help="Suppress regime summary table.",
    )
    p.add_argument(
        "--write-parquet",
        action="store_true",
        default=True,
        help="Write per-symbol regime parquet (default on).",
    )
    p.add_argument(
        "--no-write-parquet",
        dest="write_parquet",
        action="store_false",
        help="Skip writing regime parquet.",
    )
    return p


def command_classify(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Run classification for all matching feature files. Returns list of summaries."""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    files = sorted(input_dir.glob("kraken_*_features.parquet"))
    if not files:
        print(f"[regime] No feature parquet files found in {input_dir}", file=sys.stderr)
        return []

    symbol_filter: set[str] = set()
    if getattr(args, "symbols", ""):
        symbol_filter = {s.strip().upper().replace("/", "") for s in args.symbols.split(",") if s.strip()}

    summaries: list[dict[str, Any]] = []

    for file in files:
        try:
            df = pd.read_parquet(file)
        except Exception as exc:
            print(f"[regime] WARN: could not read {file}: {exc}", file=sys.stderr)
            continue

        if df.empty:
            continue

        # Resolve symbol
        if "symbol" in df.columns:
            symbol = str(df["symbol"].iloc[0])
        else:
            symbol = file.stem.replace("kraken_", "").replace("_features", "").upper()

        safe_sym = symbol.replace("/", "")
        if symbol_filter and safe_sym not in symbol_filter:
            continue

        try:
            classified = classify_regimes(
                df,
                window=args.window,
                park_void_pct=args.park_void_pct,
                park_trend_pct=args.park_trend_pct,
                min_volume_intensity=args.min_volume_intensity,
            )
        except Exception as exc:
            print(f"[regime] ERROR classifying {symbol}: {exc}", file=sys.stderr)
            continue

        s = regime_summary(classified, symbol=symbol)
        summaries.append(s)

        if getattr(args, "write_parquet", True):
            output_dir.mkdir(parents=True, exist_ok=True)
            out_file = output_dir / f"kraken_{safe_sym}_regime.parquet"
            classified.to_parquet(out_file, index=False)
            print(f"[regime] Written: {out_file}  ({len(classified):,} bars, current={s['current_regime']})")

    if getattr(args, "summary", True) and summaries:
        print_regime_table(summaries)

    if summaries:
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest_path = output_dir / f"regime_summary_{ts}.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "stage": "regime-classify",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "window": args.window,
                    "park_void_pct": args.park_void_pct,
                    "park_trend_pct": args.park_trend_pct,
                    "symbols": summaries,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[regime] Manifest written: {manifest_path}")

    return summaries


def main(argv: list[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summaries = command_classify(args)
    if not summaries:
        sys.exit(1)


if __name__ == "__main__":
    main()
