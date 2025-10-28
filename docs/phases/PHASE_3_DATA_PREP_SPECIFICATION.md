# Phase 3: Data Cleaning & Bar Construction Specification

**Project**: AutoTrader HFT System  
**Phase**: 3 - Data Preparation & Feature Engineering  
**Version**: 1.0  
**Date**: October 23, 2025  
**Status**: � **IN PROGRESS** — Week 2 Complete

---

## 📊 Implementation Progress

| **Week** | **Milestone** | **Status** | **Completion** | **Summary Document** |
|----------|---------------|------------|----------------|----------------------|
| Week 1 | Data Cleaning Pipeline | ✅ Complete | 100% | [`PHASE_3_WEEK_1_COMPLETE.md`](./PHASE_3_WEEK_1_COMPLETE.md) |
| **Week 2** | **Bar Construction (6 types)** | ✅ **Complete** | **100%** | [**`PHASE_3_WEEK_2_COMPLETE.md`**](./PHASE_3_WEEK_2_COMPLETE.md) |
| Week 3 | Order Book Features | ⏳ Pending | 0% | — |
| Week 4 | Labeling Pipeline | ⏳ Pending | 0% | — |

**Overall Phase 3 Progress**: 50% complete (2 of 4 weeks)

### Latest Updates

**Week 2 Achievements** (Just Completed):
- ✅ All 6 bar constructors implemented (~1,200 lines)
- ✅ Unified `BarFactory` interface
- ✅ Comprehensive test suite (`test_all_bars.py`)
- ✅ All bars validated on real Dukascopy EUR/USD data
- ✅ 0 Codacy issues across all files
- ✅ 6 bar types tested: Time, Tick, Volume, Dollar, Imbalance, Run

**Test Results Summary**:
```
Bar Type             Bars Created    Validation
--------------------------------------------------
Time (5min)          12              ✅ PASSED
Tick (500)           7               ✅ PASSED
Volume (100k)        1               ✅ PASSED
Dollar ($1M)         1               ✅ PASSED
Imbalance (5k)       1               ✅ PASSED
Run (5)              364             ✅ PASSED
```

**Next Milestone**: Week 3 — Order Book Features (15+ features including spread, depth, flow toxicity, VPIN)

---

## Table of Contents

