#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单管理系统基本功能测试

只测试核心功能，避免复杂的集成
"""

import sys
import os
from datetime import datetime

from loguru import logger


def test_basic_order_creation():
    """测试基本订单创建"""
    logger.info("测试基本订单创建")

    try:
        from core.trading.order_models import (
            Order, OrderRequest, OrderType, OrderStatus, OrderCategory
        )
        from core.plugin_types import AssetType
        from core.trading.order_service import OrderService
        from core.containers import get_service_container
        from core.containers.service_registry import ServiceScope
        from core.events import get_event_bus

        service_container = get_service_container()
        event_bus = get_event_bus()

        # 注册订单服务
        if not service_container.is_registered(OrderService):
            service_container.register(
                OrderService,
                scope=ServiceScope.SINGLETON,
                factory=lambda: OrderService(
                    service_container=service_container,
                    event_bus=event_bus
                )
            )

        # 获取订单服务
        order_service = service_container.resolve(OrderService)

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
        logger.info("开始创建订单...")
        order = order_service.create_order(request)

        if order:
            logger.info(f"订单创建成功: {order.order_id}")
            logger.info(f"订单详情: stock_code={order.stock_code}, "
                       f"order_type={order.order_type.value}, "
                       f"order_quantity={order.order_quantity}, "
                       f"order_status={order.order_status.value}")

            # 测试查询订单
            retrieved_order = order_service.get_order(order.order_id)
            if retrieved_order:
                logger.info(f"订单查询成功: {retrieved_order.order_id}")
            else:
                logger.error("订单查询失败")

            # 清理
            order_service.delete_order(order.order_id)
            logger.info("订单已删除")

            return True
        else:
            logger.error("订单创建失败")
            return False

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_query():
    """测试订单查询"""
    logger.info("测试订单查询")

    try:
        from core.trading.order_models import OrderQuery
        from core.trading.order_service import OrderService
        from core.containers import get_service_container
        from core.containers.service_registry import ServiceScope
        from core.events import get_event_bus

        service_container = get_service_container()
        event_bus = get_event_bus()

        # 获取订单服务
        if not service_container.is_registered(OrderService):
            service_container.register(
                OrderService,
                scope=ServiceScope.SINGLETON,
                factory=lambda: OrderService(
                    service_container=service_container,
                    event_bus=event_bus
                )
            )

        order_service = service_container.resolve(OrderService)

        # 查询所有订单
        query = OrderQuery()
        orders = order_service.query_orders(query)

        logger.info(f"查询到 {len(orders)} 个订单")

        return True

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    logger.info("开始订单管理系统基本功能测试")

    # 测试基本订单创建
    creation_success = test_basic_order_creation()
    logger.info(f"基本订单创建测试: {'成功' if creation_success else '失败'}")

    # 测试订单查询
    query_success = test_order_query()
    logger.info(f"订单查询测试: {'成功' if query_success else '失败'}")

    all_success = creation_success and query_success
    logger.info(f"订单管理系统基本功能测试: {'全部成功' if all_success else '部分失败'}")

    return 0 if all_success else 1


if __name__ == '__main__':
    sys.exit(main())
