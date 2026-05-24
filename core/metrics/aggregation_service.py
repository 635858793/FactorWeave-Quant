# core/metrics/aggregation_service.py
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from threading import Lock, Thread
import json

from ..events import EventBus
from .events import SystemResourceUpdated, ApplicationMetricRecorded
from .repository import MetricsRepository
from loguru import logger


class MetricsAggregationService:
    """
    指标聚合服务

    负责聚合和处理系统和应用程序性能指标，提供历史趋势分析和报警功能。
    """

    def __init__(self, event_bus: Optional[EventBus] = None, repository: Optional[MetricsRepository] = None):
        """
        初始化指标聚合服务

        Args:
            event_bus: 事件总线
            repository: 指标数据仓储
        """
        self.event_bus = event_bus
        self.repository = repository
        self.aggregation_interval = 60  # 聚合间隔（秒）

        # 移除硬编码的告警阈值，改为使用专业的告警规则引擎
        # 告警判断现在由 AlertRuleEngine 统一处理
        # self.alert_thresholds = {
        #     "cpu": 80.0,  # CPU使用率阈值
        #     "memory": 80.0,  # 内存使用率阈值
        #     "disk": 90.0,  # 磁盘使用率阈值
        #     "operation_time": 5.0,  # 操作响应时间阈值（秒）
        #     "error_rate": 0.1  # 错误率阈值
        # }

        # 资源指标缓存
        self.resource_metrics = {
            "cpu": [],
            "memory": [],
            "disk": []
        }

        # 应用指标缓存
        self.app_metrics: Dict[str, List[Dict[str, Any]]] = {}

        self._lock = Lock()
        self._stop_event = threading.Event()
        self._aggregation_thread: Optional[Thread] = None

        # 注册事件处理器
        if self.event_bus:
            self.event_bus.subscribe(
                SystemResourceUpdated, self._handle_resource_update)
            self.event_bus.subscribe(
                ApplicationMetricRecorded, self._handle_app_metric)

    def start(self) -> None:
        """启动聚合服务"""
        if self._aggregation_thread is not None and self._aggregation_thread.is_alive():
            logger.warning("指标聚合服务已在运行")
            return

        self._stop_event.clear()
        self._aggregation_thread = Thread(
            target=self._aggregation_loop,
            daemon=True,
            name="MetricsAggregationThread"
        )
        self._aggregation_thread.start()
        logger.info("指标聚合服务已启动")

    def stop(self) -> None:
        """停止聚合服务"""
        if self._aggregation_thread is None or not self._aggregation_thread.is_alive():
            return

        self._stop_event.set()
        self._aggregation_thread.join(timeout=5.0)
        logger.info("指标聚合服务已停止")

    def _handle_resource_update(self, event: SystemResourceUpdated) -> None:
        """
        处理系统资源更新事件

        Args:
            event: 系统资源更新事件
        """
        with self._lock:
            self.resource_metrics["cpu"].append({
                "value": event.cpu_percent,
                "timestamp": time.time()
            })

            self.resource_metrics["memory"].append({
                "value": event.memory_percent,
                "timestamp": time.time()
            })

            self.resource_metrics["disk"].append({
                "value": event.disk_percent,
                "timestamp": time.time()
            })

            # 检查是否超过阈值
            self._check_resource_thresholds(event)

            # 存储到仓储
            if self.repository:
                self.repository.store_metric(
                    metric_name="cpu_usage",
                    value=event.cpu_percent,
                    category="system"
                )

                self.repository.store_metric(
                    metric_name="memory_usage",
                    value=event.memory_percent,
                    category="system"
                )

                self.repository.store_metric(
                    metric_name="disk_usage",
                    value=event.disk_percent,
                    category="system"
                )

    def _handle_app_metric(self, event: ApplicationMetricRecorded) -> None:
        """
        处理应用指标记录事件

        Args:
            event: 应用指标记录事件
        """
        with self._lock:
            operation_name = event.operation_name

            if operation_name not in self.app_metrics:
                self.app_metrics[operation_name] = []

            self.app_metrics[operation_name].append({
                "duration": event.duration,
                "success": event.was_successful,
                "timestamp": time.time()
            })

            # 检查是否超过阈值
            self._check_app_thresholds(event)

            # 存储到仓储
            if self.repository:
                self.repository.store_metric(
                    metric_name=f"operation.{operation_name}",
                    value=event.duration,
                    category="application",
                    metadata={
                        "success": str(event.was_successful)
                    }
                )

    def _aggregation_loop(self) -> None:
        """聚合循环"""
        while not self._stop_event.is_set():
            try:
                # 等待下一个聚合间隔
                self._stop_event.wait(self.aggregation_interval)
                if self._stop_event.is_set():
                    break

                # 执行聚合
                self._aggregate_metrics()

            except Exception as e:
                logger.error(f"指标聚合过程中出错: {e}")

    def _aggregate_metrics(self) -> None:
        """聚合指标数据"""
        with self._lock:
            # 聚合资源指标
            aggregated_resources = self._aggregate_resource_metrics()

            # 聚合应用指标
            aggregated_apps = self._aggregate_app_metrics()

            # 清理旧数据
            self._clean_old_metrics()

            # 发布聚合结果
            if self.event_bus:
                try:
                    # 创建事件数据对象
                    event_data = {
                        "resources": aggregated_resources,
                        "applications": aggregated_apps,
                        "timestamp": time.time()
                    }
                    # 使用正确的参数调用 publish - 使用关键字参数而不是位置参数
                    self.event_bus.publish("MetricsAggregated", **event_data)
                except Exception as e:
                    logger.error(f"发布聚合指标事件失败: {e}")

    def _aggregate_resource_metrics(self) -> Dict[str, Dict[str, float]]:
        """
        聚合资源指标

        Returns:
            聚合结果
        """
        result = {}

        for resource_type, metrics in self.resource_metrics.items():
            if not metrics:
                continue

            # 计算平均值、最大值、最小值
            values = [m["value"] for m in metrics]
            result[resource_type] = {
                "avg": sum(values) / len(values),
                "max": max(values),
                "min": min(values),
                "count": len(values)
            }

        return result

    def _aggregate_app_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        聚合应用指标

        Returns:
            聚合结果
        """
        result = {}

        for operation_name, metrics in self.app_metrics.items():
            if not metrics:
                continue

            # 计算平均响应时间、最大响应时间、错误率
            durations = [m["duration"] for m in metrics]
            success_count = sum(1 for m in metrics if m["success"])

            result[operation_name] = {
                "avg_duration": sum(durations) / len(durations),
                "max_duration": max(durations),
                "min_duration": min(durations),
                "call_count": len(metrics),
                "error_count": len(metrics) - success_count,
                "error_rate": (len(metrics) - success_count) / len(metrics)
            }

        return result

    def _clean_old_metrics(self) -> None:
        """清理旧指标数据"""
        # 保留最近10分钟的数据
        cutoff_time = time.time() - (10 * 60)

        # 清理资源指标
        for resource_type in self.resource_metrics:
            self.resource_metrics[resource_type] = [
                m for m in self.resource_metrics[resource_type]
                if m["timestamp"] >= cutoff_time
            ]

        # 清理应用指标
        for operation_name in self.app_metrics:
            self.app_metrics[operation_name] = [
                m for m in self.app_metrics[operation_name]
                if m["timestamp"] >= cutoff_time
            ]

    def _check_resource_thresholds(self, event: SystemResourceUpdated) -> None:
        """
        检查资源指标是否超过阈值

        注意：此方法已被重构，不再进行硬编码的阈值检查。
        告警判断现在由专业的 AlertRuleEngine 统一处理，支持：
        - 数据库配置的告警规则
        - 动态阈值调整
        - 规则优先级管理
        - 告警去重和静默期

        Args:
            event: 系统资源更新事件
        """
        # 移除硬编码的告警阈值检查逻辑
        # 告警判断现在由 AlertRuleEngine 统一处理
        # 这样可以避免重复告警，并支持更灵活的规则配置

        logger.debug(f"资源指标更新: CPU={event.cpu_percent:.1f}%, "
                 f"内存={event.memory_percent:.1f}%, "
                 f"磁盘={event.disk_percent:.1f}%")

        # 通过 EventBus 发出阈值超标告警事件，重新连通已废弃的告警调用链
        # 下游订阅者（如 AlertRuleEngine、UI通知组件）可监听这些事件进行处理
        if event.cpu_percent > 80 or event.memory_percent > 80 or event.disk_percent > 90:
            if self.event_bus:
                try:
                    self.event_bus.publish("ResourceThresholdExceeded",
                        cpu_percent=event.cpu_percent,
                        memory_percent=event.memory_percent,
                        disk_percent=event.disk_percent,
                        timestamp=time.time()
                    )
                    logger.info(f"发布资源阈值超标告警: CPU={event.cpu_percent:.1f}%, "
                                f"内存={event.memory_percent:.1f}%, 磁盘={event.disk_percent:.1f}%")
                except Exception as pub_error:
                    logger.error(f"发布资源告警事件失败: {pub_error}")

    def _check_app_thresholds(self, event: ApplicationMetricRecorded) -> None:
        """
        检查应用指标是否超过阈值

        注意：此方法已被重构，不再进行硬编码的阈值检查。
        应用指标告警判断现在由专业的 AlertRuleEngine 统一处理。

        Args:
            event: 应用指标记录事件
        """
        # 移除硬编码的应用指标告警阈值检查逻辑
        # 应用指标告警判断现在由 AlertRuleEngine 统一处理

        logger.debug(f"应用指标记录: 操作={event.operation_name}, "
                 f"持续时间={event.duration:.2f}秒, "
                 f"成功={event.was_successful}")

        # 通过 EventBus 发出应用指标阈值超标告警事件，重新连通已废弃的告警调用链
        if event.duration > 5.0 or not event.was_successful:
            if self.event_bus:
                try:
                    self.event_bus.publish("ApplicationThresholdExceeded",
                        operation_name=event.operation_name,
                        duration=event.duration,
                        was_successful=event.was_successful,
                        timestamp=time.time()
                    )
                    logger.info(f"发布应用阈值超标告警: 操作={event.operation_name}, "
                                f"耗时={event.duration:.2f}秒, 成功={event.was_successful}")
                except Exception as pub_error:
                    logger.error(f"发布应用告警事件失败: {pub_error}")

    def set_aggregation_interval(self, interval: int) -> None:
        """
        设置聚合间隔

        Args:
            interval: 聚合间隔（秒）
        """
        self.aggregation_interval = max(10, interval)  # 最小10秒

    # def set_alert_threshold(self, metric_name: str, value: float) -> bool:  # 已废弃
    def _deprecated_set_alert_threshold(self, metric_name: str, value: float) -> bool:
        """
        设置告警阈值

        注意：此方法已被废弃，告警阈值现在通过 AlertRuleEngine 管理。
        请使用 AlertRuleEngine 的配置接口来设置告警规则。

        Args:
            metric_name: 指标名称
            value: 阈值

        Returns:
            是否设置成功
        """
        logger.warning(f"set_alert_threshold 方法已废弃，请使用 AlertRuleEngine 配置告警规则")
        return False

    # def get_alert_thresholds(self) -> Dict[str, float]:  # 已废弃
    def _deprecated_get_alert_thresholds(self) -> Dict[str, float]:
        """
        获取告警阈值

        注意：此方法已被废弃，告警阈值现在通过 AlertRuleEngine 管理。
        请使用 AlertRuleEngine 的配置接口来获取告警规则。

        Returns:
            告警阈值字典
        """
        logger.warning(f"get_alert_thresholds 方法已废弃，请使用 AlertRuleEngine 获取告警规则")
        return {}

    def get_recent_metrics(self) -> Dict[str, Any]:
        """
        获取最近的指标数据

        Returns:
            指标数据
        """
        with self._lock:
            # 获取最近的资源指标
            recent_resources = {}
            for resource_type, metrics in self.resource_metrics.items():
                if metrics:
                    recent_resources[resource_type] = metrics[-1]["value"]

            # 获取聚合的应用指标
            app_metrics = self._aggregate_app_metrics()

            return {
                "resources": recent_resources,
                "applications": app_metrics,
                "timestamp": time.time()
            }

    def dispose(self) -> None:
        """释放资源"""
        self.stop()

        # 取消事件订阅
        if self.event_bus:
            try:
                self.event_bus.unsubscribe(
                    SystemResourceUpdated, self._handle_resource_update)
                self.event_bus.unsubscribe(
                    ApplicationMetricRecorded, self._handle_app_metric)
            except Exception as e:
                logger.error(f"取消事件订阅失败: {e}")
