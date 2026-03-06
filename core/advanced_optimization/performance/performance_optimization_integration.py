#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
性能监控与优化集成模块
将性能监控数据反馈到自适应渲染算法，实现智能的性能优化

作者: Hikyuu UI系统
版本: 1.0
"""

import time
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import asyncio
import numpy as np
from loguru import logger

from .unified_performance_coordinator import (
    UnifiedPerformanceCoordinator, UnifiedPerformanceMetrics,
    PerformanceAlert, AlertSeverity, PerformanceCategory
)
from .advanced_performance_analytics import (
    AdvancedPerformanceAnalytics
)
from .enhanced_realtime_monitor import (
    EnhancedRealtimeMonitor, AnomalyDetectionResult
)

class RenderOptimizationLevel(Enum):
    """渲染优化级别"""
    CONSERVATIVE = "conservative"  # 保守模式 - 保持高质量
    BALANCED = "balanced"          # 平衡模式 - 质量和性能的平衡
    PERFORMANCE = "performance"    # 性能优先 - 提升性能
    AGGRESSIVE = "aggressive"      # 激进模式 - 最大化性能

class RenderQuality(Enum):
    """渲染质量级别"""
    HIGH = "high"      # 高质量
    MEDIUM = "medium"  # 中等质量
    LOW = "low"       # 低质量
    MINIMAL = "minimal" # 最小化质量

@dataclass
class RenderOptimizationConfig:
    """渲染优化配置"""
    # 基础配置
    optimization_level: RenderOptimizationLevel = RenderOptimizationLevel.BALANCED
    target_fps: int = 60  # 目标帧率
    
    # 质量控制
    high_quality_threshold: float = 0.8  # 高质量阈值
    medium_quality_threshold: float = 0.6  # 中等质量阈值
    
    # 响应速度
    adjustment_cooldown: float = 5.0  # 调整冷却时间（秒）
    rapid_response_threshold: float = 0.3  # 快速响应阈值（秒）
    
    # 性能目标
    gpu_utilization_target: float = 0.7  # GPU利用率目标
    memory_utilization_target: float = 0.8  # 内存利用率目标
    
    # 适应性配置
    enable_adaptive_quality: bool = True
    enable_predictive_optimization: bool = True
    enable_anomaly_response: bool = True

@dataclass
class RenderParameters:
    """渲染参数"""
    # 基础参数
    fps_limit: int = 60
    render_quality: RenderQuality = RenderQuality.MEDIUM
    
    # 图形参数
    antialiasing: bool = True
    texture_quality: int = 2  # 0-4 级别
    shadow_quality: int = 2   # 0-4 级别
    lighting_quality: int = 2 # 0-4 级别
    
    # 数据参数
    max_data_points: int = 10000
    sampling_rate: float = 1.0
    update_frequency: float = 1.0  # 更新频率
    
    # 内存参数
    max_memory_usage_mb: int = 512
    cache_size_mb: int = 256
    
    # 线程参数
    render_threads: int = 4
    worker_threads: int = 2

@dataclass
class OptimizationFeedback:
    """优化反馈信息"""
    timestamp: float
    optimization_level: RenderOptimizationLevel
    current_parameters: RenderParameters
    performance_metrics: Dict[str, float]
    adjustments_made: List[str]
    expected_improvement: float

class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, coordinator: UnifiedPerformanceCoordinator,
                 analytics: AdvancedPerformanceAnalytics,
                 config: Optional[RenderOptimizationConfig] = None):
        self.coordinator = coordinator
        self.analytics = analytics
        self.config = config or RenderOptimizationConfig()
        
        # 当前渲染参数
        self.current_parameters = RenderParameters()
        
        # 优化状态
        self.is_optimizing = False
        self.last_adjustment_time = 0.0
        self.adjustment_history: List[OptimizationFeedback] = []
        
        # 性能阈值和触发条件
        self.performance_thresholds = {
            'critical_gpu_usage': 0.95,
            'high_gpu_usage': 0.85,
            'critical_memory_usage': 0.9,
            'high_memory_usage': 0.8,
            'low_fps': 30.0,
            'high_latency': 100.0
        }
        
        # 回调函数
        self.optimization_callbacks: List[Callable[[RenderParameters], None]] = []
        self.adjustment_callbacks: List[Callable[[OptimizationFeedback], None]] = []
        
        # 统计信息
        self.adjustment_stats = {
            'total_adjustments': 0,
            'successful_adjustments': 0,
            'performance_improvements': 0,
            'last_adjustment_time': 0.0
        }
        
        logger.info("性能优化器初始化完成")
    
    def start_optimization(self) -> bool:
        """开始性能优化"""
        try:
            if self.is_optimizing:
                logger.warning("性能优化已在运行")
                return True
            
            self.is_optimizing = True
            
            # 启动优化循环
            optimization_thread = threading.Thread(target=self._optimization_loop, daemon=True)
            optimization_thread.start()
            
            logger.info("性能优化已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动性能优化失败: {e}")
            return False
    
    def stop_optimization(self):
        """停止性能优化"""
        try:
            self.is_optimizing = False
            logger.info("性能优化已停止")
            
        except Exception as e:
            logger.error(f"停止性能优化失败: {e}")
    
    def _optimization_loop(self):
        """优化循环"""
        while self.is_optimizing:
            try:
                # 获取当前性能数据
                current_metrics = self.coordinator.get_current_metrics()
                
                # 基于当前性能指标进行优化
                self._optimize_based_on_current_metrics(current_metrics)
                
                time.sleep(2.0)  # 每2秒检查一次
                
            except Exception as e:
                logger.error(f"优化循环异常: {e}")
                time.sleep(2.0)
    
    def _optimize_based_on_current_metrics(self, current_metrics):
        """基于当前性能指标优化 - 简化版本"""
        try:
            current_time = time.time()
            
            # 检查是否需要调整
            if current_time - self.last_adjustment_time < self.config.adjustment_cooldown:
                return
            
            # 处理不同类型的返回值
            metrics_dict = {}
            if isinstance(current_metrics, list) and len(current_metrics) > 0:
                # 从列表中提取最新的指标字典
                latest_metric = current_metrics[-1] if isinstance(current_metrics[-1], dict) else {}
                metrics_dict = latest_metric if isinstance(latest_metric, dict) else {}
            elif isinstance(current_metrics, dict):
                metrics_dict = current_metrics
            
            # 简化的性能检查 - 只检查严重性能问题
            critical_issues = []
            
            # GPU监控功能已移除
            
            # 检查内存使用率
            memory_util = metrics_dict.get('memory_usage_percent', 0) or metrics_dict.get('system_memory_usage_percent', 0) or 0
            if memory_util > 90:  # 极度严重的内存使用率
                critical_issues.append("内存使用率过高")
            
            # 检查FPS
            rendering_fps = metrics_dict.get('rendering_fps', 60) or metrics_dict.get('fps', 60)
            if rendering_fps > 0 and rendering_fps < 20:  # 严重低FPS
                critical_issues.append("FPS严重过低")
            
            # 检查延迟
            rendering_latency = metrics_dict.get('rendering_latency_ms', 0) or metrics_dict.get('latency_ms', 0)
            if rendering_latency > 200:  # 严重高延迟
                critical_issues.append("渲染延迟过高")
            
            # 如果发现严重问题，执行简单调整
            if critical_issues:
                adjustments_made = [f"检测到严重性能问题: {'; '.join(critical_issues)}"]
                expected_improvement = 0.1
                
                # 执行最基本的参数调整
                self.current_parameters.render_quality = RenderQuality.LOW
                self.current_parameters.fps_limit = min(30, self.current_parameters.fps_limit)
                
                self._apply_optimization_adjustments(adjustments_made, expected_improvement, {})
                logger.info(f"执行了紧急性能调整: {adjustments_made[0]}")
                
        except Exception as e:
            logger.error(f"基于当前指标优化失败: {e}")
    

    
    

    

    

    
    def _apply_optimization_adjustments(self, adjustments: List[str], expected_improvement: float, 
                                      analysis_result: Dict[str, Any]):
        """应用优化调整"""
        try:
            # 获取性能指标
            performance_metrics = {}
            current_metrics = self.coordinator.get_current_metrics()
            
            # 处理不同类型的返回值
            metrics_dict = {}
            if isinstance(current_metrics, list) and len(current_metrics) > 0:
                latest_metric = current_metrics[-1] if isinstance(current_metrics[-1], dict) else {}
                metrics_dict = latest_metric if isinstance(latest_metric, dict) else {}
            elif isinstance(current_metrics, dict):
                metrics_dict = current_metrics
            
            # GPU监控功能已移除
            memory_util = metrics_dict.get('memory_usage_percent', 0) or metrics_dict.get('system_memory_usage_percent', 0) or 0
            if memory_util:
                performance_metrics['memory_utilization'] = memory_util / 100.0 if memory_util > 1 else memory_util
            
            performance_metrics['fps'] = metrics_dict.get('rendering_fps', 60) or metrics_dict.get('fps', 60)
            performance_metrics['latency_ms'] = metrics_dict.get('rendering_latency_ms', 0) or metrics_dict.get('latency_ms', 0)
            
            # 创建反馈信息
            feedback = OptimizationFeedback(
                timestamp=time.time(),
                optimization_level=self.config.optimization_level,
                current_parameters=self.current_parameters,
                performance_metrics=performance_metrics,
                adjustments_made=adjustments,
                expected_improvement=expected_improvement
            )
            
            # 添加到历史记录
            self.adjustment_history.append(feedback)
            if len(self.adjustment_history) > 100:  # 保留最近100条记录
                self.adjustment_history.pop(0)
            
            # 更新统计
            self.adjustment_stats['total_adjustments'] += 1
            self.adjustment_stats['successful_adjustments'] += 1
            self.adjustment_stats['performance_improvements'] += 1 if expected_improvement > 0 else 0
            self.adjustment_stats['last_adjustment_time'] = time.time()
            
            # 通知回调
            self._notify_adjustment_callbacks(feedback)
            self._notify_optimization_callbacks(self.current_parameters)
            
            # 记录调整日志
            logger.info(f"性能优化调整完成: {', '.join(adjustments)}, 预期改善: {expected_improvement:.2%}")
            
        except Exception as e:
            logger.error(f"应用优化调整失败: {e}")
    
    def _notify_optimization_callbacks(self, parameters: RenderParameters):
        """通知优化回调"""
        try:
            for callback in self.optimization_callbacks:
                try:
                    callback(parameters)
                except Exception as e:
                    logger.error(f"优化回调执行失败: {e}")
        except Exception as e:
            logger.error(f"通知优化回调失败: {e}")
    
    def _notify_adjustment_callbacks(self, feedback: OptimizationFeedback):
        """通知调整回调"""
        try:
            for callback in self.adjustment_callbacks:
                try:
                    callback(feedback)
                except Exception as e:
                    logger.error(f"调整回调执行失败: {e}")
        except Exception as e:
            logger.error(f"通知调整回调失败: {e}")
    
    def add_optimization_callback(self, callback: Callable[[RenderParameters], None]):
        """添加优化回调"""
        self.optimization_callbacks.append(callback)
    
    def add_adjustment_callback(self, callback: Callable[[OptimizationFeedback], None]):
        """添加调整回调"""
        self.adjustment_callbacks.append(callback)
    
    def add_render_parameters_callback(self, callback: Callable[[RenderParameters, str, int], None]):
        """添加渲染参数更新回调
        
        Args:
            callback: 回调函数，参数为 (parameters, quality, fps_limit)
        """
        def wrapper(parameters: RenderParameters):
            quality = parameters.render_quality.value
            fps_limit = parameters.fps_limit
            callback(parameters, quality, fps_limit)
        
        self.optimization_callbacks.append(wrapper)
    
    def get_current_parameters(self) -> RenderParameters:
        """获取当前渲染参数"""
        return self.current_parameters
    
    def get_adjustment_history(self, limit: int = 10) -> List[OptimizationFeedback]:
        """获取调整历史"""
        return self.adjustment_history[-limit:] if limit > 0 else self.adjustment_history
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计"""
        return {
            'adjustment_stats': self.adjustment_stats,
            'current_optimization_level': self.config.optimization_level.value,
            'last_adjustment_time': self.adjustment_stats['last_adjustment_time'],
            'success_rate': (
                self.adjustment_stats['successful_adjustments'] / 
                max(1, self.adjustment_stats['total_adjustments'])
            ),
            'improvement_rate': (
                self.adjustment_stats['performance_improvements'] / 
                max(1, self.adjustment_stats['total_adjustments'])
            )
        }

