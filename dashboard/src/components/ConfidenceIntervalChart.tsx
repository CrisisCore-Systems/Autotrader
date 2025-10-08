/**
 * Confidence Interval Chart Component
 * Visualizes values with statistical confidence bands
 */

import React from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

interface ConfidenceIntervalChartProps {
  title: string;
  value: number;
  lowerBound: number;
  upperBound: number;
  confidenceLevel: number;
  unit?: string;
}

export const ConfidenceIntervalChart: React.FC<ConfidenceIntervalChartProps> = ({
  title,
  value,
  lowerBound,
  upperBound,
  confidenceLevel,
  unit = '',
}) => {
  // Create data points for visualization
  const data = [
    { x: 0, value: lowerBound, upper: upperBound, lower: lowerBound },
    { x: 1, value: value, upper: upperBound, lower: lowerBound },
    { x: 2, value: upperBound, upper: upperBound, lower: lowerBound },
  ];

  const formatValue = (val: number) => {
    if (unit === '$') {
      return `$${val.toFixed(2)}`;
    }
    if (unit === '%') {
      return `${(val * 100).toFixed(2)}%`;
    }
    return val.toFixed(4);
  };

  const range = upperBound - lowerBound;
  const uncertainty = ((range / value) * 100).toFixed(1);

  return (
    <div className="confidence-interval-chart">
      <div className="chart-header">
        <h3 className="chart-title">{title}</h3>
        <div className="confidence-badge">
          {(confidenceLevel * 100).toFixed(0)}% Confidence
        </div>
      </div>

      <div className="metrics-grid">
        <div className="metric-item">
          <span className="metric-label">Value</span>
          <span className="metric-value main-value">{formatValue(value)}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Lower Bound</span>
          <span className="metric-value lower-bound">{formatValue(lowerBound)}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Upper Bound</span>
          <span className="metric-value upper-bound">{formatValue(upperBound)}</span>
        </div>
        <div className="metric-item">
          <span className="metric-label">Uncertainty</span>
          <span className="metric-value">±{uncertainty}%</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="confidenceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis dataKey="x" hide />
          <YAxis 
            domain={[lowerBound * 0.95, upperBound * 1.05]} 
            tickFormatter={formatValue}
          />
          <Tooltip
            formatter={(val: number) => formatValue(val)}
            labelFormatter={() => ''}
            contentStyle={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
            }}
          />
          <Area
            type="monotone"
            dataKey="upper"
            stroke="#3b82f6"
            fillOpacity={0}
            strokeWidth={2}
            strokeDasharray="5 5"
          />
          <Area
            type="monotone"
            dataKey="lower"
            stroke="#3b82f6"
            fill="url(#confidenceGradient)"
            strokeWidth={2}
            strokeDasharray="5 5"
          />
          <ReferenceLine
            y={value}
            stroke="#10b981"
            strokeWidth={3}
            label={{
              value: 'Estimated Value',
              position: 'insideTopRight',
              fill: '#10b981',
              fontSize: 12,
            }}
          />
        </AreaChart>
      </ResponsiveContainer>

      <div className="chart-footer">
        <p className="uncertainty-note">
          We are {(confidenceLevel * 100).toFixed(0)}% confident the true value lies between{' '}
          <strong>{formatValue(lowerBound)}</strong> and{' '}
          <strong>{formatValue(upperBound)}</strong>
        </p>
      </div>
    </div>
  );
};
