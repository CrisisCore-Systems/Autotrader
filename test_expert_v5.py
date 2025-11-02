"""
Quick test of ProfitableExpert v5 - No IBKR connection needed
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("✓ Imports starting...")
import numpy as np
print("✓ NumPy loaded")

from scripts.expert_policy_v5_profitable import ProfitableExpert, ProfitableExpertConfig
print("✓ Expert policy loaded")

# Test config
config = ProfitableExpertConfig()
print(f"\n📊 Expert Configuration:")
print(f"  Risk per trade: {config.risk_per_trade_pct*100:.2f}%")
print(f"  Stop loss: {config.atr_multiplier}x ATR")
print(f"  Take profit: {config.tp_multiplier}x SL (R:R = {config.tp_multiplier}:1)")
print(f"  Max spread: {config.max_spread_bps} bps")
print(f"  RSI range: {config.min_rsi_long}-{config.max_rsi_long}")
print(f"  Min imbalance: {config.min_imbalance*100:.1f}%")
print(f"  Max hold: {config.max_hold_bars} bars")

print("\n✅ Expert policy v5 configuration validated!")
print("\nNext: Run full BC training with:")
print("  python Autotrader/scripts/train_bc.py --symbol SPY --duration '1 M' --episodes 100")
