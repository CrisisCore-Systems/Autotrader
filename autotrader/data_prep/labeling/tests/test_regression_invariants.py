"""
Regression labeler invariant tests.

Properties that MUST hold:
- Labels are finite (no NaN/Inf)
- Clipping percentage respected
- Cost adjustment reduces mean return
- Labels not all zero
"""

import numpy as np
import pandas as pd
import pytest

from autotrader.data_prep.labeling import RegressionLabeler, CostModel, LabelFactory


class TestRegressionInvariants:
    """Core invariants that regression labels must satisfy."""
    
    def test_labels_are_finite(self, bars_1s_2h):
        """All labels must be finite (no NaN or Inf)."""
        out = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        labels = out["label"]
        
        assert np.isfinite(labels).all(), "Regression labels contain non-finite values"
    
    def test_labels_not_all_zero(self, bars_1s_2h):
        """Labels should not all be zero (would indicate bug)."""
        out = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        labels = out["label"]
        
        assert not np.allclose(labels, 0.0), "All labels are zero"
        assert labels.std() > 0, "Labels have zero variance"
    
    def test_labels_have_reasonable_range(self, bars_1s_2h):
        """
        Labels should be in reasonable range for FX (not ±1000 bps).
        
        After clipping and cost adjustment, expect ±50 bps typical range.
        """
        out = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        labels = out["label"]
        
        assert labels.min() > -500, f"Labels too negative: {labels.min():.2f} bps"
        assert labels.max() < 500, f"Labels too positive: {labels.max():.2f} bps"
    
    def test_raw_returns_exist_and_differ_from_labels(self, bars_5m_1d):
        """
        Raw returns should exist and differ from final labels.
        
        Cost adjustment and clipping should change values.
        """
        out = LabelFactory.create(bars_5m_1d, method="regression", horizon_seconds=60)
        
        assert "raw_return_bps" in out.columns, "Missing raw_return_bps"
        
        # Raw and final labels should differ (due to costs and clipping)
        assert not np.allclose(out["raw_return_bps"], out["label"]), "Labels unchanged from raw returns"


class TestClippingInvariants:
    """Clipping must respect percentile bounds."""
    
    def test_clipping_percentage_respected(self, bars_1s_2h):
        """
        Clipped data should remove ~clip_percentile% at each tail.
        
        E.g., (5, 95) percentiles → ~5% clipped at lower, ~5% at upper.
        """
        clip_pct_lower = 5.0
        clip_pct_upper = 95.0
        
        out = LabelFactory.create(
            bars_1s_2h,
            method="regression",
            horizon_seconds=60,
            clip_percentiles=(clip_pct_lower, clip_pct_upper),
        )
        
        # Check that clipping happened
        raw_returns = out["raw_return_bps"]
        clipped_returns = out["clipped_return_bps"]
        
        # Some values should be clipped
        assert (raw_returns != clipped_returns).any(), "No clipping occurred"
        
        # Clipped values should be within bounds
        clip_lower = out["clip_lower_bps"].iloc[0]
        clip_upper = out["clip_upper_bps"].iloc[0]
        
        assert (clipped_returns >= clip_lower).all(), "Clipped values below lower bound"
        assert (clipped_returns <= clip_upper).all(), "Clipped values above upper bound"
    
    def test_clip_bounds_are_ordered(self, bars_5m_1d):
        """Clip lower bound must be < clip upper bound."""
        out = LabelFactory.create(bars_5m_1d, method="regression", horizon_seconds=60)
        
        clip_lower = out["clip_lower_bps"].iloc[0]
        clip_upper = out["clip_upper_bps"].iloc[0]
        
        assert clip_lower < clip_upper, f"Clip bounds misordered: {clip_lower} >= {clip_upper}"
    
    def test_tighter_clipping_removes_more_outliers(self, bars_1s_2h):
        """
        (10, 90) percentiles should clip more than (5, 95).
        """
        out_wide = LabelFactory.create(
            bars_1s_2h,
            method="regression",
            horizon_seconds=60,
            clip_percentiles=(5, 95),
        )
        
        out_tight = LabelFactory.create(
            bars_1s_2h,
            method="regression",
            horizon_seconds=60,
            clip_percentiles=(10, 90),
        )
        
        # Tighter bounds should be narrower
        wide_range = out_wide["clip_upper_bps"].iloc[0] - out_wide["clip_lower_bps"].iloc[0]
        tight_range = out_tight["clip_upper_bps"].iloc[0] - out_tight["clip_lower_bps"].iloc[0]
        
        assert tight_range < wide_range, "Tighter percentiles should have narrower range"
    
    def test_no_clipping_with_extreme_percentiles(self, bars_5m_1d):
        """
        (0, 100) percentiles should not clip anything.
        """
        out = LabelFactory.create(
            bars_5m_1d,
            method="regression",
            horizon_seconds=60,
            clip_percentiles=(0, 100),
        )
        
        # Raw and clipped should be identical
        assert np.allclose(
            out["raw_return_bps"],
            out["clipped_return_bps"],
            equal_nan=True
        ), "Clipping occurred with (0, 100) percentiles"


