#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R270 完整回测流程 + 风险评估面板 + 熔断机制 UI 呈现 E2E 验证 (临时验证脚本, 保留)

背景: R269 风控完善 (D1 单日最大亏损熔断 / D2 风控预警自动响应熔断 / D4 风险评估面板激活)。
本脚本验证 "完整回测流程中风险评估面板和熔断机制在界面上正常显示且无报错":
1. 真实 UnifiedBacktestEngine.run_backtest 完整跑通 (合成数据, 与 test_r267c_backtest_e2e.py 同模式)
2. RiskAssessmentPanel 用真实 BettaFishAgent 实例化 → _load_risk_data/_update_risk_data 无异常,
   get_risk_assessment 返回面板期望全部键 (bettafish_agent.py:567-688)
3. 熔断相关: OrderValidator._validate_daily_loss_limit (D1, order_validator.py:306-385)
   与 OrderExecutor._pre_trade_risk_check 熔断拦截 (D2, order_executor.py:797-807) 调用无异常
4. BettaFishDashboard 全面板实例化冒烟 + RiskGauge 绘制冒烟 (探测 QPoint 未导入缺陷)
5. smart_recommendation_panel.py:1139 monitoring_service kwarg 兼容性验证

运行: conda activate hikyuu; python -m pytest tests/_r270_e2e_backtest_check.py -q --no-header
"""
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLBACKEND', 'Agg')

import numpy as np
import pandas as pd

RISK_KEYS = ['var_95', 'cvar_95', 'max_drawdown', 'volatility', 'sharpe_ratio']


def _unmock_gui_widgets():
    """清除 tests/conftest.py:51 对 gui.widgets 顶层包的 MagicMock (mock 无 __path__,
    会阻断真实子模块导入, 报 'gui.widgets' is not a package)。本脚本需要真实面板模块。"""
    for _m in list(sys.modules):
        if _m == 'gui.widgets' or _m.startswith('gui.widgets.'):
            del sys.modules[_m]

# RiskAssessmentPanel._update_display / _update_detail_metrics / _update_risk_breakdown 消费的全部键
PANEL_KEYS = [
    'overall_risk', 'overall_risk_level',
    'var_95', 'max_drawdown', 'sharpe_ratio', 'volatility', 'correlation', 'concentration',
    'market_risk', 'liquidity_risk', 'credit_risk', 'operational_risk', 'concentration_risk',
    'market_risk_pct', 'liquidity_risk_pct', 'credit_risk_pct', 'operational_risk_pct',
    'concentration_risk_pct',
]


def _make_kline_data(n=300, seed=42):
    """构造合成 K 线数据 + 信号列 (与 test_r267c_backtest_e2e.py:35-52 一致)"""
    rng = np.random.default_rng(seed)
    dates = pd.date_range('2024-01-01', periods=n, freq='D')
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, n))
    volume = rng.integers(10000, 100000, n)
    ma5 = pd.Series(close).rolling(5).mean().values
    signal = np.zeros(n)
    signal[1:] = np.where(close[1:] > ma5[1:], 1, 0)
    return pd.DataFrame({
        'date': dates, 'open': open_, 'high': high, 'low': low,
        'close': close, 'volume': volume, 'signal': signal,
    })


def test_backtest_engine_full_run():
    """完整回测流程真实跑通, 结果含全部风险指标字段"""
    from backtest.unified_backtest_engine import create_unified_backtest_engine

    engine = create_unified_backtest_engine()
    result = engine.run_backtest(
        data=_make_kline_data(), initial_capital=100000, position_size=1.0,
        commission_pct=0.001, slippage_pct=0.001,
        enable_compound=True, mode_context=None,
    )

    assert isinstance(result, dict)
    for key in RISK_KEYS:
        assert key in result, f'回测结果缺少风险指标字段: {key}'
    assert 'equity_curve' in result
    assert result['sharpe_ratio'] is not None
    assert result['max_drawdown'] is not None


def test_risk_assessment_panel_with_real_agent():
    """真实 BettaFishAgent + RiskAssessmentPanel: _load_risk_data/_update_risk_data 无异常,
    get_risk_assessment 返回面板期望全部键"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    _unmock_gui_widgets()
    from core.agents.bettafish_agent import BettaFishAgent
    from gui.widgets.bettafish_dashboard.risk_assessment_panel import RiskAssessmentPanel

    agent = BettaFishAgent()

    # 1) 数据源方法正常返回 (bettafish_agent.py:567-606)
    assessment = agent.get_risk_assessment()
    assert isinstance(assessment, dict)
    for key in PANEL_KEYS:
        assert key in assessment, f'get_risk_assessment 缺少面板期望键: {key}'
    alerts = agent.get_risk_alerts()
    assert isinstance(alerts, list)

    # 2) 面板实例化 + 加载/更新无异常
    panel = RiskAssessmentPanel(bettafish_agent=agent)
    try:
        panel._load_risk_data()
        panel._update_risk_data()
        data = panel.get_risk_data()
        assert data, '面板 _risk_data 为空'
        for key in PANEL_KEYS:
            assert key in data, f'面板 _risk_data 缺少键: {key}'
    finally:
        panel.close()


