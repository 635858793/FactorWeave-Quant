#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R263: K线增量更新功能测试（TDD）

覆盖 UnifiedDataManager 新增的增量补齐链路：
1. _fetch_kdata_from_tet 支持 start_date/end_date 区间透传
2. _incremental_fill_kdata 场景A（隔天增量）/ 场景B（历史不足）缺口计算与合并
3. 合并去重 / 升序 / 落库（_persist_kdata_to_duckdb）
4. 无新增时标记历史尽头（防重复全量拉取）
5. TTL 频率限制（防无谓联网）
6. get_kdata 集成：DB 命中 + 增量补齐 + 超 count 截断

全部离线测试：_fetch_kdata_from_tet 与 DuckDB 均 mock，不产生网络/DB IO。
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.services.unified_data_manager import UnifiedDataManager
from core.plugin_types import AssetType


def _make_udm() -> UnifiedDataManager:
    """绕过 __init__ 构造轻量 UDM 实例（避免重型初始化与真实 IO）"""
    udm = UnifiedDataManager.__new__(UnifiedDataManager)
    udm._kdata_history_exhausted = {}
    udm._kdata_incremental_checked = {}
    udm._kdata_incremental_ttl = 6 * 3600
    udm.asset_manager = MagicMock()
    udm.tet_enabled = True
    udm.tet_pipeline = MagicMock()
    udm.duckdb_available = True
    udm.multi_cache = None
    udm.cache_manager = None
    return udm


def _ohlcv(start: str, days: int) -> pd.DataFrame:
    """构造升序 OHLCV K线（datetime 为 pd.Timestamp，day 步长）"""
    dts = pd.date_range(start=start, periods=days, freq='D')
    return pd.DataFrame({
        'datetime': dts,
        'open': [10.0] * days,
        'high': [11.0] * days,
        'low': [9.0] * days,
        'close': [10.5] * days,
        'volume': [1000] * days,
        'amount': [10500.0] * days,
    })


class TestFetchKdataFromTetInterval(unittest.TestCase):
    """_fetch_kdata_from_tet 区间透传测试"""

    def test_start_end_date_passed_to_standard_query(self):
        udm = _make_udm()
        mock_result = MagicMock()
        mock_result.data = _ohlcv('2026-01-01', 5)
        udm.tet_pipeline.process = MagicMock(return_value=mock_result)

        # R282: 适配 R275 返回值语义 (df, plugin_id)
        df, plugin_id = udm._fetch_kdata_from_tet(
            '300973', 'D', 365, AssetType.STOCK_A,
            start_date='20260801', end_date=None)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 5)
        # 断言 StandardQuery 构造透传了区间
        call_kwargs = udm.tet_pipeline.process.call_args[0][0]
        self.assertEqual(call_kwargs.start_date, '20260801')
        self.assertIsNone(call_kwargs.end_date)
        self.assertEqual(call_kwargs.extra_params['count'], 365)

    def test_tet_disabled_returns_none(self):
        udm = _make_udm()
        udm.tet_enabled = False
        # R282: 适配 R275 返回值语义：失败返回 (None, None)
        df, plugin_id = udm._fetch_kdata_from_tet('300973', 'D', 100, AssetType.STOCK_A)
        self.assertIsNone(df)
        self.assertIsNone(plugin_id)


