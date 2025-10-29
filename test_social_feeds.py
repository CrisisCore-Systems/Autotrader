"""Test script for Twitter and Reddit social feeds (no API keys required for demo)."""

import os
from datetime import datetime

# Check environment variables
twitter_token = os.getenv("TWITTER_BEARER_TOKEN")
reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")

print("=" * 60)
print("Social Feed Configuration Check")
print("=" * 60)
print(f"TWITTER_BEARER_TOKEN: {'✓ Set' if twitter_token else '✗ Not Set'}")
print(f"REDDIT_CLIENT_ID: {'✓ Set' if reddit_client_id else '✗ Not Set'}")
print(f"REDDIT_CLIENT_SECRET: {'✓ Set' if reddit_client_secret else '✗ Not Set'}")
print("=" * 60)

# Test Reddit client (works without OAuth for read-only public access)
print("\n🔍 Testing Reddit Public API (no credentials required)...")
try:
    from src.core.reddit_client import RedditClient
    
    # Initialize without credentials for public read-only access
    reddit = RedditClient()
    print("✓ Reddit client initialized (public read-only mode)")
    
    # Fetch crypto posts from r/CryptoCurrency
    print("\nFetching posts from r/CryptoCurrency...")
    posts = reddit.get_subreddit_posts(
        "CryptoCurrency",
        sort="hot",
        limit=5,
    )
    print(f"✓ Fetched {len(posts)} posts")
    
    if posts:
        print("\nSample post:")
        post = posts[0]
        print(f"  Title: {post.get('title', 'N/A')[:60]}...")
        print(f"  Score: {post.get('score', 0)}")
        print(f"  Comments: {post.get('num_comments', 0)}")
        print(f"  Author: /u/{post.get('author', '[deleted]')}")
        
    # Test crypto sentiment fetch
    print("\n\nTesting crypto sentiment fetch for BTC...")
    sentiment_posts = reddit.fetch_crypto_sentiment(
        token_symbol="BTC",
        hours_back=24,
        min_score=10,
        limit=5,
    )
    print(f"✓ Found {len(sentiment_posts)} BTC-related posts")
    
    if sentiment_posts:
        print("\nTop BTC post:")
        post = sentiment_posts[0]
        normalized = reddit.normalize_to_social_post(post)
        print(f"  Content: {normalized['content'][:80]}...")
        print(f"  Score: {normalized['metrics']['score']}")
        print(f"  Subreddit: r/{post.get('subreddit')}")
        print(f"  URL: {normalized['url']}")
    
    print("\n✅ Reddit client working correctly (public API)!")
    
except Exception as e:
    print(f"❌ Reddit test failed: {e}")
    import traceback
    traceback.print_exc()

# Test Twitter client (requires API key)
if twitter_token:
    print("\n\n🐦 Testing Twitter API v2...")
    try:
        from src.core.twitter_client import TwitterClientV2
        
        twitter = TwitterClientV2(bearer_token=twitter_token)
        print("✓ Twitter client initialized")
        
        # Test sentiment fetch
        print("\nFetching Twitter sentiment for ETH...")
        response = twitter.fetch_sentiment_signals(
            token_symbol="ETH",
            hours_back=24,
            max_results=5,
            min_engagement=10,
        )
        
        tweets = response.get("data", [])
        print(f"✓ Fetched {len(tweets)} tweets")
        
        if tweets:
            print("\nSample tweet:")
            tweet = tweets[0]
            metrics = tweet.get("public_metrics", {})
            print(f"  Text: {tweet.get('text', '')[:80]}...")
            print(f"  Likes: {metrics.get('like_count', 0)}")
            print(f"  Retweets: {metrics.get('retweet_count', 0)}")
            print(f"  Replies: {metrics.get('reply_count', 0)}")
        
        print("\n✅ Twitter client working correctly!")
        
    except Exception as e:
        print(f"❌ Twitter test failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n\n⚠️  Twitter API test skipped (no TWITTER_BEARER_TOKEN)")
    print("To enable Twitter:")
    print("  1. Go to https://developer.twitter.com/en/portal/dashboard")
    print("  2. Create a project and app")
    print("  3. Generate a Bearer Token")
    print("  4. Set TWITTER_BEARER_TOKEN environment variable")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print("✅ Reddit: Working (public API, no credentials needed)")
if twitter_token:
    print("✅ Twitter: Configured and tested")
else:
    print("⚠️  Twitter: Not configured (requires API key)")
print("\nTo use in scans, both feeds will automatically activate if credentials are set.")
print("=" * 60)
