/**
 * Sentiment Trend Chart Component
 * Time-series visualization of Twitter sentiment with dual y-axis
 */

import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ComposedChart,
  Area,
} from 'recharts';
import { fetchSentimentTrend } from '../api';
import { SentimentTrend } from '../types';

interface SentimentTrendChartProps {
  token: string;
  hours?: number;
}

export const SentimentTrendChart: React.FC<SentimentTrendChartProps> = ({
  token,
  hours = 24,
}) => {
  const [sentimentData, setSentimentData] = useState<SentimentTrend | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeframe, setTimeframe] = useState(hours);

  useEffect(() => {
    const loadSentiment = async () => {
      setLoading(true);
      try {
        const data = await fetchSentimentTrend(token, timeframe);
        setSentimentData(data);
      } catch (error) {
        console.error('Failed to load sentiment trend:', error);
      } finally {
        setLoading(false);
      }
    };

    if (token) {
      loadSentiment();
      const interval = setInterval(loadSentiment, 60000); // Refresh every minute
      return () => clearInterval(interval);
    }
  }, [token, timeframe]);

  if (loading) {
    return <div className="p-4">Loading sentiment trend...</div>;
  }

  if (!sentimentData || sentimentData.timestamps.length === 0) {
    return <div className="p-4 text-gray-500">No sentiment data available</div>;
  }

  // Prepare chart data
  const chartData = sentimentData.timestamps.map((timestamp, idx) => ({
    timestamp: new Date(timestamp * 1000).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    }),
    sentiment: sentimentData.sentiment_scores[idx],
    volume: sentimentData.tweet_volumes[idx],
    engagement: sentimentData.engagement_scores[idx],
  }));

  // Calculate metrics
  const avgSentiment =
    sentimentData.sentiment_scores.reduce((a, b) => a + b, 0) /
    sentimentData.sentiment_scores.length;
  const totalTweets = sentimentData.tweet_volumes.reduce((a, b) => a + b, 0);
  const avgEngagement =
    sentimentData.engagement_scores.reduce((a, b) => a + b, 0) /
    sentimentData.engagement_scores.length;

  // Detect sentiment trend
  const firstHalf = sentimentData.sentiment_scores.slice(
    0,
    Math.floor(sentimentData.sentiment_scores.length / 2)
  );
  const secondHalf = sentimentData.sentiment_scores.slice(
    Math.floor(sentimentData.sentiment_scores.length / 2)
  );
  const firstAvg = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
  const secondAvg = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;
  const trendDirection = secondAvg > firstAvg ? 'Improving' : 'Declining';
  const trendColor = secondAvg > firstAvg ? 'text-green-600' : 'text-red-600';

  return (
    <div className="sentiment-trend-chart">
      <div className="chart-header">
        <h3 className="text-xl font-bold">Sentiment Trend - {token}</h3>
        
        {/* Timeframe Selector */}
        <div className="flex gap-2">
          {[6, 12, 24, 48].map(h => (
            <button
              key={h}
              onClick={() => setTimeframe(h)}
              className={`px-3 py-1 rounded text-sm font-medium ${
                timeframe === h
                  ? 'bg-purple-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {h}h
            </button>
          ))}
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="sentiment-metrics">
        <div className="metric-card">
          <span className="metric-label">Avg Sentiment</span>
          <span className={`metric-value ${avgSentiment > 0 ? 'text-green-600' : 'text-red-600'}`}>
            {avgSentiment.toFixed(3)}
          </span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Total Tweets</span>
          <span className="metric-value text-blue-600">{totalTweets}</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Avg Engagement</span>
          <span className="metric-value text-purple-600">
            {avgEngagement.toFixed(2)}
          </span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Trend</span>
          <span className={`metric-value ${trendColor}`}>{trendDirection}</span>
        </div>
      </div>

      {/* Dual-axis Chart */}
      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart
          data={chartData}
          margin={{ top: 20, right: 60, left: 20, bottom: 5 }}
        >
          <defs>
            <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="timestamp"
            tick={{ fontSize: 11 }}
            interval={Math.floor(chartData.length / 8)}
          />
          <YAxis
            yAxisId="left"
            label={{ value: 'Sentiment Score', angle: -90, position: 'insideLeft' }}
            domain={[-1, 1]}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            label={{ value: 'Tweet Volume', angle: 90, position: 'insideRight' }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
            }}
          />
          <Legend />

          {/* Sentiment Score (Line + Area) */}
          <Area
            yAxisId="left"
            type="monotone"
            dataKey="sentiment"
            stroke="#8b5cf6"
            fill="url(#sentimentGradient)"
            strokeWidth={2}
            name="Sentiment Score"
          />

          {/* Tweet Volume (Bars) */}
          <Bar
            yAxisId="right"
            dataKey="volume"
            fill="#3b82f6"
            fillOpacity={0.5}
            name="Tweet Volume"
          />

          {/* Engagement Score (Line) */}
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="engagement"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={false}
            name="Engagement Score"
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Insights */}
      <div className="chart-insights">
        <h4 className="font-semibold mb-2">Sentiment Insights</h4>
        <ul className="text-sm space-y-1">
          {avgSentiment > 0.3 && (
            <li className="text-green-600">
              • <strong>Positive sentiment:</strong> Community perception is strongly favorable
            </li>
          )}
          {avgSentiment < -0.3 && (
            <li className="text-red-600">
              • <strong>Negative sentiment:</strong> Community perception is unfavorable
            </li>
          )}
          {Math.abs(avgSentiment) <= 0.3 && (
            <li className="text-blue-600">
              • <strong>Neutral sentiment:</strong> Mixed or ambivalent community perception
            </li>
          )}
          <li className={trendColor}>
            • <strong>Trend:</strong> Sentiment is {trendDirection.toLowerCase()} over time
          </li>
          <li>
            • <strong>Volume:</strong> {totalTweets} tweets analyzed in last {timeframe} hours
          </li>
          {avgEngagement > 10 && (
            <li className="text-purple-600">
              • <strong>High engagement:</strong> Tweets getting significant attention
            </li>
          )}
        </ul>
      </div>
    </div>
  );
};
