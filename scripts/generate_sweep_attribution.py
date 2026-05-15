from __future__ import annotations

import argparse
import itertools
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "reports/crypto/crypto_sweep_multimag4d.db"


def _parse_float_list(text: str) -> list[float]:
    out: list[float] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        out.append(float(chunk))
    if not out:
        raise argparse.ArgumentTypeError("Expected at least one float value")
    return list(dict.fromkeys(out))


def _parse_int_list(text: str) -> list[int]:
    out: list[int] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        out.append(int(chunk))
    if not out:
        raise argparse.ArgumentTypeError("Expected at least one integer value")
    return list(dict.fromkeys(out))


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _load_df_from_sweep_results(conn: sqlite3.Connection) -> pd.DataFrame:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(sweep_results)").fetchall()}
    has_lookback = "latency_lookback_bars" in columns
    has_cluster_gated = "gated_cluster_window_count" in columns
    lookback_expr = "latency_lookback_bars" if has_lookback else "0 AS latency_lookback_bars"
    cluster_expr = "gated_cluster_window_count" if has_cluster_gated else "0 AS gated_cluster_window_count"
    return pd.read_sql_query(
        f"""
        SELECT
            portfolio_run_id,
            gate_threshold,
            max_assets,
            high_corr_scale,
            execution_delay_bars,
            {lookback_expr},
            total_trades,
            gated_signals_count,
            {cluster_expr},
            portfolio_net_pnl,
            portfolio_profit_factor
        FROM sweep_results
        ORDER BY rowid ASC
        """,
        conn,
    )


def _reconstruct_df_from_portfolio_runs(
    conn: sqlite3.Connection,
    gates: list[float],
    assets: list[int],
    scales: list[float],
    delays: list[int],
    lookbacks: list[int],
) -> pd.DataFrame:
    raw = pd.read_sql_query(
        """
        SELECT
            rowid,
            portfolio_run_id,
            total_trades,
            gated_signals_count,
            0 AS gated_cluster_window_count,
            portfolio_net_pnl,
            portfolio_profit_factor
        FROM portfolio_runs
        ORDER BY rowid ASC
        """,
        conn,
    )
    if raw.empty:
        return raw

    grid = list(itertools.product(gates, assets, scales, delays, lookbacks))
    expected = len(grid)
    if expected <= 0:
        raise RuntimeError("Parameter grid is empty; cannot reconstruct sweep dimensions")

    # Use the latest full grid if possible.
    if len(raw) >= expected:
        raw = raw.tail(expected).reset_index(drop=True)
        grid = grid[:expected]
    else:
        grid = grid[: len(raw)]

    params = pd.DataFrame(
        grid,
        columns=[
            "gate_threshold",
            "max_assets",
            "high_corr_scale",
            "execution_delay_bars",
            "latency_lookback_bars",
        ],
    )
    out = pd.concat([raw.reset_index(drop=True), params], axis=1)
    return out


def load_sweep_df(
    db_path: Path,
    gates: list[float],
    assets: list[int],
    scales: list[float],
    delays: list[int],
    lookbacks: list[int],
) -> tuple[pd.DataFrame, str]:
    with sqlite3.connect(db_path) as conn:
        if _table_exists(conn, "sweep_results"):
            return _load_df_from_sweep_results(conn), "sweep_results"
        if _table_exists(conn, "portfolio_runs"):
            return _reconstruct_df_from_portfolio_runs(conn, gates, assets, scales, delays, lookbacks), "portfolio_runs_reconstructed"
    raise RuntimeError(f"No supported sweep table found in {db_path}")


