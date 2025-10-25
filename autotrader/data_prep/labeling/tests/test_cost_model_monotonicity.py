"""
Cost model monotonicity tests.

Core invariant: ↑costs ⇒ ↓profit (and more HOLDs for classification).

These tests ensure cost model behaves correctly across the pipeline.
"""

import numpy as np
import pytest

from autotrader.data_prep.labeling import CostModel, ClassificationLabeler, RegressionLabeler, LabelFactory


class TestCostModelMonotonicity:
    """Core monotonicity properties of cost model."""
    
    def test_higher_maker_fee_increases_round_trip_cost(self):
        """Higher maker fee → higher round-trip cost."""
        cost_low = CostModel(maker_fee=0.01, taker_fee=0.02)
        cost_high = CostModel(maker_fee=0.05, taker_fee=0.02)
        
        rt_low = cost_low.round_trip_cost_bps(is_maker=True)
        rt_high = cost_high.round_trip_cost_bps(is_maker=True)
        
        assert rt_high > rt_low, f"Higher maker fee should increase cost: {rt_low} → {rt_high}"
    
    def test_higher_taker_fee_increases_round_trip_cost(self):
        """Higher taker fee → higher round-trip cost."""
        cost_low = CostModel(maker_fee=0.02, taker_fee=0.02)
        cost_high = CostModel(maker_fee=0.02, taker_fee=0.10)
        
        rt_low = cost_low.round_trip_cost_bps(is_maker=False)
        rt_high = cost_high.round_trip_cost_bps(is_maker=False)
        
        assert rt_high > rt_low, f"Higher taker fee should increase cost: {rt_low} → {rt_high}"
    
    def test_higher_slippage_increases_round_trip_cost(self):
        """Higher slippage → higher round-trip cost."""
        cost_low = CostModel(slippage_bps=0.3)
        cost_high = CostModel(slippage_bps=2.0)
        
        rt_low = cost_low.round_trip_cost_bps(is_maker=True)
        rt_high = cost_high.round_trip_cost_bps(is_maker=True)
        
        assert rt_high > rt_low, f"Higher slippage should increase cost: {rt_low} → {rt_high}"
    
    def test_higher_spread_cost_increases_round_trip_cost(self):
        """Higher spread cost → higher round-trip cost."""
        cost_low = CostModel(spread_cost=0.3)
        cost_high = CostModel(spread_cost=1.0)
        
        rt_low = cost_low.round_trip_cost_bps(is_maker=True)
        rt_high = cost_high.round_trip_cost_bps(is_maker=True)
        
        assert rt_high > rt_low, f"Higher spread cost should increase cost: {rt_low} → {rt_high}"
    
    def test_higher_min_profit_increases_threshold(self):
        """Higher min profit → higher profitable threshold."""
        cost_low = CostModel(min_profit_bps=0.5)
        cost_high = CostModel(min_profit_bps=2.0)
        
        thresh_low = cost_low.profitable_threshold_bps(is_maker=True)
        thresh_high = cost_high.profitable_threshold_bps(is_maker=True)
        
        assert thresh_high > thresh_low, f"Higher min profit should increase threshold: {thresh_low} → {thresh_high}"
    
    def test_taker_fees_higher_than_maker(self):
        """Taker round-trip cost should be higher than maker."""
        cost_model = CostModel(maker_fee=0.02, taker_fee=0.04)
        
        maker_cost = cost_model.round_trip_cost_bps(is_maker=True)
        taker_cost = cost_model.round_trip_cost_bps(is_maker=False)
        
        assert taker_cost > maker_cost, f"Taker cost should exceed maker: {maker_cost} vs {taker_cost}"


class TestCostModelValidation:
    """Cost model parameters must be non-negative."""
    
    def test_negative_maker_fee_rejected(self):
        """Negative maker fee should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            CostModel(maker_fee=-0.01)
    
    def test_negative_taker_fee_rejected(self):
        """Negative taker fee should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            CostModel(taker_fee=-0.02)
    
    def test_negative_slippage_rejected(self):
        """Negative slippage should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            CostModel(slippage_bps=-0.5)
    
    def test_negative_spread_cost_rejected(self):
        """Negative spread cost should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            CostModel(spread_cost=-0.5)
    
    def test_negative_min_profit_rejected(self):
        """Negative min profit should raise error."""
        with pytest.raises((ValueError, AssertionError)):
            CostModel(min_profit_bps=-1.0)


