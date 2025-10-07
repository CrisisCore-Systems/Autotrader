import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { fetchTokenDetail, fetchTokenSummaries } from './api';
import { TokenDetail, TokenSummary } from './types';
import { TokenList } from './components/TokenList';
import { TokenDetailPanel } from './components/TokenDetail';

export default function App() {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

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

  return (
    <div className="app-shell">
      <header className="header">
        <h1>VoidBloom Oracle</h1>
        <span>{new Date().toLocaleString()}</span>
      </header>

      {tokensQuery.isLoading ? (
        <div>Loading token scores…</div>
      ) : tokensQuery.isError ? (
        <div>Failed to load tokens: {(tokensQuery.error as Error)?.message}</div>
      ) : (
        <div className="dashboard-layout">
          <TokenList tokens={sortedTokens} selectedSymbol={selectedSymbol} onSelect={setSelectedSymbol} />
          {detailQuery.isLoading || !detailQuery.data ? (
            <div className="token-detail">Loading analytics…</div>
          ) : detailQuery.isError ? (
            <div className="token-detail">Unable to load detail view.</div>
          ) : (
            <TokenDetailPanel token={detailQuery.data} />
          )}
        </div>
      )}
    </div>
  );
}
