#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R261 CTP 真实语义修复 TDD 测试 (RED -> GREEN)

覆盖 core/trading/interfaces/ctp_trading_interface.py 与真实 ctpbee 1.6.9 语义对齐:
- P0-A: 回报 key 永久不匹配 (map 写入 "ctp.0_1_3" 带前缀 vs 回报反查 "0_1_3" 无前缀)
  - 实证: ctpbee/interface/ctp/td_api.py:548/551 (order_id="0_1_3") + constant.py:415 (local_order_id="ctp.0_1_3")
- P0-B: 首个回报先于 map 写入 (td_api.py:550-551 send_order 内同步预发 SUBMITTING 再返回 L552)
- P0-C: order_direction 无设置方 (order_models.py:55-84 无此字段, 仅 4 处引用) -> submit 必 AttributeError
- P0-D: buy_open 参数类型错误 (level.py:82-83 buy(price, volume, origin) 需 origin.exchange/.symbol; 且无 buy_open 方法)
- P0-E: cancel_order 签名不匹配 (level.py:310 cancel_order(cancel_req: CancelRequest) 单参, 项目传两参)

测试策略 (同 R257):
- 从文件 importlib 加载被测试模块
- FakeAction/FakeOrderData/FakeTradeData/FakeContract 贴近真实 ctpbee 语义:
  * FakeAction.buy/short/sell/cover 接受 (price, volume, origin), 返回 "ctp.0_1_3" (带 gateway 前缀)
  * FakeAction.cancel_order 接受单个 CancelRequest
  * FakeOrderData.order_id = "0_1_3" (无前缀, 同 td_api.py:377/549)
