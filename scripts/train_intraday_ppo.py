"""
PPO Training Script for Intraday Trading

Goal: Achieve >70% win rate with Sharpe >3.0

Training Features:
- Historical data replay (30+ days of SPY)
- Advanced reward shaping for win rate
- Curriculum learning (easy → hard)
- Callback monitoring with early stopping
- Hyperparameter optimization ready

Usage:
    python scripts/train_intraday_ppo.py --duration 30D --timesteps 1000000
"""

import argparse
import json
import time
import logging
import random
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np

try:
    from ib_insync import IB
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import (
        BaseCallback,
        EvalCallback,
        CheckpointCallback,
        CallbackList,
    )
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.utils import get_schedule_fn
    import torch
    import os
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("\nInstall required packages:")
    print("  pip install ib_insync stable-baselines3[extra] torch tensorboard")
    exit(1)

import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.intraday import (
    EnhancedDataPipeline,
    IntradayTradingEnv,
    MicrostructureFeatures,
    MomentumFeatures,
    RobustMicrostructureFeatures,
    LegacyMicrostructureAdapter,
)
from src.intraday.data_pipeline import TickData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_microstructure_features(
    pipeline,
    *,
    mode: str = "legacy",
    normalization: str = "off",
) -> MicrostructureFeatures:
    """Construct microstructure feature engine with desired configuration."""

    normalization = normalization.lower()
    mode = mode.lower()

    if mode not in {"legacy", "extended"}:
        raise ValueError(f"Unsupported microstructure mode: {mode}")

    normalized = normalization != "off"
    norm_method = "robust"
    if normalization == "minmax":
        norm_method = "minmax"
    elif normalization not in {"off", "robust"}:
        raise ValueError(f"Unsupported normalization: {normalization}")

    engine = RobustMicrostructureFeatures(
        pipeline=pipeline,
        include_order_flow=(mode == "extended"),
        include_regimes=(mode == "extended"),
        include_liquidity_metrics=(mode == "extended"),
        normalized=normalized,
        normalization_method=norm_method,
        check_stale=False,  # Disable staleness checks for historical replay
    )

    if mode == "legacy":
        return LegacyMicrostructureAdapter(engine)
    return engine


class WinRateCallback(BaseCallback):
    """
    Monitor win rate and other trading metrics during training.
    """
    
    def __init__(self, check_freq: int = 1000, verbose: int = 1):
        super().__init__(verbose)
        self.check_freq = check_freq
        self.best_win_rate = 0.0
        self.best_sharpe = 0.0
        self.last_metrics = {}
        
        # Tracking
        self.episode_rewards = []
        self.episode_lengths = []
        self.episode_pnls = []
        self.episode_wins = []
        self.episode_trades = []
        
        # Long/Short tracking
        self.long_trades = []
        self.short_trades = []
        self.long_pnls = []
        self.short_pnls = []
        self.action_counts = {i: 0 for i in range(8)}  # Track all 8 actions
        
    def _on_step(self) -> bool:
        # Track actions taken
        if 'actions' in self.locals:
            actions = self.locals['actions']
            for action in np.atleast_1d(actions):
                if 0 <= action < 8:
                    self.action_counts[action] += 1
        
        # Collect episode stats
        if 'episode' in self.locals:
            ep_info = self.locals['episode']
            if ep_info:
                for info in self.locals.get('infos', []):
                    if 'episode' in info:
                        ep_rew = info['episode']['r']
                        ep_len = info['episode']['l']
                        
                        self.episode_rewards.append(ep_rew)
                        self.episode_lengths.append(ep_len)
                        
                        # Extract trading metrics from info
                        if 'daily_pnl' in info:
                            pnl = info['daily_pnl']
                            trades = info.get('daily_trades', 0)
                            
                            self.episode_pnls.append(pnl)
                            self.episode_wins.append(1 if pnl > 0 else 0)
                            self.episode_trades.append(trades)
                            
                            # Log episode completion
                            logger.debug(
                                f"Episode {len(self.episode_pnls)} completed: "
                                f"PnL=${pnl:.2f}, trades={trades}, win={pnl > 0}"
                            )
        
        # Log every check_freq steps
        if self.n_calls % self.check_freq == 0:
            # ALWAYS calculate and update metrics, even if no episodes yet
            # This ensures curriculum callback always gets valid metrics
            if len(self.episode_pnls) > 0:
                # Calculate metrics from actual episodes
                recent_pnls = self.episode_pnls[-100:]
                recent_wins = self.episode_wins[-100:]
                recent_trades = self.episode_trades[-100:]
                
                win_rate = np.mean(recent_wins) * 100 if recent_wins else 0
                avg_pnl = np.mean(recent_pnls) if recent_pnls else 0
                avg_trades = np.mean(recent_trades) if recent_trades else 0
                
                # Calculate Sharpe (annualized)
                if len(recent_pnls) > 1:
                    returns = np.array(recent_pnls) / 25000  # % returns
                    sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
                else:
                    sharpe = 0.0
                
                # Update best
                if win_rate > self.best_win_rate:
                    self.best_win_rate = win_rate
                
                if sharpe > self.best_sharpe:
                    self.best_sharpe = sharpe
                
                # Calculate action distribution
                total_actions = sum(self.action_counts.values())
                if total_actions > 0:
                    action_pct = {k: (v/total_actions)*100 for k, v in self.action_counts.items()}
                    long_actions = action_pct.get(2, 0) + action_pct.get(3, 0) + action_pct.get(4, 0)
                    short_actions = action_pct.get(5, 0) + action_pct.get(6, 0) + action_pct.get(7, 0)
                else:
                    long_actions = short_actions = 0.0
                
                # Log
                logger.info(
                    f"\n{'='*60}\n"
                    f"Step: {self.n_calls:,} | Episodes: {len(self.episode_pnls)}\n"
                    f"  Win Rate: {win_rate:.1f}% (Best: {self.best_win_rate:.1f}%)\n"
                    f"  Avg PnL: ${avg_pnl:.2f}\n"
                    f"  Avg Trades: {avg_trades:.1f}\n"
                    f"  Sharpe: {sharpe:.2f} (Best: {self.best_sharpe:.2f})\n"
                    f"  Actions: LONG {long_actions:.1f}% | SHORT {short_actions:.1f}%\n"
                    f"{'='*60}"
                )
            else:
                # No episodes yet - use defaults
                win_rate = 0.0
                avg_pnl = 0.0
                avg_trades = 0.0
                sharpe = 0.0
                
                logger.info(
                    f"\n{'='*60}\n"
                    f"Step: {self.n_calls:,} | Episodes: 0 (waiting for first episode)\n"
                    f"  Win Rate: {win_rate:.1f}%\n"
                    f"{'='*60}"
                )
            
            # ALWAYS update last_metrics so curriculum callback gets valid data
            self.last_metrics = {
                'win_rate': win_rate,
                'avg_pnl': avg_pnl,
                'avg_trades': avg_trades,
                'sharpe': sharpe,
            }
            
            # TensorBoard logging
            if self.logger:
                self.logger.record('metrics/win_rate', win_rate)
                self.logger.record('metrics/avg_pnl', avg_pnl)
                self.logger.record('metrics/sharpe', sharpe)
                self.logger.record('metrics/avg_trades', avg_trades)
        
        return True

    def get_recent_metrics(self) -> dict:
        """Expose most recent aggregated metrics for other callbacks."""
        return dict(self.last_metrics)


