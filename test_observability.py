"""Test script to validate observability infrastructure."""

import sys
import time

def test_imports():
    """Test that all observability modules can be imported."""
    print("Testing imports...")
    
    try:
        from src.core.logging_config import init_logging, get_logger
        print("✓ Logging module imported")
    except ImportError as e:
        print(f"✗ Failed to import logging module: {e}")
        return False
    
    try:
        from src.core.metrics import (
            record_scan_request,
            record_gem_score,
            is_prometheus_available
        )
        print(f"✓ Metrics module imported (Prometheus available: {is_prometheus_available()})")
    except ImportError as e:
        print(f"✗ Failed to import metrics module: {e}")
        return False
    
    try:
        from src.core.tracing import setup_tracing, is_tracing_available
        print(f"✓ Tracing module imported (OpenTelemetry available: {is_tracing_available()})")
    except ImportError as e:
        print(f"✗ Failed to import tracing module: {e}")
        return False
    
    return True


def test_logging():
    """Test structured logging."""
    print("\nTesting structured logging...")
    
    try:
        from src.core.logging_config import init_logging, get_logger
        
        # Initialize logging
        logger = init_logging(service_name="test", level="INFO")
        
        # Test various log levels
        logger.info("test_log", message="This is a test", value=42)
        logger.bind(request_id="test-123").warning("test_warning", code="WARN001")
        
        print("✓ Structured logging works")
        return True
    except Exception as e:
        print(f"✗ Logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_metrics():
    """Test metrics recording."""
    print("\nTesting metrics...")
    
    try:
        from src.core.metrics import (
            record_scan_request,
            record_scan_duration,
            record_gem_score,
            is_prometheus_available
        )
        
        # Record test metrics
        record_scan_request("TEST", "success")
        record_scan_duration("TEST", 1.23, "success")
        record_gem_score("TEST", 85.5)
        
        print(f"✓ Metrics recording works (Prometheus: {is_prometheus_available()})")
        return True
    except Exception as e:
        print(f"✗ Metrics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tracing():
    """Test distributed tracing."""
    print("\nTesting tracing...")
    
    try:
        from src.core.tracing import (
            setup_tracing,
            trace_operation,
            is_tracing_available
        )
        
        # Setup tracing
        tracer = setup_tracing(service_name="test")
        
        # Test trace operation
        with trace_operation("test_operation", attributes={"test": "value"}):
            time.sleep(0.1)
        
        print(f"✓ Tracing works (OpenTelemetry: {is_tracing_available()})")
        return True
    except Exception as e:
        print(f"✗ Tracing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Observability Infrastructure Validation")
    print("=" * 60)
    
    results = {
        "imports": test_imports(),
        "logging": test_logging(),
        "metrics": test_metrics(),
        "tracing": test_tracing(),
    }
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:20s}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
