"""
Hyperparameter Optimization for PPO Intraday Trader

Uses Optuna to find optimal hyperparameters for maximum win rate.

Target: >70% win rate, Sharpe >3.0

Optimizes:
- Learning rate
- Network architecture
- Batch size
- Reward scaling
- Risk parameters

Usage:
    python scripts/optimize_hyperparameters.py --trials 50 --duration 5D
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, Any
import time

try:
    import optuna
    from optuna.pruners import MedianPruner
    from optuna.samplers import TPESampler
    from ib_insync import IB
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.vec_env import DummyVecEnv
    import torch
    import numpy as np
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("\nInstall required packages:")
    print("  pip install optuna ib_insync stable-baselines3[extra] torch")
    exit(1)

import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.intraday import EnhancedDataPipeline, IntradayTradingEnv
from src.intraday import MicrostructureFeatures, MomentumFeatures

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptimizableEnv(IntradayTradingEnv):
    """Environment with configurable reward scaling."""
    
    def __init__(self, reward_scale: float = 1.0, win_bonus: float = 1.0, 
                 loss_penalty: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self.reward_scale = reward_scale
        self.win_bonus = win_bonus
        self.loss_penalty = loss_penalty
    
    def _calculate_reward(self) -> float:
        """Reward with hyperparameter-controlled scaling."""
        reward = 0.0
        
        # Base PnL (scaled)
        reward += self.daily_pnl * self.reward_scale
        
        # Risk-adjusted return
        if len(self.daily_returns) > 1:
            returns_array = np.array(self.daily_returns)
            mean_return = np.mean(returns_array)
            std_return = np.std(returns_array) + 1e-8
            sharpe = mean_return / std_return
            reward += sharpe * 100.0
        
        # Win streak bonus (configurable)
        if self.current_win_streak > 0:
            reward += self.current_win_streak * self.win_bonus
        
        # Loss penalty (configurable)
        if self.daily_pnl < 0:
            reward -= abs(self.daily_pnl) * self.loss_penalty
        
        # Trade selectivity
        if self.daily_trades > 0:
            avg_pnl_per_trade = self.daily_pnl / self.daily_trades
            if avg_pnl_per_trade > 1.0:
                reward += avg_pnl_per_trade * 10.0
        
        # Early profit lock-in
        if self.daily_pnl > 100.0:
            reward += 50.0
        
        return reward


def objective(trial: optuna.Trial, ib: IB, symbol: str, duration: str) -> float:
    """
    Objective function for Optuna optimization.
    
    Returns: Validation win rate (to maximize)
    """
    # Suggest hyperparameters
    learning_rate = trial.suggest_float('learning_rate', 1e-5, 1e-3, log=True)
    n_steps = trial.suggest_categorical('n_steps', [512, 1024, 2048, 4096])
    batch_size = trial.suggest_categorical('batch_size', [32, 64, 128, 256])
    gamma = trial.suggest_float('gamma', 0.95, 0.999)
    gae_lambda = trial.suggest_float('gae_lambda', 0.9, 0.99)
    ent_coef = trial.suggest_float('ent_coef', 0.0, 0.1)
    clip_range = trial.suggest_float('clip_range', 0.1, 0.3)
    
    # Network architecture
    n_layers = trial.suggest_int('n_layers', 2, 4)
    layer_size = trial.suggest_categorical('layer_size', [64, 128, 256, 512])
    net_arch = [layer_size] * n_layers
    
    # Reward scaling
    reward_scale = trial.suggest_float('reward_scale', 1.0, 20.0)
    win_bonus = trial.suggest_float('win_bonus', 0.5, 5.0)
    loss_penalty = trial.suggest_float('loss_penalty', 0.5, 5.0)
    
    # Risk parameters
    max_position = trial.suggest_int('max_position', 100, 500, step=100)
    max_daily_loss = trial.suggest_float('max_daily_loss', 200.0, 500.0)
    max_trades = trial.suggest_int('max_trades', 10, 30)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"Trial {trial.number}")
    logger.info(f"{'='*60}")
    logger.info(f"Learning rate: {learning_rate:.6f}")
    logger.info(f"Network: {net_arch}")
    logger.info(f"N steps: {n_steps}, Batch size: {batch_size}")
    logger.info(f"Reward scale: {reward_scale:.2f}, Win bonus: {win_bonus:.2f}")
    logger.info(f"Max position: {max_position}, Max loss: ${max_daily_loss:.0f}")
    
    try:
        # Create pipeline
        pipeline = EnhancedDataPipeline(
            mode='historical',
            ib=ib,
            symbol=symbol,
            duration=duration,
            replay_speed=100.0,
        )
        
        pipeline.start()
        time.sleep(30)  # Wait for data
        
        # Create features
        microstructure = MicrostructureFeatures(pipeline)
        momentum = MomentumFeatures(pipeline)
        
        # Create environment with trial hyperparameters
        env = OptimizableEnv(
            pipeline=pipeline,
            microstructure=microstructure,
            momentum=momentum,
            initial_capital=25000.0,
            max_position=max_position,
            max_daily_loss=max_daily_loss,
            max_trades_per_day=max_trades,
            reward_scale=reward_scale,
            win_bonus=win_bonus,
            loss_penalty=loss_penalty,
        )
        
        env = Monitor(env)
        
        # Create model
        model = PPO(
            'MlpPolicy',
            env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=10,
            gamma=gamma,
            gae_lambda=gae_lambda,
            clip_range=clip_range,
            ent_coef=ent_coef,
            policy_kwargs=dict(
                net_arch=net_arch,
                activation_fn=torch.nn.ReLU,
            ),
            device='auto',
            verbose=0,
        )
        
        # Train (short training for fast iteration)
        model.learn(total_timesteps=50_000, progress_bar=False)
        
        # Evaluate on 20 episodes
        win_count = 0
        total_episodes = 20
        pnls = []
        
        for _ in range(total_episodes):
            obs, _ = env.reset()
            done = False
            episode_pnl = 0.0
            
            while not done:
                action, _ = model.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                
                if done and 'daily_pnl' in info:
                    episode_pnl = info['daily_pnl']
            
            pnls.append(episode_pnl)
            if episode_pnl > 0:
                win_count += 1
        
        # Calculate metrics
        win_rate = (win_count / total_episodes) * 100
        avg_pnl = np.mean(pnls)
        sharpe = np.mean(pnls) / (np.std(pnls) + 1e-8) * np.sqrt(252)
        
        # Cleanup
        pipeline.stop()
        
        logger.info(f"Results: Win Rate: {win_rate:.1f}%, Avg PnL: ${avg_pnl:.2f}, Sharpe: {sharpe:.2f}")
        
        # Report intermediate value (for pruning)
        trial.report(win_rate, step=0)
        
        # Prune if performing poorly
        if trial.should_prune():
            raise optuna.TrialPruned()
        
        return win_rate
    
    except Exception as e:
        logger.error(f"Trial failed: {e}")
        return 0.0


def optimize(
    ib: IB,
    symbol: str,
    duration: str,
    n_trials: int,
    study_name: str = 'ppo_optimization',
):
    """Run hyperparameter optimization."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🔬 HYPERPARAMETER OPTIMIZATION")
    logger.info(f"{'='*60}")
    logger.info(f"Symbol: {symbol}")
    logger.info(f"Duration: {duration}")
    logger.info(f"Trials: {n_trials}")
    logger.info(f"Objective: Maximize win rate")
    logger.info(f"{'='*60}\n")
    
    # Create study
    study = optuna.create_study(
        study_name=study_name,
        direction='maximize',  # Maximize win rate
        sampler=TPESampler(seed=42),
        pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10),
    )
    
    # Optimize
    study.optimize(
        lambda trial: objective(trial, ib, symbol, duration),
        n_trials=n_trials,
        show_progress_bar=True,
    )
    
    # Results
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ OPTIMIZATION COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Best win rate: {study.best_value:.1f}%")
    logger.info(f"\nBest hyperparameters:")
    for key, value in study.best_params.items():
        logger.info(f"  {key}: {value}")
    
    # Save results
    results_dir = Path('logs') / 'optimization'
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # Save study
    study_path = results_dir / f'{study_name}.pkl'
    optuna.visualization.plot_optimization_history(study).write_html(
        str(results_dir / 'optimization_history.html')
    )
    optuna.visualization.plot_param_importances(study).write_html(
        str(results_dir / 'param_importances.html')
    )
    
    logger.info(f"\nResults saved to: {results_dir}")
    logger.info(f"{'='*60}\n")
    
    return study


def main():
    parser = argparse.ArgumentParser(description='Optimize PPO hyperparameters')
    parser.add_argument('--symbol', type=str, default='SPY', help='Trading symbol')
    parser.add_argument('--duration', type=str, default='5 D', help='Historical data duration')
    parser.add_argument('--trials', type=int, default=50, help='Number of optimization trials')
    parser.add_argument('--study-name', type=str, default='ppo_optimization', help='Study name')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='IBKR host')
    parser.add_argument('--port', type=int, default=7497, help='IBKR port')
    
    args = parser.parse_args()
    
    # Connect to IBKR
    logger.info("🔌 Connecting to IBKR...")
    ib = IB()
    
    try:
        ib.connect(args.host, args.port, clientId=3)
        logger.info(f"✅ Connected to IBKR")
    except Exception as e:
        logger.error(f"❌ Failed to connect: {e}")
        return 1
    
    try:
        # Optimize
        study = optimize(
            ib=ib,
            symbol=args.symbol,
            duration=args.duration,
            n_trials=args.trials,
            study_name=args.study_name,
        )
        
        logger.info("\n🎉 Use best hyperparameters for full training!")
        
        return 0
    
    finally:
        ib.disconnect()


if __name__ == '__main__':
    exit(main())
