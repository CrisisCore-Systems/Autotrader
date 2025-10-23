/**
 * TradingRunboard Component
 * Displays session date, market regime (SPY/VIX), and Phase 2 validation progress
 */

import React, { useEffect, useState } from 'react';
import './TradingRunboard.css';

interface MarketRegime {
  timestamp: string;
  regime: string;
  spy_price: number;
  spy_ma200: number;
  spy_above_ma: boolean;
  spy_day_change_pct: number;
  vix_level: number;
  vix_regime: string;
  allow_penny_trading: boolean;
  reason: string;
}

interface Phase2Progress {
  phase: string;
  status: string;
  trades_completed: number;
  trades_target: number;
  progress_pct: number;
  win_rate: number;
  win_rate_target_min: number;
  win_rate_target_max: number;
  total_pnl: number;
  active_trades: number;
  baseline_win_rate: number;
}

export const TradingRunboard: React.FC = () => {
  const [regime, setRegime] = useState<MarketRegime | null>(null);
  const [phase2, setPhase2] = useState<Phase2Progress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [regimeRes, phase2Res] = await Promise.all([
        fetch('/api/trading/regime'),
        fetch('/api/trading/phase2-progress'),
      ]);

      if (!regimeRes.ok || !phase2Res.ok) {
        throw new Error('Failed to fetch trading data');
      }

      const regimeData = await regimeRes.json();
      const phase2Data = await phase2Res.json();

      setRegime(regimeData);
      setPhase2(phase2Data);
      setLoading(false);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="runboard loading">Loading runboard...</div>;
  }

  if (error) {
    return <div className="runboard error">Error: {error}</div>;
  }

  const getRegimeColor = (regime: string) => {
    switch (regime) {
      case 'risk_on':
        return '#10b981';
      case 'risk_off':
        return '#ef4444';
      default:
        return '#f59e0b';
    }
  };

  const getProgressColor = (pct: number) => {
    if (pct < 25) return '#ef4444';
    if (pct < 50) return '#f59e0b';
    if (pct < 75) return '#3b82f6';
    return '#10b981';
  };

  return (
    <div className="runboard">
      <div className="runboard-header">
        <h2>Trading Runboard</h2>
        <div className="session-date">
          {new Date().toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </div>
      </div>

      <div className="runboard-content">
        {/* Market Regime Section */}
        <div className="regime-card">
          <h3>Market Regime</h3>
          <div className="regime-status">
            <div
              className="regime-indicator"
              style={{ backgroundColor: getRegimeColor(regime?.regime || 'neutral') }}
            >
              {regime?.regime?.toUpperCase().replace('_', ' ')}
            </div>
            {regime?.allow_penny_trading ? (
              <span className="trading-status allowed">✓ Trading Allowed</span>
            ) : (
              <span className="trading-status blocked">✗ Trading Blocked</span>
            )}
          </div>

          <div className="regime-metrics">
            <div className="metric">
              <span className="label">SPY:</span>
              <span className="value">
                ${regime?.spy_price.toFixed(2)}
                {regime?.spy_above_ma ? ' ✓' : ' ✗'}
              </span>
              <span className="sublabel">
                {regime?.spy_day_change_pct >= 0 ? '+' : ''}
                {regime?.spy_day_change_pct.toFixed(2)}%
              </span>
            </div>

            <div className="metric">
              <span className="label">MA200:</span>
              <span className="value">${regime?.spy_ma200.toFixed(2)}</span>
            </div>

            <div className="metric">
              <span className="label">VIX:</span>
              <span className="value">{regime?.vix_level.toFixed(2)}</span>
              <span className="sublabel">{regime?.vix_regime}</span>
            </div>
          </div>

          <div className="regime-reason">{regime?.reason}</div>
        </div>

        {/* Phase 2 Progress Section */}
        <div className="phase2-card">
          <h3>Phase 2 Validation Progress</h3>

          <div className="progress-bar-container">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: `${phase2?.progress_pct || 0}%`,
                  backgroundColor: getProgressColor(phase2?.progress_pct || 0),
                }}
              />
            </div>
            <div className="progress-text">
              {phase2?.trades_completed || 0} / {phase2?.trades_target || 20} trades
              ({phase2?.progress_pct.toFixed(0)}%)
            </div>
          </div>

          <div className="phase2-metrics">
            <div className="metric-box">
              <div className="metric-label">Win Rate</div>
              <div className="metric-value" style={{
                color: (phase2?.win_rate || 0) >= phase2?.win_rate_target_min ? '#10b981' : '#f59e0b'
              }}>
                {phase2?.win_rate.toFixed(1)}%
              </div>
              <div className="metric-target">
                Target: {phase2?.win_rate_target_min}-{phase2?.win_rate_target_max}%
              </div>
            </div>

            <div className="metric-box">
              <div className="metric-label">Total P&L</div>
              <div
                className="metric-value"
                style={{ color: (phase2?.total_pnl || 0) >= 0 ? '#10b981' : '#ef4444' }}
              >
                ${phase2?.total_pnl.toFixed(2)}
              </div>
              <div className="metric-target">Paper Trading</div>
            </div>

            <div className="metric-box">
              <div className="metric-label">Active Trades</div>
              <div className="metric-value">{phase2?.active_trades || 0}</div>
              <div className="metric-target">In Progress</div>
            </div>

            <div className="metric-box">
              <div className="metric-label">Improvement</div>
              <div className="metric-value" style={{ color: '#3b82f6' }}>
                +{((phase2?.win_rate || 0) - (phase2?.baseline_win_rate || 0)).toFixed(1)}%
              </div>
              <div className="metric-target">vs Baseline</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
