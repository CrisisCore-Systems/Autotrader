// AutoTrader Data Oracle v1 – Phase 1–2 Pipeline (TypeScript Implementation)

import 'dotenv/config';
import { createClient, SupabaseClient } from '@supabase/supabase-js';
import Parser from 'rss-parser';
// Pinecone is optional; we'll import dynamically only if configured

type TokenPayload = {
  news: Array<Record<string, unknown>>;
  social: Array<Record<string, unknown>>;
  onchain: Record<string, unknown>;
  technical: Record<string, unknown>;
  timestamp: string;
};

type Sentiment = {
  NVI: number;
  MMS: number;
  mythVectors: string[];
  topics: string[];
};

type TechnicalAnalysis = {
  APS: number;
  RSS: number;
  RRR: number;
};

type ContractSecurity = {
  ERR: number;
  OCW: boolean;
  ACI: number;
};

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_ANON_KEY;
const supabase: SupabaseClient | null = (SUPABASE_URL && SUPABASE_KEY)
  ? createClient(SUPABASE_URL, SUPABASE_KEY)
  : null;
const parser = new Parser();

const COINGECKO_TOKEN_MAP: Record<string, string> = {
  ETH: 'ethereum',
  KAS: 'kaspa',
  MANTA: 'manta-network',
  BTC: 'bitcoin',
};

const RSS_FEEDS: Record<string, string> = {
  CoinDesk: 'https://www.coindesk.com/arc/outboundfeeds/rss/',
  Cointelegraph: 'https://cointelegraph.com/rss',
  Decrypt: 'https://decrypt.co/feed',
  TheBlock: 'https://www.theblock.co/rss.xml',
};

// --- Data Ingestion ---
async function ingestSources(token: string): Promise<TokenPayload> {
  const [news, social, onchain, technical] = await Promise.all([
    fetchNews(token),
    fetchSocial(token),
    fetchOnchain(token),
    fetchTechnical(token),
  ]);

  return {
    news,
    social,
    onchain,
    technical,
    timestamp: new Date().toISOString(),
  };
}

async function fetchNews(token: string): Promise<Array<Record<string, unknown>>> {
  const [cryptoCompare, rss] = await Promise.all([
    fetchNewsCryptoCompare(token),
    fetchNewsRss(token),
  ]);
  return [...cryptoCompare, ...rss].slice(0, 24);
}

async function fetchNewsCryptoCompare(token: string) {
  const response = await fetch(
    `https://min-api.cryptocompare.com/data/v2/news/?lang=EN&categories=${token}`
  );
  const json = await response.json();
  if (!json?.Data) return [];
  return json.Data.map((item: any) => ({
    title: item.title,
    url: item.url,
    body: item.body,
    source: item.source,
    published: new Date(item.published_on * 1000).toISOString(),
  }));
}

async function fetchNewsRss(token: string) {
  const tokenLower = token.toLowerCase();
  const feeds = await Promise.all(
    Object.entries(RSS_FEEDS).map(async ([source, url]) => {
      try {
        const feed = await parser.parseURL(url);
        const entries = feed.items
          .filter((entry) =>
            `${entry.title} ${entry.contentSnippet}`.toLowerCase().includes(tokenLower)
          )
          .slice(0, 4)
          .map((entry) => ({
            title: entry.title,
            url: entry.link,
            body: entry.contentSnippet,
            source,
            published: entry.isoDate ?? new Date().toISOString(),
          }));
        return entries;
      } catch (error) {
        console.warn('RSS error', source, error);
        return [];
      }
    })
  );
  return feeds.flat();
}

async function fetchSocial(token: string): Promise<Array<Record<string, unknown>>> {
  const [reddit, stocktwits, twitter] = await Promise.all([
    fetchReddit(token),
    fetchStocktwits(token),
    fetchTwitter(token),
  ]);
  return [...reddit, ...stocktwits, ...twitter];
}

async function fetchReddit(token: string) {
  const response = await fetch(
    `https://www.reddit.com/search.json?q=${encodeURIComponent(token)}&sort=new&limit=20`,
    {
      headers: { 'User-Agent': 'AutoTraderBotTS/1.0' },
    }
  );
  const json = await response.json();
  return json?.data?.children?.map((child: any) => ({
    title: child.data.title,
    url: `https://www.reddit.com${child.data.permalink}`,
    score: child.data.score,
    num_comments: child.data.num_comments,
    created: new Date(child.data.created_utc * 1000).toISOString(),
    source: 'reddit',
  })) ?? [];
}

async function fetchStocktwits(token: string) {
  const response = await fetch(`https://api.stocktwits.com/api/2/streams/symbol/${token}.json`);
  const json = await response.json();
  return json?.messages?.map((message: any) => ({
    title: message.body,
    url: message.links?.[0]?.url,
    score: message.likes?.total ?? 0,
    num_comments: message.replies?.total ?? 0,
    created: message.created_at,
    source: 'stocktwits',
  })) ?? [];
}

