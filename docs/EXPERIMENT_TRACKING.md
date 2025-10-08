# Experiment Configuration Tracking

## Overview

The experiment tracking system provides reproducible experiment management for the AutoTrader system. Each experiment configuration is hashed to ensure reproducibility, and all configurations are stored in a searchable registry.

## Key Features

- **Deterministic Hashing**: SHA256 hash of feature set + weights + hyperparameters
- **Persistent Storage**: SQLite-based registry for experiment configurations
- **Tag-based Search**: Organize and find experiments by tags
- **Comparison Tools**: Compare feature sets and weights across experiments
- **CLI Management**: Command-line tools for listing, viewing, and comparing experiments
- **Backtest Integration**: Automatic tracking of backtest experiment configurations

## Quick Start

### Running a Backtest with Experiment Tracking

```bash
# Basic backtest with automatic experiment tracking
python -m src.pipeline.backtest \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --walk 30d \
  --k 10 \
  --experiment-description "Baseline GemScore configuration" \
  --experiment-tags "baseline,production,q4-2024"

# Disable experiment tracking (if needed)
python -m src.pipeline.backtest \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --no-track-experiments
```

### Managing Experiments via CLI

```bash
# List all experiments
python -m src.cli.experiments list

# Show detailed information about an experiment
python -m src.cli.experiments show abc123def456

# Search experiments by tag
python -m src.cli.experiments search baseline

# Compare two experiments
python -m src.cli.experiments compare abc123 def456

# Export experiment configuration
python -m src.cli.experiments export abc123 experiment_config.json

# Import experiment configuration
python -m src.cli.experiments import experiment_config.json

# Delete an experiment
python -m src.cli.experiments delete abc123 --force
```

## Programmatic Usage

### Creating and Registering an Experiment

```python
from src.utils.experiment_tracker import (
    ExperimentConfig,
    ExperimentRegistry,
    create_experiment_from_scoring_config,
)
from src.core.scoring import WEIGHTS

# Method 1: Create from scoring config
experiment = create_experiment_from_scoring_config(
    weights=WEIGHTS,
    features=list(WEIGHTS.keys()),
    hyperparameters={
        "k": 10,
        "threshold": 0.7,
        "min_confidence": 0.8,
    },
    description="GemScore baseline with increased threshold",
    tags=["gemscore", "baseline", "production"],
)

# Method 2: Create manually
experiment = ExperimentConfig(
    feature_names=[
        "SentimentScore",
        "AccumulationScore",
        "OnchainActivity",
        "LiquidityDepth",
    ],
    feature_weights={
        "SentimentScore": 0.25,
        "AccumulationScore": 0.35,
        "OnchainActivity": 0.25,
        "LiquidityDepth": 0.15,
    },
    hyperparameters={"k": 10, "seed": 42},
    feature_transformations={
        "SentimentScore": "zscore",
        "AccumulationScore": "log",
    },
    description="Custom weighted configuration",
    tags=["experimental", "high-sentiment"],
)

# Register in the registry
registry = ExperimentRegistry()
config_hash = registry.register(experiment)

print(f"Registered experiment: {config_hash[:12]}")
print(experiment.summary())
```

### Loading and Comparing Experiments

```python
from src.utils.experiment_tracker import ExperimentRegistry

registry = ExperimentRegistry()

# Load by hash (full or partial)
experiment = registry.get("abc123def456")
if experiment:
    print(experiment.summary())

# Search by tag
baseline_experiments = registry.search_by_tag("baseline")
for exp in baseline_experiments:
    print(f"{exp.config_hash[:12]}: {exp.description}")

# Compare two experiments
comparison = registry.compare("abc123", "def456")
print(f"Features only in first: {comparison['features']['only_in_config1']}")
print(f"Features only in second: {comparison['features']['only_in_config2']}")
print(f"Weight differences: {comparison['weight_differences']}")

# List all experiments
all_experiments = registry.list_all(limit=50)
for exp in all_experiments:
    print(f"{exp.config_hash[:12]} - {exp.created_at}")
```

## Configuration Hash

The configuration hash is a **deterministic SHA256 hash** computed from:

1. **Feature names** (sorted alphabetically)
2. **Feature weights** (sorted by key)
3. **Feature transformations** (sorted by key)
4. **Hyperparameters** (sorted by key)

**Important**: The hash does NOT include:
- Description (can be updated without changing hash)
- Tags (can be updated without changing hash)
- Created timestamp

