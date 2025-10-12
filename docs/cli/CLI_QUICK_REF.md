# CLI Backtest - Quick Reference

## Quick Start

```bash
# Basic backtest
python pipeline/cli_backtest.py --start 2024-01-01 --end 2024-12-31

# With baselines and extended metrics
python pipeline/cli_backtest.py \
    --start 2024-01-01 --end 2024-12-31 \
    --compare-baselines --extended-metrics \
    --engine harness --data features.csv
```

## Common Commands

| Task | Command |
|------|---------|
| Help | `python pipeline/cli_backtest.py --help` |
| Basic backtest | `python pipeline/cli_backtest.py --start 2024-01-01 --end 2024-12-31` |
| Debug mode | `python pipeline/cli_backtest.py --start 2024-01-01 --end 2024-12-31 --log-level DEBUG` |
| JSON export | `python pipeline/cli_backtest.py --start 2024-01-01 --end 2024-12-31 --json-export` |
| Compare engines | `python pipeline/cli_backtest.py --start 2024-01-01 --end 2024-12-31 --engine harness --data data.csv` |
| Run tests | `python -m pytest tests/test_cli_backtest_smoke.py -v` |

## Engine Comparison

| Feature | Pipeline | Harness |
|---------|----------|---------|
| Walk-forward | ✅ Yes | ❌ No |
| Experiment tracking | ✅ Yes | ❌ No |
| Extended metrics | ❌ No | ✅ Yes |
| Baseline comparison | ✅ Yes | ✅ Yes |
| Single period | ❌ No | ✅ Yes |
| Best for | Production | Analysis |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Config error |
| 3 | Runtime error |
| 130 | User interrupt |

## Key Options

```bash
--engine {pipeline,harness}    # Choose backtest engine
--compare-baselines            # Add baseline comparisons
--extended-metrics             # Calculate IC, Sharpe, etc.
--json-export                  # Export JSON results
--log-level {DEBUG,INFO,...}   # Set logging verbosity
--experiment-tags "tag1,tag2"  # Tag experiments
```

## Files Modified

- ✅ `pipeline/cli_backtest.py` - Enhanced CLI (383 lines)
- ✅ `pyproject.toml` - Console scripts added
- ✅ `tests/test_cli_backtest_smoke.py` - 9 tests (all passing)
- ✅ `docs/CLI_BACKTEST_GUIDE.md` - Full documentation

## Quality Metrics

- ✅ 9/9 tests passing
- ✅ 0 code quality issues
- ✅ 0 security vulnerabilities
- ✅ Full type hints
- ✅ Proper exit codes
- ✅ No circular imports

## Installation

```bash
# Development install
pip install -e .

# Then use console scripts
autotrader-backtest --start 2024-01-01 --end 2024-12-31
autotrader-backtest-harness --data features.csv
```

## Documentation

- **Full Guide**: `docs/CLI_BACKTEST_GUIDE.md`
- **Summary**: `CLI_ENHANCEMENT_SUMMARY.md`
- **This File**: Quick reference

## Support

For issues or questions:
1. Check `docs/CLI_BACKTEST_GUIDE.md` for detailed docs
2. Run tests: `python -m pytest tests/test_cli_backtest_smoke.py -v`
3. Enable debug logging: `--log-level DEBUG`
