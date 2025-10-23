"""
PnLTracker: Clean PnL accounting with realized vs unrealized tracking

Provides transparent profit/loss accounting with proper mark-to-market
using VWAP, mid-price, or last price.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class Position:
    """Current position state"""
    qty: float = 0.0
    avg_price: float = 0.0


class PnLTracker:
    """
    Track realized and unrealized PnL separately.
    
    Marks positions to VWAP if available, else to midprice (bid/ask),
    else to last price for clean accounting.
    """

    def __init__(self):
        self.position = Position()
        self.realized_pnl = 0.0
        self.fees = 0.0
        self.marks: List[float] = []  # store marks for auditing

    def on_fill(self, side: str, qty: float, price: float, fee: float = 0.0):
        """
        Record a fill (buy or sell).
        
        Args:
            side: "buy" or "sell"
            qty: Quantity filled
            price: Fill price
            fee: Transaction fee
        """
        self.fees += fee
        if side.lower() == "buy":
            new_qty = self.position.qty + qty
            if new_qty != 0:
                self.position.avg_price = (
                    (self.position.avg_price * self.position.qty + price * qty) / new_qty
                )
            self.position.qty = new_qty
        elif side.lower() == "sell":
            qty_to_close = min(self.position.qty, qty)
            self.realized_pnl += (price - self.position.avg_price) * qty_to_close
            self.position.qty -= qty_to_close
            # If over-sell (net short) is not supported, ignore extra qty

    def mark(
        self,
        last: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        vwap: Optional[float] = None
    ) -> float:
        """
        Mark position to market.
        
        Priority: VWAP > mid-price (bid/ask) > last
        
        Args:
            last: Last traded price
            bid: Current bid price
            ask: Current ask price
            vwap: VWAP price
            
        Returns:
            Unrealized PnL
        """
        if self.position.qty == 0:
            self.marks.append(0.0)
            return 0.0

        if vwap is not None:
            mark_price = vwap
        elif bid is not None and ask is not None:
            mark_price = 0.5 * (bid + ask)
        elif last is not None:
            mark_price = last
        else:
            raise ValueError("No price input provided for mark-to-market")

        unrealized = (mark_price - self.position.avg_price) * self.position.qty
        self.marks.append(unrealized)
        return unrealized

    def snapshot(self) -> dict:
        """
        Get current PnL snapshot.
        
        Returns:
            Dict with realized, unrealized, fees, position details
        """
        current_unrealized = self.marks[-1] if self.marks else 0.0
        return {
            "realized": round(self.realized_pnl - self.fees, 2),
            "unrealized": round(current_unrealized, 2),
            "fees": round(self.fees, 2),
            "qty": self.position.qty,
            "avg_price": round(self.position.avg_price, 4),
        }