class TestCostAdjustmentInvariants:
    """Cost adjustment must reduce mean return."""
    
    def test_cost_adjustment_reduces_mean_return(self, bars_1s_2h):
        """
        Cost subtraction should reduce mean return (make it less positive).
        
        This is the core monotonicity property for cost-aware labeling.
        """
        labeler = RegressionLabeler(
            horizon_seconds=60,
            subtract_costs=True,
        )
        
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        raw_mean = stats["raw_return_statistics"]["mean"]
        final_mean = stats["label_statistics"]["mean"]
        
        # Final mean should be lower (more negative) due to costs
        assert final_mean <= raw_mean, f"Cost adjustment increased mean: {raw_mean:.2f} → {final_mean:.2f}"
    
    def test_higher_costs_reduce_mean_more(self, bars_1s_2h):
        """
        Monotonicity: Higher costs → lower mean return.
        """
        cost_low = CostModel(maker_fee=0.01, taker_fee=0.02, slippage_bps=0.3)
        cost_high = CostModel(maker_fee=0.05, taker_fee=0.10, slippage_bps=1.0)
        
        labeler_low = RegressionLabeler(cost_model=cost_low, horizon_seconds=60, subtract_costs=True)
        labeler_high = RegressionLabeler(cost_model=cost_high, horizon_seconds=60, subtract_costs=True)
        
        out_low = labeler_low.generate_labels(bars_1s_2h)
        out_high = labeler_high.generate_labels(bars_1s_2h)
        
        stats_low = labeler_low.get_label_statistics(out_low)
        stats_high = labeler_high.get_label_statistics(out_high)
        
        mean_low = stats_low["label_statistics"]["mean"]
        mean_high = stats_high["label_statistics"]["mean"]
        
        assert mean_high <= mean_low, f"Higher costs should reduce mean: {mean_low:.2f} → {mean_high:.2f}"
    
    def test_no_cost_subtraction_preserves_clipped_mean(self, bars_5m_1d):
        """
        subtract_costs=False should preserve clipped mean.
        """
        labeler = RegressionLabeler(horizon_seconds=60, subtract_costs=False)
        
        labeled_data = labeler.generate_labels(bars_5m_1d)
        
        # Labels should equal clipped returns (no cost adjustment)
        assert np.allclose(
            labeled_data["label"],
            labeled_data["clipped_return_bps"],
            equal_nan=True
        ), "Cost adjustment occurred when subtract_costs=False"
    
    def test_cost_impact_is_nonzero_when_subtracting(self, bars_1s_2h):
        """
        mean_cost_impact_bps should be nonzero when subtract_costs=True.
        """
        labeler = RegressionLabeler(horizon_seconds=60, subtract_costs=True)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        cost_impact = stats["cost_adjustment"]["mean_cost_impact_bps"]
        
        # Should be nonzero (costs are being subtracted)
        assert abs(cost_impact) > 1e-6, "Cost impact is zero when subtract_costs=True"


