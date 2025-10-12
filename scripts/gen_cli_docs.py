#!/usr/bin/env python3
"""Compatibility shim for the relocated CLI docs generator."""

from scripts.docs.gen_cli_docs import main


if __name__ == "__main__":
    raise SystemExit(main())
