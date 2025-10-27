"""
Walk-forward analysis and stability metrics.

This module provides tools for walk-forward evaluation, stability testing,
and regime analysis for backtest results.

Key Classes
-----------
WalkForwardEvaluator : Walk-forward cross-validation for backtests
StabilityMetrics : Performance stability analysis
RegimeAnalyzer : Market regime detection and analysis

References
----------
- Pardo (2008): "Walk-forward analysis and optimization"
- Lopez de Prado (2018): "Advances in Financial Machine Learning"
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Literal
import pandas as pd
import numpy as np
from scipy import stats


@dataclass
class WalkForwardWindow:
    """
    Walk-forward analysis window.
    
    Attributes
    ----------
    window_id : int
        Window identifier
    train_start : pd.Timestamp
        Training period start
    train_end : pd.Timestamp
        Training period end
    test_start : pd.Timestamp
        Test period start
    test_end : pd.Timestamp
        Test period end
    performance : Dict
        Test period performance metrics
    """
    window_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    performance: Dict = None


class WalkForwardEvaluator:
    """
    Walk-forward analysis for strategy evaluation.
    
    Implements walk-forward cross-validation with:
    - Rolling or expanding training windows
    - Fixed or proportional test periods
    - Performance tracking across windows
    - Stability metrics
    
    Parameters
    ----------
    train_period : str
        Training period (e.g., '30D', '3M')
    test_period : str
        Test period (e.g., '7D', '1M')
    window_type : str
        'rolling' or 'expanding'
    step_size : str, optional
        Step between windows (default: test_period)
    min_train_size : str, optional
        Minimum training period
    
    Examples
    --------
    >>> evaluator = WalkForwardEvaluator(
    ...     train_period='90D',
    ...     test_period='30D',
    ...     window_type='rolling'
    ... )
    >>> windows = evaluator.create_windows(
    ...     start_date='2024-01-01',
    ...     end_date='2024-12-31'
    ... )
    
    References
    ----------
    - Pardo (2008): Walk-forward optimization
    - Lopez de Prado (2018): Cross-validation for financial data
    """
    
    def __init__(
        self,
        train_period: str,
        test_period: str,
        window_type: Literal['rolling', 'expanding'] = 'rolling',
        step_size: Optional[str] = None,
        min_train_size: Optional[str] = None
    ):
        self.train_period = pd.Timedelta(train_period)
        self.test_period = pd.Timedelta(test_period)
        self.window_type = window_type
        self.step_size = pd.Timedelta(step_size) if step_size else self.test_period
        self.min_train_size = pd.Timedelta(min_train_size) if min_train_size else self.train_period
        
        self.windows: List[WalkForwardWindow] = []
    
    def create_windows(
        self,
        start_date: str,
        end_date: str
    ) -> List[WalkForwardWindow]:
        """
        Create walk-forward windows.
        
        Parameters
        ----------
        start_date : str
            Overall start date
        end_date : str
            Overall end date
        
        Returns
        -------
        windows : List[WalkForwardWindow]
            List of train/test windows
        """
        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        
        windows = []
        window_id = 0
        
        # Initial training period
        train_start = start
        train_end = start + self.train_period
        
        while train_end < end:
            # Test period
            test_start = train_end
            test_end = min(test_start + self.test_period, end)
            
            if test_end <= test_start:
                break
            
            # Create window
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end
            )
            windows.append(window)
            
            # Move to next window
            if self.window_type == 'rolling':
                train_start = train_start + self.step_size
                train_end = train_end + self.step_size
            else:  # expanding
                train_end = train_end + self.step_size
            
            window_id += 1
        
        self.windows = windows
        return windows
    
    def evaluate(
        self,
        engine,
        strategy_factory,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Run walk-forward evaluation.
        
        Parameters
        ----------
        engine : BacktestEngine
            Backtest engine instance
        strategy_factory : Callable
            Function that creates strategy given training data
        data : pd.DataFrame
            Full dataset
        
        Returns
        -------
        results : pd.DataFrame
            Performance metrics for each window
        """
        if not self.windows:
            raise ValueError("No windows created. Call create_windows() first.")
        
        results = []
        
        for window in self.windows:
            # Split data
            train_data = data[
                (data.index >= window.train_start) &
                (data.index < window.train_end)
            ]
            test_data = data[
                (data.index >= window.test_start) &
                (data.index < window.test_end)
            ]
            
            if len(train_data) == 0 or len(test_data) == 0:
                continue
            
            # Train strategy
            strategy = strategy_factory(train_data)
            
            # Test strategy
            backtest_result = engine.run(
                strategy=strategy,
                data=test_data,
                start_date=str(window.test_start),
                end_date=str(window.test_end)
            )
            
            # Store performance
            window.performance = backtest_result.to_dict()
            
            results.append({
                'window_id': window.window_id,
                'train_start': window.train_start,
                'train_end': window.train_end,
                'test_start': window.test_start,
                'test_end': window.test_end,
                **backtest_result.to_dict()
            })
        
        return pd.DataFrame(results)
    
    def get_summary_statistics(self) -> Dict:
        """
        Get summary statistics across all windows.
        
        Returns
        -------
        stats : dict
            Summary statistics
        """
        if not self.windows or not any(w.performance for w in self.windows):
            return {}
        
        # Extract metrics
        returns = [w.performance['total_return'] for w in self.windows if w.performance]
        sharpes = [w.performance['sharpe'] for w in self.windows if w.performance]
        drawdowns = [w.performance['max_drawdown'] for w in self.windows if w.performance]
        
        return {
            'num_windows': len(self.windows),
            'avg_return': np.mean(returns),
            'std_return': np.std(returns),
            'avg_sharpe': np.mean(sharpes),
            'std_sharpe': np.std(sharpes),
            'avg_drawdown': np.mean(drawdowns),
            'max_drawdown': np.max(drawdowns),
            'positive_windows': sum(1 for r in returns if r > 0),
            'win_rate': sum(1 for r in returns if r > 0) / len(returns) if returns else 0
        }


