# Script Migration Quick Reference

Scripts have been reorganized from the root directory into `scripts/` subdirectories.

## Quick Command Translation

### API Scripts
```bash
# Old → New
python start_api.py          →  python scripts/api/start_api.py
python simple_api.py         →  python scripts/api/simple_api.py
```

### Debug Scripts
```bash
# Old → New
python debug_gaps.py         →  python scripts/debug/debug_gaps.py
python debug_questrade.py    →  python scripts/debug/debug_questrade.py
python debug_scan.py         →  python scripts/debug/debug_scan.py
```

### Setup Scripts
```bash
# Old → New
python set_questrade_token.py    →  python scripts/setup/set_questrade_token.py
python update_questrade_token.py →  python scripts/setup/update_questrade_token.py
```

### Test Scripts
```bash
# Old → New
python test_ibkr_connection.py      →  python scripts/testing/manual_integration/test_ibkr_connection.py
python test_ibkr_orders.py          →  python scripts/testing/manual_integration/test_ibkr_orders.py
python test_questrade.py            →  python scripts/testing/manual_integration/test_questrade.py
python test_questrade_direct.py     →  python scripts/testing/manual_integration/test_questrade_direct.py
python test_fa_scrub.py             →  python scripts/testing/manual_integration/test_fa_scrub.py
python test_token_detailed.py       →  python scripts/testing/manual_integration/test_token_detailed.py
python test_production_components.py →  python scripts/testing/manual_integration/test_production_components.py
python ibkr_smoke_test.py           →  python scripts/testing/smoke/ibkr_smoke_test.py
```

### Troubleshooting Scripts
```bash
# Old → New
python diagnose_questrade.py →  python scripts/troubleshooting/diagnose_questrade.py
python check_sessions.py     →  python scripts/troubleshooting/check_sessions.py
```

## New Directory Structure

```
scripts/
├── api/                      # API server launchers
│   ├── start_api.py
│   ├── simple_api.py
│   └── README.md
├── debug/                    # Development debugging tools
│   ├── debug_gaps.py
│   ├── debug_questrade.py
│   ├── debug_scan.py
│   └── README.md
├── setup/                    # Configuration utilities
│   ├── set_questrade_token.py
│   ├── update_questrade_token.py
│   └── README.md
├── testing/
│   ├── manual_integration/   # Manual broker integration tests
│   │   ├── test_*.py (7 files)
│   │   └── README.md
│   └── smoke/               # Quick smoke tests
│       ├── ibkr_smoke_test.py
│       └── README.md
└── troubleshooting/         # Advanced diagnostics
    ├── diagnose_questrade.py
    ├── check_sessions.py
    └── README.md
```

## Documentation

For detailed information about each script, see:
- Main guide: [scripts/README.md](scripts/README.md)
- API scripts: [scripts/api/README.md](scripts/api/README.md)
- Debug tools: [scripts/debug/README.md](scripts/debug/README.md)
- Setup utilities: [scripts/setup/README.md](scripts/setup/README.md)
- Manual tests: [scripts/testing/manual_integration/README.md](scripts/testing/manual_integration/README.md)
- Smoke tests: [scripts/testing/smoke/README.md](scripts/testing/smoke/README.md)
- Troubleshooting: [scripts/troubleshooting/README.md](scripts/troubleshooting/README.md)

## Note

All scripts function exactly as before - only their locations have changed.
No functionality or behavior has been modified.
