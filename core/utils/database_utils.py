"""
数据库工具函数库

提供数据库相关的实用工具函数，包括：
- 动态表名生成
- 股票代码格式验证
- 市场代码标准化
- 数据库连接管理
- SQL查询构建
- 数据导入导出

作者: FactorWeave-Quant团队
版本: 1.0
"""

import re
import sqlite3
import pandas as pd
from functools import lru_cache
from typing import Dict, List, Optional, Union, Tuple, Any
from datetime import datetime, date
from pathlib import Path
import json

from loguru import logger

from ..plugin_types import DataType, AssetType
from ..database.unified_sqlite_access import UnifiedSQLiteAccess

ALLOWED_TABLE_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
ALLOWED_INDEX_NAME_PATTERN = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _validate_identifier(name: str, pattern: re.Pattern, label: str = "identifier") -> str:
    if not pattern.match(name):
        raise ValueError(f"Invalid {label}: {name}")
    return name


def generate_table_name(plugin_name: str, data_type: Union[DataType, str],
                        period: Optional[str] = None) -> str:
    """
    动态生成表名

    Args:
        plugin_name: 插件名称
        data_type: 数据类型
        period: 周期（可选）

    Returns:
        标准化表名
    """
    try:
        # 清理插件名称
        clean_plugin_name = re.sub(r'[^a-zA-Z0-9_]', '_', plugin_name.lower())

        # 处理数据类型
        if isinstance(data_type, DataType):
            data_type_str = data_type.value
        else:
            data_type_str = str(data_type).lower()

        # 清理数据类型名称
        clean_data_type = re.sub(r'[^a-zA-Z0-9_]', '_', data_type_str)

        # 构建基础表名
        base_name = f"{clean_data_type}_{clean_plugin_name}"

        # 添加周期后缀
        if period:
            clean_period = re.sub(r'[^a-zA-Z0-9_]', '_', period.lower())
            return f"{base_name}_{clean_period}"

        return base_name

    except Exception as e:
        logger.error(f"生成表名失败: {e}")
        return f"unknown_table_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

@lru_cache(maxsize=128)
def validate_symbol_format(symbol: str, market: Optional[str] = None) -> bool:
    """
    验证股票代码格式

    Args:
        symbol: 股票代码
        market: 市场代码

    Returns:
        是否有效
    """
    try:
        if not symbol or not isinstance(symbol, str):
            return False

        symbol = symbol.strip().upper()

        if not market:
            # 尝试从代码中推断市场
            if '.' in symbol:
                code, market_suffix = symbol.split('.', 1)
                market = market_suffix
            else:
                code = symbol
                market = None

        if market:
            market = market.upper()

            # A股市场验证
            if market in ['SH', 'SZ']:
                # 6位数字代码
                code_part = symbol.split('.')[0] if '.' in symbol else symbol
                return len(code_part) == 6 and code_part.isdigit()

            # 港股市场验证
            elif market in ['HK', 'HKEX']:
                # 1-5位数字代码
                code_part = symbol.split('.')[0] if '.' in symbol else symbol
                return len(code_part) <= 5 and code_part.isdigit()

            # 美股市场验证
            elif market in ['US', 'NASDAQ', 'NYSE']:
                # 1-5位字母代码
                code_part = symbol.split('.')[0] if '.' in symbol else symbol
                return len(code_part) <= 5 and code_part.isalpha()

            # 其他市场暂时通过
            else:
                return len(symbol) > 0

        # 无市场信息时的基本验证
        return len(symbol) > 0 and len(symbol) <= 20

    except Exception as e:
        logger.error(f"验证股票代码格式失败: {e}")
        return False

@lru_cache(maxsize=128)
def standardize_market_code(market: str) -> str:
    """
    标准化市场代码

    Args:
        market: 原始市场代码

    Returns:
        标准化的市场代码
    """
    try:
        if not market:
            return "UNKNOWN"

        market = market.strip().upper()

        # 市场代码映射
        market_mapping = {
            # 中国A股
            'SH': 'SH',
            'SHANGHAI': 'SH',
            'SSE': 'SH',
            'SZ': 'SZ',
            'SHENZHEN': 'SZ',
            'SZSE': 'SZ',

            # 港股
            'HK': 'HK',
            'HONGKONG': 'HK',
            'HKEX': 'HK',

            # 美股
            'US': 'US',
            'USA': 'US',
            'NASDAQ': 'NASDAQ',
            'NYSE': 'NYSE',
            'AMEX': 'AMEX',

            # 其他主要市场
            'JP': 'JP',
            'JAPAN': 'JP',
            'TSE': 'JP',
            'UK': 'UK',
            'LSE': 'UK',
            'DE': 'DE',
            'GERMANY': 'DE',
            'XETRA': 'DE'
        }

        return market_mapping.get(market, market)

    except Exception as e:
        logger.error(f"标准化市场代码失败: {e}")
        return "UNKNOWN"

