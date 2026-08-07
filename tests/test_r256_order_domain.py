#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R256 交叉验证回归测试: 订单域 P0 双实例割裂修复

覆盖 (R256 交叉验证实证, 全部源码行号):
- P0 断点B: OrderService 内部自建 OrderExecutor 与容器单例双实例割裂
      (order_service.py:58-65 _initialize 中 :63 直接
       self.executor = OrderExecutor(container, event_bus) 新建; CTP 连接注入的是
       容器单例, trading_service.py:1161-1167 经 try_resolve(OrderExecutor) →
       set_trading_interface 写入容器 executor 的 _account_interface_cache,
       order_executor.py:1499-1515)。下单走 OrderService 内部实例 →
       _account_interface_cache 恒空 → 真实 CTP 下单时新建无配置接口 → 连接失败。
      修复: _initialize 中 executor 改为容器 try_resolve 优先, 未注册/旧容器回退自建。
- P0 断点D: OrderExecutor.cancel_order 用 _get_trading_interface(asset_type)
      (注册接口, 未登录) 而非账户缓存, 撤单必失败 (order_executor.py:1333;
      submit 路径用 :1001 _get_trading_interface_for_account, :860-881 账户缓存优先)。
      修复: cancel_order 改为账户缓存优先, 未命中回退注册接口 (与 submit 路径对齐)。

测试策略 (同 R252/R253/R254/R255):
- 弹出 conftest 冲突 mock 条目, 用 importlib 从文件加载被测试模块
- order_repository / account_repository / account_manager / strategy_manager
  以 mock 模块隔离重型 DB 依赖
- OrderService 构造: MagicMock 容器 + MagicMock 事件总线
  (OrderValidator/Monitor/Analyzer 真实构造, 仅依赖 mock 的 order_repository)
- OrderExecutor.cancel_order: patch 类方法断言调用路径 (账户缓存优先 vs 注册接口回退)
- 本文件末尾恢复被 mock 污染的 sys.modules 条目
"""
import os
import sys
import unittest
from datetime import datetime

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R251/R252/R253/R254/R255)
# ---------------------------------------------------------------------------
_CONFTEST_MOCKS = [
    'gui', 'gui.dialogs', 'gui.dialogs.strategy_manager_dialog',
    'gui.widgets', 'gui.widgets.backtest_widget', 'gui.widgets.trading_panel',
    'gui.widgets.enhanced_ui', 'gui.widgets.enhanced_ui.order_book_widget',
    'gui.widgets.enhanced_ui.level2_data_panel', 'gui.widgets.performance',
    'gui.widgets.performance.tabs', 'gui.utils', 'gui.utils.responsive_helper',
    'core.ui', 'core.ui.panels', 'core.ui.panels.base_panel',
    'core.ui.panels.left_panel', 'core.ui.panels.middle_panel',
    'core.ui.panels.right_panel', 'core.ui.panels.bottom_panel',
    'core.ui.widgets', 'core.coordinators.main_window_coordinator',
]
for _mod in _CONFTEST_MOCKS:
    sys.modules.pop(_mod, None)

# order_service / order_executor 依赖的 DB 重型模块以 mock 隔离
for _mod in ('core.trading.order_repository', 'core.trading.account_repository',
             'core.trading.account_manager', 'core.trading.strategy_manager'):
    sys.modules.pop(_mod, None)
from unittest.mock import MagicMock, patch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_mock_module(name: str) -> MagicMock:
    _m = MagicMock()
    _m.__name__ = name
    _m.__file__ = f'<mock:{name}>'
    sys.modules[name] = _m
    return _m


def _load_module_from_file(module_name: str, rel_path: str):
    """从文件加载模块 (绕过 sys.modules 中已注册的 mock)"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# mock 重型依赖后, 真实加载被测试模块
# ---------------------------------------------------------------------------
_make_mock_module('core.trading.order_repository')
_make_mock_module('core.trading.account_repository')
_make_mock_module('core.trading.account_manager')
_make_mock_module('core.trading.strategy_manager')

# order_models: 用于构造 core Order 测试对象 (轻量, 仅依赖 core.plugin_types)
_om_module = _load_module_from_file(
    'core.trading.order_models', 'core/trading/order_models.py')
Order = _om_module.Order
CoreOrderType = _om_module.OrderType
CoreOrderCategory = _om_module.OrderCategory
CoreOrderStatus = _om_module.OrderStatus

_tt_module = _load_module_from_file(
    'core.trading.trading_types', 'core/trading/trading_types.py')
ExecutionResult = _tt_module.ExecutionResult
ExecutionStatus = _tt_module.ExecutionStatus

_am_module = _load_module_from_file(
    'core.trading.account_models', 'core/trading/account_models.py')

_oe_module = _load_module_from_file(
    'core.trading.order_executor', 'core/trading/order_executor.py')
OrderExecutor = _oe_module.OrderExecutor

_os_module = _load_module_from_file(
    'core.trading.order_service', 'core/trading/order_service.py')
OrderService = _os_module.OrderService

from core.plugin_types import AssetType  # noqa: E402


def _make_core_order(order_id='O_R256_001', account_id='ACC_001'):
    """构造 core Order 测试对象"""
    return Order(
        order_id=order_id,
        strategy_id='default',
        asset_type=AssetType.FUTURES,
        stock_code='rb2610',
        order_type=CoreOrderType.BUY,
        order_category=CoreOrderCategory.MARKET,
        order_price=3800.0,
        order_quantity=1,
        order_status=CoreOrderStatus.PENDING,
        create_time=datetime(2026, 8, 6, 10, 0, 0),
        update_time=datetime(2026, 8, 6, 10, 0, 0),
        account_id=account_id,
    )


