"""
Visual Instrumentation for Training - Rich Live Dashboards + Progress Bars

Provides loud, live feedback during BC collection and PPO training so you always
know the system is alive and what's blocking progress.

Features:
- Rich live dashboard with episode/trade stats
- TQDM progress bars for epochs/episodes
- Heartbeat callback for PPO (prints every N steps)
- Block reason tracking (spread/cooldown/RSI/imbalance/time/stop)
- Equity curve snapshots
- Windows toast notifications on milestones
"""

from __future__ import annotations

import time
from typing import Dict, Optional, List
from pathlib import Path

import numpy as np
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.console import Console

try:
    from stable_baselines3.common.callbacks import BaseCallback
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False

console = Console()


class BCCollectionDashboard:
    """
    Live dashboard for BC episode collection with block reason tracking.
    
    Usage:
        dashboard = BCCollectionDashboard(total_episodes=100)
        dashboard.start()
        
        for ep in range(100):
            # ... collect episode ...
            dashboard.update(
                episodes=ep+1,
                trades=trades_count,
                wins=wins_count,
                losses=losses_count,
                blocks={'spread': 5, 'cooldown': 12, ...}
            )
        
        dashboard.stop()
    """
    
    def __init__(self, total_episodes: int):
        self.total_episodes = total_episodes
        self.start_time = None
        self.live = None
        self.progress = None
        self.task = None
        
        # Stats
        self.stats = {
            'episodes': 0,
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'blocked_spread': 0,
            'blocked_cooldown': 0,
            'blocked_rsi': 0,
            'blocked_imbalance': 0,
            'blocked_time': 0,
            'blocked_stop': 0,
            'blocked_size': 0,
        }
    
    def start(self):
        """Start live dashboard."""
        self.start_time = time.perf_counter()
        
        # Create progress bar
        self.progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•", TimeElapsedColumn(),
            "• ETA", TimeRemainingColumn(),
        )
        self.task = self.progress.add_task(
            "📝 Collecting expert episodes",
            total=self.total_episodes
        )
        
        # Start live display
        self.live = Live(self._render_panel(), refresh_per_second=4)
        self.live.start()
    
    def update(
        self,
        episodes: Optional[int] = None,
        trades: Optional[int] = None,
        wins: Optional[int] = None,
        losses: Optional[int] = None,
        blocks: Optional[Dict[str, int]] = None,
    ):
        """Update dashboard stats."""
        if episodes is not None:
            self.stats['episodes'] = episodes
            self.progress.update(self.task, completed=episodes)
        
        if trades is not None:
            self.stats['trades'] = trades
        
        if wins is not None:
            self.stats['wins'] = wins
        
        if losses is not None:
            self.stats['losses'] = losses
        
        if blocks is not None:
            for key, value in blocks.items():
                block_key = f'blocked_{key}'
                if block_key in self.stats:
                    self.stats[block_key] = value
        
        # Update live display
        if self.live:
            self.live.update(self._render_panel())
    
    def _render_panel(self) -> Panel:
        """Render dashboard panel."""
        # Create stats table
        table = Table(title="🧠 Behavior Cloning – Live Collection", show_header=True)
        table.add_column("Metric", style="cyan", width=20)
        table.add_column("Value", style="green", width=15)
        
        # Episode stats
        table.add_row("Episodes", str(self.stats['episodes']))
        table.add_row("Trades Collected", str(self.stats['trades']))
        
        # Win rate
        total = self.stats['wins'] + self.stats['losses']
        win_rate = (self.stats['wins'] / max(1, total)) * 100
        win_rate_str = f"{win_rate:.1f}% ({self.stats['wins']}/{total})"
        table.add_row("Win Rate", win_rate_str)
        
        # Trades per episode
        tpe = self.stats['trades'] / max(1, self.stats['episodes'])
        table.add_row("Trades/Episode", f"{tpe:.1f}")
        
        # Block reasons summary
        blocks_str = ", ".join([
            f"spr={self.stats['blocked_spread']}",
            f"cd={self.stats['blocked_cooldown']}",
            f"rsi={self.stats['blocked_rsi']}",
            f"imb={self.stats['blocked_imbalance']}",
            f"time={self.stats['blocked_time']}",
            f"stop={self.stats['blocked_stop']}",
            f"size={self.stats['blocked_size']}",
        ])
        
        # Elapsed time
        if self.start_time:
            elapsed = time.perf_counter() - self.start_time
            elapsed_str = f"{elapsed:.1f}s"
        else:
            elapsed_str = "N/A"
        
        return Panel.fit(
            table,
            subtitle=f"🚫 Blocks: {blocks_str}",
            border_style="blue"
        )
    
    def stop(self):
        """Stop live dashboard."""
        if self.live:
            self.live.stop()
        if self.progress:
            self.progress.stop()
        
        # Print final summary
        elapsed = time.perf_counter() - self.start_time if self.start_time else 0
        console.print(f"\n✅ Collection complete in {elapsed:.1f}s")
        console.print(f"   Episodes: {self.stats['episodes']}")
        console.print(f"   Trades: {self.stats['trades']}")
        console.print(f"   Win Rate: {(self.stats['wins']/max(1, self.stats['wins']+self.stats['losses']))*100:.1f}%")