@lru_cache(maxsize=128)
def normalize_symbol(symbol: str, market: Optional[str] = None) -> str:
    """
    标准化股票代码

    Args:
        symbol: 原始股票代码
        market: 市场代码

    Returns:
        标准化的股票代码
    """
    try:
        if not symbol:
            return ""

        symbol = symbol.strip().upper()

        # 如果已经包含市场后缀，分离处理
        if '.' in symbol:
            code, market_suffix = symbol.split('.', 1)
            market = market or market_suffix
        else:
            code = symbol

        # 标准化市场代码
        if market:
            standardized_market = standardize_market_code(market)
            return f"{code}.{standardized_market}"

        return code

    except Exception as e:
        logger.error(f"标准化股票代码失败: {e}")
        return symbol

def build_select_query(table_name: str, columns: Optional[List[str]] = None,
                       where_conditions: Optional[Dict[str, Any]] = None,
                       order_by: Optional[str] = None,
                       limit: Optional[int] = None) -> Tuple[str, List[Any]]:
    """
    构建SELECT查询语句

    Args:
        table_name: 表名
        columns: 要查询的列名列表
        where_conditions: WHERE条件字典
        order_by: 排序字段
        limit: 限制记录数

    Returns:
        (SQL查询语句, 参数列表) 的元组
    """
    try:
        _validate_identifier(table_name, ALLOWED_TABLE_NAME_PATTERN, "table name")

        if columns:
            columns_str = ', '.join(f'"{col}"' for col in columns)
        else:
            columns_str = '*'

        query = f'SELECT {columns_str} FROM "{table_name}"'
        params: List[Any] = []

        if where_conditions:
            where_clauses = []
            for column, value in where_conditions.items():
                if isinstance(value, (list, tuple)):
                    placeholders = ', '.join(['?' for _ in value])
                    where_clauses.append(f'"{column}" IN ({placeholders})')
                    params.extend(value)
                else:
                    where_clauses.append(f'"{column}" = ?')
                    params.append(value)

            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)

        if order_by:
            _validate_identifier(order_by, ALLOWED_TABLE_NAME_PATTERN, "order by column")
            query += f' ORDER BY "{order_by}"'

        if limit:
            query += f' LIMIT ?'
            params.append(limit)

        return query, params

    except Exception as e:
        logger.error(f"构建SELECT查询失败: {e}")
        return f'SELECT * FROM "{table_name}"', []

def build_insert_query(table_name: str, data: Dict[str, Any],
                       on_conflict: str = 'REPLACE') -> Tuple[str, List[Any]]:
    """
    构建INSERT查询语句

    Args:
        table_name: 表名
        data: 要插入的数据字典
        on_conflict: 冲突处理方式 ('REPLACE', 'IGNORE')

    Returns:
        SQL查询语句和参数列表的元组
    """
    try:
        if not data:
            raise ValueError("插入数据不能为空")

        _validate_identifier(table_name, ALLOWED_TABLE_NAME_PATTERN, "table name")

        columns = list(data.keys())
        values = list(data.values())

        columns_str = ', '.join(f'"{col}"' for col in columns)
        placeholders = ', '.join(['?' for _ in columns])

        if on_conflict.upper() == 'REPLACE':
            query = f'INSERT OR REPLACE INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
        elif on_conflict.upper() == 'IGNORE':
            query = f'INSERT OR IGNORE INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
        else:
            query = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'

        return query, values

    except Exception as e:
        logger.error(f"构建INSERT查询失败: {e}")
        return f'INSERT INTO "{table_name}" DEFAULT VALUES', []

