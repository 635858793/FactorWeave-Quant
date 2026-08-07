#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R255 回归测试: 订单基础设施域 P2 修复

覆盖 (R255 分析实证, 源码行号):
- 项1: order_repository.py 无单例, order_service.py:61 / order_monitor.py:106
      / order_analyzer.py:160 各持独立 OrderRepository 实例, 每实例独立 OrderCache
      (ttl_seconds=300) 且写穿仅本实例 (order_repository.py:227/:315/:483/:694),
      读先查缓存 (order_repository.py:449-453) → 跨实例存在 300s TTL 陈旧读。
      修复: 模块级懒单例 get_order_repository, 三个消费者共用同一实例 (缓存一致性)。
- 项2: order_repository.py:578-585 get_active_orders 仅查 PENDING, 与
      order_models.py:104-108 Order.is_active (PENDING+SUBMITTED+PARTIALLY_FILLED)
      定义不一致 → GUI 订单表 8 值状态映射中 7 个状态永不出现。
      修复: OrderQuery 增加 order_statuses 多状态字段, get_active_orders 查询三状态;
      单值 order_status 查询保持向后兼容。

测试策略 (同 R254):
- autouse fixture 重置模块级单例, 测试结束恢复原值 (防跨文件污染, R254 sys.modules 教训)
- AssetSeparatedDatabaseManager.get_instance 以 mock 隔离 (同 test_repository.py:816 模式)
- OrderService 重型依赖 (Validator/Executor/Monitor/Analyzer) 构造以 patch 隔离
- 本文件不注入任何 sys.modules mock 条目, 无文件级污染需恢复
- 跨文件模块批次一致性由 TestConsumersShareSingleton 测试方法内运行时统一批次保证
  (R255 教训: 早期版本曾做收集阶段全局 pop 自愈, 反致 r254/r255_trading_mode
  收集时固化的模块引用被破坏 → 运行时延迟 import 批次分裂, 已移除)
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import sys  # noqa: E402
import core.trading.order_repository as order_repository_mod  # noqa: E402
from core.trading.order_models import OrderStatus  # noqa: E402
from core.trading.order_repository import OrderRepository, OrderQuery, get_order_repository  # noqa: E402


# ---------------------------------------------------------------------------
# 公共 fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """每个测试前后重置模块级单例, 结束后恢复原值 (防跨测试/跨文件污染)"""
    original = order_repository_mod._order_repository_instance
    order_repository_mod._order_repository_instance = None
    yield
    order_repository_mod._order_repository_instance = original


@pytest.fixture(autouse=True)
def _mock_asset_db_manager():
    """隔离重型 DB 依赖 (同 test_repository.py:816 模式)"""
    with patch('core.trading.order_repository.AssetSeparatedDatabaseManager.get_instance',
               return_value=MagicMock()):
        yield


def _make_order_row(status: OrderStatus, order_id: str, stock_code: str) -> dict:
    """构造订单行 dict (Order.from_dict 所需完整字段)"""
    now = datetime.now().isoformat()
    return {
        'order_id': order_id,
        'strategy_id': 'test_strategy',
        'asset_type': 'stock_a',
        'stock_code': stock_code,
        'order_type': 'buy',
        'order_category': 'limit',
        'order_price': 10.0,
        'order_quantity': 100,
        'order_status': status.value,
        'create_time': now,
        'update_time': now,
        'execute_time': None,
        'filled_quantity': 0,
        'filled_price': 0.0,
        'commission': 0.0,
        'error_message': None,
        'stop_price': None,
        'user_id': 'system',
        'account_id': 'default',
        'tags': [],
        'metadata': '{}',
    }


def _make_repo(db_service=None):
    """构造绕过 __init__ 的 OrderRepository 测试实例 (同 test_repository.py:817 模式)"""
    repo = OrderRepository.__new__(OrderRepository)
    repo.logger = MagicMock()
    repo.event_bus = MagicMock()
    repo.service_container = MagicMock()
    repo.service_container.resolve.return_value = db_service or MagicMock()
    repo.asset_db_manager = MagicMock()
    repo.cache = MagicMock()
    return repo


_ACTIVE_STATUSES = [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]


class TestGetOrderRepositorySingleton:
    """项1: get_order_repository 模块级懒单例"""

    def test_returns_same_instance_on_multiple_calls(self):
        """调用两次返回同一实例, 首次调用参数被承载"""
        sc1, eb1 = MagicMock(), MagicMock()
        sc2, eb2 = MagicMock(), MagicMock()

        r1 = get_order_repository(sc1, eb1)
        r2 = get_order_repository(sc2, eb2)

        assert r1 is r2
        assert isinstance(r1, OrderRepository)
        assert r1.service_container is sc1

    def test_lazy_singleton_without_args_returns_existing(self):
        """已实例化后无参调用返回既有实例"""
        sc, eb = MagicMock(), MagicMock()

        r1 = get_order_repository(sc, eb)
        r2 = get_order_repository()

        assert r1 is r2

    def test_singleton_state_cleared_between_tests(self):
        """验证 autouse fixture 正确重置单例 (防跨测试污染)"""
        assert order_repository_mod._order_repository_instance is None


