"""Example usage of Twitter API v2 client and sentiment aggregation."""

import os
from datetime import datetime, timedelta

# Set up Twitter API credentials
# Get your Bearer Token from: https://developer.twitter.com/en/portal/dashboard
# os.environ["TWITTER_BEARER_TOKEN"] = "your_bearer_token_here"

from src.core.twitter_client import TwitterClientV2
from src.services.twitter import TwitterAggregator


def example_basic_tweet_search():
    """Demonstrate basic tweet search for crypto tokens."""
    print("=" * 80)
    print("BASIC TWEET SEARCH EXAMPLE")
    print("=" * 80)

    try:
        client = TwitterClientV2()

        # Search for Bitcoin tweets in the last 24 hours
        query = client.build_crypto_query(
            token_symbol="BTC",
            token_name="Bitcoin",
            exclude_retweets=True,
            min_likes=10,
            language="en",
        )

        print(f"\nQuery: {query}")

        results = client.search_recent_tweets(
            query=query,
            max_results=10,
        )

        tweets = results.get("data", [])
        print(f"\nFound {len(tweets)} tweets")

        for i, tweet in enumerate(tweets[:5], 1):
            metrics = tweet.get("public_metrics", {})
            print(f"\n{i}. Tweet ID: {tweet['id']}")
            print(f"   Text: {tweet.get('text', '')[:100]}...")
            print(f"   Likes: {metrics.get('like_count', 0)}, Retweets: {metrics.get('retweet_count', 0)}")

    except ValueError as e:
        print(f"\n⚠️  {e}")
        print("\nTo use Twitter API v2, you need to:")
        print("1. Create a developer account at https://developer.twitter.com/")
        print("2. Create a project and app")
        print("3. Generate a Bearer Token")
        print("4. Set TWITTER_BEARER_TOKEN environment variable")


def example_sentiment_aggregation():
    """Demonstrate sentiment aggregation for a token."""
    print("\n" + "=" * 80)
    print("SENTIMENT AGGREGATION EXAMPLE")
    print("=" * 80)

    try:
        aggregator = TwitterAggregator()

        # Aggregate sentiment for Ethereum
        snapshot = aggregator.aggregate_token_sentiment(
            token_symbol="ETH",
            include_token_name="Ethereum",
            hours_back=24,
            max_tweets=50,
            min_engagement=5,
        )

        print(f"\nToken: {snapshot.token_symbol}")
        print(f"Time Window: {snapshot.time_window_hours} hours")
        print(f"Timestamp: {snapshot.timestamp}")
        print(f"Data Quality: {snapshot.data_quality_score:.2f}")

        print(f"\n--- Volume Metrics ---")
        print(f"Total Tweets: {snapshot.total_tweets}")
        print(f"Unique Authors: {snapshot.unique_authors}")
        print(f"Verified Tweets: {snapshot.verified_tweets} ({snapshot.verified_author_pct:.1f}%)")
        print(f"Tweet Velocity: {snapshot.tweet_velocity:.2f} tweets/hour")

        print(f"\n--- Engagement Metrics ---")
        print(f"Total Engagement: {snapshot.total_engagement:,}")
        print(f"Avg Engagement/Tweet: {snapshot.avg_engagement_per_tweet:.1f}")
        print(f"Top Tweet Engagement: {snapshot.top_tweet_engagement:,}")

        if snapshot.top_influencer_usernames:
            print(f"\n--- Top Influencers ---")
            for i, username in enumerate(snapshot.top_influencer_usernames[:5], 1):
                print(f"{i}. @{username}")

        if snapshot.top_tweets:
            print(f"\n--- Top Tweets (by engagement) ---")
            for i, signal in enumerate(snapshot.top_tweets[:3], 1):
                print(f"\n{i}. @{signal.author_username}")
                if signal.author_verified:
                    print(f"   ✓ Verified")
                print(f"   Followers: {signal.author_followers:,}")
                print(f"   Text: {signal.text[:100]}...")
                print(f"   Engagement: {signal.likes} likes, {signal.retweets} RTs")
                print(f"   Velocity: {signal.velocity_score:.2f} eng/hour")

    except ValueError as e:
        print(f"\n⚠️  {e}")
        print("\nPlease set up Twitter API credentials first.")


