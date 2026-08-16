#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292 测试：A 级死代码清理回归

背景（价值分析已确认）：
- optimization/chart_renderer.py 的渐进式渲染链 / 传统渲染链 / 模块级便捷函数
  全部无外部业务与测试调用者（互为自闭环），系统存在同等且更优替代
  （render_candlesticks / render_volume / render_line + chart_widget 渲染链路）。
- core/services/unified_data_manager.py 的 _store_to_duckdb 无业务调用者，
  替代 _persist_kdata_to_duckdb 更优（asset_manager 统一管理、data_source 溯源）。

验证点：
① 被删符号不再存在于 ChartRenderer / UnifiedDataManager（hasattr 为 False）
② 模块级 render_chart / render_progressive 已移除且不在 __all__ 中
③ 核心渲染能力回归：render_candlesticks / render_volume / render_line 正常
④ 生命周期契约（start/stop/_worker_loop/_process_render_task/_update_render_stats/
   cancel_low_priority_tasks 与 get_chart_renderer 等模块级工厂）保留
"""
import os
import sys

import numpy as np
import pandas as pd
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

import optimization.chart_renderer as cr_mod  # noqa: E402
from optimization.chart_renderer import ChartRenderer  # noqa: E402
from core.services.unified_data_manager import UnifiedDataManager  # noqa: E402


# ==================== ① 已删除死代码符号断言 ====================

class TestDeadCodeRemoved:
    """A 级死代码清理后，以下符号必须不存在"""

    def test_unified_data_manager_no_store_to_duckdb(self):
        """_store_to_duckdb 已删除（替代 _persist_kdata_to_duckdb）"""
        assert not hasattr(UnifiedDataManager, '_store_to_duckdb')

    def test_chart_renderer_no_progressive_chain(self):
        """渐进式渲染链全部删除"""
        assert not hasattr(ChartRenderer, 'render_chart_progressive')
        assert not hasattr(ChartRenderer, '_render_full_chart')
        assert not hasattr(ChartRenderer, '_render_chart_stage')
        assert not hasattr(ChartRenderer, '_render_kline')
        assert not hasattr(ChartRenderer, '_render_volume')
        assert not hasattr(ChartRenderer, '_render_indicators')
        assert not hasattr(ChartRenderer, '_render_decorations')

    def test_chart_renderer_no_legacy_render_chain(self):
        """传统渲染链全部删除"""
        assert not hasattr(ChartRenderer, 'render')
        assert not hasattr(ChartRenderer, 'render_with_throttling')
        assert not hasattr(ChartRenderer, '_process_throttled_update')
        assert not hasattr(ChartRenderer, '_execute_render')
        assert not hasattr(ChartRenderer, '_do_render_prioritized')
        assert not hasattr(ChartRenderer, '_render_indicators_by_priority')
        assert not hasattr(ChartRenderer, '_get_indicator_priority')
        assert not hasattr(ChartRenderer, '_get_indicator_color')
        assert not hasattr(ChartRenderer, '_finalize_render')
        assert not hasattr(ChartRenderer, 'get_render_stats')
        assert not hasattr(ChartRenderer, 'clear_render_queue')
        assert not hasattr(ChartRenderer, '_save_state')
        assert not hasattr(ChartRenderer, '_restore_state')
        assert not hasattr(ChartRenderer, 'set_throttle_interval')
        assert not hasattr(ChartRenderer, 'render_with_priority')
        assert not hasattr(ChartRenderer, '_cancel_lower_priority_tasks')
        assert not hasattr(ChartRenderer, 'get_render_status')
        assert not hasattr(ChartRenderer, 'clear_queue')
        assert not hasattr(ChartRenderer, 'setup_figure')

    def test_module_level_functions_removed(self):
        """模块级 render_chart / render_progressive 已移除且不在 __all__"""
        assert not hasattr(cr_mod, 'render_chart')
        assert not hasattr(cr_mod, 'render_progressive')
        assert 'render_chart' not in cr_mod.__all__
        assert 'render_progressive' not in cr_mod.__all__


# ==================== ③ 核心能力回归 ====================

STYLE = {
    'up_color': '#e74c3c', 'down_color': '#27ae60',
    'limit_up_color': '#ff9800', 'limit_down_color': '#ab47bc',
    'volume_up_color': '#e74c3c', 'volume_down_color': '#27ae60', 'alpha': 1.0,
}


def make_kdata(n: int = 30, symbol: str = '600519') -> pd.DataFrame:
    """构造主板 K 线 DataFrame"""
    rng = np.random.default_rng(42)
    close = np.cumsum(rng.standard_normal(n)) + 100
    return pd.DataFrame({
        'symbol': [symbol] * n,
        'open': close + rng.standard_normal(n) * 0.5,
        'high': np.maximum(close, close + 1) + rng.random(n),
        'low': np.minimum(close, close - 1) - rng.random(n),
        'close': close,
        'volume': rng.integers(1000, 10000, n),
        'datetime': pd.date_range('2024-01-01', periods=n, freq='D'),
    })


def _make_renderer():
    """构造 ChartRenderer 轻量实例（__new__ 绕过 __init__，与
    test_r292_highvalue_render_limit.py 同款构造方式）"""
    r = ChartRenderer.__new__(ChartRenderer)
    r._view_range = None
    r._downsampling_threshold = 2000
    r.render_error = MagicMock()
    r.render_progress = MagicMock()
    r.render_complete = MagicMock()
    return r


class TestCoreRenderRegression:
    """核心渲染能力回归：render_candlesticks / render_volume / render_line 正常"""

    def test_render_candlesticks_ok(self):
        r = _make_renderer()
        ax = MagicMock()
        r.render_candlesticks(ax, make_kdata(), STYLE,
                              np.arange(30), use_datetime_axis=False)
        assert ax.add_collection.called

    def test_render_volume_ok(self):
        r = _make_renderer()
        ax = MagicMock()
        r.render_volume(ax, make_kdata(), STYLE,
                        np.arange(30), use_datetime_axis=False)
        assert ax.add_collection.called

    def test_render_line_ok(self):
        r = _make_renderer()
        ax = MagicMock()
        df = make_kdata()
        r.render_line(ax, df['close'], {'color': '#1976d2', 'label': 'MA'})
        assert ax.plot.called


# ==================== ④ 生命周期契约保留 ====================

class TestLifecycleContractKept:
    """保留方法不得误删（生命周期契约 / gui 兼容调用）"""

    def test_renderer_lifecycle_methods_kept(self):
        assert hasattr(ChartRenderer, 'start')
        assert hasattr(ChartRenderer, 'stop')
        assert hasattr(ChartRenderer, '_worker_loop')
        assert hasattr(ChartRenderer, '_process_render_task')
        assert hasattr(ChartRenderer, '_update_render_stats')
        # chart_widget.py L901-902 经 hasattr 调用，必须保留
        assert hasattr(ChartRenderer, 'cancel_low_priority_tasks')

    def test_core_render_methods_kept(self):
        # chart_widget.py / rendering_mixin.py / indicator_mixin.py /
        # webgpu_chart_renderer.py 的真实调用点
        assert hasattr(ChartRenderer, 'render_candlesticks')
        assert hasattr(ChartRenderer, '_render_candlesticks_efficient')
        assert hasattr(ChartRenderer, 'render_volume')
        assert hasattr(ChartRenderer, '_render_volume_vectorized')
        assert hasattr(ChartRenderer, 'render_line')
        assert hasattr(ChartRenderer, '_render_line_efficient')

    def test_module_factories_kept(self):
        assert hasattr(cr_mod, 'get_chart_renderer')
        assert hasattr(cr_mod, 'initialize_chart_renderer')
        assert hasattr(cr_mod, 'shutdown_chart_renderer')
