#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R267-c A1-fix 测试：performance_chart line 分支结构签名修正

背景：R267-c A1 只固定了 xlim 滑动窗口，但 `_update_chart_line_blit` 的
结构签名仍含"各系列数据长度"——累积期（len<max_points）每帧长度 +1 → 签名
每帧变化 → 每帧 `_rebuild_line_artists` 全量重建（plot+annotate+scatter+
legend+tight_layout+invalidate），A1 的增量路径在累积期完全不被执行。

A1-fix：签名仅含系列数（line.set_data 天然支持数据长度增长），
累积期也走 `_update_line_artists` 增量路径，配合 xlim 固定真正消除全量重建。

覆盖（真实 matplotlib Agg + stub Qt 命名空间 exec 动态实例化）：
- 首帧全量重建一次，后续数据增长走增量（rebuild 仅 1 次）
- 数据长度增长正确（line 点数 / xlim 固定 (0, max_points)）
- 多系列稳定时增量（rebuild 不因长度变化重复触发）
- 系列增减触发重建（annotate/scatter 数量需重建）
"""
import ast
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
PERF_CHART = os.path.join(PROJECT_ROOT, 'gui', 'widgets', 'performance', 'components', 'performance_chart.py')


def _extract_class_src(src: str, class_name: str) -> str:
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return ast.get_source_segment(src, node)
    raise AssertionError(f'类 {class_name} 未找到')


def _make_chart(cls, title='测试图表', chart_type='line'):
    """用真实 matplotlib Agg + stub Qt 实例化 ModernPerformanceChart"""
    return cls(title, chart_type)


def _build_ns():
    from collections import defaultdict

    class StubWidget:
        def __init__(self, *a, **kw):
            pass

        def layout(self):
            return MagicMock()

    ns = {
        'QWidget': StubWidget,
        'QVBoxLayout': lambda *a, **kw: MagicMock(),
        'QHBoxLayout': lambda *a, **kw: MagicMock(),
        'QLabel': lambda *a, **kw: MagicMock(),
        'QFont': MagicMock(name='QFont'),
        'Qt': MagicMock(AlignCenter=1),
        'QTimer': MagicMock(),
        'Figure': Figure,
        'FigureCanvas': FigureCanvasAgg,
        'np': np,
        'MATPLOTLIB_AVAILABLE': True,
        '_import_matplotlib': lambda: None,
        '_get_logger': lambda: MagicMock(),
        'defaultdict': defaultdict,
    }
    return ns


def _load_chart_class():
    src = open(PERF_CHART, encoding='utf-8').read()
    class_src = _extract_class_src(src, 'ModernPerformanceChart')
    ns = _build_ns()
    exec(compile(class_src, '<ModernPerformanceChart>', 'exec'), ns)
    return ns['ModernPerformanceChart']


def _force_update(chart):
    """绕过 1s 频率限制强制更新"""
    chart._last_update_time = 0
    chart.update_chart()


def test_accumulation_period_incremental_only():
    """累积期：仅首帧 rebuild，后续数据增长全走增量路径"""
    cls = _load_chart_class()
    chart = _make_chart(cls)
    rebuild_count = {'n': 0}

    orig = chart._rebuild_line_artists

    def counting_rebuild(*a, **kw):
        rebuild_count['n'] += 1
        return orig(*a, **kw)

    chart._rebuild_line_artists = counting_rebuild

    for i in range(1, 6):  # 5 帧累积
        chart.add_data_point('cpu', float(i))
        _force_update(chart)

    assert rebuild_count['n'] == 1, f'累积期应仅首帧重建，实际 {rebuild_count["n"]} 次'
    assert chart._line_sig == (1,)


def test_data_length_growth_correct():
    """长度增长正确：line 点数随数据增长，xlim 固定滑动窗口"""
    cls = _load_chart_class()
    chart = _make_chart(cls)
    for i in range(1, 8):
        chart.add_data_point('cpu', float(i))
        _force_update(chart)

    line = chart._line_artists[0]
    assert len(line.get_xdata()) == 7
    assert len(line.get_ydata()) == 7
    # A1：xlim 固定 (0, max_points)
    xlim = chart.ax.get_xlim()
    assert xlim == (0.0, 100.0), f'xlim 应固定 (0, 100)，实际 {xlim}'


def test_multiseries_stable_incremental():
    """多系列稳定：长度变化不重复重建"""
    cls = _load_chart_class()
    chart = _make_chart(cls)
    rebuild_count = {'n': 0}

    orig = chart._rebuild_line_artists

    def counting_rebuild(*a, **kw):
        rebuild_count['n'] += 1
        return orig(*a, **kw)

    chart._rebuild_line_artists = counting_rebuild

    chart.add_data_point('cpu', 1.0)
    chart.add_data_point('mem', 2.0)
    _force_update(chart)  # 首帧 rebuild (2 系列)
    for i in range(2, 6):
        chart.add_data_point('cpu', float(i))
        chart.add_data_point('mem', float(i) * 2)
        _force_update(chart)

    assert rebuild_count['n'] == 1, f'多系列长度变化不应重建，实际 {rebuild_count["n"]} 次'


def test_series_change_triggers_rebuild():
    """系列增减触发重建（annotate/scatter 数量需重建）"""
    cls = _load_chart_class()
    chart = _make_chart(cls)
    rebuild_count = {'n': 0}

    orig = chart._rebuild_line_artists

    def counting_rebuild(*a, **kw):
        rebuild_count['n'] += 1
        return orig(*a, **kw)

    chart._rebuild_line_artists = counting_rebuild

    chart.add_data_point('a', 1.0)
    _force_update(chart)  # 首帧
    assert rebuild_count['n'] == 1

    chart.add_data_point('b', 2.0)
    _force_update(chart)  # 系列 1→2 → 重建
    assert rebuild_count['n'] == 2

    chart.add_data_point('c', 3.0)
    _force_update(chart)  # 系列 2→3 → 重建
    assert rebuild_count['n'] == 3


def test_signature_contains_series_count_only():
    """静态断言：签名仅含系列数，不含数据长度"""
    src = open(PERF_CHART, encoding='utf-8').read()
    assert 'new_sig = (len(series_snapshot),)' in src
    assert 'tuple(len(data) for _, data in series_snapshot)' not in src


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
