# Experiments Workspace Documentation

## Overview

The Experiments Workspace provides a comprehensive interface for managing, analyzing, and comparing machine learning experiments for the AutoTrader GemScore evaluation system.

## Features

### 1. Experiments Registry
- **Grid View**: Visual card-based display of all experiments
- **Search**: Full-text search across experiment descriptions
- **Tag Filtering**: Filter experiments by tags (e.g., "baseline", "sentiment", "risk-adjusted")
- **Metadata Display**: Shows hash, creation date, feature count, and result availability

### 2. Experiment Detail View
- **Configuration Snapshot**: Complete experiment configuration with:
  - Feature names and weights (visual bar chart)
  - Hyperparameters
  - Tags and metadata
- **Performance Metrics**: 
  - Precision@K and Average Return@K
  - Extended metrics (Sharpe ratio, Sortino ratio, Max drawdown, Win rate)
  - Information Coefficient (IC) metrics
- **Baseline Comparison**: Compare against random and momentum baselines
- **Execution Tree**: Tree-of-Thought visualization showing experiment execution flow

### 3. Experiment Comparison
- **Side-by-Side View**: Compare two experiments simultaneously
- **Feature Set Diff**: Shows common, unique, and removed features
- **Weight Differences**: Sorted table of weight changes with deltas
- **Hyperparameter Comparison**: Side-by-side hyperparameter display
- **Metrics Comparison**: Performance metric deltas with significance indicators

### 4. Artifact Export
- **JSON Export**: Download complete experiment configuration and results
- **PDF Export**: (Planned) Generate formatted PDF reports

## API Endpoints

### List Experiments
```
GET /api/experiments
Query params:
  - limit: int (max 500, default 100)
  - tag: string (filter by tag)
  - search: string (search in descriptions)
```

### Get Experiment Detail
```
GET /api/experiments/{config_hash}
Query params:
  - include_results: bool (default true)
  - include_tree: bool (default true)
```

### Get Experiment Metrics
```
GET /api/experiments/{config_hash}/metrics
Returns: Performance metrics and backtest results
```

### Get Execution Tree
```
GET /api/experiments/{config_hash}/tree
Returns: Tree-of-Thought execution structure
```

### Compare Experiments
```
GET /api/experiments/compare/{hash1}/{hash2}
Query params:
  - include_metrics: bool (default true)
Returns: Side-by-side comparison with deltas
```

### Export Experiment
```
POST /api/experiments/export
Body: {
  config_hash: string,
  format: "json" | "pdf",
  include_metrics: bool,
  include_config: bool
}
```

### Delete Experiment
```
DELETE /api/experiments/{config_hash}
```

### Get All Tags
```
GET /api/experiments/tags/all
Returns: List of all tags with counts
```

## Frontend Components

### ExperimentsRegistry
Entry point component showing all experiments in a grid layout with search and filters.

**Props:**
- `onSelectExperiment: (hash: string) => void` - Callback when experiment is selected

### ExperimentDetail
Detailed view of a single experiment with metrics and configuration.

**Props:**
- `configHash: string` - Experiment hash to display
- `onCompare?: (hash: string) => void` - Optional compare callback
- `onExport?: (hash: string) => void` - Optional export callback

### ExperimentCompare
Side-by-side comparison of two experiments.

**Props:**
- `hash1: string` - First experiment hash
- `hash2: string` - Second experiment hash
- `onClose?: () => void` - Optional close callback

### ExperimentsWorkspace
Main workspace wrapper with navigation and routing between views.

**Features:**
- Breadcrumb navigation
- View state management
- Handles view transitions

## Data Storage

### Directory Structure
```
backtest_results/     # Backtest metrics and results (JSON)
execution_trees/      # Execution tree structures (JSON)
exports/             # Exported artifacts
experiments.sqlite   # Experiment configurations database
```

### File Naming Convention
- Results: `{short_hash}.json` (e.g., `a1b2c3d4e5f6.json`)
- Trees: `{short_hash}.json`
- Exports: `experiment_{short_hash}.{format}`

## Creating Sample Data

Use the provided script to create sample experiments:

```bash
python scripts/create_sample_experiments.py
```

This creates:
- 3 sample experiment configurations
- Corresponding backtest results
- Execution tree structures

## Integration with Existing Systems

### Experiment Tracker
The workspace integrates with `src/utils/experiment_tracker.py`:
- `ExperimentConfig`: Configuration data class
- `ExperimentRegistry`: SQLite-backed storage

### Backtest Harness
Results format matches `backtest/harness.py`:
- `BacktestResult.to_dict()` format
- Extended metrics from `backtest/extended_metrics.py`

### Execution Trees
Tree structure matches token scanning pipeline:
- Root node with children
- Outcome status (success/failure/skipped)
- Summary and data fields

## Best Practices

### Creating Experiments
1. **Descriptive Names**: Use clear, descriptive experiment descriptions
2. **Meaningful Tags**: Tag experiments by purpose (baseline, production, experimental)
3. **Deterministic Hashes**: Same config = same hash (reproducibility)
4. **Version Control**: Export important experiments to JSON for version control

### Comparing Experiments
1. **Compare Similar Configs**: Compare experiments with similar feature sets
2. **Track Deltas**: Focus on significant weight or metric differences
3. **Statistical Significance**: Consider sample size and confidence intervals
4. **Baseline Reference**: Always compare against baseline strategies

### Managing Experiments
1. **Cleanup Old Experiments**: Regularly delete obsolete experiments
2. **Tag Organization**: Maintain consistent tagging scheme
3. **Export Important Results**: Backup key experiments to exports/
4. **Document Changes**: Use descriptions to explain experiment rationale

## Testing

Run integration tests:
```bash
python tests/test_experiments_workspace.py
```

Tests verify:
- API endpoint structure
- Frontend component existence
- Type definitions
- Data directory setup
- .gitignore configuration

## Troubleshooting

### No experiments showing
- Check that `experiments.sqlite` exists
- Run sample data creation script
- Verify API endpoints are accessible

### Missing results or trees
- Ensure files exist in `backtest_results/` and `execution_trees/`
- Check file naming matches experiment hash (first 12 chars)
- Verify JSON format is valid

### Comparison not working
- Ensure both experiments exist
- Check that hashes are valid
- Verify experiments have comparable structures

## Future Enhancements

Planned features:
- [ ] Automatic experiment creation from backtest runs
- [ ] PDF export with charts and visualizations
- [ ] Real-time metrics updates via WebSocket
- [ ] Experiment versioning and history
- [ ] A/B testing framework integration
- [ ] Statistical significance testing
- [ ] Hyperparameter optimization tracking
- [ ] Multi-experiment batch comparison

## API Security

All API endpoints include:
- Rate limiting (60 requests/minute for reads, 30 for writes)
- Request validation via Pydantic models
- Error handling with descriptive messages
- CORS support for frontend integration

## Performance Considerations

- Registry queries are limited to 500 experiments max
- Results and trees are loaded on-demand
- Comparison caches common data
- Export operations have lower rate limits
- Database uses indexes on timestamps and hashes
