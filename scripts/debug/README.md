# Debug Scripts

Quick diagnostic tools for development and troubleshooting.

## Available Scripts

### debug_gaps.py
Analyzes gap trading patterns and identifies potential issues in candidate tickers.

**Usage:**
```bash
python scripts/debug/debug_gaps.py
```

**Description:**
- Analyzes the last 90 days of trading data for predefined tickers
- Identifies gaps > 3%
- Shows maximum gap and volume information
- Useful for understanding gap patterns in penny stocks

### debug_questrade.py
Tests Questrade API connectivity and authentication with detailed diagnostics.

**Usage:**
```bash
python scripts/debug/debug_questrade.py
```

**Description:**
- Validates credentials file structure
- Tests refresh token format
- Attempts API connection
- Provides detailed error diagnostics and solutions
- Shows account information on success

### debug_scan.py
Validates scanner configuration and output with a test token.

**Usage:**
```bash
python scripts/debug/debug_scan.py
```

**Description:**
- Tests the HiddenGemScanner with PEPE token
- Validates integration with free data sources
- Shows GemScore calculation and narrative
- Useful for debugging scanner pipeline issues
