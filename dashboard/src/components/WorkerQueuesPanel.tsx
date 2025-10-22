/**
 * WorkerQueuesPanel Component
 * Displays worker queue status for background jobs
 */

import React, { useEffect, useState } from 'react';
import './WorkerQueuesPanel.css';

interface QueueData {
  name: string;
  pending_jobs: number;
  active_workers: number;
  completed_today: number;
  avg_processing_time_ms: number;
  status: string;
}

interface QueuesResponse {
  queues: Record<string, QueueData>;
  timestamp: string;
}

export const WorkerQueuesPanel: React.FC = () => {
  const [queues, setQueues] = useState<QueuesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchQueues();
    const interval = setInterval(fetchQueues, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchQueues = async () => {
    try {
      const res = await fetch('/api/health/queues');
      if (!res.ok) throw new Error('Failed to fetch queue data');

      const data = await res.json();
      setQueues(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status.toLowerCase()) {
      case 'healthy':
        return '#10b981';
      case 'degraded':
        return '#f59e0b';
      case 'failed':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  const formatProcessingTime = (ms: number): string => {
    if (ms < 1000) {
      return `${ms}ms`;
    } else {
      return `${(ms / 1000).toFixed(1)}s`;
    }
  };

  if (loading) {
    return <div className="worker-queues-panel loading">Loading queue data...</div>;
  }

  if (error) {
    return <div className="worker-queues-panel error">Error: {error}</div>;
  }

  if (!queues) {
    return <div className="worker-queues-panel">No queue data available</div>;
  }

  return (
    <div className="worker-queues-panel">
      <div className="panel-header">
        <h3>Worker Queues</h3>
        <button onClick={fetchQueues} className="refresh-btn">
          ↻
        </button>
      </div>

      <div className="queues-grid">
        {Object.entries(queues.queues).map(([key, queue]) => (
          <div key={key} className="queue-card">
            <div className="card-header">
              <div className="queue-name">{queue.name}</div>
              <div
                className="status-indicator"
                style={{ color: getStatusColor(queue.status) }}
              >
                ● {queue.status}
              </div>
            </div>

            <div className="queue-metrics">
              <div className="metric-row">
                <div className="metric-item">
                  <div className="metric-value">{queue.pending_jobs}</div>
                  <div className="metric-label">Pending</div>
                </div>
                <div className="metric-item">
                  <div className="metric-value">{queue.active_workers}</div>
                  <div className="metric-label">Workers</div>
                </div>
                <div className="metric-item">
                  <div className="metric-value">{queue.completed_today}</div>
                  <div className="metric-label">Completed</div>
                </div>
              </div>

              <div className="processing-time">
                <span className="label">Avg Processing:</span>
                <span className="value">
                  {formatProcessingTime(queue.avg_processing_time_ms)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
