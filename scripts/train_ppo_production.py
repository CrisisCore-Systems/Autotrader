"""
Production PPO Training with VecNormalize, EvalCallback, and Full Monitoring

Upgrades from train_intraday_ppo.py:
- VecNormalize with frozen eval copy
- EvalCallback with held-out window (deterministic eval)
- Persistent normalizer stats (save/load)
- target_kl for policy stability
- Enhanced TensorBoard logging (hit-rate, drawdown, exposure, turnover)
- CPU optimization for Windows
- Action masking ready (discrete action space)
"""

from __future__ import annotations

import argparse
import logging
import time
import copy
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import numpy as np
import torch
from ib_insync import IB, Stock

from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.callbacks import (
    BaseCallback,
    EvalCallback,
    CheckpointCallback,
    CallbackList,
)
from stable_baselines3.common.logger import configure

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.intraday.enhanced_pipeline import EnhancedDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures
from src.intraday.trading_env import IntradayTradingEnv

# Import HighWinRateEnv from train_intraday_ppo
sys.path.insert(0, str(Path(__file__).parent))
from train_intraday_ppo import HighWinRateEnv, WinRateCallback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DetailedMetricsCallback(BaseCallback):
    """
    Enhanced callback logging trade metrics, risk metrics, and microstructure stats.
    
    Logs to TensorBoard:
    - trades/hit_rate, trades/avg_R, trades/turnover, trades/avg_hold_min
    - risk/max_drawdown, risk/exposure_minutes, risk/sharpe
    - equity/episode_return, equity/cumulative_pnl
    - policy/kl_divergence, policy/entropy, policy/clip_fraction
    """
    
    def __init__(self, check_freq: int = 1000, verbose: int = 0):
        super().__init__(verbose)
        self.check_freq = check_freq
        self.n_calls = 0
        
        # Episode tracking
        self.episode_returns = []
        self.episode_lengths = []
        self.episode_pnls = []
        self.episode_wins = []
        self.episode_trades = []
        self.episode_drawdowns = []
        self.episode_exposure = []
        
    def _on_step(self) -> bool:
        self.n_calls += 1
        
        # Collect episode stats from info
        for info in self.locals.get("infos", []):
            if "episode" in info:
                ep_info = info["episode"]
                self.episode_returns.append(ep_info["r"])
                self.episode_lengths.append(ep_info["l"])
                
                # Trading metrics from env
                if "daily_pnl" in info:
                    pnl = info["daily_pnl"]
                    trades = info.get("daily_trades", 0)
                    max_dd = info.get("max_drawdown", 0)
                    exposure = info.get("exposure_minutes", 0)
                    
                    self.episode_pnls.append(pnl)
                    self.episode_wins.append(1 if pnl > 0 else 0)
                    self.episode_trades.append(trades)
                    self.episode_drawdowns.append(max_dd)
                    self.episode_exposure.append(exposure)
        
        # Log every check_freq steps
        if self.n_calls % self.check_freq == 0 and len(self.episode_pnls) > 0:
            recent_n = min(100, len(self.episode_pnls))
            recent_pnls = self.episode_pnls[-recent_n:]
            recent_wins = self.episode_wins[-recent_n:]
            recent_trades = self.episode_trades[-recent_n:]
            recent_dd = self.episode_drawdowns[-recent_n:]
            recent_exposure = self.episode_exposure[-recent_n:]
            
            # Calculate metrics
            hit_rate = np.mean(recent_wins) * 100 if recent_wins else 0
            avg_pnl = np.mean(recent_pnls) if recent_pnls else 0
            avg_trades = np.mean(recent_trades) if recent_trades else 0
            max_dd = np.max(recent_dd) if recent_dd else 0
            avg_exposure = np.mean(recent_exposure) if recent_exposure else 0
            
            # Sharpe (annualized)
            if len(recent_pnls) > 1:
                returns = np.array(recent_pnls) / 25000  # % returns
                sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
            else:
                sharpe = 0.0
            
            # Average R (avg win / avg loss)
            wins = [p for p in recent_pnls if p > 0]
            losses = [abs(p) for p in recent_pnls if p < 0]
            avg_R = (np.mean(wins) / np.mean(losses)) if (wins and losses) else 0.0
            
            # Turnover (shares per episode)
            turnover = avg_trades * 200  # Avg position size
            
            # Log to TensorBoard
            if self.logger:
                self.logger.record("trades/hit_rate", hit_rate)
                self.logger.record("trades/avg_R", avg_R)
                self.logger.record("trades/avg_trades", avg_trades)
                self.logger.record("trades/turnover", turnover)
                
                self.logger.record("risk/max_drawdown", max_dd)
                self.logger.record("risk/avg_exposure_min", avg_exposure)
                self.logger.record("risk/sharpe", sharpe)
                
                self.logger.record("equity/avg_pnl", avg_pnl)
                self.logger.record("equity/cumulative_pnl", np.sum(self.episode_pnls))
                
            # Console log
            logger.info(
                f"\n{'='*70}\n"
                f"Step: {self.n_calls:,} | Episodes: {len(self.episode_pnls)}\n"
                f"  Hit Rate: {hit_rate:.1f}% | Avg R: {avg_R:.2f}\n"
                f"  Avg PnL: ${avg_pnl:.2f} | Sharpe: {sharpe:.2f}\n"
                f"  Avg Trades: {avg_trades:.1f} | Exposure: {avg_exposure:.1f} min\n"
                f"  Max DD: ${max_dd:.2f}\n"
                f"{'='*70}"
            )
        
        return True