This ensures that:
- Same configuration always produces same hash
- Metadata can be updated without creating new experiments
- Hash serves as a unique identifier for reproducibility

### Example Hash Computation

```python
config = ExperimentConfig(
    feature_names=["price", "volume", "sentiment"],
    feature_weights={"price": 0.3, "volume": 0.4, "sentiment": 0.3},
    hyperparameters={"k": 10, "seed": 42},
)

# Hash is automatically computed
print(config.config_hash)
# Output: "a1b2c3d4e5f6..." (64 character hex string)

# Same config produces same hash
config2 = ExperimentConfig(
    feature_names=["price", "volume", "sentiment"],
    feature_weights={"price": 0.3, "volume": 0.4, "sentiment": 0.3},
    hyperparameters={"k": 10, "seed": 42},
)
assert config.config_hash == config2.config_hash
```

## Database Schema

The experiment registry uses SQLite with the following schema:

```sql
-- Main experiments table
CREATE TABLE experiments (
    config_hash TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    description TEXT,
    feature_names TEXT NOT NULL,
    feature_weights TEXT NOT NULL,
    feature_transformations TEXT,
    hyperparameters TEXT,
    tags TEXT,
    config_json TEXT NOT NULL
);

-- Tags table for efficient searching
CREATE TABLE experiment_tags (
    config_hash TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (config_hash, tag),
    FOREIGN KEY (config_hash) REFERENCES experiments(config_hash)
);

CREATE INDEX idx_created_at ON experiments(created_at);
```

## Backtest Integration

When running a backtest with experiment tracking enabled (default), the system:

1. **Creates** an `ExperimentConfig` from current scoring weights
2. **Registers** it in the global registry (`experiments.sqlite`)
3. **Saves** the config to `experiment_config.json` in the backtest output directory
4. **Includes** the experiment hash in `summary.json`

### Backtest Output Structure

```
reports/backtests/20241008/
├── summary.json           # Includes experiment_hash
├── windows.csv
├── weights_suggestion.json
└── experiment_config.json # Full experiment configuration
```

### Example summary.json with Experiment

```json
{
  "config": {
    "start": "2024-01-01",
    "end": "2024-12-31",
    "k": 10,
    "seed": 42,
    "experiment_hash": "a1b2c3d4e5f6..."
  },
  "experiment": {
    "config_hash": "a1b2c3d4e5f6...",
    "description": "Baseline GemScore configuration",
    "tags": ["baseline", "production"],
    "feature_weights": {
      "SentimentScore": 0.15,
      "AccumulationScore": 0.20,
      ...
    }
  },
  "metrics": {
    ...
  }
}
```

## Best Practices

### 1. Meaningful Descriptions

```python
# ❌ Bad
description = "test"

# ✅ Good
description = "Increased sentiment weight from 0.15 to 0.25 to test impact on precision"
```

### 2. Consistent Tagging

Use a consistent tagging scheme:

```python
tags = [
    "gemscore",           # System/strategy name
    "baseline",           # Experiment type
    "q4-2024",           # Time period
    "production",        # Environment
    "high-sentiment",    # Variant description
]
```

### 3. Track Hyperparameters

Always include relevant hyperparameters:

```python
hyperparameters = {
    "k": 10,                    # Precision@K
    "seed": 42,                 # Random seed
    "threshold": 0.7,           # Filtering threshold
    "min_confidence": 0.8,      # Minimum confidence
    "walk_days": 30,            # Backtest window
}
```

### 4. Version Control Experiments

Export important experiments to version control:

```bash
# Export experiment
python -m src.cli.experiments export abc123 configs/baseline_v1.json

# Commit to git
git add configs/baseline_v1.json
git commit -m "Add baseline experiment configuration"
```

## Reproducibility Workflow

### 1. Run Initial Experiment

```bash
python -m src.pipeline.backtest \
  --start 2024-01-01 --end 2024-12-31 \
  --experiment-description "Baseline configuration" \
  --experiment-tags "baseline,v1"
```

Note the experiment hash: `abc123def456`

### 2. Load and Analyze

```python
from src.utils.experiment_tracker import ExperimentRegistry

registry = ExperimentRegistry()
baseline = registry.get("abc123")

print(f"Baseline weights: {baseline.feature_weights}")
print(f"Baseline hyperparams: {baseline.hyperparameters}")
```

### 3. Create Variant

