# -*- coding: utf-8 -*-
"""R270 正式回归测试: 风险评估面板修复 + 熔断错误码保留 + 止损空转验证 + 止盈对称融入

背景 (R270, 全部含源码行号):
- P1: gui/widgets/bettafish_dashboard/risk_assessment_panel.py:19 缺 QPoint 导入 →
  RiskGauge.paintEvent (该文件 L75/77) 首绘 NameError。已修复 (L19 补 QPoint,
  L16 删重复 QDial, L82-89 删死刻度变量段)。
- P2: gui/widgets/enhanced_ui/smart_recommendation_panel.py:1138-1142 向只接受
  (parent, bettafish_agent) 的 BettaFishDashboard 传 monitoring_service= kwarg →
  TypeError (被 L1176 try/except 吞掉显示红标)。已修复 (L1129 return widget,
  L1132-1137 仅传 bettafish_agent)。
- C: 熔断错误码被硬编码吞掉 —— submit_order (order_executor.py:1157) 与批量
  (:1352) 原写死 RISK_CHECK_FAILED, 丢失 RISK_HALTED/DAILY_LOSS_LIMIT_EXCEEDED。
  已修复: risk_check_result.get('error_code', 'RISK_CHECK_FAILED')。
- D: 止损空转根因 stop_loss_levels 零写入 (risk_control.py:135 唯一写入点
  calculate_stop_loss 全库零调用 → :163-165 恒放行)。R269-D3 已修复
  (order_executor._fill_stop_loss_level :931-968 填充 + :198-202 兜底)。本文件
  以正式用例固化验证。
- E: 止盈对称融入 (R270 新增): risk_control.py 新增 take_profit_levels (:14) /
  calculate_take_profit (:144-175) / check_take_profit_trigger (:219-253);
  order_executor._fill_take_profit_level (:970-1007) 填充;
  position_risk_monitor.get_dynamic_take_profit (:121-145) 新增 position 参数。

运行: conda activate hikyuu; python -m pytest tests/test_r270_risk_panel_take_profit.py -q
"""
import ast
import os
import sys
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

from core.risk_control import RiskControlStrategy  # noqa: E402


# ---------------- 工具函数 ----------------

def _unmock_gui_widgets():
    """清除 tests/conftest.py:51 对 gui.widgets 顶层包的 MagicMock (mock 无 __path__,
    会阻断真实子模块导入)。面板测试需要真实模块。"""
    for _m in list(sys.modules):
        if _m == 'gui.widgets' or _m.startswith('gui.widgets.'):
            del sys.modules[_m]


def _make_order(stock_code='000001', price=10.0, qty=100, account_id='acc_001'):
    return SimpleNamespace(
        order_id='O-test', account_id=account_id, stock_code=stock_code,
        order_price=price, order_quantity=qty, create_time=datetime.now(),
    )


def _make_executor(monitor=None):
    """构造 OrderExecutor 实例 (patch __init__)。service_container 全 mock:
    - try_resolve: EnhancedRiskMonitor → None (跳过增强风控); PositionRiskMonitor → monitor
    - resolve(AccountManager) → mock 账户 (资金充足, 无持仓限制)
    - _get_avg_entry_price / _get_position 固定为 10.0 / 100
    """
    from core.trading.order_executor import OrderExecutor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        inst = OrderExecutor()
    inst._logger = MagicMock()
    inst.service_container = MagicMock()
    inst._halted = False
    inst._risk_control_enabled = True
    inst._trading_mode = 'paper'

    def _try_resolve(cls):
        name = getattr(cls, '__name__', '')
        if name == 'EnhancedRiskMonitor':
            return None
        if name == 'PositionRiskMonitor':
            return monitor
        return None

    inst.service_container.try_resolve = MagicMock(side_effect=_try_resolve)

    mock_acct_mgr = MagicMock()
    mock_account = MagicMock()
    mock_account.available_cash = 1000000.0
    mock_account.position_limit = None
    mock_acct_mgr.get_account = MagicMock(return_value=mock_account)
    mock_acct_mgr.get_account_positions = MagicMock(return_value=[])
    inst.service_container.resolve = MagicMock(return_value=mock_acct_mgr)

    inst._get_avg_entry_price = MagicMock(return_value=10.0)
    inst._get_position = MagicMock(return_value=100)
    return inst


def _make_tp_monitor(tp_price=10.2, stop_price=None):
    """构造 PositionRiskMonitor 层 mock: 止盈价固定, 止损价默认 None (触发降级)"""
    m = MagicMock()
    m.get_dynamic_take_profit = MagicMock(return_value=tp_price)
    m.get_dynamic_stop_price = MagicMock(return_value=stop_price)
    return m


# ==================== P1: 风险评估面板 ====================

