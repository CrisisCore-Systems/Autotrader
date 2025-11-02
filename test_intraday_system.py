"""
Intraday Trading System - Integration Test

Tests all components together:
1. Data pipeline connection
2. Feature extraction
3. Environment creation
4. Random agent episode

Run this after connecting to IBKR to verify everything works.
"""

import sys
import time
import logging
from datetime import datetime

try:
    from ib_insync import IB
    from src.intraday.enhanced_pipeline import EnhancedDataPipeline
    from src.intraday.microstructure import MicrostructureFeatures
    from src.intraday.momentum import MomentumFeatures
    from src.intraday.trading_env import IntradayTradingEnv
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nInstall missing packages:")
    print("  pip install ib_insync gymnasium stable-baselines3")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_ibkr_connection(host='127.0.0.1', port=7497, client_id=1, required=False):
    """Test IBKR connection (optional)."""
    print("\n" + "="*60)
    print("TEST 1: IBKR Connection (Optional)")
    print("="*60)
    
    try:
        ib = IB()
        ib.connect(host, port, clientId=client_id, timeout=5)
        
        print(f"✅ Connected to IBKR at {host}:{port}")
        print(f"   Client ID: {client_id}")
        print(f"   Account: {ib.managedAccounts()}")
        
        return ib
    
    except Exception as e:
        if required:
            print(f"❌ Connection failed: {e}")
            print("\nTroubleshooting:")
            print("  1. Is TWS or IB Gateway running?")
            print("  2. Is API enabled? (Global Config → API → Settings)")
            print("  3. Is 127.0.0.1 in trusted IPs?")
            print("  4. Using correct port? (7497=paper, 7496=live)")
            return None
        else:
            print(f"⚠️  No IBKR connection (this is OK)")
            print(f"   Will use simulated data for testing")
            print(f"   Error: {e}")
            return None


