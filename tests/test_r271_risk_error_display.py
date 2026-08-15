# -*- coding: utf-8 -*-
"""R271 正式回归测试: 熔断错误码 UI 呈现 (数据层 error_code 落盘 + UI 展示)

背景 (R271, 全部含源码行号):
- 问题1: 熔断错误码 UI 零呈现 —— DAILY_LOSS_LIMIT_EXCEEDED (order_validator.py:374)
  → order_service.create_order (:98-103) 发 order_validation_failed, gui/ 零订阅;
  RISK_HALTED (order_executor.py:801) → ExecutionResult.error_code →
  order_service.submit_order 失败分支, 事件载荷/持久化原丢弃。
- 修复 (方案 C 主 + A 辅, performance_history 加 error_code 方案否决:
  execution_history 表无 core 写入方, 语义为执行质量):
  数据层: Order.error_code (order_models.py:74/:146/:193) + 4 处仓库持久化
  (order_repository.py:79/:107/:202/:233/:296/:325/:402/:431) + 建表列
  (asset_database_manager.py:450) + order_service 3 处 (submit_order 失败落盘
  :367, order_rejected 载荷 :341, order_submit_failed 载荷 :383)
  UI 层: order_management_dialog 12 列表格 + 拒绝原因列 (:204-207/:765-771) +
  _format_reject_reason 映射 (:782-796) + 详情面板错误码 (:1123-1126) +
  订阅 order_validation_failed (:643/:656/:1382-1396) 覆盖订单未创建型拒绝。

运行: conda activate hikyuu; python -m pytest tests/test_r271_risk_error_display.py -q
"""
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLBACKEND', 'Agg')

from core.plugin_types import AssetType  # noqa: E402
from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory  # noqa: E402
from core.trading.trading_types import ExecutionStatus, ExecutionResult  # noqa: E402


def _make_order(error_code=None, error_message=None):
    """构造 Order 实例 (error_code 为 R271 新增字段)"""
    now = datetime.now()
    return Order(
        order_id='O-r271', strategy_id='default', asset_type=AssetType.STOCK_A,
        stock_code='000001', order_type=OrderType.BUY, order_category=OrderCategory.MARKET,
        order_price=10.0, order_quantity=100, order_status=OrderStatus.SUBMITTED,
        create_time=now, update_time=now, error_code=error_code, error_message=error_message,
    )


# ==================== 1. Order.error_code 序列化/反序列化 ====================

class TestOrderErrorCode:
    def test_to_dict_keeps_error_code(self):
        """Order.to_dict() 保留 error_code (order_models.py:146)"""
        order = _make_order(error_code='RISK_HALTED')
        d = order.to_dict()
        assert d['error_code'] == 'RISK_HALTED'

    def test_from_dict_restores_error_code(self):
        """Order.from_dict() 恢复 error_code (order_models.py:193)"""
        d = _make_order(error_code='DAILY_LOSS_LIMIT_EXCEEDED').to_dict()
        order = Order.from_dict(d)
        assert order.error_code == 'DAILY_LOSS_LIMIT_EXCEEDED'

    def test_from_dict_without_error_code_defaults_none(self):
        """旧数据无 error_code 字段时反序列化不报错 (order_models.py:193 .get)"""
        d = _make_order().to_dict()
        del d['error_code']
        order = Order.from_dict(d)
        assert order.error_code is None


# ==================== 2. order_repository 持久化 SQL 含 error_code ====================

_REPO = PROJECT_ROOT / 'core' / 'trading' / 'order_repository.py'
_DIALOG = PROJECT_ROOT / 'gui' / 'dialogs' / 'order_management_dialog.py'


