#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单管理系统简单测试

避免Qt相关导入的简单测试
"""

import sys
import os
from datetime import datetime

from loguru import logger


def test_plugin_interface():
    """测试插件接口"""
    logger.info("测试插件接口")

    try:
        from plugins.plugin_interface import IPlugin, IDataSourceStrategyPlugin
        logger.info("插件接口导入成功")
        return True
    except Exception as e:
        logger.error(f"插件接口导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_models():
    """测试订单模型"""
    logger.info("测试订单模型")

    try:
        from core.trading.order_models import (
            Order, OrderRequest, OrderType, OrderStatus, OrderCategory
        )
        from core.plugin_types import AssetType

        # 创建订单请求
        request = OrderRequest(
            strategy_id="test_strategy",
            stock_code="000001",
            asset_type=AssetType.STOCK_A,
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )

        # 测试验证
        is_valid = request.validate()
        logger.info(f"订单请求验证结果: {is_valid}")

        # 创建订单
        order = Order(
            order_id="TEST001",
            strategy_id="test_strategy",
            stock_code="000001",
            asset_type=AssetType.STOCK_A,
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            order_status=OrderStatus.PENDING,
            create_time=datetime.now(),
            update_time=datetime.now(),
            user_id="test_user",
            account_id="test_account"
        )

        logger.info(f"订单创建成功: {order.order_id}")
        return True

    except Exception as e:
        logger.error(f"订单模型测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_repository():
    """测试订单仓库"""
    logger.info("测试订单仓库")

    try:
        from core.trading.order_repository import OrderRepository
        from core.containers import get_service_container
        from core.events import get_event_bus

        service_container = get_service_container()
        event_bus = get_event_bus()

        # 创建订单仓库
        repository = OrderRepository(service_container, event_bus)

        # 测试生成订单ID
        order_id = repository.generate_order_id()
        logger.info(f"生成的订单ID: {order_id}")

        return True

    except Exception as e:
        logger.error(f"订单仓库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_service():
    """测试订单服务"""
    logger.info("测试订单服务")

    try:
        from core.trading.order_service import OrderService
        from core.containers import get_service_container, ServiceScope
        from core.containers.service_registry import ServiceScope as RegistryServiceScope
        from core.events import get_event_bus

        service_container = get_service_container()
        event_bus = get_event_bus()

        # 注册订单服务
        if not service_container.is_registered(OrderService):
            service_container.register(
                OrderService,
                scope=RegistryServiceScope.SINGLETON,
                factory=lambda: OrderService(
                    service_container=service_container,
                    event_bus=event_bus
                )
            )
            logger.info("OrderService 已注册到服务容器")

        # 获取订单服务
        order_service = service_container.resolve(OrderService)

        logger.info("订单服务创建成功")
        return True

    except Exception as e:
        logger.error(f"订单服务测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    logger.info("开始订单管理系统简单测试")

    # 测试插件接口
    plugin_success = test_plugin_interface()
    logger.info(f"插件接口测试: {'成功' if plugin_success else '失败'}")

    # 测试订单模型
    model_success = test_order_models()
    logger.info(f"订单模型测试: {'成功' if model_success else '失败'}")

    # 测试订单仓库
    repo_success = test_order_repository()
    logger.info(f"订单仓库测试: {'成功' if repo_success else '失败'}")

    # 测试订单服务
    service_success = test_order_service()
    logger.info(f"订单服务测试: {'成功' if service_success else '失败'}")

    all_success = plugin_success and model_success and repo_success and service_success
    logger.info(f"订单管理系统简单测试: {'全部成功' if all_success else '部分失败'}")

    return 0 if all_success else 1


if __name__ == '__main__':
    sys.exit(main())
