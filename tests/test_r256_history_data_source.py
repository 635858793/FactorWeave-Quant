#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R256 TDD 回归测试: 交易历史表格双数据源 (P1)

覆盖 (R256 主智能体交叉验证, 源码行号实证):
- P1: gui/widgets/trading_panel.py _refresh_history (:1219-1264) 单数据源走内存模拟盘:
      :1222 get_trade_history(limit=100) 唯一取数; core/services/trading_service.py:840-862
      纯内存读取 self._trade_history, 唯一写入方为模拟成交 execute_buy_order (:489)/
      execute_sell_order (:556) → 真实已成交订单 (DuckDB orders 表) 永不展示。
      修复: OrderService.query_orders(FILLED) 优先 + 内存回退
      (参照 _refresh_orders :1266-1338 双源样板, 即 _refresh_positions :1144-1217 模式)。

测试策略 (同 R254):
- 弹出 conftest 冲突 mock 条目, 用 importlib 从文件加载被测试模块
- order_repository / account_repository 以 mock 模块隔离重型 DB 依赖
- 面板 object.__new__(TradingPanel) + MagicMock 容器/表格 (避免 UI 初始化)
- 本文件末尾恢复被 mock 污染的 sys.modules 条目
"""
import os
import sys
import unittest
from datetime import datetime

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R252/R253/R254)
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

# order_service 依赖的 DB 重型模块以 mock 隔离
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
# mock 重型依赖后, 真实加载被测试模块 (加载顺序同 R254)
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

# order_service 真实副本 (trading_panel._refresh_history 局部 import 将解析到同批次)
_load_module_from_file(
    'core.trading.order_service', 'core/trading/order_service.py')

import gui.widgets  # noqa: E402
_tp_module = _load_module_from_file(
    'gui.widgets.trading_panel', 'gui/widgets/trading_panel.py')
TradingPanel = _tp_module.TradingPanel

from core.plugin_types import AssetType  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

_APP = None


def _get_app():
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication([])
    return _APP


# ===========================================================================
# P1: _refresh_history 数据源切换 OrderService
# ===========================================================================
class TestRefreshHistoryOrderServicePriority(unittest.TestCase):
    """P1: OrderService 可解析且 FILLED 订单非空 → 真实落库成交; 否则回退内存路径"""

    def _make_panel(self, container, ctp_account_id='ACC_001'):
        """真实 TradingPanel 实例 (patch UI 初始化, 同 R254), 表格用 MagicMock"""
        _get_app()
        with patch.object(TradingPanel, '_init_ui'), \
             patch.object(TradingPanel, '_connect_signals'), \
             patch.object(TradingPanel, '_subscribe_events'):
            panel = TradingPanel(
                trading_service=MagicMock(),
                event_bus=MagicMock(),
                service_container=container,
            )
        panel.history_table = MagicMock()
        if ctp_account_id is not None:
            ctp_combo = MagicMock()
            ctp_combo.currentData.return_value = ctp_account_id
            panel.ctp_account_combo = ctp_combo
        return panel

    def _make_filled_order(self, execute_time=None):
        return Order(
            order_id='O_R256_001',
            strategy_id='default',
            asset_type=AssetType.STOCK_A,
            stock_code='600000',
            order_type=CoreOrderType.BUY,
            order_category=CoreOrderCategory.LIMIT,
            order_price=10.5,
            order_quantity=100,
            order_status=CoreOrderStatus.FILLED,
            create_time=datetime(2026, 8, 6, 10, 0, 0),
            update_time=datetime(2026, 8, 6, 10, 0, 0),
            execute_time=execute_time,  # None → Order 默认 None (order_models.py:69)
            filled_quantity=100,
            filled_price=10.5,
        )

    def test_uses_order_service_when_available_with_results(self):
        """OrderService 可解析且返回 FILLED 订单 → 渲染真实订单 (不读内存历史)"""
        order_service = MagicMock()
        order_service.query_orders.return_value = [
            self._make_filled_order(execute_time=datetime(2026, 8, 6, 10, 0, 5))]
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = self._make_panel(container)

        TradingPanel._refresh_history(panel)

        # 真实源: query_orders 以 FILLED 条件查询
        order_service.query_orders.assert_called_once()
        query = order_service.query_orders.call_args[0][0]
        # 值语义断言 (跨批次 sys.modules 分裂, 参照 R254 运行时批次防御, 不比较枚举身份)
        self.assertEqual(len(query.order_statuses), 1)
        self.assertEqual(query.order_statuses[0].value, 'filled')
        self.assertEqual(query.limit, 100)
        self.assertEqual(query.sort_by, 'create_time')
        self.assertEqual(query.sort_order, 'desc')
        # 渲染订单数 = 表格行数
        panel.history_table.setRowCount.assert_called_once_with(1)
        # 内存历史不得再被读取
        panel.trading_service.get_trade_history.assert_not_called()
        # 9 列全填且列语义对齐表头
        calls = [c.args for c in panel.history_table.setItem.call_args_list]
        self.assertEqual(len(calls), 9)  # 时间/交易编号/股票代码/股票名称/操作/价格/数量/金额/状态
        self.assertEqual(calls[0][2].text(), '2026-08-06 10:00:05')  # col0 时间
        self.assertEqual(calls[1][2].text(), 'O_R256_0')            # col1 交易编号(截断8)
        self.assertEqual(calls[2][2].text(), '600000')               # col2 股票代码
        self.assertEqual(calls[3][2].text(), '600000')               # col3 股票名称降级显示 code
        self.assertEqual(calls[4][2].text(), '买入')                  # col4 操作
        self.assertEqual(calls[5][2].text(), '10.50')                # col5 成交价
        self.assertEqual(calls[6][2].text(), '100')                  # col6 成交数量
        self.assertEqual(calls[7][2].text(), '1050.00')              # col7 金额
        self.assertEqual(calls[8][2].text(), '已成交')                # col8 状态

    def test_falls_back_when_order_service_returns_empty(self):
        """OrderService 返回空列表 → 回退 trading_service.get_trade_history"""
        order_service = MagicMock()
        order_service.query_orders.return_value = []
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = self._make_panel(container)
        panel.trading_service.get_trade_history.return_value = []

        TradingPanel._refresh_history(panel)

        order_service.query_orders.assert_called_once()
        panel.trading_service.get_trade_history.assert_called_once()

    def test_falls_back_when_order_service_unavailable(self):
        """OrderService 不可解析 (try_resolve None) → 回退内存不抛异常"""
        container = MagicMock()
        container.try_resolve.return_value = None
        panel = self._make_panel(container)
        panel.trading_service.get_trade_history.return_value = []

        TradingPanel._refresh_history(panel)  # 不应抛异常

        panel.trading_service.get_trade_history.assert_called_once()

    def test_render_ok_when_execute_time_none(self):
        """execute_time 为 None 的 FILLED 订单渲染不抛异常 (order_models.py:69)"""
        order_service = MagicMock()
        order_service.query_orders.return_value = [
            self._make_filled_order(execute_time=None)]
        container = MagicMock()
        container.try_resolve.return_value = order_service
        panel = self._make_panel(container)

        TradingPanel._refresh_history(panel)  # 不应抛异常

        panel.history_table.setRowCount.assert_called_once_with(1)
        first_time_item = panel.history_table.setItem.call_args_list[0][0][2]
        self.assertEqual(first_time_item.text(), '--')


# ---------------------------------------------------------------------------
# 恢复被 mock 污染的 sys.modules 条目 (同 R254 交叉审查教训)
# ---------------------------------------------------------------------------
for _mod_name in ('core.trading.order_repository',
                  'core.trading.account_repository',
                  'core.trading.order_models',
                  'core.trading.order_executor',
                  'core.trading.order_service',
                  'gui.widgets.trading_panel'):
    sys.modules.pop(_mod_name, None)


if __name__ == '__main__':
    unittest.main()
