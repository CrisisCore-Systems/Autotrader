"""CLI entrypoint for the GemScore backtest.

This is a wrapper script that provides a robust command-line interface
for running backtests with different engines and configurations.
Use this for command-line execution to avoid circular imports.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, NoReturn

# Import both backtest engines
import src.pipeline.backtest as pipeline_backtest
import backtest.harness as harness_backtest


def setup_logging(log_level: str) -> None:
    """Initialize centralized logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build comprehensive argument parser with all CLI options."""
    parser = argparse.ArgumentParser(
        description="GemScore Backtest CLI - Run walk-forward backtests with configurable parameters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic backtest with pipeline engine
  python -m pipeline.cli_backtest --start 2024-01-01 --end 2024-12-31

  # Compare with harness engine and extended metrics
  python -m pipeline.cli_backtest --start 2024-01-01 --end 2024-12-31 \\
      --engine harness --extended-metrics --compare-baselines

  # Full configuration with JSON export
  python -m pipeline.cli_backtest --start 2024-01-01 --end 2024-12-31 \\
      --walk 30d --k 10 --output ./results --json-export \\
      --experiment-description "Q1 2024 analysis" --log-level DEBUG
        """,
    )

    # Core backtest parameters
    core_group = parser.add_argument_group("Core Parameters")
    core_group.add_argument(
        "--start",
        required=True,
        help="Backtest start date (YYYY-MM-DD)",
    )
    core_group.add_argument(
        "--end",
        required=True,
        help="Backtest end date (YYYY-MM-DD)",
    )
    core_group.add_argument(
        "--walk",
        default="30d",
        help="Walk-forward window size (e.g., 30d, 4w). Default: 30d",
    )
    core_group.add_argument(
        "--k",
        default=10,
        type=int,
        help="Precision@K cutoff (number of top assets to evaluate). Default: 10",
    )
    core_group.add_argument(
        "--seed",
        default=13,
        type=int,
        help="Random seed for reproducibility. Default: 13",
    )

    # Engine selection
    engine_group = parser.add_argument_group("Engine Selection")
    engine_group.add_argument(
        "--engine",
        choices=["pipeline", "harness"],
        default="pipeline",
        help="Backtest engine to use. 'pipeline': walk-forward with experiment tracking. "
             "'harness': single-period evaluation with extended metrics. Default: pipeline",
    )

    # Strategy and analysis options
    strategy_group = parser.add_argument_group("Strategy & Analysis Options")
    strategy_group.add_argument(
        "--compare-baselines",
        action="store_true",
        help="Compare GemScore against baseline strategies (random, cap-weighted, momentum)",
    )
    strategy_group.add_argument(
        "--extended-metrics",
        action="store_true",
        help="Calculate extended metrics (IC, risk-adjusted returns). Harness engine only.",
    )

    # Output configuration
    output_group = parser.add_argument_group("Output Configuration")
    output_group.add_argument(
        "--output",
        default="reports/backtests",
        help="Output directory root for results. Default: reports/backtests",
    )
    output_group.add_argument(
        "--json-export",
        action="store_true",
        help="Export results in JSON format (in addition to default CSV/JSON outputs)",
    )

    # Experiment tracking (pipeline engine only)
    experiment_group = parser.add_argument_group("Experiment Tracking (Pipeline Engine)")
    experiment_group.add_argument(
        "--no-track-experiments",
        dest="track_experiments",
        action="store_false",
        help="Disable experiment tracking (pipeline engine only)",
    )
    experiment_group.add_argument(
        "--experiment-description",
        default="",
        help="Description of the experiment for tracking purposes",
    )
    experiment_group.add_argument(
        "--experiment-tags",
        default="",
        help="Comma-separated tags for the experiment (e.g., 'q1-2024,production')",
    )

    # Harness-specific options
    harness_group = parser.add_argument_group("Harness Engine Options")
    harness_group.add_argument(
        "--data",
        type=Path,
        help="Path to CSV with features (required for harness engine)",
    )

    # Logging and diagnostics
    logging_group = parser.add_argument_group("Logging & Diagnostics")
    logging_group.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level. Default: INFO",
    )

    return parser


