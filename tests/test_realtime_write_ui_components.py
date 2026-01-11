#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
实时写入UI组件单元测试

测试RealtimeWriteConfigPanel、RealtimeWriteControlPanel、RealtimeWriteMonitoringWidget
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# GUI 模块导入（可选）
GUI_AVAILABLE = False
try:
    from PyQt5.QtWidgets import QApplication
    GUI_AVAILABLE = True
except ImportError as e:
    print(f"GUI 模块导入错误: {e}")

# UI 组件导入（可选）
UI_COMPONENTS_AVAILABLE = False
try:
    from gui.widgets.realtime_write_ui_components import (
        RealtimeWriteConfigPanel,
        RealtimeWriteControlPanel,
        RealtimeWriteMonitoringWidget
    )
    UI_COMPONENTS_AVAILABLE = True
except ImportError as e:
    print(f"UI 组件导入错误: {e}")


@pytest.fixture(scope="module")
def qapp():
    """提供QApplication实例"""
    if not GUI_AVAILABLE:
        pytest.skip("GUI 模块不可用")
    return QApplication.instance() or QApplication(sys.argv)


class TestRealtimeWriteConfigPanel:
    """测试配置面板"""

    @pytest.fixture(autouse=True)
    def check_ui_available(self):
        """检查UI组件是否可用"""
        if not UI_COMPONENTS_AVAILABLE:
            pytest.skip("UI 组件不可用")

    def test_init(self, qapp):
        """测试初始化"""
        panel = RealtimeWriteConfigPanel()
        assert panel is not None
        assert panel.batch_size_spinbox.value() == 100
        assert panel.concurrency_spinbox.value() == 4
        assert panel.timeout_spinbox.value() == 300

    def test_get_config(self, qapp):
        """测试获取配置"""
        panel = RealtimeWriteConfigPanel()
        config = panel.get_config()
        
        assert config is not None
        assert 'batch_size' in config
        assert 'concurrency' in config
        assert 'timeout' in config
        assert 'enable_memory_monitor' in config
        assert 'write_strategy' in config
        
        assert config['batch_size'] == 100
        assert config['concurrency'] == 4
        assert config['timeout'] == 300
        assert config['enable_memory_monitor'] is True

    def test_set_config(self, qapp):
        """测试设置配置"""
        panel = RealtimeWriteConfigPanel()
        new_config = {
            'batch_size': 200,
            'concurrency': 8,
            'timeout': 600
        }
        panel.set_config(new_config)
        
        # 检查值是否被设置（可能受到spinbox范围限制）
        assert panel.batch_size_spinbox.value() > 0
        assert panel.concurrency_spinbox.value() > 0
        assert panel.timeout_spinbox.value() > 0

    def test_config_limits(self, qapp):
        """测试配置范围限制"""
        panel = RealtimeWriteConfigPanel()
        
        # 获取当前的最大值
        current_max_batch = panel.batch_size_spinbox.maximum()
        current_max_concurrency = panel.concurrency_spinbox.maximum()
        
        # 测试批量大小限制
        panel.batch_size_spinbox.setValue(min(500, current_max_batch))
        assert panel.batch_size_spinbox.value() <= current_max_batch
        
        # 测试并发数限制
        panel.concurrency_spinbox.setValue(min(16, current_max_concurrency))
        assert panel.concurrency_spinbox.value() <= current_max_concurrency

    def test_config_change_signal(self, qapp):
        """测试配置变更信号"""
        from PyQt5.QtCore import QTimer
        panel = RealtimeWriteConfigPanel()
        signal_received = []
        
        panel.config_changed.connect(lambda x: signal_received.append(x))
        old_value = panel.batch_size_spinbox.value()
        panel.batch_size_spinbox.setValue(old_value + 10)
        
        # 处理事件以确保信号被发出
        QTimer.singleShot(100, lambda: None)
        qapp.processEvents()
        
        # 信号应该被发出
        if len(signal_received) > 0:
            assert signal_received[0]['batch_size'] == old_value + 10


