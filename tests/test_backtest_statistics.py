"""Tests for backtest statistics utilities."""

from __future__ import annotations

import math
from typing import List

import numpy as np
import pytest
from scipy import stats

from src.pipeline.backtest_statistics import (
    bootstrap_confidence_interval,
    compute_information_coefficient,
    compute_ic_distribution,
    compute_max_drawdown,
    compute_risk_adjusted_metrics,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_variance_decomposition,
)


class TestBootstrapConfidenceInterval:
    """Tests for bootstrap confidence interval calculations."""

    def test_bootstrap_confidence_interval_returns_expected_statistics(self):
        """Bootstrap of stable values should center around the sample mean."""
        values = [0.12, 0.15, 0.18, 0.2, 0.16]

        result = bootstrap_confidence_interval(values, n_bootstrap=2000, seed=7)

        sample_mean = np.mean(values)

        assert result.mean == pytest.approx(sample_mean, rel=0.05)
        assert result.median == pytest.approx(sample_mean, rel=0.05)
        assert result.ci_lower < result.ci_upper
        assert result.ci_lower <= sample_mean <= result.ci_upper

    def test_bootstrap_confidence_interval_requires_values(self):
        """Empty value lists should raise a clear error."""
        with pytest.raises(ValueError, match="Cannot bootstrap empty values list"):
            bootstrap_confidence_interval([])


class TestInformationCoefficient:
    """Tests for information coefficient helpers."""

    def test_compute_information_coefficient_detects_inverse_relationship(self):
        """Perfectly inverse rankings should return -1 correlation."""
        predictions = [1, 2, 3, 4, 5]
        actuals = list(reversed(predictions))

        ic, p_value = compute_information_coefficient(predictions, actuals)

        assert ic == pytest.approx(-1.0, abs=1e-12)
        assert p_value == pytest.approx(0.0, abs=1e-12)

    def test_compute_ic_distribution_aggregates_window_statistics(self):
        """Distribution metrics should align with manual calculations."""
        window_predictions: List[List[float]] = [
            [0.2, 0.4, 0.6, 0.8],
            [0.5, 0.3, 0.1, -0.1],
            [1.0, 0.5, 0.2, 0.1],
        ]
        window_actuals: List[List[float]] = [
            [0.1, 0.2, 0.3, 0.4],
            [-0.2, -0.1, 0.0, 0.1],
            [0.9, 0.4, 0.3, 0.2],
        ]

        result = compute_ic_distribution(window_predictions, window_actuals)

        ics = []
        for preds, actuals in zip(window_predictions, window_actuals):
            ic, _ = stats.spearmanr(preds, actuals)
            ics.append(ic)

        ics = np.array(ics)
        expected_mean = np.mean(ics)
        expected_std = np.std(ics, ddof=1)
        expected_ir = expected_mean / expected_std
        expected_positive_pct = 100.0 * np.sum(ics > 0) / len(ics)
        expected_t_stat, expected_p_value = stats.ttest_1samp(ics, 0.0)

        assert result.mean_ic == pytest.approx(expected_mean)
        assert result.std_ic == pytest.approx(expected_std)
        assert result.ic_ir == pytest.approx(expected_ir)
        assert result.positive_pct == pytest.approx(expected_positive_pct)
        assert result.t_stat == pytest.approx(expected_t_stat)
        assert result.p_value == pytest.approx(expected_p_value)


class TestRiskMetrics:
    """Tests for risk-adjusted metric calculations."""

    def test_compute_sharpe_ratio_matches_manual_calculation(self):
        """Sharpe ratio should match manual annualised computation."""
        returns = [0.01, 0.015, -0.005, 0.02]
        risk_free = 0.001

        result = compute_sharpe_ratio(returns, risk_free_rate=risk_free, periods_per_year=252)

        returns_array = np.array(returns)
        excess = returns_array - risk_free
        expected = (np.mean(excess) / np.std(excess, ddof=1)) * math.sqrt(252)

        assert result == pytest.approx(expected)

    def test_compute_sortino_ratio_handles_positive_returns(self):
        """If there are no downside returns the ratio should be infinite."""
        returns = [0.01, 0.02, 0.015, 0.03]

        result = compute_sortino_ratio(returns, risk_free_rate=0.0, periods_per_year=252)

        assert math.isinf(result)

    def test_compute_max_drawdown_matches_manual_calculation(self):
        """Drawdown should match numpy cumulative calculations."""
        returns = [0.05, -0.02, -0.01, 0.03, -0.04]

        result = compute_max_drawdown(returns)

        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        expected = np.max((running_max - cumulative) / running_max)

        assert result == pytest.approx(expected)

    def test_compute_risk_adjusted_metrics_matches_expected_values(self):
        """Comprehensive risk metrics should align with manual calculations."""
        returns = [0.02, -0.01, 0.015, -0.005, 0.03]
        risk_free = 0.001
        periods_per_year = 252

        metrics = compute_risk_adjusted_metrics(returns, risk_free_rate=risk_free, periods_per_year=periods_per_year)

        returns_array = np.array(returns)
        total_return = np.prod(1 + returns_array) - 1
        volatility = np.std(returns_array, ddof=1) * math.sqrt(periods_per_year)
        sharpe = compute_sharpe_ratio(returns, risk_free_rate=risk_free, periods_per_year=periods_per_year)
        sortino = compute_sortino_ratio(returns, risk_free_rate=risk_free, periods_per_year=periods_per_year)
        max_drawdown = compute_max_drawdown(returns)
        annualized_return = (1 + total_return) ** (periods_per_year / len(returns)) - 1
        calmar = annualized_return / max_drawdown
        win_rate = np.mean(returns_array > 0)
        profit_factor = returns_array[returns_array > 0].sum() / abs(returns_array[returns_array < 0].sum())

        assert metrics.total_return == pytest.approx(total_return)
        assert metrics.volatility == pytest.approx(volatility)
        assert metrics.sharpe_ratio == pytest.approx(sharpe)
        assert metrics.sortino_ratio == pytest.approx(sortino)
        assert metrics.max_drawdown == pytest.approx(max_drawdown)
        assert metrics.calmar_ratio == pytest.approx(calmar)
        assert metrics.win_rate == pytest.approx(win_rate)
        assert metrics.profit_factor == pytest.approx(profit_factor)

    def test_compute_risk_adjusted_metrics_requires_data(self):
        """Empty return series should raise a ValueError."""
        with pytest.raises(ValueError, match="Cannot compute metrics on empty returns"):
            compute_risk_adjusted_metrics([])


class TestVarianceDecomposition:
    """Tests for variance decomposition helper."""

    def test_compute_variance_decomposition_allocates_contributions(self):
        """Variance contributions should match covariance proportion."""
        total_returns = [0.01, 0.015, -0.005, 0.02]
        component_returns = {
            "alpha": [0.005, 0.01, -0.002, 0.011],
            "beta": [0.004, 0.003, -0.001, 0.007],
        }

        contributions = compute_variance_decomposition(total_returns, component_returns)

        total_var = np.var(total_returns, ddof=1)
        expected = {}
        for name, comp in component_returns.items():
            cov = np.cov(comp, total_returns)[0, 1]
            expected[name] = round(100.0 * cov / total_var, 2)

        for name, contribution in contributions.items():
            assert contribution == pytest.approx(expected[name])

        assert set(contributions) == set(component_returns)