```python
# Load baseline
baseline = registry.get("abc123")

# Create variant with modified weights
variant = ExperimentConfig(
    feature_names=baseline.feature_names,
    feature_weights={
        **baseline.feature_weights,
        "SentimentScore": 0.25,  # Increased from 0.15
        "AccumulationScore": 0.15,  # Decreased from 0.20
    },
    hyperparameters=baseline.hyperparameters,
    description="Increased sentiment weight variant",
    tags=["variant", "high-sentiment", "v2"],
)

variant_hash = registry.register(variant)
```

### 4. Compare Results

```bash
python -m src.cli.experiments compare abc123 def456
```

## CLI Reference

### List Experiments

```bash
# List all experiments
python -m src.cli.experiments list

# Limit results
python -m src.cli.experiments list --limit 10
```

### Show Experiment Details

```bash
# Human-readable format
python -m src.cli.experiments show abc123

# JSON format
python -m src.cli.experiments show abc123 --json
```

### Search by Tag

```bash
python -m src.cli.experiments search baseline
python -m src.cli.experiments search production
```

### Compare Experiments

```bash
# Human-readable comparison
python -m src.cli.experiments compare abc123 def456

# JSON comparison
python -m src.cli.experiments compare abc123 def456 --json
```

### Export/Import

```bash
# Export to file
python -m src.cli.experiments export abc123 my_config.json

# Import from file
python -m src.cli.experiments import my_config.json
```

### Delete Experiment

```bash
# With confirmation
python -m src.cli.experiments delete abc123

# Skip confirmation
python -m src.cli.experiments delete abc123 --force
```

## Advanced Usage

### Custom Database Location

```python
from src.utils.experiment_tracker import ExperimentRegistry

# Use custom database path
registry = ExperimentRegistry("path/to/my_experiments.sqlite")
```

```bash
# CLI with custom database
python -m src.cli.experiments --db path/to/my_experiments.sqlite list
```

### Batch Operations

```python
from src.utils.experiment_tracker import ExperimentRegistry

registry = ExperimentRegistry()

# Find all production experiments
production_exps = registry.search_by_tag("production")

# Export all production experiments
for exp in production_exps:
    output_path = f"backups/prod_{exp.config_hash[:12]}.json"
    with open(output_path, "w") as f:
        f.write(exp.to_json())
```

## Testing

Run the test suite:

```bash
# Run all experiment tracker tests
pytest tests/test_experiment_tracker.py -v

# Run specific test
pytest tests/test_experiment_tracker.py::TestExperimentConfig::test_hash_determinism -v
```

## Troubleshooting

### Issue: Experiment not found

```python
experiment = registry.get("abc")
# Returns None
```

**Solution**: Use a longer hash prefix or the full hash:

```python
# Try with more characters
experiment = registry.get("abc123")

# Or list all to find it
all_exps = registry.list_all()
for exp in all_exps:
    print(exp.config_hash[:12])
```

### Issue: Hash collision (extremely rare)

If two different configurations somehow produce the same hash:

1. This is cryptographically extremely unlikely with SHA256
2. The configuration is likely actually identical
3. Use `registry.compare()` to verify they're truly different

### Issue: Database locked

```
sqlite3.OperationalError: database is locked
```

**Solution**: Ensure no other processes are accessing the database:

```bash
# Check for locks
lsof experiments.sqlite

# Kill locking process or wait for it to complete
```

## Migration Guide

### From Manual Config Tracking

If you've been tracking configs manually, migrate to the registry:

```python
from src.utils.experiment_tracker import ExperimentConfig, ExperimentRegistry
import json

# Load your old config
with open("old_config.json") as f:
    old_config = json.load(f)

# Create ExperimentConfig
experiment = ExperimentConfig(
    feature_names=old_config["features"],
    feature_weights=old_config["weights"],
    hyperparameters=old_config.get("hyperparameters", {}),
    description=old_config.get("description", "Migrated config"),
    tags=["migrated"] + old_config.get("tags", []),
)

# Register
registry = ExperimentRegistry()
registry.register(experiment)
```

## Related Documentation

- [Backtest Pipeline](../docs/runbooks/backtesting.md)
- [Feature Engineering](../src/services/feature_engineering.py)
- [GemScore Calculation](../src/core/scoring.py)
- [Baseline Strategies](../docs/BASELINE_STRATEGIES.md)

## Future Enhancements

Planned features:

- [ ] Web UI for experiment management
- [ ] Automatic experiment comparison in backtest output
- [ ] Integration with MLflow or Weights & Biases
- [ ] Experiment lineage tracking (parent/child relationships)
- [ ] Automatic rollback to previous configurations
- [ ] A/B testing support
