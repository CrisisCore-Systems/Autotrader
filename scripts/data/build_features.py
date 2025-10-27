"""Build features from raw market data for DVC pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime

import yaml
import pandas as pd
import numpy as np


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical features from OHLCV data."""
    # Returns
    df['returns_1'] = df['close'].pct_change()
    df['returns_5'] = df['close'].pct_change(5)
    df['returns_15'] = df['close'].pct_change(15)
    
    # Volatility
    df['volatility_15'] = df['returns_1'].rolling(15).std()
    df['volatility_60'] = df['returns_1'].rolling(60).std()
    
    # Volume features
    df['volume_ma_15'] = df['volume'].rolling(15).mean()
    df['volume_ratio'] = df['volume'] / df['volume_ma_15']
    
    # Price features
    df['high_low_range'] = (df['high'] - df['low']) / df['close']
    df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-8)
    
    # Momentum
    df['rsi_14'] = compute_rsi(df['close'], 14)
    
    return df.dropna()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI indicator."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-8)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    input_dir = Path(cfg["input"]["path"])
    output = Path(cfg["output"]["path"])
    output.mkdir(parents=True, exist_ok=True)
    
    print(f"🔧 Building features from: {input_dir}")
    
    feature_files = []
    for raw_file in input_dir.glob("*_bars.parquet"):
        if raw_file.name == 'manifest.json':
            continue
        
        print(f"  Processing {raw_file.name}...")
        df = pd.read_parquet(raw_file)
        df_features = compute_features(df)
        
        output_path = output / f"{raw_file.stem}_features.parquet"
        df_features.to_parquet(output_path)
        feature_files.append(output_path.name)
        print(f"    ✅ {len(df_features)} rows → {output_path.name}")
    
    # Write manifest
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'feature_files': feature_files,
        'total_files': len(feature_files),
        'config': str(args.config),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    
    print(f"\n✅ Built features for {len(feature_files)} files")


if __name__ == "__main__":
    main()
