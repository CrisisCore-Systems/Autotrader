/**
 * SignalsQueue Component
 * Displays filtered trading signals with quality gates and advanced filter indicators
 */

import React, { useEffect, useState } from 'react';
import './SignalsQueue.css';

interface Signal {
  ticker: string;
  gap_pct: number;
  volume: number;
  market_cap: number;
  quality_score: number;
  score_breakdown: Record<string, number>;
  entry_price: number;
  stop_price: number;
  target_price: number;
  risk_reward: number;
  filter_results: {
    overall_pass: boolean;
    filters: Record<string, { pass: boolean; reason?: string }>;
  } | null;
  timestamp: string;
}

interface SignalsQueueProps {
  onSelectSignal?: (signal: Signal) => void;
}

export const SignalsQueue: React.FC<SignalsQueueProps> = ({ onSelectSignal }) => {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [minQuality, setMinQuality] = useState(5.5);

  useEffect(() => {
    fetchSignals();
    const interval = setInterval(fetchSignals, 300000); // Refresh every 5 minutes
    return () => clearInterval(interval);
  }, [minQuality]);

  const fetchSignals = async () => {
    try {
      const res = await fetch(`/api/trading/signals?min_quality=${minQuality}&include_filters=true`);
      if (!res.ok) throw new Error('Failed to fetch signals');

      const data = await res.json();
      setSignals(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="signals-queue loading">Loading signals...</div>;
  }

  if (error) {
    return <div className="signals-queue error">Error: {error}</div>;
  }

  const getQualityColor = (score: number) => {
    if (score >= 8) return '#10b981';
    if (score >= 7) return '#3b82f6';
    if (score >= 6) return '#f59e0b';
    return '#ef4444';
  };

  return (
    <div className="signals-queue">
      <div className="signals-header">
        <h3>Signals Queue</h3>
        <div className="filter-controls">
          <label>
            Min Quality:
            <input
              type="number"
              min="0"
              max="10"
              step="0.5"
              value={minQuality}
              onChange={(e) => setMinQuality(parseFloat(e.target.value))}
            />
          </label>
          <button onClick={fetchSignals} className="refresh-btn">
            ↻ Refresh
          </button>
        </div>
      </div>

      <div className="signals-count">
        {signals.length} signal{signals.length !== 1 ? 's' : ''} found (≥{minQuality.toFixed(1)})
      </div>

      {signals.length === 0 ? (
        <div className="no-signals">
          <p>No signals passed quality gates</p>
          <p className="hint">Try lowering the minimum quality score</p>
        </div>
      ) : (
        <div className="signals-list">
          {signals.map((signal, idx) => (
            <div
              key={`${signal.ticker}-${idx}`}
              className="signal-card"
              onClick={() => onSelectSignal?.(signal)}
            >
              <div className="signal-header">
                <div className="ticker-badge">{signal.ticker}</div>
                <div
                  className="quality-badge"
                  style={{ backgroundColor: getQualityColor(signal.quality_score) }}
                >
                  {signal.quality_score.toFixed(1)}
                </div>
              </div>

              <div className="signal-metrics">
                <div className="metric">
                  <span className="label">Gap:</span>
                  <span className="value">+{signal.gap_pct.toFixed(1)}%</span>
                </div>
                <div className="metric">
                  <span className="label">Entry:</span>
                  <span className="value">${signal.entry_price.toFixed(2)}</span>
                </div>
                <div className="metric">
                  <span className="label">R:R:</span>
                  <span className="value">{signal.risk_reward.toFixed(2)}</span>
                </div>
              </div>

              <div className="signal-prices">
                <div className="price-item stop">
                  <span className="label">Stop:</span>
                  <span className="value">${signal.stop_price.toFixed(2)}</span>
                </div>
                <div className="price-item target">
                  <span className="label">Target:</span>
                  <span className="value">${signal.target_price.toFixed(2)}</span>
                </div>
              </div>

              {signal.filter_results && (
                <div className="filter-status">
                  <div className="filters-header">Advanced Filters:</div>
                  <div className="filters-grid">
                    {Object.entries(signal.filter_results.filters || {}).map(([name, result]) => (
                      <div
                        key={name}
                        className={`filter-badge ${result.pass ? 'pass' : 'fail'}`}
                        title={result.reason || ''}
                      >
                        {result.pass ? '✓' : '✗'} {name}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="score-breakdown">
                <div className="breakdown-header">Score Breakdown:</div>
                <div className="breakdown-items">
                  {Object.entries(signal.score_breakdown || {}).map(([component, score]) => (
                    <div key={component} className="breakdown-item">
                      <span className="component">{component}:</span>
                      <span className="score">{score.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
