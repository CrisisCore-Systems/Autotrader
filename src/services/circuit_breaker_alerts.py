"""Alert system for circuit breaker state changes."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class CircuitBreakerAlert:
    """Alert for circuit breaker state change."""

    breaker_name: str
    old_state: str
    new_state: str
    severity: AlertSeverity
    timestamp: datetime
    failure_count: int = 0
    message: str = ""
    metadata: Dict[str, any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert alert to dictionary."""
        return {
            "breaker_name": self.breaker_name,
            "old_state": self.old_state,
            "new_state": self.new_state,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "failure_count": self.failure_count,
            "message": self.message,
            "metadata": self.metadata,
        }


class CircuitBreakerAlertManager:
    """Manages circuit breaker alerts and notifications."""

    def __init__(self) -> None:
        """Initialize alert manager."""
        self._handlers: List[Callable[[CircuitBreakerAlert], None]] = []
        self._alert_history: List[CircuitBreakerAlert] = []
        self._max_history_size = 100

    def register_handler(
        self, handler: Callable[[CircuitBreakerAlert], None]
    ) -> None:
        """Register an alert handler.

        Args:
            handler: Callable that receives CircuitBreakerAlert
        """
        if handler not in self._handlers:
            self._handlers.append(handler)

    def unregister_handler(
        self, handler: Callable[[CircuitBreakerAlert], None]
    ) -> None:
        """Unregister an alert handler.

        Args:
            handler: Handler to remove
        """
        if handler in self._handlers:
            self._handlers.remove(handler)

    def send_alert(self, alert: CircuitBreakerAlert) -> None:
        """Send alert to all registered handlers.

        Args:
            alert: Alert to send
        """
        # Store in history
        self._alert_history.append(alert)
        if len(self._alert_history) > self._max_history_size:
            self._alert_history.pop(0)

        # Send to handlers
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"Error in alert handler: {e}")

    def get_alert_history(
        self, limit: Optional[int] = None
    ) -> List[CircuitBreakerAlert]:
        """Get recent alert history.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent alerts
        """
        if limit:
            return self._alert_history[-limit:]
        return list(self._alert_history)

    def clear_history(self) -> None:
        """Clear alert history."""
        self._alert_history.clear()

    def create_open_hook(self) -> Callable[[str], None]:
        """Create alert hook for circuit breaker open events.

        Returns:
            Callable that can be used as CircuitBreakerConfig.on_open
        """
        def on_open(breaker_name: str) -> None:
            alert = CircuitBreakerAlert(
                breaker_name=breaker_name,
                old_state="CLOSED",
                new_state="OPEN",
                severity=AlertSeverity.CRITICAL,
                timestamp=datetime.utcnow(),
                message=f"Circuit breaker '{breaker_name}' opened due to repeated failures",
            )
            self.send_alert(alert)

        return on_open

    def create_half_open_hook(self) -> Callable[[str], None]:
        """Create alert hook for circuit breaker half-open events.

        Returns:
            Callable that can be used as CircuitBreakerConfig.on_half_open
        """
        def on_half_open(breaker_name: str) -> None:
            alert = CircuitBreakerAlert(
                breaker_name=breaker_name,
                old_state="OPEN",
                new_state="HALF_OPEN",
                severity=AlertSeverity.WARNING,
                timestamp=datetime.utcnow(),
                message=f"Circuit breaker '{breaker_name}' attempting recovery",
            )
            self.send_alert(alert)

        return on_half_open

    def create_close_hook(self) -> Callable[[str], None]:
        """Create alert hook for circuit breaker close events.

        Returns:
            Callable that can be used as CircuitBreakerConfig.on_close
        """
        def on_close(breaker_name: str) -> None:
            alert = CircuitBreakerAlert(
                breaker_name=breaker_name,
                old_state="HALF_OPEN",
                new_state="CLOSED",
                severity=AlertSeverity.INFO,
                timestamp=datetime.utcnow(),
                message=f"Circuit breaker '{breaker_name}' recovered - service is healthy",
            )
            self.send_alert(alert)

        return on_close


# Global alert manager instance
_global_alert_manager = CircuitBreakerAlertManager()


def get_alert_manager() -> CircuitBreakerAlertManager:
    """Get global circuit breaker alert manager.

    Returns:
        Global alert manager instance
    """
    return _global_alert_manager


# Example handlers
def log_alert_handler(alert: CircuitBreakerAlert) -> None:
    """Example handler that logs alerts to stdout.

    Args:
        alert: Alert to log
    """
    print(
        f"[{alert.severity.value.upper()}] {alert.timestamp.isoformat()} - "
        f"{alert.message} (breaker: {alert.breaker_name}, "
        f"state: {alert.old_state} -> {alert.new_state})"
    )


def webhook_alert_handler(webhook_url: str) -> Callable[[CircuitBreakerAlert], None]:
    """Create a handler that sends alerts to a webhook.

    Args:
        webhook_url: URL to send POST requests to

    Returns:
        Handler function
    """
    def handler(alert: CircuitBreakerAlert) -> None:
        try:
            import requests
            response = requests.post(
                webhook_url,
                json=alert.to_dict(),
                timeout=5.0
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send webhook alert: {e}")

    return handler


def email_alert_handler(
    smtp_host: str,
    smtp_port: int,
    from_addr: str,
    to_addrs: List[str],
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> Callable[[CircuitBreakerAlert], None]:
    """Create a handler that sends email alerts.

    Args:
        smtp_host: SMTP server hostname
        smtp_port: SMTP server port
        from_addr: Sender email address
        to_addrs: List of recipient email addresses
        username: SMTP username (optional)
        password: SMTP password (optional)

    Returns:
        Handler function
    """
    def handler(alert: CircuitBreakerAlert) -> None:
        try:
            import smtplib
            from email.mime.text import MIMEText

            subject = f"Circuit Breaker Alert: {alert.breaker_name} - {alert.severity.value.upper()}"
            body = f"""
Circuit Breaker State Change Alert

Breaker: {alert.breaker_name}
Old State: {alert.old_state}
New State: {alert.new_state}
Severity: {alert.severity.value.upper()}
Timestamp: {alert.timestamp.isoformat()}
Failure Count: {alert.failure_count}

Message: {alert.message}

This is an automated alert from the AutoTrader reliability monitoring system.
            """.strip()

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = ", ".join(to_addrs)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if username and password:
                    server.starttls()
                    server.login(username, password)
                server.send_message(msg)

        except Exception as e:
            print(f"Failed to send email alert: {e}")

    return handler


__all__ = [
    "AlertSeverity",
    "CircuitBreakerAlert",
    "CircuitBreakerAlertManager",
    "get_alert_manager",
    "log_alert_handler",
    "webhook_alert_handler",
    "email_alert_handler",
]
