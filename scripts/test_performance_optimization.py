#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试性能优化功能
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from datetime import datetime
from core.trading.order_service import OrderService
from core.trading.order_models import OrderRequest, OrderType, OrderCategory
from core.plugin_types import AssetType
from core.containers import get_service_container
from core.events import get_event_bus


def test_batch_order_submission():
    """测试批量订单提交"""
    try:
        logger.info("=" * 80)
        logger.info("开始测试批量订单提交")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()
        order_service = OrderService(service_container, event_bus)
        logger.info("✅ 服务初始化完成")

        # 2. 创建批量订单请求
        logger.info("\n2. 创建批量订单请求...")
        batch_size = 10
        order_requests = []

        for i in range(batch_size):
            request = OrderRequest(
                strategy_id="test_strategy",
                asset_type=AssetType.STOCK_A,
                stock_code=f"60000{i}",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0 + i * 0.1,
                order_quantity=100,
                user_id="test_user",
                account_id="test_account",
                tags=["test", "batch"],
                metadata={"batch_index": i}
            )
            order_requests.append(request)

        logger.info(f"✅ 创建了 {batch_size} 个订单请求")

        # 3. 批量创建订单
        logger.info("\n3. 批量创建订单...")
        start_time = time.time()
        orders = order_service.create_orders_batch(order_requests)
        end_time = time.time()

        if orders:
            logger.info(f"✅ 批量创建订单成功")
            logger.info(f"   成功创建: {len(orders)} 个订单")
            logger.info(f"   耗时: {end_time - start_time:.3f} 秒")
            logger.info(f"   平均每个订单: {(end_time - start_time) / len(orders):.3f} 秒")
        else:
            logger.error("❌ 批量创建订单失败")
            return False

        # 4. 测试缓存性能
        logger.info("\n4. 测试缓存性能...")

        # 第一次查询（从数据库）
        start_time = time.time()
        order1 = order_service.get_order(orders[0].order_id)
        end_time = time.time()
        db_time = end_time - start_time
        logger.info(f"   第一次查询（数据库）: {db_time:.3f} 秒")

        # 第二次查询（从缓存）
        start_time = time.time()
        order2 = order_service.get_order(orders[0].order_id)
        end_time = time.time()
        cache_time = end_time - start_time
        logger.info(f"   第二次查询（缓存）: {cache_time:.3f} 秒")

        if cache_time < db_time:
            speedup = db_time / cache_time
            logger.info(f"   ✅ 缓存加速: {speedup:.1f}x")
        else:
            logger.warning(f"   ⚠️  缓存未生效")

        # 5. 测试批量查询
        logger.info("\n5. 测试批量查询...")
        start_time = time.time()
        queried_orders = order_service.get_orders_by_strategy("test_strategy", limit=batch_size)
        end_time = time.time()

        if queried_orders:
            logger.info(f"✅ 批量查询成功")
            logger.info(f"   查询到: {len(queried_orders)} 个订单")
            logger.info(f"   耗时: {end_time - start_time:.3f} 秒")
        else:
            logger.warning("⚠️  批量查询未返回结果")

        # 6. 测试批量取消
        logger.info("\n6. 测试批量取消...")
        order_ids = [order.order_id for order in orders[:5]]
        start_time = time.time()
        cancel_results = order_service.cancel_orders_batch(order_ids)
        end_time = time.time()

        success_count = sum(1 for result in cancel_results.values() if result)
        logger.info(f"✅ 批量取消完成")
        logger.info(f"   成功取消: {success_count}/{len(order_ids)} 个订单")
        logger.info(f"   耗时: {end_time - start_time:.3f} 秒")

        # 7. 测试缓存统计
        logger.info("\n7. 测试缓存统计...")
        cache_stats = order_service.repository.cache.get_stats()
        logger.info(f"✅ 缓存统计:")
        logger.info(f"   缓存大小: {cache_stats['size']}")
        logger.info(f"   TTL: {cache_stats['ttl_seconds']} 秒")
        logger.info(f"   按状态分布: {cache_stats['by_status']}")
        logger.info(f"   按资产类型分布: {cache_stats['by_asset_type']}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 性能优化测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 性能优化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_comparison():
    """测试性能对比（批量 vs 单个）"""
    try:
        logger.info("=" * 80)
        logger.info("开始性能对比测试（批量 vs 单个）")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        event_bus = get_event_bus()
        order_service = OrderService(service_container, event_bus)
        logger.info("✅ 服务初始化完成")

        # 2. 测试单个订单提交
        logger.info("\n2. 测试单个订单提交（10次）...")
        single_order_times = []

        for i in range(10):
            request = OrderRequest(
                strategy_id="test_single",
                asset_type=AssetType.STOCK_A,
                stock_code="600000",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0,
                order_quantity=100,
                user_id="test_user",
                account_id="test_account",
                tags=["test", "single"],
                metadata={"test_index": i}
            )

            start_time = time.time()
            order = order_service.create_order(request)
            end_time = time.time()

            if order:
                single_order_times.append(end_time - start_time)
                logger.debug(f"   订单 {i+1}: {end_time - start_time:.3f} 秒")

        avg_single_time = sum(single_order_times) / len(single_order_times)
        logger.info(f"✅ 单个订单提交完成")
        logger.info(f"   平均耗时: {avg_single_time:.3f} 秒")

        # 3. 测试批量订单提交
        logger.info("\n3. 测试批量订单提交（10个订单）...")
        batch_order_requests = []

        for i in range(10):
            request = OrderRequest(
                strategy_id="test_batch",
                asset_type=AssetType.STOCK_A,
                stock_code="600001",
                order_type=OrderType.BUY,
                order_category=OrderCategory.LIMIT,
                order_price=10.0,
                order_quantity=100,
                user_id="test_user",
                account_id="test_account",
                tags=["test", "batch"],
                metadata={"test_index": i}
            )
            batch_order_requests.append(request)

        start_time = time.time()
        orders = order_service.create_orders_batch(batch_order_requests)
        end_time = time.time()

        if orders:
            avg_batch_time = (end_time - start_time) / len(orders)
            logger.info(f"✅ 批量订单提交完成")
            logger.info(f"   总耗时: {end_time - start_time:.3f} 秒")
            logger.info(f"   平均耗时: {avg_batch_time:.3f} 秒")

            # 4. 性能对比
            logger.info("\n4. 性能对比:")
            speedup = avg_single_time / avg_batch_time
            logger.info(f"   单个订单平均耗时: {avg_single_time:.3f} 秒")
            logger.info(f"   批量订单平均耗时: {avg_batch_time:.3f} 秒")
            logger.info(f"   性能提升: {speedup:.1f}x")

            if speedup > 1:
                logger.info(f"   ✅ 批量操作性能更优")
            else:
                logger.warning(f"   ⚠️  批量操作性能未达到预期")

        logger.info("\n" + "=" * 80)
        logger.info("✅ 性能对比测试完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 性能对比测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success1 = test_batch_order_submission()
        success2 = test_performance_comparison()

        sys.exit(0 if (success1 and success2) else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
