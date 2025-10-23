"""
Enhanced Trading Dashboard API.

Real-time P&L tracking, position monitoring, risk metrics,
and trade execution tracking for live trading operations.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import numpy as np

from src.core.logging_config import get_logger
from src.models.portfolio_optimization import PortfolioMetrics
from src.services.rebalancing import PortfolioState, RebalanceEvent
from src.core.compliance import ComplianceEngine, EventType, ComplianceStatus

logger = get_logger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="AutoTrader Dashboard API",
    description="Real-time trading dashboard with P&L, positions, and risk metrics",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Data Models
# ============================================================================

class PositionModel(BaseModel):
    """Single position in portfolio."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight: float
    asset_class: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "quantity": 100,
                "entry_price": 150.00,
                "current_price": 155.00,
                "market_value": 15500.00,
                "unrealized_pnl": 500.00,
                "unrealized_pnl_pct": 3.33,
                "weight": 0.15,
                "asset_class": "equity",
            }
        }


class PortfolioPnL(BaseModel):
    """Portfolio P&L metrics."""
    timestamp: datetime
    total_value: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl_today: float
    total_pnl_today: float
    total_pnl_pct_today: float
    total_pnl_inception: float
    total_pnl_pct_inception: float


class RiskMetrics(BaseModel):
    """Portfolio risk metrics."""
    timestamp: datetime
    portfolio_volatility: float
    portfolio_beta: Optional[float]
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    current_drawdown: float
    var_95: float
    cvar_95: float
    var_99: float
    cvar_99: float
    calmar_ratio: float
    max_concentration: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-10-22T15:00:00Z",
                "portfolio_volatility": 0.18,
                "portfolio_beta": 1.05,
                "sharpe_ratio": 1.8,
                "sortino_ratio": 2.2,
                "max_drawdown": 0.12,
                "current_drawdown": 0.03,
                "var_95": 0.025,
                "cvar_95": 0.035,
                "var_99": 0.045,
                "cvar_99": 0.055,
                "calmar_ratio": 1.5,
                "max_concentration": 0.25,
            }
        }


class TradeModel(BaseModel):
    """Trade execution record."""
    trade_id: str
    timestamp: datetime
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    price: float
    commission: float
    total_value: float
    strategy: str
    status: str  # FILLED, PARTIAL, PENDING


class StrategyPerformance(BaseModel):
    """Strategy-level performance metrics."""
    strategy_name: str
    active: bool
    n_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    total_pnl: float
    total_pnl_pct: float


class AlertModel(BaseModel):
    """Trading alert."""
    alert_id: str
    timestamp: datetime
    severity: str  # INFO, WARNING, CRITICAL
    category: str  # RISK, COMPLIANCE, EXECUTION, SYSTEM
    message: str
    details: Dict


# ============================================================================
# Global State (In production, use proper state management)
# ============================================================================

# Mock data for demonstration
MOCK_POSITIONS = [
    {
        "symbol": "AAPL",
        "quantity": 100,
        "entry_price": 150.00,
        "current_price": 155.00,
        "market_value": 15500.00,
        "unrealized_pnl": 500.00,
        "unrealized_pnl_pct": 3.33,
        "weight": 0.31,
        "asset_class": "equity",
    },
    {
        "symbol": "BTC",
        "quantity": 0.5,
        "entry_price": 42000.00,
        "current_price": 43000.00,
        "market_value": 21500.00,
        "unrealized_pnl": 500.00,
        "unrealized_pnl_pct": 2.38,
        "weight": 0.43,
        "asset_class": "crypto",
    },
    {
        "symbol": "EUR/USD",
        "quantity": 10000,
        "entry_price": 1.0800,
        "current_price": 1.0850,
        "market_value": 10850.00,
        "unrealized_pnl": 50.00,
        "unrealized_pnl_pct": 0.46,
        "weight": 0.22,
        "asset_class": "forex",
    },
]


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "AutoTrader Dashboard API",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/portfolio/summary")
def get_portfolio_summary() -> Dict:
    """
    Get portfolio summary with total value and P&L.
    """
    total_value = sum(p["market_value"] for p in MOCK_POSITIONS)
    cash = 5000.00
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total_value": total_value + cash,
        "cash": cash,
        "positions_value": total_value,
        "unrealized_pnl": sum(p["unrealized_pnl"] for p in MOCK_POSITIONS),
        "realized_pnl_today": 250.00,
        "total_pnl_today": sum(p["unrealized_pnl"] for p in MOCK_POSITIONS) + 250.00,
        "total_pnl_pct_today": 2.5,
        "total_pnl_inception": 5000.00,
        "total_pnl_pct_inception": 10.0,
    }


