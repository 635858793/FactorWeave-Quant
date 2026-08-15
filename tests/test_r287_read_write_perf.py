#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R287 专项测试：读库写库性能修复（P0/P1 + P2-a 真 bug）

审计发现（经子智能体交叉验证 + 主智能体二次验证，全部 100% 确认为真）：
- P0-1 质量分缓存 0 生产调用：_get_quality_score_from_cache 的 key 为 4 元组
  (symbol/frequency/data_source/check_date)，而读路径 _get_db_quality_score 只按
  symbol+frequency 查"最近一次质量分"→ key 永远不匹配 → 每次读前校验直查 DB。
  修复：key 统一为 symbol+frequency，_get_db_quality_score 先查缓存、DB 结果写回。
- P0-2 view_query / unified_best_quality_kline 视图内 latest_dqm 子查询每次全表
  GROUP BY data_quality_monitor（逐日累积，聚合成本线性增长），无物化。
  修复：新增 monitor_latest 物化表（每 symbol+data_source+frequency 仅一行，
  INSERT OR REPLACE 幂等维护，含历史预填），视图/查询直接 JOIN。
- P2-a 真 bug：_incremental_fill_kdata 落库 merged 全量（DB 已有行白写）且未传
  data_source → 恒回退 'tet_plugin'，与 DB 中既有 (symbol, 'tongdaxin', ...) 主键
  不匹配 → 插入重复行。修复：只插新增行 all_new + 透传 TET failover 真实成功源。
- P1-1 同一批数据被多次评估：_upsert_data 内 _validate_kline_data_quality 与
  _evaluate_and_record_quality 内 L1552 完全重复（store_standardized_data 已统一
  评估过）。修复：删除 _upsert_data 内重复校验。
- P1-2 单次落库 3 次元数据查询零缓存（duckdb_tables + DESCRIBE + duckdb_columns）。
  修复：会话级缓存（db_path|table_name），命中跳过查询。

