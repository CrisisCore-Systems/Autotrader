"""
Data cleaning pipeline for Phase 3.

This module provides:
- TimezoneNormalizer: Convert all timestamps to UTC
- SessionFilter: Filter by trading sessions (equities/forex/crypto)
- DataQualityChecker: Detect and handle outliers, duplicates, gaps
"""

from typing import Optional
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar, AbstractHolidayCalendar


class TimezoneNormalizer:
    """Normalize timestamps to UTC across all venues."""

    def __init__(self, venue_timezones: Optional[dict[str, str]] = None):
        """
        Initialize timezone normalizer.

        Args:
            venue_timezones: Mapping of venue → timezone
                Example: {"NASDAQ": "America/New_York", "BINANCE": "UTC"}
                If None, assumes all data is already in UTC
        """
        self.venue_timezones = venue_timezones or {}

    def normalize(self, df: pd.DataFrame, timestamp_col: str = "timestamp") -> pd.DataFrame:
        """
        Convert timestamp column to UTC.

        Args:
            df: DataFrame with timestamp column
            timestamp_col: Name of timestamp column

        Returns:
            DataFrame with timestamp_utc column (microsecond precision)
        """
        df = df.copy()

        # Ensure timestamp is datetime64[ns, UTC]
        if not pd.api.types.is_datetime64_any_dtype(df[timestamp_col]):
            # Try to convert from various formats
            if pd.api.types.is_integer_dtype(df[timestamp_col]):
                # Assume microseconds since epoch
                df["timestamp_utc"] = pd.to_datetime(df[timestamp_col], unit="us", utc=True)
            else:
                # Try to parse string
                df["timestamp_utc"] = pd.to_datetime(df[timestamp_col], utc=True)
        else:
            df["timestamp_utc"] = pd.to_datetime(df[timestamp_col], utc=True)

        # Venue-specific conversion if needed
        if "venue" in df.columns and self.venue_timezones:
            for venue, tz in self.venue_timezones.items():
                mask = df["venue"] == venue
                if mask.any() and tz != "UTC":
                    # Convert from venue timezone to UTC
                    df.loc[mask, "timestamp_utc"] = (
                        df.loc[mask, "timestamp_utc"]
                        .dt.tz_convert(tz)
                        .dt.tz_convert("UTC")
                    )

        return df

    def validate(self, df: pd.DataFrame) -> dict[str, any]:
        """
        Validate timestamp normalization.

        Args:
            df: DataFrame with timestamp_utc column

        Returns:
            Dict with validation results
        """
        results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "stats": {},
        }

        if "timestamp_utc" not in df.columns:
            results["is_valid"] = False
            results["errors"].append("timestamp_utc column not found")
            return results

        # Check 1: All timestamps have UTC timezone
        if df["timestamp_utc"].dt.tz is None:
            results["is_valid"] = False
            results["errors"].append("Timestamps are not timezone-aware")
        elif str(df["timestamp_utc"].dt.tz) != "UTC":
            results["is_valid"] = False
            results["errors"].append(f"Timestamps not in UTC: {df['timestamp_utc'].dt.tz}")

        # Check 2: Microsecond precision
        if df["timestamp_utc"].dtype != "datetime64[ns, UTC]":
            results["warnings"].append(
                f"Timestamps not in nanosecond precision: {df['timestamp_utc'].dtype}"
            )

        # Check 3: No NaT values
        nat_count = df["timestamp_utc"].isna().sum()
        if nat_count > 0:
            results["warnings"].append(f"{nat_count} NaT values found")

        # Stats
        results["stats"]["min_timestamp"] = df["timestamp_utc"].min()
        results["stats"]["max_timestamp"] = df["timestamp_utc"].max()
        results["stats"]["total_rows"] = len(df)

        return results


