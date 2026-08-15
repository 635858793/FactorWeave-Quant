#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R286 专项测试：数据源路由质量加权 + 告警链路接通 + 死代码清理 + 配置声明

背景（R285 审计遗留 4 项，全项修复）：
1. get_source_risk_profile（L607）0 生产调用——质量分未接入路由决策
2. 告警链路断：_trigger_quality_alert 仅日志 + AlertRuleEngine 未接
3. IntelligentFailoverEngine 死代码（全项目 0 引用，DataSourceRouter 策略体系已覆盖其价值）
4. data.reject_low_quality_kline 未在配置模板/DataConfig 声明

修复：
1a. EnhancedDataQualityMonitor.monitor_data_quality 将评估结果写入 risk_manager
    （此前 risk_history 仅插件模板写入，生产 K 线链路无数据 → 画像恒空）
1b. DataSourceRouter.get_prioritized_sources 按"健康度+质量画像"排序候选源，
    TET extract_data_with_failover 改用之（替代纯熔断过滤顺序尝试）
2. _register_quality_alerts 预注册规则 + _feed_alert_engine 接通 AlertRuleEngine，
    _trigger_quality_alert/_process_alerts 均接入
3. 删除 core/intelligent_failover_engine.py 及两处残留引用
4. DataConfig 增加 reject_low_quality_kline 字段（默认 False）+ config.json 声明

