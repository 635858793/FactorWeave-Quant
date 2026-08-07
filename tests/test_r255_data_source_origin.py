#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R255 回归测试: 数据源溯源域 P1 缺陷修复

核心缺陷（主智能体交叉验证 100% 确认）:
- R254 的 data_source 溯源修复实际未生效:
  data_quality_risk_manager.execute_with_monitoring 返回动态创建的匿名类
  type('ValidationResult', (), {...})(), 该结构无 plugin_id 属性
  （仅 is_valid/quality_score/risk_level/assessment/error）。
  导致 uni_plugin_data_manager._persist_fetched_data 中
  getattr(validation_result, 'plugin_id', None) 恒为 None,
  data_source 恒回退硬编码 'tet_plugin';
  同缺陷波及 _execute_data_request:773, failover 后 actual_plugin_id 恒为主选插件 id,
  路由健康度记错插件。

测试点:
- T01 execute_with_monitoring 成功路径返回的 validation_result 带 plugin_id == 传入 plugin_id
- T02 execute_with_monitoring 失败路径（插件抛异常）返回的 validation_result 也带 plugin_id
- T03 _persist_fetched_data: validation_result 无 plugin_id（模拟旧匿名类）时,
      data_source 列 == context.actual_plugin_id 而非 'tet_plugin'
- T04 _persist_fetched_data: validation_result 有 plugin_id 时用真实值,
      落库 DataFrame 的 'data_source' 列不再出现字面量 'tet_plugin'
- T05 failover 场景（真实 execute_with_monitoring + 真实匿名类构造）:
      context.actual_plugin_id 反映 backup 插件 id, 落库 data_source == backup id
