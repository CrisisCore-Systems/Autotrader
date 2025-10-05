import type { TokenSummary } from '../types';

interface Props {
  tokens: TokenSummary[];
  selectedSymbol?: string | null;
  onSelect: (symbol: string) => void;
}

export function TokenList({ tokens, selectedSymbol, onSelect }: Props) {
  return (
    <div className="token-list">
      <div className="section-title">GemScore Radar</div>
      {tokens.map((token) => {
        const isSelected = token.symbol === selectedSymbol;
        return (
          <button
            key={token.symbol}
            type="button"
            className={`token-card${isSelected ? ' selected' : ''}`}
            onClick={() => onSelect(token.symbol)}
          >
            <div className="symbol">{token.symbol}</div>
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
          </button>
        );
      })}
    </div>
  );
}
