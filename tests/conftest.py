"""Test configuration helpers."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path


def pytest_configure() -> None:
    """Ensure the project root is importable when running pytest locally."""

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    warnings.filterwarnings(
        "ignore",
        message="Pyarrow will become a required dependency of pandas.*",
        category=DeprecationWarning,
    )
