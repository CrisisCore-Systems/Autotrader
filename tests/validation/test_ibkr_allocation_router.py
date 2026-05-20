import pytest
import asyncio

from execution.routing.router import StrategyAllocationRouter, AllocationError

class DummyAdapter:
    def __init__(self, ctx_map, kill_switch=False):
        self._ctx_map = ctx_map
        self._global_kill_active = kill_switch
        self.submitted = []
    def _get_account_ctx(self, acc):
        return self._ctx_map[acc]
    async def submit_order(self, account_id, symbol, qty, side, **kwargs):
        self.submitted.append((account_id, symbol, qty, side, kwargs))
        return f"ORDER-{account_id}-{symbol}-{qty}-{side}"

@pytest.mark.asyncio
async def test_fixed_equal_split():
    ctx_map = {
        'A': {'net_liquidation_value': 10000, 'maintenance_margin': 1000},
        'B': {'net_liquidation_value': 10000, 'maintenance_margin': 1000},
    }
    router = StrategyAllocationRouter(DummyAdapter(ctx_map))
    shards = router.calculate_shards(7, 'FIXED_EQUAL', ['A', 'B'])
    assert shards['A'] == 3
    assert shards['B'] == 4
    order_ids = await router.route_order('AMD', 7, 'BUY', 'FIXED_EQUAL', ['A', 'B'])
    assert len(order_ids) == 2
    assert all(oid.startswith('ORDER-') for oid in order_ids)

@pytest.mark.asyncio
async def test_dynamic_nlv_split():
    ctx_map = {
        'A': {'net_liquidation_value': 20000, 'maintenance_margin': 1000},
        'B': {'net_liquidation_value': 10000, 'maintenance_margin': 1000},
    }
    router = StrategyAllocationRouter(DummyAdapter(ctx_map))
    shards = router.calculate_shards(9, 'DYNAMIC_NLV', ['A', 'B'])
    # A gets 6, B gets 3
    assert shards['A'] == 6
    assert shards['B'] == 3
    order_ids = await router.route_order('NVDA', 9, 'SELL', 'DYNAMIC_NLV', ['A', 'B'])
    assert len(order_ids) == 2

@pytest.mark.asyncio
async def test_margin_interlock_blocks():
    ctx_map = {
        'A': {'net_liquidation_value': 10000, 'maintenance_margin': 9500},
        'B': {'net_liquidation_value': 10000, 'maintenance_margin': 1000},
    }
    router = StrategyAllocationRouter(DummyAdapter(ctx_map))
    # A's cushion will be below threshold after trade
    with pytest.raises(AllocationError):
        await router.route_order('TSLA', 10, 'BUY', 'FIXED_EQUAL', ['A', 'B'])

@pytest.mark.asyncio
async def test_kill_switch_blocks():
    ctx_map = {
        'A': {'net_liquidation_value': 10000, 'maintenance_margin': 1000},
        'B': {'net_liquidation_value': 10000, 'maintenance_margin': 1000},
    }
    router = StrategyAllocationRouter(DummyAdapter(ctx_map, kill_switch=True))
    with pytest.raises(AllocationError):
        await router.route_order('AAPL', 10, 'BUY', 'FIXED_EQUAL', ['A', 'B'])
