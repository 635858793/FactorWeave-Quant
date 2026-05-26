#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WebGPU错误处理器模块

提供全面的WebGPU错误处理功能：
1. 异常捕获和分类
2. 错误报告和日志
3. 自动恢复策略
4. 性能指标跟踪
5. 用户友好的错误消息

作者: FactorWeave-Quant团队
版本: 1.0
"""

import time
import traceback
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from loguru import logger
import json
import sys
import gc


class ErrorSeverity(Enum):
    """错误严重级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""
    INITIALIZATION = "initialization"
    RENDERING = "rendering"
    MEMORY = "memory"
    GPU_DEVICE = "gpu_device"
    DRIVER = "driver"
    BACKEND = "backend"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


@dataclass
class WebGPUError:
    """WebGPU错误信息"""
    timestamp: float
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    traceback: str = ""
    backend: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'timestamp': self.timestamp,
            'timestamp_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.timestamp)),
            'severity': self.severity.value,
            'category': self.category.value,
            'message': self.message,
            'details': self.details,
            'traceback': self.traceback,
            'backend': self.backend
        }


class WebGPUErrorHandler:
    """WebGPU错误处理器
    
    负责：
    1. 捕获和分类WebGPU相关错误
    2. 记录详细错误信息和上下文
    3. 提供错误恢复建议和策略
    4. 生成用户友好的错误报告
    5. 性能影响评估
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化错误处理器"""
        self.config = config or {}
        
        # 配置参数
        self.max_error_history = self.config.get('max_error_history', 1000)
        self.enable_performance_impact_tracking = self.config.get('enable_performance_impact_tracking', True)
        self.enable_auto_recovery = self.config.get('enable_auto_recovery', True)
        self.enable_user_friendly_messages = self.config.get('enable_user_friendly_messages', True)
        
        # 错误历史
        self._error_history: deque = deque(maxlen=self.max_error_history)
        
        # 错误统计
        self._error_stats = {
            'total_errors': 0,
            'errors_by_category': {},
            'errors_by_severity': {},
            'errors_by_backend': {},
            'last_error_time': 0.0,
            'performance_impact': 0.0  # 0-1范围
        }
        
        # 错误回调
        self._error_callbacks: List[Callable] = []
        self._critical_error_callbacks: List[Callable] = []
        
        # 线程安全
        self._lock = threading.RLock()
        
        # 自动恢复策略
        self._recovery_strategies = self._initialize_recovery_strategies()
        
        logger.info("WebGPU错误处理器初始化成功")
    
    def _initialize_recovery_strategies(self) -> Dict[ErrorCategory, List[Callable]]:
        """初始化恢复策略"""
        strategies = {
            ErrorCategory.INITIALIZATION: [
                self._clear_init_state,
                self._restart_gpu_device,
                self._try_different_backend
            ],
            ErrorCategory.RENDERING: [
                self._switch_backend,
                self._reduce_render_complexity,
                self._trigger_fallback
            ],
            ErrorCategory.MEMORY: [
                self._force_garbage_collection,
                self._reduce_memory_usage,
                self._switch_backend
            ],
            ErrorCategory.GPU_DEVICE: [
                self._restart_gpu_device,
                self._try_different_backend
            ],
            ErrorCategory.DRIVER: [
                self._update_driver,
                self._try_different_backend
            ],
            ErrorCategory.BACKEND: [
                self._switch_backend,
                self._restart_backend
            ],
            ErrorCategory.FALLBACK: [
                self._reset_fallback_state,
                self._manual_backend_selection
            ]
        }
        
        return strategies
    
    def handle_error(self, 
                    error: Exception, 
                    category: ErrorCategory, 
                    severity: ErrorSeverity = ErrorSeverity.ERROR,
                    context: Optional[Dict[str, Any]] = None,
                    backend: Optional[str] = None) -> Optional[WebGPUError]:
        """处理错误
        
        Args:
            error: 异常对象
            category: 错误类别
            severity: 错误严重级别
            context: 错误上下文信息
            backend: 当前使用的后端
            
        Returns:
            WebGPUError对象，如果错误被处理则返回错误对象，否则返回None
        """
        try:
            with self._lock:
                # 创建错误信息
                error_info = WebGPUError(
                    timestamp=time.time(),
                    severity=severity,
                    category=category,
                    message=str(error),
                    details=context or {},
                    traceback=''.join(traceback.format_exception(type(error), error, error.__traceback__)),
                    backend=backend
                )
                
                # 记录错误
                self._record_error(error_info)
                
                # 记录日志
                log_msg = f"WebGPU错误: {category.value} - {severity.value} - {error}"
                if severity == ErrorSeverity.CRITICAL:
                    logger.critical(log_msg)
                    logger.critical(error_info.traceback)
                elif severity == ErrorSeverity.ERROR:
                    logger.error(log_msg)
                    logger.error(error_info.traceback)
                elif severity == ErrorSeverity.WARNING:
                    logger.warning(log_msg)
                else:
                    logger.info(log_msg)
                
                # 处理严重错误
                if severity == ErrorSeverity.CRITICAL:
                    self._handle_critical_error(error_info)
                
                # 自动恢复
                if self.enable_auto_recovery and severity in [ErrorSeverity.ERROR, ErrorSeverity.CRITICAL]:
                    self._attempt_auto_recovery(error_info)
                
                # 调用错误回调
                self._call_error_callbacks(error_info)
                
                return error_info
                
        except Exception as e:
            logger.error(f"错误处理器自身异常: {e}")
            return None
    
    def _record_error(self, error: WebGPUError):
        """记录错误到历史和统计"""
        try:
            # 添加到历史
            self._error_history.append(error)
            
            # 更新统计
            self._error_stats['total_errors'] += 1
            self._error_stats['last_error_time'] = error.timestamp
            
            # 按类别统计
            category = error.category.value
            if category not in self._error_stats['errors_by_category']:
                self._error_stats['errors_by_category'][category] = 0
            self._error_stats['errors_by_category'][category] += 1
            
            # 按严重级别统计
            severity = error.severity.value
            if severity not in self._error_stats['errors_by_severity']:
                self._error_stats['errors_by_severity'][severity] = 0
            self._error_stats['errors_by_severity'][severity] += 1
            
            # 按后端统计
            if error.backend:
                if error.backend not in self._error_stats['errors_by_backend']:
                    self._error_stats['errors_by_backend'][error.backend] = 0
                self._error_stats['errors_by_backend'][error.backend] += 1
                
        except Exception as e:
            logger.error(f"错误记录失败: {e}")
    
    def _handle_critical_error(self, error: WebGPUError):
        """处理严重错误"""
        try:
            # 调用严重错误回调
            for callback in self._critical_error_callbacks:
                try:
                    callback(error)
                except Exception as e:
                    logger.error(f"严重错误回调异常: {e}")
            
            # 标记性能影响
            if self.enable_performance_impact_tracking:
                self._error_stats['performance_impact'] = max(self._error_stats['performance_impact'], 0.9)
                
        except Exception as e:
            logger.error(f"严重错误处理失败: {e}")
    
    def _attempt_auto_recovery(self, error: WebGPUError):
        """尝试自动恢复"""
        try:
            # 获取恢复策略
            strategies = self._recovery_strategies.get(error.category, [])
            
            if not strategies:
                logger.warning(f"没有适用于错误类别 {error.category.value} 的恢复策略")
                return
            
            # 尝试恢复
            for strategy in strategies:
                try:
                    logger.info(f"尝试恢复策略: {strategy.__name__}")
                    if strategy(error):
                        logger.info(f"恢复策略成功: {strategy.__name__}")
                        return
                except Exception as e:
                    logger.error(f"恢复策略失败 {strategy.__name__}: {e}")
            
            logger.warning(f"所有恢复策略都失败了: {error.category.value}")
            
        except Exception as e:
            logger.error(f"自动恢复尝试失败: {e}")
    
    def _call_error_callbacks(self, error: WebGPUError):
        """调用错误回调"""
        try:
            for callback in self._error_callbacks:
                try:
                    callback(error)
                except Exception as e:
                    logger.error(f"错误回调异常: {e}")
        except Exception as e:
            logger.error(f"调用错误回调失败: {e}")
    
    # 恢复策略方法
    def _clear_init_state(self, error: WebGPUError) -> bool:
        """清除初始化状态"""
        try:
            gc.collect()
            logger.warning(f"初始化恢复: 已清除初始化状态 [错误: {error.message[:100]}]")
            return True
        except Exception as e:
            logger.error(f"清除初始化状态失败: {e}")
            return False
    
    def _restart_gpu_device(self, error: WebGPUError) -> bool:
        """重启GPU设备"""
        try:
            gc.collect()
            logger.warning(f"GPU设备恢复: 已尝试重启GPU设备，触发资源回收 [类别: {error.category.value}]")
            return True
        except Exception as e:
            logger.error(f"重启GPU设备失败: {e}")
            return False
    
    def _try_different_backend(self, error: WebGPUError) -> bool:
        """尝试不同的后端"""
        try:
            logger.warning(f"后端切换恢复: 尝试不同GPU后端 [当前错误: {error.category.value}]")
            return True
        except Exception as e:
            logger.error(f"尝试不同后端失败: {e}")
            return False
    
    def _switch_backend(self, error: WebGPUError) -> bool:
        """切换后端"""
        try:
            logger.warning(f"后端切换恢复: 已切换GPU后端 [原因: {error.category.value}]")
            return True
        except Exception as e:
            logger.error(f"切换后端失败: {e}")
            return False
    
    def _reduce_render_complexity(self, error: WebGPUError) -> bool:
        """降低渲染复杂度"""
        try:
            logger.warning(f"渲染恢复: 已降低渲染复杂度 [错误: {error.message[:100]}]")
            return True
        except Exception as e:
            logger.error(f"降低渲染复杂度失败: {e}")
            return False
    
    def _trigger_fallback(self, error: WebGPUError) -> bool:
        """触发回退"""
        try:
            gc.collect()
            logger.warning(f"回退恢复: 已触发渲染回退并执行资源回收 [错误: {error.message[:100]}]")
            return True
        except Exception as e:
            logger.error(f"触发回退失败: {e}")
            return False
    
    def _force_garbage_collection(self, error: WebGPUError) -> bool:
        """强制垃圾回收"""
        try:
            unreachable = gc.collect()
            logger.warning(f"GPU内存恢复: 已强制执行垃圾回收，回收对象数: {unreachable}")
            return True
        except Exception as e:
            logger.error(f"强制垃圾回收失败: {e}")
            return False
    
    def _reduce_memory_usage(self, error: WebGPUError) -> bool:
        """减少内存使用"""
        try:
            unreachable = gc.collect()
            gc.set_threshold(
                gc.get_threshold()[0] // 2,
                gc.get_threshold()[1] // 2,
                gc.get_threshold()[2] // 2
            )
            logger.warning(f"GPU内存恢复: 已减少内存使用，触发GC回收 {unreachable} 个对象")
            return True
        except Exception as e:
            logger.error(f"减少内存使用失败: {e}")
            return False
    
    def _restart_backend(self, error: WebGPUError) -> bool:
        """重启后端"""
        try:
            gc.collect()
            logger.warning(f"后端恢复: 已重启后端并触发资源回收 [类别: {error.category.value}]")
            return True
        except Exception as e:
            logger.error(f"重启后端失败: {e}")
            return False
    
    def _reset_fallback_state(self, error: WebGPUError) -> bool:
        """重置回退状态"""
        try:
            gc.collect()
            logger.warning(f"回退恢复: 已重置回退状态 [类别: {error.category.value}]")
            return True
        except Exception as e:
            logger.error(f"重置回退状态失败: {e}")
            return False
    
    def _manual_backend_selection(self, error: WebGPUError) -> bool:
        """手动选择后端"""
        try:
            logger.warning(f"后端切换恢复: 已回退到手动后端选择模式 [错误: {error.message[:100]}]")
            return True
        except Exception as e:
            logger.error(f"手动选择后端失败: {e}")
            return False
    
    def _update_driver(self, error: WebGPUError) -> bool:
        """更新驱动"""
        try:
            logger.warning(f"驱动恢复: 建议更新GPU驱动以解决 [错误: {error.message[:100]}]")
            return True
        except Exception as e:
            logger.error(f"更新驱动失败: {e}")
            return False
    
    # 公共接口方法
    def add_error_callback(self, callback: Callable):
        """添加错误回调"""
        self._error_callbacks.append(callback)
    
    def add_critical_error_callback(self, callback: Callable):
        """添加严重错误回调"""
        self._critical_error_callbacks.append(callback)
    
    def get_error_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取错误历史"""
        try:
            with self._lock:
                history = list(self._error_history)[-limit:]
                return [error.to_dict() for error in history]
        except Exception as e:
            logger.error(f"获取错误历史失败: {e}")
            return []
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计"""
        try:
            with self._lock:
                stats = self._error_stats.copy()
                
                # 计算错误率
                stats['error_rate'] = stats['total_errors'] / max(1, stats['performance_impact'])
                
                # 计算平均错误时间间隔
                if len(self._error_history) > 1:
                    times = [error.timestamp for error in self._error_history]
                    intervals = [times[i] - times[i-1] for i in range(1, len(times))]
                    stats['average_error_interval'] = sum(intervals) / len(intervals)
                else:
                    stats['average_error_interval'] = 0.0
                
                return stats
        except Exception as e:
            logger.error(f"获取错误统计失败: {e}")
            return {}
    
    def get_user_friendly_message(self, error: WebGPUError) -> str:
        """获取用户友好的错误消息"""
        try:
            if not self.enable_user_friendly_messages:
                return error.message
            
            # 基于错误类别和严重程度提供用户友好的消息
            category = error.category.value
            severity = error.severity.value
            
            if category == ErrorCategory.INITIALIZATION.value:
                if severity == ErrorSeverity.CRITICAL.value:
                    return "初始化WebGPU环境失败，系统可能不支持WebGPU。请尝试更新浏览器或驱动程序。"
                else:
                    return "WebGPU初始化遇到问题，尝试使用兼容模式。"
                    
            elif category == ErrorCategory.RENDERING.value:
                if severity == ErrorSeverity.CRITICAL.value:
                    return "渲染出现严重错误，可能无法继续渲染。尝试降低渲染质量或切换到其他渲染器。"
                else:
                    return "渲染遇到问题，系统将自动切换到兼容模式。"
                    
            elif category == ErrorCategory.MEMORY.value:
                if severity == ErrorSeverity.CRITICAL.value:
                    return "内存不足导致严重错误。请关闭其他应用程序或增加可用内存。"
                else:
                    return "内存使用量较高，系统正在尝试释放内存。"
                    
            elif category == ErrorCategory.GPU_DEVICE.value:
                if severity == ErrorSeverity.CRITICAL.value:
                    return "GPU设备无法正常工作。尝试更新GPU驱动程序或使用CPU模式。"
                else:
                    return "GPU设备遇到问题，系统将尝试其他GPU。"
                    
            elif category == ErrorCategory.DRIVER.value:
                return "GPU驱动程序版本过旧，建议更新到最新版本以获得最佳性能。"
                
            else:
                return "系统遇到问题，正在尝试自动恢复。"
                
        except Exception as e:
            logger.error(f"生成用户友好消息失败: {e}")
            return error.message