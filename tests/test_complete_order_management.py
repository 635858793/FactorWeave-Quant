#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单管理系统完整集成测试

测试订单管理系统的完整功能，包括多资产支持、XTP接口、账户管理等
"""

import sys
import os
import unittest
from datetime import datetime
from typing import List

from loguru import logger

from core.trading.order_models import (
    Order, OrderRequest, OrderQuery, OrderType, OrderStatus, OrderCategory
)
from core.trading.order_service import OrderService
from core.trading.account_models import (
    Account, Position, FundInfo, AccountQuery, PositionQuery, AccountStatus, PositionSide
)
from core.trading.account_manager import AccountManager
from core.trading.interfaces.xtp_trading_interface import XTPTradingInterface
from core.containers import get_service_container
from core.containers.service_registry import ServiceScope
from core.events import get_event_bus
from core.plugin_types import AssetType


class TestOrderManagementCompleteIntegration(unittest.TestCase):
    """订单管理系统完整集成测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        logger.info("开始订单管理系统完整集成测试")

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

        # 注册账户管理器
        if not cls.service_container.is_registered(AccountManager):
            cls.service_container.register(
                AccountManager,
                scope=ServiceScope.SINGLETON,
                factory=lambda: AccountManager(
                    service_container=cls.service_container,
                    event_bus=cls.event_bus
                )
            )
            logger.info("AccountManager 已注册到服务容器")

        # 获取服务
        cls.order_service = cls.service_container.resolve(OrderService)
        cls.account_manager = cls.service_container.resolve(AccountManager)

        # 清理测试数据
        cls.cleanup_test_data()

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        logger.info("订单管理系统完整集成测试完成")

        # 清理测试数据
        cls.cleanup_test_data()

    @classmethod
    def cleanup_test_data(cls):
        """清理测试数据"""
        try:
            # 清理订单
            query = OrderQuery(
                strategy_id="test_complete",
                limit=1000
            )
            orders = cls.order_service.query_orders(query)

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
        for order in self.test_orders:
            try:
                self.order_service.delete_order(order.order_id)
            except Exception as e:
                logger.error(f"清理订单失败: {e}")

    def test_01_multi_asset_order_creation(self):
        """测试多资产类型订单创建"""
        logger.info("测试多资产类型订单创建")

        asset_types = [
            AssetType.STOCK_A,
            AssetType.STOCK_B,
            AssetType.STOCK_HK,
            AssetType.STOCK_US,
            AssetType.FUTURES,
            AssetType.OPTION,
            AssetType.CRYPTO,
            AssetType.FOREX,
            AssetType.FUND,
            AssetType.BOND
        ]

        created_orders = []

        for asset_type in asset_types:
            request = OrderRequest(
                strategy_id="test_complete",
                asset_type=asset_type,
                stock_code="TEST001",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0,
                order_quantity=100,
                user_id="test_user",
                account_id="test_account"
            )

            order = self.order_service.create_order(request)
            self.assertIsNotNone(order, f"{asset_type.value} 订单创建失败")
            self.assertEqual(order.asset_type, asset_type)
            self.test_orders.append(order)
            created_orders.append(order)

        logger.info(f"成功创建 {len(created_orders)} 个多资产类型订单")

    def test_02_account_management(self):
        """测试账户管理"""
        logger.info("测试账户管理")

        # 创建测试账户
        account = Account(
            account_id="TEST_ACC_001",
            account_name="测试账户",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            balance=100000.0,
            available_balance=100000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        # 创建账户
        result = self.account_manager.create_account(account)
        self.assertTrue(result, "账户创建失败")

        # 查询账户
        query = AccountQuery(account_id="TEST_ACC_001")
        accounts = self.account_manager.query_accounts(query)
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0].account_id, "TEST_ACC_001")

        # 删除账户
        result = self.account_manager.delete_account("TEST_ACC_001")
        self.assertTrue(result, "账户删除失败")

        logger.info("账户管理测试完成")

    def test_03_position_management(self):
        """测试持仓管理"""
        logger.info("测试持仓管理")

        # 创建测试账户
        account = Account(
            account_id="TEST_ACC_POS",
            account_name="持仓测试账户",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            balance=100000.0,
            available_balance=100000.0,
            frozen_balance=0.0,
            market_value=0.0,
            total_assets=100000.0,
            profit_loss=0.0,
            profit_loss_ratio=0.0,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        self.account_manager.create_account(account)

        # 创建测试持仓
        position = Position(
            position_id="POS_001",
            account_id="TEST_ACC_POS",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            stock_name="平安银行",
            side=PositionSide.LONG,
            quantity=1000,
            available_quantity=1000,
            open_price=10.0,
            current_price=10.5,
            market_value=10500.0,
            cost_price=10.0,
            cost_value=10000.0,
            profit_loss=500.0,
            profit_loss_ratio=0.05,
            open_time=datetime.now(),
            update_time=datetime.now()
        )

        # 创建持仓
        result = self.account_manager.create_position(position)
        self.assertTrue(result, "持仓创建失败")

        # 查询持仓
        query = PositionQuery(account_id="TEST_ACC_POS")
        positions = self.account_manager.query_positions(query)
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].position_id, "POS_001")

        # 删除持仓
        result = self.account_manager.delete_position("POS_001")
        self.assertTrue(result, "持仓删除失败")

        # 清理账户
        self.account_manager.delete_account("TEST_ACC_POS")

        logger.info("持仓管理测试完成")

    def test_04_xtp_interface_integration(self):
        """测试XTP接口集成"""
        logger.info("测试XTP接口集成")

        # 创建XTP接口实例
        xtp_interface = XTPTradingInterface(
            account_id="TEST_XTP",
            password="test_password",
            server_address="test.server.com"
        )

        # 测试连接
        result = xtp_interface.connect()
        self.assertTrue(result, "XTP连接失败")

        # 测试登录
        result = xtp_interface.login()
        self.assertTrue(result, "XTP登录失败")

        # 创建测试订单
        order = Order(
            order_id="TEST_XTP_ORDER",
            strategy_id="test_complete",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now()
        )

        # 测试提交订单
        execution_result = xtp_interface.submit_order(order)
        self.assertIsNotNone(execution_result, "XTP订单提交返回None")
        self.assertEqual(execution_result.order_id, "TEST_XTP_ORDER")

        # 测试断开连接
        xtp_interface.disconnect()

        logger.info("XTP接口集成测试完成")

    def test_05_order_query_with_asset_type(self):
        """测试带资产类型的订单查询"""
        logger.info("测试带资产类型的订单查询")

        # 创建不同资产类型的订单
        asset_types = [AssetType.STOCK_A, AssetType.FUTURES, AssetType.CRYPTO]

        for asset_type in asset_types:
            request = OrderRequest(
                strategy_id="test_complete",
                asset_type=asset_type,
                stock_code="TEST001",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0,
                order_quantity=100,
                user_id="test_user",
                account_id="test_account"
            )

            order = self.order_service.create_order(request)
            self.test_orders.append(order)

        # 查询股票类型订单
        query = OrderQuery(
            strategy_id="test_complete",
            asset_type=AssetType.STOCK_A
        )
        stock_orders = self.order_service.query_orders(query)
        self.assertEqual(len(stock_orders), 1)

        # 查询期货类型订单
        query = OrderQuery(
            strategy_id="test_complete",
            asset_type=AssetType.FUTURES
        )
        futures_orders = self.order_service.query_orders(query)
        self.assertEqual(len(futures_orders), 1)

        # 查询加密货币类型订单
        query = OrderQuery(
            strategy_id="test_complete",
            asset_type=AssetType.CRYPTO
        )
        crypto_orders = self.order_service.query_orders(query)
        self.assertEqual(len(crypto_orders), 1)

        logger.info("带资产类型的订单查询测试完成")

    def test_06_fund_info_management(self):
        """测试资金信息管理"""
        logger.info("测试资金信息管理")

        # 创建测试账户
        account = Account(
            account_id="TEST_ACC_FUND",
            account_name="资金测试账户",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            balance=100000.0,
            available_balance=80000.0,
            frozen_balance=20000.0,
            market_value=50000.0,
            total_assets=150000.0,
            profit_loss=5000.0,
            profit_loss_ratio=0.0333,
            create_time=datetime.now(),
            update_time=datetime.now()
        )
        self.account_manager.create_account(account)

        # 创建资金信息
        fund_info = FundInfo(
            account_id="TEST_ACC_FUND",
            total_balance=100000.0,
            available_balance=80000.0,
            frozen_balance=20000.0,
            market_value=50000.0,
            total_assets=150000.0,
            profit_loss=5000.0,
            profit_loss_ratio=0.0333,
            margin_used=20000.0,
            margin_available=80000.0,
            maintenance_margin=10000.0,
            update_time=datetime.now()
        )

        # 更新资金信息
        result = self.account_manager.update_fund_info(fund_info)
        self.assertTrue(result, "资金信息更新失败")

        # 查询资金信息
        retrieved_fund_info = self.account_manager.get_fund_info("TEST_ACC_FUND")
        self.assertIsNotNone(retrieved_fund_info, "资金信息查询失败")
        self.assertEqual(retrieved_fund_info.account_id, "TEST_ACC_FUND")
        self.assertEqual(retrieved_fund_info.total_assets, 150000.0)

        # 清理账户
        self.account_manager.delete_account("TEST_ACC_FUND")

        logger.info("资金信息管理测试完成")


if __name__ == '__main__':
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )

    # 运行测试
    unittest.main(verbosity=2)
