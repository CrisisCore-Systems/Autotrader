import { useEffect, useState } from 'react';
import './SummaryReport.css';

interface ScoreData {
  gem_score: number;
  confidence: number;
  final_score: number;
}

interface Driver {
  name: string;
  value: number;
}

interface SummaryReportData {
  token_symbol: string;
  timestamp: string;
  scores: ScoreData;
  drivers: {
    top_positive: Driver[];
    top_negative: Driver[];
  };
  risk_flags: string[];
  warnings: string[];
  recommendations: string[];
  metadata: {
    flagged: boolean;
    safety_score: number;
    safety_severity: string;
  };
}

interface SummaryReportProps {
  tokenSymbol: string;
}

export function SummaryReport({ tokenSymbol }: SummaryReportProps) {
  const [report, setReport] = useState<SummaryReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchReport() {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`http://localhost:8001/api/summary/${tokenSymbol}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch summary: ${response.statusText}`);
        }
        
        const data = await response.json();
        setReport(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }

    if (tokenSymbol) {
      fetchReport();
    }
  }, [tokenSymbol]);

  if (loading) {
    return <div className="summary-report loading">Loading summary...</div>;
  }

  if (error) {
    return <div className="summary-report error">Error: {error}</div>;
  }

  if (!report) {
    return <div className="summary-report">No data available</div>;
  }

  return (
    <div className="summary-report">
      <div className="summary-header">
        <h2>📊 Summary Report: {report.token_symbol}</h2>
        <div className="timestamp">
          Generated: {new Date(report.timestamp).toLocaleString()}
        </div>
      </div>

      {/* Scores Section */}
      <section className="scores-section">
        <h3>Scores</h3>
        <div className="scores-grid">
          <ScoreCard
            label="GemScore"
            value={report.scores.gem_score}
            max={100}
            threshold={70}
          />
          <ScoreCard
            label="Confidence"
            value={report.scores.confidence}
            max={100}
            threshold={70}
          />
          <ScoreCard
            label="Final Score"
            value={report.scores.final_score}
            max={100}
            threshold={70}
          />
        </div>
      </section>

      {/* Drivers Section */}
      <div className="drivers-section">
        <div className="drivers-column">
          <h3>✅ Top Positive Drivers</h3>
          {report.drivers.top_positive.length > 0 ? (
            <ul className="driver-list">
              {report.drivers.top_positive.map((driver, index) => (
                <li key={index} className="driver-item positive">
                  <span className="driver-name">{formatFeatureName(driver.name)}</span>
                  <span className="driver-value positive">+{driver.value.toFixed(3)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="no-data">No significant positive drivers</p>
          )}
        </div>

        <div className="drivers-column">
          <h3>⚠️ Top Improvement Areas</h3>
          {report.drivers.top_negative.length > 0 ? (
            <ul className="driver-list">
              {report.drivers.top_negative.map((driver, index) => (
                <li key={index} className="driver-item negative">
                  <span className="driver-name">{formatFeatureName(driver.name)}</span>
                  <span className="driver-value negative">-{driver.value.toFixed(3)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="no-data">No significant improvement areas</p>
          )}
        </div>
      </div>

      {/* Risk Flags Section */}
      <section className="risk-flags-section">
        <h3>🚨 Risk Flags</h3>
        {report.risk_flags.length > 0 ? (
          <ul className="flag-list">
            {report.risk_flags.map((flag, index) => (
              <li key={index} className="flag-item">{flag}</li>
            ))}
          </ul>
        ) : (
          <div className="no-flags">✅ No critical risk flags</div>
        )}
      </section>

      {/* Warnings Section */}
      {report.warnings.length > 0 && (
        <section className="warnings-section">
          <h3>⚡ Warnings</h3>
          <ul className="warning-list">
            {report.warnings.map((warning, index) => (
              <li key={index} className="warning-item">{warning}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Recommendations Section */}
      <section className="recommendations-section">
        <h3>💡 Recommendations</h3>
        <ul className="recommendation-list">
          {report.recommendations.map((rec, index) => (
            <li key={index} className="recommendation-item">{rec}</li>
          ))}
        </ul>
      </section>

      {/* Metadata Section */}
      <section className="metadata-section">
        <div className="metadata-grid">
          <div className="metadata-item">
            <span className="metadata-label">Flagged for Review:</span>
            <span className={`metadata-value ${report.metadata.flagged ? 'flagged' : 'not-flagged'}`}>
              {report.metadata.flagged ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="metadata-item">
            <span className="metadata-label">Safety Score:</span>
            <span className="metadata-value">{report.metadata.safety_score.toFixed(2)}</span>
          </div>
          <div className="metadata-item">
            <span className="metadata-label">Safety Severity:</span>
            <span className={`metadata-value severity-${report.metadata.safety_severity}`}>
              {report.metadata.safety_severity}
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}

interface ScoreCardProps {
  label: string;
  value: number;
  max: number;
  threshold: number;
}

function ScoreCard({ label, value, max, threshold }: ScoreCardProps) {
  const percentage = (value / max) * 100;
  const status = percentage >= threshold ? 'good' : percentage >= threshold * 0.7 ? 'warning' : 'danger';

  return (
    <div className={`score-card ${status}`}>
      <div className="score-label">{label}</div>
      <div className="score-value">{value.toFixed(1)}</div>
      <div className="score-bar-container">
        <div className="score-bar" style={{ width: `${percentage}%` }}></div>
      </div>
      <div className="score-percentage">{percentage.toFixed(1)}%</div>
    </div>
  );
}

function formatFeatureName(name: string): string {
  // Add spaces before capitals
  return name.replace(/([A-Z])/g, ' $1').trim();
}
