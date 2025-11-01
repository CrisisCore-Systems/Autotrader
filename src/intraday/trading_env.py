"""
Intraday Trading Environment for Reinforcement Learning

OpenAI Gym environment for training PPO agents on intraday trading.

Features:
- Dynamic state space (microstructure + momentum + volatility + regime + position)
- 8 discrete actions (CLOSE, HOLD, LONG_SMALL/MED/LARGE, SHORT_SMALL/MED/LARGE)
- Tree of Thought reasoning for long/short decision assistance
- Multi-objective reward function (PnL, Sharpe, costs)
- Realistic cost modeling (IBKR commissions + slippage)
- Position limits and risk controls
"""

from __future__ import annotations

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

from src.intraday.data_pipeline import IntradayDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures
from src.intraday.tree_of_thought import TreeOfThoughtReasoner, ToTDecision
from src.intraday.profit_taker import ProfitTaker, ProfitTakeConfig

logger = logging.getLogger(__name__)


@dataclass
class CostModel:
    """
    IBKR cost modeling for intraday trading.
    
    Tiered pricing structure:
    - Up to 300k shares/month: $0.005/share (min $1)
    - 300k-3M shares: $0.004/share
    - 3M+ shares: $0.003/share
    
    Plus:
    - SEC fees: $0.0000278 per dollar sold
    - FINRA TAF: $0.000166 per share sold (capped at $7.27)
    - Slippage: ~0.5-1 tick depending on size
    """
    
    commission_per_share: float = 0.005  # IBKR tiered pricing
    commission_min: float = 1.0  # Minimum per order
    sec_fee_rate: float = 0.0000278  # SEC fee per dollar
    finra_taf_rate: float = 0.000166  # FINRA TAF per share
    finra_taf_cap: float = 7.27  # Max TAF per order
    
    # Slippage model (in ticks)
    slippage_small: float = 0.5  # 100 shares
    slippage_med: float = 0.8  # 200 shares
    slippage_large: float = 1.2  # 300 shares
    tick_size: float = 0.01  # $0.01 per tick
    
    def calculate_commission(self, qty: int, price: float) -> float:
        """Calculate total commission for trade."""
        base_commission = qty * self.commission_per_share
        commission = max(base_commission, self.commission_min)
        
        # Add regulatory fees (for sells)
        notional = qty * price
        sec_fee = notional * self.sec_fee_rate
        finra_taf = min(qty * self.finra_taf_rate, self.finra_taf_cap)
        
        return commission + sec_fee + finra_taf
    
    def calculate_slippage(self, qty: int, action_type: str) -> float:
        """
        Calculate slippage based on order size.
        
        Args:
            qty: Number of shares
            action_type: 'small', 'med', 'large'
        
        Returns:
            Slippage in dollars per share
        """
        slippage_ticks = {
            'small': self.slippage_small,
            'med': self.slippage_med,
            'large': self.slippage_large,
        }.get(action_type, 0.5)
        
        return slippage_ticks * self.tick_size


