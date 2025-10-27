"""
Unified order book feature extraction interface.

This module provides a single entry point to extract all order book features:
- Spread features (5)
- Depth features (5)
- Flow toxicity features (5)

Total: 15 features from Level 1 or Level 2 order book data.
"""

import pandas as pd

from autotrader.data_prep.features.spread_features import SpreadFeatureExtractor
from autotrader.data_prep.features.depth_features import DepthFeatureExtractor
from autotrader.data_prep.features.flow_features import FlowFeatureExtractor


class OrderBookFeatureExtractor:
    """
    Unified interface for extracting all order book features.
    
    Combines spread, depth, and flow features into a single extraction pipeline.
    
    Example:
        extractor = OrderBookFeatureExtractor()
        features = extractor.extract_all(
            order_book_df=ob_data,
            trade_df=trade_data
        )
    """

    def __init__(
        self,
        # Spread parameters
        spread_volatility_window: int = 20,
        spread_percentile_window: int = 100,
        # Depth parameters
        num_levels: int = 5,
        # Flow parameters
        vpin_window: int = 50,
        kyle_window: int = 20,
        amihud_window: int = 20
    ):
        """
        Initialize unified feature extractor.

        Args:
            spread_volatility_window: Window for spread volatility
            spread_percentile_window: Window for spread percentile
            num_levels: Number of order book levels to analyze
            vpin_window: Window for VPIN and flow imbalance
            kyle_window: Window for Kyle's lambda
            amihud_window: Window for Amihud illiquidity
        """
        self.spread_extractor = SpreadFeatureExtractor(
            volatility_window=spread_volatility_window,
            percentile_window=spread_percentile_window
        )

        self.depth_extractor = DepthFeatureExtractor(
            num_levels=num_levels
        )

        self.flow_extractor = FlowFeatureExtractor(
            vpin_window=vpin_window,
            kyle_window=kyle_window,
            amihud_window=amihud_window
        )

    def extract_all(
        self,
        order_book_df: pd.DataFrame = None,
        trade_df: pd.DataFrame = None,
        # Order book columns
        bid_col: str = "bid",
        ask_col: str = "ask",
        bid_levels: list[tuple[str, str]] = None,
        ask_levels: list[tuple[str, str]] = None,
        # Trade columns
        price_col: str = "price",
        quantity_col: str = "quantity",
        side_col: str = "side",
        timestamp_col: str = "timestamp_utc"
    ) -> dict[str, pd.DataFrame]:
        """
        Extract all features from order book and trade data.

        Args:
            order_book_df: DataFrame with order book snapshots
            trade_df: DataFrame with trade data
            bid_col: Name of best bid column
            ask_col: Name of best ask column
            bid_levels: List of (price, volume) column tuples for bid levels
            ask_levels: List of (price, volume) column tuples for ask levels
            price_col: Name of trade price column
            quantity_col: Name of trade quantity column
            side_col: Name of trade side column
            timestamp_col: Name of timestamp column

        Returns:
            Dictionary with keys:
            - "spread_features": DataFrame with spread features
            - "depth_features": DataFrame with depth features
            - "flow_features": DataFrame with flow features
            - "feature_names": List of all feature names
            - "feature_descriptions": Dict of feature descriptions
        """
        results = {}

        # Extract spread features (requires order book data)
        if order_book_df is not None:
            spread_features = self.spread_extractor.extract(
                df=order_book_df,
                bid_col=bid_col,
                ask_col=ask_col,
                timestamp_col=timestamp_col
            )
            results["spread_features"] = spread_features
        else:
            results["spread_features"] = None

        # Extract depth features (requires Level 2 order book)
        if order_book_df is not None and bid_levels is not None:
            depth_features = self.depth_extractor.extract(
                df=order_book_df,
                bid_levels=bid_levels,
                ask_levels=ask_levels,
                timestamp_col=timestamp_col
            )
            results["depth_features"] = depth_features
        else:
            results["depth_features"] = None

        # Extract flow features (requires trade data)
        if trade_df is not None:
            flow_features = self.flow_extractor.extract(
                df=trade_df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
                side_col=side_col
            )
            results["flow_features"] = flow_features
        else:
            results["flow_features"] = None

        # Collect all feature names and descriptions
        results["feature_names"] = self.get_all_feature_names()
        results["feature_descriptions"] = self.get_all_feature_descriptions()

        return results

    def extract_spread_only(
        self,
        df: pd.DataFrame,
        bid_col: str = "bid",
        ask_col: str = "ask",
        timestamp_col: str = "timestamp_utc"
    ) -> pd.DataFrame:
        """Extract only spread features (Level 1 data)."""
        return self.spread_extractor.extract(
            df=df,
            bid_col=bid_col,
            ask_col=ask_col,
            timestamp_col=timestamp_col
        )

    def extract_depth_only(
        self,
        df: pd.DataFrame,
        bid_levels: list[tuple[str, str]] = None,
        ask_levels: list[tuple[str, str]] = None,
        timestamp_col: str = "timestamp_utc"
    ) -> pd.DataFrame:
        """Extract only depth features (Level 2 data)."""
        return self.depth_extractor.extract(
            df=df,
            bid_levels=bid_levels,
            ask_levels=ask_levels,
            timestamp_col=timestamp_col
        )

    def extract_flow_only(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
        side_col: str = "side"
    ) -> pd.DataFrame:
        """Extract only flow features (trade data)."""
        return self.flow_extractor.extract(
            df=df,
            timestamp_col=timestamp_col,
            price_col=price_col,
            quantity_col=quantity_col,
            side_col=side_col
        )

    def get_all_feature_names(self) -> list[str]:
        """Get all feature names from all extractors."""
        return (
            self.spread_extractor.get_feature_names() +
            self.depth_extractor.get_feature_names() +
            self.flow_extractor.get_feature_names()
        )

    def get_all_feature_descriptions(self) -> dict[str, str]:
        """Get all feature descriptions from all extractors."""
        descriptions = {}
        descriptions.update(self.spread_extractor.get_feature_descriptions())
        descriptions.update(self.depth_extractor.get_feature_descriptions())
        descriptions.update(self.flow_extractor.get_feature_descriptions())
        return descriptions

    def get_feature_count(self) -> dict[str, int]:
        """Get count of features by category."""
        return {
            "spread_features": len(self.spread_extractor.get_feature_names()),
            "depth_features": len(self.depth_extractor.get_feature_names()),
            "flow_features": len(self.flow_extractor.get_feature_names()),
            "total": len(self.get_all_feature_names())
        }
