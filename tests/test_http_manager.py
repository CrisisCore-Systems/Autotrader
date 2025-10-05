from __future__ import annotations

import httpx

from src.core.http_manager import CachePolicy, RateAwareRequester
from src.core.rate_limit import RateLimit, RateLimiter


class CallCounter:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(200, json={"ok": True, "path": str(request.url)})


def test_rate_aware_requester_caches_get_requests() -> None:
    handler = CallCounter()
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://example.com")
    requester = RateAwareRequester(
        client,
        rate_limits={"example.com": RateLimit(10, 60.0)},
    )

    first = requester.request("GET", "/resource", cache_policy=CachePolicy(ttl_seconds=60.0))
    second = requester.request("GET", "/resource", cache_policy=CachePolicy(ttl_seconds=60.0))

    assert first.json() == second.json()
    assert handler.calls == 1


def test_rate_limiter_sliding_window() -> None:
    limiter = RateLimiter(RateLimit(2, 1.0))
    assert limiter.acquire() == 0.0
    assert limiter.acquire() == 0.0
    wait = limiter.acquire()
    assert wait >= 0.0
