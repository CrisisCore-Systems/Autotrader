"""
Depth feature extraction for order book analysis.

This module implements 5 depth-related features:
1. Total bid depth (sum of bid volumes across levels)
2. Total ask depth (sum of ask volumes across levels)
3. Depth imbalance (bid_depth - ask_depth) / (bid_depth + ask_depth)
4. Weighted mid-price (volume-weighted average of bid/ask levels)
5. Depth-weighted spread (spread weighted by volume at each level)
"""

import pandas as pd
import numpy as np


class DepthFeatureExtractor:
    """
    Extract depth features from Level 2 order book data.
    
    Depth features capture liquidity distribution across price levels,
    revealing institutional order placement and market microstructure.
    """

    def __init__(self, num_levels: int = 5):
        """
        Initialize depth feature extractor.

        Args:
            num_levels: Number of order book levels to analyze (default 5)
        """
        self.num_levels = num_levels

    def extract(
        self,
        df: pd.DataFrame,
        bid_levels: list[tuple[str, str]] = None,
        ask_levels: list[tuple[str, str]] = None,
        timestamp_col: str = "timestamp_utc"
    ) -> pd.DataFrame:
        """
        Extract all depth features from order book data.

        Args:
            df: DataFrame with order book levels
            bid_levels: List of (price_col, volume_col) tuples for bid levels
                       Default: [("bid_price_1", "bid_vol_1"), ...]
            ask_levels: List of (price_col, volume_col) tuples for ask levels
                       Default: [("ask_price_1", "ask_vol_1"), ...]
            timestamp_col: Name of timestamp column

        Returns:
            DataFrame with original data + depth features
        """
        if df.empty:
            return self._empty_result()

        # Default level names
        if bid_levels is None:
            bid_levels = [
                (f"bid_price_{i}", f"bid_vol_{i}")
                for i in range(1, self.num_levels + 1)
            ]

        if ask_levels is None:
            ask_levels = [
                (f"ask_price_{i}", f"ask_vol_{i}")
                for i in range(1, self.num_levels + 1)
            ]

        # Validate columns exist
        required_cols = []
        for price_col, vol_col in bid_levels + ask_levels:
            required_cols.extend([price_col, vol_col])

        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Sort by timestamp
        df = df.sort_values(timestamp_col).reset_index(drop=True).copy()

        # Feature 1: Total bid depth
        bid_vol_cols = [vol_col for _, vol_col in bid_levels]
        df["bid_depth_total"] = df[bid_vol_cols].sum(axis=1)

        # Feature 2: Total ask depth
        ask_vol_cols = [vol_col for _, vol_col in ask_levels]
        df["ask_depth_total"] = df[ask_vol_cols].sum(axis=1)

        # Feature 3: Depth imbalance
        total_depth = df["bid_depth_total"] + df["ask_depth_total"]
        df["depth_imbalance"] = np.where(
            total_depth > 0,
            (df["bid_depth_total"] - df["ask_depth_total"]) / total_depth,
            0.0
        )

        # Feature 4: Weighted mid-price
        df["weighted_mid_price"] = df.apply(
            lambda row: self._calculate_weighted_mid(row, bid_levels, ask_levels),
            axis=1
        )

        # Feature 5: Depth-weighted spread
        df["depth_weighted_spread"] = df.apply(
            lambda row: self._calculate_depth_weighted_spread(row, bid_levels, ask_levels),
            axis=1
        )

        return df

    def _calculate_weighted_mid(
        self,
        row: pd.Series,
        bid_levels: list[tuple[str, str]],
        ask_levels: list[tuple[str, str]]
    ) -> float:
        """Calculate volume-weighted mid-price across all levels."""
        bid_prices = [row[price_col] for price_col, _ in bid_levels]
        bid_vols = [row[vol_col] for _, vol_col in bid_levels]

        ask_prices = [row[price_col] for price_col, _ in ask_levels]
        ask_vols = [row[vol_col] for _, vol_col in ask_levels]

        # Calculate weighted average
        total_bid_notional = sum(p * v for p, v in zip(bid_prices, bid_vols))
        total_ask_notional = sum(p * v for p, v in zip(ask_prices, ask_vols))
        total_volume = sum(bid_vols) + sum(ask_vols)

        if total_volume == 0:
            return (bid_prices[0] + ask_prices[0]) / 2.0  # Fallback to simple mid

        weighted_mid = (total_bid_notional + total_ask_notional) / total_volume
        return weighted_mid

    def _calculate_depth_weighted_spread(
        self,
        row: pd.Series,
        bid_levels: list[tuple[str, str]],
        ask_levels: list[tuple[str, str]]
    ) -> float:
        """Calculate spread weighted by depth at each level."""
        bid_prices = [row[price_col] for price_col, _ in bid_levels]
        bid_vols = [row[vol_col] for _, vol_col in bid_levels]

        ask_prices = [row[price_col] for price_col, _ in ask_levels]
        ask_vols = [row[vol_col] for _, vol_col in ask_levels]

        # Best bid and ask
        best_bid = bid_prices[0]
        best_ask = ask_prices[0]

        # Calculate volume-weighted average distance from mid
        mid = (best_bid + best_ask) / 2.0

        bid_weighted_distance = sum(
            abs(p - mid) * v for p, v in zip(bid_prices, bid_vols)
        )
        ask_weighted_distance = sum(
            abs(p - mid) * v for p, v in zip(ask_prices, ask_vols)
        )

        total_volume = sum(bid_vols) + sum(ask_vols)

        if total_volume == 0:
            return best_ask - best_bid  # Fallback to simple spread

        depth_weighted_spread = (bid_weighted_distance + ask_weighted_distance) / total_volume
        return depth_weighted_spread * 2  # Multiply by 2 for full spread

    def _empty_result(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "bid_depth_total",
                "ask_depth_total",
                "depth_imbalance",
                "weighted_mid_price",
                "depth_weighted_spread",
            ]
        )

    def get_feature_names(self) -> list[str]:
        """Get list of feature names extracted by this class."""
        return [
            "bid_depth_total",
            "ask_depth_total",
            "depth_imbalance",
            "weighted_mid_price",
            "depth_weighted_spread",
        ]

    def get_feature_descriptions(self) -> dict[str, str]:
        """Get descriptions of each feature."""
        return {
            "bid_depth_total": f"Sum of bid volumes across {self.num_levels} levels",
            "ask_depth_total": f"Sum of ask volumes across {self.num_levels} levels",
            "depth_imbalance": "Normalized depth difference: (bid - ask) / (bid + ask)",
            "weighted_mid_price": "Volume-weighted average price across all levels",
            "depth_weighted_spread": "Spread weighted by volume distribution",
        }
