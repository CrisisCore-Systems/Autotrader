"""Enhanced CLI main module for AutoTrader scanner.

Integrates all CLI enhancements:
- Config resolution (YAML, argparse, env vars)
- Metrics emission (stdout, StatsD)
- Runtime watchdog and concurrency locks
- Plugin strategy loading
- Deterministic mode
- Exit codes and error handling
- Dry-run mode
- Structured logging
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, NoReturn

# Import CLI modules
from src.cli.config import (
    ConfigError,
    load_yaml_config,
    print_config,
    resolve_config,
    validate_output_schema,
)
from src.cli.deterministic import (
    enable_deterministic_mode,
    log_deterministic_environment,
    print_seed_info,
)
from src.cli.exit_codes import (
    ExitCode,
    get_category_for_exception,
    print_exit_codes,
)
from src.cli.metrics import (
    initialize_metrics,
    get_collector,
    shutdown_metrics,
)
from src.cli.plugins import (
    create_strategy_instance,
    list_strategies,
    StrategyError,
)
from src.cli.runtime import (
    create_lock,
    create_watchdog,
    LockError,
    SignalHandler,
    WatchdogTimeout,
)

# Import core modules
from src.core.pipeline import TokenConfig

logger = logging.getLogger(__name__)


def setup_logging(log_level: str, log_format: str = "text") -> None:
    """Setup logging with specified level and format.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format style ('text' or 'json')
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"Error: Invalid log level: {log_level}", file=sys.stderr)
        sys.exit(ExitCode.MISUSE)
    
    if log_format == "json":
        # JSON structured logging
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # Standard text logging
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    
    logger.info(f"✅ Logging initialized: {log_level} ({log_format} format)")


