"""Backtest harness scaffold for GemScore evaluation."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from src.core.scoring import compute_gem_score
from backtest.baseline_strategies import (
    BaselineResult,
    evaluate_all_baselines,
    format_baseline_comparison,
)
from backtest.extended_metrics import (
    ExtendedBacktestMetrics,
    calculate_extended_metrics,
    format_ic_summary,
)


@dataclass
class TokenSnapshot:
    token: str
    date: pd.Timestamp
    features: Dict[str, float]
    future_return_7d: float


@dataclass
class BacktestResult:
    precision_at_k: float
    average_return_at_k: float
    flagged_assets: List[str]
    baseline_results: Dict[str, BaselineResult] | None = None
    extended_metrics: ExtendedBacktestMetrics | None = None
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary for JSON export."""
        result_dict = {
            "precision_at_k": self.precision_at_k,
            "average_return_at_k": self.average_return_at_k,
            "flagged_assets": self.flagged_assets,
        }
        
        if self.baseline_results:
            result_dict["baseline_results"] = {
                name: {
                    "precision": res.precision,
                    "avg_return": res.avg_return,
                }
                for name, res in self.baseline_results.items()
            }
        
        if self.extended_metrics:
            result_dict["extended_metrics"] = {
                "ic": self.extended_metrics.ic,
                "rank_ic": self.extended_metrics.rank_ic,
                "sharpe_ratio": self.extended_metrics.sharpe_ratio,
                "sortino_ratio": self.extended_metrics.sortino_ratio,
                "max_drawdown": self.extended_metrics.max_drawdown,
            }
        
        return result_dict
    
    def to_json(self, path: Optional[Path] = None, indent: int = 2) -> str:
        """Export result as JSON string or to file.
        
        Args:
            path: Optional path to write JSON file
            indent: JSON indentation level
            
        Returns:
            JSON string representation
        """
        json_str = json.dumps(self.to_dict(), indent=indent, sort_keys=True)
        
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str)
        
        return json_str


def load_snapshots(path: Path) -> Iterable[TokenSnapshot]:
    """Load token snapshots from CSV file."""

    df = pd.read_csv(path, parse_dates=["date"])
    feature_cols = [col for col in df.columns if col.startswith("f_")]
    for _, row in df.iterrows():
        features = {col.replace("f_", ""): row[col] for col in feature_cols}
        yield TokenSnapshot(
            token=row["token"],
            date=row["date"],
            features=features,
            future_return_7d=row["future_return_7d"],
        )


def evaluate_period(
    snapshots: Iterable[TokenSnapshot],
    top_k: int = 10,
    compare_baselines: bool = False,
    extended_metrics: bool = False,
    seed: int | None = None
) -> BacktestResult:
    """Compute precision@K and average return for flagged assets.
    
    Args:
        snapshots: Iterable of token snapshots
        top_k: Number of top assets to evaluate
        compare_baselines: Whether to evaluate baseline strategies
        extended_metrics: Whether to calculate IC and risk metrics
        seed: Random seed for baseline comparisons
    
    Returns:
        BacktestResult with GemScore performance and optional baseline comparisons
    """
    snapshots_list = list(snapshots)
    
    # Evaluate GemScore strategy
    scored = []
    for snapshot in snapshots_list:
        result = compute_gem_score(snapshot.features)
        scored.append((snapshot, result.score))

    # Sort with deterministic tie-breaking: primary=score (desc), secondary=token (asc)
    scored.sort(key=lambda item: (-item[1], item[0].token))
    top_assets = scored[:top_k]
    flagged_returns = [snap.future_return_7d for snap, _ in top_assets]
    positives = [r for r in flagged_returns if r > 0]

    precision_at_k = len(positives) / max(1, top_k)
    average_return_at_k = float(pd.Series(flagged_returns).mean()) if flagged_returns else 0.0

    # Optionally evaluate baseline strategies
    baseline_results = None
    if compare_baselines:
        baseline_results = evaluate_all_baselines(snapshots_list, top_k, seed)
    
    # Optionally calculate extended metrics
    extended_metrics_result = None
    if extended_metrics:
        # Prepare predictions array from all scored snapshots
        predictions = np.array([score for _, score in scored])
        extended_metrics_result = calculate_extended_metrics(
            snapshots=snapshots_list,
            predictions=predictions,
            top_k=top_k,
            risk_free_rate=0.0,
            periods_per_year=52,  # Assuming weekly returns
        )
    
    return BacktestResult(
        precision_at_k=precision_at_k,
        average_return_at_k=average_return_at_k,
        flagged_assets=[snap.token for snap, _ in top_assets],
        baseline_results=baseline_results,
        extended_metrics=extended_metrics_result,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GemScore backtest harness")
    parser.add_argument("data", type=Path, help="Path to CSV with features")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--compare-baselines", action="store_true", 
                       help="Compare against baseline strategies")
    parser.add_argument("--extended-metrics", action="store_true",
                       help="Calculate IC and risk-adjusted metrics")
    parser.add_argument("--seed", type=int, default=None, 
                       help="Random seed for reproducibility")
    parser.add_argument("--json-output", type=Path, default=None,
                       help="Path to export results as JSON")
    args = parser.parse_args()

    snapshots = list(load_snapshots(args.data))
    result = evaluate_period(
        snapshots, 
        top_k=args.top_k, 
        compare_baselines=args.compare_baselines,
        extended_metrics=args.extended_metrics,
        seed=args.seed
    )
    
    # Export JSON if requested
    if args.json_output:
        result.to_json(args.json_output)
        print(f"Results exported to: {args.json_output}")
    
    print("=" * 60)
    print("GEMSCORE PERFORMANCE")
    print("=" * 60)
    print("Precision@K:", round(result.precision_at_k, 3))
    print("Average Return@K:", round(result.average_return_at_k, 3))
    print("Flagged Assets:", ", ".join(result.flagged_assets))
    
    if result.baseline_results:
        print()
        gem_score_dict = {
            'precision': result.precision_at_k,
            'return': result.average_return_at_k
        }
        print(format_baseline_comparison(gem_score_dict, result.baseline_results))
    
    if result.extended_metrics:
        print()
        print(result.extended_metrics.summary_string())


if __name__ == "__main__":
    main()