class SessionFilter:
    """Filter data by trading sessions."""

    # Trading hours in UTC
    TRADING_HOURS = {
        "NYSE": {"start": "14:30", "end": "21:00"},  # 9:30 AM - 4:00 PM ET
        "NASDAQ": {"start": "14:30", "end": "21:00"},  # 9:30 AM - 4:00 PM ET
        "EUREX": {"start": "08:00", "end": "16:30"},  # 9:00 AM - 5:30 PM CET
    }

    def __init__(self, asset_class: str, venue: str):
        """
        Initialize session filter.

        Args:
            asset_class: Asset class ("EQUITY", "FOREX", "CRYPTO")
            venue: Venue name ("NYSE", "NASDAQ", "EUREX", "DUKASCOPY", "BINANCE", etc.)
        """
        self.asset_class = asset_class.upper()
        self.venue = venue.upper()
        self.calendar = self._get_calendar()

    def _get_calendar(self) -> Optional[AbstractHolidayCalendar]:
        """Get holiday calendar for venue."""
        if self.venue in ["NYSE", "NASDAQ"]:
            return USFederalHolidayCalendar()
        elif self.venue == "EUREX":
            # TODO: Implement Eurex calendar
            return None
        else:
            return None  # 24/7 trading (forex, crypto)

    def filter_regular_hours(
        self, df: pd.DataFrame, timestamp_col: str = "timestamp_utc"
    ) -> pd.DataFrame:
        """
        Keep only regular trading hours.

        Args:
            df: DataFrame with timestamp column
            timestamp_col: Name of timestamp column (must be UTC)

        Returns:
            Filtered DataFrame
        """
        if self.asset_class == "CRYPTO":
            return df  # No filtering for 24/7

        df_copy = df.copy()

        # Filter by time of day
        df_copy["_time"] = df_copy[timestamp_col].dt.time

        if self.venue in self.TRADING_HOURS:
            hours = self.TRADING_HOURS[self.venue]
            start_time = pd.Timestamp(hours["start"]).time()
            end_time = pd.Timestamp(hours["end"]).time()

            mask = (df_copy["_time"] >= start_time) & (df_copy["_time"] <= end_time)
        else:
            # Unknown venue - no time filtering
            mask = pd.Series([True] * len(df_copy))

        # Filter by holidays
        if self.calendar:
            holidays = self.calendar.holidays(
                start=df_copy[timestamp_col].min(), end=df_copy[timestamp_col].max()
            )
            df_copy["_date"] = df_copy[timestamp_col].dt.date
            mask &= ~df_copy["_date"].isin(holidays.date)

        # Filter weekends (for non-crypto)
        if self.asset_class not in ["CRYPTO", "FOREX"]:
            mask &= df_copy[timestamp_col].dt.dayofweek < 5  # Mon-Fri

        # Clean up temporary columns
        result = df_copy[mask].drop(columns=["_time", "_date"], errors="ignore")

        return result


