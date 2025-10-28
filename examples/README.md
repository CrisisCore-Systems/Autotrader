# Examples Directory

This directory contains example scripts, configurations, and testing utilities for AutoTrader.

## Directory Structure

### 📁 `gui/`
GUI applications and dashboards:
- `gui_trading_dashboard.py` - Trading dashboard application

### 📁 `runners/`
Executable scripts for running various AutoTrader features:
- `run_pennyhunter_nightly.py` - Run PennyHunter nightly strategy
- `run_pennyhunter_paper.py` - Run PennyHunter in paper trading mode
- `run_scanner_free.py` - Run the hidden gem scanner (free tier)
- `run_feature_tests.py` - Test feature computation
- `run_labeling_tests.py` - Test labeling system
- `demo_ml_ready_features.py` - Demo ML-ready feature generation

### 📁 `testing/`
Testing utilities and integration tests:
- `test_all_bars.py` - Test all bar types
- `test_bars_binance_live.py` - Test bars with live Binance data
- `test_bars_with_features.py` - Test bar generation with features
- `test_cleaning_pipeline.py` - Test data cleaning pipeline
- `test_dukascopy.py` - Test Dukascopy data integration
- `test_labeling_debug.py` - Debug labeling system
- `test_labeling_system.py` - Test labeling system
- `test_microstructure_features.py` - Test microstructure features
- `test_orderbook_features.py` - Test order book features
- `test_time_bars.py` - Test time-based bars
- `validate_improvements.py` - Validate system improvements

### 📄 Configuration Files
- `test_scan.yaml` - Example scanner configuration for testing

## Usage

### Running Examples

Most scripts can be run directly from the repository root:

```bash
# Run the hidden gem scanner
python examples/runners/run_scanner_free.py

# Run PennyHunter in paper trading mode
python examples/runners/run_pennyhunter_paper.py

# Test bar generation
python examples/testing/test_all_bars.py
```

### Environment Setup

Ensure you have:
1. Installed dependencies: `pip install -r requirements.txt`
2. Configured environment variables (see `.env.template`)
3. Set up necessary API keys for live data sources

### Testing Utilities

The `testing/` directory contains scripts useful for:
- Validating data pipelines
- Testing feature computation
- Debugging issues with live data
- Verifying system improvements

These are not part of the main test suite (`tests/`) but are useful for manual testing and exploration.

## Notes

- These examples are for demonstration and testing purposes
- Some scripts require API keys or broker credentials
- Check individual script documentation for specific requirements
- For automated tests, see the `tests/` directory instead

## Related Documentation

- [Main Documentation](../docs/)
- [Quick Start Guides](../docs/guides/)
- [API Reference](../docs/api_reference.md)
