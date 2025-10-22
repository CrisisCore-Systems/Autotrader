"""Backtest harness scaffold for GemScore evaluation."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from src.core.scoring import GemScoreResult, compute_gem_score
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

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


@dataclass
class TokenSnapshot:
    token: str
    date: pd.Timestamp
    features: Dict[str, float]
    future_return_7d: float


@dataclass
class FlaggedAssetSummary:
    """Snapshot of GemScore outputs for a selected asset."""

    token: str
    score: float
    confidence: float
    contributions: Dict[str, float]


@dataclass
class ExperimentConfig:
    """Configuration for a backtest experiment (for reproducibility)."""
    top_k: int
    compare_baselines: bool
    extended_metrics: bool
    seed: int | None
    data_path: str
    timestamp: str
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return asdict(self)


@dataclass
class TimeSlice:
    """Single time slice in a time-sliced evaluation."""
    period_id: int
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    result: 'BacktestResult'


@dataclass
class BacktestResult:
    precision_at_k: float
    average_return_at_k: float
    flagged_assets: List[str]
    flagged_details: List[FlaggedAssetSummary] = field(default_factory=list)
    baseline_results: Dict[str, BaselineResult] | None = None
    extended_metrics: ExtendedBacktestMetrics | None = None
    config: ExperimentConfig | None = None
    time_slices: List[TimeSlice] | None = None

    def to_dict(self) -> Dict:
        """Convert result to dictionary for JSON export."""
        result_dict = {
            "precision_at_k": self.precision_at_k,
            "average_return_at_k": self.average_return_at_k,
            "flagged_assets": self.flagged_assets,
        }

        if self.flagged_details:
            result_dict["flagged_details"] = [
                {
                    "token": detail.token,
                    "score": detail.score,
                    "confidence": detail.confidence,
                    "contributions": detail.contributions,
                }
                for detail in self.flagged_details
            ]

        if self.config:
            result_dict["config"] = self.config.to_dict()
        
        if self.baseline_results:
            result_dict["baseline_results"] = {
                name: {
                    "precision": res.precision_at_k,
                    "avg_return": res.average_return_at_k,
                }
                for name, res in self.baseline_results.items()
            }
        
        if self.extended_metrics:
            result_dict["extended_metrics"] = self.extended_metrics.to_dict()
        
        if self.time_slices:
            result_dict["time_slices"] = [
                {
                    "period_id": ts.period_id,
                    "start_date": ts.start_date.isoformat(),
                    "end_date": ts.end_date.isoformat(),
                    "precision": ts.result.precision_at_k,
                    "avg_return": ts.result.average_return_at_k,
                }
                for ts in self.time_slices
            ]
        
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


def evaluate_time_sliced(
    snapshots: List[TokenSnapshot],
    top_k: int = 10,
    slice_by: str = "month",
    compare_baselines: bool = False,
    extended_metrics: bool = False,
    seed: int | None = None,
) -> BacktestResult:
    """Evaluate backtest performance across time slices.
    
    Args:
        snapshots: List of token snapshots with date field
        top_k: Number of top assets to evaluate
        slice_by: Time slice granularity ("week", "month", "quarter")
        compare_baselines: Whether to evaluate baseline strategies
        extended_metrics: Whether to calculate IC and risk metrics
        seed: Random seed for baseline comparisons
    
    Returns:
        BacktestResult with time-sliced performance
    """
    # Group snapshots by time slice
    df = pd.DataFrame([
        {
            'date': snap.date,
            'token': snap.token,
            'snapshot': snap,
        }
        for snap in snapshots
    ])
    
    # Determine slice frequency
    if slice_by == "week":
        df['period'] = df['date'].dt.to_period('W')
    elif slice_by == "month":
        df['period'] = df['date'].dt.to_period('M')
    elif slice_by == "quarter":
        df['period'] = df['date'].dt.to_period('Q')
    else:
        raise ValueError(f"Invalid slice_by: {slice_by}")
    
    # Evaluate each time slice
    time_slices = []
    all_precisions = []
    all_returns = []
    
    for period_id, (period, group) in enumerate(df.groupby('period')):
        period_snapshots = group['snapshot'].tolist()
        
        # Evaluate this period
        result = evaluate_period(
            period_snapshots,
            top_k=top_k,
            compare_baselines=False,  # Don't duplicate baselines per slice
            extended_metrics=False,  # Don't duplicate extended metrics per slice
            seed=seed,
        )
        
        time_slice = TimeSlice(
            period_id=period_id,
            start_date=group['date'].min(),
            end_date=group['date'].max(),
            result=result,
        )
        time_slices.append(time_slice)
        
        all_precisions.append(result.precision_at_k)
        all_returns.append(result.average_return_at_k)
    
    # Calculate aggregate metrics
    overall_precision = np.mean(all_precisions) if all_precisions else 0.0
    overall_return = np.mean(all_returns) if all_returns else 0.0
    
    # Evaluate baselines and extended metrics on full dataset if requested
    baseline_results = None
    if compare_baselines:
        baseline_results = evaluate_all_baselines(snapshots, top_k, seed)
    
    extended_metrics_result = None
    if extended_metrics:
        scored = []
        for snapshot in snapshots:
            result = compute_gem_score(snapshot.features)
            scored.append((snapshot, result.score))
        predictions = np.array([score for _, score in scored])
        extended_metrics_result = calculate_extended_metrics(
            snapshots=snapshots,
            predictions=predictions,
            top_k=top_k,
        )
    
    # Collect all flagged assets across time slices
    flagged_counts: Dict[str, int] = {}
    best_details: Dict[str, FlaggedAssetSummary] = {}
    all_flagged: List[str] = []
    for ts in time_slices:
        all_flagged.extend(ts.result.flagged_assets)
        for detail in ts.result.flagged_details:
            flagged_counts[detail.token] = flagged_counts.get(detail.token, 0) + 1
            current_best = best_details.get(detail.token)
            if current_best is None or detail.score > current_best.score:
                best_details[detail.token] = detail
    unique_flagged = list(dict.fromkeys(all_flagged))  # Preserve order, remove duplicates
    if flagged_counts:
        # Re-rank by frequency and score to highlight consistent standouts
        ranked = sorted(
            flagged_counts.items(),
            key=lambda item: (
                -item[1],
                -best_details[item[0]].score,
                item[0],
            ),
        )
        unique_flagged = [token for token, _ in ranked]

    flagged_details = [best_details[token] for token in unique_flagged[:top_k] if token in best_details]

    return BacktestResult(
        precision_at_k=overall_precision,
        average_return_at_k=overall_return,
        flagged_assets=unique_flagged[:top_k],  # Return top K most frequently flagged
        flagged_details=flagged_details,
        baseline_results=baseline_results,
        extended_metrics=extended_metrics_result,
        time_slices=time_slices,
    )


def evaluate_period(
    snapshots: Iterable[TokenSnapshot],
    top_k: int = 10,
    compare_baselines: bool = False,
    extended_metrics: bool = False,
    seed: int | None = None,
    config: ExperimentConfig | None = None,
) -> BacktestResult:
    """Compute precision@K and average return for flagged assets.
    
    Args:
        snapshots: Iterable of token snapshots
        top_k: Number of top assets to evaluate
        compare_baselines: Whether to evaluate baseline strategies
        extended_metrics: Whether to calculate IC and risk metrics
        seed: Random seed for baseline comparisons
        config: Optional experiment configuration for reproducibility
    
    Returns:
        BacktestResult with GemScore performance and optional baseline comparisons
    """
    snapshots_list = list(snapshots)
    
    # Evaluate GemScore strategy
    scored: List[tuple[TokenSnapshot, GemScoreResult]] = []
    for snapshot in snapshots_list:
        result = compute_gem_score(snapshot.features)
        scored.append((snapshot, result))

    # Sort with deterministic tie-breaking: primary=score (desc), secondary=token (asc)
    scored.sort(key=lambda item: (-item[1].score, item[0].token))
    top_assets = scored[:top_k]
    flagged_returns = [snap.future_return_7d for snap, _ in top_assets]
    positives = [r for r in flagged_returns if r > 0]

    precision_at_k = len(positives) / max(1, top_k)
    average_return_at_k = float(pd.Series(flagged_returns).mean()) if flagged_returns else 0.0

    flagged_details = [
        FlaggedAssetSummary(
            token=snapshot.token,
            score=result.score,
            confidence=result.confidence,
            contributions={k: float(v) for k, v in result.contributions.items()},
        )
        for snapshot, result in top_assets
    ]

    # Optionally evaluate baseline strategies
    baseline_results = None
    if compare_baselines:
        baseline_results = evaluate_all_baselines(snapshots_list, top_k, seed)
    
    # Optionally calculate extended metrics
    extended_metrics_result = None
    if extended_metrics:
        # Prepare predictions array from all scored snapshots
        predictions = np.array([result.score for _, result in scored])
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
        flagged_details=flagged_details,
        baseline_results=baseline_results,
        extended_metrics=extended_metrics_result,
        config=config,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GemScore backtest harness")
    parser.add_argument("data", type=Path, help="Path to CSV with features")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--compare-baselines", action="store_true", 
                       help="Compare against baseline strategies")
    parser.add_argument("--extended-metrics", action="store_true",
                       help="Calculate IC and risk-adjusted metrics")
    parser.add_argument("--time-sliced", action="store_true",
                       help="Enable time-sliced evaluation")
    parser.add_argument("--slice-by", type=str, default="month",
                       choices=["week", "month", "quarter"],
                       help="Time slice granularity (default: month)")
    parser.add_argument("--seed", type=int, default=None, 
                       help="Random seed for reproducibility")
    parser.add_argument("--json-output", type=Path, default=None,
                       help="Path to export results as JSON")
    args = parser.parse_args()

    # Create experiment config for reproducibility
    from datetime import datetime
    config = ExperimentConfig(
        top_k=args.top_k,
        compare_baselines=args.compare_baselines,
        extended_metrics=args.extended_metrics,
        seed=args.seed,
        data_path=str(args.data),
        timestamp=datetime.now().isoformat(),
    )

    snapshots = list(load_snapshots(args.data))
    
    # Choose evaluation method
    if args.time_sliced:
        result = evaluate_time_sliced(
            snapshots,
            top_k=args.top_k,
            slice_by=args.slice_by,
            compare_baselines=args.compare_baselines,
            extended_metrics=args.extended_metrics,
            seed=args.seed,
        )
        result.config = config
    else:
        result = evaluate_period(
            snapshots, 
            top_k=args.top_k, 
            compare_baselines=args.compare_baselines,
            extended_metrics=args.extended_metrics,
            seed=args.seed,
            config=config,
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
    print("Flagged Assets:", ", ".join(result.flagged_assets[:10]))  # Show first 10

    if result.flagged_details:
        print()
        print("Top GemScore Candidates (score • confidence • strongest driver):")
        for detail in result.flagged_details[: min(args.top_k, len(result.flagged_details))]:
            top_driver = None
            if detail.contributions:
                top_driver = max(detail.contributions.items(), key=lambda item: item[1])
            driver_str = f"{top_driver[0]}={top_driver[1]:.2f}" if top_driver else "n/a"
            print(
                f"  {detail.token}: {detail.score:.2f} • {detail.confidence:.2f} • {driver_str}"
            )

    # Show time-sliced results if available
    if result.time_slices:
        print()
        print("=" * 60)
        print("TIME-SLICED EVALUATION")
        print("=" * 60)
        print(f"Total Periods: {len(result.time_slices)}")
        print()
        print("Per-Period Performance:")
        for ts in result.time_slices:
            print(f"  Period {ts.period_id} ({ts.start_date.date()} to {ts.end_date.date()}):")
            print(f"    Precision@K: {ts.result.precision_at_k:.3f}")
            print(f"    Avg Return:  {ts.result.average_return_at_k:.4f}")
        
        # Summary statistics
        precisions = [ts.result.precision_at_k for ts in result.time_slices]
        returns = [ts.result.average_return_at_k for ts in result.time_slices]
        print()
        print("Aggregate Statistics:")
        print(f"  Mean Precision:   {np.mean(precisions):.3f} ± {np.std(precisions):.3f}")
        print(f"  Mean Return:      {np.mean(returns):.4f} ± {np.std(returns):.4f}")
        print(f"  Min Precision:    {np.min(precisions):.3f}")
        print(f"  Max Precision:    {np.max(precisions):.3f}")
    
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
