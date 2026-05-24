"""
统一数据库访问工具
用于替换各模块中直接使用 sqlite3.connect() 的情况

提供:
- 单例模式，避免重复连接
- 自动启用 WAL 模式（Write-Ahead Logging）
- 启用外键约束（PRAGMA foreign_keys=ON）
- 线程安全的连接管理
- 自动事务管理
- 性能优化配置
"""
import sqlite3
import re
import threading
from typing import Optional, Generator, Any, List, Dict
from contextlib import contextmanager
from loguru import logger


_SAFE_TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_table_name(table_name: str) -> str:
    """校验表名，防止SQL注入"""
    if not _SAFE_TABLE_NAME_PATTERN.match(table_name):
        raise ValueError(f"非法的表名: '{table_name}'，只允许字母、数字和下划线，且不能以数字开头")
    return table_name


class UnifiedSQLiteAccess:
    """
    统一 SQLite 访问工具
    
    提供:
    - 单例模式，避免重复连接
    - 自动启用 WAL 模式
    - 启用外键约束（默认开启）
    - 线程安全
    - 自动事务管理
    """
    
    _instances: Dict[str, 'UnifiedSQLiteAccess'] = {}
    _lock = threading.Lock()
    
    def __init__(self, db_path: str, enable_foreign_keys: bool = True):
        self.db_path = db_path
        self.enable_foreign_keys = enable_foreign_keys
        self._local = threading.local()
        self._config = {
            'timeout': 30.0,
            'check_same_thread': False,
            'journal_mode': 'WAL',
            'synchronous': 'NORMAL',
            'cache_size': -64000,  # 64MB 缓存（负值表示 KB）
            'temp_store': 'MEMORY',
            'mmap_size': 268435456,  # 256MB 内存映射
            'foreign_keys': enable_foreign_keys,
            'busy_timeout': 5000,
        }
    
    @classmethod
    def get_instance(cls, db_path: str, enable_foreign_keys: bool = True) -> 'UnifiedSQLiteAccess':
        """获取单例实例（线程安全）"""
        if db_path not in cls._instances:
            with cls._lock:
                if db_path not in cls._instances:
                    cls._instances[db_path] = cls(db_path, enable_foreign_keys)
        return cls._instances[db_path]
    
    @classmethod
    def get_all_instances(cls) -> Dict[str, 'UnifiedSQLiteAccess']:
        """获取所有实例"""
        return cls._instances.copy()
    
    def _configure_connection(self, conn: sqlite3.Connection):
        """配置连接参数（启用WAL、外键、性能优化）"""
        try:
            conn.execute(f"PRAGMA journal_mode={self._config['journal_mode']}")
            conn.execute(f"PRAGMA synchronous={self._config['synchronous']}")
            conn.execute(f"PRAGMA cache_size={self._config['cache_size']}")
            conn.execute(f"PRAGMA temp_store={self._config['temp_store']}")
            conn.execute(f"PRAGMA mmap_size={self._config['mmap_size']}")
            conn.execute(f"PRAGMA busy_timeout={self._config['busy_timeout']}")
            
            if self.enable_foreign_keys:
                conn.execute("PRAGMA foreign_keys=ON")
                foreign_keys_status = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                if foreign_keys_status != 1:
                    logger.warning(f"外键约束未成功启用: {self.db_path}")
            
            conn.row_factory = sqlite3.Row
        except Exception as e:
            logger.error(f"配置数据库连接失败: {self.db_path} - {e}")
            raise
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接（自动管理事务、线程安全、连接复用）"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self._config['timeout'],
                check_same_thread=self._config['check_same_thread']
            )
            self._configure_connection(conn)
            self._local.conn = conn
        else:
            conn = self._local.conn
        
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库事务执行失败: {self.db_path} - {e}")
            raise
    
    def execute(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        """执行查询（只读操作）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()
    
    def execute_write(self, sql: str, params: tuple = ()) -> int:
        """执行写入（自动开启事务）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.rowcount
    
    def close_connection(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception as e:
                logger.warning(f"关闭数据库连接异常: {self.db_path} - {e}")
            finally:
                self._local.conn = None
    
    @classmethod
    def close_all_connections(cls):
        """关闭所有实例的所有连接"""
        for instance in cls._instances.values():
            instance.close_connection()
    
    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行（自动开启事务）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            return cursor.rowcount
    
    def execute_in_transaction(self, operations: List[tuple]) -> int:
        """在单个事务中执行多个操作（批量写入优化）"""
        total_affected = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for sql, params in operations:
                cursor.execute(sql, params)
                total_affected += cursor.rowcount
        return total_affected
    
    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            return cursor.fetchone() is not None
    
    def get_table_count(self, table_name: str) -> int:
        """获取表记录数"""
        _validate_table_name(table_name)
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]
    
    def check_foreign_keys_enabled(self) -> bool:
        """检查外键约束是否启用"""
        try:
            with self.get_connection() as conn:
                result = conn.execute("PRAGMA foreign_keys").fetchone()
                return result[0] == 1
        except Exception as e:
            logger.error(f"检查外键约束状态失败: {self.db_path} - {e}")
            return False
    
    def get_foreign_key_violations(self) -> List[Dict[str, Any]]:
        """获取外键违反情况"""
        violations = []
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("PRAGMA foreign_key_check")
                for row in cursor.fetchall():
                    violations.append({
                        'table': row[0],
                        'rowid': row[1],
                        'parent_table': row[2],
                        'fk_index': row[3]
                    })
        except Exception as e:
            logger.error(f"检查外键违反情况失败: {self.db_path} - {e}")
        return violations
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        info = {}
        try:
            with self.get_connection() as conn:
                info['journal_mode'] = conn.execute("PRAGMA journal_mode").fetchone()[0]
                info['synchronous'] = conn.execute("PRAGMA synchronous").fetchone()[0]
                info['foreign_keys'] = conn.execute("PRAGMA foreign_keys").fetchone()[0]
                info['cache_size'] = conn.execute("PRAGMA cache_size").fetchone()[0]
                info['page_count'] = conn.execute("PRAGMA page_count").fetchone()[0]
                info['page_size'] = conn.execute("PRAGMA page_size").fetchone()[0]
                info['db_size_bytes'] = info['page_count'] * info['page_size']
        except Exception as e:
            logger.error(f"获取数据库信息失败: {self.db_path} - {e}")
        return info


def get_db(db_path: str, enable_foreign_keys: bool = True) -> UnifiedSQLiteAccess:
    """便捷函数：获取统一数据库访问实例"""
    return UnifiedSQLiteAccess.get_instance(db_path, enable_foreign_keys)


def execute_query(db_path: str, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    """便捷函数：执行查询"""
    db = UnifiedSQLiteAccess.get_instance(db_path)
    return db.execute(sql, params)


def execute_write(db_path: str, sql: str, params: tuple = ()) -> int:
    """便捷函数：执行写入"""
    db = UnifiedSQLiteAccess.get_instance(db_path)
    return db.execute_write(sql, params)
