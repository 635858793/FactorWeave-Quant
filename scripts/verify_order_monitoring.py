#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单监控定时任务验证脚本

验证订单监控定时任务是否正常工作
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from core.trading.order_models import (
    Order, OrderRequest, OrderType, OrderStatus, OrderCategory
)
from core.trading.order_service import OrderService
from core.containers import get_service_container
from core.containers.service_registry import ServiceScope
from core.events import get_event_bus
from core.plugin_types import AssetType


def test_order_monitoring_setup():
    """测试订单监控设置"""
    logger.info("=" * 80)
    logger.info("【测试1】订单监控设置验证")
    logger.info("=" * 80)

    try:
        # 获取服务容器和事件总线
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

        # 启动订单监控
        logger.info("\n🔍 启动订单监控...")
        order_service.start_monitoring()
        logger.info("订单监控已启动")

        # 检查TaskScheduler是否注册
        from core.services.task_scheduler import TaskScheduler

        if service_container.is_registered(TaskScheduler):
            logger.info("TaskScheduler 已注册")

            # 获取TaskScheduler
            task_scheduler = service_container.resolve(TaskScheduler)

            # 检查订单监控任务是否已注册
            task = task_scheduler.get_task('order_monitor_check')
            if task:
                logger.info(f"订单监控任务已注册: {task['name']}")
                logger.info(f"   - 任务ID: {task['task_id']}")
                logger.info(f"   - 执行间隔: {task['interval_seconds']} 秒")
                logger.info(f"   - 下次执行时间: {task['next_run_time']}")
            else:
                logger.warning("⚠️  订单监控任务未注册")

        else:
            logger.warning("⚠️  TaskScheduler 未注册")

        logger.info("\n" + "=" * 80)
        logger.info("订单监控设置验证完成")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"订单监控设置验证失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def test_order_monitoring_execution():
    """测试订单监控执行"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试2】订单监控执行验证")
    logger.info("=" * 80)

    try:
        # 获取服务容器
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

        # 创建测试订单
        logger.info("\n📝 创建测试订单...")

        request = OrderRequest(
            strategy_id="monitor_test",
            asset_type=AssetType.STOCK_A,
            stock_code="000001",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )

        order = order_service.create_order(request)
        if order:
            logger.info(f"测试订单创建成功: {order.order_id}")
        else:
            logger.error("❌ 测试订单创建失败")
            return

        # 执行订单检查
        logger.info("\n🔍 执行订单检查...")
        checked_orders = order_service.check_orders()

        logger.info(f"订单检查完成，检查了 {len(checked_orders)} 个订单")

        # 查询订单状态
        query = OrderQuery(order_id=order.order_id)
        orders = order_service.query_orders(query)

        if len(orders) > 0:
            checked_order = orders[0]
            logger.info(f"   订单状态: {checked_order.order_status.value}")
            logger.info(f"   更新时间: {checked_order.update_time}")

        # 清理测试订单
        order_service.delete_order(order.order_id)
        logger.info(f"🗑️  已清理测试订单")

        logger.info("\n" + "=" * 80)
        logger.info("订单监控执行验证完成")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"订单监控执行验证失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def test_order_timeout_detection():
    """测试订单超时检测"""
    logger.info("\n" + "=" * 80)
    logger.info("【测试3】订单超时检测验证")
    logger.info("=" * 80)

    try:
        # 获取服务容器
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

        # 创建超时订单
        logger.info("\n📝 创建超时测试订单...")

        request = OrderRequest(
            strategy_id="timeout_test",
            asset_type=AssetType.STOCK_A,
            stock_code="000002",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account"
        )

        order = order_service.create_order(request)
        if not order:
            logger.error("❌ 超时测试订单创建失败")
            return

        logger.info(f"超时测试订单创建成功: {order.order_id}")

        # 模拟订单创建时间超过超时阈值
        logger.info("\n⏰ 模拟订单超时...")
        old_create_time = order.create_time
        order.create_time = datetime.now() - timedelta(minutes=30)  # 30分钟前
        order_service.repository.update_order(order)
        logger.info(f"   订单创建时间: {old_create_time}")
        logger.info(f"   修改为: {order.create_time}")

        # 执行订单检查（应该检测到超时）
        logger.info("\n🔍 执行订单检查（超时检测）...")
        checked_orders = order_service.check_orders()

        logger.info(f"订单检查完成，检查了 {len(checked_orders)} 个订单")

        # 查询订单状态
        query = OrderQuery(order_id=order.order_id)
        orders = order_service.query_orders(query)

        if len(orders) > 0:
            checked_order = orders[0]
            logger.info(f"   订单状态: {checked_order.order_status.value}")
            logger.info(f"   错误信息: {checked_order.error_message or '无'}")

            # 检查是否被标记为超时
            if checked_order.error_message and "超时" in checked_order.error_message:
                logger.info("订单超时检测成功")
            else:
                logger.warning("⚠️  订单超时检测未触发")

        # 清理测试订单
        order_service.delete_order(order.order_id)
        logger.info(f"🗑️  已清理测试订单")

        logger.info("\n" + "=" * 80)
        logger.info("订单超时检测验证完成")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"订单超时检测验证失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )

    logger.info("\n" + "=" * 80)
    logger.info("订单监控定时任务验证")
    logger.info("=" * 80)

    # 运行测试
    test_order_monitoring_setup()
    test_order_monitoring_execution()
    test_order_timeout_detection()

    logger.info("\n" + "=" * 80)
    logger.info("所有测试完成")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