全部离线测试：mock 连接与查询，不产生真实 DB/网络 IO。
"""

import os
import sys
import threading
import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.asset_database_manager import AssetSeparatedDatabaseManager
from core.plugin_types import AssetType, DataType
from core.services.unified_data_manager import UnifiedDataManager


def _read_source(rel_path: str) -> str:
    with open(os.path.join(os.path.dirname(__file__), '..', rel_path),
              encoding='utf-8') as f:
        return f.read()


def _make_udm() -> UnifiedDataManager:
    """轻量构造 UDM 实例（跳过 __init__，仅设置被测方法所需属性）"""
    udm = object.__new__(UnifiedDataManager)
    udm._quality_score_cache = {}
    udm._quality_cache_lock = threading.RLock()
    udm._quality_cache_ttl = 300
    udm._kdata_incremental_checked = {}
    udm._kdata_history_exhausted = {}
    udm._kdata_incremental_ttl = 300
    udm.duckdb_available = False
    udm.duckdb_operations = None
    udm.asset_manager = None
    return udm


# ---------------------------------------------------------------------------
# P0-1：质量分缓存 key 统一 + 读前校验接通缓存
# ---------------------------------------------------------------------------
class TestQualityScoreCacheUnified(unittest.TestCase):
    """缓存 key 统一为 symbol+frequency，读路径命中不再直查 DB"""

    def test_cache_key_unified_read_matches_write(self):
        udm = _make_udm()
        # 写路径传 4 参数（兼容调用点），读路径只传 symbol+frequency → 必须命中
        udm._set_quality_score_to_cache('000001', '1d', 'tongdaxin', '2026-08-11', 88.5)
        self.assertEqual(udm._get_quality_score_from_cache('000001', '1d'), 88.5)
        self.assertIn('000001_1d', udm._quality_score_cache)

    def test_cache_miss_returns_none(self):
        udm = _make_udm()
        self.assertIsNone(udm._get_quality_score_from_cache('000002', '1d'))

    def test_db_quality_score_hits_cache_without_db(self):
        udm = _make_udm()
        udm.duckdb_available = True
        udm.duckdb_operations = MagicMock()
        udm.asset_manager = MagicMock()
        udm.asset_manager.get_database_path.return_value = 'fake.db'
        udm._set_quality_score_to_cache('000001', '1d', '', '', 90.0)
        score = udm._get_db_quality_score('000001', '1d')
        self.assertEqual(score, 90.0)
        # 命中缓存 → execute_query 不应被调用
        udm.duckdb_operations.execute_query.assert_not_called()

    def test_db_quality_score_fetches_and_writes_back_cache(self):
        udm = _make_udm()
        udm.duckdb_available = True
        udm.duckdb_operations = MagicMock()

        class FakeResult:
            success = True
            data = pd.DataFrame({'quality_score': [76.5]})

        udm.duckdb_operations.execute_query.return_value = FakeResult()
        udm.asset_manager = MagicMock()
        udm.asset_manager.get_database_path.return_value = 'fake.db'

        score1 = udm._get_db_quality_score('000003', '1d')
        self.assertEqual(score1, 76.5)
        self.assertEqual(udm.duckdb_operations.execute_query.call_count, 1)
        # 第二次调用 → 缓存命中，不再直查 DB
        score2 = udm._get_db_quality_score('000003', '1d')
        self.assertEqual(score2, 76.5)
        self.assertEqual(udm.duckdb_operations.execute_query.call_count, 1)


# ---------------------------------------------------------------------------
# P0-2：monitor_latest 物化表
# ---------------------------------------------------------------------------
class TestMonitorLatestMaterialized(unittest.TestCase):
    """monitor_latest 表定义 + 视图/查询 JOIN 改造 + 落库同步维护"""

    def setUp(self):
        self.mgr = object.__new__(AssetSeparatedDatabaseManager)
        self.mgr._table_schemas = AssetSeparatedDatabaseManager._initialize_table_schemas(self.mgr)
        self.mgr._write_lock = threading.Lock()
        self.mgr._monitor_latest_table_ready = False

    def test_table_schema_declares_monitor_latest(self):
        self.assertIn('monitor_latest', self.mgr._table_schemas)
        schema = self.mgr._table_schemas['monitor_latest']
        self.assertIn('PRIMARY KEY (symbol, data_source, frequency)', schema)

    def test_view_joins_monitor_latest_not_group_by(self):
        view_sql = self.mgr._table_schemas['unified_best_quality_kline']
        self.assertIn('LEFT JOIN monitor_latest dqm ON', view_sql)
        self.assertNotIn('GROUP BY symbol, data_source, frequency', view_sql)

    def test_view_query_joins_monitor_latest(self):
        src = _read_source('core/services/unified_data_manager.py')
        # view_query 是运行时 SQL，直接引用 monitor_latest 且不再内嵌全表聚合子查询
        self.assertIn('LEFT JOIN monitor_latest dqm ON', src)
        self.assertNotIn('FROM data_quality_monitor dqm2', src)

    def test_import_engine_syncs_monitor_latest(self):
        src = _read_source('core/importdata/import_execution_engine.py')
        self.assertIn('INSERT OR REPLACE INTO monitor_latest', src)

    def test_ensure_monitor_latest_table_creates_once(self):
        conn = Mock()
        conn.execute.return_value = None
        self.mgr._ensure_monitor_latest_table(conn)
        self.assertEqual(conn.execute.call_count, 1)
        self.assertTrue(self.mgr._monitor_latest_table_ready)
        # 已就绪 → 再次调用不再执行 DDL
        self.mgr._ensure_monitor_latest_table(conn)
        self.assertEqual(conn.execute.call_count, 1)

    def test_evaluate_record_quality_syncs_monitor_latest(self):
        # _evaluate_and_record_quality 落库 monitor 后必须同步 upsert monitor_latest
        src = _read_source('core/asset_database_manager.py')
        self.assertIn('_ensure_monitor_latest_table(conn)', src)
        self.assertIn('INSERT OR REPLACE INTO monitor_latest', src)


# ---------------------------------------------------------------------------
# P2-a：增量落库只插新增行 + 透传真实 data_source
# ---------------------------------------------------------------------------
class TestIncrementalFillUsesAllNewAndSource(unittest.TestCase):
    """增量补齐落库：只插新增行（all_new），data_source 透传 TET 成功源"""

    def _base_df(self, dts):
        return pd.DataFrame({
            'datetime': dts,
            'open': [10.0] * len(dts),
            'high': [11.0] * len(dts),
            'low': [9.0] * len(dts),
            'close': [10.5] * len(dts),
            'volume': [1000] * len(dts),
            'amount': [10500.0] * len(dts),
        })

    def test_only_new_rows_persisted_with_real_source(self):
        udm = _make_udm()
        udm.duckdb_available = True

        # DB 已有 5 天（2026-01-01 ~ 01-05），count=30 → 场景B 历史补齐
        db_df = self._base_df(pd.date_range('2026-01-01', periods=5, freq='D'))
        # 增量拉回更早 3 天历史（来源 tongdaxin）
        new_df = self._base_df(pd.date_range('2025-12-29', periods=3, freq='D'))

        # 场景A（隔天增量）拉不到 → (None, None)；场景B（历史补齐）→ (new_df, 'tongdaxin')
        udm._fetch_kdata_from_tet = Mock(side_effect=[(None, None), (new_df, 'tongdaxin')])
        udm._persist_kdata_to_duckdb = Mock()

        result = udm._incremental_fill_kdata(
            '000001', '1d', 30, db_df, AssetType.STOCK_A)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 8)  # 5 旧 + 3 新

        # 落库必须只插新增行（3 行），且透传真实数据源
        udm._persist_kdata_to_duckdb.assert_called_once()
        args, kwargs = udm._persist_kdata_to_duckdb.call_args
        self.assertEqual(len(args[0]), 3)
        self.assertEqual(kwargs.get('data_source'), 'tongdaxin')

    def test_no_new_rows_no_persist(self):
        udm = _make_udm()
        udm.duckdb_available = True
        # 增量拉回的行全部已在 DB（去重后 all_new 为空）
        same_df = self._base_df(pd.date_range('2026-01-01', periods=5, freq='D'))
        udm._fetch_kdata_from_tet = Mock(side_effect=[(None, None), (same_df, 'tongdaxin')])
        udm._persist_kdata_to_duckdb = Mock()

        result = udm._incremental_fill_kdata(
            '000001', '1d', 30, same_df, AssetType.STOCK_A)
        self.assertIsNone(result)
        udm._persist_kdata_to_duckdb.assert_not_called()


# ---------------------------------------------------------------------------
# P1-1：消除 _upsert_data 内重复质量校验
# ---------------------------------------------------------------------------
class TestNoDuplicateQualityValidation(unittest.TestCase):
    """store_standardized_data 已统一评估（_evaluate_and_record_quality 含 OHLC
    校验），_upsert_data 内不再重复调用 _validate_kline_data_quality"""

    def test_upsert_no_longer_validates(self):
        src = _read_source('core/asset_database_manager.py')
        # _upsert_data 方法体
        upsert_start = src.index('def _upsert_data(')
        upsert_body = src[upsert_start:]
        next_def = upsert_body.find('\n    def ')
        if next_def != -1:
            upsert_body = upsert_body[:next_def]
        self.assertNotIn('self._validate_kline_data_quality(data)', upsert_body)

    def test_evaluate_still_validates(self):
        src = _read_source('core/asset_database_manager.py')
        # 评估入口仍保留 OHLC 校验（不误删）
        self.assertIn('_validate_kline_data_quality(data)', src)


# ---------------------------------------------------------------------------
# P1-2：表结构/列元数据会话级缓存
# ---------------------------------------------------------------------------
class TestSchemaMetadataCache(unittest.TestCase):
    """_ensure_table_exists / _get_table_columns 命中缓存后跳过元数据查询"""

    def setUp(self):
        self.mgr = object.__new__(AssetSeparatedDatabaseManager)
        self.mgr._table_exists_cache = {}
        self.mgr._table_columns_cache = {}
        self.mgr._generate_create_table_sql = Mock(return_value='CREATE TABLE x()')
        self.mgr._create_table_indexes = Mock()
        self.mgr._migrate_table_schema = Mock()

    def test_ensure_table_exists_cached(self):
        conn = Mock()
        conn.database_path = 'db_a.db'
        conn.execute.return_value.fetchone.return_value = (1,)  # 表已存在

        self.mgr._ensure_table_exists(conn, 'historical_kline_data', None, DataType.HISTORICAL_KLINE)
        first_calls = conn.execute.call_count
        self.assertEqual(first_calls, 1)  # 仅 duckdb_tables 存在性查询

        self.mgr._ensure_table_exists(conn, 'historical_kline_data', None, DataType.HISTORICAL_KLINE)
        # 二次调用命中缓存，不再查询
        self.assertEqual(conn.execute.call_count, first_calls)

    def test_get_table_columns_cached(self):
        conn = Mock()
        conn.database_path = 'db_b.db'
        conn.execute.return_value.fetchall.return_value = [('symbol',), ('timestamp',)]

        cols1 = self.mgr._get_table_columns(conn, 'historical_kline_data')
        cols2 = self.mgr._get_table_columns(conn, 'historical_kline_data')
        self.assertEqual(cols1, ['symbol', 'timestamp'])
        self.assertEqual(cols2, ['symbol', 'timestamp'])
        self.assertEqual(conn.execute.call_count, 1)  # 第二次命中缓存


if __name__ == '__main__':
    unittest.main()