def test_bettafish_dashboard_full_smoke():
    """BettaFishDashboard 全面板实例化冒烟 (含 RiskAssessmentPanel 挂载, bettafish_dashboard_main.py:191)"""
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    _unmock_gui_widgets()
    from core.agents.bettafish_agent import BettaFishAgent
    from gui.widgets.bettafish_dashboard.bettafish_dashboard_main import BettaFishDashboard
    from gui.widgets.bettafish_dashboard.risk_assessment_panel import RiskAssessmentPanel

    agent = BettaFishAgent()
    dash = BettaFishDashboard(bettafish_agent=agent)
    try:
        panels = dash._panels
        assert '风险评估' in panels, f'风险评估面板未创建: {list(panels.keys())}'
        assert isinstance(panels['风险评估'], RiskAssessmentPanel)
        # 触发一次仪表板刷新 (每个面板 update_data)
        dash._update_dashboard()
    finally:
        dash.close()


def test_risk_gauge_paint_no_nameerror():
    """RiskGauge 绘制冒烟: 捕获 paintEvent 内异常 (QPoint 未导入探测)"""
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
        pix = gauge.grab()  # 强制同步绘制
        gauge.close()
        assert not pix.isNull()
    finally:
        sys.excepthook = orig_hook

    assert not collected, f'RiskGauge 绘制异常: {collected}'


# ==================== D1 / D2 熔断路径 ====================