class TestClassificationCostMonotonicity:
    """Higher costs → more HOLD labels in classification."""
    
    def test_higher_costs_increase_hold_rate(self, bars_1s_2h):
        """
        Core monotonicity: ↑costs ⇒ ↑HOLD rate.
        
        This is THE fundamental invariant for cost-aware classification.
        """
        cost_low = CostModel(
            maker_fee=0.01,
            taker_fee=0.02,
            slippage_bps=0.3,
            spread_cost=0.3,
            min_profit_bps=0.5,
        )
        
        cost_high = CostModel(
            maker_fee=0.05,
            taker_fee=0.10,
            slippage_bps=1.0,
            spread_cost=1.0,
            min_profit_bps=2.0,
        )
        
        labeler_low = ClassificationLabeler(cost_model=cost_low, horizon_seconds=60)
        labeler_high = ClassificationLabeler(cost_model=cost_high, horizon_seconds=60)
        
        out_low = labeler_low.generate_labels(bars_1s_2h)
        out_high = labeler_high.generate_labels(bars_1s_2h)
        
        hold_low = (out_low["label"] == 0).mean()
        hold_high = (out_high["label"] == 0).mean()
        
        assert hold_high >= hold_low, (
            f"Higher costs should increase HOLD rate: "
            f"{hold_low:.1%} → {hold_high:.1%}"
        )
    
    def test_higher_costs_reduce_tradeable_signals(self, bars_5m_1d):
        """Higher costs → fewer tradeable signals."""
        cost_low = CostModel(maker_fee=0.01, min_profit_bps=0.5)
        cost_high = CostModel(maker_fee=0.05, min_profit_bps=2.0)
        
        labeler_low = ClassificationLabeler(cost_model=cost_low, horizon_seconds=60)
        labeler_high = ClassificationLabeler(cost_model=cost_high, horizon_seconds=60)
        
        out_low = labeler_low.generate_labels(bars_5m_1d)
        out_high = labeler_high.generate_labels(bars_5m_1d)
        
        tradeable_low = (out_low["label"] != 0).sum()
        tradeable_high = (out_high["label"] != 0).sum()
        
        assert tradeable_high <= tradeable_low, (
            f"Higher costs should reduce tradeable signals: "
            f"{tradeable_low} → {tradeable_high}"
        )
    
    def test_zero_cost_produces_minimal_holds(self, bars_5m_1d):
        """
        Zero costs should produce very few HOLD labels.
        
        With no transaction costs, almost all signals are profitable.
        """
        cost_zero = CostModel(
            maker_fee=0.0,
            taker_fee=0.0,
            slippage_bps=0.0,
            spread_cost=0.0,
            min_profit_bps=0.0,
        )
        
        labeler = ClassificationLabeler(cost_model=cost_zero, horizon_seconds=60)
        out = labeler.generate_labels(bars_5m_1d)
        
        hold_rate = (out["label"] == 0).mean()
        
        # With zero costs, HOLD rate should be very low
        assert hold_rate < 0.1, f"Zero-cost HOLD rate {hold_rate:.1%} unexpectedly high"


