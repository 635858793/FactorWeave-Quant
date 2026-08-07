#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R254 回归测试: 插件数据落库 / 增量同步域 P2 修复

核心需求（R254 交叉验证 100% 实证）:
- T01 failover 落库块移出 for 循环：主插件成功落库 1 次、主失败备选成功落库 1 次、全失败 0 次
- T02 FUNDAMENTAL 取数后落库，且 data_source 使用真实 plugin_id（非 'tet_plugin'）
- T03 tet_data_pipeline.process 不再落库（双写收敛，统一由 unified_data_manager 补齐链路负责）
- T04 K 线 DB 优先：DB 有数据不调插件；DB 无数据/覆盖不足走插件
- T05 三组件缺失时 download_incremental_data 降级为朴素增量路径，不抛异常
"""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
from loguru import logger

from core.plugin_types import AssetType, DataType
from core.services.uni_plugin_data_manager import UniPluginDataManager, RequestContext


def _make_kdata_df(n: int = 10, start: str = '2024-01-01') -> pd.DataFrame:
    """构造标准化K线DataFrame（字段与TET标准化输出一致）"""
    dates = pd.date_range(start, periods=n, freq='D')
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


def _make_db_kline_df(n: int = 10, start: str = '2024-01-01') -> pd.DataFrame:
    """构造模拟 DuckDB 读出的K线 DataFrame（timestamp 列，DB 格式）"""
    df = _make_kdata_df(n, start).copy()
    df['timestamp'] = df.pop('datetime')
    df['symbol'] = '000001'
    df['frequency'] = '1d'
    df['data_source'] = 'tongdaxin'
    return df


def _make_manager() -> 'UniPluginDataManager':
    """构造轻量 UniPluginDataManager 实例（跳过 __init__，避免重型依赖）"""
    mgr = object.__new__(UniPluginDataManager)
    mgr.plugin_center = MagicMock()
    mgr.tet_engine = MagicMock()
    mgr.risk_manager = MagicMock()
    mgr.stats = {
        "total_requests": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "cache_hits": 0,
        "avg_response_time": 0.0
    }
    mgr._unified_cache = None
    mgr._cache_namespace = 'test'
    mgr._cache_ttl = 300
    mgr._asset_db_manager = MagicMock()
    mgr._asset_db_manager.store_standardized_data = MagicMock(return_value=True)
    return mgr


def _make_validation(is_valid: bool = True, quality_score: float = 0.9,
                     plugin_id: str = None) -> MagicMock:
    """构造 ValidationResult mock"""
    val = MagicMock(is_valid=is_valid, quality_score=quality_score)
    if plugin_id is not None:
        val.plugin_id = plugin_id
    return val


def _build_failover_plugin_chain(mgr, plugin, result, validation):
    """装配 failover 成功链路 mock"""
    mgr.plugin_center.get_plugin = MagicMock(return_value=plugin)
    mgr._check_plugin_connection = MagicMock(return_value=True)
    mgr.risk_manager.execute_with_monitoring = MagicMock(return_value=(result, validation))


class TestFailoverPersistOnce(unittest.TestCase):
    """T01: 落库块移出 for 循环，failover 成功后统一落库一次"""

    def test_primary_success_persists_once(self):
        """主插件成功 → 落库 1 次，data_source 为真实插件 id"""
        mgr = _make_manager()
        plugin = MagicMock()
        df = _make_kdata_df(10)
        val = _make_validation(is_valid=True, quality_score=0.9, plugin_id='main_plugin')
        _build_failover_plugin_chain(mgr, plugin, df, val)

        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')
        result, validation = mgr._execute_with_failover(
            ['main_plugin', 'backup_plugin'], 'main_plugin', 'get_kline_data', context,
            {'symbol': '000001'})

        self.assertFalse(result.empty)
        self.assertTrue(validation.is_valid)
        mgr._asset_db_manager.store_standardized_data.assert_called_once()
        args, _ = mgr._asset_db_manager.store_standardized_data.call_args
        persist_df = args[0]
        self.assertEqual(args[1], AssetType.STOCK_A)
        self.assertEqual(args[2], DataType.HISTORICAL_KLINE)
        self.assertEqual(persist_df['data_source'].iloc[0], 'main_plugin')
        self.assertNotEqual(persist_df['data_source'].iloc[0], 'tet_plugin')

    def test_failover_backup_success_persists_once(self):
        """主插件失败、备选成功 → 落库 1 次，data_source 为备选插件 id"""
        mgr = _make_manager()
        plugin = MagicMock()
        df = _make_kdata_df(8)
        backup_val = _make_validation(is_valid=True, quality_score=0.9, plugin_id='backup_plugin')

        def side_effect(plugin_id, method, **kwargs):
            if plugin_id == 'main_plugin':
                return None, _make_validation(is_valid=False, quality_score=0.1)
            return df, backup_val

        mgr.plugin_center.get_plugin = MagicMock(return_value=plugin)
        mgr._check_plugin_connection = MagicMock(return_value=True)
        mgr.risk_manager.execute_with_monitoring = MagicMock(side_effect=side_effect)

        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')
        result, validation = mgr._execute_with_failover(
            ['main_plugin', 'backup_plugin'], 'main_plugin', 'get_kline_data', context,
            {'symbol': '000001'})

        self.assertFalse(result.empty)
        mgr._asset_db_manager.store_standardized_data.assert_called_once()
        args, _ = mgr._asset_db_manager.store_standardized_data.call_args
        persist_df = args[0]
        self.assertEqual(persist_df['data_source'].iloc[0], 'backup_plugin')

    def test_all_failed_persists_zero(self):
        """所有插件失败 → 抛 RuntimeError，落库 0 次"""
        mgr = _make_manager()
        plugin = MagicMock()
        mgr.plugin_center.get_plugin = MagicMock(return_value=plugin)
        mgr._check_plugin_connection = MagicMock(return_value=True)
        mgr.risk_manager.execute_with_monitoring = MagicMock(
            return_value=(None, _make_validation(is_valid=False, quality_score=0.0)))

        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')

        with self.assertRaises(RuntimeError):
            mgr._execute_with_failover(
                ['main_plugin', 'backup_plugin'], 'main_plugin', 'get_kline_data', context,
                {'symbol': '000001'})
        mgr._asset_db_manager.store_standardized_data.assert_not_called()


class TestFundamentalPersist(unittest.TestCase):
    """T02: FUNDAMENTAL 取数后落库，且 data_source 非 'tet_plugin'"""

    def test_fundamental_result_persisted_with_real_data_source(self):
        """基本面 dict → 单行 DataFrame 落库，补 symbol 列，data_source 为真实插件 id"""
        mgr = _make_manager()
        plugin = MagicMock()
        # dict 不含 symbol，验证代码补齐 context.symbol
        fund_dict = {'name': '平安银行', 'industry': '银行', 'market_cap': 3000.0}
        val = _make_validation(is_valid=True, quality_score=0.9, plugin_id='fund_plugin')
        _build_failover_plugin_chain(mgr, plugin, fund_dict, val)

        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.FUNDAMENTAL, symbol='000001')
        result, validation = mgr._execute_with_failover(
            ['fund_plugin'], 'fund_plugin', 'get_fundamental_data', context, {})

        self.assertEqual(result, fund_dict)
        mgr._asset_db_manager.store_standardized_data.assert_called_once()
        args, _ = mgr._asset_db_manager.store_standardized_data.call_args
        persist_df = args[0]
        self.assertEqual(args[2], DataType.FUNDAMENTAL)
        self.assertEqual(persist_df['symbol'].iloc[0], '000001')
        self.assertEqual(persist_df['data_source'].iloc[0], 'fund_plugin')
        self.assertNotEqual(persist_df['data_source'].iloc[0], 'tet_plugin')


class TestTETPipelineNoDoubleWrite(unittest.TestCase):
    """T03: tet_data_pipeline.process 不再落库（双写收敛）"""

    def test_process_does_not_call_store_standardized_data(self):
        """process 正常返回数据，但不再调用 store_standardized_data"""
        from core.tet_data_pipeline import TETDataPipeline, StandardQuery

        pipeline = object.__new__(TETDataPipeline)
        pipeline.logger = logger
        pipeline._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "fallback_used": 0,
            "avg_processing_time": 0.0
        }
        pipeline._cache = {}
        pipeline._cache_ttl = timedelta(minutes=5)
        pipeline._generate_cache_key = MagicMock(return_value='test-cache-key')
        pipeline._get_from_cache = MagicMock(return_value=None)
        pipeline.transform_query = MagicMock(return_value=MagicMock())
        raw_df = _make_kdata_df(6)
        pipeline.extract_data_with_failover = MagicMock(return_value=(
            raw_df,
            {'provider': 'tongdaxin'},
            MagicMock(success=True, attempts=1, failed_sources=[], successful_source='tongdaxin',
                      error_messages=[], total_time_ms=10.0)
        ))
        pipeline.transform_data = MagicMock(return_value=raw_df)
        pipeline._build_metadata = MagicMock(return_value={})
        pipeline._set_to_cache = MagicMock()
        pipeline._update_stats = MagicMock()
        # 不预置 _asset_db_manager：验证 process 不再延迟创建落库属性

        query = StandardQuery(
            symbol='000001', asset_type=AssetType.STOCK_A,
            data_type=DataType.HISTORICAL_KLINE, period='D')
        result = pipeline.process(query)

        self.assertIsNotNone(result)
        self.assertFalse(result.data.empty)
        # 落库块删除后 _asset_db_manager 属性不应被延迟创建（双写已收敛）
        self.assertFalse(hasattr(pipeline, '_asset_db_manager'))


class TestKlineDBFirst(unittest.TestCase):
    """T04: K 线 DB 优先（避免直调插件走网络）"""

    def _build_context(self) -> RequestContext:
        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')
        context.start_date = '2024-01-01'
        context.end_date = '2024-12-31'
        context.period = 'D'
        return context

    def test_db_hit_skips_plugin(self):
        """DB 有数据且覆盖请求范围 → 直接返回，不调插件"""
        mgr = _make_manager()
        # 366 条记录覆盖 2024-01-01 ~ 2024-12-31 完整请求范围
        db_df = _make_db_kline_df(366, start='2024-01-01')
        mgr._asset_db_manager.load_kline_data = MagicMock(return_value=db_df)
        mgr.plugin_center.get_available_plugins = MagicMock(return_value=['plugin_a'])

        result = mgr._execute_data_request(
            self._build_context(), 'get_kline_data', symbol='000001')

        self.assertFalse(result.empty)
        # 返回格式兼容：timestamp 已映射为 datetime 列
        self.assertIn('datetime', result.columns)
        self.assertNotIn('timestamp', result.columns)
        mgr._asset_db_manager.load_kline_data.assert_called_once()
        # 未走插件发现链路
        mgr.plugin_center.get_available_plugins.assert_not_called()

    def test_db_miss_goes_to_plugin(self):
        """DB 无数据 → 走插件流程"""
        mgr = _make_manager()
        mgr._asset_db_manager.load_kline_data = MagicMock(return_value=pd.DataFrame())
        mgr.plugin_center.get_available_plugins = MagicMock(return_value=['plugin_a'])
        mgr._filter_connected_plugins = MagicMock(return_value=['plugin_a'])
        mgr.tet_engine.select_optimal_plugin = MagicMock(return_value='plugin_a')
        plugin = MagicMock()
        mgr.plugin_center.get_plugin = MagicMock(return_value=plugin)
        df = _make_kdata_df(10)
        val = _make_validation(is_valid=True, quality_score=0.9, plugin_id='plugin_a')
        mgr.risk_manager.execute_with_monitoring = MagicMock(return_value=(df, val))

        result = mgr._execute_data_request(
            self._build_context(), 'get_kline_data', symbol='000001')

        self.assertFalse(result.empty)
        self.assertEqual(len(result), 10)
        mgr.plugin_center.get_available_plugins.assert_called_once()
        mgr.risk_manager.execute_with_monitoring.assert_called_once()

    def test_db_coverage_insufficient_falls_back_to_plugin(self):
        """DB 有数据但未覆盖请求范围（防坑）→ 视为 miss，走插件"""
        mgr = _make_manager()
        # DB 数据仅覆盖 2024-01-01 ~ 2024-01-10，请求范围 2024-01-01 ~ 2024-12-31
        db_df = _make_db_kline_df(10, start='2024-01-01')
        mgr._asset_db_manager.load_kline_data = MagicMock(return_value=db_df)
        mgr.plugin_center.get_available_plugins = MagicMock(return_value=['plugin_a'])
        mgr._filter_connected_plugins = MagicMock(return_value=['plugin_a'])
        mgr.tet_engine.select_optimal_plugin = MagicMock(return_value='plugin_a')
        plugin = MagicMock()
        mgr.plugin_center.get_plugin = MagicMock(return_value=plugin)
        df = _make_kdata_df(10)
        val = _make_validation(is_valid=True, quality_score=0.9, plugin_id='plugin_a')
        mgr.risk_manager.execute_with_monitoring = MagicMock(return_value=(df, val))

        result = mgr._execute_data_request(
            self._build_context(), 'get_kline_data', symbol='000001')

        self.assertFalse(result.empty)
        # 覆盖不足 → 插件被调用
        mgr.risk_manager.execute_with_monitoring.assert_called_once()


class TestDegradedDownload(unittest.TestCase):
    """T05: 三组件缺失时 download_incremental_data 降级，不抛异常"""

    def _build_downloader(self):
        from core.services.enhanced_duckdb_data_downloader import EnhancedDuckDBDataDownloader

        dl = object.__new__(EnhancedDuckDBDataDownloader)
        dl.incremental_analyzer = None
        dl.completeness_checker = None
        dl.update_recorder = None
        dl.download_historical_kline_data = AsyncMock(
            return_value={'000001': _make_kdata_df(5)})
        dl.download_fundamental_data = AsyncMock(
            return_value={'000001': {'financial_statement': {'a': 1}}})
        return dl

    def test_missing_components_degraded_no_raise(self):
        """三组件缺失 → 返回同构 dict（task_id=None），不抛 RuntimeError"""
        dl = self._build_downloader()

        result = asyncio.run(
            dl.download_incremental_data(['000001'], datetime(2024, 12, 31)))

        self.assertIsNotNone(result)
        self.assertIsNone(result['task_id'])
        self.assertEqual(result['success_count'], 2)  # kline + fundamental
        self.assertEqual(result['total_records'], 5)
        dl.download_historical_kline_data.assert_awaited_once()
        dl.download_fundamental_data.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
