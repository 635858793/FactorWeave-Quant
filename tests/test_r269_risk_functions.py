"""R269 风控功能完善验证 (2026-08-09)

覆盖:
- D1 单日最大亏损熔断 (order_validator.py:306-385 _validate_daily_loss_limit):
  消费 order_validator.py:53 max_daily_loss_ratio (原全库 0 消费)。
  数据源 = 当日 FILLED 订单按买卖方向反推已实现盈亏, 分母 = balance + market_value。
  默认账户(default)不熔断; 数据/账户不可用降级放行。
- D2 风控预警自动响应:
  - order_executor.py halt_trading/resume_trading/is_halted + _pre_trade_risk_check 熔断拦截
  - risk_event_subscribers.py stop_trading → 熔断; emergency_liquidation → 平仓+熔断
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.risk, pytest.mark.r269]


def _make_request(**kwargs):
    """构造订单请求 (SimpleNamespace, 含 _validate_daily_loss_limit 访问字段)"""
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


# ==================== D1: 单日最大亏损熔断 ====================

@pytest.fixture
def validator():
    """构造 OrderValidator 实例 (patch __init__, 手动注入容器/配置)"""
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
                         filled_orders=None, account_exists=True, repo_raises=False):
    """装配 D1 熔断检查所需 mock 环境"""
    from core.trading.account_manager import AccountManager
    from core.trading.order_repository import OrderRepository

    mock_account = None
    if account_exists:
        mock_account = SimpleNamespace(balance=account_balance, market_value=market_value)
    mock_acct_mgr = MagicMock()
    mock_acct_mgr.get_account = MagicMock(return_value=mock_account)

    mock_repo = MagicMock()
    if repo_raises:
        mock_repo.query_orders = MagicMock(side_effect=RuntimeError("repo down"))
    else:
        mock_repo.query_orders = MagicMock(return_value=filled_orders or [])

    def try_resolve(cls):
        if cls is AccountManager:
            return mock_acct_mgr
        if cls is OrderRepository:
            return mock_repo
        return None

    validator.service_container.try_resolve = MagicMock(side_effect=try_resolve)
    return mock_acct_mgr, mock_repo


def _filled_order(order_type, filled_price, filled_quantity, commission=0.0):
    """构造当日已成交订单 mock"""
    from core.trading.order_models import OrderType
    return SimpleNamespace(
        order_type=order_type,
        filled_price=filled_price,
        filled_quantity=filled_quantity,
        commission=commission,
    )


def test_d1_default_account_never_halts(validator):
    """默认账户 (default) 不参与熔断, 直接放行"""
    from core.trading.order_models import OrderType
    _mock_daily_loss_env(validator, filled_orders=[
        _filled_order(OrderType.SELL, 10.0, 1000, commission=0.0),
    ])
    result = validator._validate_daily_loss_limit(_make_request(account_id='default'))
    assert result.passed is True


def test_d1_loss_exceeds_threshold_rejects(validator):
    """当日已实现亏损超 5% 阈值 → 拒绝 DAILY_LOSS_LIMIT_EXCEEDED"""
    from core.trading.order_models import OrderType
    # 账户总资产 100000 (balance) + 0 (market_value), 阈值 5% → 5000
    # 当日: 买入 90000 (成本) + 卖出 83000 (收入) → 已实现 = 83000 - 90000 = -7000
    _mock_daily_loss_env(validator, account_balance=100000.0, market_value=0.0, filled_orders=[
        _filled_order(OrderType.BUY, 9.0, 10000, commission=0.0),   # -90000
        _filled_order(OrderType.SELL, 8.3, 10000, commission=0.0),  # +83000
    ])
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is False
    assert result.error_code == 'DAILY_LOSS_LIMIT_EXCEEDED'
    assert abs(result.details['realized_pnl'] + 7000.0) < 1e-6
    assert result.details['loss_ratio'] == pytest.approx(0.07)
    assert result.details['threshold'] == pytest.approx(0.05)
    assert result.details['filled_orders'] == 2


def test_d1_loss_within_threshold_passes(validator):
    """当日亏损未超阈值 → 放行"""
    from core.trading.order_models import OrderType
    # 已实现 = -3000, 总资产 100000 → 3% < 5% → 放行
    _mock_daily_loss_env(validator, account_balance=100000.0, market_value=0.0, filled_orders=[
        _filled_order(OrderType.BUY, 9.0, 10000, commission=0.0),  # -90000
        _filled_order(OrderType.SELL, 8.7, 10000, commission=0.0),  # +87000
    ])
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is True


def test_d1_profit_passes(validator):
    """当日盈利 → 直接放行"""
    from core.trading.order_models import OrderType
    _mock_daily_loss_env(validator, account_balance=100000.0, market_value=0.0, filled_orders=[
        _filled_order(OrderType.BUY, 8.0, 10000, commission=0.0),   # -80000
        _filled_order(OrderType.SELL, 9.0, 10000, commission=0.0),  # +90000
    ])
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is True


def test_d1_commission_included(validator):
    """手续费计入已实现盈亏 (卖出减佣金, 买入加佣金)"""
    from core.trading.order_models import OrderType
    # 买入 -(90000 + 100) = -90100; 卖出 +(83000 - 100) = +82900
    # 已实现 = 82900 - 90100 = -7200 → 7.2% > 5% → 拒绝
    _mock_daily_loss_env(validator, account_balance=100000.0, market_value=0.0, filled_orders=[
        _filled_order(OrderType.BUY, 9.0, 10000, commission=100.0),
        _filled_order(OrderType.SELL, 8.3, 10000, commission=100.0),
    ])
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is False
    assert result.details['realized_pnl'] == pytest.approx(-7200.0)


def test_d1_short_cover_directions(validator):
    """SHORT 视为开仓(减), COVER 视为平仓(加)"""
    from core.trading.order_models import OrderType
    _mock_daily_loss_env(validator, account_balance=100000.0, market_value=0.0, filled_orders=[
        _filled_order(OrderType.SHORT, 9.0, 10000, commission=0.0),  # -90000
        _filled_order(OrderType.COVER, 8.3, 10000, commission=0.0),  # +83000
    ])
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is False
    assert result.error_code == 'DAILY_LOSS_LIMIT_EXCEEDED'


def test_d1_no_account_degrades_open(validator):
    """账户不存在 → 降级放行"""
    _mock_daily_loss_env(validator, account_exists=False)
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is True


def test_d1_zero_total_assets_skips(validator):
    """总资产 <= 0 → 无法计算比例 → 放行"""
    _mock_daily_loss_env(validator, account_balance=0.0, market_value=0.0)
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is True


def test_d1_repo_exception_degrades_open(validator):
    """数据源异常 → 降级放行 (基础设施故障不阻塞下单)"""
    _mock_daily_loss_env(validator, repo_raises=True)
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is True


def test_d1_validate_order_request_integration(validator):
    """全链路: validate_order_request 第 4 步触发熔断"""
    from core.trading.order_models import OrderType
    _mock_daily_loss_env(validator, account_balance=100000.0, market_value=0.0, filled_orders=[
        _filled_order(OrderType.BUY, 9.0, 10000, commission=0.0),
        _filled_order(OrderType.SELL, 8.3, 10000, commission=0.0),
    ])
    result = validator.validate_order_request(_make_request(order_type=OrderType.BUY))
    assert result.passed is False
    assert result.error_code == 'DAILY_LOSS_LIMIT_EXCEEDED'


def test_d1_flag_off_skips(validator):
    """validate_daily_loss=False 时跳过熔断检查"""
    from core.trading.order_models import OrderType
    validator._config['validate_daily_loss'] = False
    _mock_daily_loss_env(validator, filled_orders=[
        _filled_order(OrderType.SELL, 10.0, 1000, commission=0.0),
    ])
    result = validator._validate_daily_loss_limit(_make_request())
    assert result.passed is True


# ==================== D2: 风控预警自动响应 ====================

@pytest.fixture
def executor():
    """构造 OrderExecutor 实例 (patch __init__, 参照 R268 模式)"""
    from core.trading.order_executor import OrderExecutor
    with patch.object(OrderExecutor, '__init__', return_value=None):
        inst = OrderExecutor()
        inst._logger = MagicMock()
        inst._account_manager = MagicMock()
        inst._account_interface_cache = {}
        inst._max_retry_count = 3
        inst._interface_health = {}
        inst.event_bus = MagicMock()
        inst.service_container = MagicMock()
        inst._halted = False
        inst._risk_control_enabled = True

        def try_resolve(cls):
            return None

        mock_acct_mgr = MagicMock()
        mock_account = MagicMock()
        mock_account.available_cash = 1000000.0
        mock_account.position_limit = None
        mock_acct_mgr.get_account = MagicMock(return_value=mock_account)
        mock_acct_mgr.get_account_positions = MagicMock(return_value=[])

        def resolve(cls):
            return mock_acct_mgr

        inst.service_container.try_resolve = MagicMock(side_effect=try_resolve)
        inst.service_container.resolve = MagicMock(side_effect=resolve)
        inst._get_avg_entry_price = MagicMock(return_value=None)
        return inst


def test_d2_halt_blocks_new_orders(executor):
    """熔断后 _pre_trade_risk_check 拒绝一切新订单 (RISK_HALTED)"""
    executor.halt_trading(reason="测试熔断")
    assert executor.is_halted() is True
    order = SimpleNamespace(
        order_id='O1', account_id='acc_001', stock_code='000001',
        order_price=10.0, order_quantity=100,
    )
    result = executor._pre_trade_risk_check(order)
    assert result['passed'] is False
    assert result['error_code'] == 'RISK_HALTED'
    assert '熔断' in result['reason']


def test_d2_halt_blocks_even_risk_control_disabled(executor):
    """熔断期间即使风控开关关闭也不放行 (熔断为最高优先级)"""
    executor._risk_control_enabled = False
    executor.halt_trading(reason="测试")
    order = SimpleNamespace(
        order_id='O1', account_id='acc_001', stock_code='000001',
        order_price=10.0, order_quantity=100,
    )
    result = executor._pre_trade_risk_check(order)
    assert result['passed'] is False
    assert result['error_code'] == 'RISK_HALTED'


def test_d2_resume_restores_order_flow(executor):
    """resume_trading 解除熔断后订单恢复受理"""
    executor.halt_trading(reason="测试")
    executor.resume_trading()
    assert executor.is_halted() is False
    order = SimpleNamespace(
        order_id='O1', account_id='acc_001', stock_code='000001',
        order_price=10.0, order_quantity=100,
    )
    result = executor._pre_trade_risk_check(order)
    # 未熔断时走正常风控链路, 账户解析失败(无 mock)会触发账户风控异常拒绝 → 只验证非 RISK_HALTED
    assert result.get('error_code') != 'RISK_HALTED'


def test_d2_is_halted_initial_false(executor):
    """初始状态未熔断"""
    assert executor.is_halted() is False


def test_d2_resume_when_not_halted_noop(executor):
    """未熔断时 resume 无副作用"""
    executor.resume_trading()
    assert executor.is_halted() is False


def test_d2_subscriber_stop_trading_halts_executor():
    """stop_trading 事件 → 订阅器调用 OrderExecutor.halt_trading"""
    from core.risk.risk_event_subscribers import RiskEventSubscriber

    mock_executor = MagicMock()
    mock_container = MagicMock()
    mock_container.try_resolve = MagicMock(
        side_effect=lambda cls: mock_executor if 'OrderExecutor' in str(cls) else None)

    subscriber = RiskEventSubscriber(audit_logger=MagicMock())
    event = SimpleNamespace(duration_minutes=60, alert={'level': 'high'})

    with patch('core.containers.get_service_container', return_value=mock_container):
        subscriber._handle_risk_stop_trading(event)

    mock_executor.halt_trading.assert_called_once()
    assert '60' in mock_executor.halt_trading.call_args[1]['reason']


def test_d2_subscriber_emergency_liquidation_cancels_and_halts():
    """紧急平仓事件 → 取消所有活跃订单 + 熔断"""
    from core.risk.risk_event_subscribers import RiskEventSubscriber

    mock_executor = MagicMock()
    mock_order_service = MagicMock()
    mock_order_service.cancel_all_active_orders = MagicMock(return_value=3)
    mock_container = MagicMock()

    def try_resolve(cls):
        cls_name = str(cls)
        if 'OrderExecutor' in cls_name:
            return mock_executor
        if 'OrderService' in cls_name:
            return mock_order_service
        return None

    mock_container.try_resolve = MagicMock(side_effect=try_resolve)

    subscriber = RiskEventSubscriber(audit_logger=MagicMock())
    event = SimpleNamespace(alert={'level': 'critical'})

    with patch('core.containers.get_service_container', return_value=mock_container):
        subscriber._handle_risk_emergency_liquidation(event)

    mock_order_service.cancel_all_active_orders.assert_called_once_with()
    mock_executor.halt_trading.assert_called_once()


def test_d2_subscriber_defensive_when_container_unavailable():
    """容器/服务不可用时降级不崩溃"""
    from core.risk.risk_event_subscribers import RiskEventSubscriber

    subscriber = RiskEventSubscriber(audit_logger=MagicMock())
    event = SimpleNamespace(duration_minutes=30, alert={})

    with patch('core.containers.get_service_container', return_value=None):
        subscriber._handle_risk_stop_trading(event)  # 不应抛异常
        subscriber._handle_risk_emergency_liquidation(event)  # 不应抛异常


def test_d2_subscriber_initialize_subscribes_risk_events():
    """initialize 订阅 risk.stop_trading / risk.emergency_liquidation 等事件"""
    from core.risk.risk_event_subscribers import RiskEventSubscriber

    mock_bus = MagicMock()
    subscriber = RiskEventSubscriber(audit_logger=MagicMock())
    subscriber._event_bus = mock_bus

    with patch('core.risk.risk_event_subscribers.get_event_bus', return_value=mock_bus):
        subscriber.initialize()

    subscribed_events = {c[0][0] for c in mock_bus.subscribe.call_args_list}
    assert 'risk.monitor' in subscribed_events
    assert 'risk.stop_trading' in subscribed_events
    assert 'risk.emergency_liquidation' in subscribed_events
    assert subscriber.is_initialized() is True


def test_d2_bootstrap_wires_subscriber():
    """service_bootstrap 生产侧接线 get_risk_event_subscriber()"""
    source = Path(PROJECT_ROOT) / 'core' / 'services' / 'service_bootstrap.py'
    text = source.read_text(encoding='utf-8')
    assert 'get_risk_event_subscriber' in text
    assert 'R269-D2' in text


# ==================== D3-A: 持仓风控执行器复活融入 ====================

def test_d3_position_risk_monitor_components_initialized():
    """PositionRiskMonitor 构造后四组件全部就绪 (三复活组件 + PositionManager)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    assert monitor._stop_loss is not None
    assert monitor._take_profit is not None
    assert monitor._money_manager is not None
    assert monitor._position_manager is not None
    monitor.dispose()
    assert monitor._disposed is True
    monitor.dispose()  # 幂等


