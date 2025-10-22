import type { TokenSummary } from '../types';
import { EmptyState } from './EmptyState';

interface Props {
  tokens: TokenSummary[];
  selectedSymbol?: string | null;
  onSelect: (symbol: string) => void;
}

export function TokenList({ tokens, selectedSymbol, onSelect }: Props) {
  if (tokens.length === 0) {
    return (
      <div className="token-list">
        <EmptyState
          title="No Tokens Found"
          description="Try adjusting your search or filter criteria to find tokens."
          icon="🔍"
        />
      </div>
    );
  }

  const getFreshnessIndicator = (token: TokenSummary): string => {
    if (!token.freshness) return '';
    const sources = Object.values(token.freshness);
    if (sources.length === 0) return '';
    
    // Find the worst freshness level
    const levels = sources.map(s => s.freshness_level);
    if (levels.some(l => l === 'outdated')) return '🔴';
    if (levels.some(l => l === 'stale')) return '🟡';
    if (levels.some(l => l === 'recent')) return '🔵';
    return '🟢';
  };

  return (
    <div className="token-list">
      <div className="section-title">GemScore Radar ({tokens.length})</div>
      {tokens.map((token) => {
        const isSelected = token.symbol === selectedSymbol;
        const freshnessIndicator = getFreshnessIndicator(token);
        const isFreeData = token.provenance?.data_sources.every(source => 
          ['coingecko', 'dexscreener', 'blockscout', 'groq_ai'].includes(source)
        ) ?? true;
        
        return (
          <button
            key={token.symbol}
            type="button"
            className={`token-card${isSelected ? ' selected' : ''}`}
            onClick={() => onSelect(token.symbol)}
          >
            <div className="token-header">
              <div className="symbol">{token.symbol}</div>
              <div className="token-badges">
                {isFreeData && <span className="badge-mini badge-free">🆓</span>}
                {freshnessIndicator && <span className="badge-mini">{freshnessIndicator}</span>}
              </div>
            </div>
            <div className="score-line">
              <span>Final Score</span>
              <strong>{token.final_score.toFixed(1)}</strong>
            </div>
            <div className="score-line">
              <span>Confidence</span>
              <strong>{token.confidence.toFixed(0)}%</strong>
            </div>
            <div className="score-line">
              <span>Liquidity</span>
              <strong>${token.liquidity_usd.toLocaleString()}</strong>
            </div>
            {token.flagged && (
              <div className="token-flag">⚠️ Flagged</div>
            )}
          </button>
        );
      })}
    </div>
  );
}
