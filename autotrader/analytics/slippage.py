"""
Slippage Decomposition Module
Phase 12: Decompose slippage into Price Impact, Timing Cost, and Opportunity Cost
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import logging

import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class OrderExecution:
    """Order execution details for slippage analysis"""
    order_id: str
    instrument: str
    side: str  # buy, sell
    order_time: datetime
    execution_time: datetime
    order_price: float  # Limit price or decision price
    execution_price: float  # Fill price
    quantity: float
    market_price_at_order: float  # Mid-price when order placed
    market_price_at_execution: float  # Mid-price when filled
    spread_at_order: float  # Bid-ask spread at order time
    spread_at_execution: float  # Bid-ask spread at execution time
    volume_ahead: Optional[float] = None  # Queue position
    market_volatility: Optional[float] = None


@dataclass
class SlippageBreakdown:
    """Decomposition of slippage components"""
    total_slippage_bps: float
    price_impact_bps: float
    timing_cost_bps: float
    opportunity_cost_bps: float
    spread_cost_bps: float
    
    # Metadata
    order_id: str
    instrument: str
    side: str
    quantity: float
    execution_seconds: float


class SlippageAnalyzer:
    """
    Decompose execution slippage into components
    
    Slippage Model:
    Total Slippage = Price Impact + Timing Cost + Opportunity Cost
    
    Price Impact: Market moves against you when you trade (permanent)
    Timing Cost: Market moves while waiting to execute (temporary)
    Opportunity Cost: Unfilled orders when market moves away
    """
    
    def __init__(self):
        """Initialize slippage analyzer"""
        logger.info("Slippage Analyzer initialized")
    
    def decompose_slippage(self, execution: OrderExecution) -> SlippageBreakdown:
        """
        Decompose slippage into components
        
        Args:
            execution: Order execution details
        
        Returns:
            SlippageBreakdown with component analysis
        """
        # Calculate execution time
        execution_seconds = (execution.execution_time - execution.order_time).total_seconds()
        
        # 1. Total Slippage: Difference between decision price and execution price
        total_slippage_bps = self._calculate_total_slippage(execution)
        
        # 2. Spread Cost: Half-spread crossing cost
        spread_cost_bps = self._calculate_spread_cost(execution)
        
        # 3. Price Impact: Permanent market move from your order
        price_impact_bps = self._calculate_price_impact(execution)
        
        # 4. Timing Cost: Market movement while waiting
        timing_cost_bps = self._calculate_timing_cost(execution)
        
        # 5. Opportunity Cost: For partial/unfilled orders (assume fully filled here)
        opportunity_cost_bps = 0.0  # Will be non-zero for partial fills
        
        # Validate decomposition
        expected_total = price_impact_bps + timing_cost_bps + opportunity_cost_bps + spread_cost_bps
        if abs(total_slippage_bps - expected_total) > 1.0:  # Allow 1 bps tolerance
            logger.warning(f"Slippage decomposition mismatch: total={total_slippage_bps:.2f}, "
                         f"sum={expected_total:.2f} bps")
        
        breakdown = SlippageBreakdown(
            total_slippage_bps=total_slippage_bps,
            price_impact_bps=price_impact_bps,
            timing_cost_bps=timing_cost_bps,
            opportunity_cost_bps=opportunity_cost_bps,
            spread_cost_bps=spread_cost_bps,
            order_id=execution.order_id,
            instrument=execution.instrument,
            side=execution.side,
            quantity=execution.quantity,
            execution_seconds=execution_seconds
        )
        
        logger.debug(f"Slippage breakdown for {execution.order_id}: "
                    f"total={total_slippage_bps:.2f} bps "
                    f"(impact={price_impact_bps:.2f}, timing={timing_cost_bps:.2f}, "
                    f"spread={spread_cost_bps:.2f})")
        
        return breakdown
    
    def _calculate_total_slippage(self, execution: OrderExecution) -> float:
        """
        Calculate total slippage in basis points
        
        Args:
            execution: Order execution details
        
        Returns:
            Total slippage in bps
        """
        # Slippage = (Execution Price - Order Price) / Order Price
        # Positive for adverse, negative for favorable
        slippage_pct = (execution.execution_price - execution.order_price) / execution.order_price
        
        # Adjust sign based on side
        if execution.side == 'sell':
            slippage_pct = -slippage_pct  # Selling higher is good, so flip sign
        
        slippage_bps = slippage_pct * 10000
        
        return slippage_bps
    
    def _calculate_spread_cost(self, execution: OrderExecution) -> float:
        """
        Calculate bid-ask spread crossing cost
        
        Args:
            execution: Order execution details
        
        Returns:
            Spread cost in bps
        """
        # Average spread during execution
        avg_spread = (execution.spread_at_order + execution.spread_at_execution) / 2
        
        # Spread cost = half spread (assuming aggressive order)
        spread_cost_pct = (avg_spread / 2) / execution.market_price_at_order
        spread_cost_bps = spread_cost_pct * 10000
        
        return spread_cost_bps
    
    def _calculate_price_impact(self, execution: OrderExecution) -> float:
        """
        Calculate permanent price impact from order
        
        Args:
            execution: Order execution details
        
        Returns:
            Price impact in bps
        """
        # Price impact = permanent market move after execution
        # Approximation: (Mid price after - Mid price before) relative to volume
        
        # Simple model: Impact proportional to order size and volatility
        if execution.market_volatility is None:
            # Fallback: Use market movement as proxy
            market_move = execution.market_price_at_execution - execution.market_price_at_order
            market_move_pct = market_move / execution.market_price_at_order
            
            # Attribute portion to our order (assume we caused 10% of move)
            impact_attribution = 0.1
            price_impact_pct = market_move_pct * impact_attribution
        else:
            # Model: Impact ∝ (Order Size / Daily Volume)^0.5 × Volatility
            # Simplified: Use volatility as proxy
            price_impact_pct = execution.market_volatility * 0.01  # 1% of volatility
        
        # Adjust sign based on side
        if execution.side == 'sell':
            price_impact_pct = -price_impact_pct
        
        price_impact_bps = abs(price_impact_pct * 10000)  # Always positive cost
        
        return price_impact_bps
    
    def _calculate_timing_cost(self, execution: OrderExecution) -> float:
        """
        Calculate timing cost from market movement during execution
        
        Args:
            execution: Order execution details
        
        Returns:
            Timing cost in bps
        """
        # Timing cost = market move during execution time
        market_move = execution.market_price_at_execution - execution.market_price_at_order
        market_move_pct = market_move / execution.market_price_at_order
        
        # If market moved in our favor, timing cost is negative (benefit)
        # If market moved against us, timing cost is positive (cost)
        
        # For buys: price increase is adverse (positive cost)
        # For sells: price decrease is adverse (positive cost)
        if execution.side == 'sell':
            market_move_pct = -market_move_pct
        
        timing_cost_bps = market_move_pct * 10000
        
        return timing_cost_bps
    
    def analyze_batch(self, executions: List[OrderExecution]) -> pd.DataFrame:
        """
        Analyze slippage for multiple executions
        
        Args:
            executions: List of order executions
        
        Returns:
            DataFrame with slippage breakdown
        """
        if not executions:
            return pd.DataFrame()
        
        breakdowns = [self.decompose_slippage(exec) for exec in executions]
        
        data = []
        for breakdown in breakdowns:
            data.append({
                'order_id': breakdown.order_id,
                'instrument': breakdown.instrument,
                'side': breakdown.side,
                'quantity': breakdown.quantity,
                'execution_seconds': breakdown.execution_seconds,
                'total_slippage_bps': breakdown.total_slippage_bps,
                'price_impact_bps': breakdown.price_impact_bps,
                'timing_cost_bps': breakdown.timing_cost_bps,
                'opportunity_cost_bps': breakdown.opportunity_cost_bps,
                'spread_cost_bps': breakdown.spread_cost_bps
            })
        
        df = pd.DataFrame(data)
        
        logger.info(f"Analyzed {len(executions)} executions: "
                   f"avg total slippage = {df['total_slippage_bps'].mean():.2f} bps")
        
        return df
    
    def generate_slippage_report(
        self,
        executions: List[OrderExecution],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Generate comprehensive slippage report
        
        Args:
            executions: List of order executions
            start_date: Report start date
            end_date: Report end date
        
        Returns:
            Dictionary with slippage analysis
        """
        logger.info(f"Generating slippage report: {len(executions)} executions "
                   f"from {start_date} to {end_date}")
        
        df = self.analyze_batch(executions)
        
        if df.empty:
            return {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'summary': {},
                'by_instrument': [],
                'by_side': [],
                'generated_at': datetime.now().isoformat()
            }
        
        # Summary statistics
        summary = {
            'total_executions': len(executions),
            'avg_total_slippage_bps': df['total_slippage_bps'].mean(),
            'median_total_slippage_bps': df['total_slippage_bps'].median(),
            'avg_price_impact_bps': df['price_impact_bps'].mean(),
            'avg_timing_cost_bps': df['timing_cost_bps'].mean(),
            'avg_spread_cost_bps': df['spread_cost_bps'].mean(),
            'avg_execution_seconds': df['execution_seconds'].mean(),
            'impact_pct_of_total': (df['price_impact_bps'].sum() / 
                                   df['total_slippage_bps'].sum() * 100 
                                   if df['total_slippage_bps'].sum() != 0 else 0),
            'timing_pct_of_total': (df['timing_cost_bps'].sum() / 
                                   df['total_slippage_bps'].sum() * 100 
                                   if df['total_slippage_bps'].sum() != 0 else 0),
            'spread_pct_of_total': (df['spread_cost_bps'].sum() / 
                                   df['total_slippage_bps'].sum() * 100 
                                   if df['total_slippage_bps'].sum() != 0 else 0)
        }
        
        # By instrument
        by_instrument = df.groupby('instrument').agg({
            'total_slippage_bps': ['mean', 'median', 'count'],
            'price_impact_bps': 'mean',
            'timing_cost_bps': 'mean',
            'spread_cost_bps': 'mean'
        }).reset_index()
        by_instrument.columns = [
            'instrument', 'avg_slippage', 'median_slippage', 'count',
            'avg_impact', 'avg_timing', 'avg_spread'
        ]
        
        # By side
        by_side = df.groupby('side').agg({
            'total_slippage_bps': ['mean', 'median', 'count'],
            'price_impact_bps': 'mean',
            'timing_cost_bps': 'mean',
            'spread_cost_bps': 'mean'
        }).reset_index()
        by_side.columns = [
            'side', 'avg_slippage', 'median_slippage', 'count',
            'avg_impact', 'avg_timing', 'avg_spread'
        ]
        
        report = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'summary': summary,
            'by_instrument': by_instrument.to_dict('records'),
            'by_side': by_side.to_dict('records'),
            'generated_at': datetime.now().isoformat()
        }
        
        logger.info("Slippage report generated")
        
        return report


def load_executions_from_audit(
    audit_trail,
    start_date: datetime,
    end_date: datetime
) -> List[OrderExecution]:
    """
    Load executions from audit trail
    
    Args:
        audit_trail: Audit trail instance
        start_date: Start date
        end_date: End date
    
    Returns:
        List of OrderExecution objects
    """
    from autotrader.audit import EventType
    
    # Query order and fill events
    orders_df = audit_trail.export_to_dataframe(
        event_type=EventType.ORDER,
        start_time=start_date,
        end_time=end_date
    )
    
    fills_df = audit_trail.export_to_dataframe(
        event_type=EventType.FILL,
        start_time=start_date,
        end_time=end_date
    )
    
    if orders_df.empty or fills_df.empty:
        return []
    
    # TODO: Match orders to fills and extract market data
    # This requires joining orders with fills and market snapshots
    # For now, return empty list - implement based on your data model
    
    logger.warning("load_executions_from_audit not fully implemented - "
                  "requires order-fill matching logic")
    
    return []
