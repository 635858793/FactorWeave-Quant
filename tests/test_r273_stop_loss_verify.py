# -*- coding: utf-8 -*-
"""R273 止损空转根因彻底修复验证 (2026-08-09, 真实类驱动, 不 mock 止损核心逻辑)

背景:
- 历史缺陷 (R269 修复前): risk_control.py stop_loss_levels 唯一写入点
  calculate_stop_loss (:136) 全库零调用 + order_executor 原每单 new
  RiskControlStrategy() 恒空 → check_stop_loss_trigger 无 level 恒放行 → 止损空转。
- R269-D3 修复: core/trading/position_risk_monitor.py 新组件 +
  order_executor._fill_stop_loss_level (:937-974) 下单路径填充止损价 +
  risk_control.check_stop_loss_trigger (:198-202) 无 level 固定比例兜底。

本文件验证:
- A (写入非零): 真实 OrderExecutor._fill_stop_loss_level → 真实
  PositionRiskMonitor.get_dynamic_stop_price → stop_loss_levels 非零写入。
- B (触发): 价格达到止损价 → check_stop_loss_trigger triggered=True + reason 非空。
- C (兜底): 无 K 线 → get_dynamic_stop_price 固定 ±2%; PositionRiskMonitor
  不可用 → 降级 calculate_stop_loss; check_stop_loss_trigger 无 level ±5% 兜底。
- D (方向): 多头 current<=stop 触发 / 空头 current>=stop 触发 (真实持仓+真实下单路径)。
- E (调用链): 完整 submit_order → _pre_trade_risk_check → _fill_stop_loss_level
  → check_stop_loss_trigger 真实激活 (拒单), 静态写入点/消费点断言。

构造策略: 真实 Account/Position/Order dataclass + 真实 AccountManager 方法
(get_account/get_account_positions, 仅绕过 __init__ 避免 DB/C 扩展, 参照
test_r269 模式) + 最小 fake 容器 (try_resolve→None 跳过增强风控与容器内
PositionRiskMonitor 解析, 使 _fill_stop_loss_level 真实实例化组件)。
"""

import sys
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.risk_control import RiskControlStrategy  # noqa: E402

pytestmark = [pytest.mark.risk, pytest.mark.r269]


# ==================== 最小 fake 容器 ====================

class _FakeContainer:
    """最小 fake 容器: resolve(AccountManager) 返回真实 AccountManager,
    try_resolve 一律 None (跳过 EnhancedRiskMonitor / 容器内 PositionRiskMonitor)。"""

    def __init__(self, account_manager):
        self._am = account_manager

    def try_resolve(self, cls):
        return None

    def resolve(self, cls):
        from core.trading.account_manager import AccountManager
        if cls is AccountManager:
            return self._am
        raise ValueError(f"未注册服务: {cls}")


# ==================== 真实对象工厂 ====================

def _make_account(account_id='acc_273', balance=1_000_000.0):
    """真实 Account dataclass (注意: 真实模型无 available_cash / position_limit 字段)"""
    from core.trading.account_models import Account, AccountStatus
    now = datetime.now()
    return Account(
        account_id=account_id, account_name='R273验证账户', account_type='paper',
        status=AccountStatus.ACTIVE, balance=balance,
        available_balance=balance, frozen_balance=0.0, market_value=0.0,
        total_assets=balance, profit_loss=0.0, profit_loss_ratio=0.0,
        create_time=now, update_time=now,
    )


def _make_position(stock_code='000001.SZ', side='long', quantity=100,
                   cost_price=10.0, current_price=10.0, account_id='acc_273'):
    """真实 Position dataclass"""
    from core.plugin_types import AssetType
    from core.trading.account_models import Position, PositionSide
    now = datetime.now()
    return Position(
        position_id=f'p_{stock_code}_{side}', account_id=account_id,
        asset_type=AssetType.STOCK_A, stock_code=stock_code,
        stock_name=stock_code, side=PositionSide(side), quantity=quantity,
        available_quantity=quantity, open_price=cost_price,
        current_price=current_price, market_value=cost_price * quantity,
        cost_price=cost_price, cost_value=cost_price * quantity,
        profit_loss=0.0, profit_loss_ratio=0.0, open_time=now, update_time=now,
    )


def _make_order(stock_code='000001.SZ', order_price=9.4, order_quantity=100,
                account_id='acc_273', order_type='buy'):
    """真实 Order dataclass"""
    from core.plugin_types import AssetType
    from core.trading.order_models import Order, OrderCategory, OrderStatus, OrderType
    now = datetime.now()
    return Order(
        order_id=f'O-R273-{order_type}-{stock_code}', strategy_id='s_r273',
        asset_type=AssetType.STOCK_A, stock_code=stock_code,
        order_type=OrderType(order_type), order_category=OrderCategory.LIMIT,
        order_price=order_price, order_quantity=order_quantity,
        order_status=OrderStatus.PENDING, create_time=now, update_time=now,
        account_id=account_id,
    )


