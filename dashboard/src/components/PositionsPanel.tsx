/**
 * PositionsPanel Component
 * Displays active positions with P&L and exposure tracking
 */

import React, { useEffect, useState } from 'react';
import './PositionsPanel.css';

interface Position {
  ticker: string;
  shares: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  exposure_pct: number;
}

export const PositionsPanel: React.FC = () => {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchPositions = async () => {
    try {
      const res = await fetch('/api/trading/positions');
      if (!res.ok) throw new Error('Failed to fetch positions');

      const data = await res.json();
      setPositions(data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="positions-panel loading">Loading positions...</div>;
  }

  if (error) {
    return <div className="positions-panel error">Error: {error}</div>;
  }

  const totalValue = positions.reduce((sum, p) => sum + p.market_value, 0);
  const totalPnL = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
  const totalPnLPct = totalValue > 0 ? (totalPnL / (totalValue - totalPnL)) * 100 : 0;

  return (
    <div className="positions-panel">
      <div className="positions-header">
        <h3>Active Positions</h3>
        <div className="portfolio-summary">
          <div className="summary-item">
            <span className="label">Total Value:</span>
            <span className="value">${totalValue.toFixed(2)}</span>
          </div>
          <div className="summary-item">
            <span className="label">Total P&L:</span>
            <span
              className="value"
              style={{ color: totalPnL >= 0 ? '#10b981' : '#ef4444' }}
            >
              {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)} ({totalPnL >= 0 ? '+' : ''}
              {totalPnLPct.toFixed(2)}%)
            </span>
          </div>
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="no-positions">
          <p>No active positions</p>
          <p className="hint">Place an order to start trading</p>
        </div>
      ) : (
        <div className="positions-table">
          <div className="table-header">
            <div className="col">Ticker</div>
            <div className="col">Shares</div>
            <div className="col">Avg Price</div>
            <div className="col">Current</div>
            <div className="col">Value</div>
            <div className="col">P&L</div>
            <div className="col">Exposure</div>
          </div>

          {positions.map((position) => (
            <div key={position.ticker} className="table-row">
              <div className="col ticker">{position.ticker}</div>
              <div className="col">{position.shares}</div>
              <div className="col">${position.avg_price.toFixed(2)}</div>
              <div className="col">${position.current_price.toFixed(2)}</div>
              <div className="col">${position.market_value.toFixed(2)}</div>
              <div className="col">
                <div
                  className="pnl-cell"
                  style={{
                    color: position.unrealized_pnl >= 0 ? '#10b981' : '#ef4444',
                  }}
                >
                  <span className="pnl-value">
                    {position.unrealized_pnl >= 0 ? '+' : ''}$
                    {position.unrealized_pnl.toFixed(2)}
                  </span>
                  <span className="pnl-pct">
                    ({position.unrealized_pnl >= 0 ? '+' : ''}
                    {position.unrealized_pnl_pct.toFixed(2)}%)
                  </span>
                </div>
              </div>
              <div className="col">
                <div className="exposure-cell">
                  <div className="exposure-bar">
                    <div
                      className="exposure-fill"
                      style={{ width: `${position.exposure_pct}%` }}
                    />
                  </div>
                  <span className="exposure-pct">{position.exposure_pct.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