def example_spike_detection():
    """Demonstrate sentiment spike detection."""
    print("\n" + "=" * 80)
    print("SENTIMENT SPIKE DETECTION EXAMPLE")
    print("=" * 80)

    try:
        aggregator = TwitterAggregator()

        # Detect if there's a spike in DOGE mentions
        result = aggregator.detect_sentiment_spike(
            token_symbol="DOGE",
            baseline_hours=24,
            recent_hours=1,
            spike_threshold=3.0,  # 3x baseline
        )

        print(f"\nToken: {result['token_symbol']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"\nBaseline Velocity: {result['baseline_velocity']:.2f} tweets/hour")
        print(f"Recent Velocity: {result['recent_velocity']:.2f} tweets/hour")
        print(f"Spike Multiplier: {result['spike_multiplier']:.2f}x")

        if result['is_spike']:
            print(f"\n🚨 SPIKE DETECTED! 🚨")
            print(f"Recent activity is {result['spike_multiplier']:.1f}x the baseline")
            print(f"Recent tweets: {result['recent_tweets']}")
            print(f"Total engagement: {result['recent_engagement']:,}")

            if result['top_recent_tweet']:
                tweet = result['top_recent_tweet']
                print(f"\nTop Recent Tweet:")
                print(f"  @{tweet.author_username}: {tweet.text[:100]}...")
                print(f"  Engagement: {tweet.likes + tweet.retweets:,}")
        else:
            print(f"\nNo significant spike detected.")

    except ValueError as e:
        print(f"\n⚠️  {e}")


def example_multi_token_monitoring():
    """Demonstrate monitoring multiple tokens."""
    print("\n" + "=" * 80)
    print("MULTI-TOKEN MONITORING EXAMPLE")
    print("=" * 80)

    try:
        aggregator = TwitterAggregator()

        # Monitor a portfolio of tokens
        tokens = ["BTC", "ETH", "SOL"]

        snapshots = aggregator.monitor_real_time_mentions(
            token_symbols=tokens,
            check_interval_seconds=60,
        )

        print(f"\nMonitoring {len(tokens)} tokens...")
        print(f"Timestamp: {datetime.utcnow()}")

        for snapshot in snapshots:
            print(f"\n{snapshot.token_symbol}:")
            print(f"  Tweets (1h): {snapshot.total_tweets}")
            print(f"  Velocity: {snapshot.tweet_velocity:.2f} tweets/hour")
            print(f"  Engagement: {snapshot.total_engagement:,}")
            print(f"  Quality: {snapshot.data_quality_score:.2f}")

    except ValueError as e:
        print(f"\n⚠️  {e}")


def example_custom_query_building():
    """Demonstrate building custom Twitter queries."""
    print("\n" + "=" * 80)
    print("CUSTOM QUERY BUILDING EXAMPLE")
    print("=" * 80)

    try:
        client = TwitterClientV2()

        # Build various queries
        queries = [
            ("Basic BTC query", client.build_crypto_query(
                token_symbol="BTC",
                exclude_retweets=True,
            )),
            ("High engagement ETH query", client.build_crypto_query(
                token_symbol="ETH",
                min_likes=50,
                verified_only=True,
            )),
            ("Solana narrative query", client.build_crypto_query(
                token_name="Solana",
                include_cashtags=False,  # Only use token name
                min_replies=10,
            )),
        ]

        for name, query in queries:
            print(f"\n{name}:")
            print(f"  {query}")

    except ValueError as e:
        print(f"\n⚠️  {e}")


if __name__ == "__main__":
    example_basic_tweet_search()
    example_sentiment_aggregation()
    example_spike_detection()
    example_multi_token_monitoring()
    example_custom_query_building()

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)
    print("\n💡 Tip: Set TWITTER_BEARER_TOKEN environment variable to enable all features")