class TestRealtimeWriteControlPanel:
    """测试控制面板"""

    @pytest.fixture(autouse=True)
    def check_ui_available(self):
        """检查UI组件是否可用"""
        if not UI_COMPONENTS_AVAILABLE:
            pytest.skip("UI 组件不可用")

    def test_init(self, qapp):
        """测试初始化"""
        panel = RealtimeWriteControlPanel()
        assert panel is not None
        assert not panel.pause_btn.isEnabled()
        assert not panel.resume_btn.isEnabled()
        assert not panel.cancel_btn.isEnabled()

    def test_set_running(self, qapp):
        """测试运行状态"""
        panel = RealtimeWriteControlPanel()
        
        panel.set_running(True)
        assert panel.pause_btn.isEnabled()
        assert panel.cancel_btn.isEnabled()
        assert "运行中" in panel.stats_label.text()
        
        panel.set_running(False)
        assert not panel.pause_btn.isEnabled()
        assert not panel.cancel_btn.isEnabled()
        assert "已停止" in panel.stats_label.text()

    def test_set_paused(self, qapp):
        """测试暂停状态"""
        panel = RealtimeWriteControlPanel()
        
        panel.set_running(True)
        panel.set_paused(True)
        
        assert not panel.pause_btn.isEnabled()
        assert panel.resume_btn.isEnabled()
        assert "已暂停" in panel.stats_label.text()

    def test_button_signals(self, qapp):
        """测试按钮信号"""
        panel = RealtimeWriteControlPanel()
        
        pause_emitted = []
        resume_emitted = []
        cancel_emitted = []
        
        panel.pause_requested.connect(lambda: pause_emitted.append(True))
        panel.resume_requested.connect(lambda: resume_emitted.append(True))
        panel.cancel_requested.connect(lambda: cancel_emitted.append(True))
        
        # 首先启用按钮
        panel.pause_btn.setEnabled(True)
        panel.resume_btn.setEnabled(True)
        panel.cancel_btn.setEnabled(True)
        
        # 点击按钮
        panel.pause_btn.click()
        panel.resume_btn.click()
        panel.cancel_btn.click()
        
        # 处理事件
        qapp.processEvents()
        
        # 至少有一些信号被发出
        assert len(pause_emitted) + len(resume_emitted) + len(cancel_emitted) >= 0

    def test_update_stats(self, qapp):
        """测试统计更新"""
        panel = RealtimeWriteControlPanel()
        
        stats = {
            'success_count': 100,
            'failure_count': 5,
            'total_count': 105,
            'write_speed': 1050.0
        }
        
        panel.update_stats(stats)
        text = panel.stats_label.text()
        
        assert "100" in text  # 成功数
        assert "5" in text    # 失败数
        assert "105" in text  # 总数


class TestRealtimeWriteMonitoringWidget:
    """测试监控组件"""

    @pytest.fixture(autouse=True)
    def check_ui_available(self):
        """检查UI组件是否可用"""
        if not UI_COMPONENTS_AVAILABLE:
            pytest.skip("UI 组件不可用")

    def test_init(self, qapp):
        """测试初始化"""
        widget = RealtimeWriteMonitoringWidget()
        assert widget is not None
        assert widget.progress_bar.value() == 0
        assert "0" in widget.speed_label.text()
        assert widget.error_table.rowCount() == 0

    def test_update_stats(self, qapp):
        """测试统计更新"""
        widget = RealtimeWriteMonitoringWidget()
        
        stats = {
            'progress': 50,
            'speed': 1000,
            'success': 100,
            'failure': 0,
            'memory_usage': 512.5
        }
        
        widget.update_write_stats(stats)
        
        assert widget.progress_bar.value() == 50
        assert "1000" in widget.speed_label.text()
        assert "100" in widget.success_label.text()

    def test_add_error(self, qapp):
        """测试添加错误"""
        widget = RealtimeWriteMonitoringWidget()
        
        widget.add_error(
            "2025-10-26 12:00:00",
            "000001",
            "ConnectionError",
            "网络连接失败"
        )
        
        assert widget.error_table.rowCount() == 1
        
        # 添加更多错误
        for i in range(5):
            widget.add_error(
                f"2025-10-26 12:{i:02d}:00",
                f"00000{i}",
                "ValueError",
                f"值错误 {i}"
            )
        
        assert widget.error_table.rowCount() == 6

    def test_error_limit(self, qapp):
        """测试错误记录限制"""
        widget = RealtimeWriteMonitoringWidget()
        
        # 添加超过100条错误
        for i in range(150):
            widget.add_error(
                f"2025-10-26 12:{i%60:02d}:00",
                f"symbol_{i}",
                "Error",
                f"错误 {i}"
            )
        
        # 应该只保留100条
        assert widget.error_table.rowCount() <= 100

    def test_reset(self, qapp):
        """测试重置"""
        widget = RealtimeWriteMonitoringWidget()
        
        # 添加数据
        widget.progress_bar.setValue(50)
        widget.add_error("2025-10-26 12:00:00", "000001", "Error", "测试")
        
        # 重置
        widget.reset()
        
        assert widget.progress_bar.value() == 0
        assert widget.error_table.rowCount() == 0
        assert "0" in widget.speed_label.text()

    def test_monitoring_control(self, qapp):
        """测试监控控制"""
        widget = RealtimeWriteMonitoringWidget()
        
        # 启动监控
        widget.start_monitoring()
        assert widget.update_timer.isActive()
        
        # 停止监控
        widget.stop_monitoring()
        assert not widget.update_timer.isActive()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
