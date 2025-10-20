"""Telegram notification service for BounceHunter signals."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import requests

from .config import BounceHunterConfig
from .engine import BounceHunter

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TelegramConfig:
    """Configuration for Telegram bot integration."""

    bot_token: str
    chat_id: str
    parse_mode: str = "Markdown"
    disable_notification: bool = False


class TelegramNotifier:
    """Send BounceHunter signals to Telegram chats."""

    def __init__(self, telegram_config: TelegramConfig) -> None:
        self.config = telegram_config
        self.api_base = f"https://api.telegram.org/bot{self.config.bot_token}"

    def send_signals(
        self,
        signals: pd.DataFrame,
        as_of_date: pd.Timestamp,
        tickers_scanned: int,
        historical_stats: tuple[int, int],  # (wins, total_events)
        config: Optional[BounceHunterConfig] = None,
    ) -> bool:
        """Format and send signal report to configured Telegram chat."""
        message = self._format_message(signals, as_of_date, tickers_scanned, historical_stats, config)
        return self._send_message(message)

    def _format_message(
        self,
        signals: pd.DataFrame,
        as_of_date: pd.Timestamp,
        tickers_scanned: int,
        historical_stats: tuple[int, int],
        config: Optional[BounceHunterConfig] = None,
    ) -> str:
        """Build a markdown-formatted message for Telegram."""
        cfg = config or BounceHunterConfig()
        historical_wins, historical_events = historical_stats
        lines = [
            "🎯 *BounceHunter Signals*",
            f"Date: `{as_of_date.date()}`",
            "",
        ]

        if signals.empty:
            lines.append("✅ No qualifying signals today")
            lines.append("")
            lines.append(f"_Scanned {tickers_scanned} tickers_")
            return "\n".join(lines)

        lines.append(f"Found *{len(signals)}* signals:")
        lines.append("")

        for _, signal in signals.iterrows():
            ticker = signal["ticker"]
            prob = signal["probability"]
            entry = signal["entry"]
            stop = signal["stop"]
            target = signal["target"]
            z_score = signal.get("z_score", 0)
            rsi2 = signal.get("rsi2", 0)

            risk_reward = (target - entry) / (entry - stop)
            notes = signal.get("notes", "")

            lines.append(f"*{ticker}*")
            lines.append(f"├ Probability: `{prob:.1%}`")
            lines.append(f"├ Entry: `${entry:.2f}`")
            lines.append(f"├ Stop: `${stop:.2f}` (-{cfg.stop_pct:.1%})")
            lines.append(f"├ Target: `${target:.2f}` (+{cfg.rebound_pct:.1%})")
            lines.append(f"├ R:R: `{risk_reward:.1f}x`")
            lines.append(f"├ Z-score: `{z_score:.2f}` | RSI2: `{rsi2:.1f}`")
            if notes:
                lines.append(f"└ ⚠️ _{notes}_")
            else:
                lines.append("└ ✓")
            lines.append("")

        lines.append("─" * 30)
        lines.append(f"_Scanned {tickers_scanned} tickers_")
        base_rate = historical_wins / historical_events if historical_events > 0 else 0
        lines.append(
            f"_Historical win rate: {base_rate:.1%} "
            f"({historical_wins}/{historical_events} events)_"
        )

        return "\n".join(lines)

    def _send_message(self, text: str) -> bool:
        """Send a text message via Telegram Bot API."""
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "parse_mode": self.config.parse_mode,
            "disable_notification": self.config.disable_notification,
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Telegram message sent successfully")
            return True
        except requests.RequestException as exc:
            logger.error(f"Failed to send Telegram message: {exc}")
            if hasattr(exc, 'response') and exc.response is not None:
                logger.error(f"Response body: {exc.response.text}")
            return False

    def test_connection(self) -> bool:
        """Verify bot token and chat access."""
        url = f"{self.api_base}/getMe"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            bot_info = response.json()
            if bot_info.get("ok"):
                username = bot_info["result"]["username"]
                logger.info(f"Connected to bot @{username}")
                return True
            logger.error("Bot token validation failed")
            return False
        except requests.RequestException as exc:
            logger.error(f"Connection test failed: {exc}")
            return False


def send_daily_scan(
    telegram_config: TelegramConfig,
    bouncer_config: Optional[BounceHunterConfig] = None,
) -> None:
    """Run a scan and send results to Telegram (cron-friendly entry point)."""
    cfg = bouncer_config or BounceHunterConfig()
    notifier = TelegramNotifier(telegram_config)

    logger.info("Running BounceHunter scan...")
    hunter = BounceHunter(cfg)
    hunter.fit()
    reports = hunter.scan()

    # Aggregate signals from all ticker reports
    all_signals = []
    total_scanned = 0
    total_events = 0
    total_wins = 0
    as_of_date = pd.Timestamp.now()

    for report in reports:
        all_signals.append(report.as_dict())
        total_scanned += 1
        as_of_date = pd.Timestamp(report.date)

    # Get historical stats from artifacts
    for artifact in hunter._artifacts.values():
        if hasattr(artifact, 'features'):
            total_events += len(artifact.features)
            total_wins += artifact.features['label'].sum()

    signals_df = pd.DataFrame(all_signals) if all_signals else pd.DataFrame()

    logger.info(f"Scan complete: {len(signals_df)} signals")
    notifier.send_signals(signals_df, as_of_date, total_scanned, (total_wins, total_events), cfg)
