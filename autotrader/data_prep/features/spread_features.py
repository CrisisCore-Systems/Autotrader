"""
Spread feature extraction for order book analysis.

This module implements 5 spread-related features:
1. Absolute spread (ask - bid)
2. Relative spread ((ask - bid) / mid)
3. Mid-quote (bid + ask) / 2
4. Spread volatility (rolling std of spread)
5. Spread percentile (current spread vs historical distribution)
"""

import pandas as pd
import numpy as np


class SpreadFeatureExtractor:
    """
    Extract spread features from order book data.
    
    Spread features capture bid-ask dynamics and provide insights into
    liquidity conditions, market maker behavior, and transaction costs.
    """

    def __init__(
        self,
        volatility_window: int = 20,
        percentile_window: int = 100
    ):
        """
        Initialize spread feature extractor.

        Args:
            volatility_window: Window size for spread volatility calculation
            percentile_window: Window size for spread percentile calculation
        """
        self.volatility_window = volatility_window
        self.percentile_window = percentile_window

    def extract(
        self,
        df: pd.DataFrame,
        bid_col: str = "bid",
        ask_col: str = "ask",
        timestamp_col: str = "timestamp_utc"
    ) -> pd.DataFrame:
        """
        Extract all spread features from order book data.

        Args:
            df: DataFrame with bid/ask data
            bid_col: Name of bid price column
            ask_col: Name of ask price column
            timestamp_col: Name of timestamp column

        Returns:
            DataFrame with original data + spread features
        """
        if df.empty:
            return self._empty_result()

        # Validate columns
        required_cols = [bid_col, ask_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Sort by timestamp
        df = df.sort_values(timestamp_col).reset_index(drop=True).copy()

        # Feature 1: Absolute spread
        df["spread_absolute"] = df[ask_col] - df[bid_col]

        # Feature 2: Mid-quote
        df["mid_quote"] = (df[bid_col] + df[ask_col]) / 2.0

        # Feature 3: Relative spread (basis points)
        df["spread_relative"] = (df["spread_absolute"] / df["mid_quote"]) * 10_000

        # Feature 4: Spread volatility (rolling std)
        df["spread_volatility"] = (
            df["spread_absolute"]
            .rolling(window=self.volatility_window, min_periods=1)
            .std()
        )

        # Feature 5: Spread percentile (current vs historical)
        df["spread_percentile"] = (
            df["spread_absolute"]
            .rolling(window=self.percentile_window, min_periods=1)
            .apply(lambda x: self._calculate_percentile(x), raw=False)
        )

        return df

    def _calculate_percentile(self, series: pd.Series) -> float:
        """Calculate percentile of last value in series."""
        if len(series) < 2:
            return 50.0  # Default to median

        current = series.iloc[-1]
        historical = series.iloc[:-1]

        # Calculate percentile
        percentile = (historical < current).sum() / len(historical) * 100
        return percentile

    def _empty_result(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "spread_absolute",
                "mid_quote",
                "spread_relative",
                "spread_volatility",
                "spread_percentile",
            ]
        )

    def get_feature_names(self) -> list[str]:
        """Get list of feature names extracted by this class."""
        return [
            "spread_absolute",
            "mid_quote",
            "spread_relative",
            "spread_volatility",
            "spread_percentile",
        ]

    def get_feature_descriptions(self) -> dict[str, str]:
        """Get descriptions of each feature."""
        return {
            "spread_absolute": "Ask price - Bid price (absolute dollars/pips)",
            "mid_quote": "Mid-point between bid and ask prices",
            "spread_relative": "Spread as percentage of mid-quote (basis points)",
            "spread_volatility": f"Rolling {self.volatility_window}-period std of spread",
            "spread_percentile": f"Current spread percentile vs last {self.percentile_window} periods",
        }
