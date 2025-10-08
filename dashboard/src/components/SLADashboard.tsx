/**
 * SLA Dashboard Component
 * Real-time monitoring of data source health and circuit breakers
 */

import React, { useState, useEffect } from 'react';

interface SLAStatus {
  source_name: string;
  status: 'HEALTHY' | 'DEGRADED' | 'FAILED';
  latency_p50: number | null;
  latency_p95: number | null;
  latency_p99: number | null;
  success_rate: number | null;
  uptime_percentage: number | null;
}

interface CircuitBreakerStatus {
  breaker_name: string;
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  failure_count: number;
}

export const SLADashboard: React.FC = () => {
  const [slaStatuses, setSlaStatuses] = useState<SLAStatus[]>([]);
  const [circuitBreakers, setCircuitBreakers] = useState<CircuitBreakerStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Use enhanced API (port 8002) - auto-configured in api.ts
        const { fetchSLAStatus, fetchCircuitBreakers } = await import('../api');
        
        const [slaData, cbData] = await Promise.all([
          fetchSLAStatus(),
          fetchCircuitBreakers(),
        ]);

        setSlaStatuses(slaData);
        setCircuitBreakers(cbData);
      } catch (error) {
        console.error('Failed to fetch SLA data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5s

    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'HEALTHY':
      case 'CLOSED':
        return 'text-green-600 bg-green-100';
      case 'DEGRADED':
      case 'HALF_OPEN':
        return 'text-yellow-600 bg-yellow-100';
      case 'FAILED':
      case 'OPEN':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  if (loading) {
    return <div className="p-4">Loading SLA dashboard...</div>;
  }

  return (
    <div className="p-6 bg-white rounded-lg shadow-lg">
      <h2 className="text-2xl font-bold mb-6">System Health Dashboard</h2>

      {/* Data Source SLAs */}
      <div className="mb-8">
        <h3 className="text-xl font-semibold mb-4">Data Source SLAs</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {slaStatuses.map((sla) => (
            <div key={sla.source_name} className="border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h4 className="font-semibold">{sla.source_name}</h4>
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(
                    sla.status
                  )}`}
                >
                  {sla.status}
                </span>
              </div>

              <div className="space-y-2 text-sm">
                {sla.latency_p95 !== null && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Latency P95:</span>
                    <span className="font-medium">{sla.latency_p95.toFixed(3)}s</span>
                  </div>
                )}
                {sla.success_rate !== null && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Success Rate:</span>
                    <span className="font-medium">{(sla.success_rate * 100).toFixed(1)}%</span>
                  </div>
                )}
                {sla.uptime_percentage !== null && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Uptime:</span>
                    <span className="font-medium">{sla.uptime_percentage.toFixed(1)}%</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Circuit Breakers */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Circuit Breakers</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {circuitBreakers.map((cb) => (
            <div key={cb.breaker_name} className="border rounded-lg p-4">
              <h4 className="font-semibold mb-2">{cb.breaker_name}</h4>
              <span
                className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(
                  cb.state
                )}`}
              >
                {cb.state}
              </span>
              <div className="mt-2 text-sm text-gray-600">
                Failures: {cb.failure_count}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
