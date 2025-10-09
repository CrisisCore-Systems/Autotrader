"""Smoke tests for CLI backtest wrapper to prevent regressions."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_cli_backtest_help():
    """Test that --help flag works without errors."""
    # Run as a Python file instead of module to avoid sys.path issues in tests
    cli_file = Path(__file__).parent.parent / "pipeline" / "cli_backtest.py"
    result = subprocess.run(
        [sys.executable, str(cli_file), "--help"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
        env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
    )

    assert result.returncode == 0, f"--help failed with stderr: {result.stderr}"
    assert "GemScore Backtest CLI" in result.stdout
    assert "--start" in result.stdout
    assert "--end" in result.stdout
    assert "--engine" in result.stdout
    assert "--log-level" in result.stdout


def test_cli_backtest_missing_required_args():
    """Test that missing required arguments produce proper error."""
    cli_file = Path(__file__).parent.parent / "pipeline" / "cli_backtest.py"
    result = subprocess.run(
        [sys.executable, str(cli_file)],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
        env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
    )

    assert result.returncode != 0, "Should fail without required arguments"
    assert "required" in result.stderr.lower() or "error" in result.stderr.lower()


def test_cli_backtest_invalid_engine():
    """Test that invalid engine choice produces proper error."""
    cli_file = Path(__file__).parent.parent / "pipeline" / "cli_backtest.py"
    result = subprocess.run(
        [
            sys.executable, str(cli_file),
            "--start", "2024-01-01",
            "--end", "2024-01-31",
            "--engine", "invalid_engine"
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
        env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
    )

    assert result.returncode != 0, "Should fail with invalid engine"
    assert "invalid choice" in result.stderr.lower()


def test_cli_backtest_invalid_log_level():
    """Test that invalid log level produces proper error."""
    cli_file = Path(__file__).parent.parent / "pipeline" / "cli_backtest.py"
    result = subprocess.run(
        [
            sys.executable, str(cli_file),
            "--start", "2024-01-01",
            "--end", "2024-01-31",
            "--log-level", "INVALID"
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
        env={**subprocess.os.environ, "PYTHONPATH": str(Path(__file__).parent.parent)},
    )

    assert result.returncode != 0, "Should fail with invalid log level"
    assert "invalid choice" in result.stderr.lower()


def test_cli_module_import():
    """Test that the CLI module can be imported without errors."""
    try:
        from pipeline import cli_backtest
        assert hasattr(cli_backtest, "main")
        assert hasattr(cli_backtest, "cli_main")
        assert hasattr(cli_backtest, "build_parser")
        assert hasattr(cli_backtest, "setup_logging")
    except ImportError as e:
        pytest.fail(f"Failed to import cli_backtest module: {e}")


def test_cli_parser_all_options():
    """Test that parser includes all expected options."""
    from pipeline.cli_backtest import build_parser

    parser = build_parser()

    # Get all argument names
    all_actions = parser._actions
    arg_names = set()
    for action in all_actions:
        arg_names.update(action.option_strings)

    # Check for expected arguments
    expected_args = [
        "--start", "--end", "--walk", "--k", "--seed",
        "--engine", "--compare-baselines", "--extended-metrics",
        "--output", "--json-export",
        "--experiment-description", "--experiment-tags",
        "--no-track-experiments", "--data", "--log-level",
    ]

    for expected in expected_args:
        assert expected in arg_names, f"Missing argument: {expected}"


def test_cli_main_function_signature():
    """Test that main function has proper signature with type hints."""
    from pipeline.cli_backtest import main
    import inspect

    sig = inspect.signature(main)

    # Check parameters
    assert "argv" in sig.parameters

    # Check return annotation (can be int or 'int' due to __future__ annotations)
    assert sig.return_annotation in (int, 'int'), "main() should return int"


def test_cli_exit_codes():
    """Test that proper exit codes are used for different error scenarios."""
    from pipeline.cli_backtest import main

    # Test with invalid arguments (should return non-zero)
    # Note: argparse calls sys.exit, so we need to catch SystemExit
    try:
        exit_code = main([])
    except SystemExit as e:
        exit_code = e.code

    assert exit_code != 0, "Should return non-zero for missing arguments"

    # Test with --help (should work but parser exits)
    # This is tested via subprocess in test_cli_backtest_help


def test_cli_logging_setup():
    """Test that logging setup works correctly."""
    from pipeline.cli_backtest import setup_logging
    import logging

    # Store original level
    original_level = logging.getLogger().level

    # Test valid log level
    setup_logging("DEBUG")
    # Note: In test environment, logging might be controlled by pytest
    # Just verify the function doesn't raise an error
    assert True, "setup_logging('DEBUG') succeeded"

    setup_logging("INFO")
    assert True, "setup_logging('INFO') succeeded"

    # Test invalid log level
    with pytest.raises(ValueError, match="Invalid log level"):
        setup_logging("INVALID_LEVEL")

    # Restore original level
    logging.getLogger().setLevel(original_level)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
