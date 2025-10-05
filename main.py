"""VoidBloom Data Oracle v1 – Phase 1–2 Pipeline implementation."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import sqlite3
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import nltk
import numpy as np
import pandas as pd
import requests
from nltk.sentiment import SentimentIntensityAnalyzer

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
    conn.commit()
    return conn


def store_raw_data(token: str, payload: Dict[str, Any], db_path: Path = DB_PATH) -> None:
    conn = ensure_database(db_path)
    conn.execute("INSERT INTO token_data VALUES (?, ?, ?)", (token, json.dumps(payload), payload["timestamp"]))
    conn.commit()
    conn.close()


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
                myth=", ".join(sentiment.get("myth_vectors", [])),
            )
        )

    DATA_DIR.mkdir(exist_ok=True)
    dashboard_path = DATA_DIR / "dashboard.md"
    dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- Main Orchestration --------------------------------------------------
def main(tokens: List[str]) -> None:
    rows: List[Tuple[str, float, Dict[str, Any], Dict[str, Any], Dict[str, Any]]] = []
    for token in tokens:
        raw = ingest_sources(token)
        store_raw_data(token, raw)
        embed_and_store(token, raw)
        sentiment = synthesize_sentiment(token, raw)
        analysis = technical_analysis(token, raw)
        contract = contract_security(token, raw, contract_addr="0x...")
        score = fuse_signals(token, analysis, sentiment, contract)
        rows.append((token, score, analysis, sentiment, contract))
        print(f"{token}: Final Score = {score:.2f}")

    generate_report(rows)


if __name__ == "__main__":
    watchlist = os.getenv("VOIDBLOOM_TOKENS", "ETH,KAS,MANTA").split(",")
    main(tokens=[token.strip().upper() for token in watchlist if token.strip()])
