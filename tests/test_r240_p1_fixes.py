"""R240-P1: uninstall CWE-22 净化 + NotificationService 写锁 + EventBus 锁域 + DataService 死变量

验证 (全部来自 4 子智能体审计 + 主智能体交叉验证):
- plugins/plugin_market.py:445-448 uninstall_plugin 路径未净化 (install 已有 _sanitize_plugin_name)
- notification_service.py 写路径 L825/L1037-1062 无锁, 读路径 L1603-1607 有锁 → 竞态
- event_bus.py 写 _event_types 用 _event_types_lock (L341), 读 (L485) 用 _lock → 锁域不一致
- data_service.py:169 _service_lock 定义后全文件 0 使用 → 死变量
- TDD: RED → GREEN
"""
import os

import pytest


class TestUninstallPluginCWE22:
    """uninstall_plugin 路径净化 (R240-P1-1)"""

    def test_uninstall_sanitizes_path_traversal(self, tmp_path):
        """../../evil.txt 净化后不得删除目录外文件"""
        from plugins.plugin_market import PluginInstaller

        installer = PluginInstaller(str(tmp_path / "plugins"))
        os.makedirs(installer.plugins_dir, exist_ok=True)

        outside = tmp_path / "evil.txt"
        outside.write_text("x")

        installer.uninstall_plugin("../../evil.txt")

        assert outside.exists(), "路径穿越未净化, 目录外文件被删除!"

    def test_uninstall_sanitizes_abs_path(self, tmp_path):
        """绝对路径净化后不得删除原目录"""
        from plugins.plugin_market import PluginInstaller

        installer = PluginInstaller(str(tmp_path / "plugins"))
        os.makedirs(installer.plugins_dir, exist_ok=True)

        target_dir = tmp_path / "absolute"
        os.makedirs(str(target_dir), exist_ok=True)

        installer.uninstall_plugin(str(target_dir))

        assert target_dir.exists(), "绝对路径未净化, 原目录被删除!"

    def test_uninstall_normal_name_ok(self, tmp_path):
        """正常插件名可卸载"""
        from plugins.plugin_market import PluginInstaller

        installer = PluginInstaller(str(tmp_path / "plugins"))
        os.makedirs(str(tmp_path / "plugins" / "mypkg"), exist_ok=True)

        assert installer.uninstall_plugin("mypkg") is True
        assert not (tmp_path / "plugins" / "mypkg").exists()


class TestNotificationServiceWriteLock:
    """NotificationService 写路径锁补全 (R240-P1-2)"""

    def test_send_internal_write_locked(self):
        """_send_message_internal 统计写操作已在 _service_lock 域内"""
        import inspect
        from core.services.notification_service import NotificationService

        src = inspect.getsource(NotificationService._send_message_internal)
        assert "with self._service_lock:" in src, "写路径缺少 _service_lock 包裹"

    def test_suppress_write_locked(self):
        """send_notification 中 total_suppressed 写操作已在锁内"""
        import inspect
        from core.services.notification_service import NotificationService

        src = inspect.getsource(NotificationService.send_notification)
        assert "with self._service_lock:" in src, "去重统计写路径缺少锁"


class TestEventBusLockDomain:
    """EventBus _event_types 锁域统一 (R240-P1-3)"""

    def test_publish_after_register_ok(self):
        """注册事件后 publish 正常分发 (功能回归)"""
        from core.events.event_bus import EventBus

        bus = EventBus()
        bus.register_event_type("test.r240.event")

        received = []
        bus.subscribe("test.r240.event", lambda e: received.append(e))
        bus.publish("test.r240.event", foo=1)

        assert len(received) == 1, "事件分发失败"


class TestDataServiceDeadLock:
    """DataService _service_lock 死变量删除 (R240-P1-4)"""

    def test_no_service_lock_defined(self):
        """__init__ 中不再定义 _service_lock"""
        import inspect
        from core.services.data_service import DataService

        src = inspect.getsource(DataService.__init__)
        assert "_service_lock" not in src, "_service_lock 死变量未删除"
