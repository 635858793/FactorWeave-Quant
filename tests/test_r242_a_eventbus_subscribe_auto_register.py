# -*- coding: utf-8 -*-
"""R242-A-001 EventBus.subscribe 自动注册 TDD 测试

验证: subscribe() 后事件自动注册到 _event_types, publish 不再误报未注册 warning
RED: 修改前 subscribe 不注册 → publish 触发未注册 warning
GREEN: subscribe 自动注册 → publish 无未注册 warning, 显式 register_event_type 不受影响
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


class TestSubscribeAutoRegister(unittest.TestCase):
    """R242-A-001: subscribe 自动注册事件类型"""

    def setUp(self):
        self.bus = EventBus(async_execution=False)

    def test_T01_subscribe_class_auto_registers(self):
        """T01: 订阅类事件 → 事件名自动进入 _event_types"""
        def handler(event):
            pass

        self.bus.subscribe(_TestBizEvent, handler)
        self.assertIn('_TestBizEvent', self.bus._event_types,
                      "subscribe 类事件应自动注册")

    def test_T02_subscribe_str_auto_registers(self):
        """T02: 订阅字符串事件 → 事件名自动进入 _event_types"""
        def handler(event):
            pass

        self.bus.subscribe('my.biz.event', handler)
        self.assertIn('my.biz.event', self.bus._event_types,
                      "subscribe 字符串事件应自动注册")

    def test_T03_subscribed_event_publish_no_warning(self):
        """T03: 已订阅事件 publish → 无未注册 warning (消除误报)"""
        def handler(event):
            pass

        self.bus.subscribe('subscribed.event', handler)
        with patch('core.events.event_bus.logger') as mock_logger:
            self.bus.publish('subscribed.event')
            for call in mock_logger.warning.call_args_list:
                self.assertNotIn('未注册事件', str(call),
                                 "已订阅事件 publish 不应触发未注册 warning")

    def test_T04_register_event_type_still_works(self):
        """T04: 显式 register_event_type 仍可用 (幂等, 不破坏原基座)"""
        self.assertTrue(self.bus.register_event_type('manual.event', source='test'))
        self.assertFalse(self.bus.register_event_type('manual.event', source='test'),
                         "重复注册应返回 False")

    def test_T05_unregistered_publish_still_warns(self):
        """T05: 未注册且未订阅事件 publish → 仍触发 warning (治理信号保留)"""
        with patch('core.events.event_bus.logger') as mock_logger:
            self.bus.publish('truly.orphan.event')
            warned = any(
                '未注册事件' in str(call)
                for call in mock_logger.warning.call_args_list
            )
            self.assertTrue(warned, "未注册孤儿事件应保留 warning")


if __name__ == '__main__':
    unittest.main()
