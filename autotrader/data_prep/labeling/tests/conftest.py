"""
Shared fixtures and synthetic market data generator for labeling tests.

Provides realistic synthetic market data with microstructure noise,
bid/ask spreads, and volume imbalances.
"""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta

# Fixed RNG for reproducible tests
RNG = np.random.default_rng(42)


@pytest.fixture(scope="session")
def bars_1s_2h():
    """
    2 hours of 1-second bars with microstructure noise and L1 volumes.
    
    Returns:
        DataFrame with realistic synthetic market data:
        - Random walk mid-price with microstructure bounce
        - Dynamic bid/ask spreads
        - Volume-weighted order book depth
        - OHLCV bars
    """
    n = 2 * 60 * 60  # 7,200 bars
    t0 = datetime(2025, 1, 1, 9, 30, 0)
    ts = [t0 + timedelta(seconds=i) for i in range(n)]

    # Base random walk + microstructure bounce
    mid = 100 + np.cumsum(RNG.normal(0, 0.01, size=n))
    spread = np.clip(RNG.normal(0.02, 0.005, size=n), 0.01, 0.05)
    bid = mid - spread / 2
    ask = mid + spread / 2

    # L1 volumes (Poisson-distributed with realistic skew)
    bid_sz = np.clip(RNG.poisson(50, size=n).astype(float), 1, None)
    ask_sz = np.clip(RNG.poisson(50, size=n).astype(float), 1, None)

    # Simple OHLC around bid/ask
    open_ = mid + RNG.normal(0, 0.01, size=n)
    close = mid + RNG.normal(0, 0.01, size=n)
    high = np.maximum(open_, close) + np.abs(RNG.normal(0, 0.01, size=n))
    low = np.minimum(open_, close) - np.abs(RNG.normal(0, 0.01, size=n))
    vol = np.clip(RNG.poisson(200, size=n).astype(float), 1, None)

    df = pd.DataFrame({
        "timestamp": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "bid": bid,
        "ask": ask,
        "bid_vol": bid_sz,
        "ask_vol": ask_sz,
    })
    return df


@pytest.fixture(scope="session")
def bars_5m_1d():
    """
    1 day of 5-minute bars (288 bars).
    
    Useful for faster tests that don't need high-frequency data.
    """
    n = 288  # 24 hours * 12 bars/hour
    t0 = datetime(2025, 1, 1, 9, 30, 0)
    ts = [t0 + timedelta(minutes=5 * i) for i in range(n)]

    # Base trend + noise
    mid = 100 + np.cumsum(RNG.normal(0, 0.05, size=n))
    spread = np.clip(RNG.normal(0.03, 0.01, size=n), 0.02, 0.08)
    bid = mid - spread / 2
    ask = mid + spread / 2

    bid_sz = np.clip(RNG.poisson(500, size=n).astype(float), 10, None)
    ask_sz = np.clip(RNG.poisson(500, size=n).astype(float), 10, None)

    open_ = mid + RNG.normal(0, 0.02, size=n)
    close = mid + RNG.normal(0, 0.02, size=n)
    high = np.maximum(open_, close) + np.abs(RNG.normal(0, 0.02, size=n))
    low = np.minimum(open_, close) - np.abs(RNG.normal(0, 0.02, size=n))
    vol = np.clip(RNG.poisson(2000, size=n).astype(float), 100, None)

    df = pd.DataFrame({
        "timestamp": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "bid": bid,
        "ask": ask,
        "bid_vol": bid_sz,
        "ask_vol": ask_sz,
    })
    return df


@pytest.fixture(scope="session")
def tiny_bars_nan(bars_1s_2h):
    """
    Small dataset (300 bars) with injected NaNs and edge cases.
    
    Tests robustness to:
    - Missing bid/ask prices
    - Zero volumes
    - Edge-of-day timestamps
    """
    df = bars_1s_2h.copy().iloc[:300].reset_index(drop=True)
    
    # Inject NaNs/zeros to test robustness
    df.loc[5, "bid"] = np.nan
    df.loc[6, "ask"] = np.nan
    df.loc[7, "volume"] = 0.0
    df.loc[8, "bid_vol"] = 0.0
    df.loc[9, "ask_vol"] = 0.0
    
    return df


@pytest.fixture(scope="session")
def trending_bars():
    """
    Strong trending data (500 bars with +10 bps/bar drift).
    
    Used to test that labelers capture trends correctly.
    """
    n = 500
    t0 = datetime(2025, 1, 1, 9, 30, 0)
    ts = [t0 + timedelta(seconds=i) for i in range(n)]

    # Strong trend: +10 bps per bar on average
    trend = np.arange(n) * 0.001  # 0.1% per bar = 10 bps
    noise = RNG.normal(0, 0.01, size=n)
    mid = 100 + trend + noise

    spread = 0.02
    bid = mid - spread / 2
    ask = mid + spread / 2

    bid_sz = np.full(n, 100.0)
    ask_sz = np.full(n, 100.0)

    open_ = mid
    close = mid
    high = mid + 0.01
    low = mid - 0.01
    vol = np.full(n, 1000.0)

    df = pd.DataFrame({
        "timestamp": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "bid": bid,
        "ask": ask,
        "bid_vol": bid_sz,
        "ask_vol": ask_sz,
    })
    return df


@pytest.fixture(scope="session")
def mean_reverting_bars():
    """
    Mean-reverting data (500 bars with AR(1) process).
    
    Used to test that labelers handle mean reversion.
    """
    n = 500
    t0 = datetime(2025, 1, 1, 9, 30, 0)
    ts = [t0 + timedelta(seconds=i) for i in range(n)]

    # AR(1) mean reversion: x[t] = 0.7 * x[t-1] + noise
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = 0.7 * x[i - 1] + RNG.normal(0, 0.02)
    
    mid = 100 + x

    spread = 0.02
    bid = mid - spread / 2
    ask = mid + spread / 2

    bid_sz = np.full(n, 100.0)
    ask_sz = np.full(n, 100.0)

    open_ = mid
    close = mid
    high = mid + 0.01
    low = mid - 0.01
    vol = np.full(n, 1000.0)

    df = pd.DataFrame({
        "timestamp": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
        "bid": bid,
        "ask": ask,
        "bid_vol": bid_sz,
        "ask_vol": ask_sz,
    })
    return df


# Required input columns (schema contract)
REQUIRED_INPUT_COLS = {
    "timestamp", "open", "high", "low", "close", "volume",
    "bid", "ask", "bid_vol", "ask_vol"
}
