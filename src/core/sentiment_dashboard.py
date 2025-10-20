import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path

# Import enhanced components
from src.core.news_client_enhanced import NewsClient
from src.core.sentiment_enhanced import SentimentAnalyzer

logger = logging.getLogger(__name__)

class NewsSentimentDashboard:
    """Dashboard for news sentiment visualization and reporting."""
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the dashboard.
        
        Args:
            output_dir: Directory for output files
        """
        self.news_client = NewsClient()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "../../artifacts/dashboard"
        )
        
        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def generate_sentiment_report(self, tokens: List[str], days: int = 3) -> Dict[str, Any]:
        """
        Generate a sentiment report for a list of tokens.
        
        Args:
            tokens: List of token symbols
            days: Days of news to analyze
            
        Returns:
            Report data
        """
        logger.info(f"Generating sentiment report for {len(tokens)} tokens")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "tokens": {},
            "rankings": {},
            "summary": {
                "token_count": len(tokens),
                "tokens_with_news": 0,
                "average_sentiment": 0,
                "most_positive": None,
                "most_negative": None,
                "most_news": None
            }
        }
        
        sentiment_scores = []
        news_counts = []
        
        # Process each token
        for token in tokens:
            logger.info(f"Processing {token}")
            
            # Get news for token
            news = self.news_client.get_news_for_token(token, days=days)
            
            # Get sentiment
            sentiment_data = self.sentiment_analyzer.get_dynamic_sentiment(token, news)
            
            # Store token data
            report["tokens"][token] = {
                "news_count": len(news),
                "sentiment": sentiment_data["score"],
                "confidence": sentiment_data["confidence"],
                "trend_7d": sentiment_data.get("trend_7d", 0),
                "trend_24h": sentiment_data.get("trend_24h", 0),
                "volatility": sentiment_data.get("volatility", 0),
                "latest_headlines": sentiment_data.get("latest_headlines", [])
            }
            
            # Track summary data
            if len(news) > 0:
                sentiment_scores.append((token, sentiment_data["score"]))
                news_counts.append((token, len(news)))
                report["summary"]["tokens_with_news"] += 1
        
        # Calculate rankings
        if sentiment_scores:
            # Most positive tokens
            most_positive = sorted(sentiment_scores, key=lambda x: x[1], reverse=True)
            report["rankings"]["most_positive"] = most_positive
            if most_positive:
                report["summary"]["most_positive"] = most_positive[0][0]
                
            # Most negative tokens
            most_negative = sorted(sentiment_scores, key=lambda x: x[1])
            report["rankings"]["most_negative"] = most_negative
            if most_negative:
                report["summary"]["most_negative"] = most_negative[0][0]
                
            # Tokens with most news
            most_news = sorted(news_counts, key=lambda x: x[1], reverse=True)
            report["rankings"]["most_news"] = most_news
            if most_news:
                report["summary"]["most_news"] = most_news[0][0]
                
            # Average sentiment
            report["summary"]["average_sentiment"] = sum(s[1] for s in sentiment_scores) / len(sentiment_scores)
        
        # Add comparative sentiment data
        report["comparative"] = self.sentiment_analyzer.compare_tokens(tokens)
        
        # Save report
        self._save_report(report)
        
        return report
    
    def _save_report(self, report: Dict[str, Any]) -> str:
        """
        Save the report to a JSON file.
        
        Args:
            report: Report data
            
        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(self.output_dir, f"sentiment_report_{timestamp}.json")
        
        try:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return ""
    
    def generate_visualizations(self, report: Dict[str, Any]) -> List[str]:
        """
        Generate visualizations from the report.
        
        Args:
            report: Report data
            
        Returns:
            List of paths to generated visualizations
        """
        logger.info("Generating visualizations")
        
        output_files = []
        
        try:
            # Create visualization directory
            viz_dir = os.path.join(self.output_dir, "visualizations")
            Path(viz_dir).mkdir(parents=True, exist_ok=True)
            
            # Generate sentiment comparison chart
            sentiment_chart_path = self._generate_sentiment_chart(report, viz_dir)
            if sentiment_chart_path:
                output_files.append(sentiment_chart_path)
                
            # Generate news count chart
            news_chart_path = self._generate_news_count_chart(report, viz_dir)
            if news_chart_path:
                output_files.append(news_chart_path)
                
            # Generate trend chart
            trend_chart_path = self._generate_trend_chart(report, viz_dir)
            if trend_chart_path:
                output_files.append(trend_chart_path)
                
        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")
            
        return output_files
    
    def _generate_sentiment_chart(self, report: Dict[str, Any], output_dir: str) -> str:
        """
        Generate a sentiment comparison chart.
        
        Args:
            report: Report data
            output_dir: Output directory
            
        Returns:
            Path to generated chart
        """
        # Extract sentiment scores
        tokens = []
        scores = []
        confidences = []
        
        for token, data in report["tokens"].items():
            tokens.append(token)
            scores.append(data["sentiment"])
            confidences.append(data["confidence"])
        
        if not tokens:
            return ""
            
        # Create DataFrame
        df = pd.DataFrame({
            "Token": tokens,
            "Sentiment": scores,
            "Confidence": confidences
        })
        
        # Sort by sentiment
        df = df.sort_values("Sentiment", ascending=False)
        
        # Create chart
        plt.figure(figsize=(12, 8))
        
        # Create bar chart with color gradient
        bars = plt.bar(df["Token"], df["Sentiment"], color=plt.cm.RdYlGn(df["Sentiment"]))
        
        # Add confidence as error bars
        plt.errorbar(df["Token"], df["Sentiment"], 
                     yerr=(1 - df["Confidence"]) * 0.1,
                     fmt="none", ecolor="black", capsize=3)
        
        # Add annotations
        for i, bar in enumerate(bars):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, height,
                    f"{height:.2f}", ha="center", va="bottom", fontsize=9)
        
        # Set labels and title
        plt.xlabel("Token")
        plt.ylabel("Sentiment Score (0-1)")
        plt.title("Crypto Token Sentiment Comparison")
        plt.ylim(0, 1.1)
        plt.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save chart
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"sentiment_comparison_{timestamp}.png")
        plt.savefig(output_path)
        plt.close()
        
        return output_path
    
    def _generate_news_count_chart(self, report: Dict[str, Any], output_dir: str) -> str:
        """
        Generate a news count chart.
        
        Args:
            report: Report data
            output_dir: Output directory
            
        Returns:
            Path to generated chart
        """
        # Extract news counts
        tokens = []
        counts = []
        
        for token, data in report["tokens"].items():
            tokens.append(token)
            counts.append(data["news_count"])
        
        if not tokens:
            return ""
            
        # Create DataFrame
        df = pd.DataFrame({
            "Token": tokens,
            "News Count": counts
        })
        
        # Sort by news count
        df = df.sort_values("News Count", ascending=False)
        
        # Create chart
        plt.figure(figsize=(12, 6))
        
        # Create bar chart
        bars = plt.bar(df["Token"], df["News Count"], color="steelblue")
        
        # Add annotations
        for i, bar in enumerate(bars):
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, height,
                    str(int(height)), ha="center", va="bottom")
        
        # Set labels and title
        plt.xlabel("Token")
        plt.ylabel("Number of News Articles")
        plt.title("News Coverage by Token")
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save chart
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"news_coverage_{timestamp}.png")
        plt.savefig(output_path)
        plt.close()
        
        return output_path
    
    def _generate_trend_chart(self, report: Dict[str, Any], output_dir: str) -> str:
        """
        Generate a sentiment trend chart.
        
        Args:
            report: Report data
            output_dir: Output directory
            
        Returns:
            Path to generated chart
        """
        # Extract trend data
        tokens = []
        trends_7d = []
        trends_24h = []
        
        for token, data in report["tokens"].items():
            if "trend_7d" in data and "trend_24h" in data:
                tokens.append(token)
                trends_7d.append(data["trend_7d"])
                trends_24h.append(data["trend_24h"])
        
        if not tokens:
            return ""
            
        # Create DataFrame
        df = pd.DataFrame({
            "Token": tokens,
            "7-Day Trend": trends_7d,
            "24-Hour Trend": trends_24h
        })
        
        # Sort by 7-day trend
        df = df.sort_values("7-Day Trend", ascending=False)
        
        # Create chart
        plt.figure(figsize=(12, 8))
        
        # Set width of bars
        bar_width = 0.35
        index = np.arange(len(df["Token"]))
        
        # Create bar chart
        plt.bar(index, df["7-Day Trend"], bar_width, label="7-Day Trend", color="cornflowerblue")
        plt.bar(index + bar_width, df["24-Hour Trend"], bar_width, label="24-Hour Trend", color="lightcoral")
        
        # Set labels and title
        plt.xlabel("Token")
        plt.ylabel("Sentiment Trend")
        plt.title("Sentiment Trend by Token")
        plt.xticks(index + bar_width / 2, df["Token"], rotation=45)
        plt.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
        plt.legend()
        plt.tight_layout()
        
        # Save chart
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"sentiment_trend_{timestamp}.png")
        plt.savefig(output_path)
        plt.close()
        
        return output_path
    
    def generate_html_dashboard(self, report: Dict[str, Any]) -> str:
        """
        Generate an HTML dashboard from the report.
        
        Args:
            report: Report data
            
        Returns:
            Path to generated HTML file
        """
        logger.info("Generating HTML dashboard")
        
        try:
            # Generate visualizations
            viz_paths = self.generate_visualizations(report)
            
            # Create HTML content
            html_content = self._generate_html_content(report, viz_paths)
            
            # Save HTML file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(self.output_dir, f"sentiment_dashboard_{timestamp}.html")
            
            with open(output_path, 'w') as f:
                f.write(html_content)
                
            logger.info(f"HTML dashboard saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error generating HTML dashboard: {e}")
            return ""
    
    def _generate_html_content(self, report: Dict[str, Any], viz_paths: List[str]) -> str:
        """
        Generate HTML content for the dashboard.
        
        Args:
            report: Report data
            viz_paths: Paths to visualizations
            
        Returns:
            HTML content
        """
        # Convert visualization paths to relative paths
        relative_viz_paths = []
        for path in viz_paths:
            if path:
                relative_viz_paths.append(os.path.relpath(path, self.output_dir))
        
        # Generate token table rows
        token_rows = ""
        for token, data in sorted(report["tokens"].items(), 
                                  key=lambda x: x[1]["sentiment"], 
                                  reverse=True):
            sentiment_color = self._get_sentiment_color(data["sentiment"])
            trend_icon = "↗️" if data.get("trend_7d", 0) > 0 else "↘️" if data.get("trend_7d", 0) < 0 else "➡️"
            
            # Format headlines
            headlines_html = ""
            for headline in data.get("latest_headlines", [])[:2]:
                title = headline.get("title", "")
                url = headline.get("url", "")
                source = headline.get("source", "")
                if title and url:
                    headlines_html += f"""
                    <div class="headline">
                        <a href="{url}" target="_blank">{title}</a>
                        <span class="source">{source}</span>
                    </div>
                    """
            
            token_rows += f"""
            <tr>
                <td><strong>{token}</strong></td>
                <td style="background-color: {sentiment_color};">{data["sentiment"]:.2f}</td>
                <td>{data["confidence"]:.2f}</td>
                <td>{data["news_count"]}</td>
                <td>{data.get("trend_7d", 0):.3f} {trend_icon}</td>
                <td>{headlines_html}</td>
            </tr>
            """
        
        # Summary section
        summary_html = f"""
        <div class="summary-box">
            <h3>Summary</h3>
            <p><strong>Analyzed tokens:</strong> {report["summary"]["token_count"]}</p>
            <p><strong>Tokens with news:</strong> {report["summary"]["tokens_with_news"]}</p>
            <p><strong>Average sentiment:</strong> {report["summary"].get("average_sentiment", 0):.2f}</p>
            <p><strong>Most positive token:</strong> {report["summary"].get("most_positive", "N/A")}</p>
            <p><strong>Most negative token:</strong> {report["summary"].get("most_negative", "N/A")}</p>
            <p><strong>Most news coverage:</strong> {report["summary"].get("most_news", "N/A")}</p>
        </div>
        """
        
        # Visualization section
        viz_html = ""
        for path in relative_viz_paths:
            viz_html += f"""
            <div class="viz-container">
                <img src="{path}" alt="Sentiment Visualization" class="viz-image">
            </div>
            """
        
        # Build complete HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>AutoTrader Crypto Sentiment Dashboard</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f4f6f9;
                    color: #333;
                }}
                
                .dashboard {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                    padding: 20px;
                }}
                
                h1 {{
                    color: #2c3e50;
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 15px;
                }}
                
                h2 {{
                    color: #3498db;
                    margin-top: 30px;
                }}
                
                .sentiment-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                
                .sentiment-table th, .sentiment-table td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                
                .sentiment-table th {{
                    background-color: #f8f9fa;
                }}
                
                .sentiment-table tr:hover {{
                    background-color: #f5f5f5;
                }}
                
                .headline {{
                    margin-bottom: 5px;
                }}
                
                .source {{
                    color: #777;
                    font-size: 0.8em;
                }}
                
                .summary-box {{
                    background-color: #f8f9fa;
                    border-left: 4px solid #3498db;
                    padding: 15px;
                    margin-top: 20px;
                    border-radius: 0 4px 4px 0;
                }}
                
                .viz-container {{
                    margin-top: 30px;
                    text-align: center;
                }}
                
                .viz-image {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 4px;
                    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
                }}
                
                .footer {{
                    margin-top: 40px;
                    text-align: center;
                    color: #777;
                    font-size: 0.9em;
                    padding-top: 20px;
                    border-top: 1px solid #eee;
                }}
            </style>
        </head>
        <body>
            <div class="dashboard">
                <h1>AutoTrader Crypto Sentiment Dashboard</h1>
                <p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                
                {summary_html}
                
                <h2>Token Sentiment Analysis</h2>
                <table class="sentiment-table">
                    <thead>
                        <tr>
                            <th>Token</th>
                            <th>Sentiment</th>
                            <th>Confidence</th>
                            <th>News Count</th>
                            <th>7-Day Trend</th>
                            <th>Latest Headlines</th>
                        </tr>
                    </thead>
                    <tbody>
                        {token_rows}
                    </tbody>
                </table>
                
                <h2>Visualizations</h2>
                {viz_html}
                
                <div class="footer">
                    <p>CrisisCore AutoTrader - News Sentiment Module</p>
                    <p>Data sources: CryptoPanic, CoinDesk</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _get_sentiment_color(self, sentiment: float) -> str:
        """
        Get a color for a sentiment score.
        
        Args:
            sentiment: Sentiment score (0-1)
            
        Returns:
            Color hex code
        """
        if sentiment >= 0.7:
            return "#a8f0a8"  # Green
        elif sentiment >= 0.55:
            return "#d6f5d6"  # Light green
        elif sentiment >= 0.45:
            return "#f5f5f5"  # Neutral
        elif sentiment >= 0.3:
            return "#f5d6d6"  # Light red
        else:
            return "#f0a8a8"  # Red