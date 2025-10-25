"""
Order book imbalance features for microstructure analysis.

Implements orderbook-based features that predict short-term price movements:
- Depth imbalance: Bid/ask liquidity asymmetry
- Queue position: Relative position in book (market making)
- Top-N imbalance: Multi-level book pressure
- Order Flow Imbalance (OFI): Net aggressive order flow
- Book pressure: Time-weighted imbalance momentum

These features capture:
- Supply/demand imbalances (depth imbalance predicts next tick)
- Queue dynamics (adverse selection risk)
- Information flow (OFI captures informed trading)
- Pressure persistence (mean reversion vs momentum)

References:
- Depth imbalance: Cont et al. (2014)
- OFI: Cont, Kukanov, Stoikov (2014)
- Queue position: Huang & Polak (2011)
- Book pressure: Lipton et al. (2013)
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal


class OrderBookImbalanceExtractor:
    """
    Extract order book imbalance features.
    
    Features:
    1. depth_imbalance: (bid_size - ask_size) / (bid_size + ask_size) at top level
    2. depth_imbalance_top5: Multi-level imbalance (levels 1-5)
    3. weighted_depth_imbalance: Distance-weighted imbalance
    4. queue_position: Relative position in best bid/ask queue
    5. ofi: Order Flow Imbalance (net aggressive flow)
    6. ofi_momentum: Rolling sum of OFI (pressure accumulation)
    7. book_pressure: Exponentially weighted imbalance
    8. imbalance_volatility: Volatility of depth imbalance
    9. imbalance_flip_rate: Frequency of imbalance sign changes
    
    Example:
        extractor = OrderBookImbalanceExtractor(
            num_levels=5,
            ofi_window=20
        )
        
        features = extractor.extract_all(
            orderbook_df=orderbook,
            trade_df=trades  # For OFI calculation
        )
    """
    
    def __init__(
        self,
        num_levels: int = 5,
        ofi_window: int = 20,
        pressure_decay: float = 0.95,
        imbalance_vol_window: int = 50
    ):
        """
        Initialize order book imbalance extractor.
        
        Args:
            num_levels: Number of orderbook levels to use
            ofi_window: Window for OFI momentum
            pressure_decay: Exponential decay for book pressure (0-1)
            imbalance_vol_window: Window for imbalance volatility
        """
        self.num_levels = num_levels
        self.ofi_window = ofi_window
        self.pressure_decay = pressure_decay
        self.imbalance_vol_window = imbalance_vol_window
    
    def extract_all(
        self,
        orderbook_df: pd.DataFrame,
        trade_df: Optional[pd.DataFrame] = None,
        target_index: Optional[pd.Index] = None
    ) -> pd.DataFrame:
        """
        Extract all order book imbalance features.
        
        Args:
            orderbook_df: Orderbook snapshots with bid/ask prices and sizes
            trade_df: Trade data (optional, for OFI)
            target_index: Target index to align features to
        
        Returns:
            DataFrame with imbalance features
        """
        if target_index is None:
            target_index = orderbook_df.index
        
        features = pd.DataFrame(index=target_index)
        
        # Depth imbalance (top level)
        features['depth_imbalance'] = self._calculate_depth_imbalance(
            orderbook_df, level=1
        )
        
        # Multi-level depth imbalance
        features['depth_imbalance_top5'] = self._calculate_multilevel_imbalance(
            orderbook_df
        )
        
        # Weighted depth imbalance (distance-weighted)
        features['weighted_depth_imbalance'] = self._calculate_weighted_imbalance(
            orderbook_df
        )
        
        # Queue position (if available)
        if 'own_bid_position' in orderbook_df.columns:
            features['queue_position_bid'] = orderbook_df['own_bid_position'] / orderbook_df['bid_size_1']
            features['queue_position_ask'] = orderbook_df['own_ask_position'] / orderbook_df['ask_size_1']
        
        # Order Flow Imbalance (if trades available)
        if trade_df is not None:
            ofi_series = self._calculate_ofi(orderbook_df, trade_df)
            features['ofi'] = ofi_series.reindex(target_index, method='ffill')
            
            # OFI momentum (accumulation of pressure)
            features['ofi_momentum'] = features['ofi'].rolling(
                window=self.ofi_window,
                min_periods=self.ofi_window
            ).sum()
        
        # Book pressure (exponentially weighted imbalance)
        features['book_pressure'] = self._calculate_book_pressure(
            features['depth_imbalance']
        )
        
        # Imbalance volatility (regime indicator)
        features['imbalance_volatility'] = self._calculate_imbalance_volatility(
            features['depth_imbalance']
        )
        
        # Imbalance flip rate (mean reversion indicator)
        features['imbalance_flip_rate'] = self._calculate_flip_rate(
            features['depth_imbalance']
        )
        
        return features
    
    def _calculate_depth_imbalance(
        self,
        orderbook_df: pd.DataFrame,
        level: int = 1
    ) -> pd.Series:
        """
        Calculate depth imbalance at given level.
        
        DI = (bid_size - ask_size) / (bid_size + ask_size)
        
        Range: [-1, 1]
        Positive = more bid liquidity (upward pressure)
        Negative = more ask liquidity (downward pressure)
        
        Predictive power: DI at t predicts price change at t+1
        (Cont et al. 2014)
        """
        bid_col = f'bid_size_{level}'
        ask_col = f'ask_size_{level}'
        
        if bid_col not in orderbook_df.columns or ask_col not in orderbook_df.columns:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        bid_size = orderbook_df[bid_col]
        ask_size = orderbook_df[ask_col]
        
        # Avoid division by zero
        total_size = bid_size + ask_size
        total_size = total_size.replace(0, np.nan)
        
        depth_imbalance = (bid_size - ask_size) / total_size
        
        return depth_imbalance
    
    def _calculate_multilevel_imbalance(
        self,
        orderbook_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate multi-level depth imbalance (top N levels).
        
        DI_N = sum_{i=1}^N (bid_size_i - ask_size_i) / sum_{i=1}^N (bid_size_i + ask_size_i)
        
        More robust than single-level because it captures deeper liquidity.
        """
        bid_sizes = []
        ask_sizes = []
        
        for level in range(1, self.num_levels + 1):
            bid_col = f'bid_size_{level}'
            ask_col = f'ask_size_{level}'
            
            if bid_col in orderbook_df.columns and ask_col in orderbook_df.columns:
                bid_sizes.append(orderbook_df[bid_col])
                ask_sizes.append(orderbook_df[ask_col])
        
        if not bid_sizes:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        total_bid = sum(bid_sizes)
        total_ask = sum(ask_sizes)
        
        total_size = total_bid + total_ask
        total_size = total_size.replace(0, np.nan)
        
        multilevel_imbalance = (total_bid - total_ask) / total_size
        
        return multilevel_imbalance
    
    def _calculate_weighted_imbalance(
        self,
        orderbook_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate distance-weighted depth imbalance.
        
        Weights levels by distance from mid:
        w_i = 1 / (1 + distance_i / spread)
        
        Closer levels get higher weight (more relevant for price discovery).
        """
        mid = (orderbook_df['bid_price_1'] + orderbook_df['ask_price_1']) / 2
        spread = orderbook_df['ask_price_1'] - orderbook_df['bid_price_1']
        spread = spread.replace(0, np.nan)
        
        weighted_bid = 0
        weighted_ask = 0
        total_weight = 0
        
        for level in range(1, self.num_levels + 1):
            bid_price_col = f'bid_price_{level}'
            ask_price_col = f'ask_price_{level}'
            bid_size_col = f'bid_size_{level}'
            ask_size_col = f'ask_size_{level}'
            
            if all(col in orderbook_df.columns for col in [bid_price_col, ask_price_col, bid_size_col, ask_size_col]):
                # Distance from mid
                bid_dist = abs(orderbook_df[bid_price_col] - mid)
                ask_dist = abs(orderbook_df[ask_price_col] - mid)
                
                # Weights (inverse distance, normalized by spread)
                bid_weight = 1 / (1 + bid_dist / spread)
                ask_weight = 1 / (1 + ask_dist / spread)
                
                weighted_bid += orderbook_df[bid_size_col] * bid_weight
                weighted_ask += orderbook_df[ask_size_col] * ask_weight
                total_weight += bid_weight + ask_weight
        
        total_weight = total_weight.replace(0, np.nan)
        
        weighted_imbalance = (weighted_bid - weighted_ask) / total_weight
        
        return weighted_imbalance
    
    def _calculate_ofi(
        self,
        orderbook_df: pd.DataFrame,
        trade_df: pd.DataFrame
    ) -> pd.Series:
        """
        Calculate Order Flow Imbalance (OFI).
        
        OFI captures net aggressive order flow:
        - Buy market order: positive OFI
        - Sell market order: negative OFI
        
        Method: Compare orderbook changes with trade flow direction.
        
        Reference: Cont, Kukanov, Stoikov (2014)
        "The Price Impact of Order Book Events"
        """
        # Simplified OFI: use trade side as proxy
        # In production, would compare orderbook deltas with trade volume
        
        if 'side' not in trade_df.columns:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        # Aggregate trades by orderbook timestamp
        trade_df = trade_df.copy()
        trade_df['ofi_contribution'] = trade_df.apply(
            lambda row: row['size'] if row['side'] == 'buy' else -row['size'],
            axis=1
        )
        
        # Group by orderbook update times
        ofi_by_time = trade_df.groupby(trade_df.index)['ofi_contribution'].sum()
        
        # Align to orderbook index
        ofi_series = ofi_by_time.reindex(orderbook_df.index, fill_value=0)
        
        return ofi_series
    
    def _calculate_book_pressure(self, depth_imbalance: pd.Series) -> pd.Series:
        """
        Calculate exponentially weighted book pressure.
        
        BP_t = α * DI_t + (1-α) * BP_{t-1}
        
        This captures persistent imbalance (not just instantaneous).
        High pressure = sustained one-sided flow.
        """
        # Exponential moving average with decay
        book_pressure = depth_imbalance.ewm(
            alpha=1 - self.pressure_decay,
            adjust=False
        ).mean()
        
        return book_pressure
    
    def _calculate_imbalance_volatility(
        self,
        depth_imbalance: pd.Series
    ) -> pd.Series:
        """
        Calculate volatility of depth imbalance.
        
        High volatility = frequent book updates (high activity)
        Low volatility = stable book (low activity)
        
        Regime indicator for market making.
        """
        imbalance_vol = depth_imbalance.rolling(
            window=self.imbalance_vol_window,
            min_periods=self.imbalance_vol_window
        ).std()
        
        return imbalance_vol
    
    def _calculate_flip_rate(self, depth_imbalance: pd.Series) -> pd.Series:
        """
        Calculate imbalance flip rate (sign changes).
        
        Flip rate = # of sign changes / window
        
        High flip rate = mean reverting (two-sided flow)
        Low flip rate = trending (one-sided flow)
        
        Used to detect regime (market making vs directional).
        """
        # Sign of imbalance
        imbalance_sign = np.sign(depth_imbalance)
        
        # Sign changes
        sign_changes = (imbalance_sign != imbalance_sign.shift(1)).astype(int)
        
        # Flip rate = # changes / window
        flip_rate = sign_changes.rolling(
            window=self.imbalance_vol_window,
            min_periods=self.imbalance_vol_window
        ).mean()
        
        return flip_rate
    
    def get_feature_names(self) -> list[str]:
        """Get list of feature names produced."""
        base_names = [
            'depth_imbalance',
            'depth_imbalance_top5',
            'weighted_depth_imbalance',
            'book_pressure',
            'imbalance_volatility',
            'imbalance_flip_rate'
        ]
        
        # Optional features (need trade data)
        optional_names = [
            'ofi',
            'ofi_momentum',
            'queue_position_bid',
            'queue_position_ask'
        ]
        
        return base_names + optional_names
