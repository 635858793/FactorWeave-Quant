#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R253 交叉验证回归测试: 实盘交易域 P0 修复

覆盖 (R253 交叉验证实证 3 个 P0, 全部源码行号):
- P0-A: account_manager._get_trading_interface_for_account (:907 resolve(OrderExecutor))
        OrderExecutor 从未注册进容器 (service_bootstrap.py:61 仅 import),
        resolve 必抛 ValueError → 外层 :836-838 吞异常 → 账户资金/持仓同步链恒失败。
        修复: try_resolve 降级 (参照 R252b-F1 order_executor.py:731-747 模板),
        失败返回 None 时 warning + 返回 None, 不抛异常。
- P0-B: trading_panel 全文件无 _service_container 赋值 (:742-745 hasattr 判断恒短路)
        → CTP 账户加载逻辑不可达。修复: __init__ 增加 service_container 参数。
- P1-C: "实盘交易" tab 直连 TradingService (内存模拟盘) 下单永不落库。
        修复: _execute_trade_async / _on_cancel_order 增加 OrderService 优先分支
        (create_order + submit_order / cancel_order), OrderService 不可用时回退内存路径。

测试策略 (同 R252):
- 弹出 conftest 冲突 mock 条目, 用 importlib 从文件加载被测试模块
- order_executor 依赖的重型链 (order_repository / account_repository) 以 mock 模块隔离
- TradingPanel 构造测试: offscreen QApplication + patch UI 初始化方法
- TradeWorker 同步执行: patch QThread.start 直接调用 run()
- 本文件末尾恢复被 mock 污染的 sys.modules 条目
- R272 治理: 模块级覆盖 sys.modules 前保存原真实模块引用, 文件末尾恢复真实模块
  (而非 pop 移除), 消除后续文件类身份漂移
"""
import os
import sys
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R251/R252)
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

# order_executor 依赖的 DB/重型模块以 mock 隔离 (R253 仅测 try_resolve 降级路径)
for _mod in ('core.trading.order_repository', 'core.trading.account_repository'):
    sys.modules.pop(_mod, None)
from unittest.mock import MagicMock, patch  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# R272 治理: sys.modules 覆盖前保存原真实模块引用, 末尾恢复真实模块
# ---------------------------------------------------------------------------
_ORIGINAL_MODULES: dict = {}


def _install(name, mod):
    """R272 治理: 覆盖 sys.modules 前保存原真实模块引用 (存在才保存)"""
    if name in sys.modules and name not in _ORIGINAL_MODULES:
        _ORIGINAL_MODULES[name] = sys.modules[name]
    sys.modules[name] = mod


def _make_mock_module(name: str) -> MagicMock:
    _m = MagicMock()
    _m.__name__ = name
    _m.__file__ = f'<mock:{name}>'
    _install(name, _m)
    return _m


def _load_module_from_file(module_name: str, rel_path: str):
    """从文件加载模块 (绕过 sys.modules 中已注册的 mock)"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        module_name, os.path.join(ROOT, rel_path))
    module = importlib.util.module_from_spec(spec)
    _install(module_name, module)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# mock 重型依赖后, 真实加载被测试模块
# ---------------------------------------------------------------------------
_ORD_REPO = _make_mock_module('core.trading.order_repository')
_make_mock_module('core.trading.account_repository')

_am_module = _load_module_from_file(
    'core.trading.account_manager', 'core/trading/account_manager.py')
AccountManager = _am_module.AccountManager

import gui.widgets  # noqa: E402
_tp_module = _load_module_from_file(
    'gui.widgets.trading_panel', 'gui/widgets/trading_panel.py')
TradingPanel = _tp_module.TradingPanel

from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402
from PyQt5.QtCore import Qt  # noqa: E402
from decimal import Decimal  # noqa: E402

import unittest  # noqa: E402
import pytest  # noqa: E402

_APP = None


def _get_app():
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


_FULL_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


