import { TokenDetail, TokenSummary, ExperimentSummary, ExperimentDetail, ExperimentComparison } from './types';

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

// Health and observability endpoints
export async function fetchSLAStatus(): Promise<any[]> {
  const response = await fetch(`${API_BASE}/health/sla`);
  return handleResponse<any[]>(response);
}

export async function fetchCircuitBreakers(): Promise<any[]> {
  const response = await fetch(`${API_BASE}/health/circuit-breakers`);
  return handleResponse<any[]>(response);
}

// ============================================================================
// Experiments API
// ============================================================================

export async function fetchExperiments(params?: {
  limit?: number;
  tag?: string;
  search?: string;
}): Promise<ExperimentSummary[]> {
  const queryParams = new URLSearchParams();
  if (params?.limit) queryParams.set('limit', params.limit.toString());
  if (params?.tag) queryParams.set('tag', params.tag);
  if (params?.search) queryParams.set('search', params.search);
  
  const url = `${API_BASE}/experiments${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
  const response = await fetch(url);
  return handleResponse<ExperimentSummary[]>(response);
}

export async function fetchExperimentDetail(
  configHash: string,
  options?: {
    includeResults?: boolean;
    includeTree?: boolean;
  }
): Promise<ExperimentDetail> {
  const queryParams = new URLSearchParams();
  if (options?.includeResults !== undefined) {
    queryParams.set('include_results', options.includeResults.toString());
  }
  if (options?.includeTree !== undefined) {
    queryParams.set('include_tree', options.includeTree.toString());
  }
  
  const url = `${API_BASE}/experiments/${configHash}${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
  const response = await fetch(url);
  return handleResponse<ExperimentDetail>(response);
}

export async function fetchExperimentMetrics(configHash: string): Promise<any> {
  const response = await fetch(`${API_BASE}/experiments/${configHash}/metrics`);
  return handleResponse<any>(response);
}

export async function fetchExecutionTree(configHash: string): Promise<any> {
  const response = await fetch(`${API_BASE}/experiments/${configHash}/tree`);
  return handleResponse<any>(response);
}

export async function compareExperiments(
  hash1: string,
  hash2: string,
  includeMetrics: boolean = true
): Promise<ExperimentComparison> {
  const queryParams = new URLSearchParams();
  queryParams.set('include_metrics', includeMetrics.toString());
  
  const url = `${API_BASE}/experiments/compare/${hash1}/${hash2}?${queryParams.toString()}`;
  const response = await fetch(url);
  return handleResponse<ExperimentComparison>(response);
}

export async function fetchAllTags(): Promise<{ tags: string[]; tag_counts: Record<string, number> }> {
  const response = await fetch(`${API_BASE}/experiments/tags/all`);
  return handleResponse<{ tags: string[]; tag_counts: Record<string, number> }>(response);
}

export async function exportExperiment(
  configHash: string,
  format: 'json' | 'pdf' = 'json',
  options?: {
    includeMetrics?: boolean;
    includeConfig?: boolean;
  }
): Promise<{ status: string; file_path?: string; message?: string }> {
  const response = await fetch(`${API_BASE}/experiments/export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      config_hash: configHash,
      format,
      include_metrics: options?.includeMetrics ?? true,
      include_config: options?.includeConfig ?? true,
    }),
  });
  return handleResponse<any>(response);
}

export async function deleteExperiment(configHash: string): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE}/experiments/${configHash}`, {
    method: 'DELETE',
  });
  return handleResponse<{ status: string; message: string }>(response);
}
