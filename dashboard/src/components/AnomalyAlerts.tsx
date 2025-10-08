/**
 * Anomaly Alerts Component
 * Real-time anomaly detection and alerting
 */

import React, { useState, useEffect } from 'react';

interface AnomalyAlert {
  alert_id: string;
  token_symbol: string;
  alert_type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: number;
  metrics: Record<string, any>;
}

export const AnomalyAlerts: React.FC = () => {
  const [alerts, setAlerts] = useState<AnomalyAlert[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        // Use enhanced API (port 8002) - auto-configured in api.ts
        const { fetchAnomalies } = await import('../api');
        
        const severityParam = filter !== 'all' ? filter : undefined;
        const data = await fetchAnomalies(severityParam);
        setAlerts(data);
      } catch (error) {
        console.error('Failed to fetch anomalies:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 10000); // Refresh every 10s

    return () => clearInterval(interval);
  }, [filter]);

  const acknowledgeAlert = async (alertId: string) => {
    try {
      const { acknowledgeAnomaly } = await import('../api');
      await acknowledgeAnomaly(alertId);
      setAlerts((prev) => prev.filter((a) => a.alert_id !== alertId));
    } catch (error) {
      console.error('Failed to acknowledge alert:', error);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 border-red-500 text-red-800';
      case 'high':
        return 'bg-orange-100 border-orange-500 text-orange-800';
      case 'medium':
        return 'bg-yellow-100 border-yellow-500 text-yellow-800';
      case 'low':
        return 'bg-blue-100 border-blue-500 text-blue-800';
      default:
        return 'bg-gray-100 border-gray-500 text-gray-800';
    }
  };

  const getAlertIcon = (alertType: string) => {
    switch (alertType) {
      case 'price_spike':
        return '📈';
      case 'volume_surge':
        return '📊';
      case 'liquidity_drain':
        return '💧';
      case 'sentiment_shift':
        return '💬';
      default:
        return '⚠️';
    }
  };

  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
    return date.toLocaleDateString();
  };

  if (loading) {
    return <div className="p-4">Loading anomalies...</div>;
  }

  return (
    <div className="p-6 bg-white rounded-lg shadow-lg">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Anomaly Alerts</h2>

        {/* Severity Filter */}
        <div className="flex gap-2">
          {['all', 'critical', 'high', 'medium', 'low'].map((severity) => (
            <button
              key={severity}
              onClick={() => setFilter(severity)}
              className={`px-3 py-1 rounded text-sm font-medium ${
                filter === severity
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {severity.charAt(0).toUpperCase() + severity.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Alert Count */}
      <div className="mb-4 text-sm text-gray-600">
        {alerts.length} active alert{alerts.length !== 1 ? 's' : ''}
      </div>

      {/* Alerts List */}
      <div className="space-y-3">
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <div className="text-4xl mb-2">✅</div>
            <div>No anomalies detected</div>
          </div>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.alert_id}
              className={`border-l-4 p-4 rounded ${getSeverityColor(alert.severity)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xl">{getAlertIcon(alert.alert_type)}</span>
                    <span className="font-bold">{alert.token_symbol}</span>
                    <span className="text-xs uppercase font-semibold">
                      {alert.alert_type.replace('_', ' ')}
                    </span>
                  </div>

                  <p className="text-sm mb-2">{alert.message}</p>

                  <div className="flex items-center gap-4 text-xs text-gray-600">
                    <span>{formatTimestamp(alert.timestamp)}</span>
                    {Object.entries(alert.metrics).map(([key, value]) => (
                      <span key={key}>
                        {key}: {typeof value === 'number' ? value.toFixed(4) : value}
                      </span>
                    ))}
                  </div>
                </div>

                <button
                  onClick={() => acknowledgeAlert(alert.alert_id)}
                  className="ml-4 px-3 py-1 text-sm bg-white border rounded hover:bg-gray-50"
                >
                  Dismiss
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
