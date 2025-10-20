"""Notification transports for GemScore alerts."""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.message import EmailMessage
from typing import Mapping, MutableMapping, Protocol

import httpx


class Notifier(Protocol):
    async def send(self, payload: Mapping[str, object]) -> None:  # pragma: no cover - interface
        ...


async def send_telegram(message: str, *, token: str | None = None, chat_id: str | None = None) -> None:
    token = token or os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": message,
                "disable_web_page_preview": True,
            },
        )


async def send_slack(message: str, *, webhook_url: str | None = None) -> None:
    webhook_url = webhook_url or os.environ["SLACK_WEBHOOK_URL"]
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(webhook_url, json={"text": message})


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
) -> None:
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


def render_markdown(payload: Mapping[str, object]) -> str:
    parts: MutableMapping[str, object] = dict(payload)
    lines = [f"**Alert:** {parts.pop('rule', 'unknown')} ({parts.pop('symbol', '')})"]
    for key, value in sorted(parts.items()):
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


__all__ = [
    "Notifier",
    "render_markdown",
    "send_email",
    "send_slack",
    "send_telegram",
]
