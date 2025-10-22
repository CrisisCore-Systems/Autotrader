# Manual Integration Tests

Scripts for manual testing of broker integrations before production deployment.

⚠️ **Note**: These are NOT part of the automated pytest suite. Run manually before production releases.

## Running Tests

### Interactive Brokers Tests

#### test_ibkr_connection.py
Quick connection test to verify IBKR paper trading setup.

```bash
python scripts/testing/manual_integration/test_ibkr_connection.py
```

**Prerequisites:**
- TWS running on port 7497
- API settings enabled in TWS
- "Use Account Groups with Allocation Methods" UNCHECKED

#### test_ibkr_orders.py
Tests order placement with Financial Advisor (FA) scrubbing.

```bash
python scripts/testing/manual_integration/test_ibkr_orders.py
```

**Tests:**
- Market order placement
- Limit order placement
- FA account scrubbing functionality

#### test_fa_scrub.py
Low-level test for FA order scrubbing functionality.

```bash
python scripts/testing/manual_integration/test_fa_scrub.py
```

### Questrade Tests

#### test_questrade.py
Comprehensive Questrade connection test with account validation.

```bash
python scripts/testing/manual_integration/test_questrade.py
```

**Tests:**
- Broker connection
- Account balance retrieval
- Position fetching
- Full integration validation

#### test_questrade_direct.py
Direct API test using raw HTTP requests.

```bash
python scripts/testing/manual_integration/test_questrade_direct.py
```

**Description:**
- Tests Questrade API without broker abstraction layer
- Useful for isolating API vs. integration issues

### Token Management Tests

#### test_token_detailed.py
Detailed token validation and management testing.

```bash
python scripts/testing/manual_integration/test_token_detailed.py
```

### Production Component Tests

#### test_production_components.py
Phase 3 validation suite for production components.

```bash
python scripts/testing/manual_integration/test_production_components.py
```

**Tests:**
- GemScorer functionality
- MarketRegimeDetector
- NewsSentry sentiment analysis
- GapScanner operations

## Prerequisites

### General Requirements
- Valid broker credentials in environment variables or configs
- Paper trading accounts for testing
- All project dependencies installed (`pip install -r requirements.txt`)

### IBKR-Specific
- Interactive Brokers TWS or IB Gateway running
- API port configured (default: 7497 for paper)
- Valid paper trading account

### Questrade-Specific
- Valid refresh token in `configs/broker_credentials.yaml`
- API access enabled in Questrade account
- See `docs/legacy/QUESTRADE_SETUP.md` for detailed setup

## Troubleshooting

If tests fail, see:
- `docs/BROKER_INTEGRATION.md` - Broker setup guide
- `docs/legacy/IBKR_SETUP_README.md` - IBKR-specific setup
- `docs/legacy/QUESTRADE_SETUP.md` - Questrade-specific setup
- `scripts/troubleshooting/` - Diagnostic scripts
