#!/usr/bin/env python3
"""
数据库和表结构初始化脚本

功能：
1. 检查数据库文件是否存在，不存在则创建
2. 检查表结构是否存在，不存在则创建
3. 创建必要的索引
4. 初始化默认配置数据

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

import os
import sqlite3
import duckdb
from pathlib import Path
from loguru import logger

from db.models.plugin_models import PluginDatabaseManager


def ensure_directory_exists(file_path: str):
    """确保目录存在"""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info(f"创建目录: {directory}")


def init_sqlite_databases():
    """初始化SQLite数据库"""
    sqlite_databases = [
        "data/factorweave_system.sqlite",
        "data/enhanced_async_tasks.sqlite",
        "data/alert_config.sqlite",
        "data/backtest_monitor.sqlite",
        "data/deep_analysis.sqlite",
        "data/metrics.sqlite"
    ]

    for db_path in sqlite_databases:
        try:
            ensure_directory_exists(db_path)

            if not os.path.exists(db_path):
                logger.info(f"创建SQLite数据库: {db_path}")
                conn = sqlite3.connect(db_path)
                conn.close()
            else:
                logger.info(f"SQLite数据库已存在: {db_path}")

        except Exception as e:
            logger.error(f"初始化SQLite数据库失败 {db_path}: {e}")


def init_duckdb_databases():
    """初始化DuckDB数据库"""
    duckdb_databases = [
        "data/factorweave_analytics.duckdb",
        "data/kline_stock.duckdb"
    ]

    for db_path in duckdb_databases:
        try:
            ensure_directory_exists(db_path)

            if not os.path.exists(db_path):
                logger.info(f"创建DuckDB数据库: {db_path}")
                conn = duckdb.connect(db_path)
                conn.close()
            else:
                logger.info(f"DuckDB数据库已存在: {db_path}")

        except Exception as e:
            logger.error(f"初始化DuckDB数据库失败 {db_path}: {e}")


def init_plugin_tables():
    """初始化插件相关表结构"""
    try:

        # 初始化插件数据库管理器
        plugin_db_manager = PluginDatabaseManager("data/factorweave_system.sqlite")
        logger.info("插件数据库表结构初始化完成")

        # 初始化数据源插件配置管理器
        from db.models.plugin_models import get_data_source_config_manager
        config_manager = get_data_source_config_manager()
        logger.info("数据源插件配置表结构初始化完成")

    except Exception as e:
        logger.error(f"初始化插件表结构失败: {e}")


def init_kline_tables():
    """初始化K线数据表结构"""
    try:
        from core.database.table_manager import get_table_manager, TableType

        table_manager = get_table_manager()
        db_path = "data/kline_stock.duckdb"

        # 确保数据库文件存在
        ensure_directory_exists(db_path)
        if not os.path.exists(db_path):
            conn = duckdb.connect(db_path)
            conn.close()

        # 创建不同频率的K线数据表
        frequencies = ['1m', '5m', '15m', '30m', '1h', '1d', '1w', '1M']

        for freq in frequencies:
            try:
                table_manager.ensure_table_exists(
                    database_path=db_path,
                    table_type=TableType.KLINE_DATA,
                    plugin_name="system",
                    period=freq
                )
                logger.info(f"K线数据表初始化完成: {freq}")
            except Exception as e:
                logger.warning(f"K线数据表初始化失败 {freq}: {e}")

    except Exception as e:
        logger.error(f"初始化K线数据表失败: {e}")


def create_indexes():
    """创建必要的索引"""
    try:
        # SQLite索引
        sqlite_conn = sqlite3.connect("data/factorweave_system.sqlite")
        cursor = sqlite_conn.cursor()

        # 数据源插件配置表索引
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_data_source_plugin_configs_plugin_id 
        ON data_source_plugin_configs(plugin_id)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_data_source_plugin_configs_enabled 
        ON data_source_plugin_configs(enabled)
        ''')

        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_data_source_plugin_configs_priority 
        ON data_source_plugin_configs(priority)
        ''')

        sqlite_conn.commit()
        sqlite_conn.close()

        logger.info("SQLite索引创建完成")

        # DuckDB索引
        duckdb_conn = duckdb.connect("data/kline_stock.duckdb")

        # K线数据表索引
        frequencies = ['1m', '5m', '15m', '30m', '1h', '1d', '1w', '1M']
        for freq in frequencies:
            table_name = f"kline_data_{freq.lower()}"
            try:
                # 检查表是否存在
                result = duckdb_conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'").fetchone()
                if result:
                    duckdb_conn.execute(f'''
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_symbol_datetime 
                    ON {table_name}(symbol, datetime)
                    ''')

                    duckdb_conn.execute(f'''
                    CREATE INDEX IF NOT EXISTS idx_{table_name}_datetime 
                    ON {table_name}(datetime)
                    ''')

                    logger.info(f"DuckDB索引创建完成: {table_name}")
            except Exception as e:
                logger.warning(f"创建DuckDB索引失败 {table_name}: {e}")

        duckdb_conn.close()

    except Exception as e:
        logger.error(f"创建索引失败: {e}")


def init_default_configs():
    """初始化默认配置"""
    try:
        from db.models.plugin_models import get_data_source_config_manager

        config_manager = get_data_source_config_manager()

        # 检查是否已有配置
        existing_configs = config_manager.get_all_plugin_configs()
        if existing_configs:
            logger.info(f"已存在 {len(existing_configs)} 个数据源配置，跳过默认配置初始化")
            return

        # 创建默认的AKShare插件配置
        default_akshare_config = {
            "connection": {
                "host": "akshare.akfamily.xyz",
                "port": 443,
                "use_ssl": True,
                "timeout": 60
            },
            "auth": {
                "type": "无认证"
            },
            "routing": {
                "weight": 50,
                "priority": 5,
                "strategy": "优先级",
                "max_retries": 3
            },
            "monitoring": {
                "health_interval": 30,
                "health_timeout": 10,
                "enable_auto_check": True
            },
            "advanced": {
                "enable_cache": True,
                "cache_ttl": 300,
                "max_cache_size": 100,
                "enable_rate_limit": False,
                "requests_per_second": 10,
                "burst_size": 20,
                "max_pool_size": 5,
                "pool_timeout": 30,
                "pool_cleanup_interval": 300,
                "custom_params": {
                    "data_source": "akshare",
                    "market": "A股",
                    "encoding": "utf-8"
                }
            }
        }

        success = config_manager.save_plugin_config(
            plugin_id="examples.akshare_stock_plugin",
            config_data=default_akshare_config,
            priority=5,
            weight=1.0,
            enabled=True,
            max_pool_size=5,
            pool_timeout=30,
            pool_cleanup_interval=300
        )

        if success:
            logger.info("默认AKShare插件配置初始化完成")
        else:
            logger.warning("默认AKShare插件配置初始化失败")

    except Exception as e:
        logger.error(f"初始化默认配置失败: {e}")


def main():
    """主函数"""
    logger.info("开始初始化数据库和表结构...")

    try:
        # 1. 初始化数据库文件
        logger.info("1. 初始化SQLite数据库...")
        init_sqlite_databases()

        logger.info("2. 初始化DuckDB数据库...")
        init_duckdb_databases()

        # 2. 初始化表结构
        logger.info("3. 初始化插件表结构...")
        init_plugin_tables()

        logger.info("4. 初始化K线数据表结构...")
        init_kline_tables()

        # 3. 创建索引
        logger.info("5. 创建数据库索引...")
        create_indexes()

        # 4. 初始化默认配置
        logger.info("6. 初始化默认配置...")
        init_default_configs()

        logger.info("数据库和表结构初始化完成！")

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise


if __name__ == "__main__":
    main()
