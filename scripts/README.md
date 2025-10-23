# Scripts Directory

This directory contains organized utilities, debugging tools, and manual tests for the AutoTrader project.

## Directory Structure

```
scripts/
├── api/                          # API server scripts
├── debug/                        # Debug scripts for development
├── setup/                        # Configuration and setup utilities
├── testing/                      # Manual testing scripts
│   ├── manual_integration/       # Broker integration tests
│   └── smoke/                    # Quick smoke tests
└── troubleshooting/              # Advanced diagnostic tools
```

## Quick Reference

### Starting the API Server
```bash
python scripts/api/start_api.py
```

### Debugging Broker Connections

**Questrade:**
```bash
python scripts/debug/debug_questrade.py
```

**IBKR:**
```bash
python scripts/testing/manual_integration/test_ibkr_connection.py
```

### Setup & Configuration

**Set Questrade Token:**
```bash
python scripts/setup/set_questrade_token.py
```

**Update Questrade Token:**
```bash
python scripts/setup/update_questrade_token.py
```

### Running Manual Tests

**IBKR Connection Test:**
```bash
python scripts/testing/manual_integration/test_ibkr_connection.py
```

**Questrade Full Test:**
```bash
python scripts/testing/manual_integration/test_questrade.py
```

**Smoke Test:**
```bash
python scripts/testing/smoke/ibkr_smoke_test.py
```

### Troubleshooting

**Diagnose Questrade Issues:**
```bash
export QTRADE_REFRESH_TOKEN="your_token"
python scripts/troubleshooting/diagnose_questrade.py
```

**Check Trading Sessions:**
```bash
python scripts/troubleshooting/check_sessions.py
```

## Categories

### API Scripts (`api/`)
Tools for starting and managing the FastAPI server. Includes the main server launcher and compatibility shims for legacy code.

See [api/README.md](api/README.md) for details.

### Debug Scripts (`debug/`)
Quick diagnostic tools for development and troubleshooting. These scripts help identify issues with data sources, broker connections, and scanner configuration.

See [debug/README.md](debug/README.md) for details.

### Setup Scripts (`setup/`)
Configuration and token management utilities. Used for initial setup and maintaining broker credentials.

See [setup/README.md](setup/README.md) for details.

### Testing Scripts (`testing/`)
Manual integration tests and smoke tests that are not part of the automated pytest suite. These should be run manually before production deployments.

- **manual_integration/**: Comprehensive broker integration tests
- **smoke/**: Quick validation tests for rapid feedback

See [testing/manual_integration/README.md](testing/manual_integration/README.md) and [testing/smoke/README.md](testing/smoke/README.md) for details.

### Troubleshooting Scripts (`troubleshooting/`)
Advanced diagnostic tools for resolving specific issues. These provide deeper analysis than debug scripts.

See [troubleshooting/README.md](troubleshooting/README.md) for details.

## Important Notes

⚠️ **Manual Tests vs Automated Tests**

Scripts in `scripts/testing/` are manual integration tests, NOT part of the automated pytest suite in `tests/`.

- **Automated tests** (`tests/`): Run with `pytest`, part of CI/CD
- **Manual tests** (`scripts/testing/`): Run manually before releases, require live broker connections

## Common Workflows

### First-Time Broker Setup

**IBKR:**
1. Install TWS/IB Gateway and start it
2. Run: `python scripts/testing/manual_integration/test_ibkr_connection.py`
3. Follow troubleshooting steps if needed

**Questrade:**
1. Get refresh token from Questrade
2. Run: `python scripts/setup/set_questrade_token.py`
3. Test: `python scripts/debug/debug_questrade.py`
4. Verify: `python scripts/testing/manual_integration/test_questrade.py`

### Pre-Release Validation

Before deploying to production:

1. Run smoke tests:
   ```bash
   python scripts/testing/smoke/ibkr_smoke_test.py
   ```

2. Run full integration tests:
   ```bash
   python scripts/testing/manual_integration/test_ibkr_connection.py
   python scripts/testing/manual_integration/test_ibkr_orders.py
   python scripts/testing/manual_integration/test_production_components.py
   ```

3. Run automated test suite:
   ```bash
   pytest tests/
   ```

### Troubleshooting Connection Issues

1. Start with debug scripts for quick diagnostics
2. If issue persists, use troubleshooting scripts for deeper analysis
3. Check relevant documentation in `docs/`

## Related Documentation

- [docs/BROKER_INTEGRATION.md](../docs/BROKER_INTEGRATION.md) - Broker setup guide
- [docs/OPERATIONS_RUNBOOKS.md](../docs/OPERATIONS_RUNBOOKS.md) - Daily operations
- [docs/legacy/IBKR_SETUP_README.md](../docs/legacy/IBKR_SETUP_README.md) - IBKR setup
- [docs/legacy/QUESTRADE_SETUP.md](../docs/legacy/QUESTRADE_SETUP.md) - Questrade setup

## Contributing

When adding new scripts:

1. Place them in the appropriate subdirectory
2. Add path setup if the script imports from `src/`:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent.parent))
   ```
3. Update the subdirectory README.md
4. Add usage examples to this main README
