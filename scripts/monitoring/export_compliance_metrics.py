"""
Export compliance monitoring metrics to Prometheus.

This script starts a Prometheus metrics server that exports compliance
monitoring metrics for Grafana visualization.

Usage:
    python scripts/monitoring/export_compliance_metrics.py [--port 9090]
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

try:
    from prometheus_client import start_http_server, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    print("❌ Error: prometheus_client not installed")
    print("   Install with: pip install prometheus-client")
    exit(1)

from autotrader.monitoring.compliance.monitor import (
    ComplianceMonitor,
    CompliancePolicy,
)
from autotrader.audit.trail import get_audit_trail


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)


def update_metrics(monitor: ComplianceMonitor) -> Dict[str, Any]:
    """
    Run compliance analysis and update Prometheus metrics.
    
    Args:
        monitor: Compliance monitor instance
        
    Returns:
        Dict with analysis results
    """
    # Analyze last 24 hours
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    logger.info(f"Running compliance analysis: {start_time} → {end_time}")
    
    try:
        report = monitor.analyze_period(
            period_start=start_time,
            period_end=end_time
        )
        
        return {
            'total_issues': report.totals.get('total', 0),
            'critical': report.totals.get('critical', 0),
            'warning': report.totals.get('warning', 0),
            'info': report.totals.get('info', 0),
            'period_start': start_time.isoformat(),
            'period_end': end_time.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error updating metrics: {e}", exc_info=True)
        return {
            'error': str(e),
            'period_start': start_time.isoformat(),
            'period_end': end_time.isoformat()
        }


def main():
    parser = argparse.ArgumentParser(
        description='Export compliance monitoring metrics to Prometheus'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=9090,
        help='Prometheus metrics server port (default: 9090)'
    )
    parser.add_argument(
        '--update-interval',
        type=int,
        default=300,
        help='Metrics update interval in seconds (default: 300 = 5 minutes)'
    )
    parser.add_argument(
        '--policy',
        type=str,
        choices=['default', 'strict', 'permissive'],
        default='default',
        help='Compliance policy to use (default: default)'
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("Compliance Monitoring - Prometheus Metrics Exporter")
    print("=" * 80)
    print()
    print(f"📊 Configuration:")
    print(f"   Port: {args.port}")
    print(f"   Update Interval: {args.update_interval}s")
    print(f"   Policy: {args.policy}")
    print()
    
    # Initialize compliance monitor
    audit_trail = get_audit_trail()
    
    if args.policy == 'strict':
        policy = CompliancePolicy(
            require_risk_check=True,
            require_llm_review=True,
            max_risk_score=0.5,
            max_order_notional=100_000.0,
            forbidden_llm_decisions=['override_human', 'bypass_risk']
        )
    elif args.policy == 'permissive':
        policy = CompliancePolicy(
            require_risk_check=False,
            require_llm_review=False,
            max_risk_score=0.95,
            max_order_notional=1_000_000.0,
            forbidden_llm_decisions=[]
        )
    else:
        policy = CompliancePolicy()  # Default policy
    
    monitor = ComplianceMonitor(
        audit_trail=audit_trail,
        policy=policy
    )
    
    # Start Prometheus HTTP server
    try:
        start_http_server(args.port)
        print(f"✅ Prometheus metrics server started on port {args.port}")
        print(f"   Metrics endpoint: http://localhost:{args.port}/metrics")
        print()
        print("📈 Available metrics:")
        print("   - compliance_issues_total{severity, issue_code}")
        print("   - compliance_checks_total{check_type, status}")
        print("   - compliance_check_duration_seconds{check_type}")
        print("   - risk_check_failures_total{failure_type}")
        print("   - alert_delivery_total{channel, severity, status}")
        print("   - active_violations{severity}")
        print()
        print("🔄 Updating metrics every", args.update_interval, "seconds...")
        print("   Press Ctrl+C to stop")
        print()
        
    except OSError as e:
        print(f"❌ Error: Failed to start metrics server on port {args.port}")
        print(f"   {e}")
        print(f"   Try a different port with --port <PORT>")
        exit(1)
    
    # Continuous metrics update loop
    update_count = 0
    try:
        while True:
            update_count += 1
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Update #{update_count}")
            
            results = update_metrics(monitor)
            
            if 'error' not in results:
                print(f"   ✅ Analysis complete:")
                print(f"      Total Issues: {results['total_issues']}")
                print(f"      - Critical: {results['critical']}")
                print(f"      - Warning:  {results['warning']}")
                print(f"      - Info:     {results['info']}")
            else:
                print(f"   ❌ Error: {results['error']}")
            
            print()
            time.sleep(args.update_interval)
            
    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("🛑 Shutting down metrics exporter...")
        print(f"   Total updates: {update_count}")
        print("=" * 80)


if __name__ == '__main__':
    main()
