# Contributing to Autotrader

Thank you for your interest in contributing to Autotrader! This guide will help you get started.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Submitting Changes](#submitting-changes)
- [CI/CD Pipeline](#cicd-pipeline)

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/Autotrader.git
   cd Autotrader
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/CrisisCore-Systems/Autotrader.git
   ```

## Development Setup

### Prerequisites

- Python 3.11 or higher (3.11, 3.12, or 3.13 recommended)
- pip package manager
- Git

### Install Dependencies

```bash
# Install core dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt
```

### Optional: Install Pre-commit Hooks

Pre-commit hooks help catch issues before pushing to GitHub:

```bash
pip install pre-commit
pre-commit install
```

Now hooks will run automatically on `git commit`.

## Making Changes

### Branch Strategy

1. **Create a feature branch** from `develop`:
   ```bash
   git checkout develop
   git pull upstream develop
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** with clear, focused commits:
   ```bash
   git add .
   git commit -m "feat: add new trading strategy"
   ```

### Commit Message Guidelines

Follow conventional commits format:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `style:` - Code style changes (formatting, etc.)
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

Example:
```
feat: add support for multiple exchanges

- Add CCXT integration for Binance
- Update configuration schema
- Add unit tests for exchange connector
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term --cov-report=html

# Run specific test file
pytest tests/test_features.py

# Run specific test
pytest tests/test_features.py::test_feature_computation
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use descriptive test names that explain what is being tested
- Aim for 80%+ code coverage

Example test:
```python
def test_feature_computation():
    """Test that feature computation handles edge cases."""
    # Arrange
    data = {"price": 100.0, "volume": 1000}
    
    # Act
    features = compute_features(data)
    
    # Assert
    assert features["price_change"] >= 0
    assert "volume_avg" in features
```

## Code Quality

### Code Formatting

We use `black` and `isort` for consistent code formatting:

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Check formatting (without changing files)
black --check src/ tests/
isort --check-only src/ tests/
```

### Linting

We use `flake8` for linting:

```bash
# Run linter
flake8 src/ tests/ --max-line-length=120
```

### Type Checking

We use `mypy` for static type checking:

```bash
# Run type checker
mypy src/ --ignore-missing-imports --exclude "src/legacy/"
```

### Security Scanning

Before submitting, run security checks:

```bash
# Security scan with Bandit
bandit -r src/

# Check dependencies
pip-audit --requirement requirements.txt
safety check
```

### Running All Checks Locally

Run all CI checks before pushing:

```bash
# Format and lint
black src/ tests/
isort src/ tests/
flake8 src/ tests/ --max-line-length=120

# Type check
mypy src/ --ignore-missing-imports --exclude "src/legacy/"

# Test with coverage
pytest --cov=src --cov-report=term --cov-fail-under=80

# Security checks
bandit -r src/ -f json -o bandit-report.json
pip-audit --requirement requirements.txt || true
```

## Submitting Changes

### Before Submitting

1. **Run all tests locally** and ensure they pass
2. **Run code quality checks** (formatting, linting, type checking)
3. **Update documentation** if needed
4. **Add tests** for new functionality
5. **Ensure coverage** meets the 80% threshold

### Creating a Pull Request

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open a Pull Request** on GitHub:
   - Go to the [Autotrader repository](https://github.com/CrisisCore-Systems/Autotrader)
   - Click "New Pull Request"
   - Select your feature branch
   - Fill out the PR template with:
     - Description of changes
     - Related issues
     - Testing performed
     - Screenshots (if applicable)

3. **Address review feedback**:
   - Make requested changes
   - Push new commits to your branch
   - The PR will automatically update

### PR Requirements

Your PR must meet these requirements before merging:

- ✅ All CI checks pass (tests, lint, security)
- ✅ Code coverage meets 80% threshold
- ✅ At least 1 approving review
- ✅ All conversations resolved
- ✅ Branch is up to date with base branch

## CI/CD Pipeline

### Automated Checks

When you open a PR, the following checks run automatically:

#### Test Suite (ci.yml)
- Tests run on Python 3.11, 3.12, and 3.13
- Code coverage calculated and reported
- Coverage must be ≥80%

#### Code Quality (ci.yml)
- Code formatting checked with `black`
- Import sorting checked with `isort`
- Linting with `flake8`
- Type checking with `mypy`

#### Security Scans (ci.yml & security-scan.yml)
- Python code scanned with Bandit
- Dependencies checked with pip-audit and safety
- Secrets scanning with Gitleaks and TruffleHog
- SAST with Semgrep
- Container scanning with Trivy

#### Integration Tests (integration.yml)
- Runs on PRs to main
- Daily scheduled runs
- Tests broker integrations

### Triggering Performance Tests

To run performance tests on your PR:

1. Add the `performance` label to your PR
2. Performance tests will run automatically
3. Results uploaded as artifacts

### CI Skip for Documentation

For documentation-only changes:

```bash
git commit -m "docs: update README [skip ci]"
```

### Viewing CI Results

1. Go to your PR on GitHub
2. Scroll to the "Checks" section
3. Click on any check to view detailed logs
4. Download artifacts for coverage reports, logs, etc.

## Getting Help

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: Search existing issues or create a new one
- **Discussions**: Use GitHub Discussions for questions

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Assume good intentions

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Additional Resources

- [CI Gating Setup Guide](docs/CI_GATING_SETUP.md)
- [Branch Protection Rules](.github/branch-protection.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [Security Policy](SECURITY.md)

Thank you for contributing to Autotrader! 🚀
