"""Rate-aware HTTP client helpers with caching and retries."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Dict, Mapping, Optional
from urllib.parse import urlparse

import httpx

from src.core.rate_limit import RateLimit, RateLimiter
from src.core.logging_config import get_logger
from src.core.metrics import (
    record_data_source_request,
    record_data_source_latency,
    record_data_source_error,
    record_cache_hit,
    record_cache_miss,
)
from src.core.tracing import trace_operation, add_span_attributes

try:  # pragma: no cover - optional dependency
    import redis
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    redis = None  # type: ignore


class CacheBackend:
    """Minimal cache backend protocol."""

    def get(self, key: str) -> Optional[bytes]:
        raise NotImplementedError

    def set(self, key: str, value: bytes, ttl: float) -> None:
        raise NotImplementedError


class InMemoryCache(CacheBackend):
    """Thread-safe in-memory cache with TTL support."""

    def __init__(self) -> None:
        self._store: Dict[str, tuple[float, bytes]] = {}

    def get(self, key: str) -> Optional[bytes]:
        entry = self._store.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return payload

    def set(self, key: str, value: bytes, ttl: float) -> None:
        self._store[key] = (time.time() + ttl, value)


class RedisCache(CacheBackend):
    """Redis-backed cache compatible with the cache protocol."""

    def __init__(self, client: "redis.Redis") -> None:  # type: ignore[name-defined]
        self._client = client

    def get(self, key: str) -> Optional[bytes]:
        value = self._client.get(key)
        return value if isinstance(value, bytes) else None

    def set(self, key: str, value: bytes, ttl: float) -> None:
        self._client.setex(key, int(ttl), value)


@dataclass
class CachePolicy:
    ttl_seconds: float = 300.0
    cache_key: str | None = None


class RateAwareRequester:
    """Wrapper around :class:`httpx.Client` with rate limits, caching, and retries."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        rate_limits: Mapping[str, RateLimit] | None = None,
        default_limit: RateLimit | None = None,
        cache_backend: CacheBackend | None = None,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
        backoff_max: float = 30.0,
    ) -> None:
        self._client = client
        self._limits = {host: RateLimiter(limit) for host, limit in (rate_limits or {}).items()}
        self._default_limit = RateLimiter(default_limit) if default_limit else None
        self._cache = cache_backend or InMemoryCache()
        self._max_retries = max(0, int(max_retries))
        self._backoff_factor = max(0.5, float(backoff_factor))
        self._backoff_max = max(1.0, float(backoff_max))
        self._logger = get_logger(__name__)

    def request(
        self,
        method: str,
        url: str,
        *,
        cache_policy: CachePolicy | None = None,
        **kwargs: object,
    ) -> httpx.Response:
        method_upper = method.upper()
        absolute_url = self._absolute_url(url)
        parsed_url = urlparse(absolute_url)
        source = parsed_url.netloc or "unknown"
        endpoint = parsed_url.path or "/"
        
        # Start tracing the request
        with trace_operation(
            "http_request",
            attributes={
                "http.method": method_upper,
                "http.url": absolute_url,
                "http.source": source,
            }
        ) as span:
            start_time = time.time()
            limiter = self._limiter_for(absolute_url)
            cache_key = None
            use_cache = method_upper == "GET" and cache_policy is not None
            
            # Check cache
            if use_cache:
                cache_key = cache_policy.cache_key or self._build_cache_key(method_upper, absolute_url, kwargs)
                cached = self._cache.get(cache_key)
                if cached is not None:
                    duration = time.time() - start_time
                    record_cache_hit(source, endpoint)
                    record_data_source_latency(source, endpoint, duration)
                    add_span_attributes(cache_hit=True)
                    self._logger.debug(
                        "http_request_cache_hit",
                        method=method_upper,
                        url=absolute_url,
                        source=source,
                        endpoint=endpoint,
                        duration_seconds=duration,
                    )
                    return self._response_from_cache(method_upper, absolute_url, cached)
                else:
                    record_cache_miss(source, endpoint)
                    add_span_attributes(cache_hit=False)

            attempt = 0
            last_error = None
            
            while True:
                if limiter:
                    sleep_for = limiter.acquire()
                    if sleep_for > 0:
                        self._logger.debug(
                            "rate_limit_sleep",
                            source=source,
                            sleep_seconds=sleep_for,
                        )
                        time.sleep(sleep_for)
                
                try:
                    response = self._client.request(method_upper, url, **kwargs)
                except httpx.HTTPError as e:
                    last_error = e
                    error_type = type(e).__name__
                    
                    if attempt >= self._max_retries:
                        duration = time.time() - start_time
                        record_data_source_error(source, endpoint, error_type)
                        record_data_source_request(source, endpoint, "error")
                        record_data_source_latency(source, endpoint, duration)
                        add_span_attributes(
                            error=True,
                            error_type=error_type,
                            attempts=attempt + 1,
                        )
                        self._logger.error(
                            "http_request_failed",
                            method=method_upper,
                            url=absolute_url,
                            source=source,
                            endpoint=endpoint,
                            error_type=error_type,
                            attempts=attempt + 1,
                            duration_seconds=duration,
                            exc_info=e,
                        )
                        raise
                    
                    self._logger.warning(
                        "http_request_retry",
                        method=method_upper,
                        url=absolute_url,
                        source=source,
                        error_type=error_type,
                        attempt=attempt + 1,
                        max_retries=self._max_retries,
                    )
                    self._sleep_backoff(attempt)
                    attempt += 1
                    continue

                if response.status_code in {429, 500, 502, 503, 504}:
                    if attempt >= self._max_retries:
                        duration = time.time() - start_time
                        error_type = f"http_{response.status_code}"
                        record_data_source_error(source, endpoint, error_type)
                        record_data_source_request(source, endpoint, "error")
                        record_data_source_latency(source, endpoint, duration)
                        add_span_attributes(
                            error=True,
                            error_type=error_type,
                            http_status_code=response.status_code,
                            attempts=attempt + 1,
                        )
                        self._logger.error(
                            "http_request_failed_status",
                            method=method_upper,
                            url=absolute_url,
                            source=source,
                            endpoint=endpoint,
                            status_code=response.status_code,
                            attempts=attempt + 1,
                            duration_seconds=duration,
                        )
                        response.raise_for_status()
                    
                    retry_after = self._retry_after_seconds(response)
                    backoff = max(retry_after, self._backoff_delay(attempt))
                    sleep_time = min(backoff, self._backoff_max)
                    
                    self._logger.warning(
                        "http_request_retry_status",
                        method=method_upper,
                        url=absolute_url,
                        source=source,
                        status_code=response.status_code,
                        attempt=attempt + 1,
                        retry_after_seconds=sleep_time,
                    )
                    time.sleep(sleep_time)
                    attempt += 1
                    continue

                # Success
                response.raise_for_status()
                duration = time.time() - start_time
                
                # Record metrics
                record_data_source_request(source, endpoint, "success")
                record_data_source_latency(source, endpoint, duration)
                add_span_attributes(
                    http_status_code=response.status_code,
                    attempts=attempt + 1,
                    response_size_bytes=len(response.content),
                )
                
                self._logger.info(
                    "http_request_success",
                    method=method_upper,
                    url=absolute_url,
                    source=source,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    duration_seconds=duration,
                    attempts=attempt + 1,
                    response_size_bytes=len(response.content),
                )
                
                # Cache the response if applicable
                if use_cache and cache_key:
                    ttl = cache_policy.ttl_seconds if cache_policy else 0.0
                    if ttl > 0:
                        payload = json.dumps(
                            {
                                "status": response.status_code,
                                "headers": dict(response.headers),
                                "content": response.content.decode("latin1"),
                                "url": absolute_url,
                            }
                        ).encode("utf-8")
                        self._cache.set(cache_key, payload, ttl)
                        self._logger.debug(
                            "http_response_cached",
                            url=absolute_url,
                            ttl_seconds=ttl,
                        )
                
                return response

    def _limiter_for(self, url: str) -> RateLimiter | None:
        host = urlparse(url).netloc or ""
        if host in self._limits:
            return self._limits[host]
        return self._default_limit

    def _absolute_url(self, url: str) -> str:
        if not url:
            return str(self._client.base_url)
        base = str(self._client.base_url)
        if not base:
            return url
        try:
            return str(httpx.URL(base).join(url))
        except Exception:
            return url

    @staticmethod
    def _build_cache_key(method: str, url: str, kwargs: Mapping[str, object]) -> str:
        normalized = json.dumps({"method": method, "url": url, "kwargs": kwargs}, sort_keys=True, default=str)
        return sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _response_from_cache(method: str, url: str, payload: bytes) -> httpx.Response:
        decoded = json.loads(payload.decode("utf-8"))
        content = decoded.get("content", "").encode("latin1")
        status = int(decoded.get("status", 200))
        headers = decoded.get("headers", {})
        
        # Remove content-encoding header to prevent double decompression
        # since httpx automatically decompresses responses
        headers = {k: v for k, v in headers.items() if k.lower() != "content-encoding"}
        
        request = httpx.Request(method, decoded.get("url", url))
        return httpx.Response(status, content=content, headers=headers, request=request)

    def _sleep_backoff(self, attempt: int) -> None:
        time.sleep(min(self._backoff_delay(attempt), self._backoff_max))

    def _backoff_delay(self, attempt: int) -> float:
        return (self._backoff_factor ** (attempt + 1))

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return 0.0
        try:
            return float(retry_after)
        except ValueError:
            return 0.0


def build_cache_backend(config: Mapping[str, object] | None = None) -> CacheBackend:
    """Factory that creates a cache backend from configuration."""

    if config is None:
        return InMemoryCache()
    backend = (config.get("backend") if isinstance(config, Mapping) else None) or "memory"
    backend = str(backend).lower()
    if backend == "redis":
        if redis is None:
            raise RuntimeError("redis backend requested but redis package is not installed")
        url = str(config.get("url") if isinstance(config, Mapping) else "redis://localhost:6379/0")
        client = redis.Redis.from_url(url)
        return RedisCache(client)
    return InMemoryCache()


__all__ = [
    "CachePolicy",
    "CacheBackend",
    "InMemoryCache",
    "RedisCache",
    "RateAwareRequester",
    "build_cache_backend",
]
