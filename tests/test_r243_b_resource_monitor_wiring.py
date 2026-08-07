#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R243-B 测试: ResourceAlertEvent 发布端三层接线修复 (P0/P1)

背景: UnifiedResourceMonitor 发布端从未进入启动链路:
     - core/performance/__init__.py 缺 4 个导出 -> system_monitor_tab_refactored.py:28-33 ImportError
     - initialize_resource_monitor() 0 调用点 -> _event_bus 恒 None (resource_monitor.py:195/439)
     - monitor.start() 无任何调用点 (resource_monitor.py:223-238)
     - ResourceAlertEvent 是 _create_alert 内局部类 (resource_monitor.py:443-446)
     - _get_event_key 无 alert_id 维度 -> 同轮多资源告警 0.5s 窗口互相去重误伤

- T01: core.performance 导出 get_resource_monitor/initialize_resource_monitor/get_data_update_manager/UpdateStrategy
- T02: ResourceAlertEvent 提升为模块级类
- T03: initialize_resource_monitor 正确接线 event_bus
- T04: _get_event_key 对 ResourceAlertEvent 生成含 alert_id 的去重键
- T05: 启动链路 (service_bootstrap) 初始化并启动资源监控器
- T06: 端到端: _create_alert -> publish -> 订阅者收到 (含不同 alert_id 均可达)
"""
import unittest
from unittest.mock import Mock

import core.performance as perf_mod
from core.events.event_bus import EventBus
from core.performance import (
    get_data_update_manager,
    get_resource_monitor,
    initialize_resource_monitor,
    UpdateStrategy,
)
from core.performance.resource_monitor import (
    AlertSeverity,
    ResourceAlertEvent,
    ResourceType,
)


class TestPerformanceExports(unittest.TestCase):
    """T01: 缺失导出恢复"""

    def test_T01_missing_exports_restored(self):
        for name in ('get_resource_monitor', 'initialize_resource_monitor',
                     'get_data_update_manager', 'UpdateStrategy'):
            self.assertTrue(hasattr(perf_mod, name),
                            f"core.performance 应导出 {name}")
            self.assertIn(name, perf_mod.__all__)


class TestResourceAlertEventModuleLevel(unittest.TestCase):
    """T02: 事件类提升为模块级"""

    def test_T02_event_is_module_level_class(self):
        from core.performance.resource_monitor import ResourceAlert, ResourceType
        alert = ResourceAlert(
            alert_id='alert-001',
            resource_type=ResourceType.CPU,
            severity=AlertSeverity.CRITICAL,
            current_value=98.0,
            threshold_value=95.0,
            exceed_percent=3.0,
            message='CPU超限')
        event = ResourceAlertEvent(alert)
        self.assertEqual(event.alert.alert_id, 'alert-001')
        self.assertEqual(event.__class__.__name__, 'ResourceAlertEvent')


class TestWiring(unittest.TestCase):
    """T03-T06: 接线与链路"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T03_initialize_wires_event_bus(self):
        monitor = initialize_resource_monitor(event_bus=self.bus)
        self.assertIs(monitor._event_bus, self.bus)
        # 还原为 None, 避免污染单例
        monitor._event_bus = None

    def test_T04_get_event_key_includes_alert_id(self):
        from core.performance.resource_monitor import ResourceAlert, ResourceType
        a1 = ResourceAlert('alert-1', ResourceType.CPU, AlertSeverity.CRITICAL,
                           98.0, 95.0, 3.0, 'cpu')
        a2 = ResourceAlert('alert-2', ResourceType.MEMORY, AlertSeverity.CRITICAL,
                           98.0, 95.0, 3.0, 'mem')
        k1 = self.bus._get_event_key(ResourceAlertEvent(a1))
        k2 = self.bus._get_event_key(ResourceAlertEvent(a2))
        self.assertNotEqual(k1, k2, "不同 alert_id 的事件去重键应不同")
        self.assertIn('alert_id:alert-1', k1)

    def test_T05_bootstrap_wires_resource_monitor(self):
        import inspect
        import core.services.service_bootstrap as sb
        src = inspect.getsource(sb)
        self.assertIn('initialize_resource_monitor', src,
                      "启动链路应初始化资源监控器")
        self.assertIn('get_resource_monitor().start()', src,
                      "启动链路应启动资源监控器")

    def test_T06_end_to_end_alert_publish_distinct_alert_ids(self):
        monitor = get_resource_monitor()
        monitor._event_bus = self.bus

        received = []
        self.bus.subscribe('ResourceAlertEvent', lambda e: received.append(e))

        # 同轮 CPU + MEMORY 超阈值, 不同 alert_id 均不应被去重
        monitor._create_alert(ResourceType.CPU, AlertSeverity.CRITICAL,
                              98.0, monitor._thresholds[ResourceType.CPU], 3.0)
        monitor._create_alert(ResourceType.MEMORY, AlertSeverity.CRITICAL,
                              98.0, monitor._thresholds[ResourceType.MEMORY], 3.0)

        self.assertEqual(len(received), 2,
                         "两个不同 alert_id 的告警事件都应到达订阅者")
        alert_ids = {e.alert.alert_id for e in received}
        self.assertEqual(len(alert_ids), 2)

        # 还原单例, 避免污染后续测试
        monitor._event_bus = None


if __name__ == '__main__':
    unittest.main()
