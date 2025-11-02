"""Quick test of expert policy v5 imports"""
import sys
from pathlib import Path

print("1. Adding path...")
sys.path.insert(0, str(Path(__file__).parent.parent))

print("2. Importing dataclasses...")
from dataclasses import dataclass

print("3. Importing numpy...")
import numpy as np

print("4. Importing typing...")
from typing import Dict, Tuple, Optional

print("5. Importing collections...")
from collections import deque

print("6. Importing logging...")
import logging

print("✓ All standard imports successful!")

print("\n7. Testing data pipeline import...")
try:
    from src.intraday.data_pipeline import IntradayDataPipeline
    print("✓ IntradayDataPipeline imported!")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n8. Testing microstructure import...")
try:
    from src.intraday.microstructure import MicrostructureFeatures
    print("✓ MicrostructureFeatures imported!")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n9. Testing momentum import...")
try:
    from src.intraday.momentum import MomentumFeatures
    print("✓ MomentumFeatures imported!")
except Exception as e:
    print(f"✗ Failed: {e}")

print("\n✅ All imports completed!")
