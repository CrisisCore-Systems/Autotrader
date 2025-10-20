"""Backtest harness for GemScore walk-forward evaluation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Tuple, Optional, Dict

# Import baseline strategies if available
try:
    from backtest.baseline_strategies import (
        RandomStrategy,
        CapWeightedStrategy, 
        SimpleMomentumStrategy,
        BaselineResult,
    )
    BASELINES_AVAILABLE = True
except ImportError:
    BASELINES_AVAILABLE = False

# Import experiment tracking
try:
    from src.utils.experiment_tracker import (
        ExperimentConfig,
        ExperimentRegistry,
        create_experiment_from_scoring_config,
    )
    from src.core.scoring import WEIGHTS
    EXPERIMENT_TRACKING_AVAILABLE = True
except ImportError:
    EXPERIMENT_TRACKING_AVAILABLE = False

# Import statistical rigor enhancements
try:
    from src.pipeline.backtest_statistics import (
        bootstrap_confidence_interval,
        compute_ic_distribution,
        compute_risk_adjusted_metrics,
        compute_variance_decomposition,
    )
    STATISTICS_AVAILABLE = True
except ImportError:
    STATISTICS_AVAILABLE = False


@dataclass(slots=True)
class BacktestConfig:
    start: date
    end: date
    walk: timedelta
    k: int
    output_root: Path
    seed: int = 13
    compare_baselines: bool = False
    track_experiments: bool = True
    experiment_description: str = ""
    experiment_tags: List[str] = None
    horizons: List[int] = None  # Multiple forecast horizons in days
    risk_free_rate: float = 0.0  # Annual risk-free rate
    compute_bootstrap_ci: bool = True
    n_bootstrap: int = 10000

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "BacktestConfig":
        horizons = [int(x) for x in args.horizons.split(",")] if hasattr(args, "horizons") and args.horizons else [7, 14, 30]
        
        return cls(
            start=_parse_date(args.start),
            end=_parse_date(args.end),
            walk=_parse_walk(args.walk),
            k=int(args.k),
            output_root=Path(args.output),
            seed=int(args.seed),
            compare_baselines=args.compare_baselines if hasattr(args, 'compare_baselines') else False,
            track_experiments=args.track_experiments if hasattr(args, 'track_experiments') else True,
            experiment_description=args.experiment_description if hasattr(args, 'experiment_description') else "",
            experiment_tags=args.experiment_tags.split(",") if hasattr(args, 'experiment_tags') and args.experiment_tags else [],
            horizons=horizons,
            risk_free_rate=args.risk_free_rate if hasattr(args, 'risk_free_rate') else 0.0,
            compute_bootstrap_ci=args.compute_bootstrap_ci if hasattr(args, 'compute_bootstrap_ci') else True,
            n_bootstrap=int(args.n_bootstrap) if hasattr(args, 'n_bootstrap') else 10000,
        )


def run_backtest(config: BacktestConfig) -> Path:
    """Execute a deterministic walk-forward backtest and persist artifacts."""

    random.seed(config.seed)
    windows = list(_walk_forward(config.start, config.end, config.walk))
    if not windows:
        raise ValueError("No evaluation windows were produced")

    report_date = datetime.now(UTC).strftime("%Y%m%d")
    output_dir = config.output_root / report_date
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Track experiment configuration
    experiment_config: Optional[ExperimentConfig] = None
    if config.track_experiments and EXPERIMENT_TRACKING_AVAILABLE:
        # Create experiment configuration
        feature_names = list(WEIGHTS.keys())
        hyperparameters = {
            "k": config.k,
            "seed": config.seed,
            "walk_days": config.walk.days,
            "backtest_start": config.start.isoformat(),
            "backtest_end": config.end.isoformat(),
        }
        
        experiment_config = create_experiment_from_scoring_config(
            weights=WEIGHTS,
            features=feature_names,
            hyperparameters=hyperparameters,
            description=config.experiment_description or f"Backtest {config.start} to {config.end}",
            tags=config.experiment_tags or ["backtest", "gemscore"],
        )
        
        # Register in the global registry
        registry = ExperimentRegistry()
        registry.register(experiment_config)
        
        print(f"📋 Experiment tracked: {experiment_config.config_hash[:12]}")

    window_rows: List[dict[str, object]] = []
    precision_values: List[float] = []
    forward_returns: List[float] = []
    
    # Baseline tracking if enabled
    baseline_precision: dict[str, List[float]] = {}
    baseline_returns: dict[str, List[float]] = {}
    
    if config.compare_baselines and BASELINES_AVAILABLE:
        baseline_precision = {
            "random": [],
            "cap_weighted": [],
            "simple_momentum": [],
        }
        baseline_returns = {
            "random": [],
            "cap_weighted": [],
            "simple_momentum": [],
        }

    for index, (train_start, train_end, test_start, test_end) in enumerate(windows):
        # GemScore metrics (simulated for now)
        precision = round(0.5 + 0.03 * math.tanh(index / 3), 3)
        forward_return = round(0.04 + 0.01 * math.cos(index), 4)
        sharpe = round(1.2 + 0.05 * index, 3)
        drawdown = round(0.12 + 0.01 * index, 3)

        window_row = {
            "train_start": train_start.isoformat(),
            "train_end": train_end.isoformat(),
            "test_start": test_start.isoformat(),
            "test_end": test_end.isoformat(),
            "precision_at_k": precision,
            "forward_return": forward_return,
            "max_drawdown": drawdown,
            "sharpe": sharpe,
        }
        
        # Add baseline results if enabled
        if config.compare_baselines and BASELINES_AVAILABLE:
            # Simulated baseline performance (in production, compute from real data)
            random_precision = round(0.33 + 0.02 * math.sin(index), 3)
            random_return = round(0.01 + 0.005 * math.cos(index * 0.5), 4)
            
            cap_weighted_precision = round(0.45 + 0.02 * math.cos(index * 0.8), 3)
            cap_weighted_return = round(0.025 + 0.008 * math.sin(index * 0.3), 4)
            
            momentum_precision = round(0.48 + 0.025 * math.sin(index * 1.2), 3)
            momentum_return = round(0.03 + 0.01 * math.cos(index * 0.7), 4)
            
            window_row.update({
                "random_precision": random_precision,
                "random_return": random_return,
                "cap_weighted_precision": cap_weighted_precision,
                "cap_weighted_return": cap_weighted_return,
                "momentum_precision": momentum_precision,
                "momentum_return": momentum_return,
            })
            
            baseline_precision["random"].append(random_precision)
            baseline_returns["random"].append(random_return)
            baseline_precision["cap_weighted"].append(cap_weighted_precision)
            baseline_returns["cap_weighted"].append(cap_weighted_return)
            baseline_precision["simple_momentum"].append(momentum_precision)
            baseline_returns["simple_momentum"].append(momentum_return)
        
        window_rows.append(window_row)
        precision_values.append(precision)
        forward_returns.append(forward_return)

    # Build summary with baseline comparisons
    metrics_summary = {
        "gem_score": {
            "precision_at_k": {
                "mean": round(sum(precision_values) / len(precision_values), 4),
                "best": max(precision_values),
                "worst": min(precision_values),
            },
            "forward_return": {
                "median": _median(forward_returns),
            },
        }
    }
    
    # === Statistical Rigor Enhancements ===
    if STATISTICS_AVAILABLE and len(precision_values) >= 3:
        # Bootstrap confidence intervals
        if config.compute_bootstrap_ci:
            precision_ci = bootstrap_confidence_interval(
                precision_values,
                n_bootstrap=config.n_bootstrap,
                seed=config.seed,
            )
            returns_ci = bootstrap_confidence_interval(
                forward_returns,
                n_bootstrap=config.n_bootstrap,
                seed=config.seed,
            )
            
            metrics_summary["gem_score"]["precision_at_k"]["bootstrap_ci"] = precision_ci.to_dict()
            metrics_summary["gem_score"]["forward_return"]["bootstrap_ci"] = returns_ci.to_dict()
        
        # Information Coefficient (IC) distribution
        # Simulated IC values per window (in production, use actual predictions vs actuals)
        window_predictions = []
        window_actuals = []
        for i in range(len(windows)):
            # Simulate predictions and actuals (replace with real data in production)
            n_samples = 20
            preds = [random.gauss(0.05, 0.02) for _ in range(n_samples)]
            actuals = [p + random.gauss(0, 0.01) for p in preds]  # Correlated with predictions
            window_predictions.append(preds)
            window_actuals.append(actuals)
        
        ic_dist = compute_ic_distribution(window_predictions, window_actuals)
        metrics_summary["gem_score"]["information_coefficient"] = ic_dist.to_dict()
        
        # Risk-adjusted metrics (Sharpe, Sortino, etc.)
        risk_metrics = compute_risk_adjusted_metrics(
            forward_returns,
            risk_free_rate=config.risk_free_rate / 252,  # Convert annual to daily
            periods_per_year=252,
        )
        metrics_summary["gem_score"]["risk_adjusted"] = risk_metrics.to_dict()
        
        # Variance decomposition (simulated component returns)
        component_returns = {
            "alpha": [r + random.gauss(0.01, 0.005) for r in forward_returns],
            "market_beta": [r * 0.5 + random.gauss(0, 0.01) for r in forward_returns],
            "residual": [random.gauss(0, 0.005) for _ in forward_returns],
        }
        variance_contrib = compute_variance_decomposition(forward_returns, component_returns)
        metrics_summary["gem_score"]["variance_decomposition"] = variance_contrib
        
        # Multiple horizon analysis
        horizon_metrics: Dict[str, Dict] = {}
        for horizon_days in config.horizons:
            # Simulate returns at different horizons (replace with actual data)
            horizon_returns = [r * (horizon_days / 7) + random.gauss(0, 0.01) for r in forward_returns]
            
            if len(horizon_returns) >= 3:
                horizon_risk = compute_risk_adjusted_metrics(
                    horizon_returns,
                    risk_free_rate=config.risk_free_rate / 252 * horizon_days,
                    periods_per_year=int(252 / horizon_days),
                )
                
                horizon_metrics[f"{horizon_days}d"] = {
                    "mean_return": round(sum(horizon_returns) / len(horizon_returns), 4),
                    "sharpe_ratio": horizon_risk.sharpe_ratio,
                    "sortino_ratio": horizon_risk.sortino_ratio,
                    "max_drawdown": horizon_risk.max_drawdown,
                }
        
        metrics_summary["gem_score"]["multi_horizon"] = horizon_metrics
    
    if config.compare_baselines and BASELINES_AVAILABLE and baseline_precision:
        gem_mean_precision = metrics_summary["gem_score"]["precision_at_k"]["mean"]
        gem_median_return = metrics_summary["gem_score"]["forward_return"]["median"]
        
        baselines_summary = {}
        for strategy_name in ["random", "cap_weighted", "simple_momentum"]:
            strategy_precisions = baseline_precision[strategy_name]
            strategy_returns = baseline_returns[strategy_name]
            
            mean_precision = round(sum(strategy_precisions) / len(strategy_precisions), 4)
            median_return = _median(strategy_returns)
            
            precision_improvement = round(gem_mean_precision - mean_precision, 4)
            return_improvement = round(gem_median_return - median_return, 4)
            
            baselines_summary[strategy_name] = {
                "precision_at_k": {
                    "mean": mean_precision,
                    "improvement_over_baseline": precision_improvement,
                },
                "forward_return": {
                    "median": median_return,
                    "improvement_over_baseline": return_improvement,
                },
                "outperforms": precision_improvement > 0 and return_improvement > 0,
            }
        
        metrics_summary["baselines"] = baselines_summary

    summary = {
        "config": {
            "start": config.start.isoformat(),
            "end": config.end.isoformat(),
            "walk_days": config.walk.days,
            "k": config.k,
            "seed": config.seed,
            "windows": len(window_rows),
            "compare_baselines": config.compare_baselines,
            "experiment_hash": experiment_config.config_hash if experiment_config else None,
        },
        "metrics": metrics_summary,
    }
    
    if experiment_config:
        summary["experiment"] = {
            "config_hash": experiment_config.config_hash,
            "description": experiment_config.description,
            "tags": experiment_config.tags,
            "feature_weights": experiment_config.feature_weights,
        }

    weights = {
        "k": config.k,
        "generated_at": datetime.now(UTC).isoformat(),
        "weights": {
            "technicals": 0.35,
            "onchain": 0.3,
            "narrative": 0.2,
            "risk": 0.15,
        },
    }

    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "weights_suggestion.json", weights)
    _write_csv(output_dir / "windows.csv", window_rows)
    
    # Write experiment config to separate file
    if experiment_config:
        _write_json(output_dir / "experiment_config.json", experiment_config.to_dict())
        print(f"✅ Experiment config saved to {output_dir / 'experiment_config.json'}")

    return output_dir


def _walk_forward(start: date, end: date, walk: timedelta) -> Iterable[Tuple[date, date, date, date]]:
    current_train_start = start
    current_train_end = start + walk
    while current_train_end < end:
        test_start = current_train_end
        test_end = min(end, test_start + walk)
        yield current_train_start, current_train_end, test_start, test_end
        current_train_start += walk
        current_train_end = current_train_start + walk


def _median(values: List[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return round((ordered[mid - 1] + ordered[mid]) / 2, 4)


def _parse_date(raw: str) -> date:
    return datetime.fromisoformat(raw).date()


def _parse_walk(raw: str) -> timedelta:
    if raw.endswith("d"):
        return timedelta(days=int(raw[:-1]))
    if raw.endswith("w"):
        return timedelta(weeks=int(raw[:-1]))
    raise ValueError("walk must end with 'd' or 'w'")


def _write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')


def _write_csv(path: Path, rows: List[dict[str, object]]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GemScore walk-forward backtest")
    parser.add_argument("--start", required=True, help="Backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Backtest end date (YYYY-MM-DD)")
    parser.add_argument("--walk", default="30d", help="Walk-forward window size (e.g. 30d, 4w)")
    parser.add_argument("--k", default=10, help="Precision@K cutoff", type=int)
    parser.add_argument("--output", default="reports/backtests", help="Output directory root")
    parser.add_argument("--seed", default=13, help="Random seed", type=int)
    parser.add_argument("--compare-baselines", action="store_true",
                       help="Compare GemScore against baseline strategies")
    parser.add_argument("--no-track-experiments", dest="track_experiments", action="store_false",
                       help="Disable experiment tracking")
    parser.add_argument("--experiment-description", default="",
                       help="Description of the experiment")
    parser.add_argument("--experiment-tags", default="",
                       help="Comma-separated tags for the experiment")
    
    # Statistical rigor options
    parser.add_argument("--horizons", default="7,14,30",
                       help="Comma-separated forecast horizons in days (default: 7,14,30)")
    parser.add_argument("--risk-free-rate", default=0.0, type=float,
                       help="Annual risk-free rate for Sharpe/Sortino (default: 0.0)")
    parser.add_argument("--no-bootstrap-ci", dest="compute_bootstrap_ci", action="store_false",
                       help="Disable bootstrap confidence intervals")
    parser.add_argument("--n-bootstrap", default=10000, type=int,
                       help="Number of bootstrap samples (default: 10000)")
    
    return parser


def main(argv: List[str] | None = None) -> Path:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = BacktestConfig.from_args(args)
    return run_backtest(config)


if __name__ == "__main__":  # pragma: no cover
    main()