def build_update_query(table_name: str, data: Dict[str, Any],
                       where_conditions: Dict[str, Any]) -> Tuple[str, List[Any]]:
    """
    构建UPDATE查询语句

    Args:
        table_name: 表名
        data: 要更新的数据字典
        where_conditions: WHERE条件字典

    Returns:
        SQL查询语句和参数列表的元组
    """
    try:
        if not data:
            raise ValueError("更新数据不能为空")

        if not where_conditions:
            raise ValueError("WHERE条件不能为空")

        _validate_identifier(table_name, ALLOWED_TABLE_NAME_PATTERN, "table name")

        set_clauses = []
        set_values = []
        for column, value in data.items():
            set_clauses.append(f'"{column}" = ?')
            set_values.append(value)

        # 构建WHERE子句
        where_clauses = []
        where_values = []
        for column, value in where_conditions.items():
            where_clauses.append(f'"{column}" = ?')
            where_values.append(value)

        query = f'UPDATE "{table_name}" SET {", ".join(set_clauses)} WHERE {" AND ".join(where_clauses)}'
        values = set_values + where_values

        return query, values

    except Exception as e:
        logger.error(f"构建UPDATE查询失败: {e}")
        return f'UPDATE "{table_name}" SET id = id', []

def execute_query(db_path: str, query: str, params: Optional[List[Any]] = None,
                  fetch_results: bool = True) -> Optional[pd.DataFrame]:
    """
    执行SQL查询

    Args:
        db_path: 数据库文件路径
        query: SQL查询语句
        params: 查询参数
        fetch_results: 是否获取查询结果

    Returns:
        查询结果DataFrame（如果fetch_results为True）
    """
    try:
        db = UnifiedSQLiteAccess.get_instance(db_path)
        with db.get_connection() as conn:
            if fetch_results:
                df = pd.read_sql_query(query, conn, params=params or [])
                return df
            else:
                cursor = conn.cursor()
                cursor.execute(query, params or [])
                return None

    except Exception as e:
        logger.error(f"执行SQL查询失败: {e}")
        return None

def batch_insert_data(db_path: str, table_name: str, data: pd.DataFrame,
                      chunk_size: int = 1000, if_exists: str = 'append') -> bool:
    """
    批量插入数据

    Args:
        db_path: 数据库文件路径
        table_name: 表名
        data: 要插入的数据DataFrame
        chunk_size: 批次大小
        if_exists: 表存在时的处理方式 ('fail', 'replace', 'append')

    Returns:
        是否成功
    """
    try:
        if data.empty:
            logger.warning("没有数据需要插入")
            return True

        db = UnifiedSQLiteAccess.get_instance(db_path)
        with db.get_connection() as conn:
            # 分批插入数据
            for i in range(0, len(data), chunk_size):
                chunk = data.iloc[i:i + chunk_size]
                chunk.to_sql(table_name, conn, if_exists=if_exists, index=False)
                if_exists = 'append'  # 第一次之后都是追加

                logger.debug(f"已插入 {min(i + chunk_size, len(data))}/{len(data)} 条记录")

        logger.info(f"成功批量插入 {len(data)} 条记录到表 {table_name}")
        return True

    except Exception as e:
        logger.error(f"批量插入数据失败: {e}")
        return False

def export_table_to_csv(db_path: str, table_name: str, output_path: str,
                        where_conditions: Optional[Dict[str, Any]] = None) -> bool:
    """
    导出表数据到CSV文件

    Args:
        db_path: 数据库文件路径
        table_name: 表名
        output_path: 输出CSV文件路径
        where_conditions: WHERE条件字典

    Returns:
        是否成功
    """
    try:
        query, params = build_select_query(table_name, where_conditions=where_conditions)
        df = execute_query(db_path, query, params=params, fetch_results=True)

        if df is not None and not df.empty:
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logger.info(f"成功导出 {len(df)} 条记录到 {output_path}")
            return True
        else:
            logger.warning(f"表 {table_name} 没有数据可导出")
            return False

    except Exception as e:
        logger.error(f"导出表数据失败: {e}")
        return False

def import_csv_to_table(db_path: str, table_name: str, csv_path: str,
                        if_exists: str = 'append') -> bool:
    """
    从CSV文件导入数据到表

    Args:
        db_path: 数据库文件路径
        table_name: 表名
        csv_path: CSV文件路径
        if_exists: 表存在时的处理方式

    Returns:
        是否成功
    """
    try:
        if not Path(csv_path).exists():
            logger.error(f"CSV文件不存在: {csv_path}")
            return False

        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        if df.empty:
            logger.warning(f"CSV文件为空: {csv_path}")
            return True

        return batch_insert_data(db_path, table_name, df, if_exists=if_exists)

    except Exception as e:
        logger.error(f"从CSV导入数据失败: {e}")
        return False

