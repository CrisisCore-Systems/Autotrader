"""
Profitable Expert Policy (v5) - For BC Pre-training

Philosophy:
- Use proven mean reversion + momentum confluence
- Strict quality filters for high win rate
- Conservative position sizing
- ATR-based dynamic TP/SL (3:1 R:R)
- Goal: 60%+ win rate, PF > 1.5

Entry Signals:
1. Price pullback from VWAP (>0.2%)
2. RSI oversold (<40) for longs
3. Positive bid-ask flow (orderbook imbalance > 0)
4. Narrow spread (<0.1%)
5. Not at market extremes (skip first/last 30min)

Exit Signals:
1. Take Profit: 3x stop distance (ATR-based)
2. Stop Loss: 1.5x ATR
3. Time exit: 15 bars (15 minutes) max hold
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
    """Track performance metrics."""
    candidates: int = 0
    entered: int = 0
    blocked_spread: int = 0
    blocked_rsi: int = 0
    blocked_imbalance: int = 0
    blocked_timing: int = 0
    blocked_volume: int = 0
    blocked_trend: int = 0
    blocked_volatility: int = 0
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
            f"  Blocked: spread={self.blocked_spread} rsi={self.blocked_rsi} "
            f"imb={self.blocked_imbalance} timing={self.blocked_timing} "
            f"volume={self.blocked_volume} trend={self.blocked_trend} vol={self.blocked_volatility}"
        )


@dataclass
class ProfitableExpertConfig:
    """Conservative config for profitable trading."""
    
    # Risk management
    risk_per_trade_pct: float = 0.20  # Slightly higher risk per trade to get fills
    atr_multiplier: float = 1.5  # SL = 1.5x ATR
    tp_multiplier: float = 3.0  # TP = 3x SL (3:1 R:R)
    
    # Quality filters (strict)
    max_spread_bps: float = 10.0  # 0.1% max spread
    min_rsi_long: float = 30.0  # Allow slightly higher RSI for longs
    max_rsi_long: float = 55.0
    min_imbalance: float = 0.02  # 2% orderbook imbalance
    pullback_threshold: float = 0.001  # 0.1% from VWAP
    epsilon_entry: float = 0.15  # Small exploration to diversify trades
    min_volume_ratio: float = 1.2  # Current volume vs 10-bar average
    use_trend_filter: bool = True
    min_trend_strength: float = 0.0  # Require positive slope for longs
    max_volatility: float = 0.05  # 5% recent bar range
    max_consecutive_losses: int = 2
    reduce_risk_after_loss: bool = True
    
    # Timing
    skip_open_minutes: int = 15  # Skip first 15 min
    skip_close_minutes: int = 30  # Skip last 30 min
    max_hold_bars: int = 15  # Max 15-minute hold
    cooldown_bars: int = 2  # 2-bar cooldown
    max_trades_per_episode: int = 15
    min_trades_to_keep_episode: int = 1


class ProfitableExpert:
    """
    Expert with proven edge for BC pre-training.
    
    Goal: Generate high-quality winning demonstrations.
    """
    
    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        microstructure: MicrostructureFeatures,
        momentum: MomentumFeatures,
        config: Optional[ProfitableExpertConfig] = None,
        equity: float = 25000.0,
        max_position: int = 300,
    ):
        self.pipeline = pipeline
        self.microstructure = microstructure
        self.momentum = momentum
        self.config = config or ProfitableExpertConfig()
        
        self.equity = equity
        self.max_position = max_position
        
        # State
        self.position = 0
        self.entry_price = 0.0
        self.entry_bar = 0
        self.cooldown_bars = 0
        self.trades_this_episode = 0
        self._rejection_logs = 0
        
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
        self._rejection_logs = 0
        
    def get_action(
        self,
        step: int,
        current_price: float,
        observation: np.ndarray,
    ) -> int:
        """
        Get expert action with strict quality filters.
        
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

        # Cooldown
        if self.cooldown_bars > 0:
            self.cooldown_bars -= 1
            return 1  # HOLD

        # Get market context
        ctx = self._get_context(step, current_price)
        
        if not ctx.get('valid', False):
            return 1  # HOLD

        # Check all quality filters
        self.stats.candidates += 1
        
        if not self._passes_filters(ctx, step):
            return 1  # HOLD

        # Signal check
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
                    f"[Profitable-Expert] Bar {step}: {'LONG' if direction > 0 else 'SHORT'} "
                    f"{shares} shares @ ${current_price:.2f} | "
                    f"RSI={ctx.get('rsi', 0):.1f} Spread={ctx.get('spread', 0)*10000:.1f}bps "
                    f"Imb={ctx.get('imbalance', 0):.3f}"
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
        """Build market context."""
        bars = self.pipeline.get_latest_bars(30)
        ticks = self.pipeline.get_latest_ticks(100)
        
        if len(bars) < 14:
            return {'valid': False}
        
        # VWAP
        recent_bars = bars[-10:]
        vwap = sum(b.close * b.volume for b in recent_bars) / sum(b.volume for b in recent_bars)
        ret_from_vwap = (current_price - vwap) / vwap if vwap > 0 else 0
        
        # RSI (14-period)
        closes = np.array([b.close for b in bars[-15:]])
        rsi = self._calculate_rsi(closes, 14)
        
        # Spread
        if len(ticks) >= 10:
            recent_ticks = list(ticks)[-10:]
            spreads = [(t.ask - t.bid) / t.bid if t.bid > 0 else 0.001 
                      for t in recent_ticks if hasattr(t, 'bid') and hasattr(t, 'ask')]
            spread = np.mean(spreads) if spreads else 0.001
        else:
            spread = 0.001
        
        # Orderbook imbalance
        if len(ticks) >= 10:
            recent_ticks = list(ticks)[-10:]
            bid_size = sum(getattr(t, 'bid_size', 0) for t in recent_ticks)
            ask_size = sum(getattr(t, 'ask_size', 0) for t in recent_ticks)
            total = bid_size + ask_size
            imbalance = (bid_size - ask_size) / total if total > 0 else 0
        else:
            imbalance = 0
        
        # ATR
        atr = np.mean(self.atr_history) if self.atr_history else 0.30
        stop_distance = atr * self.config.atr_multiplier
        
        # Position sizing
        risk_dollars = self.equity * self.config.risk_per_trade_pct
        shares = int(risk_dollars / stop_distance) if stop_distance > 0 else 100
        shares = min(shares, self.max_position)

        volume_ratio = self._calculate_volume_ratio(bars)
        closes_full = np.array([b.close for b in bars])
        trend_strength = self._calculate_trend_strength(closes_full)
        volatility = self._calculate_volatility(bars)
        
        return {
            'valid': True,
            'ret_from_vwap': ret_from_vwap,
            'rsi': rsi,
            'spread': spread,
            'imbalance': imbalance,
            'atr': atr,
            'stop_distance': stop_distance,
            'shares': shares,
            'minutes_elapsed': step,
            'minutes_to_close': 390 - step,
            'volume_ratio': volume_ratio,
            'trend_strength': trend_strength,
            'volatility': volatility,
        }

    def _passes_filters(self, ctx: Dict, step: int) -> bool:
        """Check all quality filters."""
        # Timing
        if ctx['minutes_elapsed'] < self.config.skip_open_minutes:
            self.stats.blocked_timing += 1
            self._log_rejection(step, "too_early", ctx)
            return False
        
        if ctx['minutes_to_close'] <= self.config.skip_close_minutes:
            self.stats.blocked_timing += 1
            self._log_rejection(step, "too_late", ctx)
            return False
        
        # Max trades
        if self.trades_this_episode >= self.config.max_trades_per_episode:
            return False
        
        # Spread filter
        spread_bps = ctx['spread'] * 10000
        if spread_bps > self.config.max_spread_bps:
            self.stats.blocked_spread += 1
            self._log_rejection(step, "spread", ctx)
            return False
        
        # RSI filter (only for longs, we'll focus on longs only)
        if ctx['rsi'] < self.config.min_rsi_long or ctx['rsi'] > self.config.max_rsi_long:
            self.stats.blocked_rsi += 1
            self._log_rejection(step, "rsi", ctx)
            return False
        
        # Imbalance filter
        if abs(ctx['imbalance']) < self.config.min_imbalance:
            self.stats.blocked_imbalance += 1
            self._log_rejection(step, "imbalance", ctx)
            return False

        # Volume confirmation
        if ctx['volume_ratio'] < self.config.min_volume_ratio:
            self.stats.blocked_volume += 1
            self._log_rejection(step, "volume", ctx)
            return False

        # Trend confirmation
        if self.config.use_trend_filter and ctx['trend_strength'] < self.config.min_trend_strength:
            self.stats.blocked_trend += 1
            self._log_rejection(step, "trend", ctx)
            return False

        # Volatility guard
        if ctx['volatility'] > self.config.max_volatility:
            self.stats.blocked_volatility += 1
            self._log_rejection(step, "volatility", ctx)
            return False
        
        return True

    def _log_rejection(self, step: int, reason: str, ctx: Dict):
        """Helpful debug logging without spamming console."""
        if self._rejection_logs < 20:
            logger.debug(
                "[Expert Rejection] bar=%s reason=%s rsi=%0.1f spread_bps=%0.2f imbalance=%0.3f ret_vwap=%0.4f vol_ratio=%0.2f trend=%0.5f vol=%0.3f",
                step,
                reason,
                ctx.get('rsi', 0.0),
                ctx.get('spread', 0.0) * 10000,
                ctx.get('imbalance', 0.0),
                ctx.get('ret_from_vwap', 0.0),
                ctx.get('volume_ratio', 0.0),
                ctx.get('trend_strength', 0.0),
                ctx.get('volatility', 0.0),
            )
            self._rejection_logs += 1

    def _check_signal(self, ctx: Dict) -> Tuple[bool, int]:
        """
        Mean reversion signal with momentum confluence.
        
        Long: Price below VWAP + RSI oversold + Buy pressure
        """
        # Only trade longs for simplicity
        if ctx['ret_from_vwap'] < -self.config.pullback_threshold:
            if ctx['imbalance'] > self.config.min_imbalance:
                return True, 1  # LONG
        elif (
            ctx['ret_from_vwap'] < -self.config.pullback_threshold * 0.5
            and ctx['imbalance'] > 0.0
            and np.random.rand() < self.config.epsilon_entry
        ):
            # Allow occasional exploratory longs when close to threshold
            return True, 1
        
        return False, 0

    def _check_exit(self, step: int, current_price: float) -> Tuple[bool, str]:
        """ATR-based TP/SL with time exit."""
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
        
        # Time exit
        if bars_held >= self.config.max_hold_bars:
            return True, "time_exit"
        
        return False, ""

    def _calculate_position_size(self, ctx: Dict) -> int:
        """Conservative position sizing."""
        shares = ctx['shares']
        if (
            self.config.reduce_risk_after_loss
            and self._get_consecutive_losses() >= self.config.max_consecutive_losses
        ):
            shares = max(100, shares // 2)
        return shares

    def _calculate_rsi(self, closes: np.ndarray, period: int = 14) -> float:
        """Calculate RSI."""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)

    def _update_atr(self, period: int = 14):
        """Update ATR history using rolling true ranges."""
        bars = self.pipeline.get_latest_bars(period + 1)
        if len(bars) < period + 1:
            return

        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        atr = np.mean(true_ranges[-period:])
        self.atr_history.append(atr)

    def _calculate_volume_ratio(self, bars):
        """Current volume relative to recent average."""
        if len(bars) < 11:
            return 1.0
        recent = [b.volume for b in bars[-11:]]
        current_volume = recent[-1]
        avg_volume = float(np.mean(recent[:-1])) if recent[:-1] else 0.0
        if avg_volume <= 0:
            return 1.0
        return float(current_volume / avg_volume)

    def _calculate_trend_strength(self, closes: np.ndarray) -> float:
        """Normalized slope of closing prices."""
        if len(closes) < 10:
            return 0.0
        x = np.arange(len(closes), dtype=float)
        slope = np.polyfit(x, closes, 1)[0]
        mean_price = float(np.mean(closes)) if np.mean(closes) else 0.0
        if mean_price == 0.0:
            return 0.0
        return float(slope / mean_price)

    def _calculate_volatility(self, bars) -> float:
        """Average high-low range percentage over recent bars."""
        if len(bars) < 10:
            return 0.0
        recent = bars[-10:]
        ranges = []
        for bar in recent:
            if bar.low <= 0:
                continue
            ranges.append((bar.high - bar.low) / bar.low)
        if not ranges:
            return 0.0
        return float(np.mean(ranges))

    def _get_consecutive_losses(self) -> int:
        """Count trailing losing trades."""
        consecutive = 0
        for pnl in reversed(self.episode_trade_pnls):
            if pnl <= 0:
                consecutive += 1
            else:
                break
        return consecutive

    def _record_trade(self, pnl: float, reason: str):
        """Record trade result."""
        self.position = 0
        self.entry_price = 0.0
        self.cooldown_bars = self.config.cooldown_bars
        self.episode_trade_pnls.append(pnl)
        self.stats.total_pnl += pnl
        
        if pnl > 0:
            self.stats.wins += 1
        else:
            self.stats.losses += 1
        
        logger.debug(f"[Trade Complete] PnL: ${pnl:.2f} | Reason: {reason}")

    def force_close_all(self, price: float):
        """Force close at episode end."""
        if self.position != 0:
            pnl = (price - self.entry_price) * self.position
            self._record_trade(pnl, "forced_close")

    def episode_valid(self) -> bool:
        """Check if episode has enough trades."""
        return len(self.episode_trade_pnls) >= self.config.min_trades_to_keep_episode

    def get_stats_summary(self) -> str:
        """Get formatted stats."""
        return self.stats.summary()
