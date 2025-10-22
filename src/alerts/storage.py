"""Storage layer for alert rules and inbox using SQLite."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models import AlertInboxItem, AlertRuleModel, AlertSeverity, AlertStatus


class AlertStorage:
    """SQLite-based storage for alert rules and inbox."""
    
    def __init__(self, db_path: str | Path = "alerts.db"):
        """Initialize storage with database path."""
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Create alert_rules table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                condition TEXT NOT NULL,
                where_clause TEXT,
                severity TEXT NOT NULL,
                channels TEXT NOT NULL,
                suppression_duration INTEGER DEFAULT 3600,
                tags TEXT,
                version TEXT DEFAULT 'v2',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create alerts_inbox table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts_inbox (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                token_symbol TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                metadata TEXT,
                labels TEXT,
                provenance_links TEXT,
                triggered_at TEXT NOT NULL,
                acknowledged_at TEXT,
                snoozed_until TEXT,
                resolved_at TEXT,
                FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
            )
        """)
        
        # Create delivery_metrics table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_metrics (
                id TEXT PRIMARY KEY,
                alert_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                delivery_latency_ms REAL NOT NULL,
                delivered_at TEXT NOT NULL,
                deduplicated BOOLEAN DEFAULT 0,
                FOREIGN KEY (alert_id) REFERENCES alerts_inbox(id)
            )
        """)
        
        self.conn.commit()
    
    # Alert Rules CRUD
    
    def create_rule(self, rule: AlertRuleModel) -> AlertRuleModel:
        """Create a new alert rule."""
        self.conn.execute(
            """
            INSERT INTO alert_rules 
            (id, description, enabled, condition, where_clause, severity, channels, 
             suppression_duration, tags, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule.id,
                rule.description,
                rule.enabled,
                json.dumps(rule.condition),
                json.dumps(rule.where),
                rule.severity.value if isinstance(rule.severity, AlertSeverity) else rule.severity,
                json.dumps(rule.channels),
                rule.suppression_duration,
                json.dumps(rule.tags),
                rule.version,
                rule.created_at.isoformat() if rule.created_at else datetime.now(timezone.utc).isoformat(),
                rule.updated_at.isoformat() if rule.updated_at else datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
        return rule
    
    def get_rule(self, rule_id: str) -> Optional[AlertRuleModel]:
        """Get a specific alert rule by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM alert_rules WHERE id = ?", (rule_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_rule(row)
    
    def list_rules(self, enabled_only: bool = False) -> List[AlertRuleModel]:
        """List all alert rules."""
        query = "SELECT * FROM alert_rules"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        
        cursor = self.conn.execute(query)
        return [self._row_to_rule(row) for row in cursor.fetchall()]
    
    def update_rule(self, rule_id: str, updates: Dict) -> Optional[AlertRuleModel]:
        """Update an existing alert rule."""
        # Check if rule exists
        if not self.get_rule(rule_id):
            return None
        
        # Build update query
        set_clauses = []
        values = []
        
        if "description" in updates:
            set_clauses.append("description = ?")
            values.append(updates["description"])
        if "enabled" in updates:
            set_clauses.append("enabled = ?")
            values.append(updates["enabled"])
        if "condition" in updates:
            set_clauses.append("condition = ?")
            values.append(json.dumps(updates["condition"]))
        if "where" in updates:
            set_clauses.append("where_clause = ?")
            values.append(json.dumps(updates["where"]))
        if "severity" in updates:
            set_clauses.append("severity = ?")
            values.append(updates["severity"])
        if "channels" in updates:
            set_clauses.append("channels = ?")
            values.append(json.dumps(updates["channels"]))
        if "suppression_duration" in updates:
            set_clauses.append("suppression_duration = ?")
            values.append(updates["suppression_duration"])
        if "tags" in updates:
            set_clauses.append("tags = ?")
            values.append(json.dumps(updates["tags"]))
        
        set_clauses.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        
        values.append(rule_id)
        
        query = f"UPDATE alert_rules SET {', '.join(set_clauses)} WHERE id = ?"
        self.conn.execute(query, values)
        self.conn.commit()
        
        return self.get_rule(rule_id)
    
    def delete_rule(self, rule_id: str) -> bool:
        """Delete an alert rule."""
        cursor = self.conn.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # Alerts Inbox CRUD
    
    def create_alert(self, alert: AlertInboxItem) -> AlertInboxItem:
        """Create a new alert in the inbox."""
        self.conn.execute(
            """
            INSERT INTO alerts_inbox 
            (id, rule_id, token_symbol, message, severity, status, metadata, labels, 
             provenance_links, triggered_at, acknowledged_at, snoozed_until, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.id,
                alert.rule_id,
                alert.token_symbol,
                alert.message,
                alert.severity.value if isinstance(alert.severity, AlertSeverity) else alert.severity,
                alert.status.value if isinstance(alert.status, AlertStatus) else alert.status,
                json.dumps(alert.metadata),
                json.dumps(alert.labels),
                json.dumps(alert.provenance_links),
                alert.triggered_at.isoformat() if alert.triggered_at else datetime.now(timezone.utc).isoformat(),
                alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                alert.snoozed_until.isoformat() if alert.snoozed_until else None,
                alert.resolved_at.isoformat() if alert.resolved_at else None,
            ),
        )
        self.conn.commit()
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[AlertInboxItem]:
        """Get a specific alert by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM alerts_inbox WHERE id = ?", (alert_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_alert(row)
    
    def list_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AlertInboxItem]:
        """List alerts from inbox with filters."""
        query = "SELECT * FROM alerts_inbox WHERE 1=1"
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY triggered_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self.conn.execute(query, params)
        return [self._row_to_alert(row) for row in cursor.fetchall()]
    
    def acknowledge_alert(self, alert_id: str) -> Optional[AlertInboxItem]:
        """Mark an alert as acknowledged."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            UPDATE alerts_inbox 
            SET status = ?, acknowledged_at = ?
            WHERE id = ?
            """,
            ("acknowledged", now, alert_id),
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            return None
        return self.get_alert(alert_id)
    
    def snooze_alert(self, alert_id: str, duration_seconds: int) -> Optional[AlertInboxItem]:
        """Snooze an alert for a specified duration."""
        snoozed_until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        cursor = self.conn.execute(
            """
            UPDATE alerts_inbox 
            SET status = ?, snoozed_until = ?
            WHERE id = ?
            """,
            ("snoozed", snoozed_until.isoformat(), alert_id),
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            return None
        return self.get_alert(alert_id)
    
    def update_alert_labels(self, alert_id: str, labels: List[str]) -> Optional[AlertInboxItem]:
        """Update labels for an alert."""
        cursor = self.conn.execute(
            "UPDATE alerts_inbox SET labels = ? WHERE id = ?",
            (json.dumps(labels), alert_id),
        )
        self.conn.commit()
        if cursor.rowcount == 0:
            return None
        return self.get_alert(alert_id)
    
    # Delivery Metrics
    
    def record_delivery(
        self,
        alert_id: str,
        channel: str,
        latency_ms: float,
        deduplicated: bool = False,
    ) -> None:
        """Record alert delivery metrics."""
        metric_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        self.conn.execute(
            """
            INSERT INTO delivery_metrics 
            (id, alert_id, channel, delivery_latency_ms, delivered_at, deduplicated)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (metric_id, alert_id, channel, latency_ms, now, deduplicated),
        )
        self.conn.commit()
    
    def get_delivery_metrics(self) -> Dict:
        """Get aggregated delivery metrics."""
        cursor = self.conn.execute(
            """
            SELECT 
                AVG(delivery_latency_ms) as avg_latency,
                COUNT(*) as total_deliveries,
                SUM(CASE WHEN deduplicated = 1 THEN 1 ELSE 0 END) as deduplicated_count
            FROM delivery_metrics
            """
        )
        row = cursor.fetchone()
        
        total = row["total_deliveries"] or 0
        dedupe_count = row["deduplicated_count"] or 0
        
        return {
            "average_delivery_latency_ms": row["avg_latency"] or 0.0,
            "total_deliveries": total,
            "dedupe_rate": (dedupe_count / total * 100) if total > 0 else 0.0,
        }
    
    # Helper methods
    
    def _row_to_rule(self, row: sqlite3.Row) -> AlertRuleModel:
        """Convert database row to AlertRuleModel."""
        return AlertRuleModel(
            id=row["id"],
            description=row["description"],
            enabled=bool(row["enabled"]),
            condition=json.loads(row["condition"]),
            where=json.loads(row["where_clause"] or "{}"),
            severity=AlertSeverity(row["severity"]),
            channels=json.loads(row["channels"]),
            suppression_duration=row["suppression_duration"],
            tags=json.loads(row["tags"] or "[]"),
            version=row["version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    
    def _row_to_alert(self, row: sqlite3.Row) -> AlertInboxItem:
        """Convert database row to AlertInboxItem."""
        return AlertInboxItem(
            id=row["id"],
            rule_id=row["rule_id"],
            token_symbol=row["token_symbol"],
            message=row["message"],
            severity=AlertSeverity(row["severity"]),
            status=AlertStatus(row["status"]),
            metadata=json.loads(row["metadata"] or "{}"),
            labels=json.loads(row["labels"] or "[]"),
            provenance_links=json.loads(row["provenance_links"] or "{}"),
            triggered_at=datetime.fromisoformat(row["triggered_at"]) if row["triggered_at"] else None,
            acknowledged_at=datetime.fromisoformat(row["acknowledged_at"]) if row["acknowledged_at"] else None,
            snoozed_until=datetime.fromisoformat(row["snoozed_until"]) if row["snoozed_until"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        )
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()


__all__ = ["AlertStorage"]
