"""
Alert configuration management.

Loads alert settings from YAML config file.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

_ENV_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _default_config_path() -> Path:
    """Return the preferred alert config path."""
    root = Path(__file__).parent.parent.parent
    env_path = os.getenv("AUTOTRADER_ALERT_CONFIG")
    if env_path:
        return Path(env_path)

    local_config = root / "configs" / "alerts.local.yaml"
    if local_config.exists():
        return local_config

    return root / "configs" / "alerts.yaml"


def _resolve_config_value(
    value: Any,
    *,
    field_name: str,
    fallback_env_var: Optional[str] = None,
) -> Optional[str]:
    """Resolve config placeholders without committing secret values."""
    if value is None:
        return os.getenv(fallback_env_var) if fallback_env_var else None

    if not isinstance(value, str):
        return str(value)

    stripped = value.strip()
    placeholder = _ENV_PLACEHOLDER_RE.match(stripped)
    if placeholder:
        env_var = placeholder.group(1)
        env_value = os.getenv(env_var)
        if env_value:
            return env_value
        logger.warning("%s references unset environment variable %s", field_name, env_var)
        return None

    if stripped in {"", "YOUR_BOT_TOKEN_HERE", "YOUR_CHAT_ID_HERE"}:
        return os.getenv(fallback_env_var) if fallback_env_var else None

    return value


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str
    chat_id: str
    enabled: bool = True


@dataclass
class EmailConfig:
    """Email configuration."""
    smtp_host: str
    smtp_port: int
    from_addr: str
    to_addrs: list[str]
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = True
    enabled: bool = True


@dataclass
class AlertConfig:
    """Complete alert configuration."""
    telegram: Optional[TelegramConfig] = None
    email: Optional[EmailConfig] = None
    
    def is_configured(self) -> bool:
        """Check if at least one alert channel is configured."""
        return (
            (self.telegram and self.telegram.enabled) or
            (self.email and self.email.enabled)
        )


def load_alert_config(config_path: Optional[Path] = None) -> AlertConfig:
    """
    Load alert configuration from YAML file.
    
    Args:
        config_path: Path to config file (default: configs/alerts.yaml)
        
    Returns:
        AlertConfig object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if config_path is None:
        config_path = _default_config_path()
    
    if not config_path.exists():
        logger.warning(f"Alert config not found: {config_path}")
        return AlertConfig()
    
    try:
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        
        if not data:
            logger.warning("Empty alert config file")
            return AlertConfig()
        
        # Parse Telegram config
        telegram_config = None
        if 'telegram' in data and data['telegram'].get('enabled', True):
            bot_token = _resolve_config_value(
                data['telegram'].get('bot_token'),
                field_name="telegram.bot_token",
                fallback_env_var="TELEGRAM_BOT_TOKEN"
            )
            chat_id = _resolve_config_value(
                data['telegram'].get('chat_id'),
                field_name="telegram.chat_id",
                fallback_env_var="TELEGRAM_CHAT_ID"
            )
            if bot_token and chat_id:
                telegram_config = TelegramConfig(
                    bot_token=bot_token,
                    chat_id=chat_id,
                    enabled=data['telegram'].get('enabled', True)
                )
            else:
                logger.warning("Telegram alerts enabled but bot token or chat ID is missing")
        
        # Parse Email config
        email_config = None
        if 'email' in data and data['email'].get('enabled', True):
            email_config = EmailConfig(
                smtp_host=data['email']['smtp_host'],
                smtp_port=data['email']['smtp_port'],
                from_addr=data['email']['from_addr'],
                to_addrs=data['email']['to_addrs'],
                username=data['email'].get('username'),
                password=data['email'].get('password'),
                use_tls=data['email'].get('use_tls', True),
                enabled=data['email'].get('enabled', True)
            )
        
        config = AlertConfig(telegram=telegram_config, email=email_config)
        
        if not config.is_configured():
            logger.warning("No alert channels are enabled in config")
        
        return config
        
    except Exception as e:
        logger.error(f"Failed to load alert config: {e}")
        raise ValueError(f"Invalid alert config: {e}")


def create_example_config(output_path: Optional[Path] = None) -> Path:
    """
    Create an example alert configuration file.
    
    Args:
        output_path: Where to save the config (default: configs/alerts.example.yaml)
        
    Returns:
        Path to created config file
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent.parent / "configs" / "alerts.example.yaml"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    example_config = """# Alert Configuration
# This file configures how compliance alerts are routed to notification channels

# Telegram Bot Configuration
telegram:
  enabled: true
  
  # Get bot token from @BotFather on Telegram:
  # 1. Message @BotFather
  # 2. Send /newbot
  # 3. Follow prompts to create bot
  # 4. Copy the bot token
  bot_token: "${TELEGRAM_BOT_TOKEN}"
  
  # Get chat ID:
  # 1. Start a chat with your bot
  # 2. Send any message
  # 3. Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
  # 4. Look for "chat":{"id": YOUR_CHAT_ID}
  # OR use @userinfobot to get your user ID
  chat_id: "${TELEGRAM_CHAT_ID}"

# Email Configuration (Optional - for backup/reporting)
email:
  enabled: false
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  from_addr: "alerts@yourcompany.com"
  to_addrs:
    - "trader@yourcompany.com"
    - "compliance@yourcompany.com"
  
  # SMTP Authentication (optional)
  username: "your-email@gmail.com"
  password: "your-app-password"  # Use app-specific password for Gmail
  
  use_tls: true

# Routing Logic (automatically applied):
# - CRITICAL: Telegram (immediate) + Email (audit trail)
# - WARNING: Telegram (immediate)
# - INFO: Email (daily digest)
"""
    
    with open(output_path, 'w') as f:
        f.write(example_config)
    
    logger.info(f"Created example config: {output_path}")
    return output_path