class HighWinRateEnv(IntradayTradingEnv):
    """
    Modified environment with reward shaping for high win rate.
    
    Changes:
    1. Win streak bonus increased (0.5 → 2.0)
    2. Loss penalty increased (encourage conservative trading)
    3. Early stop on profitable day (lock in wins)
    4. Reduced position sizes (better risk management)
    5. Dynamic TP/SL based on ATR
    """
    
    def __init__(self, *args, bc_mode=False, enable_per_trade_stop=True, **kwargs):
        """
        Initialize with tracking for returns and drawdown.
        
        Args:
            bc_mode: If True, disable early stop penalties to allow diverse data collection
            enable_per_trade_stop: If True, use ATR-based per-trade stop-loss (disable during bootstrap)
        """
        super().__init__(*args, **kwargs)
        self.daily_returns = []
        self.current_drawdown = 0.0
        self.unrealized_pnl = 0.0
        self.position_entry_time = 0.0
        self.bc_mode = bc_mode  # BC collection mode - no early stops
        self.trade_wins: list[int] = []
        self.obs_noise_std = 0.0
        self.curriculum_stage = "stage_00_bootstrap"
        self.reward_profile = "legacy"
        self.enable_per_trade_stop = enable_per_trade_stop
        
        # TP/SL parameters
        self.tp_multiplier = 3.0  # 3:1 risk-reward ratio
        self.sl_atr_multiplier = 2.5  # Increased from 1.5 to 2.5 for wider stops
        self.take_profit = 0.0
        self.stop_loss = 0.0
    
    def reset(self, seed=None, options=None):
        """Reset environment and tracking variables."""
        obs, info = super().reset(seed=seed, options=options)
        self.daily_returns = []
        self.current_drawdown = 0.0
        self.unrealized_pnl = 0.0
        self.position_entry_time = 0.0
        self.take_profit = 0.0
        self.stop_loss = 0.0
        self.trade_wins = []
        
        # Ensure we start flat (should already be 0 from super().reset())
        assert self.position_qty == 0, f"Episode started with position={self.position_qty}, should be 0"
        
        return obs, info

    def _get_observation(self):
        obs = super()._get_observation()
        if self.obs_noise_std > 0.0:
            noise = self.np_random.normal(0.0, self.obs_noise_std, size=obs.shape)
            obs = obs + noise.astype(obs.dtype)
        return obs

    def set_observation_noise(self, std: float) -> None:
        self.obs_noise_std = max(0.0, float(std))
    
    def _open_position(self, price: float, qty: int, action_type: str):
        """Override to set dynamic TP/SL."""
        super()._open_position(price, qty, action_type)
        
        # Calculate ATR for dynamic stop and target
        atr = self._compute_atr(14)
        
        if atr > 0:
            sl_distance = atr * self.sl_atr_multiplier
            self.stop_loss = self.entry_price - sl_distance
            tp_distance = sl_distance * self.tp_multiplier
            self.take_profit = self.entry_price + tp_distance
        else:
            # Fallback to fixed values
            self.stop_loss = self.entry_price - 0.30  # $0.30 stop
            self.take_profit = self.entry_price + 0.90  # $0.90 target (3:1)
    
    def _close_position(self, price: float):
        """Close and log trade result."""
        realized_pnl, commission = super()._close_position(price)
        self._record_trade_result(realized_pnl)
        return realized_pnl, commission

    def _record_trade_result(self, realized_pnl: float) -> None:
        """Track trade outcomes for curriculum and reward shaping."""
        if realized_pnl > 0:
            self.trade_wins.append(1)
        else:
            self.trade_wins.append(0)

    def _compute_win_rate(self) -> float:
        recent = self.trade_wins[-20:]
        if not recent:
            return 0.0
        return float(np.mean(recent) * 100)
    
    def _calculate_reward(
        self,
        realized_pnl: float,
        commission: float,
        current_price: float,
    ) -> float:
        """
        Custom reward function optimized for win rate.
        
        Priorities:
        1. Win rate > absolute PnL
        2. Risk-adjusted returns
        3. Trade selectivity (fewer, better trades)
        
        FIXED REWARD SCALING:
        - All rewards normalized to [-10, +10] range
        - PnL scaled by 0.01 (convert $100 → 1.0 reward)
        - Sharpe clipped to prevent explosion
        - Balanced incentives for exploration
        """
        reward = 0.0
        
        # Base PnL reward (SCALED: $100 → 1.0 reward)
        pnl_reward = self.daily_pnl * 0.01
        reward += pnl_reward
        
        # Risk-adjusted return (Sharpe-like, CLIPPED)
        if len(self.daily_returns) > 5:  # Need meaningful history
            returns_array = np.array(self.daily_returns[-100:])  # Last 100 returns
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array) + 1e-8
            sharpe = mean_return / std_return
            # Clip to prevent explosion, scale to +/-5 max
            sharpe_reward = np.clip(sharpe * 5.0, -5.0, 5.0)
            reward += sharpe_reward
        
        # Commission penalty (SCALED: $10 → -0.05 penalty)
        total_commissions = sum(self.trade_history[t]['commission'] 
                               for t in range(len(self.trade_history)))
        reward -= (total_commissions / 100.0) * 0.5
        
        # Win streak bonus (SCALED: encourage consistent wins)
        if self.current_win_streak > 0:
            streak_bonus = min(self.current_win_streak * 1.0, 5.0)  # Cap at +5
            reward += streak_bonus
        
        # Loss penalty (SCALED: 1.5x instead of 2.0x)
        if self.daily_pnl < 0:
            loss_penalty = abs(self.daily_pnl) * 0.015  # Gentler than PnL reward
            reward -= loss_penalty
        
        # Drawdown penalty (SCALED)
        if self.current_drawdown < -self.max_daily_loss * 0.5:
            reward -= 5.0  # Fixed penalty, not dynamic
        
        # Trade selectivity reward (SCALED)
        if self.daily_trades > 0:
            avg_pnl_per_trade = self.daily_pnl / self.daily_trades
            if avg_pnl_per_trade > 1.0:  # Profitable on average
                selectivity_reward = (avg_pnl_per_trade / 10.0)  # $10/trade → +1.0
                reward += min(selectivity_reward, 3.0)  # Cap at +3
        
        # Holding reward (SMALL: encourage taking positions)
        if self.position_qty > 0:
            reward += 0.01  # Tiny reward for being in market
        
        # Holding time penalty (SCALED: discourage holding losers)
        if self.position_qty != 0 and self.unrealized_pnl < -5.0:
            holding_time = time.time() - self.position_entry_time
            if holding_time > 300:  # 5 minutes
                reward -= min((holding_time / 600.0), 2.0)  # Cap at -2
        
        # Early exit reward (SCALED: lock in profits)
        if self.daily_pnl > 100.0:  # $100+ profit
            reward += 3.0  # Moderate bonus
        
        return reward
    
    def step(self, action: int):
        """Override step to add early stopping on good days + EOD risk kill-switch + TP/SL checks."""
        # Update tracking before parent step
        bars = self.pipeline.get_latest_bars(1)
        if bars:
            current_price = bars[-1].close
        else:
            current_price = self.pipeline.get_current_price()
        
        # Calculate unrealized PnL for both long and short positions
        if self.position_qty != 0 and current_price > 0:
            if self.position_qty > 0:  # Long position
                self.unrealized_pnl = (current_price - self.entry_price) * self.position_qty
            else:  # Short position
                self.unrealized_pnl = (self.entry_price - current_price) * abs(self.position_qty)
            
            if self.unrealized_pnl < self.current_drawdown:
                self.current_drawdown = self.unrealized_pnl
            # Update entry time tracking
            if not hasattr(self, 'position_entry_time') or self.position_entry_time == 0.0:
                self.position_entry_time = time.time()
        
        # Check TP/SL before executing action (only if enabled)
        # Note: For shorts, TP is below entry and SL is above entry
        if self.enable_per_trade_stop and self.position_qty != 0:
            hit_tp = False
            hit_sl = False
            
            if self.position_qty > 0:  # Long position
                hit_tp = current_price >= self.take_profit
                hit_sl = current_price <= self.stop_loss
            else:  # Short position (TP/SL reversed)
                hit_tp = current_price <= self.take_profit
                hit_sl = current_price >= self.stop_loss
            
            if hit_tp:
                # Hit take profit - force close
                realized_pnl, commission = self._close_position(current_price)
                self.daily_pnl += realized_pnl
                reward = self._calculate_reward(realized_pnl, commission, current_price)
                
                # Update win streak
                if realized_pnl > 0:
                    self.current_win_streak += 1
                else:
                    self.current_win_streak = 0
                
                # Reset TP/SL
                self.take_profit = 0.0
                self.stop_loss = 0.0
                
                obs = self._get_observation()
                info = self._get_info()
                return obs, reward, False, False, info
            
            elif hit_sl:
                # Hit stop loss - force close with scaled penalty
                realized_pnl, commission = self._close_position(current_price)
                self.daily_pnl += realized_pnl
                
                # Scaled penalty for hitting stop-loss (was -1000, now -1.0)
                reward = self._calculate_reward(realized_pnl, commission, current_price)
                reward -= 1.0  # Moderate penalty for cut-loss
                
                # Update win streak
                if realized_pnl > 0:
                    self.current_win_streak += 1
                else:
                    self.current_win_streak = 0
                
                logger.warning(f"🔴 STOP LOSS HIT: PnL=${realized_pnl:.2f}, Penalty=-1.0")
                
                # Reset TP/SL
                self.take_profit = 0.0
                self.stop_loss = 0.0
                
                obs = self._get_observation()
                info = self._get_info()
                return obs, reward, False, False, info
        
        # EOD RISK KILL-SWITCH: Force flat by 15:55 ET (5 min before close)
        # Trading day is 390 minutes (9:30-16:00), so step 385 = 15:55
        minutes_to_close = 390 - self.steps
        if minutes_to_close <= 5 and self.position_qty != 0:
            # Override action to CLOSE
            action = 0  # Force close
            logger.debug(f"⚠️  EOD kill-switch: Forcing flat with {minutes_to_close} min to close")
        
        # Execute parent step
        obs, reward, terminated, truncated, info = super().step(action)
        
        # Penalize overnight carry (if still holding at EOD) - DISABLED IN BOOTSTRAP
        carry_enabled = (self.curriculum_stage != "stage_00_bootstrap")
        if carry_enabled and minutes_to_close <= 0 and self.position_qty != 0:
            reward -= 5.0  # Fixed closeout penalty
            logger.warning(f"💸 Overnight carry penalty: -5.0 (position={self.position_qty})")
        
        # Track returns for Sharpe calculation
        if self.daily_pnl != 0:
            daily_return = self.daily_pnl / self.initial_capital
            self.daily_returns.append(daily_return)
        
        # Early stop on great days (lock in wins) - DISABLED IN BC MODE
        if not self.bc_mode and self.daily_pnl > 250.0:  # $250+ profit
            logger.info(f"🎯 Early stop: Locked in ${self.daily_pnl:.2f} profit!")
            terminated = True
            reward += 5.0  # Moderate bonus
        
        # Early stop on bad days (cut losses) - DISABLED IN BOOTSTRAP
        curriculum_stage = getattr(self, 'curriculum_stage', 'stage_00_bootstrap')
        if not self.bc_mode and curriculum_stage != "stage_00_bootstrap" and self.daily_pnl < -250.0:
            logger.info(f"🛑 Early stop: Cut loss at ${self.daily_pnl:.2f}")
            terminated = True
            reward -= 3.0  # Moderate penalty
        
        info['win_rate'] = self._compute_win_rate()
        info['curriculum_stage'] = self.curriculum_stage
        info['obs_noise_std'] = self.obs_noise_std

        return obs, reward, terminated, truncated, info


