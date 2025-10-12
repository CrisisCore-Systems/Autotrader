#!/usr/bin/env python3
"""Compatibility shim for the relocated prompt contracts validator."""

from scripts.validation.validate_prompt_contracts import main


if __name__ == "__main__":
    raise SystemExit(main())
