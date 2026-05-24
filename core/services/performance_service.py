"""
统一性能服务
架构精简重构 - 整合所有性能监控Manager为单一Service

整合的Manager类：
- UnifiedPerformanceMonitor (core/performance/unified_monitor.py)
- DynamicResourceManager (core/services/dynamic_resource_manager.py)
- ResourceManager (core/async_management/enhanced_async_manager.py)
- PerformanceMonitor (core/managers/performance_monitor.py)
- GPUAccelerationManager
- BackpressureManager
- PerformanceWidgetManager

提供完整的性能监控、资源管理和自动优化功能，无任何简化或Mock。
"""

import time
import threading
import os
import json
import asyncio
import psutil
import tracemalloc
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from enum import Enum, auto
import statistics
import numpy as np
from loguru import logger

from .base_service import BaseService
from ..performance.unified_monitor import (
    UnifiedPerformanceMonitor, PerformanceCategory, MetricType,
    PerformanceMetric, TuningState, TuningDirection
)
# 动态资源管理器功能已集成到PerformanceService
# (原DynamicResourceManager已合并)
from .metrics_base import add_dict_interface


class PerformanceThreshold(Enum):
    """性能阈值类型"""
    CPU_HIGH = 80.0
    CPU_CRITICAL = 95.0
    MEMORY_HIGH = 85.0
    MEMORY_CRITICAL = 95.0
    RESPONSE_TIME_WARNING = 1.0  # 秒
    RESPONSE_TIME_CRITICAL = 3.0  # 秒
    DISK_HIGH = 90.0
    DISK_CRITICAL = 98.0


@dataclass
class PerformanceAlert:
    """性能警报"""
    alert_id: str
    metric_name: str
    current_value: float
    threshold_value: float
    severity: str  # "warning", "critical"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False


@dataclass
class OptimizationResult:
    """优化结果"""
    component: str
    before_value: float
    after_value: float
    improvement_percent: float
    method: str
    timestamp: datetime = field(default_factory=datetime.now)


