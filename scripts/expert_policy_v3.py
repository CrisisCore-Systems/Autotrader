"""
Production-Ready Safe Expert with Full Instrumentation

Changes from v2:
- Full rejection reason tracking (spread, cooldown, RSI, imbalance, time, stop)
- Relaxed gates (p99.5 spread, min 4-tick stop, T-10m cutoff)
- Epsilon exploration (8% fallback entries when safe)
- Force-close all positions at episode end
- Discard empty episodes (<2 trades)
- Verbose logging of first 3 trades
- Balance tracking (candidates vs entries)
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field
from collections import deque
import logging

from src.intraday.data_pipeline import IntradayDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures

logger = logging.getLogger(__name__)


@dataclass
class ExpertStats:
    """Track entry rejection reasons."""
    candidates: int = 0
    entered: int = 0
    exit_forced: int = 0
    
    # Rejection reasons
    blocked_spread: int = 0
    blocked_cooldown: int = 0
    blocked_rsi: int = 0
    blocked_imbalance: int = 0
    blocked_time: int = 0
    blocked_stop_tight: int = 0
    blocked_no_signal: int = 0
    
    # Trade outcomes
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    
    def summary(self) -> str:
        entry_rate = 100 * self.entered / max(1, self.candidates)
        win_rate = 100 * self.wins / max(1, self.wins + self.losses)
        return (
            f"Candidates: {self.candidates} | Entered: {self.entered} ({entry_rate:.1f}%) | "
            f"Wins: {self.wins} | Losses: {self.losses} | Hit Rate: {win_rate:.1f}% | "
            f"PnL: ${self.total_pnl:.2f}\n"
            f"  Blocked: spread={self.blocked_spread} cooldown={self.blocked_cooldown} "
            f"rsi={self.blocked_rsi} imb={self.blocked_imbalance} "
            f"time={self.blocked_time} stop={self.blocked_stop_tight} "
            f"no_signal={self.blocked_no_signal}"
        )


@dataclass
class RelaxedExpertConfig:
    """Aggressively relaxed configuration to fish for profitable entries (v3.3 - MAX RELAXATION)."""
    
    # Risk management
    risk_per_trade_pct: float = 0.25
    min_stop_ticks: int = 1  # Reduced from 2
    max_stop_ticks: int = 30
    atr_multiplier: float = 10.0  # Increased from 0.5 to allow much wider stops
    
    # Filters (MAX RELAXATION)
    spread_percentile: float = 0.9999  # Increased from 0.999
    max_rsi_long: float = 70  # Tightened from 90 - require oversold for longs
    min_rsi_short: float = 30  # Tightened from 10 - require overbought for shorts
    min_imbalance_strength: float = 0.01  # Increased from 0.001 - require stronger imbalance
    rsi_soft_band: float = 10.0  # Tightened from 20.0 - smaller soft allowance
    rsi_soft_allow: float = 0.6  # Reduced from 0.8 - lower soft allow probability
    spread_soft_allow: float = 0.7  # Increased from 0.5
    spread_soft_ticks: float = 0.02  # Increased from 0.01
    imbalance_soft_allow: float = 0.98  # Increased from 0.95
    
    # Cooldowns & timing
    cooldown_after_stop: int = 0  # Reduced from 1
    cooldown_after_target: int = 0  # Reduced from 1
    skip_open_bars: int = 1  # Reduced from 2
    skip_close_minutes: int = 2  # Reduced from 5
    
    # Entry logic
    pullback_threshold: float = -0.002  # Reduced from -0.001
    profit_target_atr: float = 2.0  # Increased from 1.0
    epsilon_entry: float = 0.8  # Increased from 0.5
    max_trades_per_episode: int = 20  # Increased from 15
    min_trades_to_keep_episode: int = 1


class InstrumentedSafeExpert:
    """
    Expert with full instrumentation and relaxed gates.
    
    Guarantees:
    - Records why each candidate was rejected
    - Epsilon exploration for data diversity
    - Force-closes all positions at episode end
    - Discards empty episodes
    - Logs first 3 trades verbosely
    """
    
    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        microstructure: MicrostructureFeatures,
        momentum: MomentumFeatures,
        config: Optional[RelaxedExpertConfig] = None,
        equity: float = 25000.0,
        max_position: int = 300,
    ):
        self.pipeline = pipeline
        self.microstructure = microstructure
        self.momentum = momentum
        self.config = config or RelaxedExpertConfig()
        
        self.equity = equity
        self.max_position = max_position
        
        # State
        self.position = 0
        self.entry_price = 0.0
        self.entry_bar = 0
        self.cooldown_bars = 0
        self.trades_this_episode = 0
        self.verbose_trades_logged = 0
        self.verbose_exits_logged = 0
        
        # Spread/ATR estimates
        self.spread_history = deque(maxlen=100)
        self.atr_history = deque(maxlen=20)
        
        # Stats
        self.stats = ExpertStats()
        
        # Cache
        self._spread_pctls: Optional[np.ndarray] = None

        # Trade logs
        self.trade_history: list[float] = []
        self.episode_trade_pnls: list[float] = []
        self._rejection_debug_count: int = 0
        self._rejection_debug_limit: int = 10
        
    def reset(self):
        """Reset for new episode."""
        self.position = 0
        self.entry_price = 0.0
        self.entry_bar = 0
        self.cooldown_bars = 0
        self.trades_this_episode = 0
        self.verbose_trades_logged = 0
        self.verbose_exits_logged = 0
        self.spread_history.clear()
        self.atr_history.clear()
        self._spread_pctls = None
        self.episode_trade_pnls = []
        self._rejection_debug_count = 0
        
    def get_action(
        self,
        step: int,
        current_price: float,
        observation: np.ndarray,
    ) -> int:
        """
        Get expert action with full rejection tracking.
        
        Returns:
            action: 0=CLOSE, 1=HOLD, 2=SMALL(100), 3=MED(200), 4=LARGE(300)
        """
        # Update estimates and cooldown
        self._update_estimates()
        if self.cooldown_bars > 0:
            self.cooldown_bars -= 1

        # Manage existing position
        if self.position != 0:
            should_exit, reason = self._check_exit(step, current_price)
            if should_exit:
                pnl = (current_price - self.entry_price) * self.position
                self._record_trade(pnl, reason)
                return 0  # CLOSE
            return 1  # HOLD

        # Evaluate new entries
        self.stats.candidates += 1
        ctx = self._get_context(step, current_price)

        can_enter, rejection_reason = self._can_enter(ctx, step)
        if not can_enter:
            if self.stats.candidates <= 10:
                logger.debug(f"[BC] Bar {step}: Rejected - {rejection_reason}")
            return 1  # HOLD

        signal, direction = self._check_signal(ctx, step)
        if not signal:
            self.stats.blocked_no_signal += 1
            if (np.random.rand() < self.config.epsilon_entry and
                    self.trades_this_episode < self.config.max_trades_per_episode):
                direction = 1 if ctx['ret_from_vwap'] <= 0 else -1
                signal = True
                logger.debug(f"[BC] Bar {step}: Epsilon exploration entry (bias={direction})")

        if signal and direction != 0:
            shares = self._calculate_position_size(ctx)
            if shares >= 1:
                self.position = shares * direction
                self.entry_price = current_price
                self.entry_bar = step
                self.trades_this_episode += 1
                self.stats.entered += 1

                if self.verbose_trades_logged < 3:
                    logger.info(
                        f"[BC DEMO {self.verbose_trades_logged+1}] "
                        f"Bar {step}: {'LONG' if direction > 0 else 'SHORT'} "
                        f"{shares} shares @ ${current_price:.2f} | "
                        f"Stop: {ctx['stop_ticks']} ticks | "
                        f"Spread: {ctx['spread']:.4f} | "
                        f"RSI: {ctx['rsi']:.1f} | "
                        f"Risk: ${ctx['risk_dollars']:.2f}"
                    )
                    self.verbose_trades_logged += 1

                if shares <= 100:
                    return 2  # SMALL
                elif shares <= 200:
                    return 3  # MED
                else:
                    return 4  # LARGE

        return 1  # HOLD
    
    def _can_enter(self, ctx: Dict, step: int) -> Tuple[bool, str]:
        """Check all entry gates and return rejection reason."""
        if ctx['spread'] > ctx['spread_p995']:
            soft_limit = ctx['spread_p995'] + self.config.spread_soft_ticks
            if ctx['spread'] <= soft_limit and np.random.rand() < self.config.spread_soft_allow:
                pass
            else:
                self.stats.blocked_spread += 1
                self._log_rejection(step, "spread_too_wide", ctx)
                return False, "spread_too_wide"

        if self.cooldown_bars > 0:
            self.stats.blocked_cooldown += 1
            self._log_rejection(step, "cooldown_active", ctx)
            return False, f"cooldown_{self.cooldown_bars}"

        if ctx['bars_since_open'] < self.config.skip_open_bars:
            self.stats.blocked_time += 1
            self._log_rejection(step, "too_early", ctx)
            return False, "too_early"

        if ctx['minutes_to_close'] <= self.config.skip_close_minutes:
            self.stats.blocked_time += 1
            self._log_rejection(step, "too_late", ctx)
            return False, "too_late"

        # RSI gating (only if RSI is valid)
        if ctx.get('rsi_valid', True):
            if ctx['rsi'] > self.config.max_rsi_long:
                diff = ctx['rsi'] - self.config.max_rsi_long
                if diff <= self.config.rsi_soft_band and np.random.rand() < self.config.rsi_soft_allow:
                    pass
                else:
                    self.stats.blocked_rsi += 1
                    self._log_rejection(step, "rsi_overbought", ctx)
                    return False, "rsi_overbought"

            if ctx['rsi'] < self.config.min_rsi_short:
                diff = self.config.min_rsi_short - ctx['rsi']
                if diff <= self.config.rsi_soft_band and np.random.rand() < self.config.rsi_soft_allow:
                    pass
                else:
                    self.stats.blocked_rsi += 1
                    self._log_rejection(step, "rsi_oversold", ctx)
                    return False, "rsi_oversold"
        else:
            # RSI not valid yet - reject momentum-based entries
            self.stats.blocked_rsi += 1
            self._log_rejection(step, "rsi_invalid", ctx)
            return False, "rsi_invalid"

        if ctx['stop_ticks'] < self.config.min_stop_ticks:
            self.stats.blocked_stop_tight += 1
            self._log_rejection(step, "stop_too_tight", ctx)
            return False, "stop_too_tight"

        if abs(ctx['imbalance']) < self.config.min_imbalance_strength:
            if np.random.rand() < self.config.imbalance_soft_allow:
                pass
            else:
                self.stats.blocked_imbalance += 1
                self._log_rejection(step, "imbalance_weak", ctx)
                return False, "imbalance_weak"

        if self.trades_this_episode >= self.config.max_trades_per_episode:
            self._log_rejection(step, "max_trades_reached", ctx)
            return False, "max_trades_reached"

        return True, ""

    def _check_signal(self, ctx: Dict, step: int) -> Tuple[bool, int]:
        """Check for entry signal. MORE PERMISSIVE FOR BC."""
        # Epsilon exploration to force entries (increased chance)
        if np.random.rand() < self.config.epsilon_entry:
            direction = 1 if ctx['ret_from_vwap'] <= 0 else -1
            self._log_rejection(step, "epsilon_entry", ctx)
            return True, direction

        # Only check momentum signals if RSI is valid
        if not ctx.get('rsi_valid', False):
            self._log_rejection(step, "rsi_invalid_signal", ctx)
            return False, 0

        # LONG: Pullback below VWAP OR positive imbalance OR acceptable RSI
        long_pullback = ctx['ret_from_vwap'] < self.config.pullback_threshold
        long_imbalance = ctx['imbalance'] > self.config.min_imbalance_strength
        long_rsi = ctx['rsi'] < self.config.max_rsi_long
        
        if long_pullback or long_imbalance or long_rsi:
            return True, 1

        # SHORT: Rally above VWAP OR negative imbalance OR acceptable RSI
        short_rally = ctx['ret_from_vwap'] > -self.config.pullback_threshold
        short_imbalance = ctx['imbalance'] < -self.config.min_imbalance_strength
        short_rsi = ctx['rsi'] > self.config.min_rsi_short
        
        if short_rally or short_imbalance or short_rsi:
            return True, -1

        self._log_rejection(step, "no_signal", ctx)
        return False, 0
    
    def _check_exit(self, step: int, current_price: float) -> Tuple[bool, str]:
        """Check exit conditions."""
        unrealized_pnl = (current_price - self.entry_price) * self.position
        
        # Get context
        bars = self.pipeline.get_latest_bars(20)
        if len(bars) < 5:
            return False, ""
        
        # Estimate ATR
        atr = self._estimate_atr()
        atr_ticks = int(atr / 0.01)
        
        # Profit target (2x ATR)
        target_ticks = int(self.config.profit_target_atr * atr_ticks)
        target_dollars = target_ticks * 0.01 * abs(self.position)
        
        if unrealized_pnl >= target_dollars:
            return True, "profit_target"
        
        # Stop loss (0.5x ATR)
        stop_ticks = max(self.config.min_stop_ticks, int(self.config.atr_multiplier * atr_ticks))
        stop_dollars = stop_ticks * 0.01 * abs(self.position)
        
        if unrealized_pnl <= -stop_dollars:
            return True, "stop_loss"
        
        # Time-based exit (Reduced from 15 to 8 bars for more frequent trading)
        bars_held = step - self.entry_bar
        if bars_held >= 8:
            return True, "time_exit"
        
        return False, ""
    
    def _calculate_position_size(self, ctx: Dict) -> int:
        """Calculate shares with proper risk management."""
        risk_dollars = ctx['risk_dollars']
        stop_ticks = ctx['stop_ticks']
        
        # $ per tick per share
        tick_value = 0.01
        
        # Estimated cost (spread + commission)
        est_cost = ctx['spread'] / 2 + 0.005  # Half spread + $0.005/share
        
        # Stop distance in dollars
        stop_distance = stop_ticks * tick_value
        
        # Shares = risk / (stop + cost)
        shares = int(risk_dollars / (stop_distance + est_cost))
        
        # Clamp to limits
        shares = max(1, min(shares, self.max_position))
        
        return shares
    
    def _get_context(self, step: int, current_price: float) -> Dict:
        """Gather market context."""
        # Get data
        bars = self.pipeline.get_latest_bars(50)
        ticks = self.pipeline.get_latest_ticks(200)
        
        # Compute metrics
        atr = self._estimate_atr()
        spread = self._estimate_spread()
        
        # Get features
        try:
            micro = self.microstructure.compute()
            momentum = self.momentum.compute()
        except:
            micro = np.zeros(15)
            momentum = np.zeros(12)
        
        # Spread percentiles
        if self._spread_pctls is None and len(self.spread_history) >= 20:
            self._spread_pctls = np.percentile(list(self.spread_history), [95, 99, 99.5])
        
        spread_p995 = self._spread_pctls[2] if self._spread_pctls is not None else 0.01
        
        # Stop calculation
        atr_ticks = int(atr / 0.01)
        stop_ticks = max(self.config.min_stop_ticks, 
                        min(self.config.max_stop_ticks, 
                            int(self.config.atr_multiplier * atr_ticks)))
        
        # Risk
        risk_dollars = (self.config.risk_per_trade_pct / 100) * self.equity

        # VWAP/returns computed from raw recent bars (volume-weighted), not momentum features
        if len(bars) >= 5:
            window = bars[-20:] if len(bars) >= 20 else bars
            vol_sum = float(sum(max(0.0, float(getattr(b, 'volume', 0.0))) for b in window))
            if vol_sum > 0:
                vwap_num = float(sum(((getattr(b, 'vwap', 0.0) or (b.close + b.open) / 2.0)) * max(0.0, float(getattr(b, 'volume', 0.0))) for b in window))
                vwap = vwap_num / vol_sum
            else:
                vwap = current_price
        else:
            vwap = current_price
        if not np.isfinite(vwap) or vwap <= 1e-6:
            vwap = current_price
        ret_from_vwap = (current_price - vwap) / vwap if vwap > 0 else 0.0
        ret_from_vwap = float(np.clip(ret_from_vwap, -0.1, 0.1))

        open_price = bars[0].open if len(bars) > 0 else current_price
        ret_from_open = (current_price - open_price) / open_price if open_price > 0 else 0.0
        ret_from_open = float(np.clip(ret_from_open, -0.1, 0.1))

        # Timing
        bars_since_open = len(bars)
        minutes_to_close = max(0, 390 - bars_since_open)

        # RSI handling: mark invalid early/degenerate values as neutral and set a validity flag
        rsi_raw = momentum[4] if len(momentum) > 4 else float("nan")  # RSI is at index 4
        rsi_valid = bool(np.isfinite(rsi_raw)) and (1.0 < float(rsi_raw) < 99.0) and (bars_since_open >= 20)
        rsi = float(rsi_raw) if rsi_valid else 50.0

        return {
            'current_price': current_price,
            'spread': spread,
            'spread_p995': spread_p995,
            'atr': atr,
            'stop_ticks': stop_ticks,
            'risk_dollars': risk_dollars,
            'rsi': rsi,
            'rsi_valid': rsi_valid,
            'imbalance': micro[1] if len(micro) > 1 else 0,
            'vwap': vwap,
            'ret_from_vwap': ret_from_vwap,
            'ret_from_open': ret_from_open,
            'bars_since_open': bars_since_open,
            'minutes_to_close': minutes_to_close,
        }

    def _log_rejection(self, step: int, reason: str, ctx: Dict):
        """Log detailed rejection info for diagnostics (first N occurrences)."""
        if self._rejection_debug_count >= self._rejection_debug_limit:
            return

        self._rejection_debug_count += 1

        logger.warning(
            "[BC DEBUG] Bar %d rejected (%s) | spread=%.6f (p99.5=%.6f) | RSI=%.2f | imbalance=%.3f | ret_vwap=%.4f | ret_open=%.4f | stop_ticks=%d",
            step,
            reason,
            ctx.get('spread', float('nan')),
            ctx.get('spread_p995', float('nan')),
            ctx.get('rsi', float('nan')),
            ctx.get('imbalance', float('nan')),
            ctx.get('ret_from_vwap', float('nan')),
            ctx.get('ret_from_open', float('nan')),
            ctx.get('stop_ticks', -1),
        )
    
    def _update_estimates(self):
        """Update spread and ATR running estimates."""
        ticks = self.pipeline.get_latest_ticks(20)
        if len(ticks) >= 2:
            prices = [t.price for t in ticks[-10:]]
            spread = (max(prices) - min(prices)) / np.mean(prices)
            self.spread_history.append(spread)
        
        bars = self.pipeline.get_latest_bars(20)
        if len(bars) >= 2:
            ranges = [(b.high - b.low) for b in bars[-14:]]
            atr = np.mean(ranges) if ranges else 0.5
            self.atr_history.append(atr)
    
    def _estimate_spread(self) -> float:
        """Estimate current spread."""
        if len(self.spread_history) > 0:
            return float(np.mean(list(self.spread_history)))
        return 0.0001  # 1 bp default
    
    def _estimate_atr(self) -> float:
        """Estimate ATR in dollars."""
        if len(self.atr_history) > 0:
            return float(np.mean(list(self.atr_history)))
        return 0.50  # $0.50 default
    
    def _record_trade(self, pnl: float, reason: str):
        """Record trade outcome."""
        self.stats.total_pnl += pnl
        
        if pnl > 0:
            self.stats.wins += 1
            self.cooldown_bars = self.config.cooldown_after_target
        else:
            self.stats.losses += 1
            self.cooldown_bars = self.config.cooldown_after_stop
        
        self.trade_history.append(pnl)
        self.episode_trade_pnls.append(pnl)

        # Verbose exit log for first 3 trades
        if self.verbose_exits_logged < 3:
            logger.info(
                f"[BC DEMO {self.verbose_exits_logged+1}] "
                f"Exit: {reason} | PnL: ${pnl:.2f} | "
                f"Cooldown: {self.cooldown_bars} bars"
            )
            self.verbose_exits_logged += 1
        
        # Reset position
        self.position = 0
        self.entry_price = 0.0
        self.entry_bar = 0
    
    def force_close_all(self, current_price: float):
        """Force close position at episode end."""
        if self.position != 0:
            pnl = (current_price - self.entry_price) * self.position
            self._record_trade(pnl, "force_eod")
            # Count only truly forced EOD exits here
            self.stats.exit_forced += 1
            logger.info(f"[BC] Forced EOD close: PnL ${pnl:.2f}")
    
    def episode_valid(self) -> bool:
        """Check if episode has enough trades to keep."""
        return self.trades_this_episode >= self.config.min_trades_to_keep_episode
    
    def get_stats_summary(self) -> str:
        """Get formatted stats."""
        return self.stats.summary()
