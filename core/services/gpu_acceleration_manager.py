#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GPU加速管理器

提供GPU硬件加速功能的管理和协调，包括：
1. GPU检测和初始化
2. GPU资源管理
3. GPU加速任务调度
4. 性能监控和优化
5. 自动降级处理

作者: FactorWeave-Quant团队
版本: 2.0
"""

import os
import json
import threading
import time
from typing import Dict, Any, List, Optional, Union, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from loguru import logger

# 导入基础服务
from .base_service import BaseService

# 导入GPU相关模块
WEBGPU_AVAILABLE = False
GPU_DETECTOR_CLASS = None
WEBGPU_CONTEXT_CLASS = None
GPU_BACKEND_ENUM = None

try:
    from ..webgpu.enhanced_gpu_detection import GPUDetector, GPUAdapter, PowerPreference, GPUType
    from ..webgpu.webgpu_renderer import WebGPUContext, GPURendererConfig, GPUBackend
    WEBGPU_AVAILABLE = True
    GPU_DETECTOR_CLASS = GPUDetector
    WEBGPU_CONTEXT_CLASS = WebGPUContext
    GPU_BACKEND_ENUM = GPUBackend
except ImportError as e:
    logger.warning(f"WebGPU模块导入失败: {e}")
    WEBGPU_AVAILABLE = False

# 导入配置
try:
    from ..config_service import ConfigService
    CONFIG_SERVICE_AVAILABLE = True
except ImportError:
    CONFIG_SERVICE_AVAILABLE = False
    logger.warning("配置服务不可用，将使用默认配置")


class GPUAccelerationStatus(Enum):
    """GPU加速状态"""
    DISABLED = "disabled"          # 禁用
    INITIALIZING = "initializing"  # 初始化中
    READY = "ready"               # 就绪
    ERROR = "error"               # 错误
    FALLBACK = "fallback"         # 降级模式


@dataclass
class GPUAccelerationConfig:
    """GPU加速配置"""
    enabled: bool = True
    auto_detect: bool = True
    preferred_backend: str = "auto"
    memory_limit_mb: int = 512
    enable_profiling: bool = False
    auto_fallback_on_error: bool = True
    cpu_threads: int = 4
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'GPUAccelerationConfig':
        """从字典创建配置"""
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})
    
    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> 'GPUAccelerationConfig':
        """从文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # 提取gpu_acceleration部分
            if 'gpu_acceleration' in config_dict:
                config_dict = config_dict['gpu_acceleration']
            
            return cls.from_dict(config_dict)
        except Exception as e:
            logger.warning(f"加载GPU配置失败: {e}，使用默认配置")
            return cls()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class GPUInfo:
    """GPU信息"""
    name: str
    vendor: str
    memory_mb: int
    compute_units: int
    is_discrete: bool
    supports_webgpu: bool
    supports_webgl: bool
    driver_version: str = ""
    gpu_type: str = "unknown"
    
    @classmethod
    def from_adapter(cls, adapter) -> 'GPUInfo':
        """从GPUAdapter创建GPUInfo"""
        return cls(
            name=adapter.name,
            vendor=adapter.vendor,
            memory_mb=adapter.memory_mb,
            compute_units=adapter.compute_units,
            is_discrete=adapter.is_discrete,
            supports_webgpu=adapter.supports_webgpu,
            supports_webgl=adapter.supports_webgl,
            driver_version=adapter.driver_version,
            gpu_type=adapter.gpu_type.value if adapter.gpu_type else "unknown"
        )


