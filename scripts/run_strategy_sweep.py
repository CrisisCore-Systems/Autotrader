"""
Hyperparameter sweep orchestrator for the cross-asset portfolio engine.

Maps a 3-dimensional grid:
  - correlation_gating_threshold: [0.70, 0.75, 0.80, 0.85]
  - max_simultaneous_assets:      [1, 2]
  - high_correlation_scale:       [0.25, 0.40, 0.50, 0.60]

Optional 4th and 5th axes:
    - execution_delay_bars:         [0, 1, 2]
        - latency_lookback_bars:        [0, 1, 2]

32 configurations total. Results are stored in an isolated sweep DB and
printed as a ranked leaderboard.

Usage:
    python scripts/run_strategy_sweep.py
    python scripts/run_strategy_sweep.py --input-dir reports/crypto/collision_test/collision_data
    python scripts/run_strategy_sweep.py --top 15
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd
import yaml


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_DIR = BASE_DIR / "reports/crypto/collision_test/collision_data"
DEFAULT_OUTPUT_DIR = BASE_DIR / "reports/crypto/sweep_runs"
DEFAULT_SWEEP_DB = BASE_DIR / "reports/crypto/crypto_sweep_results.db"
CONFIG_TEMPLATE = BASE_DIR / "configs/crypto_strategy_collision_test.yaml"

GATING_THRESHOLDS = [0.70, 0.75, 0.80, 0.85]
MAX_ASSETS_OPTIONS = [1, 2]
SCALE_FACTORS = [0.25, 0.40, 0.50, 0.60]
DEFAULT_EXECUTION_DELAYS = [0, 1, 2]
DEFAULT_LATENCY_LOOKBACKS = [0, 1, 2]


def _python_exe() -> str:
    """Return the interpreter running this script (works in venv and bare Python)."""
    return sys.executable


def run_sweep(
    input_dir: Path,
    output_dir: Path,
    sweep_db: Path,
    top_n: int,
    config_template: Path = CONFIG_TEMPLATE,
    regime_dir: Path | None = None,
    execution_delays: list[int] | None = None,
    latency_lookbacks: list[int] | None = None,
) -> None:
    execution_delays = execution_delays or [0]
    latency_lookbacks = latency_lookbacks or [0]
    total_configs = (
        len(GATING_THRESHOLDS)
        * len(MAX_ASSETS_OPTIONS)
        * len(SCALE_FACTORS)
        * len(execution_delays)
        * len(latency_lookbacks)
    )

    with open(config_template) as fh:
        base_cfg: dict = yaml.safe_load(fh)

    output_dir.mkdir(parents=True, exist_ok=True)
    sweep_db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(sweep_db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sweep_results (
                sweep_id TEXT NOT NULL,
                sweep_ts_utc TEXT NOT NULL,
                config_template TEXT NOT NULL,
                input_dir TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                sweep_db TEXT NOT NULL,
                portfolio_run_id TEXT NOT NULL,
                gate_threshold REAL NOT NULL,
                max_assets INTEGER NOT NULL,
                high_corr_scale REAL NOT NULL,
                execution_delay_bars INTEGER NOT NULL,
                latency_lookback_bars INTEGER NOT NULL,
                total_trades INTEGER NOT NULL,
                gated_signals_count INTEGER NOT NULL,
                gated_cluster_window_count INTEGER NOT NULL,
                portfolio_net_pnl REAL NOT NULL,
                portfolio_profit_factor REAL NOT NULL
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sweep_results)").fetchall()}
        if "latency_lookback_bars" not in columns:
            conn.execute("ALTER TABLE sweep_results ADD COLUMN latency_lookback_bars INTEGER NOT NULL DEFAULT 0")
        if "gated_cluster_window_count" not in columns:
            conn.execute("ALTER TABLE sweep_results ADD COLUMN gated_cluster_window_count INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    now_utc = pd.Timestamp.now(tz="UTC")
    sweep_id = now_utc.strftime("sweep_%Y%m%dT%H%M%S%fZ")
    sweep_ts_utc = now_utc.isoformat()

    pipeline = str(BASE_DIR / "scripts/crypto_data_pipeline.py")
    results: list[dict] = []
    idx = 0

    print(f"Initializing grid sweep: {total_configs} configurations")
    print(f"  Gating thresholds : {GATING_THRESHOLDS}")
    print(f"  Max assets        : {MAX_ASSETS_OPTIONS}")
    print(f"  High-corr scales  : {SCALE_FACTORS}")
    print(f"  Execution delays  : {execution_delays}")
    print(f"  Latency lookbacks : {latency_lookbacks}")
    print()

    for gate_th in GATING_THRESHOLDS:
        for max_assets in MAX_ASSETS_OPTIONS:
            for scale in SCALE_FACTORS:
                for execution_delay_bars in execution_delays:
                    for latency_lookback_bars in latency_lookbacks:
                        idx += 1

                        # Patch the base config for this cell
                        cfg = yaml.safe_load(yaml.dump(base_cfg))  # deep copy via round-trip
                        cfg.setdefault("portfolio_routing", {})
                        cfg["portfolio_routing"]["correlation_gating_threshold"] = gate_th
                        cfg["portfolio_routing"]["max_simultaneous_assets"] = max_assets
                        cfg["portfolio_routing"]["latency_lookback_bars"] = latency_lookback_bars
                        cfg.setdefault("position_sizing", {})
                        cfg["position_sizing"]["high_correlation_scale"] = scale

                        with tempfile.NamedTemporaryFile(
                            mode="w",
                            suffix=".yaml",
                            dir=BASE_DIR / "configs",
                            prefix="_sweep_",
                            delete=False,
                        ) as tmp:
                            yaml.dump(cfg, tmp)
                            tmp_path = Path(tmp.name)

                        try:
                            cmd = [
                                _python_exe(),
                                pipeline,
                                "backtest-strategy",
                                "--mode", "portfolio",
                                "--input-dir", str(input_dir),
                                "--output-dir", str(output_dir),
                                "--registry-db", str(sweep_db),
                                "--strategy-config", str(tmp_path),
                                "--execution-delay-bars", str(execution_delay_bars),
                            ]
                            if regime_dir is not None:
                                cmd += ["--regime-dir", str(regime_dir)]
                            subprocess.run(
                                cmd,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=False,
                            )
                        finally:
                            try:
                                tmp_path.unlink()
                            except OSError:
                                pass

                        # Read back the most recently written portfolio run
                        if not sweep_db.exists():
                            print(
                                f"  [{idx:02d}/{total_configs}] gate={gate_th} assets={max_assets} "
                                f"scale={scale} delay={execution_delay_bars} lookback={latency_lookback_bars} "
                                "— DB not created, skipping"
                            )
                            continue

                        with sqlite3.connect(sweep_db) as conn:
                            row_df = pd.read_sql_query(
                                """
                                SELECT portfolio_run_id,
                                       total_trades,
                                       gated_signals_count,
                                       portfolio_net_pnl,
                                       portfolio_profit_factor,
                                       report_file
                                FROM   portfolio_runs
                                ORDER  BY rowid DESC
                                LIMIT  1
                                """,
                                conn,
                            )

                        if row_df.empty:
                            print(
                                f"  [{idx:02d}/{total_configs}] gate={gate_th} assets={max_assets} "
                                f"scale={scale} delay={execution_delay_bars} lookback={latency_lookback_bars} "
                                "— no row written"
                            )
                            continue

                        rec = row_df.iloc[0].to_dict()
                        gated_cluster_window_count = 0
                        report_file = rec.get("report_file")
                        if isinstance(report_file, str) and report_file:
                            report_path = Path(report_file)
                            if not report_path.is_absolute():
                                report_path = BASE_DIR / report_path
                            if report_path.exists():
                                try:
                                    report_payload = yaml.safe_load(report_path.read_text(encoding="utf-8")) or {}
                                    gated_cluster_window_count = int(report_payload.get("gated_cluster_window_count", 0) or 0)
                                except Exception:
                                    gated_cluster_window_count = 0

                        rec.update(
                            gate_threshold=gate_th,
                            max_assets=max_assets,
                            high_corr_scale=scale,
                            execution_delay_bars=execution_delay_bars,
                            latency_lookback_bars=latency_lookback_bars,
                            gated_cluster_window_count=gated_cluster_window_count,
                        )
                        results.append(rec)

                        with sqlite3.connect(sweep_db) as conn:
                            conn.execute(
                                """
                                INSERT INTO sweep_results (
                                    sweep_id,
                                    sweep_ts_utc,
                                    config_template,
                                    input_dir,
                                    output_dir,
                                    sweep_db,
                                    portfolio_run_id,
                                    gate_threshold,
                                    max_assets,
                                    high_corr_scale,
                                    execution_delay_bars,
                                    latency_lookback_bars,
                                    total_trades,
                                    gated_signals_count,
                                    gated_cluster_window_count,
                                    portfolio_net_pnl,
                                    portfolio_profit_factor
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    sweep_id,
                                    sweep_ts_utc,
                                    str(config_template),
                                    str(input_dir),
                                    str(output_dir),
                                    str(sweep_db),
                                    str(rec["portfolio_run_id"]),
                                    float(gate_th),
                                    int(max_assets),
                                    float(scale),
                                    int(execution_delay_bars),
                                    int(latency_lookback_bars),
                                    int(rec["total_trades"]),
                                    int(rec["gated_signals_count"]),
                                    int(rec["gated_cluster_window_count"]),
                                    float(rec["portfolio_net_pnl"]),
                                    float(rec["portfolio_profit_factor"]),
                                ),
                            )
                            conn.commit()

                        print(
                            f"  [{idx:02d}/{total_configs}] gate={gate_th} assets={max_assets} "
                            f"scale={scale} delay={execution_delay_bars} lookback={latency_lookback_bars}"
                            f" | trades={int(rec['total_trades'])}"
                            f" gated={int(rec['gated_signals_count'])}"
                            f" cluster_gated={int(rec['gated_cluster_window_count'])}"
                            f" pnl=${rec['portfolio_net_pnl']:+.2f}"
                            f" pf={rec['portfolio_profit_factor']:.3f}"
                        )

    if not results:
        print("\nNo results collected — check that the input data and config are valid.")
        return

    df = pd.DataFrame(results)
    df = df.sort_values("portfolio_net_pnl", ascending=False).reset_index(drop=True)

    cols = [
        "gate_threshold",
        "max_assets",
        "high_corr_scale",
        "execution_delay_bars",
        "latency_lookback_bars",
        "total_trades",
        "gated_signals_count",
        "gated_cluster_window_count",
        "portfolio_net_pnl",
        "portfolio_profit_factor",
    ]
    df_display = df[cols].head(top_n).copy()
    df_display.index = range(1, len(df_display) + 1)
    df_display.index.name = "rank"

    # Format floats for readability
    df_display["portfolio_net_pnl"] = df_display["portfolio_net_pnl"].map("{:+.2f}".format)
    df_display["portfolio_profit_factor"] = df_display["portfolio_profit_factor"].map("{:.3f}".format)
    df_display["total_trades"] = df_display["total_trades"].astype(int)
    df_display["gated_signals_count"] = df_display["gated_signals_count"].astype(int)
    df_display["gated_cluster_window_count"] = df_display["gated_cluster_window_count"].astype(int)

    header = f"\n  OPTIMIZATION LEADERBOARD — Top {top_n} of {len(df)} configurations"
    sep = "=" * 78
    print(f"\n{sep}")
    print(header)
    print(sep)
    print(df_display.rename(columns={
        "gate_threshold":        "gate_th",
        "max_assets":            "assets",
        "high_corr_scale":       "hc_scale",
        "execution_delay_bars":  "exec_delay",
        "latency_lookback_bars": "latency_lb",
        "total_trades":          "trades",
        "gated_signals_count":   "gated",
        "gated_cluster_window_count": "gated_lb",
        "portfolio_net_pnl":     "net_pnl",
        "portfolio_profit_factor": "pf",
    }).to_string())
    print(sep)

    # Best configuration summary
    best = df.iloc[0]
    print(f"\n  Best config: gate_threshold={best['gate_threshold']}"
          f"  max_assets={int(best['max_assets'])}"
            f"  high_corr_scale={best['high_corr_scale']}"
                        f"  execution_delay_bars={int(best['execution_delay_bars'])}"
                        f"  latency_lookback_bars={int(best['latency_lookback_bars'])}")
    print(f"  Net PnL: ${best['portfolio_net_pnl']:+.2f}"
          f"   PF: {best['portfolio_profit_factor']:.3f}"
          f"   Trades: {int(best['total_trades'])}"
                    f"   Gated: {int(best['gated_signals_count'])}"
                    f"   Cluster-gated: {int(best['gated_cluster_window_count'])}")
    print()


