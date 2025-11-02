"""
Metrics Client - Push metrics from training scripts to dashboard server

Simple HTTP client to send training metrics to the live dashboard.
"""

import requests
import time
from typing import Dict, Optional


class MetricsClient:
    """Push metrics to dashboard server"""
    
    def __init__(self, server_url: str = "http://127.0.0.1:8765"):
        self.server_url = server_url.rstrip('/')
        self.push_url = f"{self.server_url}/push"
        self._connected = False
        self._check_connection()
    
    def _check_connection(self):
        """Check if dashboard server is running"""
        try:
            response = requests.get(f"{self.server_url}/health", timeout=2)
            self._connected = response.status_code == 200
            if self._connected:
                print(f"✅ Connected to dashboard at {self.server_url}")
        except Exception as e:
            print(f"⚠️  Dashboard server not reachable at {self.server_url}")
            print(f"   Start it with: uvicorn dashboard_server:app --host 127.0.0.1 --port 8765")
            self._connected = False
    
    def push(
        self,
        phase: str,
        # BC metrics
        episode: Optional[int] = None,
        total_episodes: Optional[int] = None,
        trades: Optional[int] = None,
        wins: Optional[int] = None,
        losses: Optional[int] = None,
        hit_rate: Optional[float] = None,
        pf: Optional[float] = None,
        equity: Optional[float] = None,
        reasons: Optional[Dict[str, int]] = None,
        # PPO metrics
        steps: Optional[int] = None,
        total_steps: Optional[int] = None,
        kl: Optional[float] = None,
        entropy: Optional[float] = None,
        loss_policy: Optional[float] = None,
        loss_value: Optional[float] = None,
        reward_mean: Optional[float] = None,
        # General
        note: Optional[str] = None,
    ):
        """
        Push metrics to dashboard.
        
        Args:
            phase: "BC" or "PPO"
            
            BC metrics:
                episode: Current episode number
                total_episodes: Total episodes to collect
                trades: Trades in this episode
                wins: Winning trades
                losses: Losing trades
                hit_rate: Win rate (0-1)
                pf: Profit factor
                equity: Current equity value
                reasons: Dict of block reasons {"spread": 10, "rsi": 5, ...}
            
            PPO metrics:
                steps: Current timestep
                total_steps: Total training steps
                kl: KL divergence
                entropy: Policy entropy
                loss_policy: Policy loss
                loss_value: Value loss
                reward_mean: Mean episode reward
            
            General:
                note: Text note/status message
        """
        if not self._connected:
            return  # Silently skip if server not available
        
        payload = {
            "phase": phase,
            "timestamp": time.time(),
        }
        
        # Add all non-None metrics
        if episode is not None:
            payload["episode"] = episode
        if total_episodes is not None:
            payload["total_episodes"] = total_episodes
        if trades is not None:
            payload["trades"] = trades
        if wins is not None:
            payload["wins"] = wins
        if losses is not None:
            payload["losses"] = losses
        if hit_rate is not None:
            payload["hit_rate"] = hit_rate
        if pf is not None:
            payload["pf"] = pf
        if equity is not None:
            payload["equity"] = equity
        if reasons is not None:
            payload["reasons"] = reasons
        if steps is not None:
            payload["steps"] = steps
        if total_steps is not None:
            payload["total_steps"] = total_steps
        if kl is not None:
            payload["kl"] = kl
        if entropy is not None:
            payload["entropy"] = entropy
        if loss_policy is not None:
            payload["loss_policy"] = loss_policy
        if loss_value is not None:
            payload["loss_value"] = loss_value
        if reward_mean is not None:
            payload["reward_mean"] = reward_mean
        if note is not None:
            payload["note"] = note
        
        try:
            requests.post(self.push_url, json=payload, timeout=1)
        except Exception as e:
            # Silently fail - don't crash training if dashboard goes down
            pass


# Convenience function
def create_client(server_url: str = "http://127.0.0.1:8765") -> MetricsClient:
    """Create a metrics client"""
    return MetricsClient(server_url)
