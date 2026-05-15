from __future__ import annotations

import argparse
import json
import math
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import yaml


KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
KRAKEN_TRADES_URL = "https://api.kraken.com/0/public/Trades"


@dataclass(frozen=True)
class CostModel:
    fee_bps_per_side: float
    slippage_bps_total: float

    @property
    def fee_total_frac(self) -> float:
        return (2.0 * self.fee_bps_per_side) / 10000.0

    @property
    def slippage_total_frac(self) -> float:
        return self.slippage_bps_total / 10000.0


@dataclass(frozen=True)
class StrategyPolicy:
    symbol: str
    horizon_bars: int
    signal_volume_threshold: float
    signal_score_threshold: float
    cooldown_bars: int


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_symbols(symbols: str) -> list[str]:
    return [s.strip().upper() for s in symbols.split(",") if s.strip()]


def symbol_to_kraken_pair(symbol: str) -> str:
    normalized = symbol.replace("-", "/")
    base, quote = normalized.split("/", 1)
    if base == "BTC":
        base = "XBT"
    return f"{base}{quote}"


def kraken_public_get(url: str, params: dict[str, Any], timeout: int = 20) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request_url = f"{url}?{query}"
    with urllib.request.urlopen(request_url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    errors = payload.get("error", [])
    if errors:
        raise RuntimeError(f"Kraken API error: {errors}")
    return payload


def fetch_kraken_ohlc(symbol: str, timeframe_min: int, bars: int) -> pd.DataFrame:
    pair = symbol_to_kraken_pair(symbol)
    # Start far enough back to capture requested bars in rolling calls.
    since = int(time.time()) - (bars * timeframe_min * 60)
    rows: list[list[Any]] = []
    seen_timestamps: set[int] = set()

    # Kraken may cap bars per response. Loop with safety bound.
    for _ in range(10):
        payload = kraken_public_get(
            KRAKEN_OHLC_URL,
            {
                "pair": pair,
                "interval": timeframe_min,
                "since": since,
            },
        )
        result = payload.get("result", {})
        if not result:
            break

        result_key = next((k for k in result.keys() if k != "last"), None)
        if result_key is None:
            break

        chunk = result.get(result_key, [])
        if not chunk:
            break

        appended = 0
        for row in chunk:
            ts = int(float(row[0]))
            if ts not in seen_timestamps:
                rows.append(row)
                seen_timestamps.add(ts)
                appended += 1

        new_since = int(result.get("last", since))
        if appended == 0 or new_since <= since:
            break
        since = new_since

        if len(rows) >= bars:
            break

    if not rows:
        raise RuntimeError(f"No OHLC data returned for {symbol} at {timeframe_min}m")

    # Kraken OHLC row format:
    # [time, open, high, low, close, vwap, volume, count]
    df = pd.DataFrame(
        rows,
        columns=[
            "timestamp_s",
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
            "trade_count",
        ],
    )

    numeric_cols = ["open", "high", "low", "close", "vwap", "volume", "trade_count"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["timestamp"] = pd.to_datetime(df["timestamp_s"], unit="s", utc=True)
    df["symbol"] = symbol
    df["exchange"] = "kraken"
    df["timeframe_min"] = timeframe_min
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp", "symbol"]).reset_index(drop=True)

    if len(df) > bars:
        df = df.tail(bars).reset_index(drop=True)

    return df[
        [
            "timestamp",
            "symbol",
            "exchange",
            "timeframe_min",
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
            "trade_count",
        ]
    ]


def parse_kraken_trades(symbol: str, trades_raw: list[list[Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in trades_raw:
        if len(row) < 6:
            continue
        rows.append(
            {
                "timestamp": pd.to_datetime(float(row[2]), unit="s", utc=True),
                "price": float(row[0]),
                "volume": float(row[1]),
                "side": str(row[3]),
                "ordertype": str(row[4]),
                "misc": str(row[5]),
                "symbol": symbol,
                "exchange": "kraken",
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["timestamp", "price", "volume", "side", "ordertype", "misc", "symbol", "exchange"]
        )

    df = pd.DataFrame(rows)
    return df.sort_values("timestamp").reset_index(drop=True)


def safe_symbol_name(symbol: str) -> str:
    return symbol.replace("/", "_").replace("-", "_")


def trade_archive_symbol_dir(archive_root: Path, symbol: str) -> Path:
    return archive_root / safe_symbol_name(symbol)


def trade_archive_partition_path(archive_root: Path, symbol: str, timestamp: pd.Timestamp) -> Path:
    month_key = pd.Timestamp(timestamp).strftime("%Y-%m")
    return trade_archive_symbol_dir(archive_root, symbol) / f"{month_key}.parquet"


def load_trade_archive(symbol: str, archive_root: Path) -> pd.DataFrame:
    symbol_dir = trade_archive_symbol_dir(archive_root, symbol)
    partition_files = sorted(symbol_dir.glob("*.parquet")) if symbol_dir.exists() else []

    if partition_files:
        frames = [load_parquet(path) for path in partition_files]
        merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not merged.empty:
            return merged.sort_values("timestamp").drop_duplicates(subset=["timestamp", "price", "volume", "side"], keep="last").reset_index(drop=True)

    legacy_file = archive_root / f"kraken_{safe_symbol_name(symbol)}_trades.parquet"
    if legacy_file.exists():
        return load_parquet(legacy_file).sort_values("timestamp").drop_duplicates(subset=["timestamp", "price", "volume", "side"], keep="last").reset_index(drop=True)

    return pd.DataFrame(columns=["timestamp", "price", "volume", "side", "ordertype", "misc", "symbol", "exchange"])


def archive_trade_high_water_mark(symbol: str, archive_root: Path) -> tuple[pd.Timestamp | None, Path | None]:
    archive_df = load_trade_archive(symbol, archive_root)
    if archive_df.empty:
        return None, None

    latest_idx = archive_df["timestamp"].idxmax()
    latest_ts = pd.Timestamp(archive_df.loc[latest_idx, "timestamp"])
    latest_partition = trade_archive_partition_path(archive_root, symbol, latest_ts)
    return latest_ts, latest_partition


def archive_trade_bounds(symbol: str, archive_root: Path) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    archive_df = load_trade_archive(symbol, archive_root)
    if archive_df.empty:
        return None, None

    timestamps = pd.to_datetime(archive_df["timestamp"], utc=True)
    return pd.Timestamp(timestamps.min()), pd.Timestamp(timestamps.max())


def upsert_trade_archive(trades_df: pd.DataFrame, archive_root: Path, symbol: str) -> pd.DataFrame:
    archive_root.mkdir(parents=True, exist_ok=True)
    if trades_df.empty:
        return load_trade_archive(symbol, archive_root)

    merged = load_trade_archive(symbol, archive_root)
    if merged.empty:
        merged = trades_df.copy()
    else:
        merged = pd.concat([merged, trades_df], ignore_index=True)

    merged = merged.drop_duplicates(subset=["timestamp", "price", "volume", "side"], keep="last")
    merged = merged.sort_values("timestamp").reset_index(drop=True)

    symbol_dir = trade_archive_symbol_dir(archive_root, symbol)
    symbol_dir.mkdir(parents=True, exist_ok=True)
    for month_key, month_df in merged.groupby(merged["timestamp"].dt.strftime("%Y-%m")):
        partition_path = symbol_dir / f"{month_key}.parquet"
        write_parquet(month_df.reset_index(drop=True), partition_path)

    return merged


def trades_to_ohlcv(trades_df: pd.DataFrame, timeframe_min: int, symbol: str) -> pd.DataFrame:
    if trades_df.empty:
        raise RuntimeError(f"No trades available to resample for {symbol}")

    rule = f"{timeframe_min}min"
    ts_indexed = trades_df.set_index("timestamp").sort_index()

    ohlc = ts_indexed["price"].resample(rule, label="right", closed="right").ohlc()
    volume = ts_indexed["volume"].resample(rule, label="right", closed="right").sum().rename("volume")
    trade_count = ts_indexed["price"].resample(rule, label="right", closed="right").count().rename("trade_count")

    notional = (ts_indexed["price"] * ts_indexed["volume"]).resample(rule, label="right", closed="right").sum()
    vwap = (notional / volume.replace(0.0, np.nan)).rename("vwap")

    out = pd.concat([ohlc, vwap, volume, trade_count], axis=1).dropna(subset=["open", "high", "low", "close"])
    out = out.reset_index().rename(columns={"index": "timestamp"})
    out["symbol"] = symbol
    out["exchange"] = "kraken"
    out["timeframe_min"] = timeframe_min

    return out[
        [
            "timestamp",
            "symbol",
            "exchange",
            "timeframe_min",
            "open",
            "high",
            "low",
            "close",
            "vwap",
            "volume",
            "trade_count",
        ]
    ].reset_index(drop=True)


def audit_trade_tape_gaps(trades_df: pd.DataFrame, gap_threshold_seconds: float) -> dict[str, Any]:
    if trades_df.empty:
        return {
            "trade_count": 0,
            "gap_threshold_seconds": gap_threshold_seconds,
            "gap_count": 0,
            "max_gap_seconds": 0.0,
            "gaps": [],
        }

    timestamps = pd.to_datetime(trades_df["timestamp"], utc=True).sort_values().drop_duplicates().reset_index(drop=True)
    diffs = timestamps.diff().dropna()
    gap_mask = diffs > pd.Timedelta(seconds=gap_threshold_seconds)

    gaps: list[dict[str, Any]] = []
    for idx in np.flatnonzero(gap_mask.to_numpy()):
        start_ts = pd.Timestamp(timestamps.iloc[idx])
        end_ts = pd.Timestamp(timestamps.iloc[idx + 1])
        gaps.append(
            {
                "gap_seconds": float((end_ts.value - start_ts.value) / 1_000_000_000),
                "start": start_ts.isoformat(),
                "end": end_ts.isoformat(),
            }
        )

    max_gap_seconds = float(diffs.max().total_seconds()) if not diffs.empty else 0.0
    return {
        "trade_count": int(len(timestamps)),
        "gap_threshold_seconds": float(gap_threshold_seconds),
        "gap_count": int(len(gaps)),
        "max_gap_seconds": max_gap_seconds,
        "gaps": gaps,
    }


def audit_bar_gaps(bars_df: pd.DataFrame, timeframe_min: int) -> dict[str, Any]:
    if bars_df.empty:
        return {
            "bar_count": 0,
            "expected_bar_count": 0,
            "missing_bar_count": 0,
            "gaps": [],
        }

    timestamps = pd.to_datetime(bars_df["timestamp"], utc=True).sort_values().drop_duplicates().reset_index(drop=True)
    rule = pd.Timedelta(minutes=timeframe_min)
    expected = pd.date_range(start=timestamps.iloc[0], end=timestamps.iloc[-1], freq=rule, tz="UTC")
    missing = expected.difference(timestamps)

    gaps: list[dict[str, Any]] = []
    if not missing.empty:
        missing_series = pd.Series(missing).sort_values().reset_index(drop=True)
        start = missing_series.iloc[0]
        prev = start
        for ts in missing_series.iloc[1:]:
            if ts - prev > rule:
                gaps.append(
                    {
                        "start": pd.Timestamp(start).isoformat(),
                        "end": pd.Timestamp(prev).isoformat(),
                        "missing_bars": int(((prev - start) / rule) + 1),
                    }
                )
                start = ts
            prev = ts
        gaps.append(
            {
                "start": pd.Timestamp(start).isoformat(),
                "end": pd.Timestamp(prev).isoformat(),
                "missing_bars": int(((prev - start) / rule) + 1),
            }
        )

    return {
        "bar_count": int(len(timestamps)),
        "expected_bar_count": int(len(expected)),
        "missing_bar_count": int(len(missing)),
        "gaps": gaps,
    }


def fetch_kraken_trades(
    symbol: str,
    since_ns: int,
    max_pages: int,
    sleep_seconds: float,
    max_retries: int,
    until_ns: int | None = None,
) -> tuple[pd.DataFrame, int, int, bool]:
    pair = symbol_to_kraken_pair(symbol)
    all_rows: list[list[Any]] = []
    pages = 0
    cursor = int(since_ns)
    reached_until = until_ns is None

    for _ in range(max_pages):
        payload: dict[str, Any] | None = None
        for retry_idx in range(max_retries + 1):
            try:
                payload = kraken_public_get(
                    KRAKEN_TRADES_URL,
                    {
                        "pair": pair,
                        "since": str(cursor),
                    },
                )
                break
            except RuntimeError as exc:
                is_rate_limited = "Too many requests" in str(exc)
                if not is_rate_limited or retry_idx >= max_retries:
                    raise
                backoff = max(1.0, sleep_seconds) * (2 ** retry_idx)
                time.sleep(backoff)

        if payload is None:
            break

        result = payload.get("result", {})
        result_key = next((k for k in result.keys() if k != "last"), None)
        if result_key is None:
            break

        chunk = result.get(result_key, [])
        last_cursor = int(result.get("last", cursor))

        if chunk:
            all_rows.extend(chunk)
            pages += 1

        if last_cursor <= cursor:
            break

        cursor = last_cursor
        if until_ns is not None and cursor >= until_ns:
            reached_until = True
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    if until_ns is not None and cursor >= until_ns:
        reached_until = True

    trades_df = parse_kraken_trades(symbol=symbol, trades_raw=all_rows)
    return trades_df, pages, cursor, reached_until


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr_components = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    true_range = tr_components.max(axis=1)
    return true_range.rolling(period).mean()


def add_features(df: pd.DataFrame, timeframe_min: int) -> pd.DataFrame:
    out = df.copy()
    bars_per_24h = max(2, int((24 * 60) / timeframe_min))

    out["ret_1"] = out["close"].pct_change(1)
    out["ret_4"] = out["close"].pct_change(4)
    out["ret_16"] = out["close"].pct_change(16)

    out["momentum_4"] = (out["close"] - out["close"].shift(4)) / out["close"].shift(4)
    out["momentum_16"] = (out["close"] - out["close"].shift(16)) / out["close"].shift(16)

    out["vol_roll_mean_24h"] = out["volume"].rolling(bars_per_24h).mean()
    out["vol_roll_std_24h"] = out["volume"].rolling(bars_per_24h).std()
    out["volume_intensity"] = out["volume"] / out["vol_roll_mean_24h"]
    out["volume_zscore"] = (out["volume"] - out["vol_roll_mean_24h"]) / (out["vol_roll_std_24h"] + 1e-12)

    out["atr_14"] = atr(out, 14)
    out["atr_frac"] = out["atr_14"] / out["close"]

    rolling_std_20 = out["ret_1"].rolling(20).std()
    rolling_std_96 = out["ret_1"].rolling(bars_per_24h).std()
    out["range_compression"] = rolling_std_20 / (rolling_std_96 + 1e-12)

    rolling_high = out["high"].rolling(bars_per_24h).max().shift(1)
    rolling_low = out["low"].rolling(bars_per_24h).min().shift(1)
    out["breakout_up"] = (out["close"] > rolling_high).astype(int)
    out["breakout_down"] = (out["close"] < rolling_low).astype(int)

    return out.dropna().reset_index(drop=True)


def add_labels(df: pd.DataFrame, horizon_bars: int, cost_model: CostModel) -> pd.DataFrame:
    out = df.copy()
    out["future_close"] = out["close"].shift(-horizon_bars)
    out["gross_edge"] = (out["future_close"] - out["close"]) / out["close"]
    out["net_edge"] = out["gross_edge"] - cost_model.fee_total_frac - cost_model.slippage_total_frac
    out["tradeable_long"] = (out["net_edge"] > 0.0).astype(int)
    out["direction_long"] = (out["gross_edge"] > 0.0).astype(int)
    return out.dropna().reset_index(drop=True)


def baseline_breakout_volume_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["baseline_score"] = (
        out["breakout_up"] * np.maximum(out["volume_intensity"], 0.0) * np.maximum(out["momentum_4"], 0.0)
    )
    return out


def load_strategy_config(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Strategy config must be a mapping: {path}")
    return data


def resolve_strategy_policy(symbol: str, config: dict[str, Any], args: argparse.Namespace) -> StrategyPolicy:
    defaults = config.get("defaults", {}) or {}
    symbols_cfg = config.get("symbols", {}) or {}
    symbol_cfg = symbols_cfg.get(symbol, {}) or {}

    def value(name: str, fallback: Any) -> Any:
        return symbol_cfg.get(name, defaults.get(name, fallback))

    return StrategyPolicy(
        symbol=symbol,
        horizon_bars=int(value("horizon_bars", args.horizon_bars)),
        signal_volume_threshold=float(value("signal_volume_threshold", args.signal_volume_threshold)),
        signal_score_threshold=float(value("signal_score_threshold", args.signal_score_threshold)),
        cooldown_bars=int(value("cooldown_bars", args.cooldown_bars)),
    )


def _load_current_regime(symbol: str, regime_dir: Path) -> str | None:
    """Return the last-bar regime label for *symbol* from a regime parquet, or None."""
    safe = symbol.replace("/", "")
    candidate = regime_dir / f"kraken_{safe}_regime.parquet"
    if not candidate.exists():
        return None
    try:
        df = pd.read_parquet(candidate, columns=["regime"])
        if df.empty or "regime" not in df.columns:
            return None
        return str(df["regime"].iloc[-1])
    except Exception:
        return None


def _apply_regime_to_policy(
    policy: StrategyPolicy,
    regime: str,
    regime_config: dict[str, Any],
) -> StrategyPolicy:
    """Return a new StrategyPolicy with fields overridden by the active regime profile."""
    override = regime_config.get(regime, {}) or {}
    return StrategyPolicy(
        symbol=policy.symbol,
        horizon_bars=int(override.get("horizon_bars", policy.horizon_bars)),
        signal_volume_threshold=float(override.get("signal_volume_threshold", policy.signal_volume_threshold)),
        signal_score_threshold=float(override.get("signal_score_threshold", policy.signal_score_threshold)),
        cooldown_bars=int(override.get("cooldown_bars", policy.cooldown_bars)),
    )


def generate_walkforward_windows(
    timestamps: pd.Series,
    train_months: int,
    validate_months: int,
    test_months: int,
) -> list[dict[str, str]]:
    ts = pd.to_datetime(timestamps, utc=True).sort_values().reset_index(drop=True)
    start = ts.min()
    end = ts.max()

    windows: list[dict[str, str]] = []
    cursor = start

    while True:
        train_end = cursor + pd.DateOffset(months=train_months)
        validate_end = train_end + pd.DateOffset(months=validate_months)
        test_end = validate_end + pd.DateOffset(months=test_months)

        if test_end > end:
            break

        windows.append(
            {
                "train_start": cursor.isoformat(),
                "train_end": train_end.isoformat(),
                "validate_start": train_end.isoformat(),
                "validate_end": validate_end.isoformat(),
                "test_start": validate_end.isoformat(),
                "test_end": test_end.isoformat(),
            }
        )
        cursor = cursor + pd.DateOffset(months=test_months)

    return windows


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    ensure_parent(path)
    try:
        df.to_parquet(path, index=False)
    except ImportError as exc:
        raise RuntimeError(
            "Parquet support is unavailable. Install pyarrow (pip install pyarrow)."
        ) from exc


def load_parquet(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except ImportError as exc:
        raise RuntimeError(
            "Parquet support is unavailable. Install pyarrow (pip install pyarrow)."
        ) from exc


def compute_max_drawdown(cumulative_pnl: pd.Series) -> float:
    if cumulative_pnl.empty:
        return 0.0
    running_peak = cumulative_pnl.cummax()
    drawdown = cumulative_pnl - running_peak
    return float(drawdown.min())


def consecutive_loss_stats(pnl: pd.Series) -> tuple[int, float]:
    losses = (pnl < 0).astype(int).to_numpy()
    if losses.size == 0:
        return 0, 0.0
    streaks: list[int] = []
    current = 0
    for is_loss in losses:
        if is_loss:
            current += 1
        elif current > 0:
            streaks.append(current)
            current = 0
    if current > 0:
        streaks.append(current)
    if not streaks:
        return 0, 0.0
    return int(max(streaks)), float(np.mean(streaks))


def time_under_water_stats(cumulative_pnl: pd.Series) -> tuple[float, int]:
    if cumulative_pnl.empty:
        return 0.0, 0

    values = cumulative_pnl.to_numpy(dtype=float)
    peaks = np.maximum.accumulate(values)
    underwater = values < peaks

    durations: list[int] = []
    i = 0
    n = len(values)
    while i < n:
        if not underwater[i]:
            i += 1
            continue
        start = i
        while i < n and underwater[i]:
            i += 1
        durations.append(i - start)

    if not durations:
        return 0.0, 0
    return float(np.mean(durations)), int(max(durations))


def drawdown_cluster_stats(
    trades_df: pd.DataFrame,
    cluster_gap_bars: int,
) -> tuple[int, float]:
    loss_idx = np.flatnonzero((trades_df["pnl_usd"] < 0).to_numpy())
    if loss_idx.size == 0:
        return 0, 0.0

    clusters = 1
    current_size = 1
    sizes: list[int] = []

    for i in range(1, len(loss_idx)):
        gap = int(loss_idx[i] - loss_idx[i - 1])
        # Cluster by backtest trade adjacency and configurable bar proximity.
        if gap <= max(1, cluster_gap_bars):
            current_size += 1
        else:
            sizes.append(current_size)
            clusters += 1
            current_size = 1

    sizes.append(current_size)
    return int(clusters), float(np.mean(sizes))


def build_equity_frame(trades_df: pd.DataFrame) -> pd.DataFrame:
    out = trades_df.copy()
    out["running_peak"] = out["cum_pnl"].cummax()
    out["drawdown"] = out["cum_pnl"] - out["running_peak"]
    return out


def ensure_crypto_registry_schema(db_path: Path) -> None:
    ensure_parent(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS crypto_runs (
                run_id TEXT PRIMARY KEY,
                timestamp_utc TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe_min INTEGER NOT NULL,
                feature_version TEXT NOT NULL,
                fee_bps_per_side REAL NOT NULL,
                slippage_bps_total REAL NOT NULL,
                notional_usd REAL NOT NULL,
                signal_volume_threshold REAL NOT NULL,
                signal_score_threshold REAL NOT NULL,
                horizon_bars INTEGER NOT NULL,
                cooldown_bars INTEGER NOT NULL,
                trades INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                losses INTEGER NOT NULL,
                win_rate REAL NOT NULL,
                profit_factor REAL NOT NULL,
                net_pnl REAL NOT NULL,
                avg_pnl_per_trade REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                recovery_factor REAL NOT NULL,
                max_consecutive_losses INTEGER NOT NULL,
                avg_loss_streak REAL NOT NULL,
                avg_tuw_bars REAL NOT NULL,
                max_tuw_bars INTEGER NOT NULL,
                loss_cluster_count INTEGER NOT NULL,
                avg_loss_cluster_size REAL NOT NULL,
                exit_mode TEXT NOT NULL,
                input_file TEXT NOT NULL,
                report_file TEXT NOT NULL,
                notes TEXT
            )
            """
        )

        columns = {row[1] for row in conn.execute("PRAGMA table_info(crypto_runs)").fetchall()}
        migrations: list[tuple[str, str]] = [
            ("recovery_factor", "REAL NOT NULL DEFAULT 0"),
            ("max_consecutive_losses", "INTEGER NOT NULL DEFAULT 0"),
            ("avg_loss_streak", "REAL NOT NULL DEFAULT 0"),
            ("avg_tuw_bars", "REAL NOT NULL DEFAULT 0"),
            ("max_tuw_bars", "INTEGER NOT NULL DEFAULT 0"),
            ("loss_cluster_count", "INTEGER NOT NULL DEFAULT 0"),
            ("avg_loss_cluster_size", "REAL NOT NULL DEFAULT 0"),
            ("exit_mode", "TEXT NOT NULL DEFAULT 'timeout'"),
            ("target_atr_multiplier", "REAL NOT NULL DEFAULT 0"),
            ("stop_atr_multiplier", "REAL NOT NULL DEFAULT 0"),
            ("atr_column", "TEXT NOT NULL DEFAULT ''"),
        ]
        for name, ddl in migrations:
            if name not in columns:
                conn.execute(f"ALTER TABLE crypto_runs ADD COLUMN {name} {ddl}")

        conn.commit()
    finally:
        conn.close()


def write_registry_row(db_path: Path, row: dict[str, Any]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO crypto_runs (
                run_id,
                timestamp_utc,
                symbol,
                timeframe_min,
                feature_version,
                fee_bps_per_side,
                slippage_bps_total,
                notional_usd,
                signal_volume_threshold,
                signal_score_threshold,
                horizon_bars,
                cooldown_bars,
                trades,
                wins,
                losses,
                win_rate,
                profit_factor,
                net_pnl,
                avg_pnl_per_trade,
                max_drawdown,
                recovery_factor,
                max_consecutive_losses,
                avg_loss_streak,
                avg_tuw_bars,
                max_tuw_bars,
                loss_cluster_count,
                avg_loss_cluster_size,
                exit_mode,
                target_atr_multiplier,
                stop_atr_multiplier,
                atr_column,
                input_file,
                report_file,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["run_id"],
                row["timestamp_utc"],
                row["symbol"],
                row["timeframe_min"],
                row["feature_version"],
                row["fee_bps_per_side"],
                row["slippage_bps_total"],
                row["notional_usd"],
                row["signal_volume_threshold"],
                row["signal_score_threshold"],
                row["horizon_bars"],
                row["cooldown_bars"],
                row["trades"],
                row["wins"],
                row["losses"],
                row["win_rate"],
                row["profit_factor"],
                row["net_pnl"],
                row["avg_pnl_per_trade"],
                row["max_drawdown"],
                row["recovery_factor"],
                row["max_consecutive_losses"],
                row["avg_loss_streak"],
                row["avg_tuw_bars"],
                row["max_tuw_bars"],
                row["loss_cluster_count"],
                row["avg_loss_cluster_size"],
                row["exit_mode"],
                row.get("target_atr_multiplier", 0.0),
                row.get("stop_atr_multiplier", 0.0),
                row.get("atr_column", ""),
                row["input_file"],
                row["report_file"],
                row.get("notes", ""),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def build_signal_mask(df: pd.DataFrame, volume_threshold: float, score_threshold: float) -> pd.Series:
    return (
        (df["breakout_up"] == 1)
        & (df["volume_intensity"] >= volume_threshold)
        & (df["baseline_score"] >= score_threshold)
    )


def apply_cooldown(signal_mask: pd.Series, cooldown_bars: int) -> pd.Series:
    if cooldown_bars <= 0:
        return signal_mask
    accepted = np.zeros(len(signal_mask), dtype=bool)
    last_idx = -10**9
    for i, is_signal in enumerate(signal_mask.to_numpy()):
        if not is_signal:
            continue
        if i - last_idx >= cooldown_bars:
            accepted[i] = True
            last_idx = i
    return pd.Series(accepted, index=signal_mask.index)


def simulate_trades_with_atr_exit(
    df: pd.DataFrame,
    accepted_mask: pd.Series,
    args: argparse.Namespace,
) -> pd.DataFrame:
    """Path-dependent simulator for ATR-based TP/SL exits.

    Notes:
    - Uses long-only signals (consistent with breakout_up signal mask).
    - If both TP and SL are breached within the same bar, assumes SL first
      as a conservative guardrail.
    """
    entry_idx = np.flatnonzero(accepted_mask.to_numpy())
    if entry_idx.size == 0:
        return pd.DataFrame(columns=["timestamp", "net_edge", "pnl_usd", "exit_reason", "bars_held"])

    atr_col = str(getattr(args, "atr_column", "atr_14"))
    target_mult = float(getattr(args, "target_atr_multiplier", 1.5))
    stop_mult = float(getattr(args, "stop_atr_multiplier", 2.0))
    horizon_bars = int(getattr(args, "horizon_bars", 4))

    fee_total_frac = (2.0 * float(getattr(args, "fee_bps_per_side", 0.0))) / 10000.0
    slippage_total_frac = float(getattr(args, "slippage_bps_total", 0.0)) / 10000.0
    tx_cost_frac = fee_total_frac + slippage_total_frac

    records: list[dict[str, Any]] = []

    for idx in entry_idx:
        atr_value = float(df.iloc[idx].get(atr_col, np.nan))
        entry_price = float(df.iloc[idx]["close"])
        if not np.isfinite(entry_price) or entry_price <= 0.0:
            continue

        # If ATR is missing/invalid, revert this entry to timeout logic.
        use_timeout_only = (not np.isfinite(atr_value)) or (atr_value <= 0.0)

        tp_price = entry_price + (target_mult * atr_value)
        sl_price = entry_price - (stop_mult * atr_value)

        end_idx = min(len(df) - 1, idx + max(1, horizon_bars))
        exit_idx = end_idx
        exit_price = float(df.iloc[end_idx]["close"])
        exit_reason = "timeout"

        if not use_timeout_only:
            for j in range(idx + 1, end_idx + 1):
                high_k = float(df.iloc[j]["high"])
                low_k = float(df.iloc[j]["low"])
                hit_stop = low_k <= sl_price
                hit_target = high_k >= tp_price

                if hit_stop and hit_target:
                    exit_idx = j
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
                if hit_stop:
                    exit_idx = j
                    exit_price = sl_price
                    exit_reason = "stop_loss"
                    break
                if hit_target:
                    exit_idx = j
                    exit_price = tp_price
                    exit_reason = "take_profit"
                    break

        gross_edge = (exit_price - entry_price) / entry_price
        net_edge = gross_edge - tx_cost_frac
        pnl_usd = float(getattr(args, "notional_usd", 1000.0)) * net_edge
        bars_held = int(exit_idx - idx)

        records.append(
            {
                "timestamp": df.iloc[idx].get("timestamp"),
                "net_edge": net_edge,
                "pnl_usd": pnl_usd,
                "exit_reason": exit_reason,
                "bars_held": bars_held,
            }
        )

    if not records:
        return pd.DataFrame(columns=["timestamp", "net_edge", "pnl_usd", "exit_reason", "bars_held"])

    return pd.DataFrame.from_records(records)


def command_backtest(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    db_path = Path(args.registry_db)

    files = sorted(input_dir.glob("kraken_*_labels.parquet"))
    if not files:
        raise RuntimeError(f"No label parquet files found in {input_dir}")

    ensure_crypto_registry_schema(db_path)

    summary: dict[str, Any] = {
        "stage": "backtest",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "notional_usd": args.notional_usd,
        "signal_volume_threshold": args.signal_volume_threshold,
        "signal_score_threshold": args.signal_score_threshold,
        "cooldown_bars": args.cooldown_bars,
        "feature_version": args.feature_version,
        "registry_db": str(db_path),
        "runs": [],
    }

    for file in files:
        run_report = run_backtest_from_labeled_file(
            file=file,
            args=args,
            output_dir=output_dir,
            db_path=db_path,
        )
        summary["runs"].append(run_report)

    summary_file = output_dir / "manifest_backtest.json"
    ensure_parent(summary_file)
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Backtest manifest written: {summary_file}")
    print(f"Registry updated: {db_path}")


def run_backtest_from_labeled_df(df: pd.DataFrame, source_file: Path, args: argparse.Namespace, output_dir: Path, db_path: Path) -> dict[str, Any]:
    if df.empty:
        return {}

    signal_mask = build_signal_mask(
        df=df,
        volume_threshold=args.signal_volume_threshold,
        score_threshold=args.signal_score_threshold,
    )
    accepted_mask = apply_cooldown(signal_mask, cooldown_bars=args.cooldown_bars)
    use_atr_exit = bool(getattr(args, "use_atr_exit", False))
    if use_atr_exit:
        trades = simulate_trades_with_atr_exit(df=df, accepted_mask=accepted_mask, args=args)
    else:
        trades = df.loc[accepted_mask].copy()

    symbol = str(df["symbol"].iloc[0]) if "symbol" in df.columns else source_file.stem
    timeframe_min = int(df["timeframe_min"].iloc[0]) if "timeframe_min" in df.columns else 15

    exit_mode = "atr_path" if use_atr_exit else "timeout"

    if trades.empty:
        net_pnl = 0.0
        win_rate = 0.0
        profit_factor = 0.0
        max_drawdown = 0.0
        avg_pnl = 0.0
        wins = 0
        losses = 0
        trade_count = 0
        recovery_factor = 0.0
        max_consecutive_losses = 0
        avg_loss_streak = 0.0
        avg_tuw_bars = 0.0
        max_tuw_bars = 0
        loss_cluster_count = 0
        avg_loss_cluster_size = 0.0
    else:
        if "pnl_usd" not in trades.columns:
            trades["pnl_usd"] = args.notional_usd * trades["net_edge"]
        trades["is_win"] = (trades["pnl_usd"] > 0).astype(int)
        trades["is_loss"] = (trades["pnl_usd"] < 0).astype(int)
        trades["cum_pnl"] = trades["pnl_usd"].cumsum()

        trade_count = int(len(trades))
        wins = int(trades["is_win"].sum())
        losses = int(trades["is_loss"].sum())
        net_pnl = float(trades["pnl_usd"].sum())
        avg_pnl = float(trades["pnl_usd"].mean())
        win_rate = float(wins / trade_count) if trade_count else 0.0

        gross_win = float(trades.loc[trades["pnl_usd"] > 0, "pnl_usd"].sum())
        gross_loss = float(-trades.loc[trades["pnl_usd"] < 0, "pnl_usd"].sum())
        if gross_loss > 0:
            profit_factor = gross_win / gross_loss
        elif gross_win > 0:
            profit_factor = float("inf")
        else:
            profit_factor = 0.0

        max_drawdown = compute_max_drawdown(trades["cum_pnl"])
        recovery_factor = (net_pnl / abs(max_drawdown)) if max_drawdown < 0 else 0.0
        max_consecutive_losses, avg_loss_streak = consecutive_loss_stats(trades["pnl_usd"])
        avg_tuw_bars, max_tuw_bars = time_under_water_stats(trades["cum_pnl"])
        loss_cluster_count, avg_loss_cluster_size = drawdown_cluster_stats(
            trades_df=trades,
            cluster_gap_bars=args.loss_cluster_gap_bars,
        )

        if args.export_equity_csv:
            equity = build_equity_frame(trades)
            equity_file = output_dir / f"equity_{safe_symbol_name(symbol)}_{args.horizon_bars}h_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
            ensure_parent(equity_file)
            equity[["timestamp", "pnl_usd", "cum_pnl", "running_peak", "drawdown", "is_win", "is_loss"]].to_csv(
                equity_file,
                index=False,
            )

    run_id = f"crypto_{safe_symbol_name(symbol)}_{args.horizon_bars}h_{uuid4().hex[:12]}"
    report_file = output_dir / f"{run_id}.json"
    ensure_parent(report_file)

    run_report = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "timeframe_min": timeframe_min,
        "feature_version": args.feature_version,
        "fee_bps_per_side": args.fee_bps_per_side,
        "slippage_bps_total": args.slippage_bps_total,
        "notional_usd": args.notional_usd,
        "signal_volume_threshold": args.signal_volume_threshold,
        "signal_score_threshold": args.signal_score_threshold,
        "horizon_bars": args.horizon_bars,
        "cooldown_bars": args.cooldown_bars,
        "trades": trade_count,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "net_pnl": net_pnl,
        "avg_pnl_per_trade": avg_pnl,
        "max_drawdown": max_drawdown,
        "recovery_factor": recovery_factor,
        "max_consecutive_losses": max_consecutive_losses,
        "avg_loss_streak": avg_loss_streak,
        "avg_tuw_bars": avg_tuw_bars,
        "max_tuw_bars": max_tuw_bars,
        "loss_cluster_count": loss_cluster_count,
        "avg_loss_cluster_size": avg_loss_cluster_size,
        "exit_mode": exit_mode,
        "target_atr_multiplier": float(getattr(args, "target_atr_multiplier", 0.0)),
        "stop_atr_multiplier": float(getattr(args, "stop_atr_multiplier", 0.0)),
        "atr_column": str(getattr(args, "atr_column", "")),
        "input_file": str(source_file),
        "report_file": str(report_file),
        "notes": args.notes,
    }
    report_file.write_text(json.dumps(run_report, indent=2), encoding="utf-8")
    write_registry_row(db_path, run_report)

    pf_str = "inf" if math.isinf(profit_factor) else f"{profit_factor:.3f}"
    print(
        f"Backtest {symbol} h={args.horizon_bars}: trades={trade_count}, win_rate={win_rate:.2%}, "
        f"pf={pf_str}, net_pnl={net_pnl:.2f}, max_consec_losses={max_consecutive_losses}, "
        f"max_tuw_bars={max_tuw_bars} -> {report_file}"
    )
    return run_report


def run_backtest_for_labeled_file(file: Path, args: argparse.Namespace, output_dir: Path, db_path: Path) -> dict[str, Any]:
    df = load_parquet(file)
    return run_backtest_from_labeled_df(df=df, source_file=file, args=args, output_dir=output_dir, db_path=db_path)


def command_backtest_batch(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    db_path = Path(args.registry_db)
    files = sorted(input_dir.glob("kraken_*_features.parquet"))
    if not files:
        raise RuntimeError(f"No feature parquet files found in {input_dir}")

    horizons = [int(item) for item in str(args.horizons).split(",") if item.strip()]
    ensure_crypto_registry_schema(db_path)

    batch_summary: dict[str, Any] = {
        "stage": "backtest-batch",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "horizons": horizons,
        "runs": [],
    }

    for horizon in horizons:
        for file in files:
            local_args = argparse.Namespace(**vars(args))
            local_args.horizon_bars = horizon
            local_args.feature_version = f"{args.feature_version}_h{horizon}"
            local_args.notes = f"{args.notes} horizon={horizon}".strip()
            features_df = load_parquet(file)
            labeled_df = add_labels(
                features_df,
                horizon_bars=horizon,
                cost_model=CostModel(
                    fee_bps_per_side=args.fee_bps_per_side,
                    slippage_bps_total=args.slippage_bps_total,
                ),
            )
            run_report = run_backtest_from_labeled_df(
                df=labeled_df,
                source_file=file,
                args=local_args,
                output_dir=output_dir,
                db_path=db_path,
            )
            if run_report:
                batch_summary["runs"].append(run_report)

    manifest_file = output_dir / "manifest_backtest_batch.json"
    ensure_parent(manifest_file)
    manifest_file.write_text(json.dumps(batch_summary, indent=2), encoding="utf-8")
    print(f"Batch backtest manifest written: {manifest_file}")
    print(f"Registry updated: {db_path}")


def command_backtest_strategy(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    db_path = Path(args.registry_db)
    config_path = Path(args.strategy_config)

    files = sorted(input_dir.glob("kraken_*_features.parquet"))
    if not files:
        raise RuntimeError(f"No feature parquet files found in {input_dir}")

    strategy_config = load_strategy_config(config_path)
    ensure_crypto_registry_schema(db_path)

    summary: dict[str, Any] = {
        "stage": "backtest-strategy",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "strategy_config": str(config_path),
        "runs": [],
    }

    for file in files:
        features_df = load_parquet(file)
        if features_df.empty:
            continue

        symbol = str(features_df["symbol"].iloc[0]) if "symbol" in features_df.columns else file.stem
        policy = resolve_strategy_policy(symbol, strategy_config, args)

        # Regime override: if --apply-regime, swap policy fields based on current bar regime
        active_regime: str | None = None
        active_regime_cfg: dict[str, Any] = {}
        if getattr(args, "apply_regime", False):
            regime_dir = Path(getattr(args, "regime_dir", "data/crypto/regime"))
            active_regime = _load_current_regime(symbol, regime_dir)
            if active_regime:
                regime_cfg = strategy_config.get("regimes", {}) or {}
                active_regime_cfg = regime_cfg.get(active_regime, {}) or {}
                policy = _apply_regime_to_policy(policy, active_regime, regime_cfg)
                print(f"[regime] {symbol}: active_regime={active_regime}  horizon={policy.horizon_bars}  score_thr={policy.signal_score_threshold}")
            else:
                print(f"[regime] {symbol}: no regime parquet found in {regime_dir}; using static policy")

        local_args = argparse.Namespace(**vars(args))
        local_args.horizon_bars = policy.horizon_bars
        local_args.signal_volume_threshold = policy.signal_volume_threshold
        local_args.signal_score_threshold = policy.signal_score_threshold
        local_args.cooldown_bars = policy.cooldown_bars
        local_args.use_atr_exit = bool(getattr(args, "use_atr_exit", False) or active_regime_cfg.get("use_atr_exit", False))
        local_args.atr_column = str(active_regime_cfg.get("atr_column", "atr_14"))
        local_args.atr_period = int(active_regime_cfg.get("atr_period", 14))
        # CLI args take priority over regime config when explicitly provided (not None)
        cli_tp = getattr(args, "target_atr_multiplier", None)
        cli_sl = getattr(args, "stop_atr_multiplier", None)
        local_args.target_atr_multiplier = float(cli_tp if cli_tp is not None else active_regime_cfg.get("target_atr_multiplier", 1.5))
        local_args.stop_atr_multiplier = float(cli_sl if cli_sl is not None else active_regime_cfg.get("stop_atr_multiplier", 2.0))
        local_args.feature_version = f"{args.feature_version}_{safe_symbol_name(symbol)}_h{policy.horizon_bars}"
        local_args.notes = f"{args.notes} strategy_config={config_path.name}".strip()

        labeled_df = add_labels(
            features_df,
            horizon_bars=policy.horizon_bars,
            cost_model=CostModel(
                fee_bps_per_side=args.fee_bps_per_side,
                slippage_bps_total=args.slippage_bps_total,
            ),
        )
        run_report = run_backtest_from_labeled_df(
            df=labeled_df,
            source_file=file,
            args=local_args,
            output_dir=output_dir,
            db_path=db_path,
        )
        if run_report:
            run_report["strategy_policy"] = {
                "symbol": policy.symbol,
                "horizon_bars": policy.horizon_bars,
                "signal_volume_threshold": policy.signal_volume_threshold,
                "signal_score_threshold": policy.signal_score_threshold,
                "cooldown_bars": policy.cooldown_bars,
                "active_regime": active_regime,
                "use_atr_exit": bool(getattr(local_args, "use_atr_exit", False)),
                "atr_column": str(getattr(local_args, "atr_column", "atr_14")),
                "target_atr_multiplier": float(getattr(local_args, "target_atr_multiplier", 1.5)),
                "stop_atr_multiplier": float(getattr(local_args, "stop_atr_multiplier", 2.0)),
            }
            summary["runs"].append(run_report)

    manifest_file = output_dir / "manifest_backtest_strategy.json"
    ensure_parent(manifest_file)
    manifest_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Strategy backtest manifest written: {manifest_file}")
    print(f"Registry updated: {db_path}")

    # Fee-sensitivity sweep: ±5 bps on each side
    if getattr(args, "fee_sensitivity", False):
        base_fee = args.fee_bps_per_side
        base_slip = args.slippage_bps_total
        scenarios = [
            ("base", base_fee, base_slip),
            ("+5bps", base_fee + 5.0, base_slip),
            ("-5bps", max(0.0, base_fee - 5.0), base_slip),
            ("+5bps_slip", base_fee, base_slip + 5.0),
            ("-5bps_slip", base_fee, max(0.0, base_slip - 5.0)),
        ]
        sensitivity_rows: list[dict[str, Any]] = []
        for scenario_name, fee, slip in scenarios:
            scenario_runs: list[dict[str, Any]] = []
            for file in files:
                features_df = load_parquet(file)
                if features_df.empty:
                    continue
                symbol = str(features_df["symbol"].iloc[0]) if "symbol" in features_df.columns else file.stem
                policy = resolve_strategy_policy(symbol, strategy_config, args)
                active_regime2: str | None = None
                active_regime_cfg2: dict[str, Any] = {}
                if getattr(args, "apply_regime", False):
                    regime_dir2 = Path(getattr(args, "regime_dir", "data/crypto/regime"))
                    active_regime2 = _load_current_regime(symbol, regime_dir2)
                    if active_regime2:
                        regime_cfg2 = strategy_config.get("regimes", {}) or {}
                        active_regime_cfg2 = regime_cfg2.get(active_regime2, {}) or {}
                        policy = _apply_regime_to_policy(policy, active_regime2, regime_cfg2)
                local_args2 = argparse.Namespace(**vars(args))
                local_args2.horizon_bars = policy.horizon_bars
                local_args2.signal_volume_threshold = policy.signal_volume_threshold
                local_args2.signal_score_threshold = policy.signal_score_threshold
                local_args2.cooldown_bars = policy.cooldown_bars
                local_args2.use_atr_exit = bool(getattr(args, "use_atr_exit", False) or active_regime_cfg2.get("use_atr_exit", False))
                local_args2.atr_column = str(active_regime_cfg2.get("atr_column", "atr_14"))
                local_args2.atr_period = int(active_regime_cfg2.get("atr_period", 14))
                cli_tp2 = getattr(args, "target_atr_multiplier", None)
                cli_sl2 = getattr(args, "stop_atr_multiplier", None)
                local_args2.target_atr_multiplier = float(cli_tp2 if cli_tp2 is not None else active_regime_cfg2.get("target_atr_multiplier", 1.5))
                local_args2.stop_atr_multiplier = float(cli_sl2 if cli_sl2 is not None else active_regime_cfg2.get("stop_atr_multiplier", 2.0))
                local_args2.fee_bps_per_side = fee
                local_args2.slippage_bps_total = slip
                local_args2.feature_version = f"{args.feature_version}_{safe_symbol_name(symbol)}_h{policy.horizon_bars}_fee{scenario_name}"
                local_args2.notes = f"{args.notes} fee_scenario={scenario_name}".strip()
                labeled_df2 = add_labels(
                    features_df,
                    horizon_bars=policy.horizon_bars,
                    cost_model=CostModel(fee_bps_per_side=fee, slippage_bps_total=slip),
                )
                run2 = run_backtest_from_labeled_df(
                    df=labeled_df2,
                    source_file=file,
                    args=local_args2,
                    output_dir=output_dir,
                    db_path=db_path,
                )
                if run2:
                    scenario_runs.append(
                        {
                            "symbol": symbol,
                            "active_regime": active_regime2,
                            "horizon_bars": policy.horizon_bars,
                            "use_atr_exit": bool(getattr(local_args2, "use_atr_exit", False)),
                            **{k: run2.get(k) for k in ["profit_factor", "win_rate", "trades", "net_pnl", "max_drawdown", "recovery_factor"]},
                        }
                    )
            sensitivity_rows.append({"scenario": scenario_name, "fee_bps_per_side": fee, "slippage_bps_total": slip, "symbols": scenario_runs})
        sensitivity_manifest = output_dir / "manifest_fee_sensitivity.json"
        sensitivity_manifest.write_text(json.dumps({"stage": "fee-sensitivity", "base_fee_bps": base_fee, "base_slippage_bps": base_slip, "scenarios": sensitivity_rows}, indent=2), encoding="utf-8")
        print(f"Fee sensitivity manifest written: {sensitivity_manifest}")
        _print_fee_sensitivity_table(sensitivity_rows)


def _print_fee_sensitivity_table(sensitivity_rows: list[dict[str, Any]]) -> None:
    print("\nFee Sensitivity Summary")
    print(f"  {'Scenario':<16} {'Symbol':<12} {'PF':>6} {'WR%':>7} {'NetPnL':>10} {'MaxDD':>10}")
    print("  " + "-" * 66)
    for row in sensitivity_rows:
        for sym in row.get("symbols", []):
            pf = sym.get("profit_factor")
            wr = sym.get("win_rate")
            net = sym.get("net_pnl")
            dd = sym.get("max_drawdown")
            pf_str = f"{pf:.3f}" if pf is not None else "  n/a"
            wr_str = f"{wr * 100:.1f}%" if wr is not None else "  n/a"
            net_str = f"{net:+.2f}" if net is not None else "  n/a"
            dd_str = f"{dd:.4f}" if dd is not None else "  n/a"
            print(f"  {row['scenario']:<16} {sym.get('symbol', ''):<12} {pf_str:>6} {wr_str:>7} {net_str:>10} {dd_str:>10}")


def command_fetch_archive(args: argparse.Namespace) -> None:
    symbols = parse_symbols(args.symbols)
    archive_root = Path(args.trades_output_dir)
    output_dir = Path(args.output_dir)

    summary: dict[str, Any] = {
        "stage": "fetch-archive",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "exchange": "kraken",
        "source": "trades",
        "timeframe_min": args.timeframe,
        "bars_requested": args.bars,
        "symbols": symbols,
        "archive_root": str(archive_root),
        "outputs": [],
    }

    for symbol in symbols:
        archive_df_existing = load_trade_archive(symbol, archive_root)
        trade_gaps = audit_trade_tape_gaps(archive_df_existing, gap_threshold_seconds=args.trade_gap_threshold_seconds)
        gap_entries = trade_gaps.get("gaps", []) or []

        earliest_trade, high_water_mark = archive_trade_bounds(symbol, archive_root)
        latest_partition = (
            trade_archive_partition_path(archive_root, symbol, high_water_mark)
            if high_water_mark is not None
            else None
        )
        now_utc = datetime.now(timezone.utc)
        target_lookback_days = args.target_lookback_days or args.bootstrap_lookback_days
        target_start = pd.Timestamp(now_utc - pd.Timedelta(days=target_lookback_days))

        until_ns: int | None = None
        backfill_complete = True
        if gap_entries:
            gap_start = pd.Timestamp(gap_entries[0]["start"])
            gap_end = pd.Timestamp(gap_entries[0]["end"])
            if gap_start.tzinfo is None:
                gap_start = gap_start.tz_localize("UTC")
            else:
                gap_start = gap_start.tz_convert("UTC")
            if gap_end.tzinfo is None:
                gap_end = gap_end.tz_localize("UTC")
            else:
                gap_end = gap_end.tz_convert("UTC")
            since_ts = gap_start
            until_ns = int(gap_end.value)
            high_water_iso = high_water_mark.isoformat() if high_water_mark is not None else None
            gap_seconds = float((gap_end.value - gap_start.value) / 1_000_000_000)
            fetch_mode = "gap-repair"
            earliest_trade_iso = earliest_trade.isoformat() if earliest_trade is not None else None
        elif high_water_mark is None:
            since_ts = target_start
            high_water_iso = None
            gap_seconds = None
            fetch_mode = "bootstrap"
            earliest_trade_iso = None
        else:
            earliest_trade_iso = earliest_trade.isoformat() if earliest_trade is not None else None
            high_water_iso = high_water_mark.isoformat()
            gap_seconds = float((pd.Timestamp(now_utc).value - high_water_mark.value) / 1_000_000_000)
            if earliest_trade is not None and target_start < earliest_trade:
                since_ts = target_start
                until_ns = int(earliest_trade.value)
                fetch_mode = "backfill"
            else:
                since_ts = high_water_mark
                fetch_mode = "resume"

        if since_ts.tzinfo is None:
            since_ts = since_ts.tz_localize("UTC")
        else:
            since_ts = since_ts.tz_convert("UTC")

        since_ns = int(since_ts.value)
        trades_df, pages, final_cursor, reached_until = fetch_kraken_trades(
            symbol=symbol,
            since_ns=since_ns,
            max_pages=args.max_pages,
            sleep_seconds=args.sleep_seconds,
            max_retries=args.max_retries,
            until_ns=until_ns,
        )
        if until_ns is not None:
            backfill_complete = reached_until

        archive_df = upsert_trade_archive(trades_df, archive_root=archive_root, symbol=symbol)
        bars_df = trades_to_ohlcv(archive_df, timeframe_min=args.timeframe, symbol=symbol)
        if len(bars_df) > args.bars:
            bars_df = bars_df.tail(args.bars).reset_index(drop=True)

        out_file = output_dir / f"kraken_{safe_symbol_name(symbol)}_{args.timeframe}m_raw.parquet"
        write_parquet(bars_df, out_file)

        partition_files = []
        symbol_dir = trade_archive_symbol_dir(archive_root, symbol)
        if symbol_dir.exists():
            partition_files = sorted(str(path) for path in symbol_dir.glob("*.parquet"))

        summary["outputs"].append(
            {
                "symbol": symbol,
                "fetch_mode": fetch_mode,
                "earliest_trade": earliest_trade_iso,
                "high_water_mark": high_water_iso,
                "gap_seconds": gap_seconds,
                "bars_rows": len(bars_df),
                "trades_rows_fetched": int(len(trades_df)),
                "trades_archive_rows": int(len(archive_df)),
                "trade_pages": int(pages),
                "last_cursor_ns": int(final_cursor),
                "target_cursor_ns": int(until_ns) if until_ns is not None else None,
                "target_reached": backfill_complete,
                "archive_partitions": partition_files,
                "latest_partition": str(latest_partition) if latest_partition else None,
                "output": str(out_file),
                "start": bars_df["timestamp"].iloc[0].isoformat(),
                "end": bars_df["timestamp"].iloc[-1].isoformat(),
            }
        )
        completeness = "complete" if backfill_complete else "incomplete"
        print(
            f"Archived {symbol}: mode={fetch_mode}, status={completeness}, fetched={len(trades_df)} trades, "
            f"archive_total={len(archive_df)} -> {out_file}"
        )

    manifest = output_dir / "manifest_fetch_archive.json"
    ensure_parent(manifest)
    manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Archive manifest written: {manifest}")


def _build_continuity_map(archive_df: pd.DataFrame, timeframe_min: int, width: int = 72) -> dict[str, Any]:
    """Build a fixed-width ASCII block map of trade-tape coverage."""
    if archive_df.empty:
        return {"map": "-" * width, "legend": "[no data]", "start": None, "end": None, "coverage_pct": 0.0}

    ts = pd.to_datetime(archive_df["timestamp"], utc=True).sort_values()
    total_start = ts.iloc[0]
    total_end = ts.iloc[-1]
    span_ns = total_end.value - total_start.value
    if span_ns <= 0:
        return {"map": "#" * width, "legend": f"[{total_start.isoformat()} — {total_end.isoformat()}]", "start": total_start.isoformat(), "end": total_end.isoformat(), "coverage_pct": 100.0}

    bucket_ns = span_ns / width
    diffs = ts.diff().dropna()
    gap_threshold_ns = int(pd.Timedelta(minutes=timeframe_min * 4).value)  # 4-bar silence = gap in map
    gap_ranges: list[tuple[int, int]] = []
    for idx in diffs[diffs > pd.Timedelta(nanoseconds=gap_threshold_ns)].index:
        g_start = ts.iloc[ts.index.get_loc(idx) - 1].value
        g_end = ts.at[idx].value
        gap_ranges.append((g_start, g_end))

    chars = []
    gap_buckets = 0
    for i in range(width):
        b_start = total_start.value + int(i * bucket_ns)
        b_end = total_start.value + int((i + 1) * bucket_ns)
        in_gap = any(g_s < b_end and g_e > b_start for g_s, g_e in gap_ranges)
        if in_gap:
            chars.append(".")
            gap_buckets += 1
        else:
            chars.append("#")
    coverage_pct = round(100.0 * (width - gap_buckets) / width, 1)
    legend = (
        f"{total_start.strftime('%Y-%m-%d')} "
        f"[{'#' * 6}=data, {'.' * 6}=gap, {width} cols] "
        f"{total_end.strftime('%Y-%m-%d')} {coverage_pct}% covered"
    )
    return {
        "map": "".join(chars),
        "legend": legend,
        "start": total_start.isoformat(),
        "end": total_end.isoformat(),
        "coverage_pct": coverage_pct,
    }


def command_audit_archive(args: argparse.Namespace) -> None:
    archive_root = Path(args.trades_output_dir)
    output_dir = Path(args.output_dir)
    symbols = parse_symbols(args.symbols)

    summary: dict[str, Any] = {
        "stage": "audit-archive",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "archive_root": str(archive_root),
        "timeframe_min": args.timeframe,
        "trade_gap_threshold_seconds": args.trade_gap_threshold_seconds,
        "symbols": symbols,
        "outputs": [],
    }

    for symbol in symbols:
        archive_df = load_trade_archive(symbol, archive_root)
        trade_gaps = audit_trade_tape_gaps(archive_df, gap_threshold_seconds=args.trade_gap_threshold_seconds)
        bars_df = trades_to_ohlcv(archive_df, timeframe_min=args.timeframe, symbol=symbol) if not archive_df.empty else pd.DataFrame()
        bar_gaps = audit_bar_gaps(bars_df, timeframe_min=args.timeframe) if not bars_df.empty else {
            "bar_count": 0,
            "expected_bar_count": 0,
            "missing_bar_count": 0,
            "gaps": [],
        }

        continuity_map = _build_continuity_map(archive_df, timeframe_min=args.timeframe)
        result = {
            "symbol": symbol,
            "trade_archive_rows": int(len(archive_df)),
            "trade_gaps": trade_gaps,
            "bar_gaps": bar_gaps,
            "continuity_map": continuity_map,
        }
        summary["outputs"].append(result)
        print(f"  {symbol}: {continuity_map['legend']}")
        print(f"  {continuity_map['map']}")

    manifest = output_dir / "manifest_archive_audit.json"
    ensure_parent(manifest)
    manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Archive audit written: {manifest}")


def classify_integrity_status(result: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    trade_archive_rows = int(result.get("trade_archive_rows", 0))
    trade_gaps = result.get("trade_gaps", {})
    bar_gaps = result.get("bar_gaps", {})

    if trade_archive_rows == 0:
        reasons.append("no_trade_archive")
        return "red", reasons

    if int(trade_gaps.get("gap_count", 0)) > 0:
        reasons.append("trade_gap_detected")
        return "red", reasons

    if int(bar_gaps.get("missing_bar_count", 0)) > 0:
        reasons.append("bar_gap_detected")
        return "yellow", reasons

    reasons.append("artifact_grade")
    return "green", reasons


def evaluate_symbol_integrity(symbol: str, archive_root: Path, timeframe_min: int, trade_gap_threshold_seconds: float) -> dict[str, Any]:
    archive_df = load_trade_archive(symbol, archive_root)
    trade_gaps = audit_trade_tape_gaps(archive_df, gap_threshold_seconds=trade_gap_threshold_seconds)
    bars_df = trades_to_ohlcv(archive_df, timeframe_min=timeframe_min, symbol=symbol) if not archive_df.empty else pd.DataFrame()
    bar_gaps = audit_bar_gaps(bars_df, timeframe_min=timeframe_min) if not bars_df.empty else {
        "bar_count": 0,
        "expected_bar_count": 0,
        "missing_bar_count": 0,
        "gaps": [],
    }

    result = {
        "symbol": symbol,
        "trade_archive_rows": int(len(archive_df)),
        "trade_gaps": trade_gaps,
        "bar_gaps": bar_gaps,
    }
    status, reasons = classify_integrity_status(result)
    result["status"] = status
    result["reasons"] = reasons
    return result


def attempt_symbol_recovery(
    symbol: str,
    result: dict[str, Any],
    archive_root: Path,
    raw_output_dir: Path,
    timeframe_min: int,
    bars: int,
    max_pages: int,
    sleep_seconds: float,
    max_retries: int,
    bootstrap_lookback_days: int,
    overlap_seconds: int,
) -> dict[str, Any]:
    trade_gaps = result.get("trade_gaps", {})
    gaps = trade_gaps.get("gaps", []) or []

    if gaps:
        anchor = pd.Timestamp(gaps[0]["start"])
        reason = "trade_gap_detected"
        if anchor.tzinfo is None:
            anchor = anchor.tz_localize("UTC")
        else:
            anchor = anchor.tz_convert("UTC")
        since_ts = anchor - pd.Timedelta(seconds=overlap_seconds)
    else:
        since_ts = pd.Timestamp(datetime.now(timezone.utc) - pd.Timedelta(days=bootstrap_lookback_days))
        reason = "bootstrap_missing_archive"

    trades_df, pages, final_cursor, _ = fetch_kraken_trades(
        symbol=symbol,
        since_ns=int(since_ts.value),
        max_pages=max_pages,
        sleep_seconds=sleep_seconds,
        max_retries=max_retries,
    )
    archive_df = upsert_trade_archive(trades_df, archive_root=archive_root, symbol=symbol)

    refresh = None
    if not archive_df.empty:
        refresh = refresh_symbol_bars_from_archive(
            symbol=symbol,
            archive_root=archive_root,
            timeframe_min=timeframe_min,
            bars=bars,
            output_dir=raw_output_dir,
        )

    return {
        "triggered": True,
        "reason": reason,
        "since_utc": since_ts.isoformat(),
        "overlap_seconds": overlap_seconds,
        "trades_rows_fetched": int(len(trades_df)),
        "trade_pages": int(pages),
        "last_cursor_ns": int(final_cursor),
        "trade_archive_rows_after": int(len(archive_df)),
        "bar_refresh": refresh,
    }


def refresh_symbol_bars_from_archive(symbol: str, archive_root: Path, timeframe_min: int, bars: int, output_dir: Path) -> dict[str, Any]:
    archive_df = load_trade_archive(symbol, archive_root)
    if archive_df.empty:
        raise RuntimeError(f"No archive data available to refresh bars for {symbol}")

    bars_df = trades_to_ohlcv(archive_df, timeframe_min=timeframe_min, symbol=symbol)
    if len(bars_df) > bars:
        bars_df = bars_df.tail(bars).reset_index(drop=True)

    out_file = output_dir / f"kraken_{safe_symbol_name(symbol)}_{timeframe_min}m_raw.parquet"
    write_parquet(bars_df, out_file)
    return {
        "symbol": symbol,
        "output": str(out_file),
        "rows": int(len(bars_df)),
        "start": bars_df["timestamp"].iloc[0].isoformat(),
        "end": bars_df["timestamp"].iloc[-1].isoformat(),
    }


def command_training_gate(args: argparse.Namespace) -> None:
    archive_root = Path(args.trades_output_dir)
    output_dir = Path(args.output_dir)
    raw_output_dir = Path(args.raw_output_dir)
    symbols = parse_symbols(args.symbols)

    summary: dict[str, Any] = {
        "stage": "training-gate",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": symbols,
        "trade_gap_threshold_seconds": args.trade_gap_threshold_seconds,
        "timeframe_min": args.timeframe,
        "auto_refresh_bars": args.auto_refresh_bars,
        "attempt_recovery": args.attempt_recovery,
        "results": [],
    }

    saw_red = False
    for symbol in symbols:
        result = evaluate_symbol_integrity(
            symbol=symbol,
            archive_root=archive_root,
            timeframe_min=args.timeframe,
            trade_gap_threshold_seconds=args.trade_gap_threshold_seconds,
        )

        if result["status"] == "yellow" and args.auto_refresh_bars:
            refresh = refresh_symbol_bars_from_archive(
                symbol=symbol,
                archive_root=archive_root,
                timeframe_min=args.timeframe,
                bars=args.bars,
                output_dir=raw_output_dir,
            )
            refreshed_bars_df = load_parquet(Path(refresh["output"]))
            refreshed_bar_gaps = audit_bar_gaps(refreshed_bars_df, timeframe_min=args.timeframe)
            result["bar_refresh"] = refresh
            result["bar_gaps_after_refresh"] = refreshed_bar_gaps
            if int(refreshed_bar_gaps.get("missing_bar_count", 0)) == 0:
                result["status"] = "green"
                result["reasons"] = ["bar_gap_detected", "auto_refreshed", "artifact_grade"]

        if result["status"] == "red" and args.attempt_recovery:
            recovery_attempt = attempt_symbol_recovery(
                symbol=symbol,
                result=result,
                archive_root=archive_root,
                raw_output_dir=raw_output_dir,
                timeframe_min=args.timeframe,
                bars=args.bars,
                max_pages=args.recovery_max_pages,
                sleep_seconds=args.recovery_sleep_seconds,
                max_retries=args.recovery_max_retries,
                bootstrap_lookback_days=args.recovery_bootstrap_lookback_days,
                overlap_seconds=args.recovery_overlap_seconds,
            )
            result["recovery_attempt"] = recovery_attempt
            reevaluated = evaluate_symbol_integrity(
                symbol=symbol,
                archive_root=archive_root,
                timeframe_min=args.timeframe,
                trade_gap_threshold_seconds=args.trade_gap_threshold_seconds,
            )
            result["status_after_recovery"] = reevaluated["status"]
            result["reasons_after_recovery"] = reevaluated["reasons"]
            result["trade_gaps_after_recovery"] = reevaluated["trade_gaps"]
            result["bar_gaps_after_recovery"] = reevaluated["bar_gaps"]
            if reevaluated["status"] != "red":
                result["status"] = reevaluated["status"]
                result["reasons"] = reevaluated["reasons"]
                result["trade_archive_rows"] = reevaluated["trade_archive_rows"]
                result["trade_gaps"] = reevaluated["trade_gaps"]
                result["bar_gaps"] = reevaluated["bar_gaps"]
            else:
                result["reasons"] = result["reasons"] + ["recovery_failed"]

        if result["status"] == "red":
            saw_red = True

        summary["results"].append(result)
        print(f"Training gate {symbol}: status={result['status']} reasons={','.join(result['reasons'])}")

    manifest = output_dir / "manifest_training_gate.json"
    ensure_parent(manifest)
    manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Training gate written: {manifest}")

    if saw_red:
        raise RuntimeError("Training gate failed: one or more symbols are red")


def command_fetch(args: argparse.Namespace) -> None:
    symbols = parse_symbols(args.symbols)
    source = str(args.source).lower()

    since_ns: int | None = None
    if source == "trades":
        if args.since_utc:
            since_ts = pd.Timestamp(args.since_utc)
            if since_ts.tzinfo is None:
                since_ts = since_ts.tz_localize("UTC")
            else:
                since_ts = since_ts.tz_convert("UTC")
            since_ns = int(since_ts.value)
        else:
            lookback_seconds = int(args.bars * args.timeframe * 60)
            since_ns = int((time.time() - lookback_seconds) * 1_000_000_000)

    summary: dict[str, Any] = {
        "stage": "fetch",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "exchange": "kraken",
        "source": source,
        "timeframe_min": args.timeframe,
        "bars_requested": args.bars,
        "symbols": symbols,
        "outputs": [],
    }

    if since_ns is not None:
        summary["since_ns"] = since_ns

    for symbol in symbols:
        extra: dict[str, Any] = {}
        if source == "ohlc":
            df = fetch_kraken_ohlc(symbol=symbol, timeframe_min=args.timeframe, bars=args.bars)
        elif source == "trades":
            assert since_ns is not None
            trades_df, pages, final_cursor, _ = fetch_kraken_trades(
                symbol=symbol,
                since_ns=since_ns,
                max_pages=args.max_pages,
                sleep_seconds=args.sleep_seconds,
                max_retries=args.max_retries,
            )
            if trades_df.empty:
                raise RuntimeError(f"No trade tape returned for {symbol}; try an older --since-utc")

            if args.archive_trades:
                archive_root = Path(args.trades_output_dir)
                archive_df = upsert_trade_archive(trades_df, archive_root=archive_root, symbol=symbol)
                trade_source_df = archive_df
                extra["trades_archive_root"] = str(archive_root)
                extra["trades_archive_partitions"] = [str(path) for path in sorted(trade_archive_symbol_dir(archive_root, symbol).glob("*.parquet"))]
                extra["trades_archive_rows"] = int(len(archive_df))
            else:
                trade_source_df = trades_df

            df = trades_to_ohlcv(
                trades_df=trade_source_df,
                timeframe_min=args.timeframe,
                symbol=symbol,
            )
            extra["trades_rows_fetched"] = int(len(trades_df))
            extra["trade_pages"] = int(pages)
            extra["last_cursor_ns"] = int(final_cursor)
        else:
            raise RuntimeError(f"Unsupported fetch source: {source}")

        if len(df) > args.bars:
            df = df.tail(args.bars).reset_index(drop=True)

        out_file = Path(args.output_dir) / f"kraken_{symbol.replace('/', '_')}_{args.timeframe}m_raw.parquet"
        write_parquet(df, out_file)
        output_entry = {
            "symbol": symbol,
            "rows": len(df),
            "output": str(out_file),
            "start": df["timestamp"].iloc[0].isoformat(),
            "end": df["timestamp"].iloc[-1].isoformat(),
        }
        output_entry.update(extra)
        summary["outputs"].append(output_entry)
        print(f"Fetched {symbol} ({source}): {len(df)} rows -> {out_file}")

    manifest = Path(args.output_dir) / "manifest_fetch.json"
    ensure_parent(manifest)
    manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Fetch manifest written: {manifest}")


def command_features(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    files = sorted(input_dir.glob("kraken_*_raw.parquet"))
    if not files:
        raise RuntimeError(f"No raw parquet files found in {input_dir}")

    summary: dict[str, Any] = {
        "stage": "features",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "outputs": [],
    }

    for file in files:
        df = load_parquet(file)
        if "timeframe_min" not in df.columns:
            raise RuntimeError(f"Missing timeframe_min in {file}")
        timeframe_min = int(df["timeframe_min"].iloc[0])
        feats = add_features(df, timeframe_min=timeframe_min)
        feats = baseline_breakout_volume_score(feats)
        out_file = output_dir / file.name.replace("_raw.parquet", "_features.parquet")
        write_parquet(feats, out_file)
        summary["outputs"].append({
            "input": str(file),
            "output": str(out_file),
            "rows": len(feats),
        })
        print(f"Features {file.name}: {len(feats)} rows -> {out_file}")

    manifest = output_dir / "manifest_features.json"
    ensure_parent(manifest)
    manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Feature manifest written: {manifest}")


def command_labels(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    files = sorted(input_dir.glob("kraken_*_features.parquet"))
    if not files:
        raise RuntimeError(f"No feature parquet files found in {input_dir}")

    cost_model = CostModel(
        fee_bps_per_side=args.fee_bps_per_side,
        slippage_bps_total=args.slippage_bps_total,
    )

    summary: dict[str, Any] = {
        "stage": "labels",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "horizon_bars": args.horizon_bars,
        "cost_model": {
            "fee_bps_per_side": args.fee_bps_per_side,
            "slippage_bps_total": args.slippage_bps_total,
        },
        "outputs": [],
    }

    for file in files:
        df = load_parquet(file)
        labeled = add_labels(df, horizon_bars=args.horizon_bars, cost_model=cost_model)
        out_file = output_dir / file.name.replace("_features.parquet", "_labels.parquet")
        write_parquet(labeled, out_file)
        tradeable_ratio = float(labeled["tradeable_long"].mean()) if len(labeled) else 0.0
        summary["outputs"].append({
            "input": str(file),
            "output": str(out_file),
            "rows": len(labeled),
            "tradeable_long_ratio": tradeable_ratio,
        })
        print(f"Labels {file.name}: {len(labeled)} rows (tradeable={tradeable_ratio:.2%}) -> {out_file}")

    manifest = output_dir / "manifest_labels.json"
    ensure_parent(manifest)
    manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Label manifest written: {manifest}")


def command_split(args: argparse.Namespace) -> None:
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    files = sorted(input_dir.glob("kraken_*_labels.parquet"))
    if not files:
        raise RuntimeError(f"No label parquet files found in {input_dir}")

    summary: dict[str, Any] = {
        "stage": "split",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "train_months": args.train_months,
        "validate_months": args.validate_months,
        "test_months": args.test_months,
        "outputs": [],
    }

    for file in files:
        df = load_parquet(file)
        windows = generate_walkforward_windows(
            timestamps=df["timestamp"],
            train_months=args.train_months,
            validate_months=args.validate_months,
            test_months=args.test_months,
        )

        symbol = str(df["symbol"].iloc[0]) if "symbol" in df.columns and not df.empty else file.stem
        symbol_safe = symbol.replace("/", "_")
        symbol_dir = output_dir / symbol_safe
        symbol_dir.mkdir(parents=True, exist_ok=True)

        split_index: list[dict[str, Any]] = []
        for idx, window in enumerate(windows, start=1):
            train_start = pd.Timestamp(window["train_start"])
            train_end = pd.Timestamp(window["train_end"])
            val_start = pd.Timestamp(window["validate_start"])
            val_end = pd.Timestamp(window["validate_end"])
            test_start = pd.Timestamp(window["test_start"])
            test_end = pd.Timestamp(window["test_end"])

            train_df = df[(df["timestamp"] >= train_start) & (df["timestamp"] < train_end)]
            val_df = df[(df["timestamp"] >= val_start) & (df["timestamp"] < val_end)]
            test_df = df[(df["timestamp"] >= test_start) & (df["timestamp"] < test_end)]

            train_file = symbol_dir / f"window_{idx:02d}_train.parquet"
            val_file = symbol_dir / f"window_{idx:02d}_validate.parquet"
            test_file = symbol_dir / f"window_{idx:02d}_test.parquet"

            write_parquet(train_df, train_file)
            write_parquet(val_df, val_file)
            write_parquet(test_df, test_file)

            split_index.append(
                {
                    "window": idx,
                    "train_rows": int(len(train_df)),
                    "validate_rows": int(len(val_df)),
                    "test_rows": int(len(test_df)),
                    "train_file": str(train_file),
                    "validate_file": str(val_file),
                    "test_file": str(test_file),
                    "window_bounds": window,
                }
            )

        index_file = symbol_dir / "split_index.json"
        index_file.write_text(json.dumps(split_index, indent=2), encoding="utf-8")

        summary["outputs"].append(
            {
                "input": str(file),
                "symbol": symbol,
                "windows": len(windows),
                "split_index": str(index_file),
            }
        )
        print(f"Split {file.name}: windows={len(windows)} -> {index_file}")

    manifest = output_dir / "manifest_split.json"
    ensure_parent(manifest)
    manifest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Split manifest written: {manifest}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crypto data pipeline for Kraken: fetch, features, labels, split, backtest"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_fetch = subparsers.add_parser("fetch", help="Fetch raw OHLCV from Kraken or resample from trade tape")
    p_fetch.add_argument("--symbols", default="BTC/USD,ETH/USD", help="Comma-separated symbols")
    p_fetch.add_argument("--timeframe", type=int, default=15, help="Candle timeframe in minutes")
    p_fetch.add_argument("--bars", type=int, default=1000, help="Bars per symbol")
    p_fetch.add_argument("--source", choices=["ohlc", "trades"], default="ohlc", help="Data source mode")
    p_fetch.add_argument("--since-utc", default="", help="Trades mode start time (UTC ISO), optional")
    p_fetch.add_argument("--max-pages", type=int, default=250, help="Max Kraken Trades pages per symbol")
    p_fetch.add_argument("--sleep-seconds", type=float, default=1.2, help="Sleep between Trades pages")
    p_fetch.add_argument("--max-retries", type=int, default=4, help="Retries per Trades page on rate limits")
    p_fetch.add_argument("--archive-trades", action="store_true", help="Persist and upsert raw trades archive parquet")
    p_fetch.add_argument("--trades-output-dir", default="data/crypto/raw_trades", help="Raw trade archive directory")
    p_fetch.add_argument("--output-dir", default="data/crypto/raw", help="Raw output directory")
    p_fetch.set_defaults(func=command_fetch)

    p_fetch_archive = subparsers.add_parser("fetch-archive", help="Resume from local trades archive high-water mark and refresh bars")
    p_fetch_archive.add_argument("--symbols", default="BTC/USD,ETH/USD", help="Comma-separated symbols")
    p_fetch_archive.add_argument("--timeframe", type=int, default=15, help="Candle timeframe in minutes")
    p_fetch_archive.add_argument("--bars", type=int, default=1000, help="Bars per symbol")
    p_fetch_archive.add_argument("--max-pages", type=int, default=250, help="Max Kraken Trades pages per symbol")
    p_fetch_archive.add_argument("--sleep-seconds", type=float, default=1.2, help="Sleep between Trades pages")
    p_fetch_archive.add_argument("--max-retries", type=int, default=4, help="Retries per Trades page on rate limits")
    p_fetch_archive.add_argument("--bootstrap-lookback-days", type=int, default=10, help="Fallback lookback when archive is empty")
    p_fetch_archive.add_argument("--target-lookback-days", type=int, default=0, help="Backfill target depth in days when archive already exists")
    p_fetch_archive.add_argument("--trade-gap-threshold-seconds", type=float, default=1800.0, help="Gap size that triggers gap-repair mode before resume/backfill")
    p_fetch_archive.add_argument("--trades-output-dir", default="data/crypto/raw_trades", help="Partitioned raw trade archive root")
    p_fetch_archive.add_argument("--output-dir", default="data/crypto/raw", help="Raw bar output directory")
    p_fetch_archive.set_defaults(func=command_fetch_archive)

    p_features = subparsers.add_parser("features", help="Build feature parquet from raw data")
    p_features.add_argument("--input-dir", default="data/crypto/raw", help="Raw input directory")
    p_features.add_argument("--output-dir", default="data/crypto/features", help="Feature output directory")
    p_features.set_defaults(func=command_features)

    p_labels = subparsers.add_parser("labels", help="Create cost-aware labels")
    p_labels.add_argument("--input-dir", default="data/crypto/features", help="Feature input directory")
    p_labels.add_argument("--output-dir", default="data/crypto/labels", help="Label output directory")
    p_labels.add_argument("--horizon-bars", type=int, default=4, help="Label horizon in bars")
    p_labels.add_argument("--fee-bps-per-side", type=float, default=10.0, help="Fee bps per side")
    p_labels.add_argument("--slippage-bps-total", type=float, default=5.0, help="Total slippage bps")
    p_labels.set_defaults(func=command_labels)

    p_split = subparsers.add_parser("split", help="Generate walk-forward train/validate/test datasets")
    p_split.add_argument("--input-dir", default="data/crypto/labels", help="Label input directory")
    p_split.add_argument("--output-dir", default="data/crypto/splits", help="Split output directory")
    p_split.add_argument("--train-months", type=int, default=3, help="Train window in months")
    p_split.add_argument("--validate-months", type=int, default=1, help="Validation window in months")
    p_split.add_argument("--test-months", type=int, default=1, help="Test window in months")
    p_split.set_defaults(func=command_split)

    p_backtest = subparsers.add_parser("backtest", help="Run baseline breakout-volume backtest and log registry")
    p_backtest.add_argument("--input-dir", default="data/crypto/labels", help="Label input directory")
    p_backtest.add_argument("--output-dir", default="reports/crypto/backtests", help="Backtest report output directory")
    p_backtest.add_argument("--registry-db", default="reports/crypto/crypto_experiments.db", help="SQLite registry path")
    p_backtest.add_argument("--notional-usd", type=float, default=1000.0, help="Fixed notional per trade")
    p_backtest.add_argument("--signal-volume-threshold", type=float, default=1.5, help="Minimum volume intensity")
    p_backtest.add_argument("--signal-score-threshold", type=float, default=0.001, help="Minimum baseline score")
    p_backtest.add_argument("--fee-bps-per-side", type=float, default=10.0, help="Fee bps per side")
    p_backtest.add_argument("--slippage-bps-total", type=float, default=5.0, help="Total slippage bps")
    p_backtest.add_argument("--horizon-bars", type=int, default=4, help="Trade horizon in bars")
    p_backtest.add_argument("--cooldown-bars", type=int, default=4, help="Minimum bars between entries")
    p_backtest.add_argument("--loss-cluster-gap-bars", type=int, default=6, help="Bars used to group nearby losses")
    p_backtest.add_argument("--feature-version", default="crypto_v1", help="Feature/version tag for registry")
    p_backtest.add_argument("--notes", default="", help="Optional run notes")
    p_backtest.add_argument("--export-equity-csv", action="store_true", help="Export per-trade equity curve CSV")
    p_backtest.add_argument("--use-atr-exit", action="store_true", help="Enable path-dependent ATR TP/SL exits")
    p_backtest.add_argument("--atr-column", default="atr_14", help="ATR column name used for dynamic exits")
    p_backtest.add_argument("--atr-period", type=int, default=14, help="ATR lookback period metadata")
    p_backtest.add_argument("--target-atr-multiplier", type=float, default=1.5, help="TP distance in ATR multiples")
    p_backtest.add_argument("--stop-atr-multiplier", type=float, default=2.0, help="SL distance in ATR multiples")
    p_backtest.set_defaults(func=command_backtest)

    p_backtest_batch = subparsers.add_parser("backtest-batch", help="Run multiple backtest horizons and log each to the registry")
    p_backtest_batch.add_argument("--input-dir", default="data/crypto/features", help="Feature input directory")
    p_backtest_batch.add_argument("--output-dir", default="reports/crypto/backtests", help="Backtest report output directory")
    p_backtest_batch.add_argument("--registry-db", default="reports/crypto/crypto_experiments.db", help="SQLite registry path")
    p_backtest_batch.add_argument("--notional-usd", type=float, default=1000.0, help="Fixed notional per trade")
    p_backtest_batch.add_argument("--signal-volume-threshold", type=float, default=1.5, help="Minimum volume intensity")
    p_backtest_batch.add_argument("--signal-score-threshold", type=float, default=0.001, help="Minimum baseline score")
    p_backtest_batch.add_argument("--fee-bps-per-side", type=float, default=10.0, help="Fee bps per side")
    p_backtest_batch.add_argument("--slippage-bps-total", type=float, default=5.0, help="Total slippage bps")
    p_backtest_batch.add_argument("--cooldown-bars", type=int, default=4, help="Minimum bars between entries")
    p_backtest_batch.add_argument("--loss-cluster-gap-bars", type=int, default=6, help="Bars used to group nearby losses")
    p_backtest_batch.add_argument("--feature-version", default="crypto_v1_batch", help="Feature/version tag base for registry")
    p_backtest_batch.add_argument("--notes", default="", help="Optional run notes")
    p_backtest_batch.add_argument("--export-equity-csv", action="store_true", help="Export per-trade equity curve CSV")
    p_backtest_batch.add_argument("--horizons", default="4,8,12", help="Comma-separated horizon bars to test")
    p_backtest_batch.set_defaults(func=command_backtest_batch)

    p_backtest_strategy = subparsers.add_parser("backtest-strategy", help="Run config-driven per-symbol horizon and threshold backtests")
    p_backtest_strategy.add_argument("--input-dir", default="data/crypto/features", help="Feature input directory")
    p_backtest_strategy.add_argument("--output-dir", default="reports/crypto/backtests", help="Backtest report output directory")
    p_backtest_strategy.add_argument("--registry-db", default="reports/crypto/crypto_experiments.db", help="SQLite registry path")
    p_backtest_strategy.add_argument("--strategy-config", default="configs/crypto_strategy.yaml", help="YAML strategy config path")
    p_backtest_strategy.add_argument("--notional-usd", type=float, default=1000.0, help="Fixed notional per trade")
    p_backtest_strategy.add_argument("--signal-volume-threshold", type=float, default=1.5, help="Default minimum volume intensity")
    p_backtest_strategy.add_argument("--signal-score-threshold", type=float, default=0.001, help="Default minimum baseline score")
    p_backtest_strategy.add_argument("--fee-bps-per-side", type=float, default=10.0, help="Fee bps per side")
    p_backtest_strategy.add_argument("--slippage-bps-total", type=float, default=5.0, help="Total slippage bps")
    p_backtest_strategy.add_argument("--horizon-bars", type=int, default=4, help="Default trade horizon in bars")
    p_backtest_strategy.add_argument("--cooldown-bars", type=int, default=4, help="Default minimum bars between entries")
    p_backtest_strategy.add_argument("--loss-cluster-gap-bars", type=int, default=6, help="Bars used to group nearby losses")
    p_backtest_strategy.add_argument("--feature-version", default="crypto_strategy", help="Feature/version tag base for registry")
    p_backtest_strategy.add_argument("--notes", default="", help="Optional run notes")
    p_backtest_strategy.add_argument("--export-equity-csv", action="store_true", help="Export per-trade equity curve CSV")
    p_backtest_strategy.add_argument("--fee-sensitivity", action="store_true", help="Run ±5bps fee and slippage sensitivity sweep")
    p_backtest_strategy.add_argument("--apply-regime", action="store_true", help="Override per-symbol policy from regime-classify output (requires data/crypto/regime/ parquets)")
    p_backtest_strategy.add_argument("--regime-dir", default="data/crypto/regime", help="Directory containing regime parquets written by regime-classify")
    p_backtest_strategy.add_argument("--use-atr-exit", action="store_true", help="Enable path-dependent ATR TP/SL exits")
    p_backtest_strategy.add_argument("--atr-column", default="atr_14", help="ATR column name used for dynamic exits")
    p_backtest_strategy.add_argument("--atr-period", type=int, default=14, help="ATR lookback period metadata")
    p_backtest_strategy.add_argument("--target-atr-multiplier", type=float, default=None, help="TP distance in ATR multiples (overrides regime config when set)")
    p_backtest_strategy.add_argument("--stop-atr-multiplier", type=float, default=None, help="SL distance in ATR multiples (overrides regime config when set)")
    p_backtest_strategy.set_defaults(func=command_backtest_strategy)

    p_audit_archive = subparsers.add_parser("audit-archive", help="Audit local trade archive for timestamp and bar gaps")
    p_audit_archive.add_argument("--symbols", default="BTC/USD,ETH/USD", help="Comma-separated symbols")
    p_audit_archive.add_argument("--timeframe", type=int, default=15, help="Candle timeframe in minutes")
    p_audit_archive.add_argument("--trade-gap-threshold-seconds", type=float, default=1800.0, help="Gap threshold for trade-tape audit")
    p_audit_archive.add_argument("--trades-output-dir", default="data/crypto/raw_trades", help="Partitioned raw trade archive root")
    p_audit_archive.add_argument("--output-dir", default="reports/crypto/integrity", help="Audit report output directory")
    p_audit_archive.set_defaults(func=command_audit_archive)

    p_training_gate = subparsers.add_parser("training-gate", help="Preflight integrity gate before training or feature generation")
    p_training_gate.add_argument("--symbols", default="BTC/USD,ETH/USD", help="Comma-separated symbols")
    p_training_gate.add_argument("--timeframe", type=int, default=15, help="Candle timeframe in minutes")
    p_training_gate.add_argument("--bars", type=int, default=12000, help="Bars to refresh when auto-fixing yellow state")
    p_training_gate.add_argument("--trade-gap-threshold-seconds", type=float, default=1800.0, help="Red-light threshold for trade tape gaps")
    p_training_gate.add_argument("--auto-refresh-bars", action="store_true", help="Refresh raw bars from archive when only bar gaps exist")
    p_training_gate.add_argument("--attempt-recovery", action="store_true", help="Attempt one targeted fetch for red symbols before failing")
    p_training_gate.add_argument("--recovery-max-pages", type=int, default=25, help="Max pages for a single recovery attempt")
    p_training_gate.add_argument("--recovery-sleep-seconds", type=float, default=1.2, help="Sleep between recovery pages")
    p_training_gate.add_argument("--recovery-max-retries", type=int, default=4, help="Retries per recovery page on rate limits")
    p_training_gate.add_argument("--recovery-bootstrap-lookback-days", type=int, default=3, help="Fallback lookback when red due to missing archive")
    p_training_gate.add_argument("--recovery-overlap-seconds", type=int, default=300, help="Overlap before the first detected gap when attempting recovery")
    p_training_gate.add_argument("--trades-output-dir", default="data/crypto/raw_trades", help="Partitioned raw trade archive root")
    p_training_gate.add_argument("--raw-output-dir", default="data/crypto/raw", help="Raw bar output directory for auto-refresh")
    p_training_gate.add_argument("--output-dir", default="reports/crypto/integrity", help="Gate report output directory")
    p_training_gate.set_defaults(func=command_training_gate)

    # ── regime-classify ─────────────────────────────────────────────────────
    p_regime = subparsers.add_parser(
        "regime-classify",
        help="Classify OHLCV bars into market regimes (mean_reversion / momentum_trend / liquidity_void)",
    )
    p_regime.add_argument("--symbols", default="", help="Comma-separated symbol filter. Empty = all found.")
    p_regime.add_argument("--input-dir", default="data/crypto/features", help="Feature parquet directory")
    p_regime.add_argument("--output-dir", default="data/crypto/regime", help="Regime parquet + summary output directory")
    p_regime.add_argument("--window", type=int, default=96, help="Rolling window in bars (default 96 = 24 h at 15-min)")
    p_regime.add_argument("--park-void-pct", type=float, default=95.0, help="Expanding-quantile pct for liquidity-void threshold")
    p_regime.add_argument("--park-trend-pct", type=float, default=70.0, help="Expanding-quantile pct for momentum-trend threshold")
    p_regime.add_argument("--min-volume-intensity", type=float, default=0.15, help="Volume-intensity floor for liquidity-void detection")
    p_regime.add_argument("--no-summary", dest="summary", action="store_false", default=True, help="Suppress regime summary table")
    p_regime.add_argument("--no-write-parquet", dest="write_parquet", action="store_false", default=True, help="Skip writing regime parquet")
    p_regime.set_defaults(func=_command_regime_classify)

    return parser


def _command_regime_classify(args: argparse.Namespace) -> None:
    """Bridge: load classify_market_regime module and delegate."""
    import importlib.util, sys as _sys
    spec = importlib.util.spec_from_file_location(
        "classify_market_regime",
        Path(__file__).with_name("classify_market_regime.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot locate classify_market_regime.py alongside this script")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    mod.command_classify(args)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
