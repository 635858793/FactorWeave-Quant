"""
测试数据库迁移脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.migration.asset_type_migration import AssetTypeMigration
from loguru import logger


def main():
    """主函数"""
    try:
        logger.info("=" * 80)
        logger.info("测试数据库迁移脚本")
        logger.info("=" * 80)

        # 创建迁移实例
        migration = AssetTypeMigration()

        # 检查数据库文件是否存在
        logger.info(f"\nSQLite 数据库路径: {migration.db_path}")
        logger.info(f"SQLite 数据库存在: {migration.db_path.exists()}")

        logger.info(f"\nDuckDB 数据库路径: {migration.duckdb_path}")
        logger.info(f"DuckDB 数据库存在: {migration.duckdb_path.exists()}")

        # 执行迁移
        logger.info("\n开始执行迁移...")
        migration.migrate_all()

        logger.info("\n" + "=" * 80)
        logger.info("✅ 数据库迁移测试完成")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ 数据库迁移测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
