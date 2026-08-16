#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R292 清理测试：WebGPU 假实现删除后的基线断言

背景：按已确认的架构决策删除 core/webgpu/webgpu_renderer.py 中的假 GPU 实现
（WebGPUContext/VolumeDataProcessor/GPUResourcePool/WebGPURenderer 及
create_webgpu_renderer/create_optimized_gpu_config 两个工厂函数），渲染统一走
CPU / fallback（Matplotlib）路径。本文件提供删除后的基线保障：
- 被删符号不再存在（import 失败 / 包属性缺失）
- 保留符号（GPUBackend/GPURendererConfig）仍可用
- WebGPUChartRenderer 降级后（enable_webgpu=False → 走父类 CPU 向量化路径）
  render_candlesticks/render_volume/render_line 仍正常（四色 + 日期轴正确性
  由既有 R292 测试覆盖，此处验证调用不抛异常且输出到画布）
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock

import matplotlib.colors as mcolors
from matplotlib.collections import PolyCollection

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

STYLE = {
    'up_color': '#e74c3c', 'down_color': '#27ae60',
    'limit_up_color': '#FF9800', 'limit_down_color': '#AB47BC',
    'volume_up_color': '#e74c3c', 'volume_down_color': '#27ae60', 'alpha': 1.0,
}

# 创业板(300750, 20%)：row0 阳线红 / row1 涨停橙(11.00x1.2=13.20) /
# row2 跌停紫(13.20x0.8=10.56) / row3 涨停橙(10.56x1.2=12.67) / row4 阴线绿
KLINE_DF = pd.DataFrame({
    'symbol': ['300750'] * 5,
    'open': [10.0, 11.0, 13.2, 10.56, 13.0],
    'high': [11.0, 13.2, 13.2, 12.67, 13.1],
    'low': [9.9, 11.0, 10.56, 11.5, 11.9],
    'close': [11.0, 13.2, 10.56, 12.67, 12.0],
    'volume': [1000] * 5,
})


class TestFakeWebGpuRemoved:
    """被删假实现不再存在（import 必须失败）"""

    def test_webgpu_renderer_class_removed(self):
        with pytest.raises(ImportError):
            from core.webgpu.webgpu_renderer import WebGPURenderer  # noqa: F401

    def test_webgpu_context_class_removed(self):
        with pytest.raises(ImportError):
            from core.webgpu.webgpu_renderer import WebGPUContext  # noqa: F401

    def test_gpu_resource_pool_class_removed(self):
        with pytest.raises(ImportError):
            from core.webgpu.webgpu_renderer import GPUResourcePool  # noqa: F401

    def test_volume_data_processor_class_removed(self):
        with pytest.raises(ImportError):
            from core.webgpu.webgpu_renderer import VolumeDataProcessor  # noqa: F401

    def test_factory_functions_removed(self):
        with pytest.raises(ImportError):
            from core.webgpu.webgpu_renderer import create_webgpu_renderer  # noqa: F401
        with pytest.raises(ImportError):
            from core.webgpu.webgpu_renderer import create_optimized_gpu_config  # noqa: F401

    def test_package_exports_narrowed(self):
        import core.webgpu as wg
        for name in ('WebGPURenderer', 'OptimizedWebGPURenderer', 'WebGPUContext',
                     'GPUResourcePool', 'create_webgpu_renderer',
                     'create_optimized_gpu_config'):
            assert not hasattr(wg, name), f'core.webgpu 不应再导出 {name}'


class TestKeptSymbols:
    """保留符号仍可用"""

    def test_gpu_backend_enum_kept(self):
        from core.webgpu.webgpu_renderer import GPUBackend
        assert GPUBackend.WEBGPU.value == 'webgpu'
        assert GPUBackend.CPU.value == 'cpu'
        # 包级导入路径同样可用
        from core.webgpu import GPUBackend as PkgGPUBackend
        assert PkgGPUBackend is GPUBackend

    def test_gpu_renderer_config_kept(self):
        from core.webgpu.webgpu_renderer import GPURendererConfig
        cfg = GPURendererConfig()
        assert cfg.preferred_backend.value == 'moderngl'
        assert cfg.fallback_to_cpu is True


def _make_degraded_renderer():
    """构造降级 WebGPUChartRenderer（enable_webgpu=False → 直接走父类 CPU 路径）"""
    from optimization.webgpu_chart_renderer import WebGPUChartRenderer
    return WebGPUChartRenderer(max_workers=2, enable_progressive=False, enable_webgpu=False)


class TestWebGPUChartRendererDegraded:
    """WebGPUChartRenderer 降级路径下三个覆写方法仍正常"""

    def test_should_use_webgpu_false(self):
        r = _make_degraded_renderer()
        assert r._should_use_webgpu() is False

    def test_render_candlesticks_four_colors(self):
        r = _make_degraded_renderer()
        ax = MagicMock()
        r.render_candlesticks(ax, KLINE_DF, STYLE, np.arange(5), use_datetime_axis=False)
        edges = set()
        for call in ax.add_collection.call_args_list:
            coll = call[0][0]
            if isinstance(coll, PolyCollection):
                for c in coll.get_edgecolor():
                    edges.add(mcolors.to_hex(tuple(np.round(c[:3], 3))))
        assert edges == {'#27ae60', '#ab47bc', '#e74c3c', '#ff9800'}, edges

    def test_render_volume(self):
        r = _make_degraded_renderer()
        ax = MagicMock()
        r.render_volume(ax, KLINE_DF, STYLE, np.arange(5), use_datetime_axis=False)
        assert ax.add_collection.called

    def test_render_line(self):
        r = _make_degraded_renderer()
        ax = MagicMock()
        r.render_line(ax, KLINE_DF['close'], STYLE, np.arange(5), use_datetime_axis=False)
        assert ax.plot.called
