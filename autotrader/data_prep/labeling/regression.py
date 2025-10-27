"""
Regression labeling with microprice returns and robust clipping.

Generates continuous target values for regression models:
- Microprice returns (more accurate than mid-quote)
- Signed returns clipped to robust bounds (remove outliers)
- Cost-adjusted returns (subtract transaction costs)
"""

from typing import Optional, Tuple
import pandas as pd
import numpy as np

from .base import BaseLabeler, CostModel


class RegressionLabeler(BaseLabeler):
    """
    Generate regression labels with microprice returns.
    
    Returns are:
    1. Calculated using microprice (volume-weighted fair price)
    2. Clipped to robust bounds (e.g., 5th-95th percentile) to remove outliers
    3. Optionally adjusted for transaction costs
    
    This is suitable for regression models that predict continuous returns.
    """
    
    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        horizon_seconds: int = 60,
        clip_percentiles: Tuple[float, float] = (5.0, 95.0),
        subtract_costs: bool = True,
        use_microprice: bool = True,
        name: str = "regression"
    ):
        """
        Initialize regression labeler.
        
        Args:
            cost_model: Transaction cost model
            horizon_seconds: Forward-looking horizon
            clip_percentiles: (lower, upper) percentiles for clipping outliers
            subtract_costs: If True, subtract transaction costs from returns
            use_microprice: Use microprice instead of close price
            name: Labeler name
        """
        super().__init__(cost_model=cost_model, horizon_seconds=horizon_seconds, name=name)
        self.clip_percentiles = clip_percentiles
        self.subtract_costs = subtract_costs
        self.use_microprice = use_microprice
    
    def generate_labels(
        self,
        bars: pd.DataFrame,
        price_col: str = "close",
        timestamp_col: str = "timestamp",
        bid_col: Optional[str] = "bid",
        ask_col: Optional[str] = "ask",
        bid_vol_col: Optional[str] = "bid_vol",
        ask_vol_col: Optional[str] = "ask_vol",
    ) -> pd.DataFrame:
        """
        Generate regression labels with microprice returns.
        
        Args:
            bars: DataFrame with bar data
            price_col: Price column to use (if not using microprice)
            timestamp_col: Timestamp column
            bid_col: Bid price column (for microprice)
            ask_col: Ask price column (for microprice)
            bid_vol_col: Bid volume column (for microprice)
            ask_vol_col: Ask volume column (for microprice)
            
        Returns:
            DataFrame with original bars + label columns:
            - label: Regression target (cost-adjusted, clipped return in bps)
            - raw_return_bps: Raw forward return before adjustments
            - clipped_return_bps: Return after robust clipping
            - cost_adjusted_return_bps: Return after cost subtraction
            - clip_lower_bps: Lower clip bound
            - clip_upper_bps: Upper clip bound
        """
        bars = bars.copy()
        
        # Calculate reference price (microprice or close)
        if self.use_microprice and all(col in bars.columns for col in [bid_col, ask_col]):
            try:
                reference_price = self._calculate_microprice(
                    bars, bid_col, ask_col, bid_vol_col, ask_vol_col
                )
                bars["_reference_price"] = reference_price
                price_col = "_reference_price"
            except ValueError:
                # Fall back to close if microprice calculation fails
                pass
        
        # Calculate forward returns
        raw_returns_bps = self._calculate_forward_return_bps(
            bars, price_col, timestamp_col
        )
        
        # Calculate robust clip bounds
        valid_returns = raw_returns_bps.dropna()
        if len(valid_returns) > 0:
            clip_lower = np.percentile(valid_returns, self.clip_percentiles[0])
            clip_upper = np.percentile(valid_returns, self.clip_percentiles[1])
        else:
            clip_lower = -100.0  # -1% default
            clip_upper = 100.0   # +1% default
        
        # Clip returns to robust bounds
        clipped_returns_bps = raw_returns_bps.clip(lower=clip_lower, upper=clip_upper)
        
        # Subtract transaction costs if requested
        if self.subtract_costs:
            # Assume maker orders (lower fees)
            round_trip_cost_bps = self.cost_model.round_trip_cost_bps(is_maker=True)
            
            # Subtract costs from absolute returns (direction-aware)
            cost_adjusted_returns_bps = clipped_returns_bps.copy()
            
            # For positive returns: return - cost
            cost_adjusted_returns_bps[cost_adjusted_returns_bps > 0] -= round_trip_cost_bps
            
            # For negative returns: return + cost (more negative)
            cost_adjusted_returns_bps[cost_adjusted_returns_bps < 0] += round_trip_cost_bps
            
            labels = cost_adjusted_returns_bps
        else:
            cost_adjusted_returns_bps = clipped_returns_bps
            labels = clipped_returns_bps
        
        # Create result DataFrame
        result = bars.copy()
        result["label"] = labels
        result["raw_return_bps"] = raw_returns_bps
        result["clipped_return_bps"] = clipped_returns_bps
        result["cost_adjusted_return_bps"] = cost_adjusted_returns_bps
        result["clip_lower_bps"] = clip_lower
        result["clip_upper_bps"] = clip_upper
        
        return result
    
    def get_label_statistics(self, labeled_data: pd.DataFrame) -> dict:
        """
        Calculate statistics about generated labels.
        
        Args:
            labeled_data: DataFrame returned by generate_labels()
            
        Returns:
            Dictionary with label statistics
        """
        labels = labeled_data["label"]
        raw_returns = labeled_data["raw_return_bps"]
        clipped_returns = labeled_data["clipped_return_bps"]
        
        # Remove NaN
        valid_mask = labels.notna()
        labels = labels[valid_mask]
        raw_returns = raw_returns[valid_mask]
        clipped_returns = clipped_returns[valid_mask]
        
        if len(labels) == 0:
            return {"error": "No valid labels"}
        
        stats = {
            "total_samples": len(labels),
            "label_statistics": {
                "mean": labels.mean(),
                "std": labels.std(),
                "min": labels.min(),
                "max": labels.max(),
                "median": labels.median(),
                "q25": labels.quantile(0.25),
                "q75": labels.quantile(0.75),
            },
            "raw_return_statistics": {
                "mean": raw_returns.mean(),
                "std": raw_returns.std(),
                "min": raw_returns.min(),
                "max": raw_returns.max(),
                "skew": raw_returns.skew(),
                "kurtosis": raw_returns.kurtosis(),
            },
            "clipping_impact": {
                "clip_lower_bps": labeled_data["clip_lower_bps"].iloc[0],
                "clip_upper_bps": labeled_data["clip_upper_bps"].iloc[0],
                "pct_clipped_lower": (raw_returns < labeled_data["clip_lower_bps"].iloc[0]).sum() / len(raw_returns) * 100,
                "pct_clipped_upper": (raw_returns > labeled_data["clip_upper_bps"].iloc[0]).sum() / len(raw_returns) * 100,
            },
            "cost_adjustment": {
                "subtract_costs": self.subtract_costs,
                "round_trip_cost_bps": self.cost_model.round_trip_cost_bps(is_maker=True),
                "mean_cost_impact_bps": (clipped_returns - labels).mean() if self.subtract_costs else 0.0,
            },
            "horizon": {
                "horizon_seconds": self.horizon_seconds,
                "horizon_minutes": self.horizon_seconds / 60.0,
            },
            "direction_distribution": {
                "positive_pct": (labels > 0).sum() / len(labels) * 100,
                "negative_pct": (labels < 0).sum() / len(labels) * 100,
                "zero_pct": (labels == 0).sum() / len(labels) * 100,
            },
        }
        
        # Calculate Sharpe ratio (assuming returns are in bps)
        if labels.std() > 0:
            # Convert bps to decimal for Sharpe calculation
            returns_decimal = labels / 10_000
            sharpe_252 = (returns_decimal.mean() / returns_decimal.std()) * np.sqrt(252)
            stats["performance"] = {
                "sharpe_ratio_annual": sharpe_252,
                "information_ratio": labels.mean() / labels.std() if labels.std() > 0 else 0.0,
            }
        
        return stats
