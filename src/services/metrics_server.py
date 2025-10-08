"""Prometheus metrics server.

Exposes Prometheus metrics on a dedicated HTTP endpoint for scraping.
Runs separately from the main API to avoid mixing concerns.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

try:
    from prometheus_client import start_http_server, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    start_http_server = None  # type: ignore
    REGISTRY = None  # type: ignore

from src.core.logging_config import init_logging, get_logger


def start_metrics_server(
    port: int = 9090,
    addr: str = "0.0.0.0",
) -> None:
    """Start Prometheus metrics HTTP server.
    
    Args:
        port: Port to bind to
        addr: Address to bind to
        
    Raises:
        RuntimeError: If Prometheus client is not available
    """
    if not PROMETHEUS_AVAILABLE:
        raise RuntimeError(
            "prometheus_client not installed. "
            "Install with: pip install prometheus-client"
        )
    
    logger = get_logger(__name__)
    
    logger.info(
        "metrics_server_starting",
        port=port,
        address=addr,
    )
    
    try:
        start_http_server(port=port, addr=addr, registry=REGISTRY)
        
        logger.info(
            "metrics_server_started",
            port=port,
            address=addr,
            endpoint=f"http://{addr}:{port}/metrics",
        )
        
        # Keep server running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("metrics_server_shutdown", reason="keyboard_interrupt")
        sys.exit(0)
    except Exception as e:
        logger.error(
            "metrics_server_error",
            error_type=type(e).__name__,
            error_message=str(e),
            exc_info=True,
        )
        sys.exit(1)


def main() -> int:
    """Main entry point for metrics server CLI.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Prometheus metrics server for AutoTrader"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port to bind to (default: 9090)",
    )
    parser.add_argument(
        "--address",
        type=str,
        default="0.0.0.0",
        help="Address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)",
    )
    
    args = parser.parse_args()
    
    # Initialize logging
    init_logging(service_name="autotrader-metrics", level=args.log_level)
    
    # Start metrics server
    start_metrics_server(port=args.port, addr=args.address)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
