#!/usr/bin/env python3
"""
Collision Injector: Artificially force simultaneous BTC/ETH entries on the same timestamp
to verify that the portfolio router's priority-gating logic correctly gates competing signals.

This script:
1. Loads feature parquets for BTC and ETH
2. Adds labels (tradeable_long column) via add_labels()
3. Identifies or creates a collision point (shared timestamp with tradeable_long=1 for both)
4. Optionally injects correlation regime data to trigger high_correlation_sync gating
5. Runs portfolio backtest and verifies gated_signals_count > 0
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from crypto_data_pipeline import add_labels, CostModel
except ImportError:
    # Fallback: define minimal CostModel if import fails
    from dataclasses import dataclass
    
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


def add_labels_minimal(df: pd.DataFrame, horizon_bars: int, cost_model: CostModel) -> pd.DataFrame:
    """Minimal add_labels() implementation for collision injection."""
    out = df.copy()
    out["future_close"] = out["close"].shift(-horizon_bars)
    out["gross_edge"] = (out["future_close"] - out["close"]) / out["close"]
    out["net_edge"] = out["gross_edge"] - cost_model.fee_total_frac - cost_model.slippage_total_frac
    out["tradeable_long"] = (out["net_edge"] > 0.0).astype(int)
    out["signal_candidate"] = out["tradeable_long"]  # Alias for backtest
    out["direction_long"] = (out["gross_edge"] > 0.0).astype(int)
    return out.dropna().reset_index(drop=True)


def inject_collision(
    features_dir: Path,
    output_dir: Path,
    cost_model: CostModel | None = None,
    force_high_correlation: bool = True,
) -> tuple[pd.Timestamp, Path, Path]:
    """
    Inject a collision scenario: force both BTC and ETH to signal on the same timestamp.
    
    Returns:
        (collision_ts, btc_collision_path, eth_collision_path)
    """
    if cost_model is None:
        cost_model = CostModel(fee_bps_per_side=2.0, slippage_bps_total=2.0)
    
    print(f"\n🔧 === COLLISION INJECTOR ===")
    print(f"   Target Assets: BTC/USD, ETH/USD")
    print(f"   Force High Correlation: {force_high_correlation}")
    
    # Load feature parquets
    btc_features_path = features_dir / "kraken_BTC_USD_15m_features.parquet"
    eth_features_path = features_dir / "kraken_ETH_USD_15m_features.parquet"
    
    if not btc_features_path.exists():
        raise FileNotFoundError(f"BTC features not found: {btc_features_path}")
    if not eth_features_path.exists():
        raise FileNotFoundError(f"ETH features not found: {eth_features_path}")
    
    print(f"   Loading feature parquets...")
    btc_features = pd.read_parquet(btc_features_path)
    eth_features = pd.read_parquet(eth_features_path)
    
    print(f"   BTC shape: {btc_features.shape}, ETH shape: {eth_features.shape}")
    
    # Add labels (creates signal_candidate column)
    print(f"   Adding labels (computing signal_candidate)...")
    btc_labeled = add_labels_minimal(btc_features, horizon_bars=16, cost_model=cost_model)
    eth_labeled = add_labels_minimal(eth_features, horizon_bars=8, cost_model=cost_model)
    
    print(f"   After labeling: BTC {btc_labeled.shape}, ETH {eth_labeled.shape}")
    print(f"   BTC signal_candidate count: {btc_labeled['signal_candidate'].sum()}")
    print(f"   ETH signal_candidate count: {eth_labeled['signal_candidate'].sum()}")
    
    # Find or create collision timestamp
    collision_ts = None
    
    # Try to find natural overlap
    btc_signal_ts = set(btc_labeled[btc_labeled["signal_candidate"] == 1]["timestamp"])
    eth_signal_ts = set(eth_labeled[eth_labeled["signal_candidate"] == 1]["timestamp"])
    natural_collisions = btc_signal_ts & eth_signal_ts
    
    if natural_collisions:
        collision_ts = sorted(natural_collisions)[-1]  # Use most recent
        print(f"   ✅ Found natural collision at {collision_ts}")
    else:
        # Force a collision: pick last BTC signal timestamp, inject ETH signal there
        btc_signal_rows = btc_labeled[btc_labeled["signal_candidate"] == 1]
        if len(btc_signal_rows) > 0:
            collision_ts = btc_signal_rows.iloc[-1]["timestamp"]
            print(f"   🎯 Creating forced collision at BTC timestamp: {collision_ts}")
            
            # Create ETH collision row at this timestamp
            eth_nearest = eth_features[eth_features["timestamp"] < collision_ts]
            if len(eth_nearest) > 0:
                eth_collision_row = eth_nearest.iloc[-1].copy()
                eth_collision_row["timestamp"] = collision_ts
                eth_collision_row["signal_candidate"] = 1
                eth_collision_row["tradeable_long"] = 1
                
                # Append and sort
                eth_labeled = pd.concat([eth_labeled, pd.DataFrame([eth_collision_row])], ignore_index=True)
                eth_labeled = eth_labeled.sort_values("timestamp").reset_index(drop=True)
                print(f"   ✅ Injected ETH signal at collision timestamp")
    
    if collision_ts is None:
        print(f"   ❌ Could not find or create collision timestamp")
        raise RuntimeError("No collision timestamp found")
    
    print(f"   📍 Collision timestamp: {collision_ts}")
    
    # Inject high correlation regime to trigger gating
    if force_high_correlation:
        print(f"   💉 Injecting high_correlation_sync regime at collision...")
        btc_mask = btc_labeled["timestamp"] == collision_ts
        eth_mask = eth_labeled["timestamp"] == collision_ts
        
        if btc_mask.any():
            btc_labeled.loc[btc_mask, "corr_regime"] = "high_correlation_sync"
            btc_labeled.loc[btc_mask, "mean_correlation"] = 0.85
            print(f"      BTC: marked as high_correlation_sync")
        
        if eth_mask.any():
            eth_labeled.loc[eth_mask, "corr_regime"] = "high_correlation_sync"
            eth_labeled.loc[eth_mask, "mean_correlation"] = 0.85
            print(f"      ETH: marked as high_correlation_sync")
    
    # Save collision-injected parquets
    output_dir.mkdir(parents=True, exist_ok=True)
    btc_collision_path = output_dir / "kraken_BTC_USD_15m_collision.parquet"
    eth_collision_path = output_dir / "kraken_ETH_USD_15m_collision.parquet"
    
    print(f"   Saving collision-injected parquets...")
    btc_labeled.to_parquet(btc_collision_path)
    eth_labeled.to_parquet(eth_collision_path)
    print(f"   ✅ BTC collision parquet: {btc_collision_path}")
    print(f"   ✅ ETH collision parquet: {eth_collision_path}")
    
    print(f"\n✅ === COLLISION INJECTION COMPLETE ===")
    btc_at_collision = btc_labeled[btc_labeled["timestamp"] == collision_ts]["signal_candidate"].iloc[0] if (btc_labeled["timestamp"] == collision_ts).any() else 0
    eth_at_collision = eth_labeled[eth_labeled["timestamp"] == collision_ts]["signal_candidate"].iloc[0] if (eth_labeled["timestamp"] == collision_ts).any() else 0
    print(f"   Collision timestamp: {collision_ts}")
    print(f"   BTC signal_candidate at collision: {bool(btc_at_collision)}")
    print(f"   ETH signal_candidate at collision: {bool(eth_at_collision)}")
    
    return collision_ts, btc_collision_path, eth_collision_path


def run_portfolio_backtest_via_cli(
    collision_data_dir: Path,
    config_path: Path,
    output_dir: Path,
    registry_db: Path,
) -> dict[str, Any]:
    """
    Run portfolio backtest via CLI (command_backtest_strategy with --mode portfolio).
    
    Returns:
        Parsed manifest results
    """
    print(f"\n🔄 === PORTFOLIO COLLISION BACKTEST (via CLI) ===")
    
    backtest_cmd = [
        sys.executable,
        "scripts/crypto_data_pipeline.py",
        "backtest-strategy",
        "--mode",
        "portfolio",
        "--input-dir",
        str(collision_data_dir),
        "--output-dir",
        str(output_dir),
        "--registry-db",
        str(registry_db),
        "--strategy-config",
        str(config_path),
    ]
    
    print(f"   Running: {' '.join(backtest_cmd)}")
    result = subprocess.run(backtest_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"\n❌ Backtest command failed:")
        print(f"   stdout: {result.stdout}")
        print(f"   stderr: {result.stderr}")
        raise RuntimeError(f"Backtest failed with exit code {result.returncode}")
    
    print(f"   Backtest command output:")
    for line in result.stdout.split("\n"):
        if line.strip():
            print(f"   {line}")
    
    # Parse manifest to extract results
    manifest_file = output_dir / "manifest_backtest_strategy.json"
    if manifest_file.exists():
        manifest = json.loads(manifest_file.read_text())
        print(f"\n✅ === PORTFOLIO COLLISION BACKTEST RESULTS ===")
        
        # Extract gated signals from portfolio_run
        gated_count = 0
        portfolio_run = manifest.get("portfolio_run")
        if portfolio_run:
            gated_count = portfolio_run.get("gated_signals_count", 0)
            net_pnl = portfolio_run.get("portfolio_net_pnl", 0)
            pf = portfolio_run.get("portfolio_profit_factor", 0)
            total_trades = portfolio_run.get("total_trades", 0)
            
            print(f"   Portfolio Net PnL: ${net_pnl:.4f}")
            print(f"   Portfolio Profit Factor: {pf:.4f}")
            print(f"   Total Trades: {total_trades}")
            print(f"   Gated Signals Count: {gated_count}")
            
            if gated_count > 0:
                print(f"   ✅ GATING VERIFIED: {gated_count} signal(s) were gated!")
            else:
                print(f"   ⚠️  No gating observed in this run")
            
            return manifest
        else:
            print(f"   ⚠️  No portfolio_run data in manifest")
            return manifest
    else:
        print(f"   ⚠️  Manifest file not found: {manifest_file}")
        return {}


def main():
    """CLI entry point for collision injector."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Portfolio Collision Injector")
    parser.add_argument(
        "--features-dir",
        type=Path,
        default=Path("data/crypto/features"),
        help="Input features directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/crypto/collision_test"),
        help="Output directory for collision-injected data and backtest results",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/crypto_strategy.yaml"),
        help="Strategy config path",
    )
    parser.add_argument(
        "--registry-db",
        type=Path,
        default=Path("reports/crypto/crypto_experiments_collision_test.db"),
        help="SQLite registry database",
    )
    parser.add_argument(
        "--no-high-corr",
        action="store_true",
        help="Do not force high_correlation_sync regime",
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("🚀 PORTFOLIO COLLISION INJECTOR v1.0")
    print("=" * 80)
    print(f"Features Dir: {args.features_dir}")
    print(f"Output Dir: {args.output_dir}")
    print(f"Config: {args.config}")
    print(f"Registry DB: {args.registry_db}")
    print("=" * 80)
    
    # Phase 1: Inject collision
    collision_data_dir = args.output_dir / "collision_data"
    try:
        collision_ts, btc_path, eth_path = inject_collision(
            features_dir=args.features_dir,
            output_dir=collision_data_dir,
            force_high_correlation=not args.no_high_corr,
        )
    except Exception as e:
        print(f"\n❌ Collision injection failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Phase 2: Run portfolio backtest on collision data
    backtest_output_dir = args.output_dir / "backtest_results"
    try:
        results = run_portfolio_backtest_via_cli(
            collision_data_dir=collision_data_dir,
            config_path=args.config,
            output_dir=backtest_output_dir,
            registry_db=args.registry_db,
        )
    except Exception as e:
        print(f"\n❌ Portfolio backtest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("🎯 COLLISION TEST COMPLETE")
    print("=" * 80)
    
    portfolio_run = results.get("portfolio_run")
    if portfolio_run:
        gated = portfolio_run.get("gated_signals_count", 0)
        pnl = portfolio_run.get("portfolio_net_pnl", 0)
        pf = portfolio_run.get("portfolio_profit_factor", 0)
        
        print(f"\nKey Metrics:")
        print(f"  • Gated Signals: {gated}")
        print(f"  • Portfolio Net PnL: ${pnl:.4f}")
        print(f"  • Portfolio PF: {pf:.4f}")
        
        if gated > 0:
            print(f"\n✅ SUCCESS: Priority gating is active and functional!")
            print(f"   {gated} signal(s) were successfully gated by the router.")
        else:
            print(f"\n⚠️  No gating observed. Check collision data or routing config.")
    else:
        print(f"\n⚠️  No portfolio_run results available.")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
