"""R268 风控功能激活审计修复验证 (2026-08-09)

覆盖 (4 路子智能体交叉验证 + 二次源码核验, 全部含行号引用):
- F1: EnhancedRiskMonitor 未注册容器 → 增强风控(集中度/单笔金额)从未执行
      (service_bootstrap.py 原无注册, order_executor.py:785 try_resolve 恒 None)
      → 修复: service_bootstrap 注册 + order_executor 打通持仓数据源
- F4: 资金检查 fail-open (order_executor.py 原 `and account.available_cash` 使 0/None 跳过)
      + get_positions_by_account 不存在 (account_manager.py:604 实际为 get_account_positions)
      → AttributeError 误拒所有设置了 position_limit 的账户
- F2: unified_performance_widget.py 原 `risk_manager = None` → initialized AttributeError
- F3: risk_control.py 原 get_risk_metrics 桥接不存在的 calculate_risk_metrics → 恒全 0
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.risk, pytest.mark.r268]


def _make_order(**kwargs):
    """构造订单对象 (SimpleNamespace, 含 _pre_trade_risk_check 全部访问字段)"""
    base = {
        'order_id': 'R268-TEST',
        'stock_code': '000001',
        'symbol': '000001',
        'order_price': 10.0,
        'order_quantity': 100,
        'account_id': 'acc_001',
        'create_time': None,
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.fixture
def executor():
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
        # 默认: 增强风控检查通过 + 资金充足 + 无 position_limit
        mock_monitor = MagicMock()
        mock_monitor.check_order_risk = MagicMock(
            return_value={'passed': True, 'warnings': [], 'violations': []})
        mock_acct_mgr = MagicMock()
        mock_account = MagicMock()
        mock_account.available_cash = 1000000.0
        mock_account.position_limit = None
        mock_acct_mgr.get_account = MagicMock(return_value=mock_account)
        mock_acct_mgr.get_account_positions = MagicMock(return_value=[])

        def try_resolve(cls):
            return mock_monitor if 'EnhancedRiskMonitor' in str(cls) else mock_acct_mgr

        def resolve(cls):
            return mock_acct_mgr if 'AccountManager' in str(cls) else mock_monitor

        inst.service_container.try_resolve = MagicMock(side_effect=try_resolve)
        inst.service_container.resolve = MagicMock(side_effect=resolve)
        inst._get_avg_entry_price = MagicMock(return_value=None)  # 跳过止损检查分支
        inst._mock_monitor = mock_monitor
        inst._mock_acct_mgr = mock_acct_mgr
        inst._mock_account = mock_account
        return inst


# ==================== F1: 增强风控激活 ====================

class TestF1_EnhancedRiskMonitorActivation:

    def test_f1_monitor_registered_in_bootstrap(self):
        """service_bootstrap 已含 EnhancedRiskMonitor 注册代码 (原无 → try_resolve 恒 None)"""
        src = (PROJECT_ROOT / 'core' / 'services' / 'service_bootstrap.py').read_text(encoding='utf-8')
        assert 'EnhancedRiskMonitor' in src
        assert 'register_factory' in src
        assert 'R268-F1' in src

    def test_f1_monitor_constructible(self, tmp_path):
        """注册工厂 lambda 可真实构造 EnhancedRiskMonitor (db 走 tmp_path 不写项目目录)"""
        from core.risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor
        m = EnhancedRiskMonitor(config={'db_path': str(tmp_path / 'erm_r268.sqlite')})
        assert m._current_positions == []

    def test_f1_sync_positions_before_check(self, executor):
        """持仓数据源打通: 下单前同步 AccountManager 实时持仓 (原唯一填充点在死代码 risk_manager.py:508)"""
        mock_acct_mgr = executor._mock_acct_mgr
        mock_acct_mgr.get_account_positions = MagicMock(return_value=[
            SimpleNamespace(stock_code='000001', quantity=100,
                            current_price=10.0, open_price=9.0),
        ])
        result = executor._pre_trade_risk_check(_make_order())
        assert result['passed'] is True
        executor._mock_monitor.update_portfolio_positions.assert_called_once()
        args = executor._mock_monitor.update_portfolio_positions.call_args[0][0]
        assert args == [{'stock_code': '000001', 'quantity': 100, 'price': 10.0}]

    def test_f1_concentration_limit_rejects(self, executor):
        """集中度限制激活: 单一持仓 > max_concentration → 拒绝订单"""
        mock_monitor = executor._mock_monitor
        mock_monitor.check_order_risk = MagicMock(
            return_value={'passed': False, 'reason': '单一持仓集中度过高: 99.0%'})
        result = executor._pre_trade_risk_check(_make_order(order_quantity=10000))
        assert result['passed'] is False
        assert '集中度' in result['reason']

    def test_f1_concentration_real_check_order_risk(self, tmp_path):
        """真实 check_order_risk: 已有 100 股 10 元持仓 + 新买 1 万股 10 元 → 集中度 0.99 → 拒绝"""
        from core.risk_monitoring.enhanced_risk_monitor import EnhancedRiskMonitor
        m = EnhancedRiskMonitor(config={'db_path': str(tmp_path / 'erm_r268b.sqlite')})
        m.update_portfolio_positions([{'stock_code': '000001', 'quantity': 100, 'price': 10.0}])
        order = SimpleNamespace(stock_code='000001', order_price=10.0, order_quantity=10000)
        result = m.check_order_risk(order)
        assert result['passed'] is False
        assert any(v['rule'] == 'concentration_limit' for v in result['violations'])


# ==================== F4: fail-open 修复 ====================

class TestF4_FailOpenFixes:

    def test_f4_zero_cash_rejects(self, executor):
        """可用资金 0 → 拒绝 (原 `and account.available_cash` 使 0 资金跳过校验可下单)"""
        executor._mock_account.available_cash = 0.0
        result = executor._pre_trade_risk_check(_make_order())
        assert result['passed'] is False
        assert '资金不足' in result['reason']

    def test_f4_none_cash_warns_not_rejects(self, executor):
        """可用资金未知(None) → 告警不拒绝 (无法校验时降级提示)"""
        executor._mock_account.available_cash = None
        result = executor._pre_trade_risk_check(_make_order())
        assert result['passed'] is True
        assert any('可用资金未知' in w for w in result['warnings'])

    def test_f4_position_limit_no_crash(self, executor):
        """position_limit 分支不再崩溃: 原 get_positions_by_account 不存在 → AttributeError
        被捕获 → 误拒 (RISK_CHECK_FAILED)。现用真实方法名 get_account_positions → 警告放行。"""
        executor._mock_account.position_limit = 1
        executor._mock_acct_mgr.get_account_positions = MagicMock(return_value=[object()])
        result = executor._pre_trade_risk_check(_make_order())
        assert result['passed'] is True
        assert any('持仓数量接近限制' in w for w in result['warnings'])


# ==================== F2 / F3: 死代码修复 ====================

class TestF2F3_DeadCodeRemoved:

    def test_f2_risk_manager_none_removed(self):
        """F2: unified_performance_widget 改用真实 RiskManager 实例 (原 `risk_manager = None` 必崩)"""
        src = (PROJECT_ROOT / 'gui' / 'widgets' / 'performance' / 'unified_performance_widget.py').read_text(encoding='utf-8')
        assert 'risk_manager = RiskManager()' in src
        assert 'if risk_manager.initialize():' in src

    def test_f3_dead_bridge_removed(self):
        """F3: risk_control 不再引用不存在的 calculate_risk_metrics; 监控器不再调用 get_risk_metrics"""
        rc = (PROJECT_ROOT / 'core' / 'risk_control.py').read_text(encoding='utf-8')
        assert 'calculate_risk_metrics' not in rc
        assert 'def get_risk_metrics(' not in rc  # 注意: get_risk_metrics_history 属正常方法
        erm = (PROJECT_ROOT / 'core' / 'risk_monitoring' / 'enhanced_risk_monitor.py').read_text(encoding='utf-8')
        assert 'get_risk_metrics()' not in erm
