"""Notification transports for GemScore alerts with rate limiting and deduplication."""

from __future__ import annotations

import asyncio
import hashlib
import os
import smtplib
import time
from collections import defaultdict
from email.message import EmailMessage
from typing import Dict, Mapping, MutableMapping, Protocol, Tuple

import httpx


class RateLimiter:
    """Rate limiter for notifications per channel."""
    
    def __init__(self):
        # Track (channel, timestamp) tuples for rate limiting
        self._requests: Dict[str, list[float]] = defaultdict(list)
        # Rate limits per channel (requests per minute)
        self._limits = {
            "telegram": 20,  # Telegram allows ~30/min, we use 20 to be safe
            "slack": 10,     # Slack recommends ~1/sec, we use 10/min
            "email": 30,     # Conservative limit for SMTP
            "webhook": 60,   # Generic webhook limit
        }
    
    async def acquire(self, channel: str) -> bool:
        """Check if we can send to this channel now.
        
        Returns True if allowed, False if rate limited.
        """
        now = time.time()
        limit = self._limits.get(channel, 10)
        
        # Clean up old requests (older than 60 seconds)
        self._requests[channel] = [
            ts for ts in self._requests[channel] if now - ts < 60
        ]
        
        # Check if we're under the limit
        if len(self._requests[channel]) < limit:
            self._requests[channel].append(now)
            return True
        
        return False
    
    async def wait_if_needed(self, channel: str, max_wait: float = 5.0) -> bool:
        """Wait if rate limited, up to max_wait seconds.
        
        Returns True if acquired, False if timeout.
        """
        start = time.time()
        while time.time() - start < max_wait:
            if await self.acquire(channel):
                return True
            await asyncio.sleep(0.1)
        return False


class DeduplicationCache:
    """Cache for deduplicating alerts."""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, float] = {}
        self._ttl = ttl_seconds
    
    def _make_key(self, channel: str, message: str) -> str:
        """Create a hash key for the message."""
        content = f"{channel}:{message}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def is_duplicate(self, channel: str, message: str) -> bool:
        """Check if this message was recently sent.
        
        Returns True if duplicate (should suppress).
        """
        now = time.time()
        key = self._make_key(channel, message)
        
        # Clean up expired entries
        self._cache = {
            k: ts for k, ts in self._cache.items() if now - ts < self._ttl
        }
        
        # Check if duplicate
        if key in self._cache:
            return True
        
        # Mark as sent
        self._cache[key] = now
        return False


# Global instances
_rate_limiter = RateLimiter()
_dedupe_cache = DeduplicationCache(ttl_seconds=3600)


class Notifier(Protocol):
    async def send(self, payload: Mapping[str, object]) -> None:  # pragma: no cover - interface
        ...


async def send_telegram(
    message: str,
    *,
    token: str | None = None,
    chat_id: str | None = None,
    check_rate_limit: bool = True,
    check_dedupe: bool = True,
) -> Tuple[bool, str]:
    """Send a Telegram message with rate limiting and deduplication.
    
    Returns (success, status_message).
    """
    # Check for duplicates
    if check_dedupe and _dedupe_cache.is_duplicate("telegram", message):
        return False, "deduplicated"
    
    # Check rate limit
    if check_rate_limit:
        allowed = await _rate_limiter.wait_if_needed("telegram", max_wait=5.0)
        if not allowed:
            return False, "rate_limited"
    
    try:
        token = token or os.environ["TELEGRAM_BOT_TOKEN"]
        chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": message,
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()
            return True, "sent"
    except Exception as e:
        return False, f"error: {str(e)}"


async def send_slack(
    message: str,
    *,
    webhook_url: str | None = None,
    check_rate_limit: bool = True,
    check_dedupe: bool = True,
) -> Tuple[bool, str]:
    """Send a Slack message with rate limiting and deduplication.
    
    Returns (success, status_message).
    """
    # Check for duplicates
    if check_dedupe and _dedupe_cache.is_duplicate("slack", message):
        return False, "deduplicated"
    
    # Check rate limit
    if check_rate_limit:
        allowed = await _rate_limiter.wait_if_needed("slack", max_wait=5.0)
        if not allowed:
            return False, "rate_limited"
    
    try:
        webhook_url = webhook_url or os.environ["SLACK_WEBHOOK_URL"]
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json={"text": message})
            response.raise_for_status()
            return True, "sent"
    except Exception as e:
        return False, f"error: {str(e)}"


async def send_email(
    *,
    subject: str,
    body: str,
    to: str,
    sender: str | None = None,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    check_rate_limit: bool = True,
    check_dedupe: bool = True,
) -> Tuple[bool, str]:
    """Send an email with rate limiting and deduplication.
    
    Returns (success, status_message).
    """
    message_content = f"{subject}\n{body}"
    
    # Check for duplicates
    if check_dedupe and _dedupe_cache.is_duplicate("email", message_content):
        return False, "deduplicated"
    
    # Check rate limit
    if check_rate_limit:
        allowed = await _rate_limiter.wait_if_needed("email", max_wait=5.0)
        if not allowed:
            return False, "rate_limited"
    
    try:
        sender = sender or os.environ.get("ALERT_EMAIL_FROM", "alerts@example.com")
        host = host or os.environ.get("SMTP_HOST", "localhost")
        port = port or int(os.environ.get("SMTP_PORT", "25"))
        username = username or os.environ.get("SMTP_USERNAME")
        password = password or os.environ.get("SMTP_PASSWORD")

        message = EmailMessage()
        message["From"] = sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _send_email_sync,
            host,
            port,
            sender,
            to,
            message,
            username,
            password,
        )
        return True, "sent"
    except Exception as e:
        return False, f"error: {str(e)}"


def _send_email_sync(
    host: str,
    port: int,
    sender: str,
    to: str,
    message: EmailMessage,
    username: str | None,
    password: str | None,
) -> None:
    with smtplib.SMTP(host, port, timeout=10) as client:
        if username and password:
            client.starttls()
            client.login(username, password)
        client.send_message(message, from_addr=sender, to_addrs=[to])


async def send_webhook(
    url: str,
    payload: Dict,
    *,
    check_rate_limit: bool = True,
    check_dedupe: bool = True,
) -> Tuple[bool, str]:
    """Send a webhook POST request with rate limiting and deduplication.
    
    Returns (success, status_message).
    """
    message_content = f"{url}:{str(payload)}"
    
    # Check for duplicates
    if check_dedupe and _dedupe_cache.is_duplicate("webhook", message_content):
        return False, "deduplicated"
    
    # Check rate limit
    if check_rate_limit:
        allowed = await _rate_limiter.wait_if_needed("webhook", max_wait=5.0)
        if not allowed:
            return False, "rate_limited"
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return True, "sent"
    except Exception as e:
        return False, f"error: {str(e)}"


def render_markdown(payload: Mapping[str, object]) -> str:
    parts: MutableMapping[str, object] = dict(payload)
    lines = [f"**Alert:** {parts.pop('rule', 'unknown')} ({parts.pop('symbol', '')})"]
    for key, value in sorted(parts.items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _rate_limiter


def get_dedupe_cache() -> DeduplicationCache:
    """Get the global deduplication cache instance."""
    return _dedupe_cache


__all__ = [
    "Notifier",
    "RateLimiter",
    "DeduplicationCache",
    "render_markdown",
    "send_email",
    "send_slack",
    "send_telegram",
    "send_webhook",
    "get_rate_limiter",
    "get_dedupe_cache",
]
