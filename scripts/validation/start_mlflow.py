"""
Start MLflow tracking server locally for validation experiments.
Uses SQLite backend for simplicity.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def start_mlflow_server(
    backend_store_uri: str = "sqlite:///mlruns/mlflow.db",
    artifact_location: str = "mlruns/artifacts",
    host: str = "127.0.0.1",
    port: int = 5000
) -> None:
    """
    Start MLflow tracking server.
    
    Args:
        backend_store_uri: Database URI for storing experiment metadata
        artifact_location: Directory for storing artifacts
        host: Host address (default localhost)
        port: Port number (default 5000)
    """
    # Ensure directories exist
    mlruns_dir = Path("mlruns")
    mlruns_dir.mkdir(exist_ok=True)
    
    artifacts_dir = Path(artifact_location)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Starting MLflow tracking server...")
    print(f"   Backend: {backend_store_uri}")
    print(f"   Artifacts: {artifact_location}")
    print(f"   UI: http://{host}:{port}")
    print(f"\nPress Ctrl+C to stop the server.\n")
    
    cmd = [
        "mlflow",
        "server",
        "--backend-store-uri", backend_store_uri,
        "--default-artifact-root", artifact_location,
        "--host", host,
        "--port", str(port),
    ]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n\n✅ MLflow server stopped.")
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error starting MLflow server: {e}")
        sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start MLflow tracking server')
    parser.add_argument('--backend-store-uri', type=str,
                       default='sqlite:///mlruns/mlflow.db',
                       help='Backend store URI (default: SQLite)')
    parser.add_argument('--artifact-location', type=str,
                       default='mlruns/artifacts',
                       help='Artifact storage location')
    parser.add_argument('--host', type=str, default='127.0.0.1',
                       help='Host address (default: localhost)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Port number (default: 5000)')
    
    args = parser.parse_args()
    
    start_mlflow_server(
        backend_store_uri=args.backend_store_uri,
        artifact_location=args.artifact_location,
        host=args.host,
        port=args.port
    )
