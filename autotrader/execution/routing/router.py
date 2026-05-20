import math
import logging
from typing import Dict, Any, List
from autotrader.execution.adapters import Order, OrderSide, OrderType

logger = logging.getLogger("AutoTrader.Router")


def _resolve_order_side(side: str) -> OrderSide:
    normalized = str(side or "").strip().upper()
    if normalized == "BUY":
        return OrderSide.BUY
    if normalized == "SELL":
        return OrderSide.SELL
    raise AllocationError(f"Unsupported order side: {side}")


def _resolve_order_type(raw_order_type: Any) -> OrderType:
    normalized = str(raw_order_type or "MKT").strip().upper()
    mapping = {
        "MKT": OrderType.MARKET,
        "MARKET": OrderType.MARKET,
        "LMT": OrderType.LIMIT,
        "LIMIT": OrderType.LIMIT,
        "STP": OrderType.STOP,
        "STOP": OrderType.STOP,
        "STP LMT": OrderType.STOP_LIMIT,
        "STOP_LIMIT": OrderType.STOP_LIMIT,
        "IOC": OrderType.IOC,
        "FOK": OrderType.FOK,
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise AllocationError(f"Unsupported order type: {raw_order_type}") from exc

class AllocationError(Exception):
    """Raised when an order allocation fails risk or structural criteria."""
    pass

class StrategyAllocationRouter:
    def __init__(self, adapter: Any, safety_cushion_threshold: float = 0.15):
        self.adapter = adapter
        self.safety_cushion_threshold = safety_cushion_threshold

    def calculate_shards(self, total_qty: int, policy: str, target_accounts: List[str]) -> Dict[str, int]:
        """Computes integer-safe share sharding footprints across accounts."""
        if total_qty <= 0:
            raise AllocationError("Total allocation quantity must be positive.")
        if not target_accounts:
            raise AllocationError("Allocation target sub-account list cannot be empty.")

        shards = {}
        
        # Policy: Fixed Equal Weighting Split
        if policy == "FIXED_EQUAL":
            base_share = total_qty // len(target_accounts)
            for acc in target_accounts[:-1]:
                shards[acc] = base_share
            # Final account sweeps up the modulo remainder
            shards[target_accounts[-1]] = total_qty - sum(shards.values())
            
        # Policy: Dynamic Net Liquidation Value (NLV)
        elif policy == "DYNAMIC_NLV":
            nlv_map = {}
            for acc in target_accounts:
                ctx = self.adapter._get_account_ctx(acc)
                # Fallback safely to 1.0 to avoid division by zero anomalies in test harnesses
                nlv_map[acc] = max(float(ctx.get("net_liquidation_value", 1.0)), 1.0)
                
            total_nlv = sum(nlv_map.values())
            running_sum = 0
            
            for acc in target_accounts[:-1]:
                weight = nlv_map[acc] / total_nlv
                allocated = math.floor(total_qty * weight)
                shards[acc] = allocated
                running_sum += allocated
                
            shards[target_accounts[-1]] = total_qty - running_sum
        else:
            raise AllocationError(f"Unsupported allocation policy profile: {policy}")

        return shards

    async def route_order(self, symbol: str, total_qty: int, side: str, policy: str, target_accounts: List[str], **kwargs) -> List[str]:
        """
        Orchestrates cross-account validation fencing and dynamic order sharding execution.
        Rolls back the transaction block if any target leg violates risk limits.
        """
        # 1. Enforce global kill switch check from the underlying adapter context
        if getattr(self.adapter, "_global_kill_active", False):
            raise AllocationError("Route rejected: Underlying adapter master kill switch is currently active.")

        # 2. Compute candidate order footprints
        shards = self.calculate_shards(total_qty, policy, target_accounts)
        
        # 3. Pre-Trade Margin Interlock Evaluation Pass
        for acc, qty in shards.items():
            if qty <= 0:
                continue
                
            ctx = self.adapter._get_account_ctx(acc)
            nlv = float(ctx.get("net_liquidation_value", 1.0))
            current_maint_margin = float(ctx.get("maintenance_margin", 0.0))
            
            # Simple simulation wrapper (Can be extended via specific risk matrices)
            simulated_post_trade_margin = current_maint_margin + (qty * 0.10) # 10% structural margin assumption proxy
            
            if nlv > 0:
                cushion_ratio = (nlv - simulated_post_trade_margin) / nlv
                if cushion_ratio < self.safety_cushion_threshold:
                    logger.error(f"Margin interlock tripped for {acc}. Simulated Cushion: {cushion_ratio:.4f} < SLA: {self.safety_cushion_threshold}")
                    raise AllocationError(f"Pre-trade margin isolation fence breach detected on sub-account context: {acc}")

        # 4. Transaction Block Cleared -> Deploy down-path to instrumented submit pipeline
        order_ids = []
        try:
            order_side = _resolve_order_side(side)
            order_type = _resolve_order_type(kwargs.get("orderType"))
            for acc, qty in shards.items():
                if qty > 0:
                    order = Order(
                        order_id="",
                        symbol=symbol,
                        side=order_side,
                        order_type=order_type,
                        quantity=float(qty),
                        price=kwargs.get("price"),
                        stop_price=kwargs.get("stop_price"),
                        time_in_force=str(kwargs.get("time_in_force", "DAY")),
                        metadata={
                            "account_id": acc,
                            "ibkr_account_id": acc,
                            "ibkr_transmit": kwargs.get("ibkr_transmit", True),
                        },
                    )
                    submitted_order = await self.adapter.submit_order(order)
                    order_ids.append(str(submitted_order.order_id))
            return order_ids
        except Exception as e:
            logger.critical(f"FATAL EXHAUSTION DURING ROUTING DISPATCH: {str(e)}. System integrity intervention required.")
            raise AllocationError(f"Downstream transaction submission cascade failure: {str(e)}")
