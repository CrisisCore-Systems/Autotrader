"""
Post-Trade Analytics - PnL Attribution
Phase 12: Deep performance attribution by factor, instrument, horizon, and time
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import logging

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade representation for analytics"""
    trade_id: str
    signal_id: str
    instrument: str
    side: str  # buy, sell
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    fees: float
    slippage_bps: float
    holding_period_seconds: float
    features: Dict[str, float]  # Feature values at entry
    regime: Optional[str] = None


class PnLAttributor:
    """
    Decompose PnL by factors, instruments, horizons, and time
    
    Attribution Model:
    Total PnL = Σ (Factor PnL + Residual PnL)
    Factor PnL = Factor Exposure × Factor Return
    """
    
    def __init__(self):
        """Initialize PnL attributor"""
        self.factor_names = [
            'momentum_1h',
            'momentum_4h',
            'mean_reversion_15m',
            'volatility_1h',
            'regime_score',
            'volume_delta',
            'spread_quality'
        ]
        logger.info("PnL Attributor initialized")
    
    def attribute_by_factor(self, trades: List[Trade]) -> pd.DataFrame:
        """
        Decompose PnL by alpha factors
        
        Args:
            trades: List of trades with features
        
        Returns:
            DataFrame with factor attribution
        """
        if not trades:
            return pd.DataFrame()
        
        factor_pnl = {factor: 0.0 for factor in self.factor_names}
        factor_exposure = {factor: [] for factor in self.factor_names}
        
        total_pnl = sum(t.pnl for t in trades)
        
        for trade in trades:
            # Extract factor exposures from features
            for factor in self.factor_names:
                if factor in trade.features:
                    exposure = trade.features[factor]
                    factor_exposure[factor].append(exposure)
                    
                    # Attribute PnL proportionally to factor exposure
                    # PnL contribution = (factor exposure / sum of exposures) × trade PnL
                    total_exposure = sum(abs(trade.features.get(f, 0)) for f in self.factor_names)
                    if total_exposure > 0:
                        factor_pnl[factor] += (abs(exposure) / total_exposure) * trade.pnl
        
        # Create attribution DataFrame
        attribution = pd.DataFrame({
            'factor': self.factor_names,
            'pnl': [factor_pnl[f] for f in self.factor_names],
            'pnl_pct': [factor_pnl[f] / total_pnl * 100 if total_pnl != 0 else 0 
                        for f in self.factor_names],
            'avg_exposure': [np.mean(factor_exposure[f]) if factor_exposure[f] else 0 
                            for f in self.factor_names],
            'trades_count': [len([t for t in trades if f in t.features]) 
                            for f in self.factor_names]
        })
        
        # Add residual PnL (unexplained)
        explained_pnl = attribution['pnl'].sum()
        residual_pnl = total_pnl - explained_pnl
        
        residual_row = pd.DataFrame({
            'factor': ['residual'],
            'pnl': [residual_pnl],
            'pnl_pct': [residual_pnl / total_pnl * 100 if total_pnl != 0 else 0],
            'avg_exposure': [0],
            'trades_count': [len(trades)]
        })
        
        attribution = pd.concat([attribution, residual_row], ignore_index=True)
        attribution = attribution.sort_values('pnl', ascending=False)
        
        logger.info(f"Factor attribution complete: {len(trades)} trades, "
                   f"total PnL ${total_pnl:.2f}")
        
        return attribution
    
    def attribute_by_instrument(self, trades: List[Trade]) -> pd.DataFrame:
        """
        Decompose PnL by instrument
        
        Args:
            trades: List of trades
        
        Returns:
            DataFrame with instrument attribution
        """
        if not trades:
            return pd.DataFrame()
        
        # Group by instrument
        instrument_groups = {}
        for trade in trades:
            if trade.instrument not in instrument_groups:
                instrument_groups[trade.instrument] = []
            instrument_groups[trade.instrument].append(trade)
        
        # Calculate metrics per instrument
        results = []
        for instrument, inst_trades in instrument_groups.items():
            total_pnl = sum(t.pnl for t in inst_trades)
            winning_trades = [t for t in inst_trades if t.pnl > 0]
            losing_trades = [t for t in inst_trades if t.pnl < 0]
            
            gross_profit = sum(t.pnl for t in winning_trades)
            gross_loss = abs(sum(t.pnl for t in losing_trades))
            
            results.append({
                'instrument': instrument,
                'pnl': total_pnl,
                'trades_count': len(inst_trades),
                'win_rate': len(winning_trades) / len(inst_trades) * 100 if inst_trades else 0,
                'profit_factor': gross_profit / gross_loss if gross_loss > 0 else np.inf,
                'avg_pnl_per_trade': total_pnl / len(inst_trades) if inst_trades else 0,
                'avg_holding_period_minutes': np.mean([t.holding_period_seconds / 60 
                                                       for t in inst_trades]),
                'total_fees': sum(t.fees for t in inst_trades)
            })
        
        df = pd.DataFrame(results)
        df = df.sort_values('pnl', ascending=False)
        
        logger.info(f"Instrument attribution complete: {len(instrument_groups)} instruments")
        
        return df
    
    def attribute_by_horizon(self, trades: List[Trade]) -> pd.DataFrame:
        """
        Decompose PnL by holding period
        
        Args:
            trades: List of trades
        
        Returns:
            DataFrame with horizon attribution
        """
        if not trades:
            return pd.DataFrame()
        
        # Define holding period buckets (in seconds)
        horizons = {
            'scalp (<5m)': (0, 300),
            'short (5m-1h)': (300, 3600),
            'medium (1h-4h)': (3600, 14400),
            'long (>4h)': (14400, float('inf'))
        }
        
        # Bucket trades by horizon
        horizon_groups = {h: [] for h in horizons.keys()}
        
        for trade in trades:
            for horizon_name, (min_sec, max_sec) in horizons.items():
                if min_sec <= trade.holding_period_seconds < max_sec:
                    horizon_groups[horizon_name].append(trade)
                    break
        
        # Calculate metrics per horizon
        results = []
        for horizon_name, horizon_trades in horizon_groups.items():
            if not horizon_trades:
                continue
            
            total_pnl = sum(t.pnl for t in horizon_trades)
            winning_trades = [t for t in horizon_trades if t.pnl > 0]
            
            results.append({
                'horizon': horizon_name,
                'pnl': total_pnl,
                'trades_count': len(horizon_trades),
                'win_rate': len(winning_trades) / len(horizon_trades) * 100,
                'avg_pnl_per_trade': total_pnl / len(horizon_trades),
                'avg_holding_minutes': np.mean([t.holding_period_seconds / 60 
                                               for t in horizon_trades]),
                'sharpe_estimate': self._estimate_sharpe(horizon_trades)
            })
        
        df = pd.DataFrame(results)
        
        logger.info(f"Horizon attribution complete: {len(results)} horizons")
        
        return df
    
    def attribute_by_time(self, trades: List[Trade]) -> pd.DataFrame:
        """
        Decompose PnL by time of day and day of week
        
        Args:
            trades: List of trades
        
        Returns:
            DataFrame with time-based attribution
        """
        if not trades:
            return pd.DataFrame()
        
        # Add time features to trades
        trade_data = []
        for trade in trades:
            trade_data.append({
                'pnl': trade.pnl,
                'hour': trade.entry_time.hour,
                'day_of_week': trade.entry_time.strftime('%A'),
                'is_weekend': trade.entry_time.weekday() >= 5
            })
        
        df = pd.DataFrame(trade_data)
        
        # PnL by hour
        hourly_pnl = df.groupby('hour').agg({
            'pnl': ['sum', 'mean', 'count']
        }).reset_index()
        hourly_pnl.columns = ['hour', 'total_pnl', 'avg_pnl', 'trades_count']
        
        # PnL by day of week
        daily_pnl = df.groupby('day_of_week').agg({
            'pnl': ['sum', 'mean', 'count']
        }).reset_index()
        daily_pnl.columns = ['day_of_week', 'total_pnl', 'avg_pnl', 'trades_count']
        
        # Weekend vs weekday
        weekend_pnl = df.groupby('is_weekend').agg({
            'pnl': ['sum', 'mean', 'count']
        }).reset_index()
        weekend_pnl['period'] = weekend_pnl['is_weekend'].map({True: 'weekend', False: 'weekday'})
        weekend_pnl = weekend_pnl[['period', 'pnl']]
        weekend_pnl.columns = ['period', 'total_pnl', 'avg_pnl', 'trades_count']
        
        logger.info("Time-based attribution complete")
        
        return {
            'hourly': hourly_pnl,
            'daily': daily_pnl,
            'weekend_vs_weekday': weekend_pnl
        }
    
    def attribute_by_regime(self, trades: List[Trade]) -> pd.DataFrame:
        """
        Decompose PnL by market regime
        
        Args:
            trades: List of trades with regime labels
        
        Returns:
            DataFrame with regime attribution
        """
        if not trades:
            return pd.DataFrame()
        
        # Group by regime
        regime_groups = {}
        for trade in trades:
            regime = trade.regime if trade.regime else 'unknown'
            if regime not in regime_groups:
                regime_groups[regime] = []
            regime_groups[regime].append(trade)
        
        # Calculate metrics per regime
        results = []
        for regime, regime_trades in regime_groups.items():
            total_pnl = sum(t.pnl for t in regime_trades)
            winning_trades = [t for t in regime_trades if t.pnl > 0]
            
            results.append({
                'regime': regime,
                'pnl': total_pnl,
                'trades_count': len(regime_trades),
                'win_rate': len(winning_trades) / len(regime_trades) * 100,
                'avg_pnl_per_trade': total_pnl / len(regime_trades),
                'sharpe_estimate': self._estimate_sharpe(regime_trades)
            })
        
        df = pd.DataFrame(results)
        df = df.sort_values('pnl', ascending=False)
        
        logger.info(f"Regime attribution complete: {len(regime_groups)} regimes")
        
        return df
    
    def generate_full_attribution_report(
        self,
        trades: List[Trade],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Generate comprehensive attribution report
        
        Args:
            trades: List of trades
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Dictionary with all attribution analyses
        """
        logger.info(f"Generating full attribution report: {len(trades)} trades "
                   f"from {start_date} to {end_date}")
        
        total_pnl = sum(t.pnl for t in trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        report = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'summary': {
                'total_pnl': total_pnl,
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': len(winning_trades) / len(trades) * 100 if trades else 0,
                'profit_factor': sum(t.pnl for t in winning_trades) / abs(sum(t.pnl for t in losing_trades)) if losing_trades else np.inf,
                'avg_pnl_per_trade': total_pnl / len(trades) if trades else 0,
                'sharpe_ratio': self._estimate_sharpe(trades)
            },
            'by_factor': self.attribute_by_factor(trades).to_dict('records'),
            'by_instrument': self.attribute_by_instrument(trades).to_dict('records'),
            'by_horizon': self.attribute_by_horizon(trades).to_dict('records'),
            'by_time': {
                k: v.to_dict('records') 
                for k, v in self.attribute_by_time(trades).items()
            },
            'by_regime': self.attribute_by_regime(trades).to_dict('records'),
            'generated_at': datetime.now().isoformat()
        }
        
        logger.info("Full attribution report generated")
        
        return report
    
    def _estimate_sharpe(self, trades: List[Trade]) -> float:
        """
        Estimate Sharpe ratio from trades
        
        Args:
            trades: List of trades
        
        Returns:
            Estimated Sharpe ratio
        """
        if not trades:
            return 0.0
        
        returns = [t.pnl_pct for t in trades]
        
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming independent trades)
        n_trades_per_year = 365 * 24 * 60 / np.mean([t.holding_period_seconds / 60 for t in trades])
        sharpe = (mean_return / std_return) * np.sqrt(n_trades_per_year)
        
        return sharpe


def load_trades_from_audit(
    audit_trail,
    start_date: datetime,
    end_date: datetime
) -> List[Trade]:
    """
    Load trades from audit trail and convert to Trade objects
    
    Args:
        audit_trail: Audit trail instance
        start_date: Start date for trades
        end_date: End date for trades
    
    Returns:
        List of Trade objects
    """
    from autotrader.audit import EventType
    
    # Query fill events
    fills_df = audit_trail.export_to_dataframe(
        event_type=EventType.FILL,
        start_time=start_date,
        end_time=end_date
    )
    
    if fills_df.empty:
        return []
    
    # TODO: Match fills to entries/exits and create Trade objects
    # This requires more sophisticated logic to pair buy/sell fills
    # For now, return empty list - implement based on your execution model
    
    logger.warning("load_trades_from_audit not fully implemented - "
                  "requires trade matching logic")
    
    return []
