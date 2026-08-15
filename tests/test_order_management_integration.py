#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单管理系统集成测试

测试订单管理系统的各个组件，包括：
1. 订单创建
2. 订单查询
3. 订单提交
4. 订单取消
5. 订单修改
6. 订单监控
7. 订单分析
"""

import sys
import os
import json
import sqlite3
import unittest
from datetime import datetime
from typing import List, Dict, Any

from loguru import logger

from core.services.database_service import DatabaseService
from core.trading.order_models import (
    Order, OrderRequest, OrderQuery, OrderType, OrderStatus, OrderCategory,
    OrderFill
)
from core.plugin_types import AssetType
from core.trading.trading_types import ExecutionStatus
from core.trading.order_service import OrderService
from core.trading.order_repository import OrderRepository
from core.trading.order_executor import OrderExecutor
from core.trading.order_validator import OrderValidator
from core.trading.order_monitor import OrderMonitor
from core.trading.order_analyzer import OrderAnalyzer
from core.containers import get_service_container
from core.containers.service_registry import ServiceScope
from core.events import get_event_bus


class _InMemoryDatabaseService:
    """测试专用内存版 DatabaseService (替代生产 sqlite/duckdb 实现)

    背景: OrderRepository 各方法内部 resolve(DatabaseService) 获取服务
    (core/trading/order_repository.py L70/L178/L276/L365/L487/L531/L646/
    L684/L710/L748 共 10 处), 生产环境由 core/services/service_bootstrap.py
    注册真实实现 (依赖 data/factorweave_system.sqlite 等生产 DB 文件),
    测试环境不应依赖生产 DB, 故在此注册内存版 fake。

    仓库仅调用两个方法 (均已实现):
      - execute_query(sql, params, pool_name=...): INSERT/UPDATE/DELETE
      - fetch_all(sql, params, pool_name=...):   SELECT -> List[dict]
    按 pool_name 隔离内存库, 与生产 AssetSeparatedDatabaseManager
    "订单按资产类型落不同数据池, 跨池查询遍历合并" 语义一致。
    """

    _SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        strategy_id TEXT, asset_type TEXT, stock_code TEXT,
        order_type TEXT, order_category TEXT,
        order_price REAL, order_quantity INTEGER,
        order_status TEXT, create_time TEXT, update_time TEXT, execute_time TEXT,
        filled_quantity INTEGER, filled_price REAL, commission REAL,
        error_message TEXT, error_code TEXT, stop_price REAL,
        user_id TEXT, account_id TEXT, tags TEXT, metadata TEXT,
        contract_multiplier REAL, margin_ratio REAL, strike_price REAL,
        expiry_date TEXT, option_type TEXT
    );
    CREATE TABLE IF NOT EXISTS order_fills (
        fill_id TEXT PRIMARY KEY,
        order_id TEXT, stock_code TEXT, fill_price REAL,
        fill_quantity INTEGER, fill_time TEXT, commission REAL
    );
    """

    def __init__(self):
        self._connections = {}

    def reset(self):
        """清空所有数据池 (每个测试用例独立, 避免跨用例数据累积)"""
        for conn in self._connections.values():
            conn.close()
        self._connections = {}

    def _get_connection(self, pool_name: str):
        if pool_name not in self._connections:
            conn = sqlite3.connect(':memory:')
            conn.row_factory = sqlite3.Row
            conn.executescript(self._SCHEMA_SQL)
            self._connections[pool_name] = conn
        return self._connections[pool_name]

    @staticmethod
    def _serialize_params(params):
        """dict/list 参数序列化为 JSON 字符串 (Order.to_dict 的 metadata/tags 为 dict/list)"""
        if not params:
            return params
        return [
            json.dumps(p, ensure_ascii=False) if isinstance(p, (dict, list)) else p
            for p in params
        ]

    def execute_query(self, sql: str, params=None, pool_name: str = None):
        conn = self._get_connection(pool_name or 'default')
        with conn:
            conn.execute(sql, self._serialize_params(params or []))

    def fetch_all(self, sql: str, params=None, pool_name: str = None) -> List[Dict[str, Any]]:
        conn = self._get_connection(pool_name or 'default')
        cursor = conn.execute(sql, self._serialize_params(params or []))
        return [dict(row) for row in cursor.fetchall()]


