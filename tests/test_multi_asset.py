"""
Unit tests for multi-asset trading support.
"""

import pytest
import numpy as np
from datetime import date, datetime

from src.core.multi_asset import (
    Asset,
    AssetClass,
    ForexPair,
    Option,
    OptionType,
    MarketData,
    BlackScholesCalculator,
    ImpliedVolatilityCalculator,
    AssetUniverseManager,
)


class TestAsset:
    """Tests for base Asset class."""
    
    def test_asset_creation(self):
        """Test basic asset creation."""
        asset = Asset(
            symbol="AAPL",
            asset_class=AssetClass.EQUITY,
            exchange="NASDAQ",
            currency="USD",
        )
        
        assert asset.symbol == "AAPL"
        assert asset.asset_class == AssetClass.EQUITY
        assert asset.exchange == "NASDAQ"
    
    def test_asset_to_dict(self):
        """Test asset serialization."""
        asset = Asset(
            symbol="BTC",
            asset_class=AssetClass.CRYPTO,
        )
        
        d = asset.to_dict()
        
        assert d['symbol'] == "BTC"
        assert d['asset_class'] == "crypto"


class TestForexPair:
    """Tests for forex pair."""
    
    def test_forex_creation(self):
        """Test forex pair creation."""
        pair = ForexPair(
            symbol="EUR/USD",
            base_currency="EUR",
            quote_currency="USD",
        )
        
        assert pair.symbol == "EUR/USD"
        assert pair.asset_class == AssetClass.FOREX
        assert pair.base_currency == "EUR"
    
    def test_inverse_symbol(self):
        """Test inverse pair symbol."""
        pair = ForexPair(
            symbol="EUR/USD",
            base_currency="EUR",
            quote_currency="USD",
        )
        
        assert pair.inverse_symbol == "USD/EUR"
    
    def test_pip_value_calculation(self):
        """Test pip value calculation."""
        pair = ForexPair(
            symbol="EUR/USD",
            base_currency="EUR",
            quote_currency="USD",
        )
        
        pip_value = pair.calculate_pip_value(10000, "USD")
        
        assert isinstance(pip_value, float)
        assert pip_value > 0


class TestOption:
    """Tests for options."""
    
    def test_option_creation(self):
        """Test option creation."""
        opt = Option(
            symbol="",  # Will be auto-generated
            underlying="AAPL",
            option_type=OptionType.CALL,
            strike=150.0,
            expiration=date(2025, 12, 19),
        )
        
        assert opt.asset_class == AssetClass.OPTION
        assert opt.is_call
        assert not opt.is_put
        assert len(opt.symbol) > 0  # Auto-generated
    
    def test_intrinsic_value_call(self):
        """Test intrinsic value for call."""
        opt = Option(
            symbol="",
            underlying="AAPL",
            option_type=OptionType.CALL,
            strike=150.0,
            expiration=date(2025, 12, 19),
        )
        
        # In the money
        assert opt.intrinsic_value(160.0) == 10.0
        
        # Out of the money
        assert opt.intrinsic_value(140.0) == 0.0
    
    def test_intrinsic_value_put(self):
        """Test intrinsic value for put."""
        opt = Option(
            symbol="",
            underlying="AAPL",
            option_type=OptionType.PUT,
            strike=150.0,
            expiration=date(2025, 12, 19),
        )
        
        # In the money
        assert opt.intrinsic_value(140.0) == 10.0
        
        # Out of the money
        assert opt.intrinsic_value(160.0) == 0.0
    
    def test_moneyness(self):
        """Test moneyness calculation."""
        opt = Option(
            symbol="",
            underlying="AAPL",
            option_type=OptionType.CALL,
            strike=150.0,
            expiration=date(2025, 12, 19),
        )
        
        moneyness = opt.moneyness(160.0)
        
        assert moneyness > 1.0  # ITM call
    
    def test_days_to_expiration(self):
        """Test days to expiration."""
        opt = Option(
            symbol="",
            underlying="AAPL",
            option_type=OptionType.CALL,
            strike=150.0,
            expiration=date(2025, 12, 19),
        )
        
        days = opt.days_to_expiration(date(2025, 12, 1))
        
        assert days == 18


