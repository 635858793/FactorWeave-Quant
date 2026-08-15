#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R252 回归测试: 交易域修复 F1-F7

覆盖:
- F1: EnhancedRiskMonitor 未注册导致所有订单被风控拒绝 (try_resolve + except 降级为 warning)
- F2: 持仓表格刷新 AttributeError (Position 字段 symbol/symbol_name)
- F3: 撤销订单用截断 8 字符 ID 永远找不到订单 (UserRole 存完整 ID)
- F4: 交易历史表格列错位 (9 列表头对齐)
- F5: TradingPanel.dispose() 无调用者 → 3 个事件订阅永不退订 (right_panel._do_dispose 补充调用)
- F6: query_order_status 默认接口 None → 状态查询必然失败 (判空)
- F7: 信号子面板展示数据残缺 (真实 price/return + 暂无数据标注)

测试策略 (同 R251):
- 弹出 conftest 冲突 mock 条目, 用 importlib 从文件加载被测试模块
- right_panel 用假 BasePanel 避免 PyQt5 sip 组合元类无头崩溃
- order_executor 依赖的重型链 (order_repository / enhanced_risk_monitor / account_manager) 以 mock 模块隔离
- R272 治理: 模块级覆盖 sys.modules 前保存原真实模块引用, 文件末尾恢复真实模块
  (而非 pop 移除), 消除后续文件类身份漂移
