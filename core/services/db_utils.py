"""
SQLite数据库连接配置工具

提供统一的数据库连接配置函数，包括：
- WAL（Write-Ahead Logging）模式
- 外键约束
- 性能优化参数

所有服务文件应使用 configure_connection() 来配置新建的SQLite连接。

版本: 1.0
作者: FactorWeave-Quant Team
日期: 2025-01-27
"""

import sqlite3
from typing import Optional

def configure_connection(conn: sqlite3.Connection) -> None:
    """
    配置数据库连接（WAL、外键、性能优化）
    
    在创建任何SQLite连接后调用此函数，以确保：
    1. WAL模式启用（提高并发性能）
    2. 外键约束启用（保证数据完整性）
    3. 同步模式优化（平衡性能和安全性）
    4. 缓存大小优化
    5. 忙等待超时设置

    Args:
        conn: SQLite连接对象
    """
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA busy_timeout=5000")

def create_configured_connection(db_path: str, check_same_thread: bool = False) -> sqlite3.Connection:
    """
    创建并配置SQLite连接的一站式函数

    Args:
        db_path: 数据库文件路径
        check_same_thread: 是否限制线程安全

    Returns:
        已配置的SQLite连接对象
    """
    conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
    configure_connection(conn)
    return conn