class TestRegressionCostMonotonicity:
    """Higher costs → lower mean return in regression."""
    
    def test_higher_costs_reduce_mean_return(self, bars_1s_2h):
        """
        Core monotonicity: ↑costs ⇒ ↓mean return.
        
        Fundamental invariant for cost-aware regression.
        """
        cost_low = CostModel(maker_fee=0.01, slippage_bps=0.3)
        cost_high = CostModel(maker_fee=0.05, slippage_bps=1.0)
        
        labeler_low = RegressionLabeler(
            cost_model=cost_low,
            horizon_seconds=60,
            subtract_costs=True,
        )
        
        labeler_high = RegressionLabeler(
            cost_model=cost_high,
            horizon_seconds=60,
            subtract_costs=True,
        )
        
        out_low = labeler_low.generate_labels(bars_1s_2h)
        out_high = labeler_high.generate_labels(bars_1s_2h)
        
        mean_low = out_low["label"].mean()
        mean_high = out_high["label"].mean()
        
        assert mean_high <= mean_low, (
            f"Higher costs should reduce mean return: "
            f"{mean_low:.2f} bps → {mean_high:.2f} bps"
        )
    
    def test_cost_impact_scales_with_cost_model(self, bars_5m_1d):
        """Cost impact should scale with cost model parameters."""
        cost_low = CostModel(maker_fee=0.01, slippage_bps=0.3)
        cost_high = CostModel(maker_fee=0.05, slippage_bps=1.0)
        
        labeler_low = RegressionLabeler(cost_model=cost_low, horizon_seconds=60, subtract_costs=True)
        labeler_high = RegressionLabeler(cost_model=cost_high, horizon_seconds=60, subtract_costs=True)
        
        out_low = labeler_low.generate_labels(bars_5m_1d)
        out_high = labeler_high.generate_labels(bars_5m_1d)
        
        stats_low = labeler_low.get_label_statistics(out_low)
        stats_high = labeler_high.get_label_statistics(out_high)
        
        impact_low = abs(stats_low["cost_adjustment"]["mean_cost_impact_bps"])
        impact_high = abs(stats_high["cost_adjustment"]["mean_cost_impact_bps"])
        
        assert impact_high >= impact_low, (
            f"Higher costs should have larger impact: "
            f"{impact_low:.2f} → {impact_high:.2f} bps"
        )
    
    def test_zero_cost_has_zero_impact(self, bars_5m_1d):
        """Zero costs with subtract_costs=True should have ~zero impact."""
        cost_zero = CostModel(
            maker_fee=0.0,
            taker_fee=0.0,
            slippage_bps=0.0,
            spread_cost=0.0,
            min_profit_bps=0.0,
        )
        
        labeler = RegressionLabeler(
            cost_model=cost_zero,
            horizon_seconds=60,
            subtract_costs=True,
        )
        
        out = labeler.generate_labels(bars_5m_1d)
        
        # Labels should approximately equal clipped returns (minimal cost impact)
        diff = abs(out["label"] - out["clipped_return_bps"]).mean()
        
        assert diff < 0.1, f"Zero-cost impact {diff:.2f} bps unexpectedly high"


class TestCostModelComposability:
    """Cost model should compose correctly across the pipeline."""
    
    def test_factory_respects_custom_cost_model(self, bars_5m_1d):
        """LabelFactory should use provided cost model."""
        cost_custom = CostModel(maker_fee=0.10, min_profit_bps=5.0)
        
        out = LabelFactory.create(
            bars_5m_1d,
            method="classification",
            horizon_seconds=60,
            cost_model=cost_custom,
            is_maker=True,
        )
        
        # Profitable threshold should reflect custom cost model
        threshold = out["profitable_threshold_bps"].iloc[0]
        
        # Should be approximately: 2 * (10 + 0.5 + 1) + 5 = 28 bps
        expected_threshold = cost_custom.profitable_threshold_bps(is_maker=True)
        
        assert abs(threshold - expected_threshold) < 0.1, (
            f"Threshold {threshold:.2f} doesn't match expected {expected_threshold:.2f}"
        )
    
    def test_labeler_uses_cost_model_consistently(self, bars_5m_1d):
        """Labeler should apply cost model consistently."""
        cost_model = CostModel(maker_fee=0.03, min_profit_bps=1.5)
        
        labeler = ClassificationLabeler(
            cost_model=cost_model,
            horizon_seconds=60,
            is_maker=True,
        )
        
        out = labeler.generate_labels(bars_5m_1d)
        stats = labeler.get_label_statistics(out)
        
        # Cost model in stats should match provided model
        stats_threshold = stats["cost_model"]["profitable_threshold_bps"]
        model_threshold = cost_model.profitable_threshold_bps(is_maker=True)
        
        assert abs(stats_threshold - model_threshold) < 1e-6, "Cost model mismatch in stats"