def test_d3_stop_price_fallback_without_kdata():
    """无 K 线行情 → 动态止损降级固定比例 (多头 -2%)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    monitor._get_kline_data = MagicMock(return_value=None)
    stop = monitor.get_dynamic_stop_price('000001', current_price=10.0, position=100)
    assert stop == pytest.approx(10.0 * (1 - 0.02))
    monitor.dispose()


def test_d3_stop_price_short_side_fallback():
    """无 K 线行情 → 空头止损降级固定比例 (+2%)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    monitor._get_kline_data = MagicMock(return_value=None)
    stop = monitor.get_dynamic_stop_price('000001', current_price=10.0, position=-100)
    assert stop == pytest.approx(10.0 * (1 + 0.02))
    monitor.dispose()


def test_d3_stop_price_uses_adaptive_when_kdata():
    """有 K 线 → 使用 AdaptiveStopLoss 自适应止损价 (计算成功, >0)"""
    import pandas as pd
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    df = pd.DataFrame({
        'open': [10.0, 10.0, 10.0], 'high': [10.5, 10.5, 10.5],
        'low': [9.5, 9.5, 9.5], 'close': [10.0, 10.0, 10.0],
        'volume': [100, 100, 100],
    })
    monitor._get_kline_data = MagicMock(return_value=df)
    stop = monitor.get_dynamic_stop_price('000001', current_price=10.0, position=100)
    # 止损价必须有效 (>0 且不等于现价, 方向由趋势因子决定, 本测试只验证计算链成功)
    assert stop > 0
    assert stop != 10.0
    monitor.dispose()


