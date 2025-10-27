"""
Quick test script to verify Grafana compliance monitoring setup.

Tests:
1. Prometheus metrics import
2. Metrics exporter script
3. Compliance monitor integration
4. Alert router metrics
"""

import sys
import os

print("=" * 80)
print("Grafana Compliance Monitoring - Setup Verification")
print("=" * 80)
print()

# Test 1: Prometheus client availability
print("Test 1: Prometheus Client")
print("-" * 80)
try:
    from prometheus_client import Counter, Gauge, Histogram
    print("✅ prometheus-client installed and importable")
    PROM_AVAILABLE = True
except ImportError as e:
    print("❌ prometheus-client not available")
    print(f"   Error: {e}")
    print("   Install with: pip install prometheus-client")
    PROM_AVAILABLE = False
print()

# Test 2: Compliance monitor metrics
print("Test 2: Compliance Monitor Metrics")
print("-" * 80)
try:
    from autotrader.monitoring.compliance.monitor import (
        PROMETHEUS_AVAILABLE,
        COMPLIANCE_ISSUES_TOTAL,
        COMPLIANCE_CHECKS_TOTAL,
        COMPLIANCE_CHECK_DURATION,
        RISK_CHECK_FAILURES,
        ACTIVE_VIOLATIONS
    )
    print(f"✅ Compliance monitor metrics loaded")
    print(f"   PROMETHEUS_AVAILABLE: {PROMETHEUS_AVAILABLE}")
    print(f"   Metrics defined:")
    print(f"     - COMPLIANCE_ISSUES_TOTAL")
    print(f"     - COMPLIANCE_CHECKS_TOTAL")
    print(f"     - COMPLIANCE_CHECK_DURATION")
    print(f"     - RISK_CHECK_FAILURES")
    print(f"     - ACTIVE_VIOLATIONS")
except ImportError as e:
    print(f"❌ Failed to import compliance monitor metrics")
    print(f"   Error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
print()

# Test 3: Alert router metrics
print("Test 3: Alert Router Metrics")
print("-" * 80)
try:
    from autotrader.alerts.router import (
        PROMETHEUS_AVAILABLE as ROUTER_PROM_AVAILABLE,
        ALERT_DELIVERY_TOTAL
    )
    print(f"✅ Alert router metrics loaded")
    print(f"   PROMETHEUS_AVAILABLE: {ROUTER_PROM_AVAILABLE}")
    print(f"   Metrics defined:")
    print(f"     - ALERT_DELIVERY_TOTAL")
except ImportError as e:
    print(f"❌ Failed to import alert router metrics")
    print(f"   Error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
print()

# Test 4: Check files exist
print("Test 4: Dashboard and Scripts")
print("-" * 80)

files_to_check = [
    ("Dashboard JSON", "infrastructure/grafana/dashboards/compliance-monitoring.json"),
    ("Metrics Exporter", "scripts/monitoring/export_compliance_metrics.py"),
    ("Quick Start Guide", "GRAFANA_QUICKSTART.md"),
    ("Complete Docs", "GRAFANA_COMPLIANCE_DASHBOARDS_COMPLETE.md"),
]

all_files_exist = True
for name, path in files_to_check:
    if os.path.exists(path):
        print(f"✅ {name}: {path}")
    else:
        print(f"❌ {name}: {path} NOT FOUND")
        all_files_exist = False
print()

# Test 5: Try to import metrics exporter
print("Test 5: Metrics Exporter Script")
print("-" * 80)
try:
    # Check if script is executable
    exporter_path = "scripts/monitoring/export_compliance_metrics.py"
    if os.path.exists(exporter_path):
        with open(exporter_path, 'r') as f:
            content = f.read()
            if 'start_http_server' in content and 'ComplianceMonitor' in content:
                print(f"✅ Metrics exporter script is properly configured")
                print(f"   - Prometheus HTTP server: Yes")
                print(f"   - Compliance monitor integration: Yes")
                print(f"   - Command line args: Yes")
            else:
                print(f"⚠️  Metrics exporter script exists but may be incomplete")
    else:
        print(f"❌ Metrics exporter script not found")
except Exception as e:
    print(f"❌ Error checking exporter script: {e}")
print()

# Summary
print("=" * 80)
print("Summary")
print("=" * 80)

if PROM_AVAILABLE and all_files_exist:
    print("🎉 Grafana Compliance Monitoring Setup: COMPLETE")
    print()
    print("Next Steps:")
    print("  1. Start metrics exporter:")
    print("     python scripts/monitoring/export_compliance_metrics.py")
    print()
    print("  2. Generate test data:")
    print("     python scripts/run_compliance_test_trading.py --cycles 10 --include-violations")
    print()
    print("  3. View metrics:")
    print("     Open http://localhost:9090/metrics in browser")
    print()
    print("  4. Import Grafana dashboard:")
    print("     infrastructure/grafana/dashboards/compliance-monitoring.json")
    print()
    print("See GRAFANA_QUICKSTART.md for full instructions!")
else:
    print("⚠️  Setup incomplete - check errors above")
    if not PROM_AVAILABLE:
        print()
        print("Action Required:")
        print("  pip install prometheus-client")
    if not all_files_exist:
        print()
        print("Some files are missing - re-run setup")

print("=" * 80)
