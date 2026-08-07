# -*- coding: utf-8 -*-
"""R242-B 孤儿事件治理回归测试

覆盖:
- R242-B-001: HybridRecommendation 订阅错配修复 (类订阅, 恢复混合推荐链路)
- R242-B-002: alert_event_handler 死代码清理 (移除 ResourceAlert/ApplicationAlert 孤儿订阅)
- R242-B-003: MetricsAggregated 显式注册 (消除纯发布事件 warning)

说明: hybrid_recommendation_engine 模块 import 会触发 Qt 原生崩溃 (data_adapter→pyqtgraph,
无显示环境访问冲突, 预存环境问题, 与修复无关), 故 R242-B-001 采用事件总线机制验证 +
ast 静态验证修复落地, 不直接 import 该模块。
"""

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from core.events.event_bus import EventBus
from core.events.types import BaseEvent
from core.metrics.aggregation_service import MetricsAggregationService
from core.services.alert_event_handler import register_alert_handlers


class _HybridLikeEvent(BaseEvent):
    """模拟 hybrid 事件类 (含 Event 后缀, 模拟发布端类名)"""

    def __init__(self, **kwargs):
        super().__init__()
        self.request_id = kwargs.get('request_id', '')


class TestHybridRecommendationSubscribeFix(unittest.TestCase):
    """R242-B-001: 订阅类名后 handler 可达 (发布端 publish 类实例)"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T01_class_subscribe_receives_class_publish(self):
        """T01: subscribe(类) + publish(类实例) → handler 被调用"""
        received = []

        def handler(event):
            received.append(event)

        self.bus.subscribe(_HybridLikeEvent, handler)
        self.bus.publish(_HybridLikeEvent(request_id='r1'))
        self.assertEqual(len(received), 1, "类订阅应收到类实例发布")
        self.assertEqual(received[0].request_id, 'r1')

    def test_T02_str_subscribe_does_not_receive_class_publish(self):
        """T02: 订阅错误字符串 → 收不到类实例发布 (验证错配根因)"""
        received = []

        def handler(event):
            received.append(event)

        # 旧代码的错误订阅方式: 字符串 'HybridLike' vs 类名 'HybridLikeEvent'
        self.bus.subscribe('_HybridLike', handler)
        self.bus.publish(_HybridLikeEvent(request_id='r1'))
        self.assertEqual(len(received), 0,
                         "字符串订阅收不到类实例发布 (类名含 Event 后缀时错配)")

    def test_T03_engine_source_uses_class_refs(self):
        """T03: hybrid_recommendation_engine.py 的 subscribe/unsubscribe 已改用类引用"""
        src_path = (Path(__file__).parent.parent
                    / 'core' / 'services' / 'hybrid_recommendation_engine.py')
        tree = ast.parse(src_path.read_text(encoding='utf-8'))

        str_sub_refs = []
        class_sub_refs = 0
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ('subscribe', 'unsubscribe') and node.args):
                first = node.args[0]
                if (isinstance(first, ast.Constant) and isinstance(first.value, str)
                        and 'HybridRecommendation' in first.value):
                    str_sub_refs.append(node.lineno)
                elif isinstance(first, ast.Name) and 'HybridRecommendation' in first.id:
                    class_sub_refs += 1

        self.assertEqual(str_sub_refs, [],
                         f"仍存在字符串订阅 HybridRecommendation*: 行 {str_sub_refs}")
        self.assertGreaterEqual(class_sub_refs, 4,
                                "4 处 subscribe/unsubscribe 应全部改为类引用")

    def test_T04_subscribe_auto_registers_event(self):
        """T04: 类订阅自动注册 (R242-A-001 联动), publish 无未注册 warning"""
        def handler(event):
            pass

        self.bus.subscribe(_HybridLikeEvent, handler)
        self.assertIn('_HybridLikeEvent', self.bus._event_types)
        with patch('core.events.event_bus.logger') as mock_logger:
            self.bus.publish(_HybridLikeEvent(request_id='r2'))
            warned = any(
                '未注册事件' in str(call)
                for call in mock_logger.warning.call_args_list
            )
            self.assertFalse(warned, "类订阅后 publish 不应触发未注册 warning")


class TestAlertDeadCodeCleanup(unittest.TestCase):
    """R242-B-002: 死代码清理后订阅清单正确"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T05_orphan_subscriptions_removed(self):
        """T05: 不再订阅 ResourceAlert/ApplicationAlert (0 发布方死订阅)"""
        register_alert_handlers(self.bus)
        self.assertNotIn('ResourceAlert', self.bus._handlers,
                         "死订阅 'ResourceAlert' 应已移除")
        self.assertNotIn('ApplicationAlert', self.bus._handlers,
                         "死订阅 'ApplicationAlert' 应已移除")

    def test_T06_active_subscriptions_kept(self):
        """T06: R242-A-002 补订阅保持有效"""
        register_alert_handlers(self.bus)
        self.assertIn('ResourceThresholdExceeded', self.bus._handlers)
        self.assertIn('ApplicationThresholdExceeded', self.bus._handlers)
        self.assertIn('ResourceAlertEvent', self.bus._handlers)

    def test_T07_dead_handlers_removed(self):
        """T07: 死 handler 方法已从类中删除"""
        from core.services.alert_event_handler import AlertEventHandler
        self.assertFalse(hasattr(AlertEventHandler, 'handle_resource_alert'),
                         "handle_resource_alert 应已删除")
        self.assertFalse(hasattr(AlertEventHandler, 'handle_application_alert'),
                         "handle_application_alert 应已删除")


