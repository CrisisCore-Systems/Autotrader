"""VoidBloom Data Oracle v1 – Phase 1–2 Pipeline implementation."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import statistics
from html import escape
from pathlib import Path
from textwrap import shorten
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import feedparser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import nltk
import numpy as np
import pandas as pd
import requests
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer

DATA_DIR = Path("artifacts")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "voidbloom.db"


# --- Utility helpers -----------------------------------------------------
def get_utc_now() -> str:
    """Return the current UTC timestamp in ISO format."""

    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_request(url: str, *, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
    """Wrapper around ``requests.get`` with consistent error handling."""

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        if "application/json" in response.headers.get("Content-Type", ""):
            return response.json()
        return None
    except requests.RequestException:
        return None


# --- Data Ingestion ------------------------------------------------------
COINGECKO_TOKEN_MAP = {
    "ETH": "ethereum",
    "KAS": "kaspa",
    "MANTA": "manta-network",
    "BTC": "bitcoin",
}

TOKEN_CONTRACT_MAP = {
    "ETH": {"chain": "eth", "address": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"},  # WETH proxy
    "MANTA": {"chain": "eth", "address": "0x61E7427b9C6CfD02BA2fE5a0D75ee6d2bECd845d"},
}

RSS_NEWS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Cointelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "The Block": "https://www.theblock.co/rss.xml",
}


def ingest_sources(token: str) -> Dict[str, Any]:
    """Pull data for a token from news, social, on-chain, and technical APIs."""

    news = fetch_news(token)
    social = fetch_social(token)
    onchain = fetch_onchain(token)
    technical = fetch_technical(token)
    return {
        "token": token,
        "news": news,
        "social": social,
        "onchain": onchain,
        "technical": technical,
        "timestamp": get_utc_now(),
    }


def fetch_news(token: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Fetch news articles mentioning the token from multiple feeds."""

    crypto_compare = fetch_news_cryptocompare(token, limit=limit)
    rss_articles = fetch_news_rss(token, per_feed=max(2, limit // 2))
    combined = (crypto_compare + rss_articles)[: limit * 2]
    combined.sort(key=lambda item: item.get("published", ""), reverse=True)
    return combined


def fetch_news_cryptocompare(token: str, limit: int = 12) -> List[Dict[str, Any]]:
    url = "https://min-api.cryptocompare.com/data/v2/news/"
    raw = safe_request(url, params={"lang": "EN", "categories": token.upper()})
    articles: List[Dict[str, Any]] = []

    if not raw or "Data" not in raw:
        return articles

    for item in raw.get("Data", [])[:limit]:
        published = dt.datetime.fromtimestamp(item.get("published_on", 0), tz=dt.timezone.utc)
        articles.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "body": item.get("body"),
                "source": item.get("source"),
                "published": published.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            }
        )
    return articles


def fetch_news_rss(token: str, per_feed: int = 4) -> List[Dict[str, Any]]:
    token_lower = token.lower()
    collected: List[Dict[str, Any]] = []
    for source, url in RSS_NEWS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.entries[: per_feed * 3]:
            text = f"{entry.get('title', '')} {entry.get('summary', '')}"
            if token_lower not in text.lower():
                continue
            published = entry.get("published") or entry.get("updated")
            try:
                published_dt = dt.datetime(*entry.published_parsed[:6], tzinfo=dt.timezone.utc)
                published_iso = published_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            except Exception:
                published_iso = get_utc_now()
            collected.append(
                {
                    "title": entry.get("title"),
                    "url": entry.get("link"),
                    "body": entry.get("summary", ""),
                    "source": source,
                    "published": published_iso,
                }
            )
            if sum(1 for article in collected if article.get("source") == source) >= per_feed:
                break
    return collected


