"""Demonstration of Phase 12 Compliance Monitoring Framework.

This script demonstrates how to:
1. Configure compliance policies
2. Run period-based compliance analysis
3. Check individual signals
4. Integrate with anomaly detection
5. Generate compliance reports

Usage:
    python scripts/demo_compliance_monitoring.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import logging

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from autotrader.audit import (
    EventType,
    get_audit_trail,
)
from autotrader.monitoring.compliance import (
    ComplianceIssue,
    ComplianceMonitor,
    CompliancePolicy,
    ComplianceSeverity,
)
from autotrader.monitoring.anomaly import AnomalyDetector
from autotrader.alerts.router import AlertRouter, TelegramAdapter
from autotrader.alerts.config import load_alert_config


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def demo_basic_compliance_monitoring():
    """Demo 1: Basic compliance monitoring with default policy."""
    print("\n" + "=" * 80)
    print("DEMO 1: Basic Compliance Monitoring")
    print("=" * 80)

    # Initialize with default policy
    monitor = ComplianceMonitor()

    # Analyze recent activity (last 7 days)
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(days=7)

    print(f"\n📊 Analyzing compliance for period:")
    print(f"   Start: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"   End:   {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    try:
        report = monitor.analyze_period(start_time, end_time)

        print(f"\n✅ Compliance Report Generated:")
        print(f"   Total Issues: {report.totals['total']}")
        print(f"   - Critical: {report.totals[ComplianceSeverity.CRITICAL.value]}")
        print(f"   - Warning:  {report.totals[ComplianceSeverity.WARNING.value]}")
        print(f"   - Info:     {report.totals[ComplianceSeverity.INFO.value]}")

        if report.issues:
            print(f"\n⚠️  Top 5 Issues:")
            for idx, issue in enumerate(report.issues[:5], 1):
                print(f"\n   {idx}. [{issue.severity.value.upper()}] {issue.issue_code}")
                print(f"      {issue.description}")
                if issue.signal_id:
                    print(f"      Signal: {issue.signal_id}")

        print(f"\n📈 Audit Summary:")
        for key, value in report.audit_summary.items():
            print(f"   {key}: {value}")

    except ValueError as e:
        print(f"\n❌ Error: {e}")


def demo_strict_policy():
    """Demo 2: Strict compliance policy with custom thresholds."""
    print("\n" + "=" * 80)
    print("DEMO 2: Strict Compliance Policy")
    print("=" * 80)

    # Configure strict policy
    strict_policy = CompliancePolicy(
        require_risk_check=True,
        require_llm_review=True,  # Require LLM review for all signals
        max_risk_score=0.50,  # Lower threshold (default is 0.75)
        max_order_notional=100000.0,  # $100k limit per order
        forbidden_llm_decisions=(
            "override_limits",
            "proceed_despite_reject",
            "bypass_risk_check",
            "emergency_override",
        ),
    )

    print("\n🔒 Strict Policy Configuration:")
    print(f"   Require Risk Check: {strict_policy.require_risk_check}")
    print(f"   Require LLM Review: {strict_policy.require_llm_review}")
    print(f"   Max Risk Score: {strict_policy.max_risk_score}")
    print(f"   Max Order Notional: ${strict_policy.max_order_notional:,.2f}")
    print(
        f"   Forbidden LLM Decisions: {len(strict_policy.forbidden_llm_decisions)}"
    )

    monitor = ComplianceMonitor(policy=strict_policy)

    # Analyze recent activity
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(days=7)

    try:
        report = monitor.analyze_period(start_time, end_time)

        print(f"\n✅ Strict Compliance Report:")
        print(f"   Total Issues: {report.totals['total']}")
        print(f"   - Critical: {report.totals[ComplianceSeverity.CRITICAL.value]}")
        print(f"   - Warning:  {report.totals[ComplianceSeverity.WARNING.value]}")

        # Check if stricter policy found more issues
        print(
            f"\n💡 Note: Stricter policies typically find more issues due to lower thresholds"
        )

    except ValueError as e:
        print(f"\n❌ Error: {e}")


def demo_signal_specific_check():
    """Demo 3: Check compliance for a specific signal."""
    print("\n" + "=" * 80)
    print("DEMO 3: Signal-Specific Compliance Check")
    print("=" * 80)

    # Get recent signals from audit trail
    audit_trail = get_audit_trail()
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(days=30)

    signals = audit_trail.query_events(
        event_type=EventType.SIGNAL,
        start_time=start_time,
        end_time=end_time,
    )

    if not signals:
        print("\n⚠️  No signals found in the last 30 days")
        return

    # Check first signal
    signal_event = signals[0]
    signal_id = signal_event["data"]["signal_id"]

    print(f"\n🔍 Checking signal: {signal_id}")
    print(f"   Timestamp: {signal_event['timestamp']}")
    print(f"   Symbol: {signal_event['data'].get('symbol', 'N/A')}")
    print(f"   Action: {signal_event['data'].get('action', 'N/A')}")

    monitor = ComplianceMonitor()
    issues = monitor.check_signal(signal_id)

    if issues:
        print(f"\n⚠️  Found {len(issues)} compliance issues:")
        for issue in issues:
            print(f"\n   [{issue.severity.value.upper()}] {issue.issue_code}")
            print(f"   {issue.description}")
            if issue.metadata:
                print(f"   Metadata: {json.dumps(issue.metadata, indent=6)}")
    else:
        print(f"\n✅ No compliance issues found for this signal")


def demo_anomaly_integration():
    """Demo 4: Compliance monitoring with anomaly detection."""
    print("\n" + "=" * 80)
    print("DEMO 4: Compliance with Anomaly Detection")
    print("=" * 80)

    # Initialize anomaly detector
    anomaly_detector = AnomalyDetector()

    # Create monitor with anomaly detection
    monitor = ComplianceMonitor(anomaly_detector=anomaly_detector)

    # Analyze recent activity with metrics
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(days=7)

    # Mock metrics from realtime dashboard
    # In production, get these from RealtimeDashboardAggregator
    metrics = {
        "sharpe_ratio": 0.015,
        "win_rate": 0.52,
        "avg_latency_ms": 250,
        "max_drawdown": 0.08,
        "profit_factor": 1.2,
        "position_count": 5,
        "total_pnl": 1250.50,
        "risk_limit_utilization": 0.45,
    }

    print(f"\n📊 Dashboard Metrics:")
    for key, value in metrics.items():
        print(f"   {key}: {value}")

    try:
        report = monitor.analyze_period(
            start_time, end_time, metrics=metrics
        )

        print(f"\n✅ Compliance Report with Anomalies:")
        print(f"   Compliance Issues: {report.totals['total']}")
        print(f"   Anomalies Detected: {len(report.anomalies)}")

        if report.anomalies:
            print(f"\n🚨 Detected Anomalies:")
            for idx, anomaly in enumerate(report.anomalies[:5], 1):
                print(f"\n   {idx}. [{anomaly.severity.value.upper()}] {anomaly.anomaly_type}")
                print(f"      Metric: {anomaly.metric_name}")
                print(f"      Value: {anomaly.value:.4f}")
                print(f"      Deviation Score: {anomaly.deviation_score:.2f}")
                if anomaly.description:
                    print(f"      {anomaly.description}")

    except ValueError as e:
        print(f"\n❌ Error: {e}")


def demo_report_export():
    """Demo 5: Export compliance report to JSON."""
    print("\n" + "=" * 80)
    print("DEMO 5: Export Compliance Report")
    print("=" * 80)

    monitor = ComplianceMonitor()

    # Analyze recent activity
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(days=7)

    try:
        report = monitor.analyze_period(start_time, end_time)

        # Export to dict
        report_dict = report.to_dict()

        print(f"\n📄 Compliance Report JSON:")
        print(json.dumps(report_dict, indent=2))

        # Save to file
        output_file = "compliance_report.json"
        with open(output_file, "w") as f:
            json.dump(report_dict, f, indent=2)

        print(f"\n✅ Report saved to: {output_file}")

    except ValueError as e:
        print(f"\n❌ Error: {e}")


def demo_custom_issue_handling():
    """Demo 6: Custom issue handling and routing."""
    print("\n" + "=" * 80)
    print("DEMO 6: Custom Issue Handling")
    print("=" * 80)

    # Initialize Telegram alert router
    try:
        config = load_alert_config()
        if config.telegram and config.telegram.enabled:
            telegram = TelegramAdapter(
                bot_token=config.telegram.bot_token,
                chat_id=config.telegram.chat_id
            )
            alert_router = AlertRouter(telegram=telegram)
            alerts_enabled = True
            print("\n✅ Telegram alerts enabled")
        else:
            alert_router = None
            alerts_enabled = False
            print("\n⚠️  Telegram alerts disabled (not configured)")
    except Exception as e:
        logger.warning(f"Failed to initialize alerts: {e}")
        alert_router = None
        alerts_enabled = False

    def route_alert(issue: ComplianceIssue) -> None:
        """Route alerts based on severity."""
        if issue.severity == ComplianceSeverity.CRITICAL:
            print(f"   🚨 CRITICAL ALERT → Telegram")
            print(f"      {issue.issue_code}: {issue.description}")
        elif issue.severity == ComplianceSeverity.WARNING:
            print(f"   ⚠️  WARNING → Telegram")
            print(f"      {issue.issue_code}: {issue.description}")
        else:
            print(f"   ℹ️  INFO → Telegram")
            print(f"      {issue.issue_code}: {issue.description}")
        
        # Actually send to Telegram if configured
        if alerts_enabled and alert_router:
            try:
                success = alert_router.route_alert(issue)
                if success:
                    print(f"      ✅ Alert sent to Telegram")
                else:
                    print(f"      ❌ Failed to send alert")
            except Exception as e:
                print(f"      ❌ Error sending alert: {e}")

    monitor = ComplianceMonitor()

    # Analyze recent activity
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(days=7)

    try:
        report = monitor.analyze_period(start_time, end_time)

        print(f"\n📧 Routing {len(report.issues)} alerts:")
        for issue in report.issues:
            route_alert(issue)

    except ValueError as e:
        print(f"\n❌ Error: {e}")


def main():
    """Run all compliance monitoring demonstrations."""
    print("\n" + "=" * 80)
    print("Phase 12 Compliance Monitoring Framework - Demonstration")
    print("=" * 80)

    demos = [
        demo_basic_compliance_monitoring,
        demo_strict_policy,
        demo_signal_specific_check,
        demo_anomaly_integration,
        demo_report_export,
        demo_custom_issue_handling,
    ]

    for demo in demos:
        try:
            demo()
        except Exception as e:
            logger.exception(f"Demo {demo.__name__} failed: {e}")

    print("\n" + "=" * 80)
    print("All demonstrations complete!")
    print("=" * 80)
    print("\n📚 Next Steps:")
    print("   1. Configure CompliancePolicy for your requirements")
    print("   2. Integrate with realtime dashboard for metrics")
    print("   3. Set up alert routing (PagerDuty, Slack, email)")
    print("   4. Schedule periodic compliance reports")
    print("   5. Review PHASE_12_IMPLEMENTATION_GUIDE.md for details")
    print()


if __name__ == "__main__":
    main()
