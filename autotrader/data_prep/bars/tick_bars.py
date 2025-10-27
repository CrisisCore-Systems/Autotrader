"""
Tick-based bar construction for Phase 3.

This module implements fixed tick count bars (e.g., 1000 ticks per bar).
Tick bars provide activity-based sampling, creating more bars during
high-activity periods and fewer during low-activity periods.
"""

import pandas as pd


class TickBarConstructor:
    """Construct tick-based bars from tick data."""

    def __init__(self, num_ticks: int = 1000):
        """
        Initialize tick bar constructor.

        Args:
            num_ticks: Number of ticks per bar (e.g., 100, 500, 1000)
        """
        if num_ticks <= 0:
            raise ValueError(f"num_ticks must be positive, got {num_ticks}")
        
        self.num_ticks = num_ticks

    def construct(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
    ) -> pd.DataFrame:
        """
        Build OHLCV bars from fixed tick counts.

        Args:
            df: DataFrame with tick data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column

        Returns:
            DataFrame with tick-based bars
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

        # Assign bar IDs (group by tick count)
        df["bar_id"] = df.index // self.num_ticks

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
        bars["trades"] = self.num_ticks
        bars["bar_type"] = "tick"
        bars["num_ticks"] = self.num_ticks

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
                "num_ticks",
            ]
        )

    def get_bar_statistics(self, bars: pd.DataFrame) -> dict:
        """Calculate statistics about constructed bars."""
        if bars.empty:
            return {"total_bars": 0}

        stats = {
            "total_bars": len(bars),
            "num_ticks": self.num_ticks,
            "bar_type": "tick",
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
