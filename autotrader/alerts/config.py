"""
Alert configuration management.

Loads alert settings from YAML config file.
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


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
        # Default to configs/alerts.yaml
        config_path = Path(__file__).parent.parent.parent / "configs" / "alerts.yaml"
    
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
            telegram_config = TelegramConfig(
                bot_token=data['telegram']['bot_token'],
                chat_id=data['telegram']['chat_id'],
                enabled=data['telegram'].get('enabled', True)
            )
        
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
  bot_token: "YOUR_BOT_TOKEN_HERE"
  
  # Get chat ID:
  # 1. Start a chat with your bot
  # 2. Send any message
  # 3. Visit: https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
  # 4. Look for "chat":{"id": YOUR_CHAT_ID}
  # OR use @userinfobot to get your user ID
  chat_id: "YOUR_CHAT_ID_HERE"

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
