#!/usr/bin/env python3
"""
Example: Fully Monitored Token Scan

Demonstrates comprehensive logging, metrics, and tracing instrumentation
for the AutoTrader Hidden Gem Scanner.

Usage:
    python example_monitored_scan.py
    python example_monitored_scan.py --token BTC --debug
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

import pandas as pd

# Observability imports
from src.core.logging_config import init_logging, get_logger, LogContext
from src.core.metrics import (
    record_scan_request,
    record_scan_duration,
    record_scan_error,
    record_gem_score,
    record_confidence_score,
    record_flagged_token,
    record_data_source_request,
    record_data_source_latency,
    is_prometheus_available,
)
from src.core.tracing import (
    setup_tracing,
    trace_operation,
    add_span_attributes,
    add_span_event,
    get_trace_id,
    is_tracing_available,
)

# Application imports
from src.core.features import MarketSnapshot
from src.core.safety import evaluate_contract
from src.core.provenance_tracking import complete_pipeline_tracked


def create_synthetic_data(token: str) -> tuple:
    """Create synthetic market data for demonstration.
    
    Args:
        token: Token symbol
        
    Returns:
        Tuple of (snapshot, prices, contract_report)
    """
    logger = get_logger(__name__)
    
    with trace_operation("create_synthetic_data", attributes={"token": token}):
        logger.info("generating_synthetic_data", token=token)
        
        # Generate price series
        now = datetime.utcnow()
        dates = [now - timedelta(hours=i) for i in range(48)][::-1]
        prices = pd.Series(
            data=[0.03 + 0.0002 * i for i in range(48)],
            index=pd.to_datetime(dates)
        )
        
        # Create market snapshot
        snapshot = MarketSnapshot(
            symbol=token,
            timestamp=now,
            price=float(prices.iloc[-1]),
            volume_24h=250000,
            liquidity_usd=180000,
            holders=4200,
            onchain_metrics={
                "active_wallets": 950,
                "net_inflows": 125000,
                "unlock_pressure": 0.2
            },
            narratives=["AI", "DeFi", "Demo"]
        )
        
        # Create contract safety report
        contract_report = evaluate_contract(
            {
                "honeypot": False,
                "owner_can_mint": False,
                "owner_can_withdraw": False,
                "unverified": False
            },
            severity="none"
        )
        
        add_span_attributes(
            price_points=len(prices),
            snapshot_created=True,
            contract_score=contract_report.score,
        )
        
        logger.info(
            "synthetic_data_created",
            token=token,
            price_points=len(prices),
            current_price=snapshot.price,
            liquidity=snapshot.liquidity_usd,
            contract_score=contract_report.score,
        )
        
        return snapshot, prices, contract_report


def scan_token_monitored(
    token: str,
    snapshot: MarketSnapshot,
    prices: pd.Series,
    contract_report: Any,
) -> Dict[str, Any]:
    """Execute monitored token scan with full observability.
    
    Args:
        token: Token symbol
        snapshot: Market snapshot
        prices: Price series
        contract_report: Contract safety report
        
    Returns:
        Scan results dictionary
    """
    logger = get_logger(__name__)
    start_time = time.time()
    
    # Bind context for all logs in this function
    with LogContext(logger, token=token, trace_id=get_trace_id()) as log:
        log.info("scan_started", operation="complete_pipeline")
        
        try:
            # Execute pipeline with tracing
            with trace_operation(
                "complete_pipeline_tracked",
                attributes={
                    "token": token,
                    "data_source": "synthetic_demo",
                    "price_points": len(prices),
                }
            ):
                # Add event markers
                add_span_event("pipeline_phase", {"phase": "initialization"})
                
                # Execute pipeline
                results = complete_pipeline_tracked(
                    snapshot=snapshot,
                    price_series=prices,
                    narrative_embedding_score=0.72,
                    contract_report=contract_report,
                    data_source="synthetic_demo"
                )
                
                add_span_event("pipeline_phase", {"phase": "completed"})
                
                # Calculate duration
                duration_seconds = time.time() - start_time
                
                # Extract results
                gem_score = results['result'].score
                confidence = results['result'].confidence
                flagged = results['flagged']
                
                # Record success metrics
                record_scan_request(token, "success")
                record_scan_duration(token, duration_seconds, "success")
                record_gem_score(token, gem_score)
                record_confidence_score(token, confidence / 100)
                
                if flagged:
                    record_flagged_token(token, "manual_review_required")
                
                # Add span attributes for tracing
                add_span_attributes(
                    gem_score=gem_score,
                    confidence=confidence,
                    flagged=flagged,
                    duration_seconds=duration_seconds,
                )
                
                # Log success with full context
                log.info(
                    "scan_completed",
                    gem_score=gem_score,
                    confidence=confidence,
                    flagged=flagged,
                    duration_seconds=duration_seconds,
                    top_features=[
                        k for k, v in sorted(
                            results['result'].contributions.items(),
                            key=lambda x: -x[1]
                        )[:3]
                    ],
                )
                
                return {
                    "status": "success",
                    "token": token,
                    "gem_score": gem_score,
                    "confidence": confidence,
                    "flagged": flagged,
                    "duration_seconds": duration_seconds,
                    "results": results,
                }
                
        except Exception as e:
            # Calculate duration even on failure
            duration_seconds = time.time() - start_time
            
            # Record failure metrics
            record_scan_request(token, "failure")
            record_scan_duration(token, duration_seconds, "failure")
            record_scan_error(token, type(e).__name__)
            
            # Log error with full context
            log.error(
                "scan_failed",
                error_type=type(e).__name__,
                error_message=str(e),
                duration_seconds=duration_seconds,
            )
            
            # Re-raise for caller to handle
            raise


def process_batch(tokens: List[str]) -> Dict[str, Any]:
    """Process multiple tokens with batch-level monitoring.
    
    Args:
        tokens: List of token symbols to scan
        
    Returns:
        Dictionary of results per token
    """
    logger = get_logger(__name__)
    batch_start = time.time()
    
    logger.info(
        "batch_processing_started",
        batch_size=len(tokens),
        tokens=tokens,
    )
    
    results = {}
    success_count = 0
    error_count = 0
    
    with trace_operation("batch_processing", attributes={"batch_size": len(tokens)}):
        for idx, token in enumerate(tokens, 1):
            add_span_event("batch_item_started", {"token": token, "index": idx})
            
            try:
                # Generate data
                snapshot, prices, contract_report = create_synthetic_data(token)
                
                # Scan token
                result = scan_token_monitored(
                    token=token,
                    snapshot=snapshot,
                    prices=prices,
                    contract_report=contract_report,
                )
                
                results[token] = result
                success_count += 1
                
                add_span_event("batch_item_completed", {"token": token, "status": "success"})
                
            except Exception as e:
                error_count += 1
                results[token] = {
                    "status": "error",
                    "token": token,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
                
                add_span_event("batch_item_failed", {"token": token, "error": str(e)})
        
        batch_duration = time.time() - batch_start
        
        # Log batch summary
        logger.info(
            "batch_processing_completed",
            batch_size=len(tokens),
            success_count=success_count,
            error_count=error_count,
            batch_duration_seconds=batch_duration,
            avg_duration_per_token=batch_duration / len(tokens),
            success_rate=success_count / len(tokens),
        )
        
        add_span_attributes(
            success_count=success_count,
            error_count=error_count,
            batch_duration_seconds=batch_duration,
        )
    
    return results


def print_results(results: Dict[str, Any]) -> None:
    """Print formatted results.
    
    Args:
        results: Results dictionary from scan or batch
    """
    print("\n" + "=" * 80)
    print("📊 SCAN RESULTS")
    print("=" * 80)
    
    if "batch_size" in results:
        # Batch results
        for token, result in results.items():
            print(f"\n🪙 {token}:")
            if result["status"] == "success":
                print(f"   ✅ Status: Success")
                print(f"   💎 GemScore: {result['gem_score']:.2f}")
                print(f"   🎯 Confidence: {result['confidence']:.2f}%")
                print(f"   🚩 Flagged: {result['flagged']}")
                print(f"   ⏱️  Duration: {result['duration_seconds']:.3f}s")
            else:
                print(f"   ❌ Status: Error")
                print(f"   🐛 Error: {result['error']}")
    else:
        # Single result
        print(f"\n🪙 Token: {results['token']}")
        print(f"💎 GemScore: {results['gem_score']:.2f}")
        print(f"🎯 Confidence: {results['confidence']:.2f}%")
        print(f"🚩 Flagged: {results['flagged']}")
        print(f"⏱️  Duration: {results['duration_seconds']:.3f}s")
        print(f"🔍 Trace ID: {get_trace_id() or 'N/A'}")


def print_observability_status() -> None:
    """Print observability stack status."""
    print("\n" + "=" * 80)
    print("🔍 OBSERVABILITY STATUS")
    print("=" * 80)
    print(f"📝 Structured Logging: ✅ Enabled (JSON format)")
    print(f"📊 Prometheus Metrics: {'✅ Enabled' if is_prometheus_available() else '⚠️  Disabled (graceful fallback)'}")
    print(f"🔍 Distributed Tracing: {'✅ Enabled' if is_tracing_available() else '⚠️  Disabled (graceful fallback)'}")
    
    if is_prometheus_available():
        print(f"\n💡 View metrics: curl http://localhost:9090/metrics")
        print(f"💡 Start server: python -m src.services.metrics_server --port 9090")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitored Token Scanner Example",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python example_monitored_scan.py
  python example_monitored_scan.py --token BTC
  python example_monitored_scan.py --batch TOKEN1 TOKEN2 TOKEN3
  python example_monitored_scan.py --debug
        """
    )
    
    parser.add_argument(
        "--token",
        type=str,
        default="DEMO",
        help="Token symbol to scan (default: DEMO)",
    )
    
    parser.add_argument(
        "--batch",
        nargs="+",
        help="Process multiple tokens in batch mode",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    # Initialize observability
    log_level = "DEBUG" if args.debug else "INFO"
    logger = init_logging(service_name="monitored-scanner", level=log_level)
    setup_tracing(service_name="monitored-scanner", enable_console_export=False)
    
    logger.info(
        "application_started",
        mode="batch" if args.batch else "single",
        tokens=args.batch if args.batch else [args.token],
    )
    
    # Print status
    print("=" * 80)
    print("🚀 MONITORED TOKEN SCANNER")
    print("=" * 80)
    print_observability_status()
    
    try:
        if args.batch:
            # Batch mode
            print(f"\n📦 Processing batch: {', '.join(args.batch)}")
            results = process_batch(args.batch)
            print_results(results)
        else:
            # Single token mode
            print(f"\n🔍 Scanning token: {args.token}")
            
            # Generate data
            snapshot, prices, contract_report = create_synthetic_data(args.token)
            
            # Scan token
            result = scan_token_monitored(
                token=args.token,
                snapshot=snapshot,
                prices=prices,
                contract_report=contract_report,
            )
            
            print_results(result)
        
        logger.info("application_completed", status="success")
        
        print("\n" + "=" * 80)
        print("✅ SCAN COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"\n💡 All operations logged with trace ID: {get_trace_id() or 'N/A'}")
        print(f"💡 Metrics recorded for Prometheus scraping")
        
        return 0
        
    except Exception as e:
        logger.error(
            "application_failed",
            error_type=type(e).__name__,
            error_message=str(e),
        )
        
        print(f"\n❌ ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
