"""
Unit tests for portfolio optimization module.
"""

import pytest
import numpy as np
import pandas as pd

from src.models.portfolio_optimization import (
    CVaRCalculator,
    DrawdownController,
    PortfolioOptimizer,
    KellyCriterion,
    PortfolioMetrics,
)


class TestCVaRCalculator:
    """Tests for CVaR calculator."""
    
    def test_calculate_var(self):
        """Test VaR calculation."""
        returns = np.random.randn(1000) * 0.01
        
        var = CVaRCalculator.calculate_var(returns, confidence_level=0.95)
        
        assert isinstance(var, float)
        assert var >= 0  # VaR is reported as positive loss
    
    def test_calculate_cvar(self):
        """Test CVaR calculation."""
        returns = np.random.randn(1000) * 0.01
        
        cvar = CVaRCalculator.calculate_cvar(returns, confidence_level=0.95)
        
        assert isinstance(cvar, float)
        assert cvar >= 0
    
    def test_cvar_greater_than_var(self):
        """CVaR should be >= VaR."""
        returns = np.random.randn(1000) * 0.01
        
        var = CVaRCalculator.calculate_var(returns, 0.95)
        cvar = CVaRCalculator.calculate_cvar(returns, 0.95)
        
        assert cvar >= var
    
    def test_parametric_cvar(self):
        """Test parametric CVaR calculation."""
        mean = 0.0005  # Daily return
        std = 0.01  # Daily volatility
        
        cvar = CVaRCalculator.calculate_parametric_cvar(mean, std, 0.95)
        
        assert isinstance(cvar, float)
        assert cvar > 0


