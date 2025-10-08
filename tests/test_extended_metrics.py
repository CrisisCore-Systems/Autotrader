"""Tests for extended backtest metrics (IC, risk-adjusted performance)."""

import numpy as np
import pytest
from typing import Dict, List

from backtest.extended_metrics import (
    ICMetrics,
    RiskMetrics,
    ExtendedBacktestMetrics,
    calculate_ic_metrics,
    calculate_risk_metrics,
    calculate_extended_metrics,
    compare_extended_metrics,
    format_ic_summary,
)


class MockTokenSnapshot:
    """Mock token snapshot for testing."""
    
    def __init__(self, token: str, features: Dict[str, float], future_return_7d: float):
        self.token = token
        self.features = features
        self.future_return_7d = future_return_7d


class TestCalculateICMetrics:
    """Test IC calculation functions."""
    
    def test_perfect_correlation(self):
        """Test perfect positive correlation (IC = 1.0)."""
        predictions = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        actuals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        
        ic = calculate_ic_metrics(predictions, actuals)
        
        assert ic.ic_pearson == pytest.approx(1.0, abs=0.01)
        assert ic.ic_spearman == pytest.approx(1.0, abs=0.01)
        assert ic.ic_kendall == pytest.approx(1.0, abs=0.01)
        assert ic.ic_pearson_pvalue < 0.05
        assert ic.hit_rate == 1.0
        assert ic.sample_size == 5
    
    def test_negative_correlation(self):
        """Test negative correlation."""
        predictions = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        actuals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        
        ic = calculate_ic_metrics(predictions, actuals)
        
        assert ic.ic_pearson == pytest.approx(-1.0, abs=0.01)
        assert ic.ic_spearman == pytest.approx(-1.0, abs=0.01)
        assert ic.ic_kendall == pytest.approx(-1.0, abs=0.01)
    
    def test_no_correlation(self):
        """Test zero correlation."""
        np.random.seed(42)
        predictions = np.random.randn(50)
        actuals = np.random.randn(50)
        
        ic = calculate_ic_metrics(predictions, actuals)
        
        # Should be close to 0 with random data
        assert abs(ic.ic_pearson) < 0.3
        assert ic.sample_size == 50
    
    def test_moderate_correlation(self):
        """Test moderate positive correlation."""
        np.random.seed(42)
        predictions = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        noise = np.random.randn(10) * 0.5
        actuals = predictions + noise
        
        ic = calculate_ic_metrics(predictions, actuals)
        
        assert ic.ic_pearson > 0.5
        assert ic.ic_spearman > 0.5
        assert ic.sample_size == 10
    
    def test_with_nan_values(self):
        """Test handling of NaN values."""
        predictions = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
        actuals = np.array([1.0, 2.0, 3.0, np.nan, 5.0])
        
        ic = calculate_ic_metrics(predictions, actuals)
        
        # Should filter out NaNs and calculate on valid data
        assert ic.sample_size == 3
        assert not np.isnan(ic.ic_pearson)
    
    def test_insufficient_data(self):
        """Test with insufficient data points."""
        predictions = np.array([1.0])
        actuals = np.array([1.0])
        
        ic = calculate_ic_metrics(predictions, actuals)
        
        assert ic.ic_pearson == 0.0
        assert ic.ic_pearson_pvalue == 1.0
        assert ic.sample_size == 1
    
    def test_with_periods(self):
        """Test IC calculation with multiple periods."""
        predictions = np.array([1, 2, 3, 4, 5, 6, 7, 8])
        actuals = np.array([1.1, 2.1, 2.9, 4.2, 4.8, 6.1, 7.2, 7.9])
        periods = [1, 1, 1, 1, 2, 2, 2, 2]
        
        ic = calculate_ic_metrics(predictions, actuals, periods)
        
        assert ic.ic_mean != 0.0
        assert ic.ic_std >= 0.0
        assert ic.sample_size == 8
    
    def test_hit_rate_calculation(self):
        """Test hit rate (direction accuracy) calculation."""
        # All predictions correct direction
        predictions = np.array([1.0, 2.0, -1.0, -2.0])
        actuals = np.array([0.5, 1.0, -0.5, -1.0])
        
        ic = calculate_ic_metrics(predictions, actuals)
        assert ic.hit_rate == 1.0
        
        # Half correct direction
        predictions = np.array([1.0, 2.0, -1.0, -2.0])
        actuals = np.array([0.5, -1.0, -0.5, 1.0])
        
        ic = calculate_ic_metrics(predictions, actuals)
        assert ic.hit_rate == 0.5


