#!/usr/bin/env python3
"""Compatibility shim for the relocated manpage generator."""

from scripts.docs.gen_manpage import main


if __name__ == "__main__":
    raise SystemExit(main())