def compute_robustness(df: pd.DataFrame, epsilon: float) -> pd.DataFrame:
    group_cols = ["gate_threshold", "max_assets", "high_corr_scale", "latency_lookback_bars"]
    grouped = (
        df.groupby(group_cols, as_index=False)
        .agg(
            pnl_mean=("portfolio_net_pnl", "mean"),
            pnl_std=("portfolio_net_pnl", "std"),
            pf_mean=("portfolio_profit_factor", "mean"),
            trades_mean=("total_trades", "mean"),
            gated_mean=("gated_signals_count", "mean"),
            cluster_gated_mean=("gated_cluster_window_count", "mean"),
        )
    )
    grouped["pnl_std"] = grouped["pnl_std"].fillna(0.0)

    d0 = df[df["execution_delay_bars"] == 0][
        ["gate_threshold", "max_assets", "high_corr_scale", "latency_lookback_bars", "portfolio_net_pnl"]
    ].rename(columns={"portfolio_net_pnl": "pnl_delay0"})

    merged = grouped.merge(d0, on=group_cols, how="left")
    merged["pnl_delay0"] = merged["pnl_delay0"].fillna(0.0)

    mu = merged["pnl_mean"].copy()
    mu = np.where(np.abs(mu) < epsilon, np.sign(mu) * epsilon + (mu == 0.0) * epsilon, mu)
    merged["robustness_score"] = merged["pnl_delay0"] * (1.0 - (merged["pnl_std"] / mu))
    return merged.sort_values("robustness_score", ascending=False).reset_index(drop=True)


def add_penalty_weighted_score(robustness: pd.DataFrame, penalty_lambda: float) -> pd.DataFrame:
    out = robustness.copy()
    out["penalty_lambda"] = float(penalty_lambda)
    out["penalty_weighted_score"] = out["pnl_delay0"] - (float(penalty_lambda) * out["pnl_std"])
    return out.sort_values("penalty_weighted_score", ascending=False).reset_index(drop=True)


def _row_to_policy(row: pd.Series | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        "correlation_gating_threshold": float(row["gate_threshold"]),
        "max_assets": int(row["max_assets"]),
        "position_scaling_factor": float(row["high_corr_scale"]),
        "latency_lookback_bars": int(row["latency_lookback_bars"]),
        "j_score": float(row["penalty_weighted_score"]),
        "pnl_delay0": float(row["pnl_delay0"]),
        "sigma_delay": float(row["pnl_std"]),
        "empirical_cluster_gated_mean": float(row["cluster_gated_mean"]),
    }


