/**
 * RateLimitingPanel Component
 * Displays rate limiting status for all APIs
 */

import React, { useEffect, useState } from 'react';
import './RateLimitingPanel.css';

interface RateLimitData {
  name: string;
  is_free: boolean;
  limit_per_minute: number;
  estimated_usage: number;
  status: string;
  reset_at: string | null;
}

interface RateLimitResponse {
  rate_limits: Record<string, RateLimitData>;
  timestamp: string;
}

export const RateLimitingPanel: React.FC = () => {
  const [rateLimits, setRateLimits] = useState<RateLimitResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRateLimits();
    const interval = setInterval(fetchRateLimits, 15000); // Refresh every 15 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchRateLimits = async () => {
    try {
      const res = await fetch('/api/health/rate-limits');
      if (!res.ok) throw new Error('Failed to fetch rate limit data');

      const data = await res.json();
      setRateLimits(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  const getUsagePercent = (usage: number, limit: number): number => {
    return (usage / limit) * 100;
  };

  const getUsageColor = (percent: number): string => {
    if (percent < 60) return '#10b981'; // green
    if (percent < 80) return '#f59e0b'; // yellow
    return '#ef4444'; // red
  };

  if (loading) {
    return <div className="rate-limit-panel loading">Loading rate limit data...</div>;
  }

  if (error) {
    return <div className="rate-limit-panel error">Error: {error}</div>;
  }

  if (!rateLimits) {
    return <div className="rate-limit-panel">No rate limit data available</div>;
  }

  return (
    <div className="rate-limit-panel">
      <div className="panel-header">
        <h3>API Rate Limits</h3>
        <button onClick={fetchRateLimits} className="refresh-btn">
          ↻
        </button>
      </div>

      <div className="rate-limits-grid">
        {Object.entries(rateLimits.rate_limits).map(([key, limit]) => {
          const usagePercent = getUsagePercent(limit.estimated_usage, limit.limit_per_minute);
          const usageColor = getUsageColor(usagePercent);

          return (
            <div key={key} className="rate-limit-card">
              <div className="card-header">
                <div className="api-name">
                  {limit.name}
                  {limit.is_free && <span className="free-badge">FREE</span>}
                </div>
                <div className={`status-badge ${limit.status}`}>
                  {limit.status}
                </div>
              </div>

              <div className="usage-bar-container">
                <div
                  className="usage-bar"
                  style={{
                    width: `${usagePercent}%`,
                    backgroundColor: usageColor,
                  }}
                />
              </div>

              <div className="usage-stats">
                <span className="usage-text">
                  {limit.estimated_usage} / {limit.limit_per_minute} req/min
                </span>
                <span className="usage-percent" style={{ color: usageColor }}>
                  {usagePercent.toFixed(0)}%
                </span>
              </div>

              {limit.reset_at && (
                <div className="reset-info">
                  Resets at: {new Date(limit.reset_at).toLocaleTimeString()}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
