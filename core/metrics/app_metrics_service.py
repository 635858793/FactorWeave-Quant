# core/metrics/app_metrics_service.py
"""
应用性能度量服务模块

负责收集、记录和分析应用程序的性能指标，如操作响应时间、错误率等。
"""

import time
import threading
import json
import os
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from pathlib import Path
from loguru import logger

from ..events import EventBus
from .events import ApplicationMetricRecorded

@dataclass
class OperationMetrics:
    """操作指标数据类"""
    name: str
    total_duration: float = 0.0
    max_duration: float = 0.0
    call_count: int = 0
    error_count: int = 0
    last_execution_time: Optional[float] = None

    @property
    def avg_duration(self) -> float:
        """计算平均持续时间"""
        return self.total_duration / max(self.call_count, 1)

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        return 1.0 - (self.error_count / max(self.call_count, 1))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "avg_duration": self.avg_duration,
            "max_duration": self.max_duration,
            "total_duration": self.total_duration,
            "call_count": self.call_count,
            "error_count": self.error_count,
            "success_rate": self.success_rate,
            "last_execution_time": self.last_execution_time
        }

class ApplicationMetricsService:
    """
    应用性能度量服务

    负责收集、记录和分析应用程序的性能指标，如操作响应时间、错误率等。
    提供装饰器用于测量函数执行时间。
    """

    _instance = None
    _lock = Lock()

    @classmethod
    def get_instance(cls) -> 'ApplicationMetricsService':
        """获取单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        初始化应用性能度量服务

        Args:
            event_bus: 事件总线
        """
        self.event_bus = event_bus
        self.metrics: Dict[str, OperationMetrics] = {}
        self._metrics_lock = Lock()
        self._enabled = True

        self._metrics_file = Path("data") / "app_metrics.json"
        self._auto_persist = True
        self._flush_interval = 30
        self._flush_timer: Optional[threading.Timer] = None
        self._dirty = False
        self._lock = threading.Lock()
        self._disposed = False

        self._start_flush_timer()

    def measure(self, operation_name: Optional[str] = None) -> Callable:
        """
        测量函数执行时间的装饰器

        Args:
            operation_name: 操作名称，默认为函数名

        Returns:
            装饰后的函数
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self._enabled:
                    return func(*args, **kwargs)

                name = operation_name or func.__qualname__
                start_time = time.perf_counter()
                error = None

                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error = e
                    raise
                finally:
                    end_time = time.perf_counter()
                    duration = end_time - start_time
                    self.record_operation(name, duration, error is None)
            return wrapper
        return decorator

    def record_operation(self, operation_name: str, duration: float, success: bool = True) -> None:
        """
        记录操作执行情况

        Args:
            operation_name: 操作名称
            duration: 执行时间（秒）
            success: 是否成功
        """
        if self._disposed:
            return

        with self._metrics_lock:
            if operation_name not in self.metrics:
                self.metrics[operation_name] = OperationMetrics(
                    name=operation_name)

            metrics = self.metrics[operation_name]

            metrics.total_duration += duration
            metrics.call_count += 1
            metrics.last_execution_time = time.time()

            if duration > metrics.max_duration:
                metrics.max_duration = duration

            if not success:
                metrics.error_count += 1

        self._dirty = True

        # 发布事件
        if self.event_bus:
            try:
                event = ApplicationMetricRecorded(
                    operation_name=operation_name,
                    duration=duration,
                    was_successful=success
                )
                self.event_bus.publish(event)
            except Exception as e:
                logger.error(f"发布指标事件失败: {e}")

    def get_metrics(self, operation_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指标数据

        Args:
            operation_name: 操作名称，如果为None则返回所有指标

        Returns:
            指标数据字典
        """
        with self._metrics_lock:
            if operation_name:
                if operation_name in self.metrics:
                    return self.metrics[operation_name].to_dict()
                return {}

            return {name: metrics.to_dict() for name, metrics in self.metrics.items()}

    def get_slow_operations(self, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """
        获取慢操作列表

        Args:
            threshold: 阈值（秒）

        Returns:
            慢操作列表
        """
        with self._metrics_lock:
            slow_ops = [
                metrics.to_dict()
                for metrics in self.metrics.values()
                if metrics.avg_duration > threshold
            ]

            return sorted(slow_ops, key=lambda x: x["avg_duration"], reverse=True)

    def get_error_prone_operations(self, threshold: float = 0.1) -> List[Dict[str, Any]]:
        """
        获取容易出错的操作列表

        Args:
            threshold: 错误率阈值

        Returns:
            容易出错的操作列表
        """
        with self._metrics_lock:
            error_prone = [
                metrics.to_dict()
                for metrics in self.metrics.values()
                if metrics.call_count > 0 and metrics.error_count / metrics.call_count > threshold
            ]

            return sorted(error_prone, key=lambda x: 1.0 - x["success_rate"], reverse=True)

    def reset_metrics(self, operation_name: Optional[str] = None) -> None:
        """
        重置指标数据

        Args:
            operation_name: 操作名称，如果为None则重置所有指标
        """
        with self._metrics_lock:
            if operation_name:
                if operation_name in self.metrics:
                    self.metrics[operation_name] = OperationMetrics(
                        name=operation_name)
            else:
                self.metrics.clear()

    def enable(self) -> None:
        """启用度量服务"""
        self._enabled = True

    def disable(self) -> None:
        """禁用度量服务"""
        self._enabled = False

    def is_enabled(self) -> bool:
        """
        检查度量服务是否启用

        Returns:
            是否启用
        """
        return self._enabled

    def _start_flush_timer(self) -> None:
        """启动定期刷新定时器"""
        if not self._auto_persist or self._disposed:
            return
        self._flush_timer = threading.Timer(self._flush_interval, self._flush_metrics)
        self._flush_timer.daemon = True
        self._flush_timer.start()

    def _stop_flush_timer(self) -> None:
        """停止定期刷新定时器"""
        if self._flush_timer is not None:
            self._flush_timer.cancel()
            self._flush_timer = None

    def _flush_metrics(self) -> None:
        """定期刷新回调"""
        try:
            if self._dirty:
                self.flush()
        finally:
            if not self._disposed:
                self._start_flush_timer()

    def flush(self) -> bool:
        """
        将当前指标数据持久化到磁盘

        Returns:
            是否成功
        """
        if self._disposed:
            return False
        try:
            self._metrics_file.parent.mkdir(parents=True, exist_ok=True)
            data = self.get_metrics()
            serializable = {
                "updated_at": datetime.now().isoformat(),
                "metrics": data
            }
            with open(self._metrics_file, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
            self._dirty = False
            logger.debug(f"指标数据已持久化到 {self._metrics_file}")
            return True
        except Exception as e:
            logger.error(f"持久化指标数据失败: {e}")
            return False

    def load_metrics(self) -> bool:
        """
        从磁盘加载之前持久化的指标数据

        Returns:
            是否成功加载
        """
        try:
            if not self._metrics_file.exists():
                return False
            with open(self._metrics_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            saved_metrics = data.get("metrics", {})
            with self._metrics_lock:
                for name, metric_data in saved_metrics.items():
                    if name not in self.metrics:
                        m = OperationMetrics(name=name)
                        m.total_duration = metric_data.get("total_duration", 0.0)
                        m.max_duration = metric_data.get("max_duration", 0.0)
                        m.call_count = metric_data.get("call_count", 0)
                        m.error_count = metric_data.get("error_count", 0)
                        m.last_execution_time = metric_data.get("last_execution_time")
                        self.metrics[name] = m
            logger.info(f"从 {self._metrics_file} 加载了 {len(saved_metrics)} 条指标记录")
            return True
        except Exception as e:
            logger.error(f"加载指标数据失败: {e}")
            return False

    def dispose(self) -> None:
        """
        停止服务并强制持久化所有缓存指标
        """
        if self._disposed:
            return
        self._disposed = True
        self._stop_flush_timer()
        self._enabled = False
        if self._dirty:
            self.flush()
        logger.info("应用性能度量服务已停止，指标数据已持久化")

    def measure_time(self, operation_name: Optional[str] = None) -> Callable:
        """
        测量函数执行时间的装饰器 (兼容旧版API)

        Args:
            operation_name: 操作名称，默认为函数名

        Returns:
            装饰后的函数
        """
        # 直接调用 measure 方法，保持向后兼容
        return self.measure(operation_name)

# 全局单例实例
_app_metrics_service: Optional[ApplicationMetricsService] = None

def initialize_app_metrics_service(event_bus: EventBus) -> ApplicationMetricsService:
    """
    初始化应用性能度量服务

    Args:
        event_bus: 事件总线

    Returns:
        应用性能度量服务实例
    """
    global _app_metrics_service

    if _app_metrics_service is None:
        _app_metrics_service = ApplicationMetricsService(event_bus)
        logger.info("应用性能度量服务已初始化")

    return _app_metrics_service

def get_app_metrics_service() -> ApplicationMetricsService:
    """
    获取应用性能度量服务实例

    Returns:
        应用性能度量服务实例
    """
    global _app_metrics_service

    if _app_metrics_service is None:
        logger.warning("应用性能度量服务尚未初始化，返回无事件总线实例")
        return ApplicationMetricsService()

    return _app_metrics_service

def measure(operation_name: Optional[str] = None) -> Callable:
    """
    测量函数执行时间的便捷装饰器

    Args:
        operation_name: 操作名称

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 延迟获取服务，避免在导入时就初始化
            return get_app_metrics_service().measure(operation_name or func.__name__)(func)(*args, **kwargs)
        return wrapper
    return decorator

def measure_time(operation_name: Optional[str] = None) -> Callable:
    """
    测量函数执行时间的便捷装饰器 (兼容旧版API)

    Args:
        operation_name: 操作名称

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 延迟获取服务，避免在导入时就初始化
            return get_app_metrics_service().measure_time(operation_name or func.__name__)(func)(*args, **kwargs)
        return wrapper
    return decorator
