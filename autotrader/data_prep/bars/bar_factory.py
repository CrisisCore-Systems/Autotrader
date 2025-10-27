"""
Unified factory interface for all bar types in Phase 3.

This module provides a single entry point to construct any bar type
with consistent parameter validation and type selection logic.

Features can be extracted from order book data and attached to bars.
"""

from typing import Literal, Optional

import pandas as pd

from .time_bars import TimeBarConstructor
from .tick_bars import TickBarConstructor
from .volume_bars import VolumeBarConstructor
from .dollar_bars import DollarBarConstructor
from .imbalance_bars import ImbalanceBarConstructor
from .run_bars import RunBarConstructor
from autotrader.data_prep.features import OrderBookFeatureExtractor


BarType = Literal["time", "tick", "volume", "dollar", "imbalance", "run"]


class BarFactory:
    """
    Unified factory for creating any bar type.

    Provides a consistent API across all 6 bar construction algorithms:
    - Time bars: Fixed time intervals (1s, 5m, 1h, etc.)
    - Tick bars: Fixed tick count (e.g., 1000 ticks)
    - Volume bars: Fixed volume threshold (e.g., 1M shares)
    - Dollar bars: Fixed dollar value threshold (e.g., $10M)
    - Imbalance bars: Order flow imbalance threshold
    - Run bars: Consecutive price movements

    Example:
        # Create 5-minute time bars
        bars = BarFactory.create(
            bar_type="time",
            df=tick_data,
            interval="5min"
        )

        # Create dollar bars with $10M threshold
        bars = BarFactory.create(
            bar_type="dollar",
            df=tick_data,
            dollar_threshold=10_000_000
        )
    """

    @staticmethod
    def create(
        bar_type: BarType,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
        # Time bar parameters
        interval: str = "1min",
        # Tick bar parameters
        num_ticks: int = 1000,
        # Volume bar parameters
        volume_threshold: float = 1_000_000.0,
        # Dollar bar parameters
        dollar_threshold: float = 10_000_000.0,
        # Imbalance bar parameters
        imbalance_threshold: float = 10_000.0,
        # Run bar parameters
        num_runs: int = 10,
        # Feature extraction parameters
        extract_features: bool = False,
        bid_col: Optional[str] = None,
        ask_col: Optional[str] = None,
        side_col: Optional[str] = None,
        spread_volatility_window: int = 20,
        spread_percentile_window: int = 100,
        vpin_window: int = 50,
        kyle_window: int = 20,
        amihud_window: int = 20,
    ) -> pd.DataFrame:
        """
        Create bars of specified type, optionally with order book features.

        Args:
            bar_type: Type of bars to create
            df: DataFrame with tick data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column
            interval: Time bar interval (1s, 5min, 1h, etc.)
            num_ticks: Number of ticks per bar
            volume_threshold: Volume threshold for volume bars
            dollar_threshold: Dollar value threshold for dollar bars
            imbalance_threshold: Imbalance threshold for imbalance bars
            num_runs: Number of runs per bar
            extract_features: If True, extract order book features for each bar
            bid_col: Name of bid price column (required if extract_features=True)
            ask_col: Name of ask price column (required if extract_features=True)
            side_col: Name of trade side column (optional, improves flow features)
            spread_volatility_window: Window for spread volatility feature
            spread_percentile_window: Window for spread percentile feature
            vpin_window: Window for VPIN feature
            kyle_window: Window for Kyle's lambda feature
            amihud_window: Window for Amihud illiquidity feature

        Returns:
            DataFrame with constructed bars (OHLCV + optional features)

        Raises:
            ValueError: If bar_type is invalid or required columns missing
        """
        if bar_type == "time":
            constructor = TimeBarConstructor(interval=interval)
            bars = constructor.construct(
                df=df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
            )

        elif bar_type == "tick":
            constructor = TickBarConstructor(num_ticks=num_ticks)
            bars = constructor.construct(
                df=df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
            )

        elif bar_type == "volume":
            constructor = VolumeBarConstructor(volume_threshold=volume_threshold)
            bars = constructor.construct(
                df=df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
            )

        elif bar_type == "dollar":
            constructor = DollarBarConstructor(dollar_threshold=dollar_threshold)
            bars = constructor.construct(
                df=df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
            )

        elif bar_type == "imbalance":
            constructor = ImbalanceBarConstructor(imbalance_threshold=imbalance_threshold)
            bars = constructor.construct(
                df=df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
            )

        elif bar_type == "run":
            constructor = RunBarConstructor(num_runs=num_runs)
            bars = constructor.construct(
                df=df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
            )

        else:
            valid_types = ["time", "tick", "volume", "dollar", "imbalance", "run"]
            raise ValueError(
                f"Invalid bar_type '{bar_type}'. Must be one of {valid_types}"
            )

        # Extract order book features if requested
        if extract_features:
            bars = BarFactory._attach_features(
                bars=bars,
                tick_data=df,
                timestamp_col=timestamp_col,
                price_col=price_col,
                quantity_col=quantity_col,
                bid_col=bid_col,
                ask_col=ask_col,
                side_col=side_col,
                spread_volatility_window=spread_volatility_window,
                spread_percentile_window=spread_percentile_window,
                vpin_window=vpin_window,
                kyle_window=kyle_window,
                amihud_window=amihud_window,
            )

        return bars

    @staticmethod
    def get_statistics(bar_type: BarType, bars: pd.DataFrame, **kwargs) -> dict:
        """
        Get statistics for constructed bars.

        Args:
            bar_type: Type of bars
            bars: DataFrame with bars
            **kwargs: Constructor parameters (interval, num_ticks, etc.)

        Returns:
            Dictionary with bar statistics
        """
        if bar_type == "time":
            constructor = TimeBarConstructor(interval=kwargs.get("interval", "1min"))
        elif bar_type == "tick":
            constructor = TickBarConstructor(num_ticks=kwargs.get("num_ticks", 1000))
        elif bar_type == "volume":
            constructor = VolumeBarConstructor(
                volume_threshold=kwargs.get("volume_threshold", 1_000_000.0)
            )
        elif bar_type == "dollar":
            constructor = DollarBarConstructor(
                dollar_threshold=kwargs.get("dollar_threshold", 10_000_000.0)
            )
        elif bar_type == "imbalance":
            constructor = ImbalanceBarConstructor(
                imbalance_threshold=kwargs.get("imbalance_threshold", 10_000.0)
            )
        elif bar_type == "run":
            constructor = RunBarConstructor(num_runs=kwargs.get("num_runs", 10))
        else:
            raise ValueError(f"Invalid bar_type '{bar_type}'")

        return constructor.get_bar_statistics(bars)

    @staticmethod
    def _attach_features(
        bars: pd.DataFrame,
        tick_data: pd.DataFrame,
        timestamp_col: str,
        price_col: str,
        quantity_col: str,
        bid_col: Optional[str],
        ask_col: Optional[str],
        side_col: Optional[str],
        spread_volatility_window: int,
        spread_percentile_window: int,
        vpin_window: int,
        kyle_window: int,
        amihud_window: int,
    ) -> pd.DataFrame:
        """
        Attach order book features to constructed bars.

        For each bar, this method:
        1. Finds all ticks that contributed to the bar
        2. Extracts spread features (if bid/ask available)
        3. Extracts flow features (if price/quantity available)
        4. Aggregates features (mean, last, std) for the bar period
        5. Merges features into bar DataFrame

        Args:
            bars: DataFrame with constructed bars
            tick_data: Original tick data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity column
            bid_col: Name of bid price column
            ask_col: Name of ask price column
            side_col: Name of trade side column
            spread_volatility_window: Window for spread volatility
            spread_percentile_window: Window for spread percentile
            vpin_window: Window for VPIN
            kyle_window: Window for Kyle's lambda
            amihud_window: Window for Amihud illiquidity

        Returns:
            DataFrame with bars + features
        """
        # Validate required columns for feature extraction
        if bid_col is None or ask_col is None:
            raise ValueError(
                "extract_features=True requires bid_col and ask_col parameters. "
                "Order book features cannot be computed without bid/ask data."
            )

        if bid_col not in tick_data.columns:
            raise ValueError(f"bid_col '{bid_col}' not found in tick data")
        if ask_col not in tick_data.columns:
            raise ValueError(f"ask_col '{ask_col}' not found in tick data")

        # Initialize feature extractor
        extractor = OrderBookFeatureExtractor(
            spread_volatility_window=spread_volatility_window,
            spread_percentile_window=spread_percentile_window,
            vpin_window=vpin_window,
            kyle_window=kyle_window,
            amihud_window=amihud_window,
        )

        # Extract spread features from tick data
        spread_features = extractor.extract_spread_only(
            df=tick_data,
            bid_col=bid_col,
            ask_col=ask_col,
            timestamp_col=timestamp_col,
        )

        # Extract flow features from tick data
        flow_features = extractor.extract_flow_only(
            df=tick_data,
            timestamp_col=timestamp_col,
            price_col=price_col,
            quantity_col=quantity_col,
            side_col=side_col if side_col else "side",  # Will infer if missing
        )

        # Merge features with tick timestamps
        tick_features = spread_features.merge(
            flow_features,
            left_index=True,
            right_index=True,
            how="outer",
        )
        
        # Add timestamps to feature DataFrame for time-based lookups
        if timestamp_col in tick_data.columns:
            tick_features[timestamp_col] = tick_data[timestamp_col].values
            tick_features = tick_features.set_index(timestamp_col)
            
            # Ensure datetime index
            if not isinstance(tick_features.index, pd.DatetimeIndex):
                tick_features.index = pd.to_datetime(tick_features.index)
        else:
            raise ValueError(f"timestamp_col '{timestamp_col}' not found in tick_data")

        # Ensure bars have timestamp column (either 'timestamp' or 'timestamp_start')
        if "timestamp" in bars.columns:
            timestamp_bar_col = "timestamp"
        elif "timestamp_start" in bars.columns:
            timestamp_bar_col = "timestamp_start"
        else:
            raise ValueError("Bars DataFrame must have 'timestamp' or 'timestamp_start' column")

        # Aggregate features for each bar
        bar_features = []
        
        for i in range(len(bars)):
            bar_timestamp = bars.iloc[i][timestamp_bar_col]
            
            # Convert to pandas Timestamp and ensure timezone compatibility
            if not isinstance(bar_timestamp, pd.Timestamp):
                bar_timestamp = pd.Timestamp(bar_timestamp)
            
            # Match timezone with tick_features index
            if tick_features.index.tz is not None and bar_timestamp.tz is None:
                bar_timestamp = bar_timestamp.tz_localize(tick_features.index.tz)
            elif tick_features.index.tz is None and bar_timestamp.tz is not None:
                bar_timestamp = bar_timestamp.tz_localize(None)
            
            bar_start = bar_timestamp
            
            # Find next bar timestamp or use timestamp_end if available
            if "timestamp_end" in bars.columns:
                bar_end_candidate = bars.iloc[i]["timestamp_end"]
                if not isinstance(bar_end_candidate, pd.Timestamp):
                    bar_end_candidate = pd.Timestamp(bar_end_candidate)
                # Match timezone
                if tick_features.index.tz is not None and bar_end_candidate.tz is None:
                    bar_end_candidate = bar_end_candidate.tz_localize(tick_features.index.tz)
                elif tick_features.index.tz is None and bar_end_candidate.tz is not None:
                    bar_end_candidate = bar_end_candidate.tz_localize(None)
                bar_end = bar_end_candidate
            elif i + 1 < len(bars):
                next_timestamp = bars.iloc[i + 1][timestamp_bar_col]
                if not isinstance(next_timestamp, pd.Timestamp):
                    next_timestamp = pd.Timestamp(next_timestamp)
                # Match timezone
                if tick_features.index.tz is not None and next_timestamp.tz is None:
                    next_timestamp = next_timestamp.tz_localize(tick_features.index.tz)
                elif tick_features.index.tz is None and next_timestamp.tz is not None:
                    next_timestamp = next_timestamp.tz_localize(None)
                bar_end = next_timestamp
            else:
                # For last bar, use end of data
                bar_end = tick_features.index.max() + pd.Timedelta(seconds=1)

            # Get ticks within this bar's time range
            mask = (tick_features.index >= bar_start) & (tick_features.index < bar_end)
            bar_ticks = tick_features[mask]

            if len(bar_ticks) == 0:
                # No ticks in this bar, use NaN
                feature_cols = [col for col in tick_features.columns]
                feature_row = {col: float("nan") for col in feature_cols}
            else:
                # Aggregate features: use last value for each feature
                # (most recent feature value represents bar state)
                feature_row = bar_ticks.iloc[-1].to_dict()

            bar_features.append(feature_row)

        # Convert to DataFrame and merge with bars
        feature_df = pd.DataFrame(bar_features)
        bars_with_features = pd.concat([bars.reset_index(drop=True), feature_df], axis=1)

        return bars_with_features

