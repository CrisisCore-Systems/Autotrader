"""
Monte Carlo Simulation Framework for Backtesting.

Provides advanced backtesting capabilities including:
- Monte Carlo simulation of strategy returns
- Bootstrap resampling for confidence intervals
- Scenario analysis and stress testing
- Parameter sensitivity analysis
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import json

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SimulationResults:
    """Results from Monte Carlo simulation."""
    n_simulations: int
    returns: np.ndarray  # Shape: (n_simulations, n_periods)
    final_values: np.ndarray  # Final portfolio values
    max_drawdowns: np.ndarray
    sharpe_ratios: np.ndarray
    
    def get_percentiles(self, percentiles: List[float] = [5, 25, 50, 75, 95]) -> Dict[str, np.ndarray]:
        """Get percentile statistics."""
        return {
            f'p{int(p)}': {
                'returns': np.percentile(self.returns, p, axis=0),
                'final_value': np.percentile(self.final_values, p),
                'max_drawdown': np.percentile(self.max_drawdowns, p),
                'sharpe_ratio': np.percentile(self.sharpe_ratios, p),
            }
            for p in percentiles
        }
    
    def get_statistics(self) -> Dict[str, float]:
        """Get summary statistics."""
        return {
            'mean_final_value': np.mean(self.final_values),
            'std_final_value': np.std(self.final_values),
            'mean_max_drawdown': np.mean(self.max_drawdowns),
            'worst_drawdown': np.max(self.max_drawdowns),
            'mean_sharpe': np.mean(self.sharpe_ratios),
            'probability_of_profit': np.mean(self.final_values > 1.0),  # Assuming initial value = 1
        }


class MonteCarloSimulator:
    """
    Monte Carlo simulation engine for strategy backtesting.
    
    Simulates thousands of possible paths based on historical
    return distribution to assess strategy robustness.
    """
    
    def __init__(
        self,
        initial_capital: float = 100000.0,
        n_simulations: int = 10000,
        random_seed: Optional[int] = None,
    ):
        self.initial_capital = initial_capital
        self.n_simulations = n_simulations
        self.random_seed = random_seed
        
        if random_seed:
            np.random.seed(random_seed)
    
    def simulate_from_returns(
        self,
        historical_returns: np.ndarray,
        n_periods: int,
        method: str = 'bootstrap',
    ) -> SimulationResults:
        """
        Simulate future returns from historical distribution.
        
        Args:
            historical_returns: Historical return series
            n_periods: Number of periods to simulate
            method: Simulation method ('bootstrap', 'parametric', 'block_bootstrap')
        
        Returns:
            SimulationResults object
        """
        logger.info(f"Running {self.n_simulations} Monte Carlo simulations for {n_periods} periods")
        
        if method == 'bootstrap':
            simulated_returns = self._bootstrap_simulation(historical_returns, n_periods)
        elif method == 'parametric':
            simulated_returns = self._parametric_simulation(historical_returns, n_periods)
        elif method == 'block_bootstrap':
            simulated_returns = self._block_bootstrap_simulation(historical_returns, n_periods)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Calculate metrics for each simulation
        final_values = self._calculate_final_values(simulated_returns)
        max_drawdowns = self._calculate_max_drawdowns(simulated_returns)
        sharpe_ratios = self._calculate_sharpe_ratios(simulated_returns)
        
        return SimulationResults(
            n_simulations=self.n_simulations,
            returns=simulated_returns,
            final_values=final_values,
            max_drawdowns=max_drawdowns,
            sharpe_ratios=sharpe_ratios,
        )
    
    def _bootstrap_simulation(
        self,
        historical_returns: np.ndarray,
        n_periods: int,
    ) -> np.ndarray:
        """
        Bootstrap resampling of historical returns.
        
        Randomly samples with replacement from historical returns.
        """
        simulated = np.zeros((self.n_simulations, n_periods))
        
        for i in range(self.n_simulations):
            # Sample with replacement
            indices = np.random.randint(0, len(historical_returns), size=n_periods)
            simulated[i] = historical_returns[indices]
        
        return simulated
    
    def _parametric_simulation(
        self,
        historical_returns: np.ndarray,
        n_periods: int,
    ) -> np.ndarray:
        """
        Parametric simulation assuming normal distribution.
        
        Uses mean and std from historical returns.
        """
        mean = np.mean(historical_returns)
        std = np.std(historical_returns)
        
        simulated = np.random.normal(
            loc=mean,
            scale=std,
            size=(self.n_simulations, n_periods)
        )
        
        return simulated
    
    def _block_bootstrap_simulation(
        self,
        historical_returns: np.ndarray,
        n_periods: int,
        block_size: int = 20,
    ) -> np.ndarray:
        """
        Block bootstrap to preserve autocorrelation structure.
        
        Samples blocks of consecutive returns.
        """
        simulated = np.zeros((self.n_simulations, n_periods))
        
        for i in range(self.n_simulations):
            sampled = []
            while len(sampled) < n_periods:
                # Random starting point
                start = np.random.randint(0, len(historical_returns) - block_size)
                block = historical_returns[start:start + block_size]
                sampled.extend(block)
            
            simulated[i] = sampled[:n_periods]
        
        return simulated
    
    def _calculate_final_values(self, returns: np.ndarray) -> np.ndarray:
        """Calculate final portfolio values."""
        # Compound returns
        cumulative_returns = np.cumprod(1 + returns, axis=1)
        final_values = cumulative_returns[:, -1]
        return final_values
    
    def _calculate_max_drawdowns(self, returns: np.ndarray) -> np.ndarray:
        """Calculate maximum drawdown for each simulation."""
        max_drawdowns = np.zeros(self.n_simulations)
        
        for i in range(self.n_simulations):
            equity = np.cumprod(1 + returns[i])
            running_max = np.maximum.accumulate(equity)
            drawdown = (running_max - equity) / running_max
            max_drawdowns[i] = np.max(drawdown)
        
        return max_drawdowns
    
    def _calculate_sharpe_ratios(
        self,
        returns: np.ndarray,
        risk_free_rate: float = 0.02,
    ) -> np.ndarray:
        """Calculate Sharpe ratio for each simulation."""
        mean_returns = np.mean(returns, axis=1)
        std_returns = np.std(returns, axis=1)
        
        # Annualize (assuming daily returns)
        annual_return = mean_returns * 252
        annual_vol = std_returns * np.sqrt(252)
        
        sharpe_ratios = (annual_return - risk_free_rate) / annual_vol
        return sharpe_ratios


class ScenarioAnalyzer:
    """
    Scenario analysis and stress testing.
    
    Tests strategy performance under specific market scenarios.
    """
    
    def __init__(self):
        self.scenarios: Dict[str, Dict] = {}
    
    def add_scenario(
        self,
        name: str,
        description: str,
        market_shock: float,
        volatility_multiplier: float = 1.0,
        correlation_increase: float = 0.0,
    ):
        """
        Add a stress scenario.
        
        Args:
            name: Scenario name
            description: Scenario description
            market_shock: Market return shock (e.g., -0.20 for 20% crash)
            volatility_multiplier: Multiply volatility by this factor
            correlation_increase: Increase correlations by this amount
        """
        self.scenarios[name] = {
            'description': description,
            'market_shock': market_shock,
            'volatility_multiplier': volatility_multiplier,
            'correlation_increase': correlation_increase,
        }
        logger.info(f"Added scenario: {name}")
    
    def run_scenario(
        self,
        scenario_name: str,
        portfolio_returns: np.ndarray,
        portfolio_weights: np.ndarray,
    ) -> Dict[str, float]:
        """
        Run a specific scenario.
        
        Args:
            scenario_name: Name of scenario to run
            portfolio_returns: Historical returns for each asset
            portfolio_weights: Current portfolio weights
        
        Returns:
            Dict with scenario results
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Scenario {scenario_name} not found")
        
        scenario = self.scenarios[scenario_name]
        
        # Apply market shock
        shocked_returns = portfolio_returns + scenario['market_shock']
        
        # Apply volatility multiplier
        mean_returns = np.mean(shocked_returns, axis=0)
        shocked_returns = mean_returns + (shocked_returns - mean_returns) * scenario['volatility_multiplier']
        
        # Calculate portfolio impact
        portfolio_return = np.dot(shocked_returns.mean(axis=0), portfolio_weights)
        portfolio_vol = np.sqrt(
            portfolio_weights @ np.cov(shocked_returns.T) @ portfolio_weights
        )
        
        # Calculate max drawdown under scenario
        portfolio_equity = np.cumprod(1 + shocked_returns @ portfolio_weights)
        running_max = np.maximum.accumulate(portfolio_equity)
        drawdown = (running_max - portfolio_equity) / running_max
        max_drawdown = np.max(drawdown)
        
        return {
            'scenario': scenario_name,
            'description': scenario['description'],
            'portfolio_return': portfolio_return,
            'portfolio_volatility': portfolio_vol,
            'max_drawdown': max_drawdown,
            'var_95': np.percentile(shocked_returns @ portfolio_weights, 5),
        }
    
    def run_all_scenarios(
        self,
        portfolio_returns: np.ndarray,
        portfolio_weights: np.ndarray,
    ) -> pd.DataFrame:
        """Run all defined scenarios."""
        results = []
        for scenario_name in self.scenarios:
            result = self.run_scenario(scenario_name, portfolio_returns, portfolio_weights)
            results.append(result)
        
        return pd.DataFrame(results)
    
    @classmethod
    def create_standard_scenarios(cls) -> ScenarioAnalyzer:
        """Create standard stress test scenarios."""
        analyzer = cls()
        
        # 2008 Financial Crisis
        analyzer.add_scenario(
            name='2008_crisis',
            description='2008 Financial Crisis',
            market_shock=-0.37,  # S&P 500 peak to trough
            volatility_multiplier=2.5,
            correlation_increase=0.3,
        )
        
        # 2020 COVID Crash
        analyzer.add_scenario(
            name='covid_crash',
            description='2020 COVID-19 Crash',
            market_shock=-0.34,
            volatility_multiplier=3.0,
            correlation_increase=0.4,
        )
        
        # Flash Crash
        analyzer.add_scenario(
            name='flash_crash',
            description='Intraday Flash Crash',
            market_shock=-0.10,
            volatility_multiplier=5.0,
            correlation_increase=0.5,
        )
        
        # Moderate Correction
        analyzer.add_scenario(
            name='correction',
            description='10% Market Correction',
            market_shock=-0.10,
            volatility_multiplier=1.5,
            correlation_increase=0.1,
        )
        
        # Stagflation
        analyzer.add_scenario(
            name='stagflation',
            description='Stagflation Scenario',
            market_shock=-0.15,
            volatility_multiplier=1.8,
            correlation_increase=0.2,
        )
        
        return analyzer