def test_p1_risk_panel_imports_qpoint():
    """risk_assessment_panel.py: QPoint 从 QtCore 导入 (PyQt5 中 QPoint 属于 QtCore,
    不在 QtGui —— 原 :19 从 QtGui 导入会在模块加载时 ImportError)"""
    src = (PROJECT_ROOT / 'gui/widgets/bettafish_dashboard/risk_assessment_panel.py').read_text(encoding='utf-8')
    tree = ast.parse(src)
    qtcore_names, qtgui_names = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == 'PyQt5.QtCore':
                qtcore_names = [a.name for a in node.names]
            elif node.module == 'PyQt5.QtGui':
                qtgui_names = [a.name for a in node.names]
    assert 'QPoint' in qtcore_names, 'QPoint 必须从 PyQt5.QtCore 导入'
    assert 'QPoint' not in qtgui_names, 'QPoint 不得从 PyQt5.QtGui 导入 (该模块无 QPoint)'
    # QDial 仅出现在 QtWidgets 导入组 (L16), 原 QtGui 组重复 QDial 已删
    assert src.count('QDial') == 1, f'QDial 重复导入: {src.count("QDial")}'


def test_p1_risk_gauge_paint_no_nameerror():
    """RiskGauge 绘制冒烟: grab() 强制同步绘制, excepthook 收集异常 (QPoint 探测)"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    collected = []
    orig_hook = sys.excepthook

    def _hook(t, v, tb):
        collected.append((t.__name__, str(v)))

    sys.excepthook = _hook
    try:
        _unmock_gui_widgets()
        from gui.widgets.bettafish_dashboard.risk_assessment_panel import RiskGauge
        gauge = RiskGauge()
        gauge.resize(120, 120)
        gauge.show()
        app.processEvents()
        pix = gauge.grab()
        gauge.close()
        assert not pix.isNull()
    finally:
        sys.excepthook = orig_hook

    assert not collected, f'RiskGauge 绘制异常: {collected}'


def test_p1_risk_assessment_panel_data_keys():
    """真实 BettaFishAgent + RiskAssessmentPanel: _load_risk_data/_update_risk_data
    无异常, get_risk_assessment 返回面板消费全部键 (bettafish_agent.py:567-688)"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    expected = {
        'overall_risk', 'overall_risk_level',
        'var_95', 'max_drawdown', 'sharpe_ratio', 'volatility', 'correlation', 'concentration',
        'market_risk', 'liquidity_risk', 'credit_risk', 'operational_risk', 'concentration_risk',
        'market_risk_pct', 'liquidity_risk_pct', 'credit_risk_pct', 'operational_risk_pct',
        'concentration_risk_pct',
    }

    _unmock_gui_widgets()
    from core.agents.bettafish_agent import BettaFishAgent
    from gui.widgets.bettafish_dashboard.risk_assessment_panel import RiskAssessmentPanel

    agent = BettaFishAgent()
    assessment = agent.get_risk_assessment()
    assert expected.issubset(assessment.keys()), f'get_risk_assessment 缺键: {expected - assessment.keys()}'

    panel = RiskAssessmentPanel(bettafish_agent=agent)
    try:
        panel._load_risk_data()
        panel._update_risk_data()
        data = panel.get_risk_data()
        assert expected.issubset(data.keys()), f'面板 _risk_data 缺键: {expected - data.keys()}'
    finally:
        panel.close()


# ==================== P2: 智能推荐面板 ====================

def test_p2_smart_reco_no_monitoring_kwarg():
    """smart_recommendation_panel.py: 不再向 BettaFishDashboard 传 monitoring_service=
    kwarg; _create_bettafish_dashboard_tab 末尾 return widget"""
    src = (PROJECT_ROOT / 'gui/widgets/enhanced_ui/smart_recommendation_panel.py').read_text(encoding='utf-8')
    assert 'monitoring_service=' not in src, '仍存在 monitoring_service= kwarg 调用'

    tree = ast.parse(src)
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == '_create_bettafish_dashboard_tab']
    assert len(funcs) == 1
    ret = funcs[0].body[-1]
    assert isinstance(ret, ast.Return), '方法末尾非 return'
    assert isinstance(ret.value, ast.Name) and ret.value.id == 'widget', '返回值非 widget'


# ==================== C: 熔断错误码保留 ====================

def test_c_error_code_halted_preserved_single():
    """submit_order: 熔断拒绝时 ExecutionResult.error_code = RISK_HALTED (非 RISK_CHECK_FAILED)"""
    from core.trading.order_executor import ExecutionResult, ExecutionStatus, OrderExecutor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        inst = OrderExecutor()
    inst._logger = MagicMock()
    inst._validate_order_integrity = MagicMock(return_value=None)
    inst._pre_trade_risk_check = MagicMock(return_value={
        'passed': False, 'reason': '风控熔断中, 已暂停新订单受理', 'error_code': 'RISK_HALTED'})

    order = SimpleNamespace(order_id='O1', asset_type=SimpleNamespace(value='STOCK'))
    result = inst.submit_order(order)
    assert isinstance(result, ExecutionResult)
    assert result.status == ExecutionStatus.FAILED
    assert result.error_code == 'RISK_HALTED'


