#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R285 专项测试：数据质量闭环修复（落库质量准入 + 取数质量优选 + 评分失真治理）

背景（三审计交叉验证 100% 确认）：
1. 落库质量检测"只记录不拦截"：_evaluate_and_record_quality 返回值被丢弃，
   低质量数据 100% 落库（asset_database_manager.py L1487-1496）
2. 质量优选 JOIN 断链：DATE(hkd.timestamp) = dqm.check_date，check_date=落库当天
   而 timestamp=交易日 → 历史 K 线质量分恒 NULL → 回退硬编码优先级
3. TET failover 非空即成功（tet_data_pipeline.py L626），无质量门槛
4. DB 直读无读前质量校验（R264 只处理"空"不处理"低质量"）
5. 'best_quality' 伪源回写污染 DB（unified_data_manager.py L1802-1807）
6. 评分失真：consistency 检查列名 'datetime' vs 落库 timestamp（恒 1.0）；
   timeliness 对历史回填按时间差剧烈降分（合法场景被惩罚）

修复：
1. JOIN 改为关联"每 symbol+source+freq 最近一次评估记录"（与交易日解耦）
2. store_standardized_data 捕获质量分 + data.reject_low_quality_kline 开关（默认 False 兼容）
3. extract_data_with_failover 增加 _is_kline_quality_acceptable 轻量质量门槛
4. get_kdata / get_asset_data DB 直读前查 monitor 最近评分，低分触发回源重拉
5. data_source 不再强制覆盖为 'best_quality'（透传真实源）
6. consistency 兼容 timestamp 列；backfill=True 时 timeliness 给中性分

