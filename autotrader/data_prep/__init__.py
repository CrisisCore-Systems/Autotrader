"""
Data preparation module for Phase 3.

This module provides:
- Data cleaning (timezone normalization, session filtering, quality checks)
- Bar construction (time, tick, volume, dollar, imbalance, run bars)
- Feature engineering (spread, depth, flow toxicity)
- Label integrity validation (lookahead detection)
"""

from autotrader.data_prep.cleaning import (
    TimezoneNormalizer,
    SessionFilter,
    DataQualityChecker,
)

__all__ = [
    "TimezoneNormalizer",
    "SessionFilter",
    "DataQualityChecker",
]
