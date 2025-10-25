"""
Unified feature extraction factory.

Composes all feature extractors into a single pipeline:
- Technical indicators (RSI, MACD, Bollinger Bands, ATR)
- Rolling statistics (returns, volatility, percentiles)
- Temporal features (time-of-day, day-of-week, session)
- Orderbook features (spread, depth, flow toxicity)
- Volume features (VWAP, OBV, ratios, correlations)
- Microstructure features (microprice, imbalance, liquidity, flow dynamics)

Handles feature alignment, NaN filling, and validation.
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal
from dataclasses import dataclass
from datetime import time

from autotrader.data_prep.features.technical_features import TechnicalFeatureExtractor
from autotrader.data_prep.features.rolling_features import RollingFeatureExtractor
from autotrader.data_prep.features.temporal_features import TemporalFeatureExtractor
from autotrader.data_prep.features.orderbook_features import OrderBookFeatureExtractor
from autotrader.data_prep.features.volume_features import VolumeFeatureExtractor
from autotrader.data_prep.features.smart_nan_handler import SmartNaNHandler
from autotrader.data_prep.features.feature_transformer import FeatureTransformer, TransformerConfig

# PHASE 5: Microstructure extractors
from autotrader.data_prep.features.microprice_features import MicropriceFeatureExtractor
from autotrader.data_prep.features.orderbook_imbalance_features import OrderBookImbalanceExtractor
from autotrader.data_prep.features.liquidity_features import LiquidityFeatureExtractor
from autotrader.data_prep.features.flow_dynamics_features import FlowDynamicsExtractor
from autotrader.data_prep.features.session_regime_features import SessionFeatureExtractor
from autotrader.data_prep.features.cryptofx_features import CryptoFXFeatureExtractor


@dataclass
class FeatureConfig:
    """
    Configuration for feature extraction.
    
    Attributes:
        # Technical indicators
        enable_technical: Whether to extract technical features
        rsi_period: Period for RSI
        macd_fast: Fast EMA for MACD
        macd_slow: Slow EMA for MACD
        macd_signal: Signal line for MACD
        bb_period: Period for Bollinger Bands
        bb_std: Standard deviations for Bollinger Bands
        atr_period: Period for ATR
        
        # Rolling statistics
        enable_rolling: Whether to extract rolling features
        rolling_windows: List of rolling window sizes
        
        # Temporal features
        enable_temporal: Whether to extract temporal features
        timezone: Timezone for market hours
        
        # Volume features
        enable_volume: Whether to extract volume features (VWAP, OBV, ratios)
        vwap_window: Window for VWAP
        volume_ratio_window: Window for volume ratios
        volume_corr_window: Window for volume-price correlation
        
        # Orderbook features
        enable_orderbook: Whether to extract orderbook features
        orderbook_num_levels: Number of orderbook levels
        vpin_window: Window for VPIN
        
        # NaN handling
        use_smart_nan_handler: Whether to use intelligent NaN handling
        fill_method: How to fill NaN values ('forward', 'zero', 'drop') - legacy if smart handler disabled
        min_valid_features: Minimum valid features required (0.0-1.0)
        
        # Feature transformation
        transformer_config: Optional transformer configuration for ML-ready features
    """
    
    # Technical indicators
    enable_technical: bool = True
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    
    # Rolling statistics
    enable_rolling: bool = True
    rolling_windows: list[int] = None
    
    # Temporal features
    enable_temporal: bool = True
    timezone: str = "America/New_York"
    
    # Volume features (NEW - Tree-of-Thought improvements)
    enable_volume: bool = True
    vwap_window: int = 20
    volume_ratio_window: int = 20
    volume_corr_window: int = 50
    
    # Orderbook features
    enable_orderbook: bool = False  # Requires orderbook data
    orderbook_num_levels: int = 5
    vpin_window: int = 50
    kyle_window: int = 20
    amihud_window: int = 20
    
    # PHASE 5: Microstructure features (HFT-grade)
    enable_microprice: bool = False  # Requires orderbook data
    enable_orderbook_imbalance: bool = False  # Requires orderbook data
    enable_liquidity: bool = False  # Requires orderbook data
    enable_flow_dynamics: bool = False  # Requires orderbook + trade data
    enable_session_regime: bool = True  # Works with OHLCV data
    enable_cryptofx: bool = False  # For crypto/FX specific features
    
    # Microprice feature params
    realized_vol_window: int = 50
    jump_window: int = 100
    jump_threshold: float = 4.0
    vol_ratio_window: int = 200
    moment_window: int = 100
    
    # Orderbook imbalance params
    num_levels: int = 5
    ofi_window: int = 20
    pressure_decay: float = 0.95
    imbalance_vol_window: int = 50
    
    # Liquidity feature params
    kyles_window: int = 50
    amihud_illiq_window: int = 20
    roll_window: int = 100
    
    # Flow dynamics params
    momentum_window: int = 50
    decay_window: int = 100
    vpin_buckets: int = 50
    intensity_window: int = 20
    
    # Session/regime params
    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    vol_regime_window: int = 200
    vol_regime_threshold: float = 0.7
    volume_regime_window: int = 200
    volume_regime_threshold: float = 0.7
    
    # Crypto/FX params
    market_type: Literal["crypto", "fx", "equity"] = "equity"
    funding_interval_hours: int = 8
    fx_rollover_hour: int = 17
    fx_rollover_minute: int = 0
    
    # NaN handling (IMPROVED - Tree-of-Thought improvements)
    use_smart_nan_handler: bool = True  # Use feature-specific strategies
    fill_method: Literal["forward", "zero", "drop"] = "forward"  # Legacy fallback
    min_valid_features: float = 0.7  # 70% of features must be valid
    
    # Feature transformation (NEW - Tree-of-Thought improvements)
    transformer_config: Optional[TransformerConfig] = None
    
    def __post_init__(self):
        """Set defaults after initialization."""
        if self.rolling_windows is None:
            self.rolling_windows = [20, 50, 200]
    
    @classmethod
    def conservative(cls) -> "FeatureConfig":
        """
        Conservative configuration: fewer features, longer windows.
        
        Good for stable markets and longer-term strategies.
        """
        return cls(
            rolling_windows=[50, 200],
            rsi_period=20,
            bb_period=30,
            atr_period=20,
            min_valid_features=0.7  # Relaxed for 200-bar window
        )
    
    @classmethod
    def balanced(cls) -> "FeatureConfig":
        """
        Balanced configuration: standard features (default).
        
        Good general-purpose configuration.
        """
        return cls()  # Use defaults
    
    @classmethod
    def aggressive(cls) -> "FeatureConfig":
        """
        Aggressive configuration: more features, shorter windows.
        
        Good for volatile markets and short-term strategies.
        """
        return cls(
            rolling_windows=[10, 20, 50],
            rsi_period=10,
            bb_period=15,
            atr_period=10,
            min_valid_features=0.6
        )
    
    @classmethod
    def microstructure(cls) -> "FeatureConfig":
        """
        Microstructure configuration: HFT-grade features.
        
        Enables all microstructure features for high-frequency trading:
        - Microprice and realized volatility
        - Orderbook imbalance and flow dynamics
        - Liquidity measures (Kyle's lambda, Amihud)
        - Session and regime features
        
        Requires:
        - Orderbook data (bid/ask prices and sizes at multiple levels)
        - Trade data (for OFI and VPIN)
        
        Good for:
        - Market making strategies
        - High-frequency arbitrage
        - Microstructure research
        """
        return cls(
            # Disable OHLCV-based features (redundant for HFT)
            enable_technical=False,
            enable_rolling=False,
            enable_volume=False,
            
            # Enable microstructure features
            enable_microprice=True,
            enable_orderbook_imbalance=True,
            enable_liquidity=True,
            enable_flow_dynamics=True,
            enable_session_regime=True,
            enable_cryptofx=False,  # Set to True for crypto/FX
            
            # Shorter windows for HFT
            realized_vol_window=50,
            jump_window=100,
            ofi_window=20,
            kyles_window=50,
            momentum_window=50,
            vpin_buckets=50,
            
            # Relaxed validation (many NaNs in early windows)
            min_valid_features=0.5
        )


class FeatureFactory:
    """
    Unified feature extraction pipeline.
    
    Orchestrates all feature extractors and handles data alignment.
    
    Example:
        # Basic usage with OHLCV data
        factory = FeatureFactory(config=FeatureConfig.balanced())
        features = factory.extract_all(bars_df=bars)
        
        # With orderbook data
        config = FeatureConfig(enable_orderbook=True)
        factory = FeatureFactory(config=config)
        features = factory.extract_all(
            bars_df=bars,
            order_book_df=orderbook,
            trade_df=trades
        )
    """
    
    def __init__(self, config: FeatureConfig = None):
        """
        Initialize feature factory.
        
        Args:
            config: Feature configuration (default: balanced)
        """
        self.config = config or FeatureConfig.balanced()
        
        # Initialize extractors based on config
        self.technical_extractor = None
        self.rolling_extractor = None
        self.temporal_extractor = None
        self.volume_extractor = None
        self.orderbook_extractor = None
        
        # PHASE 5: Microstructure extractors
        self.microprice_extractor = None
        self.orderbook_imbalance_extractor = None
        self.liquidity_extractor = None
        self.flow_dynamics_extractor = None
        self.session_regime_extractor = None
        self.cryptofx_extractor = None
        
        # Initialize NaN handler (NEW - Tree-of-Thought)
        self.nan_handler = SmartNaNHandler() if self.config.use_smart_nan_handler else None
        
        # Initialize transformer (NEW - Tree-of-Thought)
        self.transformer = None
        if self.config.transformer_config is not None:
            self.transformer = FeatureTransformer(self.config.transformer_config)
        
        if self.config.enable_technical:
            self.technical_extractor = TechnicalFeatureExtractor(
                rsi_period=self.config.rsi_period,
                macd_fast=self.config.macd_fast,
                macd_slow=self.config.macd_slow,
                macd_signal=self.config.macd_signal,
                bb_period=self.config.bb_period,
                bb_std=self.config.bb_std,
                atr_period=self.config.atr_period
            )
        
        if self.config.enable_rolling:
            self.rolling_extractor = RollingFeatureExtractor(
                windows=self.config.rolling_windows
            )
        
        if self.config.enable_temporal:
            self.temporal_extractor = TemporalFeatureExtractor(
                timezone=self.config.timezone
            )
        
        # NEW - Tree-of-Thought: Volume features
        if self.config.enable_volume:
            self.volume_extractor = VolumeFeatureExtractor(
                vwap_window=self.config.vwap_window,
                volume_ratio_window=self.config.volume_ratio_window,
                volume_corr_window=self.config.volume_corr_window
            )
        
        if self.config.enable_orderbook:
            self.orderbook_extractor = OrderBookFeatureExtractor(
                num_levels=self.config.orderbook_num_levels,
                vpin_window=self.config.vpin_window,
                kyle_window=self.config.kyle_window,
                amihud_window=self.config.amihud_window
            )
        
        # PHASE 5: Initialize microstructure extractors
        if self.config.enable_microprice:
            self.microprice_extractor = MicropriceFeatureExtractor(
                realized_vol_window=self.config.realized_vol_window,
                jump_window=self.config.jump_window,
                jump_threshold=self.config.jump_threshold,
                vol_ratio_window=self.config.vol_ratio_window,
                moment_window=self.config.moment_window
            )
        
        if self.config.enable_orderbook_imbalance:
            self.orderbook_imbalance_extractor = OrderBookImbalanceExtractor(
                num_levels=self.config.num_levels,
                ofi_window=self.config.ofi_window,
                pressure_decay=self.config.pressure_decay,
                imbalance_vol_window=self.config.imbalance_vol_window
            )
        
        if self.config.enable_liquidity:
            self.liquidity_extractor = LiquidityFeatureExtractor(
                kyles_window=self.config.kyles_window,
                amihud_window=self.config.amihud_illiq_window,
                roll_window=self.config.roll_window
            )
        
        if self.config.enable_flow_dynamics:
            self.flow_dynamics_extractor = FlowDynamicsExtractor(
                momentum_window=self.config.momentum_window,
                decay_window=self.config.decay_window,
                vpin_buckets=self.config.vpin_buckets,
                intensity_window=self.config.intensity_window
            )
        
        if self.config.enable_session_regime:
            self.session_regime_extractor = SessionFeatureExtractor(
                market_open=time(self.config.market_open_hour, self.config.market_open_minute),
                market_close=time(self.config.market_close_hour, self.config.market_close_minute),
                vol_regime_window=self.config.vol_regime_window,
                vol_regime_threshold=self.config.vol_regime_threshold,
                volume_regime_window=self.config.volume_regime_window,
                volume_regime_threshold=self.config.volume_regime_threshold
            )
        
        if self.config.enable_cryptofx:
            self.cryptofx_extractor = CryptoFXFeatureExtractor(
                market_type=self.config.market_type,
                funding_interval_hours=self.config.funding_interval_hours,
                fx_rollover_time=time(self.config.fx_rollover_hour, self.config.fx_rollover_minute)
            )
    
    def extract_all(
        self,
        bars_df: pd.DataFrame,
        order_book_df: Optional[pd.DataFrame] = None,
        trade_df: Optional[pd.DataFrame] = None,
        # OHLCV columns
        close_col: str = "close",
        high_col: str = "high",
        low_col: str = "low",
        volume_col: str = "volume",
        timestamp_col: str = "timestamp_utc"
    ) -> pd.DataFrame:
        """
        Extract all features from bar data.
        
        Args:
            bars_df: DataFrame with OHLCV bar data (required)
            order_book_df: DataFrame with orderbook snapshots (optional)
            trade_df: DataFrame with trade data (optional)
            close_col: Name of close price column
            high_col: Name of high price column
            low_col: Name of low price column
            volume_col: Name of volume column
            timestamp_col: Name of timestamp column
        
        Returns:
            DataFrame with all features (same index as bars_df)
        
        Raises:
            ValueError: If required data is missing or invalid
        """
        # Validate inputs
        self._validate_inputs(bars_df, order_book_df, trade_df)
        
        # Start with empty feature set
        all_features = pd.DataFrame(index=bars_df.index)
        
        # Extract technical features
        if self.technical_extractor is not None:
            tech_features = self.technical_extractor.extract_all(
                bars_df=bars_df,
                close_col=close_col,
                high_col=high_col,
                low_col=low_col,
                volume_col=volume_col
            )
            all_features = pd.concat([all_features, tech_features], axis=1)
        
        # Extract rolling features
        if self.rolling_extractor is not None:
            rolling_features = self.rolling_extractor.extract_all(
                bars_df=bars_df,
                close_col=close_col,
                high_col=high_col,
                low_col=low_col
            )
            all_features = pd.concat([all_features, rolling_features], axis=1)
        
        # Extract temporal features
        if self.temporal_extractor is not None:
            temporal_features = self.temporal_extractor.extract_all(
                bars_df=bars_df,
                timestamp_col=timestamp_col
            )
            all_features = pd.concat([all_features, temporal_features], axis=1)
        
        # Extract volume features (NEW - Tree-of-Thought)
        if self.volume_extractor is not None:
            volume_features = self.volume_extractor.extract_all(
                bars_df=bars_df,
                close_col=close_col,
                volume_col=volume_col,
                high_col=high_col,
                low_col=low_col
            )
            all_features = pd.concat([all_features, volume_features], axis=1)
        
        # Extract orderbook features (if enabled and data provided)
        if self.orderbook_extractor is not None:
            if order_book_df is None:
                raise ValueError("Orderbook features enabled but order_book_df not provided")
            
            orderbook_features_dict = self.orderbook_extractor.extract_all(
                order_book_df=order_book_df,
                trade_df=trade_df
            )
            
            # Merge all orderbook feature groups
            for feature_group_df in orderbook_features_dict.values():
                # Align with bars_df index
                aligned_features = feature_group_df.reindex(bars_df.index)
                all_features = pd.concat([all_features, aligned_features], axis=1)
        
        # PHASE 5: Extract microstructure features
        if self.microprice_extractor is not None:
            if order_book_df is None:
                raise ValueError("Microprice features enabled but order_book_df not provided")
            microprice_features = self.microprice_extractor.extract_all(
                orderbook_df=order_book_df,
                target_index=bars_df.index
            )
            all_features = pd.concat([all_features, microprice_features], axis=1)
        
        if self.orderbook_imbalance_extractor is not None:
            if order_book_df is None:
                raise ValueError("Orderbook imbalance features enabled but order_book_df not provided")
            imbalance_features = self.orderbook_imbalance_extractor.extract_all(
                orderbook_df=order_book_df,
                trade_df=trade_df,
                target_index=bars_df.index
            )
            all_features = pd.concat([all_features, imbalance_features], axis=1)
        
        if self.liquidity_extractor is not None:
            if order_book_df is None:
                raise ValueError("Liquidity features enabled but order_book_df not provided")
            liquidity_features = self.liquidity_extractor.extract_all(
                orderbook_df=order_book_df,
                trade_df=trade_df,
                target_index=bars_df.index
            )
            all_features = pd.concat([all_features, liquidity_features], axis=1)
        
        if self.flow_dynamics_extractor is not None:
            if order_book_df is None or trade_df is None:
                raise ValueError("Flow dynamics features enabled but order_book_df and trade_df not provided")
            flow_features = self.flow_dynamics_extractor.extract_all(
                orderbook_df=order_book_df,
                trade_df=trade_df,
                target_index=bars_df.index
            )
            all_features = pd.concat([all_features, flow_features], axis=1)
        
        if self.session_regime_extractor is not None:
            # Session features work with OHLCV data
            session_features = self.session_regime_extractor.extract_all(
                price_df=bars_df,
                volume_series=bars_df[volume_col] if volume_col in bars_df.columns else None,
                target_index=bars_df.index
            )
            all_features = pd.concat([all_features, session_features], axis=1)
        
        if self.cryptofx_extractor is not None:
            cryptofx_features = self.cryptofx_extractor.extract_all(
                df=bars_df,
                target_index=bars_df.index
            )
            all_features = pd.concat([all_features, cryptofx_features], axis=1)
        
        # Handle NaN values (IMPROVED - Tree-of-Thought)
        all_features = self._handle_nans(all_features)
        
        # Apply feature transformation if configured (NEW - Tree-of-Thought)
        if self.transformer is not None:
            # Note: fit_transform should be called on training data
            # For inference, use transform() instead
            # This is a design choice - user should handle fit/transform split
            all_features = self.transformer.fit_transform(all_features)
        
        # Validate output
        self._validate_output(all_features)
        
        return all_features
    
    def _validate_inputs(
        self,
        bars_df: pd.DataFrame,
        order_book_df: Optional[pd.DataFrame],
        trade_df: Optional[pd.DataFrame]
    ):
        """
        Validate input DataFrames.
        
        Args:
            bars_df: Bar data
            order_book_df: Orderbook data
            trade_df: Trade data
        
        Raises:
            ValueError: If inputs are invalid
        """
        if bars_df is None or len(bars_df) == 0:
            raise ValueError("bars_df is required and must not be empty")
        
        if self.config.enable_orderbook and order_book_df is None:
            raise ValueError("Orderbook features enabled but order_book_df not provided")
        
        # Check for minimum data requirements
        min_bars = max(
            self.config.rsi_period if self.config.enable_technical else 0,
            self.config.bb_period if self.config.enable_technical else 0,
            max(self.config.rolling_windows) if self.config.enable_rolling else 0
        )
        
        if len(bars_df) < min_bars:
            raise ValueError(
                f"bars_df must have at least {min_bars} rows for configured features "
                f"(currently has {len(bars_df)})"
            )
    
    def _handle_nans(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Handle NaN values according to configuration.
        
        IMPROVED (Tree-of-Thought): Uses SmartNaNHandler by default for
        feature-specific strategies (RSI→50, returns→0, etc.)
        
        Args:
            features: Feature DataFrame
        
        Returns:
            DataFrame with NaN values handled
        """
        # Use smart NaN handler if enabled (NEW - Tree-of-Thought)
        if self.nan_handler is not None:
            return self.nan_handler.handle_nans(features)
        
        # Legacy fallback methods
        if self.config.fill_method == "forward":
            # Forward fill (carry last valid value)
            return features.ffill()
        
        elif self.config.fill_method == "zero":
            # Fill with zero
            return features.fillna(0.0)
        
        elif self.config.fill_method == "drop":
            # Drop rows with any NaN
            return features.dropna()
        
        else:
            raise ValueError(f"Unknown fill_method: {self.config.fill_method}")
    
    def _validate_output(self, features: pd.DataFrame):
        """
        Validate output features.
        
        Args:
            features: Feature DataFrame
        
        Raises:
            ValueError: If output is invalid
        """
        if len(features) == 0:
            raise ValueError("Feature extraction produced empty DataFrame")
        
        # Check for minimum valid features
        if self.config.fill_method != "drop":
            valid_pct = features.notna().mean().mean()
            if valid_pct < self.config.min_valid_features:
                raise ValueError(
                    f"Only {valid_pct:.1%} of features are valid "
                    f"(minimum required: {self.config.min_valid_features:.1%})"
                )
    
    def get_feature_names(self) -> list[str]:
        """
        Get list of all feature names that will be produced.
        
        Returns:
            List of feature names
        """
        names = []
        
        if self.technical_extractor is not None:
            names.extend(self.technical_extractor.get_feature_names())
        
        if self.rolling_extractor is not None:
            names.extend(self.rolling_extractor.get_feature_names())
        
        if self.temporal_extractor is not None:
            names.extend(self.temporal_extractor.get_feature_names())
        
        # NEW - Tree-of-Thought: Volume features
        if self.volume_extractor is not None:
            names.extend(self.volume_extractor.get_feature_names())
        
        if self.orderbook_extractor is not None:
            # Orderbook extractor has multiple sub-extractors
            # For simplicity, just add a note (actual names depend on runtime)
            names.append("orderbook_features_*")
        
        # Note: Transformer may expand features further (lags, diffs)
        if self.transformer is not None:
            names.append("# Note: Features expanded by transformer (lags, diffs, scaling)")
        
        return names
