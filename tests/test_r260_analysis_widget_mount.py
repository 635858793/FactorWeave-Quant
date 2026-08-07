#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R260 回归测试: AnalysisWidget 挂载修复 (TDD RED→GREEN)

覆盖 R260 已修复的 3 处 100% 确认项 (源码行号交叉验证实证):

1. _execute_chart_update 缺失方法 P1 (R244-R259 遗留)
   - gui/widgets/analysis_widget.py:142-143 构造时 chart_update_timer.timeout.connect
     self._execute_chart_update, 但全类 0 定义 → 定时器触发即 AttributeError
   - 修复: analysis_widget.py:724-736 补齐方法 (取 _pending_chart_update 执行后置 None,
     异常吞掉防定时器崩溃)
2. _on_analyze 降级弹窗 (恒弹"敬请期待")
   - core/coordinators/main_window_coordinator.py:2841-2866 改为真实挂载
     AnalysisWidget 独立浮窗 (惰性创建 + 二次调用 refresh 分支)
3. quick_start.py:1237 参数错位 (原将 QMainWindow 传给 config_manager 位置参数)
   - 修复: quick_start.py:1238 AnalysisWidget() 无参构造

测试策略 (污染治理 R260-c4 全量回归实证修订):
- 保留真实 PyQt5 (无头 offscreen) / numpy / pandas / matplotlib
- 仅 mock 无污染叶子 (同 R252 全量验证): analysis.pattern_recognition /
  analysis.pattern_manager; analysis_tabs 预注册轻量包 (R252:74-77 同款)
- 其余 analysis_widget 模块级依赖全部真实导入 (mock 核心包会导致其他测试文件
  collection "not a package" — R260-c4 全量回归实证)
