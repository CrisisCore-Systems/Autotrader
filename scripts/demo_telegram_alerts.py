"""
Demo script for Telegram alert routing with compliance monitoring.

This script demonstrates:
1. Generating compliance violations
2. Routing alerts to Telegram
3. Different severity levels (CRITICAL, WARNING, INFO)
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
from datetime import datetime, timezone
from autotrader.alerts.router import create_alert_router
from autotrader.alerts.config import load_alert_config
from autotrader.monitoring.compliance.monitor import (
    ComplianceMonitor,
    CompliancePolicy,
    ComplianceIssue,
    ComplianceSeverity
)
from autotrader.audit import get_audit_trail


def demo_basic_alerts():
    """Demo 1: Basic alert routing with different severities."""
    print("\n" + "="*80)
    print("Demo 1: Basic Telegram Alerts")
    print("="*80)
    
    # Load config from environment
    config = load_alert_config()
    
    if not config.telegram_bot_token or not config.telegram_chat_id:
        print("\n❌ Telegram not configured!")
        print("   Run: python scripts/setup_telegram_alerts.py")
        return
    
    # Create router
    router = create_alert_router(
        telegram_bot_token=config.telegram_bot_token,
        telegram_chat_id=config.telegram_chat_id,
        enabled=True
    )
    
    # Create test issues at each severity level
    issues = [
        ComplianceIssue(
            timestamp=datetime.now(tz=timezone.utc),
            signal_id="test_sig_001",
            instrument="AAPL",
            issue_code="MISSING_RISK_CHECK",
            description="Signal generated without required risk check",
            severity=ComplianceSeverity.INFO,
            metadata={'strategy': 'momentum', 'confidence': 0.85}
        ),
        ComplianceIssue(
            timestamp=datetime.now(tz=timezone.utc),
            signal_id="test_sig_002",
            instrument="MSFT",
            issue_code="RISK_CHECK_FAILED",
            description="Risk check failed but order was placed anyway",
            severity=ComplianceSeverity.WARNING,
            metadata={'risk_score': 0.92, 'threshold': 0.80}
        ),
        ComplianceIssue(
            timestamp=datetime.now(tz=timezone.utc),
            signal_id="test_sig_003",
            instrument="GOOGL",
            issue_code="LLM_FORBIDDEN_ACTION",
            description="LLM executed forbidden action: place_market_order",
            severity=ComplianceSeverity.CRITICAL,
            metadata={'action': 'place_market_order', 'llm_model': 'gpt-4'}
        )
    ]
    
    # Route each issue
    print(f"\n📤 Routing {len(issues)} test issues to Telegram...")
    for issue in issues:
        print(f"\n   {issue.severity.upper()}: {issue.issue_code}")
        results = router.route_issue(issue)
        
        if results.get('telegram'):
            print(f"      ✅ Sent to Telegram")
        else:
            print(f"      ❌ Failed to send")
    
    print("\n✅ Demo 1 complete! Check your Telegram for 3 alerts.")


def demo_compliance_with_alerts():
    """Demo 2: Compliance monitoring with automatic alert routing."""
    print("\n" + "="*80)
    print("Demo 2: Compliance Monitoring + Telegram Alerts")
    print("="*80)
    
    # Load config
    config = load_alert_config()
    
    if not config.telegram_bot_token or not config.telegram_chat_id:
        print("\n❌ Telegram not configured!")
        return
    
    # Create router
    router = create_alert_router(
        telegram_bot_token=config.telegram_bot_token,
        telegram_chat_id=config.telegram_chat_id,
        enabled=True
    )
    
    # Get audit trail
    audit_trail = get_audit_trail()
    
    # Create strict policy
    policy = CompliancePolicy(
        name="Production Policy",
        require_risk_check=True,
        require_llm_review=True,
        max_risk_score=0.70,  # Strict threshold
        allowed_llm_actions=[
            'approve_signal',
            'reject_signal',
            'request_review'
        ],
        max_order_notional=100000
    )
    
    # Run compliance check
    print("\n🔍 Running compliance analysis...")
    monitor = ComplianceMonitor(policy=policy)
    
    # Analyze last 24 hours
    from datetime import timedelta
    end_time = datetime.now(tz=timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    report = monitor.analyze_period(
        audit_trail=audit_trail,
        start_time=start_time,
        end_time=end_time
    )
    
    print(f"\n📊 Found {len(report.issues)} compliance issues")
    
    if report.issues:
        # Route all issues
        print(f"\n📤 Routing {len(report.issues)} issues to Telegram...")
        stats = router.route_issues(report.issues)
        
        print(f"\n   ✅ Sent: {stats['sent']}")
        print(f"   ❌ Failed: {stats['failed']}")
        
        print("\n✅ Demo 2 complete! Check your Telegram for compliance alerts.")
    else:
        print("\n✅ No compliance issues found (clean audit trail)")
        print("   Run with violations: python scripts/run_compliance_test_trading.py --violations")


def demo_live_monitoring():
    """Demo 3: Simulated live monitoring with real-time alerts."""
    print("\n" + "="*80)
    print("Demo 3: Live Monitoring Simulation")
    print("="*80)
    
    print("\n📝 This demo simulates live compliance monitoring:")
    print("   1. Generate test trading data with violations")
    print("   2. Run compliance checks in real-time")
    print("   3. Send immediate alerts to Telegram")
    
    # Load config
    config = load_alert_config()
    
    if not config.telegram_bot_token or not config.telegram_chat_id:
        print("\n❌ Telegram not configured!")
        return
    
    # Create router
    router = create_alert_router(
        telegram_bot_token=config.telegram_bot_token,
        telegram_chat_id=config.telegram_chat_id,
        enabled=True
    )
    
    print("\n🎬 Simulating 5 trading cycles with compliance checks...")
    
    import time
    from autotrader.audit import SignalEvent, get_audit_trail
    import random
    
    audit_trail = get_audit_trail()
    policy = CompliancePolicy(
        name="Live Monitoring",
        require_risk_check=True,
        max_risk_score=0.75
    )
    monitor = ComplianceMonitor(policy=policy)
    
    symbols = ['AAPL', 'MSFT', 'GOOGL']
    
    for i in range(5):
        print(f"\n   Cycle {i+1}/5...")
        
        # Generate signal
        signal_id = f"live_sig_{i+1:03d}"
        symbol = random.choice(symbols)
        
        signal = SignalEvent(
            timestamp=datetime.now(tz=timezone.utc),
            signal_id=signal_id,
            instrument=symbol,
            direction=random.choice(['buy', 'sell']),
            strategy_name='momentum',
            confidence=random.uniform(0.6, 0.95),
            metadata={}
        )
        audit_trail.record_signal(signal)
        
        # Randomly skip risk check (violation)
        if random.random() < 0.3:  # 30% chance of violation
            print(f"      ⚠️ Skipping risk check (violation!)")
            
            # Check compliance immediately
            from datetime import timedelta
            report = monitor.analyze_period(
                audit_trail=audit_trail,
                start_time=datetime.now(tz=timezone.utc) - timedelta(seconds=5),
                end_time=datetime.now(tz=timezone.utc)
            )
            
            if report.issues:
                print(f"      🚨 {len(report.issues)} violations detected!")
                # Send alert immediately
                for issue in report.issues:
                    router.route_issue(issue)
                print(f"      📤 Alert sent to Telegram")
        else:
            print(f"      ✅ Risk check passed")
        
        time.sleep(1)  # Simulate time passing
    
    print("\n✅ Demo 3 complete! Live monitoring simulation finished.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Demo Telegram alerts for compliance monitoring"
    )
    parser.add_argument(
        '--demo',
        type=int,
        choices=[1, 2, 3],
        help='Run specific demo (1=basic, 2=compliance, 3=live)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("Telegram Alert Routing Demo")
    print("AutoTrader Compliance Monitoring System")
    print("="*80)
    
    # Check if Telegram is configured
    config = load_alert_config()
    if not config.telegram_bot_token or not config.telegram_chat_id:
        print("\n⚠️  Telegram not configured!")
        print("\n   Run setup first:")
        print("   python scripts/setup_telegram_alerts.py")
        print("\n   Or set environment variables:")
        print("   - TELEGRAM_BOT_TOKEN")
        print("   - TELEGRAM_CHAT_ID")
        return 1
    
    print(f"\n✅ Telegram configured (chat ID: {config.telegram_chat_id})")
    
    # Run demos
    if args.demo == 1:
        demo_basic_alerts()
    elif args.demo == 2:
        demo_compliance_with_alerts()
    elif args.demo == 3:
        demo_live_monitoring()
    else:
        # Run all demos
        demo_basic_alerts()
        input("\n⏸️  Press Enter to continue to Demo 2...")
        demo_compliance_with_alerts()
        input("\n⏸️  Press Enter to continue to Demo 3...")
        demo_live_monitoring()
    
    print("\n" + "="*80)
    print("All demos complete! 🎉")
    print("="*80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
