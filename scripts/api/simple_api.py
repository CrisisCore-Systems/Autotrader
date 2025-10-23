"""Compatibility shim for the legacy ``simple_api`` module.

The FastAPI application now lives under ``src.api.main``. This module exists to
preserve backwards compatibility for scripts and tools that still import
``simple_api``. It simply re-exports the shared ``app`` instance.
"""

from src.api.main import app  # noqa: F401

__all__ = ["app"]
