"""Fetch market data for DVC pipeline - creates baseline dataset for validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta

import yaml
import pandas as pd
import numpy as np


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def generate_sample_data(symbol: str, lookback_days: int, asset_class: str) -> pd.DataFrame:
    """Generate synthetic market data for testing."""
    np.random.seed(hash(symbol) % 2**32)
    
    # Generate timestamps (1-minute bars)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    timestamps = pd.date_range(start=start_date, end=end_date, freq='1min')
    
    # Random walk with drift
    n = len(timestamps)
    returns = np.random.normal(0.0001, 0.005, n)
    price = 100.0 * np.exp(np.cumsum(returns))
    
    # Generate OHLCV
    df = pd.DataFrame({
        'timestamp': timestamps,
        'symbol': symbol,
        'asset_class': asset_class,
        'open': price * np.random.uniform(0.999, 1.001, n),
        'high': price * np.random.uniform(1.001, 1.005, n),
        'low': price * np.random.uniform(0.995, 0.999, n),
        'close': price,
        'volume': np.random.uniform(10000, 50000, n),
        'trades': np.random.randint(50, 500, n),
    })
    
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    output = Path(cfg["output"]["path"])
    output.mkdir(parents=True, exist_ok=True)
    
    print(f"📊 Fetching market data using config: {args.config}")
    symbols_fetched = []
    
    # Fetch equities
    for symbol in cfg.get('source', {}).get('equities', {}).get('symbols', []):
        df = generate_sample_data(
            symbol=symbol,
            lookback_days=cfg['source']['equities']['lookback_days'],
            asset_class='equity'
        )
        output_path = output / f"{symbol}_bars.parquet"
        df.to_parquet(output_path)
        symbols_fetched.append(symbol)
        print(f"  ✅ {symbol}: {len(df)} bars → {output_path.name}")
    
    # Fetch crypto
    for symbol in cfg.get('source', {}).get('crypto', {}).get('symbols', []):
        clean_symbol = symbol.replace('-', '')
        df = generate_sample_data(
            symbol=clean_symbol,
            lookback_days=cfg['source']['crypto']['lookback_days'],
            asset_class='crypto'
        )
        output_path = output / f"{clean_symbol}_bars.parquet"
        df.to_parquet(output_path)
        symbols_fetched.append(symbol)
        print(f"  ✅ {symbol}: {len(df)} bars → {output_path.name}")
    
    # Fetch FX
    for symbol in cfg.get('source', {}).get('fx', {}).get('symbols', []):
        df = generate_sample_data(
            symbol=symbol,
            lookback_days=cfg['source']['fx']['lookback_days'],
            asset_class='fx'
        )
        output_path = output / f"{symbol}_bars.parquet"
        df.to_parquet(output_path)
        symbols_fetched.append(symbol)
        print(f"  ✅ {symbol}: {len(df)} bars → {output_path.name}")
    
    # Write manifest
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'symbols_fetched': symbols_fetched,
        'total_symbols': len(symbols_fetched),
        'config': str(args.config),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    
    print(f"\n✅ Fetched {len(symbols_fetched)} symbols")


if __name__ == "__main__":
    main()
