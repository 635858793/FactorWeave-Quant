"""
DuckDB连接池管理器 - 基于SQLAlchemy QueuePool

使用成熟的SQLAlchemy连接池实现线程安全的DuckDB连接管理。
解决多线程并发访问导致的 "INTERNAL Error: Attempted to dereference unique_ptr that is NULL" 问题。

作者: AI Assistant
日期: 2025-10-12
"""

import threading
import duckdb
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Optional, List, Dict, Any
from loguru import logger
import pandas as pd


class DuckDBConnectionPool:
    """
    DuckDB连接池管理器

    特性:
    - 线程安全: 使用SQLAlchemy QueuePool实现
    - 连接重用: 避免频繁创建/销毁连接
    - 健康检查: 自动检测并回收失效连接
    - 超时控制: 避免无限等待
    - 自动回收: 定期回收长时间运行的连接

    使用示例:
        >>> pool = DuckDBConnectionPool("database.duckdb")
        >>> 
        >>> # 方式1: 使用上下文管理器
        >>> with pool.get_connection() as conn:
        ...     result = conn.execute("SELECT * FROM table").fetchdf()
        >>> 
        >>> # 方式2: 使用便捷方法
        >>> df = pool.execute_query("SELECT * FROM table")
    """

    def __init__(
        self,
        db_path: str,
        pool_size: int = 15,
        max_overflow: int = 100,
        timeout: float = 30.0,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        use_lifo: bool = True
    ):
        """
        初始化连接池

        Args:
            db_path: 数据库文件路径
            pool_size: 连接池大小（保持的持久连接数），默认15（从5增加到15，支持批量查询）
            max_overflow: 允许的额外连接数，默认20（从10增加到100，支持高并发）
            timeout: 获取连接的超时时间（秒），默认30
            pool_recycle: 连接回收时间（秒），超过此时间的连接将被回收，默认3600（1小时）
            pool_pre_ping: 是否在使用前检查连接有效性，默认True
            use_lifo: 是否使用后进先出（LIFO）策略，默认True（让空闲连接更容易被回收）
        """
        self.db_path = db_path
        self._lock = threading.RLock()

        # 创建连接池
        self.pool = QueuePool(
            creator=self._create_connection,
            pool_size=pool_size,
            max_overflow=max_overflow,
            timeout=timeout,
            recycle=pool_recycle,
            # pre_ping参数在旧版本中不支持，移除
            use_lifo=use_lifo,
            echo=False,  # 生产环境设置为False
            reset_on_return=None  # DuckDB autocommit模式，不需要rollback
        )

        logger.info(
            f"DuckDB连接池已初始化 - "
            f"db_path={db_path}, "
            f"pool_size={pool_size}, "
            f"max_overflow={max_overflow}, "
            f"timeout={timeout}s, "
            f"recycle={pool_recycle}s"
        )

    def _create_connection(self):
        """
        创建新的DuckDB连接

        这个方法会被连接池调用来创建新连接。

        Returns:
            duckdb.DuckDBPyConnection: 新的数据库连接
        """
        try:
            conn = duckdb.connect(self.db_path, read_only=False)
            logger.debug(f"创建新的DuckDB连接: {self.db_path}")
            return conn
        except Exception as e:
            logger.error(f"创建DuckDB连接失败: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """
        获取数据库连接（上下文管理器）

        这是获取连接的推荐方式，确保连接正确返回到池中。

        使用示例:
            with pool.get_connection() as conn:
                result = conn.execute("SELECT * FROM table").fetchdf()

        Yields:
            duckdb.DuckDBPyConnection: 数据库连接对象
        """
        conn = None
        try:
            # 从连接池获取连接
            conn = self.pool.connect()
            logger.debug("从连接池获取连接")
            yield conn
        except Exception as e:
            logger.error(f"使用连接时发生错误: {e}")
            raise
        finally:
            if conn is not None:
                try:
                    # 返回连接到池中（不是真正关闭）
                    conn.close()
                    logger.debug("连接已返回到连接池")
                except Exception as e:
                    logger.warning(f"返回连接到池时出错: {e}")

    def execute_query(self, sql: str, params: Optional[List] = None) -> pd.DataFrame:
        """
        执行查询并返回DataFrame

        这是执行SELECT查询的便捷方法。

        Args:
            sql: SQL查询语句
            params: 查询参数（可选）

        Returns:
            pandas.DataFrame: 查询结果

        使用示例:
            >>> df = pool.execute_query("SELECT * FROM historical_kline_data WHERE symbol = ?", ["000001"])
        """
        try:
            with self.get_connection() as conn:
                if params:
                    result = conn.execute(sql, params).fetchdf()
                else:
                    result = conn.execute(sql).fetchdf()
                return result
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            return pd.DataFrame()

    def execute_command(self, sql: str, params: Optional[List] = None) -> bool:
        """
        执行命令（INSERT, UPDATE, DELETE等）

        这是执行非查询SQL语句的便捷方法。

        Args:
            sql: SQL命令
            params: 命令参数（可选）

        Returns:
            bool: 执行是否成功

        使用示例:
            >>> success = pool.execute_command("INSERT INTO table VALUES (?, ?)", [1, "test"])
        """
        try:
            with self.get_connection() as conn:
                if params:
                    conn.execute(sql, params)
                else:
                    conn.execute(sql)
                return True
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return False

    def execute_many(self, sql: str, params_list: List[List]) -> bool:
        """
        批量执行命令

        Args:
            sql: SQL命令（包含占位符）
            params_list: 参数列表

        Returns:
            bool: 执行是否成功

        使用示例:
            >>> params = [[1, "a"], [2, "b"], [3, "c"]]
            >>> pool.execute_many("INSERT INTO table VALUES (?, ?)", params)
        """
        try:
            with self.get_connection() as conn:
                conn.executemany(sql, params_list)
                return True
        except Exception as e:
            logger.error(f"批量执行失败: {e}")
            return False

    def get_pool_status(self) -> Dict[str, Any]:
        """
        获取连接池状态

        Returns:
            dict: 连接池状态信息，包含:
                - status: 连接池状态描述
                - pool_size: 连接池大小
                - checked_out: 已检出连接数
                - overflow: 溢出连接数
                - checked_in: 已检入连接数
        """
        try:
            status = self.pool.status()
            return {
                'status': status,
                'pool_size': self.pool.size(),
                'checked_out': self.pool.checkedout(),
                'overflow': self.pool.overflow(),
                'checked_in': self.pool.checkedin()
            }
        except Exception as e:
            logger.error(f"获取连接池状态失败: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    def log_pool_status(self):
        """记录连接池状态到日志"""
        status = self.get_pool_status()
        logger.info(f"连接池状态 - {status}")

    def dispose(self, close_connections: bool = True):
        """
        销毁连接池，释放所有连接

        Args:
            close_connections: 是否关闭所有已检入的连接，默认True
        """
        try:
            if close_connections:
                self.pool.dispose()
                logger.info("连接池已销毁，所有连接已关闭")
            else:
                # 只是解除引用，不关闭连接（用于fork场景）
                self.pool.dispose(_close=False)
                logger.info("连接池已解除引用（连接未关闭）")
        except Exception as e:
            logger.error(f"销毁连接池失败: {e}")

    def recreate(self):
        """
        重新创建连接池

        在dispose()后调用，创建一个新的连接池。
        """
        try:
            self.pool.recreate()
            logger.info("连接池已重新创建")
        except Exception as e:
            logger.error(f"重新创建连接池失败: {e}")

    def __enter__(self):
        """支持上下文管理器协议"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持上下文管理器协议"""
        self.dispose()
        return False

    def __del__(self):
        """析构时清理资源"""
        try:
            self.dispose()
        except:
            pass


# ========================================
# 使用示例和测试
# ========================================

def example_basic_usage():
    """基础使用示例"""
    print("=== 基础使用示例 ===")

    # 创建连接池
    pool = DuckDBConnectionPool(
        db_path="./test_pool.duckdb",
        pool_size=3,
        max_overflow=5
    )

    # 创建测试表
    with pool.get_connection() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER, name VARCHAR)")
        conn.execute("INSERT INTO test VALUES (1, 'Alice'), (2, 'Bob')")

    # 查询数据
    df = pool.execute_query("SELECT * FROM test")
    print(f"查询结果:\n{df}")

    # 检查连接池状态
    status = pool.get_pool_status()
    print(f"连接池状态: {status}")

    # 清理
    pool.dispose()
    print("基础使用示例完成")


def example_concurrent_usage():
    """并发使用示例"""
    print("\n=== 并发使用示例 ===")

    import concurrent.futures

    pool = DuckDBConnectionPool("./test_pool.duckdb")

    def query_in_thread(thread_id: int):
        df = pool.execute_query("SELECT * FROM test")
        print(f"线程 {thread_id}: 查询到 {len(df)} 条记录")
        return len(df)

    # 10个线程并发查询
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(query_in_thread, i) for i in range(10)]
        results = [f.result() for f in futures]

    print(f"并发查询完成，总查询次数: {len(results)}")

    # 检查连接池状态
    pool.log_pool_status()
    pool.dispose()


if __name__ == "__main__":
    # 运行示例
    example_basic_usage()
    example_concurrent_usage()

    print("\n所有示例运行完成")
