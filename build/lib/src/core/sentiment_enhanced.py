import logging
import statistics
import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from collections import defaultdict

# Import client for existing LLM integration
try:
    from src.core.narrative import NarrativeGenerator
    HAS_NARRATIVE = True
except ImportError:
    NarrativeGenerator = None
    HAS_NARRATIVE = False

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """Enhanced sentiment analyzer with trend tracking and improved fallbacks."""
    def __init__(self, history_path: Optional[str] = None):
        # Initialize narrative generator if available
        self.narrative_generator = NarrativeGenerator() if HAS_NARRATIVE else None
        
        # Path for sentiment history
        self.history_path = history_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "../../artifacts/sentiment_history.json"
        )
        
        # Keywords for keyword-based sentiment analysis fallback
        self.positive_keywords = [
            "bullish", "surge", "soar", "rally", "jump", "gain", "positive", "rise", "increase", 
            "outperform", "record high", "all-time high", "ATH", "breakout", "breakthrough", 
            "strong", "strength", "momentum", "uptrend", "up trend", "adoption", "partnership", 
            "expand", "growth", "innovative"
        ]
        
        self.negative_keywords = [
            "bearish", "plunge", "crash", "collapse", "tumble", "fall", "drop", "decline", 
            "negative", "decrease", "underperform", "sell-off", "selling", "correction", 
            "downtrend", "down trend", "weak", "weakness", "risk", "concern", "warning", 
            "vulnerable", "bearish", "fear", "hack", "exploit", "attack", "scam", "fraud"
        ]
        
        # Load history if available
        self.sentiment_history = self._load_history()
        
    def _load_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load sentiment history from disk."""
        if not os.path.exists(self.history_path):
            return defaultdict(list)
            
        try:
            with open(self.history_path, 'r') as f:
                history = json.load(f)
                # Convert to defaultdict for easier handling
                return defaultdict(list, history)
        except Exception as e:
            logger.error(f"Failed to load sentiment history: {e}")
            return defaultdict(list)
    
    def _save_history(self) -> None:
        """Save sentiment history to disk."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
            
            with open(self.history_path, 'w') as f:
                json.dump(dict(self.sentiment_history), f)
        except Exception as e:
            logger.error(f"Failed to save sentiment history: {e}")
    
    def analyze_news_sentiment(self, token_symbol: str, news_articles: List[Dict[str, Any]]) -> float:
        """
        Analyze sentiment from news articles using multiple methods.
        
        Args:
            token_symbol: Symbol of the token
            news_articles: List of news articles
            
        Returns:
            Sentiment score (0-1 scale)
        """
        if not news_articles:
            logger.warning(f"No news articles for {token_symbol}, using default sentiment 0.5")
            return 0.5
            
        # Try multiple methods and combine results
        methods_results = []
        
        # Method 1: Use pre-calculated sentiment if available
        pre_calculated = []
        for article in news_articles:
            if article.get("sentiment") is not None:
                # Normalize to 0-1 scale
                norm_sentiment = (article.get("sentiment", 0) + 1) / 2
                pre_calculated.append(min(max(norm_sentiment, 0), 1))
        
        if pre_calculated:
            methods_results.append(statistics.mean(pre_calculated))
            
        # Method 2: Use LLM-based sentiment analysis
        if self.narrative_generator and len(news_articles) > 0:
            llm_sentiment = self._analyze_with_llm(token_symbol, news_articles)
            if llm_sentiment is not None:
                methods_results.append(llm_sentiment)
        
        # Method 3: Use keyword-based sentiment analysis
        keyword_sentiment = self._analyze_with_keywords(news_articles)
        if keyword_sentiment is not None:
            methods_results.append(keyword_sentiment)
            
        # Combine results with preference for LLM when available
        if not methods_results:
            # Default to neutral if no methods worked
            return 0.5
        elif len(methods_results) == 1:
            # Single method
            return methods_results[0]
        else:
            # Weight LLM higher when it's available (assuming it's the second element)
            if len(methods_results) > 1 and self.narrative_generator:
                # 60% weight to LLM, 40% to other methods
                return 0.6 * methods_results[1] + 0.4 * statistics.mean([m for m in methods_results if m != methods_results[1]])
            else:
                return statistics.mean(methods_results)
    
    def _analyze_with_llm(self, token_symbol: str, news_articles: List[Dict[str, Any]], 
                         max_articles: int = 5) -> Optional[float]:
        """
        Analyze sentiment using LLM.
        
        Args:
            token_symbol: Symbol of the token
            news_articles: List of news articles
            max_articles: Maximum number of articles to include
            
        Returns:
            Sentiment score or None if failed
        """
        if not self.narrative_generator:
            return None
            
        try:
            # Extract titles and publication dates
            articles_data = []
            for article in news_articles[:max_articles]:
                title = article.get("title", "")
                published = article.get("published_at", "")
                source = article.get("source", "Unknown")
                
                articles_data.append(f"{title} (Source: {source}, Date: {published})")
            
            combined_text = "\n".join(articles_data)
            
            prompt = f"""Analyze the sentiment of these recent news headlines about {token_symbol} cryptocurrency.
Focus on market sentiment, investor attitude, and project outlook.
Rate the overall sentiment on a scale of 0.0 (extremely negative) to 1.0 (extremely positive).

News headlines:
{combined_text}

Output only a single number between 0.0 and 1.0 representing the sentiment score. Nothing else."""

            response = self.narrative_generator.generate(prompt, max_tokens=5)
            try:
                sentiment = float(response.strip())
                return min(max(sentiment, 0), 1)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse sentiment from LLM response: {response}")
                return None
        except Exception as e:
            logger.error(f"Error analyzing sentiment with LLM: {e}")
            return None
    
    def _analyze_with_keywords(self, news_articles: List[Dict[str, Any]]) -> float:
        """
        Analyze sentiment using keyword matching.
        
        Args:
            news_articles: List of news articles
            
        Returns:
            Sentiment score (0-1 scale)
        """
        if not news_articles:
            return 0.5
            
        scores = []
        
        for article in news_articles:
            title = article.get("title", "").lower()
            content = article.get("content", "").lower()
            text = f"{title} {content}"
            
            # Count positive and negative keyword matches
            positive_count = sum(1 for keyword in self.positive_keywords if keyword.lower() in text)
            negative_count = sum(1 for keyword in self.negative_keywords if keyword.lower() in text)
            
            total = positive_count + negative_count
            if total == 0:
                scores.append(0.5)  # Neutral if no keywords match
            else:
                score = positive_count / total
                scores.append(score)
        
        if not scores:
            return 0.5
            
        return statistics.mean(scores)
    
    def get_dynamic_sentiment(self, token_symbol: str, news_articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get dynamic sentiment analysis for a token.
        
        Args:
            token_symbol: Symbol of the token
            news_articles: List of news articles
            
        Returns:
            Dictionary with sentiment analysis results
        """
        # Calculate current sentiment
        news_sentiment = self.analyze_news_sentiment(token_symbol, news_articles)
        article_count = len(news_articles)
        
        # Calculate confidence based on article count and diversity
        sources = set(article.get("source", "") for article in news_articles)
        source_count = len(sources)
        
        # More articles and diverse sources increase confidence
        article_confidence = min(1.0, article_count / 10)
        source_confidence = min(1.0, source_count / 3)
        confidence = 0.7 * article_confidence + 0.3 * source_confidence
        
        # Extract latest headlines and sources
        latest_headlines = []
        for article in sorted(news_articles, 
                             key=lambda x: x.get("published_at", ""), 
                             reverse=True)[:3]:
            latest_headlines.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "source": article.get("source", ""),
                "published_at": article.get("published_at", "")
            })
        
        # Create result
        result = {
            "token": token_symbol,
            "timestamp": datetime.now().isoformat(),
            "score": news_sentiment,
            "articles_count": article_count,
            "source_count": source_count,
            "confidence": confidence,
            "sources": list(sources),
            "latest_headlines": latest_headlines
        }
        
        # Add sentiment trend data
        trend_data = self._add_to_history(token_symbol, result)
        result.update(trend_data)
        
        return result
    
    def _add_to_history(self, token_symbol: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add current sentiment to history and calculate trends.
        
        Args:
            token_symbol: Symbol of the token
            current_data: Current sentiment data
            
        Returns:
            Dictionary with trend analysis
        """
        # Create a simplified entry for history
        history_entry = {
            "timestamp": current_data["timestamp"],
            "score": current_data["score"],
            "articles_count": current_data["articles_count"],
            "confidence": current_data["confidence"]
        }
        
        # Add to history
        token_history = self.sentiment_history[token_symbol]
        token_history.append(history_entry)
        
        # Keep only last 30 days of history
        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        token_history = [entry for entry in token_history 
                         if entry["timestamp"] >= cutoff]
        
        # Update history
        self.sentiment_history[token_symbol] = token_history
        self._save_history()
        
        # Calculate trends
        return self._calculate_trends(token_history)
    
    def _calculate_trends(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate sentiment trends from history.
        
        Args:
            history: List of historical sentiment entries
            
        Returns:
            Dictionary with trend analysis
        """
        if not history or len(history) < 2:
            return {
                "trend_7d": 0,
                "trend_24h": 0,
                "volatility": 0
            }
            
        # Sort by timestamp
        sorted_history = sorted(history, key=lambda x: x["timestamp"])
        
        # Get sentiment scores
        scores = [entry["score"] for entry in sorted_history]
        
        # Calculate 24-hour trend
        cutoff_24h = (datetime.now() - timedelta(hours=24)).isoformat()
        scores_24h = [entry["score"] for entry in sorted_history 
                     if entry["timestamp"] >= cutoff_24h]
        
        # Calculate 7-day trend
        cutoff_7d = (datetime.now() - timedelta(days=7)).isoformat()
        scores_7d = [entry["score"] for entry in sorted_history 
                    if entry["timestamp"] >= cutoff_7d]
        
        # Calculate trends (change in sentiment)
        trend_24h = 0
        if len(scores_24h) >= 2:
            trend_24h = scores_24h[-1] - scores_24h[0]
            
        trend_7d = 0
        if len(scores_7d) >= 2:
            trend_7d = scores_7d[-1] - scores_7d[0]
            
        # Calculate volatility (standard deviation)
        volatility = 0
        if len(scores) >= 3:
            volatility = float(np.std(scores))
            
        return {
            "trend_7d": round(trend_7d, 3),
            "trend_24h": round(trend_24h, 3),
            "volatility": round(volatility, 3),
            "history_count": len(history)
        }
    
    def get_sentiment_history(self, token_symbol: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get historical sentiment data for a token.
        
        Args:
            token_symbol: Symbol of the token
            days: Number of days of history to return
            
        Returns:
            List of historical sentiment entries
        """
        if token_symbol not in self.sentiment_history:
            return []
            
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return [entry for entry in self.sentiment_history[token_symbol] 
               if entry["timestamp"] >= cutoff]
    
    def compare_tokens(self, tokens: List[str]) -> Dict[str, Any]:
        """
        Compare sentiment across multiple tokens.
        
        Args:
            tokens: List of token symbols
            
        Returns:
            Dictionary with comparative sentiment analysis
        """
        result = {"tokens": {}}
        
        for token in tokens:
            token_history = self.get_sentiment_history(token)
            
            if not token_history:
                result["tokens"][token] = {
                    "score": 0.5,
                    "trend_7d": 0,
                    "data_available": False
                }
                continue
                
            # Get latest score
            latest = sorted(token_history, key=lambda x: x["timestamp"])[-1]
            
            # Calculate trends
            trends = self._calculate_trends(token_history)
            
            result["tokens"][token] = {
                "score": latest["score"],
                "confidence": latest["confidence"],
                "trend_7d": trends["trend_7d"],
                "trend_24h": trends["trend_24h"],
                "volatility": trends["volatility"],
                "data_available": True
            }
        
        # Add rankings
        scores = [(token, data["score"]) for token, data in result["tokens"].items() 
                 if data["data_available"]]
        
        if scores:
            ranked = sorted(scores, key=lambda x: x[1], reverse=True)
            result["rankings"] = {
                "by_sentiment": [{"token": token, "score": score} for token, score in ranked]
            }
            
        return result