"""
import unittest
from unittest.mock import MagicMock

import pandas as pd

from core.data_quality_risk_manager import DataQualityRiskManager
from core.plugin_types import AssetType, DataType
from core.risk.data_quality_monitor import QualityLevel, QualityReport
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


def _make_legacy_validation(is_valid: bool = True, quality_score: float = 0.9):
    """构造旧版匿名 ValidationResult（无 plugin_id 属性，模拟修复前的生产对象）"""
    return type('ValidationResult', (), {
        'is_valid': is_valid,
        'quality_score': quality_score,
        'risk_level': 'low',
    })()


def _make_real_risk_manager(quality_score: float = 0.95) -> DataQualityRiskManager:
    """构造真实 DataQualityRiskManager，mock 质量评估返回优质报告"""
    manager = DataQualityRiskManager()
    manager.quality_monitor = MagicMock()
    manager.quality_monitor.evaluate_data_quality.return_value = QualityReport(
        overall_score=quality_score,
        quality_level=QualityLevel.GOOD,
        metrics={},
        issues=[],
        recommendations=[],
        data_info={},
    )
    return manager


class TestExecuteWithMonitoringPluginId(unittest.TestCase):
    """T01/T02: execute_with_monitoring 返回的 validation_result 必须携带 plugin_id"""

    def test_success_result_carries_plugin_id(self):
        """成功路径: validation_result.plugin_id == 传入 plugin_id"""
        manager = _make_real_risk_manager()

        def fake_method(**kwargs):
            return _make_kdata_df(5)

        result, validation = manager.execute_with_monitoring(
            'plugin_x', fake_method, symbol='000001')

        self.assertFalse(result.empty)
        self.assertTrue(validation.is_valid)
        self.assertEqual(validation.plugin_id, 'plugin_x')

    def test_failure_result_carries_plugin_id(self):
        """失败路径（插件抛异常）: validation_result 也带 plugin_id"""
        manager = _make_real_risk_manager()

        def boom(**kwargs):
            raise RuntimeError('插件执行失败')

        result, validation = manager.execute_with_monitoring('plugin_y', boom)

        self.assertIsNone(result)
        self.assertFalse(validation.is_valid)
        self.assertEqual(validation.plugin_id, 'plugin_y')


class TestPersistFetchedDataSource(unittest.TestCase):
    """T03/T04: _persist_fetched_data 的 data_source 溯源"""

    def test_no_plugin_id_uses_context_actual_plugin_id(self):
        """validation_result 无 plugin_id（旧匿名类）→ data_source == context.actual_plugin_id"""
        mgr = _make_manager()
        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')
        context.actual_plugin_id = 'backup_plugin'
        df = _make_kdata_df(5)
        legacy_validation = _make_legacy_validation(is_valid=True)

        mgr._persist_fetched_data(context, {'symbol': '000001'}, df, legacy_validation)

        mgr._asset_db_manager.store_standardized_data.assert_called_once()
        persist_df = mgr._asset_db_manager.store_standardized_data.call_args[0][0]
        self.assertEqual(persist_df['data_source'].iloc[0], 'backup_plugin')
        self.assertNotEqual(persist_df['data_source'].iloc[0], 'tet_plugin')

    def test_plugin_id_used_when_context_not_set(self):
        """生产主路径: context.actual_plugin_id 未赋值（failover 内部调用时 :798 尚未执行）
        → validation_result.plugin_id 真实值生效"""
        mgr = _make_manager()
        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')
        # 不设置 context.actual_plugin_id: 模拟 _execute_with_failover 内部调用
        # _persist_fetched_data 时（:798 赋值发生在 failover 返回之后）context 尚无该属性
        df = _make_kdata_df(5)
        real_validation = type('ValidationResult', (), {
            'is_valid': True,
            'quality_score': 0.9,
            'plugin_id': 'real_plugin',
        })()

        mgr._persist_fetched_data(context, {'symbol': '000001'}, df, real_validation)

        mgr._asset_db_manager.store_standardized_data.assert_called_once()
        persist_df = mgr._asset_db_manager.store_standardized_data.call_args[0][0]
        self.assertEqual(persist_df['data_source'].iloc[0], 'real_plugin')

    def test_persisted_df_never_contains_tet_plugin_literal(self):
        """落库 DataFrame 的 'data_source' 列不再出现字面量 'tet_plugin'"""
        mgr = _make_manager()
        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')
        context.actual_plugin_id = 'backup_plugin'
        df = _make_kdata_df(8)
        legacy_validation = _make_legacy_validation(is_valid=True)

        mgr._persist_fetched_data(context, {'symbol': '000001'}, df, legacy_validation)

        persist_df = mgr._asset_db_manager.store_standardized_data.call_args[0][0]
        self.assertNotIn('tet_plugin', set(persist_df['data_source'].tolist()))


class TestFailoverActualPluginId(unittest.TestCase):
    """T05: failover 场景下 context.actual_plugin_id 反映真实（backup）插件 id

    走真实 DataQualityRiskManager（匿名类由生产代码构造）:
    主插件抛异常 → failover 到 backup 成功 → :773 从 validation_result.plugin_id
    取到 backup_plugin → :798 context.actual_plugin_id == 'backup_plugin'
    """

    def _build_manager(self, df: pd.DataFrame):
        mgr = _make_manager()
        mgr.risk_manager = _make_real_risk_manager()
        mgr._asset_db_manager.load_kline_data = MagicMock(return_value=pd.DataFrame())
        mgr.plugin_center.get_available_plugins = MagicMock(
            return_value=['main_plugin', 'backup_plugin'])
        mgr._filter_connected_plugins = MagicMock(
            return_value=['main_plugin', 'backup_plugin'])
        mgr.tet_engine.select_optimal_plugin = MagicMock(return_value='main_plugin')
        mgr._check_plugin_connection = MagicMock(return_value=True)

        plugin_main = MagicMock()
        plugin_main.get_kline_data.side_effect = RuntimeError('主插件执行失败')
        plugin_backup = MagicMock()
        plugin_backup.get_kline_data.return_value = df
        mgr.plugin_center.get_plugin = MagicMock(
            side_effect=lambda pid: plugin_main if pid == 'main_plugin' else plugin_backup)
        return mgr

    def test_failover_context_actual_plugin_id_reflects_backup(self):
        """主插件失败、backup 成功 → context.actual_plugin_id == 'backup_plugin'"""
        mgr = self._build_manager(_make_kdata_df(6))
        context = RequestContext(
            asset_type=AssetType.STOCK_A, data_type=DataType.HISTORICAL_KLINE, symbol='000001')
        context.start_date = '2024-01-01'
        context.end_date = '2024-01-10'

        result = mgr._execute_data_request(
            context, 'get_kline_data', symbol='000001')

        self.assertFalse(result.empty)
        self.assertEqual(context.actual_plugin_id, 'backup_plugin')
        # 落库 data_source 溯源到真实 backup 插件
        mgr._asset_db_manager.store_standardized_data.assert_called_once()
        persist_df = mgr._asset_db_manager.store_standardized_data.call_args[0][0]
        self.assertEqual(persist_df['data_source'].iloc[0], 'backup_plugin')
        # 路由健康度更新应记在真实插件上，而非主选插件
        mgr.tet_engine.update_plugin_health.assert_called_once()
        health_plugin_id = mgr.tet_engine.update_plugin_health.call_args[0][0]
        self.assertEqual(health_plugin_id, 'backup_plugin')


if __name__ == '__main__':
    unittest.main()