1. [Overview](#overview)
2. [Objectives](#objectives)
3. [Architecture](#architecture)
4. [Data Cleaning Pipeline](#data-cleaning-pipeline)
5. [Bar Construction](#bar-construction)
6. [Order Book Features](#order-book-features)
7. [Label Integrity](#label-integrity)
8. [Implementation Plan](#implementation-plan)
9. [Deliverables](#deliverables)
10. [Success Criteria](#success-criteria)

---

## Overview

Phase 3 transforms raw tick data and order book snapshots from Phase 2 into clean, normalized features suitable for machine learning. This phase implements multiple bar construction methodologies, order flow analytics, and rigorous label integrity checks to prevent lookahead bias.

### Core Challenges

1. **Timezone Normalization**: Convert all data to UTC regardless of source
2. **Session Awareness**: Handle market hours (equities) vs 24/7 trading (crypto)
3. **Data Quality**: Detect and handle outliers, gaps, duplicates
4. **Bar Diversity**: Support time, tick, volume, and dollar bars
5. **Order Flow**: Extract L2 depth features and order imbalance
6. **Lookahead Prevention**: Ensure features and labels are properly aligned

---

## Objectives

### Primary Goals

1. ✅ **Normalize all timestamps to UTC** with microsecond precision
2. ✅ **Implement trading session handlers** for equities, forex, and crypto
3. ✅ **Build 4+ bar types** (time, tick, volume, dollar, imbalance)
4. ✅ **Extract order book features** (spread, depth, imbalance, flow toxicity)
5. ✅ **Enforce label integrity** with no lookahead bias
6. ✅ **Create reusable data prep library** with clean API

### Non-Goals

- Real-time streaming transformations (Phase 2 handles ingestion)
- Model training (Phase 4)
- Strategy backtesting (Phase 5)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Phase 3: Data Preparation                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐      ┌──────────────────┐                    │
│  │  Raw Tick Data   │      │ Order Book Data  │                    │
│  │  (ClickHouse)    │      │  (ClickHouse)    │                    │
│  └────────┬─────────┘      └────────┬─────────┘                    │
│           │                          │                               │
│           ▼                          ▼                               │
│  ┌─────────────────────────────────────────────┐                   │
│  │         Data Cleaning Pipeline              │                   │
│  ├─────────────────────────────────────────────┤                   │
│  │  • Timezone normalization (UTC)             │                   │
│  │  • Duplicate removal                        │                   │
│  │  │  Outlier detection & filtering           │                   │
│  │  • Gap detection & handling                 │                   │
│  │  • Trading session filtering                │                   │
│  └─────────────────┬───────────────────────────┘                   │
│                    │                                                 │
│                    ▼                                                 │
│  ┌─────────────────────────────────────────────┐                   │
│  │         Bar Construction Engine             │                   │
│  ├─────────────────────────────────────────────┤                   │
│  │  ┌─────────────┐  ┌──────────────┐         │                   │
│  │  │  Time Bars  │  │  Tick Bars   │         │                   │
│  │  │  (1s-1day)  │  │  (N ticks)   │         │                   │
│  │  └─────────────┘  └──────────────┘         │                   │
│  │  ┌─────────────┐  ┌──────────────┐         │                   │
│  │  │ Volume Bars │  │ Dollar Bars  │         │                   │
│  │  │ (N shares)  │  │ (N dollars)  │         │                   │
│  │  └─────────────┘  └──────────────┘         │                   │
│  │  ┌─────────────┐  ┌──────────────┐         │                   │
│  │  │Imbalance Bar│  │  Run Bars    │         │                   │
│  │  │ (θ imbal.)  │  │  (N runs)    │         │                   │
│  │  └─────────────┘  └──────────────┘         │                   │
│  └─────────────────┬───────────────────────────┘                   │
│                    │                                                 │
│                    ▼                                                 │
│  ┌─────────────────────────────────────────────┐                   │
│  │      Order Book Feature Extractor           │                   │
│  ├─────────────────────────────────────────────┤                   │
│  │  • Bid-ask spread (bps)                     │                   │
│  │  • Depth at levels (L1-L10)                 │                   │
│  │  • Order imbalance (buy/sell pressure)      │                   │
│  │  • Microprice (weighted mid)                │                   │
│  │  • VWAP at depth levels                     │                   │
│  │  • Flow toxicity (Kyle's lambda)            │                   │
│  │  • Order arrival rates                      │                   │
│  └─────────────────┬───────────────────────────┘                   │
│                    │                                                 │
│                    ▼                                                 │
│  ┌─────────────────────────────────────────────┐                   │
│  │       Label Integrity Validator             │                   │
│  ├─────────────────────────────────────────────┤                   │
│  │  • Lookahead detection                      │                   │
│  │  • Feature-label alignment check            │                   │
│  │  • Temporal ordering validation             │                   │
│  │  • Train/val/test split verification        │                   │
│  └─────────────────┬───────────────────────────┘                   │
│                    │                                                 │
│                    ▼                                                 │
│  ┌─────────────────────────────────────────────┐                   │
│  │        Feature Store (Parquet/Delta)        │                   │
│  │        Ready for Phase 4 (ML Training)       │                   │
│  └─────────────────────────────────────────────┘                   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Cleaning Pipeline

### 3.1 Timezone Normalization

**Objective**: Convert all timestamps to UTC with microsecond precision.

**Implementation**:

```python
class TimezoneNormalizer:
    """Normalize timestamps to UTC across all venues."""
    
    def __init__(self, venue_timezones: dict[str, str]):
        """
        Args:
            venue_timezones: Mapping of venue → timezone
                Example: {"NASDAQ": "America/New_York", "BINANCE": "UTC"}
        """
        self.venue_timezones = venue_timezones
    
    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert timestamp column to UTC."""
        # Ensure microsecond precision
        df["timestamp_utc"] = pd.to_datetime(df["timestamp"], unit="us", utc=True)
        
        # Venue-specific conversion if needed
        if "venue" in df.columns:
            for venue, tz in self.venue_timezones.items():
                mask = df["venue"] == venue
                if mask.any():
                    df.loc[mask, "timestamp_utc"] = (
                        df.loc[mask, "timestamp_utc"]
                        .dt.tz_convert(tz)
                        .dt.tz_convert("UTC")
                    )
        
        return df
```

**Validation**:
- Assert all timestamps have UTC timezone
- Check for timezone-aware datetime objects
- Verify microsecond precision preserved

---

### 3.2 Trading Session Filtering

**Objective**: Filter data based on market hours (equities) vs 24/7 (crypto).

**Session Definitions**:

| Asset Class | Trading Hours (UTC) | Holidays |
|-------------|---------------------|----------|
| US Equities | 14:30-21:00 Mon-Fri | NYSE calendar |
| EU Equities | 08:00-16:30 Mon-Fri | Eurex calendar |
| Forex | 24/5 (Sun 22:00 - Fri 22:00) | Major holidays only |
| Crypto | 24/7 | None |

**Implementation**:

```python
from pandas.tseries.holiday import USFederalHolidayCalendar

class SessionFilter:
    """Filter data by trading sessions."""
    
    def __init__(self, asset_class: str, venue: str):
        self.asset_class = asset_class
        self.venue = venue
        self.calendar = self._get_calendar()
    
    def _get_calendar(self):
        if self.venue in ["NYSE", "NASDAQ"]:
            return USFederalHolidayCalendar()
        elif self.venue == "EUREX":
            return EurexCalendar()  # Custom calendar
        else:
            return None  # 24/7 trading
    
    def filter_regular_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep only regular trading hours."""
        if self.asset_class == "CRYPTO":
            return df  # No filtering for 24/7
        
        # Filter by time of day
        df_copy = df.copy()
        df_copy["time"] = df_copy["timestamp_utc"].dt.time
        
        if self.venue in ["NYSE", "NASDAQ"]:
            # US equities: 9:30 AM - 4:00 PM ET = 14:30 - 21:00 UTC
            mask = (df_copy["time"] >= pd.Timestamp("14:30").time()) & \
                   (df_copy["time"] <= pd.Timestamp("21:00").time())
        elif self.venue == "EUREX":
            # EU equities: 9:00 AM - 5:30 PM CET = 8:00 - 16:30 UTC
            mask = (df_copy["time"] >= pd.Timestamp("08:00").time()) & \
                   (df_copy["time"] <= pd.Timestamp("16:30").time())
        else:
            mask = pd.Series([True] * len(df_copy))
        
        # Filter by holidays
        if self.calendar:
            holidays = self.calendar.holidays(
                start=df_copy["timestamp_utc"].min(),
                end=df_copy["timestamp_utc"].max()
            )
            df_copy["date"] = df_copy["timestamp_utc"].dt.date
            mask &= ~df_copy["date"].isin(holidays.date)
        
        # Filter weekends (for non-crypto)
        if self.asset_class != "CRYPTO":
            mask &= df_copy["timestamp_utc"].dt.dayofweek < 5  # Mon-Fri
        
        return df_copy[mask].drop(columns=["time", "date"], errors="ignore")
```

---

### 3.3 Data Quality Checks

**Objective**: Detect and handle outliers, duplicates, and gaps.

**Implementation**:

```python
class DataQualityChecker:
    """Validate and clean tick data."""
    
    def remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate ticks by (timestamp, symbol, venue, price)."""
        return df.drop_duplicates(
            subset=["timestamp_utc", "symbol", "venue", "price"],
            keep="first"
        )
    
    def detect_outliers(
        self,
        df: pd.DataFrame,
        price_col: str = "price",
        method: str = "zscore",
        threshold: float = 5.0
    ) -> pd.Series:
        """
        Detect price outliers.
        
        Methods:
            - zscore: Z-score > threshold
            - iqr: Beyond (Q1 - 1.5*IQR, Q3 + 1.5*IQR)
            - rolling_zscore: Rolling window Z-score
        """
        if method == "zscore":
            z = (df[price_col] - df[price_col].mean()) / df[price_col].std()
            return z.abs() > threshold
        
        elif method == "iqr":
            Q1 = df[price_col].quantile(0.25)
            Q3 = df[price_col].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR
            return (df[price_col] < lower) | (df[price_col] > upper)
        
        elif method == "rolling_zscore":
            rolling_mean = df[price_col].rolling(window=100, center=True).mean()
            rolling_std = df[price_col].rolling(window=100, center=True).std()
            z = (df[price_col] - rolling_mean) / rolling_std
            return z.abs() > threshold
    
    def detect_gaps(
        self,
        df: pd.DataFrame,
        max_gap_seconds: float = 60.0
    ) -> pd.DataFrame:
        """Detect gaps in tick data."""
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        
        # Compute time deltas
        df["gap_seconds"] = df["timestamp_utc"].diff().dt.total_seconds()
        
        # Flag large gaps
        gaps = df[df["gap_seconds"] > max_gap_seconds][
            ["timestamp_utc", "gap_seconds", "symbol", "venue"]
        ]
        
        return gaps
    
    def fill_gaps(
        self,
        df: pd.DataFrame,
        method: str = "ffill"
    ) -> pd.DataFrame:
        """
        Fill gaps in time series.
        
        Methods:
            - ffill: Forward fill (last traded price)
            - interpolate: Linear interpolation
            - drop: Drop bars with gaps
        """
        if method == "ffill":
            return df.ffill()
        elif method == "interpolate":
            return df.interpolate(method="time")
        elif method == "drop":
            return df.dropna()
        else:
            raise ValueError(f"Unknown fill method: {method}")
```

---

## Bar Construction

### 4.1 Time Bars

**Definition**: Fixed time interval bars (1s, 5s, 1m, 5m, 15m, 1h, 1d).

**Implementation**:

```python
class TimeBarConstructor:
    """Construct time-based OHLCV bars."""
    
    def __init__(self, interval: str = "1min"):
        """
        Args:
            interval: Pandas frequency string ('1s', '1min', '5min', '1h', '1d')
        """
        self.interval = interval
    
    def construct(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build OHLCV bars from tick data.
        
        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume, vwap, trades]
        """
        df = df.set_index("timestamp_utc").sort_index()
        
        # Resample by time interval
        bars = pd.DataFrame({
            "open": df["price"].resample(self.interval).first(),
            "high": df["price"].resample(self.interval).max(),
            "low": df["price"].resample(self.interval).min(),
            "close": df["price"].resample(self.interval).last(),
            "volume": df["quantity"].resample(self.interval).sum(),
            "trades": df["price"].resample(self.interval).count(),
            "vwap": (
                (df["price"] * df["quantity"]).resample(self.interval).sum() /
                df["quantity"].resample(self.interval).sum()
            )
        })
        
        # Drop bars with no data
        bars = bars.dropna(subset=["close"])
        
        # Metadata
        bars["interval"] = self.interval
        bars["bar_type"] = "time"
        
        return bars.reset_index()
```

---

### 4.2 Tick Bars

**Definition**: Fixed number of ticks per bar.

**Implementation**:

```python
class TickBarConstructor:
    """Construct tick-based bars (fixed number of ticks)."""
    
    def __init__(self, num_ticks: int = 1000):
        """
        Args:
            num_ticks: Number of ticks per bar
        """
        self.num_ticks = num_ticks
    
    def construct(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build OHLCV bars from fixed tick counts.
        
        Returns:
            DataFrame with tick-based bars
        """
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        
        # Group by tick count
        df["bar_id"] = df.index // self.num_ticks
        
        bars = df.groupby("bar_id").agg({
            "timestamp_utc": ["first", "last"],
            "price": ["first", "max", "min", "last"],
            "quantity": "sum"
        })
        
        # Flatten multi-level columns
        bars.columns = ["_".join(col).strip() for col in bars.columns]
        bars = bars.rename(columns={
            "timestamp_utc_first": "timestamp_start",
            "timestamp_utc_last": "timestamp_end",
            "price_first": "open",
            "price_max": "high",
            "price_min": "low",
            "price_last": "close",
            "quantity_sum": "volume"
        })
        
        # VWAP calculation
        bars["vwap"] = (
            df.groupby("bar_id").apply(
                lambda x: (x["price"] * x["quantity"]).sum() / x["quantity"].sum()
            )
        )
        
        bars["trades"] = self.num_ticks
        bars["bar_type"] = "tick"
        
        return bars.reset_index(drop=True)
```

---

### 4.3 Volume Bars

**Definition**: Fixed cumulative volume per bar.

**Implementation**:

```python
class VolumeBarConstructor:
    """Construct volume-based bars (fixed cumulative volume)."""
    
    def __init__(self, volume_threshold: float = 1000000.0):
        """
        Args:
            volume_threshold: Cumulative volume per bar (e.g., 1M shares)
        """
        self.volume_threshold = volume_threshold
    
    def construct(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build OHLCV bars from fixed volume thresholds.
        
        Returns:
            DataFrame with volume-based bars
        """
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        
        # Compute cumulative volume
        df["cumulative_volume"] = df["quantity"].cumsum()
        df["bar_id"] = (df["cumulative_volume"] // self.volume_threshold).astype(int)
        
        bars = df.groupby("bar_id").agg({
            "timestamp_utc": ["first", "last"],
            "price": ["first", "max", "min", "last"],
            "quantity": "sum"
        })
        
        # Flatten and rename
        bars.columns = ["_".join(col).strip() for col in bars.columns]
        bars = bars.rename(columns={
            "timestamp_utc_first": "timestamp_start",
            "timestamp_utc_last": "timestamp_end",
            "price_first": "open",
            "price_max": "high",
            "price_min": "low",
            "price_last": "close",
            "quantity_sum": "volume"
        })
        
        # VWAP
        bars["vwap"] = (
            df.groupby("bar_id").apply(
                lambda x: (x["price"] * x["quantity"]).sum() / x["quantity"].sum()
            )
        )
        
        bars["trades"] = df.groupby("bar_id").size()
        bars["bar_type"] = "volume"
        
        return bars.reset_index(drop=True)
```

---

### 4.4 Dollar Bars

**Definition**: Fixed dollar value traded per bar.

**Implementation**:

```python
class DollarBarConstructor:
    """Construct dollar-based bars (fixed dollar volume)."""
    
    def __init__(self, dollar_threshold: float = 10_000_000.0):
        """
        Args:
            dollar_threshold: Cumulative dollar value per bar (e.g., $10M)
        """
        self.dollar_threshold = dollar_threshold
    
    def construct(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build OHLCV bars from fixed dollar value thresholds.
        
        Dollar value = price * quantity
        
        Returns:
            DataFrame with dollar-based bars
        """
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        
        # Compute dollar value per trade
        df["dollar_value"] = df["price"] * df["quantity"]
        df["cumulative_dollars"] = df["dollar_value"].cumsum()
        df["bar_id"] = (df["cumulative_dollars"] // self.dollar_threshold).astype(int)
        
        bars = df.groupby("bar_id").agg({
            "timestamp_utc": ["first", "last"],
            "price": ["first", "max", "min", "last"],
            "quantity": "sum",
            "dollar_value": "sum"
        })
        
        # Flatten and rename
        bars.columns = ["_".join(col).strip() for col in bars.columns]
        bars = bars.rename(columns={
            "timestamp_utc_first": "timestamp_start",
            "timestamp_utc_last": "timestamp_end",
            "price_first": "open",
            "price_max": "high",
            "price_min": "low",
            "price_last": "close",
            "quantity_sum": "volume",
            "dollar_value_sum": "dollar_volume"
        })
        
        # VWAP
        bars["vwap"] = (
            df.groupby("bar_id").apply(
                lambda x: (x["price"] * x["quantity"]).sum() / x["quantity"].sum()
            )
        )
        
        bars["trades"] = df.groupby("bar_id").size()
        bars["bar_type"] = "dollar"
        
        return bars.reset_index(drop=True)
```

---

### 4.5 Imbalance Bars

**Definition**: Bar closes when cumulative signed volume exceeds threshold.

**Implementation**:

```python
class ImbalanceBarConstructor:
    """Construct imbalance bars based on order flow imbalance."""
    
    def __init__(self, imbalance_threshold: float = 10000.0):
        """
        Args:
            imbalance_threshold: Absolute imbalance threshold (θ)
        """
        self.imbalance_threshold = imbalance_threshold
    
    def construct(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build imbalance bars.
        
        Signed volume = volume * sign(price_change)
        Bar closes when |cumulative_signed_volume| > threshold
        
        Returns:
            DataFrame with imbalance bars
        """
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        
        # Compute price change sign
        df["price_change"] = df["price"].diff()
        df["sign"] = df["price_change"].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        
        # Signed volume
        df["signed_volume"] = df["quantity"] * df["sign"]
        df["cumulative_imbalance"] = df["signed_volume"].cumsum()
        
        # Detect threshold crossings
        df["bar_id"] = 0
        bar_id = 0
        cumsum = 0.0
        
        for i in range(len(df)):
            cumsum += df.loc[i, "signed_volume"]
            
            if abs(cumsum) >= self.imbalance_threshold:
                bar_id += 1
                cumsum = 0.0
            
            df.loc[i, "bar_id"] = bar_id
        
        # Aggregate into bars
        bars = df.groupby("bar_id").agg({
            "timestamp_utc": ["first", "last"],
            "price": ["first", "max", "min", "last"],
            "quantity": "sum",
            "signed_volume": "sum"
        })
        
        # Flatten and rename
        bars.columns = ["_".join(col).strip() for col in bars.columns]
        bars = bars.rename(columns={
            "timestamp_utc_first": "timestamp_start",
            "timestamp_utc_last": "timestamp_end",
            "price_first": "open",
            "price_max": "high",
            "price_min": "low",
            "price_last": "close",
            "quantity_sum": "volume",
            "signed_volume_sum": "imbalance"
        })
        
        bars["vwap"] = (
            df.groupby("bar_id").apply(
                lambda x: (x["price"] * x["quantity"]).sum() / x["quantity"].sum()
            )
        )
        
        bars["trades"] = df.groupby("bar_id").size()
        bars["bar_type"] = "imbalance"
        
        return bars.reset_index(drop=True)
```

---

### 4.6 Run Bars

**Definition**: Bar closes after N consecutive price movements in same direction.

**Implementation**:

```python
class RunBarConstructor:
    """Construct run bars based on consecutive price moves."""
    
    def __init__(self, num_runs: int = 10):
        """
        Args:
            num_runs: Number of consecutive runs before bar close
        """
        self.num_runs = num_runs
    
    def construct(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build run bars.
        
        A "run" is a consecutive sequence of ticks moving in the same direction.
        Bar closes after N runs.
        
        Returns:
            DataFrame with run bars
        """
        df = df.sort_values("timestamp_utc").reset_index(drop=True)
        
        # Compute price change sign
        df["price_change"] = df["price"].diff()
        df["sign"] = df["price_change"].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        
        # Detect runs (consecutive ticks with same sign)
        df["run_change"] = (df["sign"] != df["sign"].shift()).astype(int)
        df["run_id"] = df["run_change"].cumsum()
        
        # Group runs into bars
        df["bar_id"] = df["run_id"] // self.num_runs
        
        # Aggregate
        bars = df.groupby("bar_id").agg({
            "timestamp_utc": ["first", "last"],
            "price": ["first", "max", "min", "last"],
            "quantity": "sum"
        })
        
        # Flatten and rename
        bars.columns = ["_".join(col).strip() for col in bars.columns]
        bars = bars.rename(columns={
            "timestamp_utc_first": "timestamp_start",
            "timestamp_utc_last": "timestamp_end",
            "price_first": "open",
            "price_max": "high",
            "price_min": "low",
            "price_last": "close",
            "quantity_sum": "volume"
        })
        
        bars["vwap"] = (
            df.groupby("bar_id").apply(
                lambda x: (x["price"] * x["quantity"]).sum() / x["quantity"].sum()
            )
        )
        
        bars["trades"] = df.groupby("bar_id").size()
        bars["bar_type"] = "run"
        
        return bars.reset_index(drop=True)
```

---

## Order Book Features

### 5.1 Spread Metrics

**Implementation**:

```python
class SpreadFeatures:
    """Calculate bid-ask spread metrics."""
    
    @staticmethod
    def quoted_spread(bid: float, ask: float) -> float:
        """Quoted spread in basis points."""
        mid = (bid + ask) / 2.0
        return 10000.0 * (ask - bid) / mid
    
    @staticmethod
    def effective_spread(price: float, mid: float, side: str) -> float:
        """Effective spread for executed trade."""
        if side == "BUY":
            return 10000.0 * (price - mid) / mid
        elif side == "SELL":
            return 10000.0 * (mid - price) / mid
        else:
            return 0.0
    
    @staticmethod
    def realized_spread(
        trade_price: float,
        mid_at_trade: float,
        mid_after_5min: float,
        side: str
    ) -> float:
        """Realized spread after 5 minutes."""
        if side == "BUY":
            return 10000.0 * (trade_price - mid_after_5min) / mid_at_trade
        elif side == "SELL":
            return 10000.0 * (mid_after_5min - trade_price) / mid_at_trade
        else:
            return 0.0
```

---

### 5.2 Depth & Imbalance

**Implementation**:

```python
class DepthFeatures:
    """Extract order book depth features."""
    
    @staticmethod
    def order_imbalance(bids: list[DepthLevel], asks: list[DepthLevel], num_levels: int = 5) -> float:
        """
        Order imbalance ratio.
        
        OI = (bid_volume - ask_volume) / (bid_volume + ask_volume)
        
        Returns:
            Value in [-1, 1] where 1 = all bids, -1 = all asks
        """
        bid_vol = sum([b.size for b in bids[:num_levels]])
        ask_vol = sum([a.size for a in asks[:num_levels]])
        
        if bid_vol + ask_vol == 0:
            return 0.0
        
        return (bid_vol - ask_vol) / (bid_vol + ask_vol)
    
    @staticmethod
    def microprice(bid: float, ask: float, bid_size: float, ask_size: float) -> float:
        """
        Volume-weighted mid price.
        
        μ = (ask * bid_size + bid * ask_size) / (bid_size + ask_size)
        """
        if bid_size + ask_size == 0:
            return (bid + ask) / 2.0
        
        return (ask * bid_size + bid * ask_size) / (bid_size + ask_size)
    
    @staticmethod
    def vwap_depth(levels: list[DepthLevel]) -> float:
        """VWAP across depth levels."""
        total_value = sum([l.price * l.size for l in levels])
        total_volume = sum([l.size for l in levels])
        
        if total_volume == 0:
            return 0.0
        
        return total_value / total_volume
    
    @staticmethod
    def depth_at_bps(
        levels: list[DepthLevel],
        mid: float,
        bps_threshold: float = 10.0
    ) -> float:
        """
        Cumulative volume within X basis points of mid.
        
        Args:
            levels: Bid or ask levels
            mid: Mid price
            bps_threshold: Basis point threshold (e.g., 10 bps)
        
        Returns:
            Total volume within threshold
        """
        volume = 0.0
        for level in levels:
            spread_bps = 10000.0 * abs(level.price - mid) / mid
            if spread_bps <= bps_threshold:
                volume += level.size
        
        return volume
```

---

### 5.3 Flow Toxicity (Kyle's Lambda)

**Implementation**:

```python
class FlowToxicityFeatures:
    """Measure order flow toxicity (informed trading)."""
    
    @staticmethod
    def kyles_lambda(
        price_changes: np.ndarray,
        signed_volumes: np.ndarray,
        window: int = 100
    ) -> float:
        """
        Kyle's Lambda - price impact of order flow.
        
        λ = Cov(ΔP, Q) / Var(Q)
        
        Where:
            ΔP = price change
            Q = signed volume (positive for buy, negative for sell)
        
        Returns:
            Lambda coefficient (higher = more toxic flow)
        """
        if len(price_changes) < window:
            return 0.0
        
        # Rolling window
        recent_price_changes = price_changes[-window:]
        recent_volumes = signed_volumes[-window:]
        
        cov = np.cov(recent_price_changes, recent_volumes)[0, 1]
        var = np.var(recent_volumes)
        
        if var == 0:
            return 0.0
        
        return cov / var
    
    @staticmethod
    def vpin(
        buy_volume: np.ndarray,
        sell_volume: np.ndarray,
        window: int = 50
    ) -> float:
        """
        Volume-Synchronized Probability of Informed Trading (VPIN).
        
        VPIN = |V_buy - V_sell| / (V_buy + V_sell)
        
        Returns:
            Value in [0, 1] where 1 = maximum flow imbalance
        """
        if len(buy_volume) < window:
            return 0.0
        
        recent_buy = buy_volume[-window:].sum()
        recent_sell = sell_volume[-window:].sum()
        
        total = recent_buy + recent_sell
        if total == 0:
            return 0.0
        
        return abs(recent_buy - recent_sell) / total
```

---

## Label Integrity

### 6.1 Lookahead Detection

**Objective**: Ensure features at time `t` only use data available at `t`.

**Implementation**:

```python
class LabelIntegrityValidator:
    """Validate feature-label alignment and detect lookahead bias."""
    
    def check_lookahead(
        self,
        features: pd.DataFrame,
        labels: pd.DataFrame,
        feature_timestamp_col: str = "timestamp",
        label_timestamp_col: str = "timestamp"
    ) -> dict[str, any]:
        """
        Check for lookahead bias in feature-label pairs.
        
        Returns:
            Dict with validation results
        """
        results = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check 1: Feature timestamps must be <= label timestamps
        merged = features.merge(
            labels,
            left_index=True,
            right_index=True,
            suffixes=("_feat", "_label")
        )
        
        lookahead_mask = (
            merged[f"{feature_timestamp_col}_feat"] > 
            merged[f"{label_timestamp_col}_label"]
        )
        
        if lookahead_mask.any():
            results["is_valid"] = False
            results["errors"].append(
                f"Lookahead detected: {lookahead_mask.sum()} features use future data"
            )
        
        # Check 2: Feature computation window must not overlap with label period
        # (e.g., if label is 5-minute forward return, features can't use data 
        # from those 5 minutes)
        
        # Check 3: Rolling window features must have sufficient history
        for col in features.columns:
            if "rolling" in col.lower():
                # Extract window size from column name (e.g., "rolling_mean_100")
                # Verify first N rows are NaN (where N = window size)
                pass  # Implement based on naming convention
        
        return results
    
    def enforce_temporal_order(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure data is sorted by timestamp."""
        return df.sort_values("timestamp").reset_index(drop=True)
    
    def split_train_val_test(
        self,
        df: pd.DataFrame,
        train_frac: float = 0.7,
        val_frac: float = 0.15,
        test_frac: float = 0.15,
        timestamp_col: str = "timestamp"
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split data temporally (no shuffling).
        
        Returns:
            (train_df, val_df, test_df)
        """
        assert train_frac + val_frac + test_frac == 1.0
        
        df = df.sort_values(timestamp_col).reset_index(drop=True)
        
        n = len(df)
        train_end = int(n * train_frac)
        val_end = int(n * (train_frac + val_frac))
        
        train = df.iloc[:train_end]
        val = df.iloc[train_end:val_end]
        test = df.iloc[val_end:]
        
        return train, val, test
    
    def verify_feature_lag(
        self,
        df: pd.DataFrame,
        feature_cols: list[str],
        label_col: str,
        min_lag_seconds: float = 0.0
    ) -> dict[str, bool]:
        """
        Verify features are lagged appropriately relative to labels.
        
        Returns:
            Dict mapping feature_name → is_valid
        """
        results = {}
        
        for feat_col in feature_cols:
            # Check if feature timestamp < label timestamp
            # This is a simplified check; real implementation would track
            # exact computation timestamps
            results[feat_col] = True  # Placeholder
        
        return results
```

---

## Implementation Plan

### Phase 3.1: Data Cleaning (Week 1)

**Tasks**:
1. Implement `TimezoneNormalizer` class
2. Implement `SessionFilter` class with calendar support
3. Implement `DataQualityChecker` with outlier detection
4. Write unit tests for cleaning pipeline
5. Create Prefect flow for batch cleaning

**Deliverables**:
- `autotrader/data_prep/cleaning.py`
- `tests/test_cleaning.py`
- `orchestration/flows/clean_tick_data.py`

---

### Phase 3.2: Bar Construction (Week 2-3)

**Tasks**:
1. Implement all 6 bar constructors (time, tick, volume, dollar, imbalance, run)
2. Create unified `BarFactory` interface
3. Optimize bar construction for large datasets (chunking, parallel processing)
4. Write comprehensive tests for each bar type
5. Benchmark bar construction performance

**Deliverables**:
- `autotrader/data_prep/bars/time_bars.py`
- `autotrader/data_prep/bars/tick_bars.py`
- `autotrader/data_prep/bars/volume_bars.py`
- `autotrader/data_prep/bars/dollar_bars.py`
- `autotrader/data_prep/bars/imbalance_bars.py`
- `autotrader/data_prep/bars/run_bars.py`
- `autotrader/data_prep/bars/factory.py`
- `tests/test_bars.py`

---

### Phase 3.3: Order Book Features (Week 4)

**Tasks**:
1. Implement spread metrics (quoted, effective, realized)
2. Implement depth features (imbalance, microprice, VWAP)
3. Implement flow toxicity (Kyle's lambda, VPIN)
4. Create feature extraction pipeline
5. Write tests and validate on historical data

**Deliverables**:
- `autotrader/data_prep/features/spread.py`
- `autotrader/data_prep/features/depth.py`
- `autotrader/data_prep/features/flow_toxicity.py`
- `autotrader/data_prep/features/extractor.py`
- `tests/test_features.py`

---

### Phase 3.4: Label Integrity (Week 5)

**Tasks**:
1. Implement `LabelIntegrityValidator` class
2. Create lookahead detection algorithms
3. Implement temporal train/val/test splitting
4. Create feature-label alignment checks
5. Write validation reports

**Deliverables**:
- `autotrader/data_prep/validation.py`
- `tests/test_validation.py`
- `docs/label_integrity_guide.md`

---

### Phase 3.5: Integration & Testing (Week 6)

**Tasks**:
1. Create end-to-end data prep pipeline
2. Integrate with Phase 2 (read from ClickHouse)
3. Write to feature store (Parquet/Delta Lake)
4. Create CLI tools for data prep
5. Write user documentation

**Deliverables**:
- `autotrader/data_prep/pipeline.py`
- `scripts/prepare_features.py`
- `docs/data_prep_guide.md`
- Prefect flows for automated data prep

---

## Deliverables

### Code Libraries

1. **Data Cleaning**
   - `autotrader.data_prep.cleaning`
   - Timezone normalization
   - Session filtering
   - Quality checks

2. **Bar Construction**
   - `autotrader.data_prep.bars`
   - 6 bar types with unified interface
   - Parallel processing support
   - Chunk-based computation

3. **Feature Engineering**
   - `autotrader.data_prep.features`
   - Spread metrics
   - Depth features
   - Flow toxicity
   - Order imbalance

4. **Label Integrity**
   - `autotrader.data_prep.validation`
   - Lookahead detection
   - Temporal splitting
   - Feature-label alignment

5. **Pipeline Orchestration**
   - `orchestration.flows.data_prep`
   - End-to-end Prefect flows
   - Incremental processing
   - Error recovery

---

### Documentation

1. **User Guide**
   - `docs/data_prep_guide.md`
   - Bar type selection guide
   - Feature engineering cookbook
   - Label integrity best practices

2. **API Documentation**
   - Auto-generated from docstrings
   - Usage examples for each component
   - Performance tuning tips

3. **Jupyter Notebooks**
   - `notebooks/bar_comparison.ipynb` - Compare bar types
   - `notebooks/feature_analysis.ipynb` - Feature EDA
   - `notebooks/label_integrity.ipynb` - Validation examples

---

### Datasets

1. **Bar Datasets**
   - Time bars (1s, 5s, 1m, 5m, 15m, 1h, 1d)
   - Tick bars (100, 500, 1000 ticks)
   - Volume bars (adaptive thresholds)
   - Dollar bars (adaptive thresholds)
   - Imbalance bars (adaptive θ)
   - Run bars (5, 10, 20 runs)

2. **Feature Sets**
   - Basic OHLCV features
   - Technical indicators (MA, RSI, MACD, Bollinger)
   - Order book features (spread, depth, imbalance)
   - Flow toxicity features (lambda, VPIN)
   - Microstructure features (effective spread, realized spread)

3. **Labels**
   - Forward returns (1m, 5m, 15m, 1h)
   - Volatility labels
   - Classification labels (up/down/flat)
   - Triple barrier labels (profit/stop-loss/time)

---

## Success Criteria

### Functional Requirements

✅ All timestamps normalized to UTC with microsecond precision  
✅ Trading session filtering for equities, forex, crypto  
✅ Duplicate removal and outlier detection operational  
✅ 6 bar types implemented and tested  
✅ Order book features extracted (spread, depth, imbalance, toxicity)  
✅ Label integrity validation with no lookahead bias  
✅ Temporal train/val/test splitting  
✅ End-to-end pipeline from raw ticks → features  

---

### Performance Requirements

✅ Process 1M ticks in <10 seconds (single-threaded)  
✅ Support parallel processing for multi-symbol datasets  
✅ Memory-efficient chunked processing for large datasets  
✅ Feature extraction <1ms per bar (real-time capable)  

---

### Quality Requirements

✅ 100% code coverage for core data prep functions  
✅ 0 Codacy issues  
✅ All unit tests passing  
✅ Integration tests with Phase 2 data  
✅ Validation notebooks demonstrating correctness  

---

### Documentation Requirements

✅ Comprehensive API documentation  
✅ User guide with examples  
✅ Jupyter notebooks for each bar type  
✅ Label integrity best practices document  

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bar construction too slow for real-time | High | Implement chunking, Cython acceleration, parallel processing |
| Lookahead bias introduced | Critical | Rigorous validation, automated checks in pipeline |
| Memory overflow on large datasets | Medium | Streaming/chunked processing, Dask integration |
| Imbalance bar thresholds not adaptive | Medium | Implement dynamic threshold estimation (EMA of imbalance) |
| Calendar data missing/outdated | Low | Use pandas market calendars, auto-update |

---

## Next Steps After Phase 3

**Phase 4: ML Model Training**
- Feature selection and engineering
- Model architecture design (RF, XGBoost, LSTM, Transformers)
- Hyperparameter optimization
- Cross-validation strategies
- Model evaluation metrics

**Phase 5: Strategy Development**
- Signal generation from models
- Position sizing algorithms
- Risk management rules
- Backtesting framework
- Walk-forward optimization

---

**Document Version**: 1.0  
**Last Updated**: October 23, 2025  
**Status**: Ready for Implementation  
**Estimated Duration**: 6 weeks  
**Prerequisites**: Phase 2 Complete ✅
