"""CLI entry point for sending BounceHunter alerts via Telegram."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from .config import BounceHunterConfig
from .telegram_bot import TelegramConfig, send_daily_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(config_path: Path) -> tuple[TelegramConfig, BounceHunterConfig]:
    """Load Telegram and scanner configuration from YAML file."""
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    telegram_data = data.get("telegram", {})
    bot_token = telegram_data.get("bot_token", "")
    chat_id = telegram_data.get("chat_id", "")

    if not bot_token or bot_token == "YOUR_BOT_TOKEN_HERE":
        logger.error("Bot token not configured in telegram.yaml")
        sys.exit(1)

    if not chat_id or chat_id == "YOUR_CHAT_ID_HERE":
        logger.error("Chat ID not configured in telegram.yaml")
        sys.exit(1)

    telegram_config = TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        parse_mode=telegram_data.get("parse_mode", "Markdown"),
        disable_notification=telegram_data.get("disable_notification", False),
    )

    scanner_data = data.get("scanner", {}) or {}

    # Build config with only provided overrides
    config_kwargs = {}
    if scanner_data.get("tickers"):
        config_kwargs["tickers"] = [t.strip() for t in scanner_data["tickers"].split(",")]

    # Map YAML keys to config fields
    field_map = {
        "start": "start",
        "min_adv_usd": "min_adv_usd",
        "z_drop": "z_score_drop",
        "rsi2_max": "rsi2_max",
        "dist200_min": "max_dist_200dma",
        "bcs_threshold": "bcs_threshold",
        "bcs_threshold_highvix": "bcs_threshold_highvix",
        "rebound": "rebound_pct",
        "stop": "stop_pct",
        "horizon": "horizon_days",
        "earnings_window": "earnings_window_days",
        "skip_earnings_for_etfs": "skip_earnings_for_etfs",
        "vix_lookback_days": "vix_lookback_days",
        "highvix_percentile": "highvix_percentile",
        "spy_stress_multiplier": "spy_stress_multiplier",
        "size_pct_base": "size_pct_base",
        "size_pct_highvix": "size_pct_highvix",
        "max_concurrent": "max_concurrent",
        "max_per_sector": "max_per_sector",
    }

    for yaml_key, config_key in field_map.items():
        if yaml_key in scanner_data:
            config_kwargs[config_key] = scanner_data[yaml_key]

    if "allow_earnings" in scanner_data:
        config_kwargs["skip_earnings"] = not scanner_data["allow_earnings"]

    scanner_config = BounceHunterConfig(**config_kwargs)

    return telegram_config, scanner_config


def main(argv: list[str] | None = None) -> int:
    """Run the Telegram alert bot."""
    parser = argparse.ArgumentParser(
        description="Send BounceHunter signals to Telegram"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/telegram.yaml"),
        help="Path to telegram.yaml configuration file",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test connection without sending signals",
    )

    args = parser.parse_args(argv)

    try:
        telegram_config, scanner_config = load_config(args.config)
    except Exception as exc:
        logger.error(f"Failed to load configuration: {exc}")
        return 1

    if args.test:
        from .telegram_bot import TelegramNotifier

        notifier = TelegramNotifier(telegram_config)
        if notifier.test_connection():
            logger.info("✓ Connection test successful")
            return 0
        logger.error("✗ Connection test failed")
        return 1

    try:
        send_daily_scan(telegram_config, scanner_config)
        return 0
    except Exception as exc:
        logger.error(f"Failed to send daily scan: {exc}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
