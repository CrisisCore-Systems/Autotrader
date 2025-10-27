"""
Factory contract tests: Schema validation and key stability.

Ensures the LabelFactory API never drifts:
- Required columns enforced
- Output schema stable
- Statistics keys locked
"""

import pandas as pd
import pytest
import numpy as np

from autotrader.data_prep.labeling import LabelFactory
from .conftest import REQUIRED_INPUT_COLS


class TestFactorySchemaContracts:
    """Enforce strict schema contracts for factory inputs/outputs."""
    
    def test_factory_rejects_missing_timestamp(self, bars_1s_2h):
        """Missing timestamp column should raise error."""
        df = bars_1s_2h.drop(columns=["timestamp"])
        with pytest.raises((KeyError, ValueError)):
            LabelFactory.create(df, method="classification", horizon_seconds=60)
    
    def test_factory_rejects_missing_bid_ask(self, bars_1s_2h):
        """Missing bid/ask columns should raise error."""
        df = bars_1s_2h.drop(columns=["bid"])
        with pytest.raises((KeyError, ValueError)):
            LabelFactory.create(df, method="classification", horizon_seconds=60)
        
        df = bars_1s_2h.drop(columns=["ask"])
        with pytest.raises((KeyError, ValueError)):
            LabelFactory.create(df, method="classification", horizon_seconds=60)
    
    def test_factory_rejects_missing_volumes(self, bars_1s_2h):
        """Missing bid_vol/ask_vol columns should raise error."""
        df = bars_1s_2h.drop(columns=["bid_vol"])
        with pytest.raises((KeyError, ValueError)):
            LabelFactory.create(df, method="classification", horizon_seconds=60)
        
        df = bars_1s_2h.drop(columns=["ask_vol"])
        with pytest.raises((KeyError, ValueError)):
            LabelFactory.create(df, method="classification", horizon_seconds=60)
    
    def test_factory_accepts_expected_columns_classification(self, bars_1s_2h):
        """Factory should accept complete input schema for classification."""
        out = LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=60)
        assert len(out) == len(bars_1s_2h), "Output length mismatch"
        assert "label" in out.columns, "Missing label column"
    
    def test_factory_accepts_expected_columns_regression(self, bars_1s_2h):
        """Factory should accept complete input schema for regression."""
        out = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        assert len(out) == len(bars_1s_2h), "Output length mismatch"
        assert "label" in out.columns, "Missing label column"
    
    def test_factory_rejects_invalid_method(self, bars_1s_2h):
        """Invalid method parameter should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown labeling method"):
            LabelFactory.create(bars_1s_2h, method="invalid_method", horizon_seconds=60)


class TestOutputSchemaStability:
    """Lock output schema so downstream code doesn't break."""
    
    def test_classification_output_has_required_columns(self, bars_1s_2h):
        """Classification output must have these exact columns."""
        out = LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=60)
        
        required = {"label", "forward_return_bps", "profitable_threshold_bps", "is_profitable"}
        assert required.issubset(out.columns), f"Missing columns: {required - set(out.columns)}"
    
    def test_regression_output_has_required_columns(self, bars_1s_2h):
        """Regression output must have these exact columns."""
        out = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        
        required = {
            "label", "raw_return_bps", "clipped_return_bps",
            "cost_adjusted_return_bps", "clip_lower_bps", "clip_upper_bps"
        }
        assert required.issubset(out.columns), f"Missing columns: {required - set(out.columns)}"
    
    def test_output_length_matches_input(self, bars_5m_1d):
        """Output should have same length as input."""
        out_cls = LabelFactory.create(bars_5m_1d, method="classification", horizon_seconds=60)
        assert len(out_cls) == len(bars_5m_1d)
        
        out_reg = LabelFactory.create(bars_5m_1d, method="regression", horizon_seconds=60)
        assert len(out_reg) == len(bars_5m_1d)