class TestMicropriceInvariants:
    """Microprice should differ from close price."""
    
    def test_microprice_differs_from_close(self, bars_5m_1d):
        """
        Microprice-based returns should differ from close-based returns.
        
        Microprice = volume-weighted fair value, not simple close.
        """
        labeler_micro = RegressionLabeler(horizon_seconds=60, use_microprice=True)
        labeler_close = RegressionLabeler(horizon_seconds=60, use_microprice=False)
        
        out_micro = labeler_micro.generate_labels(bars_5m_1d)
        out_close = labeler_close.generate_labels(bars_5m_1d)
        
        # Returns should differ (microprice != close)
        assert not np.allclose(
            out_micro["raw_return_bps"],
            out_close["raw_return_bps"],
            equal_nan=True
        ), "Microprice returns identical to close returns"


class TestEdgeCases:
    """Robustness to edge cases."""
    
    def test_handles_nans_gracefully(self, tiny_bars_nan):
        """Should handle NaNs without crashing."""
        out = LabelFactory.create(tiny_bars_nan, method="regression", horizon_seconds=30)
        
        assert len(out) == len(tiny_bars_nan), "Output length mismatch"
        # Should still produce some valid labels
        assert np.isfinite(out["label"]).sum() > 0, "All labels are NaN"
    
    def test_handles_zero_volumes_gracefully(self, tiny_bars_nan):
        """Should handle zero volumes without division errors."""
        out = LabelFactory.create(tiny_bars_nan, method="regression", horizon_seconds=30)
        
        # Should not crash with divide-by-zero
        assert len(out) > 0
    
    def test_constant_price_produces_zero_returns(self):
        """
        Constant price should produce zero returns.
        """
        n = 100
        ts = pd.date_range("2025-01-01 09:30:00", periods=n, freq="1s")
        
        df = pd.DataFrame({
            "timestamp": ts,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1000.0,
            "bid": 99.99,
            "ask": 100.01,
            "bid_vol": 100.0,
            "ask_vol": 100.0,
        })
        
        out = LabelFactory.create(df, method="regression", horizon_seconds=10)
        
        # Returns should be near zero
        assert abs(out["label"].mean()) < 1.0, "Constant price produced nonzero returns"


class TestStatisticalProperties:
    """Statistical properties of label distribution."""
    
    def test_label_std_is_positive(self, bars_1s_2h):
        """Labels should have positive standard deviation."""
        out = LabelFactory.create(bars_1s_2h, method="regression", horizon_seconds=60)
        
        assert out["label"].std() > 0, "Labels have zero variance"
    
    def test_sharpe_ratio_is_finite(self, bars_5m_1d):
        """Sharpe ratio should be finite."""
        labeler = RegressionLabeler(horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_5m_1d)
        stats = labeler.get_label_statistics(labeled_data)
        
        sharpe = stats["performance"]["sharpe_ratio_annual"]
        
        assert np.isfinite(sharpe), f"Sharpe ratio is non-finite: {sharpe}"
    
    def test_information_ratio_is_finite(self, bars_5m_1d):
        """Information ratio should be finite."""
        labeler = RegressionLabeler(horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_5m_1d)
        stats = labeler.get_label_statistics(labeled_data)
        
        ir = stats["performance"]["information_ratio"]
        
        assert np.isfinite(ir), f"Information ratio is non-finite: {ir}"
    
    def test_direction_percentages_sum_to_100(self, bars_1s_2h):
        """Direction distribution should sum to 100%."""
        labeler = RegressionLabeler(horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        pos_pct = stats["direction_distribution"]["positive_pct"]
        neg_pct = stats["direction_distribution"]["negative_pct"]
        zero_pct = stats["direction_distribution"]["zero_pct"]
        
        total_pct = pos_pct + neg_pct + zero_pct
        assert abs(total_pct - 100.0) < 1e-6, f"Direction percentages sum to {total_pct:.2f}%, not 100%"
