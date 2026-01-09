"""
简单测试订单创建
"""

import sys
import os
from decimal import Decimal
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.trading.order_service import OrderService
from core.trading.order_models import OrderType, OrderCategory, OrderRequest
from core.plugin_types import AssetType
from core.containers import get_service_container
from core.events import get_event_bus


def test_single_order():
    """测试单个订单创建"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试单个订单创建")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()

        # 2. 创建订单服务
        logger.info("\n2. 创建订单服务...")
        order_service = OrderService(service_container, event_bus)

        # 3. 创建订单请求
        logger.info("\n3. 创建订单请求...")
        order_request = OrderRequest(
            strategy_id="test_strategy_1",
            asset_type=AssetType.STOCK_A,
            stock_code="600000",
            order_type=OrderType.BUY,
            order_category=OrderCategory.LIMIT,
            order_price=10.00,
            order_quantity=100,
            user_id="test_user",
            account_id="test_account",
            tags=["test"],
            metadata={"test_index": 1}
        )

        # 4. 创建订单
        logger.info("\n4. 创建订单...")
        order = order_service.create_order(order_request)

        if order:
            logger.info(f"✅ 订单创建成功!")
            logger.info(f"   订单ID: {order.order_id}")
            logger.info(f"   资产类型: {order.asset_type.value}")
            logger.info(f"   股票代码: {order.stock_code}")
            logger.info(f"   订单类型: {order.order_type.value}")
            logger.info(f"   订单类别: {order.order_category.value}")
            logger.info(f"   订单价格: {order.order_price}")
            logger.info(f"   订单数量: {order.order_quantity}")
            logger.info(f"   订单状态: {order.order_status.value}")
            logger.info(f"   创建时间: {order.create_time}")
            return True
        else:
            logger.error("❌ 订单创建失败")
            return False

    except Exception as e:
        logger.error(f"❌ 测试单个订单创建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_single_order()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
