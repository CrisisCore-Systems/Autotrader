"""Alert notification channels for microstructure detection signals."""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import aiohttp

from src.core.logging_config import get_logger
from src.microstructure.detector import DetectionSignal

logger = get_logger(__name__)


class AlertPriority(Enum):
    """Alert priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AlertConfig:
    """Configuration for alert channels."""

    # Slack configuration
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#trading-alerts"
    slack_username: str = "Microstructure Bot"

    # Discord configuration
    discord_webhook_url: Optional[str] = None
    discord_username: str = "Microstructure Bot"

    # Telegram configuration
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Alert filtering
    min_score: float = 0.5  # Minimum score to trigger alert
    cooldown_seconds: float = 60.0  # Cooldown between alerts for same symbol

    # Rate limiting
    max_alerts_per_minute: int = 10
    max_alerts_per_hour: int = 100


class AlertChannel(ABC):
    """Base class for alert channels."""

    def __init__(self, config: AlertConfig):
        """Initialize alert channel."""
        self.config = config
        self.last_alert_time: Dict[str, float] = {}
        self.alerts_sent = 0

    @abstractmethod
    async def send_alert(
        self,
        signal: DetectionSignal,
        priority: AlertPriority = AlertPriority.MEDIUM,
    ) -> bool:
        """
        Send alert through this channel.

        Returns:
            True if alert was sent successfully, False otherwise
        """
        pass

    def should_send_alert(self, signal: DetectionSignal) -> bool:
        """Check if alert should be sent based on filters."""
        # Check score threshold
        if signal.score < self.config.min_score:
            return False

        # Check cooldown
        symbol = signal.metadata.get("symbol", "unknown")
        last_alert = self.last_alert_time.get(symbol, 0)
        if time.time() - last_alert < self.config.cooldown_seconds:
            return False

        return True

    def record_alert(self, symbol: str) -> None:
        """Record that an alert was sent."""
        self.last_alert_time[symbol] = time.time()
        self.alerts_sent += 1

    def format_signal_message(self, signal: DetectionSignal) -> str:
        """Format signal into readable message."""
        symbol = signal.metadata.get("symbol", "unknown")
        signal_id = signal.metadata.get("signal_id", "unknown")
        signal_emoji = "🟢" if signal.signal_type == "buy_imbalance" else "🔴"

        message_lines = [
            f"{signal_emoji} **Microstructure Signal Detected**",
            f"",
            f"**Symbol:** {symbol}",
            f"**Type:** {signal.signal_type.replace('_', ' ').title()}",
            f"**Score:** {signal.score:.3f}",
            f"**Time:** {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(signal.timestamp))}",
        ]

        # Add key features if available
        if signal.features:
            message_lines.append("")
            message_lines.append("**Key Features:**")

            if "book_imbalance_top5" in signal.features:
                imb = signal.features["book_imbalance_top5"]
                message_lines.append(f"• Book Imbalance (top 5): {imb:.3f}")

            if "trade_imbalance_1s" in signal.features:
                imb = signal.features["trade_imbalance_1s"]
                message_lines.append(f"• Trade Imbalance (1s): {imb:.3f}")

            if "volume_burst" in signal.features:
                burst = signal.features["volume_burst"]
                message_lines.append(f"• Volume Burst: {burst:.2f}σ")

        message_lines.append("")
        message_lines.append(f"_Signal ID: {signal_id}_")

        return "\n".join(message_lines)


class SlackChannel(AlertChannel):
    """Slack webhook alert channel."""

    async def send_alert(
        self,
        signal: DetectionSignal,
        priority: AlertPriority = AlertPriority.MEDIUM,
    ) -> bool:
        """Send alert to Slack."""
        if not self.config.slack_webhook_url:
            logger.warning("slack_webhook_not_configured")
            return False

        if not self.should_send_alert(signal):
            return False

        try:
            # Format message
            message = self.format_signal_message(signal)

            # Determine color based on priority
            color_map = {
                AlertPriority.LOW: "#36a64f",  # Green
                AlertPriority.MEDIUM: "#ff9900",  # Orange
                AlertPriority.HIGH: "#ff0000",  # Red
                AlertPriority.CRITICAL: "#990000",  # Dark red
            }

            payload = {
                "channel": self.config.slack_channel,
                "username": self.config.slack_username,
                "attachments": [
                    {
                        "color": color_map.get(priority, "#36a64f"),
                        "text": message,
                        "mrkdwn_in": ["text"],
                        "footer": "Microstructure Detection System",
                        "ts": int(signal.timestamp),
                    }
                ],
            }

            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.slack_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5.0),
                ) as response:
                    if response.status == 200:
                        symbol = signal.metadata.get("symbol", "unknown")
                        self.record_alert(symbol)

                        logger.info(
                            "slack_alert_sent",
                            signal_id=signal.metadata.get("signal_id", "unknown"),
                            symbol=symbol,
                        )
                        return True
                    else:
                        logger.error(
                            "slack_alert_failed",
                            status=response.status,
                            response=await response.text(),
                        )
                        return False

        except Exception as e:
            logger.error("slack_alert_error", error=str(e), exc_info=True)
            return False


class DiscordChannel(AlertChannel):
    """Discord webhook alert channel."""

    async def send_alert(
        self,
        signal: DetectionSignal,
        priority: AlertPriority = AlertPriority.MEDIUM,
    ) -> bool:
        """Send alert to Discord."""
        if not self.config.discord_webhook_url:
            logger.warning("discord_webhook_not_configured")
            return False

        if not self.should_send_alert(signal):
            return False

        try:
            # Format message
            message = self.format_signal_message(signal)

            # Determine embed color based on priority
            color_map = {
                AlertPriority.LOW: 0x36A64F,  # Green
                AlertPriority.MEDIUM: 0xFF9900,  # Orange
                AlertPriority.HIGH: 0xFF0000,  # Red
                AlertPriority.CRITICAL: 0x990000,  # Dark red
            }

            payload = {
                "username": self.config.discord_username,
                "embeds": [
                    {
                        "title": "🎯 Microstructure Signal",
                        "description": message,
                        "color": color_map.get(priority, 0x36A64F),
                        "timestamp": time.strftime(
                            "%Y-%m-%dT%H:%M:%S.000Z",
                            time.gmtime(signal.timestamp),
                        ),
                        "footer": {
                            "text": "Microstructure Detection System"
                        },
                    }
                ],
            }

            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config.discord_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5.0),
                ) as response:
                    if response.status in (200, 204):
                        symbol = signal.metadata.get("symbol", "unknown")
                        self.record_alert(symbol)

                        logger.info(
                            "discord_alert_sent",
                            signal_id=signal.metadata.get("signal_id", "unknown"),
                            symbol=symbol,
                        )
                        return True
                    else:
                        logger.error(
                            "discord_alert_failed",
                            status=response.status,
                            response=await response.text(),
                        )
                        return False

        except Exception as e:
            logger.error("discord_alert_error", error=str(e), exc_info=True)
            return False


class TelegramChannel(AlertChannel):
    """Telegram bot alert channel."""

    async def send_alert(
        self,
        signal: DetectionSignal,
        priority: AlertPriority = AlertPriority.MEDIUM,
    ) -> bool:
        """Send alert to Telegram."""
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            logger.warning("telegram_not_configured")
            return False

        if not self.should_send_alert(signal):
            return False

        try:
            # Format message (Telegram uses Markdown)
            message = self.format_signal_message(signal)

            # Add priority indicator
            priority_emoji = {
                AlertPriority.LOW: "ℹ️",
                AlertPriority.MEDIUM: "⚠️",
                AlertPriority.HIGH: "🚨",
                AlertPriority.CRITICAL: "🔥",
            }

            message = f"{priority_emoji.get(priority, 'ℹ️')} {message}"

            # Build API URL
            api_url = (
                f"https://api.telegram.org/bot{self.config.telegram_bot_token}"
                f"/sendMessage"
            )

            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }

            # Send message
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    api_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5.0),
                ) as response:
                    result = await response.json()

                    if result.get("ok"):
                        symbol = signal.metadata.get("symbol", "unknown")
                        self.record_alert(symbol)

                        logger.info(
                            "telegram_alert_sent",
                            signal_id=signal.metadata.get("signal_id", "unknown"),
                            symbol=symbol,
                        )
                        return True
                    else:
                        logger.error(
                            "telegram_alert_failed",
                            error=result.get("description"),
                        )
                        return False

        except Exception as e:
            logger.error("telegram_alert_error", error=str(e), exc_info=True)
            return False


class AlertManager:
    """Manages multiple alert channels and rate limiting."""

    def __init__(self, config: AlertConfig):
        """Initialize alert manager."""
        self.config = config
        self.channels: List[AlertChannel] = []

        # Initialize configured channels
        if config.slack_webhook_url:
            self.channels.append(SlackChannel(config))
            logger.info("slack_channel_enabled")

        if config.discord_webhook_url:
            self.channels.append(DiscordChannel(config))
            logger.info("discord_channel_enabled")

        if config.telegram_bot_token and config.telegram_chat_id:
            self.channels.append(TelegramChannel(config))
            logger.info("telegram_channel_enabled")

        # Rate limiting
        self.alert_timestamps: List[float] = []

    def check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = time.time()

        # Clean old timestamps
        self.alert_timestamps = [
            ts for ts in self.alert_timestamps if now - ts < 3600
        ]

        # Check per-hour limit
        if len(self.alert_timestamps) >= self.config.max_alerts_per_hour:
            logger.warning("alert_rate_limit_hourly_exceeded")
            return False

        # Check per-minute limit
        recent_alerts = [
            ts for ts in self.alert_timestamps if now - ts < 60
        ]
        if len(recent_alerts) >= self.config.max_alerts_per_minute:
            logger.warning("alert_rate_limit_minute_exceeded")
            return False

        return True

    async def send_alert(
        self,
        signal: DetectionSignal,
        priority: AlertPriority = AlertPriority.MEDIUM,
    ) -> Dict[str, bool]:
        """
        Send alert through all configured channels.

        Returns:
            Dict mapping channel name to success status
        """
        if not self.channels:
            logger.warning("no_alert_channels_configured")
            return {}

        # Check rate limit
        if not self.check_rate_limit():
            return {
                channel.__class__.__name__: False
                for channel in self.channels
            }

        # Send to all channels concurrently
        tasks = [
            channel.send_alert(signal, priority)
            for channel in self.channels
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Record timestamp if any succeeded
        if any(r is True for r in results):
            self.alert_timestamps.append(time.time())

        # Build result dict
        result_dict = {}
        for channel, result in zip(self.channels, results):
            channel_name = channel.__class__.__name__
            if isinstance(result, Exception):
                logger.error(
                    "channel_alert_exception",
                    channel=channel_name,
                    error=str(result),
                )
                result_dict[channel_name] = False
            else:
                result_dict[channel_name] = bool(result)

        return result_dict

    def get_stats(self) -> Dict:
        """Get alerting statistics."""
        return {
            "channels_configured": len(self.channels),
            "total_alerts_sent": sum(c.alerts_sent for c in self.channels),
            "alerts_by_channel": {
                c.__class__.__name__: c.alerts_sent
                for c in self.channels
            },
            "recent_alerts": len(self.alert_timestamps),
        }
