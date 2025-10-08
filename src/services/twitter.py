"""Twitter sentiment aggregation and signal extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence

from src.core.twitter_client import TwitterClientV2


@dataclass
class TweetSignal:
    """Individual tweet with extracted signals."""

    tweet_id: str
    created_at: datetime
    text: str
    author_username: str
    author_verified: bool
    author_followers: int

    # Engagement metrics
    likes: int
    retweets: int
    replies: int
    quotes: int

    # Derived signals
    engagement_score: float  # Weighted engagement
    velocity_score: float  # Engagement rate per hour
    influence_score: float  # Author influence weight

    # Sentiment (to be filled by sentiment analyzer)
    sentiment: Optional[str] = None  # "positive", "negative", "neutral"
    sentiment_score: Optional[float] = None  # -1 to 1

    # Metadata
    entities: Dict[str, Any] = field(default_factory=dict)
    referenced_tweets: List[str] = field(default_factory=list)


@dataclass
class TwitterSentimentSnapshot:
    """Aggregated Twitter sentiment for a token."""

    token_symbol: str
    timestamp: datetime
    time_window_hours: int

    # Volume metrics
    total_tweets: int
    unique_authors: int
    verified_tweets: int

    # Engagement metrics
    total_engagement: int  # Sum of likes + retweets + replies
    avg_engagement_per_tweet: float
    top_tweet_engagement: int

    # Sentiment distribution
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    avg_sentiment_score: float = 0.0  # -1 to 1

    # Influence metrics
    top_influencer_usernames: List[str] = field(default_factory=list)
    verified_author_pct: float = 0.0

    # Velocity (tweets per hour)
    tweet_velocity: float = 0.0

    # Top signals
    top_tweets: List[TweetSignal] = field(default_factory=list)

    # Metadata
    data_quality_score: float = 1.0
    query_used: str = ""


class TwitterAggregator:
    """Aggregates and processes Twitter signals for crypto tokens."""

    def __init__(
        self,
        twitter_client: Optional[TwitterClientV2] = None,
    ) -> None:
        """Initialize with Twitter API v2 client.

        Args:
            twitter_client: Optional Twitter client (will create if not provided)
        """
        self.twitter = twitter_client or TwitterClientV2()

    def aggregate_token_sentiment(
        self,
        token_symbol: str,
        *,
        hours_back: int = 24,
        max_tweets: int = 100,
        min_engagement: int = 5,
        include_token_name: Optional[str] = None,
    ) -> TwitterSentimentSnapshot:
        """Aggregate Twitter sentiment for a token.

        Args:
            token_symbol: Token symbol (e.g., "BTC", "ETH")
            hours_back: How many hours back to analyze
            max_tweets: Maximum tweets to fetch
            min_engagement: Minimum engagement threshold
            include_token_name: Optional full token name for query

        Returns:
            TwitterSentimentSnapshot with aggregated metrics
        """
        timestamp = datetime.utcnow()

        # Build query
        query = self.twitter.build_crypto_query(
            token_symbol=token_symbol,
            token_name=include_token_name,
            exclude_retweets=True,
            language="en",
        )

        if min_engagement > 0:
            query += f" (min_faves:{min_engagement} OR min_retweets:{min_engagement})"

        try:
            # Fetch tweets
            result = self.twitter.fetch_sentiment_signals(
                token_symbol=token_symbol,
                hours_back=hours_back,
                max_results=max_tweets,
                min_engagement=min_engagement,
            )

            tweets_data = result.get("data", [])
            includes = result.get("includes", {})

            if not tweets_data:
                return TwitterSentimentSnapshot(
                    token_symbol=token_symbol,
                    timestamp=timestamp,
                    time_window_hours=hours_back,
                    total_tweets=0,
                    unique_authors=0,
                    verified_tweets=0,
                    total_engagement=0,
                    avg_engagement_per_tweet=0.0,
                    top_tweet_engagement=0,
                    tweet_velocity=0.0,
                    data_quality_score=0.0,
                    query_used=query,
                )

            # Build user lookup
            users_map: Dict[str, Dict[str, Any]] = {}
            for user in includes.get("users", []):
                users_map[user["id"]] = user

            # Process tweets into signals
            signals: List[TweetSignal] = []
            unique_authors: set[str] = set()
            verified_count = 0
            total_engagement = 0

            for tweet in tweets_data:
                author_id = tweet.get("author_id", "")
                user_data = users_map.get(author_id, {})

                # Parse timestamp
                created_str = tweet.get("created_at", "")
                try:
                    created_at = datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    created_at = timestamp

                # Extract metrics
                metrics = tweet.get("public_metrics", {})
                likes = metrics.get("like_count", 0)
                retweets = metrics.get("retweet_count", 0)
                replies = metrics.get("reply_count", 0)
                quotes = metrics.get("quote_count", 0)

                engagement = likes + retweets + replies + quotes
                total_engagement += engagement

                # Author metrics
                username = user_data.get("username", "unknown")
                verified = user_data.get("verified", False)
                followers = user_data.get("public_metrics", {}).get("followers_count", 0)

                unique_authors.add(author_id)
                if verified:
                    verified_count += 1

                # Calculate derived scores
                hours_ago = (timestamp - created_at).total_seconds() / 3600
                velocity_score = engagement / max(hours_ago, 0.1)  # Engagement per hour

                # Influence score: log-scaled followers + verified bonus
                influence_score = (followers ** 0.5) * (2.0 if verified else 1.0)

                # Weighted engagement score
                engagement_score = (
                    likes * 1.0 +
                    retweets * 2.0 +  # Retweets are stronger signal
                    replies * 1.5 +
                    quotes * 2.5  # Quotes indicate strong reaction
                )

                signal = TweetSignal(
                    tweet_id=tweet["id"],
                    created_at=created_at,
                    text=tweet.get("text", ""),
                    author_username=username,
                    author_verified=verified,
                    author_followers=followers,
                    likes=likes,
                    retweets=retweets,
                    replies=replies,
                    quotes=quotes,
                    engagement_score=engagement_score,
                    velocity_score=velocity_score,
                    influence_score=influence_score,
                    entities=tweet.get("entities", {}),
                    referenced_tweets=[
                        ref["id"] for ref in tweet.get("referenced_tweets", [])
                    ],
                )

                signals.append(signal)

            # Sort by engagement score
            signals.sort(key=lambda s: s.engagement_score, reverse=True)

            # Calculate aggregate metrics
            avg_engagement = total_engagement / len(signals) if signals else 0.0
            top_engagement = signals[0].engagement_score if signals else 0
            tweet_velocity = len(signals) / hours_back
            verified_pct = (verified_count / len(signals) * 100) if signals else 0.0

            # Top influencers (by influence score)
            sorted_by_influence = sorted(signals, key=lambda s: s.influence_score, reverse=True)
            top_influencers = [s.author_username for s in sorted_by_influence[:5]]

            return TwitterSentimentSnapshot(
                token_symbol=token_symbol,
                timestamp=timestamp,
                time_window_hours=hours_back,
                total_tweets=len(signals),
                unique_authors=len(unique_authors),
                verified_tweets=verified_count,
                total_engagement=total_engagement,
                avg_engagement_per_tweet=avg_engagement,
                top_tweet_engagement=int(top_engagement),
                tweet_velocity=tweet_velocity,
                verified_author_pct=verified_pct,
                top_influencer_usernames=top_influencers,
                top_tweets=signals[:10],  # Top 10 by engagement
                data_quality_score=1.0 if len(signals) >= 10 else 0.5,
                query_used=query,
            )

        except Exception as e:
            print(f"Warning: Failed to aggregate Twitter sentiment: {e}")
            return TwitterSentimentSnapshot(
                token_symbol=token_symbol,
                timestamp=timestamp,
                time_window_hours=hours_back,
                total_tweets=0,
                unique_authors=0,
                verified_tweets=0,
                total_engagement=0,
                avg_engagement_per_tweet=0.0,
                top_tweet_engagement=0,
                tweet_velocity=0.0,
                data_quality_score=0.0,
                query_used=query,
            )

    def monitor_real_time_mentions(
        self,
        token_symbols: Sequence[str],
        *,
        check_interval_seconds: int = 60,
    ) -> List[TwitterSentimentSnapshot]:
        """Monitor multiple tokens for real-time sentiment changes.

        This method can be used in a loop or scheduled task to continuously
        monitor Twitter sentiment for a portfolio of tokens.

        Args:
            token_symbols: List of token symbols to monitor
            check_interval_seconds: How often to check (for rate limit planning)

        Returns:
            List of sentiment snapshots, one per token
        """
        snapshots: List[TwitterSentimentSnapshot] = []

        for symbol in token_symbols:
            snapshot = self.aggregate_token_sentiment(
                token_symbol=symbol,
                hours_back=1,  # Short window for real-time
                max_tweets=50,
                min_engagement=10,  # Higher threshold for real-time
            )
            snapshots.append(snapshot)

        return snapshots

    def detect_sentiment_spike(
        self,
        token_symbol: str,
        *,
        baseline_hours: int = 24,
        recent_hours: int = 1,
        spike_threshold: float = 3.0,
    ) -> Dict[str, Any]:
        """Detect if there's a sentiment spike (viral moment) for a token.

        Args:
            token_symbol: Token symbol to analyze
            baseline_hours: Historical baseline window
            recent_hours: Recent window to compare
            spike_threshold: Multiplier for spike detection (e.g., 3x baseline)

        Returns:
            Dict with spike detection results and metrics
        """
        # Get baseline sentiment
        baseline = self.aggregate_token_sentiment(
            token_symbol=token_symbol,
            hours_back=baseline_hours,
            max_tweets=100,
        )

        # Get recent sentiment
        recent = self.aggregate_token_sentiment(
            token_symbol=token_symbol,
            hours_back=recent_hours,
            max_tweets=100,
        )

        # Normalize velocities to comparable scale
        baseline_velocity = baseline.tweet_velocity
        recent_velocity = recent.tweet_velocity

        # Detect spike
        is_spike = False
        spike_multiplier = 0.0

        if baseline_velocity > 0:
            spike_multiplier = recent_velocity / baseline_velocity
            is_spike = spike_multiplier >= spike_threshold

        return {
            "token_symbol": token_symbol,
            "is_spike": is_spike,
            "spike_multiplier": spike_multiplier,
            "baseline_velocity": baseline_velocity,
            "recent_velocity": recent_velocity,
            "recent_tweets": recent.total_tweets,
            "recent_engagement": recent.total_engagement,
            "top_recent_tweet": recent.top_tweets[0] if recent.top_tweets else None,
            "timestamp": datetime.utcnow(),
        }
