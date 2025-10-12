#!/usr/bin/env python3
"""Compatibility shim for the relocated artifact generator."""

from scripts.artifacts.generate_artifact import main


if __name__ == "__main__":
    raise SystemExit(main())
