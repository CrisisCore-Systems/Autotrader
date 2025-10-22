/**
 * FreshnessPanel Component
 * Displays data freshness for ingestion sources (CoinGecko, Dexscreener, Blockscout, Ethereum RPC)
 */

import React, { useEffect, useState } from 'react';
import './FreshnessPanel.css';

interface FreshnessData {
  display_name: string;
  last_success_at: string;
  data_age_seconds: number;
  freshness_level: 'fresh' | 'recent' | 'stale' | 'outdated';
  is_free: boolean;
  update_frequency_seconds: number;
  error_rate: number;
  latency_ms: number | null;
}

interface FreshnessResponse {
  sources: Record<string, FreshnessData>;
  timestamp: string;
}

export const FreshnessPanel: React.FC = () => {
  const [freshness, setFreshness] = useState<FreshnessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFreshness();
    const interval = setInterval(fetchFreshness, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchFreshness = async () => {
    try {
      const res = await fetch('/api/health/freshness');
      if (!res.ok) throw new Error('Failed to fetch freshness data');

      const data = await res.json();
      setFreshness(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  const getFreshnessColor = (level: string) => {
    switch (level) {
      case 'fresh':
        return '#10b981'; // green
      case 'recent':
        return '#3b82f6'; // blue
      case 'stale':
        return '#f59e0b'; // yellow
      case 'outdated':
        return '#ef4444'; // red
      default:
        return '#6b7280'; // gray
    }
  };

  const getFreshnessIcon = (level: string) => {
    switch (level) {
      case 'fresh':
        return '●';
      case 'recent':
        return '◐';
      case 'stale':
        return '◔';
      case 'outdated':
        return '○';
      default:
        return '•';
    }
  };

  const formatAge = (seconds: number): string => {
    if (seconds < 60) {
      return `${Math.floor(seconds)}s ago`;
    } else if (seconds < 3600) {
      return `${Math.floor(seconds / 60)}m ago`;
    } else if (seconds < 86400) {
      return `${Math.floor(seconds / 3600)}h ago`;
    } else {
      return `${Math.floor(seconds / 86400)}d ago`;
    }
  };

  const formatTimestamp = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleTimeString();
  };

  if (loading) {
    return <div className="freshness-panel loading">Loading freshness data...</div>;
  }

  if (error) {
    return <div className="freshness-panel error">Error: {error}</div>;
  }

  if (!freshness) {
    return <div className="freshness-panel">No freshness data available</div>;
  }

  return (
    <div className="freshness-panel">
      <div className="panel-header">
        <h3>Data Freshness</h3>
        <button onClick={fetchFreshness} className="refresh-btn">
          ↻
        </button>
      </div>

      <div className="freshness-grid">
        {Object.entries(freshness.sources).map(([key, source]) => (
          <div key={key} className={`freshness-card ${source.freshness_level}`}>
            <div className="card-header">
              <div className="source-name">
                {source.display_name}
                {source.is_free && <span className="free-badge">FREE</span>}
              </div>
              <div
                className="freshness-indicator"
                style={{ color: getFreshnessColor(source.freshness_level) }}
              >
                {getFreshnessIcon(source.freshness_level)} {source.freshness_level}
              </div>
            </div>

            <div className="card-metrics">
              <div className="metric">
                <span className="label">Last Update:</span>
                <span className="value">{formatTimestamp(source.last_success_at)}</span>
              </div>
              <div className="metric">
                <span className="label">Age:</span>
                <span className="value">{formatAge(source.data_age_seconds)}</span>
              </div>
              <div className="metric">
                <span className="label">Error Rate:</span>
                <span className="value">{(source.error_rate * 100).toFixed(1)}%</span>
              </div>
              {source.latency_ms !== null && (
                <div className="metric">
                  <span className="label">Latency (P95):</span>
                  <span className="value">{source.latency_ms.toFixed(0)}ms</span>
                </div>
              )}
              <div className="metric">
                <span className="label">Update Freq:</span>
                <span className="value">{source.update_frequency_seconds}s</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="panel-footer">
        <span className="timestamp">Last checked: {formatTimestamp(freshness.timestamp)}</span>
      </div>
    </div>
  );
};
