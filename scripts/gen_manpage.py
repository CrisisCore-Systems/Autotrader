#!/usr/bin/env python
"""
Standalone script to generate AutoTrader manual page.

Usage:
    python scripts/gen_manpage.py [--format {man,md}] [--output PATH]

This script can be run as part of the build process or CI/CD pipeline
to generate up-to-date manual pages from the current CLI implementation.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.cli.manpage import ManpageGenerator


def create_cli_parser() -> argparse.ArgumentParser:
    """
    Create the actual CLI parser.
    
    This should match the main CLI parser to ensure accurate documentation.
    For production, consider importing the actual parser from main.py.
    """
    parser = argparse.ArgumentParser(
        prog="autotrader-scan",
        description="Automated trading strategy scanner and backtesting platform. "
                   "Scans markets for profitable trading strategies, backtests them "
                   "against historical data, and generates performance reports with "
                   "reproducibility guarantees."
    )
    
    # Configuration
    config_group = parser.add_argument_group("configuration")
    config_group.add_argument(
        "--config",
        metavar="PATH",
        help="Path to configuration file (YAML format)"
    )
    config_group.add_argument(
        "--print-effective-config",
        action="store_true",
        help="Print effective merged configuration with origins and exit"
    )
    
    # Logging
    logging_group = parser.add_argument_group("logging")
    logging_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging verbosity level"
    )
    logging_group.add_argument(
        "--log-file",
        metavar="PATH",
        help="Write logs to file instead of console"
    )
    
    # Locking
    lock_group = parser.add_argument_group("concurrency control")
    lock_group.add_argument(
        "--lock-ttl",
        type=int,
        metavar="SECONDS",
        help="Lock timeout in seconds (auto-cleanup stale locks)"
    )
    lock_group.add_argument(
        "--no-lock",
        action="store_true",
        help="Disable file locking (use with caution)"
    )
    
    # Reproducibility
    repro_group = parser.add_argument_group("reproducibility")
    repro_group.add_argument(
        "--enable-repro-stamp",
        action="store_true",
        help="Generate reproducibility stamp (git commit, input hashes, env)"
    )
    repro_group.add_argument(
        "--deterministic",
        action="store_true",
        help="Enable deterministic mode (fixed random seed, sorted outputs)"
    )
    repro_group.add_argument(
        "--random-seed",
        type=int,
        metavar="SEED",
        help="Random seed for reproducibility"
    )
    
    # Metrics
    metrics_group = parser.add_argument_group("observability")
    metrics_group.add_argument(
        "--metrics-port",
        type=int,
        metavar="PORT",
        default=9090,
        help="Port for Prometheus metrics endpoint"
    )
    metrics_group.add_argument(
        "--enable-tracing",
        action="store_true",
        help="Enable distributed tracing"
    )
    
    # Data sources
    data_group = parser.add_argument_group("data sources")
    data_group.add_argument(
        "--data-provider",
        choices=["yahoo", "alpha_vantage", "polygon", "csv"],
        default="yahoo",
        help="Data provider to use"
    )
    data_group.add_argument(
        "--api-key",
        metavar="KEY",
        help="API key for data provider (or use AUTOTRADER_API_KEY env var)"
    )
    data_group.add_argument(
        "--data-dir",
        metavar="PATH",
        help="Directory for data cache"
    )
    
    # Strategy
    strategy_group = parser.add_argument_group("strategy")
    strategy_group.add_argument(
        "--strategy",
        metavar="NAME",
        help="Strategy plugin to use"
    )
    strategy_group.add_argument(
        "--strategy-params",
        metavar="JSON",
        help="Strategy parameters as JSON string"
    )
    
    # Output
    output_group = parser.add_argument_group("output")
    output_group.add_argument(
        "--output",
        metavar="PATH",
        help="Output file path (default: stdout)"
    )
    output_group.add_argument(
        "--output-format",
        choices=["json", "yaml", "csv"],
        default="json",
        help="Output format"
    )
    output_group.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print output (human-readable formatting)"
    )
    
    # Schema
    schema_group = parser.add_argument_group("schema")
    schema_group.add_argument(
        "--validate-schema",
        action="store_true",
        help="Validate output against schema before writing"
    )
    schema_group.add_argument(
        "--schema-version",
        metavar="VERSION",
        help="Require specific schema version"
    )
    
    # Deprecation
    parser.add_argument(
        "--print-deprecation-warnings",
        action="store_true",
        help="Print deprecation warnings and migration guide"
    )
    
    return parser


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate AutoTrader manual page from CLI definition"
    )
    parser.add_argument(
        "--format",
        choices=["man", "md"],
        default="man",
        help="Output format (default: man)"
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--version",
        metavar="VERSION",
        default="0.1.0",
        help="Version string for manual page"
    )
    
    args = parser.parse_args()
    
    # Create CLI parser (the one we're documenting)
    cli_parser = create_cli_parser()
    
    # Generate manpage
    generator = ManpageGenerator(
        parser=cli_parser,
        prog_name="autotrader-scan",
        section=1,
        version=args.version,
        authors=["AutoTrader Development Team", "CrisisCore Systems"],
        description="Automated trading strategy scanner and backtesting platform"
    )
    
    output = generator.generate(format=args.format)
    
    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Manual page written to: {output_path}", file=sys.stderr)
    else:
        print(output)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