class StableRewardHighWinRateEnv(HighWinRateEnv):
    """High win rate environment with numerically stable reward shaping."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reward_scaling_factor = 0.01
        self.min_reward = -10.0
        self.max_reward = 10.0
        self.reward_profile = "stable"

    def _calculate_reward(
        self,
        realized_pnl: float,
        commission: float,
        current_price: float,
    ) -> float:
        reward = 0.0

        # 1. PnL component (bounded via tanh)
        reward += float(np.tanh(self.daily_pnl * 0.001) * 3.0)

        # 2. Sharpe component using recent returns
        if len(self.daily_returns) >= 10:
            returns = np.array(self.daily_returns[-50:])
            mean_ret = float(np.mean(returns))
            std_ret = float(np.std(returns) + 1e-6)
            sharpe = mean_ret / std_ret * np.sqrt(252.0)
            reward += float(np.tanh(sharpe * 0.5) * 2.0)

        # 3. Win rate component using recent trade outcomes
        recent_trade_flags = self.trade_wins[-20:]
        if recent_trade_flags:
            win_rate = float(np.mean(recent_trade_flags)) if recent_trade_flags else 0.5
            reward += (win_rate - 0.5) * 4.0

        # 4. Position sizing discipline (portfolio percentage)
        if self.position_qty != 0 and current_price > 0:
            position_value = abs(self.position_qty * current_price)
            portfolio_pct = position_value / self.initial_capital
            if 0.01 <= portfolio_pct <= 0.05:
                reward += 0.5
            elif portfolio_pct > 0.10:
                reward -= 2.0

        # 5. Drawdown penalty
        current_drawdown = min(0.0, self.daily_pnl / self.initial_capital)
        if current_drawdown < -0.02:
            reward += (current_drawdown + 0.02) * 100.0

        # 6. Commission efficiency
        total_commission = sum(t.get('commission', 0.0) for t in getattr(self, 'trade_history', []))
        if total_commission > 0:
            commission_ratio = total_commission / (abs(self.daily_pnl) + 1e-6)
            if commission_ratio > 0.1:
                reward -= 1.0

        return float(np.clip(reward, self.min_reward, self.max_reward))


@dataclass
class CurriculumStage:
    name: str
    min_timesteps: int
    target_win_rate: float
    reward_profile: str
    obs_noise_std: float
    max_trades_per_day: int
    max_daily_loss: float
    tp_multiplier: float
    sl_atr_multiplier: float
    description: str = ""


class CurriculumLearningManager:
    def __init__(self, env: HighWinRateEnv, stages: List[CurriculumStage]):
        if not stages:
            raise ValueError("Curriculum requires at least one stage")
        self.env = env
        self.stages = stages
        self.current_stage_index = 0
        self._apply_stage(self.stages[0])

    @property
    def current_stage(self) -> CurriculumStage:
        return self.stages[self.current_stage_index]

    def maybe_advance(self, metrics: Dict[str, float], timesteps: int) -> bool:
        if self.current_stage_index >= len(self.stages) - 1:
            logger.info("  Already at final stage, cannot advance")
            return False

        next_stage = self.stages[self.current_stage_index + 1]
        current_stage = self.current_stage
        win_rate = metrics.get('win_rate', 0.0)

        meets_time = timesteps >= next_stage.min_timesteps
        meets_win_rate = win_rate >= next_stage.target_win_rate if win_rate is not None else False
        
        # Special case: Bootstrap stage with 0% target should auto-advance after min_timesteps
        # This handles edge case where 0.0 >= 0.0 might have floating point issues
        if current_stage.name == "stage_00_bootstrap" and next_stage.target_win_rate == 0.0:
            meets_win_rate = True  # Always pass win rate check for bootstrap->confidence
            logger.info("  Bootstrap stage: auto-passing win rate check (0% target)")

        # Verbose logging
        logger.info(
            f"  Next stage: {next_stage.name}\n"
            f"    Requires: {next_stage.min_timesteps:,} timesteps, {next_stage.target_win_rate:.1f}% win rate\n"
            f"    Current: {timesteps:,} timesteps, {win_rate:.1f}% win rate\n"
            f"    Meets time: {meets_time} | Meets win_rate: {meets_win_rate}"
        )

        if meets_time and meets_win_rate:
            self.current_stage_index += 1
            self._apply_stage(self.current_stage)
            logger.info(
                "🎯 Curriculum advanced to %s (win_rate=%.1f%%, timesteps=%s)",
                self.current_stage.name,
                win_rate,
                f"{timesteps:,}",
            )
            return True

        return False

    def _apply_stage(self, stage: CurriculumStage) -> None:
        if stage.reward_profile == "stable" and not isinstance(self.env, StableRewardHighWinRateEnv):
            logger.warning("Stable reward requested but environment is legacy; continuing with legacy reward")
        if stage.reward_profile == "legacy" and isinstance(self.env, StableRewardHighWinRateEnv):
            logger.warning("Legacy reward requested but environment is stable; continuing with stable reward")

        self.env.curriculum_stage = stage.name
        self.env.set_observation_noise(stage.obs_noise_std)
        self.env.max_trades_per_day = stage.max_trades_per_day
        self.env.max_daily_loss = stage.max_daily_loss
        self.env.tp_multiplier = stage.tp_multiplier
        self.env.sl_atr_multiplier = stage.sl_atr_multiplier
        self.env.reward_profile = stage.reward_profile

        logger.info(
            "📈 Applied curriculum stage %s | trades=%d | loss=%.0f | noise=%.4f",
            stage.name,
            stage.max_trades_per_day,
            stage.max_daily_loss,
            stage.obs_noise_std,
        )


class CurriculumCallback(BaseCallback):
    def __init__(
        self,
        manager: CurriculumLearningManager,
        metrics_fn: Callable[[], Dict[str, float]],
        check_freq: int = 5000,
        verbose: int = 0,
    ):
        super().__init__(verbose=verbose)
        self.manager = manager
        self.metrics_fn = metrics_fn
        self.check_freq = max(1, check_freq)

    def _on_step(self) -> bool:
        if self.n_calls % self.check_freq != 0:
            return True

        metrics = self.metrics_fn() or {}
        
        # Verbose logging for debugging
        logger.info(
            f"\n🔍 CURRICULUM CHECK at step {self.model.num_timesteps:,}:\n"
            f"  Current stage: {self.manager.current_stage.name}\n"
            f"  Metrics: {metrics}\n"
        )
        
        advanced = self.manager.maybe_advance(metrics, self.model.num_timesteps)

        if advanced and self.logger:
            self.logger.record('curriculum/stage', self.manager.current_stage_index)
            self.logger.record('curriculum/stage_name', self.manager.current_stage.name)

        return True


class AdaptiveEarlyStopping(BaseCallback):
    def __init__(
        self,
        metrics_fn: Callable[[], Dict[str, float]],
        monitor: str = 'win_rate',
        patience: int = 3,
        min_delta: float = 1.0,
        check_freq: int = 5000,
        verbose: int = 0,
    ):
        super().__init__(verbose=verbose)
        self.metrics_fn = metrics_fn
        self.monitor = monitor
        self.patience = max(1, patience)
        self.min_delta = min_delta
        self.check_freq = max(1, check_freq)
        self.best_score: Optional[float] = None
        self.rounds_without_improvement = 0

    def _on_step(self) -> bool:
        if self.n_calls % self.check_freq != 0:
            return True

        metrics = self.metrics_fn() or {}
        value = metrics.get(self.monitor)

        if value is None:
            return True

        if self.best_score is None or value > self.best_score + self.min_delta:
            self.best_score = value
            self.rounds_without_improvement = 0
        else:
            self.rounds_without_improvement += 1
            if self.rounds_without_improvement >= self.patience:
                logger.warning(
                    "⏹️  Adaptive early stopping triggered on %s (score=%.2f, best=%.2f)",
                    self.monitor,
                    value,
                    self.best_score,
                )
                if self.logger:
                    self.logger.record('early_stop/triggered', 1)
                self.stop_training = True
                return False

        if self.logger and self.best_score is not None:
            self.logger.record(f'early_stop/{self.monitor}_best', self.best_score)

        return True


class HyperparameterScheduler(BaseCallback):
    def __init__(
        self,
        total_timesteps: int,
        initial_lr: float,
        final_lr: float,
        initial_ent_coef: float,
        final_ent_coef: float,
        check_freq: int = 2000,
        verbose: int = 0,
    ):
        super().__init__(verbose=verbose)
        self.total_timesteps = max(1, total_timesteps)
        self.initial_lr = initial_lr
        self.final_lr = final_lr
        self.initial_ent_coef = initial_ent_coef
        self.final_ent_coef = final_ent_coef
        self.check_freq = max(1, check_freq)

    def _on_step(self) -> bool:
        if self.n_calls % self.check_freq != 0:
            return True

        progress = min(max(self.model.num_timesteps / self.total_timesteps, 0.0), 1.0)

        new_lr = self.initial_lr + (self.final_lr - self.initial_lr) * progress
        new_ent_coef = self.initial_ent_coef + (self.final_ent_coef - self.initial_ent_coef) * progress

        for param_group in self.model.policy.optimizer.param_groups:
            param_group['lr'] = new_lr

        self.model.ent_coef = new_ent_coef

        if self.logger:
            self.logger.record('schedule/lr', new_lr)
            self.logger.record('schedule/ent_coef', new_ent_coef)

        return True


class MetricsWriterCallback(BaseCallback):
    def __init__(
        self,
        metrics_fn: Callable[[], Dict[str, float]],
        output_path: Path,
        write_freq: int = 5000,
        verbose: int = 0,
    ):
        super().__init__(verbose=verbose)
        self.metrics_fn = metrics_fn
        self.output_path = output_path
        self.write_freq = max(1, write_freq)

        # Ensure directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def _on_step(self) -> bool:
        if self.n_calls % self.write_freq != 0:
            return True

        metrics = self.metrics_fn() or {}
        metrics.update({
            'timesteps': self.model.num_timesteps,
            'timestamp': datetime.now(UTC).isoformat(),
        })

        try:
            if self.output_path.exists():
                with self.output_path.open('r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = []

            history.append(metrics)

            with self.output_path.open('w', encoding='utf-8') as f:
                json.dump(history[-200:], f, indent=2)
        except Exception as exc:
            logger.warning("Failed to write metrics checkpoint: %s", exc)

        return True


def create_env(
    pipeline,
    microstructure,
    momentum,
    normalize: bool = True,
    reward_profile: str = 'stable',
    bc_mode: bool = False,
) -> Tuple[Any, HighWinRateEnv]:
    """
    Create monitored environment with optional VecNormalize wrapper.
    
    Returns tuple of (vec_env or env, base_env) so curriculum callbacks can mutate base env.
    """

    env_cls = StableRewardHighWinRateEnv if reward_profile == 'stable' else HighWinRateEnv
    base_env_holder: Dict[str, HighWinRateEnv] = {}

    def make_env():
        inner_env = env_cls(
            pipeline=pipeline,
            microstructure=microstructure,
            momentum=momentum,
            initial_capital=25000.0,
            max_position=25,  # Reduced from 50 to 25 to limit position risk
            max_daily_loss=500.0,  # Increased from 125 to 500 to allow more exploration before stopping
            max_trades_per_day=20,
            bc_mode=bc_mode,
            enable_per_trade_stop=False,  # Disable per-trade stops to allow exploration
        )
        inner_env.reward_profile = reward_profile
        base_env_holder['env'] = inner_env
        return Monitor(inner_env)

    if normalize:
        vec_env = DummyVecEnv([make_env])
        vec_env = VecNormalize(
            vec_env,
            norm_obs=True,
            norm_reward=True,
            clip_obs=5.0,  # Reduced from 10.0 to 5.0 for tighter clipping
            clip_reward=5.0,  # Reduced from 10.0 to 5.0 to match scaled rewards
            gamma=0.995,  # Increased from 0.99 for longer horizon
        )
        logger.info("✅ VecNormalize enabled (obs + reward scaling)")
        return vec_env, base_env_holder['env']

    env = make_env()
    return env, base_env_holder['env']


def train_ppo(
    ib: IB,
    symbol: str = 'SPY',
    duration: str = '30 D',
    total_timesteps: int = 1_000_000,
    learning_rate: float = 1e-4,  # Reduced from 3e-4 for calmer updates
    final_learning_rate: float = 5e-5,  # Reduced from 1e-4
    n_steps: int = 4096,  # Increased from 2048 for longer rollouts
    batch_size: int = 8192,  # Increased from 64 for smoother gradients (if RAM allows, else 4096)
    n_epochs: int = 10,
    save_freq: int = 100_000,
    device: str = 'auto',
    microstructure_mode: str = 'legacy',
    microstructure_norm: str = 'off',
    reward_profile: str = 'stable',
    curriculum_enabled: bool = True,
    final_ent_coef: float = 0.0005,  # Reduced from 0.005 for less randomness
    early_stop_patience: int = 4,
    curriculum_check_freq: int = 5000,
):
    """
    Train PPO agent with high win rate optimization.
    
    Args:
        ib: IB connection
        symbol: Trading symbol
        duration: Historical data duration
        total_timesteps: Training steps
        learning_rate: PPO learning rate
        n_steps: Steps per rollout
        batch_size: Minibatch size
        n_epochs: Optimization epochs per rollout
        save_freq: Save checkpoint every N steps
        device: 'cpu', 'cuda', or 'auto'
        microstructure_mode: 'legacy' for 15-dim adapter or 'extended' for full feature stack
        microstructure_norm: Microstructure normalization ('off', 'robust', 'minmax')
        reward_profile: 'stable' or 'legacy' reward shaping
        curriculum_enabled: Toggle curriculum progression callbacks
        final_learning_rate: Target LR at end of schedule
        final_ent_coef: Target entropy coefficient at end of schedule
        early_stop_patience: Early stopping tolerance (check intervals)
        curriculum_check_freq: Step frequency for curriculum/scheduler checks
    """
    initial_ent_coef = 0.01
    
    # Set deterministic seed for reproducibility
    seed = 42
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

    logger.info(f"\n{'='*60}")
    logger.info(f"🚀 TRAINING HIGH WIN RATE INTRADAY TRADER")
    logger.info(f"{'='*60}")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Duration: {duration}")
    logger.info(f"Total timesteps: {total_timesteps:,}")
    logger.info(f"Learning rate: {learning_rate}")
    logger.info(f"Final learning rate: {final_learning_rate}")
    logger.info(f"Entropy coef (start→end): {initial_ent_coef}→{final_ent_coef}")
    logger.info(f"Reward profile: {reward_profile}")
    logger.info(f"Curriculum: {'enabled' if curriculum_enabled else 'disabled'}")
    logger.info(f"Device: {device}")
    logger.info(f"{'='*60}\n")

    curriculum_check_freq = max(500, curriculum_check_freq)
    
    # CPU optimization for Windows
    cpu_count = os.cpu_count() or 1
    torch_threads = max(cpu_count // 2, 1)
    torch.set_num_threads(torch_threads)
    os.environ["KMP_AFFINITY"] = "granularity=fine,compact,1,0"
    logger.info(f"⚙️  CPU optimization: {torch_threads}/{cpu_count} threads")
    
    # Create data pipeline (historical mode)
    logger.info(f"📊 Fetching {duration} of historical data for {symbol}...")
    pipeline = EnhancedDataPipeline(
        mode='historical',
        ib=ib,
        symbol=symbol,
        duration=duration,
        replay_speed=100.0,  # 100x faster
        tick_buffer_size=10000,
        bar_buffer_size=500,
    )
    
    pipeline.start()
    
    # Wait for data collection
    logger.info("⏳ Waiting for data collection (30 seconds)...")
    time.sleep(30)
    
    stats = pipeline.get_stats()
    logger.info(f"✅ Data ready: {stats['ticks_collected']:,} ticks, "
                f"{stats['bars_collected']} bars")
    
    # Create features
    logger.info("🔧 Initializing feature engines...")
    microstructure = build_microstructure_features(
        pipeline,
        mode=microstructure_mode,
        normalization=microstructure_norm,
    )
    micro_feature_names = getattr(microstructure, "get_feature_names", lambda: [])()
    if micro_feature_names:
        micro_feature_count = len(micro_feature_names)
    else:
        try:
            micro_feature_count = len(np.asarray(microstructure.compute()))
        except Exception:
            micro_feature_count = "unknown"
    logger.info(
        "  Microstructure mode=%s, dims=%s, normalization=%s",
        microstructure_mode,
        micro_feature_count,
        microstructure_norm,
    )
    momentum = MomentumFeatures(pipeline, check_stale=False)  # Disable stale check for historical replay
    
    # Create environment
    logger.info("🎮 Creating training environment...")
    env, base_env = create_env(
        pipeline,
        microstructure,
        momentum,
        normalize=True,
        reward_profile=reward_profile,
    )

    curriculum_stages = [
        CurriculumStage(
            name="stage_00_bootstrap",
            min_timesteps=0,
            target_win_rate=0.0,  # No win rate requirement - auto-advance at min_timesteps
            reward_profile=reward_profile,
            obs_noise_std=0.0,
            max_trades_per_day=30,  # Allow exploration
            max_daily_loss=500.0,  # Increased from 400 to prevent premature stops
            tp_multiplier=2.5,
            sl_atr_multiplier=1.2,
            description="Bootstrap exploration - no win rate requirement",
        ),
        CurriculumStage(
            name="stage_01_confidence",
            min_timesteps=10_000,
            target_win_rate=25.0,  # REDUCED from 52% to 25% - more achievable initial target
            reward_profile=reward_profile,
            obs_noise_std=0.002,
            max_trades_per_day=20,  # Reduced from 30 to encourage quality
            max_daily_loss=500.0,
            tp_multiplier=2.8,
            sl_atr_multiplier=1.4,
            description="Build confidence with 25% win rate target",
        ),
        CurriculumStage(
            name="stage_02_production",
            min_timesteps=50_000,
            target_win_rate=40.0,  # REDUCED from 58% to 40% - realistic long-term target
            reward_profile=reward_profile,
            obs_noise_std=0.004,
            max_trades_per_day=15,  # Reduced to encourage selectivity
            max_daily_loss=500.0,
            tp_multiplier=3.0,
            sl_atr_multiplier=1.5,
            description="Production-ready with 40% win rate target",
        ),
    ]

    if curriculum_enabled:
        logger.info("📚 Curriculum stages:")
        for stage in curriculum_stages:
            logger.info(
                "  - %s | min_steps=%s | target_win=%.1f%% | noise=%.3f",
                stage.name,
                f"{stage.min_timesteps:,}",
                stage.target_win_rate,
                stage.obs_noise_std,
            )

    curriculum_manager = CurriculumLearningManager(base_env, curriculum_stages)

    # Setup callbacks
    log_dir = Path('logs') / f"ppo_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    log_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_callback = CheckpointCallback(
        save_freq=save_freq,
        save_path=str(log_dir / 'checkpoints'),
        name_prefix='ppo_model',
        save_replay_buffer=False,
        save_vecnormalize=False,
    )

    win_rate_callback = WinRateCallback(check_freq=1000)

    metrics_provider = win_rate_callback.get_recent_metrics
    callbacks_chain: List[BaseCallback] = [checkpoint_callback, win_rate_callback]

    scheduler_check_freq = max(curriculum_check_freq // 2, 1000)
    callbacks_chain.append(
        HyperparameterScheduler(
            total_timesteps=total_timesteps,
            initial_lr=learning_rate,
            final_lr=final_learning_rate,
            initial_ent_coef=initial_ent_coef,
            final_ent_coef=final_ent_coef,
            check_freq=scheduler_check_freq,
        )
    )

    callbacks_chain.append(
        MetricsWriterCallback(
            metrics_fn=metrics_provider,
            output_path=log_dir / 'metrics.json',
            write_freq=curriculum_check_freq,
        )
    )

    if curriculum_enabled:
        callbacks_chain.append(
            CurriculumCallback(
                manager=curriculum_manager,
                metrics_fn=metrics_provider,
                check_freq=curriculum_check_freq,
            )
        )

    callbacks_chain.append(
        AdaptiveEarlyStopping(
            metrics_fn=metrics_provider,
            monitor='win_rate',
            patience=early_stop_patience,
            min_delta=1.0,
            check_freq=curriculum_check_freq,
        )
    )

    callbacks = CallbackList(callbacks_chain)
    
    # Create PPO model
    logger.info("🤖 Creating PPO model...")
    logger.info(f"  Policy: MlpPolicy [256, 256, 128]")
    logger.info(f"  Learning rate: {learning_rate}")
    logger.info(f"  Batch size: {batch_size}")
    logger.info(f"  N steps: {n_steps}")
    
    # Configure custom logger for TensorBoard
    custom_logger = configure(str(log_dir), ["stdout", "tensorboard"])
    
    model = PPO(
        'MlpPolicy',
        env,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=n_steps,  # For single env: batch_size = n_steps (buffer size)
        n_epochs=n_epochs,
        gamma=0.995,  # Slightly increased from 0.99 for longer-term planning
        gae_lambda=0.95,
        clip_range=0.10,  # Maintain tight clipping
        clip_range_vf=None,
        normalize_advantage=True,
        ent_coef=0.0005,  # Reduced from 0.001 to 0.0005 for tighter exploration
        vf_coef=0.5,
        max_grad_norm=0.5,
        target_kl=0.08,  # Relaxed to reduce early stopping frequency
        policy_kwargs=dict(
            net_arch=[256, 256, 128],  # Larger network
            activation_fn=torch.nn.ReLU,
        ),
        tensorboard_log=str(log_dir),
        device=device,
        verbose=1,
    )
    
    # Set custom logger
    model.set_logger(custom_logger)
    logger.info("📊 TensorBoard logging enabled")
    
    # Train
    logger.info(f"\n{'='*60}")
    logger.info(f"🏋️  STARTING TRAINING ({total_timesteps:,} timesteps)")
    logger.info(f"{'='*60}\n")
    
    start_time = time.time()
    
    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            log_interval=10,
            tb_log_name='ppo',
            reset_num_timesteps=True,
            progress_bar=True,
        )
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Training interrupted by user")
    
    training_time = time.time() - start_time
    
    # Save final model and VecNormalize stats
    final_model_path = log_dir / 'final_model.zip'
    model.save(str(final_model_path))
    
    # Save VecNormalize stats if using normalization
    if isinstance(env, VecNormalize):
        vecnorm_path = log_dir / 'vecnorm.pkl'
        env.save(str(vecnorm_path))
        logger.info(f"VecNormalize stats saved: {vecnorm_path}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ TRAINING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Training time: {training_time/60:.1f} minutes")
    logger.info(f"Model saved: {final_model_path}")
    logger.info(f"Logs: {log_dir}")
    logger.info(f"Best win rate: {win_rate_callback.best_win_rate:.1f}%")
    logger.info(f"Best Sharpe: {win_rate_callback.best_sharpe:.2f}")
    logger.info(f"Final curriculum stage: {curriculum_manager.current_stage.name}")
    logger.info(f"{'='*60}\n")
    
    # Cleanup
    pipeline.stop()
    
    return model, log_dir


def main():
    parser = argparse.ArgumentParser(description='Train PPO for intraday trading')
    parser.add_argument('--symbol', type=str, default='SPY', help='Trading symbol')
    parser.add_argument('--duration', type=str, default='30 D', help='Historical data duration')
    parser.add_argument('--timesteps', type=int, default=1_000_000, help='Total training timesteps')
    parser.add_argument('--lr', type=float, default=1e-4, help='Learning rate (lowered for stability)')
    parser.add_argument('--n-steps', type=int, default=4096, help='Steps per rollout (increased for longer episodes)')
    parser.add_argument('--batch-size', type=int, default=4096, help='Minibatch size (must equal n_steps for single env)')
    parser.add_argument('--save-freq', type=int, default=100_000, help='Save frequency')
    parser.add_argument('--device', type=str, default='auto', help='Device (cpu/cuda/auto)')
    parser.add_argument(
        '--microstructure-mode',
        type=str,
        choices=['legacy', 'extended'],
        default='legacy',
        help='Microstructure feature configuration',
    )
    parser.add_argument(
        '--microstructure-norm',
        type=str,
        choices=['off', 'robust', 'minmax'],
        default='off',
        help='Microstructure normalization strategy',
    )
    parser.add_argument('--host', type=str, default='127.0.0.1', help='IBKR host')
    parser.add_argument('--port', type=int, default=7497, help='IBKR port (7497=paper, 7496=live)')
    parser.add_argument('--reward-profile', type=str, choices=['stable', 'legacy'], default='stable', help='Reward shaping strategy')
    parser.add_argument('--final-lr', type=float, default=5e-5, help='Final learning rate for scheduler')
    parser.add_argument('--final-ent', type=float, default=0.0005, help='Final entropy coefficient for scheduler')
    parser.add_argument('--early-stop-patience', type=int, default=4, help='Early stopping patience (check intervals)')
    parser.add_argument('--disable-curriculum', action='store_true', help='Disable curriculum progression callbacks')
    parser.add_argument('--curriculum-check-freq', type=int, default=5000, help='Frequency for curriculum/metric checks')
    
    args = parser.parse_args()
    
    # Connect to IBKR
    logger.info("🔌 Connecting to IBKR...")
    ib = IB()
    
    try:
        ib.connect(args.host, args.port, clientId=2)
        logger.info(f"✅ Connected to IBKR at {args.host}:{args.port}")
        logger.info(f"   Account: {ib.managedAccounts()}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to IBKR: {e}")
        logger.error("\nMake sure TWS/Gateway is running and API is enabled")
        return 1
    
    try:
        # Train
        model, log_dir = train_ppo(
            ib=ib,
            symbol=args.symbol,
            duration=args.duration,
            total_timesteps=args.timesteps,
            learning_rate=args.lr,
            final_learning_rate=args.final_lr,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            save_freq=args.save_freq,
            device=args.device,
            microstructure_mode=args.microstructure_mode,
            microstructure_norm=args.microstructure_norm,
            reward_profile=args.reward_profile,
            curriculum_enabled=not args.disable_curriculum,
            final_ent_coef=args.final_ent,
            early_stop_patience=args.early_stop_patience,
            curriculum_check_freq=args.curriculum_check_freq,
        )
        
        logger.info("\n🎉 SUCCESS! Model ready for backtesting/paper trading.")
        logger.info(f"\nNext steps:")
        logger.info(f"  1. View logs: tensorboard --logdir {log_dir}")
        logger.info(f"  2. Backtest: python scripts/backtest_intraday.py --model {log_dir}/final_model.zip")
        logger.info(f"  3. Paper trade: python scripts/paper_trade_intraday.py --model {log_dir}/final_model.zip")
        
        return 0
    
    finally:
        ib.disconnect()
        logger.info("\n🧹 Disconnected from IBKR")


if __name__ == '__main__':
    exit(main())
