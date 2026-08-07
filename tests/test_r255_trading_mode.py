#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R255 交叉验证回归测试: 实盘模式域 P0/P1 修复

覆盖 (R255 交叉验证实证, 全部源码行号):
- P0: OrderExecutor 无模式闸门 → 账号解析成功 + CTP 接口连接成功即真实报单
      (order_executor.py:936-1073 submit_order 全程无 TradingMode/LIVE 检查,
       ctp_trading_interface.py:274-355 submit_order → _api.action.buy_open)。
      修复: 默认 _trading_mode='paper', 真实 CTP/XTP/MiniQMT 接口在非 live
      模式被拦截 (MODE_BLOCKED, 不调用接口 submit_order)。
- P0: GUI 连接按钮创建的 CTP 实例 (trading_service._ctp_interfaces,
      trading_service.py:1132) 与下单时 OrderExecutor 新建独立实例
      (order_executor.py:894-926) 割裂。修复: connect_ctp_account 成功后注入
      OrderExecutor._account_interface_cache (order_executor.py:1446 set_trading_interface)。
- P0: _register_trading_interfaces (order_executor.py:355-390) 无 Mock 保护层 →
      HIKYUU_TRADING_MOCK=1 环境注册 MockTradingInterface (追加而非替换)。
- P1: trading_panel._refresh_positions (trading_panel.py:1111-1152) 仅读
      trading_service 内存持仓 → 双源切换 (AccountManager.get_account_positions
      优先, 空/异常/无 account_id 回退内存, 参考 _refresh_orders :1208-1228 降级模式)。
- P1: trading_panel._render_core_orders (trading_panel.py:1314-1315) col2
      order_category.value 英文直出 → 中文化映射 (市价单/限价单/止损单/止损限价单)。