class TestRepositoryErrorCodeColumn:
    def _source(self):
        return _REPO.read_text(encoding='utf-8')

    def test_save_order_insert_has_error_code(self):
        """save_order INSERT 列含 error_code (order_repository.py:79)"""
        src = self._source()
        assert 'error_code' in src.split('def save_order')[1].split('def save_orders_batch')[0]
        assert "error_code" in src

    def test_save_orders_batch_insert_has_error_code(self):
        """save_orders_batch INSERT 列含 error_code (order_repository.py:202)"""
        src = self._source()
        assert 'error_code' in src.split('def save_orders_batch')[1].split('def update_order')[0]

    def test_update_order_set_has_error_code(self):
        """update_order SET 子句含 error_code (order_repository.py:296)"""
        src = self._source()
        seg = src.split('def update_order')[1].split('def update_orders_batch')[0]
        assert 'error_code = ?' in seg

    def test_update_orders_batch_set_has_error_code(self):
        """update_orders_batch SET 子句含 error_code (order_repository.py:402)"""
        src = self._source()
        seg = src.split('def update_orders_batch')[1]
        assert 'error_code = ?' in seg


# ==================== 3. order_service 错误码落盘 + 事件载荷 ====================

def _make_service(validation_passed=True, exec_result=None):
    """构造 OrderService 实例 (patch __init__, 绕过重型初始化)

    R271 治理: exec_result 以 (status_name, message, error_code) 三元组传入,
    内部用 order_service 模块自身的 ExecutionStatus/ExecutionResult 构造 —
    submit_order 的失败判断 (:362) 与事件载荷均引用该模块内部类, 避免与
    测试文件顶部导入类发生类身份漂移 (test_r256 模块级 pop sys.modules 场景)。
    """
    import core.trading.order_service as _os
    OrderService = _os.OrderService
    with patch.object(OrderService, '__init__', return_value=None):
        inst = OrderService()
    inst.service_container = MagicMock()
    inst.event_bus = MagicMock()
    inst.validator = MagicMock()
    inst.validator.validate_order.return_value = SimpleNamespace(
        passed=validation_passed, message='ok', error_code=None)
    inst.repository = MagicMock()
    inst.executor = MagicMock()
    if exec_result is not None:
        status_name, message, error_code = exec_result
        inst.executor.submit_order.return_value = _os.ExecutionResult(
            order_id='O-r271', status=_os.ExecutionStatus[status_name],
            message=message, error_code=error_code)
    inst._order_locks = {}
    inst._lock_manager_lock = threading.Lock()
    inst._cleanup_order_lock = MagicMock()
    inst._disposed = False
    return inst


class TestServiceErrorCode:
    def test_failed_execution_writes_error_code_to_order(self):
        """submit_order 执行失败: Order.error_code = RISK_HALTED 并 update_order (order_service.py:367-369)"""
        from core.trading.order_service import OrderService
        order = _make_order()
        inst = _make_service(exec_result=('FAILED', '风控熔断中', 'RISK_HALTED'))
        inst.repository.get_order.return_value = order
        with patch.object(OrderService, '_get_order_lock',
                          return_value=threading.Lock()):
            result = inst.submit_order('O-r271')
        assert result.status.name == 'FAILED'
        assert order.error_code == 'RISK_HALTED'
        # update_order 被调用且订单已写入 error_code
        inst.repository.update_order.assert_called_once()
        saved = inst.repository.update_order.call_args[0][0]
        assert saved.error_code == 'RISK_HALTED'

    def test_order_submit_failed_event_carries_error_code(self):
        """order_submit_failed 事件载荷含 error_code (order_service.py:380-384)"""
        order = _make_order()
        inst = _make_service(exec_result=('FAILED', '当日亏损达到上限', 'DAILY_LOSS_LIMIT_EXCEEDED'))
        inst.repository.get_order.return_value = order
        from core.trading.order_service import OrderService
        with patch.object(OrderService, '_get_order_lock',
                          return_value=threading.Lock()):
            inst.submit_order('O-r271')
        events = [c[0][0] for c in inst.event_bus.publish.call_args_list]
        assert 'order_submit_failed' in events
        for c in inst.event_bus.publish.call_args_list:
            if c[0][0] == 'order_submit_failed':
                kwargs = c[1] if c[1] else {}
                assert kwargs.get('error_code') == 'DAILY_LOSS_LIMIT_EXCEEDED'
                return
        pytest.fail('order_submit_failed 事件未发布')

    def test_order_rejected_event_carries_error_code(self):
        """验证失败拒绝: order_rejected 载荷含 error_code (order_service.py:338-342)"""
        order = _make_order()
        inst = _make_service(validation_passed=False)
        inst.validator.validate_order.return_value = SimpleNamespace(
            passed=False, message='当日亏损达到上限', error_code='DAILY_LOSS_LIMIT_EXCEEDED')
        inst.repository.get_order.return_value = order
        from core.trading.order_service import OrderService
        with patch.object(OrderService, '_get_order_lock',
                          return_value=threading.Lock()):
            inst.submit_order('O-r271')
        for c in inst.event_bus.publish.call_args_list:
            if c[0][0] == 'order_rejected':
                kwargs = c[1] if c[1] else {}
                assert kwargs.get('error_code') == 'DAILY_LOSS_LIMIT_EXCEEDED'
                assert kwargs.get('error') == '当日亏损达到上限'
                return
        pytest.fail('order_rejected 事件未发布 (验证失败拒绝路径)')


