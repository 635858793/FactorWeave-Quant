from loguru import logger
"""
FactorWeave-Quant 插件管理数据库模型

专业级插件管理系统，支持：
- 插件注册与生命周期管理
- 状态持久化存储
- 依赖关系管理
- 配置版本控制
- 远程管理支持
- 性能监控数据
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

import sys
from pathlib import Path as PathLib
project_root = PathLib(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.enums import PluginStatus
from core.plugin_types import PluginType
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

logger = logger


@dataclass
class PluginRecord:
    """插件记录数据类"""
    id: Optional[int] = None
    name: str = ""
    display_name: str = ""
    version: str = "1.0.0"
    plugin_type: str = PluginType.ANALYSIS.value
    status: str = PluginStatus.UNLOADED.value
    description: str = ""
    author: str = ""
    email: str = ""
    homepage: str = ""
    repository: str = ""
    license: str = "MIT"
    tags: str = ""  # JSON array
    install_path: str = ""
    entry_point: str = ""
    config_schema: str = "{}"  # JSON schema
    dependencies: str = "[]"  # JSON array
    compatibility: str = "{}"  # JSON object
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_enabled_at: Optional[str] = None
    install_size: int = 0
    checksum: str = ""
    remote_url: str = ""
    auto_update: bool = False
    priority: int = 100


class PluginDatabaseManager:
    """插件数据库管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db = UnifiedSQLiteAccess.get_instance(db_path)
        self.init_database()

    def init_database(self):
        """初始化插件相关数据库表"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 1. 插件注册表 - 核心插件信息
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,  -- 插件唯一标识符
                    display_name TEXT NOT NULL,  -- 显示名称
                    version TEXT NOT NULL DEFAULT '1.0.0',
                    plugin_type TEXT NOT NULL DEFAULT 'analysis',
                    status TEXT NOT NULL DEFAULT 'unloaded',
                    description TEXT DEFAULT '',
                    author TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    homepage TEXT DEFAULT '',
                    repository TEXT DEFAULT '',
                    license TEXT DEFAULT 'MIT',
                    tags TEXT DEFAULT '[]',  -- JSON数组: ["AI", "量化", "技术分析"]
                    install_path TEXT DEFAULT '',
                    entry_point TEXT DEFAULT '',  -- 入口点: module.class
                    config_schema TEXT DEFAULT '{}',  -- JSON配置模式
                    dependencies TEXT DEFAULT '[]',  -- JSON依赖数组
                    compatibility TEXT DEFAULT '{}',  -- 兼容性信息
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_enabled_at TIMESTAMP,
                    install_size INTEGER DEFAULT 0,
                    checksum TEXT DEFAULT '',  -- 文件校验和
                    remote_url TEXT DEFAULT '',  -- 远程更新URL
                    auto_update BOOLEAN DEFAULT 0,
                    priority INTEGER DEFAULT 100  -- 加载优先级
                )''')

                # 2. 迁移调整：删除插件状态历史表（合并入 plugins 表的 status 字段）
                cursor.execute('DROP TABLE IF EXISTS plugin_status_history')

                # 3. 插件配置表 - 动态配置存储
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugin_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id INTEGER NOT NULL,
                    config_key TEXT NOT NULL,
                    config_value TEXT NOT NULL,  -- JSON值
                    config_type TEXT DEFAULT 'user',  -- user/system/default
                    version INTEGER DEFAULT 1,
                    description TEXT DEFAULT '',
                    is_encrypted BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plugin_id) REFERENCES plugins (id) ON DELETE CASCADE,
                    UNIQUE(plugin_id, config_key, config_type)
                )''')

                # 4. 插件依赖关系表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugin_dependencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id INTEGER NOT NULL,
                    dependency_name TEXT NOT NULL,  -- 依赖名称
                    dependency_version TEXT DEFAULT '*',  -- 版本约束
                    dependency_type TEXT DEFAULT 'required',  -- required/optional
                    resolved_version TEXT DEFAULT '',  -- 实际解析版本
                    is_satisfied BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plugin_id) REFERENCES plugins (id) ON DELETE CASCADE
                )''')

                # 5. 插件性能监控表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugin_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id INTEGER NOT NULL,
                    metric_name TEXT NOT NULL,  -- load_time/memory_usage/cpu_usage/error_count
                    metric_value REAL NOT NULL,
                    metric_unit TEXT DEFAULT '',  -- ms/MB/%/count
                    measurement_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    session_id TEXT DEFAULT '',  -- 会话标识
                    additional_data TEXT DEFAULT '{}',  -- 额外数据JSON
                    FOREIGN KEY (plugin_id) REFERENCES plugins (id) ON DELETE CASCADE
                )''')

                # 6. 插件事件日志表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugin_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id INTEGER,
                    event_type TEXT NOT NULL,  -- load/enable/disable/error/config_change
                    event_level TEXT DEFAULT 'INFO',  -- DEBUG/INFO/WARNING/ERROR
                    event_message TEXT NOT NULL,
                    event_data TEXT DEFAULT '{}',  -- 事件详细数据JSON
                    user_agent TEXT DEFAULT '',  -- 客户端标识
                    session_id TEXT DEFAULT '',
                    ip_address TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plugin_id) REFERENCES plugins (id) ON DELETE SET NULL
                )''')

                # 7. 插件权限表 - 远程管理支持
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugin_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id INTEGER NOT NULL,
                    permission_name TEXT NOT NULL,  -- file_access/network_access/system_access
                    permission_level TEXT DEFAULT 'read',  -- read/write/execute
                    granted_by TEXT DEFAULT 'system',
                    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (plugin_id) REFERENCES plugins (id) ON DELETE CASCADE,
                    UNIQUE(plugin_id, permission_name)
                )''')

                # 8. 插件市场缓存表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugin_market_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_name TEXT NOT NULL,
                    market_data TEXT NOT NULL,  -- JSON市场信息
                    downloads_count INTEGER DEFAULT 0,
                    rating REAL DEFAULT 0.0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cache_expires_at TIMESTAMP,
                    UNIQUE(plugin_name)
                )''')

                # 创建索引优化查询性能
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plugins_status ON plugins(status)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plugins_type ON plugins(plugin_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plugins_priority ON plugins(priority)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plugin_events_type ON plugin_events(event_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plugin_performance_metric ON plugin_performance(metric_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_plugin_configs_type ON plugin_configs(config_type)')

            logger.info("插件数据库表初始化完成")

        except Exception as e:
            logger.error(f"初始化插件数据库失败: {e}")
            raise

    def register_plugin(self, plugin_record: PluginRecord) -> int:
        """注册插件到数据库"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 检查是否已存在记录
                cursor.execute('SELECT id, status FROM plugins WHERE name = ?', (plugin_record.name,))
                row = cursor.fetchone()

                if row:
                    # 已存在：仅更新元信息，保留原有状态不覆盖
                    plugin_id, existing_status = row
                    cursor.execute('''
                        UPDATE plugins
                        SET display_name = ?, version = ?, plugin_type = ?, description = ?,
                            author = ?, email = ?, homepage = ?, repository = ?, license = ?, tags = ?,
                            install_path = ?, entry_point = ?, config_schema = ?, dependencies = ?,
                            compatibility = ?, install_size = ?, checksum = ?, remote_url = ?,
                            auto_update = ?, priority = ?, updated_at = ?
                        WHERE name = ?
                    ''', (
                        plugin_record.display_name, plugin_record.version, plugin_record.plugin_type,
                        plugin_record.description, plugin_record.author, plugin_record.email,
                        plugin_record.homepage, plugin_record.repository, plugin_record.license,
                        plugin_record.tags, plugin_record.install_path, plugin_record.entry_point,
                        plugin_record.config_schema, plugin_record.dependencies,
                        plugin_record.compatibility, plugin_record.install_size,
                        plugin_record.checksum, plugin_record.remote_url,
                        plugin_record.auto_update, plugin_record.priority,
                        datetime.now().isoformat(), plugin_record.name
                    ))
                    logger.info(f"插件已存在，更新元信息并保留状态 {existing_status}: {plugin_record.name} (ID: {plugin_id})")
                    return plugin_id
                else:
                    # 不存在：插入新记录，使用传入的状态
                    cursor.execute('''
                        INSERT INTO plugins (
                            name, display_name, version, plugin_type, status, description,
                            author, email, homepage, repository, license, tags,
                            install_path, entry_point, config_schema, dependencies,
                            compatibility, install_size, checksum, remote_url,
                            auto_update, priority, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        plugin_record.name, plugin_record.display_name, plugin_record.version,
                        plugin_record.plugin_type, plugin_record.status, plugin_record.description,
                        plugin_record.author, plugin_record.email, plugin_record.homepage,
                        plugin_record.repository, plugin_record.license, plugin_record.tags,
                        plugin_record.install_path, plugin_record.entry_point,
                        plugin_record.config_schema, plugin_record.dependencies,
                        plugin_record.compatibility, plugin_record.install_size,
                        plugin_record.checksum, plugin_record.remote_url,
                        plugin_record.auto_update, plugin_record.priority,
                        datetime.now().isoformat()
                    ))
                    plugin_id = cursor.lastrowid
                    logger.info(f"插件注册成功: {plugin_record.name} (ID: {plugin_id})")
                    return plugin_id

        except Exception as e:
            logger.error(f"注册插件失败: {e}")
            raise

    def update_plugin_status(self, plugin_name: str, new_status: PluginStatus,
                             reason: str = "", error_message: str = "") -> bool:
        """更新插件状态"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 获取当前状态
                cursor.execute('SELECT id, status FROM plugins WHERE name = ?', (plugin_name,))
                result = cursor.fetchone()

                if not result:
                    logger.warning(f"插件不存在: {plugin_name}")
                    return False

                plugin_id, old_status = result
                new_status_str = new_status.value

                # 更新插件状态
                update_fields = ['status = ?', 'updated_at = ?']
                update_values = [new_status_str, datetime.now().isoformat()]

                if new_status == PluginStatus.ENABLED:
                    update_fields.append('last_enabled_at = ?')
                    update_values.append(datetime.now().isoformat())

                cursor.execute(f'''
                    UPDATE plugins 
                    SET {', '.join(update_fields)}
                    WHERE name = ?
                ''', update_values + [plugin_name])

                # 记录事件日志
                cursor.execute('''
                    INSERT INTO plugin_events (
                        plugin_id, event_type, event_level, event_message, event_data
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    plugin_id, 'status_change', 'INFO',
                    f"状态从 {old_status} 变更为 {new_status_str}",
                    json.dumps({"old_status": old_status, "new_status": new_status_str, "reason": reason})
                ))

            logger.info(f"插件状态更新成功: {plugin_name} -> {new_status_str}")
            return True

        except Exception as e:
            logger.error(f"更新插件状态失败: {e}")
            return False

    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """获取插件状态"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT status FROM plugins WHERE name = ?', (plugin_name,))
                result = cursor.fetchone()

            if result:
                return PluginStatus(result[0])
            return None

        except Exception as e:
            logger.error(f"获取插件状态失败: {e}")
            return None

    def get_all_plugins(self) -> List[PluginRecord]:
        """获取所有插件信息"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT id, name, display_name, version, plugin_type, status, description,
                           author, email, homepage, repository, license, tags, install_path,
                           entry_point, created_at, updated_at, last_enabled_at, priority
                    FROM plugins 
                    ORDER BY priority ASC, name ASC
                ''')

                columns = [desc[0] for desc in cursor.description]
                plugins = []

                for row in cursor.fetchall():
                    plugin_dict = dict(zip(columns, row))
                    try:
                        plugin_dict['tags'] = json.loads(plugin_dict['tags'] or '[]')
                    except Exception:
                        plugin_dict['tags'] = []

                    plugin_record = PluginRecord(
                        id=plugin_dict.get('id'),
                        name=plugin_dict.get('name', ''),
                        display_name=plugin_dict.get('display_name', ''),
                        version=plugin_dict.get('version', '1.0.0'),
                        plugin_type=plugin_dict.get('plugin_type', PluginType.ANALYSIS.value),
                        status=plugin_dict.get('status', PluginStatus.UNLOADED.value),
                        description=plugin_dict.get('description', ''),
                        author=plugin_dict.get('author', ''),
                        email=plugin_dict.get('email', ''),
                        homepage=plugin_dict.get('homepage', ''),
                        repository=plugin_dict.get('repository', ''),
                        license=plugin_dict.get('license', 'MIT'),
                        tags=json.dumps(plugin_dict.get('tags', [])),
                        install_path=plugin_dict.get('install_path', ''),
                        entry_point=plugin_dict.get('entry_point', ''),
                        created_at=plugin_dict.get('created_at'),
                        updated_at=plugin_dict.get('updated_at'),
                        last_enabled_at=plugin_dict.get('last_enabled_at'),
                        priority=plugin_dict.get('priority', 100)
                    )
                    plugins.append(plugin_record)

            return plugins

        except Exception as e:
            logger.error(f"获取所有插件信息失败: {e}")
            return []

    def get_plugins_by_status(self, status: PluginStatus) -> List[Dict[str, Any]]:
        """根据状态获取插件列表"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT name, display_name, version, plugin_type, status, description, author
                    FROM plugins 
                    WHERE status = ?
                    ORDER BY priority ASC, name ASC
                ''', (status.value,))

                columns = [desc[0] for desc in cursor.description]
                plugins = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return plugins

        except Exception as e:
            logger.error(f"根据状态获取插件失败: {e}")
            return []

    def get_plugin_performance_metrics(self, plugin_name: str,
                                       metric_name: str = None,
                                       limit: int = 100) -> List[Dict[str, Any]]:
        """获取插件性能指标"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                base_query = '''
                    SELECT pm.metric_name, pm.metric_value, pm.metric_unit, 
                           pm.measurement_time, pm.additional_data
                    FROM plugin_performance pm
                    JOIN plugins p ON pm.plugin_id = p.id
                    WHERE p.name = ?
                '''

                params = [plugin_name]

                if metric_name:
                    base_query += ' AND pm.metric_name = ?'
                    params.append(metric_name)

                base_query += ' ORDER BY pm.measurement_time DESC LIMIT ?'
                params.append(limit)

                cursor.execute(base_query, params)

                columns = [desc[0] for desc in cursor.description]
                metrics = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return metrics

        except Exception as e:
            logger.error(f"获取插件性能指标失败: {e}")
            return []

    def record_plugin_performance(self, plugin_name: str, metric_name: str,
                                  metric_value: float, metric_unit: str = "",
                                  additional_data: Dict[str, Any] = None) -> bool:
        """记录插件性能指标"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT id FROM plugins WHERE name = ?', (plugin_name,))
                result = cursor.fetchone()

                if not result:
                    return False

                plugin_id = result[0]

                cursor.execute('''
                    INSERT INTO plugin_performance (
                        plugin_id, metric_name, metric_value, metric_unit, additional_data
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    plugin_id, metric_name, metric_value, metric_unit,
                    json.dumps(additional_data or {})
                ))

            return True

        except Exception as e:
            logger.error(f"记录插件性能指标失败: {e}")
            return False

    def delete_plugin(self, plugin_name: str) -> bool:
        """
        删除插件及其相关记录

        Args:
            plugin_name: 插件名称

        Returns:
            bool: 是否删除成功
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 先获取插件ID
                cursor.execute('SELECT id FROM plugins WHERE name = ?', (plugin_name,))
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"插件 {plugin_name} 不存在于数据库中")
                    return True  # 不存在也算成功

                plugin_id = row[0]

                # 删除相关的性能记录
                cursor.execute('DELETE FROM plugin_performance WHERE plugin_id = ?', (plugin_id,))
                performance_deleted = cursor.rowcount

                # 删除相关的事件日志
                cursor.execute('DELETE FROM plugin_events WHERE plugin_id = ?', (plugin_id,))
                events_deleted = cursor.rowcount

                # 删除插件状态历史（已不再使用，此处兼容清理）
                history_deleted = 0

                # 最后删除插件记录
                cursor.execute('DELETE FROM plugins WHERE id = ?', (plugin_id,))

                if cursor.rowcount == 0:
                    logger.error(f"删除插件记录失败: {plugin_name}")
                    conn.rollback()
                    return False

            logger.info(f"插件 {plugin_name} 已完全删除: "
                        f"性能记录 {performance_deleted} 条, "
                        f"事件日志 {events_deleted} 条, "
                        f"状态历史 {history_deleted} 条")
            return True

        except Exception as e:
            logger.error(f"删除插件失败: {plugin_name}, 错误: {e}")
            return False

    def cleanup_old_records(self, days: int = 30) -> bool:
        """清理旧记录"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cutoff_date = datetime.now().replace(day=datetime.now().day - days).isoformat()

                # 清理旧的性能记录
                cursor.execute('''
                    DELETE FROM plugin_performance 
                    WHERE measurement_time < ?
                ''', (cutoff_date,))

                # 清理旧的事件日志
                cursor.execute('''
                    DELETE FROM plugin_events 
                    WHERE created_at < ? AND event_level != 'ERROR'
                ''', (cutoff_date,))

                deleted_performance = cursor.rowcount

            logger.info(f"清理旧记录完成，删除 {deleted_performance} 条性能记录")
            return True

        except Exception as e:
            logger.error(f"清理旧记录失败: {e}")
            return False

    def get_or_create_plugin_id(self, plugin_name: str) -> Optional[int]:
        """根据插件名称获取ID，不存在则返回None。"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT id FROM plugins WHERE name = ?', (plugin_name,))
                row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"查询插件ID失败: {plugin_name}, 错误: {e}")
            return None

    def save_unified_plugin_config(self, plugin_name: str, config: Dict[str, Any],
                                   config_type: str = 'user', description: str = '') -> bool:
        """
        保存插件统一配置JSON（单条记录，key 固定为 'config'）。
        若记录已存在则替换。
        """
        try:
            plugin_id = self.get_or_create_plugin_id(plugin_name)
            if plugin_id is None:
                logger.warning(f"保存配置前未找到插件: {plugin_name}")
                return False

            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                config_json = json.dumps(config, ensure_ascii=False)
                current_time = datetime.now().isoformat()

                cursor.execute('''
                INSERT OR REPLACE INTO plugin_configs (
                    id, plugin_id, config_key, config_value, config_type, version, description, updated_at
                )
                VALUES (
                    COALESCE((SELECT id FROM plugin_configs WHERE plugin_id = ? AND config_key = 'config' AND config_type = ?), NULL),
                    ?, 'config', ?, ?,
                    COALESCE((SELECT version FROM plugin_configs WHERE plugin_id = ? AND config_key = 'config' AND config_type = ?) + 1, 1),
                    ?, ?
                )
                ''', (
                    plugin_id, config_type,  # for COALESCE id
                    plugin_id, config_json, config_type,  # insert values
                    plugin_id, config_type,  # for version increment
                    description, current_time
                ))

            logger.info(f"插件配置已保存: {plugin_name}")
            return True
        except Exception as e:
            logger.error(f"保存插件配置失败 {plugin_name}: {e}")
            return False

    def load_unified_plugin_config(self, plugin_name: str, config_type: str = 'user') -> Optional[Dict[str, Any]]:
        """读取插件统一配置JSON，按 version 最大取最新。不存在返回 None。"""
        try:
            plugin_id = self.get_or_create_plugin_id(plugin_name)
            if plugin_id is None:
                return None

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT config_value FROM plugin_configs
                WHERE plugin_id = ? AND config_key = 'config' AND config_type = ?
                ORDER BY version DESC LIMIT 1
                ''', (plugin_id, config_type))
                row = cursor.fetchone()
                if not row:
                    return None
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"读取插件配置失败 {plugin_name}: {e}")
            return None


