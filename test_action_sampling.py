"""
Quick test to see what actions the agent is sampling during training.
"""
import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from gymnasium import spaces

# Create a dummy action space
action_space = spaces.Discrete(3)

# Test random sampling
print("Testing random action sampling (1000 samples):")
actions = [action_space.sample() for _ in range(1000)]
action_counts = {0: 0, 1: 0, 2: 0}
for a in actions:
    action_counts[a] += 1

print(f"  Action 0 (FLAT): {action_counts[0]/10:.1f}%")
print(f"  Action 1 (LONG): {action_counts[1]/10:.1f}%")
print(f"  Action 2 (SHORT): {action_counts[2]/10:.1f}%")
print()

# The PPO policy should also explore evenly with high entropy
print("Expected behavior:")
print("  - With entropy_coef=0.01, agent should explore all 3 actions")
print("  - Early training should show ~33% distribution across actions")
print("  - If seeing 100% FLAT, the policy is not exploring properly")
