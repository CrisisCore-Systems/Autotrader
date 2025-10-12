#!/usr/bin/env python3
"""Compatibility shim for the relocated alert rules validator."""

from scripts.validation.validate_alert_rules import main


if __name__ == "__main__":
    raise SystemExit(main())

