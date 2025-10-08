"""Distributed tracing configuration using OpenTelemetry.

This module provides distributed tracing setup for:
- Request/response tracing across services
- Span creation and context propagation
- Trace sampling and export
- Integration with structured logging
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SpanExporter,
    )
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.trace import Status, StatusCode, Span
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    ConsoleSpanExporter = None  # type: ignore
    SpanExporter = None  # type: ignore
    Resource = None  # type: ignore
    SERVICE_NAME = None  # type: ignore
    FastAPIInstrumentor = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    Span = None  # type: ignore


class MockSpan:
    """Mock span for when OpenTelemetry is not available."""
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Mock set_attribute."""
        pass
    
    def set_status(self, status: Any) -> None:
        """Mock set_status."""
        pass
    
    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        """Mock add_event."""
        pass
    
    def record_exception(self, exception: Exception) -> None:
        """Mock record_exception."""
        pass


class MockTracer:
    """Mock tracer for when OpenTelemetry is not available."""
    
    def start_as_current_span(self, name: str, **kwargs) -> MockSpan:
        """Mock start_as_current_span."""
        return MockSpan()


_global_tracer: Optional[Any] = None


def setup_tracing(
    service_name: str = "autotrader",
    environment: Optional[str] = None,
    exporter: Optional[Any] = None,
    enable_console_export: bool = True,
) -> Any:
    """Setup OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service
        environment: Environment (dev, staging, prod)
        exporter: Custom span exporter (defaults to console)
        enable_console_export: Enable console export for debugging
        
    Returns:
        Configured tracer instance
    """
    if not OPENTELEMETRY_AVAILABLE:
        return MockTracer()
    
    # Determine environment if not provided
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")
    
    # Create resource with service information
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "environment": environment,
        "version": os.getenv("APP_VERSION", "0.1.0"),
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Add span processors
    if enable_console_export:
        console_processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(console_processor)
    
    if exporter is not None:
        custom_processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(custom_processor)
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    # Get tracer
    tracer = trace.get_tracer(service_name)
    
    global _global_tracer
    _global_tracer = tracer
    
    return tracer


def get_tracer(name: Optional[str] = None) -> Any:
    """Get a tracer instance.
    
    Args:
        name: Optional tracer name (defaults to global tracer)
        
    Returns:
        Tracer instance
    """
    if not OPENTELEMETRY_AVAILABLE:
        return MockTracer()
    
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = setup_tracing()
    
    if name:
        return trace.get_tracer(name)
    
    return _global_tracer


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: Optional[dict] = None,
    tracer: Optional[Any] = None,
):
    """Context manager for tracing operations.
    
    Args:
        operation_name: Name of the operation
        attributes: Optional attributes to attach to span
        tracer: Optional tracer (uses global if not provided)
        
    Yields:
        Span instance
    """
    if tracer is None:
        tracer = get_tracer()
    
    if not OPENTELEMETRY_AVAILABLE:
        yield MockSpan()
        return
    
    with tracer.start_as_current_span(operation_name) as span:
        # Add attributes
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        try:
            yield span
        except Exception as e:
            # Record exception in span
            span.set_status(Status(StatusCode.ERROR))
            span.record_exception(e)
            raise


def trace_function(operation_name: Optional[str] = None):
    """Decorator for tracing function calls.
    
    Args:
        operation_name: Optional operation name (defaults to function name)
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        def wrapper(*args, **kwargs):
            with trace_operation(op_name):
                return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


async def trace_async_function(operation_name: Optional[str] = None):
    """Decorator for tracing async function calls.
    
    Args:
        operation_name: Optional operation name (defaults to function name)
        
    Returns:
        Decorated async function
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or f"{func.__module__}.{func.__name__}"
        
        async def wrapper(*args, **kwargs):
            with trace_operation(op_name):
                return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def add_span_attributes(**attributes: Any) -> None:
    """Add attributes to the current span.
    
    Args:
        **attributes: Attributes to add
    """
    if not OPENTELEMETRY_AVAILABLE:
        return
    
    current_span = trace.get_current_span()
    if current_span:
        for key, value in attributes.items():
            current_span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[dict] = None) -> None:
    """Add an event to the current span.
    
    Args:
        name: Event name
        attributes: Optional event attributes
    """
    if not OPENTELEMETRY_AVAILABLE:
        return
    
    current_span = trace.get_current_span()
    if current_span:
        current_span.add_event(name, attributes=attributes or {})


def record_exception(exception: Exception) -> None:
    """Record an exception in the current span.
    
    Args:
        exception: Exception to record
    """
    if not OPENTELEMETRY_AVAILABLE:
        return
    
    current_span = trace.get_current_span()
    if current_span:
        current_span.set_status(Status(StatusCode.ERROR))
        current_span.record_exception(exception)


def instrument_fastapi(app: Any) -> None:
    """Instrument FastAPI application with OpenTelemetry.
    
    Args:
        app: FastAPI application instance
    """
    if not OPENTELEMETRY_AVAILABLE:
        return
    
    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        # Fail gracefully if instrumentation fails
        pass


def is_tracing_available() -> bool:
    """Check if OpenTelemetry tracing is available.
    
    Returns:
        True if opentelemetry is installed
    """
    return OPENTELEMETRY_AVAILABLE


# Trace context helpers
def get_current_span() -> Any:
    """Get the current active span.
    
    Returns:
        Current span or mock span
    """
    if not OPENTELEMETRY_AVAILABLE:
        return MockSpan()
    
    return trace.get_current_span()


def get_trace_id() -> Optional[str]:
    """Get the current trace ID.
    
    Returns:
        Trace ID as hex string or None
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None
    
    current_span = trace.get_current_span()
    if current_span:
        ctx = current_span.get_span_context()
        if ctx:
            return format(ctx.trace_id, '032x')
    
    return None


def get_span_id() -> Optional[str]:
    """Get the current span ID.
    
    Returns:
        Span ID as hex string or None
    """
    if not OPENTELEMETRY_AVAILABLE:
        return None
    
    current_span = trace.get_current_span()
    if current_span:
        ctx = current_span.get_span_context()
        if ctx:
            return format(ctx.span_id, '016x')
    
    return None
