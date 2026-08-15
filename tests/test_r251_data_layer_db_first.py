#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R251 回归测试: 数据加载 DB 优先架构（根本原因修复）

核心需求: 数据加载时优先数据库，数据库缺失的数据通过可用插件补齐并落库。

验证点:
- T01 DuckDB 无数据 → 触发插件补齐（_fetch_kdata_from_tet）→ 落库 store_standardized_data → 返回数据
- T02 DuckDB 有数据 → 直接返回，不触发插件补齐、不落库
- T03 数据库与插件均无数据 → 返回空 DataFrame（不抛异常）
- T04 落库失败仅告警，不影响补齐数据返回
"""
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd


def _make_kdata_df(n: int = 10) -> pd.DataFrame:
    """构造标准化K线DataFrame（字段与TET标准化输出一致）"""
    dates = pd.date_range('2024-01-01', periods=n, freq='D')
    return pd.DataFrame({
        'datetime': dates,
        'open': [10.0 + i * 0.1 for i in range(n)],
        'high': [10.5 + i * 0.1 for i in range(n)],
        'low': [9.5 + i * 0.1 for i in range(n)],
        'close': [10.2 + i * 0.1 for i in range(n)],
        'volume': [1000000 + i * 1000 for i in range(n)],
        'amount': [10000000 + i * 10000 for i in range(n)],
        'adj_close': [10.2 + i * 0.1 for i in range(n)],
    })


def _build_udm() -> 'object':
    """构造轻量 UnifiedDataManager 实例（跳过 __init__，避免重型依赖）"""
    from core.services.unified_data_manager import UnifiedDataManager

    udm = object.__new__(UnifiedDataManager)
    udm.duckdb_available = True
    udm.asset_manager = MagicMock()
    udm.asset_manager.store_standardized_data = MagicMock(return_value=True)
    udm._get_cached_data = MagicMock(return_value=None)
    udm._cache_data = MagicMock()
    udm._get_kdata_from_duckdb = MagicMock(return_value=pd.DataFrame())
    return udm


class TestDataLayerDBFirst(unittest.TestCase):
    """数据加载 DB 优先架构回归测试"""

    def test_db_miss_plugin_fallback_and_persist(self):
        """T01: DuckDB 无数据 → 插件补齐 → 落库 → 返回数据"""
        from core.plugin_types import AssetType, DataType

        udm = _build_udm()
        expected_df = _make_kdata_df(10)

        # R290: R275 起 _fetch_kdata_from_tet 返回 (df, plugin_id) 元组契约，
        # mock 需对齐生产契约，否则解包失败导致测试假失败。
        with patch.object(udm, '_fetch_kdata_from_tet', return_value=(expected_df, 'test_plugin')) as mock_fetch:
            result = udm.get_kdata('000001', period='D', count=365, asset_type=AssetType.STOCK_A)

        # 插件补齐被调用一次
        mock_fetch.assert_called_once()
        # 落库被调用一次，且参数为 (数据, 资产类型, HISTORICAL_KLINE)
        udm.asset_manager.store_standardized_data.assert_called_once()
        args, kwargs = udm.asset_manager.store_standardized_data.call_args
        persist_df = args[0]
        self.assertEqual(args[1], AssetType.STOCK_A)
        self.assertEqual(args[2], DataType.HISTORICAL_KLINE)
        # 落库副本补齐了 symbol/frequency/data_source/timestamp 关键列
        for col in ('symbol', 'frequency', 'data_source', 'timestamp'):
            self.assertIn(col, persist_df.columns)
        # 返回数据非空且与补齐数据一致
        self.assertFalse(result.empty)
        self.assertEqual(len(result), 10)

    def test_db_hit_skips_fallback_and_persist(self):
        """T02: DuckDB 有数据 → 直接返回，不触发插件补齐与落库"""
        udm = _build_udm()
        db_df = _make_kdata_df(5)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)

        with patch.object(udm, '_fetch_kdata_from_tet') as mock_fetch:
            result = udm.get_kdata('000001', period='D', count=365)

        self.assertEqual(len(result), 5)
        mock_fetch.assert_not_called()
        udm.asset_manager.store_standardized_data.assert_not_called()

    def test_db_and_plugin_both_empty_returns_empty(self):
        """T03: 数据库与插件均无数据 → 返回空 DataFrame（不抛异常）"""
        udm = _build_udm()

        with patch.object(udm, '_fetch_kdata_from_tet', return_value=(pd.DataFrame(), None)):
            result = udm.get_kdata('000001', period='D', count=365)

        self.assertTrue(result.empty)
        udm.asset_manager.store_standardized_data.assert_not_called()

    def test_persist_failure_does_not_block_data_return(self):
        """T04: 落库失败仅告警，补齐数据仍正常返回"""
        udm = _build_udm()
        expected_df = _make_kdata_df(8)
        udm.asset_manager.store_standardized_data = MagicMock(
            side_effect=Exception('duckdb write failure'))

        with patch.object(udm, '_fetch_kdata_from_tet', return_value=(expected_df, 'test_plugin')):
            result = udm.get_kdata('000001', period='D', count=365)

        # 落库异常被吞掉，数据依然返回
        self.assertFalse(result.empty)
        self.assertEqual(len(result), 8)

    def test_tet_failure_returns_empty(self):
        """T05: 插件补齐抛异常 → 返回空 DataFrame（不抛异常）"""
        udm = _build_udm()

        with patch.object(udm, '_fetch_kdata_from_tet', side_effect=Exception('network error')):
            result = udm.get_kdata('000001', period='D', count=365)

        self.assertTrue(result.empty)


if __name__ == '__main__':
    unittest.main()
