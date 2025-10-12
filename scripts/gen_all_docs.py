#!/usr/bin/env python3
"""Compatibility shim for relocated script in `scripts/docs/`.

Prefer running `python scripts/docs/gen_all_docs.py` directly."""

from scripts.docs.gen_all_docs import main


if __name__ == "__main__":
    raise SystemExit(main())
