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
}
