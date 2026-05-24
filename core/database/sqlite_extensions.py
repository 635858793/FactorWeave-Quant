from loguru import logger
"""
SQLite管理表扩展

扩展现有SQLite管理表，提供：
- 插件表映射管理
- 数据源配置存储
- 性能统计记录
- 与现有plugin管理表集成

作者: FactorWeave-Quant团队
版本: 1.0
"""

import sqlite3
import json
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
from contextlib import contextmanager
import threading

from .unified_sqlite_access import UnifiedSQLiteAccess

from .table_manager import TableType


@dataclass
class PluginTableMapping:
    """插件表映射"""
    id: Optional[int] = None
    plugin_name: str = ""
    table_type: str = ""
    table_name: str = ""
    database_path: str = ""
    period: Optional[str] = None
    schema_version: str = "1.0"
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    row_count: int = 0
    last_sync_at: Optional[datetime] = None


@dataclass
class DataSourceConfig:
    """数据源配置"""
    id: Optional[int] = None
    plugin_name: str = ""
    config_name: str = ""
    config_data: Dict[str, Any] = None
    config_type: str = "duckdb"  # duckdb, field_mapping, performance
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.config_data is None:
            self.config_data = {}


@dataclass
class PerformanceStatistic:
    """性能统计"""
    id: Optional[int] = None
    plugin_name: str = ""
    table_name: str = ""
    operation_type: str = ""  # insert, query, update, delete
    execution_time: float = 0.0
    row_count: int = 0
    success: bool = True
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None
    additional_info: Optional[Dict[str, Any]] = None


