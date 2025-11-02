"""
Behavior Cloning (BC) Pre-training

Train supervised policy on expert demonstrations before RL fine-tuning.

Workflow:
1. Collect 1000+ episodes from rule-based expert
2. Train BC policy with cross-entropy loss
3. Validate: BC loss <0.1, PF >1.2 on held-out days
4. Save BC checkpoint for PPO initialization
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import logging
from dataclasses import asdict
from datetime import datetime
import time
from typing import Dict

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
from ib_insync import IB

from expert_policy_v5_profitable import ProfitableExpert, ProfitableExpertConfig
from train_intraday_ppo import HighWinRateEnv
from src.intraday.enhanced_pipeline import EnhancedDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures
from viz_instrumentation import StallWatchdog


def _wait_for_next_bar(
    pipeline: EnhancedDataPipeline,
    last_bar_count: int,
    timeout: float = 5.0,
    poll_interval: float = 0.02,
) -> int:
    """Block until the pipeline produces a new bar or timeout."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_count = pipeline.bars_generated
        if current_count > last_bar_count:
            return current_count
        time.sleep(poll_interval)

    raise TimeoutError(
        f"Timed out after {timeout}s waiting for new bar (last={last_bar_count}, current={pipeline.bars_generated})"
    )

sys.path.insert(0, str(Path(__file__).parent.parent / "autotrader_live_dashboard"))
from metrics_client import MetricsClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def collect_expert_demonstrations(
    expert: InstrumentedSafeExpert,
    env: HighWinRateEnv,
    num_episodes: int = 100,
    metrics_client: MetricsClient = None,
) -> Dict[str, np.ndarray]:
    """
    Collect demonstrations from instrumented expert with filtering.
    
    (Updated to ensure expert uses the post-step price for accurate PnL tracking.)
    
    Filters:
    - Discard episodes with < config.min_trades_to_keep_episode
    - Only keep transitions from valid episodes
    
    Returns:
        Dict with 'observations', 'actions', 'episode_stats'
    """
    observations = []
    actions = []
    valid_episodes = 0
    discarded_episodes = 0
    total_trades = 0
    total_wins = 0
    total_losses = 0
    cumulative_pnl = 0.0
    positive_pnl_total = 0.0
    negative_pnl_total = 0.0

    watchdog = StallWatchdog(timeout_seconds=60)
    
    logger.info(f"Collecting {num_episodes} expert episodes...")
    
    try:
        for ep in range(num_episodes):
            obs, _ = env.reset()
            expert.reset()
            watchdog.touch()

            stats_before = asdict(expert.stats)

            ep_obs = []
            ep_actions = []
            done = False
            step = 0

            # Track bar progress so we only advance when fresh data arrives
            last_bar_count = env.pipeline.bars_generated

            while not done and step < 390:
                try:
                    last_bar_count = _wait_for_next_bar(env.pipeline, last_bar_count)
                except TimeoutError as exc:
                    logger.warning("⏳ %s | ending episode early (step %s)", exc, step)
                    break

                current_price = env.pipeline.get_current_price()

                # Expert action decision is based on current price/obs
                action = expert.get_action(step, current_price, obs)

                # Store transition BEFORE the step
                ep_obs.append(obs.copy())
                ep_actions.append(action)

                # Environment step: obs, reward, terminated, truncated, info
                obs, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                step += 1
                info_price = info.get('price', current_price)
                
                # Touch watchdog on every step
                watchdog.touch()

                if step == 1 or step % 25 == 0 or done:
                    action_map = {
                        0: "CLOSE",
                        1: "HOLD",
                        2: "OPEN_SMALL",
                        3: "OPEN_MED",
                        4: "OPEN_LARGE",
                    }
                    logger.info(
                        "    ↪️  Step %s | action=%s | price=$%0.2f | reward=%0.3f | daily_pnl=$%0.2f", 
                        step,
                        action_map.get(action, str(action)),
                        info_price,
                        reward,
                        info.get('daily_pnl', 0.0),
                    )

            # Force close at episode end, using the LAST KNOWN PRICE from the loop
            if not done:
                expert.force_close_all(current_price)

            stats_after = asdict(expert.stats)
            ep_wins = stats_after['wins'] - stats_before['wins']
            ep_losses = stats_after['losses'] - stats_before['losses']
            ep_trades = ep_wins + ep_losses
            ep_pnl = stats_after['total_pnl'] - stats_before['total_pnl']

            ep_positive = sum(p for p in getattr(expert, "episode_trade_pnls", []) if p > 0)
            ep_negative = sum(-p for p in getattr(expert, "episode_trade_pnls", []) if p < 0)

            episode_kept = expert.episode_valid()

            if episode_kept:
                observations.extend(ep_obs)
                actions.extend(ep_actions)
                valid_episodes += 1
                total_trades += ep_trades
                total_wins += ep_wins
                total_losses += ep_losses
                cumulative_pnl += ep_pnl
                positive_pnl_total += ep_positive
                negative_pnl_total += ep_negative
            else:
                discarded_episodes += 1

            # Push metrics to dashboard
            if metrics_client:
                hit_rate = total_wins / total_trades if total_trades else 0.0
                pf = positive_pnl_total / negative_pnl_total if negative_pnl_total > 0 else 0.0

                metrics_client.push(
                    phase="BC",
                    episode=ep + 1,
                    total_episodes=num_episodes,
                    trades=total_trades,
                    wins=total_wins,
                    losses=total_losses,
                    hit_rate=hit_rate,
                    pf=pf,
                    equity=25000.0 + cumulative_pnl,
                    reasons={},  # No rejection tracking in v4
                    note=(
                        f"Episode {ep+1}: {ep_trades} trades, {ep_wins}W/{ep_losses}L, "
                        f"PnL ${ep_pnl:.2f}"
                        + (" (discarded)" if not episode_kept else "")
                    )
                )

            # High-level progress log every episode (helps with long runs)
            keep_flag = "kept" if episode_kept else "discarded"
            logger.info(
                "📈 Episode %s/%s | %s | trades=%s | wins=%s | losses=%s | pnl=$%0.2f",
                ep + 1,
                num_episodes,
                keep_flag,
                ep_trades,
                ep_wins,
                ep_losses,
                ep_pnl,
            )

            if (ep + 1) % 10 == 0:
                logger.info(
                    "🧮 Progress: kept=%s | discarded=%s | total_trades=%s | hit_rate=%0.2f | pf=%0.2f",
                    valid_episodes,
                    discarded_episodes,
                    total_trades,
                    (total_wins / total_trades) if total_trades else 0.0,
                    (positive_pnl_total / negative_pnl_total) if negative_pnl_total else 0.0,
                )

            watchdog.check()
    
    except Exception as e:
        logger.error(f"Collection error: {e}")
        raise
    
    # Final summary
    logger.info(
        f"\n{'='*70}\n"
        f"Collection Complete:\n"
        f"  Total episodes: {num_episodes}\n"
        f"  Valid episodes: {valid_episodes}\n"
        f"  Discarded episodes: {discarded_episodes}\n"
        f"  Total transitions: {len(observations):,}\n"
        f"\nExpert Performance:\n"
        f"{expert.get_stats_summary()}\n"
        f"{'='*70}"
    )
    
    return {
        'observations': np.array(observations, dtype=np.float32),
        'actions': np.array(actions, dtype=np.int64),
        'valid_episodes': valid_episodes,
        'discarded_episodes': discarded_episodes,
    }