class PerformanceOptimizationIntegration:
    """性能监控与优化集成器"""
    
    def __init__(self, config: Optional[RenderOptimizationConfig] = None):
        self.config = config or RenderOptimizationConfig()
        
        # 初始化协调器和分析器
        self.coordinator = None
        self.analytics = None
        self.optimizer = None
        
        # 集成状态
        self.is_initialized = False
        self.is_running = False
        
        # 性能指标
        self.integration_metrics = {
            'total_optimizations': 0,
            'successful_optimizations': 0,
            'performance_improvements': 0,
            'start_time': None
        }
        
        logger.info("性能监控与优化集成器初始化完成")
    
    async def initialize(self, coordinator: UnifiedPerformanceCoordinator, 
                        analytics: AdvancedPerformanceAnalytics) -> bool:
        """初始化集成器"""
        try:
            self.coordinator = coordinator
            self.analytics = analytics
            
            # 初始化优化器
            self.optimizer = PerformanceOptimizer(coordinator, analytics, self.config)
            
            # 设置回调
            self.optimizer.add_optimization_callback(self._on_optimization_applied)
            self.optimizer.add_adjustment_callback(self._on_adjustment_made)
            
            self.is_initialized = True
            logger.info("性能监控与优化集成器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"性能监控与优化集成器初始化失败: {e}")
            return False
    
    async def start(self) -> bool:
        """启动集成器"""
        if not self.is_initialized:
            logger.error("集成器未初始化")
            return False
        
        try:
            self.integration_metrics['start_time'] = time.time()
            
            # 启动优化器
            if not self.optimizer.start_optimization():
                return False
            
            self.is_running = True
            logger.info("性能监控与优化集成器启动成功")
            return True
            
        except Exception as e:
            logger.error(f"启动性能监控与优化集成器失败: {e}")
            return False
    
    async def stop(self):
        """停止集成器"""
        try:
            self.is_running = False
            
            if self.optimizer:
                self.optimizer.stop_optimization()
            
            logger.info("性能监控与优化集成器已停止")
            
        except Exception as e:
            logger.error(f"停止性能监控与优化集成器失败: {e}")
    
    def _on_optimization_applied(self, parameters: RenderParameters):
        """优化应用回调"""
        try:
            logger.debug(f"渲染参数已优化: FPS={parameters.fps_limit}, 质量={parameters.render_quality.value}")
            
        except Exception as e:
            logger.error(f"优化应用回调失败: {e}")
    
    def _on_adjustment_made(self, feedback: OptimizationFeedback):
        """调整完成回调"""
        try:
            self.integration_metrics['total_optimizations'] += 1
            
            if feedback.expected_improvement > 0:
                self.integration_metrics['successful_optimizations'] += 1
                self.integration_metrics['performance_improvements'] += 1
            
            logger.info(f"性能调整完成，预期改善: {feedback.expected_improvement:.2%}")
            
        except Exception as e:
            logger.error(f"调整完成回调失败: {e}")
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """获取优化状态"""
        if not self.optimizer:
            return {'status': 'not_initialized'}
        
        success_rate = (
            self.integration_metrics['successful_optimizations'] / 
            max(1, self.integration_metrics['total_optimizations'])
        )
        
        uptime = time.time() - self.integration_metrics['start_time'] if self.integration_metrics['start_time'] else 0
        
        return {
            'is_initialized': self.is_initialized,
            'is_running': self.is_running,
            'uptime_seconds': uptime,
            'current_parameters': {
                'fps_limit': self.optimizer.current_parameters.fps_limit,
                'render_quality': self.optimizer.current_parameters.render_quality.value,
                'max_data_points': self.optimizer.current_parameters.max_data_points,
                'texture_quality': self.optimizer.current_parameters.texture_quality
            },
            'integration_metrics': {
                'total_optimizations': self.integration_metrics['total_optimizations'],
                'successful_optimizations': self.integration_metrics['successful_optimizations'],
                'success_rate': success_rate,
                'performance_improvements': self.integration_metrics['performance_improvements']
            },
            'optimizer_stats': self.optimizer.get_optimization_stats()
        }
    
    def get_current_render_parameters(self) -> RenderParameters:
        """获取当前渲染参数"""
        if self.optimizer:
            return self.optimizer.get_current_parameters()
        return RenderParameters()
    
    def get_recent_adjustments(self, limit: int = 5) -> List[OptimizationFeedback]:
        """获取最近的调整记录"""
        if self.optimizer:
            return self.optimizer.get_adjustment_history(limit)
        return []

# 全局集成实例
_global_integration_engine = None

def get_performance_optimization_integration() -> PerformanceOptimizationIntegration:
    """获取全局性能优化集成实例"""
    global _global_integration_engine
    if _global_integration_engine is None:
        from .unified_performance_coordinator import get_unified_performance_coordinator
        from .advanced_performance_analytics import get_advanced_performance_analytics
        
        coordinator = get_unified_performance_coordinator()
        analytics = get_advanced_performance_analytics()
        
        _global_integration_engine = PerformanceOptimizationIntegration()
    return _global_integration_engine
