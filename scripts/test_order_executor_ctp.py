#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试订单执行器使用CTP接口
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from datetime import datetime
from core.trading.order_service import OrderService
from core.trading.order_models import OrderRequest, OrderType, OrderCategory
from core.plugin_types import AssetType
from core.containers import get_service_container
from core.events import get_event_bus


def test_order_executor_with_ctp():
    """测试订单执行器使用CTP接口"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试订单执行器使用CTP接口")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 2. 创建订单服务
        logger.info("\n2. 创建订单服务...")
        order_service = OrderService(service_container, event_bus)
        logger.info("✅ 订单服务创建成功")

        # 3. 测试期货订单
        logger.info("\n3. 测试期货订单...")
        futures_request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.FUTURES,
            stock_code="IF2401",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=4000.0,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account",
            tags=["test", "futures"],
            metadata={
                "contract_multiplier": 300,
                "margin_ratio": 0.15
            }
        )

        futures_order = order_service.create_order(futures_request)
        if futures_order:
            logger.info(f"✅ 期货订单创建成功")
            logger.info(f"   订单ID: {futures_order.order_id}")
            logger.info(f"   资产类型: {futures_order.asset_type.value}")
            logger.info(f"   合约代码: {futures_order.stock_code}")
            logger.info(f"   订单状态: {futures_order.order_status.value}")
        else:
            logger.error("❌ 期货订单创建失败")
            return False

        # 4. 测试期权订单
        logger.info("\n4. 测试期权订单...")
        option_request = OrderRequest(
            strategy_id="test_strategy",
            asset_type=AssetType.OPTION,
            stock_code="IO2401-C-4000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=50.0,
            order_quantity=10,
            user_id="test_user",
            account_id="test_account",
            tags=["test", "option"],
            metadata={
                "contract_multiplier": 100,
                "margin_ratio": 0.20,
                "strike_price": 4000.0,
                "expiry_date": "2024-01-15",
                "option_type": "CALL"
            }
        )

        option_order = order_service.create_order(option_request)
        if option_order:
            logger.info(f"✅ 期权订单创建成功")
            logger.info(f"   订单ID: {option_order.order_id}")
            logger.info(f"   资产类型: {option_order.asset_type.value}")
            logger.info(f"   合约代码: {option_order.stock_code}")
            logger.info(f"   订单状态: {option_order.order_status.value}")
        else:
            logger.error("❌ 期权订单创建失败")
            return False

        # 5. 测试查询订单
        logger.info("\n5. 测试查询订单...")
        queried_order = order_service.get_order(futures_order.order_id)
        if queried_order:
            logger.info(f"✅ 订单查询成功")
            logger.info(f"   订单ID: {queried_order.order_id}")
            logger.info(f"   订单状态: {queried_order.order_status.value}")
        else:
            logger.error("❌ 订单查询失败")
            return False

        # 6. 测试取消订单
        logger.info("\n6. 测试取消订单...")
        cancel_result = order_service.cancel_order(futures_order.order_id)
        if cancel_result:
            logger.info(f"✅ 订单取消成功")
            logger.info(f"   订单ID: {futures_order.order_id}")
        else:
            logger.error("❌ 订单取消失败")
            return False

        logger.info("\n" + "=" * 80)
        logger.info("✅ 订单执行器使用CTP接口测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 测试订单执行器使用CTP接口失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_order_executor_with_ctp()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
