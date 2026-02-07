#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试订单执行器的 StrategyManager 导入错误修复
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


def test_resolve_account_without_strategy_manager():
    """测试在没有 StrategyManager 的情况下解析账号"""
    logger.info("=" * 60)
    logger.info("测试: 订单执行器在没有 StrategyManager 的情况下的账号解析")
    logger.info("=" * 60)
    
    try:
        # 初始化服务容器和事件总线
        service_container = ServiceContainer()
        event_bus = EventBus(async_execution=False, deduplication_window=0.5, enable_history=True)
        
        # 注册事件总线到服务容器
        service_container.register(EventBus, event_bus)
        
        # 创建订单执行器
        order_executor = OrderExecutor(service_container, event_bus)
        
        # 创建测试订单（不指定账号，使用系统默认账号）
        order = Order(
            order_id="TEST_ORDER_001",
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
        logger.info("测试 1: 解析订单账号（没有 StrategyManager）")
        account = order_executor._resolve_account_for_order(order)
        
        if account:
            logger.info(f"成功解析账号: {account.account_id}")
            logger.info(f"   账号名称: {account.account_name}")
            logger.info(f"   机构名称: {account.institution_name}")
        else:
            logger.warning("⚠️ 未能解析账号（可能是因为没有配置账号）")
        
        logger.info("=" * 60)
        logger.info("测试完成：订单执行器在没有 StrategyManager 的情况下正常工作")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_resolve_account_without_strategy_manager()
    sys.exit(0 if success else 1)
