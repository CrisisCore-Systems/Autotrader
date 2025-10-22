import { useQuery } from '@tanstack/react-query';
import { fetchExperimentDetail } from '../api';
import { ExperimentDetail as ExperimentDetailType } from '../types';
import { TreeView } from './TreeView';
import './ExperimentDetail.css';

interface Props {
  configHash: string;
  onCompare?: (hash: string) => void;
  onExport?: (hash: string) => void;
}

export function ExperimentDetail({ configHash, onCompare, onExport }: Props) {
  const detailQuery = useQuery<ExperimentDetailType>({
    queryKey: ['experiment-detail', configHash],
    queryFn: () => fetchExperimentDetail(configHash, {
      includeResults: true,
      includeTree: true,
    }),
  });

  if (detailQuery.isLoading) {
    return <div className="experiment-detail loading">Loading experiment details...</div>;
  }

  if (detailQuery.isError) {
    return (
      <div className="experiment-detail error">
        Failed to load experiment: {(detailQuery.error as Error).message}
      </div>
    );
  }

  const exp = detailQuery.data;
  if (!exp) return null;

  return (
    <div className="experiment-detail">
      {/* Header */}
      <div className="detail-header">
        <div>
          <h2>Experiment Detail</h2>
          <code className="config-hash">{exp.config_hash}</code>
        </div>
        <div className="header-actions">
          {onCompare && (
            <button onClick={() => onCompare(configHash)} className="btn-secondary">
              Compare
            </button>
          )}
          {onExport && (
            <button onClick={() => onExport(configHash)} className="btn-primary">
              Export
            </button>
          )}
        </div>
      </div>

      {/* Config Snapshot */}
      <section className="config-section">
        <h3>Configuration Snapshot</h3>
        <div className="config-grid">
          <div className="config-item">
            <span className="label">Created:</span>
            <span className="value">{new Date(exp.created_at).toLocaleString()}</span>
          </div>
          <div className="config-item">
            <span className="label">Features:</span>
            <span className="value">{exp.config.feature_names.length}</span>
          </div>
          <div className="config-item">
            <span className="label">Description:</span>
            <span className="value">{exp.config.description || '(none)'}</span>
          </div>
          {exp.config.tags.length > 0 && (
            <div className="config-item full-width">
              <span className="label">Tags:</span>
              <div className="tags">
                {exp.config.tags.map((tag) => (
                  <span key={tag} className="tag">{tag}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Feature Weights */}
        <div className="feature-weights">
          <h4>Feature Weights</h4>
          <div className="weights-grid">
            {Object.entries(exp.config.feature_weights)
              .sort(([, a], [, b]) => b - a)
              .map(([feature, weight]) => (
                <div key={feature} className="weight-item">
                  <span className="feature-name">{feature}</span>
                  <div className="weight-bar-container">
                    <div className="weight-bar" style={{ width: `${weight * 100}%` }}></div>
                    <span className="weight-value">{weight.toFixed(4)}</span>
                  </div>
                </div>
              ))}
          </div>
        </div>

        {/* Hyperparameters */}
        {Object.keys(exp.config.hyperparameters).length > 0 && (
          <div className="hyperparameters">
            <h4>Hyperparameters</h4>
            <div className="params-grid">
              {Object.entries(exp.config.hyperparameters).map(([key, value]) => (
                <div key={key} className="param-item">
                  <span className="param-key">{key}:</span>
                  <span className="param-value">{JSON.stringify(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* Metrics */}
      {exp.metrics && (
        <section className="metrics-section">
          <h3>Performance Metrics</h3>
          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Precision@K</div>
              <div className="metric-value">{(exp.metrics.precision_at_k * 100).toFixed(2)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Avg Return@K</div>
              <div className="metric-value">{(exp.metrics.average_return_at_k * 100).toFixed(2)}%</div>
            </div>
            
            {exp.metrics.extended_metrics && (
              <>
                {exp.metrics.extended_metrics.sharpe_ratio !== undefined && (
                  <div className="metric-card">
                    <div className="metric-label">Sharpe Ratio</div>
                    <div className="metric-value">{exp.metrics.extended_metrics.sharpe_ratio.toFixed(3)}</div>
                  </div>
                )}
                {exp.metrics.extended_metrics.sortino_ratio !== undefined && (
                  <div className="metric-card">
                    <div className="metric-label">Sortino Ratio</div>
                    <div className="metric-value">{exp.metrics.extended_metrics.sortino_ratio.toFixed(3)}</div>
                  </div>
                )}
                {exp.metrics.extended_metrics.max_drawdown !== undefined && (
                  <div className="metric-card">
                    <div className="metric-label">Max Drawdown</div>
                    <div className="metric-value">{(exp.metrics.extended_metrics.max_drawdown * 100).toFixed(2)}%</div>
                  </div>
                )}
                {exp.metrics.extended_metrics.win_rate !== undefined && (
                  <div className="metric-card">
                    <div className="metric-label">Win Rate</div>
                    <div className="metric-value">{(exp.metrics.extended_metrics.win_rate * 100).toFixed(2)}%</div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Baseline Comparison */}
          {exp.metrics.baseline_results && Object.keys(exp.metrics.baseline_results).length > 0 && (
            <div className="baseline-comparison">
              <h4>Baseline Comparison</h4>
              <table className="baseline-table">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    <th>Precision</th>
                    <th>Avg Return</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(exp.metrics.baseline_results).map(([name, results]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{(results.precision * 100).toFixed(2)}%</td>
                      <td>{(results.avg_return * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Execution Tree */}
      {exp.execution_tree && (
        <section className="tree-section">
          <h3>Execution Tree</h3>
          <div className="tree-container">
            <TreeView node={exp.execution_tree} />
          </div>
        </section>
      )}
    </div>
  );
}