class SQLiteExtensionManager:
    """SQLite扩展管理器"""

    def __init__(self, db_path: str = "data/factorweave_system.sqlite"):
        """
        初始化SQLite扩展管理器

        Args:
            db_path: SQLite数据库路径
        """
        self.db_path = Path(db_path)
        self._lock = threading.RLock()

        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化扩展表
        self._initialize_extension_tables()

        logger.info(f"SQLite扩展管理器初始化完成: {self.db_path}")

    @contextmanager
    def get_connection(self):
        """获取数据库连接（启用WAL模式、外键、性能优化）"""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA cache_size=-64000")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"数据库连接错误: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _initialize_extension_tables(self):
        """初始化扩展表"""
        with self._lock:
            with self.get_connection() as conn:
                # 创建插件表映射表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS plugin_table_mappings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plugin_name VARCHAR(100) NOT NULL,
                        table_type VARCHAR(50) NOT NULL,
                        table_name VARCHAR(200) NOT NULL,
                        database_path TEXT NOT NULL,
                        period VARCHAR(20),
                        schema_version VARCHAR(10) DEFAULT '1.0',
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        row_count INTEGER DEFAULT 0,
                        last_sync_at TIMESTAMP,
                        UNIQUE(plugin_name, table_type, period)
                    )
                ''')

                # 创建数据源配置表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS data_source_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plugin_name VARCHAR(100) NOT NULL,
                        config_name VARCHAR(100) NOT NULL,
                        config_data TEXT NOT NULL,  -- JSON格式
                        config_type VARCHAR(50) DEFAULT 'duckdb',
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(plugin_name, config_name, config_type)
                    )
                ''')

                # 创建性能统计表
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS performance_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plugin_name VARCHAR(100) NOT NULL,
                        table_name VARCHAR(200) NOT NULL,
                        operation_type VARCHAR(20) NOT NULL,
                        execution_time REAL NOT NULL,
                        row_count INTEGER DEFAULT 0,
                        success BOOLEAN DEFAULT 1,
                        error_message TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        additional_info TEXT  -- JSON格式
                    )
                ''')

                # 创建索引
                self._create_indexes(conn)

                conn.commit()
                logger.info("SQLite扩展表初始化完成")

    def _create_indexes(self, conn):
        """创建索引"""
        indexes = [
            # 插件表映射索引
            "CREATE INDEX IF NOT EXISTS idx_plugin_table_mappings_plugin ON plugin_table_mappings(plugin_name)",
            "CREATE INDEX IF NOT EXISTS idx_plugin_table_mappings_type ON plugin_table_mappings(table_type)",
            "CREATE INDEX IF NOT EXISTS idx_plugin_table_mappings_active ON plugin_table_mappings(is_active)",

            # 数据源配置索引
            "CREATE INDEX IF NOT EXISTS idx_data_source_configs_plugin ON data_source_configs(plugin_name)",
            "CREATE INDEX IF NOT EXISTS idx_data_source_configs_type ON data_source_configs(config_type)",
            "CREATE INDEX IF NOT EXISTS idx_data_source_configs_active ON data_source_configs(is_active)",

            # 性能统计索引
            "CREATE INDEX IF NOT EXISTS idx_performance_statistics_plugin ON performance_statistics(plugin_name)",
            "CREATE INDEX IF NOT EXISTS idx_performance_statistics_table ON performance_statistics(table_name)",
            "CREATE INDEX IF NOT EXISTS idx_performance_statistics_operation ON performance_statistics(operation_type)",
            "CREATE INDEX IF NOT EXISTS idx_performance_statistics_timestamp ON performance_statistics(timestamp)",
        ]

        for index_sql in indexes:
            try:
                conn.execute(index_sql)
            except Exception as e:
                logger.warning(f"创建索引失败: {e}")

    # ==================== 插件表映射管理 ====================

    def add_table_mapping(self, mapping: PluginTableMapping) -> bool:
        """
        添加插件表映射

        Args:
            mapping: 插件表映射

        Returns:
            添加是否成功
        """
        try:
            with self._lock:
                with self.get_connection() as conn:
                    conn.execute('''
                        INSERT OR REPLACE INTO plugin_table_mappings 
                        (plugin_name, table_type, table_name, database_path, period, 
                         schema_version, is_active, updated_at, row_count, last_sync_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        mapping.plugin_name,
                        mapping.table_type,
                        mapping.table_name,
                        mapping.database_path,
                        mapping.period,
                        mapping.schema_version,
                        mapping.is_active,
                        datetime.now(),
                        mapping.row_count,
                        mapping.last_sync_at
                    ))

                    conn.commit()
                    logger.info(f"插件表映射已添加: {mapping.plugin_name} -> {mapping.table_name}")
                    return True

        except Exception as e:
            logger.error(f"添加插件表映射失败: {e}")
            return False

    def get_table_mappings(self, plugin_name: Optional[str] = None,
                           table_type: Optional[str] = None,
                           is_active: Optional[bool] = None) -> List[PluginTableMapping]:
        """
        获取插件表映射

        Args:
            plugin_name: 插件名称过滤
            table_type: 表类型过滤
            is_active: 活跃状态过滤

        Returns:
            插件表映射列表
        """
        try:
            with self.get_connection() as conn:
                sql = "SELECT * FROM plugin_table_mappings WHERE 1=1"
                params = []

                if plugin_name:
                    sql += " AND plugin_name = ?"
                    params.append(plugin_name)

                if table_type:
                    sql += " AND table_type = ?"
                    params.append(table_type)

                if is_active is not None:
                    sql += " AND is_active = ?"
                    params.append(is_active)

                sql += " ORDER BY plugin_name, table_type"

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()

                mappings = []
                for row in rows:
                    mapping = PluginTableMapping(
                        id=row['id'],
                        plugin_name=row['plugin_name'],
                        table_type=row['table_type'],
                        table_name=row['table_name'],
                        database_path=row['database_path'],
                        period=row['period'],
                        schema_version=row['schema_version'],
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
                        row_count=row['row_count'],
                        last_sync_at=datetime.fromisoformat(row['last_sync_at']) if row['last_sync_at'] else None
                    )
                    mappings.append(mapping)

                return mappings

        except Exception as e:
            logger.error(f"获取插件表映射失败: {e}")
            return []

    def update_table_mapping_stats(self, plugin_name: str, table_type: str,
                                   row_count: int, period: Optional[str] = None) -> bool:
        """
        更新表映射统计信息

        Args:
            plugin_name: 插件名称
            table_type: 表类型
            row_count: 行数
            period: 周期

        Returns:
            更新是否成功
        """
        try:
            with self._lock:
                with self.get_connection() as conn:
                    sql = '''
                        UPDATE plugin_table_mappings 
                        SET row_count = ?, last_sync_at = ?, updated_at = ?
                        WHERE plugin_name = ? AND table_type = ?
                    '''
                    params = [row_count, datetime.now(), datetime.now(), plugin_name, table_type]

                    if period:
                        sql += " AND period = ?"
                        params.append(period)
                    else:
                        sql += " AND period IS NULL"

                    conn.execute(sql, params)
                    conn.commit()

                    return True

        except Exception as e:
            logger.error(f"更新表映射统计失败: {e}")
            return False

    def remove_table_mapping(self, plugin_name: str, table_type: str,
                             period: Optional[str] = None) -> bool:
        """
        移除插件表映射

        Args:
            plugin_name: 插件名称
            table_type: 表类型
            period: 周期

        Returns:
            移除是否成功
        """
        try:
            with self._lock:
                with self.get_connection() as conn:
                    sql = "DELETE FROM plugin_table_mappings WHERE plugin_name = ? AND table_type = ?"
                    params = [plugin_name, table_type]

                    if period:
                        sql += " AND period = ?"
                        params.append(period)
                    else:
                        sql += " AND period IS NULL"

                    conn.execute(sql, params)
                    conn.commit()

                    logger.info(f"插件表映射已移除: {plugin_name} {table_type}")
                    return True

        except Exception as e:
            logger.error(f"移除插件表映射失败: {e}")
            return False

    # ==================== 数据源配置管理 ====================

    def save_config(self, config: DataSourceConfig) -> bool:
        """
        保存数据源配置

        Args:
            config: 数据源配置

        Returns:
            保存是否成功
        """
        try:
            with self._lock:
                with self.get_connection() as conn:
                    config_json = json.dumps(config.config_data, ensure_ascii=False)

                    conn.execute('''
                        INSERT OR REPLACE INTO data_source_configs 
                        (plugin_name, config_name, config_data, config_type, is_active, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        config.plugin_name,
                        config.config_name,
                        config_json,
                        config.config_type,
                        config.is_active,
                        datetime.now()
                    ))

                    conn.commit()
                    logger.info(f"数据源配置已保存: {config.plugin_name} {config.config_name}")
                    return True

        except Exception as e:
            logger.error(f"保存数据源配置失败: {e}")
            return False

    def get_config(self, plugin_name: str, config_name: str,
                   config_type: str = "duckdb") -> Optional[DataSourceConfig]:
        """
        获取数据源配置

        Args:
            plugin_name: 插件名称
            config_name: 配置名称
            config_type: 配置类型

        Returns:
            数据源配置
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute('''
                    SELECT * FROM data_source_configs 
                    WHERE plugin_name = ? AND config_name = ? AND config_type = ? AND is_active = 1
                ''', (plugin_name, config_name, config_type))

                row = cursor.fetchone()
                if row:
                    config_data = json.loads(row['config_data'])

                    return DataSourceConfig(
                        id=row['id'],
                        plugin_name=row['plugin_name'],
                        config_name=row['config_name'],
                        config_data=config_data,
                        config_type=row['config_type'],
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                    )

                return None

        except Exception as e:
            logger.error(f"获取数据源配置失败: {e}")
            return None

    def get_all_configs(self, plugin_name: Optional[str] = None,
                        config_type: Optional[str] = None) -> List[DataSourceConfig]:
        """
        获取所有数据源配置

        Args:
            plugin_name: 插件名称过滤
            config_type: 配置类型过滤

        Returns:
            数据源配置列表
        """
        try:
            with self.get_connection() as conn:
                sql = "SELECT * FROM data_source_configs WHERE is_active = 1"
                params = []

                if plugin_name:
                    sql += " AND plugin_name = ?"
                    params.append(plugin_name)

                if config_type:
                    sql += " AND config_type = ?"
                    params.append(config_type)

                sql += " ORDER BY plugin_name, config_name"

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()

                configs = []
                for row in rows:
                    config_data = json.loads(row['config_data'])

                    config = DataSourceConfig(
                        id=row['id'],
                        plugin_name=row['plugin_name'],
                        config_name=row['config_name'],
                        config_data=config_data,
                        config_type=row['config_type'],
                        is_active=bool(row['is_active']),
                        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                    )
                    configs.append(config)

                return configs

        except Exception as e:
            logger.error(f"获取所有数据源配置失败: {e}")
            return []

    def delete_config(self, plugin_name: str, config_name: str,
                      config_type: str = "duckdb") -> bool:
        """
        删除数据源配置

        Args:
            plugin_name: 插件名称
            config_name: 配置名称
            config_type: 配置类型

        Returns:
            删除是否成功
        """
        try:
            with self._lock:
                with self.get_connection() as conn:
                    conn.execute('''
                        UPDATE data_source_configs 
                        SET is_active = 0, updated_at = ?
                        WHERE plugin_name = ? AND config_name = ? AND config_type = ?
                    ''', (datetime.now(), plugin_name, config_name, config_type))

                    conn.commit()
                    logger.info(f"数据源配置已删除: {plugin_name} {config_name}")
                    return True

        except Exception as e:
            logger.error(f"删除数据源配置失败: {e}")
            return False

    # ==================== 性能统计管理 ====================

    def record_performance(self, stat: PerformanceStatistic) -> bool:
        """
        记录性能统计

        Args:
            stat: 性能统计

        Returns:
            记录是否成功
        """
        try:
            with self._lock:
                with self.get_connection() as conn:
                    additional_info_json = json.dumps(stat.additional_info) if stat.additional_info else None

                    conn.execute('''
                        INSERT INTO performance_statistics 
                        (plugin_name, table_name, operation_type, execution_time, 
                         row_count, success, error_message, timestamp, additional_info)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        stat.plugin_name,
                        stat.table_name,
                        stat.operation_type,
                        stat.execution_time,
                        stat.row_count,
                        stat.success,
                        stat.error_message,
                        stat.timestamp or datetime.now(),
                        additional_info_json
                    ))

                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"记录性能统计失败: {e}")
            return False

    def get_performance_stats(self, plugin_name: Optional[str] = None,
                              table_name: Optional[str] = None,
                              operation_type: Optional[str] = None,
                              hours: int = 24) -> List[PerformanceStatistic]:
        """
        获取性能统计

        Args:
            plugin_name: 插件名称过滤
            table_name: 表名过滤
            operation_type: 操作类型过滤
            hours: 时间范围（小时）

        Returns:
            性能统计列表
        """
        try:
            with self.get_connection() as conn:
                sql = '''
                    SELECT * FROM performance_statistics 
                    WHERE timestamp >= datetime('now', '-{} hours')
                '''.format(hours)
                params = []

                if plugin_name:
                    sql += " AND plugin_name = ?"
                    params.append(plugin_name)

                if table_name:
                    sql += " AND table_name = ?"
                    params.append(table_name)

                if operation_type:
                    sql += " AND operation_type = ?"
                    params.append(operation_type)

                sql += " ORDER BY timestamp DESC"

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()

                stats = []
                for row in rows:
                    additional_info = json.loads(row['additional_info']) if row['additional_info'] else None

                    stat = PerformanceStatistic(
                        id=row['id'],
                        plugin_name=row['plugin_name'],
                        table_name=row['table_name'],
                        operation_type=row['operation_type'],
                        execution_time=row['execution_time'],
                        row_count=row['row_count'],
                        success=bool(row['success']),
                        error_message=row['error_message'],
                        timestamp=datetime.fromisoformat(row['timestamp']) if row['timestamp'] else None,
                        additional_info=additional_info
                    )
                    stats.append(stat)

                return stats

        except Exception as e:
            logger.error(f"获取性能统计失败: {e}")
            return []

    def get_performance_summary(self, plugin_name: Optional[str] = None,
                                hours: int = 24) -> Dict[str, Any]:
        """
        获取性能统计摘要

        Args:
            plugin_name: 插件名称过滤
            hours: 时间范围（小时）

        Returns:
            性能统计摘要
        """
        try:
            with self.get_connection() as conn:
                sql = '''
                    SELECT 
                        operation_type,
                        COUNT(*) as count,
                        AVG(execution_time) as avg_time,
                        MIN(execution_time) as min_time,
                        MAX(execution_time) as max_time,
                        SUM(row_count) as total_rows,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                    FROM performance_statistics 
                    WHERE timestamp >= datetime('now', '-{} hours')
                '''.format(hours)

                params = []
                if plugin_name:
                    sql += " AND plugin_name = ?"
                    params.append(plugin_name)

                sql += " GROUP BY operation_type"

                cursor = conn.execute(sql, params)
                rows = cursor.fetchall()

                summary = {}
                for row in rows:
                    summary[row['operation_type']] = {
                        'count': row['count'],
                        'avg_time': row['avg_time'],
                        'min_time': row['min_time'],
                        'max_time': row['max_time'],
                        'total_rows': row['total_rows'],
                        'success_count': row['success_count'],
                        'error_count': row['error_count'],
                        'success_rate': row['success_count'] / row['count'] if row['count'] > 0 else 0
                    }

                return summary

        except Exception as e:
            logger.error(f"获取性能统计摘要失败: {e}")
            return {}

    def cleanup_old_stats(self, days: int = 30) -> bool:
        """
        清理旧的性能统计

        Args:
            days: 保留天数

        Returns:
            清理是否成功
        """
        try:
            with self._lock:
                with self.get_connection() as conn:
                    cursor = conn.execute('''
                        DELETE FROM performance_statistics 
                        WHERE timestamp < datetime('now', '-{} days')
                    '''.format(days))

                    deleted_count = cursor.rowcount
                    conn.commit()

                    logger.info(f"清理旧性能统计完成，删除 {deleted_count} 条记录")
                    return True

        except Exception as e:
            logger.error(f"清理旧性能统计失败: {e}")
            return False


# 全局SQLite扩展管理器实例
_sqlite_extension_manager: Optional[SQLiteExtensionManager] = None
_manager_lock = threading.Lock()


def get_sqlite_extension_manager(db_path: str = "data/factorweave_system.sqlite") -> SQLiteExtensionManager:
    """获取全局SQLite扩展管理器实例"""
    global _sqlite_extension_manager

    with _manager_lock:
        if _sqlite_extension_manager is None:
            _sqlite_extension_manager = SQLiteExtensionManager()
        return _sqlite_extension_manager