# ==================== 4. UI 层: 拒绝原因格式化 + 事件订阅 + handler ====================

class TestUiRejectReason:
    def test_format_reject_reason_code_map(self):
        """_format_reject_reason 错误码映射 (order_management_dialog.py:782-796)"""
        from gui.dialogs.order_management_dialog import OrderManagementDialog
        assert OrderManagementDialog._format_reject_reason('RISK_HALTED', '') == '风控熔断'
        assert OrderManagementDialog._format_reject_reason(
            'DAILY_LOSS_LIMIT_EXCEEDED', '') == '当日亏损熔断'
        assert OrderManagementDialog._format_reject_reason('RISK_CHECK_FAILED', '') == '风控拒绝'

    def test_format_reject_reason_with_message_truncated(self):
        """错误码 + 消息: 文案拼接且消息截断 40 字符 (order_management_dialog.py:791-792)"""
        from gui.dialogs.order_management_dialog import OrderManagementDialog
        long_msg = 'x' * 100
        r = OrderManagementDialog._format_reject_reason('RISK_HALTED', long_msg)
        assert r == f'风控熔断: {long_msg[:40]}'
        assert len(r) <= 60

    def test_format_reject_reason_only_message(self):
        """仅 error_message 无 error_code: 直接截断 40 (order_management_dialog.py:794-795)"""
        from gui.dialogs.order_management_dialog import OrderManagementDialog
        assert OrderManagementDialog._format_reject_reason(None, 'abc') == 'abc'
        assert OrderManagementDialog._format_reject_reason(None, None) == ''

    def test_dialog_12_columns_with_reject_reason_header(self):
        """订单表格 12 列且含拒绝原因表头 (order_management_dialog.py:204-207)"""
        src = _DIALOG.read_text(encoding='utf-8')
        assert 'setColumnCount(12)' in src
        assert '"拒绝原因"' in src

    def test_dialog_subscribes_validation_failed(self):
        """subscribe_events 订阅 order_validation_failed + closeEvent 退订 (order_management_dialog.py:643/:656)"""
        src = _DIALOG.read_text(encoding='utf-8')
        assert "self.event_bus.subscribe('order_validation_failed', self.on_order_validation_failed_event)" in src
        assert "self.event_bus.unsubscribe('order_validation_failed', self.on_order_validation_failed_event)" in src

    def test_validation_failed_handler_updates_status_label(self):
        """on_order_validation_failed_event: 状态栏展示拒绝原因 (order_management_dialog.py:1382-1396)"""
        from gui.dialogs.order_management_dialog import OrderManagementDialog
        inst = OrderManagementDialog.__new__(OrderManagementDialog)
        inst.status_label = MagicMock()
        event = SimpleNamespace(
            stock_code='000001', error='当日亏损达到上限', error_code='DAILY_LOSS_LIMIT_EXCEEDED')
        inst.on_order_validation_failed_event(event)
        inst.status_label.setText.assert_called_once()
        text = inst.status_label.setText.call_args[0][0]
        assert '当日亏损熔断' in text
        assert '000001' in text


# ==================== 5. 资金管理生产消费点 (calculate_position_size / calculate_exposure) ====================

_PANEL = PROJECT_ROOT / 'gui' / 'widgets' / 'trading_panel.py'


