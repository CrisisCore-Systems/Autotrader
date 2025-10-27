"""
Volume-based bar construction for Phase 3.

This module implements fixed cumulative volume bars.
Volume bars adapt to trading activity, creating more bars when
volume is high and fewer when volume is low.
"""

import pandas as pd


class VolumeBarConstructor:
    """Construct volume-based bars from tick data."""

    def __init__(self, volume_threshold: float = 1_000_000.0):
        """
        Initialize volume bar constructor.

        Args:
            volume_threshold: Cumulative volume per bar (e.g., 1M shares)
        """
        if volume_threshold <= 0:
            raise ValueError(f"volume_threshold must be positive, got {volume_threshold}")
        
        self.volume_threshold = volume_threshold

    def construct(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
    ) -> pd.DataFrame:
        """
        Build OHLCV bars from fixed volume thresholds.

        Args:
            df: DataFrame with tick data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column

        Returns:
            DataFrame with volume-based bars
        """
        if df.empty:
            return self._empty_result()

        # Validate columns
        required_cols = [timestamp_col, price_col, quantity_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Sort by timestamp
        df = df.sort_values(timestamp_col).reset_index(drop=True).copy()

        # Compute cumulative volume and assign bar IDs
        df["cumulative_volume"] = df[quantity_col].cumsum()
        df["bar_id"] = (df["cumulative_volume"] // self.volume_threshold).astype(int)

        # Aggregate into bars
        bars = df.groupby("bar_id").agg({
            timestamp_col: ["first", "last"],
            price_col: ["first", "max", "min", "last"],
            quantity_col: "sum"
        })

        # Flatten multi-level columns
        bars.columns = ["_".join(col).strip("_") for col in bars.columns]
        bars = bars.rename(columns={
            f"{timestamp_col}_first": "timestamp_start",
            f"{timestamp_col}_last": "timestamp_end",
            f"{price_col}_first": "open",
            f"{price_col}_max": "high",
            f"{price_col}_min": "low",
            f"{price_col}_last": "close",
            f"{quantity_col}_sum": "volume"
        })

        # Calculate VWAP
        bars["vwap"] = (
            df.groupby("bar_id")
            .apply(lambda x: (x[price_col] * x[quantity_col]).sum() / x[quantity_col].sum(), include_groups=False)
            .values
        )

        # Add metadata
        bars["trades"] = df.groupby("bar_id").size().values
        bars["bar_type"] = "volume"
        bars["volume_threshold"] = self.volume_threshold

        return bars.reset_index(drop=True)

    def _empty_result(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "timestamp_start",
                "timestamp_end",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "vwap",
                "trades",
                "bar_type",
                "volume_threshold",
            ]
        )

    def get_bar_statistics(self, bars: pd.DataFrame) -> dict:
        """Calculate statistics about constructed bars."""
        if bars.empty:
            return {"total_bars": 0}

        stats = {
            "total_bars": len(bars),
            "volume_threshold": self.volume_threshold,
            "bar_type": "volume",
            "timespan": {
                "start": bars["timestamp_start"].min(),
                "end": bars["timestamp_end"].max(),
                "duration_seconds": (
                    bars["timestamp_end"].max() - bars["timestamp_start"].min()
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