async function fetchTwitter(token: string) {
  try {
    const feed = await parser.parseURL(
      `https://nitter.net/search/rss?f=tweets&q=%24${token}%20OR%20${token}`
    );
    return feed.items.slice(0, 15).map((entry) => ({
      title: entry.title,
      url: entry.link,
      score: 0,
      num_comments: 0,
      created: entry.isoDate ?? new Date().toISOString(),
      source: 'twitter',
    }));
  } catch (error) {
    console.warn('Twitter RSS error', error);
    return [];
  }
}

async function fetchOnchain(token: string): Promise<Record<string, unknown>> {
  const geckoId = COINGECKO_TOKEN_MAP[token] ?? token.toLowerCase();
  const [coingecko, dex] = await Promise.all([
    fetch(`https://api.coingecko.com/api/v3/coins/${geckoId}?localization=false&tickers=false&community_data=true&developer_data=true&sparkline=false`).then((res) => res.json()),
    fetch(`https://api.dexscreener.com/latest/dex/search/?q=${geckoId}`).then((res) => res.json()),
  ]);

  const market = coingecko?.market_data ?? {};
  const community = coingecko?.community_data ?? {};
  const developer = coingecko?.developer_data ?? {};
  const pairs = dex?.pairs ?? [];
  const primary = pairs.sort((a: any, b: any) => (b?.liquidity?.usd ?? 0) - (a?.liquidity?.usd ?? 0))[0];

  return {
    market_cap: market.market_cap?.usd,
    total_volume: market.total_volume?.usd,
    price_change_24h: market.price_change_percentage_24h,
    community_score: coingecko?.community_score,
    commits_4w: developer.commit_count_4_weeks,
    reddit_subscribers: community.reddit_subscribers,
    twitter_followers: community.twitter_followers,
    dex_liquidity_usd: primary?.liquidity?.usd,
    dex_volume_24h: primary?.volume?.h24,
    dex_pair: primary?.url,
  };
}

async function fetchTechnical(token: string): Promise<Record<string, unknown>> {
  const geckoId = COINGECKO_TOKEN_MAP[token] ?? token.toLowerCase();
  const response = await fetch(
    `https://api.coingecko.com/api/v3/coins/${geckoId}/market_chart?vs_currency=usd&days=90`
  );
  const json = await response.json();
  return {
    prices: json?.prices?.map((row: [number, number]) => row[1]) ?? [],
    volumes: json?.total_volumes?.map((row: [number, number]) => row[1]) ?? [],
  };
}

// --- Storage ---
async function storeRawData(token: string, payload: TokenPayload) {
  if (!supabase) {
    console.warn('[storeRawData] Supabase not configured; skipping raw payload insert');
    return;
  }
  const { error } = await supabase.from('token_data').insert([
    { token, payload: JSON.stringify(payload), timestamp: payload.timestamp },
  ]);
  if (error) console.warn('[storeRawData] Insert error:', error.message);
}

// --- Embedding & Vector DB ---
async function embedAndStore(token: string, payload: TokenPayload) {
  const { embedding } = await getGptEmbedding(payload);
  console.log(`Embedding for ${token} length:`, embedding.length);

  // Prefer Pinecone if configured, else fallback to Supabase vector table, else log
  const usePinecone = !!process.env.PINECONE_API_KEY && !!process.env.PINECONE_INDEX;
  const useSupabaseVector = !!supabase && !!process.env.SUPABASE_VECTOR_TABLE;

  if (usePinecone) {
    await persistToPinecone(token, embedding, payload);
    return;
  }

  if (useSupabaseVector) {
    await persistToSupabase(token, embedding, payload);
    return;
  }

  console.warn('[embedAndStore] No vector store configured. Set PINECONE_API_KEY/PINECONE_INDEX or SUPABASE_VECTOR_TABLE');
}

async function persistToPinecone(token: string, embedding: number[], payload: TokenPayload) {
  try {
    const { Pinecone } = await import('@pinecone-database/pinecone');
    const apiKey = process.env.PINECONE_API_KEY as string;
    const indexName = process.env.PINECONE_INDEX as string;
    const pc = new Pinecone({ apiKey });

    // Ensure index exists (best-effort): dimension must match embedding length
    try {
      const indexes = await pc.listIndexes();
      const exists = indexes.indexes?.some((i: any) => i.name === indexName);
      if (!exists) {
        console.warn(`[pinecone] Index "${indexName}" not found. Please create it with dimension=${embedding.length}`);
      }
    } catch (_) {
      // ignore list errors in restricted environments
    }

    const index = pc.index(indexName);
    const id = `${token}-${Date.now()}`;
    await index.upsert([
      {
        id,
        values: embedding,
        metadata: {
          token,
          timestamp: payload.timestamp,
        } as Record<string, any>,
      },
    ]);
    console.log('[pinecone] upserted vector id', id);
  } catch (err: any) {
    console.warn('[pinecone] persist error:', err?.message || err);
  }
}