def _make_account_manager(account, positions):
    """真实 AccountManager 实例 (绕过 __init__ 避免 DB 加载, 手动注入真实对象)"""
    from core.trading.account_manager import AccountManager
    with patch.object(AccountManager, '__init__', return_value=None):
        am = AccountManager()
    am._accounts = {account.account_id: account}
    am._positions = {p.position_id: p for p in positions}
    am._account_lock = threading.RLock()
    am._position_lock = threading.RLock()
    am._fund_info_lock = threading.RLock()
    return am


def _make_executor(account_manager, position=None):
    """真实 OrderExecutor 实例 (绕过 __init__ 避免 C 扩展接口注册, 注入真实容器)"""
    from core.trading.order_executor import OrderExecutor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        ex = OrderExecutor()
    ex.service_container = _FakeContainer(account_manager)
    ex.event_bus = MagicMock()
    ex._halted = False
    ex._risk_control_enabled = True
    ex._logger = MagicMock()
    ex._max_retry_count = 3
    ex._account_interface_cache = {}
    return ex


# ==================== A: 写入非零 (非空转) ====================

def test_a_fill_stop_loss_level_writes_nonzero_real_monitor():
    """真实 PositionRiskMonitor (无 K 线降级 ±2%) → stop_loss_levels 非零写入"""
    from core.trading.order_executor import OrderExecutor
    ex = _make_executor(_make_account_manager(_make_account(), []))
    risk_ctrl = RiskControlStrategy()
    assert risk_ctrl.stop_loss_levels == {}
    order = _make_order()
    # 模拟无行情数据 (真实 get_dynamic_stop_price 内部逻辑, 仅数据源置空)
    with patch('core.trading.position_risk_monitor.PositionRiskMonitor._get_kline_data',
               return_value=None):
        ex._fill_stop_loss_level(risk_ctrl, order, entry_price=10.0, position=100)
    assert '000001.SZ' in risk_ctrl.stop_loss_levels
    assert risk_ctrl.stop_loss_levels['000001.SZ'] > 0
    assert risk_ctrl.stop_loss_levels['000001.SZ'] == pytest.approx(10.0 * (1 - 0.02))


def test_a_fill_uses_adaptive_when_kdata_provided():
    """有 K 线 data 参数 → 真实 AdaptiveStopLoss 计算 (非固定比例, 五路融合)"""
    import pandas as pd
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    df = pd.DataFrame({
        'open': [10.0, 10.0, 10.0, 10.0, 10.0],
        'high': [10.5, 10.5, 10.5, 10.5, 10.5],
        'low': [9.5, 9.5, 9.5, 9.5, 9.5],
        'close': [10.0, 10.0, 10.0, 10.0, 10.0],
        'volume': [100, 100, 100, 100, 100],
    })
    stop = monitor.get_dynamic_stop_price(
        stock_code='000001.SZ', current_price=10.0, position=100, data=df)
    assert stop > 0
    monitor.dispose()


# ==================== B: 触发 (triggered=True + reason 非空) ====================

def test_b_check_stop_loss_trigger_fired_with_reason():
    """价格达到止损价 → triggered=True 且 reason 非空 (多头, 基于已填充 level)"""
    rc = RiskControlStrategy()
    rc.stop_loss_levels['000001.SZ'] = 9.8
    triggered, reason = rc.check_stop_loss_trigger(
        asset='000001.SZ', position=100, entry_price=10.0, current_price=9.8)
    assert triggered is True
    assert reason and '多头止损触发' in reason


def test_b_no_trigger_above_stop():
    """价格高于止损价 → 不触发"""
    rc = RiskControlStrategy()
    rc.stop_loss_levels['000001.SZ'] = 9.8
    triggered, reason = rc.check_stop_loss_trigger(
        asset='000001.SZ', position=100, entry_price=10.0, current_price=9.81)
    assert triggered is False
    assert reason == ''


# ==================== C: 兜底路径 ====================

