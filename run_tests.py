"""
AutoTrader Test Runner

Convenient Python script to run tests with various configurations.

Usage:
    python run_tests.py              # Run all tests
    python run_tests.py --unit       # Run unit tests only
    python run_tests.py --coverage   # Run with coverage
    python run_tests.py --fast       # Skip slow tests
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and print results"""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, shell=True)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run AutoTrader tests")

    # Test selection
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--performance", action="store_true", help="Run performance tests only")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")

    # Test files
    parser.add_argument("--api", action="store_true", help="Run API tests only")
    parser.add_argument("--core", action="store_true", help="Run core services tests only")
    parser.add_argument("--enhanced", action="store_true", help="Run enhanced modules tests only")
    parser.add_argument("--e2e", action="store_true", help="Run E2E workflow tests only")
    parser.add_argument("--perf", action="store_true", help="Run performance tests only")

    # Coverage and reporting
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # Other options
    parser.add_argument("--parallel", "-n", type=int, help="Run tests in parallel (specify worker count)")
    parser.add_argument("--file", type=str, help="Run specific test file")
    parser.add_argument("--test", type=str, help="Run specific test function")

    args = parser.parse_args()

    # Build pytest command
    cmd_parts = ["pytest"]

    # Determine what to run
    if args.file:
        cmd_parts.append(f"tests/{args.file}")
    elif args.api:
        cmd_parts.append("tests/test_api_integration.py")
    elif args.core:
        cmd_parts.append("tests/test_core_services.py")
    elif args.enhanced:
        cmd_parts.append("tests/test_enhanced_modules.py")
    elif args.e2e:
        cmd_parts.append("tests/test_e2e_workflows.py")
    elif args.perf:
        cmd_parts.append("tests/test_performance.py")
    else:
        cmd_parts.append("tests/")

    # Markers
    markers = []
    if args.unit:
        markers.append("unit")
    if args.integration:
        markers.append("integration")
    if args.performance:
        markers.append("performance")
    if args.fast:
        markers.append("not slow")

    if markers:
        cmd_parts.append(f"-m \"{' and '.join(markers)}\"")

    # Specific test
    if args.test:
        cmd_parts.append(f"-k {args.test}")

    # Verbosity
    if args.verbose:
        cmd_parts.append("-vv")
    else:
        cmd_parts.append("-v")

    # Coverage
    if args.coverage or args.html:
        cmd_parts.append("--cov=src")
        if args.html:
            cmd_parts.append("--cov-report=html")
            cmd_parts.append("--cov-report=term")
        else:
            cmd_parts.append("--cov-report=term-missing")

    # Parallel execution
    if args.parallel:
        cmd_parts.append(f"-n {args.parallel}")

    # Additional options
    cmd_parts.extend([
        "--tb=short",
        "--disable-warnings"
    ])

    # Run the command
    cmd = " ".join(cmd_parts)
    exit_code = run_command(cmd, "Running AutoTrader Tests")

    # Open HTML report if generated
    if args.html and exit_code == 0:
        print("\n" + "="*60)
        print("  Opening HTML coverage report...")
        print("="*60 + "\n")
        import webbrowser
        html_path = Path("htmlcov/index.html").absolute()
        if html_path.exists():
            webbrowser.open(f"file://{html_path}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
