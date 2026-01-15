#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试策略与账号关联功能

测试完整的策略与账号关联流程，包括：
1. 创建账号
2. 创建策略并设置默认账号
3. 提交订单并验证账号解析
4. 三级优先级账号解析验证
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from loguru import logger
from core.trading.account_models import Account, AccountStatus, InstitutionType, TradingInterfaceType
from core.trading.order_models import Order, OrderType, OrderStatus, OrderCategory
from core.plugin_types import AssetType
from core.containers import ServiceContainer
from core.events import EventBus
from core.trading.order_executor import OrderExecutor
from core.trading.account_manager import AccountManager
from core.services.strategy_service import StrategyConfig


def test_strategy_account_association():
    """测试策略与账号关联"""
    logger.info("=" * 60)
    logger.info("测试：策略与账号关联功能")
    logger.info("=" * 60)
    
    try:
        # 初始化服务容器和事件总线
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        
        # 注册事件总线到服务容器
        service_container.register_instance(EventBus, event_bus)
        
        # 使用服务引导程序初始化所有服务
        from core.services.service_bootstrap import ServiceBootstrap
        bootstrap = ServiceBootstrap(service_container)
        bootstrap.bootstrap()
        
        # 创建账号管理器
        account_manager = service_container.resolve(AccountManager)
        
        # 创建测试账号
        logger.info("\n步骤 1: 创建测试账号")
        account1 = Account(
            account_id="STOCK_TEST_001",
            account_name="测试账号1",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            institution_name="测试券商",
            institution_type=InstitutionType.BROKER,
            trading_interface_type=TradingInterfaceType.MOCK,
            balance=100000.0,
            available_balance=100000.0,
            market_value=0.0,
            total_assets=100000.0
        )
        
        account2 = Account(
            account_id="STOCK_TEST_002",
            account_name="测试账号2",
            account_type="股票账户",
            status=AccountStatus.ACTIVE,
            institution_name="测试券商2",
            institution_type=InstitutionType.BROKER,
            trading_interface_type=TradingInterfaceType.MOCK,
            balance=200000.0,
            available_balance=200000.0,
            market_value=0.0,
            total_assets=200000.0
        )
        
        success1 = account_manager.create_account(account1)
        success2 = account_manager.create_account(account2)
        
        if success1 and success2:
            logger.info(f"✅ 成功创建账号: {account1.account_id}, {account2.account_id}")
        else:
            logger.error("❌ 创建账号失败")
            return False
        
        # 创建策略服务
        logger.info("\n步骤 2: 创建策略并设置默认账号")
        from core.services.strategy_service import StrategyService
        strategy_service = service_container.resolve(StrategyService)
        
        if not strategy_service:
            logger.error("❌ 无法获取 StrategyService")
            return False
        
        # 创建策略配置（设置默认账号）
        strategy_config = StrategyConfig(
            strategy_id="test_strategy_with_account",
            plugin_type="factorweave",
            parameters={
                'period': 20,
                'threshold': 0.02
            },
            metadata={
                'name': '测试策略（带账号）',
                'type': 'momentum',
                'default_account_id': 'STOCK_TEST_001',  # 设置默认账号
                'group': 'test',
                'tags': ['test', 'account_association']
            }
        )
        
        # 保存策略配置
        success = strategy_service.create_strategy_config(strategy_config)
        
        if success:
            logger.info(f"✅ 成功创建策略: {strategy_config.strategy_id}")
            logger.info(f"   默认账号: {strategy_config.metadata['default_account_id']}")
        else:
            logger.error("❌ 创建策略配置失败")
            return False
        
        # 创建订单执行器
        logger.info("\n步骤 3: 测试订单执行器的账号解析")
        order_executor = OrderExecutor(service_container, event_bus)
        
        # 测试1：使用策略的默认账号
        logger.info("\n测试 4: 使用策略的默认账号")
        order1 = Order(
            order_id="TEST_ORDER_001",
            strategy_id="test_strategy_with_account",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="default"  # 使用默认账号
        )
        
        account = order_executor._resolve_account_for_order(order1)
        if account and account.account_id == "STOCK_TEST_001":
            logger.info(f"✅ 正确使用策略的默认账号: {account.account_id}")
        else:
            logger.error(f"❌ 账号解析失败，期望: STOCK_TEST_001, 实际: {account.account_id if account else 'None'}")
            return False
        
        # 测试2：使用订单指定的账号（优先级1）
        logger.info("\n测试 5: 使用订单指定的账号（优先级1）")
        order2 = Order(
            order_id="TEST_ORDER_002",
            strategy_id="test_strategy_with_account",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="STOCK_TEST_002"  # 指定账号2
        )
        
        account = order_executor._resolve_account_for_order(order2)
        if account and account.account_id == "STOCK_TEST_002":
            logger.info(f"✅ 正确使用订单指定的账号: {account.account_id}")
        else:
            logger.error(f"❌ 账号解析失败，期望: STOCK_TEST_002, 实际: {account.account_id if account else 'None'}")
            return False
        
        # 测试3：使用系统默认账号（优先级3）
        logger.info("\n测试 6: 使用系统默认账号（优先级3）")
        order3 = Order(
            order_id="TEST_ORDER_003",
            strategy_id="non_existent_strategy",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="default"  # 使用默认账号
        )
        
        account = order_executor._resolve_account_for_order(order3)
        if account:
            logger.info(f"✅ 正确使用系统默认账号: {account.account_id}")
        else:
            logger.error("❌ 账号解析失败")
            return False
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试通过")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_strategy_account_association()
    sys.exit(0 if success else 1)
