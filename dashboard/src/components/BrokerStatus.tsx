/**
 * BrokerStatus Component
 * Displays connection status for all supported brokers
 */

import React, { useEffect, useState } from 'react';
import './BrokerStatus.css';

interface BrokerInfo {
  name: string;
  connected: boolean;
  status: string;
  account_value?: number;
  cash?: number;
  error?: string;
}

interface BrokerStatusData {
  [key: string]: BrokerInfo;
}

export const BrokerStatus: React.FC = () => {
  const [brokers, setBrokers] = useState<BrokerStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch('/api/trading/broker-status');
      if (!res.ok) throw new Error('Failed to fetch broker status');

      const data = await res.json();
      setBrokers(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="broker-status loading">Loading broker status...</div>;
  }

  if (error) {
    return <div className="broker-status error">Error: {error}</div>;
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'online':
        return '#10b981';
      case 'not_configured':
        return '#f59e0b';
      case 'error':
      case 'offline':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'online':
        return '✓';
      case 'not_configured':
        return '⚠';
      case 'error':
      case 'offline':
        return '✗';
      default:
        return '•';
    }
  };

  return (
    <div className="broker-status">
      <div className="status-header">
        <h3>Broker Connectivity</h3>
        <button onClick={fetchStatus} className="refresh-btn">
          ↻
        </button>
      </div>

      <div className="brokers-grid">
        {brokers &&
          Object.entries(brokers).map(([key, broker]) => (
            <div key={key} className={`broker-card ${broker.connected ? 'connected' : 'disconnected'}`}>
              <div className="broker-header">
                <div className="broker-name">{broker.name}</div>
                <div
                  className="status-indicator"
                  style={{ backgroundColor: getStatusColor(broker.status) }}
                >
                  {getStatusIcon(broker.status)} {broker.status.replace('_', ' ')}
                </div>
              </div>

              {broker.connected && broker.account_value !== undefined ? (
                <div className="broker-metrics">
                  <div className="metric">
                    <span className="label">Account Value:</span>
                    <span className="value">${broker.account_value.toFixed(2)}</span>
                  </div>
                  <div className="metric">
                    <span className="label">Cash:</span>
                    <span className="value">${broker.cash?.toFixed(2) || '0.00'}</span>
                  </div>
                </div>
              ) : (
                <div className="broker-error">
                  {broker.error || 'Not configured'}
                </div>
              )}
            </div>
          ))}
      </div>
    </div>
  );
};