- _execute_chart_update 以"未绑定方法 + 假 self (__new__)"调用, 不真实实例化
- _on_analyze 以 AST 源码断言验证 (零加载 main_window_coordinator, 零 sys.modules 污染)
"""
import ast
import os
import sys
import types
import importlib.util
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MPLBACKEND', 'Agg')

import pytest  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS_WIDGET_PATH = os.path.join(ROOT, 'gui', 'widgets', 'analysis_widget.py')
COORDINATOR_PATH = os.path.join(ROOT, 'core', 'coordinators', 'main_window_coordinator.py')
QUICK_START_PATH = os.path.join(ROOT, 'quick_start.py')

# ---------------------------------------------------------------------------
# sys.modules 保存/恢复工具 (同 test_r252_analysis_tabs.py:43-68)
# ---------------------------------------------------------------------------
_SAVED_MODULES = {}
_ADDED_MODULES = []


def _make_mock_module(name, **attrs):
    m = MagicMock()
    m.__name__ = name
    m.__file__ = f'<mock:{name}>'
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def _install(name, mod):
    if name in sys.modules:
        _SAVED_MODULES[name] = sys.modules[name]
    else:
        _ADDED_MODULES.append(name)
    sys.modules[name] = mod


def _pop_conftest_mock(name):
    """弹出 conftest 顶层 mock, 允许真实导入"""
    if name in sys.modules and isinstance(sys.modules[name], MagicMock):
        _SAVED_MODULES[name] = sys.modules[name]
        del sys.modules[name]


# ---------------------------------------------------------------------------
# analysis_widget 模块真实加载
# ---------------------------------------------------------------------------
# conftest 顶层 mock 了 'gui.widgets' 包 (无 __path__) → 弹出换真实包 (gui/widgets/__init__.py 为空)
_pop_conftest_mock('gui.widgets')

# 预注册轻量 analysis_tabs 包 (跳过 __init__.py 9 个子 tab 重型导入链, 同 R252:74-77)
_tabs_pkg = types.ModuleType('gui.widgets.analysis_tabs')
_tabs_pkg.__path__ = [os.path.join(ROOT, 'gui', 'widgets', 'analysis_tabs')]
_tabs_pkg.__package__ = 'gui.widgets.analysis_tabs'
for _tab in ('TechnicalAnalysisTab', 'PatternAnalysisTab', 'TrendAnalysisTab',
             'SectorFlowTab', 'WaveAnalysisTab', 'HotspotAnalysisTab'):
    setattr(_tabs_pkg, _tab, MagicMock())
_install('gui.widgets.analysis_tabs', _tabs_pkg)

# 无污染叶子 mock (R252 全量回归验证无 collection 污染; 其余依赖真实导入)
for _dep in ('analysis.pattern_recognition', 'analysis.pattern_manager'):
    _install(_dep, _make_mock_module(_dep, PatternRecognizer=MagicMock(), PatternManager=MagicMock()))

_spec = importlib.util.spec_from_file_location(
    'gui.widgets.analysis_widget', ANALYSIS_WIDGET_PATH)
_aw_mod = importlib.util.module_from_spec(_spec)
_install('gui.widgets.analysis_widget', _aw_mod)
_spec.loader.exec_module(_aw_mod)


def _get_func_source(func_name, file_path):
    """AST 提取指定函数完整源码段 (精确匹配函数体, 防注释误判)"""
    with open(file_path, encoding='utf-8') as f:
        src = f.read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return ast.get_source_segment(src, node) or ''
    return ''


# ===========================================================================
# 1. _execute_chart_update 行为测试 (analysis_widget.py:724-736)
# ===========================================================================
class TestExecuteChartUpdate:
    """未绑定方法 + 假 self: 执行挂起回调 / 清空 / 异常吞掉 / 无 pending"""

    def _make(self):
        aw = _aw_mod.AnalysisWidget.__new__(_aw_mod.AnalysisWidget)
        aw._pending_chart_update = None
        return aw

    def test_pending_executed_and_cleared(self):
        """L730-731: 取 _pending_chart_update 执行后置 None"""
        aw = self._make()
        calls = []
        aw._pending_chart_update = lambda: calls.append('executed')
        _aw_mod.AnalysisWidget._execute_chart_update(aw)
        assert calls == ['executed'], "挂起回调未被执行"
        assert aw._pending_chart_update is None, "执行后未清空挂起标记"

    def test_exception_swallowed(self):
        """L733-736: 回调异常被捕获, 不传播 (防定时器崩溃)"""
        aw = self._make()

        def boom():
            raise RuntimeError('boom')

        aw._pending_chart_update = boom
        # 不应抛异常
        _aw_mod.AnalysisWidget._execute_chart_update(aw)
        assert aw._pending_chart_update is None

    def test_no_pending_no_crash(self):
        """无挂起回调时幂等返回"""
        aw = self._make()
        _aw_mod.AnalysisWidget._execute_chart_update(aw)  # 不应抛异常


# ===========================================================================
# 2. 构造级配对断言 (analysis_widget.py:142-143 connect 目标必须存在)
# ===========================================================================
class TestChartUpdateTimerPairing:
    """connect(self._execute_chart_update) 与类体 def _execute_chart_update 配对
    —— 缺失即构造后定时器触发 AttributeError (R244-R259 遗留 P1)"""

    def test_connect_target_defined_in_class(self):
        with open(ANALYSIS_WIDGET_PATH, encoding='utf-8') as f:
            src = f.read()
        assert 'def _execute_chart_update' in src, \
            "analysis_widget.py 缺少 _execute_chart_update 定义 (L724-736 修复回退)"
        assert 'connect(self._execute_chart_update)' in src, \
            "analysis_widget.py:143 chart_update_timer connect 目标被修改"


# ===========================================================================
# 3. _on_analyze 挂载源码断言 (main_window_coordinator.py:2841-2866)
# ===========================================================================
class TestOnAnalyzeMountSource:
    """AST 提取 _on_analyze 函数体断言挂载逻辑 (零模块加载, 零污染)"""

    def test_on_analyze_creates_widget_and_window(self):
        body = _get_func_source('_on_analyze', COORDINATOR_PATH)
        assert body, "main_window_coordinator.py 缺少 _on_analyze 方法"
        assert 'AnalysisWidget(service_container=self.service_container)' in body, \
            "L2847 惰性创建 AnalysisWidget 被修改 (service_container 传参缺失)"
        assert 'QMainWindow()' in body, "L2849 独立分析窗口创建被移除"
        assert 'setCentralWidget(self._analysis_widget)' in body, \
            "L2855 widget 挂载到独立窗口被移除"
        assert '_analysis_window.show()' in body, "L2856 窗口显示被移除"

    def test_on_analyze_second_call_refreshes(self):
        body = _get_func_source('_on_analyze', COORDINATOR_PATH)
        assert 'refresh_current_tab()' in body, \
            "L2859 二次调用 refresh_current_tab 分支被移除"
        assert 'not hasattr(self, \'_analysis_widget\')' in body, \
            "L2845 惰性创建守卫被移除 (应避免重复创建)"

    def test_on_analyze_no_degraded_dialog(self):
        """旧降级弹窗 (恒弹"敬请期待") 应已移除"""
        body = _get_func_source('_on_analyze', COORDINATOR_PATH)
        assert 'QMessageBox.information' not in body, \
            "旧降级弹窗逻辑仍在 _on_analyze 中 (R260 应已替换为真实挂载)"


# ===========================================================================
# 4. quick_start.py 参数错位修复断言 (quick_start.py:1238)
# ===========================================================================
class TestQuickStartMount:
    """quick_start.py _launch_data_visualization 中 AnalysisWidget 无参构造"""

    def test_analysis_widget_no_positional_arg(self):
        body = _get_func_source('_launch_data_visualization', QUICK_START_PATH)
        assert body, "quick_start.py 缺少 _launch_data_visualization 方法"
        assert 'widget = AnalysisWidget()' in body, \
            "L1238 应为无参构造 — 原将 QMainWindow 传给 config_manager 位置参数 (参数错位)"