class DataQualityChecker:
    """Validate and clean tick data."""

    def remove_duplicates(
        self,
        df: pd.DataFrame,
        subset: Optional[list[str]] = None,
        keep: str = "first",
    ) -> pd.DataFrame:
        """
        Remove duplicate ticks.

        Args:
            df: DataFrame with tick data
            subset: Columns to check for duplicates
                    Default: ["timestamp_utc", "symbol", "venue", "price"]
            keep: Which duplicate to keep ("first", "last", False)

        Returns:
            DataFrame with duplicates removed
        """
        if subset is None:
            # Default columns for duplicate detection
            available_cols = ["timestamp_utc", "symbol", "venue", "price"]
            subset = [col for col in available_cols if col in df.columns]

        if not subset:
            # No suitable columns for duplicate detection
            return df

        return df.drop_duplicates(subset=subset, keep=keep)

    def detect_outliers(
        self,
        df: pd.DataFrame,
        price_col: str = "price",
        method: str = "zscore",
        threshold: float = 5.0,
        window: Optional[int] = None,
    ) -> pd.Series:
        """
        Detect price outliers.

        Args:
            df: DataFrame with price data
            price_col: Name of price column
            method: Detection method ("zscore", "iqr", "rolling_zscore")
            threshold: Threshold for outlier detection
            window: Window size for rolling methods (default: 100)

        Returns:
            Boolean Series (True = outlier)
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
            if window is None:
                window = 100
            rolling_mean = df[price_col].rolling(window=window, center=True).mean()
            rolling_std = df[price_col].rolling(window=window, center=True).std()
            z = (df[price_col] - rolling_mean) / rolling_std
            return z.abs() > threshold

        else:
            raise ValueError(f"Unknown method: {method}")

    def detect_gaps(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        max_gap_seconds: float = 60.0,
    ) -> pd.DataFrame:
        """
        Detect gaps in tick data.

        Args:
            df: DataFrame with timestamp column
            timestamp_col: Name of timestamp column
            max_gap_seconds: Maximum acceptable gap in seconds

        Returns:
            DataFrame with gap information
        """
        df_sorted = df.sort_values(timestamp_col).reset_index(drop=True)

        # Compute time deltas
        df_sorted["gap_seconds"] = df_sorted[timestamp_col].diff().dt.total_seconds()

        # Flag large gaps
        gaps = df_sorted[df_sorted["gap_seconds"] > max_gap_seconds].copy()

        if gaps.empty:
            return pd.DataFrame()

        # Select relevant columns
        cols = [timestamp_col, "gap_seconds"]
        if "symbol" in gaps.columns:
            cols.append("symbol")
        if "venue" in gaps.columns:
            cols.append("venue")

        return gaps[cols]

    def fill_gaps(
        self, df: pd.DataFrame, method: str = "ffill", price_cols: Optional[list[str]] = None
    ) -> pd.DataFrame:
        """
        Fill gaps in time series.

        Args:
            df: DataFrame with time series data
            method: Fill method ("ffill", "interpolate", "drop")
            price_cols: Columns to fill (default: ["price", "bid", "ask"])

        Returns:
            DataFrame with gaps filled
        """
        if price_cols is None:
            price_cols = [col for col in ["price", "bid", "ask"] if col in df.columns]

        # Simplified logic to reduce complexity
        if method == "drop":
            return df.dropna()
        
        if method == "ffill":
            return df.ffill()
        
        if method == "interpolate":
            df_copy = df.copy()
            for col in price_cols:
                if col in df_copy.columns:
                    df_copy[col] = df_copy[col].interpolate(method="linear")
            return df_copy
        
        raise ValueError(f"Unknown fill method: {method}")

    def get_quality_report(
        self, df: pd.DataFrame, price_col: str = "price", timestamp_col: str = "timestamp_utc"
    ) -> dict[str, any]:
        """
        Generate comprehensive data quality report.

        Args:
            df: DataFrame to analyze
            price_col: Name of price column
            timestamp_col: Name of timestamp column

        Returns:
            Dict with quality metrics
        """
        report = {
            "total_rows": len(df),
            "duplicates": 0,
            "outliers": {"zscore": 0, "iqr": 0},
            "missing_values": {},
            "gaps": {"count": 0, "max_gap_seconds": 0},
            "price_stats": {},
        }

        # Duplicates
        if all(col in df.columns for col in [timestamp_col, "symbol", "price"]):
            duplicates = df.duplicated(subset=[timestamp_col, "symbol", "price"])
            report["duplicates"] = duplicates.sum()

        # Outliers
        if price_col in df.columns:
            report["outliers"]["zscore"] = self.detect_outliers(
                df, price_col, method="zscore", threshold=5.0
            ).sum()
            report["outliers"]["iqr"] = self.detect_outliers(
                df, price_col, method="iqr"
            ).sum()

            # Price stats
            report["price_stats"] = {
                "mean": df[price_col].mean(),
                "std": df[price_col].std(),
                "min": df[price_col].min(),
                "max": df[price_col].max(),
                "median": df[price_col].median(),
            }

        # Missing values
        report["missing_values"] = df.isna().sum().to_dict()

        # Gaps
        if timestamp_col in df.columns:
            gaps = self.detect_gaps(df, timestamp_col=timestamp_col)
            report["gaps"]["count"] = len(gaps)
            if not gaps.empty:
                report["gaps"]["max_gap_seconds"] = gaps["gap_seconds"].max()

        return report
