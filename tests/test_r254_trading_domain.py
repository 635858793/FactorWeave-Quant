#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R254 交叉验证回归测试: 实盘交易域 P0/P1 修复

覆盖 (R254 交叉验证实证, 全部源码行号):
- P0: service_bootstrap.py:61 仅 `from core.trading.order_executor import OrderExecutor`,
      全文无 register → account_manager.py:911-917 try_resolve(OrderExecutor) 恒 None
      → 资金/持仓同步链 (account_manager.py:817-892) 实际仍不可用 (R253 只防崩溃未打通)。
      修复: _register_trading_services 补 register_factory(OrderExecutor, ..., SINGLETON)。
- P1: trading_panel.py:680 下单恒 asset_type=AssetType.FUTURES → 股票账户订单写入
      futures_orders DuckDB 池 (database_service.py:532-534 池名按 asset_type 派生)。
      修复: 有 ctp_account_id(期货/期权账户) → FUTURES, 否则股票上下文 → STOCK_A。
- P1: account_manager.py:934-955 跨类访问 order_executor._trading_interfaces 私有属性
      并改写接口字段 (第二份重复实现, order_executor.py:440-489 已有
      _load_account_info_to_interfaces)。修复: OrderExecutor 公开 get_trading_interface,
      OrderService 委托, account_manager 经 OrderService 获取。
- P1: trading_panel.py:1184-1229 _refresh_orders 仅读 trading_service 内存模拟盘,
      不展示真实落库订单。修复: OrderService 可解析且查询非空时切换真实数据源。

