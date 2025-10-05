import { TokenDetail, TokenSummary } from './types';

const defaultBase = '/api';
const rawBase = import.meta.env.VITE_API_BASE_URL;
const API_BASE = (rawBase && rawBase.trim().length > 0 ? rawBase : defaultBase).replace(/\/$/, '');

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Request failed');
  }
  return (await response.json()) as T;
}

export async function fetchTokenSummaries(): Promise<TokenSummary[]> {
  const response = await fetch(`${API_BASE}/tokens`);
  return handleResponse<TokenSummary[]>(response);
}

export async function fetchTokenDetail(symbol: string): Promise<TokenDetail> {
  const response = await fetch(`${API_BASE}/tokens/${encodeURIComponent(symbol)}`);
  return handleResponse<TokenDetail>(response);
}