class TestDrawdownController:
    """Tests for drawdown controller."""
    
    def test_initialization(self):
        """Test controller initialization."""
        controller = DrawdownController()
        
        assert controller.peak_value == 0.0
        assert controller.current_drawdown == 0.0
        assert controller.max_drawdown == 0.0
    
    def test_normal_operation(self):
        """Test normal operation without drawdown."""
        controller = DrawdownController()
        
        result = controller.update(100000.0)
        
        assert result['status'] == 'NORMAL'
        assert result['position_scalar'] == 1.0
        assert result['current_drawdown'] == 0.0
    
    def test_warning_threshold(self):
        """Test warning threshold."""
        controller = DrawdownController(
            warning_threshold=0.10,
            critical_threshold=0.20,
        )
        
        # Set peak
        controller.update(100000.0)
        
        # 12% drawdown (between warning and critical)
        result = controller.update(88000.0)
        
        assert result['status'] == 'WARNING'
        assert result['position_scalar'] == 0.75
        assert result['current_drawdown'] >= 0.10
    
    def test_critical_threshold(self):
        """Test critical threshold."""
        controller = DrawdownController(
            warning_threshold=0.10,
            critical_threshold=0.20,
        )
        
        controller.update(100000.0)
        
        # 25% drawdown (beyond critical)
        result = controller.update(75000.0)
        
        assert result['status'] == 'CRITICAL'
        assert result['position_scalar'] == 0.5
        assert result['current_drawdown'] >= 0.20
    
    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation from equity curve."""
        equity = pd.Series([100, 110, 105, 120, 90, 95, 100])
        
        max_dd = DrawdownController.calculate_max_drawdown(equity)
        
        # From 120 to 90 is 25% drawdown
        assert max_dd > 0.20
        assert max_dd < 0.30


class TestPortfolioOptimizer:
    """Tests for portfolio optimizer."""
    
    def test_initialization(self):
        """Test optimizer initialization."""
        optimizer = PortfolioOptimizer()
        
        assert optimizer.risk_free_rate == 0.02
        assert optimizer.max_position == 0.3
    
    def test_mean_variance_optimization(self):
        """Test mean-variance optimization."""
        optimizer = PortfolioOptimizer()
        
        # 3 assets
        expected_returns = np.array([0.10, 0.12, 0.15])
        cov_matrix = np.array([
            [0.04, 0.01, 0.02],
            [0.01, 0.06, 0.015],
            [0.02, 0.015, 0.09],
        ])
        
        weights = optimizer.mean_variance_optimization(
            expected_returns, cov_matrix
        )
        
        assert len(weights) == 3
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)
        assert np.all(weights <= 0.3)  # Respects max position
    
    def test_max_sharpe_ratio(self):
        """Test max Sharpe ratio optimization."""
        optimizer = PortfolioOptimizer()
        
        expected_returns = np.array([0.10, 0.12, 0.15])
        cov_matrix = np.array([
            [0.04, 0.01, 0.02],
            [0.01, 0.06, 0.015],
            [0.02, 0.015, 0.09],
        ])
        
        weights = optimizer.max_sharpe_ratio(expected_returns, cov_matrix)
        
        assert len(weights) == 3
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)
    
    def test_risk_parity(self):
        """Test risk parity allocation."""
        optimizer = PortfolioOptimizer()
        
        cov_matrix = np.array([
            [0.04, 0.01, 0.02],
            [0.01, 0.06, 0.015],
            [0.02, 0.015, 0.09],
        ])
        
        weights = optimizer.risk_parity(cov_matrix)
        
        assert len(weights) == 3
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)
    
    def test_calculate_portfolio_metrics(self):
        """Test portfolio metrics calculation."""
        optimizer = PortfolioOptimizer()
        
        weights = np.array([0.4, 0.3, 0.3])
        expected_returns = np.array([0.10, 0.12, 0.15])
        cov_matrix = np.array([
            [0.04, 0.01, 0.02],
            [0.01, 0.06, 0.015],
            [0.02, 0.015, 0.09],
        ])
        
        metrics = optimizer.calculate_portfolio_metrics(
            weights, expected_returns, cov_matrix
        )
        
        assert isinstance(metrics, PortfolioMetrics)
        assert metrics.expected_return > 0
        assert metrics.volatility > 0
        assert metrics.sharpe_ratio >= 0


class TestKellyCriterion:
    """Tests for Kelly Criterion."""
    
    def test_basic_calculation(self):
        """Test basic Kelly calculation."""
        win_prob = 0.6
        avg_win = 100
        avg_loss = 50
        
        kelly = KellyCriterion.calculate_kelly_fraction(
            win_prob, avg_win, avg_loss
        )
        
        assert 0 <= kelly <= 0.25  # Capped at 25%
        assert isinstance(kelly, float)
    
    def test_edge_cases(self):
        """Test edge cases."""
        # No edge
        kelly = KellyCriterion.calculate_kelly_fraction(0.5, 100, 100)
        assert kelly == 0
        
        # Perfect edge
        kelly = KellyCriterion.calculate_kelly_fraction(1.0, 100, 50)
        assert kelly > 0
    
    def test_fractional_kelly(self):
        """Test fractional Kelly."""
        full_kelly = 0.20
        
        half_kelly = KellyCriterion.fractional_kelly(full_kelly, 0.5)
        
        assert half_kelly == 0.10
    
    def test_kelly_capping(self):
        """Test that Kelly is capped at max fraction."""
        # Extreme edge case
        kelly = KellyCriterion.calculate_kelly_fraction(
            0.9, 1000, 10, max_kelly_fraction=0.25
        )
        
        assert kelly <= 0.25


def test_portfolio_metrics_to_dict():
    """Test PortfolioMetrics to_dict conversion."""
    metrics = PortfolioMetrics(
        expected_return=0.10,
        volatility=0.15,
        sharpe_ratio=1.5,
        sortino_ratio=1.8,
        max_drawdown=0.12,
        cvar_95=0.03,
        cvar_99=0.05,
        calmar_ratio=0.83,
    )
    
    d = metrics.to_dict()
    
    assert d['expected_return'] == 0.10
    assert d['volatility'] == 0.15
    assert d['sharpe_ratio'] == 1.5
