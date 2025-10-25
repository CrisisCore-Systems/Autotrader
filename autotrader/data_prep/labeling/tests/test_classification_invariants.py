"""
Classification labeler invariant tests.

Properties that MUST hold:
- Labels are {-1, 0, +1} only
- Cost-aware: 25-75% HOLD rate on random data
- Hit rate > 50% on trending data
- Determinism across runs
"""

import numpy as np
import pandas as pd
import pytest

from autotrader.data_prep.labeling import ClassificationLabeler, CostModel, LabelFactory


class TestClassificationInvariants:
    """Core invariants that classification labels must satisfy."""
    
    def test_labels_are_ternary(self, bars_1s_2h):
        """Labels must be exactly {-1, 0, +1}."""
        out = LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=60)
        labels = out["label"].dropna()
        
        unique_labels = set(labels.unique())
        assert unique_labels.issubset({-1, 0, 1}), f"Invalid labels found: {unique_labels}"
    
    def test_hold_rate_reasonable_on_random_data(self, bars_1s_2h):
        """
        Cost-aware labeling should produce 25-75% HOLD on random walk.
        
        Random data has no edge, so most signals shouldn't exceed cost threshold.
        """
        out = LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=60)
        labels = out["label"].dropna()
        
        hold_frac = (labels == 0).mean()
        assert 0.25 <= hold_frac <= 0.75, f"HOLD rate {hold_frac:.1%} outside expected range"
    
    def test_buy_sell_balance_on_random_data(self, bars_1s_2h):
        """
        BUY and SELL counts should be roughly balanced on random walk.
        
        No directional bias in random data.
        """
        out = LabelFactory.create(bars_1s_2h, method="classification", horizon_seconds=60)
        labels = out["label"].dropna()
        
        buy_count = (labels == 1).sum()
        sell_count = (labels == -1).sum()
        
        # Allow 60/40 imbalance but not more
        if buy_count + sell_count > 0:
            buy_pct = buy_count / (buy_count + sell_count)
            assert 0.4 <= buy_pct <= 0.6, f"BUY/SELL imbalance: {buy_pct:.1%} BUY"
    
    def test_more_buys_on_trending_data(self, trending_bars):
        """
        Strong uptrend should produce more BUY than SELL labels.
        """
        out = LabelFactory.create(trending_bars, method="classification", horizon_seconds=10)
        labels = out["label"].dropna()
        
        buy_count = (labels == 1).sum()
        sell_count = (labels == -1).sum()
        
        assert buy_count > sell_count, "Uptrend should have more BUY signals"
    
    def test_labels_match_forward_returns(self, bars_5m_1d):
        """
        BUY labels should have positive forward returns on average.
        SELL labels should have negative forward returns on average.
        """
        out = LabelFactory.create(bars_5m_1d, method="classification", horizon_seconds=60)
        
        buy_mask = out["label"] == 1
        sell_mask = out["label"] == -1
        
        if buy_mask.sum() > 0:
            buy_returns = out.loc[buy_mask, "forward_return_bps"].mean()
            assert buy_returns > 0, f"BUY labels have negative mean return: {buy_returns:.2f} bps"
        
        if sell_mask.sum() > 0:
            sell_returns = out.loc[sell_mask, "forward_return_bps"].mean()
            assert sell_returns < 0, f"SELL labels have positive mean return: {sell_returns:.2f} bps"


class TestCostAwareThresholds:
    """Test cost-aware threshold logic."""
    
    def test_profitable_threshold_scales_with_costs(self):
        """Higher costs → higher profitable threshold."""
        cost_low = CostModel(maker_fee=0.01, taker_fee=0.02, slippage_bps=0.3)
        cost_high = CostModel(maker_fee=0.05, taker_fee=0.10, slippage_bps=1.0)
        
        threshold_low = cost_low.profitable_threshold_bps(is_maker=True)
        threshold_high = cost_high.profitable_threshold_bps(is_maker=True)
        
        assert threshold_high > threshold_low, "Higher costs should increase threshold"
    
    def test_higher_costs_produce_more_holds(self, bars_1s_2h):
        """
        Monotonicity test: ↑costs ⇒ ↑HOLD rate.
        
        Core invariant for cost-aware labeling.
        """
        cost_low = CostModel(maker_fee=0.01, taker_fee=0.02, slippage_bps=0.3, min_profit_bps=0.5)
        cost_high = CostModel(maker_fee=0.05, taker_fee=0.10, slippage_bps=1.0, min_profit_bps=2.0)
        
        labeler_low = ClassificationLabeler(cost_model=cost_low, horizon_seconds=60)
        labeler_high = ClassificationLabeler(cost_model=cost_high, horizon_seconds=60)
        
        out_low = labeler_low.generate_labels(bars_1s_2h)
        out_high = labeler_high.generate_labels(bars_1s_2h)
        
        hold_low = (out_low["label"] == 0).mean()
        hold_high = (out_high["label"] == 0).mean()
        
        assert hold_high >= hold_low, f"Higher costs should increase HOLD rate: {hold_low:.1%} → {hold_high:.1%}"
    
    def test_is_profitable_matches_label(self, bars_5m_1d):
        """is_profitable should be True iff label != 0."""
        out = LabelFactory.create(bars_5m_1d, method="classification", horizon_seconds=60)
        
        assert ((out["label"] != 0) == out["is_profitable"]).all(), "is_profitable mismatch"