def _make_request(**kwargs):
    """构造订单请求 (SimpleNamespace, 含验证链访问字段)"""
    base = {
        'account_id': 'acc_001',
        'stock_code': '000001',
        'order_type': None,
        'order_price': 10.0,
        'order_quantity': 100,
        'stop_price': None,
        'order_category': None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _build_validator():
    """构造 OrderValidator 实例 (patch __init__, 手动注入容器/配置, 同 test_r269 fixture)"""
    from core.trading.order_validator import OrderValidator
    with patch.object(OrderValidator, '__init__', return_value=None):
        inst = OrderValidator()
        inst.service_container = MagicMock()
        inst.event_bus = MagicMock()
        inst._config = {
            'min_order_quantity': 100,
            'max_order_quantity': 1000000,
            'min_order_price': 0.01,
            'max_order_price': 1000000.0,
            'max_daily_loss_ratio': 0.05,
            'validate_daily_loss': True,
        }
        return inst


def _mock_daily_loss_env(validator, account_balance=100000.0, market_value=0.0,
                         filled_orders=None):
    """装配 D1 熔断检查所需 mock 环境 (同 test_r269 _mock_daily_loss_env)"""
    from core.trading.account_manager import AccountManager
    from core.trading.order_repository import OrderRepository
    mock_account = SimpleNamespace(balance=account_balance, market_value=market_value)
    mock_acct_mgr = MagicMock()
    mock_acct_mgr.get_account = MagicMock(return_value=mock_account)
    mock_repo = MagicMock()
    mock_repo.query_orders = MagicMock(return_value=filled_orders or [])

    def try_resolve(cls):
        if cls is AccountManager:
            return mock_acct_mgr
        if cls is OrderRepository:
            return mock_repo
        return None

    validator.service_container.try_resolve = MagicMock(side_effect=try_resolve)


def _filled_order(order_type, filled_price, filled_quantity, commission=0.0):
    return SimpleNamespace(
        order_type=order_type,
        filled_price=filled_price,
        filled_quantity=filled_quantity,
        commission=commission,
    )


def test_d1_daily_loss_halt_path():
    """D1 单日最大亏损熔断: 模拟下单路径调用无异常 + 错误码正确"""
    from core.trading.order_models import OrderType
    validator = _build_validator()

    # 默认账户不参与熔断 (order_validator.py:323-324)
    r0 = validator._validate_daily_loss_limit(_make_request(account_id='default'))
    assert r0.passed is True

    # 当日亏损 7000 / 100000 = 7% > 5% → DAILY_LOSS_LIMIT_EXCEEDED (order_validator.py:371-381)
    _mock_daily_loss_env(validator, filled_orders=[
        _filled_order(OrderType.BUY, 9.0, 10000, commission=0.0),   # -90000
        _filled_order(OrderType.SELL, 8.3, 10000, commission=0.0),  # +83000
    ])
    r1 = validator._validate_daily_loss_limit(_make_request())
    assert r1.passed is False
    assert r1.error_code == 'DAILY_LOSS_LIMIT_EXCEEDED'
    assert abs(r1.details['realized_pnl'] + 7000.0) < 1e-6

    # 全链路: validate_order_request 第 4 步触发熔断 (order_validator.py:77-81)
    r2 = validator.validate_order_request(
        _make_request(order_type=OrderType.BUY, order_quantity=100))
    assert r2.passed is False
    assert r2.error_code == 'DAILY_LOSS_LIMIT_EXCEEDED'


def test_d2_halt_interception_path():
    """D2 熔断拦截: 模拟下单路径调用无异常 + RISK_HALTED 错误码正确"""
    from core.trading.order_executor import OrderExecutor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        ex = OrderExecutor()
        ex._logger = MagicMock()
        ex._account_manager = MagicMock()
        ex._account_interface_cache = {}
        ex._max_retry_count = 3
        ex._interface_health = {}
        ex.event_bus = MagicMock()
        ex.service_container = MagicMock()
        ex.service_container.try_resolve = MagicMock(return_value=None)
        ex.service_container.resolve = MagicMock(side_effect=ValueError('not registered'))
        ex._halted = False
        ex._risk_control_enabled = True
        ex._get_avg_entry_price = MagicMock(return_value=None)

    order = SimpleNamespace(
        order_id='O1', account_id='acc_001', stock_code='000001',
        order_price=10.0, order_quantity=100,
    )

    # 未熔断: 走正常风控链, 不得出现 RISK_HALTED (test_r269 同断言)
    r0 = ex._pre_trade_risk_check(order)
    assert r0.get('error_code') != 'RISK_HALTED'

    # 熔断后: 拒绝一切新订单 (order_executor.py:800-801)
    ex.halt_trading(reason='E2E 模拟熔断')
    assert ex.is_halted() is True
    r1 = ex._pre_trade_risk_check(order)
    assert r1['passed'] is False
    assert r1['error_code'] == 'RISK_HALTED'
    assert '熔断' in r1['reason']

    # 熔断期间即使风控开关关闭也不放行 (order_executor.py:798-801 最高优先级)
    ex._risk_control_enabled = False
    r2 = ex._pre_trade_risk_check(order)
    assert r2['error_code'] == 'RISK_HALTED'

    # 恢复后解除熔断 (order_executor.py:775-779)
    ex.resume_trading()
    assert ex.is_halted() is False


def test_bettafish_dashboard_monitoring_service_kwarg_unsupported():
    """smart_recommendation_panel.py:1139 传 monitoring_service= 到 BettaFishDashboard 不受支持 → TypeError

    BettaFishDashboard.__init__ 签名 (bettafish_dashboard_main.py:49) 仅接受 bettafish_agent,
    不消费 monitoring_service。真实启动路径 (main_window_coordinator.py:3596) 两参数均为 None
    走 else 分支, 仅当调用方显式传 monitoring_service 时触发该缺陷 (被 L1176 try/except 吞掉)。
    """
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])

    _unmock_gui_widgets()
    from gui.widgets.bettafish_dashboard.bettafish_dashboard_main import BettaFishDashboard
    try:
        BettaFishDashboard(parent=None, monitoring_service=MagicMock())
    except TypeError as e:
        assert 'monitoring_service' in str(e), f'异常信息不含 monitoring_service: {e}'
    else:
        raise AssertionError('应抛出 TypeError (BettaFishDashboard 不支持 monitoring_service 参数)')


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v', '--no-header']))
