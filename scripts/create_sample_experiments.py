#!/usr/bin/env python3
"""Create sample experiment data for testing the experiments workspace."""

from pathlib import Path
from src.utils.experiment_tracker import ExperimentConfig, ExperimentRegistry
import json


def create_sample_experiments():
    """Create sample experiment configurations."""
    registry = ExperimentRegistry()
    
    # Experiment 1: Baseline configuration
    exp1 = ExperimentConfig(
        feature_names=["price", "volume", "liquidity", "sentiment"],
        feature_weights={
            "price": 0.25,
            "volume": 0.25,
            "liquidity": 0.25,
            "sentiment": 0.25,
        },
        hyperparameters={
            "k": 10,
            "min_score": 0.5,
        },
        description="Baseline equal-weight configuration",
        tags=["baseline", "equal-weight"],
    )
    
    # Experiment 2: Sentiment-focused
    exp2 = ExperimentConfig(
        feature_names=["price", "volume", "liquidity", "sentiment", "narrative_momentum"],
        feature_weights={
            "price": 0.15,
            "volume": 0.15,
            "liquidity": 0.15,
            "sentiment": 0.35,
            "narrative_momentum": 0.20,
        },
        hyperparameters={
            "k": 15,
            "min_score": 0.6,
        },
        description="Sentiment-focused configuration with narrative features",
        tags=["sentiment", "narrative"],
    )
    
    # Experiment 3: Risk-adjusted
    exp3 = ExperimentConfig(
        feature_names=["price", "volume", "liquidity", "volatility", "safety_score"],
        feature_weights={
            "price": 0.20,
            "volume": 0.20,
            "liquidity": 0.25,
            "volatility": 0.15,
            "safety_score": 0.20,
        },
        hyperparameters={
            "k": 12,
            "min_score": 0.7,
            "max_volatility": 0.5,
        },
        description="Risk-adjusted configuration emphasizing safety",
        tags=["risk-adjusted", "conservative"],
    )
    
    # Register experiments
    hash1 = registry.register(exp1)
    hash2 = registry.register(exp2)
    hash3 = registry.register(exp3)
    
    print(f"✓ Created experiment 1: {hash1[:12]} (baseline)")
    print(f"✓ Created experiment 2: {hash2[:12]} (sentiment-focused)")
    print(f"✓ Created experiment 3: {hash3[:12]} (risk-adjusted)")
    
    # Create sample backtest results
    results_dir = Path("backtest_results")
    results_dir.mkdir(exist_ok=True)
    
    # Sample results for exp1
    results1 = {
        "precision_at_k": 0.65,
        "average_return_at_k": 0.12,
        "extended_metrics": {
            "ic_pearson": 0.42,
            "ic_spearman": 0.38,
            "sharpe_ratio": 1.2,
            "sortino_ratio": 1.5,
            "max_drawdown": -0.15,
            "win_rate": 0.58,
        },
        "baseline_results": {
            "random": {"precision": 0.50, "avg_return": 0.05},
            "momentum": {"precision": 0.55, "avg_return": 0.08},
        },
        "flagged_assets": ["TOKEN1", "TOKEN2"],
    }
    
    with open(results_dir / f"{hash1[:12]}.json", 'w') as f:
        json.dump(results1, f, indent=2)
    print(f"✓ Created results for {hash1[:12]}")
    
    # Sample results for exp2
    results2 = {
        "precision_at_k": 0.72,
        "average_return_at_k": 0.18,
        "extended_metrics": {
            "ic_pearson": 0.51,
            "ic_spearman": 0.47,
            "sharpe_ratio": 1.6,
            "sortino_ratio": 1.9,
            "max_drawdown": -0.12,
            "win_rate": 0.64,
        },
        "baseline_results": {
            "random": {"precision": 0.50, "avg_return": 0.05},
            "momentum": {"precision": 0.55, "avg_return": 0.08},
        },
        "flagged_assets": ["TOKEN3"],
    }
    
    with open(results_dir / f"{hash2[:12]}.json", 'w') as f:
        json.dump(results2, f, indent=2)
    print(f"✓ Created results for {hash2[:12]}")
    
    # Sample results for exp3
    results3 = {
        "precision_at_k": 0.68,
        "average_return_at_k": 0.14,
        "extended_metrics": {
            "ic_pearson": 0.45,
            "ic_spearman": 0.43,
            "sharpe_ratio": 1.8,
            "sortino_ratio": 2.1,
            "max_drawdown": -0.08,
            "win_rate": 0.62,
        },
        "baseline_results": {
            "random": {"precision": 0.50, "avg_return": 0.05},
            "momentum": {"precision": 0.55, "avg_return": 0.08},
        },
        "flagged_assets": [],
    }
    
    with open(results_dir / f"{hash3[:12]}.json", 'w') as f:
        json.dump(results3, f, indent=2)
    print(f"✓ Created results for {hash3[:12]}")
    
    # Create sample execution tree
    trees_dir = Path("execution_trees")
    trees_dir.mkdir(exist_ok=True)
    
    sample_tree = {
        "key": "root",
        "title": "Experiment Execution",
        "description": "Root execution node",
        "outcome": {
            "status": "success",
            "summary": "Experiment completed successfully",
            "data": {}
        },
        "children": [
            {
                "key": "data_loading",
                "title": "Data Loading",
                "description": "Load historical data",
                "outcome": {
                    "status": "success",
                    "summary": "Loaded 1000 snapshots",
                    "data": {"num_snapshots": 1000}
                },
                "children": []
            },
            {
                "key": "feature_engineering",
                "title": "Feature Engineering",
                "description": "Compute features",
                "outcome": {
                    "status": "success",
                    "summary": "Computed 5 features",
                    "data": {"num_features": 5}
                },
                "children": []
            },
            {
                "key": "scoring",
                "title": "Scoring",
                "description": "Compute gem scores",
                "outcome": {
                    "status": "success",
                    "summary": "Scored 1000 tokens",
                    "data": {"num_scored": 1000}
                },
                "children": []
            }
        ]
    }
    
    for hash_val in [hash1, hash2, hash3]:
        with open(trees_dir / f"{hash_val[:12]}.json", 'w') as f:
            json.dump(sample_tree, f, indent=2)
    print(f"✓ Created execution trees for all experiments")
    
    print("\n✅ Sample data created successfully!")
    print("\nExperiment hashes:")
    print(f"  1. {hash1[:12]} - Baseline")
    print(f"  2. {hash2[:12]} - Sentiment-focused")
    print(f"  3. {hash3[:12]} - Risk-adjusted")


if __name__ == "__main__":
    create_sample_experiments()
