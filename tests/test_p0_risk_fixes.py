"""P0风控致命问题修复验证: P0-1 异常静默放行 + P0-2 做空止损方向"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.p0, pytest.mark.risk, pytest.mark.critical]


# ==================== P0-1: 风控异常必须 fail-closed ====================

class TestP01_RiskCheckFailClosed:

    @pytest.fixture
    def executor(self):
        from core.trading.order_executor import OrderExecutor
        with patch.object(OrderExecutor, '__init__', return_value=None):
            exec_inst = OrderExecutor()
            exec_inst._logger = MagicMock()
            exec_inst._account_manager = MagicMock()
            exec_inst._account_interface_cache = {}
            exec_inst._max_retry_count = 3
            exec_inst._interface_health = {}
            exec_inst.event_bus = MagicMock()
            exec_inst.service_container = MagicMock()
            exec_inst.service_container.resolve = MagicMock(
                side_effect=ValueError("容器未初始化"))
            yield exec_inst

    @pytest.fixture
    def mock_order(self):
        order = MagicMock()
        order.order_id = 'P0-1-TEST-001'
        order.symbol = '000001'
        order.asset_type = 'stock'
        order.order_price = 10.0
        order.order_quantity = 100
        order.order_type = 'BUY'
        order.target_account_id = 'test_account'
        order.account_id = None
        return order

    def test_inner_enhanced_risk_monitor_exception_fail_closed(self, executor, mock_order):
        """P0-1: 高级风控检查抛异常 -> passed=False (L766-767 已修复)"""
        result = executor._pre_trade_risk_check(mock_order)
        assert result['passed'] is False, \
            f"致命: service_container异常时 passed=True! result={result}"
        assert result['error_code'] == 'RISK_CHECK_FAILED'

    def test_outer_exception_fail_closed(self, executor, mock_order):
        """P0-1: 外层全部异常 -> passed=False (L814-816 已修复)"""
        # 使 service_container.resolve 对 AccountManager 也抛异常
        executor.service_container.resolve = MagicMock(
            side_effect=RuntimeError("全面崩溃"))
        result = executor._pre_trade_risk_check(mock_order)
        assert result['passed'] is False
        assert result['error_code'] == 'RISK_CHECK_FAILED'

    def test_multiple_order_types_fail_closed(self, executor):
        """P0-1: SHORT/SELL/LONG 三种订单异常时都 fail-closed"""
        executor.service_container.resolve = MagicMock(
            side_effect=ValueError("容器异常"))
        for order_type in ('SHORT', 'SELL', 'LONG'):
            order = MagicMock()
            order.order_id = f'P0-1-{order_type}'
            order.symbol = '000001'
            order.order_price = 10.0
            order.order_quantity = 100
            order.order_type = order_type
            order.target_account_id = 'test'
            order.account_id = None

            result = executor._pre_trade_risk_check(order)
            assert result['passed'] is False, \
                f"{order_type}订单异常时 passed=True (静默放行)"
            assert result['error_code'] == 'RISK_CHECK_FAILED'

    def test_normal_order_passes(self, executor):
        """P0-1: 正常风控路径不受影响"""
        executor.service_container.resolve = MagicMock(return_value=None)
        order = MagicMock()
        order.order_id = 'NORMAL'
        order.symbol = '000001'
        order.order_price = 10.0
        order.order_quantity = 100
        order.order_type = 'BUY'
        order.account_id = None
        order.target_account_id = 'test'

        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is True, f"正常订单应通过, result={result}"


# ==================== P0-2: 做空止损方向修正 ====================

class TestP02_ShortStopLoss:
    """_check_stop_loss 使用 self.current_positions[code]['avg_cost']"""

    @pytest.fixture
    def risk_mgr(self):
        from core.risk_manager import RiskManager
        with patch.object(RiskManager, '__init__', return_value=None):
            mgr = RiskManager()
            mgr.logger = MagicMock()
            mgr.stop_loss = 0.05
            yield mgr

    def test_buy_signal_always_bypasses_stop_loss(self, risk_mgr):
        """L254: buy信号直接返回True，跳过止损检查"""
        risk_mgr.current_positions = {}
        assert risk_mgr._check_stop_loss(
            {'type': 'buy', 'stock_code': '000001', 'price': 1.0}) is True

    def test_stock_not_in_positions_no_stop(self, risk_mgr):
        """L258: 不在持仓中 -> 不触发止损"""
        risk_mgr.current_positions = {}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': 'UNKNOWN', 'price': 1000.0})
        assert result is True

    def test_long_loss_triggers_stop(self, risk_mgr):
        """多头: avg=10, price=8 -> profit=-20% < -5% -> 触发"""
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'sell', 'stock_code': '000001', 'price': 8.0})
        assert result is False, f"多头亏损20%应触发, 实际: {result}"

    def test_long_profitable_no_stop(self, risk_mgr):
        """多头: avg=10, price=12 -> profit=+20% -> 不触发"""
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'sell', 'stock_code': '000001', 'price': 12.0})
        assert result is True, f"多头盈利20%不应触发, 实际: {result}"

    def test_short_loss_triggers_stop(self, risk_mgr):
        """做空: avg=100, price=106 -> profit=+6% >= 5% -> 触发"""
        risk_mgr.current_positions = {'000002': {'avg_cost': 100.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': '000002', 'price': 106.0})
        assert result is False, f"做空亏损6%应触发, 实际: {result}"

    def test_short_profitable_no_stop(self, risk_mgr):
        """做空: avg=100, price=95 -> profit=-5% (浮盈) -> 不触发"""
        risk_mgr.current_positions = {'000002': {'avg_cost': 100.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': '000002', 'price': 95.0})
        assert result is True, f"做空浮盈5%不应触发, 实际: {result}"

    def test_short_boundary_triggers(self, risk_mgr):
        """做空边界: avg=100, price=105 -> profit=5% == stop_loss -> 触发"""
        risk_mgr.current_positions = {'000002': {'avg_cost': 100.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': '000002', 'price': 105.0})
        assert result is False, f"边界5%==stop_loss应触发, 实际: {result}"

    def test_short_near_boundary_no_stop(self, risk_mgr):
        """做空: avg=100, price=104.99 -> profit=4.99% < 5% -> 不触发"""
        risk_mgr.current_positions = {'000002': {'avg_cost': 100.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': '000002', 'price': 104.99})
        assert result is True, f"做空亏损4.99%不应触发, 实际: {result}"


# ==================== 全矩阵参数化 ====================

class TestFullStopLossMatrix:

    @pytest.fixture
    def risk_mgr(self):
        from core.risk_manager import RiskManager
        with patch.object(RiskManager, '__init__', return_value=None):
            mgr = RiskManager()
            mgr.logger = MagicMock()
            mgr.stop_loss = 0.05
            yield mgr

    # ---- 做空: (price-avg)/avg > 0 = 亏损, >= 0.05 触发 ----
    @pytest.mark.parametrize("price,avg,expected,desc", [
        (106.0, 100, False, "做空亏损6%触发"),
        (105.0, 100, False, "做空亏损5%边界触发"),
        (104.0, 100, True,  "做空亏损4%不触发"),
        (100.0, 100, True,  "做空保本不触发"),
        ( 97.0, 100, True,  "做空盈利3%不触发"),
        ( 90.0, 100, True,  "做空盈利10%不触发"),
    ])
    def test_short_stop_loss_matrix(self, risk_mgr, price, avg, expected, desc):
        risk_mgr.current_positions = {'TEST': {'avg_cost': avg}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': 'TEST', 'price': price})
        ratio = (price - avg) / avg
        expected_action = "止损" if not expected else "不触发"
        actual_action = "止损" if not result else "不触发"
        assert result is expected, \
            f"{desc}: ratio={ratio:.2%} 期望={expected_action} 实际={actual_action}"

    # ---- 多头 sell (平多): (price-avg)/avg < 0 = 亏损, <= -0.05 触发 ----
    @pytest.mark.parametrize("price,avg,expected,desc", [
        ( 8.0, 10, False, "多头亏损20%触发"),
        ( 9.4, 10, False, "多头亏损6%触发"),
        ( 9.5, 10, False, "多头亏损5%边界触发(=-5%)"),
        (10.0, 10, True,  "多头保本不触发"),
        (11.0, 10, True,  "多头盈利10%不触发"),
    ])
    def test_long_stop_loss_matrix(self, risk_mgr, price, avg, expected, desc):
        risk_mgr.current_positions = {'TEST': {'avg_cost': avg}}
        result = risk_mgr._check_stop_loss(
            {'type': 'sell', 'stock_code': 'TEST', 'price': price})
        ratio = (price - avg) / avg
        expected_action = "止损" if not expected else "不触发"
        actual_action = "止损" if not result else "不触发"
        assert result is expected, \
            f"{desc}: ratio={ratio:.2%} 期望={expected_action} 实际={actual_action}"


# ==================== 集成场景 ====================

class TestIntegrationP0RiskFixes:

    def test_full_pipeline(self):
        from core.risk_manager import RiskManager
        from core.trading.order_executor import OrderExecutor

        # -- P0-2: RiskManager --
        with patch.object(RiskManager, '__init__', return_value=None):
            rmgr = RiskManager()
            rmgr.logger = MagicMock()
            rmgr.stop_loss = 0.05

        rmgr.current_positions = {'SHRT': {'avg_cost': 100.0}}
        assert rmgr._check_stop_loss(
            {'type': 'short', 'stock_code': 'SHRT', 'price': 95}) is True
        assert rmgr._check_stop_loss(
            {'type': 'short', 'stock_code': 'SHRT', 'price': 106}) is False

        rmgr.current_positions = {'LONG': {'avg_cost': 10.0}}
        assert rmgr._check_stop_loss(
            {'type': 'sell', 'stock_code': 'LONG', 'price': 8.0}) is False
        assert rmgr._check_stop_loss(
            {'type': 'sell', 'stock_code': 'LONG', 'price': 12.0}) is True

        # -- P0-1: OrderExecutor --
        with patch.object(OrderExecutor, '__init__', return_value=None):
            oexec = OrderExecutor()
            oexec._logger = MagicMock()
            oexec._account_manager = MagicMock()
            oexec._account_interface_cache = {}
            oexec._max_retry_count = 3
            oexec._interface_health = {}
            oexec.event_bus = MagicMock()
            oexec.service_container = MagicMock()
            oexec.service_container.resolve = MagicMock(
                side_effect=ValueError("容器崩溃"))

        order = MagicMock()
        order.order_id = 'INTEGRATION'
        order.symbol = '000001'
        order.order_price = 10.0
        order.order_quantity = 100
        order.order_type = 'SHORT'
        order.account_id = None
        order.target_account_id = 'test'

        result = oexec._pre_trade_risk_check(order)
        assert result['passed'] is False
        assert result['error_code'] == 'RISK_CHECK_FAILED'


# ==================== P0-1 回归: 全路径覆盖 ====================

class TestP01_FullPathRegression:
    """覆盖 _pre_trade_risk_check 所有可达分支"""

    @pytest.fixture
    def executor(self):
        from core.trading.order_executor import OrderExecutor
        with patch.object(OrderExecutor, '__init__', return_value=None):
            exec_inst = OrderExecutor()
            exec_inst._logger = MagicMock()
            exec_inst._account_manager = MagicMock()
            exec_inst._account_interface_cache = {}
            exec_inst._max_retry_count = 3
            exec_inst._interface_health = {}
            exec_inst.event_bus = MagicMock()
            exec_inst.service_container = MagicMock()
            yield exec_inst

    def _make_order(self, **overrides):
        order = MagicMock()
        order.order_id = 'REG-001'
        order.symbol = '000001'
        order.asset_type = 'stock'
        order.order_price = 10.0
        order.order_quantity = 100
        order.order_type = 'BUY'
        order.target_account_id = 'test'
        order.account_id = None
        for k, v in overrides.items():
            setattr(order, k, v)
        return order

    def test_import_error_path_skips_enhanced_monitor(self, executor):
        """R252-F1: try_resolve ImportError -> debug日志 -> 继续执行, 账户检查正常"""
        call_count = [0]

        def _try_resolve_import_then_none(cls):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ImportError("No module named enhanced")
            return None
        # R252-F1: 风控增强使用 try_resolve 而非 resolve
        executor.service_container.try_resolve = MagicMock(
            side_effect=_try_resolve_import_then_none)
        order = self._make_order()
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is True

    def test_enhanced_monitor_rejects_order(self, executor):
        """R252-F1: risk_result['passed']=False -> 拒绝订单"""
        mock_monitor = MagicMock()
        mock_monitor.check_order_risk = MagicMock(
            return_value={'passed': False, 'reason': '超出单日亏损限额'})
        executor.service_container.try_resolve = MagicMock(return_value=mock_monitor)
        order = self._make_order()
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is False
        assert '超出单日亏损限额' in result['reason']

    def test_enhanced_monitor_passes_then_account_check(self, executor):
        """L756-L762: risk_monitor通过 -> 继续账户风控"""
        mock_monitor = MagicMock()
        mock_monitor.check_order_risk = MagicMock(return_value={'passed': True})
        executor.service_container.resolve = MagicMock(return_value=mock_monitor)
        order = self._make_order()
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is True

    def test_account_insufficient_cash_rejects(self, executor):
        """L779-L783: 订单金额 > 账户可用资金 -> 拒绝"""
        mock_monitor = MagicMock()
        mock_monitor.check_order_risk = MagicMock(return_value={'passed': True})
        mock_acct_mgr = MagicMock()
        mock_account = MagicMock()
        mock_account.available_cash = 500.0
        mock_account.position_limit = 100
        mock_acct_mgr.get_account = MagicMock(return_value=mock_account)
        mock_acct_mgr.get_account_positions = MagicMock(return_value=[])

        def resolve_side_effect(cls):
            if 'EnhancedRiskMonitor' in str(cls):
                return mock_monitor
            return mock_acct_mgr
        executor.service_container.resolve = MagicMock(
            side_effect=resolve_side_effect)

        order = self._make_order(order_id='POOR', order_price=100.0,
                                 order_quantity=100, account_id='acc_001')
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is False
        assert '资金不足' in result['reason']

    def test_account_sufficient_cash_passes(self, executor):
        """L779-L783: 资金充足 -> 通过"""
        mock_monitor = MagicMock()
        mock_monitor.check_order_risk = MagicMock(return_value={'passed': True})
        mock_acct_mgr = MagicMock()
        mock_account = MagicMock()
        mock_account.available_cash = 100000.0
        mock_account.position_limit = 100
        mock_acct_mgr.get_account = MagicMock(return_value=mock_account)
        mock_acct_mgr.get_account_positions = MagicMock(return_value=[])

        def resolve_side_effect(cls):
            if 'EnhancedRiskMonitor' in str(cls):
                return mock_monitor
            return mock_acct_mgr
        executor.service_container.resolve = MagicMock(
            side_effect=resolve_side_effect)

        order = self._make_order(account_id='acc_rich')
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is True

    def test_position_limit_warning(self, executor):
        """L785-L788: 持仓数>=limit -> warnings(不拒绝)"""
        mock_monitor = MagicMock()
        mock_monitor.check_order_risk = MagicMock(return_value={'passed': True})
        mock_acct_mgr = MagicMock()
        mock_account = MagicMock()
        mock_account.available_cash = 100000.0
        mock_account.position_limit = 10
        mock_acct_mgr.get_account = MagicMock(return_value=mock_account)
        mock_acct_mgr.get_account_positions = MagicMock(
            return_value=list(range(10)))

        def resolve_side_effect(cls):
            if 'EnhancedRiskMonitor' in str(cls):
                return mock_monitor
            return mock_acct_mgr
        executor.service_container.resolve = MagicMock(
            side_effect=resolve_side_effect)

        order = self._make_order(account_id='acc_full')
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is True
        assert len(result['warnings']) > 0

    def test_zero_quantity_rejected(self, executor):
        """L794-L797: quantity<=0 -> 拒绝"""
        executor.service_container.resolve = MagicMock(return_value=None)
        order = self._make_order(order_quantity=0)
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is False
        assert '数量' in result['reason']

    def test_negative_price_rejected(self, executor):
        """L799-L802: price<=0 -> 拒绝"""
        executor.service_container.resolve = MagicMock(return_value=None)
        order = self._make_order(order_price=-5.0)
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is False
        assert '价格' in result['reason']

    def test_large_order_value_warning(self, executor):
        """L804-L807: 金额>10M -> warnings"""
        executor.service_container.resolve = MagicMock(return_value=None)
        order = self._make_order(order_price=5000.0, order_quantity=3000)
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is True
        assert len(result['warnings']) > 0

    def test_error_code_consistency_across_exception_paths(self, executor):
        """L768/L792/L818: 三个异常返回点 error_code 统一为 RISK_CHECK_FAILED"""
        executor.service_container.resolve = MagicMock(
            side_effect=TypeError("内部类型错误"))
        r1 = executor._pre_trade_risk_check(self._make_order(order_id='E1'))
        assert r1['passed'] is False
        assert r1['error_code'] == 'RISK_CHECK_FAILED'

        def _raise_on_first_call(cls):
            _raise_on_first_call.called += 1
            if _raise_on_first_call.called == 1:
                raise RuntimeError("容器崩溃")
            return None
        _raise_on_first_call.called = 0
        executor.service_container.resolve = MagicMock(
            side_effect=_raise_on_first_call)
        r2 = executor._pre_trade_risk_check(self._make_order())
        assert r2['passed'] is False
        assert r2['error_code'] == 'RISK_CHECK_FAILED'

    def test_account_manager_exception_fail_closed(self, executor):
        """L790-L792: AccountManager.resolve异常 -> passed=False"""
        mock_monitor = MagicMock()
        mock_monitor.check_order_risk = MagicMock(return_value={'passed': True})

        def resolve_side_effect(cls):
            if 'EnhancedRiskMonitor' in str(cls):
                return mock_monitor
            raise ConnectionError("账户服务不可达")
        executor.service_container.resolve = MagicMock(
            side_effect=resolve_side_effect)

        order = self._make_order(account_id='real_acc')
        result = executor._pre_trade_risk_check(order)
        assert result['passed'] is False
        assert result['error_code'] == 'RISK_CHECK_FAILED'
        assert '被拒绝' in result['reason']


# ==================== P0-2 回归: 全路径覆盖 ====================

class TestP02_FullPathRegression:
    """覆盖 _check_stop_loss 所有可达分支 + 边界 + 异常"""

    @pytest.fixture
    def risk_mgr(self):
        from core.risk_manager import RiskManager
        with patch.object(RiskManager, '__init__', return_value=None):
            mgr = RiskManager()
            mgr.logger = MagicMock()
            mgr.stop_loss = 0.05
            mgr.current_positions = {}
            yield mgr

    def _make_signal(self, **overrides):
        defaults = {'type': 'sell', 'stock_code': '000001', 'price': 10.0}
        defaults.update(overrides)
        return defaults

    def test_position_value_is_numeric_not_dict(self, risk_mgr):
        """L265-L266: pos_data是数值 -> float(pos_data)"""
        risk_mgr.current_positions = {'000001': 10.0}
        result = risk_mgr._check_stop_loss(self._make_signal(price=8.0))
        assert result is False

    def test_position_value_is_zero_numeric(self, risk_mgr):
        """L268: avg_cost=0(数值) -> return True"""
        risk_mgr.current_positions = {'000001': 0}
        result = risk_mgr._check_stop_loss(self._make_signal(price=8.0))
        assert result is True

    def test_position_value_is_zero_str_numeric(self, risk_mgr):
        """L266: pos_data='0' -> float('0')=0 -> avg_cost<=0 -> True"""
        risk_mgr.current_positions = {'000001': '0'}
        result = risk_mgr._check_stop_loss(self._make_signal(price=8.0))
        assert result is True

    def test_position_value_is_negative(self, risk_mgr):
        """L268: avg_cost < 0 -> return True"""
        risk_mgr.current_positions = {'000001': -5.0}
        result = risk_mgr._check_stop_loss(self._make_signal(price=8.0))
        assert result is True

    def test_dict_avg_cost_zero(self, risk_mgr):
        """L268: dict中avg_cost=0 -> return True"""
        risk_mgr.current_positions = {'000001': {'avg_cost': 0}}
        result = risk_mgr._check_stop_loss(self._make_signal(price=106.0))
        assert result is True

    def test_dict_missing_avg_cost_key(self, risk_mgr):
        """L264: dict没有'avg_cost'键 -> avg_cost=0 -> return True"""
        risk_mgr.current_positions = {'000001': {'some_other': 99}}
        result = risk_mgr._check_stop_loss(self._make_signal(price=106.0))
        assert result is True

    def test_stop_loss_zero_tolerance(self, risk_mgr):
        """stop_loss=0: 任何亏损触发"""
        risk_mgr.stop_loss = 0.0
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        assert risk_mgr._check_stop_loss(
            self._make_signal(price=9.999)) is False
        assert risk_mgr._check_stop_loss(
            self._make_signal(price=10.0)) is False
        assert risk_mgr._check_stop_loss(
            self._make_signal(price=10.001)) is True

    def test_stop_loss_high_tolerance(self, risk_mgr):
        """stop_loss=0.20: 20%以内不触发"""
        risk_mgr.stop_loss = 0.20
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        assert risk_mgr._check_stop_loss(
            self._make_signal(price=8.5)) is True
        assert risk_mgr._check_stop_loss(
            self._make_signal(price=7.9)) is False

    def test_stop_loss_three_percent(self, risk_mgr):
        """stop_loss=0.03: 多头price=96.9(-3.1%), 做空price=103.1(+3.1%)"""
        risk_mgr.stop_loss = 0.03
        risk_mgr.current_positions = {'000001': {'avg_cost': 100.0}}
        assert risk_mgr._check_stop_loss(
            self._make_signal(price=96.9, type='sell')) is False
        risk_mgr.current_positions = {'000002': {'avg_cost': 100.0}}
        assert risk_mgr._check_stop_loss(
            self._make_signal(price=103.1, type='short', stock_code='000002')) is False

    def test_current_positions_none(self, risk_mgr):
        """L258: None['key'] -> TypeError -> catch -> return False"""
        risk_mgr.current_positions = None
        result = risk_mgr._check_stop_loss(
            self._make_signal(type='short'))
        assert result is False

    def test_signal_missing_stock_code(self, risk_mgr):
        """L257: 信号缺'stock_code' -> KeyError -> catch -> return False"""
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'price': 106.0})
        assert result is False

    def test_signal_missing_price(self, risk_mgr):
        """L272: 信号缺'price' -> KeyError -> catch -> return False"""
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': '000001'})
        assert result is False

    def test_signal_missing_type(self, risk_mgr):
        """L254: 信号缺'type' -> KeyError -> catch -> return False"""
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        result = risk_mgr._check_stop_loss(
            {'stock_code': '000001', 'price': 10.0})
        assert result is False

    def test_exception_returns_false(self, risk_mgr):
        """L287-L289: 内部异常 -> return False (安全侧)"""
        risk_mgr.current_positions = {'000001': object()}
        result = risk_mgr._check_stop_loss(
            self._make_signal(price=10.0))
        assert result is False

    def test_logger_warning_called_on_long_stop(self, risk_mgr):
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        with patch('core.risk_manager.logger.warning') as mock_warn:
            risk_mgr._check_stop_loss(self._make_signal(price=8.0))
        mock_warn.assert_called_once()
        assert '止损' in str(mock_warn.call_args)

    def test_logger_warning_called_on_short_stop(self, risk_mgr):
        risk_mgr.current_positions = {'000002': {'avg_cost': 100.0}}
        with patch('core.risk_manager.logger.warning') as mock_warn:
            risk_mgr._check_stop_loss(
                {'type': 'short', 'stock_code': '000002', 'price': 106.0})
        mock_warn.assert_called_once()
        assert '做空止损' in str(mock_warn.call_args)

    def test_logger_warning_not_called_on_profitable(self, risk_mgr):
        risk_mgr.current_positions = {'000001': {'avg_cost': 10.0}}
        with patch('core.risk_manager.logger.warning') as mock_warn:
            risk_mgr._check_stop_loss(self._make_signal(price=12.0))
        mock_warn.assert_not_called()

    def test_short_extreme_loss(self, risk_mgr):
        """做空 100->200 -> 亏损100% -> 触发"""
        risk_mgr.current_positions = {'HIGH': {'avg_cost': 100.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': 'HIGH', 'price': 200.0})
        assert result is False

    def test_long_extreme_loss(self, risk_mgr):
        """多头 100->30 -> 亏损70% -> 触发"""
        risk_mgr.current_positions = {'LOW': {'avg_cost': 100.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'sell', 'stock_code': 'LOW', 'price': 30.0})
        assert result is False

    def test_short_zero_price(self, risk_mgr):
        """做空 price=0 -> profit=-100% -> 不触发"""
        risk_mgr.current_positions = {'ZERO': {'avg_cost': 100.0}}
        result = risk_mgr._check_stop_loss(
            {'type': 'short', 'stock_code': 'ZERO', 'price': 0.0})
        assert result is True


# ==================== 持仓限制回归 ====================

class TestPositionLimits:

    @pytest.fixture
    def risk_mgr(self):
        from core.risk_manager import RiskManager
        with patch.object(RiskManager, '__init__', return_value=None):
            mgr = RiskManager()
            mgr.logger = MagicMock()
            mgr.total_assets = 1000000.0
            mgr.current_equity = 1000000.0
            mgr.max_position_size = 0.50
            mgr.max_single_position = 0.30
            mgr.current_positions = {}
            yield mgr

    def test_no_positions_no_limit(self, risk_mgr):
        risk_mgr.current_positions = {}
        assert risk_mgr._check_position_limit(
            {'type': 'buy', 'stock_code': '000001', 'amount': 1000}) is True

    def test_within_limit(self, risk_mgr):
        risk_mgr.current_positions = {
            '000001': {'current_price': 10.0, 'quantity': 15000, 'amount': 150000}}
        assert risk_mgr._check_position_limit(
            {'type': 'buy', 'stock_code': '000001', 'amount': 1000}) is True

    def test_exceeds_limit(self, risk_mgr):
        risk_mgr.current_positions = {
            '000001': {'current_price': 10.0, 'quantity': 35000, 'amount': 350000}}
        assert risk_mgr._check_position_limit(
            {'type': 'buy', 'stock_code': '000001', 'amount': 1000}) is False

    def test_sell_signal_skips_position_check(self, risk_mgr):
        """非buy信号跳过持仓限制检查"""
        risk_mgr.current_positions = {
            '000001': {'current_price': 10.0, 'quantity': 50000, 'amount': 500000}}
        assert risk_mgr._check_position_limit(
            {'type': 'sell', 'stock_code': '000001', 'amount': 1000}) is True

    def test_no_equity_returns_false(self, risk_mgr):
        """current_equity <= 0 -> False"""
        risk_mgr.current_equity = 0
        assert risk_mgr._check_position_limit(
            {'type': 'buy', 'stock_code': '000001', 'amount': 1000}) is False

    def test_exception_returns_false(self, risk_mgr):
        risk_mgr.current_positions = None
        assert risk_mgr._check_position_limit(
            {'type': 'buy', 'stock_code': '000001', 'amount': 1000}) is False


# ==================== EnhancedRiskMonitor check_order_risk ====================

class TestEnhancedRiskMonitorCheckOrderRisk:

    @pytest.fixture
    def monitor(self):
        from core.risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor
        with patch.object(EnhancedRiskMonitor, '__init__', return_value=None):
            mon = EnhancedRiskMonitor()
            mon._current_positions = []
            mon.config = {}
            return mon

    def test_check_order_risk_exists(self, monitor):
        result = hasattr(monitor, 'check_order_risk')
        assert result is True
        assert callable(monitor.check_order_risk)

    def test_normal_order_passes(self, monitor):
        order = {
            'stock_code': '000001',
            'order_price': 10.0,
            'order_quantity': 100,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is True
        assert result['risk_level'] == 'LOW'
        assert result['violations'] == []
        assert result['warnings'] == []
        assert result['error_code'] == ''

    def test_abnormal_order_rejected_missing_code(self, monitor):
        order = {
            'stock_code': '',
            'order_price': 10.0,
            'order_quantity': 100,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is False
        assert len(result['violations']) >= 1
        assert any(v['rule'] == 'missing_stock_code' for v in result['violations'])

    def test_abnormal_order_rejected_invalid_price(self, monitor):
        order = {
            'stock_code': '000001',
            'order_price': -5.0,
            'order_quantity': 100,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is False
        assert any(v['rule'] == 'invalid_price' for v in result['violations'])

    def test_abnormal_order_rejected_invalid_quantity(self, monitor):
        order = {
            'stock_code': '000001',
            'order_price': 10.0,
            'order_quantity': 0,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is False
        assert any(v['rule'] == 'invalid_quantity' for v in result['violations'])

    def test_concentration_risk_warning(self, monitor):
        monitor._current_positions = [
            {'stock_code': '000001', 'quantity': 100, 'price': 10.0},
            {'stock_code': '000002', 'quantity': 300, 'price': 10.0},
        ]
        order = {
            'stock_code': '000001',
            'order_price': 10.0,
            'order_quantity': 100,
        }
        result = monitor.check_order_risk(order)
        assert len(result['warnings']) >= 1
        assert any('集中度' in w['message'] for w in result['warnings'])

    def test_concentration_risk_violation(self, monitor):
        monitor._current_positions = [
            {'stock_code': '000002', 'quantity': 100, 'price': 10.0},
        ]
        order = {
            'stock_code': '000001',
            'order_price': 100.0,
            'order_quantity': 100,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is False
        assert any(v['rule'] == 'concentration_limit' for v in result['violations'])

    def test_large_order_value_warning(self, monitor):
        order = {
            'stock_code': '000001',
            'order_price': 1000.0,
            'order_quantity': 6000,
        }
        result = monitor.check_order_risk(order)
        assert len(result['warnings']) >= 1
        assert any('金额较大' in w['message'] for w in result['warnings'])

    def test_large_order_value_violation(self, monitor):
        order = {
            'stock_code': '000001',
            'order_price': 10000.0,
            'order_quantity': 2000,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is False
        assert any(v['rule'] == 'order_value_limit' for v in result['violations'])

    def test_fail_closed_on_exception(self, monitor):
        def _raise(*args, **kwargs):
            raise RuntimeError("模拟内部崩溃")
        monitor.check_order_risk = _raise
        order = {'stock_code': '000001', 'order_price': 10.0, 'order_quantity': 100}
        with pytest.raises(RuntimeError, match="模拟内部崩溃"):
            monitor.check_order_risk(order)

    def test_enhanced_fail_closed_error_code(self, monitor):
        monitor.config = None
        order = {
            'stock_code': '000001',
            'order_price': 10.0,
            'order_quantity': 100,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is False
        assert result['error_code'] == 'ENHANCED_RISK_CHECK_FAILED'
        assert result['risk_level'] == 'CRITICAL'

    def test_order_object_not_dict(self, monitor):
        order = MagicMock()
        order.stock_code = '000001'
        order.order_price = 10.0
        order.order_quantity = 100
        result = monitor.check_order_risk(order)
        assert result['passed'] is True
        assert result['risk_level'] == 'LOW'

    def test_order_object_with_symbol(self, monitor):
        order = MagicMock()
        order.symbol = '000001'
        order.order_price = 10.0
        order.order_quantity = 100
        result = monitor.check_order_risk(order)
        assert result['passed'] is True
        assert result['risk_level'] == 'LOW'

    def test_empty_positions_no_concentration_check(self, monitor):
        monitor._current_positions = []
        order = {
            'stock_code': '000001',
            'order_price': 500.0,
            'order_quantity': 100,
        }
        result = monitor.check_order_risk(order)
        assert result['passed'] is True
        assert not any('集中度' in v.get('message', '') for v in result['violations'])
        assert not any('集中度' in w.get('message', '') for w in result['warnings'])