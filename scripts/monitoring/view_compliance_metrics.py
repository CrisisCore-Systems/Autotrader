"""
Simple Grafana dashboard launcher and metrics viewer.

This script helps you get started with the Grafana compliance monitoring
without needing to run the full metrics exporter.

Usage:
    python scripts/monitoring/view_compliance_metrics.py
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

print("=" * 80)
print("Grafana Compliance Monitoring - Quick Viewer")
print("=" * 80)
print()

print("📊 Current Setup Status:")
print("-" * 80)

# Check dashboard file
dashboard_path = project_root / "infrastructure" / "grafana" / "dashboards" / "compliance-monitoring.json"
if dashboard_path.exists():
    size_kb = dashboard_path.stat().st_size / 1024
    print(f"✅ Dashboard JSON: {dashboard_path}")
    print(f"   Size: {size_kb:.1f} KB")
    print(f"   Panels: 13 visualizations")
else:
    print(f"❌ Dashboard not found: {dashboard_path}")

print()

# Check docs
docs = [
    ("Quick Start", "GRAFANA_QUICKSTART.md"),
    ("Complete Guide", "GRAFANA_COMPLIANCE_DASHBOARDS_COMPLETE.md"),
    ("Telegram Alerts", "TELEGRAM_ALERTS_COMPLETE.md"),
]

print("📚 Documentation:")
print("-" * 80)
for name, filename in docs:
    doc_path = project_root / filename
    if doc_path.exists():
        print(f"✅ {name}: {filename}")
    else:
        print(f"❌ {name}: {filename} NOT FOUND")

print()
print("=" * 80)
print("🚀 Quick Start Options")
print("=" * 80)
print()

print("Option 1: View Existing Compliance Data")
print("-" * 80)
print("Run compliance analysis (generates metrics):")
print()
print("  python scripts\\demo_compliance_monitoring.py")
print()
print("This will:")
print("  - Analyze last 7 days of trading activity")
print("  - Detect any compliance violations")
print("  - Send Telegram alerts for issues")
print("  - Display results in terminal")
print()

print("Option 2: Generate New Test Data")
print("-" * 80)
print("Create violations for testing:")
print()
print("  python scripts\\run_compliance_test_trading.py --cycles 10 --include-violations")
print()
print("This creates:")
print("  - 10 trading cycles")
print("  - ~3 intentional violations")
print("  - Realistic audit trail data")
print()

print("Option 3: Import Grafana Dashboard")
print("-" * 80)
print("If you have Grafana running:")
print()
print("1. Open Grafana: http://localhost:3000")
print("2. Navigate to Dashboards → Import")
print("3. Upload file:")
print(f"   {dashboard_path}")
print("4. Select Prometheus data source")
print("5. Click Import")
print()
print("Dashboard includes:")
print("  - Active Critical/Warning Violations (Gauges)")
print("  - Issues Over Time (Time Series)")
print("  - Alert Delivery Success Rate (Gauge)")
print("  - Issue Type Breakdown (Bar Chart)")
print("  - Risk Check Failures (Time Series)")
print("  - Top 10 Issue Types (Table)")
print("  - Performance Metrics (p50/p95 latency)")
print()

print("Option 4: View Raw Metrics")
print("-" * 80)
print("Check what metrics are available:")
print()
print("The compliance monitoring system tracks:")
print("  • compliance_issues_total - All violations detected")
print("  • active_violations - Current unresolved issues")  
print("  • alert_delivery_total - Telegram alert success/failure")
print("  • risk_check_failures_total - Risk check problems")
print("  • compliance_check_duration_seconds - Performance")
print("  • compliance_checks_total - Check execution count")
print()

print("=" * 80)
print("📖 For More Information")
print("=" * 80)
print()
print(f"See: {project_root}\\GRAFANA_QUICKSTART.md")
print("     (10-minute complete setup guide)")
print()
print(f"Or:  {project_root}\\GRAFANA_COMPLIANCE_DASHBOARDS_COMPLETE.md")
print("     (Full reference documentation)")
print()
print("=" * 80)

# Check if we have any compliance data
audit_db = project_root / "data" / "audit" / "autotrader.db"
if audit_db.exists():
    size_mb = audit_db.stat().st_size / (1024 * 1024)
    print(f"📊 Audit Trail Database: {size_mb:.2f} MB")
    print("   Run demo_compliance_monitoring.py to analyze!")
else:
    print("ℹ️  No audit trail data yet.")
    print("   Generate some with run_compliance_test_trading.py")

print("=" * 80)
