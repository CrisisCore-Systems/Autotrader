"""
Quick test script for Telegram bot configuration.
Tests the bot connection and sends a test message.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from autotrader.alerts.router import TelegramAdapter
from autotrader.monitoring.compliance.monitor import (
    ComplianceIssue,
    ComplianceSeverity
)

def main():
    print("=" * 80)
    print("Telegram Bot Connection Test")
    print("=" * 80)
    print()
    
    # Your credentials
    bot_token = "8447164652:AAHTW_RmFRr4UwmBNwMTE_GlZNG0bGs1hi8"
    chat_id = "8171766594"
    
    print(f"Bot Token: {bot_token[:20]}...")
    print(f"Chat ID: {chat_id}")
    print()
    
    # Test 1: Create adapter and test connection
    print("🔗 Testing bot connection...")
    try:
        telegram = TelegramAdapter(bot_token=bot_token, chat_id=chat_id)
        
        if telegram.test_connection():
            print("✅ Bot connection successful!")
        else:
            print("❌ Bot connection failed!")
            return False
    except Exception as e:
        print(f"❌ Error creating adapter: {e}")
        return False
    
    print()
    
    # Test 2: Send INFO level test alert
    print("📤 Sending INFO test alert...")
    issue_info = ComplianceIssue(
        issue_code="SETUP_TEST",
        description="✅ Telegram bot setup successful! Your alerts are now configured.",
        severity=ComplianceSeverity.INFO,
        signal_id="test_signal_001",
        metadata={
            'setup_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Ready to receive alerts',
            'test_type': 'INFO level',
            'instrument': 'TEST'
        }
    )
    
    if telegram.send_alert(issue_info):
        print("✅ INFO alert sent!")
    else:
        print("❌ Failed to send INFO alert")
        return False
    
    print()
    
    # Test 3: Send WARNING level test alert
    print("📤 Sending WARNING test alert...")
    issue_warning = ComplianceIssue(
        issue_code="RISK_CHECK_FAILED",
        description="Risk check failed but trade was not blocked",
        severity=ComplianceSeverity.WARNING,
        signal_id="test_signal_002",
        metadata={
            'risk_score': 0.78,
            'threshold': 0.70,
            'checks_failed': 2,
            'instrument': 'MSFT'
        }
    )
    
    if telegram.send_alert(issue_warning):
        print("✅ WARNING alert sent!")
    else:
        print("❌ Failed to send WARNING alert")
        return False
    
    print()
    
    # Test 4: Send CRITICAL level test alert
    print("📤 Sending CRITICAL test alert...")
    issue_critical = ComplianceIssue(
        issue_code="RISK_OVERRIDE",
        description="Risk check was overridden without proper authorization",
        severity=ComplianceSeverity.CRITICAL,
        signal_id="test_signal_003",
        metadata={
            'original_decision': 'reject',
            'override_reason': 'Manual override',
            'risk_score': 0.92,
            'authorized': False,
            'instrument': 'AAPL'
        }
    )
    
    if telegram.send_alert(issue_critical):
        print("✅ CRITICAL alert sent!")
    else:
        print("❌ Failed to send CRITICAL alert")
        return False
    
    print()
    print("=" * 80)
    print("🎉 All Tests Passed!")
    print("=" * 80)
    print()
    print("Check your Telegram - you should see 3 messages:")
    print("  1. ℹ️  INFO: Setup successful")
    print("  2. ⚠️  WARNING: Risk check failed")
    print("  3. 🚨 CRITICAL: Risk override")
    print()
    print("Configuration saved to: configs/alerts.yaml")
    print()
    print("Next steps:")
    print("  1. Generate violations:")
    print("     python scripts/run_compliance_test_trading.py --cycles 10 --violations")
    print()
    print("  2. Test compliance monitoring with alerts:")
    print("     python scripts/demo_compliance_monitoring.py --send-alerts")
    print()
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