def get_table_info(db_path: str, table_name: str) -> Optional[Dict[str, Any]]:
    """
    获取表信息

    Args:
        db_path: 数据库文件路径
        table_name: 表名

    Returns:
        表信息字典
    """
    try:
        _validate_identifier(table_name, ALLOWED_TABLE_NAME_PATTERN, "table name")

        db = UnifiedSQLiteAccess.get_instance(db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(f'PRAGMA table_info("{table_name}")')
            columns_info = cursor.fetchall()

            cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            row_count = cursor.fetchone()[0]

            cursor.execute(f'SELECT SUM(LENGTH(quote(c0))) FROM "{table_name}"')
            size_result = cursor.fetchone()
            table_size = size_result[0] if size_result and size_result[0] else 0

            return {
                'table_name': table_name,
                'columns': [
                    {
                        'name': col[1],
                        'type': col[2],
                        'not_null': bool(col[3]),
                        'default_value': col[4],
                        'primary_key': bool(col[5])
                    }
                    for col in columns_info
                ],
                'row_count': row_count,
                'table_size_bytes': table_size,
                'column_count': len(columns_info)
            }

    except Exception as e:
        logger.error(f"获取表信息失败: {e}")
        return None

def list_all_tables(db_path: str) -> List[str]:
    """
    列出数据库中的所有表

    Args:
        db_path: 数据库文件路径

    Returns:
        表名列表
    """
    try:
        db = UnifiedSQLiteAccess.get_instance(db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            return tables

    except Exception as e:
        logger.error(f"列出数据库表失败: {e}")
        return []

def create_index(db_path: str, table_name: str, columns: List[str],
                 index_name: Optional[str] = None, unique: bool = False) -> bool:
    """
    创建索引

    Args:
        db_path: 数据库文件路径
        table_name: 表名
        columns: 索引列名列表
        index_name: 索引名称
        unique: 是否唯一索引

    Returns:
        是否成功
    """
    try:
        if not columns:
            raise ValueError("索引列不能为空")

        _validate_identifier(table_name, ALLOWED_TABLE_NAME_PATTERN, "table name")

        if not index_name:
            index_name = f"idx_{table_name}_{'_'.join(columns)}"

        _validate_identifier(index_name, ALLOWED_INDEX_NAME_PATTERN, "index name")

        columns_str = ', '.join(f'"{col}"' for col in columns)
        unique_str = 'UNIQUE ' if unique else ''

        query = f'CREATE {unique_str}INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ({columns_str})'

        result = execute_query(db_path, query, fetch_results=False)

        if result is not None:
            logger.info(f"成功创建索引 {index_name}")
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"创建索引失败: {e}")
        return False

def optimize_database(db_path: str) -> bool:
    """
    优化数据库

    Args:
        db_path: 数据库文件路径

    Returns:
        是否成功
    """
    try:
        db = UnifiedSQLiteAccess.get_instance(db_path)
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 分析查询计划
            cursor.execute('ANALYZE')

            # 清理数据库
            cursor.execute('VACUUM')

            # 重建索引
            cursor.execute('REINDEX')

        logger.info(f"数据库优化完成: {db_path}")
        return True

    except Exception as e:
        logger.error(f"数据库优化失败: {e}")
        return False

def validate_stock_code(symbol: str, market: Optional[str] = None) -> bool:
    """
    验证股票代码格式（validate_symbol_format 的别名，向后兼容）
    """
    return validate_symbol_format(symbol, market)


def format_stock_code(symbol: str, market: Optional[str] = None) -> str:
    """
    格式化股票代码（normalize_symbol 的别名，向后兼容）
    """
    return normalize_symbol(symbol, market)


def get_market_code(market: str) -> str:
    """
    获取市场代码（standardize_market_code 的别名，向后兼容）
    """
    return standardize_market_code(market)


def backup_database(source_db_path: str, backup_db_path: str) -> bool:
    """
    备份数据库

    Args:
        source_db_path: 源数据库路径
        backup_db_path: 备份数据库路径

    Returns:
        是否成功
    """
    try:
        # 确保备份目录存在
        backup_dir = Path(backup_db_path).parent
        backup_dir.mkdir(parents=True, exist_ok=True)

        source_db = UnifiedSQLiteAccess.get_instance(source_db_path)
        backup_db = UnifiedSQLiteAccess.get_instance(backup_db_path)
        
        with source_db.get_connection() as source_conn:
            with backup_db.get_connection() as backup_conn:
                source_conn.backup(backup_conn)

        logger.info(f"数据库备份完成: {source_db_path} -> {backup_db_path}")
        return True

    except Exception as e:
        logger.error(f"数据库备份失败: {e}")
        return False
