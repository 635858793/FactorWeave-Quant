#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单管理系统诊断测试

用于诊断订单创建失败的原因
"""

import sys
import os
from datetime import datetime

from loguru import logger

from core.trading.order_models import (
    Order, OrderRequest, OrderType, OrderStatus, OrderCategory
)
from core.trading.order_service import OrderService
from core.containers import get_service_container
from core.containers.service_registry import ServiceScope
from core.events import get_event_bus


def test_database_connection():
    """测试数据库连接"""
    logger.info("测试数据库连接")

    try:
        from core.services.database_service import DatabaseService

        service_container = get_service_container()
        db_service = service_container.resolve(DatabaseService)

        # 测试查询
        sql = "SELECT COUNT(*) as count FROM orders"
        result = db_service.query(sql, pool_name="strategy_sqlite")

        logger.info(f"数据库连接成功，订单表中有 {result[0]['count']} 条记录")

        return True

    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_order_service_creation():
    """测试订单服务创建"""
    logger.info("测试订单服务创建")

    try:
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
            logger.info("OrderService 已注册到服务容器")

        # 获取订单服务
        order_service = service_container.resolve(OrderService)

        logger.info("订单服务创建成功")
        return order_service

    except Exception as e:
        logger.error(f"订单服务创建失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_order_request_validation():
    """测试订单请求验证"""
    logger.info("测试订单请求验证")

    try:
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

        # 测试验证
        is_valid = request.validate()
        logger.info(f"订单请求验证结果: {is_valid}")

        return request, is_valid

    except Exception as e:
        logger.error(f"订单请求验证失败: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_order_creation():
    """测试订单创建"""
    logger.info("测试订单创建")

    try:
        # 获取订单服务
        order_service = test_order_service_creation()
        if not order_service:
            logger.error("无法获取订单服务")
            return None

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

        # 测试验证
        is_valid = request.validate()
        logger.info(f"订单请求验证结果: {is_valid}")

        if not is_valid:
            logger.error("订单请求验证失败")
            return None

        # 测试订单验证器
        validation_result = order_service.validator.validate_order_request(request)
        logger.info(f"订单验证器结果: passed={validation_result.passed}, message={validation_result.message}")

        if not validation_result.passed:
            logger.error(f"订单验证失败: {validation_result.message}")
            return None

        # 创建订单
        logger.info("开始创建订单...")
        order = order_service.create_order(request)

        if order:
            logger.info(f"订单创建成功: {order.order_id}")
            logger.info(f"订单详情: {order}")
        else:
            logger.error("订单创建失败，返回None")

            # 尝试查询订单
            from core.trading.order_models import OrderQuery
            query = OrderQuery(strategy_id="test_strategy", stock_code="000001")
            orders = order_service.query_orders(query)
            logger.info(f"查询到 {len(orders)} 个订单")

        return order

    except Exception as e:
        logger.error(f"订单创建失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_order_repository():
    """测试订单仓库"""
    logger.info("测试订单仓库")

    try:
        from core.trading.order_repository import OrderRepository

        service_container = get_service_container()
        event_bus = get_event_bus()

        # 创建订单仓库
        repository = OrderRepository(service_container, event_bus)

        # 测试生成订单ID
        order_id = repository.generate_order_id()
        logger.info(f"生成的订单ID: {order_id}")

        # 测试保存订单
        order = Order(
            order_id=order_id,
            strategy_id="test_strategy",
            stock_code="000001",
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

        logger.info("开始保存订单...")
        success = repository.save_order(order)

        if success:
            logger.info(f"订单保存成功: {order_id}")

            # 测试查询订单
            retrieved_order = repository.get_order(order_id)
            if retrieved_order:
                logger.info(f"订单查询成功: {retrieved_order.order_id}")
            else:
                logger.error("订单查询失败")
        else:
            logger.error("订单保存失败")

        return success

    except Exception as e:
        logger.error(f"订单仓库测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    logger.info("开始订单管理系统诊断测试")

    # 测试数据库连接
    db_success = test_database_connection()
    logger.info(f"数据库连接测试: {'成功' if db_success else '失败'}")

    # 测试订单请求验证
    request, is_valid = test_order_request_validation()
    logger.info(f"订单请求验证测试: {'成功' if is_valid else '失败'}")

    # 测试订单仓库
    repo_success = test_order_repository()
    logger.info(f"订单仓库测试: {'成功' if repo_success else '失败'}")

    # 测试订单创建
    order = test_order_creation()
    logger.info(f"订单创建测试: {'成功' if order else '失败'}")

    logger.info("订单管理系统诊断测试完成")


if __name__ == '__main__':
    main()
