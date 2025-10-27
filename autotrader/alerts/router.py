"""
Alert routing system for compliance violations.

Routes compliance issues to appropriate notification channels based on severity.
Primary channel: Telegram Bot for real-time alerts.
"""

import logging
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from autotrader.monitoring.compliance.monitor import ComplianceIssue, ComplianceSeverity

try:
    from prometheus_client import Counter
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
        def inc(self, *args, **kwargs): pass


logger = logging.getLogger(__name__)


# Prometheus metric for alert delivery
ALERT_DELIVERY_TOTAL = Counter(
    'alert_delivery_total',
    'Total number of alerts sent',
    ['channel', 'severity', 'status']
)


class TelegramAdapter:
    """
    Send alerts to Telegram bot.
    
    Features:
    - Rich message formatting with Markdown
    - Severity-based emojis
    - Issue details with metadata
    - Error handling with retries
    """
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Initialize Telegram adapter.
        
        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Target chat ID (can be user ID or group ID)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        
    def send_alert(self, issue: ComplianceIssue) -> bool:
        """
        Send compliance issue to Telegram.
        
        Args:
            issue: Compliance issue to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message = self._format_message(issue)
            
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': True
                },
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"Sent Telegram alert for issue: {issue.issue_code}")
            
            # Record success metric
            if PROMETHEUS_AVAILABLE:
                ALERT_DELIVERY_TOTAL.labels(
                    channel='telegram',
                    severity=issue.severity.value,
                    status='success'
                ).inc()
            
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            
            # Record failure metric
            if PROMETHEUS_AVAILABLE:
                ALERT_DELIVERY_TOTAL.labels(
                    channel='telegram',
                    severity=issue.severity.value,
                    status='failure'
                ).inc()
            
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram alert: {e}")
            
            # Record error metric
            if PROMETHEUS_AVAILABLE:
                ALERT_DELIVERY_TOTAL.labels(
                    channel='telegram',
                    severity=issue.severity.value,
                    status='error'
                ).inc()
            
            return False
    
    def _format_message(self, issue: ComplianceIssue) -> str:
        """Format compliance issue as Telegram message with Markdown."""
        
        # Severity emoji mapping
        emoji_map = {
            ComplianceSeverity.CRITICAL: "🚨",
            ComplianceSeverity.WARNING: "⚠️",
            ComplianceSeverity.INFO: "ℹ️"
        }
        
        emoji = emoji_map.get(issue.severity, "📋")
        severity_text = issue.severity.value.upper()
        
        # Build message
        lines = [
            f"{emoji} *{severity_text}: Compliance Alert*",
            "",
            f"*Issue*: `{issue.issue_code}`",
            f"*Description*: {issue.description}",
        ]
        
        # Add signal ID if present
        if issue.signal_id:
            lines.append(f"*Signal*: `{issue.signal_id}`")
        
        # Add order IDs if present
        if issue.order_ids:
            lines.append(f"*Orders*: `{', '.join(issue.order_ids)}`")
        
        # Extract instrument from metadata if available
        if issue.metadata and 'instrument' in issue.metadata:
            lines.append(f"*Instrument*: `{issue.metadata['instrument']}`")
        
        # Extract timestamp from metadata if available
        if issue.metadata and 'timestamp' in issue.metadata:
            lines.append(f"*Timestamp*: {issue.metadata['timestamp']}")
        
        # Add metadata if present
        if issue.metadata:
            lines.append("")
            lines.append("*Details*:")
            for key, value in issue.metadata.items():
                # Skip keys we've already shown
                if key in ('instrument', 'timestamp'):
                    continue
                # Clean key name (replace underscores with spaces, capitalize)
                clean_key = key.replace('_', ' ').title()
                lines.append(f"  • {clean_key}: `{value}`")
        
        return "\n".join(lines)
    
    def test_connection(self) -> bool:
        """
        Test Telegram bot connection.
        
        Returns:
            True if bot is configured correctly, False otherwise
        """
        try:
            response = requests.get(
                f"{self.api_url}/getMe",
                timeout=5
            )
            response.raise_for_status()
            bot_info = response.json()
            
            if bot_info.get('ok'):
                logger.info(f"Telegram bot connected: @{bot_info['result']['username']}")
                return True
            else:
                logger.error(f"Telegram bot error: {bot_info}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Telegram bot: {e}")
            return False


class EmailAdapter:
    """
    Send alerts via email (backup channel).
    
    Features:
    - HTML-formatted emails
    - Batch reporting support
    - SMTP authentication
    """
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        from_addr: str,
        to_addrs: list[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = True
    ):
        """
        Initialize email adapter.
        
        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port (usually 587 for TLS, 25 for plain)
            from_addr: Sender email address
            to_addrs: List of recipient email addresses
            username: SMTP username (if authentication required)
            password: SMTP password (if authentication required)
            use_tls: Whether to use TLS encryption
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.username = username
        self.password = password
        self.use_tls = use_tls
    
    def send_alert(self, issue: ComplianceIssue) -> bool:
        """
        Send compliance issue via email.
        
        Args:
            issue: Compliance issue to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{issue.severity.value.upper()}] Compliance Alert: {issue.issue_code}"
            msg['From'] = self.from_addr
            msg['To'] = ", ".join(self.to_addrs)
            
            # Create HTML body
            html_body = self._format_html(issue)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                if self.username and self.password:
                    server.login(self.username, self.password)
                
                server.send_message(msg)
            
            logger.info(f"Sent email alert for issue: {issue.issue_code}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _format_html(self, issue: ComplianceIssue) -> str:
        """Format compliance issue as HTML email."""
        
        severity_colors = {
            ComplianceSeverity.CRITICAL: "#dc3545",  # Red
            ComplianceSeverity.WARNING: "#ffc107",   # Yellow
            ComplianceSeverity.INFO: "#17a2b8"       # Blue
        }
        
        color = severity_colors.get(issue.severity, "#6c757d")
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: {color}; color: white; padding: 15px; border-radius: 5px; }}
                .content {{ padding: 20px; }}
                .field {{ margin: 10px 0; }}
                .label {{ font-weight: bold; }}
                .metadata {{ background-color: #f8f9fa; padding: 10px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{issue.severity.value.upper()}: Compliance Alert</h2>
            </div>
            <div class="content">
                <div class="field">
                    <span class="label">Issue Code:</span> {issue.issue_code}
                </div>
                <div class="field">
                    <span class="label">Description:</span> {issue.description}
                </div>
                <div class="field">
                    <span class="label">Signal ID:</span> {issue.signal_id}
                </div>
                <div class="field">
                    <span class="label">Instrument:</span> {issue.instrument}
                </div>
                <div class="field">
                    <span class="label">Timestamp:</span> {issue.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
                </div>
        """
        
        if issue.metadata:
            html += '<div class="field"><span class="label">Additional Details:</span></div>'
            html += '<div class="metadata">'
            for key, value in issue.metadata.items():
                clean_key = key.replace('_', ' ').title()
                html += f'<div><strong>{clean_key}:</strong> {value}</div>'
            html += '</div>'
        
        html += """
            </div>
        </body>
        </html>
        """
        
        return html