def main() -> None:
    def parse_execution_delays(text: str) -> list[int]:
        values: list[int] = []
        for chunk in text.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            value = int(chunk)
            if value < 0:
                raise argparse.ArgumentTypeError("execution delays must be >= 0")
            values.append(value)
        if not values:
            raise argparse.ArgumentTypeError("at least one execution delay is required")
        # Keep order stable while removing accidental duplicates.
        return list(dict.fromkeys(values))

    def parse_latency_lookbacks(text: str) -> list[int]:
        values: list[int] = []
        for chunk in text.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            value = int(chunk)
            if value < 0:
                raise argparse.ArgumentTypeError("latency lookbacks must be >= 0")
            values.append(value)
        if not values:
            raise argparse.ArgumentTypeError("at least one latency lookback is required")
        return list(dict.fromkeys(values))

    parser = argparse.ArgumentParser(description="Portfolio hyperparameter sweep")
    parser.add_argument(
        "--input-dir",
        default=str(DEFAULT_INPUT_DIR),
        help="Directory containing kraken_*_features.parquet files",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for per-run reports",
    )
    parser.add_argument(
        "--sweep-db",
        default=str(DEFAULT_SWEEP_DB),
        help="SQLite DB path for sweep results",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top configurations to display in leaderboard",
    )
    parser.add_argument(
        "--config-template",
        default=str(CONFIG_TEMPLATE),
        help="Base YAML config file to patch for each sweep cell",
    )
    parser.add_argument(
        "--regime-dir",
        default=None,
        help="Directory containing regime parquets (forwarded to pipeline --regime-dir)",
    )
    parser.add_argument(
        "--execution-delays",
        type=parse_execution_delays,
        default=DEFAULT_EXECUTION_DELAYS,
        help="Comma-separated execution delays in bars to sweep (e.g. 0,1,2)",
    )
    parser.add_argument(
        "--latency-lookbacks",
        type=parse_latency_lookbacks,
        default=DEFAULT_LATENCY_LOOKBACKS,
        help="Comma-separated latency lookback bars to sweep (e.g. 0,1,2)",
    )
    args = parser.parse_args()
    run_sweep(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
        sweep_db=Path(args.sweep_db),
        top_n=args.top,
        config_template=Path(args.config_template),
        regime_dir=Path(args.regime_dir) if args.regime_dir else None,
        execution_delays=args.execution_delays,
        latency_lookbacks=args.latency_lookbacks,
    )


if __name__ == "__main__":
    main()