def test_c_monitor_fallback_fixed_ratio_no_kline():
    """无 K 线 → PositionRiskMonitor.get_dynamic_stop_price 固定 ±2% (多/空)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    with patch.object(monitor, '_get_kline_data', return_value=None):
        assert monitor.get_dynamic_stop_price('000001.SZ', 10.0, 100) == pytest.approx(9.8)
        assert monitor.get_dynamic_stop_price('000001.SZ', 10.0, -100) == pytest.approx(10.2)
    monitor.dispose()


def test_c_fill_degrades_to_calculate_stop_loss_when_monitor_broken():
    """PositionRiskMonitor 不可用 → _fill_stop_loss_level 降级 calculate_stop_loss"""
    from core.trading.order_executor import OrderExecutor
    ex = _make_executor(_make_account_manager(_make_account(), []))
    risk_ctrl = RiskControlStrategy()
    order = _make_order()
    with patch('core.trading.position_risk_monitor.PositionRiskMonitor',
               side_effect=RuntimeError('monitor down')):
        ex._fill_stop_loss_level(risk_ctrl, order, entry_price=10.0, position=100)
    # calculate_stop_loss: max(10*(1-0.2), 8)=8.0, position_ratio>0.8 → *0.95=7.6, regime neutral
    assert '000001.SZ' in risk_ctrl.stop_loss_levels
    assert risk_ctrl.stop_loss_levels['000001.SZ'] > 0
    assert risk_ctrl.stop_loss_levels['000001.SZ'] == pytest.approx(7.6)


def test_c_trigger_fallback_no_level_long_short():
    """check_stop_loss_trigger 无 level → 固定比例兜底 (多 -5% / 空 +5%)"""
    rc = RiskControlStrategy()
    assert rc.stop_loss_levels == {}
    trig, reason = rc.check_stop_loss_trigger('000002.SZ', 100, 10.0, 9.4)
    assert trig is True and '多头止损触发' in reason
    trig2, _ = rc.check_stop_loss_trigger('000002.SZ', 100, 10.0, 9.6)
    assert trig2 is False
    trig3, reason3 = rc.check_stop_loss_trigger('000002.SZ', -100, 10.0, 10.6)
    assert trig3 is True and '空头止损触发' in reason3
    trig4, _ = rc.check_stop_loss_trigger('000002.SZ', -100, 10.0, 10.4)
    assert trig4 is False


# ==================== D: 方向语义 (真实持仓 + 真实下单路径) ====================

def test_d_long_position_reject_below_stop():
    """真实多头持仓 + 真实下单路径: 现价跌破动态止损 → _pre_trade_risk_check 拒单"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    account = _make_account()
    pos = _make_position(side='long', cost_price=10.0)
    am = _make_account_manager(account, [pos])
    ex = _make_executor(am)
    order = _make_order(order_price=9.4)  # 现价 9.4 < 动态止损 9.8
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result = ex._pre_trade_risk_check(order)
    assert result['passed'] is False
    assert '风控止损触发' in result['reason']
    assert '多头止损触发' in result['reason']


def test_d_long_position_pass_above_stop():
    """真实多头持仓: 现价高于动态止损 → 放行"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    account = _make_account()
    pos = _make_position(side='long', cost_price=10.0)
    am = _make_account_manager(account, [pos])
    ex = _make_executor(am)
    order = _make_order(order_price=9.9)  # 现价 9.9 > 动态止损 9.8
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result = ex._pre_trade_risk_check(order)
    assert result['passed'] is True


def test_d_short_position_reject_above_stop():
    """真实空头持仓 + 真实下单路径: 现价涨破动态止损 → 拒单 (空头 current>=stop 触发)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    account = _make_account()
    pos = _make_position(side='short', cost_price=10.0)
    am = _make_account_manager(account, [pos])
    ex = _make_executor(am)
    order = _make_order(order_price=10.4, order_type='short')  # 现价 10.4 > 空头止损 10.2
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result = ex._pre_trade_risk_check(order)
    assert result['passed'] is False
    assert '风控止损触发' in result['reason']
    assert '空头止损触发' in result['reason']


def test_d_short_position_pass_below_stop():
    """真实空头持仓: 现价低于动态止损 → 放行"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    account = _make_account()
    pos = _make_position(side='short', cost_price=10.0)
    am = _make_account_manager(account, [pos])
    ex = _make_executor(am)
    order = _make_order(order_price=10.1, order_type='short')  # 现价 10.1 < 空头止损 10.2
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result = ex._pre_trade_risk_check(order)
    assert result['passed'] is True


# ==================== E: 完整调用链 (submit_order 生产路径) ====================

def test_e_submit_order_full_path_activates_stop_loss():
    """生产路径 submit_order → _pre_trade_risk_check → _fill_stop_loss_level
    → check_stop_loss_trigger 真实激活 → ExecutionResult FAILED"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    from core.trading.trading_types import ExecutionResult, ExecutionStatus
    account = _make_account()
    pos = _make_position(side='long', cost_price=10.0)
    am = _make_account_manager(account, [pos])
    ex = _make_executor(am)
    ex._logger = MagicMock()
    order = _make_order(order_price=9.4)

    original_fill = ex._fill_stop_loss_level
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None), \
            patch.object(ex, '_fill_stop_loss_level', wraps=original_fill) as spy:
        result = ex.submit_order(order)

    assert spy.called, '_pre_trade_risk_check 未调用 _fill_stop_loss_level'
    assert isinstance(result, ExecutionResult)
    assert result.status == ExecutionStatus.FAILED
    assert result.error_code == 'RISK_CHECK_FAILED'
    assert '风控止损触发' in result.message


