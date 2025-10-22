/* Alert Analytics Component */

import React, { useState, useEffect } from 'react';
import './AlertAnalytics.css';

interface AnalyticsData {
  total_alerts: number;
  alerts_by_severity: Record<string, number>;
  alerts_by_rule: Record<string, number>;
  acknowledgement_rate: number;
  average_delivery_latency_ms: number;
  dedupe_rate: number;
}

interface AlertAnalyticsProps {
  apiBaseUrl?: string;
}

export const AlertAnalytics: React.FC<AlertAnalyticsProps> = ({ 
  apiBaseUrl = 'http://localhost:8001/api' 
}) => {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBaseUrl}/alerts/analytics/performance`);
      const data = await response.json();
      setAnalytics(data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
    // Refresh every minute
    const interval = setInterval(fetchAnalytics, 60000);
    return () => clearInterval(interval);
  }, []);

  const getSeverityColor = (severity: string): string => {
    const colors: Record<string, string> = {
      info: '#2196F3',
      warning: '#FF9800',
      high: '#FF5722',
      critical: '#F44336',
    };
    return colors[severity] || '#666';
  };

  const formatLatency = (ms: number): string => {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const MetricCard: React.FC<{
    title: string;
    value: string | number;
    subtitle?: string;
    color?: string;
  }> = ({ title, value, subtitle, color }) => (
    <div className="metric-card" style={{ borderTopColor: color }}>
      <div className="metric-title">{title}</div>
      <div className="metric-value">{value}</div>
      {subtitle && <div className="metric-subtitle">{subtitle}</div>}
    </div>
  );

  if (loading) {
    return (
      <div className="alert-analytics">
        <div className="loading">Loading analytics...</div>
      </div>
    );
  }

  if (!analytics) {
    return (
      <div className="alert-analytics">
        <div className="empty-state">No analytics data available</div>
      </div>
    );
  }

  const topRules = Object.entries(analytics.alerts_by_rule)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <div className="alert-analytics">
      <div className="analytics-header">
        <h2>Alert Analytics</h2>
        <button onClick={fetchAnalytics} className="refresh-btn">
          🔄 Refresh
        </button>
      </div>

      <div className="metrics-grid">
        <MetricCard
          title="Total Alerts"
          value={analytics.total_alerts}
          color="#2196F3"
        />
        <MetricCard
          title="Average Delivery"
          value={formatLatency(analytics.average_delivery_latency_ms)}
          subtitle="Latency"
          color="#4CAF50"
        />
        <MetricCard
          title="Acknowledgement Rate"
          value={`${analytics.acknowledgement_rate.toFixed(1)}%`}
          subtitle="Alerts acknowledged"
          color="#FF9800"
        />
        <MetricCard
          title="Dedupe Rate"
          value={`${analytics.dedupe_rate.toFixed(1)}%`}
          subtitle="Duplicate alerts prevented"
          color="#9C27B0"
        />
      </div>

      <div className="charts-section">
        <div className="chart-card">
          <h3>Alerts by Severity</h3>
          <div className="severity-chart">
            {Object.entries(analytics.alerts_by_severity).map(([severity, count]) => {
              const total = analytics.total_alerts;
              const percentage = total > 0 ? (count / total) * 100 : 0;
              const color = getSeverityColor(severity);

              return (
                <div key={severity} className="severity-bar">
                  <div className="severity-label">
                    <span 
                      className="severity-dot" 
                      style={{ backgroundColor: color }}
                    />
                    <span className="severity-name">{severity}</span>
                    <span className="severity-count">{count}</span>
                  </div>
                  <div className="progress-bar">
                    <div 
                      className="progress-fill" 
                      style={{ 
                        width: `${percentage}%`, 
                        backgroundColor: color 
                      }}
                    />
                  </div>
                  <span className="severity-percentage">{percentage.toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="chart-card">
          <h3>Top Alert Rules</h3>
          <div className="rules-list">
            {topRules.length > 0 ? (
              topRules.map(([rule, count], index) => (
                <div key={rule} className="rule-item">
                  <span className="rule-rank">#{index + 1}</span>
                  <span className="rule-name">{rule}</span>
                  <span className="rule-count">{count} alerts</span>
                </div>
              ))
            ) : (
              <div className="empty-state">No rules with alerts yet</div>
            )}
          </div>
        </div>
      </div>

      <div className="performance-section">
        <div className="performance-card">
          <h3>Delivery Performance</h3>
          <div className="performance-metrics">
            <div className="perf-metric">
              <div className="perf-label">Average Latency</div>
              <div className="perf-value">
                {formatLatency(analytics.average_delivery_latency_ms)}
              </div>
              <div className="perf-indicator">
                {analytics.average_delivery_latency_ms < 1000 ? (
                  <span className="indicator-good">✓ Excellent</span>
                ) : analytics.average_delivery_latency_ms < 5000 ? (
                  <span className="indicator-ok">⚠ Good</span>
                ) : (
                  <span className="indicator-poor">✗ Needs attention</span>
                )}
              </div>
            </div>

            <div className="perf-metric">
              <div className="perf-label">Deduplication</div>
              <div className="perf-value">{analytics.dedupe_rate.toFixed(1)}%</div>
              <div className="perf-indicator">
                {analytics.dedupe_rate > 10 ? (
                  <span className="indicator-good">✓ Effective</span>
                ) : analytics.dedupe_rate > 5 ? (
                  <span className="indicator-ok">⚠ Moderate</span>
                ) : (
                  <span className="indicator-ok">— Low</span>
                )}
              </div>
            </div>

            <div className="perf-metric">
              <div className="perf-label">Response Rate</div>
              <div className="perf-value">{analytics.acknowledgement_rate.toFixed(1)}%</div>
              <div className="perf-indicator">
                {analytics.acknowledgement_rate > 70 ? (
                  <span className="indicator-good">✓ High</span>
                ) : analytics.acknowledgement_rate > 40 ? (
                  <span className="indicator-ok">⚠ Medium</span>
                ) : (
                  <span className="indicator-poor">✗ Low</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