"""
import os
import sys
import types
import unittest
import importlib.util
from datetime import datetime
from unittest.mock import Mock

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
# 测试桩 (贴近真实 ctpbee 1.6.9 语义)
# ===========================================================================
class _FakeAction:
    """ctpbee action 桩: buy/short/sell/cover 接受 (price, volume, origin),
    返回 "ctp.0_1_3" (带 gateway 前缀, 同 constant.py:415); cancel 接受单参"""

    def __init__(self, return_id='ctp.0_1_3'):
        self.return_id = return_id
        self.calls = []
        self.cancel_calls = []

    def buy(self, price, volume, origin, **kwargs):
        self.calls.append(('buy', price, volume, origin))
        return self.return_id

    def short(self, price, volume, origin, **kwargs):
        self.calls.append(('short', price, volume, origin))
        return self.return_id

    def sell(self, price, volume, origin, **kwargs):
        self.calls.append(('sell', price, volume, origin))
        return self.return_id

    def cover(self, price, volume, origin, **kwargs):
        self.calls.append(('cover', price, volume, origin))
        return self.return_id

    def cancel_order(self, cancel_req):
        self.cancel_calls.append(cancel_req)


class _FakeApi:
    def __init__(self, action):
        self.action = action


class _FakeOrderData:
    """ctpbee OrderData 桩: order_id 无 gateway 前缀 (同 td_api.py:377/549)"""

    def __init__(self, order_id, status, volume, traded=0):
        self.order_id = order_id
        self.status = status
        self.volume = volume
        self.traded = traded


class _FakeTradeData:
    def __init__(self, order_id, price, volume):
        self.order_id = order_id
        self.price = price
        self.volume = volume


class _FakeContract:
    """ctpbee ContractData 桩: symbol/exchange"""

    def __init__(self, symbol, exchange='SHFE'):
        self.symbol = symbol
        self.exchange = exchange
        self.local_symbol = f"{symbol}.{exchange}"


class _FakeCancelRequest:
    """CancelRequest 桩: 断言 order_id 无前缀"""

    def __init__(self, symbol, exchange, order_id):
        self.symbol = symbol
        self.exchange = exchange
        self.order_id = order_id


# ===========================================================================
# 构造辅助
# ===========================================================================
def _make_order(order_id='ORD_LOCAL_001', order_type=OrderType.BUY):
    """构造本地订单 (不附加 order_direction! 验证 P0-C: 真实 Order 无此字段)"""
    now = datetime(2026, 8, 7, 10, 0, 0)
    order = Order(
        order_id=order_id,
        strategy_id='default',
        asset_type=AssetType.FUTURES,
        stock_code='rb2610',
        order_type=order_type,
        order_category=OrderCategory.MARKET,
        order_price=3800.0,
        order_quantity=10,
        order_status=OrderStatus.PENDING,
        create_time=now,
        update_time=now,
    )
    return order


def _make_interface(action=None):
    """构造已登录的 CTPTradingInterface (注入 FakeApi + Mock event_bus + 合约表)"""
    action = action or _FakeAction()
    interface = _ctp_module.CTPTradingInterface(_ctp_module.CTPConfig())
    interface._logged_in = True
    interface.event_bus = Mock()
    interface._api = _FakeApi(action)
    interface._contracts = {'rb2610.SHFE': _FakeContract('rb2610', 'SHFE')}
    return interface, action


# ===========================================================================
# 测试用例
# ===========================================================================
class TestR261CTPRealSemantics(unittest.TestCase):
    """R261: CTP 真实 ctpbee 语义修复"""

    # ---------------- P0-C: order_direction 缺失 ----------------
    def test_submit_works_without_order_direction(self):
        """真实 Order 无 order_direction 字段 -> submit 不抛 AttributeError (P0-C)"""
        interface, _ = _make_interface()
        order = _make_order()  # 无 order_direction 动态附加

        result = interface.submit_order(order)

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)

    # ---------------- P0-D: buy/short/sell/cover 取代 buy_open ----------------
    def test_submit_buy_uses_buy_method_with_origin(self):
        """BUY -> action.buy(price, volume, origin), origin 含 symbol/exchange (P0-D)"""
        interface, action = _make_interface()
        order = _make_order(OrderType.BUY)

        interface.submit_order(order)

        self.assertEqual(len(action.calls), 1)
        call_name, price, volume, origin = action.calls[0]
        self.assertEqual(call_name, 'buy')
        self.assertEqual(price, order.order_price)
        self.assertEqual(volume, order.order_quantity)
        self.assertEqual(getattr(origin, 'symbol', None), 'rb2610')
        self.assertIsNotNone(getattr(origin, 'exchange', None))

    def test_submit_short_uses_short_method(self):
        """SHORT -> action.short (P0-D + P0-C 映射)"""
        interface, action = _make_interface()
        order = _make_order(order_type=OrderType.SHORT)

        interface.submit_order(order)

        self.assertEqual(len(action.calls), 1)
        self.assertEqual(action.calls[0][0], 'short')

    def test_submit_sell_uses_sell_method(self):
        """SELL -> action.sell (P0-D: SELL 映射 SHORT/CLOSE -> sell 平仓)"""
        interface, action = _make_interface()
        order = _make_order(order_type=OrderType.SELL)

        interface.submit_order(order)

        self.assertEqual(len(action.calls), 1)
        self.assertEqual(action.calls[0][0], 'sell')

    def test_submit_cover_uses_cover_method(self):
        """COVER -> action.cover (P0-D)"""
        interface, action = _make_interface()
        order = _make_order(order_type=OrderType.COVER)

        interface.submit_order(order)

        self.assertEqual(len(action.calls), 1)
        self.assertEqual(action.calls[0][0], 'cover')

    # ---------------- P0-A: map key 归一化 ----------------
    def test_exchange_map_key_normalized_no_prefix(self):
        """P0-A: map key 剥离 'ctp.' 前缀 -> '0_1_3', 与回报侧 order_id 一致"""
        interface, action = _make_interface()
        order = _make_order()

        interface.submit_order(order)

        self.assertIn('0_1_3', interface._exchange_order_map)
        self.assertEqual(interface._exchange_order_map['0_1_3'], order.order_id)

    def test_on_order_data_matches_real_prefixless_id(self):
        """P0-A: 回报 order_id='0_1_3' (无前缀) 能匹配归一化后的 map key"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0_1_3'] = order.order_id

        interface._on_order_data(
            _FakeOrderData(order_id='0_1_3', status='ALLTRADED', volume=10, traded=10))

        self.assertEqual(order.order_status, OrderStatus.FILLED)

    def test_on_trade_data_matches_real_prefixless_id(self):
        """P0-A: 成交回报 order_id='0_1_3' 匹配 -> filled_quantity 累加"""
        interface, _ = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0_1_3'] = order.order_id

        interface._on_trade_data(
            _FakeTradeData(order_id='0_1_3', price=3800.0, volume=10))

        self.assertEqual(order.filled_quantity, 10)
        self.assertEqual(order.order_status, OrderStatus.FILLED)  # 10 >= 10 完全成交

    # ---------------- P0-E: cancel_order 单参 CancelRequest ----------------
    def test_cancel_order_passes_single_cancel_request(self):
        """P0-E: cancel_order 传单个 CancelRequest (非两参), order_id 无前缀"""
        interface, action = _make_interface()
        order = _make_order()
        interface._orders[order.order_id] = order
        interface._exchange_order_map['0_1_3'] = order.order_id

        result = interface.cancel_order(order.order_id)

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertEqual(len(action.cancel_calls), 1)
        cancel_req = action.cancel_calls[0]
        # 单参对象, 含 symbol/exchange/order_id
        self.assertEqual(getattr(cancel_req, 'symbol', None), 'rb2610')
        self.assertEqual(getattr(cancel_req, 'order_id', None), '0_1_3')


if __name__ == '__main__':
    unittest.main()
