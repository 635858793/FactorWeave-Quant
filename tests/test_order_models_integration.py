"""
OrderType 修复（SHORT/COVER）和 submit_orders_batch 字段修正集成测试

测试范围:
- OrderType 枚举完整性（BUY/SELL/SHORT/COVER）
- Order 模型字段正确性（stock_code/order_price/order_quantity 而非 symbol/price/quantity）
- 单笔提交事件字段正确性
- 批量提交事件一致性
- SHORT/COVER 集成验证
- 向后兼容性
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from core.trading.order_models import (
    Order, OrderType, OrderStatus, OrderCategory, OrderRequest, OrderQuery
)
from core.trading.order_executor import MockTradingInterface, OrderExecutor
from core.trading.trading_types import ExecutionResult, ExecutionStatus
from core.plugin_types import AssetType
from core.containers import ServiceContainer
from core.events import EventBus

pytestmark = [pytest.mark.order_model, pytest.mark.integration]


def _make_order(order_id, stock_code, order_type, order_price=10.0, order_quantity=100,
                asset_type=AssetType.STOCK_A, account_id='ACC001', strategy_id='STRAT001'):
    return Order(
        order_id=order_id,
        strategy_id=strategy_id,
        asset_type=asset_type,
        stock_code=stock_code,
        order_type=order_type,
        order_category=OrderCategory.LIMIT,
        order_price=order_price,
        order_quantity=order_quantity,
        order_status=OrderStatus.PENDING,
        create_time=datetime.now(),
        update_time=datetime.now(),
        account_id=account_id,
    )


class TestOrderTypeEnum:
    """OrderType 枚举完整性测试"""

    def test_order_type_has_all_four_values(self):
        members = {m.name for m in OrderType}
        assert members == {'BUY', 'SELL', 'SHORT', 'COVER'}, \
            f"OrderType 应为 {{BUY, SELL, SHORT, COVER}}, 实际: {members}"

    def test_order_type_short_cover_added(self):
        assert OrderType.SHORT.value == "short"
        assert OrderType.COVER.value == "cover"

    def test_order_type_from_string(self):
        assert OrderType("buy") == OrderType.BUY
        assert OrderType("sell") == OrderType.SELL
        assert OrderType("short") == OrderType.SHORT
        assert OrderType("cover") == OrderType.COVER

    def test_order_type_from_string_invalid_raises(self):
        with pytest.raises(ValueError):
            OrderType("nonexistent")


class TestOrderModelFields:
    """Order 模型字段完整性测试"""

    def test_order_has_required_fields(self):
        order = _make_order('ORD001', '000001', OrderType.BUY)
        required = {'stock_code', 'order_price', 'order_quantity', 'order_type', 'asset_type', 'account_id'}
        for field_name in required:
            assert hasattr(order, field_name), f"Order 缺少字段: {field_name}"
            assert getattr(order, field_name) is not None, f"Order 字段为 None: {field_name}"

    def test_order_does_not_have_bogus_fields(self):
        order = _make_order('ORD001', '000001', OrderType.BUY)
        assert not hasattr(order, 'symbol'), "Order 不应有 symbol 字段（应使用 stock_code）"
        assert not hasattr(order, 'direction'), "Order 不应有 direction 字段（应使用 order_type）"
        assert not hasattr(order, 'price'), "Order 不应有 price 字段（应使用 order_price）"
        assert not hasattr(order, 'quantity'), "Order 不应有 quantity 字段（应使用 order_quantity）"


class TestSubmitOrderEventFields:
    """单笔提交事件字段正确性测试"""

    @pytest.fixture
    def mock_components(self):
        container = MagicMock(spec=ServiceContainer)
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = MagicMock()
        return container, event_bus

    def test_submit_order_event_uses_stock_code_not_symbol(self, mock_components):
        container, event_bus = mock_components
        order = _make_order('ORD001', '000001', OrderType.BUY)
        mock_iface = MockTradingInterface()

        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.interfaces.xtp_pro_trading_interface.XTPProTradingInterface'):
                with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface'):
                    with patch('core.trading.interfaces.xtp_trading_interface.XTPTradingInterface'):
                        executor = OrderExecutor(container, event_bus)
                        executor.repository = MagicMock()
                        executor.repository.update_order = MagicMock()

        with patch.object(executor, '_get_trading_interface_for_account', return_value=mock_iface):
            with patch.object(executor, '_resolve_account_for_order', return_value=MagicMock()):
                with patch.object(executor, '_pre_trade_risk_check', return_value={'passed': True}):
                    executor.submit_order(order)

        call_args_list = event_bus.publish.call_args_list
        executed_calls = [c for c in call_args_list if c[0][0] == 'order.executed']
        assert len(executed_calls) >= 1, "应至少发布一次 order.executed 事件"

        first_call = executed_calls[0]
        kwargs = first_call[1]
        assert 'stock_code' in kwargs, "order.executed 事件应使用 stock_code 而非 symbol"
        assert 'symbol' not in kwargs, "order.executed 事件不应有 symbol"

    def test_submit_order_event_uses_order_price_not_price(self, mock_components):
        container, event_bus = mock_components
        order = _make_order('ORD001', '000001', OrderType.BUY, order_price=12.34)
        mock_iface = MockTradingInterface()

        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.interfaces.xtp_pro_trading_interface.XTPProTradingInterface'):
                with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface'):
                    with patch('core.trading.interfaces.xtp_trading_interface.XTPTradingInterface'):
                        executor = OrderExecutor(container, event_bus)
                        executor.repository = MagicMock()
                        executor.repository.update_order = MagicMock()

        with patch.object(executor, '_get_trading_interface_for_account', return_value=mock_iface):
            with patch.object(executor, '_resolve_account_for_order', return_value=MagicMock()):
                with patch.object(executor, '_pre_trade_risk_check', return_value={'passed': True}):
                    executor.submit_order(order)

        call_args_list = event_bus.publish.call_args_list
        executed_calls = [c for c in call_args_list if c[0][0] == 'order.executed']
        assert len(executed_calls) >= 1
        kwargs = executed_calls[0][1]
        assert 'order_price' in kwargs, "order.executed 事件应使用 order_price 而非 price"
        assert 'price' not in kwargs, "order.executed 事件不应有 price"
        assert kwargs['order_price'] == 12.34

    def test_submit_order_event_uses_order_quantity_not_quantity(self, mock_components):
        container, event_bus = mock_components
        order = _make_order('ORD001', '000001', OrderType.BUY, order_quantity=500)
        mock_iface = MockTradingInterface()

        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.interfaces.xtp_pro_trading_interface.XTPProTradingInterface'):
                with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface'):
                    with patch('core.trading.interfaces.xtp_trading_interface.XTPTradingInterface'):
                        executor = OrderExecutor(container, event_bus)
                        executor.repository = MagicMock()
                        executor.repository.update_order = MagicMock()

        with patch.object(executor, '_get_trading_interface_for_account', return_value=mock_iface):
            with patch.object(executor, '_resolve_account_for_order', return_value=MagicMock()):
                with patch.object(executor, '_pre_trade_risk_check', return_value={'passed': True}):
                    executor.submit_order(order)

        call_args_list = event_bus.publish.call_args_list
        executed_calls = [c for c in call_args_list if c[0][0] == 'order.executed']
        assert len(executed_calls) >= 1
        kwargs = executed_calls[0][1]
        assert 'order_quantity' in kwargs, "order.executed 事件应使用 order_quantity 而非 quantity"
        assert 'quantity' not in kwargs, "order.executed 事件不应有 quantity"
        assert kwargs['order_quantity'] == 500


class TestSubmitOrdersBatchEventFields:
    """批量提交事件字段一致性测试"""

    @pytest.fixture
    def mock_components(self):
        container = MagicMock(spec=ServiceContainer)
        event_bus = MagicMock(spec=EventBus)
        event_bus.publish = MagicMock()
        return container, event_bus

    def test_batch_and_single_use_same_field_names(self, mock_components):
        container, event_bus = mock_components
        orders = [_make_order(f'ORD{i}', f'00000{i}', OrderType.BUY) for i in range(2)]
        mock_iface = MockTradingInterface()

        repo = MagicMock()
        repo.update_order = MagicMock()
        repo.update_orders_batch = MagicMock()

        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.interfaces.xtp_pro_trading_interface.XTPProTradingInterface'):
                with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface'):
                    with patch('core.trading.interfaces.xtp_trading_interface.XTPTradingInterface'):
                        executor = OrderExecutor(container, event_bus)
                        executor.repository = repo

        with patch.object(executor, '_get_trading_interface_for_account', return_value=mock_iface):
            with patch.object(executor, '_resolve_account_for_order', return_value=MagicMock()):
                with patch.object(executor, '_pre_trade_risk_check', return_value={'passed': True}):
                    executor.submit_orders_batch(orders)

        call_args_list = event_bus.publish.call_args_list
        executed_calls = [c for c in call_args_list if c[0][0] == 'order.executed']
        assert len(executed_calls) >= 2, f"批量提交应为每个订单发布 order.executed，实际: {len(executed_calls)}"

        batch_calls = [c for c in call_args_list if c[0][0] == 'batch_orders_submitted_success']
        assert len(batch_calls) >= 1

        expected_fields = {'stock_code', 'order_price', 'order_quantity'}
        for i, call in enumerate(executed_calls):
            kwargs = call[1]
            for field in expected_fields:
                assert field in kwargs, f"批量 order.executed #{i} 缺少字段: {field}"

    def test_batch_emits_per_order_events(self, mock_components):
        container, event_bus = mock_components
        orders = [_make_order(f'ORD{i}', f'00000{i}', OrderType.BUY) for i in range(3)]
        mock_iface = MockTradingInterface()

        repo = MagicMock()
        repo.update_orders_batch = MagicMock()

        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.interfaces.xtp_pro_trading_interface.XTPProTradingInterface'):
                with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface'):
                    with patch('core.trading.interfaces.xtp_trading_interface.XTPTradingInterface'):
                        executor = OrderExecutor(container, event_bus)
                        executor.repository = repo

        with patch.object(executor, '_get_trading_interface_for_account', return_value=mock_iface):
            with patch.object(executor, '_resolve_account_for_order', return_value=MagicMock()):
                with patch.object(executor, '_pre_trade_risk_check', return_value={'passed': True}):
                    executor.submit_orders_batch(orders)

        call_args_list = event_bus.publish.call_args_list
        executed_calls = [c for c in call_args_list if c[0][0] == 'order.executed']
        assert len(executed_calls) == 3, \
            f"批量提交 3 个订单应发布 3 个 order.executed 事件，实际: {len(executed_calls)}"

        executed_order_ids = {c[1]['order_id'] for c in executed_calls}
        assert executed_order_ids == {'ORD0', 'ORD1', 'ORD2'}

    def test_batch_emits_aggregate_events(self, mock_components):
        container, event_bus = mock_components
        orders = [_make_order(f'ORD{i}', f'00000{i}', OrderType.BUY) for i in range(2)]
        mock_iface = MockTradingInterface()

        repo = MagicMock()
        repo.update_orders_batch = MagicMock()

        with patch('core.trading.order_executor.OrderRepository'):
            with patch('core.trading.interfaces.xtp_pro_trading_interface.XTPProTradingInterface'):
                with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface'):
                    with patch('core.trading.interfaces.xtp_trading_interface.XTPTradingInterface'):
                        executor = OrderExecutor(container, event_bus)
                        executor.repository = repo

        with patch.object(executor, '_get_trading_interface_for_account', return_value=mock_iface):
            with patch.object(executor, '_resolve_account_for_order', return_value=MagicMock()):
                with patch.object(executor, '_pre_trade_risk_check', return_value={'passed': True}):
                    executor.submit_orders_batch(orders)

        call_args_list = event_bus.publish.call_args_list
        success_calls = [c for c in call_args_list if c[0][0] == 'batch_orders_submitted_success']
        assert len(success_calls) >= 1, "应发布 batch_orders_submitted_success 事件"

        call = success_calls[0]
        kwargs = call[1]
        assert kwargs.get('count') == 2, f"count 应为 2，实际: {kwargs.get('count')}"
        assert len(kwargs.get('order_ids', [])) == 2, "order_ids 应包含 2 个订单ID"


class TestShortCoverIntegration:
    """SHORT/COVER 集成测试"""

    def test_order_with_type_short(self):
        order = _make_order('ORD_SHORT_001', '000001', OrderType.SHORT)
        assert order.order_type == OrderType.SHORT
        assert order.order_type.value == "short"

    def test_order_with_type_cover(self):
        order = _make_order('ORD_COVER_001', '000001', OrderType.COVER)
        assert order.order_type == OrderType.COVER
        assert order.order_type.value == "cover"

    def test_mock_is_sell_detects_short(self):
        interface = MockTradingInterface()
        short_order = _make_order('ORD_SHORT_001', '000001', OrderType.SHORT)

        result = interface.submit_order(short_order)
        assert result.status == ExecutionStatus.SUCCESS

        fill_records = interface.get_fill_records()
        assert len(fill_records) >= 1

        fill = fill_records[0]
        request_price = short_order.order_price
        filled_price = fill['fill_price']

        is_sell = short_order.order_type.value in ('sell', 'short')
        if is_sell:
            assert filled_price <= request_price, \
                f"SHORT 应作为卖出方向（滑点负向调整）: 请求价={request_price}, 成交价={filled_price}"
        else:
            assert filled_price >= request_price, \
                f"买入方向滑点应正向调整: 请求价={request_price}, 成交价={filled_price}"

    def test_mock_is_sell_detects_buy_as_not_sell(self):
        interface = MockTradingInterface()
        buy_order = _make_order('ORD_BUY_001', '000001', OrderType.BUY)

        result = interface.submit_order(buy_order)
        assert result.status == ExecutionStatus.SUCCESS

        fill_records = interface.get_fill_records()
        fill = fill_records[0]
        request_price = buy_order.order_price
        filled_price = fill['fill_price']

        is_sell = buy_order.order_type.value in ('sell', 'short')
        assert not is_sell, "BUY 不应被识别为卖出方向"
        assert filled_price >= request_price, \
            f"BUY 应为买入方向（滑点正向调整）: 请求价={request_price}, 成交价={filled_price}"

    def test_mock_is_sell_detects_sell(self):
        interface = MockTradingInterface()
        sell_order = _make_order('ORD_SELL_001', '000001', OrderType.SELL)

        result = interface.submit_order(sell_order)
        assert result.status == ExecutionStatus.SUCCESS

        fill_records = interface.get_fill_records()
        fill = fill_records[0]
        request_price = sell_order.order_price
        filled_price = fill['fill_price']

        is_sell = sell_order.order_type.value in ('sell', 'short')
        assert is_sell, "SELL 应被识别为卖出方向"
        assert filled_price <= request_price, \
            f"SELL 应为卖出方向（滑点负向调整）: 请求价={request_price}, 成交价={filled_price}"

    def test_mock_is_sell_detects_cover(self):
        interface = MockTradingInterface()
        cover_order = _make_order('ORD_COVER_001', '000001', OrderType.COVER)

        result = interface.submit_order(cover_order)
        assert result.status == ExecutionStatus.SUCCESS

        fill_records = interface.get_fill_records()
        fill = fill_records[0]
        request_price = cover_order.order_price
        filled_price = fill['fill_price']

        is_sell = cover_order.order_type.value in ('sell', 'short')
        assert not is_sell, "COVER（买回平仓）不应被识别为卖出方向"
        assert filled_price >= request_price, \
            f"COVER 应为买入方向（滑点正向调整）: 请求价={request_price}, 成交价={filled_price}"


class TestOrderTypeBackwardCompatibility:
    """向后兼容性测试"""

    def test_buy_sell_still_work(self):
        assert OrderType.BUY.value == "buy"
        assert OrderType.SELL.value == "sell"
        assert OrderType("buy") == OrderType.BUY
        assert OrderType("sell") == OrderType.SELL

        buy_order = _make_order('ORD_B_001', '000001', OrderType.BUY)
        sell_order = _make_order('ORD_S_001', '000001', OrderType.SELL)

        assert buy_order.order_type == OrderType.BUY
        assert sell_order.order_type == OrderType.SELL

        assert buy_order.stock_code == '000001'
        assert buy_order.order_price == 10.0
        assert buy_order.order_quantity == 100

    def test_from_dict_compatible_with_all_types(self):
        base_data = {
            'order_id': 'ORD_DICT_001',
            'strategy_id': 'STRAT001',
            'asset_type': 'stock_a',
            'stock_code': '000001',
            'order_category': 'limit',
            'order_price': 10.0,
            'order_quantity': 100,
            'order_status': 'pending',
            'create_time': datetime.now().isoformat(),
            'update_time': datetime.now().isoformat(),
        }

        for order_type_str in ('buy', 'sell', 'short', 'cover'):
            data = dict(base_data, order_type=order_type_str)
            order = Order.from_dict(data)
            assert order.order_type == OrderType(order_type_str), \
                f"from_dict 应正确解析 '{order_type_str}'，实际: {order.order_type}"
            assert order.stock_code == '000001'
            assert order.order_price == 10.0
            assert order.order_quantity == 100

    def test_order_request_accepts_all_four_types(self):
        for order_type in (OrderType.BUY, OrderType.SELL, OrderType.SHORT, OrderType.COVER):
            request = OrderRequest(
                strategy_id='STRAT001',
                asset_type=AssetType.STOCK_A,
                stock_code='000001',
                order_type=order_type,
                order_category=OrderCategory.LIMIT,
                order_price=10.0,
                order_quantity=100,
            )
            assert request.validate(), f"OrderRequest({order_type.value}) 验证应通过"
            assert request.order_type == order_type

    def test_order_query_supports_all_four_types(self):
        for order_type in (OrderType.BUY, OrderType.SELL, OrderType.SHORT, OrderType.COVER):
            query = OrderQuery(order_type=order_type)
            assert query.order_type == order_type, \
                f"OrderQuery 应支持 {order_type.value}"