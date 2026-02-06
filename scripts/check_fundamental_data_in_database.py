"""
检查数据库中的基本面数据

分析为什么数据库中没有基本面数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from core.plugin_types import AssetType
from core.asset_database_manager import get_asset_separated_database_manager


def check_fundamental_data_in_database():
    """检查数据库中的基本面数据"""
    logger.info("\n" + "=" * 80)
    logger.info("检查数据库中的基本面数据")
    logger.info("=" * 80)

    try:
        # 获取数据库管理器
        db_manager = get_asset_separated_database_manager()
        logger.info("[OK] 成功获取数据库管理器")

        # 检查A股数据库
        stock_a_db_path = db_manager._get_database_path(AssetType.STOCK_A)
        logger.info(f"\nA股数据库路径: {stock_a_db_path}")

        # 检查数据库文件是否存在
        if not os.path.exists(stock_a_db_path):
            logger.warning(f"[WARNING] A股数据库文件不存在: {stock_a_db_path}")
            return False

        logger.info(f"[OK] A股数据库文件存在")

        # 连接数据库并检查表
        import duckdb
        conn = duckdb.connect(stock_a_db_path)

        # 检查所有表
        logger.info("\n数据库中的所有表:")
        tables = conn.execute("SHOW TABLES").fetchall()
        for table in tables:
            logger.info(f"  - {table[0]}")

        # 检查fundamentals表是否存在
        table_exists = conn.execute("""
            SELECT COUNT(*) 
            FROM duckdb_tables() 
            WHERE table_name = 'fundamentals'
        """).fetchone()[0] > 0

        if not table_exists:
            logger.warning("[WARNING] fundamentals 表不存在")
            conn.close()
            return False

        logger.info("[OK] fundamentals 表存在")

        # 检查表结构
        logger.info("\nfundamentals 表结构:")
        columns = conn.execute("DESCRIBE fundamentals").fetchall()
        for col in columns:
            logger.info(f"  - {col[0]}: {col[1]}")

        # 检查表中的数据数量
        count = conn.execute("SELECT COUNT(*) FROM fundamentals").fetchone()[0]
        logger.info(f"\nfundamentals 表中的数据数量: {count}")

        if count == 0:
            logger.warning("[WARNING] fundamentals 表中没有数据")
            conn.close()
            return False

        logger.info(f"[OK] fundamentals 表中有 {count} 条数据")

        # 查看前10条数据
        logger.info("\nfundamentals 表中的前10条数据:")
        rows = conn.execute("SELECT * FROM fundamentals LIMIT 10").fetchall()
        for row in rows:
            logger.info(f"  - {row}")

        # 检查特定股票的基本面数据
        test_symbols = ["600543", "000001.SZ", "000002.SZ", "600000.SH"]
        logger.info(f"\n检查特定股票的基本面数据:")
        for symbol in test_symbols:
            result = conn.execute(
                "SELECT * FROM fundamentals WHERE symbol = ?",
                [symbol]
            ).fetchone()
            if result:
                logger.info(f"  [OK] {symbol}: 找到数据")
            else:
                logger.info(f"  [WARNING] {symbol}: 未找到数据")

        conn.close()
        logger.info("\n[SUCCESS] 数据库检查完成")
        return True

    except Exception as e:
        logger.error(f"[FAIL] 数据库检查失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def check_fundamental_data_download():
    """检查基本面数据的下载流程"""
    logger.info("\n" + "=" * 80)
    logger.info("检查基本面数据的下载流程")
    logger.info("=" * 80)

    try:
        from core.services.uni_plugin_data_manager import UniPluginDataManager
        from core.services.service_bootstrap import bootstrap_services

        # 引导服务
        logger.info("开始引导服务...")
        bootstrap = bootstrap_services()
        logger.info("[OK] 服务引导完成")

        # 获取UniPluginDataManager
        container = bootstrap.service_container
        data_manager = container.resolve(UniPluginDataManager)
        logger.info("[OK] 成功获取 UniPluginDataManager")

        # 尝试获取基本面数据
        test_symbol = "600543"
        logger.info(f"\n尝试获取基本面数据: {test_symbol}")

        fundamental_data = data_manager.get_fundamental_data(test_symbol, AssetType.STOCK_A)

        if fundamental_data:
            logger.info(f"[OK] 成功获取基本面数据: {test_symbol}")
            logger.info(f"数据内容: {fundamental_data}")
        else:
            logger.warning(f"[WARNING] 未获取到基本面数据: {test_symbol}")

        logger.info("\n[SUCCESS] 基本面数据下载流程检查完成")
        return True

    except Exception as e:
        logger.error(f"[FAIL] 基本面数据下载流程检查失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False


def main():
    """主函数"""
    logger.info("\n" + "=" * 80)
    logger.info("开始检查基本面数据问题")
    logger.info("=" * 80)

    # 检查数据库
    db_check = check_fundamental_data_in_database()

    # 检查下载流程
    # download_check = check_fundamental_data_download()

    if db_check:
        logger.info("\n[SUCCESS] 数据库中有基本面数据")
        return 0
    else:
        logger.warning("\n[WARNING] 数据库中没有基本面数据或表不存在")
        return 1


if __name__ == "__main__":
    sys.exit(main())