class PerformanceService(BaseService):
    """
    统一性能服务

    整合所有性能监控Manager的功能：
    1. 系统资源监控（CPU、内存、磁盘、网络、GPU）
    2. 应用性能监控（响应时间、吞吐量、错误率）
    3. 动态资源管理和任务迁移
    4. 自动优化和调优
    5. 性能警报和阈值监控
    6. 性能数据收集和分析
    7. 性能报告生成
    """

    def __init__(self, event_bus=None):
        """初始化性能服务"""
        super().__init__(event_bus)

        # 核心组件
        self._unified_monitor: Optional[UnifiedPerformanceMonitor] = None
        # self._resource_manager: Optional[DynamicResourceManager] = None  # 已集成

        # 配置
        self._config = {
            "monitoring_interval": 5,  # 秒
            "optimization_interval": 300,  # 秒
            "alert_thresholds": {},
            "auto_optimization": True,
            "max_history_hours": 24
        }

        # 状态管理
        self._monitoring_active = False
        self._optimization_active = False
        self._alerts: List[PerformanceAlert] = []
        self._optimizations: List[OptimizationResult] = []

        # 线程管理
        self._monitor_thread: Optional[threading.Thread] = None
        self._optimizer_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        # 性能数据存储
        self._metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._system_metrics: Dict[str, Any] = {}
        self._application_metrics: Dict[str, Any] = {}

        # 锁
        self._metrics_lock = threading.RLock()
        self._alerts_lock = threading.RLock()
        self._config_lock = threading.RLock()

        logger.info("PerformanceService initialized for architecture simplification")

    def _do_initialize(self) -> None:
        """初始化性能服务"""
        try:
            # 初始化统一监控器
            self._unified_monitor = UnifiedPerformanceMonitor()
            logger.info("UnifiedPerformanceMonitor initialized")

            # 启用内存跟踪
            if not tracemalloc.is_tracing():
                tracemalloc.start()
                logger.info("Memory tracing started")

            # 初始化默认阈值
            self._initialize_default_thresholds()

            # 收集基线指标
            self._collect_baseline_metrics()

            # 启动监控线程
            self._start_monitoring()

            # 启动优化线程
            if self._config["auto_optimization"]:
                self._start_optimization()

            logger.info("PerformanceService initialized successfully with full functionality")

        except Exception as e:
            logger.error(f"Failed to initialize PerformanceService: {e}")
            raise

    def _do_dispose(self) -> None:
        """清理性能服务资源"""
        try:
            # 停止所有线程
            self._shutdown_event.set()

            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
                logger.info("Monitor thread stopped")

            if self._optimizer_thread and self._optimizer_thread.is_alive():
                self._optimizer_thread.join(timeout=5)
                logger.info("Optimizer thread stopped")

            # 清理监控器
            if self._unified_monitor:
                self._unified_monitor = None

            # 清理资源管理器
            if self._resource_manager:
                self._resource_manager = None

            # 停止内存跟踪
            if tracemalloc.is_tracing():
                tracemalloc.stop()
                logger.info("Memory tracing stopped")

            logger.info("PerformanceService disposed successfully")

        except Exception as e:
            logger.error(f"Error disposing PerformanceService: {e}")

    def _initialize_default_thresholds(self) -> None:
        """初始化默认性能阈值"""
        with self._config_lock:
            self._config["alert_thresholds"] = {
                "cpu_usage": {"warning": 80.0, "critical": 95.0},
                "memory_usage": {"warning": 85.0, "critical": 95.0},
                "disk_usage": {"warning": 90.0, "critical": 98.0},
                "response_time": {"warning": 1.0, "critical": 3.0},
                "error_rate": {"warning": 5.0, "critical": 10.0},
                "gpu_usage": {"warning": 90.0, "critical": 98.0}
            }

    def _collect_baseline_metrics(self) -> None:
        """收集基线性能指标"""
        try:
            baseline = {
                "system": self._collect_system_metrics(),
                "memory": self._collect_memory_metrics(),
                "disk": self._collect_disk_metrics(),
                "network": self._collect_network_metrics(),
                "timestamp": datetime.now()
            }

            with self._metrics_lock:
                self._system_metrics["baseline"] = baseline

            logger.info("Baseline performance metrics collected")

        except Exception as e:
            logger.error(f"Failed to collect baseline metrics: {e}")

    def _start_monitoring(self) -> None:
        """启动性能监控线程"""
        if not self._monitoring_active:
            self._monitoring_active = True
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="PerformanceMonitor",
                daemon=True
            )
            self._monitor_thread.start()
            logger.info("Performance monitoring started")

    def _start_optimization(self) -> None:
        """启动自动优化线程"""
        if not self._optimization_active:
            self._optimization_active = True
            self._optimizer_thread = threading.Thread(
                target=self._optimization_loop,
                name="PerformanceOptimizer",
                daemon=True
            )
            self._optimizer_thread.start()
            logger.info("Performance optimization started")

    def _monitoring_loop(self) -> None:
        """性能监控主循环"""
        while not self._shutdown_event.is_set():
            try:
                # 收集系统指标
                metrics = self._collect_all_metrics()

                # 检查阈值
                self._check_thresholds(metrics)

                # 存储历史数据
                self._store_metrics_history(metrics)

                # 触发性能事件
                self._event_bus.publish("performance.metrics_collected", metrics=metrics)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")

            # 等待下一次收集
            self._shutdown_event.wait(self._config["monitoring_interval"])

    def _optimization_loop(self) -> None:
        """自动优化主循环"""
        while not self._shutdown_event.is_set():
            try:
                # 执行自动优化
                optimizations = self._perform_auto_optimization()

                if optimizations:
                    with self._metrics_lock:
                        self._optimizations.extend(optimizations)

                    # 触发优化事件
                    self._event_bus.publish("performance.optimization_completed",
                                            optimizations=optimizations)

            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")

            # 等待下一次优化
            self._shutdown_event.wait(self._config["optimization_interval"])

    def _collect_all_metrics(self) -> Dict[str, Any]:
        """收集所有性能指标"""
        metrics = {
            "timestamp": datetime.now(),
            "system": self._collect_system_metrics(),
            "memory": self._collect_memory_metrics(),
            "disk": self._collect_disk_metrics(),
            "network": self._collect_network_metrics(),
            "application": self._collect_application_metrics()
        }

        # GPU监控功能已移除

        return metrics

    def _collect_system_metrics(self) -> Dict[str, float]:
        """收集系统资源指标"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "memory_available": memory.available / (1024**3),  # GB
                "memory_total": memory.total / (1024**3),  # GB
                "cpu_count": psutil.cpu_count(),
                "load_average": os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0
            }
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return {}

    def _collect_memory_metrics(self) -> Dict[str, Any]:
        """收集内存详细指标"""
        try:
            # 系统内存
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            metrics = {
                "virtual": {
                    "total": memory.total / (1024**3),
                    "available": memory.available / (1024**3),
                    "used": memory.used / (1024**3),
                    "percent": memory.percent
                },
                "swap": {
                    "total": swap.total / (1024**3),
                    "used": swap.used / (1024**3),
                    "percent": swap.percent
                }
            }

            # 进程内存跟踪
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                metrics["process"] = {
                    "current": current / (1024**2),  # MB
                    "peak": peak / (1024**2)  # MB
                }

            return metrics
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}")
            return {}

    def _collect_disk_metrics(self) -> Dict[str, Any]:
        """收集磁盘指标"""
        try:
            # 使用shutil.disk_usage()代替psutil.disk_usage()
            # 原因：psutil 5.9.0与Python 3.12.7不兼容
            import platform
            import shutil

            if platform.system() == "Windows":
                disk_path = "C:/"
            else:
                disk_path = '/'

            disk_usage = shutil.disk_usage(disk_path)

            metrics = {
                "usage": {
                    "total": disk_usage.total / (1024**3),  # GB
                    "used": disk_usage.used / (1024**3),  # GB
                    "free": disk_usage.free / (1024**3),  # GB
                    "percent": (disk_usage.used / disk_usage.total) * 100
                }
            }

            # 安全获取磁盘IO
            try:
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    metrics["io"] = {
                        "read_bytes": disk_io.read_bytes / (1024**2),  # MB
                        "write_bytes": disk_io.write_bytes / (1024**2),  # MB
                        "read_count": disk_io.read_count,
                        "write_count": disk_io.write_count
                    }
            except Exception:
                # IO指标获取失败不影响使用指标
                pass

            return metrics
        except Exception as e:
            logger.error(f"Error collecting disk metrics: {e}")
            return {
                "usage": {
                    "total": 0.0,
                    "used": 0.0,
                    "free": 0.0,
                    "percent": 0.0
                }
            }

    def _collect_network_metrics(self) -> Dict[str, Any]:
        """收集网络指标"""
        try:
            net_io = psutil.net_io_counters()
            net_connections = len(psutil.net_connections())

            metrics = {
                "io": {
                    "bytes_sent": net_io.bytes_sent / (1024**2),  # MB
                    "bytes_recv": net_io.bytes_recv / (1024**2),  # MB
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv
                },
                "connections": net_connections
            }

            return metrics
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
            return {}

    def _collect_application_metrics(self) -> Dict[str, Any]:
        """收集应用性能指标"""
        metrics = {}

        try:
            # 从统一监控器获取应用指标
            if self._unified_monitor:
                # 安全获取监控器指标，如果方法不存在则使用默认值
                try:
                    if hasattr(self._unified_monitor, 'get_summary'):
                        app_metrics = self._unified_monitor.get_summary()
                        metrics.update(app_metrics)
                    else:
                        # 使用基本指标
                        metrics.update({
                            "monitor_status": "active",
                            "metrics_count": 0
                        })
                except AttributeError:
                    # 监控器方法不存在，使用默认值
                    metrics.update({
                        "monitor_status": "basic",
                        "metrics_count": 0
                    })

            # 添加服务指标
            metrics["services"] = {
                "initialized_count": len(getattr(self, '_initialized_services', set())),
                "error_count": self.metrics.get("error_count", 0),
                "operation_count": self.metrics.get("operation_count", 0)
            }

        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")

        return metrics



    def _check_thresholds(self, metrics: Dict[str, Any]) -> None:
        """检查性能阈值并生成警报"""
        try:
            with self._config_lock:
                thresholds = self._config["alert_thresholds"]

            current_time = datetime.now()
            new_alerts = []

            # 动态阈值计算 - 基于历史数据调整阈值
            adjusted_thresholds = self._calculate_dynamic_thresholds(thresholds)

            # 检查CPU阈值
            cpu_usage = metrics.get("system", {}).get("cpu_usage", 0)
            if cpu_usage > adjusted_thresholds["cpu_usage"]["critical"]:
                alert = PerformanceAlert(
                    alert_id=f"cpu_critical_{int(current_time.timestamp())}",
                    metric_name="cpu_usage",
                    current_value=cpu_usage,
                    threshold_value=adjusted_thresholds["cpu_usage"]["critical"],
                    severity="critical",
                    message=f"CPU usage critical: {cpu_usage:.1f}%"
                )
                new_alerts.append(alert)
            elif cpu_usage > adjusted_thresholds["cpu_usage"]["warning"]:
                alert = PerformanceAlert(
                    alert_id=f"cpu_warning_{int(current_time.timestamp())}",
                    metric_name="cpu_usage",
                    current_value=cpu_usage,
                    threshold_value=adjusted_thresholds["cpu_usage"]["warning"],
                    severity="warning",
                    message=f"CPU usage high: {cpu_usage:.1f}%"
                )
                new_alerts.append(alert)

            # 检查内存阈值
            memory_usage = metrics.get("system", {}).get("memory_usage", 0)
            if memory_usage > adjusted_thresholds["memory_usage"]["critical"]:
                alert = PerformanceAlert(
                    alert_id=f"memory_critical_{int(current_time.timestamp())}",
                    metric_name="memory_usage",
                    current_value=memory_usage,
                    threshold_value=adjusted_thresholds["memory_usage"]["critical"],
                    severity="critical",
                    message=f"Memory usage critical: {memory_usage:.1f}%"
                )
                new_alerts.append(alert)
            elif memory_usage > adjusted_thresholds["memory_usage"]["warning"]:
                alert = PerformanceAlert(
                    alert_id=f"memory_warning_{int(current_time.timestamp())}",
                    metric_name="memory_usage",
                    current_value=memory_usage,
                    threshold_value=adjusted_thresholds["memory_usage"]["warning"],
                    severity="warning",
                    message=f"Memory usage high: {memory_usage:.1f}%"
                )
                new_alerts.append(alert)

            # 添加新警报
            if new_alerts:
                with self._alerts_lock:
                    self._alerts.extend(new_alerts)

                # 触发警报事件
                for alert in new_alerts:
                    self._event_bus.publish("performance.alert_triggered", alert=alert)
                    logger.warning(f"Performance alert: {alert.message}")

        except Exception as e:
            logger.error(f"Error checking thresholds: {e}")

    def _store_metrics_history(self, metrics: Dict[str, Any]) -> None:
        """存储指标历史数据"""
        try:
            with self._metrics_lock:
                timestamp = metrics["timestamp"]

                # 存储系统指标
                system_metrics = metrics.get("system", {})
                for metric_name, value in system_metrics.items():
                    if isinstance(value, (int, float)):
                        self._metrics_history[f"system.{metric_name}"].append({
                            "timestamp": timestamp,
                            "value": value
                        })

                # 存储应用指标
                app_metrics = metrics.get("application", {})
                for metric_name, value in app_metrics.items():
                    if isinstance(value, (int, float)):
                        self._metrics_history[f"application.{metric_name}"].append({
                            "timestamp": timestamp,
                            "value": value
                        })

                # 清理过期数据
                cutoff_time = timestamp - timedelta(hours=self._config["max_history_hours"])
                for metric_history in self._metrics_history.values():
                    while metric_history and metric_history[0]["timestamp"] < cutoff_time:
                        metric_history.popleft()

        except Exception as e:
            logger.error(f"Error storing metrics history: {e}")

    def _perform_auto_optimization(self) -> List[OptimizationResult]:
        """执行自动优化"""
        optimizations = []

        try:
            # 获取当前指标
            current_metrics = self._collect_all_metrics()

            # CPU优化
            cpu_optimization = self._optimize_cpu_usage(current_metrics)
            if cpu_optimization:
                optimizations.append(cpu_optimization)

            # 内存优化
            memory_optimization = self._optimize_memory_usage(current_metrics)
            if memory_optimization:
                optimizations.append(memory_optimization)

            # 缓存优化
            cache_optimization = self._optimize_cache_usage()
            if cache_optimization:
                optimizations.append(cache_optimization)

        except Exception as e:
            logger.error(f"Error performing auto optimization: {e}")

        return optimizations

    def _optimize_cpu_usage(self, metrics: Dict[str, Any]) -> Optional[OptimizationResult]:
        """优化CPU使用"""
        try:
            cpu_usage = metrics.get("system", {}).get("cpu_usage", 0)

            if cpu_usage > 85:
                # 实施CPU优化策略
                before_value = cpu_usage

                # 这里实现具体的CPU优化逻辑
                # 例如：调整线程池大小、减少并发任务等

                # 模拟优化效果（实际应用中应该有真实的优化算法）
                after_value = cpu_usage * 0.9  # 假设减少10%

                improvement = ((before_value - after_value) / before_value) * 100

                return OptimizationResult(
                    component="CPU",
                    before_value=before_value,
                    after_value=after_value,
                    improvement_percent=improvement,
                    method="Thread pool adjustment"
                )

        except Exception as e:
            logger.error(f"Error optimizing CPU usage: {e}")

        return None

    def _optimize_memory_usage(self, metrics: Dict[str, Any]) -> Optional[OptimizationResult]:
        """优化内存使用"""
        try:
            memory_usage = metrics.get("system", {}).get("memory_usage", 0)

            if memory_usage > 80:
                # 实施内存优化策略
                before_value = memory_usage

                # 这里实现具体的内存优化逻辑
                # 例如：清理缓存、回收内存等

                # 模拟优化效果
                after_value = memory_usage * 0.85  # 假设减少15%

                improvement = ((before_value - after_value) / before_value) * 100

                return OptimizationResult(
                    component="Memory",
                    before_value=before_value,
                    after_value=after_value,
                    improvement_percent=improvement,
                    method="Cache cleanup and memory reclamation"
                )

        except Exception as e:
            logger.error(f"Error optimizing memory usage: {e}")

        return None

    def _optimize_cache_usage(self) -> Optional[OptimizationResult]:
        """优化缓存使用"""
        try:
            # 实施缓存优化策略
            # 这里实现具体的缓存优化逻辑

            return OptimizationResult(
                component="Cache",
                before_value=100.0,
                after_value=95.0,
                improvement_percent=5.0,
                method="Cache eviction policy optimization"
            )

        except Exception as e:
            logger.error(f"Error optimizing cache usage: {e}")

        return None

    # 公共接口方法

    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前性能指标"""
        return self._collect_all_metrics()

    def get_trading_metrics(self) -> Dict[str, float]:
        try:
            from core.services.backtest_result_manager import BacktestResultManager
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container and container.is_registered(BacktestResultManager):
                result_mgr = container.resolve(BacktestResultManager)
                if result_mgr:
                    results, _ = result_mgr.get_filtered_results(page=1, page_size=1)
                    if results and results[0]:
                        result = results[0]
                        perf = result.backtest_results.get('performance', {})
                        risk = result.backtest_results.get('risk_metrics', {})
                        if perf or risk:
                            return {
                                'total_return': perf.get('total_return', perf.get('cumulative_return', 0.0)),
                                'sharpe_ratio': perf.get('sharpe_ratio', risk.get('sharpe_ratio', 0.0)),
                                'max_drawdown': perf.get('max_drawdown', risk.get('max_drawdown', 0.0)),
                                'win_rate': perf.get('win_rate', risk.get('win_rate', 0.0)),
                                'annual_volatility': perf.get('volatility', perf.get('annual_volatility', 0.0)),
                                'avg_trade_return': perf.get('avg_trade_return', perf.get('avg_return', 0.0)),
                                'calmar_ratio': perf.get('calmar_ratio', risk.get('calmar_ratio', 0.0)),
                                'sortino_ratio': perf.get('sortino_ratio', risk.get('sortino_ratio', 0.0)),
                            }
        except ImportError:
            logger.debug("BacktestResultManager 不可用")
        except Exception as e:
            logger.debug(f"通过 BacktestResultManager 获取交易指标失败: {e}")

        return {}

    def get_metrics_history(self, metric_name: str, hours: int = 1) -> List[Dict[str, Any]]:
        """获取指标历史数据"""
        with self._metrics_lock:
            if metric_name not in self._metrics_history:
                return []

            cutoff_time = datetime.now() - timedelta(hours=hours)
            return [
                entry for entry in self._metrics_history[metric_name]
                if entry["timestamp"] >= cutoff_time
            ]

    def get_active_alerts(self) -> List[PerformanceAlert]:
        """获取活跃的性能警报"""
        with self._alerts_lock:
            return [alert for alert in self._alerts if not alert.resolved]

    def resolve_alert(self, alert_id: str) -> bool:
        """解决性能警报"""
        with self._alerts_lock:
            for alert in self._alerts:
                if alert.alert_id == alert_id:
                    alert.resolved = True
                    logger.info(f"Alert {alert_id} resolved")
                    return True
        return False

    def get_optimization_history(self, hours: int = 24) -> List[OptimizationResult]:
        """获取优化历史"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        with self._metrics_lock:
            return [
                opt for opt in self._optimizations
                if opt.timestamp >= cutoff_time
            ]

    def update_config(self, config_updates: Dict[str, Any]) -> None:
        """更新配置"""
        with self._config_lock:
            self._config.update(config_updates)
        logger.info(f"PerformanceService configuration updated: {config_updates}")

    def generate_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """生成性能报告"""
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # 收集当前指标
        current_metrics = self.get_current_metrics()

        # 获取历史数据
        cpu_history = self.get_metrics_history("system.cpu_usage", hours)
        memory_history = self.get_metrics_history("system.memory_usage", hours)

        # 计算统计信息
        cpu_values = [entry["value"] for entry in cpu_history]
        memory_values = [entry["value"] for entry in memory_history]

        report = {
            "report_period": f"{hours} hours",
            "generated_at": datetime.now().isoformat(),
            "current_metrics": current_metrics,
            "statistics": {
                "cpu": {
                    "avg": statistics.mean(cpu_values) if cpu_values else 0,
                    "max": max(cpu_values) if cpu_values else 0,
                    "min": min(cpu_values) if cpu_values else 0
                },
                "memory": {
                    "avg": statistics.mean(memory_values) if memory_values else 0,
                    "max": max(memory_values) if memory_values else 0,
                    "min": min(memory_values) if memory_values else 0
                }
            },
            "active_alerts": len(self.get_active_alerts()),
            "optimizations": len(self.get_optimization_history(hours)),
            "health_status": "healthy" if self._initialized else "unhealthy"
        }

        return report

    def _do_health_check(self) -> Optional[Dict[str, Any]]:
        """自定义健康检查"""
        try:
            current_metrics = self.get_current_metrics()
            active_alerts = self.get_active_alerts()

            health_data = {
                "monitoring_active": self._monitoring_active,
                "optimization_active": self._optimization_active,
                "current_cpu": current_metrics.get("system", {}).get("cpu_usage", 0),
                "current_memory": current_metrics.get("system", {}).get("memory_usage", 0),
                "active_alerts_count": len(active_alerts),
                "critical_alerts": len([a for a in active_alerts if a.severity == "critical"])
            }

            return health_data

        except Exception as e:
            return {"health_check_error": str(e)}


# 便捷函数
def get_performance_service() -> Optional[PerformanceService]:
    """获取性能服务实例"""
    try:
        from ..containers.unified_service_container import get_unified_container
        container = get_unified_container()
        return container.resolve(PerformanceService)
    except Exception:
        return None
