import os
import sys
from datetime import datetime
import argparse
import json

# Ensure the module is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import both original and enhanced implementations
from src.core.news_client import NewsClient as OriginalNewsClient
from src.core.sentiment import SentimentAnalyzer as OriginalSentimentAnalyzer

from src.core.news_client_enhanced import NewsClient as EnhancedNewsClient
from src.core.sentiment_enhanced import SentimentAnalyzer as EnhancedSentimentAnalyzer

def setup_argparse():
    """Set up command-line argument parsing."""
    parser = argparse.ArgumentParser(description='Test news sentiment analysis functionality.')
    parser.add_argument('--tokens', type=str, default="LINK,UNI,AAVE,PEPE,SOL,MATIC,DOT,SHIB,AVAX",
                        help='Comma-separated list of tokens to test')
    parser.add_argument('--days', type=int, default=3,
                        help='Number of days of news to fetch')
    parser.add_argument('--enhanced', action='store_true',
                        help='Use enhanced implementations')
    parser.add_argument('--compare', action='store_true',
                        help='Compare original and enhanced implementations')
    parser.add_argument('--force-refresh', action='store_true',
                        help='Force refresh of news cache')
    parser.add_argument('--output', type=str, default="",
                        help='Save results to JSON file')
    
    return parser.parse_args()

def test_news_sentiment(tokens, days=3, use_enhanced=False, force_refresh=False):
    """
    Test the news client and sentiment analyzer.
    
    Args:
        tokens: List of token symbols to test
        days: Days of news to fetch
        use_enhanced: Whether to use enhanced implementations
        force_refresh: Whether to force refresh of news cache
        
    Returns:
        Dictionary with test results
    """
    if use_enhanced:
        print(f"\n===== TESTING ENHANCED NEWS SENTIMENT ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) =====\n")
        news_client = EnhancedNewsClient()
        sentiment_analyzer = EnhancedSentimentAnalyzer()
    else:
        print(f"\n===== TESTING ORIGINAL NEWS SENTIMENT ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) =====\n")
        news_client = OriginalNewsClient()
        sentiment_analyzer = OriginalSentimentAnalyzer()
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "tokens": {},
        "summary": {
            "total_tokens": len(tokens),
            "tokens_with_news": 0,
            "average_news_count": 0,
            "average_sentiment": 0
        }
    }
    
    total_news_count = 0
    total_sentiment = 0
    
    for token in tokens:
        print(f"\n--- Testing {token} ---")
        
        # Get news for token
        if use_enhanced:
            news = news_client.get_news_for_token(token, days=days, force_refresh=force_refresh)
        else:
            news = news_client.get_news_for_token(token, days=days)
        
        # Print statistics
        print(f"Found {len(news)} articles")
        if news:
            print(f"Sample headline: {news[0].get('title', 'No title')}")
            
        # Get sentiment
        sentiment_data = sentiment_analyzer.get_dynamic_sentiment(token, news)
        
        # Print sentiment data
        print(f"Sentiment score: {sentiment_data['score']:.2f}")
        print(f"Confidence: {sentiment_data['confidence']:.2f}")
        print(f"Article count: {sentiment_data['articles_count']}")
        if sentiment_data.get('sources'):
            print(f"Sources: {', '.join(sentiment_data['sources'][:3])}")
        
        # Store results
        results["tokens"][token] = {
            "news_count": len(news),
            "sentiment_data": sentiment_data
        }
        
        # Update summary data
        if len(news) > 0:
            results["summary"]["tokens_with_news"] += 1
        total_news_count += len(news)
        total_sentiment += sentiment_data["score"]
    
    # Calculate averages
    if len(tokens) > 0:
        results["summary"]["average_news_count"] = total_news_count / len(tokens)
        results["summary"]["average_sentiment"] = total_sentiment / len(tokens)
    
    # Enhanced summary
    if use_enhanced:
        # Compare sentiment across tokens
        results["comparative"] = sentiment_analyzer.compare_tokens(tokens)
    
    print("\n===== TEST COMPLETED =====")
    return results

