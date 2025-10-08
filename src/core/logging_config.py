"""Structured logging configuration with JSON output.

This module provides centralized logging setup with:
- JSON-formatted structured logs
- Correlation IDs for request tracing
- Context injection (service, environment, version)
- Standard fields for log aggregation
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Optional

import structlog
from pythonjsonlogger import jsonlogger


class StructuredLogger:
    """Structured logger with context management."""
    
    def __init__(self, logger: structlog.BoundLogger):
        """Initialize structured logger.
        
        Args:
            logger: Bound structlog logger
        """
        self._logger = logger
        self._context: Dict[str, Any] = {}
    
    def bind(self, **context: Any) -> StructuredLogger:
        """Bind context to logger.
        
        Args:
            **context: Context key-value pairs
            
        Returns:
            Logger with bound context
        """
        new_logger = StructuredLogger(self._logger.bind(**context))
        new_logger._context = {**self._context, **context}
        return new_logger
    
    def unbind(self, *keys: str) -> StructuredLogger:
        """Remove context keys.
        
        Args:
            *keys: Context keys to remove
            
        Returns:
            Logger with unbound context
        """
        new_logger = StructuredLogger(self._logger.unbind(*keys))
        new_context = {k: v for k, v in self._context.items() if k not in keys}
        new_logger._context = new_context
        return new_logger
    
    def debug(self, event: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._logger.debug(event, **kwargs)
    
    def info(self, event: str, **kwargs: Any) -> None:
        """Log info message."""
        self._logger.info(event, **kwargs)
    
    def warning(self, event: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._logger.warning(event, **kwargs)
    
    def error(self, event: str, **kwargs: Any) -> None:
        """Log error message."""
        self._logger.error(event, **kwargs)
    
    def critical(self, event: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._logger.critical(event, **kwargs)
    
    def exception(self, event: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._logger.exception(event, **kwargs)


def setup_structured_logging(
    service_name: str = "autotrader",
    environment: Optional[str] = None,
    version: Optional[str] = None,
    level: str = "INFO",
    enable_console: bool = True,
    enable_json: bool = True,
) -> StructuredLogger:
    """Configure structured JSON logging for the application.
    
    Args:
        service_name: Name of the service
        environment: Environment (dev, staging, prod)
        version: Service version
        level: Logging level
        enable_console: Enable console output
        enable_json: Enable JSON formatting
        
    Returns:
        Configured structured logger
    """
    # Determine environment if not provided
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")
    
    # Determine version if not provided
    if version is None:
        version = os.getenv("APP_VERSION", "0.1.0")
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Add JSON renderer if enabled
    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    if enable_console and enable_json:
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            rename_fields={
                "levelname": "level",
                "name": "logger",
                "asctime": "timestamp",
            }
        )
        handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.handlers = []  # Clear existing handlers
        root_logger.addHandler(handler)
        root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Create base logger with service context
    logger = structlog.get_logger(service_name)
    structured_logger = StructuredLogger(logger).bind(
        service=service_name,
        environment=environment,
        version=version,
    )
    
    return structured_logger


def get_logger(name: str, **context: Any) -> StructuredLogger:
    """Get a logger with optional context binding.
    
    Args:
        name: Logger name (typically __name__)
        **context: Optional context to bind
        
    Returns:
        Structured logger instance
    """
    logger = structlog.get_logger(name)
    structured_logger = StructuredLogger(logger)
    
    if context:
        structured_logger = structured_logger.bind(**context)
    
    return structured_logger


# Context manager for request correlation
class LogContext:
    """Context manager for scoped logging context."""
    
    def __init__(self, logger: StructuredLogger, **context: Any):
        """Initialize log context.
        
        Args:
            logger: Base logger
            **context: Context to bind
        """
        self._base_logger = logger
        self._context = context
        self._scoped_logger: Optional[StructuredLogger] = None
    
    def __enter__(self) -> StructuredLogger:
        """Enter context and return scoped logger."""
        self._scoped_logger = self._base_logger.bind(**self._context)
        return self._scoped_logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        pass


# Initialize global logger (can be reconfigured)
_global_logger: Optional[StructuredLogger] = None


def init_logging(
    service_name: str = "autotrader",
    level: str = "INFO",
) -> StructuredLogger:
    """Initialize global logging configuration.
    
    Args:
        service_name: Name of the service
        level: Logging level
        
    Returns:
        Global structured logger
    """
    global _global_logger
    _global_logger = setup_structured_logging(
        service_name=service_name,
        level=level,
    )
    return _global_logger


def get_global_logger() -> StructuredLogger:
    """Get the global logger instance.
    
    Returns:
        Global structured logger
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = init_logging()
    return _global_logger
