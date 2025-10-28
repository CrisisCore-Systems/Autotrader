@echo off
REM Quick start script for lightweight development on Windows
REM Run this to get started in seconds!

echo ================================================================
echo   🪶 AutoTrader - Lightweight Development Quick Start
echo ================================================================
echo.
echo This script will set you up for lightweight development
echo without Docker (uses ~200-500 MB RAM instead of 4-8 GB)
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 3 is required but not found!
    echo    Please install Python 3.11+ and try again
    exit /b 1
)

echo ✅ Python found
python --version
echo.

REM Check if we're in the right directory
if not exist "setup_lightweight.py" (
    echo ❌ Please run this script from the Autotrader root directory
    exit /b 1
)

echo Running setup...
echo.

REM Run the Python setup script
python setup_lightweight.py

echo.
echo ================================================================
echo   🎉 Setup complete! Here's what to try next:
echo ================================================================
echo.
echo 1️⃣  Install dependencies (if not already done):
echo    pip install -r requirements.txt
echo.
echo 2️⃣  Run a quick test:
echo    python run_scanner_free.py
echo.
echo 3️⃣  Start the API server:
echo    uvicorn src.api.main:app --reload
echo.
echo 4️⃣  Run paper trading:
echo    python run_pennyhunter_paper.py
echo.
echo 📚 Full documentation: LIGHTWEIGHT_DEVELOPMENT.md
echo ❓ Questions? See: LIGHTWEIGHT_FAQ.md
echo.
echo Happy coding! 🚀
echo.

pause