class DataSourcePluginConfigManager:
    """数据源插件配置管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db = UnifiedSQLiteAccess.get_instance(db_path)
        self._init_data_source_tables()

    def _init_data_source_tables(self):
        """初始化数据源插件相关数据库表"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 数据源插件配置表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_source_plugin_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plugin_id TEXT NOT NULL,
                    config_data TEXT NOT NULL,  -- JSON配置数据
                    priority INTEGER DEFAULT 50,
                    weight REAL DEFAULT 1.0,
                    enabled BOOLEAN DEFAULT 1,
                    health_check_interval INTEGER DEFAULT 30,
                    timeout_seconds INTEGER DEFAULT 30,
                    retry_count INTEGER DEFAULT 3,
                    max_pool_size INTEGER DEFAULT 5,  -- 线程池最大连接数
                    pool_timeout INTEGER DEFAULT 30,  -- 连接池超时时间（秒）
                    pool_cleanup_interval INTEGER DEFAULT 300,  -- 连接池清理间隔（秒）
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(plugin_id)
                )''')

                # 数据源路由配置表
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_source_routing_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_type TEXT NOT NULL,
                    plugin_priorities TEXT NOT NULL,  -- JSON数组，存储插件优先级顺序
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(asset_type)
                )''')

        except Exception as e:
            logger.error(f"初始化数据源插件配置表失败: {e}")

    def save_plugin_config(self, plugin_id: str, config_data: dict,
                           priority: int = 50, weight: float = 1.0,
                           enabled: bool = True, max_pool_size: int = 5,
                           pool_timeout: int = 30, pool_cleanup_interval: int = 300) -> bool:
        """保存数据源插件配置"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                config_json = json.dumps(config_data, ensure_ascii=False)
                current_time = datetime.now().isoformat()

                cursor.execute('''
                INSERT OR REPLACE INTO data_source_plugin_configs 
                (plugin_id, config_data, priority, weight, enabled, max_pool_size, 
                 pool_timeout, pool_cleanup_interval, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (plugin_id, config_json, priority, weight, enabled,
                      max_pool_size, pool_timeout, pool_cleanup_interval, current_time))

                logger.info(f"数据源插件配置已保存: {plugin_id}, 线程池大小: {max_pool_size}")
                return True

        except Exception as e:
            logger.error(f"保存数据源插件配置失败 {plugin_id}: {e}")
            return False

    def get_plugin_config(self, plugin_id: str) -> Optional[dict]:
        """获取数据源插件配置"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT config_data, priority, weight, enabled, max_pool_size, 
                       pool_timeout, pool_cleanup_interval 
                FROM data_source_plugin_configs 
                WHERE plugin_id = ?
                ''', (plugin_id,))

                row = cursor.fetchone()
                if row:
                    config_data, priority, weight, enabled, max_pool_size, pool_timeout, pool_cleanup_interval = row
                    return {
                        'config_data': json.loads(config_data),
                        'priority': priority,
                        'weight': weight,
                        'enabled': enabled,
                        'max_pool_size': max_pool_size,
                        'pool_timeout': pool_timeout,
                        'pool_cleanup_interval': pool_cleanup_interval
                    }

        except Exception as e:
            logger.error(f"获取数据源插件配置失败 {plugin_id}: {e}")

        return None

    def get_all_plugin_configs(self) -> dict:
        """获取所有数据源插件配置"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT plugin_id, config_data, priority, weight, enabled, 
                       max_pool_size, pool_timeout, pool_cleanup_interval 
                FROM data_source_plugin_configs 
                WHERE enabled = 1
                ORDER BY priority ASC
                ''')

                configs = {}
                for row in cursor.fetchall():
                    plugin_id, config_data, priority, weight, enabled, max_pool_size, pool_timeout, pool_cleanup_interval = row
                    configs[plugin_id] = {
                        'config_data': json.loads(config_data),
                        'priority': priority,
                        'weight': weight,
                        'enabled': enabled,
                        'max_pool_size': max_pool_size,
                        'pool_timeout': pool_timeout,
                        'pool_cleanup_interval': pool_cleanup_interval
                    }

                return configs

        except Exception as e:
            logger.error(f"获取所有数据源插件配置失败: {e}")
            return {}

    def save_routing_config(self, asset_type: str, plugin_priorities: list) -> bool:
        """保存数据源路由配置"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                priorities_json = json.dumps(plugin_priorities, ensure_ascii=False)
                current_time = datetime.now().isoformat()

                cursor.execute('''
                INSERT OR REPLACE INTO data_source_routing_configs 
                (asset_type, plugin_priorities, updated_at)
                VALUES (?, ?, ?)
                ''', (asset_type, priorities_json, current_time))

                logger.info(f"数据源路由配置已保存: {asset_type} -> {plugin_priorities}")
                return True

        except Exception as e:
            logger.error(f"保存数据源路由配置失败 {asset_type}: {e}")
            return False

    def get_routing_config(self, asset_type: str) -> Optional[list]:
        """获取数据源路由配置"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT plugin_priorities 
                FROM data_source_routing_configs 
                WHERE asset_type = ?
                ''', (asset_type,))

                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])

        except Exception as e:
            logger.error(f"获取数据源路由配置失败 {asset_type}: {e}")

        return None

    def get_all_routing_configs(self) -> dict:
        """获取所有数据源路由配置"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                SELECT asset_type, plugin_priorities 
                FROM data_source_routing_configs
                ''')

                configs = {}
                for row in cursor.fetchall():
                    asset_type, priorities_json = row
                    configs[asset_type] = json.loads(priorities_json)

                return configs

        except Exception as e:
            logger.error(f"获取所有数据源路由配置失败: {e}")
            return {}

    def set_pool_config(self, max_pool_size: int = None, pool_timeout: int = None, pool_cleanup_interval: int = None) -> bool:
        """
        设置全局数据源实例池配置（更新所有已存在的插件配置）

        Args:
            max_pool_size: 最大连接池大小
            pool_timeout: 连接池超时时间（秒）
            pool_cleanup_interval: 连接池清理间隔（秒）

        Returns:
            bool: 是否成功保存
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()

                # 构建更新SQL，只更新非None的参数
                update_fields = []
                update_values = []

                if max_pool_size is not None:
                    update_fields.append('max_pool_size = ?')
                    update_values.append(max_pool_size)

                if pool_timeout is not None:
                    update_fields.append('pool_timeout = ?')
                    update_values.append(pool_timeout)

                if pool_cleanup_interval is not None:
                    update_fields.append('pool_cleanup_interval = ?')
                    update_values.append(pool_cleanup_interval)

                if not update_fields:
                    logger.warning("set_pool_config: 没有提供任何配置参数")
                    return False

                # 添加更新时间
                update_fields.append('updated_at = ?')
                update_values.append(current_time)

                # 更新所有已存在的插件配置
                update_sql = f'''
                    UPDATE data_source_plugin_configs 
                    SET {', '.join(update_fields)}
                    WHERE enabled = 1
                '''

                cursor.execute(update_sql, update_values)
                affected_rows = cursor.rowcount

                logger.info(f"数据源实例池配置已更新: max_pool_size={max_pool_size}, "
                            f"pool_timeout={pool_timeout}, pool_cleanup_interval={pool_cleanup_interval}, "
                            f"影响 {affected_rows} 个插件配置")
                return True

        except Exception as e:
            logger.error(f"设置数据源实例池配置失败: {e}", exc_info=True)
            return False

    def update_plugin_pool_config(self, plugin_id: str, max_pool_size: int = None,
                                  pool_timeout: int = None, pool_cleanup_interval: int = None) -> bool:
        """
        更新指定插件的实例池配置

        Args:
            plugin_id: 插件ID
            max_pool_size: 最大连接池大小
            pool_timeout: 连接池超时时间（秒）
            pool_cleanup_interval: 连接池清理间隔（秒）

        Returns:
            bool: 是否成功保存
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                current_time = datetime.now().isoformat()

                # 构建更新SQL，只更新非None的参数
                update_fields = []
                update_values = []

                if max_pool_size is not None:
                    update_fields.append('max_pool_size = ?')
                    update_values.append(max_pool_size)

                if pool_timeout is not None:
                    update_fields.append('pool_timeout = ?')
                    update_values.append(pool_timeout)

                if pool_cleanup_interval is not None:
                    update_fields.append('pool_cleanup_interval = ?')
                    update_values.append(pool_cleanup_interval)

                if not update_fields:
                    logger.warning(f"update_plugin_pool_config: 没有提供任何配置参数 (plugin_id={plugin_id})")
                    return False

                # 添加更新时间
                update_fields.append('updated_at = ?')
                update_values.append(current_time)

                # 添加WHERE条件参数
                update_values.append(plugin_id)

                # 更新指定插件的配置
                update_sql = f'''
                    UPDATE data_source_plugin_configs 
                    SET {', '.join(update_fields)}
                    WHERE plugin_id = ?
                '''

                cursor.execute(update_sql, update_values)

                logger.info(f"插件 {plugin_id} 的实例池配置已更新: max_pool_size={max_pool_size}, "
                            f"pool_timeout={pool_timeout}, pool_cleanup_interval={pool_cleanup_interval}")
                return True

        except Exception as e:
            logger.error(f"更新插件 {plugin_id} 的实例池配置失败: {e}", exc_info=True)
            return False


# 全局配置管理器实例
_data_source_config_manager = None


def get_data_source_config_manager(db_path: str = "data/factorweave_system.sqlite") -> DataSourcePluginConfigManager:
    """获取数据源插件配置管理器实例"""
    global _data_source_config_manager
    if _data_source_config_manager is None:
        _data_source_config_manager = DataSourcePluginConfigManager(db_path)
    return _data_source_config_manager
