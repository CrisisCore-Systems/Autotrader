"""
Test script for simplified action space implementation.

Validates that the 3-action space (FLAT, LONG, SHORT) works correctly
with fixed 100-share position sizing.
"""

import numpy as np
from src.intraday.trading_env import IntradayTradingEnv
from src.intraday.data_pipeline import IntradayDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures


def test_action_space():
    """Test that action space is correctly set to 3 discrete actions."""
    print("🧪 Testing action space configuration...")
    
    # Mock components (we'll use synthetic data)
    from unittest.mock import MagicMock
    
    pipeline = MagicMock(spec=IntradayDataPipeline)
    microstructure = MagicMock(spec=MicrostructureFeatures)
    momentum = MagicMock(spec=MomentumFeatures)
    
    # Set up mock returns
    microstructure.compute.return_value = np.zeros(10)
    microstructure.get_feature_names.return_value = [f"micro_{i}" for i in range(10)]
    momentum.compute.return_value = np.zeros(8)
    momentum.get_feature_names.return_value = [f"momentum_{i}" for i in range(8)]
    
    # Create environment
    env = IntradayTradingEnv(
        pipeline=pipeline,
        microstructure=microstructure,
        momentum=momentum,
        initial_capital=25000.0,
    )
    
    # Verify action space
    assert env.action_space.n == 3, f"Expected 3 actions, got {env.action_space.n}"
    print(f"✅ Action space: {env.action_space.n} discrete actions")
    
    # Verify fixed position size
    assert hasattr(env, 'fixed_position_size'), "Missing fixed_position_size attribute"
    assert env.fixed_position_size == 100, f"Expected 100 shares, got {env.fixed_position_size}"
    print(f"✅ Fixed position size: {env.fixed_position_size} shares")
    
    print("\n✅ All action space tests passed!")


def test_action_execution():
    """Test that each action executes correctly."""
    print("\n🧪 Testing action execution...")
    
    from unittest.mock import MagicMock
    from dataclasses import dataclass
    
    @dataclass
    class MockBar:
        open: float = 100.0
        high: float = 101.0
        low: float = 99.0
        close: float = 100.5
        volume: int = 1000000
    
    pipeline = MagicMock(spec=IntradayDataPipeline)
    microstructure = MagicMock(spec=MicrostructureFeatures)
    momentum = MagicMock(spec=MomentumFeatures)
    
    # Set up mocks
    microstructure.compute.return_value = np.zeros(10)
    microstructure.get_feature_names.return_value = [f"micro_{i}" for i in range(10)]
    momentum.compute.return_value = np.zeros(8)
    momentum.get_feature_names.return_value = [f"momentum_{i}" for i in range(8)]
    
    # Mock bar data
    bars = [MockBar(close=100.0 + i*0.1) for i in range(100)]
    pipeline.get_latest_bars.return_value = bars
    pipeline.get_current_price.return_value = 100.5
    pipeline.tick_buffer = []
    
    # Create environment
    env = IntradayTradingEnv(
        pipeline=pipeline,
        microstructure=microstructure,
        momentum=momentum,
        initial_capital=25000.0,
    )
    
    # Reset environment
    obs, info = env.reset()
    print(f"✅ Environment reset: obs shape={obs.shape}, capital=${info['capital']:.2f}")
    
    # Test Action 0: FLAT (should do nothing when already flat)
    obs, reward, term, trunc, info = env.step(0)
    assert env.position_qty == 0, "FLAT action should keep position at 0"
    print(f"✅ Action 0 (FLAT): position={env.position_qty}, reward={reward:.4f}")
    
    # Test Action 1: LONG (should open 100-share long)
    # Disable filters for testing
    env.curriculum.enable_quality_filters = False
    env.min_bars_between_trades = 0  # Disable throttling for tests
    obs, reward, term, trunc, info = env.step(1)
    assert env.position_qty == 100, f"LONG action should open 100 shares, got {env.position_qty}"
    print(f"✅ Action 1 (LONG): position={env.position_qty}, entry=${env.entry_price:.2f}")
    
    # Test Action 0: FLAT (should close long position)
    obs, reward, term, trunc, info = env.step(0)
    assert env.position_qty == 0, "FLAT should close long position"
    print(f"✅ Action 0 (FLAT): closed position, PnL=${info['daily_pnl']:.2f}")
    
    # Test Action 2: SHORT (should open 100-share short)
    obs, reward, term, trunc, info = env.step(2)
    assert env.position_qty == -100, f"SHORT action should open -100 shares, got {env.position_qty}"
    print(f"✅ Action 2 (SHORT): position={env.position_qty}, entry=${env.entry_price:.2f}")
    
    # Test Action 1: LONG (should reverse from short to long)
    initial_trades = env.daily_trades
    obs, reward, term, trunc, info = env.step(1)
    assert env.position_qty == 100, f"LONG should reverse to +100 shares, got {env.position_qty}"
    assert env.daily_trades > initial_trades, "Reversal should count as trades"
    print(f"✅ Action 1 (LONG): reversed from SHORT, position={env.position_qty}")
    
    print("\n✅ All action execution tests passed!")


def test_position_sizing():
    """Test that position sizing is fixed at 100 shares."""
    print("\n🧪 Testing fixed position sizing...")
    
    from unittest.mock import MagicMock
    from dataclasses import dataclass
    
    @dataclass
    class MockBar:
        open: float = 100.0
        high: float = 101.0
        low: float = 99.0
        close: float = 100.5
        volume: int = 1000000
    
    pipeline = MagicMock(spec=IntradayDataPipeline)
    microstructure = MagicMock(spec=MicrostructureFeatures)
    momentum = MagicMock(spec=MomentumFeatures)
    
    microstructure.compute.return_value = np.zeros(10)
    microstructure.get_feature_names.return_value = [f"micro_{i}" for i in range(10)]
    momentum.compute.return_value = np.zeros(8)
    momentum.get_feature_names.return_value = [f"momentum_{i}" for i in range(8)]
    
    bars = [MockBar(close=100.0 + i*0.1) for i in range(100)]
    pipeline.get_latest_bars.return_value = bars
    pipeline.get_current_price.return_value = 100.5
    pipeline.tick_buffer = []
    
    env = IntradayTradingEnv(
        pipeline=pipeline,
        microstructure=microstructure,
        momentum=momentum,
        initial_capital=25000.0,
    )
    
    env.reset()
    env.curriculum.enable_quality_filters = False
    env.min_bars_between_trades = 0  # Disable throttling for tests
    
    # Open multiple positions and verify they're all 100 shares
    position_sizes = []
    
    for _ in range(5):
        # Open long
        env.step(1)
        position_sizes.append(abs(env.position_qty))
        
        # Close
        env.step(0)
        
        # Open short
        env.step(2)
        position_sizes.append(abs(env.position_qty))
        
        # Close
        env.step(0)
    
    # Verify all positions were exactly 100 shares
    assert all(size == 100 for size in position_sizes), f"Position sizes not fixed: {position_sizes}"
    print(f"✅ All {len(position_sizes)} positions were exactly 100 shares")
    
    print("\n✅ Fixed position sizing tests passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("SIMPLIFIED ACTION SPACE TEST SUITE")
    print("=" * 60)
    
    test_action_space()
    test_action_execution()
    test_position_sizing()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nSimplified action space is ready for training.")
    print("Next step: Run training with:")
    print("  python scripts/train_intraday_ppo.py --symbol SPY --duration '30 D' --timesteps 50000")
