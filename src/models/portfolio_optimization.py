"""
Portfolio Optimization with Modern Risk Metrics.

Implements CVaR, drawdown control, mean-variance optimization,
risk parity, and Kelly criterion for dynamic position sizing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from scipy.optimize import minimize
from scipy import stats

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PortfolioMetrics:
    """Portfolio risk and return metrics."""
    expected_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    cvar_95: float  # 95% CVaR
    cvar_99: float  # 99% CVaR
    calmar_ratio: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'expected_return': self.expected_return,
            'volatility': self.volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'max_drawdown': self.max_drawdown,
            'cvar_95': self.cvar_95,
            'cvar_99': self.cvar_99,
            'calmar_ratio': self.calmar_ratio,
        }


class CVaRCalculator:
    """
    Conditional Value at Risk (CVaR) calculator.
    
    CVaR measures the expected loss in the worst α% of cases.
    More conservative than VaR as it accounts for tail risk.
    """
    
    @staticmethod
    def calculate_var(returns: np.ndarray, confidence_level: float = 0.95) -> float:
        """
        Calculate Value at Risk (VaR).
        
        Args:
            returns: Array of returns
            confidence_level: Confidence level (e.g., 0.95 for 95%)
        
        Returns:
            VaR as a positive number (loss)
        """
        if len(returns) == 0:
            return 0.0
        
        percentile = (1 - confidence_level) * 100
        var = np.percentile(returns, percentile)
        return -var  # Return as positive number
    
    @staticmethod
    def calculate_cvar(returns: np.ndarray, confidence_level: float = 0.95) -> float:
        """
        Calculate Conditional Value at Risk (CVaR).
        
        CVaR is the expected loss given that we're in the worst α% of cases.
        
        Args:
            returns: Array of returns
            confidence_level: Confidence level (e.g., 0.95 for 95%)
        
        Returns:
            CVaR as a positive number (expected tail loss)
        """
        if len(returns) == 0:
            return 0.0
        
        var = CVaRCalculator.calculate_var(returns, confidence_level)
        
        # CVaR is the mean of losses beyond VaR
        tail_losses = returns[returns <= -var]
        
        if len(tail_losses) == 0:
            return var
        
        cvar = -np.mean(tail_losses)
        return cvar
    
    @staticmethod
    def calculate_parametric_cvar(
        mean: float,
        std: float,
        confidence_level: float = 0.95
    ) -> float:
        """
        Calculate CVaR assuming normal distribution (faster).
        
        Args:
            mean: Expected return
            std: Standard deviation of returns
            confidence_level: Confidence level
        
        Returns:
            Parametric CVaR estimate
        """
        alpha = 1 - confidence_level
        z_alpha = stats.norm.ppf(alpha)
        
        # Parametric CVaR for normal distribution
        cvar = -mean + std * stats.norm.pdf(z_alpha) / alpha
        return cvar


class DrawdownController:
    """
    Maximum Drawdown Control.
    
    Monitors portfolio drawdown and triggers risk reduction
    when drawdown exceeds thresholds.
    """
    
    def __init__(
        self,
        warning_threshold: float = 0.10,  # 10% drawdown warning
        critical_threshold: float = 0.20,  # 20% drawdown critical
        recovery_threshold: float = 0.05,  # 5% drawdown to resume normal
    ):
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.recovery_threshold = recovery_threshold
        
        self.peak_value: float = 0.0
        self.current_drawdown: float = 0.0
        self.max_drawdown: float = 0.0
        self.in_drawdown_control: bool = False
    
    def update(self, portfolio_value: float) -> Dict[str, any]:
        """
        Update drawdown state.
        
        Args:
            portfolio_value: Current portfolio value
        
        Returns:
            Dict with drawdown metrics and control signals
        """
        # Update peak
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
        
        # Calculate current drawdown
        if self.peak_value > 0:
            self.current_drawdown = (self.peak_value - portfolio_value) / self.peak_value
        else:
            self.current_drawdown = 0.0
        
        # Update max drawdown
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
        
        # Determine control state
        if self.current_drawdown >= self.critical_threshold:
            status = 'CRITICAL'
            position_scalar = 0.5  # Reduce positions by 50%
            self.in_drawdown_control = True
        elif self.current_drawdown >= self.warning_threshold:
            status = 'WARNING'
            position_scalar = 0.75  # Reduce positions by 25%
            self.in_drawdown_control = True
        elif self.current_drawdown <= self.recovery_threshold:
            status = 'NORMAL'
            position_scalar = 1.0
            self.in_drawdown_control = False
        else:
            # In recovery phase
            status = 'RECOVERY'
            position_scalar = 0.75 if self.in_drawdown_control else 1.0
        
        return {
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'peak_value': self.peak_value,
            'status': status,
            'position_scalar': position_scalar,
            'in_control': self.in_drawdown_control,
        }
    
    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> float:
        """
        Calculate maximum drawdown from equity curve.
        
        Args:
            equity_curve: Series of portfolio values
        
        Returns:
            Maximum drawdown as a positive fraction
        """
        if len(equity_curve) == 0:
            return 0.0
        
        cummax = equity_curve.cummax()
        drawdown = (cummax - equity_curve) / cummax
        return drawdown.max()


class PortfolioOptimizer:
    """
    Modern portfolio optimization using various methods.
    
    Supports:
    - Mean-variance optimization (Markowitz)
    - Risk parity
    - CVaR minimization
    - Maximum Sharpe ratio
    - Minimum volatility
    """
    
    def __init__(
        self,
        risk_free_rate: float = 0.02,  # 2% annual
        max_position: float = 0.3,  # Max 30% in single position
        min_position: float = 0.0,  # Min 0% (no shorting by default)
    ):
        self.risk_free_rate = risk_free_rate
        self.max_position = max_position
        self.min_position = min_position
    
    def mean_variance_optimization(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        target_return: Optional[float] = None,
    ) -> np.ndarray:
        """
        Markowitz mean-variance optimization.
        
        Args:
            expected_returns: Expected returns for each asset
            covariance_matrix: Covariance matrix of returns
            target_return: Target portfolio return (None for max Sharpe)
        
        Returns:
            Optimal weights
        """
        n_assets = len(expected_returns)
        
        # Objective: minimize portfolio variance
        def portfolio_variance(weights):
            return weights @ covariance_matrix @ weights
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},  # Weights sum to 1
        ]
        
        if target_return is not None:
            constraints.append({
                'type': 'eq',
                'fun': lambda w: w @ expected_returns - target_return
            })
        
        # Bounds for each weight
        bounds = tuple((self.min_position, self.max_position) for _ in range(n_assets))
        
        # Initial guess: equal weights
        initial_weights = np.ones(n_assets) / n_assets
        
        # Optimize
        result = minimize(
            portfolio_variance,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
        )
        
        if not result.success:
            logger.warning(f"Optimization failed: {result.message}")
            return initial_weights
        
        return result.x
    
    def max_sharpe_ratio(
        self,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
    ) -> np.ndarray:
        """
        Maximize Sharpe ratio.
        
        Args:
            expected_returns: Expected returns for each asset
            covariance_matrix: Covariance matrix of returns
        
        Returns:
            Optimal weights
        """
        n_assets = len(expected_returns)
        
        # Objective: maximize Sharpe ratio (minimize negative Sharpe)
        def negative_sharpe(weights):
            portfolio_return = weights @ expected_returns
            portfolio_vol = np.sqrt(weights @ covariance_matrix @ weights)
            sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol
            return -sharpe
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        ]
        
        # Bounds
        bounds = tuple((self.min_position, self.max_position) for _ in range(n_assets))
        
        # Initial guess
        initial_weights = np.ones(n_assets) / n_assets
        
        # Optimize
        result = minimize(
            negative_sharpe,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
        )
        
        if not result.success:
            logger.warning(f"Max Sharpe optimization failed: {result.message}")
            return initial_weights
        
        return result.x
    
    def risk_parity(
        self,
        covariance_matrix: np.ndarray,
    ) -> np.ndarray:
        """
        Risk parity allocation.
        
        Each asset contributes equally to portfolio risk.
        
        Args:
            covariance_matrix: Covariance matrix of returns
        
        Returns:
            Risk parity weights
        """
        n_assets = covariance_matrix.shape[0]
        
        # Objective: minimize difference in risk contributions
        def risk_parity_objective(weights):
            portfolio_vol = np.sqrt(weights @ covariance_matrix @ weights)
            marginal_contrib = covariance_matrix @ weights
            risk_contrib = weights * marginal_contrib / portfolio_vol
            
            # Target equal risk contribution
            target_risk = portfolio_vol / n_assets
            return np.sum((risk_contrib - target_risk) ** 2)
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        ]
        
        # Bounds
        bounds = tuple((self.min_position, self.max_position) for _ in range(n_assets))
        
        # Initial guess
        initial_weights = np.ones(n_assets) / n_assets
        
        # Optimize
        result = minimize(
            risk_parity_objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
        )
        
        if not result.success:
            logger.warning(f"Risk parity optimization failed: {result.message}")
            return initial_weights
        
        return result.x
    
    def min_cvar(
        self,
        returns_history: pd.DataFrame,
        confidence_level: float = 0.95,
    ) -> np.ndarray:
        """
        Minimize CVaR (conditional value at risk).
        
        Args:
            returns_history: Historical returns (rows=time, cols=assets)
            confidence_level: CVaR confidence level
        
        Returns:
            CVaR-minimizing weights
        """
        n_assets = returns_history.shape[1]
        returns_matrix = returns_history.values
        
        # Objective: minimize CVaR
        def portfolio_cvar(weights):
            portfolio_returns = returns_matrix @ weights
            cvar = CVaRCalculator.calculate_cvar(portfolio_returns, confidence_level)
            return cvar
        
        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
        ]
        
        # Bounds
        bounds = tuple((self.min_position, self.max_position) for _ in range(n_assets))
        
        # Initial guess
        initial_weights = np.ones(n_assets) / n_assets
        
        # Optimize
        result = minimize(
            portfolio_cvar,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
        )
        
        if not result.success:
            logger.warning(f"CVaR optimization failed: {result.message}")
            return initial_weights
        
        return result.x
    
    def calculate_portfolio_metrics(
        self,
        weights: np.ndarray,
        expected_returns: np.ndarray,
        covariance_matrix: np.ndarray,
        returns_history: Optional[pd.DataFrame] = None,
    ) -> PortfolioMetrics:
        """
        Calculate comprehensive portfolio metrics.
        
        Args:
            weights: Portfolio weights
            expected_returns: Expected returns for each asset
            covariance_matrix: Covariance matrix
            returns_history: Historical returns for CVaR calculation
        
        Returns:
            PortfolioMetrics object
        """
        # Basic metrics
        portfolio_return = weights @ expected_returns
        portfolio_vol = np.sqrt(weights @ covariance_matrix @ weights)
        sharpe = (portfolio_return - self.risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
        
        # Sortino ratio (downside risk)
        if returns_history is not None:
            portfolio_returns = returns_history.values @ weights
            downside_returns = portfolio_returns[portfolio_returns < 0]
            downside_vol = np.std(downside_returns) if len(downside_returns) > 0 else portfolio_vol
            sortino = (portfolio_return - self.risk_free_rate) / downside_vol if downside_vol > 0 else 0
            
            # CVaR
            cvar_95 = CVaRCalculator.calculate_cvar(portfolio_returns, 0.95)
            cvar_99 = CVaRCalculator.calculate_cvar(portfolio_returns, 0.99)
            
            # Maximum drawdown
            equity_curve = (1 + portfolio_returns).cumprod()
            max_dd = DrawdownController.calculate_max_drawdown(pd.Series(equity_curve))
        else:
            sortino = sharpe  # Approximate
            cvar_95 = CVaRCalculator.calculate_parametric_cvar(portfolio_return, portfolio_vol, 0.95)
            cvar_99 = CVaRCalculator.calculate_parametric_cvar(portfolio_return, portfolio_vol, 0.99)
            max_dd = 0.0
        
        # Calmar ratio (return / max drawdown)
        calmar = portfolio_return / max_dd if max_dd > 0 else 0
        
        return PortfolioMetrics(
            expected_return=portfolio_return,
            volatility=portfolio_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            calmar_ratio=calmar,
        )


class KellyCriterion:
    """
    Kelly Criterion for optimal position sizing.
    
    Determines the optimal fraction of capital to risk
    based on win probability and payoff ratio.
    """
    
    @staticmethod
    def calculate_kelly_fraction(
        win_probability: float,
        avg_win: float,
        avg_loss: float,
        max_kelly_fraction: float = 0.25,  # Cap at 25% for safety
    ) -> float:
        """
        Calculate Kelly fraction for position sizing.
        
        Kelly% = W - (1-W)/R
        where W = win probability, R = avg_win / avg_loss
        
        Args:
            win_probability: Probability of winning trade
            avg_win: Average profit on winning trades
            avg_loss: Average loss on losing trades (positive number)
            max_kelly_fraction: Maximum Kelly fraction (for safety)
        
        Returns:
            Optimal position size as fraction of capital
        """
        if avg_loss <= 0:
            logger.warning("Average loss must be positive")
            return 0.0
        
        if not (0 <= win_probability <= 1):
            logger.warning(f"Win probability must be in [0,1], got {win_probability}")
            return 0.0
        
        # Kelly formula
        payoff_ratio = avg_win / avg_loss
        kelly_fraction = win_probability - (1 - win_probability) / payoff_ratio
        
        # Ensure non-negative
        kelly_fraction = max(0, kelly_fraction)
        
        # Cap at max Kelly fraction
        kelly_fraction = min(kelly_fraction, max_kelly_fraction)
        
        logger.debug(
            f"Kelly calculation: win_prob={win_probability:.3f}, "
            f"payoff_ratio={payoff_ratio:.2f}, kelly={kelly_fraction:.3f}"
        )
        
        return kelly_fraction
    
    @staticmethod
    def fractional_kelly(
        kelly_fraction: float,
        fraction: float = 0.5,  # Half Kelly
    ) -> float:
        """
        Apply fractional Kelly for more conservative sizing.
        
        Args:
            kelly_fraction: Full Kelly fraction
            fraction: Fraction of Kelly to use (e.g., 0.5 for half Kelly)
        
        Returns:
            Fractional Kelly position size
        """
        return kelly_fraction * fraction
