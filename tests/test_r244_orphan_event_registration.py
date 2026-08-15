#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R244 测试: 孤儿发布事件集中注册

背景: 事件仅发布无订阅 (B 类 ORPHAN_PUB, 4 路子智能体审计确认, 发布点事件名零差异):
     - 字符串形式 14 个 (performance.periodic_report 等, 含 R292 追加 service.orphan_scan_completed)
     - 类对象形式 9 个 (UpdateHistoryEvent 等, 注册名 = 类名, 含 R292 追加 StrategyConfigsLoadedEvent)
     subscribe 自动注册不覆盖无订阅方事件 -> 每次 publish 触发未注册 warning,
     需启动早期 register_event_type 显式注册.

- T01: register_orphan_event_types 注册全部 23 个事件名
- T02: 已注册字符串事件 publish 不再触发未注册 warning
- T03: 重复注册幂等
- T04: 注册函数挂在 ServiceBootstrap.__init__ 启动链路中
"""
import unittest
from unittest.mock import patch

from core.events.event_bus import EventBus
from core.services.service_bootstrap import (
    ORPHAN_EVENT_TYPES,
    register_orphan_event_types,
)

# 权威注册清单 (与 4 路审计子智能体交叉验证结果一致; R292 追加 2 项)
EXPECTED = [
    # 字符串形式 (13)
    'performance.periodic_report',
    'service_reset',
    'environment.changed',
    'auto_training.completed',
    'auto_training.failed',
    'plugin_unloaded',
    'data_source_switched',
    'order_fill_saved',
    'bettafish.sentiment.analysis.completed',
    'market.quote_updated',
    'data.masked',
    'funding_rate.analyzed',
    'gpu_acceleration_initialized',
    # 类对象形式 (8, 注册类名)
    'UpdateHistoryEvent',
    'DataAnalysisEvent',
    'DataIntegrityEvent',
    'TimerTriggerEvent',
    'TaskCompletedEvent',
    'TaskFailedEvent',
    'DataRefreshRequestedEvent',
    'DataRefreshCompletedEvent',
    # R292 追加: 启动期漏注册的孤儿发布事件 (strategy_service.py:533-538 / service_bootstrap.py:357-364)
    'StrategyConfigsLoadedEvent',
    'service.orphan_scan_completed',
]


class TestOrphanEventRegistration(unittest.TestCase):

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T01_all_orphan_events_registered(self):
        self.assertEqual(tuple(EXPECTED), ORPHAN_EVENT_TYPES,
                         "注册清单应与审计权威清单一致")
        register_orphan_event_types(self.bus)
        for name in EXPECTED:
            self.assertIn(name, self.bus._event_types,
                          f"{name} 应已注册")

    def test_T02_publish_no_warning_for_registered_string_events(self):
        register_orphan_event_types(self.bus)
        string_events = [e for e in EXPECTED
                         if '.' in e or e in ('service_reset', 'plugin_unloaded',
                                              'data_source_switched', 'order_fill_saved',
                                              'gpu_acceleration_initialized')]
        with patch('core.events.event_bus.logger') as mock_logger:
            for name in string_events:
                self.bus.publish(name, ts=1)
            warned = any(
                '未注册事件' in str(call)
                for call in mock_logger.warning.call_args_list
            )
            self.assertFalse(warned,
                             "已注册事件 publish 不应触发未注册 warning")

    def test_T03_registration_idempotent(self):
        register_orphan_event_types(self.bus)
        register_orphan_event_types(self.bus)  # 二次调用不抛异常
        self.assertEqual(len(self.bus._event_types), len(EXPECTED),
                         "重复注册不应增加事件类型数")

    def test_T04_hooked_into_bootstrap_init(self):
        import inspect
        src = inspect.getsource(
            __import__('core.services.service_bootstrap', fromlist=['ServiceBootstrap']).ServiceBootstrap)
        self.assertIn('register_orphan_event_types', src,
                      "ServiceBootstrap 启动链路应调用孤儿事件集中注册")


if __name__ == '__main__':
    unittest.main()
