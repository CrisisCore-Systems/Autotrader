# CLI Backtest Wrapper - Complete Guide

## Overview

The enhanced CLI backtest wrapper (`pipeline/cli_backtest.py`) provides a robust, production-ready command-line interface for running GemScore backtests with multiple engines and comprehensive configuration options.

## Features

### ✅ Implemented Features

1. **Robust Argument Parsing**
   - Strategy parameters (walk-forward window, precision@K, seed)
   - Output path configuration
   - JSON export capability
   - Extended metrics toggle

2. **Multi-Engine Support**
   - `--engine pipeline`: Walk-forward backtest with experiment tracking
   - `--engine harness`: Single-period evaluation with extended metrics
   - Easy comparison between engines

3. **Centralized Logging**
   - Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
   - Consistent diagnostic output
   - Proper timestamp formatting

4. **Error Handling & Exit Codes**
   - Exit code 0: Success
   - Exit code 1: Unexpected error
   - Exit code 2: Configuration error
   - Exit code 3: Execution error
   - Exit code 130: User interrupt (Ctrl+C)

5. **Type Hints**
   - Explicit type annotations throughout
   - Support for static analysis tools

6. **Package Configuration**
   - Console scripts in `pyproject.toml`:
     - `autotrader-backtest`: Main CLI wrapper
     - `autotrader-backtest-harness`: Direct harness access
   - Proper package discovery with `tool.setuptools.packages.find`

7. **Comprehensive Testing**
   - 9 smoke tests covering all major functionality
   - Help command validation
   - Error handling verification
   - Module import checks

## Usage Examples

### Basic Pipeline Backtest
```bash
python pipeline/cli_backtest.py \
    --start 2024-01-01 \
    --end 2024-12-31
```

### Harness Engine with Extended Metrics
```bash
python pipeline/cli_backtest.py \
    --engine harness \
    --data path/to/features.csv \
    --extended-metrics \
    --compare-baselines \
    --k 20
```

### Full Configuration with Experiment Tracking
```bash
python pipeline/cli_backtest.py \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --walk 30d \
    --k 10 \
    --output ./results \
    --json-export \
    --compare-baselines \
    --experiment-description "Q1 2024 Production Test" \
    --experiment-tags "q1-2024,production,baseline-comparison" \
    --log-level DEBUG
```

### Using Installed Console Scripts
After installing the package with `pip install -e .`:

```bash
# Use the CLI wrapper
autotrader-backtest --start 2024-01-01 --end 2024-12-31

# Use the harness directly
autotrader-backtest-harness --data features.csv --top-k 10
```

## Command-Line Options

### Core Parameters
- `--start START`: Backtest start date (YYYY-MM-DD) [REQUIRED]
- `--end END`: Backtest end date (YYYY-MM-DD) [REQUIRED]
- `--walk WALK`: Walk-forward window size (e.g., 30d, 4w) [Default: 30d]
- `--k K`: Precision@K cutoff [Default: 10]
- `--seed SEED`: Random seed for reproducibility [Default: 13]

### Engine Selection
- `--engine {pipeline,harness}`: Backtest engine to use [Default: pipeline]
  - `pipeline`: Walk-forward with experiment tracking
  - `harness`: Single-period with extended metrics

### Strategy & Analysis
- `--compare-baselines`: Compare against baseline strategies (random, cap-weighted, momentum)
- `--extended-metrics`: Calculate IC and risk-adjusted returns (harness only)

### Output Configuration
- `--output OUTPUT`: Output directory root [Default: reports/backtests]
- `--json-export`: Export results in JSON format

### Experiment Tracking (Pipeline Engine)
- `--no-track-experiments`: Disable experiment tracking
- `--experiment-description DESC`: Experiment description
- `--experiment-tags TAGS`: Comma-separated tags (e.g., "q1-2024,production")

### Harness Engine Options
- `--data DATA`: Path to CSV with features (required for harness)

