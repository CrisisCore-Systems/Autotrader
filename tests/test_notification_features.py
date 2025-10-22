"""Tests for notification rate limiting and deduplication."""

import pytest
import asyncio
from src.alerts.notifiers import (
    RateLimiter,
    DeduplicationCache,
    send_telegram,
    send_slack,
    send_webhook,
    get_rate_limiter,
    get_dedupe_cache,
)


@pytest.mark.asyncio
async def test_rate_limiter_allows_initial_requests():
    """Test that rate limiter allows requests under limit."""
    limiter = RateLimiter()
    
    # Should allow first request
    result = await limiter.acquire("test_channel")
    assert result is True
    
    # Should allow multiple requests under limit
    for _ in range(5):
        result = await limiter.acquire("test_channel")
        assert result is True


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_limit_reached():
    """Test that rate limiter blocks requests over limit."""
    limiter = RateLimiter()
    limiter._limits["test_channel"] = 3  # Set low limit for testing
    
    # Allow first 3 requests
    for _ in range(3):
        result = await limiter.acquire("test_channel")
        assert result is True
    
    # 4th request should be blocked
    result = await limiter.acquire("test_channel")
    assert result is False


@pytest.mark.asyncio
async def test_rate_limiter_wait_if_needed():
    """Test that wait_if_needed waits for rate limit to reset."""
    limiter = RateLimiter()
    limiter._limits["test_channel"] = 1
    
    # First request succeeds
    result = await limiter.wait_if_needed("test_channel", max_wait=0.1)
    assert result is True
    
    # Second request should timeout (we can't wait 60 seconds in a test)
    result = await limiter.wait_if_needed("test_channel", max_wait=0.1)
    assert result is False


@pytest.mark.asyncio
async def test_rate_limiter_separate_channels():
    """Test that rate limits are per-channel."""
    limiter = RateLimiter()
    limiter._limits["channel1"] = 1
    limiter._limits["channel2"] = 1
    
    # Both channels should allow first request
    result1 = await limiter.acquire("channel1")
    result2 = await limiter.acquire("channel2")
    assert result1 is True
    assert result2 is True
    
    # Both channels should block second request
    result1 = await limiter.acquire("channel1")
    result2 = await limiter.acquire("channel2")
    assert result1 is False
    assert result2 is False


def test_dedupe_cache_detects_duplicates():
    """Test that deduplication cache detects duplicate messages."""
    cache = DeduplicationCache(ttl_seconds=60)
    
    # First send should not be a duplicate
    is_dup = cache.is_duplicate("test_channel", "test message")
    assert is_dup is False
    
    # Second send of same message should be a duplicate
    is_dup = cache.is_duplicate("test_channel", "test message")
    assert is_dup is True


def test_dedupe_cache_different_messages():
    """Test that different messages are not considered duplicates."""
    cache = DeduplicationCache(ttl_seconds=60)
    
    # Send first message
    is_dup1 = cache.is_duplicate("test_channel", "message 1")
    assert is_dup1 is False
    
    # Send different message
    is_dup2 = cache.is_duplicate("test_channel", "message 2")
    assert is_dup2 is False


def test_dedupe_cache_different_channels():
    """Test that same message on different channels is not a duplicate."""
    cache = DeduplicationCache(ttl_seconds=60)
    
    # Send on channel 1
    is_dup1 = cache.is_duplicate("channel1", "test message")
    assert is_dup1 is False
    
    # Send on channel 2 (same message, different channel)
    is_dup2 = cache.is_duplicate("channel2", "test message")
    assert is_dup2 is False


def test_dedupe_cache_ttl():
    """Test that deduplication cache expires after TTL."""
    import time
    cache = DeduplicationCache(ttl_seconds=1)  # 1 second TTL
    
    # Send message
    is_dup1 = cache.is_duplicate("test_channel", "test message")
    assert is_dup1 is False
    
    # Immediately send again - should be duplicate
    is_dup2 = cache.is_duplicate("test_channel", "test message")
    assert is_dup2 is True
    
    # Wait for TTL to expire
    time.sleep(1.1)
    
    # Should not be duplicate anymore
    is_dup3 = cache.is_duplicate("test_channel", "test message")
    assert is_dup3 is False


@pytest.mark.asyncio
async def test_send_telegram_deduplication(monkeypatch):
    """Test that send_telegram deduplicates messages."""
    import os
    
    # Set fake credentials
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake_chat_id")
    
    # Mock httpx client
    class MockResponse:
        def raise_for_status(self):
            pass
    
    class MockClient:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, *args, **kwargs):
            return MockResponse()
    
    import httpx
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
    
    # Clear dedupe cache
    cache = get_dedupe_cache()
    cache._cache.clear()
    
    # First send should succeed
    success1, status1 = await send_telegram(
        "test message", 
        check_rate_limit=False,  # Disable rate limit for this test
        check_dedupe=True
    )
    assert success1 is True
    assert status1 == "sent"
    
    # Second send of same message should be deduplicated
    success2, status2 = await send_telegram(
        "test message",
        check_rate_limit=False,
        check_dedupe=True
    )
    assert success2 is False
    assert status2 == "deduplicated"


@pytest.mark.asyncio
async def test_send_slack_rate_limiting(monkeypatch):
    """Test that send_slack respects rate limits."""
    import os
    
    # Set fake webhook URL
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/fake")
    
    # Mock httpx client
    class MockResponse:
        def raise_for_status(self):
            pass
    
    class MockClient:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, *args, **kwargs):
            return MockResponse()
    
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
    
    # Set very low rate limit for testing
    limiter = get_rate_limiter()
    limiter._limits["slack"] = 1
    limiter._requests["slack"].clear()
    
    # First send should succeed
    success1, status1 = await send_slack(
        "message 1",
        check_rate_limit=True,
        check_dedupe=False  # Disable dedupe for this test
    )
    assert success1 is True
    assert status1 == "sent"
    
    # Second send should be rate limited
    success2, status2 = await send_slack(
        "message 2",
        check_rate_limit=True,
        check_dedupe=False
    )
    assert success2 is False
    assert status2 == "rate_limited"


@pytest.mark.asyncio
async def test_send_webhook_with_all_features(monkeypatch):
    """Test webhook sending with rate limiting and deduplication."""
    # Mock httpx client
    class MockResponse:
        def raise_for_status(self):
            pass
    
    class MockClient:
        async def __aenter__(self):
            return self
        
        async def __aexit__(self, *args):
            pass
        
        async def post(self, *args, **kwargs):
            return MockResponse()
    
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: MockClient())
    
    # Clear caches
    limiter = get_rate_limiter()
    limiter._requests["webhook"].clear()
    cache = get_dedupe_cache()
    cache._cache.clear()
    
    url = "https://example.com/webhook"
    payload = {"alert": "test"}
    
    # First send should succeed
    success1, status1 = await send_webhook(url, payload)
    assert success1 is True
    assert status1 == "sent"
    
    # Second send should be deduplicated
    success2, status2 = await send_webhook(url, payload)
    assert success2 is False
    assert status2 == "deduplicated"


def test_global_instances():
    """Test that global instances are accessible."""
    limiter = get_rate_limiter()
    assert limiter is not None
    assert isinstance(limiter, RateLimiter)
    
    cache = get_dedupe_cache()
    assert cache is not None
    assert isinstance(cache, DeduplicationCache)
