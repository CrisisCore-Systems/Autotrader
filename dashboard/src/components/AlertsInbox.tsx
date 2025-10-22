/* Alerts Inbox Component */

import React, { useState, useEffect } from 'react';
import './AlertsInbox.css';

interface Alert {
  id: string;
  rule_id: string;
  token_symbol: string;
  message: string;
  severity: 'info' | 'warning' | 'high' | 'critical';
  status: 'pending' | 'acknowledged' | 'snoozed' | 'resolved';
  metadata: Record<string, any>;
  labels: string[];
  provenance_links: Record<string, string>;
  triggered_at: string;
  acknowledged_at?: string;
  snoozed_until?: string;
  resolved_at?: string;
}

interface AlertsInboxProps {
  apiBaseUrl?: string;
}

export const AlertsInbox: React.FC<AlertsInboxProps> = ({ 
  apiBaseUrl = 'http://localhost:8001/api' 
}) => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<{
    status?: string;
    severity?: string;
  }>({});
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [newLabel, setNewLabel] = useState('');

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.status) params.append('status', filter.status);
      if (filter.severity) params.append('severity', filter.severity);

      const response = await fetch(`${apiBaseUrl}/alerts/inbox?${params}`);
      const data = await response.json();
      setAlerts(data.alerts || []);
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
    // Poll for updates every 30 seconds
    const interval = setInterval(fetchAlerts, 30000);
    return () => clearInterval(interval);
  }, [filter]);

  const acknowledgeAlert = async (alertId: string) => {
    try {
      await fetch(`${apiBaseUrl}/alerts/inbox/${alertId}/acknowledge`, {
        method: 'POST',
      });
      fetchAlerts();
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };

  const snoozeAlert = async (alertId: string, duration: number) => {
    try {
      await fetch(`${apiBaseUrl}/alerts/inbox/${alertId}/snooze?duration_seconds=${duration}`, {
        method: 'POST',
      });
      fetchAlerts();
    } catch (error) {
      console.error('Failed to snooze alert:', error);
    }
  };

  const updateLabels = async (alertId: string, labels: string[]) => {
    try {
      await fetch(`${apiBaseUrl}/alerts/inbox/${alertId}/labels`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(labels),
      });
      fetchAlerts();
    } catch (error) {
      console.error('Failed to update labels:', error);
    }
  };

  const addLabel = (alert: Alert) => {
    if (newLabel && !alert.labels.includes(newLabel)) {
      updateLabels(alert.id, [...alert.labels, newLabel]);
      setNewLabel('');
    }
  };

  const removeLabel = (alert: Alert, label: string) => {
    updateLabels(alert.id, alert.labels.filter(l => l !== label));
  };

  const getSeverityColor = (severity: string): string => {
    const colors = {
      info: '#2196F3',
      warning: '#FF9800',
      high: '#FF5722',
      critical: '#F44336',
    };
    return colors[severity as keyof typeof colors] || '#666';
  };

  const getStatusBadge = (status: string): JSX.Element => {
    const statusColors = {
      pending: '#FFC107',
      acknowledged: '#4CAF50',
      snoozed: '#9E9E9E',
      resolved: '#2196F3',
    };
    const color = statusColors[status as keyof typeof statusColors] || '#666';

    return (
      <span className="status-badge" style={{ backgroundColor: color }}>
        {status}
      </span>
    );
  };

  const formatTimestamp = (timestamp: string): string => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return 'Just now';
  };

  return (
    <div className="alerts-inbox">
      <div className="inbox-header">
        <h2>Alerts Inbox</h2>
        <button onClick={fetchAlerts} className="refresh-btn">
          🔄 Refresh
        </button>
      </div>

      <div className="inbox-filters">
        <select 
          value={filter.status || ''} 
          onChange={e => setFilter({ ...filter, status: e.target.value || undefined })}
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="snoozed">Snoozed</option>
          <option value="resolved">Resolved</option>
        </select>

        <select 
          value={filter.severity || ''} 
          onChange={e => setFilter({ ...filter, severity: e.target.value || undefined })}
        >
          <option value="">All Severities</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {loading ? (
        <div className="loading">Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div className="empty-state">
          <p>No alerts found</p>
        </div>
      ) : (
        <div className="alerts-list">
          {alerts.map(alert => (
            <div 
              key={alert.id} 
              className={`alert-card ${selectedAlert?.id === alert.id ? 'selected' : ''}`}
              onClick={() => setSelectedAlert(alert)}
            >
              <div className="alert-header">
                <div className="alert-title">
                  <span 
                    className="severity-dot" 
                    style={{ backgroundColor: getSeverityColor(alert.severity) }}
                  />
                  <strong>{alert.token_symbol}</strong>
                  {getStatusBadge(alert.status)}
                </div>
                <span className="alert-time">{formatTimestamp(alert.triggered_at)}</span>
              </div>

              <div className="alert-message">{alert.message}</div>

              {alert.labels.length > 0 && (
                <div className="alert-labels">
                  {alert.labels.map(label => (
                    <span key={label} className="label">{label}</span>
                  ))}
                </div>
              )}

              {selectedAlert?.id === alert.id && (
                <div className="alert-details" onClick={e => e.stopPropagation()}>
                  <div className="alert-actions">
                    {alert.status === 'pending' && (
                      <>
                        <button 
                          onClick={() => acknowledgeAlert(alert.id)}
                          className="btn-action btn-ack"
                        >
                          ✓ Acknowledge
                        </button>
                        <button 
                          onClick={() => snoozeAlert(alert.id, 3600)}
                          className="btn-action btn-snooze"
                        >
                          ⏰ Snooze 1h
                        </button>
                        <button 
                          onClick={() => snoozeAlert(alert.id, 86400)}
                          className="btn-action btn-snooze"
                        >
                          ⏰ Snooze 24h
                        </button>
                      </>
                    )}
                  </div>

                  <div className="alert-metadata">
                    <h4>Metadata</h4>
                    <pre>{JSON.stringify(alert.metadata, null, 2)}</pre>
                  </div>

                  {Object.keys(alert.provenance_links).length > 0 && (
                    <div className="alert-provenance">
                      <h4>Provenance Links</h4>
                      <div className="provenance-links">
                        {Object.entries(alert.provenance_links).map(([source, link]) => (
                          <a key={source} href={link} target="_blank" rel="noopener noreferrer">
                            {source}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="label-editor">
                    <h4>Labels</h4>
                    <div className="labels-container">
                      {alert.labels.map(label => (
                        <span key={label} className="label editable">
                          {label}
                          <button 
                            onClick={() => removeLabel(alert, label)}
                            className="label-remove"
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                    <div className="add-label">
                      <input
                        type="text"
                        value={newLabel}
                        onChange={e => setNewLabel(e.target.value)}
                        placeholder="Add label"
                        onKeyPress={e => {
                          if (e.key === 'Enter') {
                            addLabel(alert);
                          }
                        }}
                      />
                      <button onClick={() => addLabel(alert)}>Add</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
