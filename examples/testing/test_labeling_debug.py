"""Debug script to test labeling without pytest."""
import sys
sys.path.insert(0, r"c:\Users\kay\Documents\Projects\AutoTrader\Autotrader")

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from autotrader.data_prep.labeling import LabelFactory

# Create simple test data
n = 100
t0 = datetime(2025, 1, 1, 9, 30, 0)
ts = [t0 + timedelta(seconds=i) for i in range(n)]

mid = 100 + np.cumsum(np.random.normal(0, 0.01, size=n))
df = pd.DataFrame({
    "timestamp": ts,
    "open": mid,
    "high": mid + 0.01,
    "low": mid - 0.01,
    "close": mid,
    "volume": np.ones(n) * 100,
    "bid": mid - 0.01,
    "ask": mid + 0.01,
    "bid_vol": np.ones(n) * 50,
    "ask_vol": np.ones(n) * 50,
})

print("DataFrame columns:", df.columns.tolist())
print("First few rows:")
print(df.head())

print("\nRunning LabelFactory.create...")
try:
    out = LabelFactory.create(df, method="classification", horizon_seconds=10)
    print("SUCCESS! Output columns:", out.columns.tolist())
    print(out.head())
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
