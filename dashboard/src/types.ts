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
