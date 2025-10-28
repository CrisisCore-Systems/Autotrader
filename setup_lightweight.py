#!/usr/bin/env python3
"""
Setup script for lightweight development mode.
Run this to configure your environment for development without Docker.
"""

import os
import shutil
import sys
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step_num, text):
    """Print a step with number."""
    print(f"[{step_num}] {text}")


def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("❌ Python 3.11+ required!")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True


def create_env_file():
    """Create .env file from lightweight template."""
    env_light = Path(".env.lightweight")
    env_file = Path(".env")
    
    if not env_light.exists():
        print("❌ .env.lightweight not found!")
        return False
    
    if env_file.exists():
        print("⚠️  .env already exists")
        response = input("   Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("   Skipping .env creation")
            return True
    
    shutil.copy(env_light, env_file)
    print("✅ Created .env from lightweight template")
    return True


def create_directories():
    """Create necessary directories."""
    dirs = [
        "artifacts",
        "logs",
        "backups",
        "backtest_results",
        "mlruns",
        "reports",
    ]
    
    for dir_name in dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {dir_name}/")
        else:
            print(f"✓  Directory exists: {dir_name}/")
    
    return True


def check_dependencies():
    """Check if required packages are installed."""
    try:
        import pandas
        import numpy
        import pytest
        print("✅ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("   Run: pip install -r requirements.txt")
        return False


def initialize_databases():
    """Initialize SQLite databases."""
    script_path = Path("scripts/db/init_dev_databases.py")
    
    if not script_path.exists():
        print("⚠️  Database init script not found, skipping")
        return True
    
    print("🔧 Initializing databases...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✅ Databases initialized")
            return True
        else:
            print(f"⚠️  Database init warning: {result.stderr}")
            return True  # Non-critical
    except Exception as e:
        print(f"⚠️  Could not initialize databases: {e}")
        print("   You can run manually: python scripts/db/init_dev_databases.py")
        return True  # Non-critical


def run_smoke_test():
    """Run a quick smoke test."""
    print("🧪 Running smoke test...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_smoke.py", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print("✅ Smoke test passed!")
            return True
        else:
            print("⚠️  Some tests failed (this might be OK for now)")
            print("   See full output: pytest tests/test_smoke.py -v")
            return True  # Non-critical for setup
    except FileNotFoundError:
        print("⚠️  pytest not found (will be installed with dependencies)")
        return True
    except Exception as e:
        print(f"⚠️  Could not run tests: {e}")
        return True  # Non-critical


def print_next_steps():
    """Print helpful next steps."""
    print_header("🎉 Setup Complete!")
    
    print("Next steps:\n")
    print("1️⃣  Install dependencies (if not already done):")
    print("   pip install -r requirements.txt")
    print("")
    print("2️⃣  Run a quick test:")
    print("   python run_scanner_free.py")
    print("")
    print("3️⃣  Start the API server:")
    print("   uvicorn src.api.main:app --reload")
    print("")
    print("4️⃣  Run paper trading:")
    print("   python run_pennyhunter_paper.py")
    print("")
    print("5️⃣  Read the guide:")
    print("   See LIGHTWEIGHT_DEVELOPMENT.md for full documentation")
    print("")
    print("💡 Memory usage: ~200-500 MB (vs 4-8 GB with Docker)")
    print("💡 Perfect for laptops with limited resources!")
    print("")


def main():
    """Main setup function."""
    print_header("🪶 Lightweight Development Setup")
    print("This script will configure your environment for development")
    print("without Docker. Perfect for resource-constrained laptops!")
    print("")
    
    # Check Python version
    print_step(1, "Checking Python version...")
    if not check_python_version():
        sys.exit(1)
    
    # Create .env file
    print_step(2, "Creating .env configuration...")
    if not create_env_file():
        sys.exit(1)
    
    # Create directories
    print_step(3, "Creating necessary directories...")
    if not create_directories():
        sys.exit(1)
    
    # Check dependencies
    print_step(4, "Checking dependencies...")
    deps_installed = check_dependencies()
    if not deps_installed:
        print("\n⚠️  Install dependencies first: pip install -r requirements.txt")
        print("   Then run this script again.\n")
        sys.exit(0)
    
    # Initialize databases
    print_step(5, "Initializing databases...")
    initialize_databases()
    
    # Run smoke test
    print_step(6, "Running smoke test...")
    run_smoke_test()
    
    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