def test_c_error_code_daily_loss_preserved_batch():
    """submit_orders_batch: 当日亏损熔断拒绝时 error_code = DAILY_LOSS_LIMIT_EXCEEDED"""
    from core.plugin_types import AssetType
    from core.trading.order_executor import ExecutionResult, ExecutionStatus, OrderExecutor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        inst = OrderExecutor()
    inst._logger = MagicMock()
    inst._validate_order_integrity = MagicMock(return_value=None)
    inst._pre_trade_risk_check = MagicMock(return_value={
        'passed': False, 'reason': '当日亏损达到上限', 'error_code': 'DAILY_LOSS_LIMIT_EXCEEDED'})
    # 批量方法结尾调用 repository.update_orders_batch (:1440) 与 event_bus.publish (:1447)
    inst.repository = MagicMock()
    inst.event_bus = MagicMock()

    asset_type = AssetType.STOCK_A
    order = SimpleNamespace(
        order_id='O2', asset_type=asset_type,
        order_status=None, update_time=None, error_message=None)
    results = inst.submit_orders_batch([order])
    assert len(results) == 1
    assert results[0].status == ExecutionStatus.FAILED
    assert results[0].error_code == 'DAILY_LOSS_LIMIT_EXCEEDED'


# ==================== D: 止损空转修复 (正式固化) ====================

def test_d_stop_loss_fill_writes_level():
    """_fill_stop_loss_level 填充后 stop_loss_levels['000001'] 非空 (修复零写入)"""
    from core.trading.order_executor import OrderExecutor
    monitor = _make_tp_monitor(stop_price=9.0)
    inst = _make_executor(monitor)
    rc = RiskControlStrategy()
    inst._fill_stop_loss_level(rc, _make_order(price=10.0), 10.0, 100)
    assert rc.stop_loss_levels.get('000001') == pytest.approx(9.0), '止损水平未被填充'


def test_d_stop_loss_e2e_reject():
    """端到端: 现价 8.5 跌破动态止损 9.0 → _pre_trade_risk_check 拒单 (风控止损触发)"""
    from core.trading.order_executor import OrderExecutor
    monitor = _make_tp_monitor(tp_price=12.0, stop_price=9.0)
    inst = _make_executor(monitor)
    result = inst._pre_trade_risk_check(_make_order(price=8.5))
    assert result['passed'] is False
    assert '风控止损触发' in result['reason']
    assert '多头止损触发' in result['reason']


def test_d_stop_loss_e2e_pass():
    """端到端: 现价 9.5 高于止损 9.0 且低于止盈 12.0 → 放行"""
    from core.trading.order_executor import OrderExecutor
    monitor = _make_tp_monitor(tp_price=12.0, stop_price=9.0)
    inst = _make_executor(monitor)
    result = inst._pre_trade_risk_check(_make_order(price=9.5))
    assert result['passed'] is True


def test_d_stop_loss_fallback_ratio():
    """无填充 level 时固定比例兜底: 多头 -5% 触发 (risk_control.py:198-202)"""
    rc = RiskControlStrategy()  # 不填充任何 level
    triggered, reason = rc.check_stop_loss_trigger('A', 100, 10.0, 9.4)
    assert triggered is True
    assert '多头止损触发' in reason
    # 现价未跌破 5% 兜底线 → 放行
    triggered2, _ = rc.check_stop_loss_trigger('A', 100, 10.0, 9.6)
    assert triggered2 is False
    # 空头兜底: +5% (10.0 * 1.05 = 10.5)
    triggered3, reason3 = rc.check_stop_loss_trigger('B', -100, 10.0, 10.6)
    assert triggered3 is True
    assert '空头止损触发' in reason3


# ==================== E: 止盈对称融入 (R270 新增) ====================

def test_e_take_profit_fill_writes_level():
    """_fill_take_profit_level 填充后 take_profit_levels['000001'] = 10.2"""
    from core.trading.order_executor import OrderExecutor
    monitor = _make_tp_monitor(tp_price=10.2)
    inst = _make_executor(monitor)
    rc = RiskControlStrategy()
    inst._fill_take_profit_level(rc, _make_order(price=10.0), 10.0, 100)
    assert rc.take_profit_levels.get('000001') == pytest.approx(10.2)


