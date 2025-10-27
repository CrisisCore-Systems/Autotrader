"""
Run-based bar construction for Phase 3.

This module implements run bars based on consecutive price movements.
A "run" is a sequence of ticks moving in the same direction. Bars close
after N runs, capturing trend persistence and reversal patterns.
"""

import pandas as pd


class RunBarConstructor:
    """Construct run bars based on consecutive price moves."""

    def __init__(self, num_runs: int = 10):
        """
        Initialize run bar constructor.

        Args:
            num_runs: Number of consecutive runs before bar close
        """
        if num_runs <= 0:
            raise ValueError(f"num_runs must be positive, got {num_runs}")
        
        self.num_runs = num_runs

    def construct(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
    ) -> pd.DataFrame:
        """
        Build run bars.

        A "run" is a consecutive sequence of ticks moving in the same direction.
        Bar closes after N runs.

        Args:
            df: DataFrame with tick data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column

        Returns:
            DataFrame with run bars
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

        # Detect runs (consecutive ticks with same sign)
        df["run_change"] = (df["sign"] != df["sign"].shift()).astype(int)
        df["run_id"] = df["run_change"].cumsum()

        # Group runs into bars
        df["bar_id"] = df["run_id"] // self.num_runs

        # Aggregate
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
        bars["bar_type"] = "run"
        bars["num_runs"] = self.num_runs

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
                "num_runs",
            ]
        )

    def get_bar_statistics(self, bars: pd.DataFrame) -> dict:
        """Calculate statistics about constructed bars."""
        if bars.empty:
            return {"total_bars": 0}

        stats = {
            "total_bars": len(bars),
            "num_runs": self.num_runs,
            "bar_type": "run",
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