def test_d3_take_profit_fallback_and_adaptive():
    """止盈: 无 K 线固定 +2%; 有 K 线用 AdaptiveTakeProfit"""
    import pandas as pd
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    monitor._get_kline_data = MagicMock(return_value=None)
    tp = monitor.get_dynamic_take_profit('000001', current_price=10.0)
    assert tp == pytest.approx(10.0 * (1 + 0.02))

    df = pd.DataFrame({
        'open': [10.0, 10.0, 10.0], 'high': [10.5, 10.5, 10.5],
        'low': [9.5, 9.5, 9.5], 'close': [10.0, 10.0, 10.0],
        'volume': [100, 100, 100],
    })
    monitor._get_kline_data = MagicMock(return_value=df)
    tp2 = monitor.get_dynamic_take_profit('000001', current_price=10.0)
    assert tp2 > 0
    monitor.dispose()


def test_d3_position_size_uses_money_manager():
    """资金管理建议下单量 (EnhancedMoneyManager)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    monitor._money_manager = MagicMock()
    monitor._money_manager.calculate_position_size = MagicMock(return_value=500)
    size = monitor.calculate_position_size(10.0, 9.8, 100000.0)
    assert size == 500
    monitor.dispose()


def test_d3_position_size_zero_when_money_manager_missing():
    """资金管理器缺失 → 返回 0 (不阻断)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    monitor._money_manager = None
    assert monitor.calculate_position_size(10.0, 9.8, 100000.0) == 0
    monitor.dispose()


