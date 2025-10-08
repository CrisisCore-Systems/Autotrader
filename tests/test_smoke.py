"""
Smoke Tests - Basic validation that the test infrastructure works

Run with: pytest tests/test_smoke.py -v
"""

import pytest
from pathlib import Path
import sys


def test_python_version():
    """Test Python version is 3.13+"""
    assert sys.version_info >= (3, 13), f"Python 3.13+ required, got {sys.version_info}"


def test_src_directory_exists():
    """Test that src directory exists"""
    src_dir = Path(__file__).parent.parent / "src"
    assert src_dir.exists(), "src directory not found"
    assert src_dir.is_dir(), "src is not a directory"


def test_can_import_core_pipeline():
    """Test that we can import the main pipeline module"""
    try:
        from src.core.pipeline import HiddenGemScanner, TokenConfig
        assert HiddenGemScanner is not None
        assert TokenConfig is not None
    except ImportError as e:
        pytest.fail(f"Failed to import core pipeline: {e}")


def test_can_import_sentiment():
    """Test that we can import sentiment module"""
    try:
        from src.core.sentiment import SentimentAnalyzer
        assert SentimentAnalyzer is not None
    except ImportError as e:
        pytest.fail(f"Failed to import sentiment: {e}")


def test_can_import_tree():
    """Test that we can import tree module"""
    try:
        from src.core.tree import TreeNode
        assert TreeNode is not None
    except ImportError as e:
        pytest.fail(f"Failed to import tree: {e}")


def test_can_import_free_clients():
    """Test that we can import new FREE blockchain clients (Blockscout, EthereumRPC)"""
    try:
        from src.core.free_clients import BlockscoutClient, EthereumRPCClient
        assert BlockscoutClient is not None
        assert EthereumRPCClient is not None
    except ImportError as e:
        pytest.fail(f"Failed to import free clients: {e}")


def test_can_import_dexscreener():
    """Test that we can import DexscreenerClient for FREE liquidity data"""
    try:
        from src.core.orderflow_clients import DexscreenerClient
        assert DexscreenerClient is not None
    except ImportError as e:
        pytest.fail(f"Failed to import Dexscreener client: {e}")


def test_requirements_installed():
    """Test that key dependencies are installed"""
    required_packages = [
        "pytest",
        "fastapi",
        "pydantic",
        "requests",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    assert not missing, f"Missing required packages: {', '.join(missing)}"


def test_simple_math():
    """Simple test to verify pytest is working"""
    assert 1 + 1 == 2
    assert 2 * 3 == 6


@pytest.mark.parametrize("value,expected", [
    (1, True),
    (0, False),
    (-1, False),
    (100, True),
])
def test_positive_numbers(value, expected):
    """Test parametrized test functionality"""
    assert (value > 0) == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
