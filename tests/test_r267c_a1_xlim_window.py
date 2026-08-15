#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R267-c A1 优化测试：performance_chart line 分支 xlim 固定滑动窗口

背景：system_monitor_tab.py L435 monitoring_timer.start(1000) 每秒驱动
resource_chart.update_chart()（L631/633 add_data_point → L638 update_chart）。
原实现 _update_line_artists 在数据累积期（len<max_points=100）每帧
relim+autoscale_view 使 xlim 右移 → _blit.invalidate() 全画布重建，blit 形同虚设。

A1 修复：xlim 固定为 (0, max_points) 滑动窗口（满窗后 add_data_point 裁剪至
max_points，窗口恒为最新 max_points 个点），仅 ylim 变化才重建背景。

覆盖：
- _update_line_artists 不再比较 xlim（累积期不再因 xlim 变化 invalidate）
- _update_line_artists 固定 xlim 为 (0, max_points)
- _rebuild_line_artists 首帧同样固定 xlim（两路径窗口一致）
- ylim 变化检测保留（数值波动时仍需重建刻度）
"""
import ast
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PERF_CHART = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'performance', 'components', 'performance_chart.py')


def _read_source() -> str:
    with open(PERF_CHART, encoding='utf-8') as f:
        return f.read()


def _extract_method_src(src: str, method_name: str) -> str:
    """AST 提取指定方法的源码文本（顶层类内首个匹配）"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f'方法 {method_name} 未找到')


def test_update_line_artists_fixed_xlim():
    """增量更新：xlim 固定 (0, max_points)，不再比较 old_xlim"""
    src = _read_source()
    m = _extract_method_src(src, '_update_line_artists')
    assert 'set_xlim(0, self.max_points)' in m, '必须固定 xlim 为滑动窗口'
    assert 'old_xlim' not in m, '不得再因 xlim 变化 invalidate'
    assert 'old_ylim' in m, 'ylim 变化检测必须保留'


def test_update_line_artists_ylim_invalidate_only():
    """增量更新：仅 ylim 变化时 invalidate"""
    src = _read_source()
    m = _extract_method_src(src, '_update_line_artists')
    assert "if old_ylim != self.ax.get_ylim():" in m
    assert '_blit.invalidate()' in m


def test_rebuild_line_artists_fixed_xlim():
    """全量重建：首帧同样固定 xlim，与增量路径窗口一致"""
    src = _read_source()
    m = _extract_method_src(src, '_rebuild_line_artists')
    assert 'set_xlim(0, self.max_points)' in m, '重建路径也必须固定 xlim'


def test_max_points_consistent_window():
    """满窗一致性：add_data_point 裁剪至 max_points，xlim 窗口与数据长度对齐"""
    src = _read_source()
    assert 'self.max_points' in src
    assert 'len(self.data_history[series_name]) > self.max_points:' in src
    assert '.pop(0)' in src


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