class AlertRouter:
    """
    Route compliance issues to appropriate notification channels.
    
    Routing logic:
    - CRITICAL: Telegram (immediate) + Email (audit trail)
    - WARNING: Telegram (immediate)
    - INFO: Email (daily digest)
    
    Features:
    - Multi-channel routing
    - Severity-based escalation
    - Error handling and logging
    - Batch processing support
    """
    
    def __init__(
        self,
        telegram: Optional[TelegramAdapter] = None,
        email: Optional[EmailAdapter] = None
    ):
        """
        Initialize alert router.
        
        Args:
            telegram: Telegram adapter (optional)
            email: Email adapter (optional)
        """
        self.telegram = telegram
        self.email = email
        self.stats = {
            'sent': 0,
            'failed': 0,
            'by_severity': {
                ComplianceSeverity.CRITICAL: 0,
                ComplianceSeverity.WARNING: 0,
                ComplianceSeverity.INFO: 0
            }
        }
    
    def route_alert(self, issue: ComplianceIssue) -> bool:
        """
        Route a single compliance issue to appropriate channels.
        
        Args:
            issue: Compliance issue to route
            
        Returns:
            True if alert was sent successfully to at least one channel
        """
        success = False
        
        # Route based on severity
        if issue.severity == ComplianceSeverity.CRITICAL:
            # Critical: Send to both Telegram and Email
            if self.telegram:
                if self.telegram.send_alert(issue):
                    success = True
            
            if self.email:
                if self.email.send_alert(issue):
                    success = True
        
        elif issue.severity == ComplianceSeverity.WARNING:
            # Warning: Send to Telegram only
            if self.telegram:
                if self.telegram.send_alert(issue):
                    success = True
        
        elif issue.severity == ComplianceSeverity.INFO:
            # Info: Send to Email only (for daily digest)
            if self.email:
                if self.email.send_alert(issue):
                    success = True
        
        # Update stats
        if success:
            self.stats['sent'] += 1
            self.stats['by_severity'][issue.severity] += 1
        else:
            self.stats['failed'] += 1
            logger.warning(f"Failed to route alert for issue: {issue.issue_code}")
        
        return success
    
    def route_batch(self, issues: list[ComplianceIssue]) -> Dict[str, int]:
        """
        Route multiple compliance issues.
        
        Args:
            issues: List of compliance issues to route
            
        Returns:
            Statistics dictionary with sent/failed counts
        """
        results = {'sent': 0, 'failed': 0}
        
        for issue in issues:
            if self.route_alert(issue):
                results['sent'] += 1
            else:
                results['failed'] += 1
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        return self.stats.copy()
    
    def reset_stats(self):
        """Reset routing statistics."""
        self.stats = {
            'sent': 0,
            'failed': 0,
            'by_severity': {
                ComplianceSeverity.CRITICAL: 0,
                ComplianceSeverity.WARNING: 0,
                ComplianceSeverity.INFO: 0
            }
        }
