"""Quick system validation after fresh install."""

import sys


def test_imports():
    """Test all critical imports."""
    print("Testing core dependencies...")
    
    try:
        import fastapi
        import numpy
        import pandas
        import sklearn
        print(f"✅ FastAPI {fastapi.__version__}")
        print(f"✅ NumPy {numpy.__version__}")
        print(f"✅ Pandas {pandas.__version__}")
        print(f"✅ scikit-learn {sklearn.__version__}")
    except ImportError as e:
        print(f"❌ Core dependency failed: {e}")
        return False
    
    print("\nTesting VoidBloom modules...")
    
    try:
        from src.core.feature_store import FeatureStore
        from src.services.feature_engineering import FeatureEngineeringPipeline
        print("✅ Feature Store modules")
    except ImportError as e:
        print(f"❌ Feature Store failed: {e}")
        return False
    
    try:
        from src.services.reliability import SLA_REGISTRY, CIRCUIT_REGISTRY
        from src.services.sla_monitor import SLAMonitor
        from src.services.circuit_breaker import CircuitBreaker
        print("✅ Reliability modules")
    except ImportError as e:
        print(f"❌ Reliability modules failed: {e}")
        return False
    
    try:
        from src.api.dashboard_api import app
        print("✅ Dashboard API")
    except ImportError as e:
        print(f"❌ Dashboard API failed: {e}")
        return False
    
    return True


def test_feature_store():
    """Test basic feature store operations."""
    print("\nTesting Feature Store operations...")
    
    try:
        from src.core.feature_store import FeatureStore, FeatureCategory, FeatureType, FeatureMetadata
        
        store = FeatureStore()
        
        # Register a feature - must pass FeatureMetadata object
        metadata = FeatureMetadata(
            name="test_score",
            feature_type=FeatureType.NUMERIC,
            category=FeatureCategory.SCORING,
            description="Test score"
        )
        store.register_feature(metadata)
        
        # Write a value - correct parameter order: feature_name, value, token_symbol
        store.write_feature("test_score", 85.5, "TEST_TOKEN", confidence=0.9)
        
        # Read it back
        value = store.read_feature("test_score", "TEST_TOKEN")
        
        if value and value.value == 85.5:
            print("✅ Feature Store read/write works")
            return True
        else:
            print("❌ Feature Store returned unexpected value")
            return False
            
    except Exception as e:
        print(f"❌ Feature Store test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sla_monitor():
    """Test SLA monitoring."""
    print("\nTesting SLA Monitor...")
    
    try:
        from src.services.sla_monitor import SLAMonitor, SLAThresholds
        
        monitor = SLAMonitor("test_source")
        monitor.record_request(latency_ms=150.0, success=True)  # Fixed: use record_request
        
        metrics = monitor.get_metrics()
        
        if metrics.latency_p50 > 0:
            print("✅ SLA Monitor works")
            return True
        else:
            print("❌ SLA Monitor returned unexpected metrics")
            return False
            
    except Exception as e:
        print(f"❌ SLA Monitor test failed: {e}")
        return False


def test_circuit_breaker():
    """Test circuit breaker."""
    print("\nTesting Circuit Breaker...")
    
    try:
        from src.services.circuit_breaker import CircuitBreaker, CircuitState  # Fixed: use CircuitState
        
        breaker = CircuitBreaker("test_breaker")
        
        # Should start CLOSED
        if breaker.state == CircuitState.CLOSED:
            print("✅ Circuit Breaker works")
            return True
        else:
            print("❌ Circuit Breaker unexpected state")
            return False
            
    except Exception as e:
        print(f"❌ Circuit Breaker test failed: {e}")
        return False


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("VoidBloom System Validation")
    print("=" * 60)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("Feature Store", test_feature_store),
        ("SLA Monitor", test_sla_monitor),
        ("Circuit Breaker", test_circuit_breaker),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} crashed: {e}")
            results.append((name, False))
        print()
    
    print("=" * 60)
    print("Validation Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:20s} {status}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All systems operational! Ready for production.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