class HeartbeatCallback(BaseCallback):
    """
    PPO training heartbeat - prints status every N steps.
    
    Prevents training from appearing frozen by printing regular updates
    with key metrics: reward, KL divergence, entropy, win rate.
    """
    
    def __init__(self, every: int = 5000, verbose: int = 1):
        super().__init__(verbose)
        self.every = every
        self.last_print = 0
    
    def _on_step(self) -> bool:
        if (self.num_timesteps - self.last_print) >= self.every:
            self.last_print = self.num_timesteps
            
            # Get metrics from logger
            logger = self.model.logger
            rew_mean = logger.name_to_value.get('rollout/ep_rew_mean', float('nan'))
            kl = logger.name_to_value.get('train/approx_kl', float('nan'))
            ent = logger.name_to_value.get('train/entropy_loss', float('nan'))
            v_loss = logger.name_to_value.get('train/value_loss', float('nan'))
            
            # Print heartbeat
            console.print(
                f"💓 [HB] t={self.num_timesteps:,} | "
                f"rew={rew_mean:.2f} | KL={kl:.6f} | "
                f"ent={ent:.4f} | v_loss={v_loss:.2e}",
                style="bold yellow"
            )
        
        return True


class StallWatchdog:
    """
    Watchdog timer that alerts if no activity for X seconds.
    
    Useful for detecting data starvation or deadlocks.
    """
    
    def __init__(self, timeout_seconds: int = 60):
        self.timeout = timeout_seconds
        self.last_activity = time.time()
        self.alerted = False
    
    def touch(self):
        """Mark activity (call on every trade/step/episode)."""
        self.last_activity = time.time()
        self.alerted = False
    
    def check(self):
        """Check if stalled and alert if needed."""
        elapsed = time.time() - self.last_activity
        if elapsed > self.timeout and not self.alerted:
            console.print(
                f"\n⚠️  [WATCHDOG] No activity in {elapsed:.0f}s — "
                f"possible data starvation or deadlock!",
                style="bold red"
            )
            self.alerted = True


def save_equity_curve(
    equity_series: List[float],
    path: str = "artifacts/equity_curve.png",
    title: str = "Episode Equity Curve"
):
    """
    Save equity curve as PNG for quick visual check.
    
    Args:
        equity_series: List of equity values over time
        path: Output path for PNG
        title: Chart title
    """
    import matplotlib.pyplot as plt
    
    # Create output directory
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    # Plot
    plt.figure(figsize=(10, 6))
    plt.plot(equity_series, linewidth=2)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel("Step", fontsize=12)
    plt.ylabel("Equity ($)", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    
    console.print(f"📊 Equity curve saved: {path}", style="green")


def toast_notification(title: str, message: str, duration: int = 5):
    """
    Show Windows toast notification on milestone.
    
    Args:
        title: Notification title
        message: Notification message
        duration: Display duration in seconds
    """
    try:
        from win10toast import ToastNotifier
        toast = ToastNotifier()
        toast.show_toast(title, message, duration=duration, threaded=True)
    except ImportError:
        # Silently skip if win10toast not installed
        pass


if __name__ == "__main__":
    # Demo
    console.print("Testing BC Collection Dashboard...\n")
    
    dashboard = BCCollectionDashboard(total_episodes=10)
    dashboard.start()
    
    for ep in range(10):
        time.sleep(0.5)
        dashboard.update(
            episodes=ep + 1,
            trades=ep * 3 + 5,
            wins=ep * 2,
            losses=ep + 1,
            blocks={
                'spread': ep,
                'cooldown': ep * 2,
                'rsi': ep // 2,
                'imbalance': ep,
                'time': ep // 3,
                'stop': ep // 4,
            }
        )
    
    dashboard.stop()
    
    console.print("\n✅ Dashboard test complete!")
