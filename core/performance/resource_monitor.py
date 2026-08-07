#!/usr/bin/env python3
"""
统一资源监控器
监控系统资源使用情况，限制资源使用，触发资源告警，提供资源使用报告
"""

import time
import threading
from typing import Dict, List, Optional, Callable, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from collections import defaultdict, deque
from loguru import logger

from PyQt5.QtCore import QObject, pyqtSignal

from core.events.types import BaseEvent

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil 不可用，资源监控功能将受限")

class ResourceType(Enum):
    """资源类型"""
    CPU = auto()
    MEMORY = auto()
    DISK = auto()
    NETWORK = auto()
    THREAD = auto()

class AlertSeverity(Enum):
    """告警严重程度"""
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

@dataclass
class ResourceThreshold:
    """资源阈值"""
    resource_type: ResourceType
    warning_threshold: float
    critical_threshold: float
    description: str = ""

    def check(self, value: float) -> Tuple[AlertSeverity, float]:
        """
        检查资源使用是否超过阈值
        Args:
            value: 资源使用值
        Returns:
            (告警严重程度, 超出阈值百分比)
        """
        if value >= self.critical_threshold:
            exceed_percent = (value - self.critical_threshold) / self.critical_threshold * 100
            return AlertSeverity.CRITICAL, exceed_percent
        elif value >= self.warning_threshold:
            exceed_percent = (value - self.warning_threshold) / self.warning_threshold * 100
            return AlertSeverity.WARNING, exceed_percent
        else:
            return AlertSeverity.INFO, 0.0

@dataclass
class ResourceAlert:
    """资源告警"""
    alert_id: str
    resource_type: ResourceType
    severity: AlertSeverity
    current_value: float
    threshold_value: float
    exceed_percent: float
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'resource_type': self.resource_type.name,
            'severity': self.severity.name,
            'current_value': self.current_value,
            'threshold_value': self.threshold_value,
            'exceed_percent': self.exceed_percent,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'acknowledged': self.acknowledged
        }

@dataclass
class ResourceUsage:
    """资源使用情况"""
    resource_type: ResourceType
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'resource_type': self.resource_type.name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat()
        }

# R243-B-001 (2026-08-04): ResourceAlertEvent 从局部类提升为模块级类
# Why: 原类在 _create_alert 内每次告警重新定义, 类名一致但违反事件类型全局定义惯例;
#      订阅端 (alert_event_handler.py:456) 只能按字符串 'ResourceAlertEvent' 匹配
# Fix: 模块级定义, 供 EventBus 去重键 (_get_event_key) 与订阅端稳定引用
class ResourceAlertEvent(BaseEvent):
    """资源告警事件"""
    def __init__(self, alert: "ResourceAlert"):
        super().__init__()
        self.alert = alert