def test_d3_exposure_calculation():
    """多空敞口计算 (PositionManager.calculate_exposure)"""
    from core.trading.position_risk_monitor import PositionRiskMonitor
    monitor = PositionRiskMonitor(service_container=None)
    monitor._position_manager = MagicMock()
    monitor._position_manager.calculate_exposure = MagicMock(
        return_value={'long': 50000.0, 'short': 20000.0, 'net': 30000.0})
    result = monitor.calculate_exposure([object()])
    assert result['long'] == 50000.0
    assert result['short'] == 20000.0
    assert result['net'] == 30000.0
    # 无持仓 → 全 0
    empty = monitor.calculate_exposure([])
    assert empty == {'long': 0.0, 'short': 0.0, 'net': 0.0}
    monitor.dispose()


def test_d3_take_profit_accepts_params():
    """AdaptiveTakeProfit 支持 params 构造参数 (R269-D3 对齐)"""
    from core.take_profit import AdaptiveTakeProfit
    tp = AdaptiveTakeProfit(params={'atr_multiplier': 3})
    assert tp.get_param('atr_multiplier') == 3
    assert tp.get_param('atr_period') == 14  # 默认值保留
    assert tp.get_param('min_take_profit') == 0.02


def test_d3_fill_stop_loss_level_populates(executor):
    """order_executor._fill_stop_loss_level 填充 stop_loss_levels (修复空转)"""
    from core.risk_control import RiskControlStrategy
    order = SimpleNamespace(stock_code='000001', account_id='acc_001',
                            order_price=10.0, create_time=None)
    mock_monitor = MagicMock()
    mock_monitor.get_dynamic_stop_price = MagicMock(return_value=9.8)
    executor.service_container.try_resolve = MagicMock(return_value=mock_monitor)

    risk_ctrl = RiskControlStrategy()
    executor._fill_stop_loss_level(risk_ctrl, order, entry_price=10.0, position=100)
    assert risk_ctrl.stop_loss_levels['000001'] == pytest.approx(9.8)


