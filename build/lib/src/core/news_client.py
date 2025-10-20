import os
import logging
import requests
import feedparser
from typing import List, Dict, Any
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)

class NewsClient:
    """Client for fetching cryptocurrency news from various sources."""
    def __init__(self):
        self.cryptopanic_api_key = os.getenv("CRYPTOPANIC_API_KEY")
        self.coindesk_feed_url = os.getenv(
            "COINDESK_FEED_URL",
            "https://www.coindesk.com/arc/outboundfeeds/rss/?output=xml"
        )
        self.cache = {}
        self.cache_expiry = {}
        self.cache_duration = timedelta(minutes=15)

    def get_news_for_token(self, token_symbol: str, days: int = 3) -> List[Dict[str, Any]]:
        cache_key = f"{token_symbol}_{days}"
        if cache_key in self.cache and datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
            return self.cache[cache_key]
        news = []
        # Try CryptoPanic API first
        if self.cryptopanic_api_key:
            try:
                cryptopanic_news = self._fetch_from_cryptopanic(token_symbol, days)
                news.extend(cryptopanic_news)
            except Exception as e:
                logger.warning(f"Failed to fetch news from CryptoPanic: {e}")
        # Try CoinDesk RSS as backup
        if not news:
            try:
                coindesk_news = self._fetch_from_coindesk(token_symbol, days)
                news.extend(coindesk_news)
            except Exception as e:
                logger.warning(f"Failed to fetch news from CoinDesk: {e}")
        if not news:
            logger.warning(f"No news found for {token_symbol}, APIs may be down or rate limited")
            return []
        self.cache[cache_key] = news
        self.cache_expiry[cache_key] = datetime.now() + self.cache_duration
        return news

    def _fetch_from_cryptopanic(self, token_symbol: str, days: int) -> List[Dict[str, Any]]:
        url = f"https://cryptopanic.com/api/v1/posts/?auth_token={self.cryptopanic_api_key}&currencies={token_symbol}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            logger.warning(f"CryptoPanic API error: {response.status_code}")
            return []
        data = response.json()
        news = []
        for result in data.get("results", []):
            news.append({
                "title": result.get("title", ""),
                "source": result.get("source", {}).get("title", "CryptoPanic"),
                "url": result.get("url", ""),
                "published_at": result.get("published_at", ""),
                "content": result.get("title", ""),
                "sentiment": result.get("votes", {}).get("positive", 0) - result.get("votes", {}).get("negative", 0)
            })
        return news

    def _fetch_from_coindesk(self, token_symbol: str, days: int) -> List[Dict[str, Any]]:
        feed = feedparser.parse(self.coindesk_feed_url)

        if feed.bozo:
            logger.warning(f"CoinDesk feed parsing issue: {feed.bozo_exception}")

        token_symbol_lower = token_symbol.lower()
        aliases = self._get_token_aliases(token_symbol_lower)
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        news = []
        for entry in feed.entries:
            published_at = ""
            entry_time = None

            if getattr(entry, "published_parsed", None):
                try:
                    entry_time = datetime(*entry.published_parsed[:6])
                    published_at = entry_time.isoformat()
                except Exception:
                    entry_time = None
            elif entry.get("updated"):
                try:
                    entry_time = datetime.fromisoformat(entry["updated"])
                    published_at = entry_time.isoformat()
                except Exception:
                    entry_time = None

            if entry_time and entry_time < cutoff_date:
                continue

            content = " ".join([
                entry.get("title", ""),
                entry.get("summary", ""),
                " ".join(tag.get("term", "") for tag in entry.get("tags", []))
                if isinstance(entry.get("tags"), list) else ""
            ]).lower()

            if not any(alias in content for alias in aliases):
                continue

            article_id = hashlib.md5(f"{entry.get('link', '')}-{published_at}".encode()).hexdigest()

            news.append({
                "title": entry.get("title", ""),
                "source": "CoinDesk",
                "url": entry.get("link", ""),
                "published_at": published_at,
                "content": entry.get("summary", entry.get("title", "")),
                "sentiment": None,
                "id": article_id
            })

        return news

    def _get_token_aliases(self, token_symbol_lower: str) -> List[str]:
        alias_map = {
            "btc": ["bitcoin", "btc"],
            "eth": ["ethereum", "eth"],
            "sol": ["solana", "sol"],
            "link": ["chainlink", "link"],
            "avax": ["avalanche", "avax"],
            "matic": ["polygon", "matic"],
            "dot": ["polkadot", "dot"],
            "shib": ["shiba inu", "shib"],
            "aave": ["aave"],
            "uni": ["uniswap", "uni"],
            "ltc": ["litecoin", "ltc"],
            "xrp": ["ripple", "xrp"],
            "ada": ["cardano", "ada"],
            "pepe": ["pepe"],
            "arb": ["arbitrum", "arb"],
            "op": ["optimism", "op"],
            "apt": ["aptos", "apt"],
            "sei": ["sei"],
            "inj": ["injective", "inj"]
        }

        aliases = alias_map.get(token_symbol_lower, [token_symbol_lower])
        return list({alias for alias in aliases})