def fetch_social(token: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch social sentiment from Reddit, StockTwits, and Nitter."""

    reddit_posts = fetch_reddit(token, limit=limit)
    stocktwits_posts = fetch_stocktwits(token, limit=max(5, limit // 2))
    twitter_posts = fetch_twitter_nitter(token, limit=max(5, limit // 2))
    combined = reddit_posts + stocktwits_posts + twitter_posts
    combined.sort(key=lambda post: post.get("created", ""), reverse=True)
    return combined[: limit * 2]


def fetch_reddit(token: str, limit: int = 20) -> List[Dict[str, Any]]:
    url = "https://www.reddit.com/search.json"
    headers = {"User-Agent": "VoidBloomBot/1.0"}
    params = {"q": token, "sort": "new", "limit": limit}
    raw = safe_request(url, params=params, headers=headers)
    posts: List[Dict[str, Any]] = []

    if not raw:
        return posts

    for child in raw.get("data", {}).get("children", []):
        data = child.get("data", {})
        created = dt.datetime.fromtimestamp(data.get("created_utc", 0), tz=dt.timezone.utc)
        posts.append(
            {
                "title": data.get("title"),
                "url": f"https://www.reddit.com{data.get('permalink')}",
                "score": data.get("score", 0),
                "num_comments": data.get("num_comments", 0),
                "created": created.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "source": "reddit",
                "author": data.get("author"),
                "subreddit": data.get("subreddit"),
            }
        )
    return posts


def fetch_stocktwits(token: str, limit: int = 15) -> List[Dict[str, Any]]:
    symbol = f"{token.upper()}.X"
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    raw = safe_request(url)
    posts: List[Dict[str, Any]] = []

    if not raw:
        return posts

    for message in raw.get("messages", [])[:limit]:
        created_raw = message.get("created_at", "")
        try:
            created = dt.datetime.fromisoformat(created_raw.replace("Z", "+00:00")).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except Exception:
            created = created_raw
        posts.append(
            {
                "title": message.get("body"),
                "url": message.get("links", [{}])[0].get("url"),
                "score": message.get("likes", {}).get("total", 0),
                "num_comments": message.get("replies", {}).get("total", 0),
                "created": created,
                "source": "stocktwits",
                "author": message.get("user", {}).get("username"),
            }
        )
    return posts


def fetch_twitter_nitter(token: str, limit: int = 15) -> List[Dict[str, Any]]:
    url = f"https://nitter.net/search/rss?f=tweets&q=%24{token}%20OR%20{token}"
    posts: List[Dict[str, Any]] = []
    try:
        feed = feedparser.parse(url)
    except Exception:
        return posts

    for entry in feed.entries[:limit]:
        published_struct = getattr(entry, "published_parsed", None)
        if published_struct:
            published = (
                dt.datetime(*published_struct[:6], tzinfo=dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        else:
            published = entry.get("published") or get_utc_now()
        posts.append(
            {
                "title": entry.get("title"),
                "url": entry.get("link"),
                "score": 0,
                "num_comments": 0,
                "created": published,
                "source": "twitter",
                "author": entry.get("author"),
            }
        )
    return posts


def fetch_onchain(token: str) -> Dict[str, Any]:
    """Retrieve market and on-chain style metrics from multiple APIs."""

    gecko_snapshot = fetch_onchain_coingecko(token)
    dex = fetch_liquidity_profile(token)
    holders = fetch_holder_distribution(token)
    combined = {**gecko_snapshot, **dex, **holders}
    return combined


def fetch_onchain_coingecko(token: str) -> Dict[str, Any]:
    gecko_id = COINGECKO_TOKEN_MAP.get(token.upper(), token.lower())
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}"
    raw = safe_request(
        url,
        params={
            "localization": "false",
            "tickers": "false",
            "community_data": "true",
            "developer_data": "true",
            "sparkline": "false",
        },
    )

    if not raw:
        return {}

    market = raw.get("market_data", {})
    community = raw.get("community_data", {})
    developer = raw.get("developer_data", {})

    return {
        "market_cap": market.get("market_cap", {}).get("usd"),
        "total_volume": market.get("total_volume", {}).get("usd"),
        "circulating_supply": market.get("circulating_supply"),
        "price_change_24h": market.get("price_change_percentage_24h"),
        "market_cap_rank": market.get("market_cap_rank"),
        "community_score": raw.get("community_score"),
        "reddit_subscribers": community.get("reddit_subscribers"),
        "twitter_followers": community.get("twitter_followers"),
        "commit_count_4_weeks": developer.get("commit_count_4_weeks"),
        "developer_score": developer.get("developer_score"),
        "stars": developer.get("stars"),
    }


def fetch_liquidity_profile(token: str) -> Dict[str, Any]:
    gecko_id = COINGECKO_TOKEN_MAP.get(token.upper(), token.lower())
    url = f"https://api.dexscreener.com/latest/dex/search/?q={gecko_id}"
    raw = safe_request(url)

    if not raw:
        return {}

    pairs = raw.get("pairs", [])
    if not pairs:
        return {}

    primary = max(pairs, key=lambda pair: pair.get("liquidity", {}).get("usd", 0))
    liquidity = primary.get("liquidity", {}).get("usd")
    fdv = primary.get("fdv")
    volume_24h = primary.get("volume", {}).get("h24")

    return {
        "dex_liquidity_usd": liquidity,
        "dex_volume_24h": volume_24h,
        "dex_fdv": fdv,
        "dex_pair": primary.get("url"),
    }


def fetch_holder_distribution(token: str) -> Dict[str, Any]:
    meta = TOKEN_CONTRACT_MAP.get(token.upper())
    if not meta:
        return {}

    chain = meta["chain"]
    address = meta["address"]
    if chain != "eth":
        return {}

    url = f"https://api.ethplorer.io/getTopTokenHolders/{address}?apiKey=freekey&limit=20"
    raw = safe_request(url)

    if not raw or "holders" not in raw:
        return {}

    holders = raw.get("holders", [])
    total_share = sum(holder.get("share", 0) for holder in holders)
    whale_share = sum(holder.get("share", 0) for holder in holders[:5])
    gini = gini_coefficient([holder.get("share", 0) for holder in holders])

    return {
        "holder_top20_share": total_share,
        "holder_top5_share": whale_share,
        "holder_gini": gini,
    }


    }


def fetch_news(token: str, limit: int = 12) -> List[Dict[str, Any]]:
    """Fetch news articles mentioning the token from CryptoCompare."""

    url = "https://min-api.cryptocompare.com/data/v2/news/"
    raw = safe_request(url, params={"lang": "EN", "categories": token.upper()})
    articles: List[Dict[str, Any]] = []

    if not raw or "Data" not in raw:
        return articles

    for item in raw.get("Data", [])[:limit]:
        articles.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "body": item.get("body"),
                "source": item.get("source"),
                "published": dt.datetime.fromtimestamp(item.get("published_on", 0), tz=dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
            }
        )
    return articles


def fetch_social(token: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch Reddit discussions mentioning the token symbol."""

    url = "https://www.reddit.com/search.json"
    headers = {"User-Agent": "VoidBloomBot/1.0"}
    params = {"q": token, "sort": "new", "limit": limit}
    raw = safe_request(url, params=params, headers=headers)
    posts: List[Dict[str, Any]] = []

    if not raw:
        return posts

    for child in raw.get("data", {}).get("children", []):
        data = child.get("data", {})
        posts.append(
            {
                "title": data.get("title"),
                "url": f"https://www.reddit.com{data.get('permalink')}",
                "score": data.get("score", 0),
                "num_comments": data.get("num_comments", 0),
                "created": dt.datetime.fromtimestamp(data.get("created_utc", 0), tz=dt.timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z"),
                "subreddit": data.get("subreddit"),
            }
        )
    return posts


def fetch_onchain(token: str) -> Dict[str, Any]:
    """Retrieve market and on-chain style metrics from the CoinGecko API."""

    gecko_id = COINGECKO_TOKEN_MAP.get(token.upper(), token.lower())
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}"
    raw = safe_request(
        url,
        params={
            "localization": "false",
            "tickers": "false",
            "community_data": "true",
            "developer_data": "true",
            "sparkline": "false",
        },
    )

    if not raw:
        return {}

    market = raw.get("market_data", {})
    community = raw.get("community_data", {})
    developer = raw.get("developer_data", {})

    return {
        "market_cap": market.get("market_cap", {}).get("usd"),
        "total_volume": market.get("total_volume", {}).get("usd"),
        "circulating_supply": market.get("circulating_supply"),
        "price_change_24h": market.get("price_change_percentage_24h"),
        "market_cap_rank": market.get("market_cap_rank"),
        "community_score": raw.get("community_score"),
        "reddit_subscribers": community.get("reddit_subscribers"),
        "twitter_followers": community.get("twitter_followers"),
        "commit_count_4_weeks": developer.get("commit_count_4_weeks"),
    }


def fetch_technical(token: str, days: int = 90) -> Dict[str, Any]:
    """Fetch historical market data and derive common indicators."""

    gecko_id = COINGECKO_TOKEN_MAP.get(token.upper(), token.lower())
    url = f"https://api.coingecko.com/api/v3/coins/{gecko_id}/market_chart"
    raw = safe_request(url, params={"vs_currency": "usd", "days": days})

    if not raw:
        return {}

    prices = [price[1] for price in raw.get("prices", [])]
    volumes = [volume[1] for volume in raw.get("total_volumes", [])]

    if len(prices) < 30:
        return {}

    ema_12_series = exponential_moving_average(prices, window=12)
    ema_26_series = exponential_moving_average(prices, window=26)
    if ema_12_series.size == 0 or ema_26_series.size == 0:
        return {}
    macd_series = ema_12_series - ema_26_series
    signal_series = exponential_moving_average(macd_series, window=9)
    ema_12 = ema_12_series[-1]
    ema_26 = ema_26_series[-1]
    signal_line = signal_series[-1] if signal_series.size else 0.0
    macd_line = macd_series[-1]
    macd_hist = macd_line - signal_line
    rsi = relative_strength_index(prices, period=14)
    avg_volume = float(np.mean(volumes[-14:])) if volumes else 0.0
    price_trend = price_slope(prices[-30:])

    return {
        "latest_price": prices[-1],
        "ema_12": ema_12,
        "ema_26": ema_26,
        "macd": macd_line,
        "signal": signal_line,
        "macd_hist": macd_hist,
        "rsi": rsi,
        "avg_volume": avg_volume,
        "price_trend": price_trend,
        "prices": prices[-90:],
        "volumes": volumes[-90:],
    }


def exponential_moving_average(values: Iterable[float], window: int) -> np.ndarray:
    values = np.asarray(list(values), dtype=float)
    if values.size < window:
        return np.array([])
    alpha = 2 / (window + 1)
    ema = np.zeros_like(values)
    ema[:window] = values[:window]
    for i in range(window, len(values)):
        ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
    return ema


def relative_strength_index(values: Iterable[float], period: int = 14) -> float:
    series = pd.Series(list(values), dtype=float)
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else np.inf
    rsi = 100 - (100 / (1 + rs)) if rs != np.inf else 100.0
    return float(rsi)


def price_slope(prices: Iterable[float]) -> float:
    array = np.asarray(list(prices), dtype=float)
    if array.size < 2:
        return 0.0
    x = np.arange(len(array))
    slope, _ = np.polyfit(x, array, 1)
    return float(slope / array.mean())


def gini_coefficient(values: Sequence[float]) -> float:
    array = np.asarray([max(value, 0.0) for value in values], dtype=float)
    if array.size == 0:
        return 0.0
    sorted_array = np.sort(array)
    cumulative = np.cumsum(sorted_array)
    total = cumulative[-1]
    if total == 0:
        return 0.0
    index = np.arange(1, array.size + 1)
    gini = (2 * np.sum(index * sorted_array) / (array.size * total)) - (array.size + 1) / array.size
    return float(max(0.0, min(1.0, gini)))



    prices = [price[1] for price in raw.get("prices", [])]
    volumes = [volume[1] for volume in raw.get("total_volumes", [])]

    if len(prices) < 30:
        return {}

    ema_12_series = exponential_moving_average(prices, window=12)
    ema_26_series = exponential_moving_average(prices, window=26)
    if ema_12_series.size == 0 or ema_26_series.size == 0:
        return {}
    macd_series = ema_12_series - ema_26_series
    signal_series = exponential_moving_average(macd_series, window=9)
    ema_12 = ema_12_series[-1]
    ema_26 = ema_26_series[-1]
    signal_line = signal_series[-1] if signal_series.size else 0.0
    macd_line = macd_series[-1]
    macd_hist = macd_line - signal_line
    rsi = relative_strength_index(prices, period=14)
    avg_volume = float(np.mean(volumes[-14:])) if volumes else 0.0
    price_trend = price_slope(prices[-30:])

    return {
        "latest_price": prices[-1],
        "ema_12": ema_12,
        "ema_26": ema_26,
        "macd": macd_line,
        "signal": signal_line,
        "macd_hist": macd_hist,
        "rsi": rsi,
        "avg_volume": avg_volume,
        "price_trend": price_trend,
        "prices": prices[-90:],
        "volumes": volumes[-90:],
    }


def exponential_moving_average(values: Iterable[float], window: int) -> np.ndarray:
    values = np.asarray(list(values), dtype=float)
    if values.size < window:
        return np.array([])
    alpha = 2 / (window + 1)
    ema = np.zeros_like(values)
    ema[:window] = values[:window]
    for i in range(window, len(values)):
        ema[i] = alpha * values[i] + (1 - alpha) * ema[i - 1]
    return ema


def relative_strength_index(values: Iterable[float], period: int = 14) -> float:
    series = pd.Series(list(values), dtype=float)
    delta = series.diff().dropna()
    gain = delta.clip(lower=0).rolling(window=period).mean()
    loss = -delta.clip(upper=0).rolling(window=period).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else np.inf
    rsi = 100 - (100 / (1 + rs)) if rs != np.inf else 100.0
    return float(rsi)


def price_slope(prices: Iterable[float]) -> float:
    array = np.asarray(list(prices), dtype=float)
    if array.size < 2:
        return 0.0
    x = np.arange(len(array))
    slope, _ = np.polyfit(x, array, 1)
    return float(slope / array.mean())


# --- Storage -------------------------------------------------------------
def ensure_database(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS token_data (
            token TEXT,
            payload TEXT,
            timestamp TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS token_embeddings (
            token TEXT,
            embedding TEXT,
            summary TEXT,
            timestamp TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS token_index USING fts5(
            token,
            content,
            timestamp
        )
        """
    )
    conn.commit()
    return conn


def store_raw_data(token: str, payload: Dict[str, Any], db_path: Path = DB_PATH) -> None:
    conn = ensure_database(db_path)
    conn.execute("INSERT INTO token_data VALUES (?, ?, ?)", (token, json.dumps(payload), payload["timestamp"]))
    conn.commit()
    return conn


def store_raw_data(token: str, payload: Dict[str, Any], db_path: Path = DB_PATH) -> None:
    conn = ensure_database(db_path)
    conn.execute("INSERT INTO token_data VALUES (?, ?, ?)", (token, json.dumps(payload), payload["timestamp"]))
    conn.execute(
        "INSERT INTO token_index(token, content, timestamp) VALUES (?, ?, ?)",
        (
            token,
            build_index_document(payload),
            payload["timestamp"],
        ),
    )
    conn.commit()
    conn.close()


def embed_and_store(token: str, payload: Dict[str, Any], db_path: Path = DB_PATH) -> List[float]:
    conn = ensure_database(db_path)
    summary = summarize_payload(payload)
    embedding = compute_embedding(summary, conn)
    conn.execute(
        "INSERT INTO token_embeddings VALUES (?, ?, ?, ?)",
        (token, json.dumps(embedding), summary, payload["timestamp"]),
    )
    conn.commit()
    conn.close()
    return embedding


def summarize_payload(payload: Dict[str, Any]) -> str:
    top_news = [shorten(article.get("title", ""), width=120, placeholder="…") for article in payload.get("news", [])[:5]]
    top_social = [shorten(post.get("title", ""), width=120, placeholder="…") for post in payload.get("social", [])[:5]]
    return " | ".join(filter(None, ["News: " + "; ".join(top_news), "Social: " + "; ".join(top_social)]))


def compute_embedding(text: str, conn: sqlite3.Connection, dimensions: int = 32) -> List[float]:
    """Generate a TF-IDF dense embedding using historical summaries as corpus."""

    if not text:
        return [0.0] * dimensions

    cursor = conn.execute("SELECT summary FROM token_embeddings")
    corpus = [row[0] for row in cursor.fetchall() if row[0]] + [text]
    vectorizer = TfidfVectorizer(max_features=dimensions, stop_words="english")
    matrix = vectorizer.fit_transform(corpus)
    embedding = matrix[-1].toarray().ravel()
    if embedding.size < dimensions:
        embedding = np.pad(embedding, (0, dimensions - embedding.size))
    return embedding.tolist()[:dimensions]


def build_index_document(payload: Dict[str, Any]) -> str:
    news = "\n".join(f"{article.get('title', '')} {article.get('body', '')}" for article in payload.get("news", []))
    social = "\n".join(post.get("title", "") for post in payload.get("social", []))
    return f"{news}\n{social}"


def fetch_similar_tokens(token: str, embedding: List[float], db_path: Path = DB_PATH, limit: int = 3) -> List[Tuple[str, float]]:
    conn = ensure_database(db_path)
    cursor = conn.execute("SELECT token, embedding FROM token_embeddings WHERE token != ?", (token,))
    rows = cursor.fetchall()
    conn.close()

    target = np.asarray(embedding)
    if target.size == 0:
        return []

    similarities: List[Tuple[str, float]] = []
    for row in rows:
        other_token, other_embedding_json = row
        try:
            other_vector = np.asarray(json.loads(other_embedding_json))
        except Exception:
            continue
        if other_vector.size != target.size:
            min_len = min(other_vector.size, target.size)
            target_vector = target[:min_len]
            other_vector = other_vector[:min_len]
        else:
            target_vector = target
        denom = (np.linalg.norm(target_vector) * np.linalg.norm(other_vector)) or 1.0
        similarity = float(np.dot(target_vector, other_vector) / denom)
        similarities.append((other_token, similarity))

    similarities.sort(key=lambda item: item[1], reverse=True)
    return similarities[:limit]


def render_sparkline(values: Sequence[float]) -> str:
    if not values:
        return ""
    charset = "▁▂▃▄▅▆▇█"
    minimum = min(values)
    maximum = max(values)
    if minimum == maximum:
        return charset[0] * len(values)
    return "".join(
        charset[int((value - minimum) / (maximum - minimum) * (len(charset) - 1))] for value in values
    )


def craft_lore_capsule(
    token: str,
    sentiment: Dict[str, Any],
    analysis: Dict[str, Any],
    contract: Dict[str, Any],
    payload: Dict[str, Any],
) -> str:
    highlights: List[str] = []
    topics = sentiment.get("topics", [])
    if topics:
        highlights.append(f"Narratives: {', '.join(topics[:3])}")
    if contract.get("ERR") is not None:
        risk = "elevated" if contract.get("ERR", 0) > 0.6 else "controlled"
        highlights.append(f"Risk {risk} (ERR {contract.get('ERR', 0):.2f})")
    aps = analysis.get("APS", 0)
    rss = analysis.get("RSS", 0)
    if aps > 0.6 and rss > 0.6:
        highlights.append("Momentum-positive technicals")
    elif aps < 0.4:
        highlights.append("Technical structure fragile")
    social_sources = {post.get("source") for post in payload.get("social", [])}
    if social_sources:
        highlights.append("Social mix: " + ", ".join(sorted(filter(None, social_sources))))
    myth = sentiment.get("myth_vectors", [])
    if myth:
        highlights.append("Myths: " + ", ".join(myth))
    return "; ".join(highlights[:4]) or f"{token} awaiting richer data"


# --- Sentiment Synthesis -------------------------------------------------
def synthesize_sentiment(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    nltk_download("vader_lexicon")
    analyzer = SentimentIntensityAnalyzer()

    texts = [article.get("title", "") + " " + (article.get("body", "") or "") for article in payload.get("news", [])]
    texts.extend(post.get("title", "") for post in payload.get("social", []))
    combined_text = " ".join(texts) or token
    scores = [analyzer.polarity_scores(text)["compound"] for text in texts] or [0]
    avg_score = float(sum(scores) / len(scores))
    novelty = narrative_volatility(scores)
    meme = compute_mms(payload)
    myth_vectors = extract_myth_vectors(combined_text)
    topics = extract_topics(texts)
    belief_intensity = belief_score(texts)

    return {
        "NVI": normalize_score(avg_score + novelty + belief_intensity),
        "MMS": meme,
        "myth_vectors": myth_vectors,
        "topics": topics,
        "raw_sentiment": scores,
        "belief_intensity": belief_intensity,
    }


def embed_and_store(token: str, payload: Dict[str, Any], db_path: Path = DB_PATH) -> None:
    conn = ensure_database(db_path)
    summary = summarize_payload(payload)
    embedding = get_local_embedding(summary)
    conn.execute(
        "INSERT INTO token_embeddings VALUES (?, ?, ?, ?)",
        (token, json.dumps(embedding), summary, payload["timestamp"]),
    )
    conn.commit()
    conn.close()


def summarize_payload(payload: Dict[str, Any]) -> str:
    news_titles = ", ".join(article.get("title", "") for article in payload.get("news", [])[:5])
    social_titles = ", ".join(post.get("title", "") for post in payload.get("social", [])[:5])
    return f"News: {news_titles}. Social: {social_titles}."


def get_local_embedding(text: str) -> List[float]:
    """Generate a deterministic pseudo-embedding using hashing."""

    if not text:
        return [0.0] * 8

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Convert digest to eight floats between -1 and 1
    chunk_size = len(digest) // 8
    vector = []
    for i in range(0, len(digest), chunk_size):
        chunk = digest[i : i + chunk_size]
        if not chunk:
            continue
        integer = int.from_bytes(chunk, "big", signed=False)
        vector.append((integer % 2000) / 1000 - 1)
    return vector[:8]


# --- Sentiment Synthesis -------------------------------------------------
def synthesize_sentiment(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    nltk_download("vader_lexicon")
    analyzer = SentimentIntensityAnalyzer()

    texts = [article.get("title", "") + " " + (article.get("body", "") or "") for article in payload.get("news", [])]
    texts.extend(post.get("title", "") for post in payload.get("social", []))
    combined_text = " ".join(texts) or token
    scores = [analyzer.polarity_scores(text)["compound"] for text in texts] or [0]
    avg_score = float(sum(scores) / len(scores))
    novelty = narrative_volatility(scores)
    meme = compute_mms(payload)
    myth_vectors = extract_myth_vectors(combined_text)

    return {"NVI": normalize_score(avg_score + novelty), "MMS": meme, "myth_vectors": myth_vectors, "raw_sentiment": scores}


def nltk_download(package: str) -> None:
    try:
        nltk.data.find(f"sentiment/{package}")
    except LookupError:
        nltk.download(package, quiet=True)


def narrative_volatility(scores: Iterable[float]) -> float:
    if not scores:
        return 0.0
    if len(scores) == 1:
        return abs(scores[0]) / 4
    std_dev = statistics.pstdev(scores)
    return min(1.0, std_dev)


def normalize_score(value: float) -> float:
    return max(0.0, min(1.0, (value + 1) / 2))


def compute_mms(payload: Dict[str, Any]) -> float:
    posts = payload.get("social", [])
    if not posts:
        return 0.0

    engagement = [post.get("score", 0) + post.get("num_comments", 0) + (5 if post.get("source") == "twitter" else 0) for post in posts]
    recency_weights = []
    for post in posts:
        created = post.get("created")
        try:
            created_dt = dt.datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None
        except Exception:
            created_dt = None
        if created_dt:
            delta_hours = max(1, (dt.datetime.now(dt.timezone.utc) - created_dt).total_seconds() / 3600)
            recency_weights.append(1 / delta_hours)
        else:
            recency_weights.append(0.1)

    weighted = [eng * w for eng, w in zip(engagement, recency_weights)]
    top = sorted(weighted, reverse=True)[:5]
    momentum = sum(top) / (len(posts) or 1)
    return max(0.0, min(1.0, momentum))


MYTH_KEYWORDS = {
    "rebirth": ["rebirth", "revival", "phoenix", "renaissance"],
    "corruption": ["scam", "rug", "hack", "exploit"],
    "victory": ["surge", "rally", "breakout", "win"],
    "innovation": ["upgrade", "roadmap", "launch", "innov"],
}


def extract_myth_vectors(text: str) -> List[str]:
    lowered = text.lower()
    activated = [myth for myth, keywords in MYTH_KEYWORDS.items() if any(keyword in lowered for keyword in keywords)]
    return activated or ["neutral"]


def extract_topics(texts: List[str], top_k: int = 5) -> List[str]:
    corpus = [text for text in texts if text.strip()]
    if not corpus:
        return []
    vectorizer = TfidfVectorizer(max_features=64, stop_words="english")
    matrix = vectorizer.fit_transform(corpus)
    mean_scores = np.asarray(matrix.mean(axis=0)).ravel()
    indices = np.argsort(mean_scores)[::-1][:top_k]
    features = vectorizer.get_feature_names_out()
    return [features[idx] for idx in indices if idx < len(features)]


def belief_score(texts: List[str]) -> float:
    if not texts:
        return 0.0
    emphasis_keywords = ["must", "guaranteed", "soon", "definitely", "massive", "imminent"]
    count = sum(sum(1 for word in text.lower().split() if word in emphasis_keywords) for text in texts)
    normalized = min(1.0, count / (len(texts) * 3 or 1))
    return float(normalized / 2)


# --- Technical Intelligence ---------------------------------------------
def technical_analysis(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    technical = payload.get("technical", {})
    if not technical:
        return {"APS": 0.0, "RSS": 0.0, "RRR": 0.0, "indicators": technical}

    rsi = technical.get("rsi", 50)
    macd_hist = technical.get("macd_hist", 0)
    price_trend = technical.get("price_trend", 0)
    prices = technical.get("prices", [])
    volumes = technical.get("volumes", [])

    aps = 1 - abs(rsi - 50) / 50
    rss = normalize_score(macd_hist * 5 + price_trend)
    rrr = calculate_rrr(prices)
    volatility = rolling_volatility(prices, window=30)
    bbands = bollinger_bandwidth(prices)
    atr = average_true_range(prices)

    volume_trend = price_slope(volumes[-30:]) if volumes else 0.0
    enriched = {
        **technical,
        "volatility_30d": volatility,
        "bollinger_bandwidth": bbands,
        "atr14": atr,
        "volume_trend": volume_trend,
    }

    return {"APS": float(max(0, min(1, aps))), "RSS": rss, "RRR": rrr, "indicators": enriched}


def calculate_rrr(prices: List[float]) -> float:
    if len(prices) < 20:
        return 0.0
    recent = prices[-20:]
    current = recent[-1]
    high = max(recent)
    low = min(recent)
    risk = current - low
    reward = high - current
    if risk <= 0:
        return 0.0
    ratio = reward / risk if risk else 0
    return float(min(5.0, max(0.0, ratio)))


def rolling_volatility(prices: List[float], window: int = 30) -> float:
    if len(prices) < window:
        return 0.0
    series = pd.Series(prices[-window:], dtype=float)
    returns = series.pct_change().dropna()
    return float(returns.std())


def bollinger_bandwidth(prices: List[float], window: int = 20) -> float:
    if len(prices) < window:
        return 0.0
    series = pd.Series(prices[-window:], dtype=float)
    sma = series.mean()
    std = series.std()
    if sma == 0:
        return 0.0
    upper = sma + 2 * std
    lower = sma - 2 * std
    bandwidth = (upper - lower) / sma
    return float(max(0.0, bandwidth))


def average_true_range(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 0.0
    closes = pd.Series(prices[-(period + 1) :], dtype=float)
    high = closes.rolling(window=2).max().dropna()
    low = closes.rolling(window=2).min().dropna()
    prev_close = closes.shift(1).dropna()
    true_range = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.tail(period).mean()
    return float(atr)


# --- Contract & Security -------------------------------------------------
def contract_security(token: str, payload: Dict[str, Any], contract_addr: str) -> Dict[str, Any]:
    onchain = payload.get("onchain", {})
    market_cap = onchain.get("market_cap") or 0
    volume = onchain.get("total_volume") or 0
    community = onchain.get("community_score") or 0
    commits = onchain.get("commit_count_4_weeks") or 0
    liquidity = onchain.get("dex_liquidity_usd") or 0
    holder_gini = onchain.get("holder_gini") or 0

    liquidity_ratio = volume / market_cap if market_cap else 0
    liquidity_floor = normalize_score(math.tanh((liquidity or 0) / 1_000_000))
    stability = normalize_score(1 - abs((payload.get("technical", {}).get("price_trend", 0))) * 10)
    decentralization_penalty = holder_gini if holder_gini else 0.1
    err = max(
        0.01,
        1
        - (
            liquidity_ratio * 0.4
            + commits * 0.02
            + community * 0.01
            + liquidity_floor * 0.3
            - decentralization_penalty * 0.2
        ),
    )
    ocw = (onchain.get("reddit_subscribers", 0) or 0) > 1000 or (onchain.get("twitter_followers", 0) or 0) > 10000
    aci = normalize_score((commits / 10) + (community / 100) + liquidity_floor)

    return {
        "ERR": float(max(0.01, min(1.0, err))),
        "OCW": bool(ocw),
        "ACI": float(aci),
        "contract_addr": contract_addr,
        "stability": stability,
        "decentralization_penalty": decentralization_penalty,
    }


    engagement = [post.get("score", 0) + post.get("num_comments", 0) for post in posts]
    top = sorted(engagement, reverse=True)[:5]
    momentum = sum(top) / (len(posts) * 10 or 1)
    return max(0.0, min(1.0, momentum))


MYTH_KEYWORDS = {
    "rebirth": ["rebirth", "revival", "phoenix", "renaissance"],
    "corruption": ["scam", "rug", "hack", "exploit"],
    "victory": ["surge", "rally", "breakout", "win"],
    "innovation": ["upgrade", "roadmap", "launch", "innov"],
}


def extract_myth_vectors(text: str) -> List[str]:
    lowered = text.lower()
    activated = [myth for myth, keywords in MYTH_KEYWORDS.items() if any(keyword in lowered for keyword in keywords)]
    return activated or ["neutral"]


# --- Technical Intelligence ---------------------------------------------
def technical_analysis(token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    technical = payload.get("technical", {})
    if not technical:
        return {"APS": 0.0, "RSS": 0.0, "RRR": 0.0, "indicators": technical}

    rsi = technical.get("rsi", 50)
    macd_hist = technical.get("macd_hist", 0)
    price_trend = technical.get("price_trend", 0)
    prices = technical.get("prices", [])

    aps = 1 - abs(rsi - 50) / 50
    rss = normalize_score(macd_hist * 5 + price_trend)
    rrr = calculate_rrr(prices)

    return {"APS": float(max(0, min(1, aps))), "RSS": rss, "RRR": rrr, "indicators": technical}


def calculate_rrr(prices: List[float]) -> float:
    if len(prices) < 20:
        return 0.0
    recent = prices[-20:]
    current = recent[-1]
    high = max(recent)
    low = min(recent)
    risk = current - low
    reward = high - current
    if risk <= 0:
        return 0.0
    ratio = reward / risk if risk else 0
    return float(min(5.0, max(0.0, ratio)))


# --- Contract & Security -------------------------------------------------
def contract_security(token: str, payload: Dict[str, Any], contract_addr: str) -> Dict[str, Any]:
    onchain = payload.get("onchain", {})
    market_cap = onchain.get("market_cap") or 0
    volume = onchain.get("total_volume") or 0
    community = onchain.get("community_score") or 0
    commits = onchain.get("commit_count_4_weeks") or 0

    liquidity_ratio = volume / market_cap if market_cap else 0
    stability = normalize_score(1 - abs((payload.get("technical", {}).get("price_trend", 0))) * 10)
    err = max(0.01, 1 - (liquidity_ratio * 0.5 + commits * 0.02 + community * 0.01))
    ocw = (onchain.get("reddit_subscribers", 0) or 0) > 1000 or (onchain.get("twitter_followers", 0) or 0) > 10000
    aci = normalize_score((commits / 10) + (community / 100))

    return {"ERR": float(max(0.01, min(1.0, err))), "OCW": bool(ocw), "ACI": float(aci), "contract_addr": contract_addr, "stability": stability}


# --- Fusion & Visualization ---------------------------------------------
def fuse_signals(token: str, analysis: Dict[str, Any], sentiment: Dict[str, Any], contract: Dict[str, Any]) -> float:
    aps = analysis.get("APS", 0)
    nvi = sentiment.get("NVI", 0)
    err_inv = 1.0 / (contract.get("ERR", 1) + 1e-6)
    rrr = analysis.get("RRR", 0)
    score = (0.4 * aps) + (0.3 * nvi) + (0.2 * normalize_score(math.tanh(err_inv / 10))) + (0.1 * normalize_score(rrr / 5))
    return float(max(0.0, min(1.0, score)))


def generate_report(rows: List[Tuple[str, float, Dict[str, Any], Dict[str, Any], Dict[str, Any], List[Tuple[str, float]], Dict[str, Any]]]) -> None:
    now = get_utc_now()
    markdown = ["# VoidBloom Daily Intelligence Dashboard", "", f"_Generated: {now}_", ""]
    markdown.append("| Token | Final Score | APS | NVI | MMS | ERR | RRR | Myth Vectors | Topics | Similar Narratives |")
    markdown.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    html_lines = [
        "<html><head><meta charset='utf-8'><title>VoidBloom Dashboard</title>",
        "<style>body{font-family:Inter,Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:2rem;}table{border-collapse:collapse;width:100%;margin-bottom:2rem;}th,td{border:1px solid #30363d;padding:0.75rem;text-align:left;}th{background:#161b22;}tr:nth-child(even){background:#11151c;}code{background:#161b22;padding:0.2rem 0.4rem;border-radius:4px;}small{color:#8b949e;}</style>",
        "</head><body>",
        f"<h1>VoidBloom Daily Intelligence Dashboard</h1><p><small>Generated: {now}</small></p>",
        "<table><thead><tr><th>Token</th><th>Score</th><th>Tech</th><th>Sentiment</th><th>Risk</th><th>Myths</th><th>Topics</th><th>Similar</th><th>Trend</th><th>Lore Capsule</th></tr></thead><tbody>",
    ]

    for token, score, analysis, sentiment, contract, similars, payload in rows:
        topics = sentiment.get("topics", [])
        myth = ", ".join(sentiment.get("myth_vectors", []))
        spark = render_sparkline(analysis.get("indicators", {}).get("prices", [])[-30:])
        lore = craft_lore_capsule(token, sentiment, analysis, contract, payload)
        markdown.append(
            "| {token} | {score:.2f} | {aps:.2f} | {nvi:.2f} | {mms:.2f} | {err:.2f} | {rrr:.2f} | {myth} | {topics} | {similar} |".format(
def generate_report(rows: List[Tuple[str, float, Dict[str, Any], Dict[str, Any], Dict[str, Any]]]) -> None:
    lines = ["# VoidBloom Daily Intelligence Dashboard", "", f"_Generated: {get_utc_now()}_", ""]
    lines.append("| Token | Final Score | APS | NVI | MMS | ERR | RRR | Myth Vectors |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for token, score, analysis, sentiment, contract in rows:
        lines.append(
            "| {token} | {score:.2f} | {aps:.2f} | {nvi:.2f} | {mms:.2f} | {err:.2f} | {rrr:.2f} | {myth} |".format(
                token=token,
                score=score,
                aps=analysis.get("APS", 0),
                nvi=sentiment.get("NVI", 0),
                mms=sentiment.get("MMS", 0),
                err=contract.get("ERR", 0),
                rrr=analysis.get("RRR", 0),
                myth=myth,
                topics=", ".join(topics[:3]),
                similar=", ".join(f"{peer} ({sim:.2f})" for peer, sim in similars),
            )
        )

        html_lines.append(
            "<tr><td><strong>{token}</strong></td><td>{score:.2f}</td><td>APS {aps:.2f}<br>RSS {rss:.2f}<br>RRR {rrr:.2f}</td><td>NVI {nvi:.2f}<br>MMS {mms:.2f}<br>Belief {belief:.2f}</td><td>ERR {err:.2f}<br>ACI {aci:.2f}<br>Stability {stability:.2f}</td><td>{myth}</td><td>{topics}</td><td>{similar}</td><td><code>{spark}</code></td><td>{lore}</td></tr>".format(
                token=escape(token),
                score=score,
                aps=analysis.get("APS", 0),
                rss=analysis.get("RSS", 0),
                rrr=analysis.get("RRR", 0),
                nvi=sentiment.get("NVI", 0),
                mms=sentiment.get("MMS", 0),
                belief=sentiment.get("belief_intensity", 0),
                err=contract.get("ERR", 0),
                aci=contract.get("ACI", 0),
                stability=contract.get("stability", 0),
                myth=escape(myth),
                topics=escape(", ".join(topics[:5])),
                similar=escape(", ".join(f"{peer} ({sim:.2f})" for peer, sim in similars)),
                spark=escape(spark or ""),
                lore=escape(lore),
            )
        )

    html_lines.append("</tbody></table>")
    html_lines.append("</body></html>")

    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "dashboard.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    (DATA_DIR / "dashboard.html").write_text("\n".join(html_lines), encoding="utf-8")
                myth=", ".join(sentiment.get("myth_vectors", [])),
            )
        )

    DATA_DIR.mkdir(exist_ok=True)
    dashboard_path = DATA_DIR / "dashboard.md"
    dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- Main Orchestration --------------------------------------------------
def main(tokens: List[str]) -> None:
    rows: List[Tuple[str, float, Dict[str, Any], Dict[str, Any], Dict[str, Any], List[Tuple[str, float]], Dict[str, Any]]] = []
    rows: List[Tuple[str, float, Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
    for token in tokens:
        raw = ingest_sources(token)
        store_raw_data(token, raw)
        embedding = embed_and_store(token, raw)
        sentiment = synthesize_sentiment(token, raw)
        analysis = technical_analysis(token, raw)
        contract = contract_security(token, raw, contract_addr="0x...")
        score = fuse_signals(token, analysis, sentiment, contract)
        similars = fetch_similar_tokens(token, embedding)
        rows.append((token, score, analysis, sentiment, contract, similars, raw))
        similar_text = ", ".join(f"{peer}:{sim:.2f}" for peer, sim in similars) or "none"
        print(f"{token}: Final Score = {score:.2f} | Similar narratives: {similar_text}")

    generate_report(rows)

        rows.append((token, score, analysis, sentiment, contract))
        print(f"{token}: Final Score = {score:.2f}")

    generate_report(rows)


if __name__ == "__main__":
    watchlist = os.getenv("VOIDBLOOM_TOKENS", "ETH,KAS,MANTA").split(",")
    main(tokens=[token.strip().upper() for token in watchlist if token.strip()])
