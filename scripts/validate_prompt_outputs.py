#!/usr/bin/env python3
"""Compatibility shim for the relocated prompt outputs validator."""

from scripts.validation.validate_prompt_outputs import main


if __name__ == "__main__":
    raise SystemExit(main())
