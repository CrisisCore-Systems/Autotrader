import type { EvidencePanel as EvidencePanelType, DataSourceInfo } from '../types';
import './EvidencePanel.css';

interface Props {
  panel: EvidencePanelType;
  freshness?: DataSourceInfo;
  provenanceLink?: string;
}

export function EvidencePanel({ panel, freshness, provenanceLink }: Props) {
  const getFreshnessColor = (level: string) => {
    switch (level) {
      case 'fresh': return '#22c55e';
      case 'recent': return '#3b82f6';
      case 'stale': return '#f59e0b';
      case 'outdated': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getFreshnessLabel = (level: string) => {
    switch (level) {
      case 'fresh': return '🟢 Fresh';
      case 'recent': return '🔵 Recent';
      case 'stale': return '🟡 Stale';
      case 'outdated': return '🔴 Outdated';
      default: return '⚪ Unknown';
    }
  };

  const formatAge = (seconds: number): string => {
    if (seconds < 60) return `${Math.floor(seconds)}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  return (
    <div className="evidence-panel">
      <div className="evidence-header">
        <h3>{panel.title}</h3>
        <div className="evidence-badges">
          {panel.is_free && (
            <span className="badge badge-free">🆓 FREE</span>
          )}
          {freshness && (
            <span 
              className="badge badge-freshness" 
              style={{ backgroundColor: getFreshnessColor(freshness.freshness_level) }}
              title={`Updated ${formatAge(freshness.data_age_seconds)}`}
            >
              {getFreshnessLabel(freshness.freshness_level)}
            </span>
          )}
          <span className="badge badge-confidence">
            {(panel.confidence * 100).toFixed(0)}% confidence
          </span>
        </div>
      </div>
      
      <div className="evidence-metadata">
        <div className="metadata-row">
          <span className="metadata-label">Source:</span>
          <span className="metadata-value">
            {provenanceLink ? (
              <a href={provenanceLink} target="_blank" rel="noopener noreferrer" className="provenance-link">
                {panel.source} 🔗
              </a>
            ) : (
              panel.source
            )}
          </span>
        </div>
        {freshness && (
          <div className="metadata-row">
            <span className="metadata-label">Last Updated:</span>
            <span className="metadata-value">{formatAge(freshness.data_age_seconds)}</span>
          </div>
        )}
      </div>

      <div className="evidence-content">
        {renderPanelData(panel.data)}
      </div>
    </div>
  );
}

function renderPanelData(data: any): JSX.Element {
  if (typeof data === 'object' && data !== null) {
    return (
      <div className="data-grid">
        {Object.entries(data).map(([key, value]) => (
          <div key={key} className="data-item">
            <span className="data-label">{formatLabel(key)}:</span>
            <span className="data-value">{formatValue(value)}</span>
          </div>
        ))}
      </div>
    );
  }
  return <pre>{JSON.stringify(data, null, 2)}</pre>;
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (l) => l.toUpperCase());
}

function formatValue(value: any): string {
  if (typeof value === 'number') {
    if (value > 1000000) {
      return `$${(value / 1000000).toFixed(2)}M`;
    } else if (value > 1000) {
      return `$${(value / 1000).toFixed(2)}K`;
    }
    return value.toLocaleString();
  }
  if (Array.isArray(value)) {
    return value.join(', ');
  }
  if (typeof value === 'object' && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
}
