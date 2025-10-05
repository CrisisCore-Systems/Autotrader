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
        limiter = self._limiter_for(absolute_url)
        cache_key = None
        use_cache = method_upper == "GET" and cache_policy is not None
        if use_cache:
            cache_key = cache_policy.cache_key or self._build_cache_key(method_upper, absolute_url, kwargs)
            cached = self._cache.get(cache_key)
            if cached is not None:
                return self._response_from_cache(method_upper, absolute_url, cached)

        attempt = 0
        while True:
            if limiter:
                sleep_for = limiter.acquire()
                if sleep_for > 0:
                    time.sleep(sleep_for)
            try:
                response = self._client.request(method_upper, url, **kwargs)
            except httpx.HTTPError:
                if attempt >= self._max_retries:
                    raise
                self._sleep_backoff(attempt)
                attempt += 1
                continue

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt >= self._max_retries:
                    response.raise_for_status()
                retry_after = self._retry_after_seconds(response)
                backoff = max(retry_after, self._backoff_delay(attempt))
                time.sleep(min(backoff, self._backoff_max))
                attempt += 1
                continue

            response.raise_for_status()
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
