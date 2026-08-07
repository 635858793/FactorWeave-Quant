# -*- coding: utf-8 -*-
"""R238-NEW-P0 关闭链 LIFO 修复 TDD 测试

验证: main.py _cleanup() 优先调用 UnifiedServiceContainer.shutdown_all_services()
      (LIFO 关闭 + 状态更新), 而非 ServiceContainer.dispose() (无序 dict 迭代)

强约束: R229-HVD-002 启动/关闭对称铁律 + R78 dispose 幂等
TDD: tests/test_r238_a_main_cleanup_lifo.py
"""

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# 防御: 无 GUI 环境跳过
try:
    from PyQt5.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
except Exception:  # pragma: no cover
    QApplication = None


class FakeUnifiedContainer:
    """模拟 UnifiedServiceContainer: 有 shutdown_all_services"""

    def __init__(self):
        self.dispose_called = False
        self.shutdown_called = False

    def dispose(self):
        self.dispose_called = True

    def shutdown_all_services(self):
        self.shutdown_called = True


class FakeLegacyContainer:
    """模拟旧 ServiceContainer: 仅 dispose"""

    def __init__(self):
        self.dispose_called = False

    def dispose(self):
        self.dispose_called = True


class TestMainCleanupLIFO(unittest.TestCase):
    """R238-NEW-P0: main.py _cleanup() 关闭链 LIFO 验证"""

    @classmethod
    def setUpClass(cls):
        cls.has_qt = QApplication is not None
        try:
            # 直接加载 main 模块 (不执行 main())
            import main as main_module
            cls.main_module = main_module
        except Exception as e:  # pragma: no cover
            cls.main_module = None
            cls.import_error = str(e)

    def _make_app(self, container):
        """构造 FactorWeaveQuantApplication 实例 (绕过 __init__)"""
        app = object.__new__(self.main_module.FactorWeaveQuantApplication)
        app.service_container = container
        app.main_window_coordinator = MagicMock()
        app.qt_handler = MagicMock()
        return app

    def test_T01_unified_container_uses_shutdown_all_services(self):
        """T01: UnifiedServiceContainer 时优先调用 shutdown_all_services (LIFO)"""
        if self.main_module is None:
            self.skipTest(f"main 模块导入失败: {getattr(self, 'import_error', '')}")
        container = FakeUnifiedContainer()
        app = self._make_app(container)
        with patch.object(self.main_module.asyncio, 'get_event_loop', return_value=MagicMock()):
            app._cleanup()
        self.assertTrue(container.shutdown_called, "UnifiedServiceContainer 应调用 shutdown_all_services")
        self.assertFalse(container.dispose_called, "UnifiedServiceContainer 不应回退到 dispose")

    def test_T02_legacy_container_falls_back_to_dispose(self):
        """T02: 无 shutdown_all_services 时回退 dispose (向后兼容)"""
        if self.main_module is None:
            self.skipTest(f"main 模块导入失败: {getattr(self, 'import_error', '')}")
        container = FakeLegacyContainer()
        app = self._make_app(container)
        with patch.object(self.main_module.asyncio, 'get_event_loop', return_value=MagicMock()):
            app._cleanup()
        self.assertTrue(container.dispose_called, "旧容器应回退到 dispose")

    def test_T03_cleanup_does_not_raise(self):
        """T03: _cleanup 全路径不抛错 (R78 防御)"""
        if self.main_module is None:
            self.skipTest(f"main 模块导入失败: {getattr(self, 'import_error', '')}")
        container = FakeUnifiedContainer()
        app = self._make_app(container)
        try:
            with patch.object(self.main_module.asyncio, 'get_event_loop', return_value=MagicMock()):
                app._cleanup()
        except Exception as e:
            self.fail(f"_cleanup 抛错: {e}")


if __name__ == '__main__':
    unittest.main()
