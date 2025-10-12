import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { fetchTokenDetail, fetchTokenSummaries } from './api';
import { TokenDetail, TokenSummary } from './types';
import { TokenList } from './components/TokenList';
import { TokenDetailPanel } from './components/TokenDetail';
import { LoadingSpinner } from './components/LoadingSpinner';
import { SearchBar, FilterBar } from './components/SearchBar';
import { ToastProvider } from './components/Toast';

export default function App() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterBy, setFilterBy] = useState('all');

  const tokensQuery = useQuery<TokenSummary[]>({
    queryKey: ['tokens'],
    queryFn: fetchTokenSummaries,
  });

  useEffect(() => {
    if (!selectedSymbol && tokensQuery.data && tokensQuery.data.length > 0) {
      setSelectedSymbol(tokensQuery.data[0].symbol);
    }
  }, [selectedSymbol, tokensQuery.data]);

  const detailQuery = useQuery<TokenDetail>({
    queryKey: ['token', selectedSymbol?.toUpperCase()],
    queryFn: () => fetchTokenDetail(selectedSymbol ?? ''),
    enabled: Boolean(selectedSymbol),
  });

  const filteredAndSortedTokens = useMemo(() => {
    if (!tokensQuery.data) {
      return [];
    }
    
    let tokens = [...tokensQuery.data];
    
    // Apply search filter
    if (searchQuery) {
      tokens = tokens.filter((token) =>
        token.symbol.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }
    
    // Apply category filter
    if (filterBy !== 'all') {
      tokens = tokens.filter((token) => {
        switch (filterBy) {
          case 'flagged':
            return token.flagged;
          case 'high-confidence':
            return token.confidence >= 75;
          case 'high-score':
            return token.final_score >= 70;
          default:
            return true;
        }
      });
    }
    
    // Sort by final score
    return tokens.sort((a, b) => b.final_score - a.final_score);
  }, [tokensQuery.data, searchQuery, filterBy]);

  const filterOptions = [
    { label: 'All', value: 'all' },
    { label: 'High Score', value: 'high-score' },
    { label: 'High Confidence', value: 'high-confidence' },
    { label: 'Flagged', value: 'flagged' },
  ];

  return (
    <ToastProvider>
      <div className="app-shell">
        <header className="header">
          <h1>VoidBloom Oracle</h1>
          <span>{new Date().toLocaleString()}</span>
        </header>

        {tokensQuery.isLoading ? (
          <LoadingSpinner message="Scanning token data..." />
        ) : tokensQuery.isError ? (
          <div>Failed to load tokens: {(tokensQuery.error as Error)?.message}</div>
        ) : (
          <div className="dashboard-layout">
            <div className="sidebar">
              <SearchBar onSearch={setSearchQuery} placeholder="Search tokens..." />
              <FilterBar options={filterOptions} selected={filterBy} onSelect={setFilterBy} />
              <TokenList 
                tokens={filteredAndSortedTokens} 
                selectedSymbol={selectedSymbol} 
                onSelect={setSelectedSymbol} 
              />
            </div>
            <div className="main-content">
              {detailQuery.isLoading || !detailQuery.data ? (
                <LoadingSpinner message="Analyzing token details..." />
              ) : detailQuery.isError ? (
                <div className="token-detail">Unable to load detail view.</div>
              ) : (
                <TokenDetailPanel token={detailQuery.data} />
              )}
            </div>
          </div>
        )}
      </div>
    </ToastProvider>
  );
}
