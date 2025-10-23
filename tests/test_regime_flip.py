"""
Unit tests for RegimeFlip module

Tests the regime flip decision logic with various market conditions.
"""

import pytest
from src.risk.regime_flip import RegimeFlip, RegimeInputs


def test_regime_allows_when_multiple_confirmations():
    """Test that regime allows trading when multiple confirmations are present"""
    rf = RegimeFlip(vix_low=20, breadth_min=0.55, volume_thrust_min=1.2, require_confirmations=2)
    x = RegimeInputs(
        vix=18.5, vix_ma3=19.0,
        breadth_above_20dma=0.60,
        adv_volume=1_200_000, dec_volume=800_000,
        spy_ma_fast=405.0, spy_ma_slow=400.0
    )
    d = rf.decide(x)
    assert d.allow_long is True
    assert "vix_ok" in d.reason


def test_regime_blocks_when_no_confirmations():
    """Test that regime blocks trading when no confirmations are present"""
    rf = RegimeFlip(require_confirmations=2)
    x = RegimeInputs(vix=25.0, vix_ma3=24.0)  # elevated VIX, no breadth/volume/trend
    d = rf.decide(x)
    assert d.allow_long is False
    assert d.reason == "no confirmations"


def test_regime_allows_on_breadth_and_trend():
    """Test that regime allows trading with breadth and trend confirmations"""
    rf = RegimeFlip(require_confirmations=2)
    x = RegimeInputs(vix=22.0, breadth_above_20dma=0.60, spy_ret_5d=0.012)
    d = rf.decide(x)
    assert d.allow_long is True
    assert ("breadth_ok" in d.reason) or ("trend_ok" in d.reason)
