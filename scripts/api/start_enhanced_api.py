"""Start the VoidBloom Unified API server with all features."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now import and run the unified API
if __name__ == "__main__":
    import uvicorn
    from src.api.dashboard_api import app
    
    print("=" * 60)
    print("VoidBloom Unified API")
    print("=" * 60)
    print()
    print("Starting server on http://127.0.0.1:8001")
    print("API Documentation: http://127.0.0.1:8001/docs")
    print("Health Check: http://127.0.0.1:8001/health")
    print()
    print("Available Features:")
    print("  Scanner:")
    print("    - Token Discovery: /api/tokens")
    print("    - Token Details: /api/tokens/{symbol}")
    print()
    print("  Monitoring:")
    print("    - SLA Status: /api/sla/status")
    print("    - Anomaly Detection: /api/anomalies")
    print("    - Circuit Breakers: /api/sla/circuit-breakers")
    print()
    print("  Analytics:")
    print("    - Confidence Intervals: /api/confidence/*")
    print("    - Token Correlation: /api/correlation/matrix")
    print("    - Order Flow: /api/orderflow/{symbol}")
    print("    - Sentiment Trends: /api/sentiment/trend/{symbol}")
    print()
    print("  Feature Store:")
    print("    - Token Features: /api/features/{symbol}")
    print("    - Feature Schema: /api/features/schema")
    print()
    print("Press CTRL+C to stop")
    print("=" * 60)
    print()
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        log_level="info",
    )
