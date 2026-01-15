"""
验证连接池修复效果
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.services.database_service import DatabaseService
from core.containers import get_service_container
from core.plugin_types import AssetType


def verify_connection_pool_fix():
    """验证连接池修复效果"""
    try:
        logger.info("=" * 80)
        logger.info("验证连接池修复效果")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        db_service = DatabaseService(service_container=service_container)
        db_service.initialize()

        # 2. 检查订单数据库配置
        logger.info("\n2. 检查订单数据库配置...")
        order_dbs = db_service._order_db_configs
        logger.info(f"   订单数据库数量: {len(order_dbs)}")
        
        # 3. 检查连接池
        logger.info("\n3. 检查连接池...")
        connection_pools = db_service._connection_pools
        logger.info(f"   连接池数量: {len(connection_pools)}")
        
        # 4. 分析订单连接池
        logger.info("\n4. 分析订单连接池...")
        order_pools = [pool_name for pool_name in connection_pools.keys() if pool_name.endswith('_orders')]
        logger.info(f"   订单连接池数量: {len(order_pools)}")
        
        if len(order_pools) > 0:
            logger.info(f"   订单连接池列表:")
            for pool_name in sorted(order_pools):
                logger.info(f"     - {pool_name}")
        else:
            logger.warning(f"   ⚠️  没有找到订单连接池")
        
        # 5. 对比配置与实际
        logger.info("\n5. 对比配置与实际...")
        configured_order_pools = set(order_dbs.keys())
        actual_order_pools = set(order_pools)
        
        logger.info(f"   配置的订单连接池数: {len(configured_order_pools)}")
        logger.info(f"   实际创建的订单连接池数: {len(actual_order_pools)}")
        
        if configured_order_pools == actual_order_pools:
            logger.info(f"   ✅ 配置与实际一致")
        else:
            missing_pools = configured_order_pools - actual_order_pools
            if missing_pools:
                logger.warning(f"   ⚠️  配置但未创建的订单连接池 ({len(missing_pools)}):")
                for pool_name in sorted(missing_pools):
                    logger.warning(f"     - {pool_name}")
        
        # 6. 验证资产类型过滤
        logger.info("\n6. 验证资产类型过滤...")
        supported_asset_types = DatabaseService._ORDER_SUPPORTED_ASSET_TYPES
        if supported_asset_types:
            logger.info(f"   支持订单的资产类型数: {len(supported_asset_types)}")
            logger.info(f"   支持的资产类型:")
            for asset_type in sorted(supported_asset_types, key=lambda x: x.value):
                logger.info(f"     - {asset_type.value}")
        else:
            logger.warning(f"   ⚠️  未找到支持订单的资产类型配置")
        
        # 7. 总结
        logger.info("\n" + "=" * 80)
        logger.info("总结")
        logger.info("=" * 80)
        logger.info(f"总资产类型数: {len(AssetType)}")
        logger.info(f"支持订单的资产类型数: {len(supported_asset_types) if supported_asset_types else 0}")
        logger.info(f"配置的订单连接池数: {len(configured_order_pools)}")
        logger.info(f"实际创建的订单连接池数: {len(actual_order_pools)}")
        
        if len(configured_order_pools) == 13:
            logger.info(f"✅ 订单连接池配置正确（13个）")
        else:
            logger.warning(f"⚠️  订单连接池配置数量不正确（应为13，实际{len(configured_order_pools)}）")
        
        if len(actual_order_pools) == 13:
            logger.info(f"✅ 订单连接池创建成功（13个）")
        else:
            logger.warning(f"⚠️  订单连接池创建数量不正确（应为13，实际{len(actual_order_pools)}）")
        
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    verify_connection_pool_fix()