"""
import os
import sys
import types

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R251)
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
# 真实加载 core.events / core.services.trading_service (纯 Python, 安全)
# ---------------------------------------------------------------------------
from core.events import StockSelectedEvent, TradeExecutedEvent, PositionUpdatedEvent  # noqa: E402
from core.services.trading_service import (  # noqa: E402
    OrderSide, OrderStatus, OrderType, TradingOrder, TradeRecord, Position,
)

# ---------------------------------------------------------------------------
# 加载 gui.widgets (其 __init__.py 仅注释, 安全) + trading_panel (真实 PyQt5)
# ---------------------------------------------------------------------------
import gui.widgets  # noqa: E402
_tp_module = _load_module_from_file(
    'gui.widgets.trading_panel', 'gui/widgets/trading_panel.py')
TradingPanel = _tp_module.TradingPanel

# ---------------------------------------------------------------------------
# right_panel 依赖隔离 (同 R251): 轻量 analysis_tabs 包 + mock 兄弟模块 + 假 BasePanel
# ---------------------------------------------------------------------------
_analysis_tabs_mod = types.ModuleType('gui.widgets.analysis_tabs')
_analysis_tabs_mod.__path__ = [
    os.path.join(os.path.dirname(gui.widgets.__file__), 'analysis_tabs')]
_install('gui.widgets.analysis_tabs', _analysis_tabs_mod)

for _sub in ('pattern_tab', 'pattern_tab_pro', 'technical_tab', 'trend_tab',
             'wave_tab', 'sector_flow_tab', 'sector_flow_tab_pro', 'hotspot_tab'):
    _make_mock_module(f'gui.widgets.analysis_tabs.{_sub}')

if 'gui.ui_components' not in sys.modules:
    _make_mock_module('gui.ui_components')

for _dep in ('core.performance', 'core.services.analysis_service',
             'core.services.backtest_result_manager',
             'utils.config_manager', 'utils.trace_context'):
    _make_mock_module(_dep)


class _FakeBasePanel:
    """极简 BasePanel 替身, 避免 PyQt5 sip wrappertype+ABC 组合元类无头崩溃"""

    def _do_dispose(self) -> None:
        pass

    def dispose(self) -> None:
        if not getattr(self, '_disposed', False):
            self._do_dispose()
            self._disposed = True


_panels_pkg = types.ModuleType('core.ui.panels')
_panels_pkg.__path__ = [os.path.join(ROOT, 'core', 'ui', 'panels')]
_install('core.ui.panels', _panels_pkg)

_base_panel_mod = types.ModuleType('core.ui.panels.base_panel')
_base_panel_mod.BasePanel = _FakeBasePanel
_install('core.ui.panels.base_panel', _base_panel_mod)

_rp_module = _load_module_from_file(
    'core.ui.panels.right_panel', 'core/ui/panels/right_panel.py')
RightPanel = _rp_module.RightPanel

# ---------------------------------------------------------------------------
# order_executor 依赖隔离: mock 掉重型/数据库依赖模块
# ---------------------------------------------------------------------------
_make_mock_module('core.trading.order_repository')
_make_mock_module('core.risk_monitoring.enhanced_risk_monitor')
_make_mock_module('core.trading.account_manager')

_oe_module = _load_module_from_file(
    'core.trading.order_executor', 'core/trading/order_executor.py')
OrderExecutor = _oe_module.OrderExecutor

from core.trading.trading_types import ExecutionResult, ExecutionStatus  # noqa: E402
from core.trading.order_models import (  # noqa: E402
    Order as RiskOrder, OrderType as RiskOrderType,
    OrderCategory, OrderStatus as RiskOrderStatus,
)
from core.plugin_types import AssetType  # noqa: E402
from PyQt5.QtCore import Qt  # noqa: E402
from datetime import datetime  # noqa: E402
from decimal import Decimal  # noqa: E402

import unittest  # noqa: E402
import pytest  # noqa: E402

# F1: 显式引用 mock 模块内的服务类型 (MagicMock 的 __name__ 不是字符串, 不能用于名字比较)
_ERM = sys.modules['core.risk_monitoring.enhanced_risk_monitor'].EnhancedRiskMonitor
_AM = sys.modules['core.trading.account_manager'].AccountManager

# _pre_trade_risk_check 方法内延迟 import 的依赖模块 (运行时仍需要 mock)
_RUNTIME_MOCK_MODULES = [
    'core.trading.order_repository',
    'core.risk_monitoring.enhanced_risk_monitor',
    'core.trading.account_manager',
]


@pytest.fixture(autouse=True)
def _r252_ensure_runtime_mocks():
    """收集阶段的文件末尾恢复会放回真实模块 (避免污染其他测试文件),
    但 _pre_trade_risk_check 运行时延迟 import 仍需要 mock →
    每个测试前重新注入 mock, 测试后恢复真实模块 (R272 语义)"""
    global _ERM, _AM
    for _name in _RUNTIME_MOCK_MODULES:
        _make_mock_module(_name)
    _ERM = sys.modules['core.risk_monitoring.enhanced_risk_monitor'].EnhancedRiskMonitor
    _AM = sys.modules['core.trading.account_manager'].AccountManager
    yield
    for _name in _RUNTIME_MOCK_MODULES:
        if _name in _ORIGINAL_MODULES:
            sys.modules[_name] = _ORIGINAL_MODULES[_name]
        else:
            sys.modules.pop(_name, None)


_FULL_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


def _build_right_panel(**kwargs) -> RightPanel:
    """构造轻量 RightPanel 实例 (跳过 __init__ 避免重型 UI 依赖)"""
    panel = object.__new__(RightPanel)
    panel._current_stock_code = ''
    panel._current_stock_name = ''
    panel._performance_manager = None
    panel._has_basic_tabs = False
    panel._pending_tab_updates = {}
    panel._tab_stock_code = {}
    panel._backtest_result_manager = None
    panel._update_status = MagicMock()
    panel._clear_backtest_results = MagicMock()
    panel._update_analysis_display = MagicMock()
    panel._async_update_professional_tabs = MagicMock()
    panel._update_professional_tabs_with_performance_manager = MagicMock()
    for key, value in kwargs.items():
        setattr(panel, key, value)
    return panel


# ===========================================================================
# F1: EnhancedRiskMonitor 未注册导致所有订单被风控拒绝
# ===========================================================================
class TestF1EnhancedRiskMonitorFallback(unittest.TestCase):
    """F1: order_executor._pre_trade_risk_check 风控服务不可用时不得拒绝订单"""

    def _make_executor(self, container):
        executor = object.__new__(OrderExecutor)
        executor.service_container = container
        executor.event_bus = MagicMock()
        executor.repository = MagicMock()
        return executor

    def _make_order(self, account_id: str = 'default') -> RiskOrder:
        now = datetime.now()
        return RiskOrder(
            order_id='ORDER_R252_001',
            strategy_id='STRAT_001',
            asset_type=AssetType.STOCK_A,
            stock_code='600000',
            order_type=RiskOrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.2,
            order_quantity=1000,
            order_status=RiskOrderStatus.PENDING,
            create_time=now,
            update_time=now,
            user_id='test_user',
            account_id=account_id,
        )

    def _make_container(self, enhanced_monitor=None, enhanced_raises=None,
                        registered_monitor=False):
        """构造服务容器 mock

        - EnhancedRiskMonitor 未注册时: resolve 抛 ValueError, try_resolve 返回 None
        - AccountManager 总是"可注册" (resolve 返回 mock)
        """
        container = MagicMock()

        def fake_resolve(service_type):
            if service_type is _ERM:
                if registered_monitor:
                    rm = enhanced_monitor
                    if enhanced_raises is not None:
                        rm.check_order_risk.side_effect = enhanced_raises
                    return rm
                raise ValueError("Service EnhancedRiskMonitor is not registered")
            if service_type is _AM:
                return MagicMock()
            raise ValueError(f"Service {getattr(service_type, '__name__', service_type)} is not registered")

        container.resolve.side_effect = fake_resolve
        if registered_monitor:
            container.try_resolve.return_value = enhanced_monitor
        else:
            container.try_resolve.return_value = None
        return container

    def test_unregistered_risk_monitor_does_not_block_order(self):
        """EnhancedRiskMonitor 未注册 (resolve 抛 ValueError) 时订单不得被拒"""
        container = self._make_container()
        executor = self._make_executor(container)
        result = executor._pre_trade_risk_check(self._make_order())
        # 修复前: except → RISK_CHECK_FAILED passed=False; 修复后: passed=True
        self.assertTrue(result['passed'])

    def test_registered_risk_monitor_still_rejects(self):
        """EnhancedRiskMonitor 已注册且检查不通过时仍拒绝 (保留原行为)"""
        risk_monitor = MagicMock()
        risk_monitor.check_order_risk.return_value = {
            'passed': False, 'reason': '仓位超限'}
        container = self._make_container(
            enhanced_monitor=risk_monitor, registered_monitor=True)
        executor = self._make_executor(container)
        result = executor._pre_trade_risk_check(self._make_order())
        self.assertFalse(result['passed'])
        self.assertEqual(result['reason'], '仓位超限')

    def test_risk_monitor_exception_degrades_to_warning(self):
        """风控服务抛异常时应降级为 warning 继续基础检查, 而非拒绝订单"""
        risk_monitor = MagicMock()
        container = self._make_container(
            enhanced_monitor=risk_monitor,
            enhanced_raises=RuntimeError('boom'),
            registered_monitor=True,
        )
        executor = self._make_executor(container)
        result = executor._pre_trade_risk_check(self._make_order())
        # 修复前: return RISK_CHECK_FAILED passed=False; 修复后: passed=True
        self.assertTrue(result['passed'])
        self.assertNotIn('error_code', result)


# ===========================================================================
# F2: 持仓表格刷新 AttributeError → 持仓永远空白
# ===========================================================================
class TestF2PositionsRefresh(unittest.TestCase):
    """F2: _refresh_positions 使用 Position.symbol/symbol_name"""

    def test_refresh_positions_uses_symbol_fields(self):
        # TradingPanel 是 PyQt5 sip 类型, object.__new__ 不安全 → 用 SimpleNamespace + 未绑定调用
        panel = types.SimpleNamespace()
        position_table = MagicMock()
        panel.position_table = position_table
        portfolio = MagicMock()
        panel._portfolio = portfolio

        position = MagicMock()
        position.symbol = '600000'
        position.symbol_name = '浦发银行'
        position.quantity = 100
        position.avg_cost = 10.0
        position.current_price = 10.5
        position.market_value = 1050.0
        position.profit_loss = 50.0
        position.profit_loss_pct = 5.0
        portfolio.positions = {'600000': position}

        # 修复前: position.stock_code 抛 AttributeError → 表格空白
        TradingPanel._refresh_positions(panel)

        calls = [c.args for c in position_table.setItem.call_args_list]
        self.assertEqual(len(calls), 8)
        self.assertEqual(calls[0][2].text(), '600000')   # 股票代码列 = symbol
        self.assertEqual(calls[1][2].text(), '浦发银行')  # 股票名称列 = symbol_name


# ===========================================================================
# F3: 撤销订单用截断 8 字符 ID, 永远找不到订单
# ===========================================================================
class TestF3CancelOrderFullId(unittest.TestCase):
    """F3: 完整 order_id 存入 UserRole, 撤销时从 UserRole 读取"""

    def _make_panel(self):
        panel = types.SimpleNamespace()
        panel.orders_table = MagicMock()
        panel.trading_service = MagicMock()
        return panel

    def test_refresh_orders_stores_full_id_in_user_role(self):
        panel = self._make_panel()
        order = TradingOrder(
            order_id=_FULL_ID, symbol='600000', symbol_name='浦发银行',
            order_type=OrderType.LIMIT, side=OrderSide.BUY, quantity=100,
            price=Decimal('10.0'),
        )
        panel.trading_service.get_active_orders.return_value = [order]

        TradingPanel._refresh_orders(panel)

        first_item = panel.orders_table.setItem.call_args_list[0][0][2]
        self.assertEqual(first_item.text(), _FULL_ID[:8])      # 展示仍截断
        self.assertEqual(first_item.data(Qt.UserRole), _FULL_ID)  # 完整 ID 入 UserRole

    def test_cancel_order_uses_full_id(self):
        panel = self._make_panel()
        panel.trading_service.cancel_order.return_value = (True, '已撤销')
        selection_model = MagicMock()
        selected = MagicMock()
        selected.row.return_value = 0
        selection_model.selectedRows.return_value = [selected]
        panel.orders_table.selectionModel.return_value = selection_model

        order_id_item = MagicMock()
        order_id_item.data.return_value = _FULL_ID  # 修复后从 UserRole 读完整 ID
        panel.orders_table.item.return_value = order_id_item

        from PyQt5.QtWidgets import QMessageBox
        real_yes = QMessageBox.Yes
        with patch('gui.widgets.trading_panel.QMessageBox.question',
                   return_value=real_yes), \
             patch('gui.widgets.trading_panel.QMessageBox.information'), \
             patch('gui.widgets.trading_panel.QMessageBox.warning'), \
             patch('gui.widgets.trading_panel.QMessageBox.critical'):
            TradingPanel._on_cancel_order(panel)

        # 修复前: 传截断 ID (order_id_item.text()) → 断言失败
        panel.trading_service.cancel_order.assert_called_once_with(_FULL_ID)


# ===========================================================================
# F4: 交易历史表格列错位
# ===========================================================================
class TestF4HistoryColumnAlignment(unittest.TestCase):
    """F4: _refresh_history 填充顺序对齐 9 列表头"""

    def test_refresh_history_columns_align_with_header(self):
        panel = types.SimpleNamespace()
        history_table = MagicMock()
        panel.history_table = history_table
        panel.trading_service = MagicMock()

        record = TradeRecord(
            trade_id='TRADE-1234567890', symbol='600000', stock_name='浦发银行',
            action='buy', quantity=100, price=10.5, status='executed',
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
        )
        panel.trading_service.get_trade_history.return_value = [record]

        TradingPanel._refresh_history(panel)

        calls = [c.args for c in history_table.setItem.call_args_list]
        self.assertEqual(len(calls), 9)  # 9 列全填
        # 表头: 时间/交易编号/股票代码/股票名称/操作/价格/数量/金额/状态
        self.assertEqual(calls[0][2].text(), '2024-01-15 10:30:00')  # col0 时间
        self.assertEqual(calls[1][2].text(), record.trade_id[:8])    # col1 交易编号
        self.assertEqual(calls[2][2].text(), '600000')               # col2 股票代码
        self.assertEqual(calls[3][2].text(), '浦发银行')              # col3 股票名称
        self.assertEqual(calls[4][2].text(), '买入')                  # col4 操作
        self.assertEqual(calls[5][2].text(), '10.50')                # col5 价格
        self.assertEqual(calls[6][2].text(), '100')                  # col6 数量
        self.assertEqual(calls[7][2].text(), '1050.00')              # col7 金额
        self.assertEqual(calls[8][2].text(), '已成交')                # col8 状态


# ===========================================================================
# F5: TradingPanel.dispose() 无调用者 → 事件订阅永不退订
# ===========================================================================
class TestF5DisposeTradingPanel(unittest.TestCase):
    """F5: right_panel._do_dispose 需调用内部 _trading_panel.dispose()"""

    def test_do_dispose_calls_inner_trading_panel_dispose(self):
        panel = _build_right_panel(event_bus=MagicMock())
        trading_panel = MagicMock()
        panel._trading_panel = trading_panel

        panel._do_dispose()

        trading_panel.dispose.assert_called_once()

    def test_do_dispose_without_trading_panel_safe(self):
        """未创建实盘交易标签页 (无 _trading_panel) 时 dispose 不抛异常"""
        panel = _build_right_panel(event_bus=MagicMock())
        panel._do_dispose()  # 不应抛 AttributeError


# ===========================================================================
# F6: query_order_status / cancel_order 接口为 None
# ===========================================================================
class TestF6NullInterfaceGuard(unittest.TestCase):
    """F6: 无可用交易接口时显式返回, 不得抛 AttributeError"""

    def test_query_order_status_without_interface(self):
        executor = object.__new__(OrderExecutor)
        executor.trading_interface = None
        executor.repository = MagicMock()

        result = executor.query_order_status('ORDER_R252_001')

        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertEqual(result.error_code, 'QUERY_ERROR')
        self.assertIn('无可用交易接口', result.message)

    def test_cancel_order_without_interface(self):
        executor = object.__new__(OrderExecutor)
        executor.repository = MagicMock()
        executor.event_bus = MagicMock()
        order_mock = MagicMock()
        order_mock.is_completed = False
        order_mock.order_status = RiskOrderStatus.PENDING
        order_mock.asset_type = AssetType.STOCK_A
        executor.repository.get_order.return_value = order_mock
        executor._get_trading_interface = MagicMock(return_value=None)

        result = executor.cancel_order('ORDER_R252_001')

        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertIn('无可用交易接口', result.message)


# ===========================================================================
# F7: 信号子面板展示数据残缺 (价格/收益/胜率恒 0)
# ===========================================================================
class TestF7SignalPanelRealData(unittest.TestCase):
    """F7: _convert_technical_signals 提取真实 price/return, 无数据时标注暂无"""

    def test_convert_extracts_real_price_and_return(self):
        panel = _build_right_panel()
        tech_signals = [
            {'name': 'MA20', 'signal': 'bullish', 'desc': '收盘价高于MA20',
             'price': 10.5, 'return': 3.2},
            {'name': 'RSI', 'signal': 'bearish', 'desc': 'RSI超买',
             'price': 10.3, 'return': -1.5},
        ]
        converted = panel._convert_technical_signals(tech_signals)
        # 修复前: price='' return=0 写死 → 断言失败
        self.assertEqual(converted['history'][0]['price'], 10.5)
        self.assertEqual(converted['history'][0]['return'], 3.2)
        self.assertEqual(converted['history'][1]['price'], 10.3)
        self.assertEqual(converted['history'][1]['return'], -1.5)

    def test_statistics_none_when_no_real_returns(self):
        panel = _build_right_panel()
        converted = panel._convert_technical_signals([
            {'name': 'MA20', 'signal': 'bullish', 'desc': '收盘价高于MA20'},
        ])
        stats = converted['statistics']
        # 修复前: statistics 无 win_rate/avg_return 键 → KeyError
        self.assertIn('win_rate', stats)
        self.assertIn('avg_return', stats)
        self.assertIsNone(stats['win_rate'])
        self.assertIsNone(stats['avg_return'])

    def test_statistics_computed_from_history(self):
        panel = _build_right_panel()
        converted = panel._convert_technical_signals([
            {'name': 'A', 'signal': 'bullish', 'desc': 'x', 'return': 5.0},
            {'name': 'B', 'signal': 'bullish', 'desc': 'x', 'return': -2.0},
        ])
        self.assertAlmostEqual(converted['statistics']['win_rate'], 50.0)
        self.assertAlmostEqual(converted['statistics']['avg_return'], 1.5)

    def test_update_signal_analysis_marks_no_data(self):
        panel = _build_right_panel()
        stats_text = MagicMock()
        panel.get_widget = lambda name: (
            stats_text if name == 'signal_stats_text' else None)

        panel._update_signal_analysis_safe({
            'current': {'type': 'buy', 'strength': 1},
            'history': [],
            'statistics': {
                'total_signals': 0, 'buy_signals': 0, 'sell_signals': 0,
                'win_rate': None, 'avg_return': None,
            },
        })

        text = stats_text.setPlainText.call_args[0][0]
        # 修复前: "胜率: 0.0% 平均收益: 0.00%" 恒 0
        self.assertIn('暂无数据', text)
        self.assertNotIn('0.0%', text)


# ---------------------------------------------------------------------------
# R272 治理: 恢复真实模块 (而非 pop 移除) — 消除后续文件类身份漂移
# 本文件注入/加载过的全部模块名 (mock + 内联包 + _load_module_from_file 副本)
# ---------------------------------------------------------------------------
_ALL_INJECTED_NAMES = (
    'gui.widgets.analysis_tabs',
    'gui.widgets.analysis_tabs.pattern_tab',
    'gui.widgets.analysis_tabs.pattern_tab_pro',
    'gui.widgets.analysis_tabs.technical_tab',
    'gui.widgets.analysis_tabs.trend_tab',
    'gui.widgets.analysis_tabs.wave_tab',
    'gui.widgets.analysis_tabs.sector_flow_tab',
    'gui.widgets.analysis_tabs.sector_flow_tab_pro',
    'gui.widgets.analysis_tabs.hotspot_tab',
    'gui.ui_components',
    'core.performance',
    'core.services.analysis_service',
    'core.services.backtest_result_manager',
    'utils.config_manager',
    'utils.trace_context',
    'core.trading.order_repository',
    'core.risk_monitoring.enhanced_risk_monitor',
    'core.trading.account_manager',
    'core.trading.order_executor',
    'core.ui.panels',
    'core.ui.panels.base_panel',
    'core.ui.panels.right_panel',
    'gui.widgets.trading_panel',
)
for _name, _orig in _ORIGINAL_MODULES.items():
    sys.modules[_name] = _orig
for _name in _ALL_INJECTED_NAMES:
    if _name not in _ORIGINAL_MODULES:
        sys.modules.pop(_name, None)


if __name__ == '__main__':
    unittest.main()
