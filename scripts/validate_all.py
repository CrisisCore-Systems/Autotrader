#!/usr/bin/env python3
"""Compatibility shim for the relocated validation runner."""

from scripts.validation.validate_all import main


if __name__ == "__main__":
    raise SystemExit(main())