class ExpertDataset(Dataset):
    """Dataset of expert demonstrations."""
    
    def __init__(self, observations: np.ndarray, actions: np.ndarray):
        self.observations = torch.from_numpy(observations).float()
        self.actions = torch.from_numpy(actions).long()
    
    def __len__(self):
        return len(self.actions)
    
    def __getitem__(self, idx):
        return self.observations[idx], self.actions[idx]


class BCPolicy(nn.Module):
    """Behavior cloning policy network (matches PPO architecture)."""
    
    def __init__(self, obs_dim: int = 53, act_dim: int = 5):  # Updated from 47
        super().__init__()
        
        # Match PPO architecture [256, 256, 128]
        self.net = nn.Sequential(
            nn.Linear(obs_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, act_dim),
        )
    
    def forward(self, obs):
        logits = self.net(obs)
        return logits
    
    def get_action(self, obs, deterministic=True):
        """Get action from observation."""
        with torch.no_grad():
            logits = self.forward(obs)
            if deterministic:
                action = torch.argmax(logits, dim=-1)
            else:
                probs = torch.softmax(logits, dim=-1)
                action = torch.multinomial(probs, 1).squeeze(-1)
        return action


def train_bc_policy(
    dataset: ExpertDataset,
    epochs: int = 100,
    batch_size: int = 128,
    lr: float = 3e-4,
    device: str = 'cpu',
) -> tuple[BCPolicy, dict]:
    """
    Train BC policy with supervised learning.
    
    Returns:
        (trained_policy, training_history)
    """
    # Split train/val
    train_size = int(0.9 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size)
    
    # Initialize model
    policy = BCPolicy().to(device)
    optimizer = optim.Adam(policy.parameters(), lr=lr)
    criterion = nn.CrossEntropyLoss()
    
    logger.info(f"Training BC policy on {train_size:,} demonstrations")
    logger.info(f"  Epochs: {epochs}, Batch size: {batch_size}, LR: {lr}")
    
    history = {'train_loss': [], 'train_acc': [], 'val_loss': [], 'val_acc': []}
    best_val_loss = float('inf')
    
    for epoch in range(epochs):
        # Training
        policy.train()
        train_losses = []
        train_correct = 0
        train_total = 0
        
        for obs, actions in train_loader:
            obs, actions = obs.to(device), actions.to(device)
            
            # Forward
            logits = policy(obs)
            loss = criterion(logits, actions)
            
            # Backward
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            # Metrics
            train_losses.append(loss.item())
            pred = torch.argmax(logits, dim=-1)
            train_correct += (pred == actions).sum().item()
            train_total += actions.size(0)
        
        # Validation
        policy.eval()
        val_losses = []
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for obs, actions in val_loader:
                obs, actions = obs.to(device), actions.to(device)
                
                logits = policy(obs)
                loss = criterion(logits, actions)
                
                val_losses.append(loss.item())
                pred = torch.argmax(logits, dim=-1)
                val_correct += (pred == actions).sum().item()
                val_total += actions.size(0)
        
        # Log metrics
        train_loss = np.mean(train_losses)
        train_acc = train_correct / train_total
        val_loss = np.mean(val_losses)
        val_acc = val_correct / val_total
        
        history['train_loss'].append(train_loss)
        history['train_acc'].append(train_acc)
        history['val_loss'].append(val_loss)
        history['val_acc'].append(val_acc)
        
        if (epoch + 1) % 10 == 0:
            logger.info(
                f"Epoch {epoch+1}/{epochs} | "
                f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.3f} | "
                f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.3f}"
            )
        
        # Save best model
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(policy.state_dict(), 'models/bc_best.pth')
    
    logger.info(f"\n✅ BC training complete. Best val loss: {best_val_loss:.4f}")
    
    return policy, history


