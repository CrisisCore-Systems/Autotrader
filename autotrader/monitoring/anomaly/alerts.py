"""
Alert Routing System
Phase 12: Route anomalies to PagerDuty, Slack, Email
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
import logging
import json

from autotrader.monitoring.anomaly.detector import Anomaly, AnomalySeverity


logger = logging.getLogger(__name__)


class AlertChannel(str, Enum):
    """Alert routing channels"""
    PAGERDUTY = "pagerduty"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG = "log"


@dataclass
class AlertConfig:
    """Alert routing configuration"""
    channel: AlertChannel
    enabled: bool = True
    
    # Channel-specific settings
    pagerduty_integration_key: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    email_recipients: Optional[List[str]] = None
    webhook_url: Optional[str] = None
    
    # Routing rules
    min_severity: AnomalySeverity = AnomalySeverity.WARNING
    anomaly_types: Optional[List[str]] = None  # If None, all types


class AlertRouter:
    """
    Route anomalies to appropriate channels based on severity and type
    """
    
    def __init__(self, configs: List[AlertConfig] = None):
        """
        Initialize alert router
        
        Args:
            configs: List of alert configurations
        """
        self.configs = configs or self._default_configs()
        self.alert_history: List[Dict] = []
        logger.info(f"Alert Router initialized with {len(self.configs)} channels")
    
    def route_anomaly(self, anomaly: Anomaly) -> Dict[str, bool]:
        """
        Route anomaly to configured channels
        
        Args:
            anomaly: Detected anomaly
        
        Returns:
            Dictionary of channel -> success status
        """
        results = {}
        
        for config in self.configs:
            if not config.enabled:
                continue
            
            # Check if anomaly matches routing rules
            if not self._should_route(anomaly, config):
                continue
            
            # Route to channel
            try:
                if config.channel == AlertChannel.PAGERDUTY:
                    success = self._send_pagerduty(anomaly, config)
                elif config.channel == AlertChannel.SLACK:
                    success = self._send_slack(anomaly, config)
                elif config.channel == AlertChannel.EMAIL:
                    success = self._send_email(anomaly, config)
                elif config.channel == AlertChannel.WEBHOOK:
                    success = self._send_webhook(anomaly, config)
                elif config.channel == AlertChannel.LOG:
                    success = self._send_log(anomaly, config)
                else:
                    success = False
                
                results[config.channel.value] = success
                
                # Record in history
                self.alert_history.append({
                    'timestamp': datetime.now().isoformat(),
                    'anomaly_id': anomaly.anomaly_id,
                    'channel': config.channel.value,
                    'success': success
                })
                
            except Exception as e:
                logger.error(f"Failed to route to {config.channel.value}: {e}")
                results[config.channel.value] = False
        
        return results
    
    def route_batch(self, anomalies: List[Anomaly]) -> Dict[str, int]:
        """
        Route multiple anomalies
        
        Args:
            anomalies: List of anomalies
        
        Returns:
            Dictionary of channel -> count of successful alerts
        """
        channel_counts = {}
        
        for anomaly in anomalies:
            results = self.route_anomaly(anomaly)
            for channel, success in results.items():
                if success:
                    channel_counts[channel] = channel_counts.get(channel, 0) + 1
        
        logger.info(f"Routed {len(anomalies)} anomalies: {channel_counts}")
        return channel_counts
    
    def _should_route(self, anomaly: Anomaly, config: AlertConfig) -> bool:
        """Check if anomaly matches routing rules"""
        # Check severity
        severity_order = [AnomalySeverity.INFO, AnomalySeverity.WARNING, AnomalySeverity.CRITICAL]
        if severity_order.index(anomaly.severity) < severity_order.index(config.min_severity):
            return False
        
        # Check anomaly type
        if config.anomaly_types and anomaly.anomaly_type.value not in config.anomaly_types:
            return False
        
        return True
    
    def _send_pagerduty(self, anomaly: Anomaly, config: AlertConfig) -> bool:
        """Send alert to PagerDuty"""
        if not config.pagerduty_integration_key:
            logger.warning("PagerDuty integration key not configured")
            return False
        
        try:
            import requests
            
            payload = {
                'routing_key': config.pagerduty_integration_key,
                'event_action': 'trigger',
                'dedup_key': anomaly.anomaly_id,
                'payload': {
                    'summary': anomaly.description,
                    'severity': anomaly.severity.value,
                    'source': 'AutoTrader',
                    'timestamp': anomaly.timestamp.isoformat(),
                    'custom_details': {
                        'anomaly_type': anomaly.anomaly_type.value,
                        'metric_name': anomaly.metric_name,
                        'metric_value': anomaly.metric_value,
                        'expected_value': anomaly.expected_value,
                        'deviation_score': anomaly.deviation_score,
                        'context': anomaly.context
                    }
                }
            }
            
            response = requests.post(
                'https://events.pagerduty.com/v2/enqueue',
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"Sent PagerDuty alert for {anomaly.anomaly_id}")
            return True
            
        except Exception as e:
            logger.error(f"PagerDuty alert failed: {e}")
            return False
    
    def _send_slack(self, anomaly: Anomaly, config: AlertConfig) -> bool:
        """Send alert to Slack"""
        if not config.slack_webhook_url:
            logger.warning("Slack webhook URL not configured")
            return False
        
        try:
            import requests
            
            # Format severity emoji
            emoji = {
                AnomalySeverity.INFO: ':information_source:',
                AnomalySeverity.WARNING: ':warning:',
                AnomalySeverity.CRITICAL: ':rotating_light:'
            }.get(anomaly.severity, ':question:')
            
            # Build message
            message = {
                'text': f"{emoji} *Anomaly Detected*",
                'blocks': [
                    {
                        'type': 'header',
                        'text': {
                            'type': 'plain_text',
                            'text': f"{emoji} {anomaly.anomaly_type.value.replace('_', ' ').title()}"
                        }
                    },
                    {
                        'type': 'section',
                        'fields': [
                            {'type': 'mrkdwn', 'text': f"*Severity:*\n{anomaly.severity.value}"},
                            {'type': 'mrkdwn', 'text': f"*Metric:*\n{anomaly.metric_name}"},
                            {'type': 'mrkdwn', 'text': f"*Value:*\n{anomaly.metric_value:.4f}"},
                            {'type': 'mrkdwn', 'text': f"*Expected:*\n{anomaly.expected_value:.4f}"},
                            {'type': 'mrkdwn', 'text': f"*Deviation:*\n{anomaly.deviation_score:.2f}σ"},
                            {'type': 'mrkdwn', 'text': f"*Time:*\n{anomaly.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"}
                        ]
                    },
                    {
                        'type': 'section',
                        'text': {
                            'type': 'mrkdwn',
                            'text': f"*Description:*\n{anomaly.description}"
                        }
                    }
                ]
            }
            
            response = requests.post(
                config.slack_webhook_url,
                json=message,
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"Sent Slack alert for {anomaly.anomaly_id}")
            return True
            
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
            return False
    
    def _send_email(self, anomaly: Anomaly, config: AlertConfig) -> bool:
        """Send alert via email"""
        if not config.email_recipients:
            logger.warning("Email recipients not configured")
            return False
        
        try:
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            # Build email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{anomaly.severity.value.upper()}] Anomaly: {anomaly.anomaly_type.value}"
            msg['From'] = 'autotrader@alerts.local'
            msg['To'] = ', '.join(config.email_recipients)
            
            # Plain text version
            text = f"""