def _make_executor():
    """真实 OrderExecutor 实例 (patch _initialize 跳过 OrderRepository/接口注册)"""
    with patch.object(OrderExecutor, '_initialize', return_value=None):
        executor = OrderExecutor(MagicMock(), MagicMock())
    executor.repository = MagicMock()
    executor.event_bus = MagicMock()
    executor._account_interface_cache = {}
    executor._trading_interfaces = {}
    return executor


# ===========================================================================
# 测试1/2/3 (P0 断点B): OrderService 复用容器 OrderExecutor 单例
# ===========================================================================
class TestOrderServiceReusesContainerExecutor(unittest.TestCase):
    """P0 断点B: OrderService._initialize 复用容器 OrderExecutor 单例 (消除双实例割裂)"""

    def test_container_resolved_executor_is_reused(self):
        """容器 try_resolve 返回 executor → self.executor is 该实例 (不再自建新实例)"""
        executor_singleton = MagicMock()
        container = MagicMock()
        container.try_resolve.return_value = executor_singleton

        service = OrderService(container, MagicMock())

        self.assertIs(service.executor, executor_singleton,
                      "必须复用容器单例 (connect_ctp_account 注入的目标)")

    def test_try_resolve_none_falls_back_to_new_executor(self):
        """容器 try_resolve 返回 None (OrderExecutor 未注册) → 自建 OrderExecutor 不抛异常"""
        container = MagicMock()
        container.try_resolve.return_value = None

        service = OrderService(container, MagicMock())

        self.assertIsNotNone(service.executor)
        self.assertIsInstance(service.executor, OrderExecutor)

    def test_legacy_container_without_try_resolve_falls_back(self):
        """旧容器无 try_resolve 属性 → 回退自建 OrderExecutor 不抛异常"""
        container = MagicMock()
        del container.try_resolve

        service = OrderService(container, MagicMock())

        self.assertIsNotNone(service.executor)
        self.assertIsInstance(service.executor, OrderExecutor)


# ===========================================================================
# 测试4/5 (P0 断点D): cancel_order 账户缓存优先, 未命中回退注册接口
# ===========================================================================
class TestCancelOrderUsesAccountCache(unittest.TestCase):
    """P0 断点D: cancel_order 账户缓存优先 (与 submit 路径对齐), 未命中回退注册接口"""

    def test_account_cache_interface_used_when_available(self):
        """账户缓存命中 → cancel_order 走 _get_trading_interface_for_account"""
        executor = _make_executor()
        executor.repository.get_order.return_value = _make_core_order()

        fake_account_iface = MagicMock()
        fake_account_iface.cancel_order.return_value = ExecutionResult(
            order_id='O_R256_001', status=ExecutionStatus.SUCCESS, message='ok')
        fake_asset_iface = MagicMock()
        fake_asset_iface.cancel_order.return_value = ExecutionResult(
            order_id='O_R256_001', status=ExecutionStatus.SUCCESS, message='ok')

        with patch.object(OrderExecutor, '_get_trading_interface_for_account',
                          return_value=fake_account_iface) as mock_account_lookup, \
             patch.object(OrderExecutor, '_get_trading_interface',
                          return_value=fake_asset_iface), \
             patch.object(OrderExecutor, '_unfreeze_order_funds', return_value=None):
            result = executor.cancel_order('O_R256_001')

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        mock_account_lookup.assert_called_once()
        fake_account_iface.cancel_order.assert_called_once_with('O_R256_001')
        fake_asset_iface.cancel_order.assert_not_called()

    def test_falls_back_to_asset_interface_when_no_account_cache(self):
        """账户缓存未命中 → 回退 _get_trading_interface(asset_type) (原逻辑)"""
        executor = _make_executor()
        executor.repository.get_order.return_value = _make_core_order()

        fake_asset_iface = MagicMock()
        fake_asset_iface.cancel_order.return_value = ExecutionResult(
            order_id='O_R256_001', status=ExecutionStatus.SUCCESS, message='ok')

        with patch.object(OrderExecutor, '_get_trading_interface_for_account',
                          return_value=None) as mock_account_lookup, \
             patch.object(OrderExecutor, '_get_trading_interface',
                          return_value=fake_asset_iface) as mock_asset_lookup, \
             patch.object(OrderExecutor, '_unfreeze_order_funds', return_value=None):
            result = executor.cancel_order('O_R256_001')

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        mock_account_lookup.assert_called_once()
        mock_asset_lookup.assert_called_once_with(AssetType.FUTURES)
        fake_asset_iface.cancel_order.assert_called_once_with('O_R256_001')


# ---------------------------------------------------------------------------
# 恢复被 mock 污染的 sys.modules 条目 (同 R252-R255 交叉审查教训)
# R256: mock 窗口内加载的消费者副本 (order_executor/order_service 等) 内部固化了对
# order_repository mock 的引用; order_validator/order_monitor/order_analyzer 在
# 副本加载时被真实导入且固化 mock order_repository 引用, 一并弹出, 避免污染
# 后续文件 (与 test_r254_trading_domain.py 同型污染)。
# ---------------------------------------------------------------------------
for _mod_name in ('core.trading.order_repository',
                  'core.trading.account_repository',
                  'core.trading.account_manager',
                  'core.trading.strategy_manager',
                  'core.trading.order_validator',
                  'core.trading.order_monitor',
                  'core.trading.order_analyzer',
                  'core.trading.order_models',
                  'core.trading.trading_types',
                  'core.trading.account_models',
                  'core.trading.order_executor',
                  'core.trading.order_service'):
    sys.modules.pop(_mod_name, None)


if __name__ == '__main__':
    unittest.main()