全部离线测试：DuckDB / TET 管道 / 质量管理器均 mock，不产生网络/DB IO。
"""

import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.services.unified_data_manager import UnifiedDataManager
from core.tet_data_pipeline import TETDataPipeline, StandardQuery
from core.plugin_types import AssetType, DataType
from core.risk.data_quality_monitor import DataQualityMonitor


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
    udm.duckdb_operations = MagicMock()
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


# ---------------------------------------------------------------------------
# 修复1：质量优选 JOIN 断链
# ---------------------------------------------------------------------------
class TestMonitorJoinFix(unittest.TestCase):
    """JOIN 断链修复：质量分按"最近一次评估"关联，历史 K 线不再恒 NULL"""

    def test_view_sql_uses_latest_assessment(self):
        """unified_best_quality_kline 视图 SQL：不再按交易日直接 JOIN check_date"""
        from core.asset_database_manager import AssetSeparatedDatabaseManager
        mgr = AssetSeparatedDatabaseManager.__new__(AssetSeparatedDatabaseManager)
        schema = mgr._initialize_table_schemas()
        view_sql = schema['unified_best_quality_kline']
        # 旧断链条件（真实 JOIN 条件）已移除（注释文本中保留说明性引用）
        self.assertNotIn('AND DATE(hkd.timestamp)', view_sql)
        # R287 P0-2：质量分按"最近一次评估"关联，且已物化为 monitor_latest 表
        # （替代原视图内全表 GROUP BY 子查询，避免每次查询全表聚合）
        self.assertIn('LEFT JOIN monitor_latest dqm ON', view_sql)
        self.assertNotIn('GROUP BY symbol, data_source, frequency', view_sql)

    def test_udm_cte_uses_latest_assessment(self):
        """UDM _get_kdata_from_duckdb 的 CTE：同样按最近一次评估关联"""
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 10)
        db_df['data_source'] = 'tushare'
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = db_df
        captured = {}

        def fake_execute_query(**kwargs):
            captured['query'] = kwargs.get('query', '')
            captured['params'] = kwargs.get('params', [])
            return mock_result

        udm.duckdb_operations.execute_query = fake_execute_query
        udm.asset_manager.get_database_path = MagicMock(return_value=':memory:')
        udm._standardize_kdata_format = MagicMock(side_effect=lambda df, code: df)
        udm._set_quality_score_to_cache = MagicMock()

        udm._get_kdata_from_duckdb('600000', 'D', 10, asset_type=AssetType.STOCK_A)

        self.assertIn('query', captured)
        # 真实 JOIN 条件不再是按交易日匹配
        self.assertNotIn('AND DATE(hkd.timestamp)', captured['query'])
        # R287 P0-2：查询 JOIN 物化表 monitor_latest，不再内嵌全表 GROUP BY 子查询
        self.assertIn('LEFT JOIN monitor_latest dqm ON', captured['query'])
        self.assertNotIn('FROM data_quality_monitor dqm2', captured['query'])


# ---------------------------------------------------------------------------
# 修复5：'best_quality' 伪源治理
# ---------------------------------------------------------------------------
class TestBestQualitySourcePollution(unittest.TestCase):
    """data_source 不再被强制覆盖为 'best_quality' 伪源"""

    def test_db_read_keeps_real_data_source(self):
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 10)
        db_df['data_source'] = 'tushare'  # 真实源
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = db_df
        udm.duckdb_operations.execute_query = MagicMock(return_value=mock_result)
        udm.asset_manager.get_database_path = MagicMock(return_value=':memory:')
        udm._standardize_kdata_format = MagicMock(side_effect=lambda df, code: df)
        udm._set_quality_score_to_cache = MagicMock()

        out = udm._get_kdata_from_duckdb('600000', 'D', 10, asset_type=AssetType.STOCK_A)
        self.assertFalse(out.empty)
        self.assertIn('data_source', out.columns)
        # 真实源被保留，不再覆盖为伪源
        self.assertEqual(out['data_source'].iloc[0], 'tushare')
        self.assertNotIn('best_quality', set(out['data_source']))

    def test_db_read_without_data_source_col(self):
        """视图结果缺 data_source 列时仍安全补缺省（不抛异常）"""
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 10)  # 无 data_source 列
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.data = db_df
        udm.duckdb_operations.execute_query = MagicMock(return_value=mock_result)
        udm.asset_manager.get_database_path = MagicMock(return_value=':memory:')
        udm._standardize_kdata_format = MagicMock(side_effect=lambda df, code: df)
        udm._set_quality_score_to_cache = MagicMock()

        out = udm._get_kdata_from_duckdb('600000', 'D', 10, asset_type=AssetType.STOCK_A)
        self.assertFalse(out.empty)


# ---------------------------------------------------------------------------
# 修复6：评分失真（consistency 列名 + timeliness 历史回填豁免）
# ---------------------------------------------------------------------------
class TestConsistencyColumnCompat(unittest.TestCase):
    """consistency 对 timestamp 列生效（原仅检查 'datetime' 恒跳过）"""

    def test_timestamp_irregular_interval_penalized(self):
        monitor = DataQualityMonitor()
        # 用落库列名 timestamp 构造间隔不一致数据（间隔 1 天 / 10 天交替）
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(['2026-01-01', '2026-01-02', '2026-01-12', '2026-01-13']),
            'open': [10.0] * 4, 'high': [11.0] * 4, 'low': [9.0] * 4, 'close': [10.5] * 4,
        })
        score = monitor._assess_consistency(df, 'kline')
        self.assertLess(score, 1.0)  # 间隔不一致应被降分（原来恒 1.0）

    def test_regular_timestamp_not_penalized(self):
        monitor = DataQualityMonitor()
        df = pd.DataFrame({
            'timestamp': pd.date_range('2026-01-01', periods=10, freq='D'),
            'open': [10.0] * 10, 'high': [11.0] * 10, 'low': [9.0] * 10, 'close': [10.5] * 10,
        })
        score = monitor._assess_consistency(df, 'kline')
        self.assertEqual(score, 1.0)


class TestTimelinessBackfillExemption(unittest.TestCase):
    """backfill=True 时 timeliness 给中性分，历史回填不再被惩罚"""

    def test_backfill_returns_neutral(self):
        monitor = DataQualityMonitor()
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(['2020-01-01']),  # 多年前的历史
            'open': [10.0], 'high': [11.0], 'low': [9.0], 'close': [10.5],
        })
        score = monitor._assess_timeliness(df, {'backfill': True})
        self.assertEqual(score, 0.8)

    def test_non_backfill_still_penalized(self):
        monitor = DataQualityMonitor()
        df = pd.DataFrame({
            'timestamp': pd.to_datetime(['2020-01-01']),  # 多年前的历史
            'open': [10.0], 'high': [11.0], 'low': [9.0], 'close': [10.5],
        })
        score = monitor._assess_timeliness(df, {})
        self.assertLess(score, 0.5)  # 非回填场景保留原降分逻辑


# ---------------------------------------------------------------------------
# 修复2：落库质量准入
# ---------------------------------------------------------------------------
class TestStorageQualityGate(unittest.TestCase):
    """store_standardized_data 捕获质量分 + 低质量拒绝开关"""

    def _make_mgr(self, quality_score: float):
        from core.asset_database_manager import AssetSeparatedDatabaseManager
        mgr = AssetSeparatedDatabaseManager.__new__(AssetSeparatedDatabaseManager)
        mgr._write_lock = threading.Lock()
        mock_qm = MagicMock()
        mock_qm.assess_quality = MagicMock(return_value={
            'quality_score': quality_score,
            'completeness': quality_score,
            'issues': 1 if quality_score < 60 else 0,
        })
        mgr._get_quality_manager = MagicMock(return_value=mock_qm)
        mgr._ensure_database_exists = MagicMock(return_value=':memory:')
        mgr._generate_table_name = MagicMock(return_value='historical_kline_data')
        mgr._ensure_table_exists = MagicMock()
        mgr._upsert_data = MagicMock(return_value=5)
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=MagicMock())
        conn_ctx.__exit__ = MagicMock(return_value=False)
        mgr.duckdb_manager = MagicMock()
        mgr.duckdb_manager.get_connection = MagicMock(return_value=conn_ctx)
        return mgr

    def _kline_df(self) -> pd.DataFrame:
        df = _ohlcv('2026-01-01', 30)
        df['symbol'] = '600000'
        df['frequency'] = '1d'
        df['data_source'] = 'mock_src'
        return df

    @patch('core.asset_database_manager.AssetSeparatedDatabaseManager._reject_low_quality_kline_enabled',
           return_value=True)
    def test_low_quality_rejected_when_switch_on(self, mock_switch):
        mgr = self._make_mgr(quality_score=30.0)
        result = mgr.store_standardized_data(
            self._kline_df(), AssetType.STOCK_A, DataType.HISTORICAL_KLINE)
        self.assertFalse(result)  # 拒绝落库
        mgr._upsert_data.assert_not_called()  # 未执行写入

    @patch('core.asset_database_manager.AssetSeparatedDatabaseManager._reject_low_quality_kline_enabled',
           return_value=False)
    def test_low_quality_not_rejected_by_default(self, mock_switch):
        """默认开关关闭：只记录不拦截（兼容历史行为）"""
        mgr = self._make_mgr(quality_score=30.0)
        result = mgr.store_standardized_data(
            self._kline_df(), AssetType.STOCK_A, DataType.HISTORICAL_KLINE)
        self.assertTrue(result)  # 照常落库
        mgr._upsert_data.assert_called_once()  # 写入被调用

    @patch('core.asset_database_manager.AssetSeparatedDatabaseManager._reject_low_quality_kline_enabled',
           return_value=True)
    def test_high_quality_passes_even_switch_on(self, mock_switch):
        mgr = self._make_mgr(quality_score=90.0)
        result = mgr.store_standardized_data(
            self._kline_df(), AssetType.STOCK_A, DataType.HISTORICAL_KLINE)
        self.assertTrue(result)  # 高质量放行
        mgr._upsert_data.assert_called_once()


# ---------------------------------------------------------------------------
# 修复3：TET failover 质量门槛
# ---------------------------------------------------------------------------
class TestFailoverQualityThreshold(unittest.TestCase):
    """extract_data_with_failover：低质量 K 线视为该源失败，继续故障转移"""

    def _make_pipeline(self, adapters: dict, source_order: list):
        pl = TETDataPipeline.__new__(TETDataPipeline)
        pl._adapters = adapters
        pl._plugins = {}
        pl.router = MagicMock()
        pl.router.get_available_sources = MagicMock(return_value=source_order)
        pl.router.has_data_source = MagicMock(return_value=False)
        pl.router.record_request_result = MagicMock()
        pl._source_cooldowns = {}
        pl._per_source_timeout = 10.0
        pl._stats = {'total_requests': 0, 'cache_hits': 0,
                     'fallback_used': 0, 'avg_processing_time': 0.0}
        pl.logger = __import__('loguru').logger
        return pl

    def _bad_df(self) -> pd.DataFrame:
        """OHLC 逻辑错误：high < low"""
        df = _ohlcv('2026-01-01', 10)
        df.loc[df.index[0], 'high'] = 5.0  # high < low(9.0)
        return df

    def test_low_quality_continues_failover(self):
        bad_adapter = MagicMock()
        bad_adapter.plugin_id = 'bad_src'
        bad_adapter.get_kdata = MagicMock(return_value=self._bad_df())
        good_adapter = MagicMock()
        good_adapter.plugin_id = 'good_src'
        good_adapter.get_kdata = MagicMock(return_value=_ohlcv('2026-01-01', 10))
        good_adapter.get_plugin_info = MagicMock(return_value={'name': 'good_src'})

        pl = self._make_pipeline({'bad_src': bad_adapter, 'good_src': good_adapter},
                                 ['bad_src', 'good_src'])
        query = StandardQuery(symbol='600000', asset_type=AssetType.STOCK_A,
                              data_type=DataType.HISTORICAL_KLINE, period='D')
        routing_request = MagicMock()

        data, provider_info, result = pl.extract_data_with_failover(routing_request, query)

        self.assertTrue(result.success)
        self.assertEqual(result.successful_source, 'good_src')  # 转移到好源
        self.assertIn('bad_src', result.failed_sources)  # 坏源被拒
        self.assertEqual(provider_info.get('provider'), 'good_src')
        self.assertFalse(data.empty)

    def test_quality_acceptable_first_source_wins(self):
        good_adapter = MagicMock()
        good_adapter.plugin_id = 'good_src'
        good_adapter.get_kdata = MagicMock(return_value=_ohlcv('2026-01-01', 10))
        good_adapter.get_plugin_info = MagicMock(return_value={'name': 'good_src'})

        pl = self._make_pipeline({'good_src': good_adapter}, ['good_src'])
        query = StandardQuery(symbol='600000', asset_type=AssetType.STOCK_A,
                              data_type=DataType.HISTORICAL_KLINE, period='D')
        routing_request = MagicMock()

        data, provider_info, result = pl.extract_data_with_failover(routing_request, query)

        self.assertTrue(result.success)
        self.assertEqual(result.successful_source, 'good_src')
        self.assertFalse(result.failed_sources)

    def test_non_kline_not_gated(self):
        """非 K 线数据类型不受质量门槛影响（保持非空即成功）"""
        adapter = MagicMock()
        adapter.plugin_id = 'src'
        adapter.get_real_time_quotes = MagicMock(return_value=_ohlcv('2026-01-01', 10))
        adapter.get_plugin_info = MagicMock(return_value={'name': 'src'})
        pl = self._make_pipeline({'src': adapter}, ['src'])
        query = StandardQuery(symbol='600000', asset_type=AssetType.STOCK_A,
                              data_type=DataType.REAL_TIME_QUOTE, period='D')
        routing_request = MagicMock()

        data, provider_info, result = pl.extract_data_with_failover(routing_request, query)
        self.assertTrue(result.success)  # 非 K 线不看质量


# ---------------------------------------------------------------------------
# 修复4：DB 直读低质量回源重拉
# ---------------------------------------------------------------------------
class TestDbReadLowQualityRefetch(unittest.TestCase):
    """get_kdata：DB 命中但质量分低 → 回源重拉；质量正常 → 不重拉"""

    def test_low_quality_triggers_refetch(self):
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 30)
        udm._get_cached_data = MagicMock(return_value=None)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._get_db_quality_score = MagicMock(return_value=30.0)  # 低质量
        new_df = _ohlcv('2026-01-01', 60)
        udm._fetch_kdata_from_tet = MagicMock(return_value=(new_df, 'tet_plugin'))
        udm._persist_kdata_to_duckdb = MagicMock()
        udm._cache_data = MagicMock()

        out = udm.get_kdata('600000', 'D', 30, AssetType.STOCK_A)

        self.assertEqual(len(out), 60)  # 返回重拉的新数据
        udm._fetch_kdata_from_tet.assert_called_once()  # 触发回源
        udm._persist_kdata_to_duckdb.assert_called_once()  # 重拉后落库

    def test_high_quality_skips_refetch(self):
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 30)
        udm._get_cached_data = MagicMock(return_value=None)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._get_db_quality_score = MagicMock(return_value=90.0)  # 高质量
        udm._incremental_fill_kdata = MagicMock(return_value=None)  # 无新增
        udm._fetch_kdata_from_tet = MagicMock(return_value=(None, None))
        udm._cache_data = MagicMock()

        out = udm.get_kdata('600000', 'D', 30, AssetType.STOCK_A)

        self.assertEqual(len(out), 30)  # 直接用 DB 数据
        udm._fetch_kdata_from_tet.assert_not_called()  # 不重拉

    def test_no_monitor_record_keeps_db(self):
        """无 monitor 记录（返回 None）→ 不触发回源，保持现状"""
        udm = _make_udm()
        db_df = _ohlcv('2026-01-01', 30)
        udm._get_cached_data = MagicMock(return_value=None)
        udm._get_kdata_from_duckdb = MagicMock(return_value=db_df)
        udm._get_db_quality_score = MagicMock(return_value=None)
        udm._incremental_fill_kdata = MagicMock(return_value=None)
        udm._fetch_kdata_from_tet = MagicMock(return_value=(None, None))
        udm._cache_data = MagicMock()

        out = udm.get_kdata('600000', 'D', 30, AssetType.STOCK_A)
        self.assertEqual(len(out), 30)
        udm._fetch_kdata_from_tet.assert_not_called()


if __name__ == '__main__':
    unittest.main()
