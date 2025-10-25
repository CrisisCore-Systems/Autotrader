"""
Intelligent NaN handling with feature-specific strategies.

Different features have different missing data semantics:
- Technical indicators: Use neutral values (RSI→50, BB→0.5)
- Returns/changes: Zero is reasonable default (no change)
- Z-scores: Zero means "at mean"
- Volatility: Use median
- Binary flags: Use mode
- Cyclical features: Interpolate to preserve continuity

This is superior to naive forward fill which:
1. Introduces look-ahead bias in first N bars
2. Can carry stale data for extended periods
3. Treats all features the same
"""

import pandas as pd
import numpy as np
from typing import Literal


class SmartNaNHandler:
    """
    Feature-aware NaN imputation.
    
    Applies different strategies based on feature type and semantics:
    - Technical indicators: Neutral values (RSI=50, BB=0.5, MACD=0)
    - Returns/changes: Zero (no change)
    - Z-scores: Zero (at mean)
    - Volatility: Median (robust to outliers)
    - Binary flags: Mode (most common)
    - Cyclical (sin/cos): Linear interpolate (preserve continuity)
    - Volume ratios: 1.0 (average volume)
    - Percentiles: 0.5 (median rank)
    - Default: Forward fill then backward fill
    
    Example:
        handler = SmartNaNHandler()
        clean_features = handler.handle_nans(features)
        
        # Get report on NaN handling
        report = handler.get_nan_report(features)
        print(f"Handled {report['total_nans']} NaNs across {report['affected_features']} features")
    """
    
    def __init__(self, fallback_method: Literal["ffill", "bfill", "drop"] = "ffill"):
        """
        Initialize NaN handler.
        
        Args:
            fallback_method: Method for features without specific strategy
                'ffill': Forward fill (default)
                'bfill': Backward fill
                'drop': Drop rows (not recommended)
        """
        self.fallback_method = fallback_method
        self._nan_stats = {}
    
    def handle_nans(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Apply intelligent NaN handling.
        
        Args:
            features: Features with potential NaNs
        
        Returns:
            Features with NaNs handled appropriately
        """
        result = features.copy()
        self._nan_stats = {}
        
        for col in result.columns:
            nan_count = result[col].isna().sum()
            
            if nan_count == 0:
                continue
            
            # Track NaNs before handling
            self._nan_stats[col] = {
                "before": nan_count,
                "strategy": None
            }
            
            # Apply feature-specific strategy
            result[col] = self._handle_column(result[col], col)
            
            # Track NaNs after handling
            self._nan_stats[col]["after"] = result[col].isna().sum()
        
        return result
    
    def _handle_column(self, series: pd.Series, col_name: str) -> pd.Series:
        """Apply appropriate strategy for a single column."""
        
        # Technical indicators - use neutral values
        if "rsi" in col_name.lower():
            self._nan_stats[col_name]["strategy"] = "neutral_50"
            return series.fillna(50.0)
        
        if "bb_pct" in col_name.lower() or "bb_width" in col_name.lower():
            self._nan_stats[col_name]["strategy"] = "neutral_0.5"
            return series.fillna(0.5)
        
        if "macd" in col_name.lower():
            self._nan_stats[col_name]["strategy"] = "neutral_0"
            return series.fillna(0.0)
        
        # Returns and changes - zero means no change
        if any(x in col_name.lower() for x in ["return", "_diff", "change"]):
            self._nan_stats[col_name]["strategy"] = "zero_change"
            return series.fillna(0.0)
        
        # Z-scores - zero means at mean
        if "zscore" in col_name.lower() or "_z" in col_name.lower():
            self._nan_stats[col_name]["strategy"] = "zero_mean"
            return series.fillna(0.0)
        
        # Volatility - use median (robust to outliers)
        if any(x in col_name.lower() for x in ["vol", "atr", "std"]):
            median_val = series.median()
            self._nan_stats[col_name]["strategy"] = f"median_{median_val:.6f}"
            return series.fillna(median_val)
        
        # Binary flags - use mode (most common)
        if col_name.startswith("is_") or "_flag" in col_name.lower():
            # Check if actually binary
            unique_vals = series.dropna().unique()
            if len(unique_vals) <= 2:
                mode_val = series.mode().iloc[0] if len(series.mode()) > 0 else 0
                self._nan_stats[col_name]["strategy"] = f"mode_{mode_val}"
                return series.fillna(mode_val)
        
        # Cyclical features - linear interpolate to preserve continuity
        if any(x in col_name.lower() for x in ["_sin", "_cos"]):
            self._nan_stats[col_name]["strategy"] = "interpolate_linear"
            return series.interpolate(method="linear", limit_direction="both")
        
        # Volume ratios - 1.0 means average volume
        if "volume_ratio" in col_name.lower() or "relative_volume" in col_name.lower():
            self._nan_stats[col_name]["strategy"] = "neutral_1.0"
            return series.fillna(1.0)
        
        # Percentiles and ranks - 0.5 means median rank
        if "percentile" in col_name.lower() or "_pct" in col_name.lower():
            self._nan_stats[col_name]["strategy"] = "median_rank_0.5"
            return series.fillna(0.5)
        
        # VWAP and price features - use actual price as fallback
        if "vwap" in col_name.lower():
            # Try to use close price if available
            self._nan_stats[col_name]["strategy"] = "forward_fill"
            return series.ffill().bfill()
        
        # OBV and cumulative features - carry forward
        if "obv" in col_name.lower() or "cum" in col_name.lower():
            self._nan_stats[col_name]["strategy"] = "forward_fill_cumulative"
            return series.ffill().bfill()
        
        # Default fallback
        if self.fallback_method == "ffill":
            self._nan_stats[col_name]["strategy"] = "fallback_ffill"
            return series.ffill().bfill()
        elif self.fallback_method == "bfill":
            self._nan_stats[col_name]["strategy"] = "fallback_bfill"
            return series.bfill().ffill()
        else:
            self._nan_stats[col_name]["strategy"] = "no_fill"
            return series
    
    def get_nan_report(self, features: pd.DataFrame) -> dict:
        """
        Get summary of NaN handling.
        
        Args:
            features: Original features (before handling)
        
        Returns:
            Dictionary with NaN statistics
        """
        total_nans = features.isna().sum().sum()
        affected_features = (features.isna().sum() > 0).sum()
        
        # Per-feature breakdown
        feature_breakdown = []
        for col in features.columns:
            nan_count = features[col].isna().sum()
            if nan_count > 0:
                nan_pct = (nan_count / len(features)) * 100
                feature_breakdown.append({
                    "feature": col,
                    "nans": nan_count,
                    "percentage": nan_pct
                })
        
        return {
            "total_nans": total_nans,
            "total_values": features.size,
            "nan_percentage": (total_nans / features.size) * 100,
            "affected_features": affected_features,
            "total_features": len(features.columns),
            "feature_breakdown": sorted(
                feature_breakdown,
                key=lambda x: x["nans"],
                reverse=True
            )[:10]  # Top 10 worst features
        }
    
    def get_handling_summary(self) -> dict:
        """
        Get summary of how NaNs were handled.
        
        Returns:
            Dictionary mapping features to their handling strategy
        
        Raises:
            ValueError: If handle_nans() not called yet
        """
        if not self._nan_stats:
            raise ValueError("No NaN handling performed yet. Call handle_nans() first.")
        
        # Group by strategy
        strategy_counts = {}
        for col, stats in self._nan_stats.items():
            strategy = stats["strategy"]
            if strategy not in strategy_counts:
                strategy_counts[strategy] = []
            strategy_counts[strategy].append(col)
        
        return {
            "strategies_used": len(strategy_counts),
            "features_handled": len(self._nan_stats),
            "total_nans_before": sum(s["before"] for s in self._nan_stats.values()),
            "total_nans_after": sum(s["after"] for s in self._nan_stats.values()),
            "by_strategy": {
                strategy: {
                    "count": len(features),
                    "features": features[:5]  # Show first 5
                }
                for strategy, features in strategy_counts.items()
            }
        }