class TestMarketData:
    """Tests for market data."""
    
    def test_market_data_creation(self):
        """Test market data creation."""
        asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
        
        data = MarketData(
            asset=asset,
            timestamp=datetime.now(),
            price=150.0,
            bid=149.95,
            ask=150.05,
            volume=1000000,
        )
        
        assert data.price == 150.0
        assert data.bid == 149.95
    
    def test_mid_price(self):
        """Test mid price calculation."""
        asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
        
        data = MarketData(
            asset=asset,
            timestamp=datetime.now(),
            price=150.0,
            bid=149.90,
            ask=150.10,
        )
        
        assert data.mid_price == 150.0
    
    def test_spread(self):
        """Test spread calculation."""
        asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
        
        data = MarketData(
            asset=asset,
            timestamp=datetime.now(),
            price=150.0,
            bid=149.90,
            ask=150.10,
        )
        
        assert data.spread == 0.20
    
    def test_spread_bps(self):
        """Test spread in basis points."""
        asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
        
        data = MarketData(
            asset=asset,
            timestamp=datetime.now(),
            price=150.0,
            bid=149.90,
            ask=150.10,
        )
        
        # 0.20 / 150.0 * 10000 = 13.33 bps
        assert abs(data.spread_bps - 13.33) < 0.1


class TestBlackScholesCalculator:
    """Tests for Black-Scholes calculations."""
    
    def test_call_option_price(self):
        """Test call option pricing."""
        price = BlackScholesCalculator.calculate_option_price(
            option_type=OptionType.CALL,
            S=100.0,  # Spot
            K=100.0,  # Strike
            T=1.0,    # 1 year
            r=0.05,   # 5% risk-free
            sigma=0.2,  # 20% vol
        )
        
        assert isinstance(price, float)
        assert price > 0  # ATM call has value
        assert price < 100  # Less than spot
    
    def test_put_option_price(self):
        """Test put option pricing."""
        price = BlackScholesCalculator.calculate_option_price(
            option_type=OptionType.PUT,
            S=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            sigma=0.2,
        )
        
        assert isinstance(price, float)
        assert price > 0
    
    def test_greeks_call(self):
        """Test Greeks calculation for call."""
        greeks = BlackScholesCalculator.calculate_greeks(
            option_type=OptionType.CALL,
            S=100.0,
            K=100.0,
            T=1.0,
            r=0.05,
            sigma=0.2,
        )
        
        # Call delta should be 0-1
        assert 0 < greeks.delta < 1
        
        # Gamma should be positive
        assert greeks.gamma > 0
        
        # Theta should be negative (time decay)
        assert greeks.theta < 0
        
        # Vega should be positive
        assert greeks.vega > 0
    
    def test_put_call_parity(self):
        """Test put-call parity relationship."""
        S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.2
        
        call_price = BlackScholesCalculator.calculate_option_price(
            OptionType.CALL, S, K, T, r, sigma
        )
        
        put_price = BlackScholesCalculator.calculate_option_price(
            OptionType.PUT, S, K, T, r, sigma
        )
        
        # Put-call parity: C - P = S - K*exp(-rT)
        lhs = call_price - put_price
        rhs = S - K * np.exp(-r * T)
        
        assert abs(lhs - rhs) < 0.01  # Should be approximately equal


class TestImpliedVolatilityCalculator:
    """Tests for implied volatility calculation."""
    
    def test_iv_calculation_call(self):
        """Test IV calculation for call."""
        # First get a price with known vol
        S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.25
        
        option_price = BlackScholesCalculator.calculate_option_price(
            OptionType.CALL, S, K, T, r, sigma
        )
        
        # Now recover the vol
        iv = ImpliedVolatilityCalculator.calculate_iv(
            option_type=OptionType.CALL,
            option_price=option_price,
            S=S, K=K, T=T, r=r,
            initial_guess=0.3,
        )
        
        assert iv is not None
        assert abs(iv - sigma) < 0.01  # Should recover original vol


class TestAssetUniverseManager:
    """Tests for asset universe manager."""
    
    def test_add_asset(self):
        """Test adding assets."""
        manager = AssetUniverseManager()
        
        asset = Asset(symbol="AAPL", asset_class=AssetClass.EQUITY)
        manager.add_asset(asset)
        
        assert "AAPL" in manager.assets
    
    def test_get_assets_by_class(self):
        """Test filtering by asset class."""
        manager = AssetUniverseManager()
        
        manager.add_asset(Asset("AAPL", AssetClass.EQUITY))
        manager.add_asset(Asset("BTC", AssetClass.CRYPTO))
        manager.add_asset(Asset("EUR/USD", AssetClass.FOREX))
        
        equities = manager.get_assets_by_class(AssetClass.EQUITY)
        
        assert len(equities) == 1
        assert equities[0].symbol == "AAPL"
    
    def test_get_summary(self):
        """Test universe summary."""
        manager = AssetUniverseManager()
        
        manager.add_asset(Asset("AAPL", AssetClass.EQUITY))
        manager.add_asset(Asset("MSFT", AssetClass.EQUITY))
        manager.add_asset(Asset("BTC", AssetClass.CRYPTO))
        
        summary = manager.get_summary()
        
        assert summary['equity'] == 2
        assert summary['crypto'] == 1
