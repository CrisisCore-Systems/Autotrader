"""
Liquidity and market impact features.

Implements measures of trading costs and price impact:
- Spread measures: Bid-ask spread, effective spread, depth-weighted spread
- Impact measures: Kyle's lambda, Amihud illiquidity, Roll spread
- Depth measures: Total depth, depth ratio

These features capture:
- Trading costs (spreads)
- Price impact (Kyle's lambda, Amihud)
- Market resilience (depth)
- Information asymmetry (Roll spread)

References:
- Kyle's lambda: Kyle (1985)
- Amihud illiquidity: Amihud (2002)
- Roll spread: Roll (1984)
- Effective spread: Hasbrouck (2009)
"""

import pandas as pd
import numpy as np
from typing import Optional


class LiquidityFeatureExtractor:
    """
    Extract liquidity and market impact features.
    
    Features:
    1. bid_ask_spread: Raw spread (ask - bid)
    2. relative_spread: Spread / mid (basis points)
    3. effective_spread: 2 * |trade_price - mid| (realized cost)
    4. depth_weighted_spread: Spread weighted by depth
    5. kyles_lambda: dP / dV (price impact per unit volume)
    6. amihud_illiquidity: |return| / volume (daily illiquidity)
    7. roll_spread: 2 * sqrt(-cov(r_t, r_{t-1})) (implicit spread)
    8. total_depth: bid_size + ask_size (available liquidity)
    9. depth_ratio: bid_size / ask_size (liquidity imbalance)
    
    Example:
        extractor = LiquidityFeatureExtractor(
            kyles_window=50,
            amihud_window=20
        )
        
        features = extractor.extract_all(
            orderbook_df=orderbook,
            trade_df=trades  # For effective spread
        )
    """
    
    def __init__(
        self,
        kyles_window: int = 50,
        amihud_window: int = 20,
        roll_window: int = 100
    ):
        """
        Initialize liquidity feature extractor.
        
        Args:
            kyles_window: Window for Kyle's lambda estimation
            amihud_window: Window for Amihud illiquidity
            roll_window: Window for Roll spread estimation
        """
        self.kyles_window = kyles_window
        self.amihud_window = amihud_window
        self.roll_window = roll_window
    
    def extract_all(
        self,
        orderbook_df: pd.DataFrame,
        trade_df: Optional[pd.DataFrame] = None,
        target_index: Optional[pd.Index] = None
    ) -> pd.DataFrame:
        """
        Extract all liquidity features.
        
        Args:
            orderbook_df: Orderbook snapshots with bid/ask prices and sizes
            trade_df: Trade data (optional, for effective spread)
            target_index: Target index to align features to
        
        Returns:
            DataFrame with liquidity features
        """
        if target_index is None:
            target_index = orderbook_df.index
        
        features = pd.DataFrame(index=target_index)
        
        # Calculate mid price for reference
        if 'bid_price_1' in orderbook_df.columns and 'ask_price_1' in orderbook_df.columns:
            mid = (orderbook_df['bid_price_1'] + orderbook_df['ask_price_1']) / 2
        else:
            mid = pd.Series(np.nan, index=orderbook_df.index)
        
        # Bid-ask spread (raw)
        features['bid_ask_spread'] = self._calculate_bid_ask_spread(orderbook_df)
        
        # Relative spread (basis points)
        features['relative_spread'] = self._calculate_relative_spread(
            orderbook_df, mid
        )
        
        # Effective spread (if trades available)
        if trade_df is not None:
            effective_spread = self._calculate_effective_spread(
                orderbook_df, trade_df, mid
            )
            features['effective_spread'] = effective_spread.reindex(
                target_index, method='ffill'
            )
        
        # Depth-weighted spread
        features['depth_weighted_spread'] = self._calculate_depth_weighted_spread(
            orderbook_df, mid
        )
        
        # Kyle's lambda (price impact)
        features['kyles_lambda'] = self._calculate_kyles_lambda(
            orderbook_df, mid
        )
        
        # Amihud illiquidity
        features['amihud_illiquidity'] = self._calculate_amihud_illiquidity(
            orderbook_df, mid
        )
        
        # Roll spread (implicit spread from serial covariance)
        features['roll_spread'] = self._calculate_roll_spread(mid)
        
        # Total depth (available liquidity)
        features['total_depth'] = self._calculate_total_depth(orderbook_df)
        
        # Depth ratio (liquidity imbalance)
        features['depth_ratio'] = self._calculate_depth_ratio(orderbook_df)
        
        return features
    
    def _calculate_bid_ask_spread(self, orderbook_df: pd.DataFrame) -> pd.Series:
        """
        Calculate raw bid-ask spread.
        
        Spread = Ask_1 - Bid_1
        
        Measures the cost of round-trip trade (buy + sell).
        """
        if 'bid_price_1' not in orderbook_df.columns or 'ask_price_1' not in orderbook_df.columns:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        spread = orderbook_df['ask_price_1'] - orderbook_df['bid_price_1']
        
        return spread
    
    def _calculate_relative_spread(
        self,
        orderbook_df: pd.DataFrame,
        mid: pd.Series
    ) -> pd.Series:
        """
        Calculate relative spread (normalized by price).
        
        Relative Spread = (Ask - Bid) / Mid * 10000  (basis points)
        
        Allows comparison across different price levels.
        """
        spread = self._calculate_bid_ask_spread(orderbook_df)
        
        # Avoid division by zero
        mid_safe = mid.replace(0, np.nan)
        
        relative_spread = (spread / mid_safe) * 10000  # Basis points
        
        return relative_spread
    
    def _calculate_effective_spread(
        self,
        orderbook_df: pd.DataFrame,
        trade_df: pd.DataFrame,
        mid: pd.Series
    ) -> pd.Series:
        """
        Calculate effective spread (realized trading cost).
        
        Effective Spread = 2 * |Trade_Price - Mid|
        
        Measures actual cost paid (can be less than quoted spread
        for trades inside the spread or more for aggressive trades).
        
        Reference: Hasbrouck (2009)
        """
        if 'price' not in trade_df.columns:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        # Align mid price to trade times
        trade_mid = mid.reindex(trade_df.index, method='ffill')
        
        # Effective spread per trade
        effective_spread_per_trade = 2 * abs(trade_df['price'] - trade_mid)
        
        # Average by orderbook update time
        effective_spread_by_time = effective_spread_per_trade.groupby(
            effective_spread_per_trade.index
        ).mean()
        
        return effective_spread_by_time
    
    def _calculate_depth_weighted_spread(
        self,
        orderbook_df: pd.DataFrame,
        mid: pd.Series
    ) -> pd.Series:
        """
        Calculate depth-weighted spread.
        
        DWS = sum(spread_i * depth_i) / sum(depth_i)
        
        Weights spread by available liquidity at each level.
        Captures cost of trading larger sizes.
        """
        if 'bid_price_1' not in orderbook_df.columns or 'ask_price_1' not in orderbook_df.columns:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        # Use top 5 levels if available
        total_weighted_spread = 0
        total_depth = 0
        
        for level in range(1, 6):
            bid_price_col = f'bid_price_{level}'
            ask_price_col = f'ask_price_{level}'
            bid_size_col = f'bid_size_{level}'
            ask_size_col = f'ask_size_{level}'
            
            if all(col in orderbook_df.columns for col in [bid_price_col, ask_price_col, bid_size_col, ask_size_col]):
                level_spread = orderbook_df[ask_price_col] - orderbook_df[bid_price_col]
                level_depth = orderbook_df[bid_size_col] + orderbook_df[ask_size_col]
                
                total_weighted_spread += level_spread * level_depth
                total_depth += level_depth
        
        # Avoid division by zero
        total_depth = total_depth.replace(0, np.nan)
        
        depth_weighted_spread = total_weighted_spread / total_depth
        
        return depth_weighted_spread
    
    def _calculate_kyles_lambda(
        self,
        orderbook_df: pd.DataFrame,
        mid: pd.Series
    ) -> pd.Series:
        """
        Calculate Kyle's lambda (price impact coefficient).
        
        Lambda = dP / dV
        
        Estimates as: cov(dP, V) / var(V)
        where dP = price change, V = signed volume
        
        Higher lambda = higher price impact per unit volume.
        
        Reference: Kyle (1985) "Continuous Auctions and Insider Trading"
        """
        # Price changes
        price_changes = mid.diff()
        
        # Signed volume (use depth imbalance as proxy)
        if 'bid_size_1' in orderbook_df.columns and 'ask_size_1' in orderbook_df.columns:
            signed_volume = (
                orderbook_df['bid_size_1'] - orderbook_df['ask_size_1']
            ).reindex(mid.index, method='ffill')
        else:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        # Rolling regression: dP = lambda * V + noise
        def calculate_lambda_window(df_window):
            if len(df_window) < 2:
                return np.nan
            
            cov = np.cov(df_window['dP'], df_window['V'])[0, 1]
            var_v = np.var(df_window['V'])
            
            if var_v == 0 or np.isnan(var_v):
                return np.nan
            
            return cov / var_v
        
        # Combine into DataFrame for rolling window
        impact_df = pd.DataFrame({
            'dP': price_changes,
            'V': signed_volume
        })
        
        kyles_lambda = impact_df.rolling(
            window=self.kyles_window,
            min_periods=self.kyles_window
        ).apply(lambda x: calculate_lambda_window(impact_df.loc[x.index]), raw=False)['dP']
        
        return kyles_lambda
    
    def _calculate_amihud_illiquidity(
        self,
        orderbook_df: pd.DataFrame,
        mid: pd.Series
    ) -> pd.Series:
        """
        Calculate Amihud illiquidity ratio.
        
        Amihud = |return| / volume
        
        Measures price impact per dollar traded.
        Higher = more illiquid (larger price move per volume).
        
        Reference: Amihud (2002) "Illiquidity and stock returns"
        """
        # Returns
        returns = mid.pct_change()
        abs_returns = abs(returns)
        
        # Volume (use total depth as proxy)
        if 'bid_size_1' in orderbook_df.columns and 'ask_size_1' in orderbook_df.columns:
            volume = (
                orderbook_df['bid_size_1'] + orderbook_df['ask_size_1']
            ).reindex(mid.index, method='ffill')
        else:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        # Avoid division by zero
        volume_safe = volume.replace(0, np.nan)
        
        # Amihud ratio
        amihud = abs_returns / volume_safe
        
        # Rolling average
        amihud_rolling = amihud.rolling(
            window=self.amihud_window,
            min_periods=self.amihud_window
        ).mean()
        
        return amihud_rolling
    
    def _calculate_roll_spread(self, mid: pd.Series) -> pd.Series:
        """
        Calculate Roll spread (implicit spread estimate).
        
        Roll Spread = 2 * sqrt(-cov(r_t, r_{t-1}))
        
        Estimates bid-ask spread from serial covariance of returns.
        Assumes all price changes are due to bid-ask bounce.
        
        Negative covariance = bid-ask bounce effect
        (buy at ask, sell at bid causes negative autocorrelation)
        
        Reference: Roll (1984) "A Simple Implicit Measure of the Effective Bid-Ask Spread"
        """
        # Returns
        returns = mid.pct_change()
        
        # Rolling serial covariance
        def calculate_roll_window(returns_window):
            if len(returns_window) < 2:
                return np.nan
            
            # Serial covariance: cov(r_t, r_{t-1})
            r_t = returns_window[1:]
            r_t_minus_1 = returns_window[:-1]
            
            cov = np.cov(r_t, r_t_minus_1)[0, 1]
            
            # Roll spread = 2 * sqrt(-cov)
            if cov >= 0:
                # No bid-ask bounce detected
                return 0
            
            roll_spread = 2 * np.sqrt(-cov)
            
            return roll_spread
        
        roll_spread_series = returns.rolling(
            window=self.roll_window,
            min_periods=self.roll_window
        ).apply(calculate_roll_window, raw=False)
        
        return roll_spread_series
    
    def _calculate_total_depth(self, orderbook_df: pd.DataFrame) -> pd.Series:
        """
        Calculate total depth (available liquidity).
        
        Total Depth = sum(bid_size_i + ask_size_i) for all levels
        
        Measures total available liquidity in the orderbook.
        Higher depth = easier to trade large sizes.
        """
        total_depth = 0
        
        for level in range(1, 6):
            bid_size_col = f'bid_size_{level}'
            ask_size_col = f'ask_size_{level}'
            
            if bid_size_col in orderbook_df.columns and ask_size_col in orderbook_df.columns:
                total_depth += orderbook_df[bid_size_col] + orderbook_df[ask_size_col]
        
        return total_depth
    
    def _calculate_depth_ratio(self, orderbook_df: pd.DataFrame) -> pd.Series:
        """
        Calculate depth ratio (liquidity imbalance).
        
        Depth Ratio = bid_size_1 / ask_size_1
        
        > 1: More bid liquidity (buyers waiting)
        < 1: More ask liquidity (sellers waiting)
        
        Different from depth imbalance (which is normalized).
        """
        if 'bid_size_1' not in orderbook_df.columns or 'ask_size_1' not in orderbook_df.columns:
            return pd.Series(np.nan, index=orderbook_df.index)
        
        # Avoid division by zero
        ask_size_safe = orderbook_df['ask_size_1'].replace(0, np.nan)
        
        depth_ratio = orderbook_df['bid_size_1'] / ask_size_safe
        
        return depth_ratio
    
    def get_feature_names(self) -> list[str]:
        """Get list of feature names produced."""
        base_names = [
            'bid_ask_spread',
            'relative_spread',
            'depth_weighted_spread',
            'kyles_lambda',
            'amihud_illiquidity',
            'roll_spread',
            'total_depth',
            'depth_ratio'
        ]
        
        # Optional features (need trade data)
        optional_names = [
            'effective_spread'
        ]
        
        return base_names + optional_names