async function persistToSupabase(token: string, embedding: number[], payload: TokenPayload) {
  if (!supabase) {
    console.warn('[supabase] client not configured; skipping');
    return;
  }
  const table = process.env.SUPABASE_VECTOR_TABLE as string; // e.g., 'embeddings'
  const id = `${token}-${Date.now()}`;
  // Assumes table has columns: id (text), token (text), embedding (vector or json), timestamp (timestamptz)
  const row: any = {
    id,
    token,
    embedding,
    timestamp: payload.timestamp,
  };
  const { error } = await supabase.from(table).upsert(row);
  if (error) {
    console.warn('[supabase] upsert error:', error.message);
  } else {
    console.log('[supabase] upserted vector id', id);
  }
}

async function getGptEmbedding(payload: TokenPayload): Promise<{ embedding: number[] }> {
  const summary = `${payload.news.map((n) => n.title).join(' ')} ${payload.social
    .map((s) => s.title)
    .join(' ')}`;
  const words = summary.split(/\s+/).filter(Boolean);
  const vector = new Array(32).fill(0).map((_, index) => {
    const word = words[index % words.length] ?? '';
    let hash = 0;
    for (const char of word) {
      hash = (hash * 31 + char.charCodeAt(0)) % 997;
    }
    return hash / 997;
  });
  return { embedding: vector };
}

// --- Sentiment Synthesis ---
function synthesizeSentiment(token: string, payload: TokenPayload): Sentiment {
  const text = `${payload.news.map((n) => n.title).join(' ')} ${payload.social
    .map((s) => s.title)
    .join(' ')}`.toLowerCase();
  const mythVectors = ['rebirth', 'corruption', 'innovation'].filter((myth) =>
    text.includes(myth)
  );
  const topics = Array.from(new Set(text.split(/\W+/).slice(0, 5))).filter(Boolean);
  const sentimentScore = text.includes('hack') ? 0.2 : 0.6;
  const memeScore = payload.social.length / 50;
  return {
    NVI: Math.max(0, Math.min(1, sentimentScore)),
    MMS: Math.max(0, Math.min(1, memeScore)),
    mythVectors: mythVectors.length ? mythVectors : ['neutral'],
    topics,
  };
}

// --- Technical Intelligence ---
function technicalAnalysis(token: string, payload: TokenPayload): TechnicalAnalysis {
  const prices = payload.technical.prices as number[];
  if (!prices?.length) {
    return { APS: 0.5, RSS: 0.5, RRR: 1.0 };
  }
  const latest = prices[prices.length - 1];
  const earliest = prices[0];
  const trend = (latest - earliest) / earliest;
  return {
    APS: Math.max(0, Math.min(1, 1 - Math.abs(trend))),
    RSS: Math.max(0, Math.min(1, trend + 0.5)),
    RRR: Math.max(0.5, Math.min(4, (latest / earliest) * 2)),
  };
}

// --- Contract & Security ---
function contractSecurity(token: string, payload: TokenPayload): ContractSecurity {
  const onchain = payload.onchain;
  const liquidity = Number(onchain.dex_liquidity_usd ?? 0);
  const commits = Number(onchain.commits_4w ?? 0);
  const volume = Number(onchain.total_volume ?? 0);
  const marketCap = Number(onchain.market_cap ?? 0) || 1;
  const err = Math.max(0.05, 1 - (volume / marketCap) * 0.4 - commits * 0.02 - liquidity / 1_000_000);
  const aci = Math.max(0, Math.min(1, commits / 20 + liquidity / 5_000_000));
  const ocw = (onchain.reddit_subscribers as number) > 1000;
  return {
    ERR: Math.min(1, err),
    OCW: ocw,
    ACI: aci,
  };
}

// --- Fusion & Scoring ---
function fuseSignals(
  token: string,
  analysis: TechnicalAnalysis,
  sentiment: Sentiment,
  contract: ContractSecurity
): number {
  const errInv = 1 / (contract.ERR + 1e-6);
  return (
    0.4 * analysis.APS +
    0.3 * sentiment.NVI +
    0.2 * Math.tanh(errInv / 10) +
    0.1 * Math.min(1, analysis.RRR / 5)
  );
}

// --- Main Orchestration ---
async function main(tokens: string[]) {
  for (const token of tokens) {
    const raw = await ingestSources(token);
    await storeRawData(token, raw);
    await embedAndStore(token, raw);
    const sentiment = synthesizeSentiment(token, raw);
    const analysis = technicalAnalysis(token, raw);
    const contract = contractSecurity(token, raw);
    const score = fuseSignals(token, analysis, sentiment, contract);
    console.log(`${token}: Final Score = ${score.toFixed(2)}`);
  }
}

main(['ETH', 'KAS', 'MANTA']);
