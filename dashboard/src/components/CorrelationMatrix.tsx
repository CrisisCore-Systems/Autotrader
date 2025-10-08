/**
 * Correlation Matrix Component
 * Heatmap visualization of cross-token correlations
 */

import React, { useState, useEffect } from 'react';
import { fetchCorrelationMatrix } from '../api';
import { TokenCorrelation } from '../types';

interface CorrelationMatrixProps {
  tokens: string[];
  metric?: 'price' | 'volume' | 'sentiment';
}

export const CorrelationMatrix: React.FC<CorrelationMatrixProps> = ({
  tokens,
  metric = 'price',
}) => {
  const [correlations, setCorrelations] = useState<TokenCorrelation[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedMetric, setSelectedMetric] = useState(metric);

  useEffect(() => {
    const loadCorrelations = async () => {
      setLoading(true);
      try {
        const data = await fetchCorrelationMatrix(selectedMetric);
        setCorrelations(data);
      } catch (error) {
        console.error('Failed to load correlations:', error);
      } finally {
        setLoading(false);
      }
    };

    loadCorrelations();
    const interval = setInterval(loadCorrelations, 30000); // Refresh every 30s

    return () => clearInterval(interval);
  }, [selectedMetric]);

  // Build correlation matrix
  const buildMatrix = () => {
    const matrix: Record<string, Record<string, number>> = {};
    
    // Initialize matrix
    tokens.forEach(tokenA => {
      matrix[tokenA] = {};
      tokens.forEach(tokenB => {
        if (tokenA === tokenB) {
          matrix[tokenA][tokenB] = 1.0; // Perfect correlation with self
        } else {
          matrix[tokenA][tokenB] = 0.0; // Default
        }
      });
    });

    // Fill matrix with correlation data
    correlations.forEach(corr => {
      if (matrix[corr.token_a] && matrix[corr.token_a][corr.token_b] !== undefined) {
        matrix[corr.token_a][corr.token_b] = corr.correlation;
      }
      if (matrix[corr.token_b] && matrix[corr.token_b][corr.token_a] !== undefined) {
        matrix[corr.token_b][corr.token_a] = corr.correlation;
      }
    });

    return matrix;
  };

  const getCorrelationColor = (correlation: number): string => {
    // Strong positive correlation (0.7 to 1.0) = dark green
    // Moderate positive (0.3 to 0.7) = light green
    // Weak (−0.3 to 0.3) = gray
    // Moderate negative (−0.7 to −0.3) = light red
    // Strong negative (−1.0 to −0.7) = dark red

    const abs = Math.abs(correlation);
    
    if (correlation > 0.7) return '#059669'; // emerald-600
    if (correlation > 0.3) return '#34d399'; // emerald-400
    if (correlation > -0.3) return '#d1d5db'; // gray-300
    if (correlation > -0.7) return '#fca5a5'; // red-300
    return '#dc2626'; // red-600
  };

  const getCorrelationLabel = (correlation: number): string => {
    const abs = Math.abs(correlation);
    const sign = correlation >= 0 ? 'Positive' : 'Negative';
    
    if (abs > 0.7) return `Strong ${sign}`;
    if (abs > 0.3) return `Moderate ${sign}`;
    return 'Weak';
  };

  const matrix = buildMatrix();

  if (loading) {
    return <div className="p-4">Loading correlation matrix...</div>;
  }

  return (
    <div className="correlation-matrix">
      <div className="matrix-header">
        <h3 className="text-xl font-bold">Cross-Token Correlation Matrix</h3>
        
        {/* Metric Selector */}
        <div className="flex gap-2">
          {(['price', 'volume', 'sentiment'] as const).map(m => (
            <button
              key={m}
              onClick={() => setSelectedMetric(m)}
              className={`px-3 py-1 rounded text-sm font-medium ${
                selectedMetric === m
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="correlation-legend">
        <span className="legend-label">Correlation Strength:</span>
        <div className="legend-colors">
          <div className="legend-item">
            <div className="color-box" style={{ backgroundColor: '#dc2626' }}></div>
            <span>Strong Negative</span>
          </div>
          <div className="legend-item">
            <div className="color-box" style={{ backgroundColor: '#fca5a5' }}></div>
            <span>Weak Negative</span>
          </div>
          <div className="legend-item">
            <div className="color-box" style={{ backgroundColor: '#d1d5db' }}></div>
            <span>No Correlation</span>
          </div>
          <div className="legend-item">
            <div className="color-box" style={{ backgroundColor: '#34d399' }}></div>
            <span>Weak Positive</span>
          </div>
          <div className="legend-item">
            <div className="color-box" style={{ backgroundColor: '#059669' }}></div>
            <span>Strong Positive</span>
          </div>
        </div>
      </div>

      {/* Matrix Grid */}
      <div className="matrix-grid">
        <div className="matrix-table">
          {/* Header Row */}
          <div className="matrix-row header-row">
            <div className="matrix-cell corner-cell"></div>
            {tokens.map(token => (
              <div key={token} className="matrix-cell header-cell">
                {token}
              </div>
            ))}
          </div>

          {/* Data Rows */}
          {tokens.map(tokenA => (
            <div key={tokenA} className="matrix-row">
              <div className="matrix-cell header-cell">{tokenA}</div>
              {tokens.map(tokenB => {
                const correlation = matrix[tokenA]?.[tokenB] ?? 0;
                return (
                  <div
                    key={`${tokenA}-${tokenB}`}
                    className="matrix-cell data-cell"
                    style={{ backgroundColor: getCorrelationColor(correlation) }}
                    title={`${tokenA} vs ${tokenB}: ${correlation.toFixed(3)} (${getCorrelationLabel(correlation)})`}
                  >
                    {correlation.toFixed(2)}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Insights */}
      <div className="matrix-insights">
        <h4 className="font-semibold mb-2">Insights</h4>
        <ul className="text-sm space-y-1">
          <li>
            • <strong>Strong positive correlation:</strong> Tokens tend to move together
          </li>
          <li>
            • <strong>Strong negative correlation:</strong> Tokens tend to move in opposite directions
          </li>
          <li>
            • <strong>Weak correlation:</strong> Token movements are largely independent
          </li>
          <li>
            • Use this matrix to identify diversification opportunities and correlated risk
          </li>
        </ul>
      </div>
    </div>
  );
};
