#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R290 回归测试: bottom_panel.LogWidget 后台线程日志刷新修复

用户报告: "为什么日志在应用程序的控制台上基本看不到呢? 只有启动的时候控制台上有日志
后面基本都不刷新了"。

根因 (R290): append_log 原实现用 _flush_timer(100ms) 批量刷新, 但运行期日志大量来自
后台工作线程 (数据源重连/告警去重/K线落库等), QTimer 无法在非拥有线程 start()
("QObject::startTimer: Timers cannot be started from another thread"), 定时器永不触发,
日志永久堆积在 _pending_logs, 导致 GUI 日志面板启动完成后不再刷新。启动阶段日志由
主线程产生所以能显示——与用户观察完全吻合。

修复: 移除 _pending_logs/_flush_timer 批量机制, append_log 直接 emit log_appended
信号, 跨线程自动 QueuedConnection 调度到主线程执行, Qt 信号发射本身线程安全。

覆盖:
- 后台线程调用 append_log 后日志能显示在面板 (核心修复行为)
- 主线程调用 append_log 日志能显示
- 信号链路 log_appended → _append_log_safe 生效
- 回归守卫: _pending_logs / _flush_timer 批量机制已彻底移除
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import sys
import types
import threading
import time

# ---------------------------------------------------------------------------
# conftest.py 会把 core.ui / core.ui.panels / base_panel / bottom_panel 预注册为
# MagicMock (见 conftest.py _GUI_MOCK_MODULES L59-65), 导致真实导入失败。
# 同时 core.ui.panels/__init__.py 会拉入 right_panel 等重型依赖链 (无头环境崩溃),
# 因此采用与 test_r251 相同的策略:
#   1) 移除 conftest 冲突 mock 条目;
#   2) 预注册轻量 core.ui.panels 包 (跳过 __init__.py 重型链);
#   3) 仅真实加载 bottom_panel + base_panel (两者只依赖 PyQt5 + ABC, 安全).
# ---------------------------------------------------------------------------
for _mod in (
    'core.ui', 'core.ui.panels', 'core.ui.panels.base_panel',
    'core.ui.panels.bottom_panel',
):
    sys.modules.pop(_mod, None)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_panels_pkg = types.ModuleType('core.ui.panels')
_panels_pkg.__path__ = [
    os.path.join(_ROOT, 'core', 'ui', 'panels')]
sys.modules['core.ui.panels'] = _panels_pkg

from PyQt5.QtWidgets import QApplication  # noqa: E402

from core.ui.panels.bottom_panel import LogWidget  # noqa: E402

import pytest  # noqa: E402


def _get_app():
    """获取或创建 QApplication 单例 (offscreen)"""
    return QApplication.instance() or QApplication(sys.argv[:1])


@pytest.fixture
def log_widget():
    """创建 LogWidget 并在 teardown 显式销毁 (规避 Qt 无头环境连续实例化硬崩溃)"""
    app = _get_app()
    w = LogWidget()
    yield w
    w.setParent(None)
    w.deleteLater()
    _pump_events(app, 50)
    import gc
    gc.collect()


def _pump_events(app, timeout_ms: float = 1000.0):
    """持续处理 Qt 事件, 直至跨线程 QueuedConnection 信号消费完毕"""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.005)


# ---------------------------------------------------------------------------
# 核心修复行为: 后台线程日志必须能显示在面板
# ---------------------------------------------------------------------------
def test_worker_thread_append_log_displays_in_panel(log_widget):
    """后台线程调用 append_log → 跨线程信号 → 面板显示全部日志"""
    app = _get_app()
    w = log_widget
    errors = []

    def worker():
        try:
            for i in range(10):
                w.append_log(f'后台线程日志 #{i}', 'INFO')
                time.sleep(0.01)
        except Exception as e:  # pragma: no cover
            errors.append(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=5.0)

    _pump_events(app)

    assert not errors, f'后台线程 append_log 抛异常: {errors}'
    text = w.toPlainText()
    lines = text.splitlines()
    assert len(lines) >= 10, f'面板应显示全部 10 条后台线程日志, 实际 {len(lines)} 行: {text!r}'
    assert '后台线程日志 #9' in text


def test_worker_thread_high_volume_no_loss(log_widget):
    """后台线程高频打日志 (非主线程触发) 不丢失"""
    app = _get_app()
    w = log_widget
    count = 50

    def worker():
        for i in range(count):
            w.append_log(f'高频日志 {i}', 'DEBUG')

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=5.0)

    _pump_events(app)

    text = w.toPlainText()
    assert len(text.splitlines()) >= count, (
        f'50 条后台线程日志应全部显示, 实际 {len(text.splitlines())} 行')


# ---------------------------------------------------------------------------
# 主线程行为与信号链路
# ---------------------------------------------------------------------------
def test_direct_append_log_displays(log_widget):
    """主线程直接调用 append_log 日志能显示"""
    app = _get_app()
    w = log_widget
    w.append_log('主线程日志', 'INFO')
    _pump_events(app)
    assert '主线程日志' in w.toPlainText()


def test_signal_chain_log_appended_to_append_log_safe(log_widget):
    """信号链路 log_appended → _append_log_safe 生效 (修复后显式连接)"""
    app = _get_app()
    w = log_widget
    w.log_appended.emit('<span>信号链路测试</span>', 'INFO')
    _pump_events(app)
    assert '信号链路测试' in w.toPlainText()


def test_add_log_compat_still_works(log_widget):
    """LogHandler 兼容入口 add_log(timestamp, level, message) 链路完好"""
    app = _get_app()
    w = log_widget
    w.add_log('12:00:00.123', 'WARNING', '兼容入口日志')
    _pump_events(app)
    text = w.toPlainText()
    assert '兼容入口日志' in text
    assert '12:00:00.123' in text


# ---------------------------------------------------------------------------
# 回归守卫: 旧批量刷新机制不得复活
# ---------------------------------------------------------------------------
def test_no_pending_logs_buffer_regression(log_widget):
    """回归守卫: 移除 _pending_logs 批量堆积缓冲 (根因结构)"""
    w = log_widget
    assert not hasattr(w, '_pending_logs'), (
        '旧批量机制 _pending_logs 不得复活: 后台线程日志会永久堆积于此')


def test_no_flush_timer_regression(log_widget):
    """回归守卫: 移除 _flush_timer 定时器 (根因: 非拥有线程 start() 永不触发)"""
    w = log_widget
    assert not hasattr(w, '_flush_timer'), (
        '旧批量机制 _flush_timer 不得复活: 定时器无法在后台线程启动')


def test_append_log_emits_formatted_with_color(log_widget):
    """append_log 构造含级别颜色的格式化消息后发射信号"""
    w = log_widget
    received = []

    def _spy(fmt, level):
        received.append((fmt, level))

    w.log_appended.connect(_spy)
    w.append_log('磁盘告警', 'WARNING')
    assert len(received) == 1
    fmt, level = received[0]
    assert level == 'WARNING'
    assert 'FF8C00' in fmt, f'WARNING 级别应带颜色 span, 实际: {fmt}'
    assert '磁盘告警' in fmt