def test_d3_stop_loss_check_no_longer_spins(executor):
    """端到端: 下单路径止损检查不再空转, 现价跌破动态止损价 → 拒单"""
    order = SimpleNamespace(order_id='O1', stock_code='000001', account_id='acc_001',
                            order_price=9.4, order_quantity=100, create_time=None)
    mock_monitor = MagicMock()
    mock_monitor.get_dynamic_stop_price = MagicMock(return_value=9.5)
    executor.service_container.try_resolve = MagicMock(return_value=mock_monitor)
    executor._get_avg_entry_price = MagicMock(return_value=10.0)
    executor._get_position = MagicMock(return_value=100)

    result = executor._pre_trade_risk_check(order)
    assert result['passed'] is False
    assert '风控止损触发' in result['reason']


def test_d3_stop_loss_check_passes_above_stop(executor):
    """现价高于动态止损价 → 放行"""
    order = SimpleNamespace(order_id='O1', stock_code='000001', account_id='acc_001',
                            order_price=9.6, order_quantity=100, create_time=None)
    mock_monitor = MagicMock()
    mock_monitor.get_dynamic_stop_price = MagicMock(return_value=9.5)
    executor.service_container.try_resolve = MagicMock(return_value=mock_monitor)
    executor._get_avg_entry_price = MagicMock(return_value=10.0)
    executor._get_position = MagicMock(return_value=100)

    result = executor._pre_trade_risk_check(order)
    assert result['passed'] is True


