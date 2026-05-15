from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class AnalysisSummary:
    trace_file: str
    rows_total: int
    executed_rows: int
    cooldown_bars: int
    bar_seconds: float
    anomaly_a_count: int
    anomaly_b_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze cooldown leakage diagnostics from portfolio trace CSV")
    parser.add_argument(
        "--trace-file",
        default="reports/crypto/debug_cooldown_leak.csv",
        help="Path to cooldown trace CSV written by backtest-strategy --debug-cooldown-trace",
    )
    parser.add_argument(
        "--cooldown-bars",
        type=int,
        default=4,
        help="Configured cooldown bars used by the backtest run",
    )
    parser.add_argument(
        "--bar-minutes",
        type=float,
        default=None,
        help="Bar size in minutes (auto-inferred when omitted)",
    )
    parser.add_argument(
        "--violations-csv",
        default="",
        help="Optional output CSV path for anomaly rows",
    )
    parser.add_argument(
        "--summary-json",
        default="",
        help="Optional output JSON path for compact summary",
    )
    return parser.parse_args()


def _infer_bar_seconds(ts: pd.Series) -> float:
    unique_ts = ts.dropna().drop_duplicates().sort_values()
    if len(unique_ts) < 2:
        return 900.0
    deltas = unique_ts.diff().dropna().dt.total_seconds()
    deltas = deltas[deltas > 0]
    if deltas.empty:
        return 900.0
    return float(deltas.median())


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    required = {
        "timestamp",
        "symbol",
        "raw_signal",
        "effective_signal",
        "in_cooldown",
        "router_decision",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise RuntimeError(f"Trace file is missing columns: {', '.join(missing)}")

    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
    out["raw_signal"] = pd.to_numeric(out["raw_signal"], errors="coerce").fillna(0).astype(int)
    out["effective_signal"] = pd.to_numeric(out["effective_signal"], errors="coerce").fillna(0).astype(int)
    out["in_cooldown"] = pd.to_numeric(out["in_cooldown"], errors="coerce").fillna(0).astype(int)
    out["router_decision"] = out["router_decision"].fillna("").astype(str)
    out["csv_line"] = np.arange(len(out), dtype=int) + 2
    return out


def analyze_trace(df: pd.DataFrame, cooldown_bars: int, bar_seconds: float) -> tuple[pd.DataFrame, AnalysisSummary]:
    executed = df[df["router_decision"] == "executed"].copy()

    anomaly_a = executed[executed["in_cooldown"] == 1].copy()
    if not anomaly_a.empty:
        anomaly_a["anomaly_type"] = "A_executed_while_in_cooldown"
        anomaly_a["bars_since_prev_exec"] = np.nan

    by_symbol = []
    for symbol, group in executed.groupby("symbol", sort=True):
        g = group.sort_values("timestamp").copy()
        g["prev_exec_ts"] = g["timestamp"].shift(1)
        g["seconds_since_prev_exec"] = (g["timestamp"] - g["prev_exec_ts"]).dt.total_seconds()
        g["bars_since_prev_exec"] = g["seconds_since_prev_exec"] / max(bar_seconds, 1.0)
        g["symbol"] = symbol
        by_symbol.append(g)

    if by_symbol:
        exec_gaps = pd.concat(by_symbol, ignore_index=True)
    else:
        exec_gaps = executed.copy()
        exec_gaps["prev_exec_ts"] = pd.NaT
        exec_gaps["seconds_since_prev_exec"] = np.nan
        exec_gaps["bars_since_prev_exec"] = np.nan

    anomaly_b = exec_gaps[
        exec_gaps["bars_since_prev_exec"].notna() & (exec_gaps["bars_since_prev_exec"] < float(cooldown_bars))
    ].copy()
    if not anomaly_b.empty:
        anomaly_b["anomaly_type"] = "B_reentry_before_cooldown_window"

    violations = pd.concat([anomaly_a, anomaly_b], ignore_index=True, sort=False)
    if not violations.empty:
        violations = violations.sort_values(["timestamp", "symbol", "anomaly_type"]).reset_index(drop=True)

    summary = AnalysisSummary(
        trace_file="",
        rows_total=int(len(df)),
        executed_rows=int(len(executed)),
        cooldown_bars=int(cooldown_bars),
        bar_seconds=float(bar_seconds),
        anomaly_a_count=int(len(anomaly_a)),
        anomaly_b_count=int(len(anomaly_b)),
    )
    return violations, summary


def print_report(df: pd.DataFrame, violations: pd.DataFrame, summary: AnalysisSummary) -> None:
    decision_counts = df["router_decision"].replace("", "none").value_counts().sort_index()
    by_symbol = (
        df[
            df["router_decision"].isin(
                ["executed", "gated", "gated_cluster_window", "masked_by_cooldown"]
            )
        ]
        .groupby(["symbol", "router_decision"])
        .size()
        .unstack(fill_value=0)
        .sort_index()
    )

    print("\n" + "=" * 88)
    print("  COOLDOWN TRACE ANOMALY REPORT")
    print("=" * 88)
    print(f"trace_file      : {summary.trace_file}")
    print(f"rows_total      : {summary.rows_total}")
    print(f"executed_rows   : {summary.executed_rows}")
    print(f"cooldown_bars   : {summary.cooldown_bars}")
    print(f"bar_seconds     : {summary.bar_seconds:.2f}")
    print(f"anomaly_A_count : {summary.anomaly_a_count}")
    print(f"anomaly_B_count : {summary.anomaly_b_count}")

    print("\nDecision counts:")
    print(decision_counts.to_string())

    if not by_symbol.empty:
        print("\nPer-symbol decision counts:")
        print(by_symbol.to_string())

    if violations.empty:
        print("\nNo anomaly rows detected.")
        return

    preview_cols = [
        "csv_line",
        "timestamp",
        "symbol",
        "raw_signal",
        "effective_signal",
        "in_cooldown",
        "router_decision",
        "bars_since_prev_exec",
        "anomaly_type",
    ]
    existing_cols = [c for c in preview_cols if c in violations.columns]
    print("\nAnomaly preview (first 20 rows):")
    print(violations[existing_cols].head(20).to_string(index=False))


def main() -> None:
    args = parse_args()
    trace_path = Path(args.trace_file)
    if not trace_path.is_absolute():
        trace_path = (BASE_DIR / trace_path).resolve()
    if not trace_path.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_path}")

    df = pd.read_csv(trace_path)
    df = _normalize(df)
    if args.bar_minutes is not None:
        bar_seconds = float(args.bar_minutes) * 60.0
    else:
        bar_seconds = _infer_bar_seconds(df["timestamp"])

    violations, summary = analyze_trace(df, cooldown_bars=args.cooldown_bars, bar_seconds=bar_seconds)
    summary.trace_file = str(trace_path)
    print_report(df, violations, summary)

    if args.violations_csv:
        out_csv = Path(args.violations_csv)
        if not out_csv.is_absolute():
            out_csv = (BASE_DIR / out_csv).resolve()
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        violations.to_csv(out_csv, index=False)
        print(f"\nViolations CSV written: {out_csv}")

    if args.summary_json:
        out_json = Path(args.summary_json)
        if not out_json.is_absolute():
            out_json = (BASE_DIR / out_json).resolve()
        out_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trace_file": summary.trace_file,
            "rows_total": summary.rows_total,
            "executed_rows": summary.executed_rows,
            "cooldown_bars": summary.cooldown_bars,
            "bar_seconds": summary.bar_seconds,
            "anomaly_a_count": summary.anomaly_a_count,
            "anomaly_b_count": summary.anomaly_b_count,
        }
        out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Summary JSON written: {out_json}")


if __name__ == "__main__":
    main()