class TestHitRateInvariants:
    """Hit rate must be > 50% on predictable data."""
    
    def test_hit_rate_above_50_on_trending_data(self, trending_bars):
        """
        Strong trend should produce >50% hit rate (better than random).
        """
        labeler = ClassificationLabeler(horizon_seconds=10)
        labeled_data = labeler.generate_labels(trending_bars)
        stats = labeler.get_label_statistics(labeled_data)
        
        if "performance" in stats and "overall_hit_rate" in stats["performance"]:
            hit_rate = stats["performance"]["overall_hit_rate"]
            assert hit_rate > 50, f"Hit rate {hit_rate:.1f}% should exceed 50% on trending data"
    
    def test_hit_rate_close_to_50_on_random_data(self, bars_1s_2h):
        """
        Random data should produce ~50% hit rate (no edge).
        
        Allow 45-55% range for noise.
        """
        labeler = ClassificationLabeler(horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        if "performance" in stats and "overall_hit_rate" in stats["performance"]:
            hit_rate = stats["performance"]["overall_hit_rate"]
            # Random data should be close to 50%
            assert 45 <= hit_rate <= 55, f"Hit rate {hit_rate:.1f}% too far from 50% on random data"


class TestEdgeCases:
    """Robustness to edge cases and bad data."""
    
    def test_handles_nans_gracefully(self, tiny_bars_nan):
        """Should handle NaNs without crashing."""
        out = LabelFactory.create(tiny_bars_nan, method="classification", horizon_seconds=30)
        
        assert len(out) == len(tiny_bars_nan), "Output length mismatch"
        # Should still produce some valid labels
        assert out["label"].notna().sum() > 0, "All labels are NaN"
    
    def test_handles_zero_volumes_gracefully(self, tiny_bars_nan):
        """Should handle zero volumes without division errors."""
        out = LabelFactory.create(tiny_bars_nan, method="classification", horizon_seconds=30)
        
        # Should not crash
        assert len(out) > 0
    
    def test_short_horizon_produces_labels(self, bars_5m_1d):
        """Very short horizon (5s) should still work."""
        out = LabelFactory.create(bars_5m_1d, method="classification", horizon_seconds=5)
        
        assert out["label"].notna().sum() > 0, "No labels produced for short horizon"
    
    def test_long_horizon_produces_labels(self, bars_5m_1d):
        """Very long horizon (5m) should still work."""
        out = LabelFactory.create(bars_5m_1d, method="classification", horizon_seconds=300)
        
        assert out["label"].notna().sum() > 0, "No labels produced for long horizon"


class TestStatisticalProperties:
    """Statistical properties of label distribution."""
    
    def test_label_counts_sum_to_total(self, bars_1s_2h):
        """Label distribution counts should sum to total samples."""
        labeler = ClassificationLabeler(horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        buy_count = stats["label_distribution"]["buy_count"]
        sell_count = stats["label_distribution"]["sell_count"]
        hold_count = stats["label_distribution"]["hold_count"]
        total = stats["total_samples"]
        
        assert buy_count + sell_count + hold_count == total, "Label counts don't sum to total"
    
    def test_label_percentages_sum_to_100(self, bars_1s_2h):
        """Label distribution percentages should sum to ~100%."""
        labeler = ClassificationLabeler(horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        stats = labeler.get_label_statistics(labeled_data)
        
        buy_pct = stats["label_distribution"]["buy_pct"]
        sell_pct = stats["label_distribution"]["sell_pct"]
        hold_pct = stats["label_distribution"]["hold_pct"]
        
        total_pct = buy_pct + sell_pct + hold_pct
        assert abs(total_pct - 100.0) < 1e-6, f"Percentages sum to {total_pct:.2f}%, not 100%"
