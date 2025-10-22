"""Start the AutoTrader Dashboard API server."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Now import and run the API
if __name__ == "__main__":
    import uvicorn
    
    # Import the reorganized scanner API entry point
    from src.api.main import app
    
    print("=" * 60)
    print("AutoTrader Scanner API")
    print("=" * 60)
    print()
    print("Starting server on http://127.0.0.1:8001")
    print("API Documentation: http://127.0.0.1:8001/docs")
    print("Health Check: http://127.0.0.1:8001/health")
    print("Token List: http://127.0.0.1:8001/api/tokens")
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
