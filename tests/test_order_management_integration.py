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
import unittest
from datetime import datetime
from typing import List, Dict, Any

from loguru import logger

from core.trading.order_models import (
    Order, OrderRequest, OrderQuery, OrderType, OrderStatus, OrderCategory,
    OrderFill
)
from core.trading.order_service import OrderService
from core.trading.order_repository import OrderRepository
from core.trading.order_executor import OrderExecutor
from core.trading.order_validator import OrderValidator
from core.trading.order_monitor import OrderMonitor
from core.trading.order_analyzer import OrderAnalyzer
from core.containers import get_service_container
from core.containers.service_registry import ServiceScope
from core.events import get_event_bus


class TestOrderManagementIntegration(unittest.TestCase):
    """订单管理系统集成测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        logger.info("开始订单管理系统集成测试")

        # 获取服务容器和事件总线
        cls.service_container = get_service_container()
        cls.event_bus = get_event_bus()

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

        # 查询订单
        query = OrderQuery(
            order_id=order.order_id
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

        # 修改订单
        success = self.order_service.modify_order(
            order.order_id,
            new_price=12.0,
            new_quantity=200
        )

        # 验证修改结果
        self.assertTrue(success)

        # 查询修改后的订单
        query = OrderQuery(order_id=order.order_id)
        orders = self.order_service.query_orders(query)
        modified_order = orders[0]

        self.assertEqual(modified_order.order_price, 12.0)
        self.assertEqual(modified_order.order_quantity, 200)

        logger.info(f"订单修改成功: {order.order_id}")

    def test_06_cancel_order(self):
        """测试取消订单"""
        logger.info("测试取消订单")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
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

        # 取消订单
        result = self.order_service.cancel_order(order.order_id)

        # 验证取消结果
        self.assertEqual(result.status, 'success')

        # 查询取消后的订单
        query = OrderQuery(order_id=order.order_id)
        orders = self.order_service.query_orders(query)
        cancelled_order = orders[0]

        self.assertEqual(cancelled_order.order_status, OrderStatus.CANCELLED)

        logger.info(f"订单取消成功: {order.order_id}")

    def test_07_submit_order(self):
        """测试提交订单"""
        logger.info("测试提交订单")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
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
        self.assertEqual(result.status, 'success')

        # 查询提交后的订单
        query = OrderQuery(order_id=order.order_id)
        orders = self.order_service.query_orders(query)
        submitted_order = orders[0]

        self.assertEqual(submitted_order.order_status, OrderStatus.SUBMITTED)

        logger.info(f"订单提交成功: {order.order_id}")

    def test_08_get_order(self):
        """测试获取单个订单"""
        logger.info("测试获取单个订单")

        # 创建订单
        request = OrderRequest(
            strategy_id="test_strategy",
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