class TestCalculateRiskMetrics:
    """Test risk metric calculation functions."""
    
    def test_positive_returns(self):
        """Test with all positive returns."""
        returns = np.array([0.01, 0.02, 0.015, 0.025, 0.02])
        
        risk = calculate_risk_metrics(returns)
        
        assert risk.total_return > 0
        assert risk.mean_return > 0
        assert risk.volatility > 0
        assert risk.win_rate == 1.0
        assert risk.max_drawdown == 0.0
        assert risk.sample_size == 5
    
    def test_negative_returns(self):
        """Test with all negative returns."""
        returns = np.array([-0.01, -0.02, -0.015, -0.025, -0.02])
        
        risk = calculate_risk_metrics(returns)
        
        assert risk.total_return < 0
        assert risk.mean_return < 0
        assert risk.win_rate == 0.0
        assert risk.max_drawdown < 0
    
    def test_mixed_returns(self):
        """Test with mixed positive and negative returns."""
        returns = np.array([0.05, -0.02, 0.03, -0.01, 0.04, -0.015, 0.02])
        
        risk = calculate_risk_metrics(returns)
        
        assert 0.0 < risk.win_rate < 1.0
        assert risk.volatility > 0
        assert risk.profit_factor > 0
        assert risk.sample_size == 7
    
    def test_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        # High return, low volatility
        returns = np.array([0.02] * 10)
        risk = calculate_risk_metrics(returns, risk_free_rate=0.0)
        
        # Should have infinite/very high Sharpe (no volatility)
        assert risk.sharpe_ratio >= 0
        
        # Normal case
        returns = np.array([0.01, 0.02, 0.015, 0.005, 0.018, 0.012, 0.008])
        risk = calculate_risk_metrics(returns, risk_free_rate=0.005)
        
        assert risk.sharpe_ratio > 0
    
    def test_sortino_ratio(self):
        """Test Sortino ratio calculation."""
        returns = np.array([0.05, -0.02, 0.03, -0.01, 0.04])
        
        risk = calculate_risk_metrics(returns, risk_free_rate=0.0)
        
        assert risk.sortino_ratio != 0
        assert risk.downside_deviation > 0
        # Sortino should be higher than Sharpe (only penalizes downside)
        assert risk.sortino_ratio >= risk.sharpe_ratio
    
    def test_calmar_ratio(self):
        """Test Calmar ratio calculation."""
        # Create returns with drawdown
        returns = np.array([0.05, -0.1, 0.03, 0.02, 0.04])
        
        risk = calculate_risk_metrics(returns, risk_free_rate=0.0)
        
        assert risk.max_drawdown < 0
        assert risk.calmar_ratio != 0
    
    def test_max_drawdown(self):
        """Test maximum drawdown calculation."""
        # Create specific drawdown scenario
        returns = np.array([0.1, -0.2, -0.1, 0.05, 0.15])
        
        risk = calculate_risk_metrics(returns)
        
        assert risk.max_drawdown < 0
        assert risk.max_drawdown >= -0.3  # Max possible with these returns
    
    def test_profit_factor(self):
        """Test profit factor calculation."""
        returns = np.array([0.1, 0.05, -0.02, -0.01, 0.08])
        
        risk = calculate_risk_metrics(returns)
        
        # Profit factor = sum(positive) / abs(sum(negative))
        expected_pf = (0.1 + 0.05 + 0.08) / (0.02 + 0.01)
        assert risk.profit_factor == pytest.approx(expected_pf, abs=0.01)
    
    def test_annualized_return(self):
        """Test annualized return calculation."""
        # 52 weekly returns of 0.01 each
        returns = np.array([0.01] * 52)
        
        risk = calculate_risk_metrics(returns, periods_per_year=52)
        
        # Should compound to approximately (1.01)^52 - 1
        expected = (1.01 ** 52) - 1
        assert risk.annualized_return == pytest.approx(expected, rel=0.01)
    
    def test_empty_returns(self):
        """Test with empty returns array."""
        returns = np.array([])
        
        risk = calculate_risk_metrics(returns)
        
        assert risk.total_return == 0.0
        assert risk.volatility == 0.0
        assert risk.sample_size == 0
    
    def test_with_nan_values(self):
        """Test handling of NaN values."""
        returns = np.array([0.01, np.nan, 0.02, np.nan, 0.015])
        
        risk = calculate_risk_metrics(returns)
        
        assert risk.sample_size == 3
        assert not np.isnan(risk.mean_return)


