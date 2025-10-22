"""
Reinforcement Learning Module for Dynamic Strategy Weighting.

Implements Q-learning and PPO agents for adaptive strategy selection
and weight optimization based on market conditions and performance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from collections import deque
import json
from pathlib import Path

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RLState:
    """State representation for RL agent."""
    market_regime: str  # 'normal', 'high_vix', 'spy_stress'
    recent_returns: np.ndarray  # Last N strategy returns
    volatility: float
    correlation_matrix: np.ndarray
    portfolio_concentration: float
    current_weights: np.ndarray


@dataclass
class RLAction:
    """Action representation - new strategy weights."""
    strategy_weights: np.ndarray  # Weights for each strategy (sum to 1)
    
    def validate(self) -> bool:
        """Ensure weights are valid (sum to 1, non-negative)."""
        return np.allclose(self.strategy_weights.sum(), 1.0) and np.all(self.strategy_weights >= 0)


class QLearningAgent:
    """
    Q-Learning agent for strategy weight optimization.
    
    Discretizes the weight space and learns optimal allocations
    through exploration and exploitation.
    """
    
    def __init__(
        self,
        n_strategies: int,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 0.1,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
    ):
        self.n_strategies = n_strategies
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        
        # Q-table: state -> action -> value
        self.q_table: Dict[str, Dict[str, float]] = {}
        
        # Discrete weight allocations (e.g., 0%, 25%, 50%, 75%, 100%)
        self.weight_levels = [0.0, 0.25, 0.5, 0.75, 1.0]
        self.actions = self._generate_valid_actions()
        
        logger.info(f"Initialized Q-Learning agent with {len(self.actions)} discrete actions")
    
    def _generate_valid_actions(self) -> List[np.ndarray]:
        """Generate all valid weight combinations that sum to 1."""
        actions = []
        
        # For simplicity, use simple allocations
        if self.n_strategies == 2:
            for w1 in self.weight_levels:
                w2 = 1.0 - w1
                if 0 <= w2 <= 1:
                    actions.append(np.array([w1, w2]))
        
        elif self.n_strategies == 3:
            for w1 in self.weight_levels:
                for w2 in self.weight_levels:
                    w3 = 1.0 - w1 - w2
                    if 0 <= w3 <= 1:
                        actions.append(np.array([w1, w2, w3]))
        
        else:
            # For more strategies, use equal weight and variations
            equal = 1.0 / self.n_strategies
            actions.append(np.ones(self.n_strategies) * equal)
            
            # Single strategy allocations
            for i in range(self.n_strategies):
                weights = np.zeros(self.n_strategies)
                weights[i] = 1.0
                actions.append(weights)
            
            # Pairs
            for i in range(self.n_strategies):
                for j in range(i + 1, self.n_strategies):
                    weights = np.zeros(self.n_strategies)
                    weights[i] = 0.5
                    weights[j] = 0.5
                    actions.append(weights)
        
        return actions
    
    def _state_to_key(self, state: RLState) -> str:
        """Convert state to hashable key."""
        # Simplified state discretization
        regime = state.market_regime
        volatility_bucket = 'low' if state.volatility < 0.15 else 'medium' if state.volatility < 0.25 else 'high'
        recent_return = 'positive' if state.recent_returns.mean() > 0 else 'negative'
        
        return f"{regime}_{volatility_bucket}_{recent_return}"
    
    def _action_to_key(self, action: np.ndarray) -> str:
        """Convert action to hashable key."""
        return ",".join([f"{w:.2f}" for w in action])
    
    def select_action(self, state: RLState, explore: bool = True) -> RLAction:
        """
        Select action using epsilon-greedy policy.
        
        Args:
            state: Current market state
            explore: Whether to allow exploration (False for inference)
        
        Returns:
            Action to take (strategy weights)
        """
        state_key = self._state_to_key(state)
        
        # Initialize state in Q-table if new
        if state_key not in self.q_table:
            self.q_table[state_key] = {
                self._action_to_key(action): 0.0 for action in self.actions
            }
        
        # Epsilon-greedy exploration
        if explore and np.random.random() < self.epsilon:
            action = self.actions[np.random.randint(len(self.actions))]
            logger.debug(f"Exploring with action: {action}")
        else:
            # Exploit: choose best action
            q_values = self.q_table[state_key]
            best_action_key = max(q_values, key=q_values.get)
            action = np.array([float(w) for w in best_action_key.split(",")])
            logger.debug(f"Exploiting with best action: {action}")
        
        return RLAction(strategy_weights=action)
    
    def update(
        self,
        state: RLState,
        action: RLAction,
        reward: float,
        next_state: RLState,
        done: bool
    ):
        """
        Update Q-values using the Q-learning update rule.
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received (e.g., Sharpe ratio, return)
            next_state: Next state
            done: Whether episode ended
        """
        state_key = self._state_to_key(state)
        action_key = self._action_to_key(action.strategy_weights)
        next_state_key = self._state_to_key(next_state)
        
        # Initialize if needed
        if state_key not in self.q_table:
            self.q_table[state_key] = {
                self._action_to_key(a): 0.0 for a in self.actions
            }
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = {
                self._action_to_key(a): 0.0 for a in self.actions
            }
        
        # Q-learning update
        current_q = self.q_table[state_key][action_key]
        
        if done:
            target_q = reward
        else:
            max_next_q = max(self.q_table[next_state_key].values())
            target_q = reward + self.discount_factor * max_next_q
        
        # Update Q-value
        new_q = current_q + self.learning_rate * (target_q - current_q)
        self.q_table[state_key][action_key] = new_q
        
        # Decay epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        
        logger.debug(
            f"Updated Q({state_key}, {action_key}): {current_q:.3f} -> {new_q:.3f}, "
            f"reward={reward:.3f}, epsilon={self.epsilon:.3f}"
        )
    
    def save(self, path: Path):
        """Save Q-table to disk."""
        data = {
            'q_table': self.q_table,
            'epsilon': self.epsilon,
            'n_strategies': self.n_strategies,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved Q-learning model to {path}")
    
    def load(self, path: Path):
        """Load Q-table from disk."""
        with open(path, 'r') as f:
            data = json.load(f)
        self.q_table = data['q_table']
        self.epsilon = data['epsilon']
        logger.info(f"Loaded Q-learning model from {path}")


class StrategyWeightOptimizer:
    """
    High-level optimizer that uses RL to adapt strategy weights.
    
    Integrates with existing trading strategies (GemScore, BounceHunter)
    to dynamically adjust allocations based on performance and market regime.
    """
    
    def __init__(
        self,
        strategy_names: List[str],
        agent_type: str = 'qlearning',
        lookback_window: int = 20,
        rebalance_frequency: int = 5,  # days
    ):
        """
        Initialize strategy weight optimizer.
        
        Args:
            strategy_names: List of strategy identifiers
            agent_type: RL agent type ('qlearning' or 'ppo')
            lookback_window: Number of periods for state calculation
            rebalance_frequency: How often to rebalance (in days)
        """
        self.strategy_names = strategy_names
        self.n_strategies = len(strategy_names)
        self.lookback_window = lookback_window
        self.rebalance_frequency = rebalance_frequency
        
        # Initialize RL agent
        if agent_type == 'qlearning':
            self.agent = QLearningAgent(n_strategies=self.n_strategies)
        else:
            raise ValueError(f"Agent type {agent_type} not supported yet")
        
        # Performance tracking
        self.performance_history: deque = deque(maxlen=lookback_window)
        self.weight_history: List[Tuple[pd.Timestamp, np.ndarray]] = []
        
        logger.info(f"Initialized StrategyWeightOptimizer with {self.n_strategies} strategies")
    
    def compute_state(
        self,
        market_regime: str,
        strategy_returns: pd.DataFrame,
        volatility: float,
    ) -> RLState:
        """
        Compute current state representation.
        
        Args:
            market_regime: Current market regime classification
            strategy_returns: DataFrame with strategy returns (rows=time, cols=strategies)
            volatility: Current market volatility (e.g., VIX)
        
        Returns:
            RLState object
        """
        # Recent returns for each strategy
        recent_returns = strategy_returns.tail(self.lookback_window).mean().values
        
        # Correlation matrix
        correlation_matrix = strategy_returns.tail(self.lookback_window).corr().values
        
        # Portfolio concentration (inverse of effective number of strategies)
        current_weights = np.ones(self.n_strategies) / self.n_strategies  # Default equal weight
        if len(self.weight_history) > 0:
            current_weights = self.weight_history[-1][1]
        
        herfindahl = np.sum(current_weights ** 2)
        portfolio_concentration = herfindahl
        
        return RLState(
            market_regime=market_regime,
            recent_returns=recent_returns,
            volatility=volatility,
            correlation_matrix=correlation_matrix,
            portfolio_concentration=portfolio_concentration,
            current_weights=current_weights,
        )
    
    def optimize_weights(
        self,
        state: RLState,
        train: bool = False,
    ) -> np.ndarray:
        """
        Get optimal strategy weights for current state.
        
        Args:
            state: Current market state
            train: Whether we're in training mode (allows exploration)
        
        Returns:
            Array of strategy weights (sum to 1)
        """
        action = self.agent.select_action(state, explore=train)
        
        if not action.validate():
            logger.warning("Invalid action generated, using equal weights")
            return np.ones(self.n_strategies) / self.n_strategies
        
        return action.strategy_weights
    
    def update_from_performance(
        self,
        prev_state: RLState,
        action: RLAction,
        portfolio_return: float,
        portfolio_sharpe: float,
        next_state: RLState,
        done: bool = False,
    ):
        """
        Update agent based on realized performance.
        
        Args:
            prev_state: Previous market state
            action: Action taken (weights used)
            portfolio_return: Realized portfolio return
            portfolio_sharpe: Realized Sharpe ratio
            next_state: New market state
            done: Whether episode ended
        """
        # Reward is a combination of return and risk-adjusted return
        reward = 0.5 * portfolio_return + 0.5 * portfolio_sharpe
        
        self.agent.update(prev_state, action, reward, next_state, done)
        
        # Track performance
        self.performance_history.append({
            'return': portfolio_return,
            'sharpe': portfolio_sharpe,
            'reward': reward,
        })
        
        logger.info(
            f"Performance update: return={portfolio_return:.3f}, "
            f"sharpe={portfolio_sharpe:.3f}, reward={reward:.3f}"
        )
    
    def get_performance_summary(self) -> Dict[str, float]:
        """Get summary statistics of recent performance."""
        if not self.performance_history:
            return {}
        
        returns = [p['return'] for p in self.performance_history]
        sharpes = [p['sharpe'] for p in self.performance_history]
        rewards = [p['reward'] for p in self.performance_history]
        
        return {
            'mean_return': np.mean(returns),
            'mean_sharpe': np.mean(sharpes),
            'mean_reward': np.mean(rewards),
            'volatility': np.std(returns),
            'n_samples': len(self.performance_history),
        }
    
    def save(self, path: Path):
        """Save optimizer state."""
        self.agent.save(path / 'agent.json')
        
        # Save weight history
        weight_df = pd.DataFrame(
            [{'timestamp': ts, **{f'weight_{i}': w for i, w in enumerate(weights)}}
             for ts, weights in self.weight_history]
        )
        weight_df.to_csv(path / 'weight_history.csv', index=False)
        
        logger.info(f"Saved optimizer state to {path}")
    
    def load(self, path: Path):
        """Load optimizer state."""
        self.agent.load(path / 'agent.json')
        
        # Load weight history
        weight_df = pd.read_csv(path / 'weight_history.csv')
        self.weight_history = [
            (pd.Timestamp(row['timestamp']), 
             np.array([row[f'weight_{i}'] for i in range(self.n_strategies)]))
            for _, row in weight_df.iterrows()
        ]
        
        logger.info(f"Loaded optimizer state from {path}")
