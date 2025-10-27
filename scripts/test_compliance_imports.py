"""Quick test to verify compliance monitoring imports work."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("Testing compliance monitoring imports...")

try:
    from autotrader.audit import EventType, get_audit_trail
    print("✅ autotrader.audit imports OK")
except ImportError as e:
    print(f"❌ autotrader.audit import failed: {e}")
    sys.exit(1)

try:
    from autotrader.monitoring.compliance import (
        ComplianceIssue,
        ComplianceMonitor,
        CompliancePolicy,
        ComplianceSeverity,
    )
    print("✅ autotrader.monitoring.compliance imports OK")
except ImportError as e:
    print(f"❌ autotrader.monitoring.compliance import failed: {e}")
    sys.exit(1)

try:
    from autotrader.monitoring.anomaly import AnomalyDetector
    print("✅ autotrader.monitoring.anomaly imports OK")
except ImportError as e:
    print(f"❌ autotrader.monitoring.anomaly import failed: {e}")
    sys.exit(1)

print("\n✅ All imports successful!")
print("\nNow testing basic instantiation...")

try:
    # Test CompliancePolicy
    policy = CompliancePolicy(
        require_risk_check=True,
        require_llm_review=False,
        max_risk_score=0.75,
    )
    print(f"✅ CompliancePolicy created: max_risk_score={policy.max_risk_score}")
except Exception as e:
    print(f"❌ CompliancePolicy failed: {e}")
    sys.exit(1)

try:
    # Test ComplianceMonitor
    monitor = ComplianceMonitor(policy=policy)
    print("✅ ComplianceMonitor created")
except Exception as e:
    print(f"❌ ComplianceMonitor failed: {e}")
    sys.exit(1)

print("\n🎉 Compliance Monitoring Framework is working!")
print("\nYou can now run the full demo:")
print("  python scripts/demo_compliance_monitoring.py")
