#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R251 回归测试: DuckDB 写路径统一 (historical_kline_data)

背景 (已交叉验证):
- unified_data_manager.add_kline/delete_kline 调用 duckdb_operations.insert_kline_data/
  delete_kline_data, 但 DuckDBOperations 之前没有这两个方法 → AttributeError
- 存储侧写 kline_data_{period} 动态表, 读取端查 historical_kline_data → 永远查不到

验证点:
- T01 add_kline 调用 insert_kline_data 且参数正确 (股票代码/周期/数据/库路径)
- T02 _store_to_duckdb 使用 'historical_kline_data' 表名 (patch insert_dataframe 断言)
- T03 duckdb_operations.insert_kline_data 列名映射 (code→symbol, date/datetime→timestamp,
      补充 frequency/data_source, 仅保留表结构列)
- T04 duckdb_operations.delete_kline_data 按 symbol + frequency 删除
- T05 delete_kline 调用 delete_kline_data 且参数正确
"""
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from core.database.duckdb_operations import DuckDBOperations, InsertResult
from core.plugin_types import AssetType


def _make_kdata_df(n: int = 10, use_code: bool = False, use_date: bool = False) -> pd.DataFrame:
    """构造K线DataFrame (支持 code/date 变体列名)"""
    dates = pd.date_range('2024-01-01', periods=n, freq='D')
    data = {
        'datetime': dates,
        'open': [10.0 + i * 0.1 for i in range(n)],
        'high': [10.5 + i * 0.1 for i in range(n)],
        'low': [9.5 + i * 0.1 for i in range(n)],
        'close': [10.2 + i * 0.1 for i in range(n)],
        'volume': [1000000 + i * 1000 for i in range(n)],
        'amount': [10000000 + i * 10000 for i in range(n)],
    }
    if use_code:
        data['code'] = ['000001'] * n
    if use_date:
        data['date'] = data.pop('datetime')
    return pd.DataFrame(data)


def _build_udm():
    """构造轻量 UnifiedDataManager 实例 (跳过 __init__ 避免重型依赖)"""
    from core.services.unified_data_manager import UnifiedDataManager

    udm = object.__new__(UnifiedDataManager)
    udm.duckdb_available = True
    udm.duckdb_operations = MagicMock()
    udm.asset_identifier = MagicMock()
    udm.asset_identifier.identify_asset_type = MagicMock(return_value=AssetType.STOCK_A)
    udm.asset_manager = MagicMock()
    udm.asset_manager.get_database_path = MagicMock(return_value='/tmp/test_asset.duckdb')
    udm.db_access = None
    udm._cache_data = MagicMock()
    udm._invalidate_cache = MagicMock()
    return udm


class TestR251DBWritePath(unittest.TestCase):
    """R251 DuckDB 写路径统一测试"""

    # ---------------------------------------------------------------- T01
    def test_add_kline_calls_insert_kline_data(self):
        """T01: add_kline 调用 insert_kline_data 且参数正确"""
        udm = _build_udm()
        udm.duckdb_operations.insert_kline_data = MagicMock(
            return_value=InsertResult(success=True, rows_inserted=10, execution_time=0.1, batch_count=1)
        )
        data = _make_kdata_df(10)

        result = udm.add_kline('000001', 'D', data)

        self.assertTrue(result)
        udm.duckdb_operations.insert_kline_data.assert_called_once_with(
            '000001', 'D', data, database_path='/tmp/test_asset.duckdb'
        )

    def test_add_kline_failure_returns_false(self):
        """T01b: insert_kline_data 失败时不走成功分支"""
        udm = _build_udm()
        udm.duckdb_operations.insert_kline_data = MagicMock(
            return_value=InsertResult(success=False, rows_inserted=0, execution_time=0.1, batch_count=0,
                                      error_message='mock failure')
        )
        data = _make_kdata_df(5)

        result = udm.add_kline('000001', 'D', data)

        self.assertFalse(result)
        udm._cache_data.assert_not_called()

    # ---------------------------------------------------------------- T02
    def test_store_to_duckdb_uses_historical_kline_data(self):
        """T02: _store_to_duckdb 使用 historical_kline_data 表名且完成列名映射"""
        udm = _build_udm()
        udm.duckdb_operations.insert_dataframe = MagicMock(
            return_value=InsertResult(success=True, rows_inserted=10, execution_time=0.1, batch_count=1)
        )
        data = _make_kdata_df(10)

        udm._store_to_duckdb(data, '000001', 'D')

        call_kwargs = udm.duckdb_operations.insert_dataframe.call_args.kwargs
        self.assertEqual(call_kwargs['table_name'], 'historical_kline_data')
        self.assertEqual(call_kwargs['database_path'], '/tmp/test_asset.duckdb')
        self.assertTrue(call_kwargs['upsert'])

        store_df = call_kwargs['data']
        for col in ('symbol', 'timestamp', 'frequency', 'data_source'):
            self.assertIn(col, store_df.columns)
        self.assertEqual(store_df['symbol'].iloc[0], '000001')
        self.assertEqual(store_df['frequency'].iloc[0], '1d')
        self.assertEqual(store_df['data_source'].iloc[0], 'unified_data_manager')
        self.assertNotIn('datetime', store_df.columns)
        self.assertNotIn('code', store_df.columns)

    # ---------------------------------------------------------------- T03
    def test_insert_kline_data_column_mapping(self):
        """T03: insert_kline_data 完成 code→symbol / date→timestamp 列名映射"""
        ops = object.__new__(DuckDBOperations)
        ops.connection_manager = MagicMock()
        ops.table_manager = MagicMock()
        with patch.object(ops, 'insert_dataframe',
                          return_value=InsertResult(success=True, rows_inserted=3,
                                                    execution_time=0.1, batch_count=1)) as mock_insert, \
             patch.object(ops, '_get_default_asset_database_path', return_value='/tmp/test_asset.duckdb'):
            data = _make_kdata_df(3, use_code=True, use_date=True)
            result = ops.insert_kline_data('000001', 'D', data)

        self.assertTrue(result.success)
        call_kwargs = mock_insert.call_args.kwargs
        self.assertEqual(call_kwargs['table_name'], 'historical_kline_data')
        self.assertEqual(call_kwargs['database_path'], '/tmp/test_asset.duckdb')
        self.assertTrue(call_kwargs['upsert'])
        self.assertEqual(call_kwargs['conflict_columns'], ['symbol', 'data_source', 'timestamp', 'frequency'])

        store_df = call_kwargs['data']
        for col in ('symbol', 'timestamp', 'frequency', 'data_source',
                    'open', 'high', 'low', 'close', 'volume', 'amount'):
            self.assertIn(col, store_df.columns)
        self.assertEqual(store_df['symbol'].iloc[0], '000001')
        self.assertEqual(store_df['frequency'].iloc[0], '1d')
        self.assertEqual(store_df['data_source'].iloc[0], 'unified_data_manager')
        # 原列已被映射/过滤, 不再残留
        for col in ('code', 'date', 'datetime'):
            self.assertNotIn(col, store_df.columns)

    def test_insert_kline_data_default_db_path(self):
        """T03b: 未传 database_path 时使用默认资产库路径"""
        ops = object.__new__(DuckDBOperations)
        ops.connection_manager = MagicMock()
        ops.table_manager = MagicMock()
        with patch.object(ops, 'insert_dataframe',
                          return_value=InsertResult(success=True, rows_inserted=3,
                                                    execution_time=0.1, batch_count=1)) as mock_insert, \
             patch.object(ops, '_get_default_asset_database_path', return_value='/tmp/default.duckdb'):
            data = _make_kdata_df(3)
            result = ops.insert_kline_data('000001', 'D', data)

        self.assertTrue(result.success)
        self.assertEqual(mock_insert.call_args.kwargs['database_path'], '/tmp/default.duckdb')

    # ---------------------------------------------------------------- T04
    def test_delete_kline_data_uses_symbol_and_frequency(self):
        """T04: delete_kline_data 按 symbol + frequency (DuckDB frequency) 删除"""
        ops = object.__new__(DuckDBOperations)
        ops.connection_manager = MagicMock()
        conn = MagicMock()
        ops.connection_manager.get_connection.return_value.__enter__.return_value = conn

        result = ops.delete_kline_data('000001', 'D', database_path='/tmp/test_asset.duckdb')

        self.assertTrue(result)
        conn.execute.assert_called_once()
        sql, params = conn.execute.call_args[0]
        self.assertIn('DELETE FROM historical_kline_data', sql)
        self.assertIn('symbol = ?', sql)
        self.assertIn('frequency = ?', sql)
        self.assertEqual(params, ['000001', '1d'])

    # ---------------------------------------------------------------- T05
    def test_delete_kline_calls_delete_kline_data(self):
        """T05: delete_kline 调用 delete_kline_data 且参数正确"""
        udm = _build_udm()
        udm.duckdb_operations.delete_kline_data = MagicMock(return_value=True)

        result = udm.delete_kline('000001', 'D')

        self.assertTrue(result)
        udm.duckdb_operations.delete_kline_data.assert_called_once_with(
            '000001', 'D', database_path='/tmp/test_asset.duckdb'
        )


if __name__ == '__main__':
    unittest.main()
