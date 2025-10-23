/**
 * Data Drift and Freshness Monitoring Dashboard Component
 * 
 * Displays real-time monitoring of feature drift and data freshness,
 * with SLA tracking and alerting for critical features.
 */

import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, XCircle, Clock, TrendingUp, RefreshCw } from 'lucide-react';

// ============================================================================
// Types
// ============================================================================

interface FeatureHealth {
  feature_name: string;
  drift_detected: boolean;
  drift_severity: string;
  freshness_level: string;
  data_age_seconds: number;
  sla_violated: boolean;
  last_updated: string;
}

interface MonitoringSummary {
  timestamp: string;
  status: string;
  features_monitored: number;
  features_drifted: number;
  features_stale: number;
  sla_violations: number;
  critical_features: number;
  recommendations: string[];
}

interface MonitoringDetail {
  timestamp: string;
  features_monitored: number;
  features_drifted: number;
  features_stale: number;
  sla_violations: number;
  feature_health: Record<string, FeatureHealth>;
  recommendations: string[];
}

// ============================================================================
// Utility Functions
// ============================================================================

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'healthy':
      return 'text-green-600 bg-green-100';
    case 'warning':
      return 'text-yellow-600 bg-yellow-100';
    case 'degraded':
      return 'text-orange-600 bg-orange-100';
    case 'critical':
      return 'text-red-600 bg-red-100';
    default:
      return 'text-gray-600 bg-gray-100';
  }
};

const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'none':
      return 'text-green-600';
    case 'low':
      return 'text-blue-600';
    case 'medium':
      return 'text-yellow-600';
    case 'high':
      return 'text-orange-600';
    case 'critical':
      return 'text-red-600';
    default:
      return 'text-gray-600';
  }
};

const getFreshnessColor = (level: string): string => {
  switch (level) {
    case 'fresh':
      return 'text-green-600';
    case 'recent':
      return 'text-blue-600';
    case 'stale':
      return 'text-yellow-600';
    case 'outdated':
      return 'text-red-600';
    default:
      return 'text-gray-600';
  }
};

const formatDuration = (seconds: number): string => {
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  } else if (seconds < 3600) {
    return `${Math.round(seconds / 60)}m`;
  } else if (seconds < 86400) {
    return `${Math.round(seconds / 3600)}h`;
  } else {
    return `${Math.round(seconds / 86400)}d`;
  }
};

// ============================================================================
// Main Component
// ============================================================================

export const DriftMonitoring: React.FC = () => {
  const [summary, setSummary] = useState<MonitoringSummary | null>(null);
  const [details, setDetails] = useState<MonitoringDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Fetch monitoring data
  const fetchData = async () => {
    try {
      setError(null);
      
      // Fetch summary
      const summaryRes = await fetch('/api/monitoring/summary');
      if (!summaryRes.ok) throw new Error('Failed to fetch summary');
      const summaryData = await summaryRes.json();
      setSummary(summaryData);

      // Fetch details
      try {
        const detailsRes = await fetch('/api/monitoring/details');
        if (detailsRes.ok) {
          const detailsData = await detailsRes.json();
          setDetails(detailsData);
        }
      } catch (err) {
        // Details might not be available yet
        console.warn('Details not available:', err);
      }

      setLoading(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  // Initial fetch and auto-refresh
  useEffect(() => {
    fetchData();

    if (autoRefresh) {
      const interval = setInterval(fetchData, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  // ============================================================================
  // Render
  // ============================================================================

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-800">
          <XCircle className="w-5 h-5" />
          <span className="font-semibold">Error loading monitoring data</span>
        </div>
        <p className="mt-2 text-red-600">{error}</p>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
        <p className="text-gray-600">No monitoring data available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">
          Data Drift & Freshness Monitoring
        </h2>
        <div className="flex items-center gap-4">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1 rounded text-sm font-medium ${
              autoRefresh
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-700'
            }`}
          >
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}
          </button>
          <button
            onClick={fetchData}
            className="px-3 py-1 bg-blue-500 text-white rounded text-sm font-medium hover:bg-blue-600"
          >
            <RefreshCw className="w-4 h-4 inline mr-1" />
            Refresh
          </button>
        </div>
      </div>

      {/* Status Overview */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={`px-3 py-1 rounded-full text-sm font-semibold ${getStatusColor(summary.status)}`}>
            {summary.status.toUpperCase()}
          </div>
          <span className="text-gray-500 text-sm">
            Last updated: {new Date(summary.timestamp).toLocaleString()}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="text-blue-600 text-sm font-medium">Features Monitored</div>
            <div className="text-2xl font-bold text-blue-900">{summary.features_monitored}</div>
          </div>

          <div className="bg-orange-50 rounded-lg p-4">
            <div className="text-orange-600 text-sm font-medium">Features Drifted</div>
            <div className="text-2xl font-bold text-orange-900">{summary.features_drifted}</div>
          </div>

          <div className="bg-yellow-50 rounded-lg p-4">
            <div className="text-yellow-600 text-sm font-medium">Stale Features</div>
            <div className="text-2xl font-bold text-yellow-900">{summary.features_stale}</div>
          </div>

          <div className="bg-red-50 rounded-lg p-4">
            <div className="text-red-600 text-sm font-medium">SLA Violations</div>
            <div className="text-2xl font-bold text-red-900">{summary.sla_violations}</div>
          </div>
        </div>

        {summary.critical_features > 0 && (
          <div className="mt-4 bg-purple-50 rounded-lg p-3">
            <div className="text-purple-700 text-sm font-medium">
              {summary.critical_features} critical feature(s) with enforced SLAs
            </div>
          </div>
        )}
      </div>

      {/* Recommendations */}
      {summary.recommendations.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-3">
            Recommendations
          </h3>
          <ul className="space-y-2">
            {summary.recommendations.map((rec, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                <span className="text-gray-700">{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Feature Health Details */}
      {details && Object.keys(details.feature_health).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Feature Health
          </h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Feature
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Drift Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Freshness
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Data Age
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    SLA
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {Object.values(details.feature_health).map((health) => (
                  <tr key={health.feature_name} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {health.feature_name}
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {health.drift_detected ? (
                        <div className="flex items-center gap-2">
                          <TrendingUp className={`w-4 h-4 ${getSeverityColor(health.drift_severity)}`} />
                          <span className={`text-sm font-medium ${getSeverityColor(health.drift_severity)}`}>
                            {health.drift_severity.toUpperCase()}
                          </span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-sm text-green-600">No Drift</span>
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`text-sm font-medium ${getFreshnessColor(health.freshness_level)}`}>
                        {health.freshness_level.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-1">
                        <Clock className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-600">
                          {formatDuration(health.data_age_seconds)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {health.sla_violated ? (
                        <div className="flex items-center gap-1">
                          <XCircle className="w-4 h-4 text-red-500" />
                          <span className="text-sm text-red-600 font-medium">Violated</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <CheckCircle className="w-4 h-4 text-green-500" />
                          <span className="text-sm text-green-600">OK</span>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default DriftMonitoring;
