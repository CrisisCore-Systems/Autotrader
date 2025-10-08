import os
import sys
import argparse
import logging
from datetime import datetime
import webbrowser
from typing import List

# Ensure the module is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.sentiment_dashboard import NewsSentimentDashboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def setup_argparse():
    """Set up command-line argument parsing."""
    parser = argparse.ArgumentParser(description='Generate news sentiment dashboard for crypto tokens.')
    parser.add_argument('--tokens', type=str, 
                        default="BTC,ETH,SOL,LINK,UNI,AAVE,PEPE,MATIC,DOT,SHIB,AVAX,DOGE",
                        help='Comma-separated list of tokens to analyze')
    parser.add_argument('--days', type=int, default=3,
                        help='Number of days of news to analyze')
    parser.add_argument('--output-dir', type=str, default="",
                        help='Directory for output files')
    parser.add_argument('--open-browser', action='store_true',
                        help='Open dashboard in browser when ready')
    parser.add_argument('--force-refresh', action='store_true',
                        help='Force refresh of news cache')
    
    return parser.parse_args()

def parse_token_list(token_string: str) -> List[str]:
    """
    Parse a comma-separated list of tokens.
    
    Args:
        token_string: Comma-separated list of tokens
        
    Returns:
        List of token symbols
    """
    tokens = [token.strip().upper() for token in token_string.split(',') if token.strip()]
    return tokens

def main():
    """Main function."""
    args = setup_argparse()
    
    # Parse token list
    tokens = parse_token_list(args.tokens)
    if not tokens:
        logger.error("No tokens specified. Use --tokens to specify tokens.")
        return 1
    
    logger.info(f"Analyzing sentiment for {len(tokens)} tokens: {', '.join(tokens)}")
    logger.info(f"Days of news to analyze: {args.days}")
    
    try:
        # Create dashboard
        output_dir = args.output_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            "../artifacts/dashboard"
        )
        
        dashboard = NewsSentimentDashboard(output_dir=output_dir)
        
        # Generate report
        logger.info("Generating sentiment report...")
        report = dashboard.generate_sentiment_report(tokens, days=args.days)
        
        # Generate HTML dashboard
        logger.info("Generating HTML dashboard...")
        dashboard_path = dashboard.generate_html_dashboard(report)
        
        if dashboard_path:
            logger.info(f"Dashboard generated: {dashboard_path}")
            
            # Open in browser if requested
            if args.open_browser:
                logger.info("Opening dashboard in browser...")
                webbrowser.open(f"file://{os.path.abspath(dashboard_path)}")
                
            return 0
        else:
            logger.error("Failed to generate dashboard.")
            return 1
            
    except Exception as e:
        logger.exception(f"Error generating dashboard: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())