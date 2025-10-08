# Experiment Tracking Quick Reference

## TL;DR

```bash
# Run backtest with experiment tracking
python -m src.pipeline.backtest --start 2024-01-01 --end 2024-12-31 \
  --experiment-description "Baseline config" --experiment-tags "baseline,prod"

# List experiments
python -m src.cli.experiments list

# Show details
python -m src.cli.experiments show abc123

# Compare two experiments
python -m src.cli.experiments compare abc123 def456

# Search by tag
python -m src.cli.experiments search baseline
```

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Config Hash** | SHA256 hash of features + weights + hyperparameters |
| **Reproducibility** | Same hash = identical configuration |
| **Registry** | SQLite database storing all experiments |
| **Tags** | Searchable labels (e.g., "baseline", "production") |

## Python Quick Start

```python
from src.utils.experiment_tracker import (
    ExperimentConfig,
    ExperimentRegistry,
    create_experiment_from_scoring_config,
)
from src.core.scoring import WEIGHTS

# Create and register experiment
experiment = create_experiment_from_scoring_config(
    weights=WEIGHTS,
    features=list(WEIGHTS.keys()),
    hyperparameters={"k": 10, "seed": 42},
    description="Baseline GemScore",
    tags=["baseline", "production"],
)

registry = ExperimentRegistry()
hash_id = registry.register(experiment)
print(f"Registered: {hash_id[:12]}")

# Load and use
loaded = registry.get(hash_id[:12])
print(loaded.summary())
```

## CLI Commands

### List & Search

```bash
# List all
python -m src.cli.experiments list

# Search by tag
python -m src.cli.experiments search baseline
python -m src.cli.experiments search production
```

### View Details

```bash
# Human-readable
python -m src.cli.experiments show abc123

# JSON format
python -m src.cli.experiments show abc123 --json
```

### Compare

```bash
# Compare two experiments
python -m src.cli.experiments compare abc123 def456
```

### Export/Import

```bash
# Export
python -m src.cli.experiments export abc123 config.json

# Import
python -m src.cli.experiments import config.json
```

### Delete

```bash
# With confirmation
python -m src.cli.experiments delete abc123

# Skip confirmation
python -m src.cli.experiments delete abc123 --force
```

## What Gets Tracked

### ✅ Included in Hash
- Feature names
- Feature weights
- Feature transformations
- Hyperparameters

### ❌ Not in Hash (Metadata Only)
- Description
- Tags
- Created timestamp

## Common Patterns

### Pattern 1: Baseline + Variants

```bash
# Create baseline
python -m src.pipeline.backtest --start 2024-01-01 --end 2024-12-31 \
  --experiment-description "Baseline config" \
  --experiment-tags "baseline,v1"
# Note hash: abc123

# Compare with variant
python -m src.cli.experiments compare abc123 def456
```

### Pattern 2: Tag-based Organization

```python
tags = [
    "gemscore",        # System
    "baseline",        # Type
    "q4-2024",        # Period
    "production",     # Environment
]
```

### Pattern 3: Hyperparameter Search

```python
for k in [5, 10, 15, 20]:
    experiment = create_experiment_from_scoring_config(
        weights=WEIGHTS,
        features=list(WEIGHTS.keys()),
        hyperparameters={"k": k, "seed": 42},
        description=f"K={k} experiment",
        tags=["hyperparam-search", f"k={k}"],
    )
    registry.register(experiment)

# Find best K
results = registry.search_by_tag("hyperparam-search")
```

## Backtest Integration

When running backtests, experiments are automatically:

1. Created from current scoring configuration
2. Registered in `experiments.sqlite`
3. Saved to `experiment_config.json` in output directory
4. Referenced in `summary.json` via hash

### Disable Tracking

```bash
python -m src.pipeline.backtest --start 2024-01-01 --end 2024-12-31 \
  --no-track-experiments
```

## Reproducibility Workflow

```bash
# 1. Run experiment
python -m src.pipeline.backtest ... --experiment-tags "exp-001"

# 2. Note the hash from output
# Experiment tracked: abc123def456

# 3. Later: load exact configuration
python -m src.cli.experiments show abc123

# 4. Compare with another run
python -m src.cli.experiments compare abc123 xyz789

# 5. Export for archival
python -m src.cli.experiments export abc123 archive/baseline.json
```

## Database Location

Default: `experiments.sqlite` in project root

Custom location:

```bash
# CLI
python -m src.cli.experiments --db path/to/db.sqlite list

# Python
registry = ExperimentRegistry("path/to/db.sqlite")
```

## Testing

```bash
# Run tests
pytest tests/test_experiment_tracker.py -v

# Quick smoke test
python -c "
from src.utils.experiment_tracker import ExperimentConfig, ExperimentRegistry
config = ExperimentConfig(
    feature_names=['a', 'b'],
    feature_weights={'a': 0.5, 'b': 0.5}
)
print(f'Hash: {config.config_hash[:12]}')
"
```

## Common Issues

### Hash not found

Use longer prefix or full hash:

```bash
# Instead of
python -m src.cli.experiments show abc

# Use
python -m src.cli.experiments show abc123def456
```

### Database locked

Wait for other process to complete or:

```bash
# Check locks
lsof experiments.sqlite
```

## Examples

See:
- `examples/experiment_tracking_example.py` - Complete examples
- `docs/EXPERIMENT_TRACKING.md` - Full documentation
- `tests/test_experiment_tracker.py` - Test cases

## Next Steps

1. Run a backtest with tracking
2. List experiments to see your config
3. Create a variant by modifying weights
4. Compare the two experiments
5. Export the best config for production