def build_parser() -> argparse.ArgumentParser:
    """Build comprehensive argument parser."""
    parser = argparse.ArgumentParser(
        description="AutoTrader Hidden Gem Scanner - Production CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scan with config file
  autotrader-scan --config configs/example.yaml
  
  # Override with environment variable
  AUTOTRADER_LOG_LEVEL=DEBUG autotrader-scan --config config.yaml
  
  # Deterministic mode with metrics
  autotrader-scan --config config.yaml --deterministic --seed 42 --emit-metrics stdout
  
  # Production run with watchdog and lock
  autotrader-scan --config config.yaml --max-duration-seconds 3600 --lock-file /tmp/scan.lock
  
  # Dry run to validate config
  autotrader-scan --config config.yaml --dry-run
  
  # List available strategies
  autotrader-scan --list-strategies
  
  # Show exit codes
  autotrader-scan --list-exit-codes
        """,
    )
    
    # Core arguments
    core = parser.add_argument_group("Core Options")
    core.add_argument(
        "--config",
        type=Path,
        help="Path to YAML configuration file (overrides defaults)",
    )
    core.add_argument(
        "--output",
        type=Path,
        default=Path("reports/scans"),
        help="Output directory for results (default: reports/scans)",
    )
    
    # Strategy selection
    strategy = parser.add_argument_group("Strategy Options")
    strategy.add_argument(
        "--strategy",
        default="default",
        help="Strategy name or module path (default: default)",
    )
    strategy.add_argument(
        "--list-strategies",
        action="store_true",
        help="List available strategies and exit",
    )
    
    # Deterministic mode
    deterministic = parser.add_argument_group("Deterministic Mode")
    deterministic.add_argument(
        "--deterministic",
        action="store_true",
        help="Enable deterministic mode (seed Python, NumPy, PyTorch)",
    )
    deterministic.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic mode (default: 42)",
    )
    
    # Logging
    logging_group = parser.add_argument_group("Logging Options")
    logging_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    logging_group.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Log format (default: text)",
    )
    
    # Metrics and telemetry
    metrics_group = parser.add_argument_group("Metrics & Telemetry")
    metrics_group.add_argument(
        "--emit-metrics",
        choices=["none", "stdout", "statsd"],
        help="Emit metrics (none=disabled, stdout=JSON lines, statsd=StatsD)",
    )
    metrics_group.add_argument(
        "--statsd-host",
        default="localhost",
        help="StatsD server hostname (default: localhost)",
    )
    metrics_group.add_argument(
        "--statsd-port",
        type=int,
        default=8125,
        help="StatsD server port (default: 8125)",
    )
    
    # Runtime limits
    runtime = parser.add_argument_group("Runtime Limits")
    runtime.add_argument(
        "--max-duration-seconds",
        type=float,
        help="Maximum execution duration (watchdog timeout)",
    )
    runtime.add_argument(
        "--lock-file",
        type=Path,
        help="File lock path to prevent concurrent runs",
    )
    
    # Output validation
    output = parser.add_argument_group("Output Validation")
    output.add_argument(
        "--validate-output",
        action="store_true",
        help="Validate output against JSON schema",
    )
    output.add_argument(
        "--schema-path",
        type=Path,
        default=Path("configs/output_schema.json"),
        help="Path to JSON schema (default: configs/output_schema.json)",
    )
    
    # Utility flags
    utility = parser.add_argument_group("Utility Flags")
    utility.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run: validate config and exit without scanning",
    )
    utility.add_argument(
        "--list-exit-codes",
        action="store_true",
        help="List all exit codes and exit",
    )
    utility.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )
    
    return parser


def run_dry_run(config: dict[str, Any]) -> None:
    """Execute dry-run mode: validate config and print.
    
    Args:
        config: Resolved configuration
    """
    logger.info("=" * 60)
    logger.info("DRY RUN MODE - Configuration Validation")
    logger.info("=" * 60)
    
    print_config(config, mask_secrets=True)
    
    # Validate strategy
    strategy_name = config.get("strategy", "default")
    try:
        from src.cli.plugins import load_strategy
        strategy_class = load_strategy(strategy_name)
        logger.info(f"✅ Strategy validated: {strategy_name} -> {strategy_class.__name__}")
    except StrategyError as e:
        logger.error(f"❌ Strategy validation failed: {e}")
        sys.exit(ExitCode.STRATEGY_ERROR)
    
    # Validate output directory
    output_dir = Path(config.get("output", "reports/scans"))
    if output_dir.exists() and not output_dir.is_dir():
        logger.error(f"❌ Output path exists but is not a directory: {output_dir}")
        sys.exit(ExitCode.OUTPUT_ERROR)
    logger.info(f"✅ Output directory: {output_dir}")
    
    # Check schema if validation enabled
    if config.get("validate_output"):
        schema_path = Path(config.get("schema_path", "configs/output_schema.json"))
        if schema_path.exists():
            logger.info(f"✅ Schema found: {schema_path}")
        else:
            logger.warning(f"⚠️  Schema not found: {schema_path}")
    
    logger.info("=" * 60)
    logger.info("✅ Dry run complete - configuration is valid")
    logger.info("=" * 60)


def run_scan(config: dict[str, Any]) -> dict[str, Any]:
    """Execute the scanner with resolved configuration.
    
    Args:
        config: Resolved configuration
        
    Returns:
        Scan results dictionary
        
    Raises:
        Various exceptions for different error conditions
    """
    metrics = get_collector()
    
    with metrics.timed("scan_total_duration"):
        # Initialize strategy
        strategy_name = config.get("strategy", "default")
        logger.info(f"Loading strategy: {strategy_name}")
        
        try:
            strategy = create_strategy_instance(strategy_name)
        except StrategyError as e:
            logger.error(f"❌ Failed to load strategy: {e}")
            raise
        
        # Load tokens from config
        tokens_config = config.get("tokens", [])
        if not tokens_config:
            raise ValueError("No tokens specified in configuration")
        
        tokens = []
        for token_data in tokens_config:
            tokens.append(TokenConfig(**token_data))
        
        logger.info(f"Processing {len(tokens)} token(s)")
        metrics.gauge("tokens_to_scan", len(tokens))
        
        # Execute scans
        results = {
            "tokens": [],
            "metadata": {
                "version": "0.1.0",
                "strategy": strategy_name,
                "tokens_processed": 0,
                "tokens_successful": 0,
                "tokens_failed": 0,
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "config": {
                "liquidity_threshold": config.get("scanner", {}).get("liquidity_threshold"),
                "deterministic": config.get("deterministic", False),
                "seed": config.get("seed"),
            },
        }
        
        start_time = time.time()
        
        for token in tokens:
            try:
                logger.info(f"Scanning: {token.symbol}")
                metrics.counter("tokens_scanned")
                
                with metrics.timed(f"scan_token_{token.symbol}"):
                    result, tree = strategy.scan_with_tree(token)
                
                # Save artifacts
                output_dir = Path(config.get("output", "reports/scans"))
                output_dir.mkdir(parents=True, exist_ok=True)
                
                md_path = output_dir / f"{token.symbol.lower()}_report.md"
                html_path = output_dir / f"{token.symbol.lower()}_report.html"
                
                md_path.write_text(result.artifact_markdown, encoding='utf-8')
                html_path.write_text(result.artifact_html, encoding='utf-8')
                
                # Add to results
                token_result = {
                    "symbol": token.symbol,
                    "gem_score": result.gem_score,
                    "status": "success",
                    "artifacts": {
                        "markdown_path": str(md_path),
                        "html_path": str(html_path),
                    },
                }
                results["tokens"].append(token_result)
                results["metadata"]["tokens_successful"] += 1
                
                logger.info(f"✅ {token.symbol}: GemScore={result.gem_score:.1f}")
                metrics.counter("tokens_successful")
                metrics.gauge(f"gem_score_{token.symbol}", result.gem_score)
            
            except Exception as e:
                logger.error(f"❌ Failed to scan {token.symbol}: {e}")
                results["tokens"].append({
                    "symbol": token.symbol,
                    "status": "failed",
                    "errors": [str(e)],
                })
                results["metadata"]["tokens_failed"] += 1
                metrics.counter("tokens_failed")
            
            results["metadata"]["tokens_processed"] += 1
        
        duration = time.time() - start_time
        results["metadata"]["duration_seconds"] = duration
        
        logger.info(f"✅ Scan complete: {results['metadata']['tokens_successful']}/{len(tokens)} successful")
        
        return results


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point.
    
    Args:
        argv: Command-line arguments
        
    Returns:
        Exit code
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    
    # Handle utility flags first
    if args.list_exit_codes:
        print_exit_codes()
        return ExitCode.SUCCESS
    
    if args.version:
        print("AutoTrader v0.1.0")
        return ExitCode.SUCCESS
    
    if args.list_strategies:
        strategies = list_strategies()
        print("\n" + "=" * 60)
        print("AVAILABLE STRATEGIES")
        print("=" * 60)
        if strategies:
            for name in strategies:
                print(f"  - {name}")
        else:
            print("  No strategies found (use entry points or built-ins)")
        print("=" * 60 + "\n")
        return ExitCode.SUCCESS
    
    # Setup logging
    setup_logging(args.log_level, args.log_format)
    
    logger.info("=" * 60)
    logger.info("AUTOTRADER SCANNER CLI")
    logger.info("=" * 60)
    
    # Initialize signal handler
    signal_handler = SignalHandler()
    signal_handler.setup()
    
    # Initialize metrics
    metrics = None
    if args.emit_metrics:
        try:
            metrics = initialize_metrics(
                args.emit_metrics,
                statsd_host=args.statsd_host,
                statsd_port=args.statsd_port,
            )
            signal_handler.register_cleanup(shutdown_metrics)
        except Exception as e:
            logger.error(f"Failed to initialize metrics: {e}")
            return ExitCode.GENERAL_ERROR
    
    # Create watchdog if specified
    watchdog = None
    if args.max_duration_seconds:
        try:
            watchdog = create_watchdog(
                args.max_duration_seconds,
                cleanup_callback=shutdown_metrics if metrics else None,
            )
            logger.info(f"⏱️  Watchdog enabled: {args.max_duration_seconds}s timeout")
        except Exception as e:
            logger.error(f"Failed to create watchdog: {e}")
            return ExitCode.RUNTIME_ERROR
    
    # Acquire lock if specified
    lock = None
    if args.lock_file:
        try:
            lock = create_lock(args.lock_file, timeout=10)
            signal_handler.register_cleanup(lambda: lock.release() if lock else None)
        except LockError as e:
            logger.error(f"❌ {e}")
            return ExitCode.LOCK_ERROR
    
    try:
        # Resolve configuration
        try:
            config = resolve_config(args, args.config)
        except ConfigError as e:
            logger.error(f"❌ Configuration error: {e}")
            return ExitCode.CONFIG_ERROR
        
        # Enable deterministic mode if requested
        if args.deterministic or config.get("deterministic"):
            seed = args.seed if hasattr(args, "seed") else config.get("seed", 42)
            enable_deterministic_mode(seed)
            log_deterministic_environment(seed)
        
        # Dry run mode
        if args.dry_run:
            run_dry_run(config)
            return ExitCode.SUCCESS
        
        # Execute scan
        logger.info("Starting scan...")
        results = run_scan(config)
        
        # Export results
        output_dir = Path(config.get("output", "reports/scans"))
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results_path = output_dir / "scan_results.json"
        with results_path.open("w") as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"📄 Results exported: {results_path}")
        
        # Validate output if requested
        if args.validate_output or config.get("validate_output"):
            schema_path = Path(config.get("schema_path", args.schema_path))
            try:
                validate_output_schema(results, schema_path)
            except ConfigError as e:
                logger.error(f"❌ Output validation failed: {e}")
                return ExitCode.SCHEMA_VALIDATION_ERROR
        
        # Cancel watchdog
        if watchdog:
            watchdog.cancel()
        
        logger.info("=" * 60)
        logger.info("✅ SCAN COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
        return ExitCode.SUCCESS
    
    except KeyboardInterrupt:
        logger.warning("⚠️  Interrupted by user")
        return ExitCode.SIGINT
    
    except WatchdogTimeout:
        logger.error("❌ Watchdog timeout exceeded")
        return ExitCode.WATCHDOG_TIMEOUT
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        exit_code = get_category_for_exception(e)
        return exit_code
    
    finally:
        # Cleanup
        if lock:
            lock.release()
        if metrics:
            shutdown_metrics()
        logger.info("✅ Cleanup complete")


def cli_main() -> NoReturn:
    """Entry point for console script."""
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