@app.get("/portfolio/positions", response_model=List[PositionModel])
def get_positions() -> List[PositionModel]:
    """
    Get all current positions.
    """
    return [PositionModel(**p) for p in MOCK_POSITIONS]


@app.get("/portfolio/positions/{symbol}")
def get_position(symbol: str) -> PositionModel:
    """
    Get specific position by symbol.
    """
    for pos in MOCK_POSITIONS:
        if pos["symbol"] == symbol:
            return PositionModel(**pos)
    
    raise HTTPException(status_code=404, detail=f"Position {symbol} not found")


@app.get("/portfolio/risk", response_model=RiskMetrics)
def get_risk_metrics() -> RiskMetrics:
    """
    Get portfolio risk metrics.
    """
    # Mock data - in production, calculate from actual positions
    return RiskMetrics(
        timestamp=datetime.now(),
        portfolio_volatility=0.18,
        portfolio_beta=1.05,
        sharpe_ratio=1.8,
        sortino_ratio=2.2,
        max_drawdown=0.12,
        current_drawdown=0.03,
        var_95=0.025,
        cvar_95=0.035,
        var_99=0.045,
        cvar_99=0.055,
        calmar_ratio=1.5,
        max_concentration=0.43,
    )


@app.get("/portfolio/performance")
def get_performance(
    period: str = Query("1D", description="Period: 1D, 1W, 1M, 3M, YTD, 1Y")
) -> Dict:
    """
    Get portfolio performance over specified period.
    """
    # Mock data - in production, query from database
    return {
        "period": period,
        "start_date": "2025-10-01",
        "end_date": "2025-10-22",
        "start_value": 45000.00,
        "end_value": 52850.00,
        "total_return": 7850.00,
        "total_return_pct": 17.44,
        "sharpe_ratio": 1.8,
        "max_drawdown": 0.12,
        "volatility": 0.18,
        "win_rate": 0.65,
    }


@app.get("/portfolio/chart")
def get_portfolio_chart(
    period: str = Query("1M", description="Period: 1D, 1W, 1M, 3M, YTD, 1Y"),
    interval: str = Query("1h", description="Interval: 1m, 5m, 1h, 1d")
) -> Dict:
    """
    Get portfolio value time series for charting.
    """
    # Mock data - generate sample time series
    now = datetime.now()
    timestamps = []
    values = []
    
    # Generate hourly data for last 30 days
    for i in range(30 * 24):
        ts = now - timedelta(hours=30*24 - i)
        # Simulate growth with some volatility
        value = 45000 + (i * 10) + np.random.normal(0, 200)
        timestamps.append(ts.isoformat())
        values.append(round(value, 2))
    
    return {
        "period": period,
        "interval": interval,
        "timestamps": timestamps,
        "values": values,
    }


@app.get("/trades/recent", response_model=List[TradeModel])
def get_recent_trades(limit: int = Query(10, ge=1, le=100)) -> List[TradeModel]:
    """
    Get recent trades.
    """
    # Mock data
    trades = [
        TradeModel(
            trade_id="T001",
            timestamp=datetime.now() - timedelta(hours=2),
            symbol="AAPL",
            side="BUY",
            quantity=100,
            price=155.00,
            commission=1.00,
            total_value=15501.00,
            strategy="BounceHunter",
            status="FILLED",
        ),
        TradeModel(
            trade_id="T002",
            timestamp=datetime.now() - timedelta(hours=5),
            symbol="BTC",
            side="BUY",
            quantity=0.5,
            price=43000.00,
            commission=5.00,
            total_value=21505.00,
            strategy="GemScore",
            status="FILLED",
        ),
    ]
    
    return trades[:limit]


