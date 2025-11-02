"""
Intelligent Profit-Taking Module for Intraday Trading

Implements multiple profit-taking strategies:
1. ATR-based dynamic targets
2. Trailing stops for momentum capture
3. Time-based profit locks
4. Volatility-adjusted exits
5. Partial profit-taking (scale out)

Usage:
    from src.intraday.profit_taker import ProfitTaker, ProfitTakeConfig
    
    config = ProfitTakeConfig(
        initial_target_rr=3.0,  # 3:1 risk-reward
        trailing_activation=1.5,  # Start trailing at 1.5R
        trailing_distance=0.5,  # Trail by 0.5R
    )
    
    profit_taker = ProfitTaker(config)
    
    # On position open
    profit_taker.on_position_open(entry_price=100.0, qty=10, stop_loss=99.0)
    
    # Each bar
    should_exit, reason = profit_taker.check_exit(current_price=102.5, current_bar=50)
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ExitReason(Enum):
    """Exit reason classification."""
    TARGET_HIT = "target_hit"
    TRAILING_STOP = "trailing_stop"
    TIME_STOP = "time_stop"
    PARTIAL_PROFIT = "partial_profit"
    VOLATILITY_EXIT = "volatility_exit"
    RISK_OFF = "risk_off"


@dataclass
class ProfitTakeConfig:
    """Configuration for profit-taking strategy."""
    
    # Target settings
    initial_target_rr: float = 3.0  # Initial risk-reward ratio (3:1)
    use_dynamic_targets: bool = True  # Adjust based on volatility
    min_target_rr: float = 2.0
    max_target_rr: float = 5.0
    
    # Trailing stop settings
    enable_trailing: bool = True
    trailing_activation: float = 1.5  # Start trailing at 1.5R profit
    trailing_distance: float = 0.5  # Trail by 0.5R from peak
    trailing_step: float = 0.25  # Move stop up every 0.25R gain
    
    # Partial profit settings
    enable_partial: bool = True
    partial_exits: List[Tuple[float, float]] = None  # [(profit_level, pct_to_close)]
    
    # Time-based exits
    max_hold_bars: int = 80  # Max bars to hold position (80 min = ~1.5 hours)
    profit_lock_time: int = 40  # After 40 bars, lock in profits
    min_profit_lock: float = 0.5  # Minimum 0.5R profit to lock
    
    # Volatility exits
    enable_volatility_exit: bool = True
    volatility_threshold: float = 2.5  # Exit if volatility spikes 2.5x
    
    def __post_init__(self):
        """Set default partial exits if not provided."""
        if self.partial_exits is None:
            self.partial_exits = [
                (2.0, 0.33),  # Take 1/3 off at 2R
                (3.0, 0.50),  # Take 1/2 of remaining at 3R
            ]


class ProfitTaker:
    """
    Intelligent profit-taking manager.
    
    Tracks position state and determines optimal exit points based on:
    - Price action relative to entry
    - Time in trade
    - Volatility changes
    - Trailing stop logic
    """
    
    def __init__(self, config: ProfitTakeConfig):
        self.config = config
        
        # Position state
        self.entry_price: float = 0.0
        self.initial_qty: int = 0
        self.current_qty: int = 0
        self.stop_loss: float = 0.0
        self.initial_risk: float = 0.0  # $ risk per share
        
        # Target state
        self.take_profit: float = 0.0
        self.trailing_stop: float = 0.0
        self.highest_price: float = 0.0
        self.lowest_price: float = 999999.0
        
        # Timing state
        self.entry_bar: int = 0
        self.bars_held: int = 0
        
        # Volatility tracking
        self.entry_volatility: float = 0.0
        
        # Partial exit tracking
        self.partial_exits_taken: List[float] = []
        
        self.is_long: bool = True
        self.is_active: bool = False
    
    def on_position_open(
        self,
        entry_price: float,
        qty: int,
        stop_loss: float,
        current_bar: int = 0,
        current_volatility: float = 0.0,
    ) -> None:
        """
        Initialize profit-taking logic when position opens.
        
        Args:
            entry_price: Entry price
            qty: Position size (positive=long, negative=short)
            stop_loss: Stop loss price
            current_bar: Current bar number
            current_volatility: Current ATR or volatility measure
        """
        self.entry_price = entry_price
        self.initial_qty = abs(qty)
        self.current_qty = abs(qty)
        self.stop_loss = stop_loss
        self.entry_bar = current_bar
        self.bars_held = 0
        self.entry_volatility = current_volatility
        
        # Determine direction
        self.is_long = qty > 0
        
        # Calculate initial risk per share
        self.initial_risk = abs(entry_price - stop_loss)
        
        if self.initial_risk == 0:
            logger.warning("Zero initial risk - using 0.5% of entry price")
            self.initial_risk = entry_price * 0.005
        
        # Set initial profit target
        target_distance = self.initial_risk * self.config.initial_target_rr
        
        if self.is_long:
            self.take_profit = entry_price + target_distance
            self.highest_price = entry_price
            self.lowest_price = entry_price
            self.trailing_stop = stop_loss
        else:  # Short
            self.take_profit = entry_price - target_distance
            self.highest_price = entry_price
            self.lowest_price = entry_price
            self.trailing_stop = stop_loss
        
        self.partial_exits_taken = []
        self.is_active = True
        
        logger.info(
            f"🎯 Profit taker initialized: "
            f"{'LONG' if self.is_long else 'SHORT'} {self.initial_qty} @ ${entry_price:.2f}, "
            f"SL=${stop_loss:.2f}, TP=${self.take_profit:.2f}, "
            f"Risk=${self.initial_risk:.2f}/share (R={self.config.initial_target_rr})"
        )
    
    def check_exit(
        self,
        current_price: float,
        current_bar: int,
        current_volatility: float = 0.0,
    ) -> Tuple[bool, Optional[ExitReason], float]:
        """
        Check if position should be exited.
        
        Args:
            current_price: Current market price
            current_bar: Current bar number
            current_volatility: Current ATR or volatility measure
        
        Returns:
            (should_exit, exit_reason, exit_qty_pct)
            - should_exit: True if should exit
            - exit_reason: Reason for exit
            - exit_qty_pct: Percentage of position to close (1.0 = full, 0.33 = 1/3)
        """
        if not self.is_active or self.current_qty == 0:
            return False, None, 0.0
        
        self.bars_held = current_bar - self.entry_bar
        
        # Update price extremes
        if self.is_long:
            self.highest_price = max(self.highest_price, current_price)
        else:
            self.lowest_price = min(self.lowest_price, current_price)
        
        # Calculate current R-multiple (profit in terms of initial risk)
        if self.is_long:
            current_profit = current_price - self.entry_price
        else:
            current_profit = self.entry_price - current_price
        
        r_multiple = current_profit / self.initial_risk if self.initial_risk > 0 else 0
        
        # 1. CHECK INITIAL TARGET
        if self._check_target_hit(current_price):
            logger.info(f"✅ Target hit: {r_multiple:.2f}R profit at ${current_price:.2f}")
            return True, ExitReason.TARGET_HIT, 1.0
        
        # 2. CHECK TRAILING STOP
        if self.config.enable_trailing:
            hit_trailing = self._update_and_check_trailing_stop(current_price, r_multiple)
            if hit_trailing:
                logger.info(f"🔒 Trailing stop hit: Locked {r_multiple:.2f}R at ${current_price:.2f}")
                return True, ExitReason.TRAILING_STOP, 1.0
        
        # 3. CHECK PARTIAL EXITS
        if self.config.enable_partial:
            should_partial, partial_pct = self._check_partial_exit(r_multiple)
            if should_partial:
                logger.info(f"💰 Partial exit: Taking {partial_pct*100:.0f}% off at {r_multiple:.2f}R")
                return True, ExitReason.PARTIAL_PROFIT, partial_pct
        
        # 4. CHECK TIME-BASED EXITS
        if self.bars_held >= self.config.max_hold_bars:
            logger.info(f"⏰ Time stop: Held {self.bars_held} bars, closing at {r_multiple:.2f}R")
            return True, ExitReason.TIME_STOP, 1.0
        
        # 5. CHECK PROFIT LOCK (time + minimum profit)
        if self.bars_held >= self.config.profit_lock_time and r_multiple >= self.config.min_profit_lock:
            # Move stop to breakeven + small profit
            if self._lock_profit(current_price, r_multiple):
                logger.info(f"🔐 Profit locked at {r_multiple:.2f}R after {self.bars_held} bars")
                # Don't exit yet, just tightened stop
        
        # 6. CHECK VOLATILITY SPIKE
        if self.config.enable_volatility_exit and current_volatility > 0 and self.entry_volatility > 0:
            vol_ratio = current_volatility / self.entry_volatility
            if vol_ratio >= self.config.volatility_threshold:
                logger.info(f"⚡ Volatility exit: {vol_ratio:.2f}x spike, closing at {r_multiple:.2f}R")
                return True, ExitReason.VOLATILITY_EXIT, 1.0
        
        return False, None, 0.0
    
    def _check_target_hit(self, current_price: float) -> bool:
        """Check if initial profit target is hit."""
        if self.is_long:
            return current_price >= self.take_profit
        else:
            return current_price <= self.take_profit
    
    def _update_and_check_trailing_stop(self, current_price: float, r_multiple: float) -> bool:
        """
        Update trailing stop and check if hit.
        
        Returns:
            True if trailing stop is hit
        """
        # Only activate trailing after minimum profit threshold
        if r_multiple < self.config.trailing_activation:
            return False
        
        # Calculate trailing stop distance
        trail_distance = self.initial_risk * self.config.trailing_distance
        
        if self.is_long:
            # Trail from highest price
            new_trailing_stop = self.highest_price - trail_distance
            
            # Only move stop up (never down)
            if new_trailing_stop > self.trailing_stop:
                self.trailing_stop = new_trailing_stop
            
            # Check if hit
            return current_price <= self.trailing_stop
        else:  # Short
            # Trail from lowest price
            new_trailing_stop = self.lowest_price + trail_distance
            
            # Only move stop down (never up)
            if new_trailing_stop < self.trailing_stop:
                self.trailing_stop = new_trailing_stop
            
            # Check if hit
            return current_price >= self.trailing_stop
    
    def _check_partial_exit(self, r_multiple: float) -> Tuple[bool, float]:
        """
        Check if should take partial profits.
        
        Returns:
            (should_exit, exit_percentage)
        """
        for profit_level, exit_pct in self.config.partial_exits:
            if profit_level not in self.partial_exits_taken and r_multiple >= profit_level:
                self.partial_exits_taken.append(profit_level)
                
                # Update current quantity
                qty_to_close = int(self.current_qty * exit_pct)
                self.current_qty -= qty_to_close
                
                return True, exit_pct
        
        return False, 0.0
    
    def _lock_profit(self, current_price: float, r_multiple: float) -> bool:
        """
        Lock in profits by moving stop to breakeven or better.
        
        Returns:
            True if stop was moved
        """
        lock_distance = self.initial_risk * 0.3  # Lock at +0.3R
        
        if self.is_long:
            new_stop = self.entry_price + lock_distance
            if new_stop > self.trailing_stop:
                self.trailing_stop = new_stop
                return True
        else:  # Short
            new_stop = self.entry_price - lock_distance
            if new_stop < self.trailing_stop:
                self.trailing_stop = new_stop
                return True
        
        return False
    
    def on_position_close(self) -> None:
        """Reset state when position is closed."""
        self.is_active = False
        self.current_qty = 0
        logger.debug("Profit taker deactivated - position closed")
    
    def get_current_state(self) -> dict:
        """Get current state for monitoring/debugging."""
        if not self.is_active:
            return {"active": False}
        
        if self.is_long:
            current_profit = self.highest_price - self.entry_price
        else:
            current_profit = self.entry_price - self.lowest_price
        
        r_multiple = current_profit / self.initial_risk if self.initial_risk > 0 else 0
        
        return {
            "active": True,
            "direction": "LONG" if self.is_long else "SHORT",
            "entry_price": self.entry_price,
            "initial_qty": self.initial_qty,
            "current_qty": self.current_qty,
            "take_profit": self.take_profit,
            "trailing_stop": self.trailing_stop,
            "highest_price": self.highest_price,
            "lowest_price": self.lowest_price,
            "r_multiple": r_multiple,
            "bars_held": self.bars_held,
            "partial_exits_taken": self.partial_exits_taken,
        }
    
    def __repr__(self) -> str:
        if not self.is_active:
            return "ProfitTaker(inactive)"
        
        state = self.get_current_state()
        return (
            f"ProfitTaker("
            f"{state['direction']} {state['current_qty']}/{state['initial_qty']}, "
            f"R={state['r_multiple']:.2f}, "
            f"bars={state['bars_held']}, "
            f"TP=${state['take_profit']:.2f}, "
            f"Trail=${state['trailing_stop']:.2f})"
        )


if __name__ == "__main__":
    """Test profit-taking logic with simulated price movement."""
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Configure profit taker
    config = ProfitTakeConfig(
        initial_target_rr=3.0,
        enable_trailing=True,
        trailing_activation=1.5,
        trailing_distance=0.5,
        enable_partial=True,
        partial_exits=[
            (2.0, 0.50),  # Take 50% off at 2R
        ],
    )
    
    profit_taker = ProfitTaker(config)
    
    # Simulate long position
    print("\n=== Testing LONG Position ===")
    profit_taker.on_position_open(
        entry_price=100.0,
        qty=100,
        stop_loss=99.0,
        current_bar=0,
        current_volatility=1.0,
    )
    
    # Simulate price movement
    prices = [
        (100.5, 10),   # +0.5R
        (101.0, 20),   # +1.0R
        (101.5, 30),   # +1.5R (trailing activates)
        (102.0, 40),   # +2.0R (partial exit)
        (102.5, 50),   # +2.5R
        (103.0, 60),   # +3.0R (target hit)
    ]
    
    for price, bar in prices:
        should_exit, reason, qty_pct = profit_taker.check_exit(price, bar, 1.0)
        state = profit_taker.get_current_state()
        print(f"\nBar {bar}: ${price:.2f} | R={state['r_multiple']:.2f}")
        print(f"  State: {profit_taker}")
        
        if should_exit:
            print(f"  ✅ EXIT: {reason.value} ({qty_pct*100:.0f}% of position)")
            if qty_pct == 1.0:
                profit_taker.on_position_close()
                break
    
    print("\n=== Testing SHORT Position ===")
    profit_taker.on_position_open(
        entry_price=100.0,
        qty=-100,
        stop_loss=101.0,
        current_bar=0,
        current_volatility=1.0,
    )
    
    # Simulate price movement (down)
    prices = [
        (99.5, 10),    # +0.5R
        (99.0, 20),    # +1.0R
        (98.5, 30),    # +1.5R (trailing activates)
        (98.0, 40),    # +2.0R (partial exit)
        (97.5, 50),    # +2.5R
        (97.0, 60),    # +3.0R (target hit)
    ]
    
    for price, bar in prices:
        should_exit, reason, qty_pct = profit_taker.check_exit(price, bar, 1.0)
        state = profit_taker.get_current_state()
        print(f"\nBar {bar}: ${price:.2f} | R={state['r_multiple']:.2f}")
        print(f"  State: {profit_taker}")
        
        if should_exit:
            print(f"  ✅ EXIT: {reason.value} ({qty_pct*100:.0f}% of position)")
            if qty_pct == 1.0:
                profit_taker.on_position_close()
                break
