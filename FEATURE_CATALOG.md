# AutoTrader Feature Catalog

**Version:** 1.0.0  
**Last Updated:** October 22, 2025  
**Status:** Production

---

## Table of Contents

1. [Overview](#overview)
2. [Feature Categories](#feature-categories)
3. [Hidden-Gem Scanner Features](#hidden-gem-scanner-features)
4. [BounceHunter/PennyHunter Features](#bouncehunterpennyhunter-features)
5. [Cross-Exchange Features](#cross-exchange-features)
6. [Microstructure Features](#microstructure-features)
7. [Feature Dependencies](#feature-dependencies)
8. [Data Contracts](#data-contracts)
9. [Feature Validation Rules](#feature-validation-rules)

---

## Overview

This document provides a canonical inventory of all features used across AutoTrader's trading strategies. Each feature includes:

- **Name**: Feature identifier
- **Type**: Data type (numeric, categorical, boolean, timestamp, vector)
- **Category**: Functional grouping
- **Description**: What the feature measures
- **Source**: Data provider or computation
- **Unit**: Measurement unit (if applicable)
- **Range**: Valid value range
- **Nullable**: Whether null values are permitted
- **Version**: Feature version for backward compatibility

---

## Feature Categories

| Category | Description | Feature Count |
|----------|-------------|---------------|
| **Market** | Price, volume, market capitalization | 15 |
| **Liquidity** | Order book depth, pool liquidity, spreads | 12 |
| **Order Flow** | CEX/DEX flow metrics, imbalances | 18 |
| **Derivatives** | Funding rates, open interest, liquidations | 10 |
| **Sentiment** | Twitter, news, social media sentiment | 14 |
| **On-Chain** | Holder distribution, transaction activity | 16 |
| **Technical** | Indicators, patterns, momentum | 22 |
| **Quality** | Data recency, completeness, confidence | 8 |
| **Scoring** | GemScore, BCS, confidence metrics | 12 |

**Total Features**: 127

---

## Hidden-Gem Scanner Features

### Market Features

#### `price_usd`
- **Type**: Numeric
- **Category**: Market
- **Description**: Current price in USD
- **Source**: CoinGecko, DefiLlama
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `market_cap_usd`
- **Type**: Numeric
- **Category**: Market
- **Description**: Fully diluted market capitalization
- **Source**: CoinGecko
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `volume_24h_usd`
- **Type**: Numeric
- **Category**: Market
- **Description**: Trading volume over last 24 hours
- **Source**: CoinGecko, Dexscreener
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `price_change_24h_pct`
- **Type**: Numeric
- **Category**: Market
- **Description**: Percentage price change over 24 hours
- **Source**: CoinGecko
- **Unit**: Percentage
- **Range**: [-100.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `price_change_7d_pct`
- **Type**: Numeric
- **Category**: Market
- **Description**: Percentage price change over 7 days
- **Source**: CoinGecko
- **Unit**: Percentage
- **Range**: [-100.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `price_ath_usd`
- **Type**: Numeric
- **Category**: Market
- **Description**: All-time high price
- **Source**: CoinGecko
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: Yes
- **Version**: 1.0.0

#### `price_ath_distance_pct`
- **Type**: Numeric
- **Category**: Market
- **Description**: Distance from all-time high as percentage
- **Source**: Computed from price and price_ath
- **Unit**: Percentage
- **Range**: [-100.0, 0.0]
- **Nullable**: Yes
- **Version**: 1.0.0

### Liquidity Features

#### `liquidity_pool_usd`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Total DEX liquidity pool value
- **Source**: Dexscreener, DefiLlama
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `liquidity_depth_usd`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Order book depth (sum of bids/asks within 2% of mid)
- **Source**: CEX APIs, Dexscreener
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `bid_ask_spread_bps`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Bid-ask spread in basis points
- **Source**: CEX/DEX order books
- **Unit**: Basis Points
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `LiquidityDepth`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Normalized liquidity depth score [0, 1]
- **Source**: Computed from liquidity_depth_usd
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `min(liquidity_depth_usd / 1_000_000, 1.0)`

### Order Flow Features

#### `cex_orderflow_imbalance`
- **Type**: Numeric
- **Category**: Order Flow
- **Description**: Imbalance between buy and sell orders on CEX
- **Source**: CEX order books (Binance, Coinbase)
- **Unit**: None (ratio)
- **Range**: [-1.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(buy_volume - sell_volume) / (buy_volume + sell_volume)`

#### `dex_orderflow_imbalance`
- **Type**: Numeric
- **Category**: Order Flow
- **Description**: Imbalance between buy and sell orders on DEX
- **Source**: Dexscreener
- **Unit**: None (ratio)
- **Range**: [-1.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `orderflow_divergence`
- **Type**: Numeric
- **Category**: Order Flow
- **Description**: Difference between CEX and DEX order flow
- **Source**: Computed from cex_orderflow_imbalance and dex_orderflow_imbalance
- **Unit**: None (difference)
- **Range**: [-2.0, 2.0]
- **Nullable**: No
- **Version**: 1.0.0

### Derivatives Features

#### `funding_rate_pct`
- **Type**: Numeric
- **Category**: Derivatives
- **Description**: Perpetual futures funding rate (8-hour)
- **Source**: Binance, Bybit, OKX
- **Unit**: Percentage
- **Range**: [-5.0, 5.0]
- **Nullable**: Yes
- **Version**: 1.0.0

#### `open_interest_usd`
- **Type**: Numeric
- **Category**: Derivatives
- **Description**: Total open interest in futures contracts
- **Source**: Binance, Bybit
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: Yes
- **Version**: 1.0.0

#### `open_interest_change_24h_pct`
- **Type**: Numeric
- **Category**: Derivatives
- **Description**: Change in open interest over 24 hours
- **Source**: Computed from open_interest_usd
- **Unit**: Percentage
- **Range**: [-100.0, ∞)
- **Nullable**: Yes
- **Version**: 1.0.0

### Sentiment Features

#### `twitter_sentiment_score`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Aggregated Twitter sentiment [-1, 1]
- **Source**: Twitter API, sentiment model
- **Unit**: None (score)
- **Range**: [-1.0, 1.0]
- **Nullable**: Yes
- **Version**: 1.0.0

#### `twitter_volume_24h`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Number of tweets mentioning token in 24h
- **Source**: Twitter API
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: Yes
- **Version**: 1.0.0

#### `news_sentiment_score`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Aggregated news sentiment [-1, 1]
- **Source**: RSS feeds, news APIs, LLM analysis
- **Unit**: None (score)
- **Range**: [-1.0, 1.0]
- **Nullable**: Yes
- **Version**: 1.0.0

#### `SentimentScore`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Combined sentiment score [0, 1]
- **Source**: Weighted average of twitter and news sentiment
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(twitter_sentiment_score * 0.6 + news_sentiment_score * 0.4 + 1) / 2`

### On-Chain Features

#### `holder_count`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Number of unique token holders
- **Source**: Etherscan, Blockscout
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `holder_concentration_top10_pct`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Percentage of supply held by top 10 holders
- **Source**: Etherscan, on-chain analysis
- **Unit**: Percentage
- **Range**: [0.0, 100.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `transaction_count_24h`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Number of transactions in last 24 hours
- **Source**: Etherscan, RPC
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `unique_traders_24h`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Number of unique addresses trading in 24h
- **Source**: On-chain analysis
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `OnchainActivity`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Normalized on-chain activity score [0, 1]
- **Source**: Computed from transaction and holder metrics
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `weighted_avg(transaction_count, unique_traders, holder_growth)`

### Technical Features

#### `rsi_14`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Relative Strength Index (14 periods)
- **Source**: Computed from price data
- **Unit**: None (indicator)
- **Range**: [0.0, 100.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `macd`
- **Type**: Numeric
- **Category**: Technical
- **Description**: MACD line (12, 26, 9)
- **Source**: Computed from price data
- **Unit**: None (indicator)
- **Range**: (-∞, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `bollinger_band_width`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Width of Bollinger Bands (20, 2)
- **Source**: Computed from price data
- **Unit**: None (ratio)
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `AccumulationScore`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Accumulation/distribution score [0, 1]
- **Source**: Computed from volume and price patterns
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `analyze_volume_price_divergence()`

### Tokenomics Features

#### `total_supply`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Total token supply
- **Source**: Contract, CoinGecko
- **Unit**: Tokens
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `circulating_supply`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Circulating token supply
- **Source**: CoinGecko
- **Unit**: Tokens
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `circulating_supply_pct`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Percentage of total supply in circulation
- **Source**: Computed from circulating_supply / total_supply
- **Unit**: Percentage
- **Range**: [0.0, 100.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `upcoming_unlock_pct`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Percentage of supply unlocking in next 30 days
- **Source**: Tokenomics schedule, manual data
- **Unit**: Percentage
- **Range**: [0.0, 100.0]
- **Nullable**: Yes
- **Version**: 1.0.0

#### `TokenomicsRisk`
- **Type**: Numeric
- **Category**: On-Chain
- **Description**: Tokenomics risk score [0, 1], 1 = low risk
- **Source**: Computed from supply metrics and unlocks
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `1.0 - (upcoming_unlock_pct / 100 * 0.5 + (1 - circulating_pct) * 0.5)`

### Narrative Features

#### `narrative_tags`
- **Type**: Vector (categorical)
- **Category**: Sentiment
- **Description**: Associated narrative categories (DeFi, AI, GameFi, etc.)
- **Source**: Manual tagging, LLM classification
- **Unit**: None (categories)
- **Range**: N/A
- **Nullable**: Yes
- **Version**: 1.0.0

#### `narrative_momentum_score`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Strength of narrative momentum [0, 1]
- **Source**: Twitter volume, news mentions, social trends
- **Unit**: None (score)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `NarrativeMomentum`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Normalized narrative momentum [0, 1]
- **Source**: Alias for narrative_momentum_score
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0

### Safety Features

#### `contract_verified`
- **Type**: Boolean
- **Category**: Quality
- **Description**: Whether contract source code is verified
- **Source**: Etherscan
- **Unit**: None (boolean)
- **Range**: {True, False}
- **Nullable**: No
- **Version**: 1.0.0

#### `honeypot_detected`
- **Type**: Boolean
- **Category**: Quality
- **Description**: Whether contract is flagged as honeypot
- **Source**: Honeypot detection API
- **Unit**: None (boolean)
- **Range**: {True, False}
- **Nullable**: No
- **Version**: 1.0.0

#### `owner_can_mint`
- **Type**: Boolean
- **Category**: Quality
- **Description**: Whether owner can mint additional tokens
- **Source**: Contract analysis
- **Unit**: None (boolean)
- **Range**: {True, False}
- **Nullable**: No
- **Version**: 1.0.0

#### `ContractSafety`
- **Type**: Numeric
- **Category**: Quality
- **Description**: Contract safety score [0, 1]
- **Source**: Computed from safety checks
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `evaluate_contract(findings, severity)`

### Community Features

#### `github_stars`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Number of GitHub stars for project repo
- **Source**: GitHub API
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: Yes
- **Version**: 1.0.0

#### `github_commit_count_30d`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Number of commits in last 30 days
- **Source**: GitHub API
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: Yes
- **Version**: 1.0.0

#### `telegram_member_count`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Number of Telegram group members
- **Source**: Telegram API
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: Yes
- **Version**: 1.0.0

#### `CommunityGrowth`
- **Type**: Numeric
- **Category**: Sentiment
- **Description**: Community growth score [0, 1]
- **Source**: Computed from GitHub, Telegram, Twitter metrics
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0

### Quality Features

#### `Recency`
- **Type**: Numeric
- **Category**: Quality
- **Description**: Data freshness score [0, 1]
- **Source**: Computed from data timestamps
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `exp(-age_seconds / 3600)`

#### `DataCompleteness`
- **Type**: Numeric
- **Category**: Quality
- **Description**: Percentage of required features populated
- **Source**: Computed from feature availability
- **Unit**: None (normalized)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `non_null_features / total_features`

### Scoring Features

#### `GemScore`
- **Type**: Numeric
- **Category**: Scoring
- **Description**: Overall gem quality score [0, 100]
- **Source**: Weighted sum of feature scores
- **Unit**: None (score)
- **Range**: [0.0, 100.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: See [GemScore Calculation](#gemscore-calculation)

#### `Confidence`
- **Type**: Numeric
- **Category**: Scoring
- **Description**: Confidence in GemScore [0, 100]
- **Source**: Computed from Recency and DataCompleteness
- **Unit**: None (score)
- **Range**: [0.0, 100.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `0.5 * Recency + 0.5 * DataCompleteness`

---

## BounceHunter/PennyHunter Features

### Price & Volume Features

#### `close`
- **Type**: Numeric
- **Category**: Market
- **Description**: Daily closing price
- **Source**: yfinance
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `volume`
- **Type**: Numeric
- **Category**: Market
- **Description**: Daily trading volume (shares)
- **Source**: yfinance
- **Unit**: Shares
- **Range**: [0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `adv_usd`
- **Type**: Numeric
- **Category**: Market
- **Description**: Average daily volume in USD (20-day)
- **Source**: Computed from volume and price
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `mean(volume * close, 20 days)`

### Mean-Reversion Features

#### `z5`
- **Type**: Numeric
- **Category**: Technical
- **Description**: 5-day z-score of price returns
- **Source**: Computed from close prices
- **Unit**: None (z-score)
- **Range**: (-∞, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(close - mean(close, 5)) / std(close, 5)`

#### `rsi2`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Relative Strength Index (2 periods)
- **Source**: Computed from close prices
- **Unit**: None (indicator)
- **Range**: [0.0, 100.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `bb_dev`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Bollinger Band deviation (price distance from lower band)
- **Source**: Computed from close prices
- **Unit**: None (standard deviations)
- **Range**: (-∞, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(close - bb_lower) / bb_width`

#### `dist_200`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Distance from 200-day moving average
- **Source**: Computed from close prices
- **Unit**: Percentage
- **Range**: (-∞, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(close / ma_200 - 1) * 100`

#### `trend_63`
- **Type**: Numeric
- **Category**: Technical
- **Description**: 63-day (quarter) trend slope
- **Source**: Linear regression on close prices
- **Unit**: None (slope)
- **Range**: (-∞, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `gap_dn`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Gap down percentage (open vs. prior close)
- **Source**: Computed from open and prior close
- **Unit**: Percentage
- **Range**: [-100.0, 0.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(open / prior_close - 1) * 100`

### Market Regime Features

#### `vix`
- **Type**: Numeric
- **Category**: Market
- **Description**: CBOE Volatility Index
- **Source**: yfinance (^VIX)
- **Unit**: None (index)
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `vix_regime`
- **Type**: Categorical
- **Category**: Market
- **Description**: VIX regime classification
- **Source**: Computed from vix percentile
- **Unit**: None (category)
- **Range**: {0: normal, 1: elevated, 2: high}
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `0 if vix_pct < 0.6 else (1 if vix_pct < 0.8 else 2)`

#### `spy_dist_200dma`
- **Type**: Numeric
- **Category**: Market
- **Description**: SPY distance from 200-day moving average
- **Source**: Computed from SPY close prices
- **Unit**: Percentage
- **Range**: (-∞, ∞)
- **Nullable**: No
- **Version**: 1.0.0

### Probability & Confidence Features

#### `probability`
- **Type**: Numeric
- **Category**: Scoring
- **Description**: Probability of mean-reversion success
- **Source**: Calibrated classifier model
- **Unit**: None (probability)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `bcs`
- **Type**: Numeric
- **Category**: Scoring
- **Description**: BounceHunter Confidence Score
- **Source**: Computed from probability and filters
- **Unit**: None (score)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `probability * filter_adjustments`

### Entry/Exit Features

#### `entry`
- **Type**: Numeric
- **Category**: Trading
- **Description**: Suggested entry price
- **Source**: Computed from current close
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `stop`
- **Type**: Numeric
- **Category**: Trading
- **Description**: Stop loss price (-8% from entry)
- **Source**: Computed from entry
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `entry * 0.92`

#### `target`
- **Type**: Numeric
- **Category**: Trading
- **Description**: Profit target price (+6% from entry)
- **Source**: Computed from entry
- **Unit**: USD
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `entry * 1.06`

### Filter Features

#### `liquidity_delta_pct`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Recent volume vs. 20-day average
- **Source**: Computed from volume history
- **Unit**: Percentage
- **Range**: [-100.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(recent_volume / avg_volume_20d - 1) * 100`

#### `effective_slippage_bps`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Expected slippage in basis points
- **Source**: Computed from ADV and position size
- **Unit**: Basis Points
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `sqrt(position_size / adv_usd) * market_impact_coeff`

#### `runway_days`
- **Type**: Numeric
- **Category**: Trading
- **Description**: Days of cash runway at current risk per trade
- **Source**: Computed from account balance and risk per trade
- **Unit**: Days
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `account_balance / (risk_pct * account_balance)`

#### `sector_exposure_count`
- **Type**: Numeric
- **Category**: Trading
- **Description**: Number of open positions in same sector
- **Source**: Computed from current positions
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `volume_fade_detected`
- **Type**: Boolean
- **Category**: Technical
- **Description**: Whether declining volume trend detected
- **Source**: Linear regression on volume
- **Unit**: None (boolean)
- **Range**: {True, False}
- **Nullable**: No
- **Version**: 1.0.0

---

## Cross-Exchange Features

### Price Dislocation Features

#### `price_dispersion`
- **Type**: Numeric
- **Category**: Market
- **Description**: Coefficient of variation of prices across exchanges
- **Source**: Computed from multi-exchange price data
- **Unit**: None (coefficient)
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `std(prices) / mean(prices)`

#### `max_price_spread_bps`
- **Type**: Numeric
- **Category**: Market
- **Description**: Maximum price spread between exchanges
- **Source**: Computed from multi-exchange price data
- **Unit**: Basis Points
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `(max(prices) - min(prices)) / mean(prices) * 10000`

#### `price_entropy`
- **Type**: Numeric
- **Category**: Market
- **Description**: Shannon entropy of price distribution
- **Source**: Computed from price histogram
- **Unit**: None (bits)
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

### Arbitrage Features

#### `best_arb_opportunity_bps`
- **Type**: Numeric
- **Category**: Market
- **Description**: Best arbitrage profit after fees
- **Source**: Computed from order books and fees
- **Unit**: Basis Points
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `arb_opportunity_count`
- **Type**: Numeric
- **Category**: Market
- **Description**: Number of profitable arbitrage opportunities
- **Source**: Computed from multi-exchange order books
- **Unit**: Count
- **Range**: [0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

### Volume-Weighted Features

#### `vw_price_dispersion`
- **Type**: Numeric
- **Category**: Market
- **Description**: Volume-weighted price dispersion
- **Source**: Computed from prices and volumes
- **Unit**: None (coefficient)
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `volume_concentration`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Herfindahl index of volume distribution
- **Source**: Computed from exchange volumes
- **Unit**: None (index)
- **Range**: [0.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `sum((volume_i / total_volume)^2)`

### Temporal Features

#### `price_sync_correlation`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Correlation of price movements across exchanges
- **Source**: Computed from price time series
- **Unit**: None (correlation)
- **Range**: [-1.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0

#### `lead_lag_coefficient`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Strength of lead-lag relationship
- **Source**: Cross-correlation analysis
- **Unit**: None (coefficient)
- **Range**: [-1.0, 1.0]
- **Nullable**: No
- **Version**: 1.0.0

---

## Microstructure Features

### Order Book Features

#### `depth_imbalance_ratio`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Ratio of bid depth to ask depth
- **Source**: Computed from order book
- **Unit**: None (ratio)
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0
- **Computation**: `bid_depth / ask_depth`

#### `consolidated_spread_bps`
- **Type**: Numeric
- **Category**: Liquidity
- **Description**: Weighted average spread across exchanges
- **Source**: Computed from multi-exchange order books
- **Unit**: Basis Points
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

### Volatility Features

#### `cross_exchange_vol_ratio`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Ratio of highest to lowest volatility
- **Source**: Computed from price volatilities
- **Unit**: None (ratio)
- **Range**: [1.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

#### `vol_dispersion`
- **Type**: Numeric
- **Category**: Technical
- **Description**: Standard deviation of volatilities
- **Source**: Computed from exchange volatilities
- **Unit**: None (standard deviation)
- **Range**: [0.0, ∞)
- **Nullable**: No
- **Version**: 1.0.0

---

## Feature Dependencies

### Dependency Graph

```
Raw Data Sources
    │
    ├─→ Market Data (price, volume, market_cap)
    │       ├─→ Technical Indicators (rsi, macd, z5)
    │       ├─→ Mean-Reversion Features (bb_dev, dist_200)
    │       └─→ Price Derivatives (price_change_24h_pct)
    │
    ├─→ Order Book Data (bids, asks)
    │       ├─→ Liquidity Features (liquidity_depth, bid_ask_spread)
    │       ├─→ Order Flow Features (orderflow_imbalance)
    │       └─→ Microstructure Features (depth_imbalance_ratio)
    │
    ├─→ On-Chain Data (transactions, holders)
    │       ├─→ Activity Features (transaction_count, unique_traders)
    │       └─→ Tokenomics Features (holder_concentration)
    │
    ├─→ Sentiment Data (tweets, news)
    │       ├─→ Sentiment Scores (twitter_sentiment, news_sentiment)
    │       └─→ Narrative Features (narrative_momentum)
    │
    └─→ Derivatives Data (funding, OI)
            └─→ Derivatives Features (funding_rate, open_interest_change)

Normalized Features
    │
    ├─→ AccumulationScore (from volume/price patterns)
    ├─→ OnchainActivity (from on-chain metrics)
    ├─→ LiquidityDepth (from liquidity metrics)
    ├─→ TokenomicsRisk (from supply metrics)
    ├─→ ContractSafety (from safety checks)
    ├─→ NarrativeMomentum (from sentiment metrics)
    ├─→ CommunityGrowth (from social metrics)
    └─→ SentimentScore (from sentiment data)

Scoring Features
    │
    ├─→ GemScore (weighted sum of normalized features)
    ├─→ Confidence (from Recency + DataCompleteness)
    └─→ BCS (from probability + filter adjustments)
```

### Feature Calculation Order

**Stage 1: Raw Features**
1. Fetch market data (price, volume, market_cap)
2. Fetch order book data (bids, asks)
3. Fetch on-chain data (transactions, holders)
4. Fetch sentiment data (tweets, news)
5. Fetch derivatives data (funding rates, OI)

**Stage 2: Derived Features**
1. Compute technical indicators (rsi, macd, bollinger bands)
2. Compute liquidity metrics (depth, spread)
3. Compute order flow metrics (imbalances)
4. Compute on-chain activity metrics
5. Compute sentiment scores

**Stage 3: Normalized Features**
1. AccumulationScore
2. OnchainActivity
3. LiquidityDepth
4. TokenomicsRisk
5. ContractSafety
6. NarrativeMomentum
7. CommunityGrowth
8. SentimentScore

**Stage 4: Quality Metrics**
1. Recency (data freshness)
2. DataCompleteness (feature availability)

**Stage 5: Final Scoring**
1. GemScore (weighted sum)
2. Confidence (quality-based)
3. BCS (probability-based)

---

## Data Contracts

### GemScore Calculation

```python
WEIGHTS = {
    "SentimentScore": 0.15,
    "AccumulationScore": 0.20,
    "OnchainActivity": 0.15,
    "LiquidityDepth": 0.10,
    "TokenomicsRisk": 0.12,
    "ContractSafety": 0.12,
    "NarrativeMomentum": 0.08,
    "CommunityGrowth": 0.08,
}

GemScore = sum(weight * feature for feature, weight in WEIGHTS.items()) * 100
```

**Constraints:**
- All input features must be in range [0, 1]
- Sum of weights must equal 1.0
- Output range: [0, 100]

### Confidence Calculation

```python
Confidence = (0.5 * Recency + 0.5 * DataCompleteness) * 100
```

**Constraints:**
- Recency, DataCompleteness in range [0, 1]
- Output range: [0, 100]

### BCS Calculation

```python
BCS = probability * liquidity_adjustment * slippage_adjustment * sector_adjustment
```

**Adjustments:**
- `liquidity_adjustment`: 1.0 if ADV ≥ $5M, 0.8 otherwise
- `slippage_adjustment`: 1.0 if slippage < 0.5%, 0.9 if < 1%, 0.7 otherwise
- `sector_adjustment`: 1.0 if sector_count < 3, 0.8 if < 5, 0.6 otherwise

---

## Feature Validation Rules

### Type Validation

| Type | Python Type | Validation |
|------|-------------|------------|
| Numeric | float, int | `isinstance(value, (int, float))` |
| Categorical | str | `isinstance(value, str) and value in valid_categories` |
| Boolean | bool | `isinstance(value, bool)` |
| Timestamp | float | `isinstance(value, float) and value > 0` |
| Vector | list, np.ndarray | `isinstance(value, (list, np.ndarray))` |

### Range Validation

Features with defined ranges are validated on write:

```python
if feature.min_value is not None and value < feature.min_value:
    raise ValidationError(f"Value {value} below minimum {feature.min_value}")

if feature.max_value is not None and value > feature.max_value:
    raise ValidationError(f"Value {value} above maximum {feature.max_value}")
```

### Freshness Validation

Features have maximum age constraints:

```python
max_age_seconds = {
    "Market": 300,      # 5 minutes
    "Liquidity": 60,    # 1 minute
    "OrderFlow": 30,    # 30 seconds
    "Derivatives": 300, # 5 minutes
    "Sentiment": 3600,  # 1 hour
    "OnChain": 3600,    # 1 hour
    "Technical": 300,   # 5 minutes
}

if time.time() - feature_timestamp > max_age_seconds[category]:
    raise ValidationError("Feature stale")
```

### Completeness Validation

Required features must be present:

```python
required_features = [
    "price_usd",
    "market_cap_usd",
    "volume_24h_usd",
    "liquidity_pool_usd",
]

missing = [f for f in required_features if f not in features]
if missing:
    raise ValidationError(f"Missing required features: {missing}")
```

---

## Feature Versioning

Features follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking change (computation method changed, incompatible)
- **MINOR**: New feature added (backward compatible)
- **PATCH**: Bug fix or minor improvement (backward compatible)

### Version History

| Feature | Version | Date | Change |
|---------|---------|------|--------|
| `GemScore` | 1.0.0 | 2025-01-15 | Initial implementation |
| `ContractSafety` | 1.1.0 | 2025-02-20 | Added FA field scrubbing |
| `BCS` | 1.0.0 | 2025-03-10 | Initial implementation |
| `OnchainActivity` | 1.0.1 | 2025-04-05 | Fixed holder count bug |

---

## Appendix: Feature Registry

The complete feature registry is maintained in code:

```python
# src/core/feature_store.py

class FeatureType(Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    VECTOR = "vector"

class FeatureCategory(Enum):
    MARKET = "market"
    LIQUIDITY = "liquidity"
    ORDERFLOW = "orderflow"
    DERIVATIVES = "derivatives"
    SENTIMENT = "sentiment"
    ONCHAIN = "onchain"
    TECHNICAL = "technical"
    QUALITY = "quality"
    SCORING = "scoring"
```

---

## Related Documents

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [docs/FEATURE_STORE_IMPLEMENTATION.md](docs/FEATURE_STORE_IMPLEMENTATION.md) - Feature store implementation
- [docs/FEATURE_VALIDATION_GUIDE.md](docs/FEATURE_VALIDATION_GUIDE.md) - Feature validation guide
- [FEATURE_VALIDATION_IMPLEMENTATION.md](FEATURE_VALIDATION_IMPLEMENTATION.md) - Validation implementation details

---

**Document Owner**: Data Engineering Team  
**Review Cycle**: Quarterly  
**Last Review**: October 22, 2025  
**Next Review**: January 22, 2026
