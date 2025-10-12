#!/usr/bin/env python3
"""Compatibility shim for the relocated metrics docs generator."""

from scripts.docs.gen_metrics_docs import main


if __name__ == "__main__":
    raise SystemExit(main())
