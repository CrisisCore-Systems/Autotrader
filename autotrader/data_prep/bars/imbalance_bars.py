"""
Imbalance-based bar construction for Phase 3.

This module implements imbalance bars based on order flow imbalance.
Bars close when cumulative signed volume exceeds a threshold, revealing
informed trading activity and institutional order flow.
"""

import pandas as pd


class ImbalanceBarConstructor:
    """Construct imbalance bars based on order flow imbalance."""

    def __init__(self, imbalance_threshold: float = 10_000.0):
        """
        Initialize imbalance bar constructor.

        Args:
            imbalance_threshold: Absolute imbalance threshold (θ)
        """
        if imbalance_threshold <= 0:
            raise ValueError(f"imbalance_threshold must be positive, got {imbalance_threshold}")
        
        self.imbalance_threshold = imbalance_threshold

    def construct(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
    ) -> pd.DataFrame:
        """
        Build imbalance bars.

        Signed volume = volume * sign(price_change)
        Bar closes when |cumulative_signed_volume| > threshold

        Args:
            df: DataFrame with tick data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column

        Returns:
            DataFrame with imbalance bars
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

        # Compute price change sign
        df["price_change"] = df[price_col].diff()
        df["sign"] = df["price_change"].apply(
            lambda x: 1 if x > 0 else (-1 if x < 0 else 0)
        )

        # Signed volume
        df["signed_volume"] = df[quantity_col] * df["sign"]

        # Detect threshold crossings
        df["bar_id"] = 0
        bar_id = 0
        cumsum = 0.0

        bar_ids = []
        for i in range(len(df)):
            cumsum += df.loc[i, "signed_volume"]

            if abs(cumsum) >= self.imbalance_threshold:
                bar_id += 1
                cumsum = 0.0

            bar_ids.append(bar_id)

        df["bar_id"] = bar_ids

        # Aggregate into bars
        bars = df.groupby("bar_id").agg({
            timestamp_col: ["first", "last"],
            price_col: ["first", "max", "min", "last"],
            quantity_col: "sum",
            "signed_volume": "sum"
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
            "signed_volume_sum": "imbalance"
        })

        # Calculate VWAP
        bars["vwap"] = (
            df.groupby("bar_id")
            .apply(lambda x: (x[price_col] * x[quantity_col]).sum() / x[quantity_col].sum(), include_groups=False)
            .values
        )

        # Add metadata
        bars["trades"] = df.groupby("bar_id").size().values
        bars["bar_type"] = "imbalance"
        bars["imbalance_threshold"] = self.imbalance_threshold

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
                "imbalance",
                "vwap",
                "trades",
                "bar_type",
                "imbalance_threshold",
            ]
        )

    def get_bar_statistics(self, bars: pd.DataFrame) -> dict:
        """Calculate statistics about constructed bars."""
        if bars.empty:
            return {"total_bars": 0}

        stats = {
            "total_bars": len(bars),
            "imbalance_threshold": self.imbalance_threshold,
            "bar_type": "imbalance",
            "timespan": {
                "start": bars["timestamp_start"].min(),
                "end": bars["timestamp_end"].max(),
                "duration_seconds": (
                    bars["timestamp_end"].max() - bars["timestamp_start"].min()
                ).total_seconds(),
            },
            "imbalance": {
                "mean": bars["imbalance"].mean(),
                "std": bars["imbalance"].std(),
                "min": bars["imbalance"].min(),
                "max": bars["imbalance"].max(),
            },
            "volume": {
                "total": bars["volume"].sum(),
                "mean": bars["volume"].mean(),
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
