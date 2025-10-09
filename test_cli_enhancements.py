"""Test script to verify CLI enhancements installation and basic functionality.

Run this after installing the package to ensure everything works.
"""

import sys
from pathlib import Path


def test_imports():
    """Test that all CLI modules can be imported."""
    print("Testing imports...")
    
    try:
        from src.cli import config
        from src.cli import metrics
        from src.cli import runtime
        from src.cli import plugins
        from src.cli import deterministic
        from src.cli import exit_codes
        from src.cli import main
        print("✅ All CLI modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_config_loading():
    """Test config resolution."""
    print("\nTesting config resolution...")
    
    try:
        from src.cli.config import get_env_overrides, _parse_env_value
        
        # Test env value parsing
        assert _parse_env_value("true") == True
        assert _parse_env_value("false") == False
        assert _parse_env_value("42") == 42
        assert _parse_env_value("3.14") == 3.14
        assert _parse_env_value("hello") == "hello"
        
        # Test env overrides (won't find any but shouldn't crash)
        overrides = get_env_overrides("AUTOTRADER_")
        assert isinstance(overrides, dict)
        
        print("✅ Config resolution working")
        return True
    except Exception as e:
        print(f"❌ Config test failed: {e}")
        return False


def test_metrics():
    """Test metrics system."""
    print("\nTesting metrics system...")
    
    try:
        from src.cli.metrics import MetricsCollector, NullEmitter, Metric, MetricType
        
        # Create collector
        collector = MetricsCollector(NullEmitter())
        
        # Test counter
        collector.counter("test_counter", 1.0)
        
        # Test gauge
        collector.gauge("test_gauge", 42.0)
        
        # Test timer
        collector.timer("test_timer", 1.5)
        
        # Get summary
        summary = collector.get_summary()
        assert "counters" in summary
        assert "gauges" in summary
        
        print("✅ Metrics system working")
        return True
    except Exception as e:
        print(f"❌ Metrics test failed: {e}")
        return False


def test_deterministic():
    """Test deterministic mode."""
    print("\nTesting deterministic mode...")
    
    try:
        from src.cli.deterministic import enable_deterministic_mode
        
        # Enable deterministic mode
        results = enable_deterministic_mode(42)
        
        # Check Python random was seeded
        assert results['python'] == True
        
        print("✅ Deterministic mode working")
        return True
    except Exception as e:
        print(f"❌ Deterministic test failed: {e}")
        return False


def test_exit_codes():
    """Test exit code definitions."""
    print("\nTesting exit codes...")
    
    try:
        from src.cli.exit_codes import ExitCode, EXIT_CODE_DESCRIPTIONS
        
        # Test enum
        assert ExitCode.SUCCESS == 0
        assert ExitCode.CONFIG_ERROR == 10
        assert ExitCode.WATCHDOG_TIMEOUT == 24
        assert ExitCode.SIGINT == 130
        
        # Test descriptions
        assert ExitCode.SUCCESS in EXIT_CODE_DESCRIPTIONS
        assert len(EXIT_CODE_DESCRIPTIONS) > 10
        
        print("✅ Exit codes defined correctly")
        return True
    except Exception as e:
        print(f"❌ Exit code test failed: {e}")
        return False


def test_plugins():
    """Test plugin system."""
    print("\nTesting plugin system...")
    
    try:
        from src.cli.plugins import StrategyRegistry
        
        # Create registry
        registry = StrategyRegistry()
        
        # Discover plugins (may find none, but shouldn't crash)
        registry.discover()
        
        # List strategies
        strategies = registry.list_strategies()
        assert isinstance(strategies, list)
        
        print("✅ Plugin system working")
        return True
    except Exception as e:
        print(f"❌ Plugin test failed: {e}")
        return False


def test_runtime():
    """Test runtime utilities."""
    print("\nTesting runtime utilities...")
    
    try:
        from src.cli.runtime import Watchdog
        
        # Create watchdog (don't start it)
        watchdog = Watchdog(10.0)
        assert watchdog.max_duration == 10.0
        
        print("✅ Runtime utilities working")
        return True
    except Exception as e:
        print(f"❌ Runtime test failed: {e}")
        return False


def test_schema():
    """Test that output schema exists."""
    print("\nTesting output schema...")
    
    try:
        schema_path = Path("configs/output_schema.json")
        
        if not schema_path.exists():
            print(f"⚠️  Schema not found at {schema_path}")
            return False
        
        import json
        with schema_path.open() as f:
            schema = json.load(f)
        
        assert "$schema" in schema
        assert "properties" in schema
        
        print("✅ Output schema valid")
        return True
    except Exception as e:
        print(f"❌ Schema test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("CLI ENHANCEMENTS - INSTALLATION TEST")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Config", test_config_loading),
        ("Metrics", test_metrics),
        ("Deterministic", test_deterministic),
        ("Exit Codes", test_exit_codes),
        ("Plugins", test_plugins),
        ("Runtime", test_runtime),
        ("Schema", test_schema),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n✅ All tests passed! CLI enhancements are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
