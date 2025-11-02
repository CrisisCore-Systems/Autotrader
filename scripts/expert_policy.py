"""
Rule-Based Expert Policy for Behavior Cloning Warm-Start

Gap Strategy:
- Entry: Mean-reversion at k·ATR pullback from VWAP (k=1.5-2.0)
- Exit: MAE/ATR bands (profit target 2×ATR, stop loss 1×ATR)
- Position sizing: Scale by volatility (lower vol → larger size)
- Time filter: No trades first/last 15 minutes

This expert policy generates demonstrations for BC pre-training.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from src.intraday.data_pipeline import IntradayDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures


@dataclass
class ExpertConfig:
    """Configuration for expert policy."""
    entry_atr_threshold: float = 1.5  # Enter at 1.5×ATR from VWAP
    profit_target_atr: float = 2.0    # Take profit at 2×ATR
    stop_loss_atr: float = 1.0        # Stop loss at 1×ATR
    min_position_duration: int = 5    # Min bars to hold (5 minutes)
    max_position_duration: int = 30   # Max bars to hold (30 minutes)
    blackout_start: int = 0           # No trades first 0 minutes (disabled)
    blackout_end: int = 385           # No trades last 5 minutes
    min_spread_bps: float = 1.0       # Min spread 1bp (filter low liquidity)
    max_spread_bps: float = 50.0      # Max spread 50bp (filter wide markets)


class RuleBasedExpert:
    """
    Rule-based expert for generating training demonstrations.
    
    Strategy:
    1. Wait for pullback: price deviates k·ATR from VWAP
    2. Enter with size scaled by inverse volatility
    3. Exit on profit target (2×ATR) or stop loss (1×ATR)
    4. Force exit on time limit or EOD
    
    Returns action probabilities for BC training.
    """
    
    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        microstructure: MicrostructureFeatures,
        momentum: MomentumFeatures,
        config: Optional[ExpertConfig] = None,
    ):
        self.pipeline = pipeline
        self.microstructure = microstructure
        self.momentum = momentum
        self.config = config or ExpertConfig()
        
        # Track position state
        self.position_qty = 0
        self.entry_price = 0.0
        self.entry_step = 0
        self.entry_atr = 0.0
        
    def get_action(
        self,
        current_step: int,
        current_price: float,
        observation: np.ndarray,
    ) -> int:
        """
        Get expert action (0=CLOSE, 1=HOLD, 2=SMALL, 3=MED, 4=LARGE).
        
        Args:
            current_step: Current step in episode (0-390)
            current_price: Current price
            observation: Full 47-dim observation
        
        Returns:
            action: 0-4 discrete action
        """
        # Parse observation (simplified - assumes known structure)
        # In practice, you'd extract these from the observation vector
        features = self.momentum.compute()
        if features is None or len(features) == 0:
            return 1  # HOLD if no data
        
        # Extract key features
        rsi = features[0] if len(features) > 0 else 50.0
        vwap_dev = features[5] if len(features) > 5 else 0.0  # VWAP deviation
        atr = self._estimate_atr()
        spread = self._estimate_spread()
        
        # Check blackout periods
        if current_step < self.config.blackout_start or current_step >= self.config.blackout_end:
            if self.position_qty > 0:
                return 0  # CLOSE before blackout
            return 1  # HOLD during blackout
        
        # Check spread filter (risk control)
        spread_bps = (spread / current_price) * 10000
        if spread_bps < self.config.min_spread_bps or spread_bps > self.config.max_spread_bps:
            if self.position_qty > 0:
                return 0  # CLOSE in bad liquidity
            return 1  # HOLD
        
        # Position management
        if self.position_qty > 0:
            return self._manage_position(current_step, current_price, atr)
        else:
            return self._check_entry(current_step, current_price, rsi, vwap_dev, atr)
    
    def _manage_position(
        self,
        current_step: int,
        current_price: float,
        atr: float,
    ) -> int:
        """Manage existing position - check exits."""
        pnl = (current_price - self.entry_price) * self.position_qty
        pnl_atr = pnl / (self.entry_atr + 1e-8)
        position_duration = current_step - self.entry_step
        
        # Profit target
        if pnl_atr >= self.config.profit_target_atr:
            return 0  # CLOSE - take profit
        
        # Stop loss
        if pnl_atr <= -self.config.stop_loss_atr:
            return 0  # CLOSE - cut loss
        
        # Time-based exit
        if position_duration >= self.config.max_position_duration:
            return 0  # CLOSE - max hold time
        
        # Min holding period
        if position_duration < self.config.min_position_duration:
            return 1  # HOLD - let it run
        
        # Hold if none of the above
        return 1  # HOLD
    
    def _check_entry(
        self,
        current_step: int,
        current_price: float,
        rsi: float,
        vwap_dev: float,
        atr: float,
    ) -> int:
        """Check for entry signals."""
        # Mean reversion signal: price pulled back k·ATR from VWAP
        # vwap_dev is % deviation, so convert to price units
        deviation_price = abs(vwap_dev) * current_price / 100.0
        deviation_atr = deviation_price / (atr + 1e-8)
        
        # Entry conditions
        entry_signal = deviation_atr >= self.config.entry_atr_threshold
        
        # RSI filter (mean reversion bias)
        rsi_oversold = rsi < 35  # Oversold - potential bounce
        rsi_overbought = rsi > 65  # Overbought - potential fade
        
        if entry_signal and (rsi_oversold or rsi_overbought):
            # Size based on volatility (inverse ATR scaling)
            # Low vol → larger size, high vol → smaller size
            atr_pct = atr / current_price
            if atr_pct < 0.005:  # Low vol (<0.5%)
                return 4  # LARGE (300 shares)
            elif atr_pct < 0.01:  # Medium vol (0.5-1%)
                return 3  # MED (200 shares)
            else:  # High vol (>1%)
                return 2  # SMALL (100 shares)
        
        return 1  # HOLD - no signal
    
    def update_position_state(
        self,
        action: int,
        current_step: int,
        current_price: float,
    ):
        """Update internal position tracking after action."""
        if action in [2, 3, 4]:  # Opening position
            qty_map = {2: 100, 3: 200, 4: 300}
            self.position_qty = qty_map[action]
            self.entry_price = current_price
            self.entry_step = current_step
            self.entry_atr = self._estimate_atr()
        
        elif action == 0:  # Closing position
            self.position_qty = 0
            self.entry_price = 0.0
            self.entry_step = 0
            self.entry_atr = 0.0
    
    def _estimate_atr(self) -> float:
        """Estimate ATR from recent bars."""
        bars = self.pipeline.get_latest_bars(14)
        if len(bars) < 2:
            return 1.0  # Default
        
        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i-1].close
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        return np.mean(true_ranges) if true_ranges else 1.0
    
    def _estimate_spread(self) -> float:
        """Estimate spread from tick data."""
        ticks = self.pipeline.get_latest_ticks(100)
        if len(ticks) < 2:
            return 0.01  # Default 1 cent
        
        # Estimate from high-low range
        prices = [t.price for t in ticks]
        spread = (max(prices) - min(prices)) / 2
        return max(spread, 0.01)
    
    def get_action_probabilities(
        self,
        current_step: int,
        current_price: float,
        observation: np.ndarray,
    ) -> np.ndarray:
        """
        Get action probabilities for BC training (one-hot encoding).
        
        Returns:
            probs: 5-dim probability vector (deterministic policy)
        """
        action = self.get_action(current_step, current_price, observation)
        probs = np.zeros(5, dtype=np.float32)
        probs[action] = 1.0
        return probs


def collect_expert_demonstrations(
    expert: RuleBasedExpert,
    env,
    num_episodes: int = 1000,
) -> Dict[str, np.ndarray]:
    """
    Collect expert demonstrations for BC training.
    
    Args:
        expert: RuleBasedExpert policy
        env: Trading environment
        num_episodes: Number of episodes to collect
    
    Returns:
        demonstrations: Dict with 'observations', 'actions', 'rewards'
    """
    observations = []
    actions = []
    rewards = []
    
    for episode in range(num_episodes):
        obs, info = env.reset()
        done = False
        step = 0
        
        while not done:
            current_price = env.pipeline.get_current_price()
            
            # Get expert action
            action = expert.get_action(step, current_price, obs)
            
            # Store demonstration
            observations.append(obs.copy())
            actions.append(action)
            
            # Step environment
            obs, reward, terminated, truncated, info = env.step(action)
            rewards.append(reward)
            
            # Update expert state
            expert.update_position_state(action, step, current_price)
            
            done = terminated or truncated
            step += 1
        
        if (episode + 1) % 100 == 0:
            print(f"Collected {episode + 1}/{num_episodes} episodes")
    
    return {
        'observations': np.array(observations, dtype=np.float32),
        'actions': np.array(actions, dtype=np.int64),
        'rewards': np.array(rewards, dtype=np.float32),
    }


if __name__ == "__main__":
    print("Rule-based expert policy for BC warm-start")
    print("Entry: Mean-reversion at 1.5×ATR pullback from VWAP")
    print("Exit: Profit target 2×ATR, stop loss 1×ATR")
    print("Size: Scaled by inverse volatility")