def test_d3_check_stop_loss_trigger_fallback():
    """check_stop_loss_trigger 无 level 时固定比例兜底 (消除恒放行)"""
    from core.risk_control import RiskControlStrategy
    risk_ctrl = RiskControlStrategy()
    # 多头: entry 10.0 → 兜底止损 9.5; current 9.4 <= 9.5 → 触发
    triggered, reason = risk_ctrl.check_stop_loss_trigger(
        asset='000001', position=100, entry_price=10.0, current_price=9.4)
    assert triggered is True
    # current 9.6 > 9.5 → 不触发
    triggered2, _ = risk_ctrl.check_stop_loss_trigger(
        asset='000001', position=100, entry_price=10.0, current_price=9.6)
    assert triggered2 is False
    # 空头: entry 10.0 → 兜底止损 10.5; current 10.6 >= 10.5 → 触发
    triggered3, _ = risk_ctrl.check_stop_loss_trigger(
        asset='000001', position=-100, entry_price=10.0, current_price=10.6)
    assert triggered3 is True


def test_d3_trade_orchestrator_removed():
    """死类 TradeOrchestrator 已移除 (半成品, TradingInstruction 无定义)"""
    source = Path(PROJECT_ROOT) / 'core' / 'risk_manager.py'
    text = source.read_text(encoding='utf-8')
    assert 'R269-D3 REMOVED' in text
    assert 'def orchestrate' not in text
    assert 'TradingInstruction(' not in text
    # 活类 RiskManager 保留
    assert 'class RiskManager' in text


def test_d3_bootstrap_registers_position_risk_monitor():
    """service_bootstrap 注册 PositionRiskMonitor (R269-D3)"""
    source = Path(PROJECT_ROOT) / 'core' / 'services' / 'service_bootstrap.py'
    text = source.read_text(encoding='utf-8')
    assert 'PositionRiskMonitor' in text
    assert 'R269-D3' in text