def test_e_stop_loss_levels_write_consume_points_static():
    """stop_loss_levels 写入点/消费点静态断言 (防零写入回归)"""
    risk_src = (PROJECT_ROOT / 'core' / 'risk_control.py').read_text(encoding='utf-8')
    executor_src = (PROJECT_ROOT / 'core' / 'trading' / 'order_executor.py').read_text(encoding='utf-8')
    # 写入点1: risk_control.calculate_stop_loss (:136)
    assert 'self.stop_loss_levels[asset] = base_stop' in risk_src
    # 写入点2: order_executor._fill_stop_loss_level (:972) —— 活跃消费路径
    assert 'risk_ctrl.stop_loss_levels[order.stock_code] = float(stop_price)' in executor_src
    # 消费点: check_stop_loss_trigger (:197)
    assert 'stop_price = self.stop_loss_levels.get(asset)' in risk_src
    # 调用链: _pre_trade_risk_check → _fill_stop_loss_level (:892) → check_stop_loss_trigger (:893)
    assert 'self._fill_stop_loss_level(risk_ctrl, order, entry_price, position)' in executor_src
    assert 'risk_ctrl.check_stop_loss_trigger(' in executor_src


def test_e_position_read_from_real_account_manager():
    """真实 AccountManager.get_account_positions → _get_position/_get_avg_entry_price
    (验证 _pre_trade_risk_check 的持仓/入场价数据源真实打通)"""
    account = _make_account()
    pos_long = _make_position(stock_code='000001.SZ', side='long', quantity=100, cost_price=10.0)
    pos_short = _make_position(stock_code='600000.SH', side='short', quantity=50, cost_price=20.0)
    am = _make_account_manager(account, [pos_long, pos_short])
    ex = _make_executor(am)
    assert ex._get_position('acc_273', '000001.SZ') == 100
    assert ex._get_position('acc_273', '600000.SH') == -50
    assert ex._get_avg_entry_price('acc_273', '000001.SZ') == pytest.approx(10.0)
    assert ex._get_avg_entry_price('acc_273', '600000.SH') == pytest.approx(20.0)
    assert ex._get_position('acc_273', '999999.XX') == 0
    assert ex._get_avg_entry_price('acc_273', '999999.XX') is None


# ==================== F: 资金校验 fail-open 修复验证 (R273-F1) ====================

def test_f_real_account_missing_available_cash_fail_open():
    """R273-F1 修复验证: 真实 Account 模型 (account_models.py:64-176) 无
    available_cash / position_limit 字段 → order_executor.py:851/:864 的
    hasattr 校验恒 False → 资金充足性校验在真实账户下被整体跳过 (fail-open)。

    R273-F1 修复: order_executor.py:854-862 双字段兼容 (available_cash 优先,
    缺省回退 available_balance) → 真实账户资金不足必须被拦截 (fail-closed)。
    """
    account = _make_account(balance=100.0)
    # 真实 Account 无 available_cash (只有 available_balance :72)
    assert not hasattr(account, 'available_cash')
    assert not hasattr(account, 'position_limit')

    # 账户仅 100 元, 下单 10 万股×10 元=100 万 → 资金校验必须拦截 (修复前 fail-open 放行)
    from core.trading.position_risk_monitor import PositionRiskMonitor
    am = _make_account_manager(account, [])
    ex = _make_executor(am)
    order = _make_order(order_price=10.0, order_quantity=100_000)  # 订单价值 1,000,000
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result = ex._pre_trade_risk_check(order)
    # fail-closed: 资金不足被拦截 + reason 明确
    assert result['passed'] is False, f"资金不足应被拦截, 实际: {result}"
    assert '资金不足' in result['reason'], f"reason 应含资金不足: {result['reason']}"

    # 资金充足 (balance=500,000) 但下单金额 (1,000,000) 超过可用 → 同样拦截
    account_rich = _make_account(balance=500_000.0)
    am_rich = _make_account_manager(account_rich, [])
    ex_rich = _make_executor(am_rich)
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result_rich = ex_rich._pre_trade_risk_check(order)
    assert result_rich['passed'] is False, f"超可用资金应被拦截, 实际: {result_rich}"

    # 可用资金充足 → 资金校验通过 (不阻断, 继续后续检查)
    order_small = _make_order(order_price=10.0, order_quantity=100)  # 订单价值 1,000
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result_ok = ex_rich._pre_trade_risk_check(order_small)
    assert result_ok['passed'] is True, f"资金充足不应被拦截, 实际: {result_ok}"
