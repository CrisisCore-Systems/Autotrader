#!/usr/bin/env python
"""
Example: Using Correlation Analysis with Market Regime Classification

This script demonstrates:
1. Loading multi-symbol feature data
2. Computing rolling correlations
3. Classifying regimes with correlation refinement
4. Analyzing correlation-based trading opportunities
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import numpy as np

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from scripts.classify_market_regime import (
    classify_regimes,
    classify_correlation_regimes,
    compute_rolling_correlations,
    regime_summary,
    print_regime_table,
)


def example_basic_classification():
    """Load single symbol and classify regimes."""
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Single-Symbol Regime Classification")
    print("="*80)
    
    feature_dir = Path("data/crypto/features")
    
    # Find first available feature file
    files = sorted(feature_dir.glob("kraken_*_features.parquet"))
    if not files:
        print("No feature files found. Skipping example 1.")
        return None
    
    file = files[0]
    print(f"\nLoading: {file.name}")
    df = pd.read_parquet(file)
    print(f"Loaded {len(df):,} bars")
    
    # Classify regimes
    classified = classify_regimes(df, window=96)
    
    # Extract symbol name
    symbol = df["symbol"].iloc[0] if "symbol" in df.columns else file.stem
    
    # Generate summary
    summary = regime_summary(classified, symbol=symbol)
    
    print(f"\nRegime Distribution for {symbol}:")
    dist = summary["distribution"]
    for regime, counts in dist.items():
        print(f"  {regime:20} {counts['count']:6,} bars ({counts['pct']:5.1f}%)")
    
    print(f"\nCurrent Regime: {summary['current_regime']}")
    print(f"Last Parkinson Vol (annualized): {summary['last_park_vol_ann']:.4f}")
    print(f"Last Sign Autocorrelation: {summary['last_sign_autocorr']:.4f}")
    
    return classified


def example_correlation_analysis():
    """Load multiple symbols and compute correlations."""
    print("\n" + "="*80)
    print("EXAMPLE 2: Multi-Symbol Correlation Analysis")
    print("="*80)
    
    feature_dir = Path("data/crypto/features")
    
    # Find first 3 available feature files
    files = sorted(feature_dir.glob("kraken_*_features.parquet"))[:3]
    if len(files) < 2:
        print("Need at least 2 feature files for correlation analysis. Skipping example 2.")
        return None
    
    print(f"\nLoading {len(files)} symbols for correlation analysis...")
    
    returns_dict = {}
    dfs = {}
    for file in files:
        df = pd.read_parquet(file)
        if df.empty or "ret_1" not in df.columns:
            continue
        
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else file.stem.replace("kraken_", "").upper()
        returns_dict[symbol] = df["ret_1"].copy()
        dfs[symbol] = df
        print(f"  {symbol}: {len(df):,} bars")
    
    if len(returns_dict) < 2:
        print("Insufficient data for correlation analysis.")
        return None
    
    # Compute rolling correlations
    print("\nComputing rolling correlations (window=96)...")
    rolling_corr = compute_rolling_correlations(returns_dict, window=96)
    
    print(f"Computed correlations for {len(rolling_corr)} symbol pairs:")
    for (sym_a, sym_b), corr_series in rolling_corr.items():
        if not corr_series.empty:
            last_corr = corr_series.iloc[-1]
            mean_corr = corr_series.mean()
            print(f"  {sym_a:15} ↔ {sym_b:15}  latest={last_corr:+.3f}  mean={mean_corr:+.3f}")
    
    return dfs, rolling_corr


def example_correlation_regimes(dfs, rolling_corr):
    """Classify each symbol with correlation-based regime refinement."""
    if dfs is None or rolling_corr is None:
        print("Skipping example 3 (requires correlation data from example 2).")
        return None
    
    print("\n" + "="*80)
    print("EXAMPLE 3: Correlation-Based Regime Refinement")
    print("="*80)
    
    summaries = []
    
    for symbol, df in dfs.items():
        print(f"\nProcessing {symbol}...")
        
        # Classify base regimes
        classified = classify_regimes(df, window=96)
        
        # Add correlation-based refinement
        classified_with_corr = classify_correlation_regimes(
            classified,
            rolling_corr,
            symbol,
            corr_threshold_high=0.7,
            corr_threshold_low=0.3,
        )
        
        # Generate summary
        summary = regime_summary(classified_with_corr, symbol=symbol)
        summaries.append(summary)
        
        # Display results
        print(f"  Current Regime: {summary['current_regime']}")
        print(f"  Mean Correlation: {summary['last_mean_correlation']:+.4f}")
        print(f"  Correlation Regime: {summary['current_corr_regime']}")
        
        if "corr_distribution" in summary:
            corr_dist = summary["corr_distribution"]
            print(f"  Correlation Distribution:")
            for regime, counts in corr_dist.items():
                print(f"    {regime:25} {counts['count']:6,} bars ({counts['pct']:5.1f}%)")
    
    # Print summary table
    if summaries:
        print_regime_table(summaries)
    
    return summaries


def example_correlation_trading():
    """Analyze correlation-based trading signals."""
    print("\n" + "="*80)
    print("EXAMPLE 4: Correlation-Based Trading Signals")
    print("="*80)
    
    feature_dir = Path("data/crypto/features")
    files = sorted(feature_dir.glob("kraken_*_features.parquet"))[:3]
    
    if len(files) < 2:
        print("Need at least 2 symbols. Skipping example 4.")
        return
    
    returns_dict = {}
    dfs = {}
    for file in files:
        df = pd.read_parquet(file)
        if df.empty or "ret_1" not in df.columns:
            continue
        
        symbol = df["symbol"].iloc[0] if "symbol" in df.columns else file.stem.replace("kraken_", "").upper()
        returns_dict[symbol] = df["ret_1"].copy()
        dfs[symbol] = df
    
    if len(returns_dict) < 2:
        return
    
    # Compute correlations
    rolling_corr = compute_rolling_correlations(returns_dict, window=96)
    
    print("\nCorrelation-Based Trading Opportunities:")
    print("-" * 80)
    
    for symbol, df in dfs.items():
        classified = classify_regimes(df, window=96)
        classified = classify_correlation_regimes(classified, rolling_corr, symbol)
        
        last_rows = classified.tail(100)  # Last 100 bars
        
        # Count different scenarios
        high_corr_trend = ((last_rows["regime"] == "momentum_trend") & 
                           (last_rows["corr_regime"] == "high_correlation_sync")).sum()
        decorr_revert = ((last_rows["regime"] == "mean_reversion") & 
                         (last_rows["corr_regime"] == "decorrelation_risk")).sum()
        decorr_trend = ((last_rows["regime"] == "momentum_trend") & 
                        (last_rows["corr_regime"] == "decorrelation_risk")).sum()
        
        print(f"\n{symbol}:")
        print(f"  High Correlation + Trending:    {high_corr_trend:3} bars")
        print(f"  Decorrelation + Mean Reversion: {decorr_revert:3} bars")
        print(f"  Decorrelation + Trending:       {decorr_trend:3} bars")
        
        if decorr_trend > 5:
            print(f"  → SIGNAL: Potential uncorrelated breakout opportunity")
        if decorr_revert > 5:
            print(f"  → SIGNAL: Potential uncorrelated mean-reversion opportunity")


def main():
    """Run all examples."""
    print("\n" + "="*80)
    print("Market Regime Classification with Correlation Analysis — Examples")
    print("="*80)
    
    try:
        # Example 1: Basic classification
        example_basic_classification()
        
        # Examples 2-3: Correlation analysis
        result = example_correlation_analysis()
        if result is not None:
            dfs, rolling_corr = result
            example_correlation_regimes(dfs, rolling_corr)
        
        # Example 4: Trading signals
        example_correlation_trading()
        
    except Exception as exc:
        print(f"\nError during examples: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("\n" + "="*80)
    print("Examples completed!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