# ==================== D4: 风险评估面板激活 (BettaFishAgent 补方法) ====================

@pytest.fixture
def bettafish_agent():
    """构造 BettaFishAgent 实例 (patch __init__, 注入真实 RiskAssessmentAgent)"""
    from core.agents.bettafish_agent import BettaFishAgent
    from core.agents.risk_agent import RiskAssessmentAgent
    with patch.object(BettaFishAgent, '__init__', return_value=None):
        inst = BettaFishAgent()
    inst.risk_agent = RiskAssessmentAgent()
    return inst


def _make_risk_cache_entry(risk_score=42.0, var=0.03, alerts=None):
    """构造 risk_agent._risk_cache 的成功评估缓存项"""
    from datetime import datetime
    from core.agents.risk_agent import (
        RiskAssessmentResult, RiskAlert, RiskLevel, RiskMetric, RiskType,
    )
    metrics = [
        RiskMetric('Volatility', 0.25, RiskLevel.MEDIUM, '年化波动率: 25.00%', 0.03, 1.0),
        RiskMetric('MaxDrawdown', 0.18, RiskLevel.MEDIUM, '最大回撤: 18.00%', 0.2, 0.9),
        RiskMetric('SharpeRatio', 0.8, RiskLevel.LOW, '夏普比率: 0.80', 0.5, 0.9),
        RiskMetric('MarketRisk', 1.1, RiskLevel.MEDIUM, '市场风险系数: 1.10', 1.2, 0.9),
        RiskMetric('ConcentrationRisk', 0.6, RiskLevel.HIGH, '集中度风险', 0.6, 1.0),
        RiskMetric('Beta', 1.2, RiskLevel.MEDIUM, 'Beta系数: 1.20', 1.5, 1.0),
    ]
    return {
        'status': 'success',
        'assessment_result': RiskAssessmentResult(
            stock_code='000001',
            assessment_time=datetime.now(),
            overall_risk_level=RiskLevel.MEDIUM,
            risk_score=risk_score,
            risk_metrics=metrics,
            risk_alerts=alerts or [],
            risk_decomposition={'MarketRisk': 0.4, 'LiquidityRisk': 0.3,
                                'ConcentrationRisk': 0.3},
            var_estimate=var,
            recommendations=['建议控制仓位'],
            confidence=0.8,
        ),
    }


def test_d4_panel_methods_exist(bettafish_agent):
    """BettaFishAgent 提供 get_risk_assessment/get_risk_alerts (面板 hasattr 激活条件)"""
    assert hasattr(bettafish_agent, 'get_risk_assessment')
    assert hasattr(bettafish_agent, 'get_risk_alerts')
    # 面板调用点保持无参调用
    risk = bettafish_agent.get_risk_assessment()
    assert isinstance(risk, dict)


def test_d4_default_risk_assessment_keys(bettafish_agent):
    """无缓存 → 默认数据含面板全部期望键 (overall_risk 0 占位)"""
    risk = bettafish_agent.get_risk_assessment()
    expected_keys = {
        'overall_risk', 'var_95', 'max_drawdown', 'sharpe_ratio', 'volatility',
        'correlation', 'concentration', 'market_risk', 'liquidity_risk',
        'credit_risk', 'operational_risk', 'concentration_risk',
        'market_risk_pct', 'liquidity_risk_pct', 'credit_risk_pct',
        'operational_risk_pct', 'concentration_risk_pct',
    }
    assert expected_keys.issubset(risk.keys())
    assert risk['overall_risk'] == 0
    # 无缓存时 breakdown 均分兜底 (100/5)
    assert risk['market_risk_pct'] == pytest.approx(20.0)


