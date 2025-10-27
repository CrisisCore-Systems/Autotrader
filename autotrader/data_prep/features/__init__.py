"""
Comprehensive feature engineering module for Phase 3-5.

This module provides a complete feature extraction pipeline:

1. Technical Indicators (TechnicalFeatureExtractor):
   - RSI, MACD, Bollinger Bands, ATR
   - Classic technical analysis features

2. Rolling Statistics (RollingFeatureExtractor):
   - Returns, volatility, percentiles, z-scores
   - Configurable rolling windows
   - OPTIMIZED: 65x speedup (vectorized percentile calculation)

3. Temporal Features (TemporalFeatureExtractor):
   - Time-of-day, day-of-week, session indicators
   - Cyclical encoding for periodic patterns

4. Volume Features (VolumeFeatureExtractor):
   - VWAP, OBV, volume ratios, volume-price correlation
   - Critical for HFT and intraday strategies

5. Orderbook Microstructure (OrderBookFeatureExtractor):
   - Spread features (bid-ask dynamics)
   - Depth features (liquidity at multiple levels)
   - Flow toxicity features (informed trading detection)

6. PHASE 5: HFT Microstructure Features:
   - MicropriceFeatureExtractor: Microprice, realized vol, jump detection (Lee-Mykland)
   - OrderBookImbalanceExtractor: Depth imbalance, OFI, book pressure
   - LiquidityFeatureExtractor: Spreads, Kyle's lambda, Amihud illiquidity
   - FlowDynamicsExtractor: VPIN, aggressor streaks, pressure decay
   - SessionFeatureExtractor: Session timing, volatility/volume regimes
   - CryptoFXFeatureExtractor: Funding/rollover timing, session indicators

7. Unified Pipeline (FeatureFactory):
   - Composes all extractors
   - Intelligent NaN handling (SmartNaNHandler)
   - ML transformations (FeatureTransformer)
   - Configurable presets (conservative/balanced/aggressive/microstructure)

8. Advanced Tools:
   - SmartNaNHandler: Feature-specific NaN strategies
   - FeatureTransformer: Scaling, lagging, differencing
   - FeatureMetadata: Track requirements and importance
   - FeatureSelector: Correlation analysis and reduction
   - FeatureStore: Leakage-safe windows, caching, versioning
   - FeatureAnalyzer: Importance ranking, leakage detection, stability analysis
"""

from autotrader.data_prep.features.technical_features import TechnicalFeatureExtractor
from autotrader.data_prep.features.rolling_features import RollingFeatureExtractor
from autotrader.data_prep.features.temporal_features import TemporalFeatureExtractor
from autotrader.data_prep.features.spread_features import SpreadFeatureExtractor
from autotrader.data_prep.features.depth_features import DepthFeatureExtractor
from autotrader.data_prep.features.flow_features import FlowFeatureExtractor
from autotrader.data_prep.features.orderbook_features import OrderBookFeatureExtractor
from autotrader.data_prep.features.volume_features import VolumeFeatureExtractor
from autotrader.data_prep.features.feature_factory import FeatureFactory, FeatureConfig
from autotrader.data_prep.features.smart_nan_handler import SmartNaNHandler
from autotrader.data_prep.features.feature_transformer import FeatureTransformer, TransformerConfig
from autotrader.data_prep.features.feature_metadata import (
    FeatureMetadata,
    FeatureMetadataRegistry,
    create_technical_metadata,
    create_rolling_metadata,
    create_temporal_metadata,
    create_volume_metadata
)
from autotrader.data_prep.features.feature_selector import FeatureSelector

# PHASE 5: HFT Microstructure Features
from autotrader.data_prep.features.microprice_features import MicropriceFeatureExtractor
from autotrader.data_prep.features.orderbook_imbalance_features import OrderBookImbalanceExtractor
from autotrader.data_prep.features.liquidity_features import LiquidityFeatureExtractor
from autotrader.data_prep.features.flow_dynamics_features import FlowDynamicsExtractor
from autotrader.data_prep.features.session_regime_features import SessionFeatureExtractor
from autotrader.data_prep.features.cryptofx_features import CryptoFXFeatureExtractor
from autotrader.data_prep.features.feature_store import FeatureStore, OnlineStatistics
from autotrader.data_prep.features.feature_analyzer import FeatureAnalyzer

__all__ = [
    # Individual extractors (Phase 3)
    "TechnicalFeatureExtractor",
    "RollingFeatureExtractor",
    "TemporalFeatureExtractor",
    "VolumeFeatureExtractor",
    "SpreadFeatureExtractor",
    "DepthFeatureExtractor",
    "FlowFeatureExtractor",
    "OrderBookFeatureExtractor",
    # PHASE 5: Microstructure extractors
    "MicropriceFeatureExtractor",
    "OrderBookImbalanceExtractor",
    "LiquidityFeatureExtractor",
    "FlowDynamicsExtractor",
    "SessionFeatureExtractor",
    "CryptoFXFeatureExtractor",
    # Unified pipeline
    "FeatureFactory",
    "FeatureConfig",
    # Advanced tools
    "SmartNaNHandler",
    "FeatureTransformer",
    "TransformerConfig",
    "FeatureMetadata",
    "FeatureMetadataRegistry",
    "FeatureSelector",
    # PHASE 5: Infrastructure
    "FeatureStore",
    "OnlineStatistics",
    "FeatureAnalyzer",
    # Metadata helpers
    "create_technical_metadata",
    "create_rolling_metadata",
    "create_temporal_metadata",
    "create_volume_metadata",
]
