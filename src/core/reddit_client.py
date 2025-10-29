"""Reddit API client for crypto sentiment signals."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence

import httpx

from src.core.clients import BaseClient
from src.core.http_manager import CachePolicy
from src.core.rate_limit import RateLimit


class RedditClient(BaseClient):
    """Client for Reddit API (OAuth2).

    Provides access to:
    - Subreddit posts (hot, new, top)
    - Post comments
    - User posts
    - Search across subreddits

    Can work in two modes:
    1. Public read-only (no authentication) - limited rate
    2. OAuth2 authenticated (recommended) - higher rate limits

    For authenticated access, register an app at:
    https://www.reddit.com/prefs/apps
    """

    def __init__(
        self,
        *,
        base_url: str = "https://oauth.reddit.com",
        public_base_url: str = "https://www.reddit.com",
        timeout: float = 15.0,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
        client: Optional[httpx.Client] = None,
        rate_limits: Mapping[str, RateLimit] | None = None,
    ) -> None:
        """Initialize Reddit API client.

        Args:
            base_url: OAuth API base URL (requires authentication)
            public_base_url: Public read-only API base URL (no auth required)
            timeout: Request timeout in seconds
            client_id: Reddit app client ID (optional for public access)
            client_secret: Reddit app client secret (optional for public access)
            user_agent: Custom user agent string
            client: Optional httpx client instance
            rate_limits: Optional custom rate limits
        """
        self._client_id = client_id or os.getenv("REDDIT_CLIENT_ID", "")
        self._client_secret = client_secret or os.getenv("REDDIT_CLIENT_SECRET", "")
        self._user_agent = user_agent or "CrisisCore-AutoTrader/1.0 (by /u/autotrader_bot)"
        self._access_token: str | None = None
        self._use_oauth = bool(self._client_id and self._client_secret)
        self._base_url = base_url if self._use_oauth else public_base_url

        headers = {
            "User-Agent": self._user_agent,
        }

        if self._use_oauth:
            # Get OAuth token on init
            self._access_token = self._get_access_token()
            headers["Authorization"] = f"Bearer {self._access_token}"

        session = client or httpx.Client(base_url=self._base_url, timeout=timeout, headers=headers)

        # Reddit rate limits: 60 requests per minute (1 per second)
        resolved_limits = rate_limits or {
            "reddit.com": RateLimit(60, 60.0),
            "oauth.reddit.com": RateLimit(60, 60.0),
        }

        super().__init__(
            session,
            rate_limits=resolved_limits,
        )

    def _get_access_token(self) -> str:
        """Obtain OAuth2 access token for authenticated requests."""
        if not self._client_id or not self._client_secret:
            raise ValueError("client_id and client_secret required for OAuth access")

        auth_client = httpx.Client()
        response = auth_client.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=(self._client_id, self._client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": self._user_agent},
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def get_subreddit_posts(
        self,
        subreddit: str,
        *,
        sort: str = "hot",
        time_filter: str = "day",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/)
            sort: Sort order (hot, new, top, rising, controversial)
            time_filter: Time filter for top/controversial (hour, day, week, month, year, all)
            limit: Number of posts to fetch (max 100)

        Returns:
            List of post dictionaries with title, selftext, score, num_comments, etc.
        """
        endpoint = f"/r/{subreddit}/{sort}.json"

        params: Dict[str, Any] = {
            "limit": min(limit, 100),
        }

        if sort in ("top", "controversial"):
            params["t"] = time_filter

        response = self.requester.request(
            "GET",
            endpoint,
            params=params,
            cache_policy=CachePolicy(ttl_seconds=60.0),  # Cache for 1 minute
        )

        data = response.json()
        if isinstance(data, dict) and "data" in data:
            children = data["data"].get("children", [])
            return [child["data"] for child in children if isinstance(child, dict)]
        return []

    def search_subreddit(
        self,
        subreddit: str,
        query: str,
        *,
        sort: str = "relevance",
        time_filter: str = "day",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search posts within a specific subreddit.

        Args:
            subreddit: Subreddit name (without r/)
            query: Search query
            sort: Sort order (relevance, hot, top, new, comments)
            time_filter: Time filter (hour, day, week, month, year, all)
            limit: Number of results to fetch (max 100)

        Returns:
            List of matching post dictionaries
        """
        endpoint = f"/r/{subreddit}/search.json"

        params = {
            "q": query,
            "restrict_sr": "true",  # Restrict search to this subreddit
            "sort": sort,
            "t": time_filter,
            "limit": min(limit, 100),
        }

        response = self.requester.request(
            "GET",
            endpoint,
            params=params,
            cache_policy=CachePolicy(ttl_seconds=60.0),
        )

        data = response.json()
        if isinstance(data, dict) and "data" in data:
            children = data["data"].get("children", [])
            return [child["data"] for child in children if isinstance(child, dict)]
        return []

    def get_post_comments(
        self,
        subreddit: str,
        post_id: str,
        *,
        sort: str = "best",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch comments for a specific post.

        Args:
            subreddit: Subreddit name (without r/)
            post_id: Reddit post ID (without t3_ prefix)
            sort: Sort order (best, top, new, controversial, old, qa)
            limit: Number of comments to fetch

        Returns:
            List of comment dictionaries with body, score, author, etc.
        """
        endpoint = f"/r/{subreddit}/comments/{post_id}.json"

        params = {
            "sort": sort,
            "limit": min(limit, 100),
        }

        response = self.requester.request(
            "GET",
            endpoint,
            params=params,
            cache_policy=CachePolicy(ttl_seconds=120.0),  # Cache for 2 minutes
        )

        data = response.json()
        # Reddit returns [post_data, comments_data]
        if isinstance(data, list) and len(data) > 1:
            comments_listing = data[1]
            if isinstance(comments_listing, dict) and "data" in comments_listing:
                children = comments_listing["data"].get("children", [])
                comments = []
                for child in children:
                    if isinstance(child, dict) and child.get("kind") == "t1":
                        comments.append(child["data"])
                return comments
        return []

    def fetch_crypto_sentiment(
        self,
        token_symbol: str | None = None,
        token_name: str | None = None,
        *,
        subreddits: Sequence[str] | None = None,
        hours_back: int = 24,
        min_score: int = 10,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch crypto-related posts optimized for sentiment analysis.

        Args:
            token_symbol: Token symbol (e.g., "BTC", "ETH")
            token_name: Token name (e.g., "Bitcoin", "Ethereum")
            subreddits: List of subreddits to search (defaults to crypto subs)
            hours_back: How many hours back to search
            min_score: Minimum post score (upvotes - downvotes)
            limit: Maximum posts to return per subreddit

        Returns:
            List of post dictionaries with sentiment-relevant fields
        """
        if not token_symbol and not token_name:
            raise ValueError("Must provide either token_symbol or token_name")

        if subreddits is None:
            subreddits = [
                "CryptoCurrency",
                "CryptoMarkets",
                "altcoin",
                "defi",
                "ethtrader",
                "Bitcoin",
            ]

        # Build search query
        query_terms = []
        if token_symbol:
            query_terms.append(token_symbol.upper())
        if token_name:
            query_terms.append(token_name)

        query = " OR ".join(query_terms)

        # Map hours to Reddit time filter
        if hours_back <= 24:
            time_filter = "day"
        elif hours_back <= 168:  # 7 days
            time_filter = "week"
        else:
            time_filter = "month"

        all_posts: List[Dict[str, Any]] = []

        for subreddit in subreddits:
            try:
                posts = self.search_subreddit(
                    subreddit=subreddit,
                    query=query,
                    sort="top",
                    time_filter=time_filter,
                    limit=limit,
                )
                # Filter by minimum score
                filtered = [p for p in posts if p.get("score", 0) >= min_score]
                all_posts.extend(filtered)
            except Exception:
                # Continue if one subreddit fails
                continue

        # Sort by score descending and deduplicate
        seen_ids = set()
        unique_posts = []
        for post in sorted(all_posts, key=lambda p: p.get("score", 0), reverse=True):
            post_id = post.get("id")
            if post_id and post_id not in seen_ids:
                seen_ids.add(post_id)
                unique_posts.append(post)

        return unique_posts[:limit]

    def normalize_to_social_post(self, reddit_post: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Reddit post to common social post format.

        Args:
            reddit_post: Raw Reddit API post response

        Returns:
            Normalized post dict compatible with SocialPost
        """
        created_utc = reddit_post.get("created_utc", 0)
        posted_at = datetime.utcfromtimestamp(created_utc) if created_utc else None

        # Combine title and selftext for full content
        title = reddit_post.get("title", "")
        selftext = reddit_post.get("selftext", "")
        content = f"{title}\n\n{selftext}".strip() if selftext else title

        return {
            "id": reddit_post.get("id", ""),
            "platform": "reddit",
            "author": reddit_post.get("author", "[deleted]"),
            "content": content,
            "url": f"https://reddit.com{reddit_post.get('permalink', '')}",
            "posted_at": posted_at.isoformat() if posted_at else None,
            "timestamp": created_utc,
            "metrics": {
                "upvotes": reddit_post.get("ups", 0),
                "score": reddit_post.get("score", 0),
                "comments": reddit_post.get("num_comments", 0),
                "upvote_ratio": reddit_post.get("upvote_ratio", 0.0),
            },
            "subreddit": reddit_post.get("subreddit", ""),
            "is_self": reddit_post.get("is_self", False),
        }


__all__ = ["RedditClient"]
