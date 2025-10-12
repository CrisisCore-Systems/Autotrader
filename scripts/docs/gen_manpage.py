#!/usr/bin/env python
"""
Standalone script to generate AutoTrader manual page.

Usage:
    python scripts/docs/gen_manpage.py [--format {man,md}] [--output PATH]

This script can be run as part of the build process or CI/CD pipeline
to generate up-to-date manual pages from the current CLI implementation.
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
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
        description=(
            "Automated trading strategy scanner and backtesting platform. "
            "Scans markets for profitable trading strategies, backtests them "
            "against historical data, and generates performance reports with "
            "reproducibility guarantees."
        ),
    )

    # Configuration
    config_group = parser.add_argument_group("configuration")
    config_group.add_argument(
        "--config",
        metavar="PATH",
        help="Path to configuration file (YAML or JSON)",
    )
    config_group.add_argument(
        "--config-format",
        choices=["yaml", "json"],
        help="Override auto-detected config format",
    )
    config_group.add_argument(
        "--profile",
        metavar="NAME",
        help="Named configuration profile (from config file)",
    )

    config_group.add_argument(
        "--environment",
        choices=["dev", "staging", "prod"],
        default="dev",
        help="Environment config to apply",
    )

    # Execution controls
    execution_group = parser.add_argument_group("execution")
    execution_group.add_argument(
        "--strategy",
        metavar="NAME",
        help="Strategy name to run",
    )
    execution_group.add_argument(
        "--strategy-params",
        metavar="JSON",
        help="Strategy parameters as JSON",
    )
    execution_group.add_argument(
        "--lookback",
        type=int,
        default=30,
        help="Lookback window in days",
    )
    execution_group.add_argument(
        "--exchange",
        metavar="NAME",
        help="Target exchange name",
    )
    execution_group.add_argument(
        "--symbol",
        metavar="PAIR",
        help="Trading pair symbol (e.g., BTC/USDT)",
    )

    execution_group.add_argument(
        "--timeframe",
        choices=["1m", "5m", "15m", "1h", "4h", "1d"],
        default="1h",
        help="Candlestick timeframe",
    )
    execution_group.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Number of candles to fetch",
    )
    execution_group.add_argument(
        "--deterministic",
        action="store_true",
        help="Enable deterministic execution with fixed seed",
    )
    execution_group.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Random seed for deterministic runs",
    )

    execution_group.add_argument(
        "--enable-repro-stamp",
        action="store_true",
        help="Embed reproducibility metadata in results",
    )
    execution_group.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow partial results when some data is missing",
    )

    # Output controls
    output_group = parser.add_argument_group("output")
    output_group.add_argument(
        "--output",
        metavar="PATH",
        help="Output file path",
    )
    output_group.add_argument(
        "--format",
        choices=["json", "csv", "md", "html"],
        default="json",
        help="Output format",
    )
    output_group.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print output",
    )
    output_group.add_argument(
        "--include-metrics",
        action="store_true",
        help="Include extended metrics in output",
    )
    output_group.add_argument(
        "--no-metadata",
        action="store_true",
        help="Skip metadata in output",
    )

    output_group.add_argument(
        "--man-format",
        choices=["man", "md", "html"],
        default="man",
        help="Format for generated man page",
    )

    # Monitoring
    monitoring_group = parser.add_argument_group("monitoring")
    monitoring_group.add_argument(
        "--metrics-port",
        type=int,
        default=8001,
        help="Prometheus metrics port",
    )
    monitoring_group.add_argument(
        "--metrics-host",
        default="127.0.0.1",
        help="Prometheus metrics host",
    )
    monitoring_group.add_argument(
        "--enable-tracing",
        action="store_true",
        help="Enable OpenTelemetry tracing",
    )
    monitoring_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Log level",
    )
    monitoring_group.add_argument(
        "--log-file",
        metavar="PATH",
        help="Log file path",
    )

    # Concurrency
    concurrency_group = parser.add_argument_group("concurrency")
    concurrency_group.add_argument(
        "--allow-concurrency",
        action="store_true",
        help="Allow concurrent scans",
    )
    concurrency_group.add_argument(
        "--no-lock",
        action="store_true",
        help="Disable lock file for concurrent runs",
    )
    concurrency_group.add_argument(
        "--lock-file",
        metavar="PATH",
        default="/tmp/autotrader.lock",
        help="Lock file path",
    )
    concurrency_group.add_argument(
        "--lock-ttl",
        type=int,
        default=900,
        help="Lock TTL in seconds",
    )

    concurrency_group.add_argument(
        "--lock-wait",
        type=int,
        default=60,
        help="Wait time for lock acquisition",
    )
    concurrency_group.add_argument(
        "--lock-force",
        action="store_true",
        help="Force lock acquisition",
    )

    # Alerts
    alert_group = parser.add_argument_group("alerts")
    alert_group.add_argument(
        "--alert-config",
        metavar="PATH",
        help="Alert configuration file",
    )
    alert_group.add_argument(
        "--alert-channel",
        choices=["email", "slack", "pagerduty"],
        help="Alert notification channel",
    )
    alert_group.add_argument(
        "--alert-threshold",
        type=float,
        help="Alert trigger threshold",
    )
    alert_group.add_argument(
        "--alert-output",
        metavar="PATH",
        help="Alert output file",
    )

    # Risk controls
    risk_group = parser.add_argument_group("risk")
    risk_group.add_argument(
        "--max-drawdown",
        type=float,
        help="Maximum allowable drawdown",
    )
    risk_group.add_argument(
        "--max-position-size",
        type=float,
        help="Maximum position size as percentage",
    )
    risk_group.add_argument(
        "--max-leverage",
        type=float,
        help="Maximum leverage multiplier",
    )
    risk_group.add_argument(
        "--max-open-trades",
        type=int,
        help="Maximum concurrent trades",
    )
    risk_group.add_argument(
        "--risk-model",
        choices=["value_at_risk", "expected_shortfall", "custom"],
        help="Risk model to use",
    )

    # Advanced
    advanced_group = parser.add_argument_group("advanced")
    advanced_group.add_argument(
        "--prompt-contract",
        metavar="PATH",
        help="Path to prompt contract file for LLM strategies",
    )
    advanced_group.add_argument(
        "--prompt-output",
        metavar="PATH",
        help="Path to prompt output file for validation",
    )
    advanced_group.add_argument(
        "--feature-store",
        action="store_true",
        help="Enable feature store integration",
    )
    advanced_group.add_argument(
        "--feature-refresh",
        type=int,
        default=60,
        help="Feature store refresh interval (minutes)",
    )

    advanced_group.add_argument(
        "--experiment-id",
        metavar="UUID",
        help="Experiment tracking identifier",
    )
    advanced_group.add_argument(
        "--experiment-tag",
        metavar="TAG",
        action="append",
        help="Experiment tag (can be used multiple times)",
    )
    advanced_group.add_argument(
        "--experiment-notes",
        metavar="TEXT",
        help="Experiment notes",
    )

    advanced_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Run validation only without executing strategies",
    )
    advanced_group.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate configuration without executing scans",
    )

    return parser


def generate_markdown(parser: argparse.ArgumentParser, output_path: Path) -> None:
    """Generate markdown documentation."""
    generator = ManpageGenerator(parser=parser)
    output_path.write_text(generator.generate_markdown(), encoding="utf-8")


def generate_manpage(parser: argparse.ArgumentParser, output_path: Path) -> None:
    """Generate man page documentation."""
    generator = ManpageGenerator(parser=parser)
    output_path.write_text(generator.generate_manpage(), encoding="utf-8")


def main(argv=None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate AutoTrader man page")
    parser.add_argument(
        "--format",
        choices=["man", "md"],
        default="man",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args(argv)

    cli_parser = create_cli_parser()

    if args.output:
        output_path = args.output
    else:
        output_suffix = ".1" if args.format == "man" else ".md"
        output_path = project_root / "docs" / "cli" / f"autotrader-scan{output_suffix}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "man":
        generate_manpage(cli_parser, output_path)
    else:
        generate_markdown(cli_parser, output_path)

    print(f"✅ Generated {args.format} documentation at: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
