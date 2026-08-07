# -*- coding: utf-8 -*-
"""R242-A-002 告警阈值事件订阅补全 TDD 测试

验证: ResourceThresholdExceeded / ApplicationThresholdExceeded / ResourceAlertEvent
      已注册到告警事件处理器, handler 能正确处理事件对象并分发告警
RED: 修改前 aggregation_service 发布 (aggregation_service.py:307/339) 与
     resource_monitor 发布 (resource_monitor.py:448) 均无订阅者 (ORPHAN_PUB)
GREEN: register_alert_handlers 补订阅 + handler 构造 AlertMessage 走告警链路
"""

import unittest
from unittest.mock import MagicMock, patch

from core.events.event_bus import EventBus
from core.services.alert_event_handler import (
    AlertEventHandler, register_alert_handlers,
)


class _Event:
    """模拟字符串事件 publish 生成的动态事件对象 (event_bus.py:473-476)"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.event_type = 'dynamic'


class TestThresholdAlertHandlers(unittest.TestCase):
    """R242-A-002: 阈值告警 handler 功能验证"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)
        self.handler = AlertEventHandler()
        # 替换告警去重服务, 避免依赖真实服务与副作用
        self.handler.alert_service = MagicMock()
        self.handler.alert_service.process_alert.return_value = True

    def test_T01_register_subscribes_threshold_events(self):
        """T01: register_alert_handlers 补订阅 3 个孤儿告警事件"""
        register_alert_handlers(self.bus)
        self.assertIn('ResourceThresholdExceeded', self.bus._handlers)
        self.assertIn('ApplicationThresholdExceeded', self.bus._handlers)
        self.assertIn('ResourceAlertEvent', self.bus._handlers)

    def test_T02_subscribe_auto_registers_threshold_events(self):
        """T02: 补订阅后事件自动注册, publish 无未注册 warning"""
        register_alert_handlers(self.bus)
        with patch('core.events.event_bus.logger') as mock_logger:
            self.bus.publish('ResourceThresholdExceeded',
                             cpu_percent=95.0, memory_percent=50.0,
                             disk_percent=40.0, timestamp=0)
            warned = any(
                '未注册事件' in str(call)
                for call in mock_logger.warning.call_args_list
            )
            self.assertFalse(warned, "补订阅后 publish 不应触发未注册 warning")

    def test_T03_resource_threshold_handler_builds_alert(self):
        """T03: handle_resource_threshold_exceeded 分发告警 (process_alert 参数版)"""
        event = _Event(cpu_percent=95.0, memory_percent=88.0,
                       disk_percent=30.0, timestamp=1000000000)
        self.handler.handle_resource_threshold_exceeded(event)
        self.assertTrue(self.handler.alert_service.process_alert.called,
                        "应调用去重服务分发告警")
        calls = self.handler.alert_service.process_alert.call_args_list
        self.assertEqual(len(calls), 2, "CPU 与内存均超限应各分发一条告警")
        cpu_call = next(
            c for c in calls if 'CPU使用率' in c[1]['message'])
        self.assertEqual(cpu_call[1]['category'], "系统资源")
        self.assertEqual(cpu_call[1]['metadata']['current_value'], 95.0)

    def test_T04_application_threshold_handler_builds_alert(self):
        """T04: handle_application_threshold_exceeded 分发告警"""
        event = _Event(operation_name='query_data', duration=8.5,
                       was_successful=True, timestamp=1000000000)
        self.handler.handle_application_threshold_exceeded(event)
        self.assertTrue(self.handler.alert_service.process_alert.called,
                        "应调用去重服务分发告警")
        kwargs = self.handler.alert_service.process_alert.call_args[1]
        self.assertEqual(kwargs['category'], "应用性能")
        self.assertIn("响应时间", kwargs['message'])

    def test_T05_application_failure_builds_alert(self):
        """T05: 执行失败事件同样分发告警"""
        event = _Event(operation_name='save_order', duration=0.1,
                       was_successful=False, timestamp=1000000000)
        self.handler.handle_application_threshold_exceeded(event)
        kwargs = self.handler.alert_service.process_alert.call_args[1]
        self.assertEqual(kwargs['level'].value, "error")

    def test_T06_resource_alert_event_handler(self):
        """T06: handle_resource_alert_event 读取 alert 字段分发告警"""
        from core.performance.resource_monitor import (
            ResourceAlert, ResourceType, AlertSeverity,
        )
        alert_obj = ResourceAlert(
            alert_id='a1', resource_type=ResourceType.CPU,
            severity=AlertSeverity.CRITICAL, current_value=95.0,
            threshold_value=80.0, exceed_percent=18.75,
            message='CPU使用率 (95.0%) 超过阈值 (80%)')
        event = _Event(alert=alert_obj)
        self.handler.handle_resource_alert_event(event)
        kwargs = self.handler.alert_service.process_alert.call_args[1]
        self.assertEqual(kwargs['message'], alert_obj.message)
        self.assertEqual(kwargs['metadata']['current_value'], 95.0)
        # R242-A-003: 采用权威 severity 字段, CRITICAL 不再被倍率重算降级
        self.assertEqual(kwargs['level'].value, "critical")


if __name__ == '__main__':
    unittest.main()