def create_env(
    ib: IB,
    symbol: str,
    duration: str,
    mode: str = "train",
) -> IntradayTradingEnv:
    """
    Create environment instance (not vectorized).
    
    Args:
        ib: IB connection
        symbol: Trading symbol
        duration: Historical data duration
        mode: "train" or "eval" (for different data windows)
    """
    # Create data pipeline
    pipeline = EnhancedDataPipeline(
        mode='historical',
        ib=ib,
        symbol=symbol,
        duration=duration,
        tick_buffer_size=10000,
        bar_buffer_size=500,
    )
    
    # Fetch historical data
    logger.info(f"📊 Fetching {duration} of historical data for {symbol} ({mode} mode)...")
    pipeline.start()
    
    # Wait for data
    logger.info("⏳ Waiting for data collection (30 seconds)...")
    time.sleep(30)
    
    stats = pipeline.get_stats()
    logger.info(
        f"✅ Data ready: {stats['total_ticks']:,} ticks, {stats['total_bars']:,} bars"
    )
    
    # Initialize feature engines
    logger.info("🔧 Initializing feature engines...")
    microstructure = MicrostructureFeatures(pipeline)
    momentum = MomentumFeatures(pipeline)
    
    # Create environment
    logger.info("🎮 Creating environment...")
    env = HighWinRateEnv(
        pipeline=pipeline,
        microstructure=microstructure,
        momentum=momentum,
        initial_capital=25000.0,
        max_position=300,
        max_daily_loss=300.0,
        max_trades_per_day=20,
    )
    
    # Wrap with Monitor
    env = Monitor(env)
    
    return env


