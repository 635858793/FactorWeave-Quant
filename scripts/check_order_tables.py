"""
检查订单数据库表是否存在
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.services.database_service import DatabaseService
from core.containers import get_service_container
from core.plugin_types import AssetType


def check_order_tables():
    """检查订单数据库表"""
    try:
        logger.info("=" * 80)
        logger.info("开始检查订单数据库表")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        db_service = service_container.resolve(DatabaseService)

        # 2. 检查订单数据库配置
        logger.info("\n2. 检查订单数据库配置...")
        order_dbs = db_service._order_db_configs
        logger.info(f"   订单数据库数量: {len(order_dbs)}")
        for pool_name, config in order_dbs.items():
            logger.info(f"   - {pool_name}: {config.db_path}")

        # 3. 检查表是否存在
        logger.info("\n3. 检查表是否存在...")
        for pool_name in order_dbs.keys():
            try:
                with db_service.get_connection(pool_name) as conn:
                    # 检查orders表
                    result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'").fetchall()
                    orders_exists = len(result) > 0
                    logger.info(f"   {pool_name}: orders表 {'存在' if orders_exists else '不存在'}")

                    if orders_exists:
                        # 检查表结构
                        result = conn.execute("PRAGMA table_info(orders)").fetchall()
                        logger.info(f"      列数: {len(result)}")
                        for col in result[:5]:
                            logger.info(f"      - {col[1]} ({col[2]})")

                    # 检查order_fills表
                    result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_fills'").fetchall()
                    fills_exists = len(result) > 0
                    logger.info(f"   {pool_name}: order_fills表 {'存在' if fills_exists else '不存在'}")

            except Exception as e:
                logger.error(f"   {pool_name}: 检查失败 - {e}")

        # 4. 尝试创建表
        logger.info("\n4. 尝试创建订单表...")
        for pool_name in order_dbs.keys():
            try:
                db_service._create_orders_table(pool_name)
                db_service._create_order_fills_table(pool_name)
                logger.info(f"   {pool_name}: 表创建成功")
            except Exception as e:
                logger.error(f"   {pool_name}: 表创建失败 - {e}")

        # 5. 再次检查表是否存在
        logger.info("\n5. 再次检查表是否存在...")
        for pool_name in order_dbs.keys():
            try:
                with db_service.get_connection(pool_name) as conn:
                    result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'").fetchall()
                    orders_exists = len(result) > 0
                    logger.info(f"   {pool_name}: orders表 {'存在' if orders_exists else '不存在'}")

            except Exception as e:
                logger.error(f"   {pool_name}: 检查失败 - {e}")

        logger.info("\n" + "=" * 80)
        logger.info("订单数据库表检查完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 检查订单数据库表失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = check_order_tables()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