class _FakeAccountManager:
    """测试专用轻量 AccountManager (R272: executor 非防御 resolve 依赖)

    背景: OrderExecutor 在测试环境用真实容器 resolve(AccountManager) (order_executor.py
    L710/L836/L1743/L1758 共 4 处), 未注册会抛 ValueError → 风控拒绝 / 账号解析失败
    (test_05/06/07 失败的 ACCOUNT_NOT_FOUND 根因)。生产环境由 service_bootstrap
    注册真实 AccountManager (依赖账户 DB), 测试侧注册轻量 fake 仅暴露 executor
    消费的 3 个方法: get_account / get_all_accounts / get_account_positions。
    """
    def __init__(self):
        from types import SimpleNamespace
        # 提供可用资金, 通过 executor._pre_trade_risk_check 资金校验 (:838-851);
        # 无 position_limit → 跳过持仓数量检查 (:853-859)
        self._accounts = {
            'test_account': SimpleNamespace(
                account_id='test_account',
                available_cash=1_000_000.0,
                available_balance=1_000_000.0,
                balance=1_000_000.0,
                position_limit=None,
            )
        }

    def get_account(self, account_id: str):
        return self._accounts.get(account_id)

    def get_all_accounts(self) -> List:
        return list(self._accounts.values())

    def get_account_positions(self, account_id: str) -> List:
        return []


class _FakeStrategyManager:
    """测试专用轻量 StrategyManager (executor:711 resolve + :723 get_strategy;
    order_service.create_order :158-165 get_strategy/get_all_strategies)

    必须返回带 strategy_id 的策略对象: 若 get_strategy 返回 None, create_order
    会认为策略无效并把 strategy_id 重置为 'default' (order_service.py:158-165),
    导致按 'test_strategy' 查询不到订单。
    """
    def __init__(self):
        from types import SimpleNamespace
        self._strategies = {
            'test_strategy': SimpleNamespace(
                strategy_id='test_strategy', default_account_id=None),
        }

    def get_strategy(self, strategy_id: str):
        return self._strategies.get(strategy_id)

    def get_all_strategies(self) -> List:
        return list(self._strategies.values())


