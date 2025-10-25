"""
Horizon optimization for finding optimal prediction horizons per instrument.

Performs grid search over horizons (5s-5m) to find the horizon that maximizes:
- Information ratio
- Sharpe ratio  
- Trading capacity

Results in horizon-per-instrument optimization report with KPIs.
"""

from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass

from .base import CostModel, calculate_sharpe_ratio, calculate_information_ratio, estimate_capacity
from .classification import ClassificationLabeler
from .regression import RegressionLabeler


@dataclass
class HorizonResult:
    """Results for a single horizon."""
    horizon_seconds: int
    information_ratio: float
    sharpe_ratio: float
    hit_rate: float
    mean_return_bps: float
    std_return_bps: float
    capacity: float
    tradeable_pct: float
    num_samples: int


class HorizonOptimizer:
    """
    Optimize prediction horizon for maximum information ratio and capacity.
    
    Performs grid search over horizons to find the optimal forward-looking
    window that balances predictability and trading capacity.
    """
    
    def __init__(
        self,
        horizons_seconds: Optional[List[int]] = None,
        cost_model: Optional[CostModel] = None,
        labeling_method: str = "classification",  # or "regression"
        max_participation_rate: float = 0.02,
    ):
        """
        Initialize horizon optimizer.
        
        Args:
            horizons_seconds: List of horizons to test (default: 5s to 5m)
            cost_model: Transaction cost model
            labeling_method: "classification" or "regression"
            max_participation_rate: Maximum volume participation (for capacity estimation)
        """
        if horizons_seconds is None:
            # Default grid: 5s, 10s, 15s, 30s, 1m, 2m, 3m, 5m
            self.horizons_seconds = [5, 10, 15, 30, 60, 120, 180, 300]
        else:
            self.horizons_seconds = sorted(horizons_seconds)
        
        self.cost_model = cost_model or CostModel()
        self.labeling_method = labeling_method
        self.max_participation_rate = max_participation_rate
    
    def optimize(
        self,
        bars: pd.DataFrame,
        symbol: str = "UNKNOWN",
        price_col: str = "close",
        timestamp_col: str = "timestamp",
        volume_col: str = "volume",
        **labeler_kwargs
    ) -> Tuple[HorizonResult, List[HorizonResult], pd.DataFrame]:
        """
        Find optimal horizon for given instrument data.
        
        Args:
            bars: DataFrame with bar data
            symbol: Instrument symbol for reporting
            price_col: Price column name
            timestamp_col: Timestamp column name
            volume_col: Volume column name
            **labeler_kwargs: Additional arguments for labeler (bid_col, ask_col, etc.)
            
        Returns:
            Tuple of (best_result, all_results, results_df)
        """
        results = []
        
        print(f"\n{'='*80}")
        print(f"HORIZON OPTIMIZATION: {symbol}")
        print(f"{'='*80}")
        print(f"Testing {len(self.horizons_seconds)} horizons: {self.horizons_seconds}")
        print(f"Labeling method: {self.labeling_method}")
        print(f"Data: {len(bars)} bars")
        print()
        
        for horizon in self.horizons_seconds:
            print(f"[Horizon {horizon}s] Generating labels...")
            
            # Create labeler
            if self.labeling_method == "classification":
                labeler = ClassificationLabeler(
                    cost_model=self.cost_model,
                    horizon_seconds=horizon,
                )
            else:  # regression
                labeler = RegressionLabeler(
                    cost_model=self.cost_model,
                    horizon_seconds=horizon,
                )
            
            # Generate labels
            labeled_data = labeler.generate_labels(
                bars,
                price_col=price_col,
                timestamp_col=timestamp_col,
                **labeler_kwargs
            )
            
            # Get statistics
            stats = labeler.get_label_statistics(labeled_data)
            
            if "error" in stats:
                print(f"   [SKIP] {stats['error']}")
                continue
            
            # Calculate metrics
            labels = labeled_data["label"].dropna()
            forward_returns = labeled_data["forward_return_bps"].dropna()
            
            # Align labels and returns
            valid_mask = labels.notna() & forward_returns.notna()
            labels = labels[valid_mask]
            forward_returns = forward_returns[valid_mask]
            
            if len(labels) < 10:
                print(f"   [SKIP] Insufficient samples: {len(labels)}")
                continue
            
            # Information ratio (correlation between labels and actual returns)
            if self.labeling_method == "classification":
                # For classification, use label as signal (-1, 0, +1)
                ir = calculate_information_ratio(labels, forward_returns)
                
                # Hit rate
                if "performance" in stats and "overall_hit_rate" in stats["performance"]:
                    hit_rate = stats["performance"]["overall_hit_rate"]
                else:
                    hit_rate = 0.0
                
                # Tradeable percentage
                tradeable_pct = stats["label_distribution"].get("buy_pct", 0) + \
                               stats["label_distribution"].get("sell_pct", 0)
            else:  # regression
                # For regression, labels are predicted returns
                ir = calculate_information_ratio(labels, forward_returns)
                
                # Hit rate (sign agreement)
                hit_rate = ((labels > 0) == (forward_returns > 0)).sum() / len(labels) * 100
                
                # All samples are tradeable for regression
                tradeable_pct = 100.0
            
            # Sharpe ratio (of actual returns when following labels)
            if self.labeling_method == "classification":
                # Returns when trading on signals
                trade_returns = forward_returns[labels != 0] * labels[labels != 0]  # Direction-adjusted
            else:
                # Use predicted returns for Sharpe
                trade_returns = labels
            
            if len(trade_returns) > 0 and trade_returns.std() > 0:
                sharpe = calculate_sharpe_ratio(trade_returns / 10_000)  # Convert bps to decimal
            else:
                sharpe = 0.0
            
            # Capacity estimation
            capacity = estimate_capacity(
                bars,
                volume_col=volume_col,
                horizon_seconds=horizon,
                max_participation_rate=self.max_participation_rate
            )
            
            # Create result
            result = HorizonResult(
                horizon_seconds=horizon,
                information_ratio=ir,
                sharpe_ratio=sharpe,
                hit_rate=hit_rate,
                mean_return_bps=forward_returns.mean(),
                std_return_bps=forward_returns.std(),
                capacity=capacity,
                tradeable_pct=tradeable_pct,
                num_samples=len(labels),
            )
            
            results.append(result)
            
            print(f"   [OK] IR={ir:.4f}, Sharpe={sharpe:.2f}, Hit={hit_rate:.1f}%, "
                  f"Capacity={capacity:.0f}, Tradeable={tradeable_pct:.1f}%")
        
        if not results:
            raise ValueError("No valid horizons found. Check data quality.")
        
        # Find best horizon by information ratio
        best_result = max(results, key=lambda r: r.information_ratio)
        
        # Create results DataFrame
        results_df = pd.DataFrame([
            {
                "horizon_seconds": r.horizon_seconds,
                "horizon_minutes": r.horizon_seconds / 60.0,
                "information_ratio": r.information_ratio,
                "sharpe_ratio": r.sharpe_ratio,
                "hit_rate_pct": r.hit_rate,
                "mean_return_bps": r.mean_return_bps,
                "std_return_bps": r.std_return_bps,
                "capacity": r.capacity,
                "tradeable_pct": r.tradeable_pct,
                "num_samples": r.num_samples,
            }
            for r in results
        ])
        
        print(f"\n{'='*80}")
        print(f"OPTIMIZATION COMPLETE")
        print(f"{'='*80}")
        print(f"Best horizon: {best_result.horizon_seconds}s ({best_result.horizon_seconds/60:.1f}m)")
        print(f"Information ratio: {best_result.information_ratio:.4f}")
        print(f"Sharpe ratio: {best_result.sharpe_ratio:.2f}")
        print(f"Hit rate: {best_result.hit_rate:.1f}%")
        print(f"Capacity: {best_result.capacity:.0f}")
        print()
        
        return best_result, results, results_df
    
    def generate_report(
        self,
        results_df: pd.DataFrame,
        symbol: str,
        output_file: Optional[str] = None
    ) -> str:
        """
        Generate optimization report with KPIs and recommendations.
        
        Args:
            results_df: DataFrame from optimize() method
            symbol: Instrument symbol
            output_file: Optional file path to save report
            
        Returns:
            Report text
        """
        report_lines = []
        report_lines.append("=" * 100)
        report_lines.append(f"HORIZON OPTIMIZATION REPORT: {symbol}")
        report_lines.append("=" * 100)
        report_lines.append("")
        
        # Configuration
        report_lines.append("Configuration:")
        report_lines.append(f"  Labeling method: {self.labeling_method}")
        report_lines.append(f"  Cost model: Maker fee={self.cost_model.maker_fee}bps, "
                          f"Slippage={self.cost_model.slippage_bps}bps")
        report_lines.append(f"  Max participation rate: {self.max_participation_rate*100:.1f}%")
        report_lines.append("")
        
        # Best horizon
        best_row = results_df.loc[results_df["information_ratio"].idxmax()]
        report_lines.append("Optimal Horizon:")
        report_lines.append(f"  Horizon: {best_row['horizon_seconds']:.0f}s ({best_row['horizon_minutes']:.2f}m)")
        report_lines.append(f"  Information ratio: {best_row['information_ratio']:.4f}")
        report_lines.append(f"  Sharpe ratio: {best_row['sharpe_ratio']:.2f}")
        report_lines.append(f"  Hit rate: {best_row['hit_rate_pct']:.2f}%")
        report_lines.append(f"  Mean return: {best_row['mean_return_bps']:.2f} bps")
        report_lines.append(f"  Capacity: {best_row['capacity']:.0f}")
        report_lines.append(f"  Tradeable signals: {best_row['tradeable_pct']:.1f}%")
        report_lines.append("")
        
        # All horizons table
        report_lines.append("All Horizons:")
        report_lines.append(results_df.to_string(index=False))
        report_lines.append("")
        
        # Recommendations
        report_lines.append("Recommendations:")
        
        # Check if shorter horizons have better capacity
        if len(results_df) > 1:
            best_capacity_row = results_df.loc[results_df["capacity"].idxmax()]
            if best_capacity_row["horizon_seconds"] != best_row["horizon_seconds"]:
                report_lines.append(f"  ⚠️  Note: {best_capacity_row['horizon_seconds']:.0f}s has higher capacity "
                                  f"({best_capacity_row['capacity']:.0f}) but lower IR ({best_capacity_row['information_ratio']:.4f})")
        
        # Check if IR is acceptable
        if best_row["information_ratio"] < 0.1:
            report_lines.append(f"  ⚠️  Warning: Low information ratio ({best_row['information_ratio']:.4f}). "
                              "Consider more features or different horizons.")
        elif best_row["information_ratio"] > 0.3:
            report_lines.append(f"  ✓ Excellent information ratio ({best_row['information_ratio']:.4f}). "
                              "Strong predictive signal.")
        
        # Check hit rate
        if best_row["hit_rate_pct"] < 52:
            report_lines.append(f"  ⚠️  Warning: Hit rate ({best_row['hit_rate_pct']:.1f}%) below 52%. "
                              "May not be profitable after costs.")
        elif best_row["hit_rate_pct"] > 55:
            report_lines.append(f"  ✓ Good hit rate ({best_row['hit_rate_pct']:.1f}%). "
                              "Likely profitable strategy.")
        
        # Check tradeable percentage
        if best_row["tradeable_pct"] < 20:
            report_lines.append(f"  ⚠️  Low tradeable signals ({best_row['tradeable_pct']:.1f}%). "
                              "Consider loosening cost thresholds.")
        
        report_lines.append("")
        report_lines.append("=" * 100)
        
        report_text = "\n".join(report_lines)
        
        # Save to file if requested
        if output_file:
            with open(output_file, "w") as f:
                f.write(report_text)
            print(f"Report saved to {output_file}")
        
        return report_text
