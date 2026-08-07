#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R257 CTP 回报匹配 P0 修复 TDD 测试 (RED -> GREEN)

覆盖 core/trading/interfaces/ctp_trading_interface.py 结构性缺陷 (已交叉验证根因):
- P0: submit_order 丢弃 action 返回值 (:318-325) -> CTP 侧订单号从未捕获
- P0: _orders 以本地 UUID 为 key, 回调 :723/:764 以 CTP 侧 order_id 直查 -> 必失配
- P0: status_map 缺 'REJECTED' 且默认值 OrderStatus.UNKNOWN 不存在 (:735) -> AttributeError
- P1: order.traded_volume 字段名存疑 (:749) / ExecutionResult 未设 exchange_order_id (:332)
- P1: cancel_order 把本地 UUID 传给 ctpbee (:391) -> 撤单必失败
- P2: _orders/_exchange_order_map 无终态清理 (:98)

测试策略 (同 R255):
- 从文件 importlib 加载被测试模块 (不依赖包内 import 链)
- 环境若未安装 ctpbee: 注入最小 stub 模块到 sys.modules 保证类体类型注解可解析
  (ctp_trading_interface.py 类定义处参数注解会在模块加载时求值)
- FakeAction/FakeOrderData/FakeTradeData 鸭子类型桩, 不 import 真实 ctpbee 类型
"""
import os
import sys
import types
import unittest
import importlib.util
from datetime import datetime
from unittest.mock import Mock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# ctpbee stub (仅在环境未安装时注入, 保证模块类型注解可解析)
# ---------------------------------------------------------------------------
try:
    import ctpbee  # noqa: F401
    _CTPBEE_PRESENT = True
except ImportError:
    _CTPBEE_PRESENT = False

if not _CTPBEE_PRESENT:
    _ctp = types.ModuleType('ctpbee')
    _ctp.CtpbeeApi = type('CtpbeeApi', (), {})
    _ctp.CtpBee = type('CtpBee', (), {})
    _ctp.constant = types.ModuleType('ctpbee.constant')
    _ctp.constant.TickData = type('TickData', (), {})
    _ctp.constant.ContractData = type('ContractData', (), {})
    _ctp.constant.TradeData = type('TradeData', (), {})
    _ctp.constant.OrderData = type('OrderData', (), {})
    _ctp.constant.Direction = type('Direction', (), {'LONG': 'LONG', 'SHORT': 'SHORT'})
    _ctp.constant.Offset = type('Offset', (), {'OPEN': 'OPEN', 'CLOSE': 'CLOSE'})
    sys.modules['ctpbee'] = _ctp
    sys.modules['ctpbee.constant'] = _ctp.constant


def _load_module(module_name: str, rel_path: str):
    """从文件加载模块 (绕过 sys.modules 注册/污染)"""
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_ctp_module = _load_module(
    'core.trading.interfaces.ctp_trading_interface',
    'core/trading/interfaces/ctp_trading_interface.py')

from core.trading.order_models import Order, OrderType, OrderCategory, OrderStatus  # noqa: E402
from core.trading.trading_types import ExecutionStatus  # noqa: E402
from core.plugin_types import AssetType  # noqa: E402


# ===========================================================================
# 测试桩
# ===========================================================================
class _FakeAction:
    """ctpbee action 桩: 记录调用, buy_open 返回 ctpbee 风格订单号"""

    def __init__(self, return_id='0.1.3'):
        self.return_id = return_id
        self.buy_open_calls = []
        self.cancel_calls = []

    def buy_open(self, price, volume, symbol):
        self.buy_open_calls.append((price, volume, symbol))
        return self.return_id

    def cancel_order(self, symbol, order_id):
        self.cancel_calls.append((symbol, order_id))


class _FakeApi:
    def __init__(self, action):
        self.action = action


class _FakeOrderData:
    """ctpbee OrderData 桩 (attrs: order_id/status/volume/traded, 无 traded_volume)"""

    def __init__(self, order_id, status, volume, traded=0):
        self.order_id = order_id
        self.status = status
        self.volume = volume
        self.traded = traded


class _FakeTradeData:
    """ctpbee TradeData 桩 (attrs: order_id/price/volume)"""

    def __init__(self, order_id, price, volume):
        self.order_id = order_id
        self.price = price
        self.volume = volume


# ===========================================================================
# 构造辅助
# ===========================================================================
def _make_order(order_id='ORD_LOCAL_001'):
    """构造本地订单 (submit_order 使用的 order_direction/price 动态附加)"""
    now = datetime(2026, 8, 7, 10, 0, 0)
    order = Order(
        order_id=order_id,
        strategy_id='default',
        asset_type=AssetType.FUTURES,
        stock_code='rb2610',
        order_type=OrderType.BUY,
        order_category=OrderCategory.MARKET,
        order_price=3800.0,
        order_quantity=10,
        order_status=OrderStatus.PENDING,
        create_time=now,
        update_time=now,
    )
    order.order_direction = 'BUY'    # 接口层语义字段 (动态附加)
    order.price = order.order_price  # 接口层使用字段 (动态附加)
    return order


def _make_interface(action=None):
    """构造已登录的 CTPTradingInterface (注入 FakeApi + Mock event_bus)"""
    action = action or _FakeAction()
    interface = _ctp_module.CTPTradingInterface(_ctp_module.CTPConfig())
    interface._logged_in = True
    interface.event_bus = Mock()
    interface._api = _FakeApi(action)
    return interface, action


# ===========================================================================
# 测试用例
# ===========================================================================
class TestCTPMatchingFix(unittest.TestCase):
    """R257: CTP 回报匹配 P0 修复"""

    def test_submit_captures_exchange_order_id(self):
        """submit 捕获 CTP 侧订单号 -> _exchange_order_map 建立 交易所id -> 本地id"""
        interface, _ = _make_interface()
        order = _make_order()

        result = interface.submit_order(order)

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertIn('0.1.3', interface._exchange_order_map)
        self.assertEqual(interface._exchange_order_map['0.1.3'], order.order_id)

    def test_submit_result_has_exchange_order_id(self):
        """ExecutionResult.exchange_order_id 非 None (下游 order_executor.py:1041 依赖)"""
        interface, _ = _make_interface()

        result = interface.submit_order(_make_order())

        self.assertIsNotNone(result.exchange_order_id)
        self.assertEqual(result.exchange_order_id, '0.1.3')

    def test_on_order_data_matches_via_exchange_map(self):
        """CTP 侧回报 id 经 _exchange_order_map 反查 -> 本地订单状态更新 + 发布事件"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0.1.3'] = order.order_id

        interface._on_order_data(
            _FakeOrderData(order_id='0.1.3', status='ALLTRADED', volume=10, traded=10))

        self.assertEqual(order.order_status, OrderStatus.FILLED)
        self.assertTrue(interface.event_bus.publish.called)
        self.assertEqual(interface.event_bus.publish.call_args.args[0], 'order_status_changed')

    def test_on_order_data_unmatched_warns(self):
        """未匹配回报 -> warning 日志, 订单状态不变, 无事件发布"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order

        with patch('loguru.logger.warning') as mock_warn:
            interface._on_order_data(
                _FakeOrderData(order_id='UNKNOWN_CTP', status='ALLTRADED', volume=10, traded=10))

        self.assertEqual(order.order_status, OrderStatus.PENDING)
        interface.event_bus.publish.assert_not_called()
        mock_warn.assert_called()

    def test_on_order_data_rejected_mapped(self):
        """REJECTED 状态映射 (status_map 补键, 不抛 AttributeError)"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0.1.3'] = order.order_id

        interface._on_order_data(
            _FakeOrderData(order_id='0.1.3', status='REJECTED', volume=1, traded=0))

        self.assertEqual(order.order_status, OrderStatus.REJECTED)

    def test_on_order_data_traded_volume_compat(self):
        """ctpbee 字段名兼容: 无 traded_volume 只有 traded -> 不抛异常且事件正常发布"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0.1.3'] = order.order_id

        interface._on_order_data(
            _FakeOrderData(order_id='0.1.3', status='PARTTRADED', volume=10, traded=3))

        self.assertEqual(order.order_status, OrderStatus.PARTIALLY_FILLED)
        self.assertTrue(interface.event_bus.publish.called)

    def test_on_trade_data_fills_order(self):
        """成交回报经反查匹配 -> filled_quantity 累加 + 发布 order_filled"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0.1.3'] = order.order_id

        interface._on_trade_data(
            _FakeTradeData(order_id='0.1.3', price=3800.0, volume=5))

        self.assertEqual(order.filled_quantity, 5)
        self.assertTrue(interface.event_bus.publish.called)
        self.assertEqual(interface.event_bus.publish.call_args.args[0], 'order_filled')

    def test_cancel_order_uses_exchange_id(self):
        """撤单传 CTP 侧订单号而非本地 UUID"""
        interface, action = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0.1.3'] = order.order_id

        result = interface.cancel_order(order.order_id)

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(action.cancel_calls, [('rb2610', '0.1.3')])

    def test_terminal_state_cleans_maps(self):
        """终态 (FILLED) 后 _orders/_exchange_order_map 清理, 防内存累积"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0.1.3'] = order.order_id

        interface._on_order_data(
            _FakeOrderData(order_id='0.1.3', status='ALLTRADED', volume=10, traded=10))

        self.assertNotIn(order.order_id, interface._orders)
        self.assertNotIn('0.1.3', interface._exchange_order_map)


if __name__ == '__main__':
    unittest.main()
