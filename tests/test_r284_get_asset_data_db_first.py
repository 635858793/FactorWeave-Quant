#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R284 专项测试：UI 主链路 K线 DB 优先（get_asset_data 接入 DB 直读 + 增量回源 + 落库）

背景（三审计交叉验证 100% 确认）：
- 用户"切换股票每次都重新联网"根因 = UI 主链路
  left_panel → request_data → ChartService → StockService → DataAccess →
  KlineRepository → AssetService.get_historical_data → UDM.get_asset_data
  → tet_pipeline.process(query)，而 get_asset_data 原实现无任何 DB 查询，
  TET 内存缓存键含 symbol 且 TTL 5 分钟，切换股票必然 miss → 每次联网。
- DB 直读+增量+落库闭环（get_kdata L898-967 / _incremental_fill_kdata L1042 /
  _persist_kdata_to_duckdb L969）完整可用，但只挂在 get_kdata 上，主链路不走。

修复：get_asset_data K线分支（unified_data_manager.py L2658-2680）DB 优先：
- DB 命中 → 返回（数据不满足 count 时 _incremental_fill_kdata 自动回源补齐并落库）
- DB 空 → 走 TET 网络管道（成功后 R277 落库）
- 非 K线类型 / 显式日期区间 → 跳过 DB 优先，保持原行为

全部离线测试：DuckDB 与 TET 管道均 mock，不产生网络/DB IO。
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.services.unified_data_manager import UnifiedDataManager
from core.plugin_types import AssetType, DataType


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
    udm._get_enhanced_quality_monitor = MagicMock(return_value=None)
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


class TestGetAssetDataDbFirst(unittest.TestCase):
    """get_asset_data K线 DB 优先分支"""

    def _mock_tet_result(self, df: pd.DataFrame):
        result = MagicMock()
        result.data = df
        result.source_info = {'provider': 'mock_plugin'}
        return result

    def test_db_hit_returns_without_tet(self):
        """DB 命中 → 直接返回 DB 数据，tet_pipeline.process 不被调用（免联网）"""
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 365)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._incremental_fill_kdata = MagicMock(return_value=None)  # 无新增

        out = udm.get_asset_data(
            '300973', AssetType.STOCK_A, DataType.HISTORICAL_KLINE,
            period='D', count=365)

        self.assertIsNotNone(out)
        self.assertEqual(len(out), 365)
        udm.tet_pipeline.process.assert_not_called()
        udm._get_kdata_from_duckdb.assert_called_once()

    def test_db_short_auto_fills_from_source(self):
        """DB 数据不足 count → _incremental_fill_kdata 自动回源补齐并更新库"""
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 300)          # DB 仅 300 条
        filled = _ohlcv('2025-07-01', 400)         # 回源补齐后 400 条
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._incremental_fill_kdata = MagicMock(return_value=filled)

        out = udm.get_asset_data(
            '300973', AssetType.STOCK_A, DataType.HISTORICAL_KLINE,
            period='D', count=400)

        self.assertEqual(len(out), 400)
        udm._incremental_fill_kdata.assert_called_once()
        udm.tet_pipeline.process.assert_not_called()

    def test_db_over_count_truncated(self):
        """DB 数据超过 count → 截断为最新 count 条"""
        udm = _make_udm()
        db_df = _ohlcv('2025-01-01', 500)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._incremental_fill_kdata = MagicMock(return_value=None)

        out = udm.get_asset_data(
            '300973', AssetType.STOCK_A, DataType.HISTORICAL_KLINE,
            period='D', count=400)

        self.assertEqual(len(out), 400)
        self.assertEqual(out.iloc[-1]['datetime'], db_df.iloc[-1]['datetime'])

    def test_db_empty_falls_back_to_tet_and_persists(self):
        """DB 空 → 走 TET 网络管道，成功后落库（R277），并返回管道数据"""
        udm = _make_udm()
        udm._get_kdata_from_duckdb = MagicMock(return_value=pd.DataFrame())
        udm._persist_kdata_to_duckdb = MagicMock()
        tet_df = _ohlcv('2026-01-01', 365)
        udm.tet_pipeline.process = MagicMock(return_value=self._mock_tet_result(tet_df))

        out = udm.get_asset_data(
            '300973', AssetType.STOCK_A, DataType.HISTORICAL_KLINE,
            period='D', count=365)

        udm.tet_pipeline.process.assert_called_once()
        udm._persist_kdata_to_duckdb.assert_called_once()
        self.assertEqual(len(out), 365)

    def test_non_kline_type_skips_db_first(self):
        """非 K线数据类型（资金流）→ 跳过 DB 优先，直接走 TET"""
        udm = _make_udm()
        udm._get_kdata_from_duckdb = MagicMock()
        tet_df = _ohlcv('2026-01-01', 5)
        udm.tet_pipeline.process = MagicMock(return_value=self._mock_tet_result(tet_df))

        out = udm.get_asset_data(
            '300973', AssetType.STOCK_A, DataType.FUND_FLOW,
            period='D')

        udm._get_kdata_from_duckdb.assert_not_called()
        udm.tet_pipeline.process.assert_called_once()
        self.assertEqual(len(out), 5)

    def test_explicit_date_range_skips_db_first(self):
        """显式 start_date/end_date（区间语义）→ 跳过 DB 优先，走 TET 保证区间准确"""
        udm = _make_udm()
        udm._get_kdata_from_duckdb = MagicMock()
        tet_df = _ohlcv('2026-01-01', 5)
        udm.tet_pipeline.process = MagicMock(return_value=self._mock_tet_result(tet_df))

        out = udm.get_asset_data(
            '300973', AssetType.STOCK_A, DataType.HISTORICAL_KLINE,
            period='D', count=365, start_date='20260101', end_date='20260201')

        udm._get_kdata_from_duckdb.assert_not_called()
        udm.tet_pipeline.process.assert_called_once()
        query = udm.tet_pipeline.process.call_args[0][0]
        self.assertEqual(query.start_date, '20260101')
        self.assertEqual(query.end_date, '20260201')


if __name__ == '__main__':
    unittest.main()
