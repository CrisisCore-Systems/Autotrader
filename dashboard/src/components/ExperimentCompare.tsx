import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { compareExperiments } from '../api';
import { ExperimentComparison } from '../types';
import './ExperimentCompare.css';

interface Props {
  hash1: string;
  hash2: string;
  onClose?: () => void;
}

export function ExperimentCompare({ hash1, hash2, onClose }: Props) {
  const comparisonQuery = useQuery<ExperimentComparison>({
    queryKey: ['experiment-comparison', hash1, hash2],
    queryFn: () => compareExperiments(hash1, hash2, true),
  });

  if (comparisonQuery.isLoading) {
    return <div className="experiment-compare loading">Loading comparison...</div>;
  }

  if (comparisonQuery.isError) {
    return (
      <div className="experiment-compare error">
        Failed to load comparison: {(comparisonQuery.error as Error).message}
      </div>
    );
  }

  const comparison = comparisonQuery.data;
  if (!comparison) return null;

  return (
    <div className="experiment-compare">
      {/* Header */}
      <div className="compare-header">
        <div>
          <h2>Experiment Comparison</h2>
          <div className="comparing-hashes">
            <code>{comparison.config1_hash}</code>
            <span className="vs">vs</span>
            <code>{comparison.config2_hash}</code>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="close-button">×</button>
        )}
      </div>

      {/* Feature Set Comparison */}
      <section className="feature-comparison">
        <h3>Feature Set Comparison</h3>
        <div className="feature-sets">
          <div className="feature-set">
            <h4>Common Features ({comparison.features.common.length})</h4>
            <div className="feature-list common">
              {comparison.features.common.map((feature) => (
                <span key={feature} className="feature-chip">{feature}</span>
              ))}
              {comparison.features.common.length === 0 && (
                <span className="empty">No common features</span>
              )}
            </div>
          </div>

          <div className="feature-set">
            <h4>Only in {comparison.config1_hash}</h4>
            <div className="feature-list only-in-1">
              {comparison.features.only_in_config1.map((feature) => (
                <span key={feature} className="feature-chip">{feature}</span>
              ))}
              {comparison.features.only_in_config1.length === 0 && (
                <span className="empty">None</span>
              )}
            </div>
          </div>

          <div className="feature-set">
            <h4>Only in {comparison.config2_hash}</h4>
            <div className="feature-list only-in-2">
              {comparison.features.only_in_config2.map((feature) => (
                <span key={feature} className="feature-chip">{feature}</span>
              ))}
              {comparison.features.only_in_config2.length === 0 && (
                <span className="empty">None</span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Weight Differences */}
      {Object.keys(comparison.weight_differences).length > 0 && (
        <section className="weight-differences">
          <h3>Weight Differences</h3>
          <div className="differences-table">
            <table>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>{comparison.config1_hash}</th>
                  <th>{comparison.config2_hash}</th>
                  <th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(comparison.weight_differences)
                  .sort(([, a], [, b]) => Math.abs(b.diff) - Math.abs(a.diff))
                  .map(([feature, diff]) => (
                    <tr key={feature}>
                      <td className="feature-name">{feature}</td>
                      <td className="weight-value">{diff.config1.toFixed(4)}</td>
                      <td className="weight-value">{diff.config2.toFixed(4)}</td>
                      <td className={`delta-value ${diff.diff > 0 ? 'positive' : 'negative'}`}>
                        {diff.diff > 0 ? '+' : ''}{diff.diff.toFixed(4)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Hyperparameter Comparison */}
      <section className="hyperparameter-comparison">
        <h3>Hyperparameters</h3>
        <div className="side-by-side">
          <div className="config-params">
            <h4>{comparison.config1_hash}</h4>
            <div className="params-list">
              {Object.keys(comparison.hyperparameters.config1).length === 0 ? (
                <span className="empty">No hyperparameters</span>
              ) : (
                Object.entries(comparison.hyperparameters.config1).map(([key, value]) => (
                  <div key={key} className="param-row">
                    <span className="param-key">{key}:</span>
                    <span className="param-value">{JSON.stringify(value)}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="config-params">
            <h4>{comparison.config2_hash}</h4>
            <div className="params-list">
              {Object.keys(comparison.hyperparameters.config2).length === 0 ? (
                <span className="empty">No hyperparameters</span>
              ) : (
                Object.entries(comparison.hyperparameters.config2).map(([key, value]) => (
                  <div key={key} className="param-row">
                    <span className="param-key">{key}:</span>
                    <span className="param-value">{JSON.stringify(value)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Metrics Comparison */}
      {comparison.metrics_comparison && (
        <section className="metrics-comparison">
          <h3>Performance Metrics</h3>
          <div className="metrics-grid">
            <div className="metric-comparison-card">
              <div className="metric-name">Precision@K</div>
              <div className="metric-values">
                <div className="value-box">
                  <span className="label">{comparison.config1_hash}</span>
                  <span className="value">
                    {(comparison.metrics_comparison.config1.precision_at_k * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="value-box">
                  <span className="label">{comparison.config2_hash}</span>
                  <span className="value">
                    {(comparison.metrics_comparison.config2.precision_at_k * 100).toFixed(2)}%
                  </span>
                </div>
              </div>
              <div className={`delta ${comparison.metrics_comparison.deltas.precision_delta > 0 ? 'positive' : 'negative'}`}>
                {comparison.metrics_comparison.deltas.precision_delta > 0 ? '▲' : '▼'}
                {Math.abs(comparison.metrics_comparison.deltas.precision_delta * 100).toFixed(2)}%
              </div>
            </div>

            <div className="metric-comparison-card">
              <div className="metric-name">Avg Return@K</div>
              <div className="metric-values">
                <div className="value-box">
                  <span className="label">{comparison.config1_hash}</span>
                  <span className="value">
                    {(comparison.metrics_comparison.config1.average_return_at_k * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="value-box">
                  <span className="label">{comparison.config2_hash}</span>
                  <span className="value">
                    {(comparison.metrics_comparison.config2.average_return_at_k * 100).toFixed(2)}%
                  </span>
                </div>
              </div>
              <div className={`delta ${comparison.metrics_comparison.deltas.return_delta > 0 ? 'positive' : 'negative'}`}>
                {comparison.metrics_comparison.deltas.return_delta > 0 ? '▲' : '▼'}
                {Math.abs(comparison.metrics_comparison.deltas.return_delta * 100).toFixed(2)}%
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
