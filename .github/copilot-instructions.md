# Copilot Instructions for AutoTrader

## Project Overview

AutoTrader is a sophisticated cryptocurrency trading system featuring:
- **Hidden-Gem Scanner**: Fuses on-chain telemetry, narrative intelligence, technical analysis, and safety gating
- **BounceHunter/PennyHunter**: Gap trading strategy with multi-broker support
- **Multi-Exchange Support**: Integration with Binance, IBKR, Alpaca, Questrade (Canadian broker)
- **ML/MLOps Pipeline**: Feature engineering, model training, backtesting, and deployment
- **Observability**: Comprehensive monitoring with Prometheus, Grafana, and OpenTelemetry
- **Compliance Monitoring**: Market regime detection, risk filters, and regulatory compliance

## Tech Stack

- **Language**: Python 3.11+ (3.11, 3.12, 3.13 supported)
- **Frameworks**: FastAPI, Pydantic, SQLAlchemy, Alembic
- **Data Science**: NumPy, Pandas, scikit-learn, LightGBM, Optuna
- **ML Ops**: MLflow, Prefect, Weights & Biases (wandb), DVC
- **Exchange APIs**: CCXT, ccxt.pro (WebSocket), yfinance, ib_insync
- **Observability**: Structlog, Prometheus, OpenTelemetry
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Code Quality**: black, isort, flake8, mypy, bandit

## Architecture

- **Source Code**: `src/` - Main application code
- **Pipeline**: `pipeline/` - Data processing and backtesting
- **Backtest**: `backtest/` - Backtesting harness
- **Scripts**: `scripts/` - Utility scripts and automation
- **Tests**: `tests/` - Test suite
- **Documentation**: `docs/` - Comprehensive documentation (20+ guides)
- **Configuration**: `configs/` - YAML configuration files
- **Infrastructure**: `infrastructure/`, `infra/`, `terraform/` - Deployment configs

Key modules in `src/`:
- `src/bouncehunter/` - Gap trading strategy implementation
- `src/core/` - Core trading engine and pipeline
- `src/services/` - API services and metrics
- `src/brokers/` - Broker integrations (Alpaca, Questrade, IBKR)
- `src/feature_engineering/` - ML feature computation
- `src/compliance/` - Compliance and risk management

## Build and Setup

### Initial Setup

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Or use Make
make bootstrap
```

### Database Setup

```bash
# Run migrations
alembic upgrade head
```

### Configuration

- Copy `.env.template` to `.env` and configure environment variables
- See `.env.example` for complete configuration options
- For Canadian users, use `.env.production.template`

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage (80% minimum required)
pytest --cov=src --cov-report=term --cov-fail-under=80

# Or use Make
make coverage

# Run specific test file
pytest tests/test_features.py

# Run specific test
pytest tests/test_features.py::test_feature_computation
```

### Test Configuration

- Test files: `tests/` directory with `test_*.py` naming
- Test functions: `test_*` naming convention
- Coverage threshold: 80% minimum (enforced in CI)
- Async tests: Use `pytest-asyncio` for async/await code

### Test Data

- Use fixtures in `tests/fixtures/` for test data
- Mock external services (exchanges, brokers, APIs)
- Real data tests are in `test_*_live.py` files (may require API keys)

## Linting and Code Quality

### Code Formatting

```bash
# Format code with black (line length: 120)
black src/ tests/

# Sort imports
isort src/ tests/

# Check formatting without changes
black --check src/ tests/
isort --check-only src/ tests/
```

### Linting

```bash
# Run flake8
flake8 src/ tests/ --max-line-length=120

# Run ruff (faster linter)
ruff check src/ tests/ --fix
```

### Type Checking

```bash
# Run mypy
mypy src/ --ignore-missing-imports --exclude "src/legacy/"
```

### Security Scanning

```bash
# Security checks
make security

# Or manually:
bandit -r src/ -ll
pip-audit --requirement requirements.txt
```

### Pre-commit Hooks

Pre-commit hooks are configured in `.pre-commit-config.yaml`:
- Code formatting (black, isort)
- Linting (ruff)
- Security (bandit, detect-secrets)
- Type checking (mypy)
- YAML/JSON validation
- Markdown linting
- Configuration validation

To install: `pre-commit install`

## Style Guidelines

### Python Style

- **Line length**: 120 characters (black and flake8 configured)
- **Imports**: Use isort with black profile
- **Type hints**: Required for new code (mypy enforced)
- **Docstrings**: Use Google-style docstrings for functions and classes
- **Naming**:
  - Classes: `PascalCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
  - Private members: `_leading_underscore`

### Code Organization

- Keep modules focused and single-purpose
- Use `__init__.py` for package exports
- Separate concerns: business logic, API routes, data models
- Use dependency injection for testability

### Documentation

- Update relevant documentation in `docs/` for user-facing changes
- Keep inline comments minimal and explain "why" not "what"
- Update CHANGELOG or phase documents for significant changes

## Common Patterns

### Configuration

```python
from pydantic import BaseModel

class MyConfig(BaseModel):
    """Configuration with validation."""
    api_key: str
    timeout: int = 30
    
config = MyConfig.parse_obj(data)
```

### Logging

```python
import structlog

logger = structlog.get_logger(__name__)
logger.info("operation_completed", duration=1.5, records=100)
```

### Async/Await

```python
import asyncio

