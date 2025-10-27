"""
Regime Analysis Module
Phase 12: Analyze strategy performance by market regime
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List
import logging

import pandas as pd
import numpy as np


logger = logging.getLogger(__name__)


class TrendRegime(str, Enum):
    """Trend regime classification"""
    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    SIDEWAYS = "sideways"
    WEAK_DOWNTREND = "weak_downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class VolatilityRegime(str, Enum):
    """Volatility regime classification"""
    VERY_LOW = "very_low_vol"
    LOW = "low_vol"
    NORMAL = "normal_vol"
    HIGH = "high_vol"
    VERY_HIGH = "very_high_vol"


class RiskRegime(str, Enum):
    """Risk appetite regime"""
    RISK_ON = "risk_on"
    RISK_NEUTRAL = "risk_neutral"
    RISK_OFF = "risk_off"


@dataclass
class RegimeLabel:
    """Multi-dimensional regime classification"""
    timestamp: datetime
    instrument: str
    trend: TrendRegime
    volatility: VolatilityRegime
    risk: RiskRegime
    
    # Raw metrics
    trend_score: float  # -1 to 1
    volatility_percentile: float  # 0 to 100
    risk_score: float  # -1 to 1


@dataclass
class RegimePerformance:
    """Performance statistics for a regime"""
    regime_name: str
    trades_count: int
    total_pnl: float
    avg_pnl_per_trade: float
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    avg_holding_minutes: float
    total_exposure_time: float  # Total time in regime (hours)


class RegimeAnalyzer:
    """
    Classify market regimes and analyze strategy performance
    
    Regimes analyzed:
    1. Trend: Strong up/weak up/sideways/weak down/strong down
    2. Volatility: Very low/low/normal/high/very high
    3. Risk: Risk on/neutral/risk off
    """
    
    def __init__(
        self,
        lookback_periods: Dict[str, int] = None
    ):
        """
        Initialize regime analyzer
        
        Args:
            lookback_periods: Lookback windows for regime detection
        """
        self.lookback_periods = lookback_periods or {
            'trend_short': 20,  # 20 bars
            'trend_long': 50,   # 50 bars
            'volatility': 30,   # 30 bars
            'risk': 20          # 20 bars
        }
        logger.info("Regime Analyzer initialized")
    
    def classify_trend_regime(
        self,
        prices: pd.Series,
        timestamp: datetime
    ) -> tuple[TrendRegime, float]:
        """
        Classify trend regime from price series
        
        Args:
            prices: Price time series (indexed by datetime)
            timestamp: Current timestamp
        
        Returns:
            Tuple of (TrendRegime, trend_score)
        """
        # Calculate short and long moving averages
        short_ma = prices.rolling(self.lookback_periods['trend_short']).mean()
        long_ma = prices.rolling(self.lookback_periods['trend_long']).mean()
        
        current_price = prices.loc[timestamp] if timestamp in prices.index else prices.iloc[-1]
        current_short_ma = short_ma.loc[timestamp] if timestamp in short_ma.index else short_ma.iloc[-1]
        current_long_ma = long_ma.loc[timestamp] if timestamp in long_ma.index else long_ma.iloc[-1]
        
        # Trend score: -1 (strong down) to +1 (strong up)
        # Based on: current price vs MAs, short MA vs long MA
        price_to_short = (current_price - current_short_ma) / current_short_ma
        price_to_long = (current_price - current_long_ma) / current_long_ma
        ma_diff = (current_short_ma - current_long_ma) / current_long_ma
        
        trend_score = (price_to_short + price_to_long + ma_diff) / 3
        
        # Classify
        if trend_score > 0.02:
            regime = TrendRegime.STRONG_UPTREND
        elif trend_score > 0.005:
            regime = TrendRegime.WEAK_UPTREND
        elif trend_score > -0.005:
            regime = TrendRegime.SIDEWAYS
        elif trend_score > -0.02:
            regime = TrendRegime.WEAK_DOWNTREND
        else:
            regime = TrendRegime.STRONG_DOWNTREND
        
        return regime, trend_score
    
    def classify_volatility_regime(
        self,
        prices: pd.Series,
        timestamp: datetime
    ) -> tuple[VolatilityRegime, float]:
        """
        Classify volatility regime
        
        Args:
            prices: Price time series
            timestamp: Current timestamp
        
        Returns:
            Tuple of (VolatilityRegime, volatility_percentile)
        """
        # Calculate returns
        returns = prices.pct_change()
        
        # Rolling volatility (annualized)
        rolling_vol = returns.rolling(self.lookback_periods['volatility']).std() * np.sqrt(252 * 24 * 60)
        
        current_vol = rolling_vol.loc[timestamp] if timestamp in rolling_vol.index else rolling_vol.iloc[-1]
        
        # Historical volatility distribution
        vol_percentile = (rolling_vol < current_vol).sum() / len(rolling_vol) * 100
        
        # Classify
        if vol_percentile < 10:
            regime = VolatilityRegime.VERY_LOW
        elif vol_percentile < 30:
            regime = VolatilityRegime.LOW
        elif vol_percentile < 70:
            regime = VolatilityRegime.NORMAL
        elif vol_percentile < 90:
            regime = VolatilityRegime.HIGH
        else:
            regime = VolatilityRegime.VERY_HIGH
        
        return regime, vol_percentile
    
    def classify_risk_regime(
        self,
        market_features: pd.DataFrame,
        timestamp: datetime
    ) -> tuple[RiskRegime, float]:
        """
        Classify risk appetite regime
        
        Args:
            market_features: DataFrame with market indicators
                            (e.g., VIX, credit spreads, correlations)
            timestamp: Current timestamp
        
        Returns:
            Tuple of (RiskRegime, risk_score)
        """
        # Simple risk score: -1 (risk off) to +1 (risk on)
        # Based on available market features
        
        # Example: Use volume, spread, volatility as proxies
        if 'volume_delta' in market_features.columns:
            volume_score = market_features.loc[timestamp, 'volume_delta'] if timestamp in market_features.index else 0
        else:
            volume_score = 0
        
        if 'spread_quality' in market_features.columns:
            spread_score = market_features.loc[timestamp, 'spread_quality'] if timestamp in market_features.index else 0
        else:
            spread_score = 0
        
        # Combine indicators
        risk_score = (volume_score + spread_score) / 2
        
        # Classify
        if risk_score > 0.2:
            regime = RiskRegime.RISK_ON
        elif risk_score > -0.2:
            regime = RiskRegime.RISK_NEUTRAL
        else:
            regime = RiskRegime.RISK_OFF
        
        return regime, risk_score
    
    def label_regime(
        self,
        prices: pd.Series,
        market_features: pd.DataFrame,
        timestamp: datetime,
        instrument: str
    ) -> RegimeLabel:
        """
        Generate full regime label for a timestamp
        
        Args:
            prices: Price time series
            market_features: Market indicators
            timestamp: Current timestamp
            instrument: Instrument identifier
        
        Returns:
            RegimeLabel with multi-dimensional classification
        """
        trend, trend_score = self.classify_trend_regime(prices, timestamp)
        volatility, vol_percentile = self.classify_volatility_regime(prices, timestamp)
        risk, risk_score = self.classify_risk_regime(market_features, timestamp)
        
        label = RegimeLabel(
            timestamp=timestamp,
            instrument=instrument,
            trend=trend,
            volatility=volatility,
            risk=risk,
            trend_score=trend_score,
            volatility_percentile=vol_percentile,
            risk_score=risk_score
        )
        
        return label
    
    def analyze_performance_by_regime(
        self,
        trades: List,  # List of Trade objects from pnl_attribution
        regime_dimension: str = 'trend'
    ) -> pd.DataFrame:
        """
        Analyze performance by regime dimension
        
        Args:
            trades: List of Trade objects with regime labels
            regime_dimension: 'trend', 'volatility', or 'risk'
        
        Returns:
            DataFrame with performance by regime
        """
        if not trades:
            return pd.DataFrame()
        
        # Extract regime values
        regime_values = []
        for trade in trades:
            if trade.regime:
                # Assume regime is stored as "trend:sideways,vol:high,risk:neutral"
                regime_dict = dict(item.split(':') for item in trade.regime.split(','))
                regime_values.append(regime_dict.get(regime_dimension, 'unknown'))
            else:
                regime_values.append('unknown')
        
        # Create DataFrame
        df = pd.DataFrame({
            'regime': regime_values,
            'pnl': [t.pnl for t in trades],
            'pnl_pct': [t.pnl_pct for t in trades],
            'holding_minutes': [t.holding_period_seconds / 60 for t in trades]
        })
        
        # Group by regime
        regime_groups = df.groupby('regime')
        
        # Calculate metrics
        results = []
        for regime_name, group in regime_groups:
            winning_trades = group[group['pnl'] > 0]
            losing_trades = group[group['pnl'] < 0]
            
            gross_profit = winning_trades['pnl'].sum()
            gross_loss = abs(losing_trades['pnl'].sum())
            
            results.append({
                'regime': regime_name,
                'trades_count': len(group),
                'total_pnl': group['pnl'].sum(),
                'avg_pnl_per_trade': group['pnl'].mean(),
                'win_rate': len(winning_trades) / len(group) * 100,
                'profit_factor': gross_profit / gross_loss if gross_loss > 0 else np.inf,
                'sharpe_estimate': self._estimate_sharpe(group['pnl_pct'].tolist()),
                'avg_holding_minutes': group['holding_minutes'].mean()
            })
        
        result_df = pd.DataFrame(results)
        result_df = result_df.sort_values('total_pnl', ascending=False)
        
        logger.info(f"Regime analysis complete: {len(result_df)} {regime_dimension} regimes")
        
        return result_df
    
    def generate_regime_report(
        self,
        trades: List,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Generate comprehensive regime analysis report
        
        Args:
            trades: List of Trade objects with regime labels
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Dictionary with regime analysis
        """
        logger.info(f"Generating regime report: {len(trades)} trades "
                   f"from {start_date} to {end_date}")
        
        report = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'by_trend': self.analyze_performance_by_regime(trades, 'trend').to_dict('records'),
            'by_volatility': self.analyze_performance_by_regime(trades, 'volatility').to_dict('records'),
            'by_risk': self.analyze_performance_by_regime(trades, 'risk').to_dict('records'),
            'generated_at': datetime.now().isoformat()
        }
        
        logger.info("Regime report generated")
        
        return report
    
    def _estimate_sharpe(self, returns: List[float]) -> float:
        """
        Estimate Sharpe ratio from returns
        
        Args:
            returns: List of returns (%)
        
        Returns:
            Estimated Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assume ~100 trades per year)
        sharpe = (mean_return / std_return) * np.sqrt(100)
        
        return sharpe
