"""Test unlock pressure calculation after fixes."""
import sys
from datetime import datetime, timezone, timedelta

from src.core.pipeline import HiddenGemScanner, UnlockEvent
from src.core.clients import CoinGeckoClient

# Test 1: Single unlock event
print("Test 1: Single unlock (10 days away, 10% supply)")
client = CoinGeckoClient()
scanner = HiddenGemScanner(coin_client=client)
unlocks = [UnlockEvent(date=datetime.now(timezone.utc) + timedelta(days=10), percent_supply=10.0)]
pressure, meta = scanner._compute_unlock_pressure(unlocks)
print(f"  Pressure: {pressure:.4f}")
print(f"  Upcoming risk: {meta['upcoming_unlock_risk']}")
print(f"  Next unlock days: {meta['next_unlock_days']}")
print(f"  Next unlock %: {meta['next_unlock_percent']:.1f}")
assert isinstance(pressure, float), "Pressure should be a float"
assert isinstance(meta, dict), "Metadata should be a dict"
print("  ✓ Test 1 passed\n")

# Test 2: Multiple unlock events
print("Test 2: Multiple unlocks")
unlocks = [
    UnlockEvent(date=datetime.now(timezone.utc) + timedelta(days=10), percent_supply=10.0),
    UnlockEvent(date=datetime.now(timezone.utc) + timedelta(days=60), percent_supply=5.0),
]
pressure, meta = scanner._compute_unlock_pressure(unlocks)
print(f"  Pressure: {pressure:.4f}")
print(f"  Upcoming risk: {meta['upcoming_unlock_risk']}")
print(f"  Next unlock days: {meta['next_unlock_days']}")
assert meta['next_unlock_days'] < 15, "Soonest unlock should be tracked"
print("  ✓ Test 2 passed\n")

# Test 3: No unlocks
print("Test 3: No unlocks")
pressure, meta = scanner._compute_unlock_pressure([])
print(f"  Pressure: {pressure:.4f}")
print(f"  Upcoming risk: {meta['upcoming_unlock_risk']}")
assert pressure == 0.0, "Pressure should be zero with no unlocks"
print("  ✓ Test 3 passed\n")

# Test 4: _derive_onchain_metrics integration
print("Test 4: Integration with _derive_onchain_metrics")
protocol_metrics = {
    "tvl": [{"totalLiquidityUSD": 100000.0}],
    "metrics": {"activeUsers": 500}
}
unlocks = [UnlockEvent(date=datetime.now(timezone.utc) + timedelta(days=20), percent_supply=8.0)]
result = scanner._derive_onchain_metrics(protocol_metrics, unlocks)
print(f"  Onchain metrics keys: {sorted(result.keys())}")
assert "unlock_pressure" in result, "unlock_pressure should be in metrics"
assert isinstance(result["unlock_pressure"], float), "unlock_pressure should be a float"
assert "upcoming_unlock_risk" in result, "upcoming_unlock_risk should be in metrics"
print(f"  Unlock pressure: {result['unlock_pressure']:.4f}")
print(f"  Upcoming unlock risk: {result['upcoming_unlock_risk']}")
print("  ✓ Test 4 passed\n")

client.close()
print("=" * 60)
print("ALL TESTS PASSED! ✓")
print("=" * 60)
