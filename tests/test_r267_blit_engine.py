#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R267 blit 推广测试：BlitEngine 基础设施（core/utils/mpl_blit.py）

覆盖：
- 首帧 render：全量 draw + copy_from_bbox 重建背景，随后 restore_region/blit
- 第二帧：背景已缓存，不重复 draw/copy，仍执行 restore_region + draw_artist + blit
- invalidate 后：重新全量 draw + copy 重建背景
- 异常回退：blit 抛异常 → draw_idle 兜底、背景置空、返回 False
- canvas 为 None：直接返回 False 不抛错
- 隐藏 artist 过滤：get_visible()=False 不执行 draw_artist
- 采样累计：达 sample_every 阈值后重置计数
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock

from core.utils.mpl_blit import BlitEngine


def _make_canvas():
    canvas = MagicMock()
    canvas.figure = MagicMock()
    canvas.figure.bbox = 'figure-bbox'
    return canvas


def _make_artist(visible=True, axes=None):
    artist = MagicMock()
    artist.get_visible.return_value = visible
    artist.axes = axes if axes is not None else MagicMock()
    return artist


def test_first_render_rebuilds_background():
    """首帧：全量 draw + copy_from_bbox 重建背景，随后 blit"""
    canvas = _make_canvas()
    eng = BlitEngine(canvas, log_tag='[T]', sample_every=0)
    artists = [_make_artist()]

    ok = eng.render(artists)

    assert ok is True
    canvas.draw.assert_called_once()
    canvas.copy_from_bbox.assert_called_once_with('figure-bbox')
    canvas.restore_region.assert_called_once()
    canvas.blit.assert_called_once_with('figure-bbox')
    # 背景已缓存
    assert eng._background is not None


def test_second_render_reuses_background():
    """第二帧：背景已缓存，不重复 draw/copy"""
    canvas = _make_canvas()
    eng = BlitEngine(canvas, log_tag='[T]', sample_every=0)
    artist = _make_artist()

    eng.render([artist])
    eng.render([artist])

    assert canvas.draw.call_count == 1
    assert canvas.copy_from_bbox.call_count == 1
    assert canvas.restore_region.call_count == 2
    assert canvas.blit.call_count == 2
    artist.axes.draw_artist.assert_called_with(artist)


def test_invalidate_forces_rebuild():
    """invalidate 后重新全量 draw + copy"""
    canvas = _make_canvas()
    eng = BlitEngine(canvas, log_tag='[T]', sample_every=0)
    artist = _make_artist()

    eng.render([artist])
    eng.invalidate()
    assert eng._background is None
    eng.render([artist])

    assert canvas.draw.call_count == 2
    assert canvas.copy_from_bbox.call_count == 2


def test_failure_fallback_to_draw_idle():
    """blit 异常 → draw_idle 兜底、背景置空、返回 False"""
    canvas = _make_canvas()
    canvas.blit.side_effect = RuntimeError('blit failed')
    eng = BlitEngine(canvas, log_tag='[T]', sample_every=0)

    ok = eng.render([_make_artist()])

    assert ok is False
    canvas.draw_idle.assert_called_once()
    assert eng._background is None


def test_none_canvas_returns_false():
    """canvas 为 None 直接返回 False，不抛错"""
    eng = BlitEngine(None, log_tag='[T]', sample_every=0)
    assert eng.render([_make_artist()]) is False


def test_hidden_artist_skipped():
    """不可见 artist 不执行 draw_artist"""
    canvas = _make_canvas()
    eng = BlitEngine(canvas, log_tag='[T]', sample_every=0)
    hidden = _make_artist(visible=False)

    eng.render([hidden])

    hidden.axes.draw_artist.assert_not_called()


def test_accumulate_resets_at_threshold():
    """采样累计达 sample_every 后重置计数"""
    canvas = _make_canvas()
    eng = BlitEngine(canvas, log_tag='[T]', sample_every=3)
    artist = _make_artist()

    for _ in range(4):
        eng.render([artist])

    assert eng._count == 1  # 4 - 3 = 1
    assert eng._total > 0.0


# ---------------------------------------------------------------------------
# 真实 matplotlib（Agg 后端）冒烟测试：验证 BlitEngine 与真实 API 协作
# ---------------------------------------------------------------------------
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402


def _make_real_canvas():
    fig = Figure(figsize=(4, 3), dpi=80)
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    return fig, canvas, ax


def test_real_line_blit():
    """真实 matplotlib：line 首帧重建 + 更新帧 blit + invalidate 重建"""
    fig, canvas, ax = _make_real_canvas()
    line, = ax.plot([1, 2, 3], [1, 2, 3])
    eng = BlitEngine(canvas, bbox_getter=lambda: ax.bbox, log_tag='[T]', sample_every=0)

    assert eng.render([line]) is True
    assert eng._background is not None

    # 更新帧：背景已缓存
    line.set_ydata([2, 3, 4])
    assert eng.render([line]) is True

    # invalidate 后重建
    eng.invalidate()
    assert eng.render([line]) is True


def test_real_fill_between_blit():
    """真实 matplotlib：fill_between（PolyCollection）+ legend 动态层 blit"""
    fig, canvas, ax = _make_real_canvas()
    pc = ax.fill_between([1, 2, 3], [1, 2, 1], 0, color='red', alpha=0.3)
    line, = ax.plot([1, 2, 3], [1, 2, 3])
    legend = ax.legend()
    eng = BlitEngine(canvas, bbox_getter=lambda: ax.bbox, log_tag='[T]', sample_every=0)

    assert eng.render([pc, line, legend]) is True

    # 更新帧：移除旧 fill + 重建（order_book/monitor 的通用模式）
    pc.remove()
    pc2 = ax.fill_between([1, 2, 3], [2, 1, 2], 0, color='green', alpha=0.3)
    assert eng.render([pc2, line, legend]) is True


def test_real_bar_container_blit():
    """真实 matplotlib：bar 容器（BarContainer）作为动态层 blit"""
    fig, canvas, ax = _make_real_canvas()
    bars = ax.bar([1, 2, 3], [1, 2, 3], width=0.02)
    eng = BlitEngine(canvas, bbox_getter=lambda: ax.bbox, log_tag='[T]', sample_every=0)

    assert eng.render(list(bars)) is True

    # 增量更新柱高（data_quality_monitor 模式）
    for rect, h in zip(bars, [3, 2, 1]):
        rect.set_height(h)
    assert eng.render(list(bars)) is True