def run_pipeline_engine(args: argparse.Namespace) -> Path:
    """Run backtest using the pipeline engine.

    Args:
        args: Parsed command-line arguments

    Returns:
        Path to output directory

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If backtest execution fails
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting backtest with pipeline engine")

    config = pipeline_backtest.BacktestConfig.from_args(args)
    logger.debug(f"Configuration: {config}")

    try:
        output_path = pipeline_backtest.run_backtest(config)
        logger.info(f"✅ Pipeline backtest completed: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Pipeline backtest failed: {e}", exc_info=True)
        raise RuntimeError(f"Pipeline engine execution failed: {e}") from e


def run_harness_engine(args: argparse.Namespace) -> dict[str, Any]:
    """Run backtest using the harness engine.

    Args:
        args: Parsed command-line arguments

    Returns:
        Dictionary with backtest results

    Raises:
        ValueError: If required parameters are missing or invalid
        RuntimeError: If backtest execution fails
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting backtest with harness engine")

    if not args.data:
        raise ValueError("--data parameter is required for harness engine")

    if not args.data.exists():
        raise ValueError(f"Data file not found: {args.data}")

    try:
        snapshots = list(harness_backtest.load_snapshots(args.data))
        logger.debug(f"Loaded {len(snapshots)} snapshots from {args.data}")

        result = harness_backtest.evaluate_period(
            snapshots,
            top_k=args.k,
            compare_baselines=args.compare_baselines,
            extended_metrics=args.extended_metrics,
            seed=args.seed,
        )

        logger.info("✅ Harness backtest completed")

        # Convert result to dictionary for JSON export
        result_dict = {
            "precision_at_k": result.precision_at_k,
            "average_return_at_k": result.average_return_at_k,
            "flagged_assets": result.flagged_assets,
            "engine": "harness",
            "parameters": {
                "k": args.k,
                "seed": args.seed,
                "compare_baselines": args.compare_baselines,
                "extended_metrics": args.extended_metrics,
            },
        }

        if result.baseline_results:
            result_dict["baseline_results"] = {
                name: {
                    "precision": res.precision,
                    "avg_return": res.avg_return,
                }
                for name, res in result.baseline_results.items()
            }

        if result.extended_metrics:
            result_dict["extended_metrics"] = {
                "ic": result.extended_metrics.ic,
                "rank_ic": result.extended_metrics.rank_ic,
                "sharpe_ratio": result.extended_metrics.sharpe_ratio,
                "sortino_ratio": result.extended_metrics.sortino_ratio,
                "max_drawdown": result.extended_metrics.max_drawdown,
            }

        return result_dict

    except Exception as e:
        logger.error(f"Harness backtest failed: {e}", exc_info=True)
        raise RuntimeError(f"Harness engine execution failed: {e}") from e


def export_json_results(results: dict[str, Any], output_path: Path) -> None:
    """Export results to JSON file.

    Args:
        results: Results dictionary to export
        output_path: Path to output file
    """
    logger = logging.getLogger(__name__)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    logger.info(f"📄 Results exported to JSON: {output_path}")


def main(argv: list[str] | None = None) -> int:
    """Main CLI entrypoint with robust error handling.

    Args:
        argv: Command-line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Setup logging first
    try:
        setup_logging(args.log_level)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("GemScore Backtest CLI")
    logger.info("=" * 60)

    try:
        if args.engine == "pipeline":
            output_path = run_pipeline_engine(args)

            # Optional JSON export for pipeline results
            if args.json_export:
                summary_file = output_path / "summary.json"
                if summary_file.exists():
                    logger.info(f"📄 JSON results available at: {summary_file}")
                else:
                    logger.warning("JSON export requested but summary.json not found")

        elif args.engine == "harness":
            results = run_harness_engine(args)

            # Print results to console
            print("\n" + "=" * 60)
            print("GEMSCORE PERFORMANCE (Harness Engine)")
            print("=" * 60)
            print(f"Precision@K: {results['precision_at_k']:.3f}")
            print(f"Average Return@K: {results['average_return_at_k']:.3f}")
            print(f"Flagged Assets: {', '.join(results['flagged_assets'][:10])}")

            if "baseline_results" in results:
                print("\n" + "=" * 60)
                print("BASELINE COMPARISONS")
                print("=" * 60)
                for name, baseline in results["baseline_results"].items():
                    print(f"{name}: precision={baseline['precision']:.3f}, "
                          f"return={baseline['avg_return']:.3f}")

            if "extended_metrics" in results:
                print("\n" + "=" * 60)
                print("EXTENDED METRICS")
                print("=" * 60)
                metrics = results["extended_metrics"]
                print(f"IC: {metrics.get('ic', 'N/A')}")
                print(f"Rank IC: {metrics.get('rank_ic', 'N/A')}")
                print(f"Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}")
                print(f"Sortino Ratio: {metrics.get('sortino_ratio', 'N/A')}")
                print(f"Max Drawdown: {metrics.get('max_drawdown', 'N/A')}")

            # JSON export for harness results
            if args.json_export:
                output_dir = Path(args.output)
                json_path = output_dir / "harness_results.json"
                export_json_results(results, json_path)

        logger.info("=" * 60)
        logger.info("✅ Backtest completed successfully")
        logger.info("=" * 60)
        return 0

    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        return 2
    except RuntimeError as e:
        logger.error(f"❌ Execution error: {e}")
        return 3
    except KeyboardInterrupt:
        logger.warning("⚠️  Backtest interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        return 1


def cli_main() -> NoReturn:
    """Entry point for console script that exits with proper code."""
    sys.exit(main())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
