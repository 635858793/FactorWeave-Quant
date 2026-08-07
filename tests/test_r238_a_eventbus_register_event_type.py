# -*- coding: utf-8 -*-
"""R238-NEW-P0-C EventBus 事件注册基座重建 TDD 测试

验证: EventBus.register_event_type() 存在 + 幂等 + publish 未注册 warning

强约束: R8 §8.1 铁律 #1 双轨注册 + R85 §10 假修复鉴别
TDD: tests/test_r238_a_eventbus_register_event_type.py
"""

import unittest
from unittest.mock import patch

from core.events.event_bus import EventBus
from core.events.types import BaseEvent


class _TestBizEvent(BaseEvent):
    """测试用事件类"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestRegisterEventType(unittest.TestCase):
    """R238-NEW-P0-C: EventBus.register_event_type 基座验证"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T01_method_exists(self):
        """T01: register_event_type 方法必须存在 (R222 声称基座, R157 物理删除后重建)"""
        self.assertTrue(
            hasattr(self.bus, 'register_event_type') and callable(self.bus.register_event_type),
            "EventBus.register_event_type 不存在 (R8 §8.1 铁律 #1 基座缺失)"
        )

    def test_T02_register_class_returns_true_new(self):
        """T02: 注册 BaseEvent 类 → 返回 True (新注册)"""
        result = self.bus.register_event_type(_TestBizEvent, source='test')
        self.assertTrue(result, "首次注册应返回 True")

    def test_T03_register_class_idempotent(self):
        """T03: 重复注册 → 返回 False (幂等)"""
        self.bus.register_event_type(_TestBizEvent, source='test')
        result = self.bus.register_event_type(_TestBizEvent, source='test')
        self.assertFalse(result, "重复注册应返回 False (幂等)")

    def test_T04_register_str_name(self):
        """T04: 注册字符串事件名"""
        result = self.bus.register_event_type('my.custom.event', source='test')
        self.assertTrue(result, "字符串事件名注册应返回 True")

    def test_T05_publish_registered_no_warning(self):
        """T05: 已注册事件 publish → 无未注册 warning"""
        self.bus.register_event_type('my.registered.event', source='test')
        with patch('core.events.event_bus.logger') as mock_logger:
            self.bus.publish('my.registered.event')
            for call in mock_logger.warning.call_args_list:
                self.assertNotIn('未注册事件', str(call), "已注册事件不应触发未注册 warning")

    def test_T06_publish_unregistered_warns(self):
        """T06: 未注册事件 publish → 触发 warning (R8 §8.1 铁律 #1 机制)"""
        with patch('core.events.event_bus.logger') as mock_logger:
            self.bus.publish('my.unregistered.event')
            warned = any(
                '未注册事件' in str(call)
                for call in mock_logger.warning.call_args_list
            )
            self.assertTrue(warned, "未注册事件应触发 warning")

    def test_T07_internal_state_event_types(self):
        """T07: _event_types 注册表存在且可读"""
        self.bus.register_event_type('state.check.event', source='test')
        self.assertIn('state.check.event', self.bus._event_types)


if __name__ == '__main__':
    unittest.main()
