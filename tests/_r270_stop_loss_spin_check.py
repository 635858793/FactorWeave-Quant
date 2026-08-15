# -*- coding: utf-8 -*-
"""R270 止损空转修复深度验证 (临时验证文件, 只读验证, 不修改生产代码)

目标: 验证 R269-D3 修复真实生效:
- 场景1 (核心空转): _fill_stop_loss_level 填充后 risk_ctrl.stop_loss_levels 非空,
  check_stop_loss_trigger 对多/空头基于该 level 正确触发/放行。
- 场景2 (端到端拒单): order_executor._pre_trade_risk_check 现价跌破动态止损 → 拒单;
  现价高于止损 → 放行。
- 场景3 (兜底路径): 无 level 时 check_stop_loss_trigger 固定比例兜底 (多 -5% / 空 +5%)。
- 场景4 (残留断点扫描): stop_loss_levels 全部读写点清单 + take_profit 空转扫描。
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.risk_control import RiskControlStrategy  # noqa: E402

PROJ = PROJECT_ROOT


# ---------------- 工具函数 ----------------

def _make_order(stock_code='000001', price=10.0, qty=100, account_id='acc_001'):
    """构造模拟订单 (SimpleNamespace, 含 _pre_trade_risk_check 访问的全部字段)"""
    return SimpleNamespace(
        order_id='O-test', account_id=account_id, stock_code=stock_code,
        order_price=price, order_quantity=qty, create_time=datetime.now(),
    )


def _make_executor():
    """构造 OrderExecutor 实例 (patch __init__, 参照 R269 测试模式)。

    service_container 全 mock:
    - try_resolve → None (EnhancedRiskMonitor / PositionRiskMonitor 均跳过容器解析)
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

    inst.service_container.try_resolve = MagicMock(return_value=None)

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


# ==================== 场景1: 核心空转验证 ====================

def test_scene1_fill_stop_loss_level_writes_dict():
    """_fill_stop_loss_level 填充后 stop_loss_levels['000001'] 非空 (修复零写入)"""
    from core.trading.order_executor import OrderExecutor
    from core.trading.position_risk_monitor import PositionRiskMonitor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        inst = OrderExecutor()
    inst.service_container = MagicMock()
    inst.service_container.try_resolve = MagicMock(return_value=None)
    inst._logger = MagicMock()

    risk_ctrl = RiskControlStrategy()
    assert risk_ctrl.stop_loss_levels == {}  # 初始为空

    order = _make_order()
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        inst._fill_stop_loss_level(risk_ctrl, order, entry_price=10.0, position=100)

    # 修复生效: 写入点真实执行, 字典非空
    assert '000001' in risk_ctrl.stop_loss_levels
    assert risk_ctrl.stop_loss_levels['000001'] > 0
    # 无 K 线降级固定比例 -2% (PositionRiskMonitor.get_dynamic_stop_price)
    assert risk_ctrl.stop_loss_levels['000001'] == pytest.approx(10.0 * (1 - 0.02))


def test_scene1_trigger_uses_filled_level_long_short():
    """check_stop_loss_trigger 基于已填充 level 正确触发/放行 (多/空)"""
    from core.trading.order_executor import OrderExecutor
    from core.trading.position_risk_monitor import PositionRiskMonitor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        inst = OrderExecutor()
    inst.service_container = MagicMock()
    inst.service_container.try_resolve = MagicMock(return_value=None)
    inst._logger = MagicMock()

    risk_ctrl = RiskControlStrategy()
    order = _make_order()
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        inst._fill_stop_loss_level(risk_ctrl, order, entry_price=10.0, position=100)
    stop_level = risk_ctrl.stop_loss_levels['000001']  # == 9.8

    # 多头: 现价跌破 level → 触发; 高于 level → 放行
    trig_long_down, reason = risk_ctrl.check_stop_loss_trigger(
        '000001', position=100, entry_price=10.0, current_price=stop_level - 0.1)
    assert trig_long_down is True
    assert '多头止损触发' in reason
    trig_long_up, _ = risk_ctrl.check_stop_loss_trigger(
        '000001', position=100, entry_price=10.0, current_price=stop_level + 0.1)
    assert trig_long_up is False

    # 空头: 现价涨破 level → 触发; 低于 level → 放行
    trig_short_up, reason_s = risk_ctrl.check_stop_loss_trigger(
        '000001', position=-100, entry_price=10.0, current_price=stop_level + 0.1)
    assert trig_short_up is True
    assert '空头止损触发' in reason_s
    trig_short_down, _ = risk_ctrl.check_stop_loss_trigger(
        '000001', position=-100, entry_price=10.0, current_price=stop_level - 0.1)
    assert trig_short_down is False


# ==================== 场景2: 端到端拒单 ====================

def test_scene2_pre_trade_reject_when_below_stop():
    """现价跌破动态止损 → _pre_trade_risk_check passed=False, reason 含"风控止损触发" """
    from core.trading.position_risk_monitor import PositionRiskMonitor
    inst = _make_executor()
    order = _make_order(price=9.4, qty=100)  # 现价 9.4 < 动态止损 9.8
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result = inst._pre_trade_risk_check(order)
    assert result['passed'] is False
    assert '风控止损触发' in result['reason']
    assert '多头止损触发' in result['reason']


