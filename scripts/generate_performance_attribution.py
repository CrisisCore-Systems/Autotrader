#!/usr/bin/env python3
"""
Phase 4: Multi-Asset Performance Attribution Reporting
=======================================================
Reads the trade_ledger and crypto_runs / portfolio_runs tables to produce
three attribution slices:

  A. Correlation State Efficiency  – PnL / win-rate / profit-factor by corr_regime
  B. Sizing Efficiency Matrix      – realized PnL vs theoretical unscaled PnL
  C. Routing Efficiency            – capital cost of gated (blocked) signals

Outputs:
  1. attribution_report_<RUN_ID>.json  – machine-readable matrices
  2. Terminal Markdown summary          – human-readable table print

Usage:
    python scripts/generate_performance_attribution.py \
        --db reports/crypto/crypto_experiments_collision_test.db \
        --output-dir reports/crypto/attribution
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def load_trade_ledger(db_path: Path, portfolio_run_id: str | None = None) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        # Verify trade_ledger exists
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "trade_ledger" not in tables:
            return pd.DataFrame()
        if portfolio_run_id:
            df = pd.read_sql_query(
                "SELECT * FROM trade_ledger WHERE portfolio_run_id = ?",
                conn,
                params=(portfolio_run_id,),
            )
        else:
            df = pd.read_sql_query("SELECT * FROM trade_ledger", conn)
        return df
    finally:
        conn.close()


def load_crypto_runs(db_path: Path, run_ids: list[str] | None = None) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "crypto_runs" not in tables:
            return pd.DataFrame()
        if run_ids:
            placeholders = ",".join("?" * len(run_ids))
            df = pd.read_sql_query(f"SELECT * FROM crypto_runs WHERE run_id IN ({placeholders})", conn, params=run_ids)
        else:
            df = pd.read_sql_query("SELECT * FROM crypto_runs", conn)
        return df
    finally:
        conn.close()


def load_portfolio_runs(db_path: Path) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "portfolio_runs" not in tables:
            return pd.DataFrame()
        return pd.read_sql_query("SELECT * FROM portfolio_runs", conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Slice A: Correlation State Attribution
# ---------------------------------------------------------------------------

def compute_corr_regime_attribution(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Group realized PnL, win-rate, and profit factor by corr_regime and symbol.
    Returns a DataFrame with one row per (symbol, corr_regime) pair.
    """
    if trades.empty:
        return pd.DataFrame()

    def regime_stats(g: pd.DataFrame) -> pd.Series:
        n = len(g)
        wins = int((g["pnl_usd"] > 0).sum())
        losses = int((g["pnl_usd"] < 0).sum())
        gross_win = float(g.loc[g["pnl_usd"] > 0, "pnl_usd"].sum())
        gross_loss = float(-g.loc[g["pnl_usd"] < 0, "pnl_usd"].sum())
        pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
        return pd.Series({
            "trades": n,
            "wins": wins,
            "losses": losses,
            "win_rate": wins / n if n else 0.0,
            "net_pnl": float(g["pnl_usd"].sum()),
            "avg_pnl": float(g["pnl_usd"].mean()),
            "profit_factor": pf,
            "avg_bars_held": float(g["bars_held"].mean()) if "bars_held" in g.columns else 0.0,
            "avg_scale_factor": float(g["bps_scale_factor"].mean()) if "bps_scale_factor" in g.columns else 1.0,
        })

    by_symbol_regime = trades.groupby(["symbol", "corr_regime"]).apply(regime_stats).reset_index()
    portfolio_totals = trades.groupby("corr_regime").apply(regime_stats).reset_index()
    portfolio_totals.insert(0, "symbol", "PORTFOLIO")

    return pd.concat([by_symbol_regime, portfolio_totals], ignore_index=True)


# ---------------------------------------------------------------------------
# Slice B: Sizing Efficiency Matrix
# ---------------------------------------------------------------------------