class StabilityMetrics:
    """
    Performance stability analysis.
    
    Computes:
    - Performance decay over time
    - Consistency metrics
    - Robustness to parameter changes
    
    Parameters
    ----------
    min_periods : int
        Minimum periods for rolling calculations
    
    Examples
    --------
    >>> stability = StabilityMetrics()
    >>> metrics = stability.compute_stability(backtest_results)
    
    References
    ----------
    - Bailey & Lopez de Prado (2014): "The Deflated Sharpe Ratio"
    """
    
    def __init__(self, min_periods: int = 20):
        self.min_periods = min_periods
    
    def compute_stability(
        self,
        equity_curve: pd.Series,
        window: str = '30D'
    ) -> Dict:
        """
        Compute stability metrics.
        
        Parameters
        ----------
        equity_curve : pd.Series
            Equity time series
        window : str
            Rolling window size
        
        Returns
        -------
        metrics : dict
            Stability metrics
        """
        returns = equity_curve.pct_change().fillna(0)
        
        # Rolling Sharpe ratio
        rolling_sharpe = self._rolling_sharpe(returns, window)
        
        # Performance decay (correlation between returns and time)
        time_index = np.arange(len(returns))
        decay_corr, decay_pvalue = stats.spearmanr(time_index, returns)
        
        # Consistency (proportion of positive rolling windows)
        rolling_returns = returns.rolling(window).sum()
        consistency = (rolling_returns > 0).sum() / len(rolling_returns.dropna())
        
        # Sharpe stability (std of rolling Sharpe)
        sharpe_stability = rolling_sharpe.std()
        
        return {
            'performance_decay_corr': decay_corr,
            'performance_decay_pvalue': decay_pvalue,
            'consistency_ratio': consistency,
            'sharpe_stability': sharpe_stability,
            'avg_rolling_sharpe': rolling_sharpe.mean(),
            'min_rolling_sharpe': rolling_sharpe.min(),
            'max_rolling_sharpe': rolling_sharpe.max()
        }
    
    def _rolling_sharpe(
        self,
        returns: pd.Series,
        window: str
    ) -> pd.Series:
        """Compute rolling Sharpe ratio."""
        rolling_mean = returns.rolling(window).mean()
        rolling_std = returns.rolling(window).std()
        
        sharpe = np.sqrt(252) * rolling_mean / rolling_std
        return sharpe.fillna(0)
    
    def compute_information_coefficient(
        self,
        predicted: pd.Series,
        actual: pd.Series,
        method: str = 'spearman'
    ) -> Dict:
        """
        Compute information coefficient (IC).
        
        Parameters
        ----------
        predicted : pd.Series
            Predicted returns/signals
        actual : pd.Series
            Actual returns
        method : str
            Correlation method ('spearman' or 'pearson')
        
        Returns
        -------
        ic_stats : dict
            IC statistics
        """
        # Align series
        aligned = pd.DataFrame({
            'predicted': predicted,
            'actual': actual
        }).dropna()
        
        if len(aligned) < 2:
            return {'ic': 0.0, 'ic_pvalue': 1.0}
        
        # Compute IC
        if method == 'spearman':
            ic, pvalue = stats.spearmanr(
                aligned['predicted'],
                aligned['actual']
            )
        else:
            ic, pvalue = stats.pearsonr(
                aligned['predicted'],
                aligned['actual']
            )
        
        # Rolling IC
        rolling_window = min(20, len(aligned) // 5)
        rolling_ic = aligned.rolling(rolling_window).apply(
            lambda x: stats.spearmanr(x['predicted'], x['actual'])[0]
            if len(x) >= 2 else np.nan,
            raw=False
        )
        
        return {
            'ic': ic,
            'ic_pvalue': pvalue,
            'ic_std': rolling_ic['predicted'].std() if len(rolling_ic) > 0 else 0.0,
            'ic_ir': ic / rolling_ic['predicted'].std() if rolling_ic['predicted'].std() > 0 else 0.0
        }


class RegimeAnalyzer:
    """
    Market regime detection and analysis.
    
    Detects regimes based on:
    - Volatility (low/medium/high)
    - Trend (up/down/sideways)
    - Liquidity (good/poor)
    
    Parameters
    ----------
    volatility_window : str
        Window for volatility calculation
    trend_window : str
        Window for trend detection
    
    Examples
    --------
    >>> analyzer = RegimeAnalyzer()
    >>> regimes = analyzer.detect_regimes(market_data)
    >>> performance_by_regime = analyzer.analyze_performance_by_regime(
    ...     equity_curve, regimes
    ... )
    
    References
    ----------
    - Kritzman & Li (2010): "Regime detection"
    """
    
    def __init__(
        self,
        volatility_window: str = '20D',
        trend_window: str = '50D'
    ):
        self.volatility_window = volatility_window
        self.trend_window = trend_window
    
    def detect_regimes(
        self,
        prices: pd.Series,
        volumes: Optional[pd.Series] = None
    ) -> pd.DataFrame:
        """
        Detect market regimes.
        
        Parameters
        ----------
        prices : pd.Series
            Price time series
        volumes : pd.Series, optional
            Volume time series
        
        Returns
        -------
        regimes : pd.DataFrame
            Regime classifications
        """
        regimes = pd.DataFrame(index=prices.index)
        
        # Volatility regime
        returns = prices.pct_change()
        volatility = returns.rolling(self.volatility_window).std()
        
        vol_quantiles = volatility.quantile([0.33, 0.67])
        regimes['volatility_regime'] = 'medium'
        regimes.loc[volatility < vol_quantiles[0.33], 'volatility_regime'] = 'low'
        regimes.loc[volatility > vol_quantiles[0.67], 'volatility_regime'] = 'high'
        
        # Trend regime
        sma_short = prices.rolling(20).mean()
        sma_long = prices.rolling(self.trend_window).mean()
        
        regimes['trend_regime'] = 'sideways'
        regimes.loc[sma_short > sma_long * 1.02, 'trend_regime'] = 'uptrend'
        regimes.loc[sma_short < sma_long * 0.98, 'trend_regime'] = 'downtrend'
        
        # Liquidity regime (if volume available)
        if volumes is not None:
            avg_volume = volumes.rolling(self.volatility_window).mean()
            vol_vol_quantiles = avg_volume.quantile([0.33, 0.67])
            
            regimes['liquidity_regime'] = 'normal'
            regimes.loc[avg_volume < vol_vol_quantiles[0.33], 'liquidity_regime'] = 'poor'
            regimes.loc[avg_volume > vol_vol_quantiles[0.67], 'liquidity_regime'] = 'good'
        
        return regimes
    
    def analyze_performance_by_regime(
        self,
        equity_curve: pd.Series,
        regimes: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Analyze performance by market regime.
        
        Parameters
        ----------
        equity_curve : pd.Series
            Equity time series
        regimes : pd.DataFrame
            Regime classifications
        
        Returns
        -------
        performance : pd.DataFrame
            Performance metrics by regime
        """
        returns = equity_curve.pct_change().fillna(0)
        
        # Align returns and regimes
        aligned = pd.DataFrame({
            'returns': returns,
            **{col: regimes[col] for col in regimes.columns}
        }).dropna()
        
        results = []
        
        for col in regimes.columns:
            for regime in aligned[col].unique():
                regime_returns = aligned[aligned[col] == regime]['returns']
                
                if len(regime_returns) < 2:
                    continue
                
                results.append({
                    'regime_type': col,
                    'regime': regime,
                    'avg_return': regime_returns.mean(),
                    'std_return': regime_returns.std(),
                    'sharpe': np.sqrt(252) * regime_returns.mean() / regime_returns.std()
                        if regime_returns.std() > 0 else 0,
                    'num_periods': len(regime_returns),
                    'win_rate': (regime_returns > 0).sum() / len(regime_returns)
                })
        
        return pd.DataFrame(results)
    
    def compute_regime_transitions(
        self,
        regimes: pd.DataFrame,
        regime_column: str = 'volatility_regime'
    ) -> pd.DataFrame:
        """
        Compute regime transition matrix.
        
        Parameters
        ----------
        regimes : pd.DataFrame
            Regime classifications
        regime_column : str
            Column to analyze
        
        Returns
        -------
        transition_matrix : pd.DataFrame
            Transition probability matrix
        """
        regime_series = regimes[regime_column]
        states = regime_series.unique()
        
        # Count transitions
        transitions = pd.DataFrame(0, index=states, columns=states)
        
        for i in range(len(regime_series) - 1):
            from_state = regime_series.iloc[i]
            to_state = regime_series.iloc[i + 1]
            if pd.notna(from_state) and pd.notna(to_state):
                transitions.loc[from_state, to_state] += 1
        
        # Convert to probabilities
        row_sums = transitions.sum(axis=1)
        transition_probs = transitions.div(row_sums, axis=0).fillna(0)
        
        return transition_probs


# Export public API
__all__ = [
    'WalkForwardEvaluator',
    'WalkForwardWindow',
    'StabilityMetrics',
    'RegimeAnalyzer',
]
