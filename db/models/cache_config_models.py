import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from loguru import logger
from core.database.unified_sqlite_access import UnifiedSQLiteAccess


class CacheConfigManager:
    """缓存配置管理器 - 负责缓存配置的持久化和加载"""

    def __init__(self, db_path: str = "data/factorweave_system.sqlite"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()

    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)

    def _init_database(self):
        """初始化数据库表"""
        db = UnifiedSQLiteAccess.get_instance(self.db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建缓存配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_name TEXT NOT NULL UNIQUE,
                    strategy TEXT DEFAULT 'LRU',
                    max_size INTEGER DEFAULT 1000,
                    max_memory_mb INTEGER DEFAULT 100,
                    max_disk_mb INTEGER DEFAULT 1000,
                    default_ttl_minutes INTEGER DEFAULT 30,
                    cleanup_interval_minutes INTEGER DEFAULT 10,
                    enable_compression BOOLEAN DEFAULT 0,
                    enable_statistics BOOLEAN DEFAULT 1,
                    enable_adaptive BOOLEAN DEFAULT 1,
                    hit_rate_threshold REAL DEFAULT 0.7,
                    adjustment_interval INTEGER DEFAULT 300,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            
            # 创建命名空间配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_namespace_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL UNIQUE,
                    max_size INTEGER DEFAULT 100,
                    priority TEXT DEFAULT 'MEDIUM',
                    ttl_minutes INTEGER DEFAULT 30,
                    strategy TEXT DEFAULT 'LRU',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # 创建配置历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_config_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_name TEXT NOT NULL,
                    old_config TEXT,
                    new_config TEXT NOT NULL,
                    changed_by TEXT DEFAULT 'system',
                    changed_at TEXT NOT NULL,
                    operation TEXT NOT NULL
                )
            """)
            
            # 插入默认配置（如果不存在）
            cursor.execute("SELECT COUNT(*) FROM cache_config WHERE config_name = 'default'")
            if cursor.fetchone()[0] == 0:
                current_time = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO cache_config (
                        config_name, strategy, max_size, max_memory_mb, max_disk_mb,
                        default_ttl_minutes, cleanup_interval_minutes, enable_compression,
                        enable_statistics, enable_adaptive, hit_rate_threshold,
                        adjustment_interval, created_at, updated_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'default', 'LRU', 1000, 100, 1000, 30, 10, 0, 1, 1,
                    0.7, 300, current_time, current_time, 1
                ))
            
            logger.info("缓存配置数据库初始化完成")

    def get_config(self, config_name: str = 'default') -> Optional[Dict[str, Any]]:
        """获取缓存配置"""
        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT * FROM cache_config WHERE config_name = ? AND is_active = 1",
                    (config_name,)
                )
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"获取缓存配置失败: {e}")
            return None

    def save_config(self, config: Dict[str, Any], config_name: str = 'default', 
                    changed_by: str = "user") -> bool:
        """保存缓存配置"""
        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取旧配置
                cursor.execute(
                    "SELECT * FROM cache_config WHERE config_name = ?",
                    (config_name,)
                )
                old_row = cursor.fetchone()
                
                current_time = datetime.now().isoformat()
                
                if old_row:
                    # 记录历史
                    old_config = {
                        'strategy': old_row[1],
                        'max_size': old_row[2],
                        'max_memory_mb': old_row[3],
                        'max_disk_mb': old_row[4],
                        'default_ttl_minutes': old_row[5],
                        'cleanup_interval_minutes': old_row[6],
                        'enable_compression': bool(old_row[7]),
                        'enable_statistics': bool(old_row[8]),
                        'enable_adaptive': bool(old_row[9]),
                        'hit_rate_threshold': old_row[10],
                        'adjustment_interval': old_row[11]
                    }
                    
                    cursor.execute("""
                        INSERT INTO cache_config_history 
                        (config_name, old_config, new_config, changed_by, changed_at, operation)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        config_name, 
                        json.dumps(old_config, ensure_ascii=False),
                        json.dumps(config, ensure_ascii=False),
                        changed_by,
                        current_time,
                        'update'
                    ))
                    
                    # 更新配置
                    cursor.execute("""
                        UPDATE cache_config SET
                            strategy = ?,
                            max_size = ?,
                            max_memory_mb = ?,
                            max_disk_mb = ?,
                            default_ttl_minutes = ?,
                            cleanup_interval_minutes = ?,
                            enable_compression = ?,
                            enable_statistics = ?,
                            enable_adaptive = ?,
                            hit_rate_threshold = ?,
                            adjustment_interval = ?,
                            updated_at = ?
                        WHERE config_name = ?
                    """, (
                        config.get('strategy', 'LRU'),
                        config.get('max_size', 1000),
                        config.get('max_memory_mb', 100),
                        config.get('max_disk_mb', 1000),
                        config.get('default_ttl_minutes', 30),
                        config.get('cleanup_interval_minutes', 10),
                        int(config.get('enable_compression', False)),
                        int(config.get('enable_statistics', True)),
                        int(config.get('enable_adaptive', True)),
                        config.get('hit_rate_threshold', 0.7),
                        config.get('adjustment_interval', 300),
                        current_time,
                        config_name
                    ))
                else:
                    # 插入新配置
                    cursor.execute("""
                        INSERT INTO cache_config (
                            config_name, strategy, max_size, max_memory_mb, max_disk_mb,
                            default_ttl_minutes, cleanup_interval_minutes, enable_compression,
                            enable_statistics, enable_adaptive, hit_rate_threshold,
                            adjustment_interval, created_at, updated_at, is_active
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        config_name,
                        config.get('strategy', 'LRU'),
                        config.get('max_size', 1000),
                        config.get('max_memory_mb', 100),
                        config.get('max_disk_mb', 1000),
                        config.get('default_ttl_minutes', 30),
                        config.get('cleanup_interval_minutes', 10),
                        int(config.get('enable_compression', False)),
                        int(config.get('enable_statistics', True)),
                        int(config.get('enable_adaptive', True)),
                        config.get('hit_rate_threshold', 0.7),
                        config.get('adjustment_interval', 300),
                        current_time,
                        current_time,
                        1
                    ))
                
                logger.info(f"缓存配置已保存: {config_name}")
                return True
                
        except Exception as e:
            logger.error(f"保存缓存配置失败: {e}")
            return False

    def get_namespace_config(self, namespace: str) -> Optional[Dict[str, Any]]:
        """获取命名空间配置"""
        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT * FROM cache_namespace_config WHERE namespace = ?",
                    (namespace,)
                )
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"获取命名空间配置失败: {e}")
            return None

    def save_namespace_config(self, namespace: str, config: Dict[str, Any]) -> bool:
        """保存命名空间配置"""
        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                current_time = datetime.now().isoformat()
                
                cursor.execute(
                    "SELECT * FROM cache_namespace_config WHERE namespace = ?",
                    (namespace,)
                )
                
                if cursor.fetchone():
                    cursor.execute("""
                        UPDATE cache_namespace_config SET
                            max_size = ?,
                            priority = ?,
                            ttl_minutes = ?,
                            strategy = ?,
                            updated_at = ?
                        WHERE namespace = ?
                    """, (
                        config.get('max_size', 100),
                        config.get('priority', 'MEDIUM'),
                        config.get('ttl_minutes', 30),
                        config.get('strategy', 'LRU'),
                        current_time,
                        namespace
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO cache_namespace_config (
                            namespace, max_size, priority, ttl_minutes, strategy,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        namespace,
                        config.get('max_size', 100),
                        config.get('priority', 'MEDIUM'),
                        config.get('ttl_minutes', 30),
                        config.get('strategy', 'LRU'),
                        current_time,
                        current_time
                    ))
                
                logger.info(f"命名空间配置已保存: {namespace}")
                return True
                
        except Exception as e:
            logger.error(f"保存命名空间配置失败: {e}")
            return False

    def list_namespaces(self) -> List[str]:
        """列出所有已配置的命名空间"""
        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT namespace FROM cache_namespace_config")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"列出命名空间失败: {e}")
            return []

    def get_config_history(self, config_name: str = 'default', 
                          limit: int = 10) -> List[Dict[str, Any]]:
        """获取配置历史"""
        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM cache_config_history 
                    WHERE config_name = ?
                    ORDER BY changed_at DESC
                    LIMIT ?
                """, (config_name, limit))
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"获取配置历史失败: {e}")
            return []

    def reset_to_default(self, config_name: str = 'default') -> bool:
        """重置为默认配置"""
        default_config = {
            'strategy': 'LRU',
            'max_size': 1000,
            'max_memory_mb': 100,
            'max_disk_mb': 1000,
            'default_ttl_minutes': 30,
            'cleanup_interval_minutes': 10,
            'enable_compression': False,
            'enable_statistics': True,
            'enable_adaptive': True,
            'hit_rate_threshold': 0.7,
            'adjustment_interval': 300
        }
        return self.save_config(default_config, config_name, 'system')