class TestCalculateExtendedMetrics:
    """Test comprehensive metrics calculation."""
    
    def test_basic_calculation(self):
        """Test basic extended metrics calculation."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.05),
            MockTokenSnapshot("TOKEN2", {}, 0.03),
            MockTokenSnapshot("TOKEN3", {}, -0.02),
            MockTokenSnapshot("TOKEN4", {}, 0.04),
            MockTokenSnapshot("TOKEN5", {}, 0.01),
        ]
        predictions = np.array([0.9, 0.7, 0.3, 0.8, 0.5])
        
        metrics = calculate_extended_metrics(snapshots, predictions)
        
        assert isinstance(metrics, ExtendedBacktestMetrics)
        assert isinstance(metrics.ic_metrics, ICMetrics)
        assert isinstance(metrics.risk_metrics, RiskMetrics)
        assert metrics.ic_metrics.sample_size == 5
        assert metrics.risk_metrics.sample_size == 5
    
    def test_with_top_k(self):
        """Test with top_k filter."""
        snapshots = [
            MockTokenSnapshot(f"TOKEN{i}", {}, 0.01 * i)
            for i in range(10)
        ]
        predictions = np.array([0.1 * i for i in range(10)])
        
        metrics = calculate_extended_metrics(snapshots, predictions, top_k=5)
        
        # Should only evaluate top 5
        assert metrics.metadata['evaluated_snapshots'] == 5
        assert metrics.metadata['top_k'] == 5
    
    def test_mismatch_length_error(self):
        """Test error when snapshots and predictions don't match."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.05),
            MockTokenSnapshot("TOKEN2", {}, 0.03),
        ]
        predictions = np.array([0.9, 0.7, 0.5])  # Wrong length
        
        with pytest.raises(ValueError, match="same length"):
            calculate_extended_metrics(snapshots, predictions)
    
    def test_with_periods(self):
        """Test with period information."""
        snapshots = [
            MockTokenSnapshot(f"TOKEN{i}", {}, 0.01 * i)
            for i in range(8)
        ]
        predictions = np.array([0.1 * i for i in range(8)])
        periods = [1, 1, 1, 1, 2, 2, 2, 2]
        
        metrics = calculate_extended_metrics(
            snapshots, predictions, periods=periods
        )
        
        # Should calculate multi-period IC
        assert metrics.ic_metrics.sample_size == 8
    
    def test_metadata_populated(self):
        """Test that metadata is correctly populated."""
        snapshots = [MockTokenSnapshot(f"TOKEN{i}", {}, 0.01) for i in range(5)]
        predictions = np.array([0.5] * 5)
        
        metrics = calculate_extended_metrics(
            snapshots, predictions, top_k=3, risk_free_rate=0.02
        )
        
        assert metrics.metadata['total_snapshots'] == 5
        assert metrics.metadata['evaluated_snapshots'] == 3
        assert metrics.metadata['top_k'] == 3
        assert metrics.metadata['risk_free_rate'] == 0.02


class TestCompareExtendedMetrics:
    """Test comparison of extended metrics."""
    
    def test_comparison_calculation(self):
        """Test comparison between GemScore and baselines."""
        gem_score = ExtendedBacktestMetrics(
            ic_metrics=ICMetrics(
                ic_pearson=0.5, ic_spearman=0.48, ic_kendall=0.4,
                ic_pearson_pvalue=0.01, ic_spearman_pvalue=0.01, ic_kendall_pvalue=0.01,
                ic_mean=0.5, ic_std=0.1, ic_ir=5.0,
                hit_rate=0.7, sample_size=100
            ),
            risk_metrics=RiskMetrics(
                total_return=0.5, annualized_return=0.3,
                mean_return=0.01, median_return=0.01,
                volatility=0.05, downside_deviation=0.03, max_drawdown=-0.1,
                sharpe_ratio=2.0, sortino_ratio=3.0, calmar_ratio=3.0,
                win_rate=0.7, profit_factor=2.5, sample_size=100
            )
        )
        
        baseline = ExtendedBacktestMetrics(
            ic_metrics=ICMetrics(
                ic_pearson=0.2, ic_spearman=0.18, ic_kendall=0.15,
                ic_pearson_pvalue=0.05, ic_spearman_pvalue=0.05, ic_kendall_pvalue=0.05,
                ic_mean=0.2, ic_std=0.1, ic_ir=2.0,
                hit_rate=0.55, sample_size=100
            ),
            risk_metrics=RiskMetrics(
                total_return=0.2, annualized_return=0.15,
                mean_return=0.005, median_return=0.005,
                volatility=0.08, downside_deviation=0.06, max_drawdown=-0.15,
                sharpe_ratio=1.0, sortino_ratio=1.5, calmar_ratio=1.0,
                win_rate=0.55, profit_factor=1.5, sample_size=100
            )
        )
        
        comparisons = compare_extended_metrics(gem_score, {"random": baseline})
        
        assert "random" in comparisons
        assert comparisons["random"]["ic_improvement"] == pytest.approx(0.3, abs=0.01)
        assert comparisons["random"]["sharpe_improvement"] == pytest.approx(1.0, abs=0.01)
        assert comparisons["random"]["ic_better"] is True
        assert comparisons["random"]["sharpe_better"] is True
        assert comparisons["random"]["risk_adjusted_better"] is True


