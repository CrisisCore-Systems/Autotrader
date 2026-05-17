#!/usr/bin/env python
"""CLI runner for the bounded IBKR paper trading harness v1."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ibkr_paper_harness_v1 import build_parser, run_harness


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run_harness(args))


if __name__ == "__main__":
    raise SystemExit(main())
