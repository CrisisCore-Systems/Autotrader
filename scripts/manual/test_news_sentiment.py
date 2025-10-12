import os
import sys
from datetime import datetime

# Ensure the module is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.news_client import NewsClient
from src.core.sentiment import SentimentAnalyzer

def test_news_sentiment():
    """Test the news client and sentiment analyzer."""
    tokens = ["LINK", "UNI", "AAVE", "PEPE", "SOL", "MATIC", "DOT", "SHIB", "AVAX"]
    print(f"\n===== TESTING NEWS SENTIMENT ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) =====\n")
    news_client = NewsClient()
    sentiment_analyzer = SentimentAnalyzer()
    for token in tokens:
        print(f"\n--- Testing {token} ---")
        news = news_client.get_news_for_token(token, days=3)
        print(f"Found {len(news)} articles")
        if news:
            print(f"Sample headline: {news[0].get('title', 'No title')}")
        sentiment_data = sentiment_analyzer.get_dynamic_sentiment(token, news)
        print(f"Sentiment score: {sentiment_data['score']:.2f}")
        print(f"Confidence: {sentiment_data['confidence']:.2f}")
        print(f"Article count: {sentiment_data['articles_count']}")
        if sentiment_data.get('sources'):
            print(f"Sources: {', '.join(sentiment_data['sources'][:3])}")
    print("\n===== TEST COMPLETED =====")

if __name__ == "__main__":
    test_news_sentiment()
