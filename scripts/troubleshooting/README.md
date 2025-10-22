# Troubleshooting Scripts

Advanced diagnostic tools for resolving specific issues.

## Available Scripts

### diagnose_questrade.py
Deep diagnostics for Questrade token issues with both production and practice endpoints.

**Usage:**
```bash
# Set token in environment variable first
export QTRADE_REFRESH_TOKEN="your_token_here"
python scripts/troubleshooting/diagnose_questrade.py
```

**Description:**
- Tests both production and practice Questrade endpoints
- Identifies which endpoint the token is valid for
- Fetches account information on successful connection
- Provides specific error codes and solutions
- Helpful for determining if token is for live or paper trading

### check_sessions.py
Inspects cumulative trading history and session markers.

**Usage:**
```bash
python scripts/troubleshooting/check_sessions.py
```

**Description:**
- Loads pennyhunter cumulative history
- Shows total sessions and date range
- Lists all session markers with dates
- Useful for validating historical trading data integrity