def test_e_take_profit_fill_fallback():
    """_fill_take_profit_level 降级路径: 容器无 monitor → 真实 PositionRiskMonitor
    (AdaptiveTakeProfit 无 K 线 → 固定比例降级 1.02 → 10.2, position_risk_monitor.py:144-145)"""
    from core.trading.order_executor import OrderExecutor
    inst = _make_executor(monitor=None)  # try_resolve 返回 None → 构造真实 monitor
    rc = RiskControlStrategy()
    inst._fill_take_profit_level(rc, _make_order(price=10.0), 10.0, 100)
    assert rc.take_profit_levels.get('000001') == pytest.approx(10.2)


def test_e_calculate_take_profit_conservative():
    """calculate_take_profit 保守计算 (risk_control.py:144-175):
    vol=0.2, beta=1.0 → 10*1.2=12.0; position_ratio>0.8 → *1.05=12.6"""
    rc = RiskControlStrategy()
    tp = rc.calculate_take_profit(
        asset='000001', price=10.0, position=100,
        risk_metrics={'market_risk': {'volatility': 0.2, 'beta': 1.0}})
    assert tp == pytest.approx(12.6)
    assert rc.take_profit_levels.get('000001') == pytest.approx(12.6)
    # 空头: max(10*0.8, 10*0.8)=8.0 → *1.05=8.4
    tp_short = rc.calculate_take_profit(
        asset='000002', price=10.0, position=-100,
        risk_metrics={'market_risk': {'volatility': 0.2, 'beta': 1.0}})
    assert tp_short == pytest.approx(8.4)


def test_e_take_profit_trigger_direction():
    """check_take_profit_trigger 多/空头触发与放行 (risk_control.py:240-249)"""
    rc = RiskControlStrategy()
    rc.take_profit_levels['A'] = 11.0
    # 多头: 现价 >= 止盈价 → 触发
    ok, reason = rc.check_take_profit_trigger('A', 100, 10.0, 11.5)
    assert ok is True and '多头止盈触发' in reason
    # 多头: 未达 → 放行
    ok2, _ = rc.check_take_profit_trigger('A', 100, 10.0, 10.5)
    assert ok2 is False

    rc.take_profit_levels['B'] = 9.0
    # 空头: 现价 <= 止盈价 → 触发
    ok3, reason3 = rc.check_take_profit_trigger('B', -100, 10.0, 8.5)
    assert ok3 is True and '空头止盈触发' in reason3
    # 空头: 未达 → 放行
    ok4, _ = rc.check_take_profit_trigger('B', -100, 10.0, 9.5)
    assert ok4 is False

    # 无持仓/无效价 → 恒放行
    assert rc.check_take_profit_trigger('A', 0, 10.0, 11.5) == (False, '')
    assert rc.check_take_profit_trigger('A', 100, 0, 11.5) == (False, '')


def test_e_take_profit_fallback_ratio():
    """无填充 level 时固定比例兜底: 多头 +5% 触发 (risk_control.py:236-238)"""
    rc = RiskControlStrategy()
    ok, reason = rc.check_take_profit_trigger('C', 100, 10.0, 10.6)
    assert ok is True and '多头止盈触发' in reason
    ok2, _ = rc.check_take_profit_trigger('C', 100, 10.0, 10.4)
    assert ok2 is False
    # 空头兜底: -5% (10.0 * 0.95 = 9.5)
    ok3, reason3 = rc.check_take_profit_trigger('D', -100, 10.0, 9.4)
    assert ok3 is True and '空头止盈触发' in reason3


def test_e_take_profit_e2e_reject():
    """端到端止盈: 现价 10.5 >= 止盈 10.2 → 拒单 (风控止盈触发, 拒绝追价开仓)"""
    from core.trading.order_executor import OrderExecutor
    monitor = _make_tp_monitor(tp_price=10.2)
    inst = _make_executor(monitor)
    result = inst._pre_trade_risk_check(_make_order(price=10.5))
    assert result['passed'] is False
    assert '风控止盈触发' in result['reason']
    assert '多头止盈触发' in result['reason']


def test_e_position_risk_monitor_direction():
    """get_dynamic_take_profit 降级方向: 多头 (1+ratio) / 空头 (1-ratio) (position_risk_monitor.py:144-145)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    with patch.object(PositionRiskMonitor, '_init_components', return_value=None):
        mon = PositionRiskMonitor()  # _take_profit = None → 固定比例降级
    mon._take_profit = None
    tp_long = mon.get_dynamic_take_profit('000001', 10.0, position=100)
    tp_short = mon.get_dynamic_take_profit('000001', 10.0, position=-100)
    assert tp_long == pytest.approx(10.2)   # 10.0 * 1.02
    assert tp_short == pytest.approx(9.8)   # 10.0 * 0.98


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v', '--no-header']))
