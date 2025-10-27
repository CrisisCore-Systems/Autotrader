"""
Tier-2 Exit Logic: Momentum Spike Detection (Day 2+)

This module implements the Tier-2 exit strategy for PennyHunter positions:
- Triggers on Day 2+ (after Tier-1 window has passed)
- Requires profit in 8-10% range with 2x volume spike
- Sells 40% of position size
- Includes cooldown period (30 min) to prevent rapid re-triggers

Expected Impact:
- Captures momentum breakouts on Day 2+
- Locks in intermediate profits before reversals
- No PDT impact (separate day from entry)
- Contributes to overall WR improvement (70% → 78%)

Author: PennyHunter Pro
Date: 2025-10-20
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from zoneinfo import ZoneInfo

from .adjustments import AdjustmentCalculator

# Eastern Time (NYSE market hours)
EASTERN = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)


class Tier2Exit:
    """
    Tier-2 exit executor for momentum spike detection.
    
    Strategy:
    - Day 2+ positions only (after Tier-1 window)
    - Profit in 8-10% range (not too early, not too late)
    - Volume spike: current_volume >= 2x average volume
    - Cooldown: 30 min between attempts (prevent rapid re-triggers)
    - Exit size: 40% of current position
    
    Example:
        >>> config = ExitConfigManager()
        >>> tier2 = Tier2Exit(config, broker=alpaca_broker, price_provider=alpaca_price)
        >>> 
        >>> position = {
        ...     'ticker': 'INTR',
        ...     'entry_date': '2025-10-19',
        ...     'entry_time': '09:35:00',
        ...     'entry_price': 10.0,
        ...     'shares': 70,  # After Tier-1 sold 30 shares
        ...     'exit_tiers': {'tier1': {'timestamp': '2025-10-19 15:52:00'}}
        ... }
        >>> 
        >>> quote = Quote('INTR', 10.85, 10.84, 10.86, datetime.now(EASTERN))
        >>> 
        >>> should_exec, reason = tier2.should_execute(position, quote)
        >>> if should_exec:
        ...     result = tier2.execute_exit(position, quote, dry_run=False)
        ...     print(f"Sold {result['shares_sold']} shares @ ${result['exit_price']}")
    """

    def __init__(
        self,
        config: Dict[str, Any],
        broker=None,
        price_provider=None,
        adjustment_calculator: Optional[AdjustmentCalculator] = None,
    ):
        """
        Initialize Tier-2 exit executor.
        
        Args:
            config: Tier-2 configuration dictionary
            broker: Broker interface for order execution (optional for dry-run)
            price_provider: Price provider for fetching bars (required for volume analysis)
            adjustment_calculator: Optional adjustment calculator for dynamic targets
        """
        self.config = config
        self.broker = broker
        self.price_provider = price_provider
        self.adjustment_calculator = adjustment_calculator
        
        # Execution statistics
        self._stats = {
            'tier2_exits': 0,
            'volume_spikes_detected': 0,
            'cooldown_blocks': 0,
            'profit_range_misses': 0,
        }
    
    def should_execute(
        self,
        position: Dict,
        quote,
        current_time: Optional[datetime] = None,
    ) -> Tuple[bool, str]:
        """
        Determine if Tier-2 exit should execute for this position.
        
        Validation checks (all must pass):
        1. Not already executed (check exit_tiers['tier2'])
        2. Day 2+ validation (min_trading_days >= 2)
        3. Profit in 8-10% range
        4. Volume spike detected (current >= 2x average)
        5. Cooldown period elapsed (30 min since last attempt)
        6. Sufficient shares remaining (>= min_shares)
        
        Args:
            position: Position dict with ticker, entry_date, entry_time, shares, exit_tiers
            quote: Current quote with bid/ask/last
            current_time: Current timestamp (defaults to now in ET)
        
        Returns:
            Tuple of (should_execute: bool, reason: str)
            
        Example:
            >>> should_exec, reason = tier2.should_execute(position, quote)
            >>> if should_exec:
            ...     print(f"EXECUTE: {reason}")
            >>> else:
            ...     print(f"SKIP: {reason}")
        """
        if current_time is None:
            current_time = datetime.now(EASTERN)
        
        ticker = position.get('ticker', 'UNKNOWN')
        exit_tiers = position.get('exit_tiers', {})
        
        # Check 1: Already executed?
        if 'tier2' in exit_tiers:
            return False, f"{ticker}: Tier-2 already executed"
        
        # Check 2: Day 2+ validation
        trading_day = self.count_trading_days(position, current_time)
        min_days = self.config.get('min_trading_days', 2)
        
        if trading_day < min_days:
            return False, f"{ticker}: Day {trading_day} < {min_days} (too early)"
        
        # Check 3: Profit in 8-10% range (with adjustments if available)
        entry_price = position.get('entry_price', 0)
        current_price = quote.price
        
        if entry_price <= 0:
            return False, f"{ticker}: Invalid entry_price {entry_price}"
        
        profit_pct = ((current_price - entry_price) / entry_price) * 100
        
        # Get base profit range
        base_profit_min = self.config.get('profit_threshold_min', 8.0)
        base_profit_max = self.config.get('profit_threshold_max', 10.0)
        
        profit_min = base_profit_min
        profit_max = base_profit_max
        adjustment_details = None
        
        # Apply intelligent adjustments if calculator available
        if self.adjustment_calculator is not None:
            (profit_min, profit_max), adjustment_details = self.adjustment_calculator.adjust_tier2_target(
                base_min=base_profit_min,
                base_max=base_profit_max,
                current_time=current_time,
                current_vix=None  # Will be fetched by calculator if vix_provider set
            )
            logger.debug(
                f"Tier-2 range adjusted: base={base_profit_min:.2f}-{base_profit_max:.2f}%, "
                f"adjusted={profit_min:.2f}-{profit_max:.2f}%, details={adjustment_details}"
            )
        
        if profit_pct < profit_min:
            self._stats['profit_range_misses'] += 1
            if adjustment_details:
                return False, (
                    f"{ticker}: Profit {profit_pct:.2f}% < {profit_min:.2f}% (adjusted from base {base_profit_min:.2f}%)"
                )
            return False, f"{ticker}: Profit {profit_pct:.2f}% < {profit_min}% (too low)"
        
        if profit_pct > profit_max:
            self._stats['profit_range_misses'] += 1
            if adjustment_details:
                return False, (
                    f"{ticker}: Profit {profit_pct:.2f}% > {profit_max:.2f}% (adjusted from base {base_profit_max:.2f}%)"
                )
            return False, f"{ticker}: Profit {profit_pct:.2f}% > {profit_max}% (too high)"
        
        # Check 4: Volume spike detection
        has_spike, spike_reason = self._detect_volume_spike(position, current_time)
        
        if not has_spike:
            return False, f"{ticker}: {spike_reason}"
        
        # If spike detected, increment stats
        self._stats['volume_spikes_detected'] += 1
        
        # Check 5: Cooldown period
        cooldown_elapsed, cooldown_reason = self._check_cooldown(position, current_time)
        
        if not cooldown_elapsed:
            self._stats['cooldown_blocks'] += 1
            return False, f"{ticker}: {cooldown_reason}"
        
        # Check 6: Sufficient shares remaining
        current_shares = position.get('shares', 0)
        exit_pct = self.config.get('exit_percent', 40.0) / 100.0
        shares_to_sell = int(current_shares * exit_pct)
        shares_remaining = current_shares - shares_to_sell
        
        min_shares = self.config.get('min_shares_remaining', 10)
        
        if shares_remaining < min_shares:
            return False, f"{ticker}: {shares_remaining} shares remaining < {min_shares} minimum"
        
        # All checks passed!
        reason = (
            f"Day {trading_day}, profit {profit_pct:.2f}% in range ({profit_min:.2f}-{profit_max:.2f}%), "
            f"{spike_reason}, cooldown OK, exit {shares_to_sell} shares"
        )
        if adjustment_details:
            reason += (
                f" [adjusted from base {base_profit_min:.2f}-{base_profit_max:.2f}%: "
                f"vol={adjustment_details.get('volatility_adjustment', 0):+.2f}%, "
                f"time={adjustment_details.get('time_adjustment', 0):+.2f}%, "
                f"regime={adjustment_details.get('regime_adjustment', 0):+.2f}%]"
            )
        return True, reason
    
    def count_trading_days(
        self,
        position: Dict,
        current_time: datetime,
    ) -> int:
        """
        Count trading days since entry (1-indexed).
        
        NOTE: This is a calendar day proxy. Production would use
        pandas_market_calendars for NYSE holiday awareness.
        
        Args:
            position: Position with entry_date and entry_time
            current_time: Current timestamp (timezone-aware)
        
        Returns:
            Trading day count (1 = entry day, 2 = next day, etc.)
            Returns 1 if entry date is invalid
            
        Example:
            >>> # Position entered Oct 20, 2025 @ 09:35 ET
            >>> position = {
            ...     'entry_date': '2025-10-20',
            ...     'entry_time': '09:35:00'
            ... }
            >>> 
            >>> # On entry day (Oct 20)
            >>> count = tier2.count_trading_days(position, datetime(2025, 10, 20, 10, 0, tzinfo=EASTERN))
            >>> assert count == 1
            >>> 
            >>> # Next day (Oct 21)
            >>> count = tier2.count_trading_days(position, datetime(2025, 10, 21, 10, 0, tzinfo=EASTERN))
            >>> assert count == 2
        """
        try:
            entry_date = position.get('entry_date', '')
            entry_time = position.get('entry_time', '00:00:00')
            
            # Parse entry datetime
            entry_datetime_str = f"{entry_date} {entry_time}"
            entry_datetime = datetime.strptime(entry_datetime_str, "%Y-%m-%d %H:%M:%S")
            
            # Convert to Eastern timezone
            entry_datetime = entry_datetime.replace(tzinfo=EASTERN)
            
            # Calculate days difference
            delta = current_time.date() - entry_datetime.date()
            
            # Return 1-indexed day count (entry day = 1)
            return delta.days + 1
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid entry date/time in position: {e}. Defaulting to Day 1.")
            return 1
    
    def _detect_volume_spike(
        self,
        position: Dict,
        current_time: datetime,
    ) -> Tuple[bool, str]:
        """
        Detect if current volume is spiking (>= 2x average).
        
        Strategy:
        - Fetch last 30 bars of 1-minute data
        - Calculate average volume (bars 0-29)
        - Compare current bar volume vs average
        - Spike detected if: current_vol >= volume_multiplier * avg_vol
        
        Args:
            position: Position dict with ticker
            current_time: Current timestamp
        
        Returns:
            Tuple of (has_spike: bool, reason: str)
            
        Example:
            >>> # With volume spike
            >>> has_spike, reason = tier2._detect_volume_spike(position, current_time)
            >>> assert has_spike == True
            >>> assert "volume spike" in reason.lower()
        """
        ticker = position.get('ticker', 'UNKNOWN')
        
        # Validate price provider available
        if self.price_provider is None:
            return False, "No price provider (cannot fetch bars)"
        
        try:
            # Fetch last 30 bars of 1-minute data
            lookback_bars = self.config.get('volume_lookback_bars', 30)
            
            bars = self.price_provider.get_bars(
                ticker=ticker,
                timeframe='1Min',
                limit=lookback_bars,
                end_time=current_time,
            )
            
            if not bars or len(bars) < 2:
                return False, f"Insufficient bar data ({len(bars) if bars else 0} bars)"
            
            # Calculate average volume (exclude current bar for comparison)
            volumes = [bar.volume for bar in bars[:-1]]
            avg_volume = sum(volumes) / len(volumes) if volumes else 0
            
            # Get current bar volume
            current_volume = bars[-1].volume
            
            # Check for spike
            volume_multiplier = self.config.get('volume_spike_multiplier', 2.0)
            
            if avg_volume == 0:
                return False, "Average volume is zero"
            
            volume_ratio = current_volume / avg_volume
            
            if volume_ratio >= volume_multiplier:
                return True, f"Volume spike detected ({volume_ratio:.2f}x avg)"
            else:
                return False, f"No spike (current {volume_ratio:.2f}x < {volume_multiplier}x threshold)"
        
        except Exception as e:
            logger.error(f"Error fetching bars for {ticker}: {e}")
            return False, f"Bar fetch error: {str(e)}"
    
    def _check_cooldown(
        self,
        position: Dict,
        current_time: datetime,
    ) -> Tuple[bool, str]:
        """
        Check if cooldown period has elapsed since last Tier-2 attempt.
        
        Prevents rapid re-triggers if position fluctuates in/out of criteria.
        
        Args:
            position: Position with exit_tiers data
            current_time: Current timestamp
        
        Returns:
            Tuple of (cooldown_elapsed: bool, reason: str)
            
        Example:
            >>> # First attempt (no previous tier2_last_attempt)
            >>> elapsed, reason = tier2._check_cooldown(position, current_time)
            >>> assert elapsed == True
            >>> 
            >>> # Within cooldown window
            >>> position['exit_tiers']['tier2_last_attempt'] = (current_time - timedelta(minutes=15)).isoformat()
            >>> elapsed, reason = tier2._check_cooldown(position, current_time)
            >>> assert elapsed == False
            >>> assert "cooldown" in reason.lower()
        """
        exit_tiers = position.get('exit_tiers', {})
        
        # If no previous attempt, cooldown is satisfied
        last_attempt_str = exit_tiers.get('tier2_last_attempt')
        
        if not last_attempt_str:
            return True, "No previous attempt (cooldown OK)"
        
        try:
            # Parse last attempt timestamp
            last_attempt = datetime.fromisoformat(last_attempt_str)
            
            # Ensure timezone-aware
            if last_attempt.tzinfo is None:
                last_attempt = last_attempt.replace(tzinfo=EASTERN)
            
            # Calculate elapsed time
            elapsed = current_time - last_attempt
            
            # Check cooldown period
            cooldown_minutes = self.config.get('cooldown_minutes', 30)
            cooldown_period = timedelta(minutes=cooldown_minutes)
            
            if elapsed >= cooldown_period:
                return True, f"Cooldown elapsed ({elapsed.total_seconds() / 60:.1f} min)"
            else:
                remaining = (cooldown_period - elapsed).total_seconds() / 60
                return False, f"Cooldown active ({remaining:.1f} min remaining)"
        
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid tier2_last_attempt timestamp: {e}. Allowing execution.")
            return True, "Invalid last_attempt (cooldown assumed OK)"
    
    def execute_exit(
        self,
        position: Dict,
        quote,
        dry_run: bool = False,
    ) -> Dict:
        """
        Execute Tier-2 exit (sell 40% at market).
        
        Args:
            position: Position dict
            quote: Current quote
            dry_run: If True, simulate execution (no broker call)
        
        Returns:
            Dict with execution result:
            {
                'status': 'success' | 'error',
                'shares_to_sell': int,
                'shares_sold': int,  # May differ if partial fill
                'exit_price': float,
                'order_id': str,
                'timestamp': str,
                'error': str  # Only if status == 'error'
            }
            
        Example:
            >>> result = tier2.execute_exit(position, quote, dry_run=False)
            >>> if result['status'] == 'success':
            ...     print(f"Sold {result['shares_sold']} @ ${result['exit_price']}")
        """
        ticker = position.get('ticker', 'UNKNOWN')
        current_shares = position.get('shares', 0)
        
        # Calculate shares to sell
        exit_pct = self.config.get('exit_percent', 40.0) / 100.0
        shares_to_sell = int(current_shares * exit_pct)
        
        logger.info(
            f"Tier-2 EXIT: {ticker} - Selling {shares_to_sell}/{current_shares} shares "
            f"@ ${quote.price:.2f} (momentum spike)"
        )
        
        # Dry-run mode: simulate execution
        if dry_run:
            self._stats['tier2_exits'] += 1
            
            return {
                'status': 'success',
                'shares_to_sell': shares_to_sell,
                'shares_sold': shares_to_sell,
                'exit_price': quote.price,
                'order_id': 'DRY_RUN_TIER2',
                'timestamp': datetime.now(EASTERN).isoformat(),
            }
        
        # Real execution: submit market order
        if self.broker is None:
            logger.error(f"Cannot execute {ticker}: No broker configured")
            return {
                'status': 'error',
                'shares_to_sell': shares_to_sell,
                'error': 'No broker configured',
            }
        
        try:
            order = self.broker.submit_order(
                ticker=ticker,
                qty=shares_to_sell,
                side='sell',
                order_type='market',
            )
            
            self._stats['tier2_exits'] += 1
            
            return {
                'status': 'success',
                'shares_to_sell': shares_to_sell,
                'shares_sold': order.get('filled_qty', shares_to_sell),
                'exit_price': order.get('filled_avg_price', quote.price),
                'order_id': order.get('id', 'UNKNOWN'),
                'timestamp': datetime.now(EASTERN).isoformat(),
            }
        
        except Exception as e:
            logger.error(f"Tier-2 exit failed for {ticker}: {e}")
            return {
                'status': 'error',
                'shares_to_sell': shares_to_sell,
                'error': str(e),
            }
    
    def get_stats(self) -> Dict:
        """
        Get execution statistics.
        
        Returns:
            Dict with counters:
            {
                'tier2_exits': int,
                'volume_spikes_detected': int,
                'cooldown_blocks': int,
                'profit_range_misses': int,
            }
        """
        return self._stats.copy()
