import os
import logging
import requests
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
import feedparser

logger = logging.getLogger(__name__)

class NewsClient:
    """Enhanced client for fetching cryptocurrency news from multiple sources."""
    def __init__(self, cache_path: Optional[str] = None):
        self.cryptopanic_api_key = os.getenv("CRYPTOPANIC_API_KEY")
        self.coindesk_feed_url = os.getenv(
            "COINDESK_FEED_URL",
            "https://www.coindesk.com/arc/outboundfeeds/rss/?output=xml"
        )
        self.cache = {}
        self.cache_expiry = {}
        # Default cache duration is 15 minutes
        self.cache_duration = timedelta(minutes=15)
        # Path for persistent cache
        self.cache_path = cache_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                                   "../../artifacts/news_cache.json")
        self._load_cache()
        
    def _load_cache(self) -> None:
        """Load the cache from disk if available"""
        if not os.path.exists(self.cache_path):
            return
            
        try:
            with open(self.cache_path, 'r') as f:
                data = json.load(f)
                self.cache = data.get('cache', {})
                # Convert string dates back to datetime
                self.cache_expiry = {
                    k: datetime.fromisoformat(v) 
                    for k, v in data.get('expiry', {}).items()
                }
        except Exception as e:
            logger.error(f"Failed to load news cache: {e}")
            self.cache = {}
            self.cache_expiry = {}
    
    def _save_cache(self) -> None:
        """Save the cache to disk"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            
            # Convert datetime objects to ISO strings for serialization
            expiry_dict = {
                k: v.isoformat() 
                for k, v in self.cache_expiry.items()
            }
            
            with open(self.cache_path, 'w') as f:
                json.dump({
                    'cache': self.cache,
                    'expiry': expiry_dict
                }, f)
        except Exception as e:
            logger.error(f"Failed to save news cache: {e}")

    def get_news_for_token(self, token_symbol: str, days: int = 3, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get news for a specific token, with options for fresh data.
        
        Args:
            token_symbol: Symbol of the token (e.g., BTC, ETH)
            days: How many days of news to fetch
            force_refresh: Whether to bypass cache and fetch fresh data
            
        Returns:
            List of news articles
        """
        cache_key = f"{token_symbol}_{days}"
        
        # Return cached data if available and not expired
        if not force_refresh and cache_key in self.cache and datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
            return self.cache[cache_key]
            
        news = []
        # Try multiple sources in order of preference
        
        # 1. Try CryptoPanic API first (usually most relevant)
        if self.cryptopanic_api_key:
            try:
                cryptopanic_news = self._fetch_from_cryptopanic(token_symbol, days)
                news.extend(cryptopanic_news)
                logger.info(f"Fetched {len(cryptopanic_news)} articles from CryptoPanic for {token_symbol}")
            except Exception as e:
                logger.warning(f"Failed to fetch news from CryptoPanic: {e}")
        
        # 2. Try CoinDesk RSS feed (broad industry coverage)
        try:
            coindesk_news = self._fetch_from_coindesk(token_symbol, days)

            # Deduplicate news by URL
            existing_urls = {article.get("url") for article in news}
            unique_articles = [
                article for article in coindesk_news
                if article.get("url") not in existing_urls
            ]

            news.extend(unique_articles)
            logger.info(
                f"Fetched {len(unique_articles)} additional articles from CoinDesk for {token_symbol}"
            )
        except Exception as e:
            logger.warning(f"Failed to fetch news from CoinDesk: {e}")
        
        # 3. Add more news sources here as needed
        
        if not news:
            logger.warning(f"No news found for {token_symbol}, APIs may be down or rate limited")
            return []
            
        # Sort news by publication date (newest first)
        try:
            news = sorted(
                news,
                key=lambda x: datetime.fromisoformat(x.get("published_at")) if isinstance(x.get("published_at"), str) else datetime.now(),
                reverse=True
            )
        except Exception as e:
            logger.warning(f"Failed to sort news by date: {e}")
        
        # Update cache
        self.cache[cache_key] = news
        self.cache_expiry[cache_key] = datetime.now() + self.cache_duration
        self._save_cache()
        
        return news

    def _fetch_from_cryptopanic(self, token_symbol: str, days: int) -> List[Dict[str, Any]]:
        """Fetch news from CryptoPanic API"""
        # Create an API endpoint URL with filters
        url = f"https://cryptopanic.com/api/v1/posts/"
        params = {
            "auth_token": self.cryptopanic_api_key,
            "currencies": token_symbol,
            "kind": "news",  # Only news, not signals/posts
            "filter": "important",  # Focus on important news
            "public": True
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            logger.warning(f"CryptoPanic API error: {response.status_code}")
            return []
            
        data = response.json()
        news = []
        
        for result in data.get("results", []):
            # Generate unique ID for the article
            article_id = hashlib.md5(f"{result.get('url', '')}-{result.get('published_at', '')}".encode()).hexdigest()
            
            # Calculate sentiment from votes if available
            raw_sentiment = None
            votes = result.get("votes", {})
            if votes:
                positive = votes.get("positive", 0)
                negative = votes.get("negative", 0)
                total = positive + negative
                if total > 0:
                    raw_sentiment = (positive - negative) / total
            
            # Parse the publication date
            published_at = result.get("published_at", "")
            if published_at:
                try:
                    # Convert to ISO format for consistency
                    dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    published_at = dt.isoformat()
                except Exception:
                    pass
            
            news.append({
                "id": article_id,
                "title": result.get("title", ""),
                "source": result.get("source", {}).get("title", "CryptoPanic"),
                "url": result.get("url", ""),
                "published_at": published_at,
                "content": result.get("title", ""),  # Often only the title is available
                "sentiment": raw_sentiment,
                "domain": result.get("domain", ""),
                "currencies": [c.get("code", "") for c in result.get("currencies", [])],
                "votes": {
                    "positive": votes.get("positive", 0),
                    "negative": votes.get("negative", 0)
                }
            })
            
        return news

    def _fetch_from_coindesk(self, token_symbol: str, days: int) -> List[Dict[str, Any]]:
        """Fetch news from CoinDesk RSS feed and filter by token relevance"""
        feed = feedparser.parse(self.coindesk_feed_url)

        if feed.bozo:
            logger.warning(f"CoinDesk feed parsing issue: {feed.bozo_exception}")

        token_symbol_lower = token_symbol.lower()
        token_aliases = self._get_token_aliases(token_symbol_lower)
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        news = []
        for entry in feed.entries:
            published_at = ""
            entry_time = None

            # Determine publication time
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

            # Check token relevance
            content = " ".join([
                entry.get("title", ""),
                entry.get("summary", ""),
                " ".join(tag.get("term", "") for tag in entry.get("tags", []))
                if isinstance(entry.get("tags"), list) else ""
            ]).lower()

            if not any(alias in content for alias in token_aliases):
                continue

            article_id = hashlib.md5(f"{entry.get('link', '')}-{published_at}".encode()).hexdigest()

            news.append({
                "id": article_id,
                "title": entry.get("title", ""),
                "source": "CoinDesk",
                "url": entry.get("link", ""),
                "published_at": published_at,
                "content": entry.get("summary", entry.get("title", "")),
                "sentiment": None,
                "domain": "coindesk.com",
                "currencies": [token_symbol.upper()],
                "votes": {
                    "positive": 0,
                    "negative": 0
                }
            })

        return news

    def _get_token_aliases(self, token_symbol_lower: str) -> List[str]:
        """Return common name aliases for a token symbol for better matching"""
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
    
    def get_news_stats(self, token_symbol: str, days_range: List[int] = [1, 3, 7]) -> Dict[str, Any]:
        """
        Get news statistics for a token over different time ranges.
        
        Args:
            token_symbol: Symbol of the token
            days_range: List of day ranges to check
            
        Returns:
            Dictionary with news stats for each time range
        """
        stats = {}
        
        for days in days_range:
            news = self.get_news_for_token(token_symbol, days)
            
            # Count news sources
            sources = {}
            for article in news:
                source = article.get("source", "Unknown")
                sources[source] = sources.get(source, 0) + 1
            
            # Calculate volume trend (articles per day)
            volume_per_day = len(news) / max(1, days)
            
            stats[f"{days}d"] = {
                "count": len(news),
                "sources_count": len(sources),
                "top_sources": dict(sorted(sources.items(), key=lambda x: x[1], reverse=True)[:3]),
                "volume_per_day": volume_per_day
            }
            
        return stats
    
    def clear_cache(self, token_symbol: Optional[str] = None) -> None:
        """
        Clear cache for a specific token or all tokens.
        
        Args:
            token_symbol: Symbol to clear cache for, or None for all
        """
        if token_symbol:
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{token_symbol}_")]
            for k in keys_to_remove:
                if k in self.cache:
                    del self.cache[k]
                if k in self.cache_expiry:
                    del self.cache_expiry[k]
        else:
            self.cache = {}
            self.cache_expiry = {}
            
        self._save_cache()
        logger.info(f"Cleared news cache for {'all tokens' if token_symbol is None else token_symbol}")