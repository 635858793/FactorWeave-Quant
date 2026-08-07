#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R243-A 测试: ui_state_synchronizer 订阅错配修复 (P0)

背景: core/ui_integration/ui_state_synchronizer.py:300-302 订阅了 3 个
     项目中不存在的事件名 (task.status_changed / ai.status_updated /
     performance.metrics_updated), 真实发布方分别发布:
     - training.task.status_changed   (core/services/model_training_service.py:575)
     - ai_selection.completed         (core/services/ai_selection_integration_service.py:688)
     - performance.metrics_collected  (core/services/performance_service.py:267)
     且旧 handler 直接读 event.data (dict), 而 EventBus.publish(str, **kwargs)
     生成动态属性对象 (event_bus.py:477-485) -> AttributeError 静默失败.

- T01: _setup_event_handlers 订阅名改为真实事件名
- T02: _on_business_task_changed 适配动态属性 (training.task.status_changed)
- T03: _on_business_ai_changed 适配动态属性 (ai_selection.completed)
- T04: _on_business_performance_changed 适配动态属性 (performance.metrics_collected)
- T05: 兼容旧 event.data dict 形式
"""
import unittest
from unittest.mock import Mock

from core.ui_integration.ui_state_synchronizer import UIStateSynchronizer


def _make_event(**kwargs):
    """构造与 EventBus.publish(str, **kwargs) 生成的动态属性对象一致的事件"""
    obj = type('Event', (), {})()
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


class TestSubscriptionNames(unittest.TestCase):
    """T01: 订阅名应与真实发布方一致"""

    def setUp(self):
        obj = UIStateSynchronizer.__new__(UIStateSynchronizer)
        obj.event_bus = Mock()
        self.obj = obj

    def test_T01_subscribe_uses_real_event_names(self):
        self.obj._setup_event_handlers()
        names = [c.args[0] for c in self.obj.event_bus.subscribe.call_args_list]
        self.assertEqual(
            names,
            [
                'training.task.status_changed',
                'ai_selection.completed',
                'performance.metrics_collected',
            ],
            "订阅名应与真实发布方一致")


class TestHandlersDynamicAttributes(unittest.TestCase):
    """T02-T05: handler 从动态属性提取数据并触发同步"""

    def setUp(self):
        obj = UIStateSynchronizer.__new__(UIStateSynchronizer)
        obj.ui_provider = Mock()
        obj.business_provider = None
        obj.sync_configs = {
            'task': Mock(sync_direction='BUSINESS_TO_UI'),
            'ai_status': Mock(sync_direction='BUSINESS_TO_UI'),
            'performance': Mock(sync_direction='BUSINESS_TO_UI'),
        }
        obj._sync_from_business = Mock()
        self.obj = obj

    def test_T02_task_handler_extracts_dynamic_attrs(self):
        event = _make_event(task_id='task-1', status='RUNNING', progress=50)
        self.obj._on_business_task_changed(event)
        self.obj._sync_from_business.assert_called_once_with(
            'task', 'task-1',
            {'task_id': 'task-1', 'status': 'RUNNING', 'progress': 50})

    def test_T03_ai_handler_extracts_dynamic_attrs(self):
        event = _make_event(strategy_id='s1', result_id='r1',
                            selected_stocks=['600000'])
        self.obj._on_business_ai_changed(event)
        self.obj._sync_from_business.assert_called_once_with(
            'ai_status', 'global',
            {'strategy_id': 's1', 'result_id': 'r1',
             'selected_stocks': ['600000']})

    def test_T04_performance_handler_extracts_dynamic_attrs(self):
        event = _make_event(metrics={'cpu': 10.0})
        self.obj._on_business_performance_changed(event)
        self.obj._sync_from_business.assert_called_once_with(
            'performance', 'global', {'metrics': {'cpu': 10.0}})

    def test_T05_task_handler_compatible_with_data_dict(self):
        event = _make_event(data={'task_id': 'task-9', 'status': 'DONE'})
        self.obj._on_business_task_changed(event)
        self.obj._sync_from_business.assert_called_once_with(
            'task', 'task-9',
            {'task_id': 'task-9', 'status': 'DONE'})


if __name__ == '__main__':
    unittest.main()
