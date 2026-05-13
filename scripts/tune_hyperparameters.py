"""
Hyperparameter Tuning for Intraday PPO Trading Agent

Uses Optuna (Bayesian optimization) to find optimal PPO hyperparameters.

Goal: Maximize win rate while maintaining stable training.

Tunable Parameters:
- Learning rate (1e-5 to 1e-3)
- Entropy coefficient (0.001 to 0.1)
- Batch size (256, 512, 1024, 2048)
- N steps (1024, 2048, 4096)
- Clip range (0.1 to 0.3)
- Gamma (0.95 to 0.995)
- GAE lambda (0.9 to 0.99)
- Network architecture ([128,128], [256,256], [256,256,128])

Usage:
    python scripts/tune_hyperparameters.py --trials 50 --timesteps 50000
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Any, List

import numpy as np
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
import torch

try:
    from ib_insync import IB
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.callbacks import BaseCallback, CallbackList
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("\nInstall required packages:")
    print("  pip install optuna ib_insync stable-baselines3[extra] torch")
    exit(1)

import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.intraday import (
    EnhancedDataPipeline,
    MicrostructureFeatures,
    MomentumFeatures,
    RobustMicrostructureFeatures,
    LegacyMicrostructureAdapter,
)

# Import training components
from scripts.train_intraday_ppo import (
    StableRewardHighWinRateEnv,
    WinRateCallback,
    build_microstructure_features,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptunaPruningCallback(BaseCallback):
    """
    Callback for pruning unpromising trials during training.
    
    Reports intermediate win rate values to Optuna and prunes trials
    that perform poorly compared to other trials.
    """
    
    def __init__(
        self,
        trial: optuna.Trial,
        win_rate_callback: WinRateCallback,
        eval_freq: int = 5000,
        verbose: int = 0,
    ):
        super().__init__(verbose)
        self.trial = trial
        self.win_rate_callback = win_rate_callback
        self.eval_freq = eval_freq
        self.last_eval_step = 0
        
    def _on_step(self) -> bool:
        if self.n_calls - self.last_eval_step < self.eval_freq:
            return True
        
        self.last_eval_step = self.n_calls
        
        # Get current metrics
        metrics = self.win_rate_callback.get_recent_metrics()
        win_rate = metrics.get('win_rate', 0.0)
        
        # Report to Optuna
        self.trial.report(win_rate, self.n_calls)
        
        # Check if trial should be pruned
        if self.trial.should_prune():
            logger.warning(
                f"🔪 Trial pruned at step {self.n_calls:,} "
                f"(win_rate={win_rate:.1f}%)"
            )
            raise optuna.TrialPruned()
        
        return True


def create_tuning_env(
    pipeline,
    microstructure,
    momentum,
    normalize: bool = True,
) -> tuple:
    """Create environment for hyperparameter tuning with pipeline restart on reset."""
    
    base_env_holder: Dict[str, Any] = {}
    
    def make_env():
        inner_env = StableRewardHighWinRateEnv(
            pipeline=pipeline,
            microstructure=microstructure,
            momentum=momentum,
            initial_capital=25000.0,
            max_position=25,
            max_daily_loss=500.0,
            max_trades_per_day=20,
            bc_mode=True,  # DISABLE early stopping during tuning (let episodes run full 400 steps)
            enable_per_trade_stop=False,
        )
        
        # Store reference to pipeline for restart
        inner_env._pipeline_ref = pipeline
        
        # Monkey-patch reset to restart pipeline (enables new random window each episode)
        original_reset = inner_env.reset
        def reset_with_pipeline_restart(seed=None, options=None):
            # Restart pipeline to get new random window (if random_start=True)
            if hasattr(inner_env, '_pipeline_ref'):
                inner_env._pipeline_ref.restart()
                # No sleep needed - bar_buffer kept intact, only tick buffer cleared
            return original_reset(seed=seed, options=options)
        
        inner_env.reset = reset_with_pipeline_restart
        base_env_holder['env'] = inner_env
        return Monitor(inner_env)
    
    if normalize:
        vec_env = DummyVecEnv([make_env])
        vec_env = VecNormalize(
            vec_env,
            norm_obs=True,
            norm_reward=True,
            clip_obs=5.0,
            clip_reward=5.0,
            gamma=0.99,
        )
        return vec_env, base_env_holder['env']
    
    env = make_env()
    return env, base_env_holder['env']


def objective(
    trial: optuna.Trial,
    ib: IB,
    pipeline,
    microstructure,
    momentum,
    total_timesteps: int,
    device: str,
) -> float:
    """
    Objective function for Optuna optimization.
    
    Args:
        trial: Optuna trial object
        ib: Interactive Brokers connection
        pipeline: Data pipeline
        microstructure: Microstructure features
        momentum: Momentum features
        total_timesteps: Training timesteps
        device: 'cpu' or 'cuda'
    
    Returns:
        Final win rate (to maximize)
    """
    
    # Sample hyperparameters
    learning_rate = trial.suggest_float('learning_rate', 1e-5, 1e-3, log=True)
    ent_coef = trial.suggest_float('ent_coef', 0.001, 0.1, log=True)
    batch_size = trial.suggest_categorical('batch_size', [256, 512, 1024, 2048])
    n_steps = trial.suggest_categorical('n_steps', [1024, 2048, 4096])
    clip_range = trial.suggest_float('clip_range', 0.1, 0.3)
    gamma = trial.suggest_float('gamma', 0.95, 0.995)
    gae_lambda = trial.suggest_float('gae_lambda', 0.90, 0.99)
    n_epochs = trial.suggest_int('n_epochs', 5, 20)
    max_grad_norm = trial.suggest_float('max_grad_norm', 0.3, 1.0)
    
    # Network architecture
    net_arch_choice = trial.suggest_categorical('net_arch', ['small', 'medium', 'large'])
    net_arch_map = {
        'small': [128, 128],
        'medium': [256, 256],
        'large': [256, 256, 128],
    }
    net_arch = net_arch_map[net_arch_choice]
    
    # Ensure batch_size <= n_steps
    if batch_size > n_steps:
        batch_size = n_steps
    
    logger.info(
        f"\n{'='*60}\n"
        f"Trial {trial.number} | Hyperparameters:\n"
        f"  LR: {learning_rate:.6f}\n"
        f"  Entropy: {ent_coef:.6f}\n"
        f"  Batch size: {batch_size}\n"
        f"  N steps: {n_steps}\n"
        f"  Clip range: {clip_range:.3f}\n"
        f"  Gamma: {gamma:.4f}\n"
        f"  GAE lambda: {gae_lambda:.3f}\n"
        f"  N epochs: {n_epochs}\n"
        f"  Max grad norm: {max_grad_norm:.2f}\n"
        f"  Net arch: {net_arch}\n"
        f"{'='*60}"
    )
    
    try:
        # Create environment
        env, base_env = create_tuning_env(
            pipeline,
            microstructure,
            momentum,
            normalize=True,
        )
        
        # Create PPO model with sampled hyperparameters
        model = PPO(
            'MlpPolicy',
            env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            clip_range_vf=None,
            normalize_advantage=True,
            ent_coef=ent_coef,
            vf_coef=0.5,
            max_grad_norm=max_grad_norm,
            target_kl=None,
            policy_kwargs=dict(
                net_arch=net_arch,
                activation_fn=torch.nn.ReLU,
            ),
            device=device,
            verbose=0,
        )
        
        # Setup callbacks
        win_rate_callback = WinRateCallback(check_freq=1000, verbose=0)
        pruning_callback = OptunaPruningCallback(
            trial=trial,
            win_rate_callback=win_rate_callback,
            eval_freq=5000,
        )
        callbacks = CallbackList([win_rate_callback, pruning_callback])
        
        # Train
        start_time = time.time()
        model.learn(
            total_timesteps=total_timesteps,
            callback=callbacks,
            log_interval=None,
            reset_num_timesteps=True,
            progress_bar=False,
        )
        training_time = time.time() - start_time
        
        # Get final metrics
        metrics = win_rate_callback.get_recent_metrics()
        final_win_rate = metrics.get('win_rate', 0.0)
        final_sharpe = metrics.get('sharpe', 0.0)
        avg_pnl = metrics.get('avg_pnl', 0.0)
        
        logger.info(
            f"\n✅ Trial {trial.number} completed:\n"
            f"  Win rate: {final_win_rate:.1f}%\n"
            f"  Sharpe: {final_sharpe:.2f}\n"
            f"  Avg PnL: ${avg_pnl:.2f}\n"
            f"  Training time: {training_time/60:.1f} min\n"
        )
        
        # Store additional metrics
        trial.set_user_attr('sharpe', final_sharpe)
        trial.set_user_attr('avg_pnl', avg_pnl)
        trial.set_user_attr('training_time', training_time)
        
        # Cleanup
        env.close()
        del model
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        return final_win_rate
    
    except optuna.TrialPruned:
        # Trial was pruned - return current win rate
        metrics = win_rate_callback.get_recent_metrics()
        return metrics.get('win_rate', 0.0)
    
    except Exception as e:
        logger.error(f"❌ Trial {trial.number} failed: {e}")
        return 0.0


def run_hyperparameter_tuning(
    ib: IB,
    symbol: str = 'SPY',
    duration: str = '30 D',  # IBKR timeout limit for 1-min bars with basic subscription
    n_trials: int = 50,
    timesteps_per_trial: int = 50000,
    timeout: int = None,
    device: str = 'auto',
    study_name: str = None,
    storage: str = None,
):
    """
    Run hyperparameter tuning with Optuna.
    
    Args:
        ib: Interactive Brokers connection
        symbol: Trading symbol
        duration: Historical data duration
        n_trials: Number of optimization trials
        timesteps_per_trial: Training steps per trial
        timeout: Maximum time in seconds (None = no limit)
        device: 'cpu', 'cuda', or 'auto'
        study_name: Name for Optuna study (for resuming)
        storage: Database URL for persistence
    """
    
    logger.info(
        f"\n{'='*60}\n"
        f"🔧 HYPERPARAMETER TUNING\n"
        f"{'='*60}\n"
        f"Symbol: {symbol}\n"
        f"Duration: {duration}\n"
        f"Trials: {n_trials}\n"
        f"Timesteps/trial: {timesteps_per_trial:,}\n"
        f"Device: {device}\n"
        f"{'='*60}\n"
    )
    
    # Create data pipeline (reused across trials)
    logger.info(f"📊 Fetching {duration} of historical data...")
    pipeline = EnhancedDataPipeline(
        mode='historical',
        ib=ib,
        symbol=symbol,
        duration=duration,
        replay_speed=100.0,
        tick_buffer_size=10000,
        bar_buffer_size=500,
        # DATA DIVERSITY: Enable random windowing to prevent overfitting
        # Each episode will start from a random position in the historical data
        # This provides infinite training diversity (like image augmentation)
        # CRITICAL: Use random_start=True for production training to avoid data exhaustion
        # With 30D data (11,700 bars) and 400-step episodes, you get ~29 unique sequences
        # Random windowing creates infinite combinations from the same historical data
        random_start=True,  # ← ENABLED to overcome 30D IBKR limit
        window_size=400,  # Episode length in bars (matches env horizon)
    )
    
    pipeline.start()
    
    # Wait for data collection
    logger.info("⏳ Waiting for data collection (30 seconds)...")
    time.sleep(30)
    
    stats = pipeline.get_stats()
    logger.info(f"✅ Data ready: {stats['ticks_collected']:,} ticks, "
                f"{stats['bars_collected']} bars")
    
    # Create features (reused across trials)
    logger.info("🔧 Initializing feature engines...")
    microstructure = build_microstructure_features(
        pipeline,
        mode='legacy',
        normalization='off',
    )
    momentum = MomentumFeatures(pipeline, check_stale=False)
    
    # Create Optuna study
    if study_name is None:
        study_name = f"ppo_tuning_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    logger.info(f"📚 Creating Optuna study: {study_name}")
    
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        load_if_exists=True,
        direction='maximize',  # Maximize win rate
        sampler=TPESampler(seed=42),
        pruner=MedianPruner(
            n_startup_trials=5,
            n_warmup_steps=10000,
            interval_steps=5000,
        ),
    )
    
    # Run optimization
    logger.info(f"\n🚀 Starting optimization with {n_trials} trials...")
    
    start_time = time.time()
    
    try:
        study.optimize(
            lambda trial: objective(
                trial,
                ib,
                pipeline,
                microstructure,
                momentum,
                timesteps_per_trial,
                device,
            ),
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True,
        )
    except KeyboardInterrupt:
        logger.info("\n⚠️  Optimization interrupted by user")
    
    total_time = time.time() - start_time
    
    # Results
    logger.info(
        f"\n{'='*60}\n"
        f"🏆 OPTIMIZATION COMPLETE\n"
        f"{'='*60}\n"
        f"Total time: {total_time/3600:.1f} hours\n"
        f"Completed trials: {len(study.trials)}\n"
        f"{'='*60}\n"
    )
    
    # Best trial
    best_trial = study.best_trial
    logger.info(
        f"\n🥇 BEST TRIAL (#{best_trial.number}):\n"
        f"  Win rate: {best_trial.value:.1f}%\n"
        f"  Sharpe: {best_trial.user_attrs.get('sharpe', 0.0):.2f}\n"
        f"  Avg PnL: ${best_trial.user_attrs.get('avg_pnl', 0.0):.2f}\n"
        f"  Training time: {best_trial.user_attrs.get('training_time', 0.0)/60:.1f} min\n"
        f"\n  Hyperparameters:\n"
    )
    
    for key, value in best_trial.params.items():
        logger.info(f"    {key}: {value}")
    
    # Save results
    results_dir = Path('logs') / 'hyperparameter_tuning'
    results_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = results_dir / f"{study_name}_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            'study_name': study_name,
            'n_trials': len(study.trials),
            'best_value': best_trial.value,
            'best_params': best_trial.params,
            'best_user_attrs': best_trial.user_attrs,
            'all_trials': [
                {
                    'number': t.number,
                    'value': t.value,
                    'params': t.params,
                    'user_attrs': t.user_attrs,
                    'state': t.state.name,
                }
                for t in study.trials
            ],
        }, f, indent=2)
    
    logger.info(f"\n💾 Results saved: {results_file}")
    
    # Generate importance plot data
    try:
        importance = optuna.importance.get_param_importances(study)
        logger.info("\n📊 Parameter Importance:")
        for param, imp in sorted(importance.items(), key=lambda x: -x[1]):
            logger.info(f"  {param}: {imp:.4f}")
    except Exception as e:
        logger.warning(f"Could not compute parameter importance: {e}")
    
    # Cleanup
    pipeline.stop()
    
    return study


def main():
    parser = argparse.ArgumentParser(description='Hyperparameter tuning for PPO trading agent')
    parser.add_argument('--symbol', type=str, default='SPY', help='Trading symbol')
    parser.add_argument('--duration', type=str, default='30 D', help='Historical data duration (IBKR limit: 30D for 1-min bars)')
    parser.add_argument('--trials', type=int, default=50, help='Number of optimization trials')
    parser.add_argument('--timesteps', type=int, default=50000, help='Timesteps per trial')
    parser.add_argument('--timeout', type=int, default=None, help='Timeout in seconds')
    parser.add_argument('--device', type=str, default='auto', help='Device (cpu/cuda/auto)')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='IBKR host')
    parser.add_argument('--port', type=int, default=7497, help='IBKR port (7497=paper)')
    parser.add_argument('--study-name', type=str, default=None, help='Optuna study name (for resuming)')
    parser.add_argument('--storage', type=str, default=None, help='Database URL (e.g., sqlite:///optuna.db)')
    
    args = parser.parse_args()
    
    # Connect to IBKR
    logger.info("🔌 Connecting to IBKR...")
    ib = IB()
    
    try:
        ib.connect(args.host, args.port, clientId=3)
        logger.info(f"✅ Connected to IBKR at {args.host}:{args.port}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to IBKR: {e}")
        return 1
    
    try:
        # Run tuning
        study = run_hyperparameter_tuning(
            ib=ib,
            symbol=args.symbol,
            duration=args.duration,
            n_trials=args.trials,
            timesteps_per_trial=args.timesteps,
            timeout=args.timeout,
            device=args.device,
            study_name=args.study_name,
            storage=args.storage,
        )
        
        logger.info("\n🎉 Hyperparameter tuning complete!")
        logger.info("\nNext steps:")
        logger.info("  1. Review results in logs/hyperparameter_tuning/")
        logger.info("  2. Update train_intraday_ppo.py with best hyperparameters")
        logger.info("  3. Train final model with optimized settings")
        
        return 0
    
    finally:
        ib.disconnect()
        logger.info("\n🧹 Disconnected from IBKR")


if __name__ == '__main__':
    exit(main())