class TestStatisticsKeysStability:
    """Lock statistics keys (caught your earlier mean_forward_return vs mean_return_bps)."""
    
    def test_classification_stats_keys_locked(self, bars_1s_2h):
        """Classification statistics must have these exact keys."""
        labeler = LabelFactory.get_labeler(method="classification", horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        # Top-level keys
        required_top = {
            "total_samples", "label_distribution", "return_statistics",
            "return_by_label", "performance", "cost_model", "horizon"
        }
        assert required_top.issubset(stats.keys()), f"Missing keys: {required_top - set(stats.keys())}"
        
        # Label distribution keys
        required_dist = {"buy_count", "sell_count", "hold_count", "buy_pct", "sell_pct", "hold_pct"}
        assert required_dist.issubset(stats["label_distribution"].keys())
        
        # Return statistics keys (THIS IS THE FIX FOR YOUR EARLIER BUG)
        required_return = {"mean_return_bps", "std_return_bps", "min_return_bps", "max_return_bps"}
        assert required_return.issubset(stats["return_statistics"].keys())
        
        # Performance keys
        if "performance" in stats:
            required_perf = {"buy_hit_rate", "sell_hit_rate", "overall_hit_rate"}
            assert required_perf.issubset(stats["performance"].keys())
    
    def test_regression_stats_keys_locked(self, bars_1s_2h):
        """Regression statistics must have these exact keys."""
        labeler = LabelFactory.get_labeler(method="regression", horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        # Top-level keys
        required_top = {
            "total_samples", "label_statistics", "raw_return_statistics",
            "clipping_impact", "cost_adjustment", "direction_distribution",
            "horizon", "performance"
        }
        assert required_top.issubset(stats.keys()), f"Missing keys: {required_top - set(stats.keys())}"
        
        # Label statistics keys
        required_label = {"mean", "std", "min", "max", "median", "q25", "q75"}
        assert required_label.issubset(stats["label_statistics"].keys())
        
        # Clipping impact keys
        required_clip = {
            "clip_lower_bps", "clip_upper_bps",
            "pct_clipped_lower", "pct_clipped_upper"
        }
        assert required_clip.issubset(stats["clipping_impact"].keys())
        
        # Cost adjustment keys (THIS IS THE KEY NAME FIX)
        required_cost = {"subtract_costs", "round_trip_cost_bps", "mean_cost_impact_bps"}
        assert required_cost.issubset(stats["cost_adjustment"].keys())
        
        # Performance keys
        required_perf = {"sharpe_ratio_annual", "information_ratio"}
        assert required_perf.issubset(stats["performance"].keys())


class TestParameterValidation:
    """Validate parameter constraints early."""
    
    def test_negative_horizon_rejected(self, bars_1s_2h):
        """Negative horizon should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=-60)
    
    def test_zero_horizon_rejected(self, bars_1s_2h):
        """Zero horizon should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=0)
    
    def test_invalid_clip_percentiles(self, bars_1s_2h):
        """Invalid clip percentiles should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            LabelFactory.create(
                bars_1s_2h,
                method="regression",
                horizon_seconds=60,
                clip_percentiles=(95, 5)  # Backwards!
            )


class TestDeterminism:
    """Ensure labeling is deterministic (no hidden randomness)."""
    
    def test_classification_deterministic(self, bars_1s_2h):
        """Two runs should produce identical labels."""
        out1 = LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=60)
        out2 = LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=60)
        
        pd.testing.assert_frame_equal(out1, out2)
    
    def test_regression_deterministic(self, bars_1s_2h):
        """Two runs should produce identical labels."""
        out1 = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        out2 = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        
        pd.testing.assert_frame_equal(out1, out2)
    
    def test_factory_get_labeler_deterministic(self, bars_5m_1d):
        """get_labeler() should produce identical results."""
        labeler1 = LabelFactory.get_labeler(method="classification", horizon_seconds=60)
        labeler2 = LabelFactory.get_labeler(method="classification", horizon_seconds=60)
        
        out1 = labeler1.generate_labels(bars_5m_1d)
        out2 = labeler2.generate_labels(bars_5m_1d)
        
        pd.testing.assert_frame_equal(out1, out2)
