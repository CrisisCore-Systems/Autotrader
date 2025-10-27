"""
Cost-aware classification labeling for HFT strategies.

Generates {-1, 0, +1} labels based on forward returns adjusted for transaction costs:
- +1: Return exceeds profitable threshold (after costs)
- -1: Return below negative threshold (profitable short after costs)
-  0: Return within cost bounds (not tradeable)
"""

from typing import Optional
import pandas as pd
import numpy as np

from .base import BaseLabeler, CostModel


class ClassificationLabeler(BaseLabeler):
    """
    Generate cost-aware classification labels.
    
    Labels are generated based on forward returns relative to transaction costs:
    - BUY (+1): forward_return > cost_threshold + min_profit
    - SELL (-1): forward_return < -(cost_threshold + min_profit)
    - HOLD (0): |forward_return| <= cost_threshold + min_profit
    
    This ensures labels only signal trades that are profitable after costs.
    """
    
    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        horizon_seconds: int = 60,
        is_maker: bool = True,
        use_microprice: bool = True,
        name: str = "classification"
    ):
        """
        Initialize classification labeler.
        
        Args:
            cost_model: Transaction cost model
            horizon_seconds: Forward-looking horizon
            is_maker: True for maker orders (lower fees)
            use_microprice: Use microprice instead of close price
            name: Labeler name
        """
        super().__init__(cost_model=cost_model, horizon_seconds=horizon_seconds, name=name)
        self.is_maker = is_maker
        self.use_microprice = use_microprice
        
        # Calculate thresholds
        self.profitable_threshold_bps = self.cost_model.profitable_threshold_bps(is_maker)
    
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
        Generate cost-aware classification labels.
        
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
            - label: {-1, 0, +1}
            - forward_return_bps: Forward return in basis points
            - profitable_threshold_bps: Threshold for profitable trade
            - is_profitable: Boolean indicating if label is tradeable
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
        forward_returns_bps = self._calculate_forward_return_bps(
            bars, price_col, timestamp_col
        )
        
        # Generate labels based on cost-adjusted thresholds
        labels = np.zeros(len(bars), dtype=int)
        
        # BUY signal: return exceeds profitable threshold
        labels[forward_returns_bps > self.profitable_threshold_bps] = 1
        
        # SELL signal: return below negative profitable threshold
        labels[forward_returns_bps < -self.profitable_threshold_bps] = -1
        
        # HOLD signal: within cost bounds (already 0)
        
        # Create result DataFrame
        result = bars.copy()
        result["label"] = labels
        result["forward_return_bps"] = forward_returns_bps
        result["profitable_threshold_bps"] = self.profitable_threshold_bps
        result["is_profitable"] = (labels != 0)
        
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
        forward_returns = labeled_data["forward_return_bps"]
        
        # Remove NaN (end of data with no forward horizon)
        valid_mask = labels.notna() & forward_returns.notna()
        labels = labels[valid_mask]
        forward_returns = forward_returns[valid_mask]
        
        if len(labels) == 0:
            return {"error": "No valid labels"}
        
        # Label distribution
        label_counts = labels.value_counts().to_dict()
        label_pcts = (labels.value_counts(normalize=True) * 100).to_dict()
        
        # Return statistics by label
        stats = {
            "total_samples": len(labels),
            "label_distribution": {
                "buy_count": label_counts.get(1, 0),
                "sell_count": label_counts.get(-1, 0),
                "hold_count": label_counts.get(0, 0),
                "buy_pct": label_pcts.get(1, 0.0),
                "sell_pct": label_pcts.get(-1, 0.0),
                "hold_pct": label_pcts.get(0, 0.0),
            },
            "return_statistics": {
                "mean_return_bps": forward_returns.mean(),
                "std_return_bps": forward_returns.std(),
                "min_return_bps": forward_returns.min(),
                "max_return_bps": forward_returns.max(),
            },
            "return_by_label": {
                "buy_mean_return_bps": forward_returns[labels == 1].mean() if (labels == 1).any() else np.nan,
                "sell_mean_return_bps": forward_returns[labels == -1].mean() if (labels == -1).any() else np.nan,
                "hold_mean_return_bps": forward_returns[labels == 0].mean() if (labels == 0).any() else np.nan,
            },
            "cost_model": {
                "profitable_threshold_bps": self.profitable_threshold_bps,
                "round_trip_cost_bps": self.cost_model.round_trip_cost_bps(self.is_maker),
                "is_maker": self.is_maker,
            },
            "horizon": {
                "horizon_seconds": self.horizon_seconds,
                "horizon_minutes": self.horizon_seconds / 60.0,
            },
        }
        
        # Calculate hit rate (labels predict correct direction)
        buy_mask = labels == 1
        sell_mask = labels == -1
        
        if buy_mask.any():
            buy_correct = (forward_returns[buy_mask] > 0).sum()
            buy_total = buy_mask.sum()
            stats["performance"] = stats.get("performance", {})
            stats["performance"]["buy_hit_rate"] = (buy_correct / buy_total * 100) if buy_total > 0 else 0.0
        
        if sell_mask.any():
            sell_correct = (forward_returns[sell_mask] < 0).sum()
            sell_total = sell_mask.sum()
            stats["performance"] = stats.get("performance", {})
            stats["performance"]["sell_hit_rate"] = (sell_correct / sell_total * 100) if sell_total > 0 else 0.0
        
        # Overall hit rate (ignoring hold)
        tradeable_mask = labels != 0
        if tradeable_mask.any():
            correct = ((labels[tradeable_mask] == 1) & (forward_returns[tradeable_mask] > 0)).sum() + \
                     ((labels[tradeable_mask] == -1) & (forward_returns[tradeable_mask] < 0)).sum()
            total_tradeable = tradeable_mask.sum()
            stats["performance"] = stats.get("performance", {})
            stats["performance"]["overall_hit_rate"] = (correct / total_tradeable * 100) if total_tradeable > 0 else 0.0
        
        return stats