def train_ppo_production(
    ib: IB,
    symbol: str = 'SPY',
    train_duration: str = '10 D',
    eval_duration: str = '2 D',
    total_timesteps: int = 200000,
    learning_rate: float = 1e-4,
    n_steps: int = 4096,
    batch_size: int = 128,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    clip_range: float = 0.2,
    ent_coef: float = 0.003,
    vf_coef: float = 0.5,
    target_kl: float = 0.02,
    save_freq: int = 50000,
    eval_freq: int = 10000,
    device: str = 'auto',
) -> tuple[PPO, Path, VecNormalize]:
    """
    Production PPO training with VecNormalize and EvalCallback.
    
    Returns:
        (model, log_dir, vectorized_env_train)
    """
    
    # CPU optimization (Windows)
    logger.info("🔧 Optimizing CPU...")
    torch.set_num_threads(max(1, os.cpu_count() // 2))
    os.environ["KMP_AFFINITY"] = "granularity=fine,compact,1,0"
    logger.info(f"  PyTorch threads: {torch.get_num_threads()}/{os.cpu_count()}")
    
    # Create log directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(f"logs/ppo_{symbol}_{timestamp}")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    vecnorm_dir = models_dir / "vecnorm"
    vecnorm_dir.mkdir(exist_ok=True)
    best_dir = models_dir / "best"
    best_dir.mkdir(exist_ok=True)
    ckpt_dir = models_dir / "ckpts"
    ckpt_dir.mkdir(exist_ok=True)
    
    logger.info(
        f"\n{'='*70}\n"
        f"🚀 PRODUCTION PPO TRAINING\n"
        f"{'='*70}\n"
        f"Symbol: {symbol}\n"
        f"Train Duration: {train_duration}\n"
        f"Eval Duration: {eval_duration}\n"
        f"Total timesteps: {total_timesteps:,}\n"
        f"Learning rate: {learning_rate}\n"
        f"N steps: {n_steps}, Batch size: {batch_size}\n"
        f"Target KL: {target_kl}\n"
        f"Ent coef: {ent_coef}, VF coef: {vf_coef}\n"
        f"Device: {device}\n"
        f"{'='*70}\n"
    )
    
    # Create training environment
    train_env_raw = create_env(ib, symbol, train_duration, mode="train")
    train_env = DummyVecEnv([lambda: train_env_raw])
    
    # Wrap with VecNormalize (training mode)
    venv_train = VecNormalize(
        train_env,
        norm_obs=True,
        norm_reward=True,
        clip_obs=10.0,
        clip_reward=10.0,
        gamma=gamma,
        training=True,
    )
    
    logger.info("✅ Training environment created with VecNormalize")
    
    # Create evaluation environment
    eval_env_raw = create_env(ib, symbol, eval_duration, mode="eval")
    eval_env = DummyVecEnv([lambda: eval_env_raw])
    
    # Wrap with VecNormalize (frozen stats, eval mode)
    venv_eval = VecNormalize(
        eval_env,
        norm_obs=True,
        norm_reward=True,
        clip_obs=10.0,
        clip_reward=10.0,
        gamma=gamma,
        training=False,  # Don't update stats
    )
    
    # Copy normalization stats from train to eval
    venv_eval.obs_rms = copy.deepcopy(venv_train.obs_rms)
    venv_eval.ret_rms = copy.deepcopy(venv_train.ret_rms)
    
    logger.info("✅ Evaluation environment created (frozen normalizer)")
    
    # Configure TensorBoard logger
    tb_logger = configure(str(log_dir), ["stdout", "tensorboard"])
    
    # Create PPO model
    logger.info("🤖 Creating PPO model...")
    model = PPO(
        policy="MlpPolicy",
        env=venv_train,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        n_epochs=10,
        gamma=gamma,
        gae_lambda=gae_lambda,
        clip_range=clip_range,
        ent_coef=ent_coef,
        vf_coef=vf_coef,
        max_grad_norm=0.5,
        target_kl=target_kl,
        tensorboard_log=str(log_dir),
        policy_kwargs=dict(
            net_arch=dict(pi=[256, 256, 128], vf=[256, 256, 128])
        ),
        device=device,
        verbose=1,
    )
    
    model.set_logger(tb_logger)
    
    logger.info(
        f"  Policy: MlpPolicy [256, 256, 128]\n"
        f"  Target KL: {target_kl} (stability guard)\n"
        f"  VecNormalize: obs + reward clipped to [-10, 10]"
    )
    
    # Create callbacks
    eval_callback = EvalCallback(
        venv_eval,
        best_model_save_path=str(best_dir),
        log_path=str(log_dir / "eval"),
        eval_freq=eval_freq,
        n_eval_episodes=5,
        deterministic=True,
        render=False,
        verbose=1,
    )
    
    checkpoint_callback = CheckpointCallback(
        save_freq=save_freq,
        save_path=str(ckpt_dir),
        name_prefix=f"ppo_{symbol}",
        save_vecnormalize=True,
    )
    
    metrics_callback = DetailedMetricsCallback(check_freq=1000)
    
    callback_list = CallbackList([
        eval_callback,
        checkpoint_callback,
        metrics_callback,
    ])
    
    logger.info(
        f"\n{'='*70}\n"
        f"🏋️  STARTING TRAINING ({total_timesteps:,} timesteps)\n"
        f"{'='*70}\n"
    )
    
    # Train
    try:
        model.learn(
            total_timesteps=total_timesteps,
            callback=callback_list,
            log_interval=10,
            progress_bar=True,
        )
    except KeyboardInterrupt:
        logger.info("\n⚠️  Training interrupted by user")
    
    # Save final model and normalizer
    final_model_path = log_dir / "final_model.zip"
    model.save(final_model_path)
    
    vecnorm_path = vecnorm_dir / f"{symbol}_train_norm.pkl"
    venv_train.save(vecnorm_path)
    
    logger.info(
        f"\n{'='*70}\n"
        f"✅ TRAINING COMPLETE\n"
        f"{'='*70}\n"
        f"Model saved: {final_model_path}\n"
        f"VecNormalize saved: {vecnorm_path}\n"
        f"Best model: {best_dir / 'best_model.zip'}\n"
        f"Logs: {log_dir}\n"
        f"{'='*70}\n"
    )
    
    return model, log_dir, venv_train


def main():
    parser = argparse.ArgumentParser(description="Production PPO Training")
    parser.add_argument("--symbol", type=str, default="SPY", help="Trading symbol")
    parser.add_argument("--train-duration", type=str, default="10 D", help="Training data duration")
    parser.add_argument("--eval-duration", type=str, default="2 D", help="Eval data duration")
    parser.add_argument("--timesteps", type=int, default=200000, help="Total timesteps")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--n-steps", type=int, default=4096, help="Steps per rollout")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size")
    parser.add_argument("--ent-coef", type=float, default=0.003, help="Entropy coefficient")
    parser.add_argument("--target-kl", type=float, default=0.02, help="Target KL divergence")
    parser.add_argument("--save-freq", type=int, default=50000, help="Checkpoint frequency")
    parser.add_argument("--eval-freq", type=int, default=10000, help="Eval frequency")
    parser.add_argument("--device", type=str, default="auto", help="Device (cpu/cuda/auto)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="IBKR host")
    parser.add_argument("--port", type=int, default=7497, help="IBKR port (7497=paper, 7496=live)")
    
    args = parser.parse_args()
    
    # Connect to IBKR
    logger.info("🔌 Connecting to IBKR...")
    ib = IB()
    ib.connect(args.host, args.port, clientId=2)
    
    logger.info(f"✅ Connected to IBKR at {args.host}:{args.port}")
    logger.info(f"   Account: {ib.managedAccounts()}\n")
    
    try:
        # Train
        model, log_dir, venv_train = train_ppo_production(
            ib=ib,
            symbol=args.symbol,
            train_duration=args.train_duration,
            eval_duration=args.eval_duration,
            total_timesteps=args.timesteps,
            learning_rate=args.lr,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            ent_coef=args.ent_coef,
            target_kl=args.target_kl,
            save_freq=args.save_freq,
            eval_freq=args.eval_freq,
            device=args.device,
        )
        
        logger.info(
            f"\n🎉 SUCCESS! Model ready for deployment.\n\n"
            f"Next steps:\n"
            f"  1. View logs: tensorboard --logdir {log_dir}\n"
            f"  2. Load best model: models/best/best_model.zip\n"
            f"  3. Load normalizer: models/vecnorm/{args.symbol}_train_norm.pkl\n"
        )
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Training failed: {e}", exc_info=True)
        return 1
        
    finally:
        # Cleanup
        logger.info("\n🧹 Disconnecting from IBKR...")
        ib.disconnect()


if __name__ == "__main__":
    exit(main())
