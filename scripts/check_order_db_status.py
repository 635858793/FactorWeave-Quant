"""
检查订单数据库表状态
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.services.database_service import DatabaseService
from core.containers import get_service_container


def check_order_database_status():
    """检查订单数据库表状态"""
    try:
        logger.info("=" * 80)
        logger.info("开始检查订单数据库表状态")
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

        # 3. 检查连接池
        logger.info("\n3. 检查连接池...")
        connection_pools = db_service._connection_pools
        logger.info(f"   连接池数量: {len(connection_pools)}")
        for pool_name in connection_pools.keys():
            logger.info(f"   - {pool_name}")

        # 4. 检查表是否存在
        logger.info("\n4. 检查表是否存在...")
        for pool_name in order_dbs.keys():
            try:
                with db_service.get_connection(pool_name) as conn:
                    # 检查orders表
                    result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'").fetchall()
                    orders_exists = len(result) > 0
                    logger.info(f"   {pool_name}: orders表 {'✅ 存在' if orders_exists else '❌ 不存在'}")

                    if orders_exists:
                        # 查询订单数量
                        result = conn.execute("SELECT COUNT(*) FROM orders").fetchone()
                        if result:
                            logger.info(f"      订单数量: {result[0]}")
                    else:
                        logger.warning(f"      orders表不存在，无法查询订单数量")

            except Exception as e:
                logger.error(f"   {pool_name}: 检查失败 - {e}")

        logger.info("\n" + "=" * 80)
        logger.info("订单数据库表状态检查完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 检查订单数据库表状态失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    try:
        success = check_order_database_status()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
