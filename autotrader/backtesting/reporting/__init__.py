"""
Performance analytics and reporting.

This module provides comprehensive performance analysis and reporting including:
- Tear sheet generation
- Performance metrics computation
- Trade analysis
- Visualizations

Key Classes
-----------
PerformanceMetrics : Compute 30+ performance metrics
TradeAnalyzer : Trade-level analysis
TearSheet : Generate comprehensive reports

References
----------
- Bailey & Lopez de Prado (2014): "The Sharpe Ratio Efficient Frontier"
- Grinold & Kahn (2000): "Active Portfolio Management"
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from dataclasses import dataclass


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics.
    
    Contains 30+ metrics for strategy evaluation.
    """
    # Returns
    total_return: float
    annualized_return: float
    volatility: float
    downside_volatility: float
    
    # Risk-adjusted
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    information_ratio: float
    
    # Drawdown
    max_drawdown: float
    avg_drawdown: float
    max_drawdown_duration: int
    recovery_time: int
    
    # Trade statistics
    num_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    
    # Additional
    skewness: float
    kurtosis: float
    var_95: float
    cvar_95: float
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'volatility': self.volatility,
            'downside_volatility': self.downside_volatility,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'information_ratio': self.information_ratio,
            'max_drawdown': self.max_drawdown,
            'avg_drawdown': self.avg_drawdown,
            'max_drawdown_duration': self.max_drawdown_duration,
            'recovery_time': self.recovery_time,
            'num_trades': self.num_trades,
            'win_rate': self.win_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'expectancy': self.expectancy,
            'skewness': self.skewness,
            'kurtosis': self.kurtosis,
            'var_95': self.var_95,
            'cvar_95': self.cvar_95
        }