def _unmock_gui_widgets():
    """清除 tests/conftest.py:51 gui.widgets 顶层包 MagicMock (mock 无 __path__ 阻断真实子模块导入)"""
    for _m in list(sys.modules):
        if _m == 'gui.widgets' or _m.startswith('gui.widgets.'):
            del sys.modules[_m]


class TestMoneyManagerConsumption:
    def test_suggest_quantity_btn_wired(self):
        """建议数量按钮创建并连接 _on_suggest_quantity_clicked (trading_panel.py:271-275)"""
        src = _PANEL.read_text(encoding='utf-8')
        assert "self.suggest_quantity_btn = QPushButton(\"建议数量\")" in src
        assert "clicked.connect(self._on_suggest_quantity_clicked)" in src

    def test_exposure_label_wired(self):
        """多空敞口标签创建且 _update_portfolio_display 刷新 (trading_panel.py:341-343/:1235-1236)"""
        src = _PANEL.read_text(encoding='utf-8')
        assert 'self.exposure_label = QLabel("多: -- / 空: -- / 净: --")' in src
        assert 'self.exposure_label.setText(self._compute_exposure_display())' in src

    def test_suggest_quantity_flow_calls_calculate_position_size(self):
        """_on_suggest_quantity_clicked: 真实调用 PositionRiskMonitor.calculate_position_size
        并将建议量写入 buy_quantity_spin (trading_panel.py:666-715)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._current_stock_code = '000001'
        inst._get_current_price = MagicMock(return_value=10.0)
        inst._portfolio = SimpleNamespace(available_cash=10000.0)
        inst.buy_quantity_spin = MagicMock()
        monitor = MagicMock()
        monitor.calculate_position_size.return_value = 500
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_quantity_clicked()
        monitor.calculate_position_size.assert_called_once()
        call_kwargs = monitor.calculate_position_size.call_args[1]
        assert call_kwargs['current_price'] == 10.0
        assert call_kwargs['available_cash'] == 10000.0
        assert call_kwargs['stop_loss_price'] == pytest.approx(9.8)
        inst.buy_quantity_spin.setValue.assert_called_once_with(500)
        assert mb.information.called, '应弹出建议数量提示'

    def test_suggest_quantity_zero_result_no_spin_write(self):
        """calculate_position_size 返回 0: 不写入数量, 仅警告提示 (trading_panel.py:708-711)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._current_stock_code = '000001'
        inst._get_current_price = MagicMock(return_value=10.0)
        inst._portfolio = SimpleNamespace(available_cash=10000.0)
        inst.buy_quantity_spin = MagicMock()
        monitor = MagicMock()
        monitor.calculate_position_size.return_value = 0
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_quantity_clicked()
        inst.buy_quantity_spin.setValue.assert_not_called()
        assert mb.warning.called

    def test_exposure_display_adapts_side_to_position_type(self):
        """_compute_exposure_display: 系统 Position (side) → PositionManager (position_type) 适配
        并返回格式化敞口文本 (trading_panel.py:717-778)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._service_container = None
        inst._portfolio = SimpleNamespace(positions={
            '000001': SimpleNamespace(quantity=100, current_price=10.0),
            '000002': SimpleNamespace(quantity=50, current_price=20.0),
        })
        monitor = MagicMock()
        monitor.calculate_exposure.return_value = {'long': 2000.0, 'short': 0.0, 'net': 2000.0}
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        text = inst._compute_exposure_display()
        assert '¥2,000' in text
        monitor.calculate_exposure.assert_called_once()
        adapted = monitor.calculate_exposure.call_args[0][0]
        assert len(adapted) == 2
        from core.trading_engine import PositionType
        assert all(p.position_type == PositionType.LONG for p in adapted)
        assert adapted[0].quantity == 100 and adapted[0].current_price == 10.0

    def test_exposure_display_monitor_unavailable(self):
        """PositionRiskMonitor 解析失败: 返回占位文本, 不抛异常 (trading_panel.py:726-728)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._service_container = None
        inst._portfolio = SimpleNamespace(positions={})
        inst._resolve_position_risk_monitor = MagicMock(return_value=None)
        assert inst._compute_exposure_display() == "多: -- / 空: -- / 净: --"