class UnifiedResourceMonitor(QObject):
    """
    统一资源监控器
    功能：
    1. 监控CPU、内存、网络使用情况
    2. 限制资源使用
    3. 触发资源告警
    4. 提供资源使用报告
    """

    # 信号
    resource_alert = pyqtSignal(str, ResourceAlert)  # 资源告警信号
    resource_usage_updated = pyqtSignal(ResourceUsage)  # 资源使用更新信号
    threshold_exceeded = pyqtSignal(ResourceType, float, float)  # 阈值超出信号
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, monitor_interval: float = 5.0):
        """
        初始化资源监控器

        Args:
            monitor_interval: 监控间隔（秒）
        """
        if self._initialized:
            return

        super().__init__()

        self._initialized = True
        self._monitor_interval = monitor_interval
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 资源阈值配置
        self._thresholds: Dict[ResourceType, ResourceThreshold] = {
            ResourceType.CPU: ResourceThreshold(
                resource_type=ResourceType.CPU,
                warning_threshold=80.0,
                critical_threshold=95.0,
                description="CPU使用率"
            ),
            ResourceType.MEMORY: ResourceThreshold(
                resource_type=ResourceType.MEMORY,
                warning_threshold=85.0,
                critical_threshold=95.0,
                description="内存使用率"
            ),
            ResourceType.DISK: ResourceThreshold(
                resource_type=ResourceType.DISK,
                warning_threshold=90.0,
                critical_threshold=98.0,
                description="磁盘使用率"
            )
        }

        # 资源使用历史
        self._usage_history: Dict[ResourceType, deque] = {
            ResourceType.CPU: deque(maxlen=100),
            ResourceType.MEMORY: deque(maxlen=100),
            ResourceType.DISK: deque(maxlen=100),
            ResourceType.NETWORK: deque(maxlen=100)
        }

        # 告警历史
        self._alert_history: deque = deque(maxlen=1000)
        self._alert_counter = 0

        # 统计信息
        self._stats = {
            'total_alerts': 0,
            'critical_alerts': 0,
            'warning_alerts': 0,
            'info_alerts': 0,
            'monitoring_time': 0.0
        }

        # 事件总线引用（延迟加载）
        self._event_bus = None

        # R237 HVD-237-B-004: dispose 幂等标志 (R78 铁律 #6)
        self._disposed = False

        logger.info(f"统一资源监控器已初始化，监控间隔: {monitor_interval}s")

    def set_event_bus(self, event_bus):
        """设置事件总线"""
        self._event_bus = event_bus

    def set_threshold(self, resource_type: ResourceType, warning_threshold: float, critical_threshold: float):
        """
        设置资源阈值
        Args:
            resource_type: 资源类型
            warning_threshold: 警告阈值
            critical_threshold: 严重阈值
        """
        self._thresholds[resource_type] = ResourceThreshold(
            resource_type=resource_type,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            description=resource_type.name
        )

        logger.info(f"资源阈值已更新: {resource_type.name}, 警告: {warning_threshold}%, 严重: {critical_threshold}%")

    def start(self):
        """启动资源监控"""
        if self._running:
            logger.warning("资源监控器已在运行")
            return

        if not PSUTIL_AVAILABLE:
            logger.warning("psutil 不可用，无法启动资源监控")
            return

        self._running = True
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        logger.info("资源监控器已启动")

    def stop(self):
        """停止资源监控"""
        if not self._running:
            logger.warning("资源监控器未运行")
            return

        self._running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)

        logger.info("资源监控器已停止")

    def _monitor_loop(self):
        """监控循环"""
        start_time = time.time()

        while self._running:
            try:
                # 监控CPU
                cpu_usage = self._monitor_cpu()
                if cpu_usage is not None:
                    self._check_threshold(ResourceType.CPU, cpu_usage)

                # 监控内存
                memory_usage = self._monitor_memory()
                if memory_usage is not None:
                    self._check_threshold(ResourceType.MEMORY, memory_usage)

                # 监控磁盘
                disk_usage = self._monitor_disk()
                if disk_usage is not None:
                    self._check_threshold(ResourceType.DISK, disk_usage)

                # 监控网络
                network_usage = self._monitor_network()
                if network_usage is not None:
                    pass  # 网络使用率通常不设置阈值

                # 更新统计信息
                self._stats['monitoring_time'] = time.time() - start_time

                # 等待下一次监控
                self._stop_event.wait(self._monitor_interval)

            except Exception as e:
                logger.error(f"资源监控循环错误: {e}")

    def _monitor_cpu(self) -> Optional[float]:
        """监控CPU使用率"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            usage = ResourceUsage(
                resource_type=ResourceType.CPU,
                value=cpu_percent,
                unit="%"
            )

            self._usage_history[ResourceType.CPU].append(usage)
            self.resource_usage_updated.emit(usage)

            logger.debug(f"CPU使用率: {cpu_percent:.1f}%")
            return cpu_percent

        except Exception as e:
            logger.error(f"监控CPU失败: {e}")
            return None

    def _monitor_memory(self) -> Optional[float]:
        """监控内存使用率"""
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            usage = ResourceUsage(
                resource_type=ResourceType.MEMORY,
                value=memory_percent,
                unit="%"
            )

            self._usage_history[ResourceType.MEMORY].append(usage)
            self.resource_usage_updated.emit(usage)

            logger.debug(f"内存使用率: {memory_percent:.1f}%")
            return memory_percent

        except Exception as e:
            logger.error(f"监控内存失败: {e}")
            return None

    def _monitor_disk(self) -> Optional[float]:
        """监控磁盘使用率"""
        try:
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent

            usage = ResourceUsage(
                resource_type=ResourceType.DISK,
                value=disk_percent,
                unit="%"
            )

            self._usage_history[ResourceType.DISK].append(usage)
            self.resource_usage_updated.emit(usage)

            logger.debug(f"磁盘使用率: {disk_percent:.1f}%")
            return disk_percent

        except Exception as e:
            logger.error(f"监控磁盘失败: {e}")
            return None

    def _monitor_network(self) -> Optional[Dict[str, float]]:
        """监控网络使用情况"""
        try:
            network = psutil.net_io_counters()
            sent_mb = network.bytes_sent / 1024 / 1024
            recv_mb = network.bytes_recv / 1024 / 1024

            usage = ResourceUsage(
                resource_type=ResourceType.NETWORK,
                value=sent_mb + recv_mb,
                unit="MB"
            )

            self._usage_history[ResourceType.NETWORK].append(usage)
            self.resource_usage_updated.emit(usage)

            logger.debug(f"网络使用: 发送 {sent_mb:.2f}MB, 接收 {recv_mb:.2f}MB")
            return {'sent': sent_mb, 'recv': recv_mb}

        except Exception as e:
            logger.error(f"监控网络失败: {e}")
            return None

    def _check_threshold(self, resource_type: ResourceType, value: float):
        """
        检查资源使用是否超过阈值
        Args:
            resource_type: 资源类型
            value: 资源使用值
        """
        if resource_type not in self._thresholds:
            return

        threshold = self._thresholds[resource_type]
        severity, exceed_percent = threshold.check(value)

        if severity != AlertSeverity.INFO:
            self._create_alert(resource_type, severity, value, threshold, exceed_percent)

    def _create_alert(self,
                     resource_type: ResourceType,
                     severity: AlertSeverity,
                     current_value: float,
                     threshold: ResourceThreshold,
                     exceed_percent: float):
        """
        创建告警

        Args:
            resource_type: 资源类型
            severity: 告警严重程度
            current_value: 当前值
            threshold: 阈值
            exceed_percent: 超出阈值百分比
        """
        try:
            self._alert_counter += 1
            alert_id = f"alert_{self._alert_counter}"

            threshold_value = threshold.critical_threshold if severity == AlertSeverity.CRITICAL else threshold.warning_threshold

            alert = ResourceAlert(
                alert_id=alert_id,
                resource_type=resource_type,
                severity=severity,
                current_value=current_value,
                threshold_value=threshold_value,
                exceed_percent=exceed_percent,
                message=f"{threshold.description}超过{severity.name}阈值: {current_value:.1f}% > {threshold_value:.1f}%"
            )

            self._alert_history.append(alert)

            # 更新统计信息
            self._stats['total_alerts'] += 1
            if severity == AlertSeverity.CRITICAL:
                self._stats['critical_alerts'] += 1
            elif severity == AlertSeverity.WARNING:
                self._stats['warning_alerts'] += 1
            else:
                self._stats['info_alerts'] += 1

            # 发送信号
            self.resource_alert.emit(alert_id, alert)
            self.threshold_exceeded.emit(resource_type, current_value, threshold_value)

            # 发布事件 (R243-B-001: 使用模块级 ResourceAlertEvent, 替代原局部类)
            if self._event_bus:
                try:
                    event = ResourceAlertEvent(alert)
                    self._event_bus.publish(event)
                except Exception as e:
                    logger.debug(f"发布资源告警事件失败: {e}")

            logger.warning(f"资源告警: {alert.message}")

        except Exception as e:
            logger.error(f"创建告警失败: {e}")

    def get_current_usage(self, resource_type: ResourceType) -> Optional[ResourceUsage]:
        """
        获取当前资源使用情况

        Args:
            resource_type: 资源类型

        Returns:
            资源使用情况
        """
        if not PSUTIL_AVAILABLE:
            return None

        try:
            if resource_type == ResourceType.CPU:
                value = psutil.cpu_percent(interval=0.1)
                unit = "%"
            elif resource_type == ResourceType.MEMORY:
                value = psutil.virtual_memory().percent
                unit = "%"
            elif resource_type == ResourceType.DISK:
                value = psutil.disk_usage('/').percent
                unit = "%"
            elif resource_type == ResourceType.NETWORK:
                network = psutil.net_io_counters()
                value = (network.bytes_sent + network.bytes_recv) / 1024 / 1024
                unit = "MB"
            else:
                return None

            return ResourceUsage(
                resource_type=resource_type,
                value=value,
                unit=unit
            )

        except Exception as e:
            logger.error(f"获取资源使用情况失败: {e}")
            return None

    def get_usage_history(self, resource_type: ResourceType, limit: int = 100) -> List[ResourceUsage]:
        """
        获取资源使用历史

        Args:
            resource_type: 资源类型
            limit: 限制数量

        Returns:
            资源使用历史
        """
        if resource_type not in self._usage_history:
            return []

        history = list(self._usage_history[resource_type])
        return history[-limit:] if limit > 0 else history

    def get_alert_history(self, limit: int = 100) -> List[ResourceAlert]:
        """
        获取告警历史

        Args:
            limit: 限制数量

        Returns:
            告警历史
        """
        history = list(self._alert_history)
        return history[-limit:] if limit > 0 else history

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            'monitoring': self._running,
            'monitor_interval': self._monitor_interval,
            'thresholds': {
                rt.name: {
                    'warning': t.warning_threshold,
                    'critical': t.critical_threshold
                }
                for rt, t in self._thresholds.items()
            }
        }

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        确认告警

        Args:
            alert_id: 告警ID

        Returns:
            是否确认成功
        """
        try:
            for alert in self._alert_history:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    logger.info(f"告警已确认: {alert_id}")
                    return True

            logger.warning(f"告警不存在: {alert_id}")
            return False

        except Exception as e:
            logger.error(f"确认告警失败: {alert_id}, 错误: {e}")
            return False

    # ========================================================================
    # R237 HVD-237-B-004: 4 链 dispose 治理 (R78 铁律)
    # 业务影响: 2-3 业务方 (GracefulShutdown.py:192, SystemMonitorTab, R10 启动期线程)
    # 业务资源: _usage_history / _alert_history / _stats / _monitor_thread
    # ========================================================================
    def dispose(self) -> None:
        """R237 HVD-237-B-004: 4 链 dispose 入口 (R78 铁律 #6 幂等短路)"""
        if getattr(self, '_disposed', False):
            return
        try:
            self.shutdown()
            self.close()
            self.cleanup()
        except Exception as e:
            logger.warning(
                f"UnifiedResourceMonitor.dispose 异常: {e}",
                exc_info=True,
            )
        finally:
            self._disposed = True

    def shutdown(self) -> None:
        """R237 HVD-237-B-004: shutdown - 监控线程停止 + 业务数据清空"""
        try:
            # 1) 优先调用现有 stop 方法 (R235 子智能体 B 候选特征: 有 stop 但未接入统一链)
            if hasattr(self, 'stop') and callable(getattr(self, 'stop')):
                try:
                    self.stop()
                except Exception:
                    pass
            # 2) 业务数据清空
            if hasattr(self, '_usage_history') and isinstance(self._usage_history, dict):
                for q in self._usage_history.values():
                    if hasattr(q, 'clear'):
                        q.clear()
            if hasattr(self, '_alert_history') and hasattr(self._alert_history, 'clear'):
                self._alert_history.clear()
        except Exception as e:
            logger.warning(
                f"UnifiedResourceMonitor.shutdown 异常: {e}",
                exc_info=True,
            )

    def close(self) -> None:
        """R237 HVD-237-B-004: close - 统计重置 + QObject 信号 disconnect"""
        try:
            # 重置 _stats
            if hasattr(self, '_stats') and isinstance(self._stats, dict):
                for k in self._stats:
                    if isinstance(self._stats[k], (int, float)):
                        self._stats[k] = 0
            # 释放 _event_bus 引用
            if hasattr(self, '_event_bus'):
                self._event_bus = None
        except Exception as e:
            logger.warning(
                f"UnifiedResourceMonitor.close 异常: {e}",
                exc_info=True,
            )

    def cleanup(self) -> None:
        """R237 HVD-237-B-004: cleanup - 监控配置 + 阈值引用置 None"""
        try:
            # 释放 _thresholds 引用 (重建时重新初始化)
            if hasattr(self, '_thresholds'):
                self._thresholds = None
            # 释放 _monitor_thread 引用
            if hasattr(self, '_monitor_thread'):
                self._monitor_thread = None
            # 释放 _stop_event 引用
            if hasattr(self, '_stop_event'):
                self._stop_event = None
        except Exception as e:
            logger.warning(
                f"UnifiedResourceMonitor.cleanup 异常: {e}",
                exc_info=True,
            )


# 全局实例
_resource_monitor_instance: Optional[UnifiedResourceMonitor] = None
_resource_monitor_lock = threading.Lock()

def get_resource_monitor() -> UnifiedResourceMonitor:
    """获取资源监控器实例"""
    global _resource_monitor_instance

    if _resource_monitor_instance is None:
        with _resource_monitor_lock:
            if _resource_monitor_instance is None:
                _resource_monitor_instance = UnifiedResourceMonitor()

    return _resource_monitor_instance

def initialize_resource_monitor(monitor_interval: float = 5.0, event_bus=None) -> UnifiedResourceMonitor:
    """初始化资源监控器"""
    monitor = get_resource_monitor()
    monitor.set_event_bus(event_bus)
    return monitor