def compare_implementations(tokens, days=3, force_refresh=False):
    """
    Compare original and enhanced implementations.
    
    Args:
        tokens: List of token symbols to test
        days: Days of news to fetch
        force_refresh: Whether to force refresh of news cache
        
    Returns:
        Dictionary with comparison results
    """
    print(f"\n===== COMPARING IMPLEMENTATIONS ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) =====\n")
    
    # Run both implementations
    original_results = test_news_sentiment(tokens, days, use_enhanced=False, force_refresh=force_refresh)
    enhanced_results = test_news_sentiment(tokens, days, use_enhanced=True, force_refresh=force_refresh)
    
    # Combine results
    comparison = {
        "timestamp": datetime.now().isoformat(),
        "tokens": {},
        "summary": {
            "original": original_results["summary"],
            "enhanced": enhanced_results["summary"],
        }
    }
    
    # Compare token-by-token
    for token in tokens:
        comparison["tokens"][token] = {
            "original": {
                "news_count": original_results["tokens"][token]["news_count"],
                "sentiment": original_results["tokens"][token]["sentiment_data"]["score"],
                "confidence": original_results["tokens"][token]["sentiment_data"]["confidence"]
            },
            "enhanced": {
                "news_count": enhanced_results["tokens"][token]["news_count"],
                "sentiment": enhanced_results["tokens"][token]["sentiment_data"]["score"],
                "confidence": enhanced_results["tokens"][token]["sentiment_data"]["confidence"]
            },
            "differences": {
                "news_count_diff": enhanced_results["tokens"][token]["news_count"] - original_results["tokens"][token]["news_count"],
                "sentiment_diff": enhanced_results["tokens"][token]["sentiment_data"]["score"] - original_results["tokens"][token]["sentiment_data"]["score"],
                "confidence_diff": enhanced_results["tokens"][token]["sentiment_data"]["confidence"] - original_results["tokens"][token]["sentiment_data"]["confidence"]
            }
        }
    
    # Add comparative sentiment data
    if "comparative" in enhanced_results:
        comparison["comparative"] = enhanced_results["comparative"]
    
    return comparison

def save_results(results, output_file):
    """Save results to a JSON file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {output_file}")
    except Exception as e:
        print(f"Error saving results: {e}")

def main():
    """Main function."""
    args = setup_argparse()
    
    # Parse token list
    tokens = [token.strip() for token in args.tokens.split(',') if token.strip()]
    
    # Run tests
    if args.compare:
        results = compare_implementations(tokens, args.days, args.force_refresh)
    else:
        results = test_news_sentiment(tokens, args.days, args.enhanced, args.force_refresh)
    
    # Save results if requested
    if args.output:
        save_results(results, args.output)
        
    # Print summary
    print("\n===== SUMMARY =====")
    if args.compare:
        print(f"Original implementation found news for {results['summary']['original']['tokens_with_news']} tokens")
        print(f"Enhanced implementation found news for {results['summary']['enhanced']['tokens_with_news']} tokens")
        
        # Show tokens with biggest sentiment differences
        diffs = [(token, abs(data["differences"]["sentiment_diff"])) 
                for token, data in results["tokens"].items()]
        if diffs:
            print("\nBiggest sentiment differences:")
            for token, diff in sorted(diffs, key=lambda x: x[1], reverse=True)[:3]:
                original = results["tokens"][token]["original"]["sentiment"]
                enhanced = results["tokens"][token]["enhanced"]["sentiment"]
                print(f"  {token}: {original:.2f} → {enhanced:.2f} (diff: {results['tokens'][token]['differences']['sentiment_diff']:.2f})")
    else:
        print(f"Found news for {results['summary']['tokens_with_news']} out of {results['summary']['total_tokens']} tokens")
        print(f"Average news count: {results['summary']['average_news_count']:.1f}")
        print(f"Average sentiment: {results['summary']['average_sentiment']:.2f}")

if __name__ == "__main__":
    main()