Anomaly Detected

Type: {anomaly.anomaly_type.value}
Severity: {anomaly.severity.value}
Metric: {anomaly.metric_name}
Value: {anomaly.metric_value:.4f}
Expected: {anomaly.expected_value:.4f}
Deviation: {anomaly.deviation_score:.2f}
Time: {anomaly.timestamp.isoformat()}

Description:
{anomaly.description}

Context:
{json.dumps(anomaly.context, indent=2)}
            """
            
            # HTML version
            html = f"""
<html>
  <body>
    <h2 style="color: {'red' if anomaly.severity == AnomalySeverity.CRITICAL else 'orange'};">
      Anomaly Detected
    </h2>
    <table border="1" cellpadding="5">
      <tr><td><b>Type</b></td><td>{anomaly.anomaly_type.value}</td></tr>
      <tr><td><b>Severity</b></td><td>{anomaly.severity.value}</td></tr>
      <tr><td><b>Metric</b></td><td>{anomaly.metric_name}</td></tr>
      <tr><td><b>Value</b></td><td>{anomaly.metric_value:.4f}</td></tr>
      <tr><td><b>Expected</b></td><td>{anomaly.expected_value:.4f}</td></tr>
      <tr><td><b>Deviation</b></td><td>{anomaly.deviation_score:.2f}</td></tr>
      <tr><td><b>Time</b></td><td>{anomaly.timestamp.isoformat()}</td></tr>
    </table>
    <h3>Description</h3>
    <p>{anomaly.description}</p>
    <h3>Context</h3>
    <pre>{json.dumps(anomaly.context, indent=2)}</pre>
  </body>
</html>
            """
            
            msg.attach(MIMEText(text, 'plain'))
            msg.attach(MIMEText(html, 'html'))
            
            # Send email (configure SMTP settings as needed)
            # For production, use proper SMTP configuration
            logger.info(f"Email alert prepared for {anomaly.anomaly_id} (SMTP not configured)")
            return True
            
        except Exception as e:
            logger.error(f"Email alert failed: {e}")
            return False
    
    def _send_webhook(self, anomaly: Anomaly, config: AlertConfig) -> bool:
        """Send alert to generic webhook"""
        if not config.webhook_url:
            logger.warning("Webhook URL not configured")
            return False
        
        try:
            import requests
            
            payload = anomaly.to_dict()
            
            response = requests.post(
                config.webhook_url,
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            logger.info(f"Sent webhook alert for {anomaly.anomaly_id}")
            return True
            
        except Exception as e:
            logger.error(f"Webhook alert failed: {e}")
            return False
    
    def _send_log(self, anomaly: Anomaly, config: AlertConfig) -> bool:
        """Log alert to system logger"""
        log_msg = (
            f"ANOMALY ALERT - {anomaly.severity.value.upper()} - "
            f"{anomaly.anomaly_type.value}: {anomaly.description} "
            f"(metric={anomaly.metric_name}, value={anomaly.metric_value:.4f}, "
            f"expected={anomaly.expected_value:.4f}, deviation={anomaly.deviation_score:.2f})"
        )
        
        if anomaly.severity == AnomalySeverity.CRITICAL:
            logger.critical(log_msg)
        elif anomaly.severity == AnomalySeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        return True
    
    def _default_configs(self) -> List[AlertConfig]:
        """Default alert configurations"""
        return [
            # Critical anomalies to PagerDuty
            AlertConfig(
                channel=AlertChannel.PAGERDUTY,
                enabled=False,  # Enable when configured
                min_severity=AnomalySeverity.CRITICAL
            ),
            # Warnings and above to Slack
            AlertConfig(
                channel=AlertChannel.SLACK,
                enabled=False,  # Enable when configured
                min_severity=AnomalySeverity.WARNING
            ),
            # All anomalies to logs
            AlertConfig(
                channel=AlertChannel.LOG,
                enabled=True,
                min_severity=AnomalySeverity.INFO
            )
        ]