class IntradayTradingEnv(gym.Env):
    """OpenAI Gym environment for intraday trading with PPO agents."""

    VOL_FEATURE_DIM = 8
    REGIME_FEATURE_DIM = 6
    POSITION_FEATURE_DIM = 6
    QUALITY_FEATURE_DIM = 6
    
    metadata = {"render_modes": ["human"]}
    
    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        microstructure: MicrostructureFeatures,
        momentum: MomentumFeatures,
        initial_capital: float = 25000.0,
        max_position: int = 500,
        max_daily_loss: float = 500.0,
        max_trades_per_day: int = 30,
        cost_model: Optional[CostModel] = None,
        enable_tot_reasoning: bool = True,
    ):
        super().__init__()
        
        # Core components
        self.pipeline = pipeline
        self.microstructure = microstructure
        self.momentum = momentum
        
        # Tree of Thought reasoning
        self.enable_tot_reasoning = enable_tot_reasoning
        if self.enable_tot_reasoning:
            self.tot_reasoner = TreeOfThoughtReasoner(
                momentum_weight=0.35,
                microstructure_weight=0.30,
                volatility_weight=0.20,
                regime_weight=0.15,
            )
            logger.info("Tree of Thought reasoning enabled")
        else:
            self.tot_reasoner = None
            logger.info("Tree of Thought reasoning disabled (direct RL)")
        
        # Determine dynamic observation dimensions based on feature engines
        self._micro_feature_names = self._resolve_feature_names(self.microstructure)
        self._micro_dim = len(self._micro_feature_names)
        self._momentum_feature_names = self._resolve_feature_names(self.momentum)
        self._momentum_dim = len(self._momentum_feature_names)
        self._observation_dim = (
            self._micro_dim
            + self._momentum_dim
            + self.VOL_FEATURE_DIM
            + self.REGIME_FEATURE_DIM
            + self.POSITION_FEATURE_DIM
            + self.QUALITY_FEATURE_DIM
        )
        
        # Trading constraints
        self.initial_capital = initial_capital
        self.max_position = max_position
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        
        # Trade throttling: prevent spam trading
        self.min_bars_between_trades = 10  # Increased from 5 to 10 bars (10 min) between trades
        self.last_trade_step = -999
        
        # Direction consistency: prevent flip-flopping
        self.last_direction = 0  # 1=LONG, -1=SHORT, 0=NONE
        self.direction_changes = 0  # Count of direction flips
        
        # Cost model
        self.cost_model = cost_model or CostModel()
        
        # Intelligent profit-taking system
        profit_config = ProfitTakeConfig(
            initial_target_rr=2.0,  # 2:1 risk-reward (more realistic for intraday with wider stop)
            enable_trailing=True,
            trailing_activation=1.2,  # Start trailing at 1.2R
            trailing_distance=0.4,  # Trail by 0.4R
            enable_partial=False,  # Disable partial exits for RL training simplicity
            max_hold_bars=60,  # Max 60 bars (~1 hour)
            profit_lock_time=30,  # Lock profits after 30 bars
            min_profit_lock=0.5,  # Minimum 0.5R to lock
        )
        self.profit_taker = ProfitTaker(profit_config)
        
        # Observation noise (used by several environment variants). Default to 0.0
        # so derived envs that reference `obs_noise_std` won't fail if they
        # don't set it explicitly.
        self.obs_noise_std = 0.0
        
        # Gym spaces
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self._observation_dim,),
            dtype=np.float32,
        )
        
        # Action space: 0=CLOSE, 1=HOLD, 2-4=LONG (small/med/large), 5-7=SHORT (small/med/large)
        self.action_space = spaces.Discrete(8)
        
        # Episode state
        self.reset()
        
        logger.info(
            f"Initialized IntradayTradingEnv "
            f"(capital=${initial_capital}, max_pos={max_position}, max_loss=${max_daily_loss})"
        )
    
    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None) -> Tuple[np.ndarray, dict]:
        """Reset environment to initial state."""
        super().reset(seed=seed)
        
        # Portfolio state
        self.capital = self.initial_capital
        self.position_qty = 0
        self.entry_price = 0.0
        self.entry_time = 0.0
        self.max_position_drawdown = 0.0
        
        # PnL tracking for per-step reward calculation
        self._prev_total_pnl = 0.0
        self.last_trade_size = 0
        
        # Trade throttling
        self.last_trade_step = -999  # Initialize far in past
        self.min_steps_between_trades = 10  # Increased from 5 to 10 steps between trades
        
        # Direction consistency
        self.last_direction = 0
        self.direction_changes = 0
        
        # Daily stats
        self.daily_pnl = 0.0
        self.daily_pnl0 = 0.0  # Starting PnL for episode reward centering
        self.daily_trades = 0
        self.current_win_streak = 0
        self.trade_history: List[Dict] = []
        
        # Time tracking (for regime features)
        self.episode_start_time = datetime.now()
        self.steps = 0
        
        # Current price tracking
        self.current_price = 0.0
        
        # Get initial observation
        obs = self._get_observation()
        info = self._get_info()
        
        return obs, info
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, dict]:
        """
        Execute one timestep.
        
        Args:
            action: 0=CLOSE, 1=HOLD, 2=LONG_SMALL, 3=LONG_MED, 4=LONG_LARGE,
                   5=SHORT_SMALL, 6=SHORT_MED, 7=SHORT_LARGE
        
        Returns:
            (observation, reward, terminated, truncated, info)
        """
        self.steps += 1
        
        # Get current price from latest bar (stable for historical) or tick (live)
        bars = self.pipeline.get_latest_bars(1)
        if bars:
            current_price = bars[-1].close
        else:
            current_price = self.pipeline.get_current_price()
        
        # Store current price for info
        self.current_price = current_price
        
        if current_price <= 0:
            # Invalid price - return neutral
            return self._get_observation(), 0.0, False, False, self._get_info()
        
        # CHECK PROFIT TAKER FIRST (before executing action)
        # This ensures we lock in profits at optimal points
        if self.profit_taker.is_active and self.position_qty != 0:
            current_atr = self._compute_atr(14)
            should_exit, exit_reason, exit_pct = self.profit_taker.check_exit(
                current_price=current_price,
                current_bar=self.steps,
                current_volatility=current_atr,
            )
            
            if should_exit:
                # Profit taker triggered exit
                if exit_pct == 1.0:
                    # Full exit
                    realized_pnl, commission = self._close_position(current_price)
                    self.daily_pnl += realized_pnl
                    
                    # Add bonus reward for profitable exits
                    base_reward = self._calculate_reward(realized_pnl, commission, current_price)
                    
                    if exit_reason and realized_pnl > 0:
                        if exit_reason.name == "TARGET_HIT":
                            bonus = 1.0  # Big bonus for hitting target
                        elif exit_reason.name == "TRAILING_STOP":
                            bonus = 0.5  # Moderate bonus for trailing stop
                        else:
                            bonus = 0.2  # Small bonus for other profitable exits
                        
                        logger.info(f"💰 Profit exit: {exit_reason.name}, PnL=${realized_pnl:.2f}, bonus=+{bonus}")
                        base_reward += bonus
                    
                    obs = self._get_observation()
                    info = self._get_info()
                    info["profit_exit"] = exit_reason.name if exit_reason else "unknown"
                    return obs, base_reward, False, False, info
                else:
                    # Partial exit (not used in current config, but supported)
                    logger.info(f"💰 Partial exit: {exit_pct*100:.0f}% at ${current_price:.2f}")
                    # For simplicity, we'll treat partial exits as holds with info
                    pass
        
        # Execute action
        realized_pnl = 0.0
        commission = 0.0
        
        if action == 0:  # CLOSE
            if self.position_qty != 0:
                realized_pnl, commission = self._close_position(current_price)
        
        elif action == 1:  # HOLD
            if self.position_qty != 0:
                unrealized = self._calculate_unrealized_pnl(current_price)
                self.max_position_drawdown = min(self.max_position_drawdown, unrealized)

        else:
            # Actions 2-7: LONG or SHORT positions
            # Check trade throttling
            bars_since_last_trade = self.steps - self.last_trade_step
            can_trade = bars_since_last_trade >= self.min_bars_between_trades
            
            if not can_trade and self.position_qty == 0:
                # Throttled: can't open new position yet
                logger.debug(f"Trade throttled: {bars_since_last_trade}/{self.min_bars_between_trades} bars since last trade")
                # Treat as hold
                pass
            else:
                action_map = {
                    2: ("long_small", 10),   # Reduced from 100 to 10 shares
                    3: ("long_med", 15),     # Reduced from 200 to 15 shares
                    4: ("long_large", 25),   # Reduced from 300 to 25 shares
                    5: ("short_small", -10), # Reduced from -100 to -10 shares
                    6: ("short_med", -15),   # Reduced from -200 to -15 shares
                    7: ("short_large", -25), # Reduced from -300 to -25 shares
                }
                action_meta = action_map.get(action)

                if action_meta is None:
                    logger.warning("Received invalid action %s", action)
                else:
                    action_type, target_qty = action_meta
                    
                    # Trade throttling check
                    steps_since_last_trade = self.steps - self.last_trade_step
                    can_trade = (self.position_qty != 0) or (steps_since_last_trade >= self.min_steps_between_trades)
                    
                    if not can_trade:
                        # Too soon to open new position, skip
                        pass
                    else:
                        # Ensure target_qty respects max_position limit
                        if target_qty > 0:
                            target_qty = min(target_qty, self.max_position)
                        else:
                            target_qty = max(target_qty, -self.max_position)

                        if abs(target_qty) == 0:
                            logger.debug("Skipping trade because target_qty=%s", target_qty)
                        elif self.position_qty == 0:
                            # Open new position (long or short)
                            self._open_position(current_price, target_qty, action_type)
                            self.last_trade_step = self.steps
                        elif (self.position_qty > 0 and target_qty < 0) or (self.position_qty < 0 and target_qty > 0):
                            # Position direction reversal: close current, then open opposite
                            realized_pnl_close, commission_close = self._close_position(current_price)
                            realized_pnl += realized_pnl_close
                            commission += commission_close
                            self._open_position(current_price, target_qty, action_type)
                            self.last_trade_step = self.steps
                        else:
                            # Already in a position of same direction: treat as hold/update drawdown
                            unrealized = self._calculate_unrealized_pnl(current_price)
                            self.max_position_drawdown = min(self.max_position_drawdown, unrealized)

        # Update realized PnL after action
        if realized_pnl != 0.0:
            self.daily_pnl += realized_pnl

        # FORCED TRADE COMPLETION: Close stale positions after MAX_HOLD_BARS
        MAX_HOLD_BARS = 60
        if self.position_qty != 0 and (self.steps - self.entry_time) >= MAX_HOLD_BARS:
            realized_pnl_forced, commission_forced = self._close_position(current_price)
            self.daily_pnl += realized_pnl_forced
            realized_pnl += realized_pnl_forced  # Add to realized_pnl for reward calculation
            commission += commission_forced
            logger.info(
                f"Forced close after {MAX_HOLD_BARS} bars: "
                f"PnL=${realized_pnl_forced:.2f}, commission=${commission_forced:.2f}"
            )

        # Calculate reward using full RL-optimized method
        reward = self._calculate_reward(realized_pnl, commission, current_price)
        
        # Check termination conditions - ONLY daily stop (no trade limit during exploration)
        done_reason = None
        terminated = False
        
        if self.daily_pnl <= -self.max_daily_loss:
            terminated = True
            done_reason = "daily_stop"
        
        # Truncate at fixed horizon (400 steps) OR if running low on data
        # This guarantees long episodes for exploration
        bars_available = len(self.pipeline.get_latest_bars(500))
        truncated = False
        
        if self.steps >= 400:  # Fixed 400-step horizon (~1 trading day)
            truncated = True
            if done_reason is None:
                done_reason = "horizon"
        elif bars_available < 250:  # Running low on historical data
            truncated = True
            if done_reason is None:
                done_reason = "insufficient_data"
        
        # Get next observation
        obs = self._get_observation()
        
        # NaN guard: replace any NaNs/infs with 0
        obs = np.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Telemetry: assert finite values and log feature statistics every 500 steps
        if not np.all(np.isfinite(obs)):
            nan_count = np.sum(np.isnan(obs))
            inf_count = np.sum(np.isinf(obs))
            logger.error(f"Step {self.steps}: Non-finite observation detected! NaN={nan_count}, Inf={inf_count}")
            # Replace with zeros (already done above, but log the issue)
        
        info = self._get_info()
        
        # Log termination reason for diagnostics
        if terminated or truncated:
            if done_reason is None:
                done_reason = "unknown"
            info["done_reason"] = done_reason
            
            # Verbose episode end logging for diagnostics
            logger.info(
                f"Episode ended at step {self.steps}: reason={done_reason}, "
                f"daily_pnl=${self.daily_pnl:.2f}, daily_trades={self.daily_trades}, "
                f"position_qty={self.position_qty}"
            )
        
        # Add feature statistics to info for monitoring (every 500 steps)
        if self.steps % 500 == 0:
            info["feat_mean"] = float(np.mean(obs))
            info["feat_std"] = float(np.std(obs))
            info["feat_min"] = float(np.min(obs))
            info["feat_max"] = float(np.max(obs))
            
            # Log reward and position for diagnostics
            unrealized = self._calculate_unrealized_pnl(current_price)
            logger.info(
                f"Step {self.steps}: feat_std={info['feat_std']:.3f} | "
                f"reward={reward:.5f} | pos={self.position_qty} "
                f"daily_pnl=${self.daily_pnl:.2f} unrealized=${unrealized:.2f}"
            )
        
        return obs, reward, terminated, truncated, info
    
    def _get_observation(self) -> np.ndarray:
        """
        Build the state vector by concatenating all feature groups.

        Included features:
        - Microstructure (dynamic length)
        - Momentum (dynamic length)
        - Volatility (8)
        - Regime (6)
        - Position (6)
        - Trading quality signals (6)
        """

        def _as_feature_vector(features, expected_dim: int, name: str) -> np.ndarray:
            vec = np.asarray(features, dtype=np.float32).ravel()
            if vec.size != expected_dim:
                raise ValueError(
                    f"{name} feature dimension mismatch: expected {expected_dim}, got {vec.size}"
                )
            return vec

        micro_features = _as_feature_vector(
            self.microstructure.compute(),
            self._micro_dim,
            "microstructure",
        )
        momentum_features = _as_feature_vector(
            self.momentum.compute(),
            self._momentum_dim,
            "momentum",
        )

        vol_features = np.asarray(self._compute_volatility_features(), dtype=np.float32).ravel()
        regime_features = np.asarray(self._compute_regime_features(), dtype=np.float32).ravel()
        position_features = np.asarray(self._compute_position_features(), dtype=np.float32).ravel()
        quality_features = np.asarray(self._compute_quality_signals(), dtype=np.float32).ravel()

        state = np.concatenate([
            micro_features,
            momentum_features,
            vol_features,
            regime_features,
            position_features,
            quality_features,
        ]).astype(np.float32)

        if state.size != self._observation_dim:
            raise ValueError(
                "Observation dimension mismatch: "
                f"expected {self._observation_dim}, got {state.size}"
            )
        
        # NaN guard: replace any NaNs/Infs with 0
        if not np.isfinite(state).all():
            state = np.nan_to_num(state, nan=0.0, posinf=0.0, neginf=0.0)

        return state

    def _resolve_feature_names(self, feature_engine) -> List[str]:
        names = []
        if hasattr(feature_engine, "get_feature_names"):
            try:
                names = list(feature_engine.get_feature_names())
            except Exception:
                names = []
        if not names:
            try:
                features = np.asarray(feature_engine.compute())
                names = [f"f_{i}" for i in range(len(features))]
            except Exception:
                names = []
        return names
    
    def _compute_volatility_features(self) -> np.ndarray:
        """
        Compute simplified volatility features (8 dim).
        
        Uses bar data to calculate realized volatility at multiple timeframes.
        """
        bars = self.pipeline.get_latest_bars(100)
        
        if len(bars) < 10:
            return np.zeros(8)
        
        # Extract close prices
        closes = np.array([bar.close for bar in bars])
        
        # Calculate returns
        returns = np.diff(closes) / closes[:-1]
        
        # Realized volatility at different windows (annualized)
        def realized_vol(window):
            if len(returns) < window:
                return 0.0
            recent_returns = returns[-window:]
            return float(np.std(recent_returns) * np.sqrt(252 * 390))  # Annualized
        
        vol_1min = realized_vol(1)
        vol_5min = realized_vol(5)
        vol_30min = realized_vol(30)
        
        # Parkinson estimator (high-low range)
        def parkinson_vol(window):
            if len(bars) < window:
                return 0.0
            recent_bars = bars[-window:]
            hl_ratio = [(bar.high / bar.low) if bar.low > 0 else 1.0 for bar in recent_bars]
            return float(np.sqrt(np.mean([np.log(r)**2 for r in hl_ratio]) / (4 * np.log(2))) * np.sqrt(252 * 390))
        
        parkinson = parkinson_vol(20)
        
        # Volatility percentile (vs recent history)
        if len(returns) >= 50:
            recent_vol = np.std(returns[-10:])
            historical_vols = [np.std(returns[i:i+10]) for i in range(len(returns)-10)]
            vol_percentile = float(np.percentile(historical_vols, recent_vol) / 100) if historical_vols else 0.5
        else:
            vol_percentile = 0.5
        
        # Volatility trend (rising/falling)
        if len(returns) >= 20:
            vol_recent = np.std(returns[-10:])
            vol_older = np.std(returns[-20:-10])
            vol_trend = float((vol_recent - vol_older) / vol_older) if vol_older > 0 else 0.0
        else:
            vol_trend = 0.0
        
        # Volatility of volatility
        if len(returns) >= 50:
            rolling_vols = [np.std(returns[i:i+10]) for i in range(len(returns)-10)]
            vol_of_vol = float(np.std(rolling_vols))
        else:
            vol_of_vol = 0.0
        
        # ATR (Average True Range)
        atr = self._compute_atr(14)
        
        return np.array([
            vol_1min,
            vol_5min,
            vol_30min,
            parkinson,
            vol_percentile,
            vol_trend,
            vol_of_vol,
            atr,  # Replaced garch_forecast with ATR
        ])
    
    def _compute_atr(self, period: int = 14) -> float:
        """
        Compute Average True Range.
        
        Args:
            period: Lookback period for ATR calculation
        
        Returns:
            ATR value in dollars
        """
        bars = self.pipeline.get_latest_bars(period + 1)
        
        if len(bars) < period + 1:
            return 0.0
        
        true_ranges = []
        for i in range(1, len(bars)):
            high = bars[i].high
            low = bars[i].low
            prev_close = bars[i-1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        
        return float(np.mean(true_ranges))
    
    def _compute_regime_features(self) -> np.ndarray:
        """
        Compute market regime features (6 dim).
        
        - Trend strength
        - Trend direction
        - Time since open
        - Time until close
        - Volatility regime
        - Market phase
        """
        bars = self.pipeline.get_latest_bars(50)
        
        if len(bars) < 10:
            return np.array([0.0, 0, 0.0, 390.0, 1, 0])
        
        # Trend strength (ADX-like using price range)
        closes = np.array([bar.close for bar in bars])
        highs = np.array([bar.high for bar in bars])
        lows = np.array([bar.low for bar in bars])
        
        # Simple trend strength: correlation of closes with time
        trend_strength = float(np.corrcoef(closes, np.arange(len(closes)))[0, 1])
        
        # Trend direction: sign of recent returns
        returns = (closes[-1] - closes[-10]) / closes[-10] if len(closes) >= 10 else 0
        trend_direction = int(np.sign(returns))
        
        # Time features (minutes)
        time_since_open = float(self.steps)
        time_until_close = float(390 - self.steps)
        
        # Volatility regime (0=low, 1=med, 2=high)
        recent_vol = np.std(closes[-10:]) if len(closes) >= 10 else 0
        vol_regime = 0 if recent_vol < 0.01 else (2 if recent_vol > 0.03 else 1)
        
        # Market phase (0=open, 1=midday, 2=close)
        if self.steps < 60:
            market_phase = 0  # First hour
        elif self.steps > 330:
            market_phase = 2  # Last hour
        else:
            market_phase = 1  # Midday
        
        return np.array([
            trend_strength,
            trend_direction,
            time_since_open,
            time_until_close,
            vol_regime,
            market_phase,
        ])
    
    def _compute_position_features(self) -> np.ndarray:
        """
        Compute position context features (6 dim).
        
        - Position quantity
        - Unrealized P&L
        - Position duration (minutes)
        - Entry price
        - Daily P&L
        - Daily trades
        """
        current_price = self.pipeline.get_current_price()
        unrealized_pnl = self._calculate_unrealized_pnl(current_price)
        
        # Position duration (estimate based on steps)
        position_duration = float(self.steps - (self.entry_time or self.steps))
        
        return np.array([
            float(self.position_qty),
            unrealized_pnl,
            position_duration,
            self.entry_price,
            self.daily_pnl,
            float(self.daily_trades),
        ])
    
    def _compute_quality_signals(self) -> np.ndarray:
        """
        Compute trading quality signals (6 dim) - RL-NATIVE FEATURES.
        
        Instead of hard-coded reject rules, feed raw quality signals to RL agent:
        - Bid-ask spread (raw value)
        - Order imbalance (raw value)
        - RSI value (raw, not thresholded)
        - Return from VWAP (conviction measure)
        - Current ATR (volatility context)
        - Trade conviction score (composite)
        
        The PPO agent will learn optimal thresholds for these values.
        """
        # Get current bars and ticks
        bars = self.pipeline.get_latest_bars(20)
        
        if len(bars) < 5:
            return np.zeros(6)
        
        # 1. Bid-Ask Spread (raw value, normalized)
        ticks = self.pipeline.tick_buffer
        if len(ticks) >= 10:
            recent_ticks = list(ticks)[-10:]
            spreads = [(t.ask - t.bid) / t.bid if t.bid > 0 else 0 for t in recent_ticks]
            bid_ask_spread = float(np.mean(spreads))
        else:
            bid_ask_spread = 0.001  # Default 10 bps
        
        # 2. Order Imbalance (raw value)
        if len(ticks) >= 10:
            recent_ticks = list(ticks)[-10:]
            bid_sizes = sum(t.bid_size for t in recent_ticks if hasattr(t, 'bid_size'))
            ask_sizes = sum(t.ask_size for t in recent_ticks if hasattr(t, 'ask_size'))
            total = bid_sizes + ask_sizes
            order_imbalance = float((bid_sizes - ask_sizes) / total) if total > 0 else 0.0
        else:
            order_imbalance = 0.0
        
        # 3. RSI (raw value, not thresholded)
        closes = np.array([bar.close for bar in bars])
        if len(closes) >= 14:
            gains = np.maximum(np.diff(closes), 0)
            losses = np.abs(np.minimum(np.diff(closes), 0))
            avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 0
            avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 0
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                rsi = float(100 - (100 / (1 + rs)))
            else:
                rsi = 50.0
        else:
            rsi = 50.0
        
        # 4. Return from VWAP (conviction measure)
        if len(bars) >= 10:
            recent_bars = bars[-10:]
            vwap = sum(b.close * b.volume for b in recent_bars) / sum(b.volume for b in recent_bars)
            current_price = bars[-1].close
            ret_from_vwap = float((current_price - vwap) / vwap) if vwap > 0 else 0.0
        else:
            ret_from_vwap = 0.0
        
        # 5. Current ATR (volatility context)
        atr = self._compute_atr(14)
        
        # 6. Trade Conviction Score (composite: |ret_vwap| * |imbalance| / spread)
        # Higher = better quality opportunity
        conviction = float(abs(ret_from_vwap) * abs(order_imbalance) / (bid_ask_spread + 1e-6))
        conviction = np.clip(conviction, 0, 10)  # Clip to reasonable range
        
        return np.array([
            bid_ask_spread,
            order_imbalance,
            rsi / 100.0,  # Normalize to [0, 1]
            ret_from_vwap,
            atr,
            conviction,
        ])
    
    def _open_position(self, price: float, qty: int, action_type: str):
        """Open new position with cost modeling. qty can be negative for shorts."""
        # Calculate costs (use abs(qty) for commission calc)
        commission = self.cost_model.calculate_commission(abs(qty), price)
        slippage = self.cost_model.calculate_slippage(abs(qty), action_type)
        
        # Effective entry price (includes slippage)
        # For shorts, slippage works against us (we sell at worse price)
        if qty > 0:  # Long
            effective_price = price + slippage
        else:  # Short
            effective_price = price - slippage
        
        # Deduct from capital (for shorts, we receive proceeds minus commission)
        if qty > 0:  # Long: pay to buy shares
            cost = effective_price * qty + commission
            self.capital -= cost
        else:  # Short: receive proceeds from selling shares (minus commission)
            proceeds = effective_price * abs(qty) - commission
            self.capital += proceeds
        
        # Update position
        self.position_qty = qty
        self.entry_price = effective_price
        self.entry_time = float(self.steps)
        self.max_position_drawdown = 0.0
        self.daily_trades += 1
        
        # Track direction consistency
        current_direction = 1 if qty > 0 else -1
        if self.last_direction != 0 and current_direction != self.last_direction:
            self.direction_changes += 1
        self.last_direction = current_direction
        
        # Calculate stop loss (ATR-based)
        atr = self._compute_atr(14)
        if atr > 0:
            stop_distance = atr * 4.0  # 4.0x ATR stop (wider for intraday noise)
        else:
            stop_distance = effective_price * 0.005  # 0.5% stop as fallback
        
        if qty > 0:  # Long
            stop_loss = effective_price - stop_distance
        else:  # Short
            stop_loss = effective_price + stop_distance
        
        # Initialize profit taker
        self.profit_taker.on_position_open(
            entry_price=effective_price,
            qty=qty,
            stop_loss=stop_loss,
            current_bar=self.steps,
            current_volatility=atr,
        )
        
        position_type = "LONG" if qty > 0 else "SHORT"
        logger.debug(
            f"Opened {position_type} position: {abs(qty)} shares @ ${effective_price:.2f}, "
            f"commission=${commission:.2f}, slippage=${slippage:.4f}, "
            f"SL=${stop_loss:.2f}, TP=${self.profit_taker.take_profit:.2f}"
        )
    
    def _close_position(self, price: float) -> Tuple[float, float]:
        """
        Close position and return (PnL, commission).
        Handles both long and short positions.
        
        Returns:
            (realized_pnl, commission)
        """
        # Calculate costs (use abs(qty) for commission calc)
        commission = self.cost_model.calculate_commission(abs(self.position_qty), price)
        
        # Assume minimal slippage on market close (using current bid/ask mid)
        slippage = 0.005  # Half penny
        
        # For longs, we sell (price - slippage)
        # For shorts, we buy to cover (price + slippage)
        if self.position_qty > 0:  # Closing long
            exit_price = price - slippage
            # PnL = (exit - entry) * qty - commission
            realized_pnl = (exit_price - self.entry_price) * self.position_qty - commission
            # Return capital from sale
            self.capital += (exit_price * self.position_qty) - commission
        else:  # Closing short (position_qty < 0)
            exit_price = price + slippage
            # PnL = (entry - exit) * abs(qty) - commission (profit when price drops)
            realized_pnl = (self.entry_price - exit_price) * abs(self.position_qty) - commission
            # Pay to cover short position
            self.capital -= (exit_price * abs(self.position_qty)) + commission
        
        # Record trade
        trade_record = {
            "entry_price": self.entry_price,
            "exit_price": exit_price,
            "qty": self.position_qty,
            "pnl": realized_pnl,
            "commission": commission,
            "duration": self.steps - self.entry_time,
            "max_drawdown": self.max_position_drawdown,
        }
        self.trade_history.append(trade_record)
        
        # Update win streak
        if realized_pnl > 0:
            self.current_win_streak += 1
        else:
            self.current_win_streak = 0
        
        # Reset position
        self.position_qty = 0
        self.entry_price = 0.0
        self.entry_time = 0.0
        self.max_position_drawdown = 0.0
        self.daily_trades += 1
        
        # Deactivate profit taker
        self.profit_taker.on_position_close()
        
        logger.debug(
            f"Closed position: {trade_record['qty']} shares @ ${exit_price:.2f}, "
            f"PnL=${realized_pnl:.2f}"
        )
        
        return realized_pnl, commission
    
    def _calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L for open position (handles both long and short)."""
        if self.position_qty == 0 or current_price <= 0:
            return 0.0
        
        if self.position_qty > 0:  # Long position
            return (current_price - self.entry_price) * self.position_qty
        else:  # Short position
            return (self.entry_price - current_price) * abs(self.position_qty)
    
    def _calculate_reward(
        self,
        realized_pnl: float,
        commission: float,
        current_price: float,
    ) -> float:
        """
        SIMPLIFIED reward function for curriculum learning.
        
        Bootstrap Phase: Teach agent to HOLD and let profit taker work.
        Key insight: Reward based on TRADE DURATION when closed, not current hold time.
        
        Current focus: PnL per trade + patience bonus for closed trades.
        """
        reward = 0.0
        
        # PRIMARY SIGNAL: PnL per trade (normalized)
        if realized_pnl != 0:
            # Get the duration of the CLOSED trade from trade history
            if self.trade_history:
                last_trade = self.trade_history[-1]
                trade_duration = last_trade['duration']
            else:
                trade_duration = 0
            
            # Normalize by initial capital for consistent scale
            pnl_normalized = realized_pnl / self.initial_capital
            
            # Strong positive reward for profitable trades (target 3R = ~$26)
            if realized_pnl > 0:
                # Base reward: $26 profit → +0.52 reward (26/50)
                base_reward = min(pnl_normalized * 50.0, 2.0)  # Cap at +2.0
                
                # PATIENCE BONUS: Extra reward if held for 20+ bars
                # This teaches agent to let profit taker work
                if trade_duration >= 20:
                    patience_multiplier = 1.5  # 50% bonus
                    reward = base_reward * patience_multiplier
                    logger.info(f"🎯 Patience bonus! Held {trade_duration} bars, reward={reward:.3f}")
                else:
                    reward = base_reward
            else:
                # Penalty for losses (but not too harsh to allow exploration)
                # Scale: -$26 loss → -0.52 reward
                base_penalty = max(pnl_normalized * 50.0, -1.0)  # Cap at -1.0
                
                # IMPATIENCE PENALTY: Extra penalty if exited too quickly
                if trade_duration < 10:
                    impatience_multiplier = 1.5  # 50% worse
                    reward = base_penalty * impatience_multiplier
                else:
                    reward = base_penalty
        
        # SECONDARY SIGNAL: Small positive reward for holding open positions
        # This encourages not closing immediately
        elif self.position_qty != 0:
            hold_duration = self.steps - self.entry_time
            
            # Small continuous reward for holding in the sweet spot
            if 15 <= hold_duration <= 70:
                holding_reward = 0.005  # Small constant reward per step
                reward += holding_reward
        
        # TERTIARY SIGNAL: Overtrading penalty
        # Penalize excessive trading (>50 trades per episode)
        if self.daily_trades > 50:
            overtrade_penalty = -0.1 * (self.daily_trades - 50) / 100.0
            reward += max(overtrade_penalty, -0.5)  # Cap at -0.5
        
        # DIRECTION FLIP-FLOP PENALTY: Discourage changing between LONG/SHORT
        # Excessive direction changes = no conviction
        if self.direction_changes > 10:  # More than 10 direction flips
            flip_penalty = -0.05 * (self.direction_changes - 10)
            reward += max(flip_penalty, -0.3)  # Cap at -0.3
        
        # COMMISSION AWARENESS: Deduct commission impact
        if commission > 0:
            commission_penalty = -commission / self.initial_capital * 10.0
            reward += max(commission_penalty, -0.1)  # Cap at -0.1
        
        # Final clipping for safety
        return float(np.clip(reward, -2.0, 2.0))
    
    def _get_tot_decision(self) -> Optional[ToTDecision]:
        """Get Tree of Thought decision for current state."""
        if not self.enable_tot_reasoning or self.tot_reasoner is None:
            return None
        
        try:
            # Get feature groups
            micro_features = self.microstructure.compute()
            momentum_features = self.momentum.compute()
            vol_features = self._compute_volatility_features()
            regime_features = self._compute_regime_features()
            position_features = self._compute_position_features()
            
            # Convert to arrays
            micro_arr = np.asarray(micro_features, dtype=np.float32).ravel()
            momentum_arr = np.asarray(momentum_features, dtype=np.float32).ravel()
            vol_arr = np.asarray(vol_features, dtype=np.float32).ravel()
            regime_arr = np.asarray(regime_features, dtype=np.float32).ravel()
            position_arr = np.asarray(position_features, dtype=np.float32).ravel()
            
            # Get ToT decision
            decision = self.tot_reasoner.reason(
                momentum_features=momentum_arr,
                microstructure_features=micro_arr,
                volatility_features=vol_arr,
                regime_features=regime_arr,
                position_features=position_arr,
            )
            
            return decision
        except Exception as e:
            logger.warning(f"ToT reasoning failed: {e}")
            return None
    
    def _get_info(self) -> dict:
        """Get info dictionary for step."""
        info = {
            "capital": self.capital,
            "position_qty": self.position_qty,
            "entry_price": self.entry_price,
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "current_win_streak": self.current_win_streak,
            "steps": self.steps,
            "price": self.current_price,
            "direction_changes": self.direction_changes,  # Track flip-flopping
        }
        
        # Add ToT decision if enabled
        if self.enable_tot_reasoning:
            tot_decision = self._get_tot_decision()
            if tot_decision:
                info["tot_direction"] = tot_decision.direction.name
                info["tot_confidence"] = tot_decision.confidence
                info["tot_action"] = tot_decision.action_recommendation
                info["tot_consensus"] = tot_decision.consensus_score
        
        return info
    
    def render(self, mode: str = "human"):
        """Render environment state (for debugging)."""
        if mode == "human":
            print(f"\n=== Step {self.steps} ===")
            print(f"Capital: ${self.capital:.2f}")
            print(f"Position: {self.position_qty} shares @ ${self.entry_price:.2f}")
            print(f"Daily PnL: ${self.daily_pnl:.2f}")
            print(f"Trades: {self.daily_trades}/{self.max_trades_per_day}")
            print(f"Win Streak: {self.current_win_streak}")
    
    def __repr__(self) -> str:
        return (
            f"IntradayTradingEnv("
            f"capital=${self.capital:.0f}, "
            f"position={self.position_qty}, "
            f"pnl=${self.daily_pnl:.2f})"
        )


if __name__ == "__main__":
    # Example usage
    import logging
    from ib_insync import IB
    import time
    
    logging.basicConfig(level=logging.INFO)
    
    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    
    # Create pipeline and features
    from src.intraday.data_pipeline import IntradayDataPipeline
    from src.intraday.microstructure import MicrostructureFeatures
    from src.intraday.momentum import MomentumFeatures
    
    pipeline = IntradayDataPipeline(ib, 'SPY')
    pipeline.start()
    
    # Wait for data
    print("Collecting data for 120 seconds...")
    time.sleep(120)
    
    # Create environment
    microstructure = MicrostructureFeatures(pipeline)
    momentum = MomentumFeatures(pipeline)
    
    env = IntradayTradingEnv(
        pipeline=pipeline,
        microstructure=microstructure,
        momentum=momentum,
    )
    
    # Run random episode
    print("\n🤖 Running random agent...")
    obs, info = env.reset()
    total_reward = 0
    
    for step in range(50):  # 50 steps
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        if step % 10 == 0:
            env.render()
        
        if terminated or truncated:
            break
    
    print(f"\n✅ Episode complete: Total reward = {total_reward:.2f}")
    print(f"Final PnL: ${info['daily_pnl']:.2f}")
    print(f"Trades: {info['daily_trades']}")
    
    # Cleanup
    pipeline.stop()
    ib.disconnect()