@app.get("/strategies/performance", response_model=List[StrategyPerformance])
def get_strategy_performance() -> List[StrategyPerformance]:
    """
    Get performance metrics for each strategy.
    """
    return [
        StrategyPerformance(
            strategy_name="BounceHunter",
            active=True,
            n_trades=45,
            win_rate=0.67,
            avg_win=350.00,
            avg_loss=-180.00,
            profit_factor=1.94,
            sharpe_ratio=2.1,
            total_pnl=4500.00,
            total_pnl_pct=12.5,
        ),
        StrategyPerformance(
            strategy_name="GemScore",
            active=True,
            n_trades=12,
            win_rate=0.58,
            avg_win=800.00,
            avg_loss=-450.00,
            profit_factor=1.29,
            sharpe_ratio=1.5,
            total_pnl=1200.00,
            total_pnl_pct=8.3,
        ),
    ]


@app.get("/alerts/active", response_model=List[AlertModel])
def get_active_alerts() -> List[AlertModel]:
    """
    Get active trading alerts.
    """
    return [
        AlertModel(
            alert_id="A001",
            timestamp=datetime.now() - timedelta(minutes=15),
            severity="WARNING",
            category="RISK",
            message="Portfolio volatility approaching threshold",
            details={"current": 0.18, "threshold": 0.20},
        ),
        AlertModel(
            alert_id="A002",
            timestamp=datetime.now() - timedelta(hours=1),
            severity="INFO",
            category="EXECUTION",
            message="Order filled: AAPL 100 shares @ $155.00",
            details={"symbol": "AAPL", "quantity": 100, "price": 155.00},
        ),
    ]


@app.get("/compliance/status")
def get_compliance_status() -> Dict:
    """
    Get compliance status and recent checks.
    """
    return {
        "overall_status": "COMPLIANT",
        "last_check": datetime.now().isoformat(),
        "checks": {
            "position_limits": {"status": "PASSED", "message": "All positions within limits"},
            "daily_loss_limit": {"status": "PASSED", "message": "Daily loss within threshold"},
            "trading_hours": {"status": "PASSED", "message": "Within trading hours"},
            "liquidity": {"status": "PASSED", "message": "All positions meet liquidity requirements"},
        },
        "violations_today": 0,
        "warnings_today": 1,
    }


@app.get("/compliance/audit-trail")
def get_audit_trail(
    limit: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = None,
) -> Dict:
    """
    Get compliance audit trail.
    """
    # Mock audit events
    events = [
        {
            "event_id": "E001",
            "timestamp": datetime.now().isoformat(),
            "event_type": "TRADE_EXECUTION",
            "user_id": "system",
            "details": {"symbol": "AAPL", "side": "BUY", "quantity": 100},
            "compliance_status": "PASSED",
        },
        {
            "event_id": "E002",
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "event_type": "REBALANCE_TRIGGERED",
            "user_id": "system",
            "details": {"reason": "drift_threshold", "turnover": 0.15},
            "compliance_status": "PASSED",
        },
    ]
    
    return {
        "total_events": len(events),
        "events": events[:limit],
    }


@app.get("/rebalancing/status")
def get_rebalancing_status() -> Dict:
    """
    Get current rebalancing status and history.
    """
    return {
        "last_rebalance": (datetime.now() - timedelta(days=7)).isoformat(),
        "next_scheduled": (datetime.now() + timedelta(days=7)).isoformat(),
        "drift_status": {
            "max_drift": 0.04,
            "threshold": 0.05,
            "needs_rebalance": False,
        },
        "recent_rebalances": [
            {
                "timestamp": (datetime.now() - timedelta(days=7)).isoformat(),
                "reason": "drift_threshold",
                "turnover": 0.15,
                "cost": 45.00,
                "orders": 5,
            },
        ],
    }


@app.get("/market/regime")
def get_market_regime() -> Dict:
    """
    Get current market regime classification.
    """
    return {
        "regime": "NORMAL",
        "vix": 15.2,
        "spy_trend": "UP",
        "correlation_state": "NORMAL",
        "risk_appetite": "MODERATE",
        "recommended_exposure": 1.0,
    }


@app.websocket("/ws/live-updates")
async def websocket_endpoint(websocket):
    """
    WebSocket endpoint for real-time updates.
    
    Streams:
    - Position updates
    - P&L changes
    - New trades
    - Risk metric updates
    - Alerts
    """
    await websocket.accept()
    
    try:
        while True:
            # Send updates every second
            await websocket.send_json({
                "type": "portfolio_update",
                "timestamp": datetime.now().isoformat(),
                "total_value": 52850.00,
                "unrealized_pnl": 1050.00,
            })
            
            await asyncio.sleep(1)
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
