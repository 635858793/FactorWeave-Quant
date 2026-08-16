#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebGPU 渲染器模块（清理版）

历史假实现已按架构决策整体删除：WebGPUContext/VolumeDataProcessor/
GPUResourcePool/WebGPURenderer 及 create_webgpu_renderer/create_optimized_gpu_config
从未真正调用 GPU —— GLSL 只定义不编译、_create_moderngl_fallback 假成功
（把 self.context 置为字符串）、_initialize_opengl 假成功、GPUResourcePool
"顶点缓冲区"实为 numpy 数组、_render_with_gpu 恒回退、_render_moderngl 因
shader_modules 恒空不可达、_render_opengl 直接转 CPU、
_convert_gpu_data_to_matplotlib 逐 quad Python 循环（负优化）。
系统渲染统一走 CPU / fallback（Matplotlib）路径。

本模块仅保留：
- GPUBackend：GPU 后端类型枚举（供配置与状态展示使用）
- GPURendererConfig：GPU 渲染器配置数据类（供外部配置兼容）

作者: FactorWeave-Quant团队
版本: 3.0（清理版）
"""

from dataclasses import dataclass
from enum import Enum


class GPUBackend(Enum):
    """GPU后端类型"""
    WEBGPU = "webgpu"
    OPENGL = "opengl"
    MODERNGL = "moderngl"
    CUDA = "cuda"
    CPU = "cpu"


@dataclass
class GPURendererConfig:
    """GPU渲染器配置"""
    # 后端选择
    backend_type: GPUBackend = GPUBackend.MODERNGL
    preferred_backend: GPUBackend = GPUBackend.MODERNGL
    fallback_to_opengl: bool = True
    fallback_to_cpu: bool = True

    # 性能配置
    max_vertices_per_batch: int = 10000
    enable_vertex_buffer_objects: bool = True
    use_shader_programs: bool = True

    # 数据优化
    enable_data_compression: bool = True
    chunk_processing: bool = True
    chunk_size: int = 5000

    # 内存管理
    gpu_memory_limit_mb: int = 512
    enable_memory_pool: bool = True
    cleanup_threshold: float = 0.8  # 内存使用率超过80%时触发清理

    # 分辨率配置
    default_width: int = 1920
    default_height: int = 1080
