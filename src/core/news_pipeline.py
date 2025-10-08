"""Integration module for enhanced news sentiment functionality with the core pipeline."""

from src.core.news_client_enhanced import NewsClient as EnhancedNewsClient
from src.core.sentiment_enhanced import SentimentAnalyzer as EnhancedSentimentAnalyzer
from src.core.sentiment_dashboard import NewsSentimentDashboard

class EnhancedNewsPipeline:
    """Enhanced news sentiment pipeline for integration with the Hidden-Gem Scanner."""
    
    def __init__(self):
        """Initialize the enhanced news pipeline."""
        self.news_client = EnhancedNewsClient()
        self.sentiment_analyzer = EnhancedSentimentAnalyzer()
        self.dashboard = NewsSentimentDashboard()
    
    def analyze_token(self, token_symbol: str, days: int = 3, force_refresh: bool = False):
        """
        Analyze news sentiment for a specific token.
        
        Args:
            token_symbol: Symbol of the token
            days: Days of news to analyze
            force_refresh: Whether to force refresh of news cache
            
        Returns:
            Sentiment analysis results
        """
        news_articles = self.news_client.get_news_for_token(token_symbol, days=days, force_refresh=force_refresh)
        sentiment_data = self.sentiment_analyzer.get_dynamic_sentiment(token_symbol, news_articles)
        
        return {
            "token": token_symbol,
            "news_count": len(news_articles),
            "sentiment": sentiment_data
        }
    
    def analyze_multiple_tokens(self, tokens: list, days: int = 3):
        """
        Analyze news sentiment for multiple tokens.
        
        Args:
            tokens: List of token symbols
            days: Days of news to analyze
            
        Returns:
            Comparative sentiment analysis
        """
        results = {}
        
        for token in tokens:
            results[token] = self.analyze_token(token, days)
        
        # Add comparative analysis
        comparative = self.sentiment_analyzer.compare_tokens(tokens)
        
        return {
            "tokens": results,
            "comparative": comparative
        }
    
    def generate_dashboard(self, tokens: list, days: int = 3):
        """
        Generate a sentiment dashboard for a list of tokens.
        
        Args:
            tokens: List of token symbols
            days: Days of news to analyze
            
        Returns:
            Path to generated dashboard
        """
        report = self.dashboard.generate_sentiment_report(tokens, days=days)
        dashboard_path = self.dashboard.generate_html_dashboard(report)
        
        return dashboard_path
    
    def get_news_stats(self, token_symbol: str, days_range: list = [1, 3, 7]):
        """
        Get news statistics for a token over different time ranges.
        
        Args:
            token_symbol: Symbol of the token
            days_range: List of day ranges to check
            
        Returns:
            News statistics
        """
        return self.news_client.get_news_stats(token_symbol, days_range)

# Integration helper to replace standard NewsClient with enhanced version in pipeline
def enhance_pipeline(pipeline):
    """
    Replace standard NewsClient with enhanced version in a HiddenGemScanner pipeline.
    
    Args:
        pipeline: HiddenGemScanner instance
        
    Returns:
        Enhanced pipeline
    """
    # Replace news client
    pipeline.news_client = EnhancedNewsClient()
    
    # Replace sentiment analyzer
    pipeline.sentiment_analyzer = EnhancedSentimentAnalyzer()
    
    # Add enhanced news methods to pipeline
    pipeline.get_news_stats = pipeline.news_client.get_news_stats
    pipeline.compare_tokens = pipeline.sentiment_analyzer.compare_tokens
    
    return pipeline