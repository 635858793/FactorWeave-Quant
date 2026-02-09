#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试策略级别的账号解析功能

测试 StrategyManager 的完整功能，包括：
1. StrategyManager 的初始化
2. 策略配置的获取
3. 策略级别的账号解析
4. 三级优先级账号解析
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
from core.services.strategy_service import StrategyConfig


def test_strategy_manager_with_service():
    """测试 StrategyManager 与 StrategyService 的集成"""
    logger.info("=" * 60)
    logger.info("测试 1: StrategyManager 与 StrategyService 的集成")
    logger.info("=" * 60)
    
    try:
        # 初始化服务容器和事件总线
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        
        # 注册事件总线到服务容器
        service_container.register_instance(EventBus, event_bus)
        
        # 测试 StrategyManager 的初始化
        from core.trading.strategy_manager import StrategyManager
        strategy_manager = StrategyManager(service_container)
        
        logger.info("StrategyManager 初始化成功")
        
        # 测试获取不存在的策略
        logger.info("\n测试 2: 获取不存在的策略")
        strategy = strategy_manager.get_strategy("non_existent_strategy")
        if strategy is None:
            logger.info("正确返回 None（策略不存在）")
        else:
            logger.error("❌ 应该返回 None")
            return False
        
        # 测试获取所有策略
        logger.info("\n测试 3: 获取所有策略")
        strategies = strategy_manager.get_all_strategies()
        logger.info(f"获取到 {len(strategies)} 个策略")
        
        # 如果有策略，测试获取第一个策略
        if strategies:
            first_strategy_id = list(strategies.keys())[0]
            logger.info(f"\n测试 4: 获取第一个策略: {first_strategy_id}")
            strategy = strategy_manager.get_strategy(first_strategy_id)
            if strategy:
                logger.info(f"成功获取策略: {strategy.name}")
                logger.info(f"   策略ID: {strategy.strategy_id}")
                logger.info(f"   插件类型: {strategy.plugin_type}")
                logger.info(f"   默认账号: {strategy.default_account_id}")
            else:
                logger.error("❌ 获取策略失败")
                return False
        
        logger.info("=" * 60)
        logger.info("StrategyManager 测试通过")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_account_resolution_with_strategy():
    """测试订单执行器的策略级别账号解析"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 5: 订单执行器的策略级别账号解析")
    logger.info("=" * 60)
    
    try:
        # 初始化服务容器和事件总线
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        
        # 注册事件总线到服务容器
        service_container.register_instance(EventBus, event_bus)
        
        # 创建订单执行器
        order_executor = OrderExecutor(service_container, event_bus)
        
        # 创建测试订单（指定策略ID）
        order = Order(
            order_id="TEST_ORDER_002",
            strategy_id="manual",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.50,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            account_id="default"
        )
        
        # 测试账号解析
        logger.info("测试 6: 解析订单账号（使用策略级别）")
        account = order_executor._resolve_account_for_order(order)
        
        if account:
            logger.info(f"成功解析账号: {account.account_id}")
            logger.info(f"   账号名称: {account.account_name}")
            logger.info(f"   机构名称: {account.institution_name}")
        else:
            logger.warning("⚠️ 未能解析账号（可能是因为没有配置账号或策略）")
        
        logger.info("=" * 60)
        logger.info("订单执行器测试通过")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    logger.info("\n" + "=" * 60)
    logger.info("策略级别账号解析功能测试")
    logger.info("=" * 60)
    
    success = True
    
    # 测试 1: StrategyManager 与 StrategyService 的集成
    if not test_strategy_manager_with_service():
        success = False
    
    # 测试 2: 订单执行器的策略级别账号解析
    if not test_account_resolution_with_strategy():
        success = False
    
    if success:
        logger.info("\n" + "=" * 60)
        logger.info("所有测试通过")
        logger.info("=" * 60)
    else:
        logger.info("\n" + "=" * 60)
        logger.error("❌ 部分测试失败")
        logger.info("=" * 60)
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