class GPUAccelerationManager(BaseService):
    """
    GPU加速管理器
    
    负责GPU硬件加速功能的管理和协调，包括：
    - GPU检测和初始化
    - GPU资源管理
    - GPU加速任务调度
    - 性能监控和优化
    - 自动降级处理
    """
    
    def __init__(self, event_bus=None):
        """初始化GPU加速管理器"""
        super().__init__(event_bus)
        
        # 配置和状态
        self._config: Optional[GPUAccelerationConfig] = None
        self._status = GPUAccelerationStatus.DISABLED
        self._gpu_info: List[GPUInfo] = []
        self._active_gpu: Optional[GPUInfo] = None
        self._webgpu_context: Optional[WebGPUContext] = None
        self._gpu_detector: Optional[GPUDetector] = None
        
        # 性能统计
        self._performance_stats = {
            "tasks_processed": 0,
            "gpu_time_used": 0.0,
            "cpu_time_used": 0.0,
            "memory_used_mb": 0,
            "errors": 0
        }
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 配置路径
        self._config_path = Path(__file__).parent.parent.parent / "config" / "gpu_acceleration.json"
        
        logger.info("GPU加速管理器初始化完成")
    
    def initialize(self) -> None:
        """初始化GPU加速管理器"""
        with self._lock:
            if self._initialized:
                logger.warning("GPU加速管理器已初始化")
                return
            
            try:
                self._status = GPUAccelerationStatus.INITIALIZING
                start_time = time.time()
                
                # 加载配置
                self._load_config()
                
                # 检查是否启用GPU加速
                if not self._config.enabled:
                    logger.info("GPU加速已禁用")
                    self._status = GPUAccelerationStatus.DISABLED
                    self._initialized = True
                    self._initialization_time = time.time() - start_time
                    return
                
                # 检测GPU
                if self._config.auto_detect:
                    self._detect_gpu()
                
                # 初始化WebGPU上下文
                if WEBGPU_AVAILABLE and self._gpu_info:
                    self._initialize_webgpu_context()
                
                # 设置活动GPU
                self._select_active_gpu()
                
                # 更新状态
                if self._active_gpu:
                    self._status = GPUAccelerationStatus.READY
                    logger.info(f"GPU加速初始化成功，使用GPU: {self._active_gpu.name}")
                else:
                    self._status = GPUAccelerationStatus.FALLBACK
                    logger.warning("GPU加速初始化失败，使用CPU降级模式")
                
                self._initialized = True
                self._initialization_time = time.time() - start_time
                
                # 发布初始化完成事件
                self._publish_event("gpu_acceleration_initialized", {
                    "status": self._status.value,
                    "gpu_count": len(self._gpu_info),
                    "active_gpu": self._active_gpu.name if self._active_gpu else None,
                    "initialization_time": self._initialization_time
                })
                
            except Exception as e:
                logger.error(f"GPU加速管理器初始化失败: {e}")
                self._status = GPUAccelerationStatus.ERROR
                if self._config and self._config.auto_fallback_on_error:
                    self._status = GPUAccelerationStatus.FALLBACK
                    logger.info("启用自动降级模式")
                self._initialized = True
                self._metrics["error_count"] += 1
                self._metrics["last_error"] = str(e)
    
    def dispose(self) -> None:
        """释放GPU加速管理器资源"""
        with self._lock:
            if self._disposed:
                return
            
            try:
                # 释放WebGPU上下文
                if self._webgpu_context:
                    # WebGPU上下文释放逻辑（如果有的话）
                    self._webgpu_context = None
                
                # 清理资源
                self._gpu_info.clear()
                self._active_gpu = None
                self._gpu_detector = None
                
                self._disposed = True
                self._status = GPUAccelerationStatus.DISABLED
                
                logger.info("GPU加速管理器资源已释放")
                
            except Exception as e:
                logger.error(f"释放GPU加速管理器资源失败: {e}")
    
    def _load_config(self) -> None:
        """加载GPU加速配置"""
        try:
            # 尝试从配置服务加载
            if CONFIG_SERVICE_AVAILABLE:
                config_service = self._event_bus.get_service("ConfigService")
                if config_service:
                    config_dict = config_service.get("gpu_acceleration", {})
                    self._config = GPUAccelerationConfig.from_dict(config_dict)
                    logger.info("从配置服务加载GPU加速配置")
                    return
            
            # 尝试从文件加载
            if self._config_path.exists():
                self._config = GPUAccelerationConfig.from_file(self._config_path)
                logger.info(f"从文件加载GPU加速配置: {self._config_path}")
            else:
                # 使用默认配置
                self._config = GPUAccelerationConfig()
                logger.info("使用默认GPU加速配置")
                
        except Exception as e:
            logger.warning(f"加载GPU加速配置失败: {e}，使用默认配置")
            self._config = GPUAccelerationConfig()
    
    def _detect_gpu(self) -> None:
        """检测GPU"""
        if not WEBGPU_AVAILABLE or GPU_DETECTOR_CLASS is None:
            logger.warning("WebGPU模块不可用，跳过GPU检测")
            return
        
        try:
            self._gpu_detector = GPU_DETECTOR_CLASS()
            
            # 获取GPU适配器
            adapters = self._gpu_detector.get_adapters()
            
            # 转换为GPUInfo
            self._gpu_info = [GPUInfo.from_adapter(adapter) for adapter in adapters]
            
            logger.info(f"检测到 {len(self._gpu_info)} 个GPU:")
            for gpu in self._gpu_info:
                logger.info(f"  - {gpu.name} ({gpu.vendor}, {gpu.memory_mb}MB, 离散显卡: {gpu.is_discrete})")
                
        except Exception as e:
            logger.error(f"GPU检测失败: {e}")
            self._gpu_info = []
    
    def _initialize_webgpu_context(self) -> None:
        """初始化WebGPU上下文"""
        if not WEBGPU_AVAILABLE or not self._gpu_info:
            return
        
        try:
            # 创建渲染器配置
            backend_map = {
                "auto": GPUBackend.MODERNGL,
                "opengl": GPUBackend.OPENGL,
                "moderngl": GPUBackend.MODERNGL,
                "cuda": GPUBackend.CUDA,
                "cpu": GPUBackend.CPU
            }
            
            backend = backend_map.get(
                self._config.preferred_backend.lower(), 
                GPUBackend.MODERNGL
            )
            
            renderer_config = GPURendererConfig(
                backend_type=backend,
                preferred_backend=backend,
                fallback_to_opengl=self._config.auto_fallback_on_error,
                fallback_to_cpu=self._config.auto_fallback_on_error,
                gpu_memory_limit_mb=self._config.memory_limit_mb
            )
            
            # 创建WebGPU上下文
            self._webgpu_context = WebGPUContext(renderer_config)
            
            # 初始化上下文
            if self._webgpu_context.initialize():
                logger.info(f"WebGPU上下文初始化成功，后端: {backend.value}")
            else:
                logger.warning("WebGPU上下文初始化失败")
                self._webgpu_context = None
                
        except Exception as e:
            logger.error(f"WebGPU上下文初始化异常: {e}")
            self._webgpu_context = None
    
    def _select_active_gpu(self) -> None:
        """选择活动GPU"""
        if not self._gpu_info:
            return
        
        # 优先选择离散显卡
        discrete_gpus = [gpu for gpu in self._gpu_info if gpu.is_discrete]
        
        if discrete_gpus:
            # 选择显存最大的离散显卡
            self._active_gpu = max(discrete_gpus, key=lambda gpu: gpu.memory_mb)
        else:
            # 选择显存最大的集成显卡
            self._active_gpu = max(self._gpu_info, key=lambda gpu: gpu.memory_mb)
        
        logger.info(f"选择GPU: {self._active_gpu.name}")
    
    def _publish_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """发布事件"""
        try:
            if self._event_bus:
                self._event_bus.publish(event_name, **data)
        except Exception as e:
            logger.warning(f"发布事件失败: {e}")
    
    # 公共接口
    
    def get_status(self) -> GPUAccelerationStatus:
        """获取GPU加速状态"""
        return self._status
    
    def get_gpu_info(self) -> List[GPUInfo]:
        """获取GPU信息列表"""
        return self._gpu_info.copy()
    
    def get_active_gpu(self) -> Optional[GPUInfo]:
        """获取活动GPU信息"""
        return self._active_gpu
    
    def is_gpu_available(self) -> bool:
        """检查GPU是否可用"""
        return self._status == GPUAccelerationStatus.READY and self._active_gpu is not None
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        with self._lock:
            return self._performance_stats.copy()
    
    def execute_gpu_task(self, task_func, *args, **kwargs) -> Any:
        """执行GPU加速任务"""
        if not self.is_gpu_available():
            logger.warning("GPU不可用，使用CPU执行任务")
            return task_func(*args, **kwargs)
        
        try:
            start_time = time.time()
            
            # 执行任务
            result = task_func(*args, **kwargs)
            
            # 更新统计
            execution_time = time.time() - start_time
            with self._lock:
                self._performance_stats["tasks_processed"] += 1
                self._performance_stats["gpu_time_used"] += execution_time
            
            return result
            
        except Exception as e:
            logger.error(f"GPU任务执行失败: {e}")
            with self._lock:
                self._performance_stats["errors"] += 1
            
            # 如果启用自动降级，使用CPU重试
            if self._config.auto_fallback_on_error:
                logger.info("使用CPU降级执行任务")
                return task_func(*args, **kwargs)
            else:
                raise
    
    def update_config(self, config: Union[Dict[str, Any], GPUAccelerationConfig]) -> None:
        """更新配置"""
        with self._lock:
            if isinstance(config, dict):
                self._config = GPUAccelerationConfig.from_dict(config)
            else:
                self._config = config
            
            # 如果已初始化，重新初始化
            if self._initialized:
                self.dispose()
                self.initialize()
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        with self._lock:
            return {
                "status": self._status.value,
                "initialized": self._initialized,
                "gpu_count": len(self._gpu_info),
                "active_gpu": self._active_gpu.name if self._active_gpu else None,
                "webgpu_context_available": self._webgpu_context is not None,
                "performance_stats": self._performance_stats,
                "config": self._config.to_dict() if self._config else None
            }