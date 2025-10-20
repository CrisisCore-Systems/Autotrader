import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { 
  fetchTokenDetail, 
  fetchTokenSummaries,
  fetchGemScoreConfidence,
  fetchLiquidityConfidence,
} from './api';
import { TokenDetail, TokenSummary } from './types';
import { TokenList } from './components/TokenList';
import { TokenDetailPanel } from './components/TokenDetail';
import { SLADashboard } from './components/SLADashboard';
import { AnomalyAlerts } from './components/AnomalyAlerts';
import { ConfidenceIntervalChart } from './components/ConfidenceIntervalChart';
import { CorrelationMatrix } from './components/CorrelationMatrix';
import { OrderFlowDepthChart } from './components/OrderFlowDepthChart';
import { SentimentTrendChart } from './components/SentimentTrendChart';
import { FeatureStoreViewer } from './components/FeatureStoreViewer';

type Tab = 'overview' | 'analytics' | 'system' | 'features';

export default function App() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');

  const tokensQuery = useQuery<TokenSummary[]>({
    queryKey: ['tokens'],
    queryFn: fetchTokenSummaries,
    refetchInterval: 10000, // Refetch every 10s
  });

  useEffect(() => {
    if (!selectedSymbol && tokensQuery.data && tokensQuery.data.length > 0) {
      setSelectedSymbol(tokensQuery.data[0].symbol);
    }
  }, [selectedSymbol, tokensQuery.data]);

  const detailQuery = useQuery<TokenDetail>({
    queryKey: ['token', selectedSymbol],
    queryFn: () => fetchTokenDetail(selectedSymbol ?? ''),
    enabled: Boolean(selectedSymbol),
  });

  const sortedTokens = useMemo(() => {
    if (!tokensQuery.data) {
      return [];
    }
    return [...tokensQuery.data].sort((a, b) => b.final_score - a.final_score);
  }, [tokensQuery.data]);

  const renderTabContent = () => {
    if (tokensQuery.isLoading) {
      return <div className="loading-state">Loading token scores…</div>;
    }

    if (tokensQuery.isError) {
      return (
        <div className="error-state">
          Failed to load tokens: {(tokensQuery.error as Error)?.message}
        </div>
      );
    }

    switch (activeTab) {
      case 'overview':
        return (
          <div className="dashboard-layout">
            <TokenList
              tokens={sortedTokens}
              selectedSymbol={selectedSymbol}
              onSelect={setSelectedSymbol}
            />
            {detailQuery.isLoading || !detailQuery.data ? (
              <div className="token-detail">Loading analytics…</div>
            ) : detailQuery.isError ? (
              <div className="token-detail">Unable to load detail view.</div>
            ) : (
              <TokenDetailPanel token={detailQuery.data} />
            )}
          </div>
        );

      case 'analytics':
        if (!selectedSymbol) {
          return <div className="empty-state">Please select a token to view analytics</div>;
        }
        return (
          <div className="analytics-layout">
            <div className="analytics-sidebar">
              <TokenList
                tokens={sortedTokens}
                selectedSymbol={selectedSymbol}
                onSelect={setSelectedSymbol}
              />
            </div>
            <div className="analytics-content">
              <h2 className="section-title">{selectedSymbol} Advanced Analytics</h2>
              
              {/* Confidence Intervals */}
              <div className="chart-section">
                <ConfidenceIntervalChart
                  title="GemScore Confidence"
                  value={detailQuery.data?.gem_score ?? 0}
                  lowerBound={0}
                  upperBound={100}
                  confidenceLevel={0.95}
                  unit=""
                />
                <ConfidenceIntervalChart
                  title="Liquidity Confidence"
                  value={detailQuery.data?.liquidity_usd ?? 0}
                  lowerBound={0}
                  upperBound={(detailQuery.data?.liquidity_usd ?? 0) * 1.2}
                  confidenceLevel={0.95}
                  unit="$"
                />
              </div>

              {/* Order Flow & Sentiment */}
              <div className="chart-section">
                <OrderFlowDepthChart token={selectedSymbol} />
                <SentimentTrendChart token={selectedSymbol} />
              </div>

              {/* Correlation Matrix */}
              <div className="chart-section full-width">
                <CorrelationMatrix tokens={sortedTokens.map(t => t.symbol).slice(0, 10)} />
              </div>
            </div>
          </div>
        );

      case 'system':
        return (
          <div className="system-layout">
            <div className="system-section">
              <AnomalyAlerts />
            </div>
            <div className="system-section">
              <SLADashboard />
            </div>
          </div>
        );

      case 'features':
        if (!selectedSymbol) {
          return <div className="empty-state">Please select a token to view features</div>;
        }
        return (
          <div className="features-layout">
            <div className="features-sidebar">
              <TokenList
                tokens={sortedTokens}
                selectedSymbol={selectedSymbol}
                onSelect={setSelectedSymbol}
              />
            </div>
            <div className="features-content">
              <FeatureStoreViewer token={selectedSymbol} />
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="app-shell">
      <header className="header">
        <div className="header-content">
          <h1>AutoTrader Oracle</h1>
          <span className="timestamp">{new Date().toLocaleString()}</span>
        </div>
        
        {/* Tab Navigation */}
        <nav className="tab-navigation">
          <button
            className={`tab-button ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            📊 Overview
          </button>
          <button
            className={`tab-button ${activeTab === 'analytics' ? 'active' : ''}`}
            onClick={() => setActiveTab('analytics')}
          >
            📈 Analytics
          </button>
          <button
            className={`tab-button ${activeTab === 'system' ? 'active' : ''}`}
            onClick={() => setActiveTab('system')}
          >
            🔧 System Health
          </button>
          <button
            className={`tab-button ${activeTab === 'features' ? 'active' : ''}`}
            onClick={() => setActiveTab('features')}
          >
            📦 Features
          </button>
        </nav>
      </header>

      <main className="main-content">{renderTabContent()}</main>
    </div>
  );
}
