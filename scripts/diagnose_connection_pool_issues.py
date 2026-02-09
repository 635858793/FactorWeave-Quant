"""
诊断连接池使用率和监控问题
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.services.database_service import DatabaseService
from core.containers import get_service_container
from core.plugin_types import AssetType


def diagnose_connection_pool_issues():
    """诊断连接池使用率和监控问题"""
    try:
        logger.info("=" * 80)
        logger.info("诊断连接池使用率和监控问题")
        logger.info("=" * 80)

        # 1. 初始化服务
        logger.info("\n1. 初始化服务...")
        service_container = get_service_container()
        db_service = DatabaseService(service_container=service_container)
        db_service.initialize()

        # 2. 检查连接池状态
        logger.info("\n2. 检查连接池状态...")
        for pool_name in list(db_service._connection_pools.keys())[:3]:  # 只检查前3个
            logger.info(f"\n   连接池: {pool_name}")
            
            pool = db_service._connection_pools[pool_name]
            metrics = db_service._pool_metrics[pool_name]
            
            logger.info(f"   总连接数: {len(pool)}")
            logger.info(f"   指标总连接数: {metrics.total_connections}")
            logger.info(f"   活跃连接数: {metrics.active_connections}")
            logger.info(f"   峰值连接数: {metrics.peak_connections}")
            
            # 检查每个连接的状态
            logger.info(f"   连接详情:")
            for i, conn in enumerate(pool):
                logger.info(f"     连接 {i}: is_active={conn.is_active}, created_at={conn.created_at}, query_count={conn.query_count}")
            
            # 计算使用率
            if metrics.total_connections > 0:
                usage_rate = (metrics.active_connections / metrics.total_connections) * 100
                logger.info(f"   使用率: {usage_rate:.1f}%")
            else:
                logger.info(f"   使用率: 0.0%")

        # 3. 测试连接获取和释放
        logger.info("\n3. 测试连接获取和释放...")
        test_pool_name = list(db_service._connection_pools.keys())[0]
        logger.info(f"   测试连接池: {test_pool_name}")
        
        # 获取指标
        metrics_before = db_service._pool_metrics[test_pool_name]
        logger.info(f"   获取前 - 活跃连接: {metrics_before.active_connections}, 总连接: {metrics_before.total_connections}")
        
        # 获取连接
        with db_service.get_connection(test_pool_name) as conn:
            logger.info(f"   连接已获取: is_active={conn.is_active}")
            
            # 获取指标
            metrics_during = db_service._pool_metrics[test_pool_name]
            logger.info(f"   使用中 - 活跃连接: {metrics_during.active_connections}, 总连接: {metrics_during.total_connections}")
            
            # 执行简单查询
            if conn.db_type.name == "DUCKDB":
                result = conn.execute("SELECT 1")
                logger.info(f"   查询执行成功: {result}")
            elif conn.db_type.name == "SQLITE":
                result = conn.execute("SELECT 1")
                logger.info(f"   查询执行成功: {result}")
        
        # 获取指标
        metrics_after = db_service._pool_metrics[test_pool_name]
        logger.info(f"   释放后 - 活跃连接: {metrics_after.active_connections}, 总连接: {metrics_after.total_connections}")
        
        # 4. 检查监控组件
        logger.info("\n4. 检查监控组件...")
        try:
            from gui.widgets.adaptive_pool_monitor_widget import AdaptivePoolMonitorWidget
            logger.info(f"   AdaptivePoolMonitorWidget 导入成功")
            
            # 尝试创建实例
            monitor_widget = AdaptivePoolMonitorWidget()
            logger.info(f"   AdaptivePoolMonitorWidget 实例化成功")
        except ImportError as e:
            logger.error(f"   ❌ AdaptivePoolMonitorWidget 导入失败: {e}")
        except Exception as e:
            logger.error(f"   ❌ AdaptivePoolMonitorWidget 实例化失败: {e}")
            import traceback
            traceback.print_exc()

        # 5. 检查 UI 组件
        logger.info("\n5. 检查 UI 组件...")
        try:
            from gui.dialogs.connection_pool_manager_dialog import ConnectionPoolManagerDialog
            logger.info(f"   ConnectionPoolManagerDialog 导入成功")
        except ImportError as e:
            logger.error(f"   ❌ ConnectionPoolManagerDialog 导入失败: {e}")

        logger.info("\n" + "=" * 80)
        logger.info("诊断完成")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    diagnose_connection_pool_issues()
