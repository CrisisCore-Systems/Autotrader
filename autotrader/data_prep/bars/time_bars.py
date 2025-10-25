"""
Time-based bar construction for Phase 3.

This module implements fixed time interval bars (1s, 1m, 5m, 1h, 1d).
Time bars are the simplest and most common bar type, aggregating OHLCV
data over fixed time intervals.
"""

import pandas as pd


class TimeBarConstructor:
    """Construct time-based OHLCV bars from tick data."""

    def __init__(self, interval: str = "1min"):
        """
        Initialize time bar constructor.

        Args:
            interval: Pandas frequency string
                Examples: '1s', '5s', '10s', '30s',
                         '1min', '5min', '15min', '30min',
                         '1h', '4h', '1d'
        """
        self.interval = interval
        self._validate_interval()

    def _validate_interval(self):
        """Validate interval string."""
        valid_units = ["s", "min", "h", "d", "S", "T", "H", "D"]
        
        # Check if interval ends with valid unit
        if not any(self.interval.endswith(unit) for unit in valid_units):
            raise ValueError(
                f"Invalid interval: {self.interval}. "
                f"Must end with one of: {valid_units}"
            )

    def construct(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
    ) -> pd.DataFrame:
        """
        Build OHLCV bars from tick data.

        Args:
            df: DataFrame with tick data
            timestamp_col: Name of timestamp column (must be datetime64)
            price_col: Name of price column (for OHLC)
            quantity_col: Name of quantity/volume column

        Returns:
            DataFrame with columns:
                - timestamp: Bar start timestamp
                - open: First price in interval
                - high: Highest price in interval
                - low: Lowest price in interval
                - close: Last price in interval
                - volume: Total volume in interval
                - vwap: Volume-weighted average price
                - trades: Number of trades in interval
                - interval: Interval string (e.g., "1min")
                - bar_type: "time"
        """
        if df.empty:
            return self._empty_result()

        # Validate columns exist
        required_cols = [timestamp_col, price_col, quantity_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Set timestamp as index
        df = df.copy()
        df = df.set_index(timestamp_col).sort_index()

        # Resample by time interval
        bars = pd.DataFrame(
            {
                "open": df[price_col].resample(self.interval).first(),
                "high": df[price_col].resample(self.interval).max(),
                "low": df[price_col].resample(self.interval).min(),
                "close": df[price_col].resample(self.interval).last(),
                "volume": df[quantity_col].resample(self.interval).sum(),
                "trades": df[price_col].resample(self.interval).count(),
            }
        )

        # Calculate VWAP
        dollar_volume = (df[price_col] * df[quantity_col]).resample(self.interval).sum()
        total_volume = df[quantity_col].resample(self.interval).sum()
        bars["vwap"] = dollar_volume / total_volume

        # Drop bars with no data
        bars = bars.dropna(subset=["close"])

        # Add metadata
        bars["interval"] = self.interval
        bars["bar_type"] = "time"

        # Reset index to make timestamp a column
        bars = bars.reset_index()
        bars = bars.rename(columns={timestamp_col: "timestamp"})

        return bars

    def _empty_result(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "vwap",
                "trades",
                "interval",
                "bar_type",
            ]
        )

    def construct_multiple_intervals(
        self,
        df: pd.DataFrame,
        intervals: list[str],
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
    ) -> dict[str, pd.DataFrame]:
        """
        Construct bars for multiple time intervals at once.

        Args:
            df: DataFrame with tick data
            intervals: List of interval strings (e.g., ["1min", "5min", "1h"])
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column

        Returns:
            Dict mapping interval → bars DataFrame
        """
        results = {}
        for interval in intervals:
            constructor = TimeBarConstructor(interval=interval)
            results[interval] = constructor.construct(
                df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
            )
        return results

    def get_bar_statistics(self, bars: pd.DataFrame) -> dict:
        """
        Calculate statistics about constructed bars.

        Args:
            bars: DataFrame with bar data

        Returns:
            Dict with bar statistics
        """
        if bars.empty:
            return {"total_bars": 0}

        stats = {
            "total_bars": len(bars),
            "interval": self.interval,
            "bar_type": "time",
            "timespan": {
                "start": bars["timestamp"].min(),
                "end": bars["timestamp"].max(),
                "duration_seconds": (
                    bars["timestamp"].max() - bars["timestamp"].min()
                ).total_seconds(),
            },
            "volume": {
                "total": bars["volume"].sum(),
                "mean": bars["volume"].mean(),
                "std": bars["volume"].std(),
                "min": bars["volume"].min(),
                "max": bars["volume"].max(),
            },
            "trades": {
                "total": bars["trades"].sum(),
                "mean": bars["trades"].mean(),
                "std": bars["trades"].std(),
                "min": bars["trades"].min(),
                "max": bars["trades"].max(),
            },
            "price": {
                "start": bars.iloc[0]["open"],
                "end": bars.iloc[-1]["close"],
                "high": bars["high"].max(),
                "low": bars["low"].min(),
                "range": bars["high"].max() - bars["low"].min(),
            },
        }

        return stats