def test_d4_risk_assessment_from_cache(bettafish_agent):
    """缓存存在 → 返回真实评估值 (键映射正确)"""
    bettafish_agent.risk_agent._risk_cache['risk_assessment_000001_0'] = \
        _make_risk_cache_entry(risk_score=42.0, var=0.03)
    risk = bettafish_agent.get_risk_assessment()
    assert risk['overall_risk'] == 42.0
    assert risk['var_95'] == pytest.approx(3.0)          # 0.03 * 100
    assert risk['max_drawdown'] == pytest.approx(18.0)   # 0.18 * 100
    assert risk['sharpe_ratio'] == pytest.approx(0.8)
    assert risk['volatility'] == pytest.approx(25.0)     # 0.25 * 100
    assert risk['correlation'] == pytest.approx(1.2)     # Beta 值
    assert risk['concentration'] == pytest.approx(60.0)  # 0.6 * 100
    assert risk['market_risk'] == 'medium'
    assert risk['concentration_risk'] == 'high'
    assert risk['market_risk_pct'] == pytest.approx(40.0)  # 0.4 * 100


def test_d4_latest_cache_entry_wins(bettafish_agent):
    """多缓存项 → 取最后一条 (最新评估)"""
    from datetime import datetime
    from core.agents.risk_agent import RiskAssessmentResult, RiskLevel
    entry = _make_risk_cache_entry(risk_score=42.0)
    entry2 = _make_risk_cache_entry(risk_score=75.0)
    entry2['assessment_result'] = RiskAssessmentResult(
        stock_code='000002', assessment_time=datetime.now(),
        overall_risk_level=RiskLevel.HIGH, risk_score=75.0,
        risk_metrics=[], risk_alerts=[], risk_decomposition={},
        var_estimate=None, recommendations=[], confidence=0.5)
    bettafish_agent.risk_agent._risk_cache['a'] = entry
    bettafish_agent.risk_agent._risk_cache['b'] = entry2
    risk = bettafish_agent.get_risk_assessment()
    assert risk['overall_risk'] == 75.0


def test_d4_risk_alerts_empty(bettafish_agent):
    """无缓存 → 预警列表为空"""
    assert bettafish_agent.get_risk_alerts() == []


def test_d4_risk_alerts_from_cache(bettafish_agent):
    """缓存含 HIGH 预警 → 转换为面板期望格式 (level ERROR)"""
    from datetime import datetime
    from core.agents.risk_agent import RiskAlert, RiskLevel, RiskType
    alert = RiskAlert(risk_type=RiskType.MARKET_RISK, level=RiskLevel.HIGH,
                      message='市场风险较高', timestamp=datetime.now(),
                      action_required=True)
    bettafish_agent.risk_agent._risk_cache['risk_assessment_000001_0'] = \
        _make_risk_cache_entry(alerts=[alert])
    alerts = bettafish_agent.get_risk_alerts()
    assert len(alerts) == 1
    assert alerts[0]['level'] == 'ERROR'
    assert alerts[0]['type'] == 'market_risk'
    assert alerts[0]['description'] == '市场风险较高'
    assert hasattr(alerts[0]['timestamp'], 'strftime')


def test_d4_panel_source_wiring():
    """面板调用点与 agent 方法契约一致 (hasattr 条件可被满足)"""
    panel_source = Path(PROJECT_ROOT) / 'gui' / 'widgets' / 'bettafish_dashboard' / \
        'risk_assessment_panel.py'
    text = panel_source.read_text(encoding='utf-8')
    assert "hasattr(self._bettafish_agent, 'get_risk_assessment')" in text
    assert "hasattr(self._bettafish_agent, 'get_risk_alerts')" in text
    agent_source = Path(PROJECT_ROOT) / 'core' / 'agents' / 'bettafish_agent.py'
    agent_text = agent_source.read_text(encoding='utf-8')
    assert 'def get_risk_assessment' in agent_text
    assert 'def get_risk_alerts' in agent_text
    assert 'def _risk_assessment_to_panel_dict' in agent_text
    assert 'def _default_risk_assessment' in agent_text
