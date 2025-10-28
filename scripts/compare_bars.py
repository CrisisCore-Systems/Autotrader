"""Quick bar comparison summary."""

import pandas as pd
from pathlib import Path

output_dir = Path("data/bars")
files = sorted(output_dir.glob("EURUSD_20241018_*.parquet"))

print("\n" + "=" * 70)
print("📊 BAR COMPARISON SUMMARY — All 6 Types")
print("=" * 70)

for f in files:
    df = pd.read_parquet(f)
    print(f"\n{f.name}:")
    print(f"  Bars: {len(df):>6}")
    print(f"  Avg volume/bar: {df['volume'].mean():>10.1f}")
    print(f"  Avg trades/bar: {df['trades'].mean():>10.1f}")
    print(f"  Price range: {df['low'].min():.5f} - {df['high'].max():.5f}")

print("\n" + "=" * 70)