class ParameterSensitivityAnalyzer:
    """
    Analyze sensitivity to strategy parameters.
    
    Tests how strategy performance changes with different parameter values.
    """
    
    def __init__(
        self,
        strategy_func: Callable,
        base_params: Dict,
    ):
        """
        Initialize analyzer.
        
        Args:
            strategy_func: Function that runs strategy and returns performance metrics
            base_params: Base parameter values
        """
        self.strategy_func = strategy_func
        self.base_params = base_params
    
    def analyze_parameter(
        self,
        param_name: str,
        param_values: List[float],
        n_parallel: int = 4,
    ) -> pd.DataFrame:
        """
        Analyze sensitivity to a single parameter.
        
        Args:
            param_name: Name of parameter to vary
            param_values: List of values to test
            n_parallel: Number of parallel workers
        
        Returns:
            DataFrame with results for each parameter value
        """
        logger.info(f"Analyzing sensitivity to {param_name}: {len(param_values)} values")
        
        results = []
        
        # Run simulations in parallel
        with ProcessPoolExecutor(max_workers=n_parallel) as executor:
            futures = {}
            
            for value in param_values:
                params = self.base_params.copy()
                params[param_name] = value
                
                future = executor.submit(self.strategy_func, params)
                futures[future] = value
            
            for future in as_completed(futures):
                value = futures[future]
                try:
                    metrics = future.result()
                    results.append({
                        'param_name': param_name,
                        'param_value': value,
                        **metrics,
                    })
                except Exception as e:
                    logger.error(f"Error with {param_name}={value}: {e}")
        
        return pd.DataFrame(results)
    
    def analyze_multiple_parameters(
        self,
        param_ranges: Dict[str, List[float]],
        n_parallel: int = 4,
    ) -> Dict[str, pd.DataFrame]:
        """
        Analyze sensitivity to multiple parameters.
        
        Args:
            param_ranges: Dict mapping parameter names to value lists
            n_parallel: Number of parallel workers
        
        Returns:
            Dict mapping parameter names to result DataFrames
        """
        results = {}
        
        for param_name, param_values in param_ranges.items():
            results[param_name] = self.analyze_parameter(
                param_name, param_values, n_parallel
            )
        
        return results
    
    def find_optimal_parameters(
        self,
        param_ranges: Dict[str, List[float]],
        metric: str = 'sharpe_ratio',
        n_parallel: int = 4,
    ) -> Dict[str, float]:
        """
        Find optimal parameter values that maximize a metric.
        
        Args:
            param_ranges: Dict mapping parameter names to value lists
            metric: Metric to optimize
            n_parallel: Number of parallel workers
        
        Returns:
            Dict of optimal parameter values
        """
        sensitivity_results = self.analyze_multiple_parameters(param_ranges, n_parallel)
        
        optimal_params = {}
        for param_name, results_df in sensitivity_results.items():
            best_row = results_df.loc[results_df[metric].idxmax()]
            optimal_params[param_name] = best_row['param_value']
        
        logger.info(f"Optimal parameters: {optimal_params}")
        return optimal_params


def calculate_confidence_interval(
    returns: np.ndarray,
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
) -> Tuple[float, float]:
    """
    Calculate bootstrap confidence interval for mean return.
    
    Args:
        returns: Return series
        confidence_level: Confidence level (e.g., 0.95)
        n_bootstrap: Number of bootstrap samples
    
    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    bootstrap_means = []
    
    for _ in range(n_bootstrap):
        sample = np.random.choice(returns, size=len(returns), replace=True)
        bootstrap_means.append(np.mean(sample))
    
    bootstrap_means = np.array(bootstrap_means)
    
    alpha = (1 - confidence_level) / 2
    lower = np.percentile(bootstrap_means, alpha * 100)
    upper = np.percentile(bootstrap_means, (1 - alpha) * 100)
    
    return lower, upper


def save_simulation_results(results: SimulationResults, path: Path):
    """Save Monte Carlo simulation results to disk."""
    output = {
        'n_simulations': results.n_simulations,
        'statistics': results.get_statistics(),
        'percentiles': {
            k: {kk: vv.tolist() if isinstance(vv, np.ndarray) else vv 
                for kk, vv in v.items()}
            for k, v in results.get_percentiles().items()
        },
    }
    
    with open(path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Saved simulation results to {path}")
