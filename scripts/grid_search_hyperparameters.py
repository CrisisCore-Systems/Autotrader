"""
Grid Search Hyperparameter Tuning for Intraday PPO Trading Agent

Exhaustive grid search over specified hyperparameter ranges.
Simpler alternative to Bayesian optimization (Optuna).

Usage:
    python scripts/grid_search_hyperparameters.py --timesteps 30000
"""

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from itertools import product
from typing import Dict, Any, List

import numpy as np
import torch

try:
    from ib_insync import IB
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    from stable_baselines3.common.monitor import Monitor
    from stable_baselines3.common.callbacks import CallbackList
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    exit(1)

import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.intraday import (
    EnhancedDataPipeline,
    MomentumFeatures,
)

from scripts.train_intraday_ppo import (
    StableRewardHighWinRateEnv,
    WinRateCallback,
    build_microstructure_features,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define grid search space
GRID_SEARCH_SPACE = {
    'learning_rate': [1e-4, 3e-4, 5e-4],
    'ent_coef': [0.01, 0.05, 0.1],
    'batch_size': [512, 1024],
    'n_steps': [2048, 4096],
    'clip_range': [0.15, 0.20, 0.25],
    'gamma': [0.99, 0.995],
    'net_arch': [
        [256, 256],
        [256, 256, 128],
    ],
}


def create_tuning_env(pipeline, microstructure, momentum):
    """Create environment for tuning."""
    
    def make_env():
        inner_env = StableRewardHighWinRateEnv(
            pipeline=pipeline,
            microstructure=microstructure,
            momentum=momentum,
            initial_capital=25000.0,
            max_position=25,
            max_daily_loss=500.0,
            max_trades_per_day=20,
            bc_mode=False,
            enable_per_trade_stop=False,
        )
        return Monitor(inner_env)
    
    vec_env = DummyVecEnv([make_env])
    vec_env = VecNormalize(
        vec_env,
        norm_obs=True,
        norm_reward=True,
        clip_obs=5.0,
        clip_reward=5.0,
        gamma=0.99,
    )
    return vec_env


def train_and_evaluate(
    params: Dict[str, Any],
    pipeline,
    microstructure,
    momentum,
    total_timesteps: int,
    device: str,
    trial_num: int,
    total_trials: int,
) -> Dict[str, Any]:
    """Train model with given hyperparameters and return results."""
    
    logger.info(
        f"\n{'='*60}\n"
        f"Trial {trial_num}/{total_trials}\n"
        f"Hyperparameters: {params}\n"
        f"{'='*60}"
    )
    
    try:
        # Create environment
        env = create_tuning_env(pipeline, microstructure, momentum)
        
        # Create model
        model = PPO(
            'MlpPolicy',
            env,
            learning_rate=params['learning_rate'],
            n_steps=params['n_steps'],
            batch_size=params['batch_size'],
            n_epochs=10,
            gamma=params['gamma'],
            gae_lambda=0.95,
            clip_range=params['clip_range'],
            clip_range_vf=None,
            normalize_advantage=True,
            ent_coef=params['ent_coef'],
            vf_coef=0.5,
            max_grad_norm=0.5,
            target_kl=None,
            policy_kwargs=dict(
                net_arch=params['net_arch'],
                activation_fn=torch.nn.ReLU,
            ),
            device=device,
            verbose=0,
        )
        
        # Setup callback
        win_rate_callback = WinRateCallback(check_freq=1000, verbose=0)
        
        # Train
        start_time = time.time()
        model.learn(
            total_timesteps=total_timesteps,
            callback=win_rate_callback,
            log_interval=None,
            reset_num_timesteps=True,
            progress_bar=False,
        )
        training_time = time.time() - start_time
        
        # Get metrics
        metrics = win_rate_callback.get_recent_metrics()
        win_rate = metrics.get('win_rate', 0.0)
        sharpe = metrics.get('sharpe', 0.0)
        avg_pnl = metrics.get('avg_pnl', 0.0)
        
        logger.info(
            f"✅ Trial {trial_num} complete:\n"
            f"  Win rate: {win_rate:.1f}%\n"
            f"  Sharpe: {sharpe:.2f}\n"
            f"  Avg PnL: ${avg_pnl:.2f}\n"
            f"  Time: {training_time/60:.1f} min"
        )
        
        # Cleanup
        env.close()
        del model
        torch.cuda.empty_cache() if torch.cuda.is_available() else None
        
        return {
            'params': params,
            'win_rate': win_rate,
            'sharpe': sharpe,
            'avg_pnl': avg_pnl,
            'training_time': training_time,
            'success': True,
        }
    
    except Exception as e:
        logger.error(f"❌ Trial {trial_num} failed: {e}")
        return {
            'params': params,
            'win_rate': 0.0,
            'sharpe': 0.0,
            'avg_pnl': 0.0,
            'training_time': 0.0,
            'success': False,
            'error': str(e),
        }


def run_grid_search(
    ib: IB,
    symbol: str = 'SPY',
    duration: str = '30 D',
    timesteps_per_trial: int = 30000,
    device: str = 'auto',
    grid_space: Dict = None,
):
    """Run grid search over hyperparameter space."""
    
    if grid_space is None:
        grid_space = GRID_SEARCH_SPACE
    
    logger.info(
        f"\n{'='*60}\n"
        f"🔧 GRID SEARCH HYPERPARAMETER TUNING\n"
        f"{'='*60}"
    )
    
    # Calculate total trials
    total_trials = 1
    for values in grid_space.values():
        total_trials *= len(values)
    
    logger.info(f"Grid space: {total_trials} combinations")
    for param, values in grid_space.items():
        logger.info(f"  {param}: {values}")
    logger.info(f"{'='*60}\n")
    
    # Create data pipeline
    logger.info(f"📊 Fetching {duration} of historical data...")
    pipeline = EnhancedDataPipeline(
        mode='historical',
        ib=ib,
        symbol=symbol,
        duration=duration,
        replay_speed=100.0,
        tick_buffer_size=10000,
        bar_buffer_size=500,
    )
    
    pipeline.start()
    time.sleep(30)
    
    stats = pipeline.get_stats()
    logger.info(f"✅ Data ready: {stats['ticks_collected']:,} ticks")
    
    # Create features
    microstructure = build_microstructure_features(pipeline, mode='legacy', normalization='off')
    momentum = MomentumFeatures(pipeline, check_stale=False)
    
    # Generate all parameter combinations
    param_names = list(grid_space.keys())
    param_values = [grid_space[name] for name in param_names]
    combinations = list(product(*param_values))
    
    logger.info(f"\n🚀 Starting grid search: {len(combinations)} trials\n")
    
    # Run trials
    results = []
    start_time = time.time()
    
    for i, combo in enumerate(combinations, 1):
        params = dict(zip(param_names, combo))
        
        result = train_and_evaluate(
            params,
            pipeline,
            microstructure,
            momentum,
            timesteps_per_trial,
            device,
            i,
            len(combinations),
        )
        
        results.append(result)
        
        # Progress update
        elapsed = time.time() - start_time
        avg_time_per_trial = elapsed / i
        remaining_trials = len(combinations) - i
        eta = avg_time_per_trial * remaining_trials
        
        logger.info(
            f"\nProgress: {i}/{len(combinations)} "
            f"({i/len(combinations)*100:.1f}%)\n"
            f"Elapsed: {elapsed/3600:.1f}h | "
            f"ETA: {eta/3600:.1f}h\n"
        )
    
    total_time = time.time() - start_time
    
    # Analyze results
    logger.info(
        f"\n{'='*60}\n"
        f"🏆 GRID SEARCH COMPLETE\n"
        f"{'='*60}\n"
        f"Total time: {total_time/3600:.1f} hours\n"
        f"Completed trials: {len([r for r in results if r['success']])}/{len(results)}\n"
    )
    
    # Find best result
    successful_results = [r for r in results if r['success']]
    if successful_results:
        best_result = max(successful_results, key=lambda x: x['win_rate'])
        
        logger.info(
            f"\n🥇 BEST RESULT:\n"
            f"  Win rate: {best_result['win_rate']:.1f}%\n"
            f"  Sharpe: {best_result['sharpe']:.2f}\n"
            f"  Avg PnL: ${best_result['avg_pnl']:.2f}\n"
            f"\n  Hyperparameters:\n"
        )
        
        for key, value in best_result['params'].items():
            logger.info(f"    {key}: {value}")
    
    # Save results
    results_dir = Path('logs') / 'hyperparameter_tuning'
    results_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = results_dir / f"grid_search_{symbol}_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            'grid_space': {k: v for k, v in grid_space.items() if k != 'net_arch'},
            'net_arch_options': ['[256,256]', '[256,256,128]'],
            'total_trials': len(results),
            'successful_trials': len(successful_results),
            'best_result': best_result if successful_results else None,
            'all_results': results,
        }, f, indent=2, default=str)
    
    logger.info(f"\n💾 Results saved: {results_file}")
    
    # Cleanup
    pipeline.stop()
    
    return results, best_result if successful_results else None


def main():
    parser = argparse.ArgumentParser(description='Grid search hyperparameter tuning')
    parser.add_argument('--symbol', type=str, default='SPY')
    parser.add_argument('--duration', type=str, default='30 D')
    parser.add_argument('--timesteps', type=int, default=30000)
    parser.add_argument('--device', type=str, default='auto')
    parser.add_argument('--host', type=str, default='127.0.0.1')
    parser.add_argument('--port', type=int, default=7497)
    
    args = parser.parse_args()
    
    # Connect to IBKR
    logger.info("🔌 Connecting to IBKR...")
    ib = IB()
    
    try:
        ib.connect(args.host, args.port, clientId=4)
        logger.info(f"✅ Connected to IBKR")
    except Exception as e:
        logger.error(f"❌ Failed to connect: {e}")
        return 1
    
    try:
        results, best = run_grid_search(
            ib=ib,
            symbol=args.symbol,
            duration=args.duration,
            timesteps_per_trial=args.timesteps,
            device=args.device,
        )
        
        logger.info("\n🎉 Grid search complete!")
        return 0
    
    finally:
        ib.disconnect()


if __name__ == '__main__':
    exit(main())
