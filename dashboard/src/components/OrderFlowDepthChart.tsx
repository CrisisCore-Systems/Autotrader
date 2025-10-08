/**
 * Order Flow Depth Chart Component
 * Visualizes order book depth with bids/asks
 */

import React, { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { fetchOrderFlow } from '../api';
import { OrderFlowSnapshot } from '../types';

interface OrderFlowDepthChartProps {
  token: string;
}

export const OrderFlowDepthChart: React.FC<OrderFlowDepthChartProps> = ({ token }) => {
  const [orderFlow, setOrderFlow] = useState<OrderFlowSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadOrderFlow = async () => {
      setLoading(true);
      try {
        const data = await fetchOrderFlow(token);
        setOrderFlow(data);
      } catch (error) {
        console.error('Failed to load order flow:', error);
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      loadOrderFlow();
      const interval = setInterval(loadOrderFlow, 10000); // Refresh every 10s
      return () => clearInterval(interval);
    }
  }, [token]);

  if (loading) {
    return <div className="p-4">Loading order flow data...</div>;
  }

  if (!orderFlow) {
    return <div className="p-4 text-gray-500">No order flow data available</div>;
  }

  // Prepare chart data - combine bids and asks
  // Take top 15 levels from each side
  const topBids = orderFlow.bids.slice(0, 15).reverse();
  const topAsks = orderFlow.asks.slice(0, 15);

  const chartData = [
    ...topBids.map(([price, volume]) => ({
      price: price.toFixed(6),
      bid: volume,
      ask: 0,
      type: 'bid',
    })),
    ...topAsks.map(([price, volume]) => ({
      price: price.toFixed(6),
      bid: 0,
      ask: volume,
      type: 'ask',
    })),
  ];

  const formatValue = (value: number) => {
    if (value >= 1e6) return `$${(value / 1e6).toFixed(2)}M`;
    if (value >= 1e3) return `$${(value / 1e3).toFixed(2)}K`;
    return `$${value.toFixed(2)}`;
  };

  const imbalancePercent = (orderFlow.imbalance * 100).toFixed(1);
  const imbalanceDirection = orderFlow.imbalance > 0 ? 'Buy' : 'Sell';
  const imbalanceColor = orderFlow.imbalance > 0 ? 'text-green-600' : 'text-red-600';

  return (
    <div className="orderflow-chart">
      <div className="chart-header">
        <h3 className="text-xl font-bold">Order Book Depth - {token}</h3>
        <div className="timestamp text-sm text-gray-500">
          {new Date(orderFlow.timestamp * 1000).toLocaleTimeString()}
        </div>
      </div>

      {/* Depth Metrics */}
      <div className="depth-metrics">
        <div className="metric-card bid-card">
          <span className="metric-label">Bid Depth</span>
          <span className="metric-value text-green-600">
            {formatValue(orderFlow.bid_depth_usd)}
          </span>
        </div>

        <div className="metric-card imbalance-card">
          <span className="metric-label">Imbalance</span>
          <span className={`metric-value ${imbalanceColor}`}>
            {imbalancePercent}% {imbalanceDirection}
          </span>
        </div>

        <div className="metric-card ask-card">
          <span className="metric-label">Ask Depth</span>
          <span className="metric-value text-red-600">
            {formatValue(orderFlow.ask_depth_usd)}
          </span>
        </div>
      </div>

      {/* Depth Chart */}
      <ResponsiveContainer width="100%" height={400}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 20, right: 30, left: 80, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis type="number" tickFormatter={(val) => val.toFixed(2)} />
          <YAxis 
            type="category" 
            dataKey="price" 
            tick={{ fontSize: 10 }}
            interval={1}
          />
          <Tooltip
            formatter={(value: number, name: string) => [
              `${value.toFixed(4)} tokens`,
              name === 'bid' ? 'Bids' : 'Asks',
            ]}
            contentStyle={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
            }}
          />
          <Legend />
          <Bar 
            dataKey="bid" 
            fill="#10b981" 
            name="Bids" 
            stackId="depth"
          />
          <Bar 
            dataKey="ask" 
            fill="#ef4444" 
            name="Asks" 
            stackId="depth"
          />
        </BarChart>
      </ResponsiveContainer>

      {/* Insights */}
      <div className="chart-insights">
        <h4 className="font-semibold mb-2">Order Book Insights</h4>
        <ul className="text-sm space-y-1">
          {orderFlow.imbalance > 0.2 && (
            <li className="text-green-600">
              • <strong>Strong buy pressure:</strong> Bid depth significantly exceeds ask depth
            </li>
          )}
          {orderFlow.imbalance < -0.2 && (
            <li className="text-red-600">
              • <strong>Strong sell pressure:</strong> Ask depth significantly exceeds bid depth
            </li>
          )}
          {Math.abs(orderFlow.imbalance) <= 0.2 && (
            <li className="text-blue-600">
              • <strong>Balanced book:</strong> Relatively even buy and sell pressure
            </li>
          )}
          <li>
            • <strong>Total liquidity:</strong>{' '}
            {formatValue(orderFlow.bid_depth_usd + orderFlow.ask_depth_usd)} within shown levels
          </li>
        </ul>
      </div>
    </div>
  );
};
