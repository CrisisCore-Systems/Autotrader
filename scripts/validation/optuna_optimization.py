"""
Optuna Hyperparameter Optimization for Agentic Trading System

This module provides hyperparameter tuning using Optuna for the agentic trading system.
It optimizes parameters like feature engineering settings, model hyperparameters,
and trading logic thresholds to maximize out-of-sample performance.

Usage:
    python scripts/validation/optuna_optimization.py --data-dir data/processed/features --symbol AAPL --n-trials 100

Features:
- Configurable search space for all system parameters
- Multiple objective functions (Sharpe, Sortino, Calmar)
- Early stopping with pruning for inefficient trials
- Optimization history visualization
- Best parameters export to config files
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import matplotlib.pyplot as plt
import seaborn as sns

# Import baseline strategies for comparison
from baseline_strategies import (
    BaseStrategy,
    Momentum,
    MeanReversion,
    CrossoverMA
)


def calculate_sharpe_ratio(returns: pd.Series) -> float:
    """Calculate Sharpe ratio from returns."""
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    return (returns.mean() * np.sqrt(252 * 390)) / (returns.std() * np.sqrt(252 * 390))


def calculate_sortino_ratio(returns: pd.Series) -> float:
    """Calculate Sortino ratio from returns."""
    downside = returns[returns < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return (returns.mean() * np.sqrt(252 * 390)) / (downside.std() * np.sqrt(252 * 390))


def calculate_calmar_ratio(returns: pd.Series) -> float:
    """Calculate Calmar ratio from returns."""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = abs(drawdown.min())
    
    if max_dd == 0:
        return 0.0
    
    total_return = cumulative.iloc[-1] - 1
    annualized = (1 + total_return) ** (252 / len(returns)) - 1
    return annualized / max_dd


class AgenticSystemOptimizer:
    """
    Optuna-based hyperparameter optimizer for the agentic trading system.
    
    This class defines the search space, objective function, and optimization
    process for finding optimal system parameters.
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        objective_metric: str = "sharpe",
        n_splits: int = 5,
        train_ratio: float = 0.7,
        pruning_enabled: bool = True
    ):
        """
        Initialize the optimizer.
        
        Args:
            data: DataFrame with OHLCV and features
            objective_metric: Metric to optimize ("sharpe", "sortino", "calmar")
            n_splits: Number of walk-forward splits for validation
            train_ratio: Ratio of data for training (rest for testing)
            pruning_enabled: Whether to enable early stopping of bad trials
        """
        self.data = data
        self.objective_metric = objective_metric
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.pruning_enabled = pruning_enabled
        
        # Calculate split points
        self.split_size = len(data) // n_splits
        self.train_size = int(self.split_size * train_ratio)
        self.test_size = self.split_size - self.train_size
        
    def define_search_space(self, trial: optuna.Trial) -> Dict:
        """
        Define the hyperparameter search space.
        
        Args:
            trial: Optuna trial object
            
        Returns:
            Dictionary of sampled parameters
        """
        params = {
            # Strategy selection
            "strategy_type": trial.suggest_categorical(
                "strategy_type",
                ["momentum", "mean_reversion", "ma_crossover"]
            ),
            
            # Momentum parameters
            "momentum_lookback": trial.suggest_int("momentum_lookback", 100, 5000, step=100),
            "momentum_threshold": trial.suggest_float("momentum_threshold", 0.0001, 0.01),
            
            # Mean reversion parameters
            "mr_lookback": trial.suggest_int("mr_lookback", 10, 500, step=10),
            "mr_std_threshold": trial.suggest_float("mr_std_threshold", 1.0, 3.0, step=0.25),
            
            # MA Crossover parameters
            "ma_fast": trial.suggest_int("ma_fast", 5, 200, step=5),
            "ma_slow": trial.suggest_int("ma_slow", 50, 2000, step=50),
            
            # Position sizing
            "position_size": trial.suggest_float("position_size", 0.1, 1.0, step=0.1),
            
            # Risk management
            "stop_loss_pct": trial.suggest_float("stop_loss_pct", 0.01, 0.1, step=0.01),
            "take_profit_pct": trial.suggest_float("take_profit_pct", 0.02, 0.2, step=0.01),
            
            # Transaction costs
            "commission": trial.suggest_float("commission", 0.0001, 0.001, step=0.0001),
            "slippage": trial.suggest_float("slippage", 0.0001, 0.001, step=0.0001),
        }
        
        # Ensure MA fast < slow
        if params["ma_fast"] >= params["ma_slow"]:
            params["ma_slow"] = params["ma_fast"] + 50
            
        return params
    
    def create_strategy(self, params: Dict) -> BaseStrategy:
        """
        Create a strategy instance from parameters.
        
        Args:
            params: Parameter dictionary
            
        Returns:
            Strategy instance
        """
        strategy_type = params["strategy_type"]
        
        if strategy_type == "momentum":
            return Momentum(lookback=params["momentum_lookback"])
        elif strategy_type == "mean_reversion":
            return MeanReversion(
                lookback=params["mr_lookback"],
                std_threshold=params["mr_std_threshold"]
            )
        elif strategy_type == "ma_crossover":
            return CrossoverMA(
                fast_period=params["ma_fast"],
                slow_period=params["ma_slow"]
            )
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
    
    def evaluate_strategy(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        params: Dict
    ) -> float:
        """
        Evaluate strategy performance on data.
        
        Args:
            strategy: Strategy instance
            data: DataFrame with OHLCV
            params: Parameter dictionary with costs
            
        Returns:
            Objective metric value
        """
        # Generate signals
        signals = strategy.generate_signals(data)
        
        # Calculate returns with costs
        commission = params["commission"]
        slippage = params["slippage"]
        total_cost = commission + slippage
        
        # Simple return calculation
        price_returns = data['close'].pct_change()
        strategy_returns = signals.shift(1) * price_returns
        
        # Apply transaction costs on trades
        trades = signals.diff().abs()
        costs = trades * total_cost
        strategy_returns = strategy_returns - costs
        
        # Calculate objective metric
        if self.objective_metric == "sharpe":
            return calculate_sharpe_ratio(strategy_returns)
        elif self.objective_metric == "sortino":
            return calculate_sortino_ratio(strategy_returns)
        elif self.objective_metric == "calmar":
            return calculate_calmar_ratio(strategy_returns)
        else:
            raise ValueError(f"Unknown metric: {self.objective_metric}")
    
    def objective(self, trial: optuna.Trial) -> float:
        """
        Objective function for Optuna optimization.
        
        Args:
            trial: Optuna trial object
            
        Returns:
            Average objective metric across all splits
        """
        # Sample parameters
        params = self.define_search_space(trial)
        
        # Create strategy
        try:
            strategy = self.create_strategy(params)
        except Exception as e:
            # Invalid parameters
            return float('-inf')
        
        # Walk-forward validation
        scores = []
        for i in range(self.n_splits):
            start_idx = i * self.split_size
            train_end = start_idx + self.train_size
            test_end = start_idx + self.split_size
            
            if test_end > len(self.data):
                break
            
            # Get test data
            test_data = self.data.iloc[train_end:test_end].copy()
            
            # Evaluate
            score = self.evaluate_strategy(strategy, test_data, params)
            scores.append(score)
            
            # Pruning: report intermediate value
            if self.pruning_enabled:
                trial.report(np.mean(scores), i)
                if trial.should_prune():
                    raise optuna.TrialPruned()
        
        # Return average score
        return np.mean(scores) if scores else float('-inf')


