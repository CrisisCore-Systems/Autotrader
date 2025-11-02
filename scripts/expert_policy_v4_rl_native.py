"""
RL-Native Expert Policy (v4) - Minimal Hard-Coded Gates

Philosophy:
- Remove hard-coded reject rules for spread, RSI, imbalance
- Let PPO learn optimal thresholds from raw features
- Only keep safety rails: cooldown, timing, max trades
- Focus on generating diverse, realistic demonstrations

Key Changes from v3:
- No spread filtering (feed raw to RL)
- No RSI gates (feed raw to RL)
- No imbalance filtering (feed raw to RL)
- Epsilon exploration increased to 90%
- Simple signal: pullback from VWAP or epsilon
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from collections import deque
import logging

from src.intraday.data_pipeline import IntradayDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures

logger = logging.getLogger(__name__)


@dataclass
class ExpertStats:
    """Track minimal stats."""
    entered: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    
    def summary(self) -> str:
        win_rate = 100 * self.wins / max(1, self.wins + self.losses)
        return (
            f"Entered: {self.entered} | "
            f"Wins: {self.wins} | Losses: {self.losses} | Hit Rate: {win_rate:.1f}% | "
            f"PnL: ${self.total_pnl:.2f}"
        )


@dataclass
class RLNativeConfig:
    """Minimal config - let RL learn the rest."""
    
    # Risk management
    risk_per_trade_pct: float = 0.25
    atr_multiplier: float = 1.5
    tp_multiplier: float = 3.0
    
    # Safety rails (only these are hard-coded)
    cooldown_after_trade: int = 0  # No cooldown
    skip_open_bars: int = 1  # Skip first bar
    skip_close_minutes: int = 5  # Close positions 5 min before EOD
    max_trades_per_episode: int = 20
    min_trades_to_keep_episode: int = 1
    
    # Entry logic
    epsilon_entry: float = 0.9  # 90% epsilon for diverse data
    pullback_threshold: float = -0.001  # Simple VWAP reversion signal


class RLNativeExpert:
    """
    Expert with minimal hard-coded rules.
    
    Goal: Generate diverse demonstrations, let RL learn quality filters.
    """
    
    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        microstructure: MicrostructureFeatures,
        momentum: MomentumFeatures,
        config: Optional[RLNativeConfig] = None,
        equity: float = 25000.0,
        max_position: int = 300,
    ):
        self.pipeline = pipeline
        self.microstructure = microstructure
        self.momentum = momentum
        self.config = config or RLNativeConfig()
        
        self.equity = equity
        self.max_position = max_position
        
        # State
        self.position = 0
        self.entry_price = 0.0
        self.entry_bar = 0
        self.cooldown_bars = 0
        self.trades_this_episode = 0
        
        # ATR tracking
        self.atr_history = deque(maxlen=20)
        
        # Stats
        self.stats = ExpertStats()
        
        # Trade logs
        self.episode_trade_pnls: list[float] = []
        
    def reset(self):
        """Reset for new episode."""
        self.position = 0
        self.entry_price = 0.0
        self.entry_bar = 0
        self.cooldown_bars = 0
        self.trades_this_episode = 0
        self.atr_history.clear()
        self.episode_trade_pnls = []
        
    def get_action(
        self,
        step: int,
        current_price: float,
        observation: np.ndarray,
    ) -> int:
        """
        Get expert action with minimal gates.
        
        Returns:
            action: 0=CLOSE, 1=HOLD, 2=SMALL(100), 3=MED(200), 4=LARGE(300)
        """
        # Update ATR
        self._update_atr()
        
        # Manage existing position
        if self.position != 0:
            should_exit, reason = self._check_exit(step, current_price)
            if should_exit:
                pnl = (current_price - self.entry_price) * self.position
                self._record_trade(pnl, reason)
                return 0  # CLOSE
            return 1  # HOLD

        # Cooldown check (only safety rail)
        if self.cooldown_bars > 0:
            self.cooldown_bars -= 1
            return 1  # HOLD

        # Get context
        ctx = self._get_context(step, current_price)

        # Safety rails only
        if not self._safety_check(ctx, step):
            return 1  # HOLD

        # Simple signal: VWAP reversion or epsilon
        signal, direction = self._check_signal(ctx)
        
        if signal and direction != 0:
            shares = self._calculate_position_size(ctx)
            if shares >= 1:
                self.position = shares * direction
                self.entry_price = current_price
                self.entry_bar = step
                self.trades_this_episode += 1
                self.stats.entered += 1
                
                logger.debug(
                    f"[RL-Expert] Bar {step}: {'LONG' if direction > 0 else 'SHORT'} "
                    f"{shares} shares @ ${current_price:.2f}"
                )
                
                # Return appropriate action
                if shares <= 100:
                    return 2  # SMALL
                elif shares <= 200:
                    return 3  # MED
                else:
                    return 4  # LARGE
        
        return 1  # HOLD

    def _get_context(self, step: int, current_price: float) -> Dict:
        """Build minimal context."""
        bars = self.pipeline.get_latest_bars(20)
        
        if len(bars) < 5:
            return {'valid': False}
        
        # VWAP
        recent_bars = bars[-10:]
        vwap = sum(b.close * b.volume for b in recent_bars) / sum(b.volume for b in recent_bars)
        ret_from_vwap = (current_price - vwap) / vwap if vwap > 0 else 0
        
        # ATR for stop calculation
        atr = np.mean(self.atr_history) if self.atr_history else 0.30
        stop_distance = atr * self.config.atr_multiplier
        stop_ticks = int(stop_distance / 0.01)
        
        # Position sizing
        risk_dollars = self.equity * self.config.risk_per_trade_pct
        shares = int(risk_dollars / stop_distance) if stop_distance > 0 else 100
        shares = min(shares, self.max_position)
        
        # Timing
        bars_since_open = step
        minutes_to_close = 390 - step
        
        return {
            'valid': True,
            'ret_from_vwap': ret_from_vwap,
            'atr': atr,
            'stop_distance': stop_distance,
            'stop_ticks': stop_ticks,
            'shares': shares,
            'bars_since_open': bars_since_open,
            'minutes_to_close': minutes_to_close,
            'risk_dollars': risk_dollars,
        }

    def _safety_check(self, ctx: Dict, step: int) -> bool:
        """Minimal safety rails."""
        if not ctx.get('valid', False):
            return False
        
        # Timing
        if ctx['bars_since_open'] < self.config.skip_open_bars:
            return False
        
        if ctx['minutes_to_close'] <= self.config.skip_close_minutes:
            return False
        
        # Max trades
        if self.trades_this_episode >= self.config.max_trades_per_episode:
            return False
        
        return True

    def _check_signal(self, ctx: Dict) -> Tuple[bool, int]:
        """
        Simple signal: VWAP reversion or epsilon exploration.
        
        No hard-coded quality filters - let RL learn.
        """
        # Epsilon exploration (90% random)
        if np.random.rand() < self.config.epsilon_entry:
            direction = 1 if ctx['ret_from_vwap'] <= 0 else -1
            return True, direction
        
        # VWAP mean reversion
        if ctx['ret_from_vwap'] < self.config.pullback_threshold:
            return True, 1  # LONG on pullback
        
        if ctx['ret_from_vwap'] > -self.config.pullback_threshold:
            return True, -1  # SHORT on rally
        
        return False, 0

    def _check_exit(self, step: int, current_price: float) -> Tuple[bool, str]:
        """Check exit conditions with ATR-based TP/SL."""
        bars_held = step - self.entry_bar
        
        # Calculate PnL
        pnl_per_share = (current_price - self.entry_price) * np.sign(self.position)
        
        # ATR-based TP/SL
        atr = np.mean(self.atr_history) if self.atr_history else 0.30
        stop_distance = atr * self.config.atr_multiplier
        tp_distance = stop_distance * self.config.tp_multiplier
        
        # Take profit
        if pnl_per_share >= tp_distance:
            return True, "take_profit"
        
        # Stop loss
        if pnl_per_share <= -stop_distance:
            return True, "stop_loss"
        
        # Time exit (8 bars = 8 minutes)
        if bars_held >= 8:
            return True, "time_exit"
        
        return False, ""

    def _calculate_position_size(self, ctx: Dict) -> int:
        """Simple position sizing from context."""
        return ctx.get('shares', 100)

    def _update_atr(self):
        """Update ATR history."""
        bars = self.pipeline.get_latest_bars(15)
        
        if len(bars) >= 2:
            bar = bars[-1]
            prev_bar = bars[-2]
            tr = max(
                bar.high - bar.low,
                abs(bar.high - prev_bar.close),
                abs(bar.low - prev_bar.close)
            )
            self.atr_history.append(tr)

    def _record_trade(self, pnl: float, reason: str):
        """Record trade outcome."""
        self.episode_trade_pnls.append(pnl)
        self.stats.total_pnl += pnl
        
        if pnl > 0:
            self.stats.wins += 1
        else:
            self.stats.losses += 1
        
        # Reset position
        self.position = 0
        self.entry_price = 0.0
        self.entry_bar = 0
        self.cooldown_bars = self.config.cooldown_after_trade

    def force_close_all(self, current_price: float):
        """Force close all positions at episode end."""
        if self.position != 0:
            pnl = (current_price - self.entry_price) * self.position
            self._record_trade(pnl, "force_close")
            logger.debug(f"[RL-Expert] Force closed: PnL=${pnl:.2f}")

    def episode_valid(self) -> bool:
        """Check if episode has enough trades."""
        return len(self.episode_trade_pnls) >= self.config.min_trades_to_keep_episode

    def get_stats_summary(self) -> str:
        """Get formatted stats."""
        return self.stats.summary()