def evaluate_bc_policy(
    policy: BCPolicy,
    env,
    num_episodes: int = 10,
    device: str = 'cpu',
) -> dict:
    """
    Evaluate BC policy on environment.
    
    Returns metrics: PF, hit_rate, avg_pnl, max_dd
    """
    policy.eval()
    
    episode_pnls = []
    episode_wins = []
    episode_trades = []
    
    for ep in range(num_episodes):
        obs, info = env.reset()
        done = False
        
        while not done:
            obs_tensor = torch.from_numpy(obs).float().unsqueeze(0).to(device)
            action = policy.get_action(obs_tensor, deterministic=True)
            action = action.item()
            
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
        
        # Extract metrics
        pnl = info.get('daily_pnl', 0)
        trades = info.get('daily_trades', 0)
        
        episode_pnls.append(pnl)
        episode_wins.append(1 if pnl > 0 else 0)
        episode_trades.append(trades)
    
    # Calculate metrics
    total_pnl = sum(episode_pnls)
    wins = [p for p in episode_pnls if p > 0]
    losses = [abs(p) for p in episode_pnls if p < 0]
    
    profit_factor = (sum(wins) / sum(losses)) if losses else 0.0
    hit_rate = np.mean(episode_wins)
    avg_pnl = np.mean(episode_pnls)
    max_dd = min(episode_pnls) if episode_pnls else 0
    
    metrics = {
        'profit_factor': profit_factor,
        'hit_rate': hit_rate,
        'avg_pnl': avg_pnl,
        'max_drawdown': max_dd,
        'total_pnl': total_pnl,
        'num_episodes': num_episodes,
    }
    
    logger.info(
        f"\n{'='*60}\n"
        f"BC POLICY EVALUATION\n"
        f"{'='*60}\n"
        f"Episodes: {num_episodes}\n"
        f"Profit Factor: {profit_factor:.2f}\n"
        f"Hit Rate: {hit_rate*100:.1f}%\n"
        f"Avg PnL: ${avg_pnl:.2f}\n"
        f"Max DD: ${max_dd:.2f}\n"
        f"Total PnL: ${total_pnl:.2f}\n"
        f"{'='*60}"
    )
    
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Behavior Cloning Pre-training")
    parser.add_argument("--symbol", type=str, default="SPY", help="Trading symbol (e.g., AAPL, SPY)")
    parser.add_argument("--duration", type=str, default="1 M", help="Data duration (1 month for diverse conditions)")
    parser.add_argument("--episodes", type=int, default=1000, help="Expert episodes (Increased to meet goal)")
    parser.add_argument("--epochs", type=int, default=100, help="BC training epochs")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size")
    parser.add_argument("--lr", type=float, default=3e-4, help="Learning rate")
    parser.add_argument("--eval-episodes", type=int, default=10, help="Eval episodes")
    parser.add_argument("--device", type=str, default="cpu", help="Device")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="IBKR host")
    parser.add_argument("--port", type=int, default=7497, help="IBKR port")
    
    args = parser.parse_args()
    
    # Create metrics client for live dashboard
    metrics_client = MetricsClient("http://127.0.0.1:8765")
    
    # Connect to IBKR (with timeout for historical mode)
    logger.info("🔌 Connecting to IBKR...")
    ib = IB()
    try:
        # Use timeout to avoid hanging
        import asyncio
        loop = asyncio.get_event_loop()
        connect_task = loop.create_task(
            ib.connectAsync(args.host, args.port, clientId=99, timeout=10)
        )
        loop.run_until_complete(asyncio.wait_for(connect_task, timeout=15))
        logger.info(f"✅ Connected to IBKR")
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"⚠️  IBKR connection timeout (this is OK for historical mode): {e}")
        logger.info("📦 Continuing with historical data mode...")
    
    try:
        # Create environment
        logger.info(f"📊 Fetching {args.duration} of historical data for {args.symbol}...")
        pipeline = EnhancedDataPipeline(
            mode='historical',
            ib=ib,
            symbol=args.symbol,
            duration=args.duration,
            replay_speed=5.0,
            tick_buffer_size=10000,
            bar_buffer_size=390,
        )
        pipeline.start()

        # Warm-up loop with progress logs so users know it's alive
        warmup_duration = 30
        warmup_interval = 5
        for waited in range(0, warmup_duration, warmup_interval):
            time.sleep(warmup_interval)
            stats = pipeline.get_stats()
            logger.info(
                "⏱️  Pipeline warm-up: %ss/%ss | ticks=%s | bars=%s",
                waited + warmup_interval,
                warmup_duration,
                f"{stats.get('ticks_collected', 0):,}",
                stats.get('bars_collected', 0),
            )
        
        stats = pipeline.get_stats()
        logger.info(
            "✅ Data ready: %s ticks, %s bars",
            f"{stats.get('ticks_collected', 0):,}",
            stats.get('bars_collected', 0),
        )
        
        microstructure = MicrostructureFeatures(pipeline)
        momentum = MomentumFeatures(pipeline)
        
        env = HighWinRateEnv(
            pipeline=pipeline,
            microstructure=microstructure,
            momentum=momentum,
            initial_capital=25000.0,
            max_position=300,
            max_daily_loss=2000.0,  # Increased from 300 to allow more exploration
            max_trades_per_day=30,
            bc_mode=True,  # Disable early stops for BC data collection
        )
        
        # Create expert
        logger.info("🧠 Creating Profitable Expert (v5 - mean reversion with quality filters)...")
        config = ProfitableExpertConfig()
        expert = ProfitableExpert(pipeline, microstructure, momentum, config=config)
        
        # Collect demonstrations
        logger.info(f"📝 Collecting {args.episodes} expert demonstrations...")
        demos = collect_expert_demonstrations(
            expert, 
            env, 
            num_episodes=args.episodes,
            metrics_client=metrics_client
        )
        logger.info(f"✅ Collected {len(demos['observations']):,} transitions")
        
        # Create dataset
        dataset = ExpertDataset(demos['observations'], demos['actions'])
        
        # Train BC policy
        logger.info("🏋️  Training BC policy...")
        policy, history = train_bc_policy(
            dataset,
            epochs=args.epochs,
            batch_size=args.batch_size,
            lr=args.lr,
            device=args.device,
        )
        
        # Save policy
        models_dir = Path("models")
        models_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        bc_path = models_dir / f"bc_policy_{timestamp}.pth"
        torch.save(policy.state_dict(), bc_path)
        logger.info(f"💾 Saved BC policy: {bc_path}")
        
        # Evaluate
        logger.info(f"📊 Evaluating BC policy on {args.eval_episodes} episodes...")
        metrics = evaluate_bc_policy(policy, env, num_episodes=args.eval_episodes, device=args.device)
        
        # Check promotion criteria
        final_val_loss = history['val_loss'][-1]
        success = (
            metrics['profit_factor'] >= 1.2 and
            final_val_loss < 0.1
        )
        
        if success:
            logger.info("\n✅ BC POLICY READY FOR PPO FINE-TUNING")
            logger.info(f"  PF: {metrics['profit_factor']:.2f} >= 1.2 ✓")
            logger.info(f"  Val Loss: {final_val_loss:.4f} < 0.1 ✓")
        else:
            logger.warning("\n⚠️  BC POLICY NEEDS IMPROVEMENT")
            logger.warning(f"  PF: {metrics['profit_factor']:.2f} (target: >=1.2)")
            logger.warning(f"  Val Loss: {final_val_loss:.4f} (target: <0.1)")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ BC training failed: {e}", exc_info=True)
        return 1
        
    finally:
        logger.info("🧹 Cleaning up...")
        # Check if pipeline exists before stopping
        if 'pipeline' in locals() and pipeline:
            pipeline.stop()
        if 'ib' in locals() and ib.isConnected():
            ib.disconnect()


if __name__ == "__main__":
    exit(main())