def test_data_pipeline(ib, symbol='SPY', duration=120):
    """Test data pipeline with simulated or real data."""
    print("\n" + "="*60)
    print(f"TEST 2: Data Pipeline (collecting for {duration}s)")
    print("="*60)
    
    try:
        # Choose mode based on IBKR connection
        if ib is not None:
            mode = 'historical'
            print(f"📊 Using HISTORICAL data mode (5-day replay)")
        else:
            mode = 'simulated'
            print(f"🎲 Using SIMULATED data mode (synthetic ticks)")
        
        pipeline = EnhancedDataPipeline(
            mode=mode,
            ib=ib,
            symbol=symbol,
            # Historical params
            duration='5 D',
            replay_speed=10.0,  # 10x faster
            # Simulated params
            initial_price=580.0,
            tick_interval=0.01,  # 10ms per tick
            volatility=0.0001,
        )
        
        pipeline.start()
        
        print(f"✅ Started {mode} pipeline for {symbol}")
        print(f"   Collecting data for {duration} seconds...")
        
        # Wait and show progress
        for i in range(duration // 10):
            time.sleep(10)
            stats = pipeline.get_stats()
            print(f"   [{(i+1)*10}s] Ticks: {stats['ticks_collected']}, "
                  f"Bars: {stats['bars_collected']}, "
                  f"Price: ${stats['current_price']:.2f}, "
                  f"Imbalance: {stats['volume_imbalance']:.3f}")
        
        # Final stats
        stats = pipeline.get_stats()
        print(f"\n📊 Final Stats:")
        print(f"   Mode: {stats['mode']}")
        print(f"   Ticks collected: {stats['ticks_collected']}")
        print(f"   Bars collected: {stats['bars_collected']}")
        print(f"   Current price: ${stats['current_price']:.2f}")
        print(f"   Spread: ${stats['spread']:.4f} ({stats['spread_pct']:.2f}%)")
        print(f"   Volume imbalance: {stats['volume_imbalance']:.3f}")
        
        if stats['ticks_collected'] < 50:
            print(f"\n⚠️  Warning: Only {stats['ticks_collected']} ticks collected.")
            print("   Features may be inaccurate. Consider longer collection time.")
        else:
            print(f"\n✅ Sufficient data collected ({stats['ticks_collected']} ticks)")
        
        return pipeline
    
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_features(pipeline):
    """Test feature extraction."""
    print("\n" + "="*60)
    print("TEST 3: Feature Extraction")
    print("="*60)
    
    try:
        # Microstructure features
        micro = MicrostructureFeatures(pipeline)
        micro_features = micro.compute()
        
        print(f"✅ Microstructure features: {micro_features.shape}")
        micro_dict = micro.compute_dict()
        print("\nTop 5 microstructure features:")
        for i, (name, value) in enumerate(list(micro_dict.items())[:5]):
            print(f"   {name:25s}: {value:10.6f}")
        
        # Momentum features
        momentum = MomentumFeatures(pipeline)
        momentum_features = momentum.compute()
        
        print(f"\n✅ Momentum features: {momentum_features.shape}")
        momentum_dict = momentum.compute_dict()
        print("\nTop 5 momentum features:")
        for i, (name, value) in enumerate(list(momentum_dict.items())[:5]):
            print(f"   {name:25s}: {value:10.6f}")
        
        return micro, momentum
    
    except Exception as e:
        print(f"❌ Feature extraction error: {e}")
        return None, None


def test_environment(pipeline, micro, momentum):
    """Test trading environment."""
    print("\n" + "="*60)
    print("TEST 4: Trading Environment")
    print("="*60)
    
    try:
        env = IntradayTradingEnv(
            pipeline=pipeline,
            microstructure=micro,
            momentum=momentum,
            initial_capital=25000.0,
            max_position=500,
            max_daily_loss=500.0,
            max_trades_per_day=30,
        )
        
        print(f"✅ Created environment")
        print(f"   Observation space: {env.observation_space.shape}")
        print(f"   Action space: {env.action_space.n} actions")
        print(f"   Initial capital: ${env.initial_capital:.2f}")
        
        # Reset
        obs, info = env.reset()
        print(f"\n✅ Environment reset")
        print(f"   Observation shape: {obs.shape}")
        print(f"   Capital: ${info['capital']:.2f}")
        
        return env
    
    except Exception as e:
        print(f"❌ Environment error: {e}")
        return None


def test_random_episode(env, steps=20):
    """Run random episode."""
    print("\n" + "="*60)
    print(f"TEST 5: Random Agent Episode ({steps} steps)")
    print("="*60)
    
    try:
        obs, info = env.reset()
        total_reward = 0
        
        print(f"\nStarting episode...")
        print(f"{'Step':<6} {'Action':<15} {'Reward':<10} {'PnL':<10} {'Pos':<6} {'Trades':<7}")
        print("-" * 60)
        
        action_names = ['CLOSE', 'HOLD', 'SMALL', 'MED', 'LARGE']
        
        for step in range(steps):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            
            print(f"{step:<6} {action_names[action]:<15} {reward:<10.2f} "
                  f"${info['daily_pnl']:<9.2f} {info['position_qty']:<6} "
                  f"{info['daily_trades']:<7}")
            
            if terminated or truncated:
                print(f"\nEpisode ended: {'terminated' if terminated else 'truncated'}")
                break
        
        print("-" * 60)
        print(f"\n📊 Episode Summary:")
        print(f"   Total steps: {step + 1}")
        print(f"   Total reward: {total_reward:.2f}")
        print(f"   Final PnL: ${info['daily_pnl']:.2f}")
        print(f"   Total trades: {info['daily_trades']}")
        print(f"   Win streak: {info['current_win_streak']}")
        print(f"   Final capital: ${info['capital']:.2f}")
        
        if info['daily_pnl'] > 0:
            print(f"\n✅ Profitable episode! (+${info['daily_pnl']:.2f})")
        else:
            print(f"\n📉 Losing episode (${info['daily_pnl']:.2f})")
        
        return True
    
    except Exception as e:
        print(f"❌ Episode error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 INTRADAY TRADING SYSTEM - INTEGRATION TEST")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nNOTE: This test can run WITHOUT IBKR connection!")
    print("      It will use simulated data if IBKR is unavailable.")
    
    # Test 1: IBKR connection (optional)
    ib = test_ibkr_connection(required=False)
    
    try:
        # Test 2: Data pipeline (simulated if no IBKR)
        pipeline = test_data_pipeline(ib, symbol='SPY', duration=30)  # Reduced to 30s
        if not pipeline:
            print("\n❌ Tests failed: Data pipeline error")
            return False
        
        # Test 3: Features
        micro, momentum = test_features(pipeline)
        if not micro or not momentum:
            print("\n❌ Tests failed: Feature extraction error")
            return False
        
        # Test 4: Environment
        env = test_environment(pipeline, micro, momentum)
        if not env:
            print("\n❌ Tests failed: Environment creation error")
            return False
        
        # Test 5: Random episode
        success = test_random_episode(env, steps=20)
        if not success:
            print("\n❌ Tests failed: Episode execution error")
            return False
        
        # All tests passed!
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\n🎉 Intraday trading system is ready!")
        print("\nNext steps:")
        print("  1. Train PPO agent: python scripts/train_intraday_ppo.py")
        print("  2. Or run live trader: python scripts/live_intraday_trader.py")
        print("  3. See INTRADAY_QUICKSTART.md for full guide")
        
        return True
    
    finally:
        # Cleanup
        try:
            if 'pipeline' in locals():
                pipeline.stop()
            if ib:
                ib.disconnect()
            print("\n🧹 Cleaned up connections")
        except Exception:
            pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