# ===========================================================================
# P0-A: account_manager._get_trading_interface_for_account try_resolve 降级
# ===========================================================================
class TestP0ATradingInterfaceFallback(unittest.TestCase):
    """P0-A: OrderExecutor 未注册时不得抛 ValueError, 应降级返回 None"""

    def _make_manager(self, container):
        manager = object.__new__(AccountManager)
        manager.service_container = container
        return manager

    def _make_account(self):
        account = MagicMock()
        account.account_id = 'ACC_001'
        account.account_type = '期货账户'
        return account

    def test_try_resolve_none_returns_none_without_exception(self):
        """容器 try_resolve 返回 None (OrderExecutor 未注册) → 返回 None 不抛异常"""
        container = MagicMock()
        container.try_resolve.return_value = None
        manager = self._make_manager(container)

        result = manager._get_trading_interface_for_account(self._make_account())

        # 修复前: resolve(OrderExecutor) 抛 ValueError → 测试异常; 修复后: None
        self.assertIsNone(result)

    def test_missing_try_resolve_falls_back_to_resolve_safely(self):
        """旧容器 mock 只有 resolve (无 try_resolve), resolve 抛 ValueError → 返回 None 不抛"""
        container = MagicMock()
        del container.try_resolve
        container.resolve.side_effect = ValueError(
            "Service OrderExecutor is not registered")
        manager = self._make_manager(container)

        result = manager._get_trading_interface_for_account(self._make_account())

        self.assertIsNone(result)


# ===========================================================================
# P0-B: trading_panel 构造可传 service_container
# ===========================================================================
class TestP0BServiceContainerInjection(unittest.TestCase):
    """P0-B: __init__ 增加 service_container 参数并赋值 _service_container"""

    def _make_panel(self, **kwargs):
        _get_app()
        with patch.object(TradingPanel, '_init_ui'), \
             patch.object(TradingPanel, '_connect_signals'), \
             patch.object(TradingPanel, '_subscribe_events'):
            return TradingPanel(
                trading_service=MagicMock(),
                event_bus=MagicMock(),
                **kwargs,
            )

    def test_constructor_accepts_service_container(self):
        """传 service_container → self._service_container 被赋值 (修复前 TypeError)"""
        container = MagicMock()
        panel = self._make_panel(service_container=container)
        self.assertIs(panel._service_container, container)

    def test_constructor_default_service_container_none(self):
        """旧调用不传 service_container → _service_container 为 None (兼容)"""
        panel = self._make_panel()
        self.assertIsNone(panel._service_container)


# ===========================================================================
# P1-C: OrderService 优先分支 (下单落库 / 撤单)
# ===========================================================================
class TestP1COrderServicePriority(unittest.TestCase):
    """P1-C: _execute_trade_async / _on_cancel_order 优先走 OrderService"""

    def _make_panel(self, container, account_id='ACC_001'):
        panel = types.SimpleNamespace()
        panel.trading_service = MagicMock()
        panel._service_container = container
        ctp_combo = MagicMock()
        ctp_combo.currentData.return_value = account_id
        panel.ctp_account_combo = ctp_combo
        panel._current_stock_code = '600000'
        panel._current_stock_name = '浦发银行'
        panel.buy_button = MagicMock()
        panel.sell_button = MagicMock()
        panel._on_trade_finished = MagicMock()
        panel._on_trade_error = MagicMock()
        panel._refresh_orders = MagicMock()
        # orders_table (撤单使用)
        panel.orders_table = MagicMock()
        selection_model = MagicMock()
        selected = MagicMock()
        selected.row.return_value = 0
        selection_model.selectedRows.return_value = [selected]
        panel.orders_table.selectionModel.return_value = selection_model
        order_id_item = MagicMock()
        order_id_item.data.return_value = _FULL_ID
        panel.orders_table.item.return_value = order_id_item
        return panel

    def test_execute_trade_uses_order_service_when_available(self):
        """OrderService 可解析且账户有效 → create_order + submit_order (落库)"""
        order_service = MagicMock()
        created_order = MagicMock()
        created_order.order_id = 'O_R253_001'
        order_service.create_order.return_value = created_order
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = self._make_panel(container)

        with patch('gui.widgets.trading_panel.QThread.start',
                   new=lambda self: self.run()):
            TradingPanel._execute_trade_async(
                panel, 'BUY', 100, Decimal('10.0'), False)

        # 修复前: 仅 trading_service.execute_buy_order (内存模拟), create_order 不被调用
        order_service.create_order.assert_called_once()
        order_service.submit_order.assert_called_once_with('O_R253_001')
        panel.trading_service.execute_buy_order.assert_not_called()

    def test_cancel_order_uses_order_service_when_available(self):
        """OrderService 可解析 → cancel_order 走 OrderService (修复前走 trading_service)"""
        order_service = MagicMock()
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = self._make_panel(container)

        with patch('gui.widgets.trading_panel.QMessageBox.question',
                   return_value=QMessageBox.Yes), \
             patch('gui.widgets.trading_panel.QMessageBox.information'), \
             patch('gui.widgets.trading_panel.QMessageBox.warning'), \
             patch('gui.widgets.trading_panel.QMessageBox.critical'):
            TradingPanel._on_cancel_order(panel)

        order_service.cancel_order.assert_called_once_with(_FULL_ID)
        panel.trading_service.cancel_order.assert_not_called()


