#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R243-C 测试: P2 治理残留清理

背景: core/events/types.py 的 ResourceAlert (L718-743) / ApplicationAlert
     (L746-773) 为死类 (全项目运行时代码零引用), core/events/__init__.py
     L38-39 死导入 + L106-107 死导出.

- T01: types.py 不再包含 ResourceAlert/ApplicationAlert
- T02: core.events 不再导出 ResourceAlert/ApplicationAlert
"""
import unittest


class TestDeadTypeCleanup(unittest.TestCase):
    def test_T01_dead_types_removed_from_types_module(self):
        import core.events.types as t
        self.assertFalse(hasattr(t, 'ApplicationAlert'),
                         "ApplicationAlert 死类应已删除")
        self.assertFalse(hasattr(t, 'ResourceAlert'),
                         "ResourceAlert 死类应已删除")

    def test_T02_dead_exports_removed_from_package(self):
        import core.events as ev
        self.assertNotIn('ApplicationAlert', ev.__all__)
        self.assertNotIn('ResourceAlert', ev.__all__)
        self.assertFalse(hasattr(ev, 'ApplicationAlert'))
        self.assertFalse(hasattr(ev, 'ResourceAlert'))


if __name__ == '__main__':
    unittest.main()
