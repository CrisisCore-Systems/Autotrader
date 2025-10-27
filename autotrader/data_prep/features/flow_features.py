"""
Flow toxicity feature extraction for informed trading detection.

This module implements 5 flow-related features:
1. VPIN (Volume-Synchronized Probability of Informed Trading)
2. Order flow imbalance (signed volume accumulation)
3. Trade intensity (trades per second)
4. Kyle's lambda (price impact coefficient)
5. Amihud illiquidity measure
"""

import pandas as pd
import numpy as np


class FlowFeatureExtractor:
    """
    Extract flow toxicity features from trade data.
    
    Flow features reveal informed trading activity, institutional order flow,
    and market microstructure dynamics that predict short-term price movements.
    """

    def __init__(
        self,
        vpin_window: int = 50,
        kyle_window: int = 20,
        amihud_window: int = 20
    ):
        """
        Initialize flow feature extractor.

        Args:
            vpin_window: Number of bars for VPIN calculation
            kyle_window: Window size for Kyle's lambda estimation
            amihud_window: Window size for Amihud illiquidity measure
        """
        self.vpin_window = vpin_window
        self.kyle_window = kyle_window
        self.amihud_window = amihud_window

    def extract(
        self,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc",
        price_col: str = "price",
        quantity_col: str = "quantity",
        side_col: str = "side"
    ) -> pd.DataFrame:
        """
        Extract all flow toxicity features from trade data.

        Args:
            df: DataFrame with trade data
            timestamp_col: Name of timestamp column
            price_col: Name of price column
            quantity_col: Name of quantity/volume column
            side_col: Name of side column ("BUY"/"SELL" or 1/-1)

        Returns:
            DataFrame with original data + flow features
        """
        if df.empty:
            return self._empty_result()

        # Validate columns
        required_cols = [timestamp_col, price_col, quantity_col, side_col]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        # Sort by timestamp
        df = df.sort_values(timestamp_col).reset_index(drop=True).copy()

        # Convert side to signed indicator
        df["side_sign"] = df[side_col].apply(self._convert_side_to_sign)

        # Feature 1: VPIN (Volume-Synchronized Probability of Informed Trading)
        df["vpin"] = self._calculate_vpin(df, quantity_col)

        # Feature 2: Order flow imbalance
        df["order_flow_imbalance"] = (
            (df[quantity_col] * df["side_sign"])
            .rolling(window=self.vpin_window, min_periods=1)
            .sum()
        )

        # Feature 3: Trade intensity (trades per second)
        df["trade_intensity"] = self._calculate_trade_intensity(df, timestamp_col)

        # Feature 4: Kyle's lambda (price impact)
        df["kyle_lambda"] = self._calculate_kyle_lambda(
            df, price_col, quantity_col
        )

        # Feature 5: Amihud illiquidity measure
        df["amihud_illiquidity"] = self._calculate_amihud_illiquidity(
            df, price_col, quantity_col
        )

        # Drop temporary column
        df = df.drop(columns=["side_sign"])

        return df

    def _convert_side_to_sign(self, side: str) -> int:
        """Convert side string to +1 (buy) or -1 (sell)."""
        if isinstance(side, (int, float)):
            return int(side)

        side_upper = str(side).upper()
        if side_upper in ["BUY", "B", "1"]:
            return 1
        elif side_upper in ["SELL", "S", "-1"]:
            return -1
        else:
            return 0  # Unknown

    def _calculate_vpin(self, df: pd.DataFrame, quantity_col: str) -> pd.Series:
        """
        Calculate VPIN (Volume-Synchronized Probability of Informed Trading).
        
        VPIN = |Buy Volume - Sell Volume| / Total Volume
        """
        buy_volume = (df[quantity_col] * (df["side_sign"] == 1)).rolling(
            window=self.vpin_window, min_periods=1
        ).sum()

        sell_volume = (df[quantity_col] * (df["side_sign"] == -1)).rolling(
            window=self.vpin_window, min_periods=1
        ).sum()

        total_volume = df[quantity_col].rolling(
            window=self.vpin_window, min_periods=1
        ).sum()

        vpin = np.where(
            total_volume > 0,
            abs(buy_volume - sell_volume) / total_volume,
            0.0
        )

        return pd.Series(vpin, index=df.index)

    def _calculate_trade_intensity(
        self,
        df: pd.DataFrame,
        timestamp_col: str
    ) -> pd.Series:
        """Calculate trades per second (rolling average)."""
        # Calculate time delta in seconds
        df["time_delta"] = df[timestamp_col].diff().dt.total_seconds()

        # Trades per second (inverse of time delta)
        trades_per_sec = np.where(
            df["time_delta"] > 0,
            1.0 / df["time_delta"],
            0.0
        )

        # Rolling average
        intensity = pd.Series(trades_per_sec, index=df.index).rolling(
            window=self.vpin_window, min_periods=1
        ).mean()

        df = df.drop(columns=["time_delta"])

        return intensity

    def _calculate_kyle_lambda(
        self,
        df: pd.DataFrame,
        price_col: str,
        quantity_col: str
    ) -> pd.Series:
        """
        Calculate Kyle's lambda (price impact coefficient).
        
        Lambda = Cov(ΔPrice, SignedVolume) / Var(SignedVolume)
        """
        # Price change
        df["price_change"] = df[price_col].diff()

        # Signed volume
        df["signed_volume"] = df[quantity_col] * df["side_sign"]

        # Rolling covariance and variance
        lambda_values = []

        for i in range(len(df)):
            if i < self.kyle_window:
                lambda_values.append(0.0)
                continue

            window_data = df.iloc[i - self.kyle_window:i]

            cov = window_data["price_change"].cov(window_data["signed_volume"])
            var = window_data["signed_volume"].var()

            if var > 0:
                lambda_val = cov / var
            else:
                lambda_val = 0.0

            lambda_values.append(lambda_val)

        df = df.drop(columns=["price_change", "signed_volume"])

        return pd.Series(lambda_values, index=df.index)

    def _calculate_amihud_illiquidity(
        self,
        df: pd.DataFrame,
        price_col: str,
        quantity_col: str
    ) -> pd.Series:
        """
        Calculate Amihud illiquidity measure.
        
        Amihud = Average(|Return| / Dollar Volume)
        """
        # Calculate returns
        df["return"] = df[price_col].pct_change()

        # Dollar volume
        df["dollar_volume"] = df[price_col] * df[quantity_col]

        # Illiquidity ratio
        df["illiquidity_ratio"] = np.where(
            df["dollar_volume"] > 0,
            abs(df["return"]) / df["dollar_volume"],
            0.0
        )

        # Rolling average
        amihud = df["illiquidity_ratio"].rolling(
            window=self.amihud_window, min_periods=1
        ).mean()

        df = df.drop(columns=["return", "dollar_volume", "illiquidity_ratio"])

        return amihud

    def _empty_result(self) -> pd.DataFrame:
        """Return empty DataFrame with correct schema."""
        return pd.DataFrame(
            columns=[
                "vpin",
                "order_flow_imbalance",
                "trade_intensity",
                "kyle_lambda",
                "amihud_illiquidity",
            ]
        )

    def get_feature_names(self) -> list[str]:
        """Get list of feature names extracted by this class."""
        return [
            "vpin",
            "order_flow_imbalance",
            "trade_intensity",
            "kyle_lambda",
            "amihud_illiquidity",
        ]

    def get_feature_descriptions(self) -> dict[str, str]:
        """Get descriptions of each feature."""
        return {
            "vpin": f"Volume-Synchronized Probability of Informed Trading ({self.vpin_window} bars)",
            "order_flow_imbalance": f"Cumulative signed volume ({self.vpin_window} bars)",
            "trade_intensity": f"Trades per second (rolling avg, {self.vpin_window} bars)",
            "kyle_lambda": f"Price impact coefficient (Kyle's lambda, {self.kyle_window} bars)",
            "amihud_illiquidity": f"Amihud illiquidity measure ({self.amihud_window} bars)",
        }