测试策略 (同 R252/R253):
- 弹出 conftest 冲突 mock 条目, 用 importlib 从文件加载被测试模块
- order_repository / account_repository 以 mock 模块隔离重型 DB 依赖
- TradingPanel 构造/方法测试: offscreen QApplication + SimpleNamespace 面板 + MagicMock 容器
- TradeWorker 同步执行: patch QThread.start 直接调用 run()
- 本文件末尾恢复被 mock 污染的 sys.modules 条目
"""
import os
import sys
import types
import unittest
from datetime import datetime
from decimal import Decimal

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R251/R252/R253)
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

# order_executor / order_service / account_manager 依赖的 DB 重型模块以 mock 隔离
for _mod in ('core.trading.order_repository', 'core.trading.account_repository'):
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

# order_models: 用于构造 core Order 测试对象 (轻量, 仅依赖 core.plugin_types)
_om_module = _load_module_from_file(
    'core.trading.order_models', 'core/trading/order_models.py')
Order = _om_module.Order
CoreOrderType = _om_module.OrderType
CoreOrderCategory = _om_module.OrderCategory
CoreOrderStatus = _om_module.OrderStatus

_oe_module = _load_module_from_file(
    'core.trading.order_executor', 'core/trading/order_executor.py')
OrderExecutor = _oe_module.OrderExecutor

_os_module = _load_module_from_file(
    'core.trading.order_service', 'core/trading/order_service.py')
OrderService = _os_module.OrderService

_am_module = _load_module_from_file(
    'core.trading.account_manager', 'core/trading/account_manager.py')
AccountManager = _am_module.AccountManager

import gui.widgets  # noqa: E402
_tp_module = _load_module_from_file(
    'gui.widgets.trading_panel', 'gui/widgets/trading_panel.py')
TradingPanel = _tp_module.TradingPanel
# 修复前不存在 _select_asset_type_for_account (TDD 红阶段容错, 测试方法内断言 None 触发失败)
_select_asset_type_for_account = getattr(
    _tp_module, '_select_asset_type_for_account', None)

from core.plugin_types import AssetType  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402
from PyQt5.QtCore import Qt  # noqa: E402

import pytest  # noqa: E402

_APP = None


def _get_app():
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


# ===========================================================================
# 测试1 (P0): service_bootstrap 注册 OrderExecutor 单例
# ===========================================================================
class TestBootstrapOrderExecutorRegistration(unittest.TestCase):
    """P0: _register_trading_services 必须注册 OrderExecutor (此前仅 import 无 register)"""

    def _trading_services_source(self) -> str:
        src_path = os.path.join(ROOT, 'core/services/service_bootstrap.py')
        with open(src_path, encoding='utf-8') as f:
            src = f.read()
        start = src.index('def _register_trading_services')
        end = src.index('def _setup_order_monitoring')
        return src[start:end]

    def test_trading_services_registers_order_executor_factory(self):
        """源码断言: _register_trading_services 区域内存在 OrderExecutor 注册调用"""
        src = self._trading_services_source()
        self.assertIn('OrderExecutor', src, "P0: OrderExecutor 仅 import 未注册")
        self.assertRegex(src, r'register_factory\(\s*OrderExecutor',
                         "P0: 缺少 register_factory(OrderExecutor ...) 注册")

    def test_order_executor_resolvable_from_container_after_registration(self):
        """注册模式等效验证: register_factory(SINGLETON) 后容器可 resolve 出单例实例"""
        from core.containers.service_container import ServiceContainer
        from core.containers.service_registry import ServiceScope
        with patch.object(OrderExecutor, '_initialize', return_value=None):
            container = ServiceContainer()
            container.register_factory(
                OrderExecutor,
                lambda: OrderExecutor(container, MagicMock()),
                scope=ServiceScope.SINGLETON,
            )
            instance = container.resolve(OrderExecutor)
            self.assertIs(instance, container.resolve(OrderExecutor),
                          "SINGLETON 作用域必须复用同一实例")


# ===========================================================================
# 测试2 (P1): account_manager 经 OrderService 公开接口获取交易接口
# ===========================================================================
class TestAccountManagerOrderServiceDelegation(unittest.TestCase):
    """P1: _get_trading_interface_for_account 委托 OrderService.get_trading_interface,
    消除对 OrderExecutor._trading_interfaces 的跨类私有访问"""

    def _make_manager(self, container):
        manager = object.__new__(AccountManager)
        manager.service_container = container
        return manager

    def _make_account(self, account_type='期货账户'):
        account = MagicMock()
        account.account_id = 'ACC_001'
        account.account_type = account_type
        return account

    def test_uses_order_service_public_interface(self):
        """经 OrderService.get_trading_interface 获取接口 (修复前无此调用链)"""
        order_service = MagicMock()
        interface = MagicMock()
        order_service.get_trading_interface.return_value = interface
        container = MagicMock()
        container.try_resolve.return_value = order_service
        manager = self._make_manager(container)

        result = manager._get_trading_interface_for_account(self._make_account())

        self.assertIs(result, interface)
        # 修复前: try_resolve(OrderExecutor) + 直接访问 _trading_interfaces
        # 运行时批次防御: account_manager._get_trading_interface_for_account 内部
        # 延迟 import (account_manager.py:905), 实际解析的是 sys.modules 当前批次
        # 的 OrderService, 可能与收集阶段绑定的批次不同 (跨文件 sys.modules 分裂) →
        # 断言以运行时批次为准, 而非模块级绑定类。
        runtime_order_service = sys.modules['core.trading.order_service'].OrderService
        container.try_resolve.assert_called_once_with(runtime_order_service)
        order_service.get_trading_interface.assert_called_once_with(AssetType.FUTURES)

    def test_stock_account_uses_stock_a_asset_type(self):
        """股票账户 → OrderService.get_trading_interface(STOCK_A)"""
        order_service = MagicMock()
        container = MagicMock()
        container.try_resolve.return_value = order_service
        manager = self._make_manager(container)

        manager._get_trading_interface_for_account(self._make_account('股票账户'))

        order_service.get_trading_interface.assert_called_once_with(AssetType.STOCK_A)

    def test_order_service_unavailable_returns_none(self):
        """OrderService 不可解析 → 返回 None 不抛异常 (保留 R253 降级语义)"""
        container = MagicMock()
        container.try_resolve.return_value = None
        manager = self._make_manager(container)

        result = manager._get_trading_interface_for_account(self._make_account())

        self.assertIsNone(result)

    def test_missing_try_resolve_falls_back_to_resolve_safely(self):
        """旧容器 mock 只有 resolve (无 try_resolve) → 返回 None 不抛"""
        container = MagicMock()
        del container.try_resolve
        container.resolve.side_effect = ValueError(
            "Service OrderService is not registered")
        manager = self._make_manager(container)

        result = manager._get_trading_interface_for_account(self._make_account())

        self.assertIsNone(result)


# ===========================================================================
# 测试3 (P1): OrderExecutor.get_trading_interface 公开薄封装
# ===========================================================================
class TestOrderExecutorPublicInterface(unittest.TestCase):
    """P1: OrderExecutor.get_trading_interface 返回 _trading_interfaces.get 结果"""

    def _make_executor(self):
        executor = object.__new__(OrderExecutor)
        executor._trading_interfaces = {AssetType.FUTURES: object()}
        return executor

    def test_public_method_exists(self):
        """公开方法存在 (修复前无 get_trading_interface)"""
        self.assertTrue(callable(getattr(OrderExecutor, 'get_trading_interface', None)))

    def test_returns_interface_for_registered_asset_type(self):
        executor = self._make_executor()
        self.assertIsNotNone(executor.get_trading_interface(AssetType.FUTURES))

    def test_returns_none_for_unregistered_asset_type(self):
        executor = self._make_executor()
        self.assertIsNone(executor.get_trading_interface(AssetType.STOCK_A))


# ===========================================================================
# 测试4 (P1): _refresh_orders 数据源切换 OrderService
# ===========================================================================
class TestRefreshOrdersOrderServicePriority(unittest.TestCase):
    """P1: OrderService 可解析且查询非空 → 真实落库订单; 否则回退内存路径"""

    def _make_panel(self, container, ctp_account_id='ACC_001'):
        """真实 TradingPanel 实例 (patch UI 初始化), 保留真实 _render_core_orders 方法"""
        _get_app()
        with patch.object(TradingPanel, '_init_ui'), \
             patch.object(TradingPanel, '_connect_signals'), \
             patch.object(TradingPanel, '_subscribe_events'):
            panel = TradingPanel(
                trading_service=MagicMock(),
                event_bus=MagicMock(),
                service_container=container,
            )
        panel.trading_service.get_active_orders.return_value = []
        panel.orders_table = MagicMock()
        if ctp_account_id is not None:
            ctp_combo = MagicMock()
            ctp_combo.currentData.return_value = ctp_account_id
            panel.ctp_account_combo = ctp_combo
        return panel

    def _make_core_order(self):
        return Order(
            order_id='O_R254_001',
            strategy_id='default',
            asset_type=AssetType.STOCK_A,
            stock_code='600000',
            order_type=CoreOrderType.BUY,
            order_category=CoreOrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=CoreOrderStatus.SUBMITTED,
            create_time=datetime(2026, 8, 6, 10, 0, 0),
            update_time=datetime(2026, 8, 6, 10, 0, 0),
        )

    def test_uses_order_service_when_available_with_results(self):
        """OrderService 可解析且返回非空 → 读 order_service.get_active_orders(account_id)"""
        order_service = MagicMock()
        order_service.get_active_orders.return_value = [self._make_core_order()]
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = self._make_panel(container)

        TradingPanel._refresh_orders(panel)

        order_service.get_active_orders.assert_called_once_with('ACC_001')
        panel.trading_service.get_active_orders.assert_not_called()
        # col0 完整 order_id 存入 UserRole 供撤单使用 (保持 R252-F3 模式)
        first_set = panel.orders_table.setItem.call_args_list[0]
        self.assertEqual(first_set.args[0], 0)
        self.assertEqual(first_set.args[1], 0)
        self.assertEqual(first_set.args[2].data(Qt.UserRole), 'O_R254_001')

    def test_falls_back_when_order_service_unavailable(self):
        """OrderService 不可解析 → 回退 trading_service 内存路径, 不崩溃"""
        container = MagicMock()
        container.try_resolve.return_value = None
        panel = self._make_panel(container)

        TradingPanel._refresh_orders(panel)

        panel.trading_service.get_active_orders.assert_called_once()

    def test_falls_back_when_order_service_returns_empty(self):
        """OrderService 返回空列表 → 回退 trading_service 内存路径"""
        order_service = MagicMock()
        order_service.get_active_orders.return_value = []
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = self._make_panel(container)

        TradingPanel._refresh_orders(panel)

        order_service.get_active_orders.assert_called_once_with('ACC_001')
        panel.trading_service.get_active_orders.assert_called_once()


# ===========================================================================
# 测试5 (P1): asset_type 按账户上下文选择
# ===========================================================================
class TestAssetTypeSelection(unittest.TestCase):
    """P1: 有 ctp_account_id(期货/期权账户) → FUTURES; 股票上下文 → STOCK_A"""

    def test_stock_context_uses_stock_a(self):
        """无 CTP 账户 (股票上下文) → STOCK_A (修复前硬编码 FUTURES)"""
        self.assertIs(_select_asset_type_for_account(None), AssetType.STOCK_A)
        self.assertIs(_select_asset_type_for_account(''), AssetType.STOCK_A)

    def test_ctp_futures_account_uses_futures(self):
        """有 CTP 账户 → FUTURES"""
        self.assertIs(_select_asset_type_for_account('ACC_001'), AssetType.FUTURES)

    def test_trade_worker_order_request_asset_type_futures_for_ctp_account(self):
        """集成: CTP 账户下单 → OrderRequest.asset_type=FUTURES (落 futures 池正确)"""
        _get_app()
        order_service = MagicMock()
        created = MagicMock()
        created.order_id = 'O_R254_002'
        order_service.create_order.return_value = created
        result = MagicMock()
        result.status = 'SUCCESS'
        order_service.submit_order.return_value = result
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = types.SimpleNamespace()
        panel.trading_service = MagicMock()
        panel._service_container = container
        ctp_combo = MagicMock()
        ctp_combo.currentData.return_value = 'ACC_001'
        panel.ctp_account_combo = ctp_combo
        panel._current_stock_code = '600000'
        panel._current_stock_name = '浦发银行'
        panel.buy_button = MagicMock()
        panel.sell_button = MagicMock()
        panel._on_trade_finished = MagicMock()
        panel._on_trade_error = MagicMock()
        panel._refresh_orders = MagicMock()

        with patch('gui.widgets.trading_panel.QThread.start',
                   new=lambda self: self.run()):
            TradingPanel._execute_trade_async(
                panel, 'BUY', 100, Decimal('10.0'), False)

        request = order_service.create_order.call_args[0][0]
        self.assertEqual(request.asset_type, AssetType.FUTURES)

    def test_trade_worker_falls_back_when_no_ctp_account(self):
        """无 CTP 账户 (currentData None) → 内存模拟路径, 不解析 OrderService"""
        _get_app()
        container = MagicMock()
        panel = types.SimpleNamespace()
        panel.trading_service = MagicMock()
        panel._service_container = container
        ctp_combo = MagicMock()
        ctp_combo.currentData.return_value = None
        panel.ctp_account_combo = ctp_combo
        panel._current_stock_code = '600000'
        panel._current_stock_name = '浦发银行'
        panel.buy_button = MagicMock()
        panel.sell_button = MagicMock()
        panel._on_trade_finished = MagicMock()
        panel._on_trade_error = MagicMock()
        panel._refresh_orders = MagicMock()

        async def fake_execute_buy(stock_code, stock_name, quantity, price=None):
            return MagicMock()

        panel.trading_service.execute_buy_order.side_effect = fake_execute_buy

        with patch('gui.widgets.trading_panel.QThread.start',
                   new=lambda self: self.run()):
            TradingPanel._execute_trade_async(
                panel, 'BUY', 100, Decimal('10.0'), False)

        panel.trading_service.execute_buy_order.assert_called_once()
        container.try_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# 恢复被 mock 污染的 sys.modules 条目 (同 R252/R253 交叉审查教训)
# R255: mock 窗口 (:84) 内 _load_module_from_file 加载的消费者副本
# (order_service/account_manager/order_executor 等) 内部固化了对 order_repository
# mock 的引用, 仅 pop order_repository 不够 —— 副本残留 sys.modules 会污染
# 后续文件 (如 test_r255_order_repository.py 构造 OrderService 拿到 mock repository)。
# 一并弹出全部副本, 让后续文件重新加载真实模块。
# ---------------------------------------------------------------------------
for _mod_name in ('core.trading.order_repository',
                  'core.trading.account_repository',
                  'core.trading.order_service',
                  'core.trading.order_models',
                  'core.trading.order_executor',
                  'core.trading.account_manager',
                  'gui.widgets.trading_panel'):
    sys.modules.pop(_mod_name, None)


if __name__ == '__main__':
    unittest.main()
