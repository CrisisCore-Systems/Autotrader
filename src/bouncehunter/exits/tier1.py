"""
Tier-1 exit logic: End of Day 1 exit system.

Executes partial exit (30%) at end of first trading day if profit threshold met.
Avoids PDT by only triggering on Day 1 (entry day).
"""

from typing import Dict, Any, Optional
from datetime import datetime, time, timedelta
import logging
import pytz
from zoneinfo import ZoneInfo

from ..data.price_provider import Quote
from .adjustments import AdjustmentCalculator

logger = logging.getLogger(__name__)

# US/Eastern timezone for market hours
EASTERN = ZoneInfo("America/New_York")


class Tier1Exit:
    """
    Tier-1 exit executor: EOD Day 1 @ +5% profit → sell 30%.
    
    Criteria:
    - Must be Day 1 (entry day only)
    - Profit >= threshold (default 5%)
    - Current time within EOD window (default 15:50-15:55 ET)
    - Position has sufficient shares remaining
    
    Attributes:
        config: Exit configuration
        broker: Broker interface for order execution
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        broker: Any = None,
        adjustment_calculator: Optional[AdjustmentCalculator] = None
    ):
        """
        Initialize Tier-1 exit executor.
        
        Args:
            config: Tier-1 configuration dictionary
            broker: Optional broker interface for order execution
            adjustment_calculator: Optional adjustment calculator for dynamic targets
        """
        self.config = config
        self.broker = broker
        self.adjustment_calculator = adjustment_calculator
        self.execution_count = 0
        self.last_execution = None
    
    def should_execute(
        self,
        position: Dict[str, Any],
        current_quote: Quote,
        current_time: Optional[datetime] = None
    ) -> tuple[bool, str]:
        """
        Determine if Tier-1 exit should execute.
        
        Args:
            position: Position dictionary from store
            current_quote: Current market quote
            current_time: Current time (defaults to now in ET)
            
        Returns:
            Tuple of (should_execute: bool, reason: str)
            
        Example:
            >>> tier1 = Tier1Exit(config)
            >>> position = {'ticker': 'INTR', 'entry_price': 10.0, 'entry_date': '2025-10-20'}
            >>> quote = Quote('INTR', 10.50, 10.49, 10.51, datetime.now())
            >>> should_exec, reason = tier1.should_execute(position, quote)
            >>> print(f"Execute: {should_exec}, Reason: {reason}")
        """
        if current_time is None:
            current_time = datetime.now(EASTERN)
        
        # Check if already executed
        exit_tiers = position.get('exit_tiers', {})
        tier1_data = exit_tiers.get('tier1', {})
        if tier1_data.get('executed', False):
            return False, "Tier-1 already executed"
        
        # Check if Day 1
        trading_days = self.count_trading_days(position, current_time)
        min_days = self.config.get('min_trading_days', 1)
        max_days = self.config.get('max_trading_days', 1)
        
        if trading_days < min_days:
            return False, f"Not yet Day {min_days} (currently Day {trading_days})"
        
        if trading_days > max_days:
            return False, f"Past Day {max_days} window (currently Day {trading_days})"
        
        # Check time window (15:50-15:55 ET)
        if not self._is_within_time_window(current_time):
            window_start = self.config.get('time_window_start', '15:50')
            window_end = self.config.get('time_window_end', '15:55')
            return False, f"Outside time window {window_start}-{window_end} ET"
        
        # Get profit threshold (base or adjusted)
        base_threshold = self.config.get('profit_threshold_pct', 5.0)
        threshold = base_threshold
        adjustment_details = None
        
        # Apply intelligent adjustments if calculator available
        if self.adjustment_calculator is not None:
            threshold, adjustment_details = self.adjustment_calculator.adjust_tier1_target(
                base_target=base_threshold,
                current_time=current_time,
                current_vix=None  # Will be fetched by calculator if vix_provider set
            )
            logger.debug(
                f"Tier-1 target adjusted: base={base_threshold:.2f}%, "
                f"adjusted={threshold:.2f}%, details={adjustment_details}"
            )
        
        # Check profit threshold
        entry_price = position.get('entry_price', 0)
        current_price = current_quote.price
        
        if entry_price == 0:
            return False, "Invalid entry price (zero)"
        
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        
        if profit_pct < threshold:
            if adjustment_details:
                return False, (
                    f"Profit {profit_pct:.2f}% < adjusted threshold {threshold:.2f}% "
                    f"(base={base_threshold:.2f}%, vol_adj={adjustment_details.get('volatility_adjustment', 0):.2f}%, "
                    f"time_adj={adjustment_details.get('time_adjustment', 0):.2f}%, "
                    f"regime_adj={adjustment_details.get('regime_adjustment', 0):.2f}%)"
                )
            return False, f"Profit {profit_pct:.2f}% < threshold {threshold}%"
        
        # Check minimum shares remaining
        shares = position.get('shares', 0)
        min_shares = self.config.get('min_shares_remaining', 5)
        exit_pct = self.config.get('exit_percentage', 30.0)
        shares_to_exit = int(shares * (exit_pct / 100))
        
        if shares_to_exit < 1:
            return False, f"Exit amount < 1 share (position: {shares})"
        
        shares_remaining = shares - shares_to_exit
        if shares_remaining < min_shares:
            return False, f"Would leave {shares_remaining} < min {min_shares} shares"
        
        # All criteria met
        reason = (
            f"Day {trading_days}, profit {profit_pct:.2f}% >= {threshold:.2f}%, "
            f"time window OK, exit {shares_to_exit} shares"
        )
        if adjustment_details:
            reason += (
                f" [adjusted from base {base_threshold:.2f}%: "
                f"vol={adjustment_details.get('volatility_adjustment', 0):+.2f}%, "
                f"time={adjustment_details.get('time_adjustment', 0):+.2f}%, "
                f"regime={adjustment_details.get('regime_adjustment', 0):+.2f}%]"
            )
        return True, reason
    
    def count_trading_days(
        self,
        position: Dict[str, Any],
        current_time: Optional[datetime] = None
    ) -> int:
        """
        Count trading days since position entry.
        
        Uses simple calendar day count as proxy for trading days.
        In production, would use pandas_market_calendars for NYSE holidays.
        
        Args:
            position: Position dictionary
            current_time: Current time (defaults to now in ET)
            
        Returns:
            Number of trading days (1-indexed, entry day = Day 1)
            
        Example:
            >>> tier1 = Tier1Exit(config)
            >>> position = {'entry_date': '2025-10-20', 'entry_time': '09:35:00'}
            >>> days = tier1.count_trading_days(position)
            >>> print(f"Day {days}")
        """
        if current_time is None:
            current_time = datetime.now(EASTERN)
        
        # Parse entry timestamp
        entry_date_str = position.get('entry_date', '')
        entry_time_str = position.get('entry_time', '09:30:00')
        
        try:
            # Combine date and time
            entry_datetime_str = f"{entry_date_str} {entry_time_str}"
            entry_dt = datetime.strptime(entry_datetime_str, '%Y-%m-%d %H:%M:%S')
            
            # Make timezone-aware (ET)
            if entry_dt.tzinfo is None:
                entry_dt = entry_dt.replace(tzinfo=EASTERN)
            
            # Calculate calendar days difference
            entry_date = entry_dt.date()
            current_date = current_time.date()
            days_diff = (current_date - entry_date).days
            
            # Day counting: entry day = Day 1, next day = Day 2, etc.
            trading_day = days_diff + 1
            
            return max(1, trading_day)  # Minimum Day 1
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse entry date/time: {e}, assuming Day 1")
            return 1
    
    def execute_exit(
        self,
        position: Dict[str, Any],
        current_quote: Quote,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Execute Tier-1 exit order.
        
        Args:
            position: Position dictionary
            current_quote: Current market quote
            dry_run: If True, simulate order without executing
            
        Returns:
            Exit result dictionary with status, shares_sold, price, etc.
            
        Example:
            >>> result = tier1.execute_exit(position, quote, dry_run=True)
            >>> print(f"Status: {result['status']}, Shares: {result['shares_sold']}")
        """
        ticker = position.get('ticker', 'UNKNOWN')
        shares = position.get('shares', 0)
        exit_pct = self.config.get('exit_percentage', 30.0)
        shares_to_sell = int(shares * (exit_pct / 100))
        
        result = {
            'tier': 'tier1',
            'ticker': ticker,
            'shares_to_sell': shares_to_sell,
            'exit_price': current_quote.price,
            'timestamp': datetime.now(EASTERN).isoformat(),
            'dry_run': dry_run,
            'status': 'pending'
        }
        
        if dry_run:
            result['status'] = 'success_dry_run'
            result['order_id'] = 'DRY_RUN'
            logger.info(
                f"[DRY RUN] Tier-1 exit for {ticker}: "
                f"SELL {shares_to_sell} @ ${current_quote.price:.2f}"
            )
            self.execution_count += 1
            self.last_execution = datetime.now(EASTERN)
            return result
        
        # Real execution
        if self.broker is None:
            result['status'] = 'error'
            result['error'] = 'No broker configured'
            logger.error("Cannot execute Tier-1 exit: no broker configured")
            return result
        
        try:
            # Submit market order
            order = self.broker.submit_order(
                symbol=ticker,
                qty=shares_to_sell,
                side='sell',
                type='market',
                time_in_force='day'
            )
            
            result['status'] = 'success'
            result['order_id'] = order.get('id', 'unknown')
            result['filled_qty'] = order.get('filled_qty', 0)
            result['filled_avg_price'] = order.get('filled_avg_price', current_quote.price)
            
            self.execution_count += 1
            self.last_execution = datetime.now(EASTERN)
            
            logger.info(
                f"Tier-1 exit executed for {ticker}: "
                f"SELL {shares_to_sell} @ ${result['filled_avg_price']:.2f}, "
                f"Order ID: {result['order_id']}"
            )
            
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"Tier-1 exit failed for {ticker}: {e}")
        
        return result
    
    def _is_within_time_window(self, current_time: datetime) -> bool:
        """
        Check if current time is within configured EOD window.
        
        Args:
            current_time: Current time (must be timezone-aware)
            
        Returns:
            True if within window, False otherwise
        """
        # Parse time window from config
        window_start_str = self.config.get('time_window_start', '15:50')
        window_end_str = self.config.get('time_window_end', '15:55')
        
        try:
            window_start = datetime.strptime(window_start_str, '%H:%M').time()
            window_end = datetime.strptime(window_end_str, '%H:%M').time()
        except ValueError as e:
            logger.warning(f"Invalid time window format: {e}, using defaults")
            window_start = time(15, 50)
            window_end = time(15, 55)
        
        current_time_et = current_time.astimezone(EASTERN)
        current_time_only = current_time_et.time()
        
        return window_start <= current_time_only <= window_end
    
    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            'execution_count': self.execution_count,
            'last_execution': self.last_execution.isoformat() if self.last_execution else None
        }