class TestMetricsAggregatedRegister(unittest.TestCase):
    """R242-B-003: MetricsAggregated 显式注册"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T08_service_init_registers_event(self):
        """T08: MetricsAggregationService 实例化时显式注册 MetricsAggregated"""
        MetricsAggregationService(event_bus=self.bus)
        self.assertIn('MetricsAggregated', self.bus._event_types,
                      "'MetricsAggregated' 应被显式注册")

    def test_T09_aggregated_publish_no_warning(self):
        """T09: 显式注册后 publish 无未注册 warning"""
        MetricsAggregationService(event_bus=self.bus)
        with patch('core.events.event_bus.logger') as mock_logger:
            self.bus.publish('MetricsAggregated',
                             resources={}, applications={}, timestamp=0)
            warned = any(
                '未注册事件' in str(call)
                for call in mock_logger.warning.call_args_list
            )
            self.assertFalse(warned, "显式注册后 publish 不应触发未注册 warning")


class TestEventBusBoolFix(unittest.TestCase):
    """R242-B-004: EventBus.__bool__ 恒 True (修复 len()!=0 真值误判)"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T10_bool_always_true(self):
        """T10: 无订阅者时 bool(bus) 仍为 True (此前 False 导致订阅失效)"""
        self.assertTrue(bool(self.bus), "空总线也应视为有效对象引用")

    def test_T11_aggregation_subscribe_takes_effect(self):
        """T11: __bool__ 修复后 aggregation_service 的订阅真正注册"""
        MetricsAggregationService(event_bus=self.bus)
        self.assertIn('SystemResourceUpdated', self.bus._event_types,
                      "SystemResourceUpdated 订阅应生效 (此前被 bool 误判吞掉)")
        self.assertIn('ApplicationMetricRecorded', self.bus._event_types)
        self.assertIn('MetricsAggregated', self.bus._event_types)

    def test_T12_len_still_reports_handlers(self):
        """T12: __len__ 语义不受影响 (handler 统计)"""
        def handler(event):
            pass

        self.bus.subscribe('x.event', handler)
        self.assertEqual(len(self.bus), 1, "__len__ 仍返回处理器总数")


if __name__ == '__main__':
    unittest.main()
