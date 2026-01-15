#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深度分析连接池创建情况

检查：
1. 所有 AssetType 枚举
2. 订单连接池配置
3. 实际创建的连接池
4. 连接池创建失败的原因
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.services.database_service import DatabaseService
from core.containers import get_service_container
from core.plugin_types import AssetType


def analyze_connection_pools():
    """分析连接池创建情况"""
    try:
        logger.info("=" * 80)
        logger.info("深度分析连接池创建情况")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        db_service = DatabaseService()

        # 2. 分析所有 AssetType
        logger.info("\n2. 分析所有 AssetType 枚举...")
        logger.info(f"   总资产类型数: {len(AssetType)}")

        asset_types_list = list(AssetType)
        for i, asset_type in enumerate(asset_types_list, 1):
            logger.info(f"   {i:2d}. {asset_type.value:30s} ({asset_type.name})")

        # 3. 分析订单数据库配置
        logger.info("\n3. 分析订单数据库配置...")
        order_db_configs = db_service._order_db_configs
        logger.info(f"   订单数据库配置数: {len(order_db_configs)}")

        for pool_name, config in sorted(order_db_configs.items()):
            logger.info(f"   - {pool_name:30s} -> {config.db_path}")

        # 4. 分析实际创建的连接池
        logger.info("\n4. 分析实际创建的连接池...")
        connection_pools = db_service._connection_pools
        logger.info(f"   实际连接池数: {len(connection_pools)}")

        # 分类连接池
        default_pools = []
        order_pools = []
        other_pools = []

        for pool_name in sorted(connection_pools.keys()):
            if pool_name in db_service._default_db_configs:
                default_pools.append(pool_name)
            elif "_orders" in pool_name:
                order_pools.append(pool_name)
            else:
                other_pools.append(pool_name)

        logger.info(f"\n   默认连接池 ({len(default_pools)}):")
        for pool_name in default_pools:
            logger.info(f"     - {pool_name}")

        logger.info(f"\n   订单连接池 ({len(order_pools)}):")
        for pool_name in order_pools:
            logger.info(f"     - {pool_name}")

        if other_pools:
            logger.info(f"\n   其他连接池 ({len(other_pools)}):")
            for pool_name in other_pools:
                logger.info(f"     - {pool_name}")

        # 4.5 尝试手动创建订单连接池以查看错误
        logger.info("\n4.5 尝试手动创建订单连接池以查看错误...")
        failed_pools = []
        for pool_name, config in sorted(order_db_configs.items())[:3]:  # 只测试前3个
            try:
                logger.info(f"   尝试创建: {pool_name}")
                db_service.create_connection_pool(pool_name, config)
                logger.info(f"   ✅ 成功创建: {pool_name}")
            except Exception as e:
                logger.error(f"   ❌ 创建失败: {pool_name} - {e}")
                failed_pools.append((pool_name, str(e)))
                import traceback
                logger.error(traceback.format_exc())

        if failed_pools:
            logger.warning(f"\n   失败的连接池 ({len(failed_pools)}):")
            for pool_name, error in failed_pools:
                logger.warning(f"     - {pool_name}: {error}")

        # 5. 对比配置与实际
        logger.info("\n5. 对比配置与实际...")
        configured_order_pools = set(order_db_configs.keys())
        actual_order_pools = set(order_pools)

        missing_pools = configured_order_pools - actual_order_pools
        if missing_pools:
            logger.warning(f"   ⚠️  配置但未创建的订单连接池 ({len(missing_pools)}):")
            for pool_name in sorted(missing_pools):
                logger.warning(f"     - {pool_name}")
        else:
            logger.info(f"   ✅ 所有配置的订单连接池都已创建")

        extra_pools = actual_order_pools - configured_order_pools
        if extra_pools:
            logger.info(f"   ℹ️  额外创建的连接池 ({len(extra_pools)}):")
            for pool_name in sorted(extra_pools):
                logger.info(f"     - {pool_name}")

        # 6. 检查订单数据库文件
        logger.info("\n6. 检查订单数据库文件...")
        base_path = Path("data/databases")
        if base_path.exists():
            order_db_files = list(base_path.glob("*/*_orders.duckdb"))
            logger.info(f"   找到 {len(order_db_files)} 个订单数据库文件:")

            for db_file in sorted(order_db_files):
                # 获取文件大小
                file_size = db_file.stat().st_size
                size_str = f"{file_size / 1024:.2f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB"

                # 检查表是否存在
                try:
                    import duckdb
                    conn = duckdb.connect(str(db_file))
                    tables = conn.execute("SHOW TABLES").fetchall()
                    table_names = [t[0] for t in tables]
                    has_orders = "orders" in table_names
                    has_fills = "fills" in table_names

                    status = "✅" if has_orders else "⚠️ "
                    logger.info(f"     {status} {db_file.name:40s} ({size_str}) - 表: {', '.join(table_names)}")

                    conn.close()
                except Exception as e:
                    logger.error(f"     ❌ {db_file.name:40s} - 检查失败: {e}")
        else:
            logger.warning(f"   ⚠️  订单数据库目录不存在: {base_path}")

        # 7. 分析支持订单的资产类型
        logger.info("\n7. 分析支持订单的资产类型...")

        # 手动定义支持的资产类型（避免导入 GUI 组件）
        supported_asset_types = {
            AssetType.STOCK_A,
            AssetType.STOCK_B,
            AssetType.STOCK_HK,
            AssetType.STOCK_US,
            AssetType.FUTURES,
            AssetType.OPTION,
            AssetType.CRYPTO,
            AssetType.FOREX,
            AssetType.BOND,
            AssetType.COMMODITY,
            AssetType.INDEX,
            AssetType.FUND,
            AssetType.WARRANT
        }
        logger.info(f"   支持订单的资产类型 ({len(supported_asset_types)}):")
        for asset_type in sorted(supported_asset_types, key=lambda x: x.value):
            logger.info(f"     - {asset_type.value:30s}")

        unsupported_asset_types = set(AssetType) - supported_asset_types
        if unsupported_asset_types:
            logger.info(f"\n   不支持订单的资产类型 ({len(unsupported_asset_types)}):")
            for asset_type in sorted(unsupported_asset_types, key=lambda x: x.value):
                logger.info(f"     - {asset_type.value:30s}")

        # 8. 总结
        logger.info("\n" + "=" * 80)
        logger.info("总结")
        logger.info("=" * 80)
        logger.info(f"总资产类型数: {len(AssetType)}")
        logger.info(f"支持订单的资产类型数: {len(supported_asset_types)}")
        logger.info(f"不支持订单的资产类型数: {len(unsupported_asset_types)}")
        logger.info(f"配置的订单连接池数: {len(order_db_configs)}")
        logger.info(f"实际创建的订单连接池数: {len(order_pools)}")
        logger.info(f"实际连接池总数: {len(connection_pools)}")

        if missing_pools:
            logger.warning(f"\n⚠️  发现 {len(missing_pools)} 个配置但未创建的订单连接池")
            logger.warning("可能原因：")
            logger.warning("  1. 资产类型不支持订单功能")
            logger.warning("  2. 数据库路径创建失败")
            logger.warning("  3. 连接池创建时出现异常")
        else:
            logger.info("\n✅ 所有配置的订单连接池都已成功创建")

        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 分析连接池创建情况失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = analyze_connection_pools()
    sys.exit(0 if success else 1)
