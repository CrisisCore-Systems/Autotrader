import { formatDistanceToNowStrict, parseISO } from 'date-fns';

import type { TokenDetail } from '../types';
import { ScoreChart } from './ScoreChart';
import { TreeView } from './TreeView';
import { EvidencePanel } from './EvidencePanel';

interface Props {
  token: TokenDetail;
}

function renderMetricEntries(entries: Record<string, number>) {
  return Object.entries(entries)
    .filter(([, value]) => Number.isFinite(value))
    .map(([key, value]) => (
      <div key={key} className="metric">
        <span>{key}</span>
        <strong>{value.toFixed(2)}</strong>
      </div>
    ));
}

function renderNewsDate(iso: string | null) {
  if (!iso) {
    return 'Unknown';
  }
  try {
    return formatDistanceToNowStrict(parseISO(iso), { addSuffix: true });
  } catch (error) {
    return iso;
  }
}

export function TokenDetailPanel({ token }: Props) {
  const sentimentMetrics = renderMetricEntries(token.sentiment_metrics);
  const technicalMetrics = renderMetricEntries(token.technical_metrics);
  const securityMetrics = renderMetricEntries(token.security_metrics);

  return (
    <div className="token-detail">
      <div>
        <div className="section-title">{token.symbol} composite signal</div>
        <div className="score-grid">
          <div className="score-pill">
            <h3>Final Score</h3>
            <span>{token.final_score.toFixed(2)}</span>
            <small>GemScore + composite metrics</small>
          </div>
          <div className="score-pill">
            <h3>GemScore</h3>
            <span>{token.gem_score.toFixed(2)}</span>
            <small>Weighted across eight features</small>
          </div>
          <div className="score-pill">
            <h3>Confidence</h3>
            <span>{token.confidence.toFixed(0)}%</span>
            <small>Recency × data completeness</small>
          </div>
          <div className="score-pill">
            <h3>Liquidity</h3>
            <span>${token.market_snapshot.liquidity_usd.toLocaleString()}</span>
            <small>24h depth snapshot</small>
          </div>
        </div>
      </div>

      <div className="detail-grid">
        <div className="panel">
          <div className="section-title">GemScore contributions</div>
          <ScoreChart contributions={token.contributions} />
        </div>
        <div className="panel">
          <div className="section-title">Sentiment & Narrative</div>
          <div className="metrics-grid">{sentimentMetrics}</div>
          <div className="section-title" style={{ marginTop: '1rem' }}>
            Themes
          </div>
          <div>{token.narrative.themes.length ? token.narrative.themes.join(', ') : 'No dominant themes'}</div>
        </div>
        <div className="panel">
          <div className="section-title">Technical & Security</div>
          <div className="metrics-grid">
            {technicalMetrics}
            {securityMetrics}
          </div>
          <div className="section-title" style={{ marginTop: '1rem' }}>
            Safety Status
          </div>
          <div>
            <strong>{token.safety_report.score.toFixed(2)}</strong> – {token.safety_report.severity}
          </div>
          {token.safety_report.findings.length ? (
            <div style={{ marginTop: '0.5rem' }}>
              Flags: {token.safety_report.findings.join(', ')}
            </div>
          ) : (
            <div style={{ marginTop: '0.5rem' }}>No critical flags</div>
          )}
        </div>
      </div>

      <div className="detail-grid">
        <div className="panel">
          <div className="section-title">Upcoming unlocks</div>
          <div className="unlocks">
            {token.unlock_events.length ? (
              token.unlock_events.map((unlock) => (
                <div key={unlock.date} className="unlock-card">
                  <strong>{new Date(unlock.date).toLocaleDateString()}</strong>
                  <span>{unlock.percent_supply.toFixed(2)}% of supply</span>
                </div>
              ))
            ) : (
              <div>No unlocks configured</div>
            )}
          </div>
        </div>
        <div className="panel">
          <div className="section-title">Latest headlines</div>
          <div className="news-list">
            {token.news_items.length ? (
              token.news_items.slice(0, 4).map((item) => (
                <article key={item.link || item.title} className="news-item">
                  <h4>{item.title}</h4>
                  <p>{item.summary || 'No summary available.'}</p>
                  <footer>
                    <span>{item.source}</span>
                    <span>{renderNewsDate(item.published_at)}</span>
                  </footer>
                </article>
              ))
            ) : (
              <div>No recent news captured.</div>
            )}
          </div>
        </div>
      </div>

      {token.evidence_panels && (
        <div className="panel">
          <div className="section-title">Evidence & Data Sources</div>
          {Object.entries(token.evidence_panels).map(([key, panel]) => (
            <EvidencePanel
              key={key}
              panel={panel}
              freshness={token.freshness?.[panel.source]}
              provenanceLink={token.provenance?.clickable_links?.[panel.source]}
            />
          ))}
        </div>
      )}

      <div className="panel">
        <div className="section-title">Tree-of-Thought execution</div>
        <TreeView node={token.tree} />
      </div>

      <div className="panel">
        <div className="section-title">Artifact excerpt</div>
        <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{token.artifact.markdown.slice(0, 2000)}</pre>
      </div>
    </div>
  );
}
