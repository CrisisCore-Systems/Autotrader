#!/usr/bin/env python3
"""Example demonstrating observability features in Autotrader.

This script shows how to use structured logging, metrics, and tracing
in your application code.
"""

import time
import random
from typing import Dict, Any

from src.core.logging_config import setup_structured_logging, get_logger, LogContext
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_gem_score,
    record_confidence_score,
    record_data_source_request,
    record_data_source_latency,
    is_prometheus_available,
)
from src.core.tracing import setup_tracing, trace_operation, add_span_attributes


def simulate_data_fetch(source: str, endpoint: str) -> Dict[str, Any]:
    """Simulate fetching data from an external source."""
    logger = get_logger(__name__)
    
    with trace_operation(
        f"{source}_fetch",
        attributes={"source": source, "endpoint": endpoint}
    ):
        start_time = time.time()
        
        logger.info(
            "data_fetch_started",
            source=source,
            endpoint=endpoint,
        )
        
        # Simulate API call with random latency
        latency = random.uniform(0.1, 0.5)
        time.sleep(latency)
        
        # Simulate occasional errors
        if random.random() < 0.1:  # 10% error rate
            duration = time.time() - start_time
            record_data_source_request(source, endpoint, "error")
            record_data_source_latency(source, endpoint, duration)
            
            logger.error(
                "data_fetch_failed",
                source=source,
                endpoint=endpoint,
                duration_seconds=duration,
            )
            raise RuntimeError(f"Failed to fetch from {source}")
        
        # Success case
        duration = time.time() - start_time
        record_data_source_request(source, endpoint, "success")
        record_data_source_latency(source, endpoint, duration)
        
        data = {
            "prices": [100, 101, 102],
            "volume": 1000000,
            "timestamp": time.time(),
        }
        
        add_span_attributes(data_points=len(data["prices"]))
        
        logger.info(
            "data_fetch_completed",
            source=source,
            endpoint=endpoint,
            duration_seconds=duration,
            data_points=len(data["prices"]),
        )
        
        return data


def simulate_token_scan(token_symbol: str) -> Dict[str, Any]:
    """Simulate scanning a token."""
    logger = get_logger(__name__)
    
    with trace_operation(
        "token_scan",
        attributes={"token_symbol": token_symbol}
    ):
        start_time = time.time()
        
        # Use context binding for the scan
        scan_logger = logger.bind(token_symbol=token_symbol)
        
        scan_logger.info("scan_started")
        
        try:
            # Fetch data from multiple sources
            market_data = simulate_data_fetch("coingecko", "/api/v3/coins/market_chart")
            protocol_data = simulate_data_fetch("defillama", "/protocol/info")
            
            # Simulate score calculation
            time.sleep(0.2)
            gem_score = random.uniform(60, 95)
            confidence = random.uniform(70, 99)
            
            # Record metrics
            duration = time.time() - start_time
            record_scan_request(token_symbol, "success")
            record_scan_duration(token_symbol, duration, "success")
            record_gem_score(token_symbol, gem_score)
            record_confidence_score(token_symbol, confidence / 100)
            
            # Add span attributes
            add_span_attributes(
                gem_score=gem_score,
                confidence=confidence,
                duration_seconds=duration,
            )
            
            scan_logger.info(
                "scan_completed",
                gem_score=gem_score,
                confidence=confidence,
                duration_seconds=duration,
            )
            
            return {
                "token_symbol": token_symbol,
                "gem_score": gem_score,
                "confidence": confidence,
                "market_data": market_data,
                "protocol_data": protocol_data,
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_type = type(e).__name__
            
            record_scan_request(token_symbol, "failure")
            record_scan_duration(token_symbol, duration, "failure")
            
            scan_logger.error(
                "scan_failed",
                error_type=error_type,
                error_message=str(e),
                duration_seconds=duration,
                exc_info=True,
            )
            raise


def main():
    """Main example function."""
    # Initialize observability
    print("Initializing observability...")
    logger = setup_structured_logging(
        service_name="observability-example",
        environment="development",
        level="INFO",
        enable_json=True,
    )
    
    setup_tracing(
        service_name="observability-example",
        enable_console_export=True,
    )
    
    print(f"Prometheus metrics available: {is_prometheus_available()}")
    print()
    
    # Example 1: Simple logging
    print("=" * 60)
    print("Example 1: Simple structured logging")
    print("=" * 60)
    logger.info("application_started", version="1.0.0")
    logger.debug("debug_message", component="main", details="This is a debug message")
    logger.warning("example_warning", reason="demonstration")
    print()
    
    # Example 2: Context binding
    print("=" * 60)
    print("Example 2: Context binding")
    print("=" * 60)
    user_logger = logger.bind(user_id="user-123", session_id="session-456")
    user_logger.info("user_action", action="login")
    user_logger.info("user_action", action="view_dashboard")
    print()
    
    # Example 3: Context manager
    print("=" * 60)
    print("Example 3: Context manager")
    print("=" * 60)
    with LogContext(logger, request_id="req-789") as request_logger:
        request_logger.info("processing_request", endpoint="/api/scan")
        time.sleep(0.1)
        request_logger.info("request_completed", status_code=200)
    print()
    
    # Example 4: Token scanning with full observability
    print("=" * 60)
    print("Example 4: Token scanning with observability")
    print("=" * 60)
    
    tokens = ["ETH", "BTC", "SOL", "MATIC", "AVAX"]
    
    for token in tokens:
        print(f"\nScanning {token}...")
        try:
            result = simulate_token_scan(token)
            print(f"✓ {token}: GemScore={result['gem_score']:.2f}, "
                  f"Confidence={result['confidence']:.2f}%")
        except Exception as e:
            print(f"✗ {token}: Failed - {e}")
        
        # Small delay between scans
        time.sleep(0.5)
    
    print()
    print("=" * 60)
    print("Example completed!")
    print("=" * 60)
    print()
    print("To view metrics, start the metrics server:")
    print("  python -m src.services.metrics_server --port 9090")
    print("Then visit: http://localhost:9090/metrics")
    print()
    print("Check the console output above for structured JSON logs and traces.")


if __name__ == "__main__":
    main()