class TestFormatICSummary:
    """Test IC summary formatting."""
    
    def test_strong_ic_formatting(self):
        """Test formatting for strong IC."""
        ic = ICMetrics(
            ic_pearson=0.08, ic_spearman=0.075, ic_kendall=0.06,
            ic_pearson_pvalue=0.001, ic_spearman_pvalue=0.002, ic_kendall_pvalue=0.003,
            ic_mean=0.08, ic_std=0.02, ic_ir=4.0,
            hit_rate=0.65, sample_size=200
        )
        
        summary = format_ic_summary(ic)
        
        assert "Information Coefficient" in summary
        assert "0.0800" in summary
        assert "Strong predictive power" in summary
        assert "Statistically significant" in summary
    
    def test_weak_ic_formatting(self):
        """Test formatting for weak IC."""
        ic = ICMetrics(
            ic_pearson=0.01, ic_spearman=0.01, ic_kendall=0.008,
            ic_pearson_pvalue=0.5, ic_spearman_pvalue=0.6, ic_kendall_pvalue=0.7,
            ic_mean=0.01, ic_std=0.05, ic_ir=0.2,
            hit_rate=0.52, sample_size=50
        )
        
        summary = format_ic_summary(ic)
        
        assert "Weak predictive power" in summary
        assert "Not statistically significant" in summary


class TestExtendedBacktestMetrics:
    """Test ExtendedBacktestMetrics dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        ic = ICMetrics(
            ic_pearson=0.5, ic_spearman=0.48, ic_kendall=0.4,
            ic_pearson_pvalue=0.01, ic_spearman_pvalue=0.01, ic_kendall_pvalue=0.01,
            ic_mean=0.5, ic_std=0.1, ic_ir=5.0,
            hit_rate=0.7, sample_size=100
        )
        
        risk = RiskMetrics(
            total_return=0.5, annualized_return=0.3,
            mean_return=0.01, median_return=0.01,
            volatility=0.05, downside_deviation=0.03, max_drawdown=-0.1,
            sharpe_ratio=2.0, sortino_ratio=3.0, calmar_ratio=3.0,
            win_rate=0.7, profit_factor=2.5, sample_size=100
        )
        
        metrics = ExtendedBacktestMetrics(ic_metrics=ic, risk_metrics=risk)
        result = metrics.to_dict()
        
        assert 'ic_metrics' in result
        assert 'risk_metrics' in result
        assert result['ic_metrics']['ic_pearson'] == 0.5
        assert result['risk_metrics']['sharpe_ratio'] == 2.0
    
    def test_summary_string(self):
        """Test summary string generation."""
        ic = ICMetrics(
            ic_pearson=0.5, ic_spearman=0.48, ic_kendall=0.4,
            ic_pearson_pvalue=0.01, ic_spearman_pvalue=0.01, ic_kendall_pvalue=0.01,
            ic_mean=0.5, ic_std=0.1, ic_ir=5.0,
            hit_rate=0.7, sample_size=100
        )
        
        risk = RiskMetrics(
            total_return=0.5, annualized_return=0.3,
            mean_return=0.01, median_return=0.01,
            volatility=0.05, downside_deviation=0.03, max_drawdown=-0.1,
            sharpe_ratio=2.0, sortino_ratio=3.0, calmar_ratio=3.0,
            win_rate=0.7, profit_factor=2.5, sample_size=100
        )
        
        metrics = ExtendedBacktestMetrics(ic_metrics=ic, risk_metrics=risk)
        summary = metrics.summary_string()
        
        assert "EXTENDED BACKTEST METRICS" in summary
        assert "INFORMATION COEFFICIENT" in summary
        assert "RETURNS & RISK" in summary
        assert "RISK-ADJUSTED PERFORMANCE" in summary
        assert "Sharpe Ratio" in summary
        assert "2.0000" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
