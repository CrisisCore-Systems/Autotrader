"""Production worker CLI for orchestrating AutoTrader jobs.

This module provides a unified entrypoint for containerized workers that can:
- Run data ingestion cycles (market data, news, social feeds)
- Execute backtesting workflows with configurable strategies
- Process optimization jobs (hyperparameter search)
- Emit Prometheus metrics for observability
- Support graceful shutdown and health checks

Example:
    # Run ingestion worker
    python -m src.cli.worker ingestion --config configs/ingestion.yaml
    
    # Run backtest worker
    python -m src.cli.worker backtest --data-dir data/features --symbols AAPL,MSFT
    
    # Run optimization worker
    python -m src.cli.worker optimize --trials 50 --splits 5
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Sequence

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Gauge = Histogram = None  # type: ignore
    start_http_server = None  # type: ignore

from src.core.logging_config import init_logging
from src.core.worker import build_worker, load_config


# ============================================================================
# Prometheus Metrics
# ============================================================================

if PROMETHEUS_AVAILABLE:
    WORKER_JOBS_TOTAL = Counter(
        'worker_jobs_total',
        'Total number of jobs processed',
        ['worker_type', 'job_type', 'status']
    )
    
    WORKER_JOB_DURATION_SECONDS = Histogram(
        'worker_job_duration_seconds',
        'Duration of job processing',
        ['worker_type', 'job_type'],
        buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0)
    )
    
    WORKER_ACTIVE_JOBS = Gauge(
        'worker_active_jobs',
        'Number of jobs currently being processed',
        ['worker_type']
    )
    
    WORKER_HEALTH_STATUS = Gauge(
        'worker_health_status',
        'Worker health status (1 = healthy, 0 = unhealthy)',
        ['worker_type']
    )
else:
    # Dummy metrics when Prometheus not available
    class _DummyMetric:
        def labels(self, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            pass
        def observe(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
    
    WORKER_JOBS_TOTAL = _DummyMetric()
    WORKER_JOB_DURATION_SECONDS = _DummyMetric()
    WORKER_ACTIVE_JOBS = _DummyMetric()
    WORKER_HEALTH_STATUS = _DummyMetric()


# ============================================================================
# Worker Types
# ============================================================================

class IngestionWorkerService:
    """Service for running data ingestion cycles."""
    
    def __init__(self, config_path: Path, db_path: Path, worker_name: str = "ingestion"):
        self.worker_name = worker_name
        self.config = load_config(config_path)
        self.worker = build_worker(self.config, db_path=db_path)
        self.logger = init_logging(service_name=worker_name).bind(worker_type="ingestion")
        self.stop_event = threading.Event()
        WORKER_HEALTH_STATUS.labels(worker_type=worker_name).set(1)
    
    def run_once(self) -> dict:
        """Execute single ingestion cycle."""
        start_time = time.perf_counter()
        WORKER_ACTIVE_JOBS.labels(worker_type=self.worker_name).inc()
        
        try:
            stats = self.worker.run_once()
            duration = time.perf_counter() - start_time
            
            WORKER_JOB_DURATION_SECONDS.labels(
                worker_type=self.worker_name,
                job_type="ingestion_cycle"
            ).observe(duration)
            
            WORKER_JOBS_TOTAL.labels(
                worker_type=self.worker_name,
                job_type="ingestion_cycle",
                status="success"
            ).inc()
            
            self.logger.info(
                "ingestion_cycle_complete",
                duration_seconds=round(duration, 3),
                total_items=stats.total,
                news=stats.news_items,
                social=stats.social_posts,
                github=stats.github_events,
                tokenomics=stats.token_snapshots,
            )
            
            return {
                "status": "success",
                "duration": duration,
                "stats": stats.as_mapping()
            }
        
        except Exception as exc:
            duration = time.perf_counter() - start_time
            WORKER_JOBS_TOTAL.labels(
                worker_type=self.worker_name,
                job_type="ingestion_cycle",
                status="error"
            ).inc()
            
            self.logger.error(
                "ingestion_cycle_failed",
                duration_seconds=round(duration, 3),
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True
            )
            
            return {
                "status": "error",
                "duration": duration,
                "error": str(exc)
            }
        
        finally:
            WORKER_ACTIVE_JOBS.labels(worker_type=self.worker_name).dec()
    
    def run_forever(self, poll_interval: float | None = None):
        """Run continuous ingestion loop."""
        interval = poll_interval or self.config.poll_interval
        self.logger.info("worker_started", poll_interval_seconds=interval)
        
        while not self.stop_event.is_set():
            self.run_once()
            
            if self.stop_event.wait(interval):
                break
        
        self.logger.info("worker_stopped")
    
    def shutdown(self):
        """Graceful shutdown."""
        self.logger.info("worker_shutdown_requested")
        self.stop_event.set()
        WORKER_HEALTH_STATUS.labels(worker_type=self.worker_name).set(0)
        self.worker.close()


class BacktestWorkerService:
    """Service for running backtest jobs."""
    
    def __init__(self, worker_name: str = "backtest"):
        self.worker_name = worker_name
        self.logger = init_logging(service_name=worker_name).bind(worker_type="backtest")
        self.stop_event = threading.Event()
        WORKER_HEALTH_STATUS.labels(worker_type=worker_name).set(1)
    
    def run_backtest(
        self,
        data_dir: Path,
        symbols: list[str],
        config: dict | None = None
    ) -> dict:
        """Execute backtest for given symbols."""
        start_time = time.perf_counter()
        WORKER_ACTIVE_JOBS.labels(worker_type=self.worker_name).inc()
        
        try:
            # Import here to avoid circular dependencies
            from autotrader.backtesting.runner import BacktestRunner
            
            runner = BacktestRunner(data_dir=data_dir, config=config)
            results = runner.run_multi_symbol(symbols)
            
            duration = time.perf_counter() - start_time
            
            WORKER_JOB_DURATION_SECONDS.labels(
                worker_type=self.worker_name,
                job_type="backtest"
            ).observe(duration)
            
            WORKER_JOBS_TOTAL.labels(
                worker_type=self.worker_name,
                job_type="backtest",
                status="success"
            ).inc()
            
            self.logger.info(
                "backtest_complete",
                duration_seconds=round(duration, 3),
                symbols_count=len(symbols),
                symbols=symbols,
            )
            
            return {
                "status": "success",
                "duration": duration,
                "results": results
            }
        
        except Exception as exc:
            duration = time.perf_counter() - start_time
            WORKER_JOBS_TOTAL.labels(
                worker_type=self.worker_name,
                job_type="backtest",
                status="error"
            ).inc()
            
            self.logger.error(
                "backtest_failed",
                duration_seconds=round(duration, 3),
                symbols=symbols,
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True
            )
            
            return {
                "status": "error",
                "duration": duration,
                "error": str(exc)
            }
        
        finally:
            WORKER_ACTIVE_JOBS.labels(worker_type=self.worker_name).dec()
    
    def shutdown(self):
        """Graceful shutdown."""
        self.logger.info("worker_shutdown_requested")
        self.stop_event.set()
        WORKER_HEALTH_STATUS.labels(worker_type=self.worker_name).set(0)


class OptimizationWorkerService:
    """Service for running hyperparameter optimization jobs."""
    
    def __init__(self, worker_name: str = "optimization"):
        self.worker_name = worker_name
        self.logger = init_logging(service_name=worker_name).bind(worker_type="optimization")
        self.stop_event = threading.Event()
        WORKER_HEALTH_STATUS.labels(worker_type=worker_name).set(1)
    
    def run_optimization(
        self,
        data_dir: Path,
        symbols: list[str],
        n_trials: int = 50,
        n_splits: int = 5,
        output_dir: Path | None = None
    ) -> dict:
        """Execute Optuna optimization for given symbols."""
        start_time = time.perf_counter()
        WORKER_ACTIVE_JOBS.labels(worker_type=self.worker_name).inc()
        
        try:
            import subprocess
            from pathlib import Path
            
            output_dir = output_dir or Path("reports/optuna")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            results = {}
            for symbol in symbols:
                if self.stop_event.is_set():
                    break
                
                cmd = [
                    sys.executable,
                    "scripts/validation/optuna_optimization.py",
                    "--data-dir", str(data_dir),
                    "--symbol", symbol,
                    "--n-trials", str(n_trials),
                    "--n-splits", str(n_splits),
                ]
                
                self.logger.info(
                    "optimization_started",
                    symbol=symbol,
                    n_trials=n_trials,
                    n_splits=n_splits
                )
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    results[symbol] = {"status": "success", "stdout": result.stdout}
                    self.logger.info("optimization_success", symbol=symbol)
                else:
                    results[symbol] = {"status": "error", "stderr": result.stderr}
                    self.logger.error("optimization_failed", symbol=symbol, error=result.stderr)
            
            duration = time.perf_counter() - start_time
            
            WORKER_JOB_DURATION_SECONDS.labels(
                worker_type=self.worker_name,
                job_type="optimization"
            ).observe(duration)
            
            success_count = sum(1 for r in results.values() if r["status"] == "success")
            status = "success" if success_count == len(symbols) else "partial"
            
            WORKER_JOBS_TOTAL.labels(
                worker_type=self.worker_name,
                job_type="optimization",
                status=status
            ).inc()
            
            self.logger.info(
                "optimization_complete",
                duration_seconds=round(duration, 3),
                total_symbols=len(symbols),
                successful=success_count,
            )
            
            return {
                "status": status,
                "duration": duration,
                "results": results
            }
        
        except Exception as exc:
            duration = time.perf_counter() - start_time
            WORKER_JOBS_TOTAL.labels(
                worker_type=self.worker_name,
                job_type="optimization",
                status="error"
            ).inc()
            
            self.logger.error(
                "optimization_failed",
                duration_seconds=round(duration, 3),
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True
            )
            
            return {
                "status": "error",
                "duration": duration,
                "error": str(exc)
            }
        
        finally:
            WORKER_ACTIVE_JOBS.labels(worker_type=self.worker_name).dec()
    
    def shutdown(self):
        """Graceful shutdown."""
        self.logger.info("worker_shutdown_requested")
        self.stop_event.set()
        WORKER_HEALTH_STATUS.labels(worker_type=self.worker_name).set(0)


# ============================================================================
# CLI Entrypoint
# ============================================================================

def start_metrics_server(port: int, address: str = "0.0.0.0") -> bool:
    """Start Prometheus metrics HTTP server."""
    if not PROMETHEUS_AVAILABLE:
        return False
    
    try:
        start_http_server(port, addr=address)
        logging.info(f"Metrics server started on {address}:{port}")
        return True
    except Exception as exc:
        logging.error(f"Failed to start metrics server: {exc}")
        return False


def setup_signal_handlers(service: IngestionWorkerService | BacktestWorkerService | OptimizationWorkerService):
    """Set up graceful shutdown handlers."""
    def handler(signum, frame):
        logging.info(f"Received signal {signum}, shutting down...")
        service.shutdown()
    
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


def cmd_ingestion(args: argparse.Namespace) -> int:
    """Run ingestion worker."""
    config_path = Path(args.config)
    db_path = Path(args.db_path)
    
    # Start metrics server
    if args.metrics_port > 0:
        start_metrics_server(args.metrics_port, args.metrics_address)
    
    # Create and start service
    service = IngestionWorkerService(
        config_path=config_path,
        db_path=db_path,
        worker_name=args.worker_name
    )
    
    setup_signal_handlers(service)
    
    if args.once:
        result = service.run_once()
        return 0 if result["status"] == "success" else 1
    else:
        service.run_forever(poll_interval=args.poll_interval)
        return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    """Run backtest worker."""
    data_dir = Path(args.data_dir)
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    # Start metrics server
    if args.metrics_port > 0:
        start_metrics_server(args.metrics_port, args.metrics_address)
    
    # Create and start service
    service = BacktestWorkerService(worker_name=args.worker_name)
    setup_signal_handlers(service)
    
    result = service.run_backtest(
        data_dir=data_dir,
        symbols=symbols,
        config=None  # TODO: Load from args.config if provided
    )
    
    return 0 if result["status"] == "success" else 1


def cmd_optimize(args: argparse.Namespace) -> int:
    """Run optimization worker."""
    data_dir = Path(args.data_dir)
    symbols = [s.strip() for s in args.symbols.split(",")]
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    # Start metrics server
    if args.metrics_port > 0:
        start_metrics_server(args.metrics_port, args.metrics_address)
    
    # Create and start service
    service = OptimizationWorkerService(worker_name=args.worker_name)
    setup_signal_handlers(service)
    
    result = service.run_optimization(
        data_dir=data_dir,
        symbols=symbols,
        n_trials=args.trials,
        n_splits=args.splits,
        output_dir=output_dir
    )
    
    return 0 if result["status"] in ("success", "partial") else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="AutoTrader Production Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Global arguments
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=int(os.getenv("WORKER_METRICS_PORT", "9100")),
        help="Port for Prometheus metrics (0 to disable)"
    )
    parser.add_argument(
        "--metrics-address",
        default=os.getenv("WORKER_METRICS_ADDRESS", "0.0.0.0"),
        help="Bind address for metrics server"
    )
    parser.add_argument(
        "--worker-name",
        default=os.getenv("WORKER_NAME", "autotrader-worker"),
        help="Worker identifier for logging and metrics"
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Ingestion worker
    ing_parser = subparsers.add_parser("ingestion", help="Run data ingestion worker")
    ing_parser.add_argument(
        "--config",
        default=os.getenv("INGESTION_CONFIG", "configs/ingestion.yaml"),
        help="Path to ingestion configuration"
    )
    ing_parser.add_argument(
        "--db-path",
        default=os.getenv("INGESTION_DB_PATH", "artifacts/autotrader.db"),
        help="SQLite database path"
    )
    ing_parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("WORKER_POLL_INTERVAL", "900")),
        help="Poll interval in seconds"
    )
    ing_parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit"
    )
    ing_parser.set_defaults(func=cmd_ingestion)
    
    # Backtest worker
    bt_parser = subparsers.add_parser("backtest", help="Run backtest worker")
    bt_parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing feature data"
    )
    bt_parser.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated list of symbols"
    )
    bt_parser.add_argument(
        "--config",
        help="Path to backtest configuration (optional)"
    )
    bt_parser.set_defaults(func=cmd_backtest)
    
    # Optimization worker
    opt_parser = subparsers.add_parser("optimize", help="Run optimization worker")
    opt_parser.add_argument(
        "--data-dir",
        default="data/processed/features",
        help="Directory containing feature data"
    )
    opt_parser.add_argument(
        "--symbols",
        default="AAPL,MSFT,NVDA,BTCUSD,ETHUSD,EURUSD,GBPUSD",
        help="Comma-separated list of symbols"
    )
    opt_parser.add_argument(
        "--trials",
        type=int,
        default=50,
        help="Number of Optuna trials per symbol"
    )
    opt_parser.add_argument(
        "--splits",
        type=int,
        default=5,
        help="Number of cross-validation splits"
    )
    opt_parser.add_argument(
        "--output-dir",
        help="Output directory for results (default: reports/optuna)"
    )
    opt_parser.set_defaults(func=cmd_optimize)
    
    args = parser.parse_args(argv)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    # Execute command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
