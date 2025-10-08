"""Test enhanced Groq AI capabilities with improved prompts and model"""
import os
import sys
from pathlib import Path

# API keys must be set via environment variables
# Example: export GROQ_API_KEY="your-key-here"
if not os.environ.get('GROQ_API_KEY'):
    print("ERROR: GROQ_API_KEY not set. Please set it as an environment variable.")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))

from src.core.narrative import NarrativeAnalyzer

print("=" * 80)
print("ENHANCED GROQ AI - CAPABILITY TEST")
print("=" * 80)
print()

# Create analyzer with enhanced settings
analyzer = NarrativeAnalyzer()

print("[1/3] Testing Basic Narratives")
print("-" * 80)
basic_narratives = [
    "Chainlink expands oracle services to 5 new blockchains",
    "LINK token holders approve governance proposal",
]
result = analyzer.analyze(basic_narratives)
print(f"Sentiment Score: {result.sentiment_score:.3f}")
print(f"Momentum: {result.momentum:.3f}")
print(f"Themes: {', '.join(result.themes[:3])}")
print(f"Meme Momentum: {result.meme_momentum:.3f}")
print(f"Volatility: {result.volatility:.3f}")
print()

print("[2/3] Testing Bullish Narratives")
print("-" * 80)
bullish_narratives = [
    "Uniswap V4 launches with revolutionary hook system",
    "TVL surges 150% following major institutional partnership announcement",
    "Community celebrates successful mainnet deployment with zero downtime",
    "Breaking: Fortune 500 company adopts protocol for treasury management",
    "Developer activity at all-time high with 500+ commits this month",
]
result = analyzer.analyze(bullish_narratives)
print(f"Sentiment Score: {result.sentiment_score:.3f}")
print(f"Momentum: {result.momentum:.3f}")
print(f"Themes: {', '.join(result.themes[:5])}")
print(f"Meme Momentum: {result.meme_momentum:.3f}")
print(f"Volatility: {result.volatility:.3f}")
print()

print("[3/3] Testing Mixed/Risk Narratives")
print("-" * 80)
risk_narratives = [
    "Token unlock event scheduled for next month raises concerns",
    "SEC investigation announced targeting governance token",
    "Smart contract vulnerability discovered in older version",
    "Despite exploit, team announces compensation plan",
    "Community debates fork proposal amid controversy",
]
result = analyzer.analyze(risk_narratives)
print(f"Sentiment Score: {result.sentiment_score:.3f}")
print(f"Momentum: {result.momentum:.3f}")
print(f"Themes: {', '.join(result.themes[:5])}")
print(f"Meme Momentum: {result.meme_momentum:.3f}")
print(f"Volatility: {result.volatility:.3f}")
print()

print("=" * 80)
print("ENHANCED MODEL INFO")
print("=" * 80)
print(f"Model: {analyzer._model}")
print(f"Temperature: {analyzer._temperature}")
print(f"Max Tokens: {analyzer._max_tokens}")
print(f"LLM Enabled: {analyzer._use_llm}")
print()

if analyzer._use_llm:
    print("AI ENHANCEMENTS ACTIVE:")
    print("  - Upgraded to llama-3.3-70b-versatile (more capable model)")
    print("  - Reduced temperature (0.2) for more focused analysis")
    print("  - Doubled max_tokens (1200) for richer insights")
    print("  - Enhanced prompt with expert instructions")
    print("  - Expanded keyword dictionaries (40+ positive, 30+ risk terms)")
    print("  - Added crypto-specific terminology (DeFi, L2, TVL, etc.)")
else:
    print("WARNING: Running in fallback mode (LLM not available)")

print()
print("=" * 80)
print("Test complete! The AI should now provide:")
print("  - More accurate sentiment analysis")
print("  - Richer thematic extraction")
print("  - Better risk detection")
print("  - Deeper market context understanding")
print("  - More nuanced scoring")
print("=" * 80)
