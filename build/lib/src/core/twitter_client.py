"""Twitter API v2 client for real-time social sentiment signals."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence

import httpx

from src.core.clients import BaseClient
from src.core.http_manager import CachePolicy
from src.core.rate_limit import RateLimit


class TwitterClientV2(BaseClient):
    """Client for Twitter API v2.

    Provides access to:
    - Recent tweet search (last 7 days)
    - Filtered stream (real-time)
    - Tweet lookup with engagement metrics
    - User timeline

    Requires Twitter API v2 Bearer Token from https://developer.twitter.com/
    """

    def __init__(
        self,
        *,
        base_url: str = "https://api.twitter.com",
        timeout: float = 15.0,
        bearer_token: str | None = None,
        client: Optional[httpx.Client] = None,
        rate_limits: Mapping[str, RateLimit] | None = None,
    ) -> None:
        """Initialize Twitter API v2 client.

        Args:
            base_url: API base URL
            timeout: Request timeout in seconds
            bearer_token: Twitter API v2 Bearer Token (required)
            client: Optional httpx client instance
            rate_limits: Optional custom rate limits

        Raises:
            ValueError: If bearer_token is not provided
        """
        self._bearer_token = bearer_token or os.getenv("TWITTER_BEARER_TOKEN", "")

        if not self._bearer_token:
            raise ValueError(
                "Twitter API v2 requires a bearer token. "
                "Set TWITTER_BEARER_TOKEN environment variable or pass bearer_token parameter. "
                "Get your token at https://developer.twitter.com/en/portal/dashboard"
            )

        headers = {
            "Authorization": f"Bearer {self._bearer_token}",
            "User-Agent": "VoidBloom-AutoTrader/1.0",
        }

        session = client or httpx.Client(base_url=base_url, timeout=timeout, headers=headers)

        # Twitter API v2 rate limits (per 15-minute window)
        resolved_limits = rate_limits or {
            "api.twitter.com": RateLimit(450, 900.0),  # 450 requests per 15 min (general)
        }

        super().__init__(
            session,
            rate_limits=resolved_limits,
        )

    def search_recent_tweets(
        self,
        query: str,
        *,
        max_results: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tweet_fields: Sequence[str] | None = None,
        expansions: Sequence[str] | None = None,
        user_fields: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        """Search recent tweets (last 7 days) matching a query.

        Args:
            query: Search query using Twitter search operators
                   Examples:
                   - "$BTC OR #Bitcoin" (hashtags and cashtags)
                   - "ethereum lang:en -is:retweet" (with filters)
                   - "(crypto OR defi) has:links" (boolean operators)
            max_results: Number of tweets to return (10-100 per request, default 10)
            start_time: Oldest UTC timestamp to search (within last 7 days)
            end_time: Newest UTC timestamp to search
            tweet_fields: Additional tweet fields to include
                         (author_id, created_at, public_metrics, entities, etc.)
            expansions: Related data to expand (author_id, referenced_tweets.id, etc.)
            user_fields: User object fields when expanding author_id

        Returns:
            Dict with 'data' (tweets), 'includes' (expanded objects), and 'meta' (pagination)
        """
        # Default fields optimized for sentiment analysis
        if tweet_fields is None:
            tweet_fields = [
                "created_at",
                "public_metrics",
                "author_id",
                "conversation_id",
                "entities",
                "referenced_tweets",
                "lang",
            ]

        if expansions is None:
            expansions = ["author_id", "referenced_tweets.id"]

        if user_fields is None:
            user_fields = ["username", "verified", "public_metrics", "description"]

        params: Dict[str, Any] = {
            "query": query,
            "max_results": min(max_results, 100),  # API max is 100
            "tweet.fields": ",".join(tweet_fields),
            "expansions": ",".join(expansions),
            "user.fields": ",".join(user_fields),
        }

        if start_time:
            params["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        if end_time:
            params["end_time"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        response = self.requester.request(
            "GET",
            "/2/tweets/search/recent",
            params=params,
            cache_policy=CachePolicy(ttl_seconds=60.0),  # Cache for 1 minute
        )

        return response.json()

    def get_tweets_by_ids(
        self,
        tweet_ids: Sequence[str],
        *,
        tweet_fields: Sequence[str] | None = None,
        expansions: Sequence[str] | None = None,
        user_fields: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        """Fetch specific tweets by their IDs (up to 100 per request).

        Args:
            tweet_ids: List of tweet IDs to fetch
            tweet_fields: Additional tweet fields to include
            expansions: Related data to expand
            user_fields: User object fields when expanding author_id

        Returns:
            Dict with 'data' (tweets) and 'includes' (expanded objects)
        """
        if not tweet_ids:
            return {"data": [], "includes": {}}

        if tweet_fields is None:
            tweet_fields = [
                "created_at",
                "public_metrics",
                "author_id",
                "entities",
                "lang",
            ]

        if expansions is None:
            expansions = ["author_id"]

        if user_fields is None:
            user_fields = ["username", "verified", "public_metrics"]

        params = {
            "ids": ",".join(tweet_ids[:100]),  # Max 100 IDs
            "tweet.fields": ",".join(tweet_fields),
            "expansions": ",".join(expansions),
            "user.fields": ",".join(user_fields),
        }

        response = self.requester.request(
            "GET",
            "/2/tweets",
            params=params,
            cache_policy=CachePolicy(ttl_seconds=300.0),  # Cache for 5 minutes
        )

        return response.json()

    def get_user_tweets(
        self,
        user_id: str,
        *,
        max_results: int = 100,
        exclude: Sequence[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        tweet_fields: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        """Fetch tweets from a specific user's timeline.

        Args:
            user_id: Twitter user ID (not username)
            max_results: Number of tweets to return (5-100, default 10)
            exclude: Types to exclude (retweets, replies)
            start_time: Oldest UTC timestamp to include
            end_time: Newest UTC timestamp to include
            tweet_fields: Additional tweet fields to include

        Returns:
            Dict with 'data' (tweets) and 'meta' (pagination info)
        """
        if tweet_fields is None:
            tweet_fields = [
                "created_at",
                "public_metrics",
                "entities",
                "referenced_tweets",
                "lang",
            ]

        params: Dict[str, Any] = {
            "max_results": min(max_results, 100),
            "tweet.fields": ",".join(tweet_fields),
        }

        if exclude:
            params["exclude"] = ",".join(exclude)

        if start_time:
            params["start_time"] = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        if end_time:
            params["end_time"] = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        response = self.requester.request(
            "GET",
            f"/2/users/{user_id}/tweets",
            params=params,
            cache_policy=CachePolicy(ttl_seconds=60.0),
        )

        return response.json()

    def get_user_by_username(
        self,
        username: str,
        *,
        user_fields: Sequence[str] | None = None,
    ) -> Dict[str, Any]:
        """Look up a user by their username.

        Args:
            username: Twitter username (without @)
            user_fields: User fields to include

        Returns:
            Dict with 'data' (user object)
        """
        if user_fields is None:
            user_fields = [
                "id",
                "name",
                "username",
                "verified",
                "description",
                "public_metrics",
                "created_at",
            ]

        params = {
            "user.fields": ",".join(user_fields),
        }

        response = self.requester.request(
            "GET",
            f"/2/users/by/username/{username}",
            params=params,
            cache_policy=CachePolicy(ttl_seconds=300.0),
        )

        return response.json()

    def build_crypto_query(
        self,
        token_symbol: str | None = None,
        token_name: str | None = None,
        *,
        include_cashtags: bool = True,
        include_hashtags: bool = True,
        exclude_retweets: bool = True,
        min_replies: int | None = None,
        min_likes: int | None = None,
        verified_only: bool = False,
        language: str = "en",
    ) -> str:
        """Build an optimized search query for crypto token sentiment.

        Args:
            token_symbol: Token symbol (e.g., "BTC", "ETH")
            token_name: Token name (e.g., "Bitcoin", "Ethereum")
            include_cashtags: Include $SYMBOL searches
            include_hashtags: Include #SYMBOL searches
            exclude_retweets: Filter out retweets
            min_replies: Minimum reply count filter
            min_likes: Minimum like count filter
            verified_only: Only search tweets from verified accounts
            language: Language filter (ISO 639-1 code)

        Returns:
            Formatted Twitter search query string
        """
        if not token_symbol and not token_name:
            raise ValueError("Must provide either token_symbol or token_name")

        query_parts: List[str] = []

        # Build token references
        token_refs: List[str] = []

        if token_symbol:
            if include_cashtags:
                token_refs.append(f"${token_symbol.upper()}")
            if include_hashtags:
                token_refs.append(f"#{token_symbol.upper()}")

        if token_name:
            token_refs.append(token_name)

        if token_refs:
            query_parts.append(f"({' OR '.join(token_refs)})")

        # Add filters
        if exclude_retweets:
            query_parts.append("-is:retweet")

        if min_replies:
            query_parts.append(f"min_replies:{min_replies}")

        if min_likes:
            query_parts.append(f"min_faves:{min_likes}")

        if verified_only:
            query_parts.append("is:verified")

        if language:
            query_parts.append(f"lang:{language}")

        return " ".join(query_parts)

    def fetch_sentiment_signals(
        self,
        token_symbol: str,
        *,
        hours_back: int = 24,
        max_results: int = 100,
        min_engagement: int = 5,
    ) -> Dict[str, Any]:
        """Convenience method to fetch recent tweets optimized for sentiment analysis.

        Args:
            token_symbol: Token symbol (e.g., "BTC", "ETH")
            hours_back: How many hours back to search (max 168 for 7 days)
            max_results: Maximum tweets to return
            min_engagement: Minimum combined likes + retweets

        Returns:
            Dict with tweets and metadata optimized for sentiment analysis
        """
        # Build optimized query
        query = self.build_crypto_query(
            token_symbol=token_symbol,
            exclude_retweets=True,
            language="en",
        )

        # Add engagement filter
        if min_engagement > 0:
            query += f" (min_faves:{min_engagement} OR min_retweets:{min_engagement})"

        # Calculate time window
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=min(hours_back, 168))  # API max 7 days

        return self.search_recent_tweets(
            query=query,
            max_results=max_results,
            start_time=start_time,
            end_time=end_time,
        )
