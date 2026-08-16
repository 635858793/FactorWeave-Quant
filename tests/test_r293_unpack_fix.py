#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
R293 修复测试：ChunkRenderer._create_render_chunk 对 aggregate_chunk 的错误双值解包

背景（主智能体交叉验证，带行号）：
- core/advanced_optimization/performance/virtualization.py L336-370
  DataAggregator.aggregate_chunk() 返回单值 np.ndarray（L341 切片 / L350 / L366 /
  L370 均单值返回）。
- L531-532 ChunkRenderer._create_render_chunk 内错误地解包为 2 值：
    aggregated_data, actual_quality = self.aggregator.aggregate_chunk(...)
  当聚合结果长度 >=3 时抛 "too many values to unpack (expected 2)"（被 L549 的
  try/except 吞掉后返回 None，chunk_id=0 必现）；长度 ==2 时静默拆成两个标量，
  后续 RenderChunk 构造 len(标量) 抛 TypeError。
- L412 adaptive_aggregate 内为正确单值接收（对照）。
- L535-545 RenderChunk 构造只用 aggregated_data，解包出的 actual_quality 从未使用。

覆盖：
① quality_level=1（默认）路径：_create_render_chunk 返回非 None，data_points 为
   np.ndarray 且长度正确
② quality_level>1 路径（monkeypatch _get_memory_usage=0.9）：聚合不抛异常，返回数组
③ 基线契约：aggregate_chunk 恒返回单值 np.ndarray
"""
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from core.advanced_optimization.performance.virtualization import (
    ChunkRenderer, DataAggregator, RenderChunk, VirtualizationConfig,
)


def _make_renderer():
    """构造 ChunkRenderer（config=VirtualizationConfig()、aggregator=DataAggregator(config)）"""
    config = VirtualizationConfig()
    return ChunkRenderer(config, DataAggregator(config))


class TestCreateRenderChunk:
    """① quality_level=1（默认）路径"""

    def test_returns_chunk_with_aggregated_data(self):
        """data 长度>=3，_create_render_chunk 返回非 None RenderChunk，data_points 长度正确"""
        renderer = _make_renderer()
        data = np.arange(50)

        chunk = renderer._create_render_chunk(0, data, 0, 10)

        # 修复前：双值解包抛 "too many values to unpack" 被 L549 捕获 → 返回 None
        assert chunk is not None, '_create_render_chunk 返回 None（双值解包异常被吞）'
        assert isinstance(chunk, RenderChunk)
        assert isinstance(chunk.data_points, np.ndarray), type(chunk.data_points)
        assert len(chunk.data_points) == 10
        np.testing.assert_array_equal(chunk.data_points, data[0:10])

    def test_returns_chunk_with_2d_data(self):
        """2D 输入 (50,1) 同样不抛异常，data_points 为 ndarray 且形状正确"""
        renderer = _make_renderer()
        data = np.arange(50).reshape(50, 1)

        chunk = renderer._create_render_chunk(0, data, 0, 10)

        assert chunk is not None
        assert isinstance(chunk.data_points, np.ndarray)
        assert chunk.data_points.shape == (10, 1)

    def test_request_chunk_path(self):
        """经 request_chunk（可见块）整链路返回非 None"""
        from PyQt5.QtCore import QRectF

        renderer = _make_renderer()
        data = np.arange(50)

        chunk = renderer.request_chunk(0, data, QRectF(0, 0, 200, 2000))

        assert chunk is not None
        assert isinstance(chunk.data_points, np.ndarray)
        # end_idx = min(len(data), (chunk_id+1)*chunk_size + overlap) = min(50, 1100) = 50
        assert len(chunk.data_points) == len(data)


class TestCreateRenderChunkHighQuality:
    """② quality_level>1（内存压力）路径"""

    def test_high_quality_aggregation_no_error(self, monkeypatch):
        """monkeypatch _get_memory_usage=0.9 → quality_level=8，聚合不抛异常且返回数组"""
        renderer = _make_renderer()
        monkeypatch.setattr(renderer, '_get_memory_usage', lambda: 0.9)
        # 0.9 > cleanup_threshold(0.8) → quality_level = min(8, int(0.9*10)) = 8
        data = np.arange(100)

        chunk = renderer._create_render_chunk(0, data, 0, 30)

        assert chunk is not None, '_create_render_chunk 返回 None（quality_level>1 聚合路径异常被吞）'
        assert isinstance(chunk.data_points, np.ndarray), type(chunk.data_points)
        assert len(chunk.data_points) > 0


class TestAggregateChunkContract:
    """③ 基线契约：aggregate_chunk 恒返回单值 np.ndarray"""

    def test_returns_single_ndarray_quality1(self):
        aggregator = DataAggregator(VirtualizationConfig())
        data = np.arange(50)

        result = aggregator.aggregate_chunk(data, 0, 10, quality_level=1)

        # 单值返回：不是 tuple，不能双值解包
        assert isinstance(result, np.ndarray), type(result)
        assert len(result) == 10

    def test_returns_single_ndarray_quality8(self):
        aggregator = DataAggregator(VirtualizationConfig())
        data = np.arange(100)

        result = aggregator.aggregate_chunk(data, 0, 30, quality_level=8)

        assert isinstance(result, np.ndarray), type(result)
        assert len(result) > 0
