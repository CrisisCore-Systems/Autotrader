/**
 * OpsOverview Component
 * Main operations and observability dashboard combining all panels
 */

import React from 'react';
import { FreshnessPanel } from './FreshnessPanel';
import { BrokerStatus } from './BrokerStatus';
import { SLADashboard } from './SLADashboard';
import { RateLimitingPanel } from './RateLimitingPanel';
import { WorkerQueuesPanel } from './WorkerQueuesPanel';
import { SecurityChecksPanel } from './SecurityChecksPanel';
import './OpsOverview.css';

export const OpsOverview: React.FC = () => {
  return (
    <div className="ops-overview">
      <div className="ops-header">
        <h1>Operations & Observability Dashboard</h1>
        <p className="ops-subtitle">
          Monitor system health, data freshness, and broker connectivity in real-time
        </p>
      </div>

      <div className="ops-grid">
        {/* Row 1: Freshness and Broker Status */}
        <div className="ops-section full-width">
          <FreshnessPanel />
        </div>

        <div className="ops-section">
          <BrokerStatus />
        </div>

        {/* Row 2: Rate Limits and Worker Queues */}
        <div className="ops-section">
          <RateLimitingPanel />
        </div>

        <div className="ops-section">
          <WorkerQueuesPanel />
        </div>

        {/* Row 3: SLA Dashboard (full width) */}
        <div className="ops-section full-width">
          <SLADashboard />
        </div>

        {/* Row 4: Security Checks (full width) */}
        <div className="ops-section full-width">
          <SecurityChecksPanel />
        </div>
      </div>

      <div className="ops-footer">
        <p>
          All panels auto-refresh. For detailed runbooks and troubleshooting guides, 
          see <a href="/docs/operations" target="_blank" rel="noopener noreferrer">Operations Documentation</a>
        </p>
      </div>
    </div>
  );
};
