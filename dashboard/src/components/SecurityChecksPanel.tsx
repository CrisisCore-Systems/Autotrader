/**
 * SecurityChecksPanel Component
 * Displays security check status including IBKR FA scrubbing and dependency scanning
 */

import React, { useEffect, useState } from 'react';
import './SecurityChecksPanel.css';

interface SecurityCheck {
  name: string;
  status: string;
  last_check: string;
  description: string;
  critical_issues?: number;
  high_issues?: number;
  medium_issues?: number;
  issues_found?: number;
  missing_keys?: string[];
}

interface SecurityResponse {
  checks: Record<string, SecurityCheck>;
  overall_status: string;
  timestamp: string;
}

export const SecurityChecksPanel: React.FC = () => {
  const [security, setSecurity] = useState<SecurityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSecurity();
    const interval = setInterval(fetchSecurity, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const fetchSecurity = async () => {
    try {
      const res = await fetch('/api/health/security');
      if (!res.ok) throw new Error('Failed to fetch security data');

      const data = await res.json();
      setSecurity(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'passing':
      case 'active':
        return '#10b981';
      case 'warning':
        return '#f59e0b';
      case 'failing':
      case 'inactive':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const getStatusIcon = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'passing':
      case 'active':
        return '✓';
      case 'warning':
        return '⚠';
      case 'failing':
      case 'inactive':
        return '✗';
      default:
        return '•';
    }
  };

  const formatTimestamp = (isoString: string): string => {
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  if (loading) {
    return <div className="security-checks-panel loading">Loading security data...</div>;
  }

  if (error) {
    return <div className="security-checks-panel error">Error: {error}</div>;
  }

  if (!security) {
    return <div className="security-checks-panel">No security data available</div>;
  }

  return (
    <div className="security-checks-panel">
      <div className="panel-header">
        <h3>Security Checks</h3>
        <div className="overall-status" style={{ color: getStatusColor(security.overall_status) }}>
          {getStatusIcon(security.overall_status)} {security.overall_status}
        </div>
      </div>

      <div className="checks-grid">
        {Object.entries(security.checks).map(([key, check]) => (
          <div key={key} className="check-card">
            <div className="card-header">
              <div className="check-name">{check.name}</div>
              <div
                className="status-badge"
                style={{
                  backgroundColor: getStatusColor(check.status),
                  color: 'white',
                }}
              >
                {getStatusIcon(check.status)} {check.status}
              </div>
            </div>

            <div className="check-description">{check.description}</div>

            <div className="check-details">
              {check.critical_issues !== undefined && (
                <div className="issue-count critical">
                  <span className="count">{check.critical_issues}</span>
                  <span className="label">Critical</span>
                </div>
              )}
              {check.high_issues !== undefined && (
                <div className="issue-count high">
                  <span className="count">{check.high_issues}</span>
                  <span className="label">High</span>
                </div>
              )}
              {check.medium_issues !== undefined && (
                <div className="issue-count medium">
                  <span className="count">{check.medium_issues}</span>
                  <span className="label">Medium</span>
                </div>
              )}
              {check.issues_found !== undefined && (
                <div className="issue-count">
                  <span className="count">{check.issues_found}</span>
                  <span className="label">Issues</span>
                </div>
              )}
              {check.missing_keys && check.missing_keys.length > 0 && (
                <div className="missing-keys">
                  <span className="label">Missing:</span>
                  <span className="keys">{check.missing_keys.join(', ')}</span>
                </div>
              )}
            </div>

            <div className="last-check">
              Last checked: {formatTimestamp(check.last_check)}
            </div>
          </div>
        ))}
      </div>

      <button onClick={fetchSecurity} className="refresh-btn">
        Refresh Security Checks
      </button>
    </div>
  );
};
