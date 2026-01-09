#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试性能优化功能
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from datetime import datetime
from core.trading.order_models import Order, OrderType, OrderCategory, OrderStatus
from core.plugin_types import AssetType
from core.trading.order_cache import OrderCache


def test_order_cache():
    """测试订单缓存"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试订单缓存")
        logger.info("=" * 80)

        # 1. 初始化缓存
        logger.info("\n1. 初始化缓存...")
        cache = OrderCache(ttl_seconds=300)
        logger.info("✅ 缓存初始化完成")

        # 2. 创建测试订单
        logger.info("\n2. 创建测试订单...")
        orders = []
        for i in range(10):
            order = Order(
                order_id=f"TEST_ORDER_{i:03d}",
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=f"60000{i}",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i * 0.1,
                order_quantity=100,
                order_status=OrderStatus.PENDING,
                create_time=datetime.now(),
                update_time=datetime.now(),
                user_id="test_user",
                account_id="test_account"
            )
            orders.append(order)
            cache.set(order)

        logger.info(f"✅ 创建并缓存了 {len(orders)} 个订单")

        # 3. 测试缓存读取
        logger.info("\n3. 测试缓存读取...")
        start_time = time.time()
        for order in orders:
            cached_order = cache.get(order.order_id)
            if cached_order:
                logger.debug(f"   从缓存读取: {order.order_id}")
        end_time = time.time()

        logger.info(f"✅ 缓存读取完成")
        logger.info(f"   读取 {len(orders)} 个订单")
        logger.info(f"   耗时: {end_time - start_time:.3f} 秒")
        logger.info(f"   平均每个: {(end_time - start_time) / len(orders):.6f} 秒")

        # 4. 测试缓存查询功能
        logger.info("\n4. 测试缓存查询功能...")

        # 按状态查询
        pending_orders = cache.get_by_status(OrderStatus.PENDING)
        logger.info(f"   按状态查询（PENDING）: {len(pending_orders)} 个订单")

        # 按资产类型查询
        stock_orders = cache.get_by_asset_type(AssetType.STOCK_A)
        logger.info(f"   按资产类型查询（STOCK_A）: {len(stock_orders)} 个订单")

        # 按策略查询
        strategy_orders = cache.get_by_strategy("test_strategy")
        logger.info(f"   按策略查询（test_strategy）: {len(strategy_orders)} 个订单")

        # 按股票代码查询
        stock_code_orders = cache.get_by_stock_code("600000")
        logger.info(f"   按股票代码查询（600000）: {len(stock_code_orders)} 个订单")

        # 5. 测试缓存统计
        logger.info("\n5. 测试缓存统计...")
        stats = cache.get_stats()
        logger.info(f"✅ 缓存统计:")
        logger.info(f"   缓存大小: {stats['size']}")
        logger.info(f"   TTL: {stats['ttl_seconds']} 秒")
        logger.info(f"   按状态分布: {stats['by_status']}")
        logger.info(f"   按资产类型分布: {stats['by_asset_type']}")

        # 6. 测试缓存更新
        logger.info("\n6. 测试缓存更新...")
        test_order = orders[0]
        test_order.order_price = 20.0
        test_order.update_time = datetime.now()
        cache.update(test_order)

        updated_order = cache.get(test_order.order_id)
        if updated_order and updated_order.order_price == 20.0:
            logger.info("✅ 缓存更新成功")
        else:
            logger.error("❌ 缓存更新失败")

        # 7. 测试缓存删除
        logger.info("\n7. 测试缓存删除...")
        cache.delete(test_order.order_id)
        deleted_order = cache.get(test_order.order_id)

        if deleted_order is None:
            logger.info("✅ 缓存删除成功")
        else:
            logger.error("❌ 缓存删除失败")

        # 8. 测试缓存清空
        logger.info("\n8. 测试缓存清空...")
        cache.clear()
        stats_after_clear = cache.get_stats()

        if stats_after_clear['size'] == 0:
            logger.info("✅ 缓存清空成功")
        else:
            logger.error(f"❌ 缓存清空失败，剩余 {stats_after_clear['size']} 个订单")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 订单缓存测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 订单缓存测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = test_order_cache()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