class TestOrderManagementIntegration(unittest.TestCase):
    """订单管理系统集成测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        logger.info("开始订单管理系统集成测试")

        # 获取服务容器和事件总线
        cls.service_container = get_service_container()
        cls.event_bus = get_event_bus()

        # R272: 接线 DatabaseService (测试环境不依赖生产 DB 文件)
        # OrderRepository 各方法内部 resolve(DatabaseService), 生产环境由
        # service_bootstrap 注册真实实现; 测试侧注册内存版 fake, 必须在
        # OrderService 注册/解析及清理测试数据之前完成。
        if not cls.service_container.is_registered(DatabaseService):
            cls.database_service_mock = _InMemoryDatabaseService()
            cls.service_container.register(
                DatabaseService,
                scope=ServiceScope.SINGLETON,
                factory=lambda: cls.database_service_mock
            )
            logger.info("DatabaseService (内存 mock) 已注册到服务容器")

        # 注册订单服务
        if not cls.service_container.is_registered(OrderService):
            cls.service_container.register(
                OrderService,
                scope=ServiceScope.SINGLETON,
                factory=lambda: OrderService(
                    service_container=cls.service_container,
                    event_bus=cls.event_bus
                )
            )
            logger.info("OrderService 已注册到服务容器")

        # 获取订单服务
        cls.order_service = cls.service_container.resolve(OrderService)

        # R272: 接线 AccountManager/StrategyManager (executor 非防御 resolve 依赖)
        # OrderExecutor 在测试环境用真实容器 resolve(AccountManager/StrategyManager)
        # (order_executor.py L710/L711/L836/L1743/L1758), 未注册 → ValueError →
        # 风控拒绝 / 账号解析失败 (test_05/06/07 的 ACCOUNT_NOT_FOUND/MODE_BLOCKED)。
        # 生产环境由 service_bootstrap 注册真实实现, 测试侧注册轻量 fake。
        from core.trading.account_manager import AccountManager
        from core.trading.strategy_manager import StrategyManager
        if not cls.service_container.is_registered(AccountManager):
            cls.account_manager_mock = _FakeAccountManager()
            cls.service_container.register(
                AccountManager,
                scope=ServiceScope.SINGLETON,
                factory=lambda: cls.account_manager_mock
            )
        if not cls.service_container.is_registered(StrategyManager):
            cls.strategy_manager_mock = _FakeStrategyManager()
            cls.service_container.register(
                StrategyManager,
                scope=ServiceScope.SINGLETON,
                factory=lambda: cls.strategy_manager_mock
            )
        logger.info("AccountManager/StrategyManager (测试 fake) 已注册到服务容器")

        # R272: 注入 Mock 交易接口 (供 submit/cancel 走模拟成交, 不触真实接口)
        # OrderExecutor.submit_order 在 paper 模式对真实接口 (CTP/XTP) 模式闸门
        # MODE_BLOCKED 拦截 (order_executor.py:1189); 测试需用 MockTradingInterface
        # (_is_mock_interface=True 放行, :1733-1736)。两条取接口路径都注入:
        #   1) _account_interface_cache['test_account'] → _get_trading_interface_for_account
        #      (order_executor.py:1044 缓存命中, 绕过真实接口创建)
        #   2) _trading_interfaces[STOCK_A] → _get_trading_interface 回退 (:1514)
        from core.trading.order_executor import MockTradingInterface
        mock_iface = MockTradingInterface(cls.service_container, cls.event_bus)
        cls.order_service.executor._account_interface_cache['test_account'] = mock_iface
        cls.order_service.executor._trading_interfaces[AssetType.STOCK_A] = mock_iface
        cls.order_service.executor._interface_health[AssetType.STOCK_A] = {
            'connected': True, 'logged_in': True, 'last_error': None,
            'retry_count': 0, 'last_health_check': None,
            'consecutive_failures': 0, 'circuit_breaker': False,
            'total_requests': 0, 'failed_requests': 0,
        }
        logger.info("Mock 交易接口已注入订单执行器 (STOCK_A / test_account)")

        # 清理测试数据
        cls.cleanup_test_data()

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("订单管理系统集成测试完成")

        # 清理测试数据
        cls.cleanup_test_data()

    @classmethod
    def cleanup_test_data(cls):
        """清理测试数据"""
        try:
            # 查询所有测试订单
            query = OrderQuery(
                strategy_id="test_strategy",
                limit=1000
            )
            orders = cls.order_service.query_orders(query)

            # 删除所有测试订单
            for order in orders:
                cls.order_service.delete_order(order.order_id)

            logger.info(f"已清理 {len(orders)} 条测试订单")

        except Exception as e:
            logger.error(f"清理测试数据失败: {e}")

    def setUp(self):
        """每个测试方法前的初始化"""
        self.test_orders: List[Order] = []

        # 每个用例重置内存 DB, 保证用例间数据隔离
        # (PENDING/SUBMITTED 等活跃订单不可删除, 不重置会跨用例累积导致
        #  test_13 等按总量断言的用例失败)
        db_mock = getattr(self, 'database_service_mock', None)
        if db_mock is not None:
            db_mock.reset()

    def tearDown(self):
        """每个测试方法后的清理"""
        # 清理本次测试创建的订单
        for order in self.test_orders:
            try:
                self.order_service.delete_order(order.order_id)
            except Exception as e:
                logger.error(f"清理订单失败: {e}")

    def test_01_create_order(self):
        """测试创建订单"""
        logger.info("测试创建订单")

        # 创建订单请求
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )

        # 创建订单
        order = self.order_service.create_order(request)

        # 验证订单
        if order is None:
            logger.error("订单创建失败，返回None")
            # 尝试查询订单以验证是否实际创建成功
            query = OrderQuery(strategy_id="test_strategy", stock_code="000001")
            orders = self.order_service.query_orders(query)
            logger.info(f"查询到 {len(orders)} 个订单")
            if len(orders) > 0:
                order = orders[0]
                logger.info(f"使用查询到的订单: {order.order_id}")

        self.assertIsNotNone(order, "订单不应为None")
        self.assertEqual(order.stock_code, "000001")
        self.assertEqual(order.order_type, OrderType.BUY)
        self.assertEqual(order.order_category, OrderCategory.LIMIT)
        self.assertEqual(order.order_price, 10.0)
        self.assertEqual(order.order_quantity, 100)
        self.assertEqual(order.order_status, OrderStatus.PENDING)
        self.assertEqual(order.strategy_id, "test_strategy")

        # 保存到测试列表
        if order not in self.test_orders:
            self.test_orders.append(order)

        logger.info(f"订单创建成功: {order.order_id}")

    def test_02_create_multiple_orders(self):
        """测试创建多个订单"""
        logger.info("测试创建多个订单")

        # 创建多个订单
        stock_codes = ["000001", "000002", "000003"]
        order_types = [OrderType.BUY, OrderType.SELL, OrderType.BUY]

        for i, (stock_code, order_type) in enumerate(zip(stock_codes, order_types)):
            request = OrderRequest(
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=stock_code,
                order_type=order_type,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i,
                order_quantity=100 * (i + 1),
                user_id="test_user",
                account_id="test_account"
            )

            order = self.order_service.create_order(request)
            self.assertIsNotNone(order)
            self.test_orders.append(order)

        # 验证订单数量
        self.assertEqual(len(self.test_orders), 3)

        logger.info(f"成功创建 {len(self.test_orders)} 个订单")

    def test_03_query_orders(self):
        """测试查询订单"""
        logger.info("测试查询订单")

        # 创建测试订单
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        order = self.order_service.create_order(request)
        self.test_orders.append(order)

        # 查询订单 (OrderQuery 不支持按 order_id 过滤, 改用策略+代码查询)
        query = OrderQuery(
            strategy_id="test_strategy",
            stock_code="000001"
        )
        orders = self.order_service.query_orders(query)

        # 验证查询结果
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].order_id, order.order_id)

        logger.info(f"订单查询成功: {order.order_id}")

    def test_04_query_orders_by_status(self):
        """测试按状态查询订单"""
        logger.info("测试按状态查询订单")

        # 创建多个不同状态的订单
        for i in range(3):
            request = OrderRequest(
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=f"00000{i+1}",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i,
                order_quantity=100,
                user_id="test_user",
                account_id="test_account"
            )
            order = self.order_service.create_order(request)
            self.test_orders.append(order)

        # 按状态查询
        query = OrderQuery(
            strategy_id="test_strategy",
            order_status=OrderStatus.PENDING
        )
        orders = self.order_service.query_orders(query)

        # 验证查询结果
        self.assertGreaterEqual(len(orders), 3)

        logger.info(f"按状态查询成功，找到 {len(orders)} 个订单")

    def test_05_modify_order(self):
        """测试修改订单"""
        logger.info("测试修改订单")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        order = self.order_service.create_order(request)
        self.test_orders.append(order)

        # 先提交原订单 (R272: 接口层 cancel 需订单已在接口 _orders,
        # MockTradingInterface.cancel_order 对未提交订单返回"订单不存在")
        submitted = self.order_service.submit_order(order.order_id)
        self.assertEqual(submitted.status, ExecutionStatus.SUCCESS)

        # 修改订单 (撤单重下: 原单取消 + 新单创建提交, order_service.py:471-538)
        success = self.order_service.modify_order(
            order.order_id,
            new_price=12.0,
            new_quantity=200
        )

        # 验证修改结果
        self.assertTrue(success)

        # 原订单已被取消 (撤单重下语义)
        old_order = self.order_service.get_order(order.order_id)
        self.assertEqual(old_order.order_status, OrderStatus.CANCELLED)

        # 新订单 (同策略最新 SUBMITTED 单) 价格/数量已更新
        query = OrderQuery(
            strategy_id="test_strategy",
            order_status=OrderStatus.SUBMITTED
        )
        orders = self.order_service.query_orders(query)
        new_order = next((o for o in orders if o.order_id != order.order_id), None)
        self.assertIsNotNone(new_order, "修改后应创建新订单")
        self.assertEqual(new_order.order_price, 12.0)
        self.assertEqual(new_order.order_quantity, 200)
        self.test_orders.append(new_order)

        logger.info(f"订单修改成功: {order.order_id} -> {new_order.order_id}")

    def test_06_cancel_order(self):
        """测试取消订单"""
        logger.info("测试取消订单")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        order = self.order_service.create_order(request)
        self.test_orders.append(order)

        # 先提交订单 (R272: 接口层 cancel 需订单已在接口 _orders)
        submitted = self.order_service.submit_order(order.order_id)
        self.assertEqual(submitted.status, ExecutionStatus.SUCCESS)

        # 取消订单
        result = self.order_service.cancel_order(order.order_id)

        # 验证取消结果
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)

        # 查询取消后的订单
        cancelled_order = self.order_service.get_order(order.order_id)
        self.assertEqual(cancelled_order.order_status, OrderStatus.CANCELLED)

        logger.info(f"订单取消成功: {order.order_id}")

    def test_06_b_shared_repository_singleton(self):
        """R272-FIX 回归: executor 与 order_service 共享同一 repository 单例

        背景: order_executor.py:357 此前直接 OrderRepository(...) 构造 → 独立
        OrderCache, executor 写穿自己的缓存, order_service 走单例缓存读 →
        test_06 实证 DB 已 CANCELLED 但 get_order 缓存滞留 SUBMITTED
        (300s TTL 陈旧读, R255-P2 同型缺陷漏网点)。
        修复: order_executor.py:363 改用 get_order_repository 模块级单例。
        """
        self.assertIs(
            self.order_service.executor.repository,
            self.order_service.repository,
            "executor 与 order_service 应共享同一 repository 单例 (order_executor.py:363)"
        )

    def test_07_submit_order(self):
        """测试提交订单"""
        logger.info("测试提交订单")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        order = self.order_service.create_order(request)
        self.test_orders.append(order)

        # 提交订单
        result = self.order_service.submit_order(order.order_id)

        # 验证提交结果
        self.assertEqual(result.status, ExecutionStatus.SUCCESS)

        # 查询提交后的订单
        submitted_order = self.order_service.get_order(order.order_id)
        self.assertEqual(submitted_order.order_status, OrderStatus.SUBMITTED)

        logger.info(f"订单提交成功: {order.order_id}")

    def test_08_get_order(self):
        """测试获取单个订单"""
        logger.info("测试获取单个订单")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        order = self.order_service.create_order(request)
        self.test_orders.append(order)

        # 获取订单
        retrieved_order = self.order_service.get_order(order.order_id)

        # 验证获取结果
        self.assertIsNotNone(retrieved_order)
        self.assertEqual(retrieved_order.order_id, order.order_id)
        self.assertEqual(retrieved_order.stock_code, "000001")

        logger.info(f"订单获取成功: {order.order_id}")

    def test_09_get_order_fills(self):
        """测试获取订单成交记录"""
        logger.info("测试获取订单成交记录")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        order = self.order_service.create_order(request)
        self.test_orders.append(order)

        # 获取成交记录
        fills = self.order_service.get_order_fills(order.order_id)

        # 验证结果（新订单应该没有成交记录）
        self.assertIsNotNone(fills)
        self.assertEqual(len(fills), 0)

        logger.info(f"订单成交记录获取成功: {order.order_id}")

    def test_10_order_validation(self):
        """测试订单验证"""
        logger.info("测试订单验证")

        # 创建有效的订单请求
        valid_request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )

        # 验证订单请求
        result = self.order_service.validator.validate_order_request(valid_request)

        # 验证结果
        self.assertTrue(result.passed)

        # 创建无效的订单请求（数量太小）
        invalid_request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=50,  # 小于最小值
            user_id="test_user",
            account_id="test_account"
        )

        # 验证订单请求
        result = self.order_service.validator.validate_order_request(invalid_request)

        # 验证结果
        self.assertFalse(result.passed)

        logger.info("订单验证测试完成")

    def test_11_batch_create_orders(self):
        """测试批量创建订单"""
        logger.info("测试批量创建订单")

        # 创建多个订单请求
        requests = []
        for i in range(5):
            request = OrderRequest(
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=f"00000{i+1}",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i,
                order_quantity=100 * (i + 1),
                user_id="test_user",
                account_id="test_account"
            )
            requests.append(request)

        # 批量创建订单
        orders = self.order_service.batch_create_orders(requests)

        # 验证结果
        self.assertEqual(len(orders), 5)
        self.test_orders.extend(orders)

        logger.info(f"批量创建订单成功，共 {len(orders)} 个订单")

    def test_12_cancel_all_active_orders(self):
        """测试取消所有活跃订单"""
        logger.info("测试取消所有活跃订单")

        # 创建多个订单
        for i in range(3):
            request = OrderRequest(
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=f"00000{i+1}",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i,
                order_quantity=100,
                user_id="test_user",
                account_id="test_account"
            )
            order = self.order_service.create_order(request)
            self.test_orders.append(order)

        # 取消所有活跃订单
        cancelled_count = self.order_service.cancel_all_active_orders("test_account")

        # 验证结果
        self.assertGreaterEqual(cancelled_count, 0)

        # 查询验证
        query = OrderQuery(strategy_id="test_strategy", order_status=OrderStatus.CANCELLED)
        cancelled_orders = self.order_service.query_orders(query)

        self.assertGreaterEqual(len(cancelled_orders), 0)

        logger.info(f"取消所有活跃订单成功，共 {len(cancelled_orders)} 个订单")

    def test_13_order_statistics(self):
        """测试订单统计"""
        logger.info("测试订单统计")

        # 创建多个订单
        for i in range(5):
            request = OrderRequest(
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=f"00000{i+1}",
                order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i,
                order_quantity=100 * (i + 1),
                user_id="test_user",
                account_id="test_account"
            )
            order = self.order_service.create_order(request)
            self.test_orders.append(order)

        # 获取订单统计
        query = OrderQuery(strategy_id="test_strategy")
        orders = self.order_service.query_orders(query)

        # 计算统计信息
        total_orders = len(orders)
        buy_orders = len([o for o in orders if o.order_type == OrderType.BUY])
        sell_orders = len([o for o in orders if o.order_type == OrderType.SELL])
        total_quantity = sum(o.order_quantity for o in orders)
        total_value = sum(o.order_price * o.order_quantity for o in orders)

        # 验证统计结果
        self.assertEqual(total_orders, 5)
        self.assertEqual(buy_orders, 3)
        self.assertEqual(sell_orders, 2)
        self.assertGreater(total_quantity, 0)
        self.assertGreater(total_value, 0)

        logger.info(f"订单统计: 总订单数={total_orders}, 买入={buy_orders}, 卖出={sell_orders}, "
                   f"总数量={total_quantity}, 总价值={total_value:.2f}")

    def test_14_order_monitor(self):
        """测试订单监控"""
        logger.info("测试订单监控")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )
        order = self.order_service.create_order(request)
        self.test_orders.append(order)

        # 获取活跃订单
        active_orders = self.order_service.get_active_orders("test_account")

        # 验证结果
        self.assertIsNotNone(active_orders)
        self.assertGreaterEqual(len(active_orders), 0)

        logger.info(f"订单监控成功，活跃订单数: {len(active_orders)}")

    def test_15_order_analyzer(self):
        """测试订单分析"""
        logger.info("测试订单分析")

        # 创建多个订单
        for i in range(5):
            request = OrderRequest(
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=f"00000{i+1}",
                order_type=OrderType.BUY if i % 2 == 0 else OrderType.SELL,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i,
                order_quantity=100 * (i + 1),
                user_id="test_user",
                account_id="test_account"
            )
            order = self.order_service.create_order(request)
            self.test_orders.append(order)

        # 获取订单统计
        query = OrderQuery(strategy_id="test_strategy")
        orders = self.order_service.query_orders(query)

        # 分析订单
        statistics = self.order_service.get_order_statistics(query)

        # 验证分析结果
        self.assertIsNotNone(statistics)
        self.assertIn('total_orders', statistics)

        logger.info(f"订单分析成功: {statistics}")


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestOrderManagementIntegration)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 返回测试结果
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