class TestConsumersShareSingleton:
    """项1: 三个消费者 _initialize 后共用同一 get_order_repository 实例"""

    @staticmethod
    def _load_domain_batch():
        """运行时统一批次: 先确保 order_repository 在 sys.modules, 再重载消费者模块,
        使其固化同一批次的 get_order_repository 引用 (消除跨文件模块批次分裂)。
        注: 前序 R 系列文件收集时可能 pop/覆盖 order_repository, 运行阶段需以
        sys.modules 当前批次为准, 而非模块级 import 的批次。
        """
        import importlib
        orm = importlib.import_module('core.trading.order_repository')
        for name in ('core.trading.order_service',
                     'core.trading.order_monitor',
                     'core.trading.order_analyzer'):
            sys.modules.pop(name, None)
        omm = importlib.import_module('core.trading.order_monitor')
        oam = importlib.import_module('core.trading.order_analyzer')
        osm = importlib.import_module('core.trading.order_service')
        return orm, omm, oam, osm

    def test_order_monitor_uses_singleton(self):
        """order_monitor.py:106 改造后共用单例"""
        orm, omm, _, _ = self._load_domain_batch()
        sc, eb = MagicMock(), MagicMock()

        monitor = omm.OrderMonitor(sc, eb)

        assert isinstance(monitor.repository, orm.OrderRepository)
        assert monitor.repository is orm.get_order_repository()

    def test_order_analyzer_uses_singleton(self):
        """order_analyzer.py:160 改造后共用单例"""
        orm, _, oam, _ = self._load_domain_batch()
        sc, eb = MagicMock(), MagicMock()

        analyzer = oam.OrderAnalyzer(sc, eb)

        assert isinstance(analyzer.repository, orm.OrderRepository)
        assert analyzer.repository is orm.get_order_repository()

    def test_order_service_uses_singleton(self):
        """order_service.py:61 改造后共用单例 (重型依赖构造以 patch 隔离)"""
        orm, _, _, osm = self._load_domain_batch()
        sc, eb = MagicMock(), MagicMock()
        with patch('core.trading.order_service.OrderValidator'), \
             patch('core.trading.order_service.OrderExecutor'), \
             patch('core.trading.order_service.OrderMonitor'), \
             patch('core.trading.order_service.OrderAnalyzer'):
            service = osm.OrderService(sc, eb)

        assert isinstance(service.repository, orm.OrderRepository)
        assert service.repository is orm.get_order_repository()

    def test_three_consumers_share_same_instance(self):
        """三个消费者经 get_order_repository 得到同一实例 (缓存一致性)"""
        orm, omm, oam, osm = self._load_domain_batch()
        sc, eb = MagicMock(), MagicMock()

        monitor = omm.OrderMonitor(sc, eb)
        analyzer = oam.OrderAnalyzer(sc, eb)
        with patch('core.trading.order_service.OrderValidator'), \
             patch('core.trading.order_service.OrderExecutor'), \
             patch('core.trading.order_service.OrderMonitor'), \
             patch('core.trading.order_service.OrderAnalyzer'):
            service = osm.OrderService(sc, eb)

        assert monitor.repository is analyzer.repository
        assert service.repository is monitor.repository
        assert service.repository is orm.get_order_repository()


class TestGetActiveOrders:
    """项2: get_active_orders 三状态活跃语义"""

    def test_returns_three_active_statuses(self):
        """返回 PENDING + SUBMITTED + PARTIALLY_FILLED 三种状态订单

        注: query_orders 在未指定 asset_type 时遍历所有资产池,
        每池返回全部活跃状态行 → 结果状态集合等于三活跃状态。
        """
        rows = [
            _make_order_row(s, f"ORD_{i}", f"00000{i}")
            for i, s in enumerate(_ACTIVE_STATUSES)
        ]
        db_service = MagicMock()
        db_service.fetch_all.return_value = rows
        repo = _make_repo(db_service)

        orders = repo.get_active_orders(account_id='test_account')

        assert len(orders) >= 3
        assert {o.order_status for o in orders} == set(_ACTIVE_STATUSES)

    def test_where_clause_includes_exactly_active_statuses(self):
        """SQL WHERE 使用 IN 语法且仅含三个活跃状态值 (终态不在查询参数中)"""
        db_service = MagicMock()
        db_service.fetch_all.return_value = []
        repo = _make_repo(db_service)

        repo.get_active_orders()

        sql = db_service.fetch_all.call_args[0][0]
        params = db_service.fetch_all.call_args[0][1]
        assert 'order_status IN (?, ?, ?)' in sql
        status_values = [
            p for p in params
            if isinstance(p, str) and p in (s.value for s in OrderStatus)
        ]
        assert set(status_values) == {s.value for s in _ACTIVE_STATUSES}
        for terminal in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED,
                         OrderStatus.EXPIRED, OrderStatus.FAILED):
            assert terminal.value not in status_values


class TestOrderQueryBackwardCompat:
    """项2: OrderQuery 向后兼容性"""

    def test_order_status_single_value_still_works(self):
        """单值 order_status 字段行为不变"""
        q = OrderQuery(order_status=OrderStatus.PENDING)
        assert q.order_status == OrderStatus.PENDING
        assert q.order_statuses is None

    def test_order_statuses_field_supported(self):
        """多状态 order_statuses 字段可用"""
        q = OrderQuery(order_statuses=[OrderStatus.PENDING, OrderStatus.SUBMITTED])
        assert q.order_statuses == [OrderStatus.PENDING, OrderStatus.SUBMITTED]
        assert q.order_status is None

    def test_single_status_query_sql_unchanged(self):
        """单值 order_status 查询 SQL 仍为等值条件, 无 IN 语法回归"""
        db_service = MagicMock()
        db_service.fetch_all.return_value = []
        repo = _make_repo(db_service)

        repo.query_orders(OrderQuery(order_status=OrderStatus.PENDING))

        sql = db_service.fetch_all.call_args[0][0]
        params = db_service.fetch_all.call_args[0][1]
        assert 'order_status = ?' in sql
        assert 'order_status IN' not in sql
        assert OrderStatus.PENDING.value in params


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
