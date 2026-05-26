from loguru import logger
"""
DuckDB数据操作接口

提供DuckDB数据库的高效数据操作，包括：
- 批量数据插入
- 高效数据查询
- 数据更新和删除
- 事务管理
- 查询性能监控

注意: update_data 和 delete_data 方法当前无调用方，仅为死代码保留。
      如后续启用，需确保 where_conditions 使用 Dict[str, Any] 参数化查询格式。

作者: FactorWeave-Quant团队
版本: 1.0
"""

import time
import pandas as pd
import re
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, date
from contextlib import contextmanager
import json

from .duckdb_manager import DuckDBConnectionManager, get_connection_manager
from .table_manager import DynamicTableManager, TableType, get_table_manager


_SAFE_TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_table_name(table_name: str) -> str:
    """校验表名，防止SQL注入"""
    if not _SAFE_TABLE_NAME_PATTERN.match(table_name):
        raise ValueError(f"非法的表名: '{table_name}'，只允许字母、数字和下划线，且不能以数字开头")
    return table_name


@dataclass
class QueryResult:
    """查询结果"""
    data: pd.DataFrame
    execution_time: float
    row_count: int
    columns: List[str]
    query_sql: str
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class InsertResult:
    """插入结果"""
    success: bool
    rows_inserted: int
    execution_time: float
    batch_count: int
    error_message: Optional[str] = None
    failed_batches: List[int] = None


@dataclass
class QueryFilter:
    """查询过滤条件"""
    symbols: Optional[List[str]] = None
    start_date: Optional[Union[str, datetime, date]] = None
    end_date: Optional[Union[str, datetime, date]] = None
    date_column: str = 'datetime'
    limit: Optional[int] = None
    order_by: Optional[str] = None
    where_conditions: Optional[List[str]] = None
    additional_filters: Optional[Dict[str, Any]] = None


