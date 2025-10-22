export interface DataSourceInfo {
  source_name: string;
  last_updated: string;
  data_age_seconds: number;
  freshness_level: 'fresh' | 'recent' | 'stale' | 'outdated';
  is_free: boolean;
  update_frequency_seconds?: number;
}

export interface ProvenanceInfo {
  artifact_id?: string;
  data_sources: string[];
  pipeline_version?: string;
  created_at?: string;
  clickable_links?: Record<string, string>;
}

export interface EvidencePanel {
  title: string;
  confidence: number;
  freshness: string;
  source: string;
  is_free: boolean;
  data: any;
}

export interface TokenSummary {
  symbol: string;
  final_score: number;
  gem_score: number;
  confidence: number;
  flagged: boolean;
  price: number;
  liquidity_usd: number;
  holders: number;
  narrative_momentum: number;
  sentiment_score: number;
  updated_at: string;
  provenance?: ProvenanceInfo;
  freshness?: Record<string, DataSourceInfo>;
}

export interface ExecutionTreeNode {
  key: string;
  title: string;
  description: string;
  outcome?: {
    status: 'success' | 'failure' | 'skipped';
    summary: string;
    data: Record<string, unknown>;
  } | null;
  children: ExecutionTreeNode[];
}

export interface NewsItem {
  title: string;
  summary: string;
  link: string;
  source: string;
  published_at: string | null;
}

export interface TokenDetail extends TokenSummary {
  raw_features: Record<string, number>;
  adjusted_features: Record<string, number>;
  contributions: Record<string, number>;
  market_snapshot: {
    symbol: string;
    timestamp: string;
    price: number;
    volume_24h: number;
    liquidity_usd: number;
    holders: number;
    onchain_metrics: Record<string, number>;
    narratives: string[];
  };
  narrative: {
    sentiment_score: number;
    momentum: number;
    themes: string[];
    volatility: number;
    meme_momentum: number;
  };
  safety_report: {
    score: number;
    severity: string;
    findings: string[];
    flags: Record<string, boolean>;
  };
  news_items: NewsItem[];
  sentiment_metrics: Record<string, number>;
  technical_metrics: Record<string, number>;
  security_metrics: Record<string, number>;
  unlock_events: { date: string; percent_supply: number }[];
  narratives: string[];
  keywords: string[];
  artifact: {
    markdown: string;
    html: string;
  };
  tree: ExecutionTreeNode;
  evidence_panels?: Record<string, EvidencePanel>;
}

// ============================================================================
// Experiment Types
// ============================================================================

export interface ExperimentSummary {
  config_hash: string;
  short_hash: string;
  created_at: string;
  description: string;
  tags: string[];
  feature_count: number;
  has_results: boolean;
}

export interface ExperimentConfig {
  feature_names: string[];
  feature_weights: Record<string, number>;
  hyperparameters: Record<string, any>;
  feature_transformations: Record<string, string>;
  description: string;
  tags: string[];
  created_at: string;
  config_hash: string;
}

export interface ExperimentMetrics {
  precision_at_k: number;
  average_return_at_k: number;
  extended_metrics?: {
    ic_pearson?: number;
    ic_spearman?: number;
    sharpe_ratio?: number;
    sortino_ratio?: number;
    max_drawdown?: number;
    win_rate?: number;
  };
  baseline_results?: Record<string, {
    precision: number;
    avg_return: number;
  }>;
  flagged_assets?: string[];
}

export interface ExperimentDetail {
  config: ExperimentConfig;
  config_hash: string;
  created_at: string;
  results?: any;
  metrics?: ExperimentMetrics;
  execution_tree?: ExecutionTreeNode;
}

export interface ExperimentComparison {
  config1_hash: string;
  config2_hash: string;
  features: {
    only_in_config1: string[];
    only_in_config2: string[];
    common: string[];
  };
  weight_differences: Record<string, {
    config1: number;
    config2: number;
    diff: number;
  }>;
  hyperparameters: {
    config1: Record<string, any>;
    config2: Record<string, any>;
  };
  metrics_comparison?: {
    config1: ExperimentMetrics;
    config2: ExperimentMetrics;
    deltas: {
      precision_delta: number;
      return_delta: number;
    };
  };
}