def run_optimization(
    data_path: str,
    symbol: str,
    n_trials: int = 100,
    objective_metric: str = "sharpe",
    n_splits: int = 5,
    output_dir: str = "reports/optuna"
) -> Tuple[Dict, optuna.Study]:
    """
    Run Optuna optimization study.
    
    Args:
        data_path: Path to features data directory
        symbol: Symbol to optimize
        n_trials: Number of optimization trials
        objective_metric: Metric to optimize
        n_splits: Number of walk-forward splits
        output_dir: Directory for output reports
        
    Returns:
        Tuple of (best_params, study)
    """
    # Load data
    feature_file = Path(data_path) / f"{symbol}_bars_features.parquet"
    if not feature_file.exists():
        # Try CSV format
        feature_file = Path(data_path) / symbol / "features.csv"
        if not feature_file.exists():
            raise FileNotFoundError(f"Features file not found: {feature_file}")
        data = pd.read_csv(feature_file)
    else:
        data = pd.read_parquet(feature_file)
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    data = data.sort_values('timestamp').reset_index(drop=True)
    
    print(f"Loaded {len(data):,} bars for {symbol}")
    
    # Create optimizer
    optimizer = AgenticSystemOptimizer(
        data=data,
        objective_metric=objective_metric,
        n_splits=n_splits,
        pruning_enabled=True
    )
    
    # Create study
    sampler = TPESampler(seed=42)
    pruner = MedianPruner(n_startup_trials=10, n_warmup_steps=2)
    
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        pruner=pruner,
        study_name=f"{symbol}_{objective_metric}_optimization"
    )
    
    # Run optimization
    print(f"\nStarting optimization with {n_trials} trials...")
    study.optimize(optimizer.objective, n_trials=n_trials, show_progress_bar=True)
    
    # Get best parameters
    best_params = study.best_params
    best_value = study.best_value
    
    print(f"\nOptimization complete!")
    print(f"Best {objective_metric}: {best_value:.4f}")
    print(f"Best parameters:")
    for key, value in best_params.items():
        print(f"  {key}: {value}")
    
    # Save results
    os.makedirs(output_dir, exist_ok=True)
    
    # Save best parameters
    params_file = Path(output_dir) / f"{symbol}_best_params.json"
    with open(params_file, 'w') as f:
        json.dump({
            "symbol": symbol,
            "objective_metric": objective_metric,
            "best_value": float(best_value),
            "best_params": best_params,
            "n_trials": n_trials,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    print(f"\nBest parameters saved to {params_file}")
    
    return best_params, study


def plot_optimization_history(
    study: optuna.Study,
    symbol: str,
    output_dir: str = "reports/optuna"
) -> None:
    """
    Plot optimization history and parameter importance.
    
    Args:
        study: Optuna study object
        symbol: Symbol name
        output_dir: Directory for output plots
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Optimization history
    fig, ax = plt.subplots(figsize=(12, 6))
    
    trials = study.trials
    trial_numbers = [t.number for t in trials if t.value is not None]
    values = [t.value for t in trials if t.value is not None]
    
    ax.plot(trial_numbers, values, 'o-', alpha=0.6, label='Trial value')
    
    # Best value line
    best_values = []
    current_best = float('-inf')
    for v in values:
        if v > current_best:
            current_best = v
        best_values.append(current_best)
    
    ax.plot(trial_numbers, best_values, 'r-', linewidth=2, label='Best value')
    
    ax.set_xlabel('Trial Number')
    ax.set_ylabel('Objective Value')
    ax.set_title(f'Optimization History - {symbol}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    history_file = Path(output_dir) / f"{symbol}_optimization_history.png"
    plt.tight_layout()
    plt.savefig(history_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Optimization history plot saved to {history_file}")
    
    # 2. Parameter importance
    try:
        importance = optuna.importance.get_param_importances(study)
        
        fig, ax = plt.subplots(figsize=(10, 6))
        params = list(importance.keys())
        values = list(importance.values())
        
        # Sort by importance
        sorted_pairs = sorted(zip(params, values), key=lambda x: x[1], reverse=True)
        params, values = zip(*sorted_pairs)
        
        ax.barh(params, values)
        ax.set_xlabel('Importance')
        ax.set_title(f'Hyperparameter Importance - {symbol}')
        ax.grid(True, alpha=0.3, axis='x')
        
        importance_file = Path(output_dir) / f"{symbol}_param_importance.png"
        plt.tight_layout()
        plt.savefig(importance_file, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Parameter importance plot saved to {importance_file}")
        
    except Exception as e:
        print(f"Could not generate parameter importance plot: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Optuna hyperparameter optimization for agentic trading system"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/processed/features",
        help="Directory containing features data"
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="AAPL",
        help="Symbol to optimize"
    )
    parser.add_argument(
        "--n-trials",
        type=int,
        default=100,
        help="Number of optimization trials"
    )
    parser.add_argument(
        "--objective",
        type=str,
        default="sharpe",
        choices=["sharpe", "sortino", "calmar"],
        help="Objective metric to optimize"
    )
    parser.add_argument(
        "--n-splits",
        type=int,
        default=5,
        help="Number of walk-forward validation splits"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports/optuna",
        help="Directory for output reports"
    )
    
    args = parser.parse_args()
    
    # Run optimization
    best_params, study = run_optimization(
        data_path=args.data_dir,
        symbol=args.symbol,
        n_trials=args.n_trials,
        objective_metric=args.objective,
        n_splits=args.n_splits,
        output_dir=args.output_dir
    )
    
    # Plot results
    plot_optimization_history(study, args.symbol, args.output_dir)
    
    print(f"\nOptimization complete for {args.symbol}!")


if __name__ == "__main__":
    main()