class DuckDBOperations:
    """DuckDB数据操作类"""

    def __init__(self, connection_manager: Optional[DuckDBConnectionManager] = None,
                 table_manager: Optional[DynamicTableManager] = None):
        """
        初始化数据操作类

        Args:
            connection_manager: DuckDB连接管理器
            table_manager: 动态表管理器
        """
        self.connection_manager = connection_manager or get_connection_manager()
        self.table_manager = table_manager or get_table_manager()

        # 性能监控
        self._query_stats: Dict[str, List[float]] = {}
        self._insert_stats: Dict[str, List[float]] = {}

        logger.info("DuckDB数据操作类初始化完成")

    def insert_dataframe(self, database_path: str, table_name: str,
                         data: pd.DataFrame, batch_size: int = 10000,
                         upsert: bool = False, conflict_columns: Optional[List[str]] = None) -> InsertResult:
        """
        批量插入DataFrame数据

        Args:
            database_path: 数据库路径
            table_name: 表名
            data: 要插入的数据
            batch_size: 批次大小
            upsert: 是否使用upsert模式
            conflict_columns: 冲突检测列（upsert模式使用）

        Returns:
            插入结果
        """
        start_time = time.time()

        try:
            _validate_table_name(table_name)

            if data.empty:
                return InsertResult(
                    success=True,
                    rows_inserted=0,
                    execution_time=0,
                    batch_count=0
                )

            total_rows = len(data)
            batch_count = (total_rows + batch_size - 1) // batch_size
            rows_inserted = 0
            failed_batches = []

            with self.connection_manager.get_connection(database_path) as conn:
                # 开始事务
                conn.execute("BEGIN TRANSACTION")

                try:
                    for i in range(0, total_rows, batch_size):
                        batch_data = data.iloc[i:i + batch_size]
                        batch_index = i // batch_size

                        try:
                            if upsert and conflict_columns:
                                # 使用upsert模式
                                self._upsert_batch(conn, table_name, batch_data, conflict_columns)
                            else:
                                # 普通插入模式
                                self._insert_batch(conn, table_name, batch_data)

                            rows_inserted += len(batch_data)

                        except Exception as e:
                            logger.error(f"批次 {batch_index} 插入失败: {e}")
                            failed_batches.append(batch_index)

                    if failed_batches:
                        conn.execute("ROLLBACK")
                        rows_inserted = 0
                    else:
                        conn.execute("COMMIT")

                    execution_time = time.time() - start_time

                    # 记录性能统计
                    self._record_insert_stats(table_name, execution_time)

                    result = InsertResult(
                        success=len(failed_batches) == 0,
                        rows_inserted=rows_inserted,
                        execution_time=execution_time,
                        batch_count=batch_count,
                        failed_batches=failed_batches if failed_batches else None
                    )

                    logger.info(f"数据插入完成: {table_name}, 插入 {rows_inserted}/{total_rows} 行, "
                                f"耗时 {execution_time:.2f}秒")

                    return result

                except Exception as e:
                    # 回滚事务
                    conn.execute("ROLLBACK")
                    raise e

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"数据插入失败 {table_name}: {e}")

            return InsertResult(
                success=False,
                rows_inserted=0,
                execution_time=execution_time,
                batch_count=0,
                error_message=str(e)
            )

    def _insert_batch(self, conn, table_name: str, batch_data: pd.DataFrame):
        """插入单个批次数据"""
        columns = list(batch_data.columns)
        columns_str = ', '.join(f'"{col}"' for col in columns)

        conn.register('temp_batch', batch_data)
        conn.execute(f"INSERT INTO {table_name} ({columns_str}) SELECT {columns_str} FROM temp_batch")
        conn.unregister('temp_batch')

    def _upsert_batch(self, conn, table_name: str, batch_data: pd.DataFrame,
                      conflict_columns: List[str]):
        """Upsert单个批次数据"""
        columns = list(batch_data.columns)

        conflict_cols = ', '.join(f'"{col}"' for col in conflict_columns)

        update_clauses = []
        for col in columns:
            if col not in conflict_columns:
                update_clauses.append(f'"{col}" = EXCLUDED."{col}"')

        update_set = ', '.join(update_clauses)

        conn.register('temp_batch', batch_data)

        columns_str = ', '.join(f'"{col}"' for col in columns)
        upsert_sql = f"""
        INSERT INTO {table_name} ({columns_str})
        SELECT {columns_str} FROM temp_batch
        ON CONFLICT ({conflict_cols}) 
        DO UPDATE SET {update_set}
        """

        conn.execute(upsert_sql)
        conn.unregister('temp_batch')

    def query_data(self, database_path: str, table_name: str,
                   query_filter: Optional[QueryFilter] = None,
                   custom_sql: Optional[str] = None) -> QueryResult:
        """
        查询数据

        Args:
            database_path: 数据库路径
            table_name: 表名
            query_filter: 查询过滤条件
            custom_sql: 自定义SQL查询

        Returns:
            查询结果
        """
        start_time = time.time()

        try:
            _validate_table_name(table_name)

            with self.connection_manager.get_connection(database_path) as conn:
                if custom_sql:
                    query_sql = custom_sql
                    query_params = None
                else:
                    query_sql, query_params = self._build_query_sql(table_name, query_filter)

                if query_params:
                    result_df = conn.execute(query_sql, query_params).df()
                else:
                    result_df = conn.execute(query_sql).df()

                execution_time = time.time() - start_time

                # 记录性能统计
                self._record_query_stats(table_name, execution_time)

                result = QueryResult(
                    data=result_df,
                    execution_time=execution_time,
                    row_count=len(result_df),
                    columns=list(result_df.columns),
                    query_sql=query_sql
                )

                logger.debug(f"查询完成: {table_name}, 返回 {len(result_df)} 行, "
                             f"耗时 {execution_time:.3f}秒")

                return result

        except Exception as e:
            execution_time = time.time() - start_time

            # 表不存在是正常的降级情况，使用debug级别
            if "does not exist" in str(e) or "Table with name" in str(e):
                logger.debug(f"查询失败（表不存在，正常降级） {table_name}: {e}")
            else:
                logger.error(f"查询失败 {table_name}: {e}")

            return QueryResult(
                data=pd.DataFrame(),
                execution_time=execution_time,
                row_count=0,
                columns=[],
                query_sql=custom_sql or "",
                success=False,
                error_message=str(e)
            )

    def _build_query_sql(self, table_name: str, query_filter: Optional[QueryFilter]) -> tuple:
        """构建查询SQL，返回(sql, params)元组以支持参数化查询"""
        sql_parts = [f"SELECT * FROM {table_name}"]
        where_conditions = []
        params = []

        if query_filter:
            # 符号过滤
            if query_filter.symbols:
                placeholders = ", ".join(["?"] * len(query_filter.symbols))
                where_conditions.append(f"symbol IN ({placeholders})")
                params.extend(query_filter.symbols)

            # 日期范围过滤
            if query_filter.start_date:
                start_date_str = self._format_date(query_filter.start_date)
                where_conditions.append(f"{query_filter.date_column} >= ?")
                params.append(start_date_str)

            if query_filter.end_date:
                end_date_str = self._format_date(query_filter.end_date)
                where_conditions.append(f"{query_filter.date_column} <= ?")
                params.append(end_date_str)

            # 自定义WHERE条件
            if query_filter.where_conditions:
                where_conditions.extend(query_filter.where_conditions)

            # 额外过滤条件
            if query_filter.additional_filters:
                for key, value in query_filter.additional_filters.items():
                    if isinstance(value, str):
                        where_conditions.append(f"{key} = ?")
                        params.append(value)
                    elif isinstance(value, (int, float)):
                        where_conditions.append(f"{key} = ?")
                        params.append(value)
                    elif isinstance(value, list):
                        placeholders = ", ".join(["?"] * len(value))
                        where_conditions.append(f"{key} IN ({placeholders})")
                        params.extend([str(v) for v in value])

        # 添加WHERE子句
        if where_conditions:
            sql_parts.append("WHERE " + " AND ".join(where_conditions))

        # 添加ORDER BY
        if query_filter and query_filter.order_by:
            sql_parts.append(f"ORDER BY {query_filter.order_by}")

        # 添加LIMIT
        if query_filter and query_filter.limit:
            sql_parts.append(f"LIMIT {query_filter.limit}")

        return " ".join(sql_parts), params

    def _format_date(self, date_value: Union[str, datetime, date]) -> str:
        """格式化日期"""
        if isinstance(date_value, str):
            return date_value
        elif isinstance(date_value, datetime):
            return date_value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(date_value, date):
            return date_value.strftime('%Y-%m-%d')
        else:
            return str(date_value)

    def update_data(self, database_path: str, table_name: str,
                    update_data: Dict[str, Any], where_conditions: Dict[str, Any]) -> bool:
        """
        更新数据

        Args:
            database_path: 数据库路径
            table_name: 表名
            update_data: 更新数据字典
            where_conditions: WHERE条件字典 (key=column, value=condition_value)

        Returns:
            更新是否成功
        """
        try:
            _validate_table_name(table_name)

            set_clauses = []
            params = []
            for key, value in update_data.items():
                set_clauses.append(f"{key} = ?")
                params.append(value)

            where_parts = []
            for key, value in where_conditions.items():
                where_parts.append(f"{key} = ?")
                params.append(value)

            set_clause = ", ".join(set_clauses)
            where_clause = " AND ".join(where_parts)

            update_sql = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"

            with self.connection_manager.get_connection(database_path) as conn:
                result = conn.execute(update_sql, params)
                affected_rows = result.fetchall() if hasattr(result, 'fetchall') else 0

                logger.info(f"数据更新完成: {table_name}, 影响 {affected_rows} 行")
                return True

        except Exception as e:
            logger.error(f"数据更新失败 {table_name}: {e}")
            return False

    def delete_data(self, database_path: str, table_name: str,
                    where_conditions: Dict[str, Any]) -> bool:
        """
        删除数据

        Args:
            database_path: 数据库路径
            table_name: 表名
            where_conditions: WHERE条件字典 (key=column, value=condition_value)

        Returns:
            删除是否成功
        """
        try:
            _validate_table_name(table_name)

            where_parts = []
            params = []
            for key, value in where_conditions.items():
                where_parts.append(f"{key} = ?")
                params.append(value)

            where_clause = " AND ".join(where_parts)
            delete_sql = f"DELETE FROM {table_name} WHERE {where_clause}"

            with self.connection_manager.get_connection(database_path) as conn:
                result = conn.execute(delete_sql, params)
                affected_rows = result.fetchall() if hasattr(result, 'fetchall') else 0

                logger.info(f"数据删除完成: {table_name}, 影响 {affected_rows} 行")
                return True

        except Exception as e:
            logger.error(f"数据删除失败 {table_name}: {e}")
            return False

    @contextmanager
    def transaction(self, database_path: str):
        """
        事务上下文管理器

        Args:
            database_path: 数据库路径
        """
        with self.connection_manager.get_connection(database_path) as conn:
            try:
                conn.execute("BEGIN TRANSACTION")
                yield conn
                conn.execute("COMMIT")
                logger.debug("事务提交成功")

            except Exception as e:
                conn.execute("ROLLBACK")
                logger.error(f"事务回滚: {e}")
                raise

    def execute_sql(self, database_path: str, sql: str,
                    params: Optional[List[Any]] = None) -> QueryResult:
        """
        执行自定义SQL

        Args:
            database_path: 数据库路径
            sql: SQL语句
            params: 参数列表

        Returns:
            查询结果
        """
        start_time = time.time()

        try:
            with self.connection_manager.get_connection(database_path) as conn:
                if params:
                    result = conn.execute(sql, params)
                else:
                    result = conn.execute(sql)

                # 尝试获取DataFrame结果
                try:
                    result_df = result.df()
                except Exception:
                    # 如果不是SELECT语句，创建空DataFrame
                    result_df = pd.DataFrame()

                execution_time = time.time() - start_time

                return QueryResult(
                    data=result_df,
                    execution_time=execution_time,
                    row_count=len(result_df),
                    columns=list(result_df.columns) if not result_df.empty else [],
                    query_sql=sql
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"SQL执行失败: {e}")

            return QueryResult(
                data=pd.DataFrame(),
                execution_time=execution_time,
                row_count=0,
                columns=[],
                query_sql=sql,
                success=False,
                error_message=str(e)
            )

    def get_table_statistics(self, database_path: str, table_name: str) -> Dict[str, Any]:
        """
        获取表统计信息

        Args:
            database_path: 数据库路径
            table_name: 表名

        Returns:
            统计信息
        """
        try:
            _validate_table_name(table_name)

            with self.connection_manager.get_connection(database_path) as conn:
                # 获取行数
                row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

                # 获取表大小（DuckDB不支持pg_total_relation_size，使用估算方法）
                try:
                    # 尝试获取表的存储信息
                    table_size_result = conn.execute(
                        f"SELECT COUNT(*) * 1000 as estimated_size FROM {table_name}"  # 粗略估算
                    ).fetchone()
                    table_size = table_size_result[0] if table_size_result else 0
                except Exception:
                    table_size = 0

                # 获取列信息
                columns_info = conn.execute(f"DESCRIBE {table_name}").fetchall()

                return {
                    'table_name': table_name,
                    'row_count': row_count,
                    'table_size_bytes': table_size,
                    'column_count': len(columns_info),
                    'columns': [{'name': col[0], 'type': col[1]} for col in columns_info]
                }

        except Exception as e:
            logger.error(f"获取表统计信息失败 {table_name}: {e}")
            return {'table_name': table_name, 'error': str(e)}

    def optimize_table(self, database_path: str, table_name: str) -> bool:
        """
        优化表（重建索引、更新统计信息等）

        Args:
            database_path: 数据库路径
            table_name: 表名

        Returns:
            优化是否成功
        """
        try:
            _validate_table_name(table_name)

            with self.connection_manager.get_connection(database_path) as conn:
                # DuckDB的优化操作
                conn.execute(f"ANALYZE {table_name}")
                logger.info(f"表优化完成: {table_name}")
                return True

        except Exception as e:
            logger.error(f"表优化失败 {table_name}: {e}")
            return False

    def _record_query_stats(self, table_name: str, execution_time: float):
        """记录查询性能统计"""
        if table_name not in self._query_stats:
            self._query_stats[table_name] = []

        self._query_stats[table_name].append(execution_time)

        # 保持最近100次记录
        if len(self._query_stats[table_name]) > 100:
            self._query_stats[table_name] = self._query_stats[table_name][-100:]

    def _record_insert_stats(self, table_name: str, execution_time: float):
        """记录插入性能统计"""
        if table_name not in self._insert_stats:
            self._insert_stats[table_name] = []

        self._insert_stats[table_name].append(execution_time)

        # 保持最近100次记录
        if len(self._insert_stats[table_name]) > 100:
            self._insert_stats[table_name] = self._insert_stats[table_name][-100:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = {
            'query_stats': {},
            'insert_stats': {}
        }

        # 查询统计
        for table_name, times in self._query_stats.items():
            if times:
                stats['query_stats'][table_name] = {
                    'count': len(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'total_time': sum(times)
                }

        # 插入统计
        for table_name, times in self._insert_stats.items():
            if times:
                stats['insert_stats'][table_name] = {
                    'count': len(times),
                    'avg_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times),
                    'total_time': sum(times)
                }

        return stats

    def clear_performance_stats(self):
        """清理性能统计"""
        self._query_stats.clear()
        self._insert_stats.clear()
        logger.info("性能统计已清理")

    def execute_query(self, database_path: str, query: str, params: Optional[List[Any]] = None) -> QueryResult:
        """
        执行自定义SQL查询（带参数支持）

        这是为了向后兼容而添加的方法，内部使用query_data实现

        Args:
            database_path: 数据库路径
            query: SQL查询语句（可以包含?占位符）
            params: 查询参数列表

        Returns:
            查询结果
        """
        try:
            start_time = time.time()

            with self.connection_manager.get_connection(database_path) as conn:
                if params:
                    result = conn.execute(query, params).fetchdf()
                else:
                    result = conn.execute(query).fetchdf()

            execution_time = time.time() - start_time

            return QueryResult(
                data=result,
                execution_time=execution_time,
                row_count=len(result),
                columns=list(result.columns) if not result.empty else [],
                query_sql=query,
                success=True
            )

        except Exception as e:
            logger.error(f"执行查询失败: {e}")
            return QueryResult(
                data=pd.DataFrame(),
                execution_time=0,
                row_count=0,
                columns=[],
                query_sql=query,
                success=False,
                error_message=str(e)
            )

    def _extract_table_name(self, sql: str) -> str:
        """从SQL语句中提取表名（简单实现）"""
        try:
            # 转换为小写以便匹配
            sql_lower = sql.lower()

            # 查找FROM关键字
            from_index = sql_lower.find('from')
            if from_index == -1:
                return "unknown"

            # 提取FROM后的第一个单词作为表名
            after_from = sql[from_index + 4:].strip()
            table_name = after_from.split()[0]

            # 移除可能的引号
            table_name = table_name.strip('"').strip("'")

            return table_name

        except Exception:
            return "unknown"


# 全局数据操作实例
_duckdb_operations: Optional[DuckDBOperations] = None


def get_duckdb_operations() -> DuckDBOperations:
    """获取全局数据操作实例"""
    global _duckdb_operations

    if _duckdb_operations is None:
        _duckdb_operations = DuckDBOperations()

    return _duckdb_operations
