"""
Position monitor orchestrator for intelligent exit management.

Runs monitoring cycles to check positions against exit tier criteria.
Coordinates price fetching, position updates, and exit execution.

Features:
- Tier-1 and Tier-2 exit execution
- Circuit breaker (pauses after consecutive errors)
- Retry logic with exponential backoff
- Structured JSON logging
- Comprehensive error handling
"""

from typing import Dict, List, Optional, Any
import logging
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import ExitConfig
from .tier1 import Tier1Exit
from .tier2 import Tier2Exit
from .adjustments import MarketConditions, AdjustmentCalculator, SymbolLearner
from ..data.position_store import PositionStore
from ..data.price_provider import PriceProvider, Quote

logger = logging.getLogger(__name__)

# Eastern Time for market hours
EASTERN = ZoneInfo("America/New_York")


class PositionMonitor:
    """
    Orchestrates intelligent exit monitoring and execution.
    
    Monitors active positions, checks tier criteria, executes exits.
    Includes production-grade safety features:
    - Circuit breaker (pauses after 3 consecutive errors)
    - Retry logic with exponential backoff (1s, 2s, 4s)
    - Structured JSON logging for observability
    - Comprehensive error handling
    
    Attributes:
        config: Exit configuration
        position_store: Position storage interface
        price_provider: Price data provider
        broker: Order execution interface
        tier1: Tier-1 exit executor (if enabled)
        tier2: Tier-2 exit executor (if enabled)
    """
    
    def __init__(
        self,
        config: ExitConfig,
        position_store: PositionStore,
        price_provider: PriceProvider,
        broker: Any = None,
        enable_adjustments: bool = True,
        vix_provider: Any = None
    ):
        """
        Initialize position monitor.
        
        Args:
            config: Exit configuration
            position_store: Position storage interface
            price_provider: Price data provider
            broker: Optional broker for order execution
            enable_adjustments: Enable intelligent adjustments (default True)
            vix_provider: Optional VIX data provider for volatility adjustments
        """
        self.config = config
        self.position_store = position_store
        self.price_provider = price_provider
        self.broker = broker
        
        # Initialize intelligence layer (if enabled)
        self.market_conditions = None
        self.adjustment_calculator = None
        self.symbol_learner = None
        
        if enable_adjustments:
            self.market_conditions = MarketConditions(vix_provider=vix_provider)
            self.adjustment_calculator = AdjustmentCalculator(self.market_conditions)
            self.symbol_learner = SymbolLearner()
            logger.info("Intelligent adjustments ENABLED (volatility, time-of-day, regime)")
        else:
            self.market_conditions = None
            self.adjustment_calculator = None
            self.symbol_learner = None
            logger.info("Intelligent adjustments DISABLED (using base targets)")
        
        # Initialize tier executors
        self.tier1 = Tier1Exit(
            config=config.get_tier_config('tier1'),
            broker=broker,
            adjustment_calculator=self.adjustment_calculator
        ) if config.is_tier_enabled('tier1') else None
        
        self.tier2 = Tier2Exit(
            config=config.get_tier_config('tier2'),
            broker=broker,
            price_provider=price_provider,
            adjustment_calculator=self.adjustment_calculator
        ) if config.is_tier_enabled('tier2') else None
        
        # Circuit breaker state
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3
        self._circuit_breaker_active = False
        self._circuit_breaker_cooldown = 300  # 5 minutes
        self._circuit_breaker_triggered_at = None
        
        # Retry configuration
        self._max_retries = 3
        self._retry_delays = [1.0, 2.0, 4.0]  # Exponential backoff
        
        self.stats = {
            'cycles_run': 0,
            'positions_processed': 0,
            'tier1_exits': 0,
            'tier2_exits': 0,
            'errors': 0,
            'circuit_breaker_trips': 0,
            'retries_performed': 0
        }
    
    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """
        Run one monitoring cycle.
        
        Fetches active positions, checks exit criteria, executes exits.
        Includes circuit breaker protection and structured logging.
        
        Returns:
            Cycle statistics (positions_checked, exits_executed, errors)
        """
        cycle_id = f"cycle_{int(time.time())}"
        cycle_start = datetime.now(EASTERN)
        
        self._log_structured({
            'event': 'monitoring_cycle_start',
            'cycle_id': cycle_id,
            'timestamp': cycle_start.isoformat()
        })
        
        cycle_stats = {
            'positions_checked': 0,
            'tier1_exits': 0,
            'tier2_exits': 0,
            'errors': 0,
            'duration_seconds': 0.0,
            'circuit_breaker_active': self._circuit_breaker_active
        }
        
        # Check circuit breaker
        if self._circuit_breaker_active:
            if self._check_circuit_breaker_cooldown():
                self._reset_circuit_breaker()
                self._log_structured({
                    'event': 'circuit_breaker_reset',
                    'cycle_id': cycle_id,
                    'consecutive_errors': self._consecutive_errors
                })
            else:
                self._log_structured({
                    'event': 'circuit_breaker_active',
                    'cycle_id': cycle_id,
                    'message': 'Skipping cycle due to circuit breaker'
                })
                return cycle_stats
        
        try:
            # Get active positions with retry
            positions = self._retry_operation(
                operation=lambda: self.position_store.get_active_positions(),
                operation_name='get_active_positions',
                cycle_id=cycle_id
            )
            
            if positions is None:
                logger.error("Failed to fetch positions after retries")
                self._handle_error(cycle_id, "position_fetch_failed")
                cycle_stats['errors'] += 1
                return cycle_stats
            
            self._log_structured({
                'event': 'positions_fetched',
                'cycle_id': cycle_id,
                'count': len(positions)
            })
            
            # Process each position
            for position in positions:
                try:
                    if self._should_monitor(position):
                        tier1_executed, tier2_executed = self._process_position(position, cycle_id)
                        cycle_stats['positions_checked'] += 1
                        
                        if tier1_executed:
                            cycle_stats['tier1_exits'] += 1
                        if tier2_executed:
                            cycle_stats['tier2_exits'] += 1
                        
                except Exception as e:
                    ticker = position.get('ticker', 'UNKNOWN')
                    self._log_structured({
                        'event': 'position_processing_error',
                        'cycle_id': cycle_id,
                        'ticker': ticker,
                        'error': str(e),
                        'error_type': type(e).__name__
                    }, level='error')
                    cycle_stats['errors'] += 1
                    self._handle_error(cycle_id, f"processing_{ticker}")
            
            # Success - reset error counter
            self._consecutive_errors = 0
            
            # Update global stats
            self.stats['cycles_run'] += 1
            self.stats['positions_processed'] += cycle_stats['positions_checked']
            self.stats['tier1_exits'] += cycle_stats['tier1_exits']
            self.stats['tier2_exits'] += cycle_stats['tier2_exits']
            
            # Calculate duration
            cycle_end = datetime.now(EASTERN)
            duration = (cycle_end - cycle_start).total_seconds()
            cycle_stats['duration_seconds'] = duration
            
            self._log_structured({
                'event': 'monitoring_cycle_complete',
                'cycle_id': cycle_id,
                'stats': cycle_stats,
                'duration_seconds': duration
            })
            
        except Exception as e:
            self._log_structured({
                'event': 'monitoring_cycle_error',
                'cycle_id': cycle_id,
                'error': str(e),
                'error_type': type(e).__name__
            }, level='error')
            cycle_stats['errors'] += 1
            self._handle_error(cycle_id, "cycle_critical")
        
        return cycle_stats
    
    def _should_monitor(self, position: Dict) -> bool:
        """
        Determine if position should be monitored.
        
        Skip positions where all enabled tiers already executed.
        
        Args:
            position: Position dictionary from store
            
        Returns:
            True if should monitor, False otherwise
        """
        exit_tiers = position.get('exit_tiers', {})
        
        # Check Tier-1
        if self.tier1 is not None:
            if 'tier1' not in exit_tiers:
                return True
        
        # Check Tier-2
        if self.tier2 is not None:
            if 'tier2' not in exit_tiers:
                return True
        
        # All enabled tiers executed
        ticker = position.get('ticker', 'UNKNOWN')
        logger.debug(f"Skipping {ticker}: all tiers executed")
        return False
    
    def _process_position(self, position: Dict, cycle_id: str) -> tuple[bool, bool]:
        """
        Process a single position for exit criteria.
        
        Checks Tier-1 and Tier-2 criteria and executes exits.
        
        Args:
            position: Position dictionary from store
            cycle_id: Unique cycle identifier for logging
            
        Returns:
            Tuple of (tier1_executed: bool, tier2_executed: bool)
        """
        ticker = position.get('ticker', 'UNKNOWN')
        tier1_executed = False
        tier2_executed = False
        
        self._log_structured({
            'event': 'position_processing_start',
            'cycle_id': cycle_id,
            'ticker': ticker,
            'entry_price': position.get('entry_price'),
            'shares': position.get('shares')
        }, level='debug')
        
        # Get current price (with retry)
        quote = self._retry_operation(
            operation=lambda: self.price_provider.get_quote(ticker),
            operation_name=f'get_quote_{ticker}',
            cycle_id=cycle_id
        )
        
        if quote is None:
            self._log_structured({
                'event': 'quote_fetch_failed',
                'cycle_id': cycle_id,
                'ticker': ticker
            }, level='error')
            return tier1_executed, tier2_executed
        
        current_time = datetime.now(EASTERN)
        
        # Check Tier-1 criteria (if enabled and not yet executed)
        if self.tier1 and 'tier1' not in position.get('exit_tiers', {}):
            tier1_executed = self._process_tier1(position, quote, current_time, cycle_id)
        
        # Check Tier-2 criteria (if enabled and not yet executed)
        if self.tier2 and 'tier2' not in position.get('exit_tiers', {}):
            tier2_executed = self._process_tier2(position, quote, current_time, cycle_id)
        
        return tier1_executed, tier2_executed
    
    def _process_tier1(
        self,
        position: Dict,
        quote: Quote,
        current_time: datetime,
        cycle_id: str
    ) -> bool:
        """
        Process Tier-1 exit logic for a position.
        
        Args:
            position: Position dictionary
            quote: Current price quote
            current_time: Current timestamp
            cycle_id: Unique cycle identifier
            
        Returns:
            True if Tier-1 exit executed, False otherwise
        """
        ticker = position.get('ticker', 'UNKNOWN')
        
        try:
            should_exec, reason = self.tier1.should_execute(position, quote, current_time)
            
            if should_exec:
                self._log_structured({
                    'event': 'tier1_triggered',
                    'cycle_id': cycle_id,
                    'ticker': ticker,
                    'reason': reason,
                    'price': quote.price
                })
                
                # Execute exit (dry-run based on config)
                dry_run = self.config.get('safety', 'dry_run_mode', default=False)
                result = self.tier1.execute_exit(position, quote, dry_run=dry_run)
                
                if result['status'] == 'success':
                    # Update position in store
                    exit_data = {
                        'exit_tiers': position.get('exit_tiers', {})
                    }
                    exit_data['exit_tiers']['tier1'] = {
                        'exit_price': result['exit_price'],
                        'shares_sold': result['shares_sold'],
                        'timestamp': result['timestamp'],
                        'order_id': result.get('order_id'),
                        'dry_run': dry_run
                    }
                    
                    # Update shares remaining
                    new_shares = position.get('shares', 0) - result['shares_sold']
                    exit_data['shares'] = new_shares
                    
                    self.position_store.update_position(ticker, exit_data)
                    
                    # Record for symbol learning
                    self._record_symbol_learning(position, result['exit_price'], 'tier1')
                    
                    self._log_structured({
                        'event': 'tier1_executed',
                        'cycle_id': cycle_id,
                        'ticker': ticker,
                        'shares_sold': result['shares_sold'],
                        'exit_price': result['exit_price'],
                        'shares_remaining': new_shares,
                        'order_id': result.get('order_id'),
                        'dry_run': dry_run
                    })
                    
                    return True
                else:
                    self._log_structured({
                        'event': 'tier1_execution_failed',
                        'cycle_id': cycle_id,
                        'ticker': ticker,
                        'error': result.get('error', 'Unknown error')
                    }, level='error')
            else:
                logger.debug(f"Tier-1 not triggered for {ticker}: {reason}")
                
        except Exception as e:
            self._log_structured({
                'event': 'tier1_processing_error',
                'cycle_id': cycle_id,
                'ticker': ticker,
                'error': str(e),
                'error_type': type(e).__name__
            }, level='error')
        
        return False
    
    def _process_tier2(
        self,
        position: Dict,
        quote: Quote,
        current_time: datetime,
        cycle_id: str
    ) -> bool:
        """
        Process Tier-2 exit logic for a position.
        
        Args:
            position: Position dictionary
            quote: Current price quote
            current_time: Current timestamp
            cycle_id: Unique cycle identifier
            
        Returns:
            True if Tier-2 exit executed, False otherwise
        """
        ticker = position.get('ticker', 'UNKNOWN')
        
        try:
            should_exec, reason = self.tier2.should_execute(position, quote, current_time)
            
            if should_exec:
                self._log_structured({
                    'event': 'tier2_triggered',
                    'cycle_id': cycle_id,
                    'ticker': ticker,
                    'reason': reason,
                    'price': quote.price
                })
                
                # Update last attempt timestamp (for cooldown)
                position_update = {
                    'exit_tiers': position.get('exit_tiers', {})
                }
                position_update['exit_tiers']['tier2_last_attempt'] = current_time.isoformat()
                self.position_store.update_position(ticker, position_update)
                
                # Execute exit (dry-run based on config)
                dry_run = self.config.get('safety', 'dry_run_mode', default=False)
                result = self.tier2.execute_exit(position, quote, dry_run=dry_run)
                
                if result['status'] == 'success':
                    # Update position in store
                    exit_data = {
                        'exit_tiers': position.get('exit_tiers', {})
                    }
                    exit_data['exit_tiers']['tier2'] = {
                        'exit_price': result['exit_price'],
                        'shares_sold': result['shares_sold'],
                        'timestamp': result['timestamp'],
                        'order_id': result.get('order_id'),
                        'dry_run': dry_run
                    }
                    
                    # Update shares remaining
                    new_shares = position.get('shares', 0) - result['shares_sold']
                    exit_data['shares'] = new_shares
                    
                    self.position_store.update_position(ticker, exit_data)
                    
                    # Record for symbol learning
                    self._record_symbol_learning(position, result['exit_price'], 'tier2')
                    
                    self._log_structured({
                        'event': 'tier2_executed',
                        'cycle_id': cycle_id,
                        'ticker': ticker,
                        'shares_sold': result['shares_sold'],
                        'exit_price': result['exit_price'],
                        'shares_remaining': new_shares,
                        'order_id': result.get('order_id'),
                        'dry_run': dry_run
                    })
                    
                    return True
                else:
                    self._log_structured({
                        'event': 'tier2_execution_failed',
                        'cycle_id': cycle_id,
                        'ticker': ticker,
                        'error': result.get('error', 'Unknown error')
                    }, level='error')
            else:
                logger.debug(f"Tier-2 not triggered for {ticker}: {reason}")
                
        except Exception as e:
            self._log_structured({
                'event': 'tier2_processing_error',
                'cycle_id': cycle_id,
                'ticker': ticker,
                'error': str(e),
                'error_type': type(e).__name__
            }, level='error')
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.
        
        Returns:
            Dictionary with cycles_run, positions_processed, exits, errors
        """
        stats = self.stats.copy()
        stats['circuit_breaker_active'] = self._circuit_breaker_active
        stats['consecutive_errors'] = self._consecutive_errors
        
        # Add tier-specific stats
        if self.tier1:
            tier1_stats = self.tier1.get_stats()
            stats['tier1'] = tier1_stats
        
        if self.tier2:
            tier2_stats = self.tier2.get_stats()
            stats['tier2'] = tier2_stats
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset monitoring statistics (for testing)."""
        self.stats = {
            'cycles_run': 0,
            'positions_processed': 0,
            'tier1_exits': 0,
            'tier2_exits': 0,
            'errors': 0,
            'circuit_breaker_trips': 0,
            'retries_performed': 0
        }
        self._consecutive_errors = 0
        self._circuit_breaker_active = False
        self._circuit_breaker_triggered_at = None
    
    # ========================================================================
    # Safety Feature Helpers
    # ========================================================================
    
    def _retry_operation(
        self,
        operation: callable,
        operation_name: str,
        cycle_id: str
    ) -> Any:
        """
        Retry an operation with exponential backoff.
        
        Args:
            operation: Callable to retry
            operation_name: Name for logging
            cycle_id: Unique cycle identifier
            
        Returns:
            Operation result, or None if all retries failed
        """
        last_error = None
        
        for attempt in range(self._max_retries + 1):
            try:
                result = operation()
                
                # Log successful retry (if not first attempt)
                if attempt > 0:
                    self._log_structured({
                        'event': 'retry_success',
                        'cycle_id': cycle_id,
                        'operation': operation_name,
                        'attempt': attempt + 1
                    })
                
                return result
                
            except Exception as e:
                last_error = e
                
                if attempt < self._max_retries:
                    delay = self._retry_delays[attempt]
                    
                    self._log_structured({
                        'event': 'retry_attempt',
                        'cycle_id': cycle_id,
                        'operation': operation_name,
                        'attempt': attempt + 1,
                        'max_retries': self._max_retries,
                        'delay_seconds': delay,
                        'error': str(e)
                    }, level='warning')
                    
                    self.stats['retries_performed'] += 1
                    time.sleep(delay)
                else:
                    self._log_structured({
                        'event': 'retry_exhausted',
                        'cycle_id': cycle_id,
                        'operation': operation_name,
                        'attempts': attempt + 1,
                        'error': str(e)
                    }, level='error')
        
        return None
    
    def _handle_error(self, cycle_id: str, error_context: str) -> None:
        """
        Handle error occurrence and manage circuit breaker.
        
        Args:
            cycle_id: Unique cycle identifier
            error_context: Context of the error
        """
        self._consecutive_errors += 1
        self.stats['errors'] += 1
        
        if self._consecutive_errors >= self._max_consecutive_errors:
            self._trigger_circuit_breaker(cycle_id, error_context)
    
    def _trigger_circuit_breaker(self, cycle_id: str, error_context: str) -> None:
        """
        Trigger circuit breaker to pause monitoring.
        
        Args:
            cycle_id: Unique cycle identifier
            error_context: Context that triggered the breaker
        """
        self._circuit_breaker_active = True
        self._circuit_breaker_triggered_at = datetime.now(EASTERN)
        self.stats['circuit_breaker_trips'] += 1
        
        self._log_structured({
            'event': 'circuit_breaker_triggered',
            'cycle_id': cycle_id,
            'error_context': error_context,
            'consecutive_errors': self._consecutive_errors,
            'cooldown_seconds': self._circuit_breaker_cooldown,
            'triggered_at': self._circuit_breaker_triggered_at.isoformat()
        }, level='critical')
    
    def _check_circuit_breaker_cooldown(self) -> bool:
        """
        Check if circuit breaker cooldown period has elapsed.
        
        Returns:
            True if cooldown elapsed, False otherwise
        """
        if not self._circuit_breaker_triggered_at:
            return False
        
        elapsed = (datetime.now(EASTERN) - self._circuit_breaker_triggered_at).total_seconds()
        return elapsed >= self._circuit_breaker_cooldown
    
    def _reset_circuit_breaker(self) -> None:
        """Reset circuit breaker state."""
        self._circuit_breaker_active = False
        self._circuit_breaker_triggered_at = None
        self._consecutive_errors = 0
    
    def _log_structured(
        self,
        data: Dict[str, Any],
        level: str = 'info'
    ) -> None:
        """
        Log structured JSON data for observability.
        
        Args:
            data: Dictionary of log data
            level: Log level ('debug', 'info', 'warning', 'error', 'critical')
        """
        # Add common context
        log_data = {
            'timestamp': datetime.now(EASTERN).isoformat(),
            'component': 'PositionMonitor',
            **data
        }
        
        # Convert to JSON string
        log_message = json.dumps(log_data)
        
        # Log at appropriate level
        if level == 'debug':
            logger.debug(log_message)
        elif level == 'info':
            logger.info(log_message)
        elif level == 'warning':
            logger.warning(log_message)
        elif level == 'error':
            logger.error(log_message)
        elif level == 'critical':
            logger.critical(log_message)
        else:
            logger.info(log_message)
    
    def update_market_regime(self, regime: str) -> None:
        """
        Update market regime (BULL/BEAR/SIDEWAYS).
        
        This should be called once per day (typically pre-market)
        after analyzing market conditions (e.g., SPY trend).
        
        Args:
            regime: Market regime ('BULL', 'BEAR', 'SIDEWAYS', or 'UNKNOWN')
        """
        if not self.market_conditions:
            logger.warning("Cannot update regime: adjustments disabled")
            return
        
        from .adjustments import MarketRegime
        
        regime_map = {
            'BULL': MarketRegime.BULL,
            'BEAR': MarketRegime.BEAR,
            'SIDEWAYS': MarketRegime.SIDEWAYS,
            'UNKNOWN': MarketRegime.UNKNOWN
        }
        
        regime_enum = regime_map.get(regime.upper(), MarketRegime.UNKNOWN)
        self.market_conditions.set_market_regime(regime_enum)
        
        self._log_structured({
            'event': 'market_regime_updated',
            'regime': regime.upper(),
            'timestamp': datetime.now(EASTERN).isoformat()
        })
        
        logger.info(f"Market regime updated to: {regime.upper()}")
    
    def _record_symbol_learning(
        self,
        position: Dict,
        exit_price: float,
        tier: str
    ) -> None:
        """
        Record exit for symbol learning.
        
        Args:
            position: Position dictionary
            exit_price: Exit price
            tier: Exit tier ('tier1' or 'tier2')
        """
        if not self.symbol_learner:
            return  # Learning disabled
        
        ticker = position.get('ticker', '')
        entry_price = position.get('entry_price', 0)
        
        if entry_price <= 0:
            return
        
        # Calculate hold days
        entry_date_str = position.get('entry_date', '')
        try:
            from datetime import datetime as dt
            entry_date = dt.strptime(entry_date_str, '%Y-%m-%d').date()
            current_date = datetime.now(EASTERN).date()
            hold_days = (current_date - entry_date).days + 1  # Include entry day
        except:
            hold_days = 1
        
        # Calculate profit
        profit_pct = ((exit_price - entry_price) / entry_price) * 100
        
        # Record exit
        self.symbol_learner.record_exit(
            ticker=ticker,
            entry_price=entry_price,
            exit_price=exit_price,
            hold_days=hold_days,
            tier=tier,
            profit_pct=profit_pct
        )
        
        # Get learning insights
        adjustment = self.symbol_learner.get_symbol_adjustment(ticker)
        if adjustment.get('has_data', False):
            self._log_structured({
                'event': 'symbol_learning_update',
                'ticker': ticker,
                'runner_score': adjustment.get('runner_score', 0),
                'best_exit_tier': adjustment.get('best_exit_tier', 'unknown'),
                'recommendation': adjustment.get('recommendation', '')
            })