# ===========================================================================
# P1-C: OrderService 不可用 → 回退内存模拟路径 (回归守卫)
# ===========================================================================
class TestP1CFallbackPath(unittest.TestCase):
    """P1-C: OrderService 不可用时回退 trading_service 内存路径, 不崩溃"""

    def _make_panel(self, container):
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
        panel.orders_table = MagicMock()
        selection_model = MagicMock()
        selected = MagicMock()
        selected.row.return_value = 0
        selection_model.selectedRows.return_value = [selected]
        panel.orders_table.selectionModel.return_value = selection_model
        order_id_item = MagicMock()
        order_id_item.data.return_value = _FULL_ID
        panel.orders_table.item.return_value = order_id_item
        return panel

    def test_execute_trade_falls_back_to_trading_service(self):
        """OrderService 不可用 → 回退 trading_service.execute_buy_order 不崩溃"""
        container = MagicMock()
        container.try_resolve.return_value = None
        panel = self._make_panel(container)

        async def fake_execute_buy(stock_code, stock_name, quantity, price=None):
            return MagicMock()

        panel.trading_service.execute_buy_order.side_effect = fake_execute_buy

        with patch('gui.widgets.trading_panel.QThread.start',
                   new=lambda self: self.run()):
            TradingPanel._execute_trade_async(
                panel, 'BUY', 100, Decimal('10.0'), False)

        panel.trading_service.execute_buy_order.assert_called_once()

    def test_cancel_order_falls_back_to_trading_service(self):
        """OrderService 不可用 → 回退 trading_service.cancel_order 不崩溃"""
        container = MagicMock()
        container.try_resolve.return_value = None
        panel = self._make_panel(container)
        panel.trading_service.cancel_order.return_value = (True, '已撤销')

        with patch('gui.widgets.trading_panel.QMessageBox.question',
                   return_value=QMessageBox.Yes), \
             patch('gui.widgets.trading_panel.QMessageBox.information'), \
             patch('gui.widgets.trading_panel.QMessageBox.warning'), \
             patch('gui.widgets.trading_panel.QMessageBox.critical'):
            TradingPanel._on_cancel_order(panel)

        panel.trading_service.cancel_order.assert_called_once_with(_FULL_ID)


# ---------------------------------------------------------------------------
# R272 治理: 恢复真实模块 (而非 pop 移除) — 消除后续文件类身份漂移
# ---------------------------------------------------------------------------
_ALL_INJECTED_NAMES = (
    'core.trading.order_repository',
    'core.trading.account_repository',
    'core.trading.account_manager',
    'gui.widgets.trading_panel',
)
for _name, _orig in _ORIGINAL_MODULES.items():
    sys.modules[_name] = _orig
for _name in _ALL_INJECTED_NAMES:
    if _name not in _ORIGINAL_MODULES:
        sys.modules.pop(_name, None)


if __name__ == '__main__':
    unittest.main()
