"""Example usage of experiment tracking system.

This script demonstrates how to:
1. Create experiment configurations
2. Register them in the registry
3. Search and retrieve experiments
4. Compare configurations
5. Use experiments for reproducibility
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.experiment_tracker import (
    ExperimentConfig,
    ExperimentRegistry,
    create_experiment_from_scoring_config,
)
from src.core.scoring import WEIGHTS


def example_1_basic_creation():
    """Example 1: Create and register a basic experiment."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Experiment Creation")
    print("=" * 60 + "\n")
    
    # Create experiment configuration
    experiment = ExperimentConfig(
        feature_names=["price_momentum", "volume_trend", "sentiment_score"],
        feature_weights={
            "price_momentum": 0.4,
            "volume_trend": 0.3,
            "sentiment_score": 0.3,
        },
        hyperparameters={
            "k": 10,
            "threshold": 0.7,
            "seed": 42,
        },
        description="Simple momentum strategy",
        tags=["momentum", "baseline", "example"],
    )
    
    print(f"Created experiment with hash: {experiment.config_hash[:12]}")
    print(f"\nSummary:\n{experiment.summary()}")
    
    # Register in registry
    registry = ExperimentRegistry()
    config_hash = registry.register(experiment)
    
    print(f"\n✅ Registered in registry with hash: {config_hash[:12]}")


def example_2_from_scoring_config():
    """Example 2: Create experiment from GemScore configuration."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: From Scoring Configuration")
    print("=" * 60 + "\n")
    
    # Create from current scoring weights
    experiment = create_experiment_from_scoring_config(
        weights=WEIGHTS,
        features=list(WEIGHTS.keys()),
        hyperparameters={
            "k": 10,
            "min_confidence": 0.8,
            "seed": 42,
        },
        description="GemScore baseline configuration",
        tags=["gemscore", "baseline", "production"],
    )
    
    print(f"GemScore experiment hash: {experiment.config_hash[:12]}")
    print(f"\nFeatures ({len(experiment.feature_names)}):")
    for name, weight in sorted(experiment.feature_weights.items(), key=lambda x: x[1], reverse=True):
        print(f"  {name}: {weight:.2%}")
    
    # Register
    registry = ExperimentRegistry()
    registry.register(experiment)
    
    print(f"\n✅ Registered GemScore baseline")


def example_3_search_and_retrieve():
    """Example 3: Search and retrieve experiments."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Search and Retrieve")
    print("=" * 60 + "\n")
    
    registry = ExperimentRegistry()
    
    # List all experiments
    print("All experiments:")
    experiments = registry.list_all(limit=5)
    for exp in experiments:
        print(f"  {exp.config_hash[:12]} - {exp.description or '(no description)'}")
        if exp.tags:
            print(f"    Tags: {', '.join(exp.tags)}")
    
    if not experiments:
        print("  (No experiments found)")
        return
    
    print()
    
    # Search by tag
    baseline_exps = registry.search_by_tag("baseline")
    print(f"Baseline experiments ({len(baseline_exps)}):")
    for exp in baseline_exps:
        print(f"  {exp.config_hash[:12]} - {exp.description}")
    
    print()
    
    # Retrieve specific experiment (using partial hash)
    if experiments:
        partial_hash = experiments[0].config_hash[:12]
        retrieved = registry.get(partial_hash)
        print(f"Retrieved experiment by partial hash '{partial_hash}':")
        print(f"  Full hash: {retrieved.config_hash}")
        print(f"  Features: {len(retrieved.feature_names)}")


def example_4_compare_experiments():
    """Example 4: Compare two experiments."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Compare Experiments")
    print("=" * 60 + "\n")
    
    # Create two variant configurations
    base_config = ExperimentConfig(
        feature_names=["sentiment", "volume", "momentum"],
        feature_weights={
            "sentiment": 0.3,
            "volume": 0.4,
            "momentum": 0.3,
        },
        hyperparameters={"k": 10, "seed": 42},
        description="Base configuration",
        tags=["comparison", "base"],
    )
    
    variant_config = ExperimentConfig(
        feature_names=["sentiment", "volume", "momentum", "liquidity"],
        feature_weights={
            "sentiment": 0.4,  # Increased
            "volume": 0.3,     # Decreased
            "momentum": 0.2,   # Decreased
            "liquidity": 0.1,  # New feature
        },
        hyperparameters={"k": 15, "seed": 42},  # Changed k
        description="High sentiment variant",
        tags=["comparison", "variant"],
    )
    
    # Register both
    registry = ExperimentRegistry()
    hash1 = registry.register(base_config)
    hash2 = registry.register(variant_config)
    
    print(f"Base config: {hash1[:12]}")
    print(f"Variant config: {hash2[:12]}")
    print()
    
    # Compare
    comparison = registry.compare(hash1, hash2)
    
    print("Comparison Results:")
    print(f"  Features only in base: {comparison['features']['only_in_config1']}")
    print(f"  Features only in variant: {comparison['features']['only_in_config2']}")
    print(f"  Common features: {len(comparison['features']['common'])}")
    print()
    
    if comparison['weight_differences']:
        print("Weight Changes:")
        for feature, diff in comparison['weight_differences'].items():
            print(f"  {feature}:")
            print(f"    Base: {diff['config1']:.3f}")
            print(f"    Variant: {diff['config2']:.3f}")
            print(f"    Change: {diff['diff']:+.3f}")


def example_5_variant_creation():
    """Example 5: Create experiment variants."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Creating Experiment Variants")
    print("=" * 60 + "\n")
    
    registry = ExperimentRegistry()
    
    # Create baseline
    baseline = create_experiment_from_scoring_config(
        weights=WEIGHTS,
        features=list(WEIGHTS.keys()),
        hyperparameters={"k": 10, "seed": 42},
        description="Baseline GemScore configuration",
        tags=["gemscore", "baseline", "v1"],
    )
    
    baseline_hash = registry.register(baseline)
    print(f"Created baseline: {baseline_hash[:12]}")
    
    # Create variants by modifying weights
    variants = [
        {
            "name": "High Sentiment",
            "weight_changes": {"SentimentScore": 0.25, "AccumulationScore": 0.15},
            "tags": ["gemscore", "variant", "high-sentiment"],
        },
        {
            "name": "High Safety",
            "weight_changes": {"ContractSafety": 0.20, "TokenomicsRisk": 0.18},
            "tags": ["gemscore", "variant", "high-safety"],
        },
        {
            "name": "Momentum Focus",
            "weight_changes": {"NarrativeMomentum": 0.15, "CommunityGrowth": 0.12},
            "tags": ["gemscore", "variant", "momentum"],
        },
    ]
    
    print("\nCreating variants:")
    for variant_spec in variants:
        # Copy baseline weights and apply changes
        variant_weights = dict(WEIGHTS)
        variant_weights.update(variant_spec["weight_changes"])
        
        # Normalize weights to sum to 1.0
        total = sum(variant_weights.values())
        variant_weights = {k: v / total for k, v in variant_weights.items()}
        
        # Create variant config
        variant = ExperimentConfig(
            feature_names=list(WEIGHTS.keys()),
            feature_weights=variant_weights,
            hyperparameters=baseline.hyperparameters,
            description=f"{variant_spec['name']} variant of GemScore",
            tags=variant_spec["tags"],
        )
        
        variant_hash = registry.register(variant)
        print(f"  {variant_spec['name']}: {variant_hash[:12]}")
        
        # Show key differences
        for feature, new_weight in variant_spec["weight_changes"].items():
            old_weight = WEIGHTS[feature]
            print(f"    {feature}: {old_weight:.3f} → {new_weight:.3f} ({(new_weight - old_weight):+.3f})")