async def fetch_data(symbol: str) -> dict:
    """Fetch data asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/api/{symbol}") as response:
            return await response.json()
```

### Testing

```python
import pytest

@pytest.mark.asyncio
async def test_fetch_data():
    """Test async data fetching."""
    result = await fetch_data("BTC/USD")
    assert "price" in result
    assert result["price"] > 0
```

## Dependencies

### Adding New Dependencies

1. Check if dependency is already available (check `requirements.txt`)
2. Add to `requirements.txt` or `pyproject.toml`
3. Run security checks: `pip-audit` and `safety check`
4. Update `requirements-dev.txt` for dev-only dependencies
5. Document any special setup in relevant docs

### Python Version Support

- Minimum: Python 3.11
- Supported: 3.11, 3.12, 3.13
- Test matrix: CI runs on all supported versions

## Security Guidelines

### Sensitive Data

- Never commit API keys, secrets, or credentials
- Use environment variables for secrets (`.env` file, not committed)
- See `.env.template` for required environment variables
- Use `.secrets.baseline` for detect-secrets exceptions

### Security Scanning

- Bandit: Python code security scanning (runs in CI)
- pip-audit: Dependency vulnerability scanning
- Semgrep: SAST (Static Application Security Testing)
- Trivy: Container and filesystem scanning
- Gitleaks/TruffleHog: Secret detection

### Best Practices

- Validate all user inputs
- Use parameterized queries (SQLAlchemy ORM)
- Sanitize data for external services
- Use HTTPS for all external API calls
- Implement rate limiting for API endpoints

## Broker Integration (Important!)

### Canadian Users

- **IBKR** (Interactive Brokers): Recommended for Canadian residents
- **Questrade**: Canadian broker with auto-refreshing tokens
- **Alpaca**: NOT available for Canadian residents (US only)

### Adding Broker Support

- Implement interface in `src/brokers/base.py`
- Add broker-specific client in `src/brokers/`
- Update `src/brokers/factory.py`
- Add tests in `tests/brokers/`
- Document setup in `docs/`

## Common Issues

### Import Errors

- Ensure you're in the correct virtual environment
- Run `pip install -r requirements.txt`
- Check that you're running from the repository root

### Test Failures

- Many tests require mock data or environment setup
- Tests with `_live` suffix may need API keys (skip in CI)
- Check test fixtures in `tests/fixtures/`

### Database Migrations

- Use Alembic for schema changes
- Run `alembic upgrade head` after pulling changes
- Create new migration: `alembic revision --autogenerate -m "description"`

## Contributing

### Before Submitting PRs

1. Run all tests: `pytest`
2. Check coverage: `pytest --cov=src --cov-report=term --cov-fail-under=80`
3. Format code: `black src/ tests/` and `isort src/ tests/`
4. Run linting: `flake8 src/ tests/ --max-line-length=120`
5. Type check: `mypy src/ --ignore-missing-imports --exclude "src/legacy/"`
6. Security scan: `make security`

### Commit Messages

Follow conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance

### CI/CD

- All PRs must pass CI checks
- Code coverage must be ≥80%
- Security scans must pass
- At least 1 approving review required

## Key Documentation Files

- **Architecture**: `ARCHITECTURE.md` - System architecture and design
- **Features**: `FEATURE_CATALOG.md` - Complete feature inventory
- **Contributing**: `CONTRIBUTING.md` - Contribution guidelines
- **Security**: `SECURITY.md` - Security policies
- **Phase Docs**: `PHASE_*.md` - Implementation roadmap and status

## Ecosystem Tools

### Use Scaffolding Tools

- **FastAPI**: Use `fastapi.APIRouter` for route organization
- **Pydantic**: Use for configuration and data validation
- **SQLAlchemy**: Use ORM for database operations
- **Alembic**: Use for database migrations

### Prefer Library Functions

- Use `pandas` for data manipulation
- Use `numpy` for numerical operations
- Use `ccxt` for exchange integrations
- Use `structlog` for logging
- Use `pytest` fixtures for test setup

### Automation

- Use `make` targets for common operations
- Use pre-commit hooks for code quality
- Use CI/CD for automated testing
- Use Alembic for database migrations

## Special Directories

### Do Not Modify

- `site/` - Generated documentation (do not commit)
- `mlruns/` - MLflow tracking data
- `build/`, `dist/` - Build artifacts
- `.dvc/` - DVC internal files
- `autotrader.egg-info/` - Package metadata

### Generated Files

- `compliance_report.json` - Generated by compliance checks
- `bandit-report.json` - Security scan results
- `*.log` - Log files

## Performance Considerations

- Use async/await for I/O-bound operations
- Batch database operations when possible
- Use connection pooling for databases and APIs
- Cache expensive computations
- Profile before optimizing

## Legacy Code

The `src/legacy/` directory contains deprecated code:
- Not covered by type checking (mypy excludes it)
- Should not be modified unless necessary
- Use new implementations in `src/` instead

## Additional Resources

- **Quick Start Guides**: See `docs/` for specific workflows
- **API Documentation**: Generated with `make docs`
- **Phase Documents**: Track implementation progress
- **Example Configs**: See `configs/` directory
- **Example Scripts**: See `examples/` directory
