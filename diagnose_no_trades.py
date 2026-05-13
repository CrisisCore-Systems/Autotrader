"""
Diagnostic script to understand why agent isn't making trades.
"""
import logging
from ib_insync import IB
import time
import numpy as np

from src.intraday.enhanced_pipeline import EnhancedDataPipeline
from src.intraday.microstructure import MicrostructureFeatures
from src.intraday.momentum import MomentumFeatures
from src.intraday.trading_env import IntradayTradingEnv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to IBKR
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=99)

# Create pipeline
pipeline = EnhancedDataPipeline(
    ib=ib,
    symbol='SPY',
    mode='historical',
    duration='30 D',
)
pipeline.start()

print("⏳ Waiting for data (30 seconds)...")
time.sleep(30)

# Create feature engines
microstructure = MicrostructureFeatures(pipeline)
momentum = MomentumFeatures(pipeline)

# Create environment
env = IntradayTradingEnv(
    pipeline=pipeline,
    microstructure=microstructure,
    momentum=momentum,
)

print("\n" + "="*60)
print("DIAGNOSTIC TEST: Manual action execution")
print("="*60)

obs, info = env.reset()
print(f"\n📊 Initial state:")
print(f"  Capital: ${env.capital:.2f}")
print(f"  Position: {env.position_qty}")
print(f"  Price: ${env.current_price:.2f}")

# Test each action manually
for action in [1, 2, 0]:  # LONG, SHORT, FLAT
    action_names = {0: "FLAT", 1: "LONG", 2: "SHORT"}
    print(f"\n🎯 Testing action {action} ({action_names[action]})...")
    
    # Take 5 steps with this action
    for step in range(5):
        obs, reward, terminated, truncated, info = env.step(action)
        print(f"  Step {step+1}: reward={reward:.5f}, pos={info['position_qty']}, trades={info['daily_trades']}, pnl=${info['daily_pnl']:.2f}")
        
        if terminated or truncated:
            print(f"  Episode ended: {info.get('done_reason', 'unknown')}")
            obs, info = env.reset()
            break
    
    # Reset for next test
    obs, info = env.reset()

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
print("\n🔍 Analysis:")
print("  If trades=0 for all actions, check:")
print("    1. Quality filters blocking trades")
print("    2. Trade throttling too aggressive")
print("    3. Data pipeline issues")
print("\n  If trades>0, then PPO policy is the issue:")
print("    1. Entropy coefficient too low (not exploring)")
print("    2. Learning rate too high (converging to FLAT too fast)")
print("    3. Reward signal too weak (commissions dominating)")

# Cleanup
pipeline.stop()
ib.disconnect()