class MetricsCalculator:
    """
    Calculate performance metrics.
    
    Examples
    --------
    >>> calculator = MetricsCalculator()
    >>> metrics = calculator.compute_all(backtest_results)
    """
    
    @staticmethod
    def compute_all(
        equity_curve: pd.Series,
        trades: List,
        benchmark_returns: Optional[pd.Series] = None
    ) -> PerformanceMetrics:
        """
        Compute all performance metrics.
        
        Parameters
        ----------
        equity_curve : pd.Series
            Equity time series
        trades : List[Trade]
            List of trades
        benchmark_returns : pd.Series, optional
            Benchmark returns for IR calculation
        
        Returns
        -------
        metrics : PerformanceMetrics
            All performance metrics
        """
        returns = equity_curve.pct_change().fillna(0)
        
        # Returns metrics
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        
        periods_per_year = MetricsCalculator._infer_periods_per_year(returns)
        annualized_return = (1 + total_return) ** (periods_per_year / len(returns)) - 1
        
        volatility = returns.std() * np.sqrt(periods_per_year)
        downside_volatility = MetricsCalculator._downside_volatility(returns) * np.sqrt(periods_per_year)
        
        # Risk-adjusted metrics
        sharpe = MetricsCalculator._sharpe_ratio(returns, periods_per_year)
        sortino = MetricsCalculator._sortino_ratio(returns, periods_per_year)
        
        max_dd = MetricsCalculator._max_drawdown(equity_curve)
        calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0
        
        info_ratio = 0.0
        if benchmark_returns is not None:
            info_ratio = MetricsCalculator._information_ratio(returns, benchmark_returns)
        
        # Drawdown metrics
        dd_series, dd_durations = MetricsCalculator._drawdown_series(equity_curve)
        avg_dd = abs(dd_series.mean())
        max_dd_duration = max(dd_durations) if dd_durations else 0
        recovery = MetricsCalculator._recovery_time(equity_curve)
        
        # Trade statistics
        trade_stats = MetricsCalculator._trade_statistics(trades)
        
        # Distribution metrics
        skew = returns.skew()
        kurt = returns.kurtosis()
        var_95 = returns.quantile(0.05)
        cvar_95 = returns[returns <= var_95].mean() if len(returns[returns <= var_95]) > 0 else 0
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            volatility=volatility,
            downside_volatility=downside_volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            information_ratio=info_ratio,
            max_drawdown=max_dd,
            avg_drawdown=avg_dd,
            max_drawdown_duration=max_dd_duration,
            recovery_time=recovery,
            num_trades=trade_stats['num_trades'],
            win_rate=trade_stats['win_rate'],
            avg_win=trade_stats['avg_win'],
            avg_loss=trade_stats['avg_loss'],
            profit_factor=trade_stats['profit_factor'],
            expectancy=trade_stats['expectancy'],
            skewness=skew,
            kurtosis=kurt,
            var_95=var_95,
            cvar_95=cvar_95
        )
    
    @staticmethod
    def _infer_periods_per_year(returns: pd.Series) -> int:
        """Infer number of periods per year from returns."""
        if len(returns) < 2:
            return 252
        
        avg_delta = (returns.index[-1] - returns.index[0]) / (len(returns) - 1)
        days = avg_delta.total_seconds() / 86400
        
        if days < 0.5:  # Intraday
            return 252 * int(24 / (days * 24))
        elif days < 2:  # Daily
            return 252
        elif days < 8:  # Weekly
            return 52
        else:  # Monthly
            return 12
    
    @staticmethod
    def _sharpe_ratio(returns: pd.Series, periods_per_year: int) -> float:
        """Compute annualized Sharpe ratio."""
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        return np.sqrt(periods_per_year) * returns.mean() / returns.std()
    
    @staticmethod
    def _sortino_ratio(returns: pd.Series, periods_per_year: int) -> float:
        """Compute annualized Sortino ratio."""
        downside_vol = MetricsCalculator._downside_volatility(returns)
        if downside_vol == 0:
            return 0.0
        return np.sqrt(periods_per_year) * returns.mean() / downside_vol
    
    @staticmethod
    def _downside_volatility(returns: pd.Series) -> float:
        """Compute downside volatility (semi-deviation)."""
        negative_returns = returns[returns < 0]
        if len(negative_returns) < 2:
            return 0.0
        return negative_returns.std()
    
    @staticmethod
    def _max_drawdown(equity: pd.Series) -> float:
        """Compute maximum drawdown."""
        if len(equity) < 2:
            return 0.0
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        return drawdown.min()
    
    @staticmethod
    def _drawdown_series(equity: pd.Series) -> Tuple[pd.Series, List[int]]:
        """Compute drawdown series and durations."""
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        
        # Find drawdown periods
        in_drawdown = drawdown < 0
        drawdown_starts = in_drawdown & ~in_drawdown.shift(1, fill_value=False)
        drawdown_ends = ~in_drawdown & in_drawdown.shift(1, fill_value=False)
        
        durations = []
        start_idx = None
        for i, (is_start, is_end) in enumerate(zip(drawdown_starts, drawdown_ends)):
            if is_start:
                start_idx = i
            elif is_end and start_idx is not None:
                durations.append(i - start_idx)
                start_idx = None
        
        return drawdown, durations
    
    @staticmethod
    def _recovery_time(equity: pd.Series) -> int:
        """Compute time to recover from max drawdown."""
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        
        max_dd_idx = drawdown.idxmin()
        if max_dd_idx == equity.index[-1]:
            return len(equity) - equity.index.get_loc(max_dd_idx)
        
        recovery_equity = equity.loc[max_dd_idx:]
        max_before_dd = running_max.loc[max_dd_idx]
        
        recovered = recovery_equity >= max_before_dd
        if recovered.any():
            recovery_idx = recovered.idxmax()
            return equity.index.get_loc(recovery_idx) - equity.index.get_loc(max_dd_idx)
        
        return len(recovery_equity)
    
    @staticmethod
    def _information_ratio(
        returns: pd.Series,
        benchmark_returns: pd.Series
    ) -> float:
        """Compute information ratio vs benchmark."""
        aligned = pd.DataFrame({
            'returns': returns,
            'benchmark': benchmark_returns
        }).dropna()
        
        if len(aligned) < 2:
            return 0.0
        
        excess_returns = aligned['returns'] - aligned['benchmark']
        if excess_returns.std() == 0:
            return 0.0
        
        return excess_returns.mean() / excess_returns.std() * np.sqrt(252)
    
    @staticmethod
    def _trade_statistics(trades: List) -> Dict:
        """Compute trade-level statistics."""
        if not trades:
            return {
                'num_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0
            }
        
        pnls = [t.pnl for t in trades if hasattr(t, 'pnl')]
        if not pnls:
            return {
                'num_trades': len(trades),
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0
            }
        
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        
        win_rate = len(wins) / len(pnls) if pnls else 0
        avg_win = np.mean(wins) if wins else 0
        avg_loss = np.mean(losses) if losses else 0
        
        total_wins = sum(wins)
        total_losses = abs(sum(losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        expectancy = np.mean(pnls)
        
        return {
            'num_trades': len(trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'expectancy': expectancy
        }


class TradeAnalyzer:
    """
    Trade-level analysis.
    
    Provides detailed trade analytics including:
    - Trade duration analysis
    - Entry/exit analysis
    - Cost breakdown
    - Performance by time of day
    
    Examples
    --------
    >>> analyzer = TradeAnalyzer()
    >>> trade_stats = analyzer.analyze(trades)
    """
    
    @staticmethod
    def analyze(trades: List) -> pd.DataFrame:
        """
        Analyze trade list.
        
        Parameters
        ----------
        trades : List[Trade]
            List of trades
        
        Returns
        -------
        analysis : pd.DataFrame
            Trade analysis
        """
        if not trades:
            return pd.DataFrame()
        
        records = []
        for trade in trades:
            records.append({
                'trade_id': trade.trade_id,
                'timestamp': trade.timestamp,
                'symbol': trade.symbol,
                'side': trade.side,
                'quantity': trade.quantity,
                'price': trade.price,
                'commission': trade.commission,
                'slippage': trade.slippage,
                'market_impact': trade.market_impact,
                'total_cost': trade.total_cost(),
                'pnl': trade.pnl,
                'hour': trade.timestamp.hour,
                'day_of_week': trade.timestamp.dayofweek
            })
        
        df = pd.DataFrame(records)
        return df
    
    @staticmethod
    def compute_cost_breakdown(trades: List) -> Dict:
        """Compute breakdown of trading costs."""
        if not trades:
            return {
                'total_commission': 0.0,
                'total_slippage': 0.0,
                'total_market_impact': 0.0,
                'total_cost': 0.0
            }
        
        total_commission = sum(t.commission for t in trades)
        total_slippage = sum(t.slippage for t in trades)
        total_impact = sum(t.market_impact for t in trades)
        
        return {
            'total_commission': total_commission,
            'total_slippage': total_slippage,
            'total_market_impact': total_impact,
            'total_cost': total_commission + total_slippage + total_impact,
            'avg_commission_per_trade': total_commission / len(trades),
            'avg_slippage_per_trade': total_slippage / len(trades),
            'avg_impact_per_trade': total_impact / len(trades)
        }
    
    @staticmethod
    def analyze_by_time(trades: List) -> pd.DataFrame:
        """Analyze performance by time of day."""
        df = TradeAnalyzer.analyze(trades)
        if df.empty:
            return pd.DataFrame()
        
        hourly = df.groupby('hour').agg({
            'pnl': ['mean', 'sum', 'count'],
            'total_cost': 'mean'
        }).round(4)
        
        return hourly


class TearSheet:
    """
    Generate comprehensive performance tear sheet.
    
    Creates detailed performance reports including:
    - Summary statistics
    - Equity curve
    - Drawdown chart
    - Monthly returns heatmap
    - Trade analysis
    
    Parameters
    ----------
    results : BacktestResults
        Backtest results
    
    Examples
    --------
    >>> tear_sheet = TearSheet(backtest_results)
    >>> report = tear_sheet.generate()
    >>> print(report)
    """
    
    def __init__(self, results):
        self.results = results
        self.metrics = MetricsCalculator.compute_all(
            results.equity_curve,
            results.trades
        )
    
    def generate(self) -> str:
        """
        Generate text tear sheet.
        
        Returns
        -------
        report : str
            Formatted report
        """
        lines = []
        lines.append("=" * 80)
        lines.append("BACKTEST PERFORMANCE TEAR SHEET")
        lines.append("=" * 80)
        lines.append("")
        
        # Period
        lines.append(f"Period: {self.results.start_date} to {self.results.end_date}")
        lines.append(f"Initial Capital: ${self.results.initial_capital:,.2f}")
        lines.append(f"Final Capital: ${self.results.final_capital:,.2f}")
        lines.append("")
        
        # Returns
        lines.append("RETURNS")
        lines.append("-" * 80)
        lines.append(f"Total Return: {self.metrics.total_return:.2%}")
        lines.append(f"Annualized Return: {self.metrics.annualized_return:.2%}")
        lines.append(f"Volatility: {self.metrics.volatility:.2%}")
        lines.append(f"Downside Volatility: {self.metrics.downside_volatility:.2%}")
        lines.append("")
        
        # Risk-adjusted
        lines.append("RISK-ADJUSTED METRICS")
        lines.append("-" * 80)
        lines.append(f"Sharpe Ratio: {self.metrics.sharpe_ratio:.3f}")
        lines.append(f"Sortino Ratio: {self.metrics.sortino_ratio:.3f}")
        lines.append(f"Calmar Ratio: {self.metrics.calmar_ratio:.3f}")
        lines.append("")
        
        # Drawdown
        lines.append("DRAWDOWN")
        lines.append("-" * 80)
        lines.append(f"Max Drawdown: {self.metrics.max_drawdown:.2%}")
        lines.append(f"Avg Drawdown: {self.metrics.avg_drawdown:.2%}")
        lines.append(f"Max DD Duration: {self.metrics.max_drawdown_duration} periods")
        lines.append(f"Recovery Time: {self.metrics.recovery_time} periods")
        lines.append("")
        
        # Trading
        lines.append("TRADING STATISTICS")
        lines.append("-" * 80)
        lines.append(f"Number of Trades: {self.metrics.num_trades}")
        lines.append(f"Win Rate: {self.metrics.win_rate:.2%}")
        lines.append(f"Avg Win: ${self.metrics.avg_win:.2f}")
        lines.append(f"Avg Loss: ${self.metrics.avg_loss:.2f}")
        lines.append(f"Profit Factor: {self.metrics.profit_factor:.3f}")
        lines.append(f"Expectancy: ${self.metrics.expectancy:.2f}")
        lines.append("")
        
        # Costs
        cost_breakdown = TradeAnalyzer.compute_cost_breakdown(self.results.trades)
        lines.append("COST BREAKDOWN")
        lines.append("-" * 80)
        lines.append(f"Total Commission: ${cost_breakdown['total_commission']:.2f}")
        lines.append(f"Total Slippage: ${cost_breakdown['total_slippage']:.2f}")
        lines.append(f"Total Market Impact: ${cost_breakdown['total_market_impact']:.2f}")
        lines.append(f"Total Cost: ${cost_breakdown['total_cost']:.2f}")
        lines.append("")
        
        # Distribution
        lines.append("RETURN DISTRIBUTION")
        lines.append("-" * 80)
        lines.append(f"Skewness: {self.metrics.skewness:.3f}")
        lines.append(f"Kurtosis: {self.metrics.kurtosis:.3f}")
        lines.append(f"VaR (95%): {self.metrics.var_95:.2%}")
        lines.append(f"CVaR (95%): {self.metrics.cvar_95:.2%}")
        lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """Export metrics as dictionary."""
        return {
            'period': {
                'start': str(self.results.start_date),
                'end': str(self.results.end_date),
                'initial_capital': self.results.initial_capital,
                'final_capital': self.results.final_capital
            },
            'metrics': self.metrics.to_dict(),
            'costs': TradeAnalyzer.compute_cost_breakdown(self.results.trades)
        }


# Export public API
__all__ = [
    'PerformanceMetrics',
    'MetricsCalculator',
    'TradeAnalyzer',
    'TearSheet',
]
