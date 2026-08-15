# -*- coding: utf-8 -*-
"""R272 修复验证: modify_order 死锁 (RLock) + 买入建议 Decimal→float

背景 (R272 交叉验证发现, 全部含源码行号):
- 缺陷1: order_service._get_order_lock (:71-76) 用 threading.Lock (非重入);
  modify_order (:474) 持锁后调 cancel_order (:496), cancel_order (:399) 对
  同一把非重入锁再取 → 永久死锁 (test_order_management_integration test_05 卡死)。
  修复: :76 threading.Lock() → threading.RLock() (可重入)。
- 缺陷2: trading_panel._get_current_price (:1237) 返回 Optional[Decimal];
  R271 _on_suggest_quantity_clicked (:686-691) 未转 float, :704
  stop_loss_price = current_price * 0.98 为 Decimal * float → TypeError,
  真实价格路径必失败 (被 :722 except 吞掉, 建议数量永远算不出)。
  修复: :692-695 _get_current_price 成功分支补 float(current_price)。

运行: conda activate hikyuu; python -m pytest tests/test_r272_fix_verify.py -q
"""
import os
import sys
import threading
from datetime import datetime
from decimal import Decimal
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


def _make_order():
    """PENDING 订单 (modify_order 前置条件)"""
    now = datetime.now()
    return Order(
        order_id='O-r272', strategy_id='default', asset_type=AssetType.STOCK_A,
        stock_code='000001', order_type=OrderType.BUY, order_category=OrderCategory.LIMIT,
        order_price=10.0, order_quantity=100, order_status=OrderStatus.PENDING,
        create_time=now, update_time=now,
    )


def _make_service():
    """构造 OrderService 实例 (patch __init__, 绕过重型初始化)"""
    from core.trading.order_service import OrderService
    with patch.object(OrderService, '__init__', return_value=None):
        inst = OrderService()
    inst.service_container = MagicMock()
    inst.event_bus = MagicMock()
    inst.validator = MagicMock()
    inst.validator.validate_order.return_value = SimpleNamespace(
        passed=True, message='ok', error_code=None)
    inst.repository = MagicMock()
    inst.executor = MagicMock()
    inst._order_locks = {}
    inst._lock_manager_lock = threading.Lock()
    inst._cleanup_order_lock = MagicMock()
    inst._disposed = False
    return inst


# ==================== 1. modify_order 死锁修复 (RLock) ====================

class TestModifyOrderDeadlockFix:
    def test_get_order_lock_returns_rlock(self):
        """_get_order_lock 返回 threading.RLock (可重入, order_service.py:71-77)"""
        inst = _make_service()
        lock = inst._get_order_lock('O-r272')
        # threading.RLock 是工厂函数非类型, 用 type(threading.RLock()) 作 isinstance 基准
        assert isinstance(lock, type(threading.RLock())), \
            f"应为 RLock (可重入), 实际: {type(lock).__name__}"

    def test_modify_order_no_deadlock_cancel_reentrant(self):
        """modify_order 持锁内调 cancel_order (同锁重入) 不再死锁 (order_service.py:474/:496)"""
        from core.trading.trading_types import ExecutionStatus, ExecutionResult
        inst = _make_service()
        order = _make_order()
        inst.repository.get_order.return_value = order
        inst.executor.cancel_order.return_value = ExecutionResult(
            order_id='O-r272', status=ExecutionStatus.SUCCESS, message='ok')
        # 阻断 create_order (不进入新订单创建)
        inst.create_order = MagicMock(return_value=None)

        box = {}
        def _run():
            try:
                box['result'] = inst.modify_order('O-r272')
            except Exception as e:  # pragma: no cover
                box['error'] = e

        t = threading.Thread(target=_run)
        t.start()
        t.join(timeout=5.0)
        assert not t.is_alive(), \
            'modify_order 5 秒未返回 → 死锁 (RLock 修复未生效)'
        assert 'error' not in box, f"modify_order 异常: {box.get('error')}"
        # cancel_order 同锁重入成功 (RLock 语义验证)
        inst.executor.cancel_order.assert_called_once_with('O-r272')

    def test_same_lock_object_across_calls(self):
        """同一订单多次获取锁返回同一对象 (锁复用语义不变)"""
        inst = _make_service()
        lock1 = inst._get_order_lock('O-r272')
        lock2 = inst._get_order_lock('O-r272')
        assert lock1 is lock2


# ==================== 2. 买入建议 Decimal→float 修复 ====================

def _unmock_gui_widgets():
    """清除 tests/conftest.py:51 gui.widgets 顶层包 MagicMock"""
    for _m in list(sys.modules):
        if _m == 'gui.widgets' or _m.startswith('gui.widgets.'):
            del sys.modules[_m]


class TestSuggestQuantityDecimalFix:
    def test_decimal_price_converted_to_float(self):
        """_get_current_price 返回 Decimal → 转 float 传给 calculate_position_size
        (不再抛 Decimal*float TypeError, trading_panel.py:692-695)"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._current_stock_code = '000001'
        inst._get_current_price = MagicMock(return_value=Decimal('10.5'))
        inst._portfolio = SimpleNamespace(available_cash=10000.0)
        inst.buy_quantity_spin = MagicMock()
        monitor = MagicMock()
        monitor.calculate_position_size.return_value = 500
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        with patch('gui.widgets.trading_panel.QMessageBox') as mb:
            inst._on_suggest_quantity_clicked()
        # 核心: 不抛 TypeError, calculate_position_size 被调用且参数为 float
        monitor.calculate_position_size.assert_called_once()
        kwargs = monitor.calculate_position_size.call_args[1]
        assert isinstance(kwargs['current_price'], float), \
            f"current_price 应为 float, 实际: {type(kwargs['current_price'])}"
        assert isinstance(kwargs['stop_loss_price'], float), \
            f"stop_loss_price 应为 float, 实际: {type(kwargs['stop_loss_price'])}"
        assert kwargs['stop_loss_price'] == pytest.approx(10.5 * 0.98)
        inst.buy_quantity_spin.setValue.assert_called_once_with(500)
        assert mb.information.called, '应弹出建议数量提示 (修复前此处为计算失败警告)'

    def test_float_price_unchanged(self):
        """_get_current_price 已返回 float → 保持 float 语义不变"""
        _unmock_gui_widgets()
        from gui.widgets.trading_panel import TradingPanel
        inst = TradingPanel.__new__(TradingPanel)
        inst._current_stock_code = '000001'
        inst._get_current_price = MagicMock(return_value=10.5)
        inst._portfolio = SimpleNamespace(available_cash=10000.0)
        inst.buy_quantity_spin = MagicMock()
        monitor = MagicMock()
        monitor.calculate_position_size.return_value = 300
        inst._resolve_position_risk_monitor = MagicMock(return_value=monitor)
        with patch('gui.widgets.trading_panel.QMessageBox'):
            inst._on_suggest_quantity_clicked()
        kwargs = monitor.calculate_position_size.call_args[1]
        assert kwargs['current_price'] == 10.5
        assert isinstance(kwargs['current_price'], float)

    def test_src_contains_decimal_conversion(self):
        """源码断言: 买入建议 handler 含 float(current_price) 转换 (trading_panel.py:695)"""
        src = (PROJECT_ROOT / 'gui' / 'widgets' / 'trading_panel.py').read_text(encoding='utf-8')
        assert 'current_price = float(current_price)' in src


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
