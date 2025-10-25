"""
Dollar-based bar construction for Phase 3.

This module implements fixed dollar value bars.
Dollar bars normalize by notional value (price × quantity), making them
ideal for multi-asset strategies and HFT. They adapt to both price and volume.
"""

import pandas as pd


class DollarBarConstructor:
    """Construct dollar-based bars from tick data."""

    def __init__(self, dollar_threshold: float = 10_000_000.0):
        """
        Initialize dollar bar constructor.

        Args:
            dollar_threshold: Cumulative dollar value per bar (e.g., $10M)
        """
        if dollar_threshold <= 0:
            raise ValueError(f"dollar_threshold must be positive, got {dollar_threshold}")
        
        self.dollar_threshold = dollar_threshold

    def construct(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
    ) -> pd.DataFrame:
        """
        Build OHLCV bars from fixed dollar value thresholds.

        Dollar value = price * quantity

        Args:
            df: DataFrame with tick data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column

        Returns:
            DataFrame with dollar-based bars
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

        # Compute dollar value per trade
        df["dollar_value"] = df[price_col] * df[quantity_col]
        df["cumulative_dollars"] = df["dollar_value"].cumsum()
        df["bar_id"] = (df["cumulative_dollars"] // self.dollar_threshold).astype(int)

        # Aggregate into bars
        bars = df.groupby("bar_id").agg({
            timestamp_col: ["first", "last"],
            price_col: ["first", "max", "min", "last"],
            quantity_col: "sum",
            "dollar_value": "sum"
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
            f"{quantity_col}_sum": "volume",
            "dollar_value_sum": "dollar_volume"
        })

        # Calculate VWAP
        bars["vwap"] = (
            df.groupby("bar_id")
            .apply(lambda x: (x[price_col] * x[quantity_col]).sum() / x[quantity_col].sum(), include_groups=False)
            .values
        )

        # Add metadata
        bars["trades"] = df.groupby("bar_id").size().values
        bars["bar_type"] = "dollar"
        bars["dollar_threshold"] = self.dollar_threshold

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
                "dollar_volume",
                "vwap",
                "trades",
                "bar_type",
                "dollar_threshold",
            ]
        )

    def get_bar_statistics(self, bars: pd.DataFrame) -> dict:
        """Calculate statistics about constructed bars."""
        if bars.empty:
            return {"total_bars": 0}

        stats = {
            "total_bars": len(bars),
            "dollar_threshold": self.dollar_threshold,
            "bar_type": "dollar",
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
            },
            "dollar_volume": {
                "total": bars["dollar_volume"].sum(),
                "mean": bars["dollar_volume"].mean(),
                "std": bars["dollar_volume"].std(),
            },
            "trades": {
                "total": bars["trades"].sum(),
                "mean": bars["trades"].mean(),
                "std": bars["trades"].std(),
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
