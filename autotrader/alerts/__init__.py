"""
Alert routing system for compliance violations.

Supports multiple notification channels:
- Telegram Bot (primary)
- Email (backup/reporting)
"""

from autotrader.alerts.router import AlertRouter, TelegramAdapter, EmailAdapter
from autotrader.alerts.config import AlertConfig, load_alert_config

__all__ = [
    'AlertRouter',
    'TelegramAdapter',
    'EmailAdapter',
    'AlertConfig',
    'load_alert_config',
]