def render_reports(
    df: pd.DataFrame,
    top_n: int,
    max_assets_filter: int | None,
    epsilon: float,
    penalty_lambda: float,
    shield_min_lookback: int,
    min_cluster_gating_activity: float,
) -> dict[str, object]:
    work = df.copy()
    if max_assets_filter is not None:
        work = work[work["max_assets"] == max_assets_filter].copy()

    if work.empty:
        print("No rows available after filtering.")
        return {
            "shield_feasible": False,
            "theoretical_optimum": None,
            "operational_optimum": None,
        }

    pnl_latency_xtab = pd.pivot_table(
        work,
        index="execution_delay_bars",
        columns="latency_lookback_bars",
        values="portfolio_net_pnl",
        aggfunc="mean",
    ).sort_index()

    cluster_gated_latency_xtab = pd.pivot_table(
        work,
        index="execution_delay_bars",
        columns="latency_lookback_bars",
        values="gated_cluster_window_count",
        aggfunc="mean",
    ).sort_index()

    pnl_xtab = pd.pivot_table(
        work,
        index="execution_delay_bars",
        columns="gate_threshold",
        values="portfolio_net_pnl",
        aggfunc="mean",
    ).sort_index()

    gated_xtab = pd.pivot_table(
        work,
        index="execution_delay_bars",
        columns="gate_threshold",
        values="gated_signals_count",
        aggfunc="mean",
    ).sort_index()

    robustness = compute_robustness(work, epsilon=epsilon)
    scored = add_penalty_weighted_score(robustness, penalty_lambda=penalty_lambda)

    print("\n" + "=" * 88)
    print("  4.5D SWEEP ATTRIBUTION: MEAN NET PNL BY DELAY x LOOKBACK")
    print("=" * 88)
    print(pnl_latency_xtab.to_string(float_format=lambda x: f"{x:+.2f}"))

    print("\n" + "=" * 88)
    print("  4.5D SWEEP ATTRIBUTION: MEAN CLUSTER GATED BY DELAY x LOOKBACK")
    print("=" * 88)
    print(cluster_gated_latency_xtab.to_string(float_format=lambda x: f"{x:.2f}"))

    print("\n" + "=" * 88)
    print("  4D SWEEP ATTRIBUTION: MEAN NET PNL BY DELAY x GATE")
    print("=" * 88)
    print(pnl_xtab.to_string(float_format=lambda x: f"{x:+.2f}"))

    print("\n" + "=" * 88)
    print("  4D SWEEP ATTRIBUTION: MEAN GATED COUNT BY DELAY x GATE")
    print("=" * 88)
    print(gated_xtab.to_string(float_format=lambda x: f"{x:.2f}"))

    board = scored.head(top_n).copy()
    board.index = range(1, len(board) + 1)
    board.index.name = "rank"
    board = board[
        [
            "gate_threshold",
            "max_assets",
            "high_corr_scale",
            "latency_lookback_bars",
            "pnl_delay0",
            "pnl_mean",
            "pnl_std",
            "pf_mean",
            "gated_mean",
            "cluster_gated_mean",
            "robustness_score",
            "penalty_weighted_score",
        ]
    ]

    print("\n" + "=" * 88)
    print(f"  ROBUSTNESS LEADERBOARD (TOP {top_n})")
    print("=" * 88)
    print(board.rename(columns={
        "gate_threshold": "gate_th",
        "max_assets": "assets",
        "high_corr_scale": "hc_scale",
        "latency_lookback_bars": "latency_lb",
        "pnl_delay0": "pnl_d0",
        "pnl_mean": "pnl_mu",
        "pnl_std": "pnl_sigma",
        "pf_mean": "pf_mu",
        "gated_mean": "gated_mu",
        "cluster_gated_mean": "gated_lb_mu",
        "robustness_score": "R_s",
        "penalty_weighted_score": "J_lambda",
    }).to_string(float_format=lambda x: f"{x:+.4f}"))

    best = scored.iloc[0]
    shielded = scored[
        (scored["latency_lookback_bars"] >= int(shield_min_lookback))
        & (scored["cluster_gated_mean"] >= float(min_cluster_gating_activity))
    ].copy()
    shield_best = shielded.iloc[0] if not shielded.empty else None

    print("\n" + "=" * 88)
    print("  DUAL POLICY RECOMMENDATION (PENALTY-WEIGHTED)")
    print("=" * 88)
    print(f"lambda={float(penalty_lambda):.4f}")
    print(f"shield_min_lookback={int(shield_min_lookback)}")
    print(f"min_cluster_gating_activity={float(min_cluster_gating_activity):.4f}")

    print("\nTheoretical Optimum (Unconstrained):")
    print(
        f"Recommended: gate={float(best['gate_threshold']):.2f}, "
        f"assets={int(best['max_assets'])}, "
        f"scale={float(best['high_corr_scale']):.2f}, "
        f"latency_lookback={int(best['latency_lookback_bars'])}"
    )
    print(
        f"J_lambda={float(best['penalty_weighted_score']):+.4f} "
        f"(pnl_d0={float(best['pnl_delay0']):+.4f}, sigma_delay={float(best['pnl_std']):+.4f})"
    )

    print("\nOperational Optimum (Shield-Constrained):")
    if shield_best is None:
        print(
            "No configurations satisfy "
            f"latency_lookback_bars >= {int(shield_min_lookback)} and "
            f"cluster_gated_mean >= {float(min_cluster_gating_activity):.4f}"
        )
    else:
        print(
            f"Recommended: gate={float(shield_best['gate_threshold']):.2f}, "
            f"assets={int(shield_best['max_assets'])}, "
            f"scale={float(shield_best['high_corr_scale']):.2f}, "
            f"latency_lookback={int(shield_best['latency_lookback_bars'])}"
        )
        print(
            f"J_lambda={float(shield_best['penalty_weighted_score']):+.4f} "
            f"(pnl_d0={float(shield_best['pnl_delay0']):+.4f}, sigma_delay={float(shield_best['pnl_std']):+.4f})"
        )

    return {
        "shield_feasible": bool(shield_best is not None),
        "theoretical_optimum": _row_to_policy(best),
        "operational_optimum": _row_to_policy(shield_best),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate aggregate attribution and robustness metrics for 4D sweep DB")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to sweep SQLite DB")
    parser.add_argument("--top", type=int, default=20, help="Top-N rows for robustness leaderboard")
    parser.add_argument("--max-assets-filter", type=int, default=2, help="Filter to a max_assets value; use -1 for no filter")
    parser.add_argument("--gates", type=_parse_float_list, default=[0.70, 0.75, 0.80, 0.85], help="Gate threshold grid used in sweep")
    parser.add_argument("--assets", type=_parse_int_list, default=[1, 2], help="max_assets grid used in sweep")
    parser.add_argument("--scales", type=_parse_float_list, default=[0.25, 0.40, 0.50, 0.60], help="high_corr_scale grid used in sweep")
    parser.add_argument("--delays", type=_parse_int_list, default=[0, 1, 2], help="execution_delay_bars grid used in sweep")
    parser.add_argument("--lookbacks", type=_parse_int_list, default=[0], help="latency_lookback_bars grid used in sweep")
    parser.add_argument("--epsilon", type=float, default=1e-9, help="Numerical floor for robustness denominator")
    parser.add_argument(
        "--latency-penalty-lambda",
        type=float,
        default=1.0,
        help="Penalty lambda for J = pnl_delay0 - lambda * sigma_delay",
    )
    parser.add_argument(
        "--shield-min-lookback",
        type=int,
        default=1,
        help="Minimum latency_lookback_bars used for operational (shielded) recommendation",
    )
    parser.add_argument(
        "--min-cluster-gating-activity",
        type=float,
        default=0.0,
        help="Minimum mean gated_cluster_window_count required for operational recommendation",
    )
    parser.add_argument(
        "--fail-on-empty-shield",
        action="store_true",
        help="Exit with code 1 when no operational shield-constrained recommendation is feasible",
    )
    parser.add_argument(
        "--emit-policy-json",
        default="",
        help="Optional JSON path for machine-readable theoretical/operational policy handoff",
    )
    parser.add_argument("--export-csv", default="", help="Optional CSV export path for the enriched sweep dataframe")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise RuntimeError(f"DB not found: {db_path}")

    max_assets_filter = None if args.max_assets_filter < 0 else int(args.max_assets_filter)
    df, source = load_sweep_df(
        db_path=db_path,
        gates=args.gates,
        assets=args.assets,
        scales=args.scales,
        delays=args.delays,
        lookbacks=args.lookbacks,
    )
    if df.empty:
        raise RuntimeError(f"No sweep rows found in {db_path}")

    print(f"Loaded {len(df)} rows from {db_path} using source={source}")
    report_meta = render_reports(
        df=df,
        top_n=args.top,
        max_assets_filter=max_assets_filter,
        epsilon=float(args.epsilon),
        penalty_lambda=float(args.latency_penalty_lambda),
        shield_min_lookback=max(0, int(args.shield_min_lookback)),
        min_cluster_gating_activity=max(0.0, float(args.min_cluster_gating_activity)),
    )

    shield_feasible = bool(report_meta.get("shield_feasible", False))

    if args.emit_policy_json:
        out_policy_path = Path(args.emit_policy_json)
        if not out_policy_path.is_absolute():
            out_policy_path = Path.cwd() / out_policy_path
        out_policy_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sweep_db_source": str(db_path),
            "status": "PASS" if shield_feasible else "FAIL",
            "constraints": {
                "latency_penalty_lambda": float(args.latency_penalty_lambda),
                "shield_min_lookback": int(max(0, int(args.shield_min_lookback))),
                "min_cluster_gating_activity": float(max(0.0, float(args.min_cluster_gating_activity))),
                "max_assets_filter": max_assets_filter,
            },
            "theoretical_optimum": report_meta.get("theoretical_optimum"),
            "operational_optimum": report_meta.get("operational_optimum"),
        }
        out_policy_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Policy JSON written: {out_policy_path}")

    if bool(args.fail_on_empty_shield) and not shield_feasible:
        print(
            "CRITICAL: Operational shield constraints could not be satisfied.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if args.export_csv:
        out_path = Path(args.export_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        print(f"\nExported enriched sweep rows to: {out_path}")


if __name__ == "__main__":
    main()
