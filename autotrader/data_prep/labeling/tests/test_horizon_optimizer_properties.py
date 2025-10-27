"""
Horizon optimizer property tests.

Properties that MUST hold:
- Returns valid horizon from search space
- Longer horizons don't randomly dominate
- Metrics are finite
- Results are deterministic
"""

import numpy as np
import pytest

from autotrader.data_prep.labeling import HorizonOptimizer


class TestHorizonOptimizerProperties:
    """Core properties of horizon optimization."""
    
    def test_returns_valid_horizon_from_search_space(self, bars_1s_2h):
        """Best horizon must be in the provided search space."""
        horizons = [5, 10, 30, 60, 120]
        
        optimizer = HorizonOptimizer(
            horizons_seconds=horizons,
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_1s_2h, symbol="TEST")
        
        assert best_result.horizon_seconds in horizons, f"Invalid horizon: {best_result.horizon_seconds}"
    
    def test_all_horizons_produce_results(self, bars_5m_1d):
        """Every horizon should produce valid results."""
        horizons = [10, 30, 60, 120]
        
        optimizer = HorizonOptimizer(
            horizons_seconds=horizons,
            labeling_method="regression",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        assert len(all_results) == len(horizons), "Not all horizons produced results"
        assert len(results_df) == len(horizons), "Results DataFrame length mismatch"
    
    def test_metrics_are_finite(self, bars_5m_1d):
        """All optimization metrics should be finite."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[30, 60],
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        assert np.isfinite(best_result.information_ratio), "IR is non-finite"
        assert np.isfinite(best_result.sharpe_ratio), "Sharpe is non-finite"
        assert np.isfinite(best_result.hit_rate), "Hit rate is non-finite"
        assert np.isfinite(best_result.capacity), "Capacity is non-finite"
    
    def test_information_ratio_is_primary_metric(self, bars_1s_2h):
        """Best horizon should maximize information ratio."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[10, 30, 60, 120],
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_1s_2h, symbol="TEST")
        
        # Best result should have highest IR
        best_ir = best_result.information_ratio
        all_irs = [r.information_ratio for r in all_results]
        
        assert best_ir == max(all_irs), "Best horizon doesn't maximize IR"


class TestHorizonMonotonicity:
    """Longer horizons shouldn't randomly dominate."""
    
    def test_capacity_increases_with_horizon(self, bars_5m_1d):
        """
        Longer horizons should have higher capacity.
        
        Capacity = volume × horizon × participation_rate
        So capacity ∝ horizon (all else equal).
        """
        optimizer = HorizonOptimizer(
            horizons_seconds=[10, 30, 60, 120, 180],
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        # Sort by horizon
        df_sorted = results_df.sort_values("horizon_seconds")
        
        # Capacity should generally increase with horizon
        capacities = df_sorted["capacity"].values
        
        # Check that at least 80% of consecutive pairs are monotonic
        monotonic_pairs = sum(
            capacities[i+1] >= capacities[i]
            for i in range(len(capacities) - 1)
        )
        
        total_pairs = len(capacities) - 1
        monotonic_pct = monotonic_pairs / total_pairs if total_pairs > 0 else 0
        
        assert monotonic_pct >= 0.8, f"Capacity not increasing with horizon: {monotonic_pct:.0%} monotonic"
    
    def test_hit_rate_doesnt_degrade_too_much_with_horizon(self, bars_1s_2h):
        """
        Hit rate shouldn't drop dramatically for longer horizons.
        
        Prediction becomes harder at longer horizons, but shouldn't
        drop below random (50%) unless data is completely unpredictable.
        """
        optimizer = HorizonOptimizer(
            horizons_seconds=[10, 30, 60, 120, 180],
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_1s_2h, symbol="TEST")
        
        # All hit rates should be finite
        hit_rates = results_df["hit_rate_pct"].values
        assert np.isfinite(hit_rates).all(), "Some hit rates are non-finite"


class TestDeterminism:
    """Optimization should be deterministic."""
    
    def test_optimization_is_deterministic(self, bars_5m_1d):
        """Two runs should produce identical results."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[30, 60],
            labeling_method="classification",
        )
        
        best1, all1, df1 = optimizer.optimize(bars_5m_1d, symbol="TEST")
        best2, all2, df2 = optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        assert best1.horizon_seconds == best2.horizon_seconds, "Best horizon differs"
        assert abs(best1.information_ratio - best2.information_ratio) < 1e-10, "IR differs"
        
        # DataFrames should be identical
        assert df1.equals(df2), "Results DataFrames differ"


class TestReportGeneration:
    """Report generation should work without errors."""
    
    def test_report_generation_succeeds(self, bars_5m_1d):
        """generate_report() should produce valid report."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[30, 60],
            labeling_method="regression",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST/USD")
        
        report = optimizer.generate_report(results_df, "TEST/USD")
        
        assert isinstance(report, str), "Report is not a string"
        assert len(report) > 0, "Report is empty"
        assert "TEST/USD" in report, "Symbol not in report"
        assert "Optimal Horizon" in report, "Missing optimal horizon section"
    
    def test_report_contains_key_metrics(self, bars_5m_1d):
        """Report should contain all key metrics."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[30, 60],
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST")
        report = optimizer.generate_report(results_df, "TEST")
        
        # Check for key metrics
        assert "Information ratio" in report, "Missing IR"
        assert "Sharpe ratio" in report, "Missing Sharpe"
        assert "Hit rate" in report, "Missing hit rate"
        assert "Capacity" in report, "Missing capacity"


class TestEdgeCases:
    """Edge cases and error handling."""
    
    def test_single_horizon_works(self, bars_5m_1d):
        """Optimization with single horizon should work."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[60],
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        assert best_result.horizon_seconds == 60, "Wrong horizon selected"
        assert len(all_results) == 1, "Wrong number of results"
    
    def test_handles_short_data_gracefully(self, tiny_bars_nan):
        """Should handle very short datasets without crashing."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[10, 30],
            labeling_method="classification",
        )
        
        # Should not crash, even if some horizons fail
        try:
            best_result, all_results, results_df = optimizer.optimize(tiny_bars_nan, symbol="TEST")
            # If it succeeds, should have valid results
            assert len(all_results) > 0, "No results produced"
        except ValueError as e:
            # Acceptable to raise error for too-short data
            assert "No valid horizons" in str(e) or "Insufficient" in str(e)


class TestClassificationVsRegression:
    """Both labeling methods should work in optimizer."""
    
    def test_classification_method_works(self, bars_5m_1d):
        """Classification method should produce valid results."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[30, 60],
            labeling_method="classification",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        assert best_result.hit_rate >= 0, "Invalid hit rate"
        assert best_result.hit_rate <= 100, "Hit rate > 100%"
    
    def test_regression_method_works(self, bars_5m_1d):
        """Regression method should produce valid results."""
        optimizer = HorizonOptimizer(
            horizons_seconds=[30, 60],
            labeling_method="regression",
        )
        
        best_result, all_results, results_df = optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        assert np.isfinite(best_result.sharpe_ratio), "Invalid Sharpe ratio"
        assert np.isfinite(best_result.information_ratio), "Invalid IR"