class TestIncrementalFillKdata(unittest.TestCase):
    """_incremental_fill_kdata 缺口计算/合并/去重/落库测试"""

    def setUp(self):
        self.udm = _make_udm()

    def test_scene_a_next_day_increment(self):
        """场景A：DB 最新K线早于今天 → 只拉最新日期之后的新数据并合并落库"""
        db_df = _ohlcv((datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d'), 30)
        today = datetime.now().date()
        latest = pd.Timestamp(db_df['datetime'].max()).date()
        self.assertLess(latest, today)  # 前置：确实过期

        new_df = _ohlcv((latest + timedelta(days=1)).strftime('%Y-%m-%d'),
                        (today - latest).days)
        self.udm._fetch_kdata_from_tet = MagicMock(return_value=(new_df, 'tet_plugin'))
        self.udm._persist_kdata_to_duckdb = MagicMock()

        # count=30 与 DB 条数一致 → 场景B（历史不足）不触发，仅测场景A
        merged = self.udm._incremental_fill_kdata(
            '300973', 'D', count=30, db_df=db_df, asset_type=AssetType.STOCK_A)

        self.assertIsNotNone(merged)
        self.assertEqual(len(merged), len(db_df) + len(new_df))
        # 升序
        self.assertTrue(merged['datetime'].is_monotonic_increasing)
        # 无重复 datetime
        self.assertEqual(merged['datetime'].nunique(), len(merged))
        # 落库被调用（upsert 回库）
        self.udm._persist_kdata_to_duckdb.assert_called_once()
        # 仅场景A 1 次网络调用，start_date 应为 DB 最新日期 + 1 天（YYYYMMDD）
        self.assertEqual(self.udm._fetch_kdata_from_tet.call_count, 1)
        start_arg = self.udm._fetch_kdata_from_tet.call_args.kwargs['start_date']
        expect_start = (pd.Timestamp(db_df['datetime'].max()) + pd.Timedelta(days=1)).strftime('%Y%m%d')
        self.assertEqual(start_arg, expect_start)

    def test_scene_b_history_fill(self):
        """场景B：DB 条数 < count → 拉取更早历史补齐缺口"""
        # DB 最新日期 = 今天 → 场景A（隔天增量）不触发，仅测场景B
        end = pd.Timestamp.now().normalize()
        db_dates = pd.date_range(end=end, periods=50, freq='D')
        db_df = pd.DataFrame({'datetime': db_dates, 'open': 10.0, 'high': 11.0,
                              'low': 9.0, 'close': 10.5, 'volume': 1000, 'amount': 10500.0})
        # 返回更早 40 条历史（紧贴 DB 最早日期之前）
        history_df = _ohlcv((db_dates[0] - pd.Timedelta(days=40)).strftime('%Y-%m-%d'), 40)
        self.udm._fetch_kdata_from_tet = MagicMock(return_value=(history_df, 'tet_plugin'))
        self.udm._persist_kdata_to_duckdb = MagicMock()

        merged = self.udm._incremental_fill_kdata(
            '300973', 'D', count=100, db_df=db_df, asset_type=AssetType.STOCK_A)

        self.assertIsNotNone(merged)
        self.assertEqual(len(merged), 90)
        self.assertTrue(merged['datetime'].is_monotonic_increasing)
        # 仅场景B 1 次网络调用，end_date 应为 DB 最早日期 - 1 天
        self.assertEqual(self.udm._fetch_kdata_from_tet.call_count, 1)
        end_arg = self.udm._fetch_kdata_from_tet.call_args.kwargs['end_date']
        expect_end = (pd.Timestamp(db_df['datetime'].min()) - pd.Timedelta(days=1)).strftime('%Y%m%d')
        self.assertEqual(end_arg, expect_end)

    def test_no_new_data_marks_history_exhausted(self):
        """场景B 拉到的新数据全在 DB 已有 → 返回 None 并标记历史尽头（防重复全量拉取）"""
        # DB 最新日期 = 今天 → 场景A 不触发；count 大于条数 → 仅场景B
        end = pd.Timestamp.now().normalize()
        db_dates = pd.date_range(end=end, periods=50, freq='D')
        db_df = pd.DataFrame({'datetime': db_dates, 'open': 10.0, 'high': 11.0,
                              'low': 9.0, 'close': 10.5, 'volume': 1000, 'amount': 10500.0})
        # 拉回与 DB 完全重叠的数据（东财 end 边界可能重复返回）
        overlap_df = db_df.head(10).copy()
        self.udm._fetch_kdata_from_tet = MagicMock(return_value=(overlap_df, 'tet_plugin'))

        merged = self.udm._incremental_fill_kdata(
            '300973', 'D', count=100, db_df=db_df, asset_type=AssetType.STOCK_A)

        self.assertIsNone(merged)
        # 历史尽头标记已写入
        check_key = f"{AssetType.STOCK_A.value}|300973|1d"
        self.assertIn(check_key, self.udm._kdata_history_exhausted)

        # 第二次调用：历史尽头命中 → 场景B 不再联网（场景A 未触发，总调用 0 次）
        self.udm._kdata_incremental_checked = {}
        self.udm._fetch_kdata_from_tet.reset_mock()
        merged2 = self.udm._incremental_fill_kdata(
            '300973', 'D', count=100, db_df=db_df, asset_type=AssetType.STOCK_A)
        self.assertIsNone(merged2)
        self.udm._fetch_kdata_from_tet.assert_not_called()

    def test_ttl_throttle(self):
        """TTL 内不重复增量检查（防无谓联网）"""
        db_df = _ohlcv((datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d'), 30)
        self.udm._fetch_kdata_from_tet = MagicMock()

        self.udm._incremental_fill_kdata('300973', 'D', 100, db_df, AssetType.STOCK_A)
        first_calls = self.udm._fetch_kdata_from_tet.call_count

        # 立即二次调用 → TTL 内跳过
        self.udm._incremental_fill_kdata('300973', 'D', 100, db_df, AssetType.STOCK_A)
        self.assertEqual(self.udm._fetch_kdata_from_tet.call_count, first_calls)

    def test_fetch_failure_returns_none(self):
        """拉取失败（返回 None）→ 静默返回 None，不影响主流程"""
        db_df = _ohlcv((datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d'), 30)
        # R282: 适配 R275 返回值语义（失败返回 (None, None)）
        self.udm._fetch_kdata_from_tet = MagicMock(return_value=(None, None))
        result = self.udm._incremental_fill_kdata(
            '300973', 'D', 100, db_df, AssetType.STOCK_A)
        self.assertIsNone(result)


class TestPersistKdataToDuckdb(unittest.TestCase):
    """_persist_kdata_to_duckdb 落库列补齐测试"""

    def test_adds_required_columns_and_calls_store(self):
        udm = _make_udm()
        df = _ohlcv('2026-01-01', 5)  # 仅 datetime/OHLCV
        udm._persist_kdata_to_duckdb(df, '300973', 'D', AssetType.STOCK_A)

        stored_df = udm.asset_manager.store_standardized_data.call_args[0][0]
        self.assertIn('timestamp', stored_df.columns)
        self.assertIn('symbol', stored_df.columns)
        self.assertIn('frequency', stored_df.columns)
        self.assertIn('data_source', stored_df.columns)
        self.assertEqual(stored_df['symbol'].iloc[0], '300973')
        self.assertEqual(stored_df['frequency'].iloc[0], '1d')
        self.assertEqual(stored_df['data_source'].iloc[0], 'tet_plugin')

    def test_noop_without_asset_manager(self):
        udm = _make_udm()
        udm.asset_manager = None
        udm._persist_kdata_to_duckdb(_ohlcv('2026-01-01', 3), '300973', 'D', AssetType.STOCK_A)
        # 不抛异常即可


class TestGetKdataIncrementalIntegration(unittest.TestCase):
    """get_kdata 集成：DB 命中 → 增量补齐 → 超 count 截断"""

    def test_db_hit_with_increment(self):
        udm = _make_udm()
        db_df = _ohlcv((datetime.now() - timedelta(days=40)).strftime('%Y-%m-%d'), 30)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._get_cached_data = MagicMock(return_value=None)
        udm._cache_data = MagicMock()

        # 增量返回 5 条新数据 → 合并后 35 条，不超过 count=100
        today = datetime.now().date()
        latest = pd.Timestamp(db_df['datetime'].max()).date()
        new_df = _ohlcv((latest + timedelta(days=1)).strftime('%Y-%m-%d'),
                        (today - latest).days)
        udm._fetch_kdata_from_tet = MagicMock(return_value=(new_df, 'tet_plugin'))
        udm._persist_kdata_to_duckdb = MagicMock()

        result = udm.get_kdata('300973', 'D', count=100, asset_type=AssetType.STOCK_A)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), len(db_df) + len(new_df))
        self.assertTrue(result['datetime'].is_monotonic_increasing)
        # 落库被调用（增量数据 upsert 回库）
        udm._persist_kdata_to_duckdb.assert_called_once()

    def test_db_hit_truncates_to_count(self):
        """合并后超过 count → 截断为最近 count 条"""
        udm = _make_udm()
        # DB 120 条（超过请求 100），最新日期过期 → 增量补齐后 125 条
        db_df = _ohlcv((datetime.now() - timedelta(days=140)).strftime('%Y-%m-%d'), 120)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._get_cached_data = MagicMock(return_value=None)
        udm._cache_data = MagicMock()

        today = datetime.now().date()
        latest = pd.Timestamp(db_df['datetime'].max()).date()
        new_df = _ohlcv((latest + timedelta(days=1)).strftime('%Y-%m-%d'),
                        (today - latest).days)
        udm._fetch_kdata_from_tet = MagicMock(return_value=(new_df, 'tet_plugin'))
        udm._persist_kdata_to_duckdb = MagicMock()

        result = udm.get_kdata('300973', 'D', count=100, asset_type=AssetType.STOCK_A)

        self.assertEqual(len(result), 100)
        # 截断后仍为最近 100 条（升序）
        self.assertTrue(result['datetime'].is_monotonic_increasing)
        self.assertEqual(pd.Timestamp(result['datetime'].max()),
                         pd.Timestamp(new_df['datetime'].max()))

    def test_db_empty_fallback_persists(self):
        """DB 无数据 → 插件全量补齐并落库"""
        udm = _make_udm()
        udm._get_kdata_from_duckdb = MagicMock(return_value=pd.DataFrame())
        udm._get_cached_data = MagicMock(return_value=None)
        udm._cache_data = MagicMock()
        full_df = _ohlcv((datetime.now() - timedelta(days=100)).strftime('%Y-%m-%d'), 100)
        udm._fetch_kdata_from_tet = MagicMock(return_value=(full_df, 'tet_plugin'))
        udm._persist_kdata_to_duckdb = MagicMock()

        result = udm.get_kdata('300973', 'D', count=100, asset_type=AssetType.STOCK_A)

        self.assertIsNotNone(result)
        self.assertEqual(len(result), 100)
        udm._persist_kdata_to_duckdb.assert_called_once()


if __name__ == '__main__':
    unittest.main()