def example_6_reproducibility():
    """Example 6: Using experiments for reproducibility."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Reproducibility Workflow")
    print("=" * 60 + "\n")
    
    registry = ExperimentRegistry()
    
    # Simulate: You ran a backtest and got a hash
    print("Scenario: You ran a backtest 3 months ago with great results.")
    print("The backtest output included experiment hash: abc123def456")
    print()
    
    # Create a sample experiment (simulate it was created 3 months ago)
    experiment = create_experiment_from_scoring_config(
        weights=WEIGHTS,
        features=list(WEIGHTS.keys()),
        hyperparameters={"k": 10, "seed": 42, "walk_days": 30},
        description="Historical backtest with great results",
        tags=["backtest", "production", "q3-2024"],
    )
    
    config_hash = registry.register(experiment)
    print(f"Actual hash: {config_hash[:12]}")
    print()
    
    # Later: Load the exact configuration
    print("3 months later: Loading the exact configuration...")
    loaded_config = registry.get(config_hash[:12])
    
    if loaded_config:
        print("✅ Successfully loaded configuration")
        print(f"  Description: {loaded_config.description}")
        print(f"  Features: {len(loaded_config.feature_names)}")
        print(f"  Hyperparameters: {loaded_config.hyperparameters}")
        print()
        print("You can now re-run the exact same experiment:")
        print("  - Same features")
        print("  - Same weights")
        print("  - Same hyperparameters")
        print("  - Guaranteed reproducibility")
    else:
        print("❌ Configuration not found")


def example_7_export_import():
    """Example 7: Export and import configurations."""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Export and Import")
    print("=" * 60 + "\n")
    
    import tempfile
    import json
    
    registry = ExperimentRegistry()
    
    # Create an experiment
    experiment = create_experiment_from_scoring_config(
        weights=WEIGHTS,
        features=list(WEIGHTS.keys()),
        hyperparameters={"k": 10},
        description="Configuration for export",
        tags=["export-example"],
    )
    
    config_hash = registry.register(experiment)
    print(f"Created experiment: {config_hash[:12]}")
    
    # Export to JSON
    export_path = Path(tempfile.gettempdir()) / "experiment_config.json"
    export_path.write_text(experiment.to_json())
    print(f"✅ Exported to: {export_path}")
    
    # Show exported JSON (pretty print)
    exported_data = json.loads(export_path.read_text())
    print(f"\nExported JSON structure:")
    print(f"  - feature_names: {len(exported_data['feature_names'])} features")
    print(f"  - feature_weights: {len(exported_data['feature_weights'])} weights")
    print(f"  - config_hash: {exported_data['config_hash'][:12]}...")
    
    # Import back
    imported_config = ExperimentConfig.from_json(export_path.read_text())
    print(f"\n✅ Imported successfully")
    print(f"  Hash matches: {imported_config.config_hash == experiment.config_hash}")
    
    # Cleanup
    export_path.unlink()


def main():
    """Run all examples."""
    print("\n" + "█" * 60)
    print("  EXPERIMENT TRACKING EXAMPLES")
    print("█" * 60)
    
    examples = [
        example_1_basic_creation,
        example_2_from_scoring_config,
        example_3_search_and_retrieve,
        example_4_compare_experiments,
        example_5_variant_creation,
        example_6_reproducibility,
        example_7_export_import,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\n❌ Error in {example.__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run 'python -m src.cli.experiments list' to see registered experiments")
    print("  2. Try creating your own experiment variants")
    print("  3. Run a backtest with experiment tracking enabled")
    print("\nDocumentation:")
    print("  - docs/EXPERIMENT_TRACKING.md")
    print("  - docs/EXPERIMENT_TRACKING_QUICK_REF.md")


if __name__ == "__main__":
    main()
