import logging
import statistics
from typing import List, Dict, Any

# Import client for existing LLM integration
try:
    from src.core.narrative import NarrativeAnalyzer
except ImportError:
    NarrativeAnalyzer = None  # Placeholder if not available

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Analyzes sentiment from news and social media for crypto tokens."""
    def __init__(self):
        self.narrative_generator = NarrativeAnalyzer() if NarrativeAnalyzer else None

    def analyze_news_sentiment(self, token_symbol: str, news_articles: List[Dict[str, Any]]) -> float:
        if not news_articles:
            logger.warning(f"No news articles for {token_symbol}, using default sentiment 0.5")
            return 0.5
        sentiments = []
        for article in news_articles:
            if article.get("sentiment") is not None:
                norm_sentiment = (article.get("sentiment", 0) + 10) / 20
                sentiments.append(min(max(norm_sentiment, 0), 1))
        if sentiments:
            return statistics.mean(sentiments)
        titles = [article.get("title", "") for article in news_articles]
        return self._analyze_with_llm(token_symbol, titles)

    def _analyze_with_llm(self, token_symbol: str, texts: List[str]) -> float:
        if not self.narrative_generator:
            logger.warning("NarrativeAnalyzer not available, returning default sentiment 0.5")
            return 0.5
        try:
            # Use NarrativeAnalyzer's analyze method which returns NarrativeInsight
            combined_text = [f"{token_symbol}: {text}" for text in texts[:5]]
            insight = self.narrative_generator.analyze(combined_text)
            # Return the sentiment_score from the insight (0.0 to 1.0)
            return insight.sentiment_score
        except Exception as e:
            logger.error(f"Error analyzing sentiment with LLM: {e}")
            return 0.5

    def get_dynamic_sentiment(self, token_symbol: str, news_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        news_sentiment = self.analyze_news_sentiment(token_symbol, news_articles)
        article_count = len(news_articles)
        confidence = min(1.0, article_count / 10)
        return {
            "score": news_sentiment,
            "articles_count": article_count,
            "confidence": confidence,
            "sources": list(set(article.get("source", "") for article in news_articles)),
            "latest_titles": [article.get("title", "") for article in news_articles[:3]]
        }