def compute_sizing_efficiency(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Compare realized PnL (with BPS scaling) vs theoretical unscaled PnL.
    
    sizing_efficiency = realized_pnl / unscaled_pnl
    capital_saved     = unscaled_pnl - realized_pnl  (positive = saved from losses)
    """
    if trades.empty:
        return pd.DataFrame()

    t = trades.copy()
    t["net_edge"] = pd.to_numeric(t["net_edge"], errors="coerce").fillna(0.0)
    t["unscaled_notional"] = pd.to_numeric(t["unscaled_notional"], errors="coerce").fillna(1000.0)
    t["scaled_notional"] = pd.to_numeric(t["scaled_notional"], errors="coerce").fillna(t["unscaled_notional"])
    t["pnl_usd"] = pd.to_numeric(t["pnl_usd"], errors="coerce").fillna(0.0)

    t["unscaled_pnl"] = t["unscaled_notional"] * t["net_edge"]
    t["capital_saved"] = t["unscaled_pnl"] - t["pnl_usd"]

    def eff_stats(g: pd.DataFrame) -> pd.Series:
        realized = float(g["pnl_usd"].sum())
        unscaled = float(g["unscaled_pnl"].sum())
        saved = float(g["capital_saved"].sum())
        efficiency = realized / unscaled if abs(unscaled) > 1e-9 else float("nan")
        return pd.Series({
            "trades": len(g),
            "realized_pnl": realized,
            "unscaled_pnl": unscaled,
            "capital_saved_from_haircut": saved,
            "sizing_efficiency": efficiency,
            "avg_scale_factor": float(g["bps_scale_factor"].mean()),
        })

    by_symbol = t.groupby("symbol").apply(eff_stats).reset_index()
    by_regime = t.groupby("corr_regime").apply(eff_stats).reset_index()
    by_regime.insert(0, "symbol", "ALL")

    return pd.concat(
        [by_symbol.assign(breakdown="by_symbol"), by_regime.assign(breakdown="by_corr_regime")],
        ignore_index=True,
    )


# ---------------------------------------------------------------------------
# Slice C: Routing Efficiency (Gating Opportunity Cost)
# ---------------------------------------------------------------------------

def compute_routing_efficiency(portfolio_runs: pd.DataFrame, trades: pd.DataFrame) -> dict[str, Any]:
    """
    Analyze gating costs. Since we don't have gated trade records (gated signals
    were blocked before execution), we compute:
    - How many signals were gated per portfolio run
    - What % of total candidate signals were blocked
    - Portfolio-level PnL decomposition by symbol rank
    """
    if portfolio_runs.empty:
        return {}

    result: dict[str, Any] = {}

    for _, pr in portfolio_runs.iterrows():
        run_id = str(pr["portfolio_run_id"])
        gated = int(pr.get("gated_signals_count", 0))
        total = int(pr.get("total_trades", 0))
        total_candidates = total + gated
        gate_rate = gated / total_candidates if total_candidates > 0 else 0.0

        # Per-symbol PnL decomposition for this portfolio run
        symbol_pnl: dict[str, Any] = {}
        if not trades.empty and "portfolio_run_id" in trades.columns:
            run_trades = trades[trades["portfolio_run_id"] == run_id]
            if not run_trades.empty:
                for sym, g in run_trades.groupby("symbol"):
                    gross_win = float(g.loc[g["pnl_usd"] > 0, "pnl_usd"].sum())
                    gross_loss = float(-g.loc[g["pnl_usd"] < 0, "pnl_usd"].sum())
                    pf = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
                    symbol_pnl[str(sym)] = {
                        "trades": len(g),
                        "net_pnl": float(g["pnl_usd"].sum()),
                        "win_rate": float((g["pnl_usd"] > 0).mean()),
                        "profit_factor": pf,
                        "avg_scale_factor": float(g["bps_scale_factor"].mean()),
                    }

        result[run_id] = {
            "portfolio_run_id": run_id,
            "coordination_mode": str(pr.get("coordination_mode", "")),
            "max_simultaneous_assets": int(pr.get("max_simultaneous_assets", 1)),
            "total_executed_trades": total,
            "gated_signals_count": gated,
            "total_candidate_signals": total_candidates,
            "gate_rate_pct": round(gate_rate * 100, 2),
            "portfolio_net_pnl": float(pr.get("portfolio_net_pnl", 0.0)),
            "portfolio_profit_factor": float(pr.get("portfolio_profit_factor", 0.0)),
            "symbol_pnl_decomposition": symbol_pnl,
        }

    return result


# ---------------------------------------------------------------------------
# Terminal renderer
# ---------------------------------------------------------------------------

def _pf_str(v: float) -> str:
    if math.isinf(v):
        return "inf"
    if math.isnan(v):
        return "N/A"
    return f"{v:.3f}"


def render_terminal_report(
    corr_attr: pd.DataFrame,
    sizing_eff: pd.DataFrame,
    routing_eff: dict[str, Any],
    run_id: str,
) -> str:
    lines: list[str] = []
    sep = "=" * 76

    lines += [
        "",
        sep,
        f"  PHASE 4 ATTRIBUTION REPORT  [{run_id}]",
        f"  Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}",
        sep,
    ]

    # --- Slice A ---
    lines += [
        "",
        "  A. CORRELATION STATE ATTRIBUTION",
        "  " + "-" * 74,
        f"  {'Symbol':<14} {'Regime':<26} {'Trades':>6} {'WinRate':>8} {'PF':>7} {'NetPnL':>10} {'AvgScale':>9}",
        "  " + "-" * 74,
    ]
    if not corr_attr.empty:
        for _, row in corr_attr.iterrows():
            sym = str(row.get("symbol", "?"))[:14]
            regime = str(row.get("corr_regime", "?"))[:26]
            n = int(row.get("trades", 0))
            wr = f"{row.get('win_rate', 0):.1%}"
            pf = _pf_str(float(row.get("profit_factor", 0)))
            pnl = float(row.get("net_pnl", 0))
            pnl_str = f"{'+' if pnl >= 0 else ''}{pnl:.2f}"
            scale = float(row.get("avg_scale_factor", 1.0))
            lines.append(
                f"  {sym:<14} {regime:<26} {n:>6} {wr:>8} {pf:>7} {pnl_str:>10} {scale:>9.4f}"
            )
    else:
        lines.append("  (no trade_ledger data – run backtest with updated pipeline)")

    # --- Slice B ---
    lines += [
        "",
        "  B. SIZING EFFICIENCY MATRIX",
        "  " + "-" * 74,
        f"  {'Breakdown':<14} {'Key':<26} {'Realized':>10} {'Unscaled':>10} {'Saved':>10} {'Eff%':>7}",
        "  " + "-" * 74,
    ]
    if not sizing_eff.empty:
        for _, row in sizing_eff.iterrows():
            brk = str(row.get("breakdown", ""))[:14]
            key = str(row.get("symbol", row.get("corr_regime", "?")))[:26]
            realized = float(row.get("realized_pnl", 0))
            unscaled = float(row.get("unscaled_pnl", 0))
            saved = float(row.get("capital_saved_from_haircut", 0))
            eff = row.get("sizing_efficiency", float("nan"))
            eff_str = f"{eff:.1%}" if not (math.isnan(eff) or math.isinf(eff)) else "N/A"
            lines.append(
                f"  {brk:<14} {key:<26} {realized:>+10.2f} {unscaled:>+10.2f} {saved:>+10.2f} {eff_str:>7}"
            )
    else:
        lines.append("  (no trade_ledger data)")

    # --- Slice C ---
    lines += [
        "",
        "  C. ROUTING EFFICIENCY",
        "  " + "-" * 74,
    ]
    if routing_eff:
        for pr_id, info in routing_eff.items():
            lines += [
                f"  Portfolio Run : {pr_id}",
                f"  Mode          : {info['coordination_mode']}  (max_assets={info['max_simultaneous_assets']})",
                f"  Executed      : {info['total_executed_trades']} trades",
                f"  Gated         : {info['gated_signals_count']} signals  "
                f"({info['gate_rate_pct']:.1f}% of {info['total_candidate_signals']} candidates)",
                f"  Portfolio PnL : ${info['portfolio_net_pnl']:+.4f}   PF: {_pf_str(info['portfolio_profit_factor'])}",
            ]
            if info["symbol_pnl_decomposition"]:
                lines.append(f"  {'Symbol':<14} {'Trades':>6} {'NetPnL':>10} {'WinRate':>8} {'PF':>7} {'AvgScale':>9}")
                for sym, sd in info["symbol_pnl_decomposition"].items():
                    pnl = float(sd["net_pnl"])
                    lines.append(
                        f"  {sym:<14} {sd['trades']:>6} {pnl:>+10.2f} {sd['win_rate']:>8.1%} "
                        f"{_pf_str(sd['profit_factor']):>7} {sd['avg_scale_factor']:>9.4f}"
                    )
            lines.append("")
    else:
        lines.append("  (no portfolio_runs found)")

    lines.append(sep)
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main attribution builder
# ---------------------------------------------------------------------------

def generate_attribution(
    db_path: Path,
    output_dir: Path,
    portfolio_run_id: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    trades = load_trade_ledger(db_path, portfolio_run_id=portfolio_run_id)
    crypto_runs = load_crypto_runs(db_path)
    portfolio_runs = load_portfolio_runs(db_path)

    run_id = portfolio_run_id or f"attr_{uuid4().hex[:12]}"

    corr_attr = compute_corr_regime_attribution(trades)
    sizing_eff = compute_sizing_efficiency(trades)
    routing_eff = compute_routing_efficiency(portfolio_runs, trades)

    # Serialise DataFrames (convert inf/nan for JSON)
    def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
        records = []
        for rec in df.to_dict(orient="records"):
            clean: dict[str, Any] = {}
            for k, v in rec.items():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    clean[k] = None
                else:
                    clean[k] = v
            records.append(clean)
        return records

    attribution_doc: dict[str, Any] = {
        "report_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "portfolio_run_filter": portfolio_run_id,
        "trade_count": len(trades),
        "sliceA_corr_regime_attribution": _df_to_records(corr_attr),
        "sliceB_sizing_efficiency": _df_to_records(sizing_eff),
        "sliceC_routing_efficiency": routing_eff,
    }

    report_file = output_dir / f"attribution_report_{run_id}.json"
    report_file.write_text(json.dumps(attribution_doc, indent=2), encoding="utf-8")

    terminal_report = render_terminal_report(corr_attr, sizing_eff, routing_eff, run_id)
    print(terminal_report)

    txt_file = output_dir / f"attribution_summary_{run_id}.txt"
    txt_file.write_text(terminal_report, encoding="utf-8")

    print(f"  Attribution JSON : {report_file}")
    print(f"  Attribution Text : {txt_file}")

    return attribution_doc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4: Multi-Asset Performance Attribution")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("reports/crypto/crypto_experiments_phase3_validation.db"),
        help="SQLite database path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/crypto/attribution"),
        help="Output directory for attribution reports",
    )
    parser.add_argument(
        "--portfolio-run-id",
        type=str,
        default=None,
        help="Filter to a specific portfolio_run_id (omit for all runs)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERROR: Database not found: {args.db}")
        raise SystemExit(1)

    generate_attribution(
        db_path=args.db,
        output_dir=args.output_dir,
        portfolio_run_id=args.portfolio_run_id,
    )


if __name__ == "__main__":
    main()