def test_scene2_pre_trade_pass_when_above_stop():
    """现价高于动态止损 → _pre_trade_risk_check passed=True"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    inst = _make_executor()
    order = _make_order(price=9.9, qty=100)  # 现价 9.9 > 动态止损 9.8
    with patch.object(PositionRiskMonitor, '_get_kline_data', return_value=None):
        result = inst._pre_trade_risk_check(order)
    assert result['passed'] is True


# ==================== 场景3: 兜底路径 ====================

def test_scene3_fallback_long():
    """无 level 时兜底: 多头 entry=10.0 → 兜底止损 9.5; 9.4 触发, 9.6 放行"""
    rc = RiskControlStrategy()
    assert rc.stop_loss_levels == {}  # 无任何填充
    trig, reason = rc.check_stop_loss_trigger('000002', position=100,
                                              entry_price=10.0, current_price=9.4)
    assert trig is True
    assert '多头止损触发' in reason
    trig2, _ = rc.check_stop_loss_trigger('000002', position=100,
                                          entry_price=10.0, current_price=9.6)
    assert trig2 is False


def test_scene3_fallback_short():
    """无 level 时兜底: 空头 entry=10.0 → 兜底止损 10.5; 10.6 触发, 10.4 放行"""
    rc = RiskControlStrategy()
    trig, reason = rc.check_stop_loss_trigger('000002', position=-100,
                                              entry_price=10.0, current_price=10.6)
    assert trig is True
    assert '空头止损触发' in reason
    trig2, _ = rc.check_stop_loss_trigger('000002', position=-100,
                                          entry_price=10.0, current_price=10.4)
    assert trig2 is False


def test_scene3_no_trigger_zero_position_or_bad_price():
    """position==0 或价格非法 → 恒放行"""
    rc = RiskControlStrategy()
    assert rc.check_stop_loss_trigger('000002', 0, 10.0, 9.0)[0] is False
    assert rc.check_stop_loss_trigger('000002', 100, 0.0, 9.0)[0] is False
    assert rc.check_stop_loss_trigger('000002', 100, 10.0, 0.0)[0] is False


# ==================== 场景4: 残留断点扫描 (源码静态断言) ====================

def _read(rel):
    return (PROJ / rel).read_text(encoding='utf-8')


def test_scene4_stop_loss_levels_write_points():
    """stop_loss_levels 写入点: 生产代码必须 ≥2 (risk_control.py:135 + order_executor.py:952)"""
    risk_control_src = _read('core/risk_control.py')
    order_executor_src = _read('core/trading/order_executor.py')

    # risk_control.py 内写入点 (calculate_stop_loss)
    assert 'self.stop_loss_levels[asset] = base_stop' in risk_control_src
    # order_executor.py 内写入点 (_fill_stop_loss_level)
    assert 'risk_ctrl.stop_loss_levels[order.stock_code] = float(stop_price)' in order_executor_src
    # 读取点 (check_stop_loss_trigger)
    assert 'stop_price = self.stop_loss_levels.get(asset)' in risk_control_src


def test_scene4_calculate_stop_loss_not_zero_called():
    """calculate_stop_loss 不再零调用: 必须被 _fill_stop_loss_level 降级分支引用"""
    order_executor_src = _read('core/trading/order_executor.py')
    # _fill_stop_loss_level 内存在降级调用
    assert 'risk_ctrl.calculate_stop_loss(' in order_executor_src
    # 该调用位于 _fill_stop_loss_level 函数体内 (L945)
    m = re.search(r'def _fill_stop_loss_level.*?def _sync_positions_to_risk_monitor',
                  order_executor_src, re.S)
    assert m is not None, '_fill_stop_loss_level 函数体未找到'
    body = m.group(0)
    assert 'risk_ctrl.calculate_stop_loss(' in body


def test_scene4_take_profit_spin_scan():
    """take_profit 空转扫描: 全库(排除测试/tools/文档)中 take_profit_levels /
    check_take_profit_trigger 符号仅允许出现在 R270 已激活消费点
    (core/risk_control.py 定义 + core/trading/order_executor.py 订单链消费),
    其他任何文件命中 = 独立空转残留 → 失败"""
    hits = []
    for p in sorted(PROJ.rglob('*.py')):
        rel = p.relative_to(PROJ).as_posix()
        if rel.startswith('tests/') or rel.startswith('tools/') or rel.startswith('drawio/'):
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        for line_no, line in enumerate(text.splitlines(), 1):
            if 'take_profit_levels' in line or 'check_take_profit_trigger' in line:
                hits.append(f'{rel}:{line_no}: {line.strip()}')
    # R270 止盈融入后, 符号仅存在于已激活的两处消费点 (risk_control.py:14/169/219/235,
    # order_executor.py:901/971/975/1005/1007); 其他文件命中 = 未消费残留
    allowed_files = {'core/risk_control.py', 'core/trading/order_executor.py'}
    orphan = [h for h in hits if h.split(':')[0] not in allowed_files]
    assert orphan == [], f'存在空转 take_profit 符号: {orphan}'


def test_scene4_no_orphan_stop_loss_write_besides_fix():
    """除修复外无其他"写入点零调用"断链: stop_loss_levels 写入点均被活链路消费"""
    # 写入点1: risk_control.calculate_stop_loss —— 被 order_executor._fill_stop_loss_level 降级调用
    order_executor_src = _read('core/trading/order_executor.py')
    # 写入点2: _fill_stop_loss_level —— 被 _pre_trade_risk_check 在 position!=0 时调用
    assert '_fill_stop_loss_level(risk_ctrl, order, entry_price, position)' in order_executor_src
    # 读取点: check_stop_loss_trigger —— 被 _pre_trade_risk_check 调用
    assert 'risk_ctrl.check_stop_loss_trigger(' in order_executor_src