测试策略 (同 R252/R253/R254):
- 弹出 conftest 冲突 mock 条目, 用 importlib 从文件加载被测试模块
- order_repository / account_repository 以 mock 模块隔离重型 DB 依赖
- TradingPanel 构造/方法测试: offscreen QApplication + MagicMock 容器 + MagicMock 表格
- OrderExecutor 闸门测试: 桩接口类名含 CTP/XTP (与闸门 type 名判定一致), Mock 接口放行
- 本文件末尾恢复被 mock 污染的 sys.modules 条目
"""
import os
import sys
import threading
import types
import unittest
from datetime import datetime
from decimal import Decimal

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

# ---------------------------------------------------------------------------
# 弹出 conftest 冲突 mock 条目 (同 R251/R252/R253/R254)
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

# order_executor / trading_service 依赖的 DB 重型模块以 mock 隔离
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

_tt_module = _load_module_from_file(
    'core.trading.trading_types', 'core/trading/trading_types.py')
ExecutionResult = _tt_module.ExecutionResult
ExecutionStatus = _tt_module.ExecutionStatus

_oe_module = _load_module_from_file(
    'core.trading.order_executor', 'core/trading/order_executor.py')
OrderExecutor = _oe_module.OrderExecutor
MockTradingInterface = _oe_module.MockTradingInterface

_am_module = _load_module_from_file(
    'core.trading.account_models', 'core/trading/account_models.py')
TradingInterfaceType = _am_module.TradingInterfaceType
AmPosition = _am_module.Position
AmPositionSide = _am_module.PositionSide

_ts_module = _load_module_from_file(
    'core.services.trading_service', 'core/services/trading_service.py')
TradingService = _ts_module.TradingService
TradingMode = _ts_module.TradingMode
TsPosition = _ts_module.Position
TsPortfolio = _ts_module.Portfolio

import gui.widgets  # noqa: E402
_tp_module = _load_module_from_file(
    'gui.widgets.trading_panel', 'gui/widgets/trading_panel.py')
TradingPanel = _tp_module.TradingPanel

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
# 测试桩: 类名含 CTP/XTP 的真实接口替身 (与闸门 type 名判定逻辑一致)
# ===========================================================================
class _FakeCTPInterface:
    """类名含 CTP 的桩接口: 模拟真实 CTP 交易接口"""

    def __init__(self):
        self.submit_called = False

    def submit_order(self, order):
        self.submit_called = True
        return ExecutionResult(
            order_id=order.order_id,
            status=ExecutionStatus.SUCCESS,
            message='ok',
            exchange_order_id='E1',
            details={'filled_price': order.order_price},
        )


class _FakeXTPInterface:
    """类名含 XTP 的桩接口: 模拟真实 XTP 交易接口"""

    def __init__(self):
        self.submit_called = False

    def submit_order(self, order):
        self.submit_called = True
        return ExecutionResult(
            order_id=order.order_id,
            status=ExecutionStatus.SUCCESS,
            message='ok',
            exchange_order_id='E1',
            details={'filled_price': order.order_price},
        )


def _make_core_order(order_id='O_R255_001', account_id='ACC_001'):
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


# ===========================================================================
# 测试1/2 (P0): OrderExecutor 模式闸门 (真实资金安全)
# ===========================================================================
class TestModeGateBlocksRealInterface(unittest.TestCase):
    """P0: 真实 CTP/XTP 接口 + 非 live 模式 → MODE_BLOCKED, 接口 submit_order 不被调用"""

    def _make_executor(self):
        with patch.object(OrderExecutor, '_initialize', return_value=None):
            executor = OrderExecutor(MagicMock(), MagicMock())
        # 默认模式必须为 paper (绝不默认 live, 真实资金安全铁律)
        self.assertEqual(executor.get_trading_mode(), 'paper')
        executor._validate_order_integrity = lambda order: None
        executor._pre_trade_risk_check = lambda order: {
            'passed': True, 'reason': '', 'warnings': []}
        executor._resolve_account_for_order = lambda order: types.SimpleNamespace(
            account_id=order.account_id)
        executor._interface_health = {}
        executor.repository = MagicMock()
        return executor

    def test_paper_mode_blocks_real_ctp_interface_submit(self):
        """真实 CTP 类型接口 + 默认 paper 模式 → MODE_BLOCKED, 不调用接口 submit_order"""
        executor = self._make_executor()
        stub = _FakeCTPInterface()
        executor._get_trading_interface_for_account = lambda account: stub

        result = executor.submit_order(_make_core_order())

        self.assertEqual(result.error_code, 'MODE_BLOCKED')
        self.assertEqual(result.status, ExecutionStatus.FAILED)
        self.assertFalse(stub.submit_called,
                         "真实接口不得被调用 (防止误触发真实报单)")

    def test_paper_mode_blocks_real_xtp_interface_submit(self):
        """真实 XTP 类型接口 + 非 live 模式 → MODE_BLOCKED"""
        executor = self._make_executor()
        stub = _FakeXTPInterface()
        executor._get_trading_interface_for_account = lambda account: stub

        result = executor.submit_order(_make_core_order())

        self.assertEqual(result.error_code, 'MODE_BLOCKED')
        self.assertFalse(stub.submit_called)

    def test_mock_interface_allowed_in_paper_mode(self):
        """MockTradingInterface 在非 live 模式放行 (测试环境正常模拟成交)"""
        executor = self._make_executor()
        mock_iface = MockTradingInterface(service_container=None, event_bus=None)
        executor._get_trading_interface_for_account = lambda account: mock_iface

        result = executor.submit_order(_make_core_order())

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertNotEqual(result.error_code, 'MODE_BLOCKED')

    def test_live_mode_allows_real_interface_submit(self):
        """set_trading_mode('live') 后真实接口正常提交 (唯一实盘放行通道)"""
        executor = self._make_executor()
        stub = _FakeCTPInterface()
        executor._get_trading_interface_for_account = lambda account: stub

        executor.set_trading_mode('live')

        result = executor.submit_order(_make_core_order())

        self.assertEqual(result.status, ExecutionStatus.SUCCESS)
        self.assertTrue(stub.submit_called)

    def test_set_trading_mode_rejects_unknown_mode(self):
        """set_trading_mode 未知模式回退 paper, 绝不进入 live"""
        executor = self._make_executor()
        executor.set_trading_mode('whatever')
        self.assertEqual(executor.get_trading_mode(), 'paper')


# ===========================================================================
# 测试3 (P0): Mock 保护层 (HIKYUU_TRADING_MOCK 环境注册 MockTradingInterface)
# ===========================================================================
class TestMockEnvironmentProtection(unittest.TestCase):
    """P0: HIKYUU_TRADING_MOCK=1/true 时 _register_trading_interfaces 注册 Mock"""

    def _call_register(self):
        executor = object.__new__(OrderExecutor)
        executor.service_container = MagicMock()
        executor.event_bus = MagicMock()
        executor._trading_interfaces = {}
        # 隔离真实 CTP/XTP C 扩展导入 (延迟导入目标替换为 MagicMock)。
        # 注意: 不能用 patch.dict(sys.modules, ...) —— 其退出时 _clear_dict 会清空
        # 整个 sys.modules 再恢复进入时快照, 补丁窗口内新导入的模块 (如 cryptography
        # 全链) 会被抹除 → 后续再导入 cryptography._rust 触发 PyO3 二次初始化错误
        # (R255 4文件并行实测). 改为手动保存/恢复仅涉及的 3 个接口模块键。
        _iface_mock_names = (
            'core.trading.interfaces.ctp_trading_interface',
            'core.trading.interfaces.xtp_pro_trading_interface',
            'core.trading.interfaces.xtp_trading_interface',
        )
        _saved = {name: sys.modules.get(name) for name in _iface_mock_names}
        for name in _iface_mock_names:
            sys.modules[name] = MagicMock()
        try:
            with patch.object(OrderExecutor, '_initialize_trading_interfaces',
                              return_value=None):
                executor._register_trading_interfaces()
        finally:
            for name in _iface_mock_names:
                if _saved[name] is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = _saved[name]
        return executor

    def test_mock_env_registers_mock_interface(self):
        """HIKYUU_TRADING_MOCK=1 → 注册 MockTradingInterface (追加而非替换)"""
        with patch.dict(os.environ, {'HIKYUU_TRADING_MOCK': '1'}, clear=False):
            executor = self._call_register()

        mock_ifaces = [i for i in executor._trading_interfaces.values()
                       if isinstance(i, MockTradingInterface)]
        self.assertTrue(mock_ifaces, "Mock 环境必须注册 MockTradingInterface")

    def test_mock_env_true_value_registers_mock_interface(self):
        """HIKYUU_TRADING_MOCK=true → 同样注册 MockTradingInterface"""
        with patch.dict(os.environ, {'HIKYUU_TRADING_MOCK': 'true'}, clear=False):
            executor = self._call_register()

        mock_ifaces = [i for i in executor._trading_interfaces.values()
                       if isinstance(i, MockTradingInterface)]
        self.assertTrue(mock_ifaces)

    def test_default_env_does_not_register_mock(self):
        """未设置 HIKYUU_TRADING_MOCK → 不注册 MockTradingInterface (默认安全)"""
        saved = os.environ.pop('HIKYUU_TRADING_MOCK', None)
        try:
            executor = self._call_register()
        finally:
            if saved is not None:
                os.environ['HIKYUU_TRADING_MOCK'] = saved

        mock_ifaces = [i for i in executor._trading_interfaces.values()
                       if isinstance(i, MockTradingInterface)]
        self.assertFalse(mock_ifaces, "默认环境不得注册 MockTradingInterface")

    def test_mock_interface_has_mock_marker(self):
        """MockTradingInterface 携带 _is_mock_interface=True 标记 (闸门放行依据)"""
        self.assertTrue(
            getattr(MockTradingInterface, '_is_mock_interface', False),
            "MockTradingInterface 必须标记 _is_mock_interface=True")


# ===========================================================================
# 测试4 (P1): _refresh_positions 双源切换
# ===========================================================================
class TestPositionsRefreshDualSource(unittest.TestCase):
    """P1: 有 account_id 且 AccountManager 返回持仓 → 渲染 AccountManager;
    空/异常/无 account_id → 回退 TradingService 内存持仓"""

    def _make_memory_position(self):
        return TsPosition(
            symbol='600001',
            symbol_name='内存股',
            quantity=200,
            cost_price=Decimal('9.0'),
            current_price=Decimal('9.5'),
            market_value=Decimal('1900.0'),
            profit_loss=Decimal('100.0'),
            profit_loss_ratio=5.0,
        )

    def _make_am_position(self, stock_code='600000'):
        return AmPosition(
            position_id='P_AM_001',
            account_id='ACC_001',
            asset_type=AssetType.FUTURES,
            stock_code=stock_code,
            stock_name='浦发银行',
            side=AmPositionSide.LONG,
            quantity=100,
            available_quantity=100,
            open_price=10.0,
            current_price=11.0,
            market_value=1100.0,
            cost_price=10.0,
            cost_value=1000.0,
            profit_loss=100.0,
            profit_loss_ratio=10.0,
            open_time=datetime(2026, 8, 1, 9, 30, 0),
            update_time=datetime(2026, 8, 6, 10, 0, 0),
        )

    def _make_panel(self, container, ctp_account_id='ACC_001'):
        _get_app()
        with patch.object(TradingPanel, '_init_ui'), \
             patch.object(TradingPanel, '_connect_signals'), \
             patch.object(TradingPanel, '_subscribe_events'):
            panel = TradingPanel(
                trading_service=MagicMock(),
                event_bus=MagicMock(),
                service_container=container,
            )
        panel.position_table = MagicMock()
        portfolio = TsPortfolio(portfolio_id='default', name='默认投资组合',
                                cash=Decimal('100000'))
        portfolio.positions['p1'] = self._make_memory_position()
        panel._portfolio = portfolio
        if ctp_account_id is not None:
            ctp_combo = MagicMock()
            ctp_combo.currentData.return_value = ctp_account_id
            panel.ctp_account_combo = ctp_combo
        return panel

    def _col0_text(self, panel):
        for call in panel.position_table.setItem.call_args_list:
            if call.args[1] == 0:
                return call.args[2].text()
        return None

    def test_uses_account_manager_positions_when_available(self):
        """有 account_id 且 AccountManager 返回持仓 → 渲染 AccountManager 数据"""
        account_manager = MagicMock()
        account_manager.get_account_positions.return_value = [
            self._make_am_position('600000')]
        container = MagicMock()
        container.try_resolve.return_value = account_manager
        panel = self._make_panel(container)

        TradingPanel._refresh_positions(panel)

        account_manager.get_account_positions.assert_called_once_with('ACC_001')
        panel.position_table.setRowCount.assert_called_once_with(1)
        self.assertEqual(self._col0_text(panel), '600000',
                         "col0 应为 AccountManager 持仓的 stock_code")

    def test_falls_back_when_account_manager_returns_empty(self):
        """AccountManager 返回空列表 → 回退 TradingService 内存持仓"""
        account_manager = MagicMock()
        account_manager.get_account_positions.return_value = []
        container = MagicMock()
        container.try_resolve.return_value = account_manager
        panel = self._make_panel(container)

        TradingPanel._refresh_positions(panel)

        self.assertEqual(self._col0_text(panel), '600001',
                         "回退后 col0 应为内存持仓 symbol")

    def test_falls_back_when_account_manager_raises(self):
        """AccountManager 查询抛异常 → 回退内存持仓, 不崩溃"""
        account_manager = MagicMock()
        account_manager.get_account_positions.side_effect = RuntimeError('db down')
        container = MagicMock()
        container.try_resolve.return_value = account_manager
        panel = self._make_panel(container)

        TradingPanel._refresh_positions(panel)

        self.assertEqual(self._col0_text(panel), '600001')

    def test_falls_back_when_no_account_id(self):
        """无 account_id → 不解析 AccountManager, 回退内存持仓"""
        container = MagicMock()
        panel = self._make_panel(container, ctp_account_id=None)

        TradingPanel._refresh_positions(panel)

        self.assertEqual(self._col0_text(panel), '600001')
        container.try_resolve.assert_not_called()


# ===========================================================================
# 测试5 (P1): col2 订单类别中文化
# ===========================================================================
class TestCoreOrdersCategoryChinese(unittest.TestCase):
    """P1: _render_core_orders col2 渲染中文类别 (市价单/限价单/止损单/止损限价单)"""

    def _render_col2(self, category):
        _get_app()
        panel = types.SimpleNamespace(orders_table=MagicMock())
        order = Order(
            order_id='O_R255_005',
            strategy_id='default',
            asset_type=AssetType.STOCK_A,
            stock_code='600000',
            order_type=CoreOrderType.BUY,
            order_category=category,
            order_price=10.0,
            order_quantity=100,
            order_status=CoreOrderStatus.SUBMITTED,
            create_time=datetime(2026, 8, 6, 10, 0, 0),
            update_time=datetime(2026, 8, 6, 10, 0, 0),
        )
        TradingPanel._render_core_orders(panel, [order])
        for call in panel.orders_table.setItem.call_args_list:
            if call.args[1] == 2:
                return call.args[2].text()
        return None

    def test_market_category_chinese(self):
        self.assertEqual(self._render_col2(CoreOrderCategory.MARKET), '市价单')

    def test_limit_category_chinese(self):
        self.assertEqual(self._render_col2(CoreOrderCategory.LIMIT), '限价单')

    def test_stop_category_chinese(self):
        self.assertEqual(self._render_col2(CoreOrderCategory.STOP), '止损单')

    def test_stop_limit_category_chinese(self):
        self.assertEqual(self._render_col2(CoreOrderCategory.STOP_LIMIT), '止损限价单')

    def test_unknown_category_keeps_raw_value(self):
        """未知类别保留英文原值 (降级不丢失信息)"""
        self.assertEqual(self._render_col2('fancy_type'), 'fancy_type')


# ===========================================================================
# 测试6 (P0): connect_ctp_account 双实例打通 (注入 OrderExecutor)
# ===========================================================================
class TestCtpConnectInjectsInterface(unittest.TestCase):
    """P0: connect_ctp_account 成功后注入 OrderExecutor._account_interface_cache,
    下单复用已登录实例, 不再新建独立 CTP 接口"""

    def _make_service(self, container):
        ts = object.__new__(TradingService)
        ts._service_container = container
        ts._event_bus = MagicMock()
        ts._ctp_interfaces = {}
        ts._ctp_market_interfaces = {}
        ts._ctp_lock = threading.RLock()
        return ts

    def _make_ctp_account(self, account_id):
        """构造 CTP 账户: trading_interface_type 使用运行时批次枚举。

        connect_ctp_account 内部延迟 import account_models (trading_service.py:1090),
        若用收集阶段绑定的枚举 (可能与运行阶段批次不同), 类型比较
        (trading_service.py:1098) 会因枚举对象不同而恒 False → 连接被拒。
        """
        import importlib
        runtime_am = importlib.import_module('core.trading.account_models')
        account = MagicMock()
        account.account_id = account_id
        account.trading_interface_type = runtime_am.TradingInterfaceType.CTP
        account.ctp_trade_front = 'tcp://front'
        account.ctp_quote_front = 'tcp://quote'
        account.ctp_broker_id = '9999'
        account.ctp_investor_id = 'investor'
        account.ctp_password = 'pw'
        account.ctp_app_id = 'app'
        account.ctp_auth_code = 'auth'
        account.ctp_product_info = 'info'
        return account

    def test_connect_injects_interface_into_order_executor(self):
        """连接成功后调用 order_executor.set_trading_interface(ctp_interface, account_id)"""
        account = self._make_ctp_account('simnow_001')

        account_manager = MagicMock()
        account_manager.get_account.return_value = account

        order_executor = MagicMock()

        container = MagicMock()
        container.resolve.return_value = account_manager
        container.try_resolve.return_value = order_executor
        ts = self._make_service(container)

        fake_ctp = MagicMock()
        fake_ctp.connect.return_value = True
        fake_ctp.login.return_value = True
        fake_market = MagicMock()
        fake_market.connect.return_value = True
        fake_market.login.return_value = True

        with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface',
                   return_value=fake_ctp), \
             patch('core.trading.interfaces.ctp_market_interface.CTPMarketInterface',
                   return_value=fake_market):
            success, message = ts.connect_ctp_account('simnow_001')

        self.assertTrue(success)
        self.assertIn('simnow_001', ts._ctp_interfaces)
        order_executor.set_trading_interface.assert_called_once_with(
            fake_ctp, account_id='simnow_001')

    def test_connect_skips_injection_when_order_executor_unavailable(self):
        """OrderExecutor 不可解析 → 连接仍成功, 注入静默跳过 (不影响连接主链路)"""
        account = self._make_ctp_account('simnow_002')

        account_manager = MagicMock()
        account_manager.get_account.return_value = account

        container = MagicMock()
        container.resolve.return_value = account_manager
        container.try_resolve.return_value = None
        ts = self._make_service(container)

        fake_ctp = MagicMock()
        fake_ctp.connect.return_value = True
        fake_ctp.login.return_value = True
        fake_market = MagicMock()
        fake_market.connect.return_value = True
        fake_market.login.return_value = True

        with patch('core.trading.interfaces.ctp_trading_interface.CTPTradingInterface',
                   return_value=fake_ctp), \
             patch('core.trading.interfaces.ctp_market_interface.CTPMarketInterface',
                   return_value=fake_market):
            success, message = ts.connect_ctp_account('simnow_002')

        self.assertTrue(success)
        self.assertIn('simnow_002', ts._ctp_interfaces)


# ===========================================================================
# 交叉审查补充 (P0): set_mode 联动 OrderExecutor 模式闸门
# ===========================================================================
class TestSetModeSyncsOrderExecutor(unittest.TestCase):
    """R255-P0: TradingService.set_mode 必须同步 OrderExecutor.set_trading_mode。

    背景: OrderExecutor 默认 _trading_mode='paper', 真实 CTP/XTP 接口在非 live
    模式被 MODE_BLOCKED 拦截 (order_executor.py:1011-1027)。若 set_mode(LIVE)
    不联动放行, 实盘下单路径永远被闸门拦截 (R255 交叉审查发现: 修复代理A 仅
    实现了闸门与 connect 注入, 遗漏了 set_mode→闸门的联动)。
    """

    def _make_service(self, container):
        ts = object.__new__(TradingService)
        ts._service_container = container
        ts._event_bus = MagicMock()
        ts._ctp_interfaces = {}
        ts._ctp_market_interfaces = {}
        ts._ctp_lock = threading.RLock()
        ts._trading_config = {}
        ts._current_mode_context = None
        ts._mode_config = {}
        return ts

    def test_set_live_mode_syncs_order_executor(self):
        """set_mode(LIVE) → OrderExecutor.set_trading_mode('live') 被调用 (闸门放行前提)"""
        executor = MagicMock()
        container = MagicMock()
        container.try_resolve.return_value = executor
        ts = self._make_service(container)

        ts.set_mode(TradingMode.LIVE)

        # R258-P0: set_mode 联动下发 enable_risk_control (LIVE 强制 True, 资金安全)
        executor.set_trading_mode.assert_called_once_with('live', enable_risk_control=True)

    def test_set_paper_mode_syncs_order_executor(self):
        """set_mode(PAPER) → OrderExecutor.set_trading_mode('paper') (维持模拟闸门)"""
        executor = MagicMock()
        container = MagicMock()
        container.try_resolve.return_value = executor
        ts = self._make_service(container)

        ts.set_mode(TradingMode.PAPER)

        executor.set_trading_mode.assert_called_once_with('paper', enable_risk_control=True)

    def test_set_backtest_mode_syncs_order_executor(self):
        """set_mode(BACKTEST) → OrderExecutor.set_trading_mode('backtest')"""
        executor = MagicMock()
        container = MagicMock()
        container.try_resolve.return_value = executor
        ts = self._make_service(container)

        ts.set_mode(TradingMode.BACKTEST)

        # R258-P0: BACKTEST 默认 config 未传 enable_risk_control → False (回测可关风控)
        executor.set_trading_mode.assert_called_once_with('backtest', enable_risk_control=False)

    def test_order_executor_unavailable_degrades_gracefully(self):
        """OrderExecutor 不可解析 → set_mode 不抛异常 (try_resolve 降级 warning)"""
        container = MagicMock()
        container.try_resolve.return_value = None
        ts = self._make_service(container)

        ts.set_mode(TradingMode.LIVE)  # 不应抛异常

        container.try_resolve.assert_called_once()

    def test_legacy_container_resolve_fallback(self):
        """旧容器 mock 仅 resolve → 经 getattr 回退 resolve 联动, 不抛异常"""
        executor = MagicMock()
        container = MagicMock()
        del container.try_resolve
        container.resolve.return_value = executor
        ts = self._make_service(container)

        ts.set_mode(TradingMode.LIVE)

        # R258-P0: set_mode 联动下发 enable_risk_control (LIVE 强制 True, 资金安全)
        executor.set_trading_mode.assert_called_once_with('live', enable_risk_control=True)


# ---------------------------------------------------------------------------
# 恢复被 mock 污染的 sys.modules 条目 (同 R252/R253/R254 交叉审查教训)
# R255: mock 窗口 (:88) 内加载的消费者副本 (order_executor/trading_service/
# trading_panel 等) 内部固化了对 order_repository mock 的引用, 一并弹出,
# 避免污染后续文件 (与 test_r254_trading_domain.py 同型污染)。
# ---------------------------------------------------------------------------
for _mod_name in ('core.trading.order_repository',
                  'core.trading.account_repository',
                  'core.trading.order_models',
                  'core.trading.trading_types',
                  'core.trading.order_executor',
                  'core.trading.account_models',
                  'core.services.trading_service',
                  'gui.widgets.trading_panel'):
    sys.modules.pop(_mod_name, None)


if __name__ == '__main__':
    unittest.main()