### Logging & Diagnostics
- `--log-level LEVEL`: Logging level [Choices: DEBUG, INFO, WARNING, ERROR, CRITICAL] [Default: INFO]

## Architecture

### File Structure
```
pipeline/
├── cli_backtest.py      # Enhanced CLI wrapper (this file)
├── __init__.py          # Pipeline module exports
└── __main__.py          # Module execution support

src/pipeline/
└── backtest.py          # Pipeline engine implementation

backtest/
├── harness.py           # Harness engine implementation
├── baseline_strategies.py
└── extended_metrics.py

tests/
└── test_cli_backtest_smoke.py  # CLI smoke tests
```

### Design Decisions

1. **No Circular Imports**: Renamed from `pipeline/backtest.py` to `pipeline/cli_backtest.py` to avoid conflicts with `src.pipeline.backtest`

2. **Dual Engine Support**: Both engines accessible through single CLI for easy comparison

3. **Fail-Fast Validation**: Comprehensive argument validation before execution

4. **CI/CD Ready**: Proper exit codes enable integration with CI/CD pipelines

5. **Extensible**: Easy to add new engines or options without breaking existing functionality

## Testing

Run all smoke tests:
```bash
python -m pytest tests/test_cli_backtest_smoke.py -v
```

Individual test categories:
```bash
# Test help functionality
python -m pytest tests/test_cli_backtest_smoke.py::test_cli_backtest_help -v

# Test error handling
python -m pytest tests/test_cli_backtest_smoke.py::test_cli_backtest_missing_required_args -v

# Test module imports
python -m pytest tests/test_cli_backtest_smoke.py::test_cli_module_import -v
```

## Code Quality

All files pass Codacy analysis:
- ✅ Pylint: No issues
- ✅ Semgrep: No issues
- ✅ Trivy: No security vulnerabilities

## Exit Codes Reference

| Code | Meaning | Use Case |
|------|---------|----------|
| 0 | Success | Normal completion |
| 1 | General error | Unexpected failures |
| 2 | Configuration error | Invalid arguments or config |
| 3 | Execution error | Runtime failures |
| 130 | User interrupt | Ctrl+C pressed |

## Integration with CI/CD

Example GitHub Actions workflow:
```yaml
- name: Run Backtest
  run: |
    python pipeline/cli_backtest.py \
      --start 2024-01-01 \
      --end 2024-12-31 \
      --output ./ci-results \
      --json-export \
      --log-level INFO
    
- name: Check Exit Code
  if: failure()
  run: echo "Backtest failed with exit code $?"
```

## Future Enhancements

Potential additions for future versions:
- [ ] Configuration file support (YAML/TOML)
- [ ] Parallel execution for multiple date ranges
- [ ] Live progress reporting with progress bars
- [ ] Email notifications on completion
- [ ] Integration with MLflow for experiment tracking
- [ ] Docker container support
- [ ] Web dashboard for results visualization

## Troubleshooting

### Import Errors
If you see `ModuleNotFoundError: No module named 'src'`:
- Ensure you're running from the project root directory
- Set PYTHONPATH: `export PYTHONPATH=/path/to/AutoTrader`
- Or use the installed console script

### Timeout Issues
If backtests timeout:
- Reduce the date range
- Use larger walk-forward windows (--walk 90d)
- Disable extended metrics and baselines for faster execution

### Memory Issues
For large datasets:
- Process in smaller date ranges
- Increase available RAM
- Use the harness engine for single-period analysis

## Contributing

When adding new features:
1. Update argument parser in `build_parser()`
2. Add corresponding logic in `run_pipeline_engine()` or `run_harness_engine()`
3. Add smoke tests to `tests/test_cli_backtest_smoke.py`
4. Update this documentation
5. Run Codacy analysis to ensure code quality

## License

Part of the AutoTrader project. See main project LICENSE for details.
