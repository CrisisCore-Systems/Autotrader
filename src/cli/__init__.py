"""Enhanced CLI module for AutoTrader.

Provides production-ready CLI features:
- Config resolution (YAML → argparse → env vars)
- Metrics emission (stdout JSON lines, StatsD)
- Runtime watchdog and concurrency locks
- Plugin strategy loading via entry points
- Deterministic mode for reproducibility
- Comprehensive exit codes
- Structured logging (text/JSON)
- Output validation (JSON schema)
- Dry-run mode
"""

from src.cli.config import (
    ConfigError,
    load_yaml_config,
    resolve_config,
    validate_output_schema,
)
from src.cli.deterministic import (
    enable_deterministic_mode,
    log_deterministic_environment,
)
from src.cli.exit_codes import (
    ExitCode,
    print_exit_codes,
    get_category_for_exception,
)
from src.cli.metrics import (
    initialize_metrics,
    get_collector,
    shutdown_metrics,
    MetricsCollector,
)
from src.cli.plugins import (
    load_strategy,
    list_strategies,
    create_strategy_instance,
    StrategyError,
)
from src.cli.runtime import (
    create_lock,
    create_watchdog,
    FileLock,
    LockError,
    Watchdog,
    WatchdogTimeout,
)
from src.cli.worker import main as worker_main

__all__ = [
    # Config
    'ConfigError',
    'load_yaml_config',
    'resolve_config',
    'validate_output_schema',
    # Deterministic
    'enable_deterministic_mode',
    'log_deterministic_environment',
    # Exit codes
    'ExitCode',
    'print_exit_codes',
    'get_category_for_exception',
    # Metrics
    'initialize_metrics',
    'get_collector',
    'shutdown_metrics',
    'MetricsCollector',
    # Plugins
    'load_strategy',
    'list_strategies',
    'create_strategy_instance',
    'StrategyError',
    # Runtime
    'create_lock',
    'create_watchdog',
    'FileLock',
    'LockError',
    'Watchdog',
    'WatchdogTimeout',
    # Worker
    'worker_main',
]

__version__ = '0.1.0'
