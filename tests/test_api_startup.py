"""Lightweight checks around the FastAPI application boot process."""

from __future__ import annotations

import importlib
import logging
import sys
import types


def test_app_initializes_without_required_keys(monkeypatch, caplog):
    """Import the API without key env vars to ensure graceful degradation."""

    for key in ["GROQ_API_KEY", "ETHERSCAN_API_KEY", "COINGECKO_API_KEY"]:
        monkeypatch.delenv(key, raising=False)

    module_name = "src.api.main"
    monkeypatch.setitem(
        sys.modules,
        "dotenv",
        types.SimpleNamespace(load_dotenv=lambda *args, **kwargs: None),
    )

    fake_fastapi = types.ModuleType("fastapi")

    class _FakeRequest:  # noqa: D401 - simple placeholder for FastAPI Request
        """Minimal stand-in for fastapi.Request used during import."""

        def __init__(self, *args, **kwargs):  # noqa: D401 - accepts anything
            pass

    class _FakeFastAPI:
        def __init__(self, *args, **kwargs):
            self.state = types.SimpleNamespace()

        def add_exception_handler(self, *args, **kwargs):
            return None

        def add_middleware(self, *args, **kwargs):
            return None

        def include_router(self, *args, **kwargs):
            return None

        def middleware(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    fake_fastapi.FastAPI = _FakeFastAPI
    fake_fastapi.Request = _FakeRequest

    fake_fastapi_middleware = types.ModuleType("fastapi.middleware")
    fake_fastapi_middleware_cors = types.ModuleType("fastapi.middleware.cors")

    class _FakeCORSMiddleware:  # noqa: D401 - placeholder class
        pass

    fake_fastapi_middleware_cors.CORSMiddleware = _FakeCORSMiddleware

    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)
    monkeypatch.setitem(sys.modules, "fastapi.middleware", fake_fastapi_middleware)
    monkeypatch.setitem(
        sys.modules, "fastapi.middleware.cors", fake_fastapi_middleware_cors
    )

    fake_slowapi = types.ModuleType("slowapi")

    class _FakeLimiter:
        def __init__(self, *args, **kwargs):
            pass

        def limit(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def _fake_get_remote_address(*args, **kwargs):
        return "127.0.0.1"

    class _FakeRateLimitExceeded(Exception):
        pass

    fake_slowapi.Limiter = _FakeLimiter
    fake_slowapi._rate_limit_exceeded_handler = lambda *args, **kwargs: None

    fake_slowapi_errors = types.ModuleType("slowapi.errors")
    fake_slowapi_errors.RateLimitExceeded = _FakeRateLimitExceeded

    fake_slowapi_util = types.ModuleType("slowapi.util")
    fake_slowapi_util.get_remote_address = _fake_get_remote_address

    monkeypatch.setitem(sys.modules, "slowapi", fake_slowapi)
    monkeypatch.setitem(sys.modules, "slowapi.errors", fake_slowapi_errors)
    monkeypatch.setitem(sys.modules, "slowapi.util", fake_slowapi_util)

    fake_logging_config = types.ModuleType("src.core.logging_config")
    fake_logging_config.setup_structured_logging = lambda *args, **kwargs: logging.getLogger("autotrader-api")
    fake_logging_config.get_logger = lambda *args, **kwargs: logging.getLogger("autotrader-api")
    monkeypatch.setitem(sys.modules, "src.core.logging_config", fake_logging_config)

    fake_metrics = types.ModuleType("src.core.metrics")
    fake_metrics.record_api_request = lambda *args, **kwargs: None
    fake_metrics.record_api_duration = lambda *args, **kwargs: None
    fake_metrics.record_api_error = lambda *args, **kwargs: None

    class _FakeActiveRequestTracker:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_metrics.ActiveRequestTracker = _FakeActiveRequestTracker
    monkeypatch.setitem(sys.modules, "src.core.metrics", fake_metrics)

    fake_tracing = types.ModuleType("src.core.tracing")
    fake_tracing.setup_tracing = lambda *args, **kwargs: None
    fake_tracing.instrument_fastapi = lambda *args, **kwargs: None
    fake_tracing.get_trace_id = lambda *args, **kwargs: "trace-id"
    monkeypatch.setitem(sys.modules, "src.core.tracing", fake_tracing)

    fake_fastapi_middleware.cors = fake_fastapi_middleware_cors

    fake_routes_pkg = types.ModuleType("src.api.routes")
    fake_routes_pkg.__path__ = []  # Mark as package for dotted imports.
    fake_tokens_module = types.ModuleType("src.api.routes.tokens")
    fake_tokens_module.router = object()
    fake_health_module = types.ModuleType("src.api.routes.health")
    fake_health_module.router = object()
    fake_experiments_module = types.ModuleType("src.api.routes.experiments")
    fake_experiments_module.router = object()
    fake_monitoring_module = types.ModuleType("src.api.routes.monitoring")
    fake_monitoring_module.router = object()
    fake_scan_module = types.ModuleType("src.api.routes.scan")
    fake_scan_module.router = object()
    fake_bouncehunter_module = types.ModuleType("src.api.routes.bouncehunter")
    fake_bouncehunter_module.router = object()
    fake_llm_module = types.ModuleType("src.api.routes.llm")
    fake_llm_module.router = object()

    fake_routes_pkg.tokens = fake_tokens_module
    fake_routes_pkg.health = fake_health_module
    fake_routes_pkg.experiments = fake_experiments_module
    fake_routes_pkg.monitoring = fake_monitoring_module
    fake_routes_pkg.scan = fake_scan_module
    fake_routes_pkg.bouncehunter = fake_bouncehunter_module
    fake_routes_pkg.llm = fake_llm_module

    monkeypatch.setitem(sys.modules, "src.api.routes", fake_routes_pkg)
    monkeypatch.setitem(sys.modules, "src.api.routes.tokens", fake_tokens_module)
    monkeypatch.setitem(sys.modules, "src.api.routes.health", fake_health_module)
    monkeypatch.setitem(sys.modules, "src.api.routes.experiments", fake_experiments_module)
    monkeypatch.setitem(sys.modules, "src.api.routes.monitoring", fake_monitoring_module)
    monkeypatch.setitem(sys.modules, "src.api.routes.scan", fake_scan_module)
    monkeypatch.setitem(sys.modules, "src.api.routes.bouncehunter", fake_bouncehunter_module)
    monkeypatch.setitem(sys.modules, "src.api.routes.llm", fake_llm_module)
    sys.modules.pop(module_name, None)

    with caplog.at_level(logging.WARNING):
        module = importlib.import_module(module_name)

    assert hasattr(module, "app"), "FastAPI app should be created during import"

    messages = [record.getMessage() for record in caplog.records]

    assert any(
        "GROQ_API_KEY" in message and "disabled" in message.lower()
        for message in messages
    ), "LLM functionality warning should be emitted when GROQ_API_KEY is missing"

    assert any(
        "ETHERSCAN_API_KEY" in message and "unavailable" in message.lower()
        for message in messages
    ), "On-chain data warning should be emitted when ETHERSCAN_API_KEY is missing"

    assert any(
        "COINGECKO_API_KEY" in message and "rate" in message.lower()
        for message in messages
    ), "Optional CoinGecko warning should be emitted when the key is missing"
