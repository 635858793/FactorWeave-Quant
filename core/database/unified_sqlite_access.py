"""
统一数据库访问工具
用于替换各模块中直接使用 sqlite3.connect() 的情况
"""
import sqlite3
from typing import Optional, Generator, Any, List, Dict
from contextlib import contextmanager

from ..database.sqlite_extensions import get_sqlite_extension_manager


class UnifiedSQLiteAccess:
    """
    统一 SQLite 访问工具
    
    提供:
    - 单例模式，避免重复连接
    - 自动启用 WAL 模式
    - 线程安全
    - 自动事务管理
    """
    
    _instances: Dict[str, 'UnifiedSQLiteAccess'] = {}
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._config = {
            'timeout': 30.0,
            'check_same_thread': False,
            'journal_mode': 'WAL',
            'synchronous': 'NORMAL',
        }
    
    @classmethod
    def get_instance(cls, db_path: str) -> 'UnifiedSQLiteAccess':
        """获取单例实例"""
        if db_path not in cls._instances:
            cls._instances[db_path] = cls(db_path)
        return cls._instances[db_path]
    
    @classmethod
    def get_all_instances(cls) -> Dict[str, 'UnifiedSQLiteAccess']:
        """获取所有实例"""
        return cls._instances.copy()
    
    def _configure_connection(self, conn: sqlite3.Connection):
        """配置连接参数"""
        conn.execute(f"PRAGMA journal_mode={self._config['journal_mode']}")
        conn.execute(f"PRAGMA synchronous={self._config['synchronous']}")
        conn.row_factory = sqlite3.Row
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接（自动管理事务）"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self._config['timeout'],
            check_same_thread=self._config['check_same_thread']
        )
        
        try:
            self._configure_connection(conn)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def execute(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        """执行查询"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.fetchall()
    
    def execute_write(self, sql: str, params: tuple = ()) -> int:
        """执行写入"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.rowcount
    
    def execute_many(self, sql: str, params_list: List[tuple]) -> int:
        """批量执行"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            return cursor.rowcount
    
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
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            return cursor.fetchone()[0]


def get_db(db_path: str) -> UnifiedSQLiteAccess:
    """便捷函数：获取统一数据库访问实例"""
    return UnifiedSQLiteAccess.get_instance(db_path)


def execute_query(db_path: str, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
    """便捷函数：执行查询"""
    db = UnifiedSQLiteAccess.get_instance(db_path)
    return db.execute(sql, params)


def execute_write(db_path: str, sql: str, params: tuple = ()) -> int:
    """便捷函数：执行写入"""
    db = UnifiedSQLiteAccess.get_instance(db_path)
    return db.execute_write(sql, params)