全部离线测试：路由/管道/告警引擎均 mock 或轻量实例，不产生网络/DB IO。
"""

import importlib.util
import os
import sys
import unittest
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.data_quality_risk_manager import DataQualityRiskManager
from core.data_source_router import DataSourceRouter, RoutingRequest
from core.plugin_types import AssetType, DataType
from core.services.alert_rule_engine import AlertRuleEngine
from core.services.enhanced_data_quality_monitor import (
    EnhancedDataQualityMonitor, QualityMetrics,
)
from core.tet_data_pipeline import TETDataPipeline, StandardQuery
from utils.config_types import DataConfig


class _FakePluginInfo:
    supported_asset_types = [AssetType.STOCK_A]
    supported_data_types = [DataType.HISTORICAL_KLINE]


class _FakeAdapter:
    """满足 register_data_source 的最小适配器（_get_available_sources 仅需 plugin_info）"""

    def get_plugin_info(self):
        return _FakePluginInfo()


class _FakeRouter:
    """模拟 TET 主链路 router（不触发任何真实 IO）"""

    def __init__(self, with_prioritized: bool = True):
        self.with_prioritized = with_prioritized
        self.prioritized_called = False
        self.available_called = False
        if not with_prioritized:
            # 模拟旧版 router：无 get_prioritized_sources（生产代码 callable 检查回退）
            self.get_prioritized_sources = None

    def get_prioritized_sources(self, routing_request):
        self.prioritized_called = True
        return ['src_a']

    def get_available_sources(self, routing_request):
        self.available_called = True
        return ['src_a']

    def has_data_source(self, source_id):
        return False


def _make_router() -> DataSourceRouter:
    router = DataSourceRouter()
    router.register_data_source('src_a', _FakeAdapter(), priority=0, weight=1.0)
    router.register_data_source('src_b', _FakeAdapter(), priority=1, weight=1.0)
    return router


def _ohlcv_recent(days: int = 30) -> pd.DataFrame:
    """构造以今天为终点的升序 OHLCV K线"""
    dts = pd.date_range(end=datetime.now(), periods=days, freq='D')
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
# 修复4：配置声明
# ---------------------------------------------------------------------------
class TestDataConfigDeclaration(unittest.TestCase):
    """data.reject_low_quality_kline 在 DataConfig 中声明（默认 False 兼容）"""

    def test_default_false(self):
        cfg = DataConfig()
        self.assertFalse(cfg.reject_low_quality_kline)

    def test_to_dict_contains_key(self):
        cfg = DataConfig()
        d = cfg.to_dict()
        self.assertIn('reject_low_quality_kline', d)
        self.assertFalse(d['reject_low_quality_kline'])

    def test_from_dict_parses_true(self):
        cfg = DataConfig.from_dict({'reject_low_quality_kline': True})
        self.assertTrue(cfg.reject_low_quality_kline)

    def test_from_dict_absent_defaults_false(self):
        cfg = DataConfig.from_dict({})
        self.assertFalse(cfg.reject_low_quality_kline)


# ---------------------------------------------------------------------------
# 修复1b：failover 质量加权排序
# ---------------------------------------------------------------------------
class TestPrioritizedSources(unittest.TestCase):
    """get_prioritized_sources：健康度+质量画像加权排序，熔断过滤保留"""

    def _seed_quality(self, router: DataSourceRouter):
        """在 router 质量画像管理器里按数据源写入近 7 天质量分"""
        rm = DataQualityRiskManager()
        now = datetime.now()
        rm.risk_history['src_a'].append(
            {'risk_level': 'low', 'risk_score': 0.1, 'quality_score': 90.0, 'timestamp': now})
        rm.risk_history['src_b'].append(
            {'risk_level': 'high', 'risk_score': 0.9, 'quality_score': 40.0, 'timestamp': now})
        router._quality_manager = rm

    def test_quality_ranking_puts_better_source_first(self):
        router = _make_router()
        self._seed_quality(router)
        req = RoutingRequest(asset_type=AssetType.STOCK_A,
                             data_type=DataType.HISTORICAL_KLINE, symbol='x')
        result = router.get_prioritized_sources(req)
        # src_a 质量分 90 高于 src_b 40 → src_a 优先
        self.assertEqual(result[0], 'src_a')
        self.assertEqual(set(result), {'src_a', 'src_b'})

    def test_no_quality_profile_neutral_not_penalized(self):
        router = _make_router()
        req = RoutingRequest(asset_type=AssetType.STOCK_A,
                             data_type=DataType.HISTORICAL_KLINE, symbol='x')
        result = router.get_prioritized_sources(req)
        # 无画像 → 中性 0.5，两个健康源都保留
        self.assertEqual(set(result), {'src_a', 'src_b'})

    def test_circuit_broken_source_filtered_out(self):
        router = _make_router()
        self._seed_quality(router)
        router.circuit_breakers['src_b'].force_open()
        req = RoutingRequest(asset_type=AssetType.STOCK_A,
                             data_type=DataType.HISTORICAL_KLINE, symbol='x')
        result = router.get_prioritized_sources(req)
        # 熔断的 src_b 即使质量分低也直接过滤，不参与排序
        self.assertEqual(result, ['src_a'])

    def test_all_broken_returns_empty(self):
        router = _make_router()
        router.circuit_breakers['src_a'].force_open()
        router.circuit_breakers['src_b'].force_open()
        req = RoutingRequest(asset_type=AssetType.STOCK_A,
                             data_type=DataType.HISTORICAL_KLINE, symbol='x')
        self.assertEqual(router.get_prioritized_sources(req), [])


class TestTETUsesPrioritizedSources(unittest.TestCase):
    """TET failover 主链路改用质量加权排序（含旧 router 兼容回退）"""

    def test_extract_uses_prioritized_sources(self):
        fake = _FakeRouter(with_prioritized=True)
        pipeline = TETDataPipeline(fake)
        req = RoutingRequest(asset_type=AssetType.STOCK_A,
                             data_type=DataType.HISTORICAL_KLINE, symbol='x')
        query = StandardQuery(symbol='x', asset_type=AssetType.STOCK_A,
                              data_type=DataType.HISTORICAL_KLINE)
        _, _, failover = pipeline.extract_data_with_failover(req, query)
        self.assertTrue(fake.prioritized_called)
        self.assertFalse(fake.available_called)
        self.assertFalse(failover.success)  # 无适配器 → 失败，但路径已走质量排序

    def test_fallback_to_available_sources(self):
        fake = _FakeRouter(with_prioritized=False)
        pipeline = TETDataPipeline(fake)
        req = RoutingRequest(asset_type=AssetType.STOCK_A,
                             data_type=DataType.HISTORICAL_KLINE, symbol='x')
        query = StandardQuery(symbol='x', asset_type=AssetType.STOCK_A,
                              data_type=DataType.HISTORICAL_KLINE)
        pipeline.extract_data_with_failover(req, query)
        # 无 get_prioritized_sources 的旧 router → 回退 get_available_sources
        self.assertTrue(fake.available_called)


# ---------------------------------------------------------------------------
# 修复1a：monitor_data_quality 写每源质量画像
# ---------------------------------------------------------------------------
class TestMonitorWritesRiskHistory(unittest.TestCase):
    """TET 主链路质量监控结果灌入 risk_manager → get_source_risk_profile 有数据"""

    def test_monitor_populates_risk_profile(self):
        rm = DataQualityRiskManager()
        monitor = EnhancedDataQualityMonitor(risk_manager=rm, alert_engine=None)
        monitor.monitor_data_quality('src_a', 'kline', _ohlcv_recent(), 'TEST')
        profile = rm.get_source_risk_profile('src_a', days=7)
        self.assertIn('average_quality_score', profile)
        self.assertGreaterEqual(profile['average_quality_score'], 0)
        self.assertGreaterEqual(profile['total_assessments'], 1)

    def test_monitor_writes_under_distinct_sources(self):
        rm = DataQualityRiskManager()
        monitor = EnhancedDataQualityMonitor(risk_manager=rm, alert_engine=None)
        monitor.monitor_data_quality('src_a', 'kline', _ohlcv_recent(), 'A')
        monitor.monitor_data_quality('src_b', 'kline', _ohlcv_recent(), 'B')
        profile_a = rm.get_source_risk_profile('src_a')
        profile_b = rm.get_source_risk_profile('src_b')
        self.assertIn('average_quality_score', profile_a)
        self.assertIn('average_quality_score', profile_b)


# ---------------------------------------------------------------------------
# 修复2：告警链路接通
# ---------------------------------------------------------------------------
class TestAlertEngineConnected(unittest.TestCase):
    """_trigger_quality_alert/_process_alerts 接通 AlertRuleEngine"""

    def test_quality_alert_rule_pre_registered(self):
        alert_engine = AlertRuleEngine()
        rm = DataQualityRiskManager()
        monitor = EnhancedDataQualityMonitor(risk_manager=rm, alert_engine=alert_engine)
        self.assertIsNotNone(alert_engine.get_rule('data_quality_low_score'))
        self.assertEqual(len(alert_engine.list_rules()), 1)

    def test_low_quality_feed_triggers_alert(self):
        alert_engine = AlertRuleEngine()
        rm = DataQualityRiskManager()
        monitor = EnhancedDataQualityMonitor(risk_manager=rm, alert_engine=alert_engine)
        metrics = QualityMetrics(
            data_source='src_a', data_type='kline', symbol='T',
            overall_score=0.5, completeness_score=0.5,
        )
        monitor._feed_alert_engine(metrics)
        # 规则条件 quality_overall_score < 0.8 满足 → 至少一次告警触发
        self.assertGreaterEqual(alert_engine._stats['triggered_alerts'], 1)

    def test_high_quality_feed_not_trigger(self):
        alert_engine = AlertRuleEngine()
        rm = DataQualityRiskManager()
        monitor = EnhancedDataQualityMonitor(risk_manager=rm, alert_engine=alert_engine)
        metrics = QualityMetrics(
            data_source='src_a', data_type='kline', symbol='T',
            overall_score=0.95, completeness_score=0.95,
        )
        monitor._feed_alert_engine(metrics)
        # 高质量不触发阈值规则
        self.assertEqual(alert_engine._stats['triggered_alerts'], 0)

    def test_trigger_quality_alert_bridges_engine(self):
        alert_engine = AlertRuleEngine()
        rm = DataQualityRiskManager()
        monitor = EnhancedDataQualityMonitor(risk_manager=rm, alert_engine=alert_engine)
        metrics = QualityMetrics(
            data_source='src_a', data_type='kline', symbol='T',
            overall_score=0.4, completeness_score=0.4,
        )
        monitor._trigger_quality_alert(metrics)
        self.assertGreaterEqual(alert_engine._stats['triggered_alerts'], 1)

    def test_process_alerts_feeds_latest(self):
        alert_engine = AlertRuleEngine()
        rm = DataQualityRiskManager()
        monitor = EnhancedDataQualityMonitor(risk_manager=rm, alert_engine=alert_engine)
        # 低分指标入库后，监控循环 _process_alerts 应把最近一条灌入引擎
        low = QualityMetrics(data_source='s', data_type='kline', symbol='T',
                             overall_score=0.3, completeness_score=0.3)
        monitor.monitor_data_quality = lambda *a, **k: low
        with monitor._lock:
            monitor._quality_metrics['s_kline_T'] = low
        monitor._process_alerts()
        self.assertGreaterEqual(alert_engine._stats['triggered_alerts'], 1)


# ---------------------------------------------------------------------------
# 修复3：IntelligentFailoverEngine 死代码清理
# ---------------------------------------------------------------------------
class TestDeadCodeRemoved(unittest.TestCase):
    """intelligent_failover_engine 已删除，模块不可导入"""

    def test_module_not_found(self):
        self.assertIsNone(importlib.util.find_spec('core.intelligent_failover_engine'))


if __name__ == '__main__':
    unittest.main()
