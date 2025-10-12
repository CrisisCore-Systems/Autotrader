#!/usr/bin/env python3
"""
Test script for Phase 3 integration validation.
Tests the derivatives and on-chain flow analysis features.
"""

from src.core.pipeline import HiddenGemScanner, ScanResult

def test_phase3_integration():
    """Test Phase 3 features integration."""
    print("Testing Phase 3 integration...")

    # Test ScanResult includes Phase 3 fields
    result = ScanResult(
        token="TEST",
        market_snapshot=None,  # Mock
        narrative=None,  # Mock
        raw_features={},
        adjusted_features={},
        gem_score=None,  # Mock
        safety_report=None,  # Mock
        flag=False,
        debug={},
        artifact_payload={},
        artifact_markdown="",
        artifact_html="",
        derivatives_data={"test": "data"},
        onchain_alerts=[{"test": "alert"}],
        liquidation_spikes={"test": "spike"},
    )

    assert hasattr(result, "derivatives_data"), "ScanResult missing derivatives_data field"
    assert hasattr(result, "onchain_alerts"), "ScanResult missing onchain_alerts field"
    assert hasattr(result, "liquidation_spikes"), "ScanResult missing liquidation_spikes field"

    # Test that Phase 3 action methods exist in the scanner class
    scanner_methods = dir(HiddenGemScanner)
    expected_methods = ['_action_fetch_derivatives_data', '_action_scan_onchain_transfers']

    found_methods = [method for method in scanner_methods if method in expected_methods]

    assert len(found_methods) == len(expected_methods), (
        f"HiddenGemScanner missing expected Phase 3 methods. Found: {found_methods}, "
        f"Expected: {expected_methods}"
    )

