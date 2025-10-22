"""
Unit tests for reinforcement learning module.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import tempfile

from src.models.reinforcement_learning import (
    QLearningAgent,
    RLState,
    RLAction,
    StrategyWeightOptimizer,
)


class TestQLearningAgent:
    """Tests for Q-learning agent."""
    
    def test_initialization(self):
        """Test agent initialization."""
        agent = QLearningAgent(n_strategies=2)
        
        assert agent.n_strategies == 2
        assert agent.learning_rate == 0.1
        assert agent.discount_factor == 0.95
        assert len(agent.actions) > 0
    
    def test_action_generation(self):
        """Test valid action generation."""
        agent = QLearningAgent(n_strategies=2)
        
        for action in agent.actions:
            assert len(action) == 2
            assert np.allclose(action.sum(), 1.0)
            assert np.all(action >= 0)
    
    def test_select_action(self):
        """Test action selection."""
        agent = QLearningAgent(n_strategies=2)
        
        state = RLState(
            market_regime='normal',
            recent_returns=np.array([0.01, 0.02]),
            volatility=0.15,
            correlation_matrix=np.eye(2),
            portfolio_concentration=0.5,
            current_weights=np.array([0.5, 0.5]),
        )
        
        action = agent.select_action(state, explore=False)
        
        assert isinstance(action, RLAction)
        assert action.validate()
    
    def test_update_q_values(self):
        """Test Q-value updates."""
        agent = QLearningAgent(n_strategies=2)
        
        state = RLState(
            market_regime='normal',
            recent_returns=np.array([0.01, 0.02]),
            volatility=0.15,
            correlation_matrix=np.eye(2),
            portfolio_concentration=0.5,
            current_weights=np.array([0.5, 0.5]),
        )
        
        next_state = RLState(
            market_regime='normal',
            recent_returns=np.array([0.015, 0.025]),
            volatility=0.16,
            correlation_matrix=np.eye(2),
            portfolio_concentration=0.5,
            current_weights=np.array([0.5, 0.5]),
        )
        
        action = agent.select_action(state, explore=False)
        reward = 0.5
        
        # Update should not raise
        agent.update(state, action, reward, next_state, done=False)
    
    def test_save_load(self):
        """Test model persistence."""
        agent = QLearningAgent(n_strategies=2)
        
        # Train a bit
        state = RLState(
            market_regime='normal',
            recent_returns=np.array([0.01, 0.02]),
            volatility=0.15,
            correlation_matrix=np.eye(2),
            portfolio_concentration=0.5,
            current_weights=np.array([0.5, 0.5]),
        )
        
        for _ in range(10):
            action = agent.select_action(state, explore=True)
            agent.update(state, action, 0.5, state, done=False)
        
        # Save and load
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'agent.json'
            agent.save(path)
            
            new_agent = QLearningAgent(n_strategies=2)
            new_agent.load(path)
            
            assert new_agent.epsilon == agent.epsilon
            assert len(new_agent.q_table) > 0


class TestStrategyWeightOptimizer:
    """Tests for strategy weight optimizer."""
    
    def test_initialization(self):
        """Test optimizer initialization."""
        optimizer = StrategyWeightOptimizer(
            strategy_names=['Strategy1', 'Strategy2'],
            agent_type='qlearning',
        )
        
        assert optimizer.n_strategies == 2
        assert len(optimizer.strategy_names) == 2
    
    def test_compute_state(self):
        """Test state computation."""
        optimizer = StrategyWeightOptimizer(
            strategy_names=['Strategy1', 'Strategy2'],
        )
        
        # Create mock returns
        returns_df = pd.DataFrame({
            'Strategy1': np.random.randn(100) * 0.01,
            'Strategy2': np.random.randn(100) * 0.01,
        })
        
        state = optimizer.compute_state(
            market_regime='normal',
            strategy_returns=returns_df,
            volatility=0.15,
        )
        
        assert isinstance(state, RLState)
        assert state.market_regime == 'normal'
        assert len(state.recent_returns) == 2
    
    def test_optimize_weights(self):
        """Test weight optimization."""
        optimizer = StrategyWeightOptimizer(
            strategy_names=['Strategy1', 'Strategy2'],
        )
        
        returns_df = pd.DataFrame({
            'Strategy1': np.random.randn(100) * 0.01,
            'Strategy2': np.random.randn(100) * 0.01,
        })
        
        state = optimizer.compute_state(
            market_regime='normal',
            strategy_returns=returns_df,
            volatility=0.15,
        )
        
        weights = optimizer.optimize_weights(state, train=False)
        
        assert len(weights) == 2
        assert np.allclose(weights.sum(), 1.0)
        assert np.all(weights >= 0)
    
    def test_update_from_performance(self):
        """Test performance-based updates."""
        optimizer = StrategyWeightOptimizer(
            strategy_names=['Strategy1', 'Strategy2'],
        )
        
        returns_df = pd.DataFrame({
            'Strategy1': np.random.randn(50) * 0.01,
            'Strategy2': np.random.randn(50) * 0.01,
        })
        
        prev_state = optimizer.compute_state('normal', returns_df, 0.15)
        action = RLAction(strategy_weights=np.array([0.5, 0.5]))
        next_state = optimizer.compute_state('normal', returns_df.iloc[1:], 0.16)
        
        # Should not raise
        optimizer.update_from_performance(
            prev_state=prev_state,
            action=action,
            portfolio_return=0.01,
            portfolio_sharpe=1.5,
            next_state=next_state,
        )
        
        assert len(optimizer.performance_history) == 1


def test_rl_action_validation():
    """Test RLAction validation."""
    # Valid action
    action = RLAction(strategy_weights=np.array([0.3, 0.7]))
    assert action.validate()
    
    # Invalid: doesn't sum to 1
    action = RLAction(strategy_weights=np.array([0.3, 0.5]))
    assert not action.validate()
    
    # Invalid: negative weight
    action = RLAction(strategy_weights=np.array([-0.1, 1.1]))
    assert not action.validate()
