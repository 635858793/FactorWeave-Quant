from loguru import logger
"""
数据源智能路由模块

实现高可用的数据源路由策略，包括健康检查、负载均衡、故障切换等功能。
基于Circuit Breaker模式设计，确保系统的稳定性和高可用性。

作者: FactorWeave-Quant 开发团队
版本: 1.0.0
日期: 2024
"""

import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import random
import pandas as pd
from collections import defaultdict, deque

# 导入项目模块
from .plugin_types import AssetType, DataType
from .data_source_extensions import DataSourcePluginAdapter, HealthCheckResult


class RoutingStrategy(Enum):
    """路由策略枚举"""
    PRIORITY = "priority"                    # 优先级路由
    ROUND_ROBIN = "round_robin"              # 轮询路由
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"  # 加权轮询
    HEALTH_BASED = "health_based"            # 基于健康状态路由
    LEAST_CONNECTIONS = "least_connections"  # 最少连接数路由
    RANDOM = "random"                        # 随机路由
    CIRCUIT_BREAKER = "circuit_breaker"      # 熔断器路由


class CircuitBreakerState(Enum):
    """熔断器状态枚举"""
    CLOSED = "closed"        # 关闭状态，正常工作
    OPEN = "open"            # 开启状态，拒绝请求
    HALF_OPEN = "half_open"  # 半开状态，试探性请求


@dataclass
class DataSourceMetrics:
    """数据源性能指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    current_connections: int = 0
    health_score: float = 1.0        # 健康分数 0.0-1.0
    weight: float = 1.0              # 权重

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def failure_rate(self) -> float:
        """失败率"""
        return 1.0 - self.success_rate


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 15          # 失败阈值
    failure_rate_threshold: float = 0.5  # 失败率阈值
    recovery_timeout_ms: int = 60000     # 恢复超时时间（毫秒）
    half_open_max_calls: int = 3         # 半开状态最大调用次数
    sliding_window_size: int = 10        # 滑动窗口大小
    timeout_ms: int = 5000               # 请求超时时间


@dataclass
class RoutingRequest:
    """路由请求"""
    asset_type: AssetType
    data_type: DataType
    symbol: str
    priority: int = 0
    timeout_ms: int = 5000
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class IRoutingStrategy(ABC):
    """路由策略接口"""

    @abstractmethod
    def select_data_source(self,
                           available_sources: List[str],
                           request: RoutingRequest,
                           metrics: Dict[str, DataSourceMetrics]) -> Optional[str]:
        """
        选择数据源

        Args:
            available_sources: 可用数据源列表
            request: 路由请求
            metrics: 数据源指标

        Returns:
            选中的数据源ID，如果没有可用数据源则返回None
        """
        pass


class PriorityRoutingStrategy(IRoutingStrategy):
    """优先级路由策略"""

    def __init__(self, priorities: Dict[str, int]):
        """
        初始化优先级路由策略

        Args:
            priorities: 数据源优先级映射 {source_id: priority}，数字越小优先级越高
        """
        self.priorities = priorities

    def select_data_source(self,
                           available_sources: List[str],
                           request: RoutingRequest,
                           metrics: Dict[str, DataSourceMetrics]) -> Optional[str]:
        if not available_sources:
            return None

        # 按优先级排序，考虑健康状态
        sorted_sources = sorted(
            available_sources,
            key=lambda x: (
                self.priorities.get(x, 999),  # 优先级（越小越优先）
                -metrics.get(x, DataSourceMetrics()).health_score  # 健康分数（越大越好）
            )
        )

        return sorted_sources[0]


class RoundRobinRoutingStrategy(IRoutingStrategy):
    """轮询路由策略"""

    def __init__(self):
        self._current_index = 0
        self._lock = threading.Lock()

    def select_data_source(self,
                           available_sources: List[str],
                           request: RoutingRequest,
                           metrics: Dict[str, DataSourceMetrics]) -> Optional[str]:
        if not available_sources:
            return None

        with self._lock:
            # 过滤健康的数据源
            healthy_sources = [
                source for source in available_sources
                if metrics.get(source, DataSourceMetrics()).health_score > 0.5
            ]

            if not healthy_sources:
                healthy_sources = available_sources  # 如果没有健康的，使用所有可用的

            source = healthy_sources[self._current_index % len(healthy_sources)]
            self._current_index += 1
            return source


class WeightedRoundRobinRoutingStrategy(IRoutingStrategy):
    """加权轮询路由策略"""

    def __init__(self, weights: Dict[str, float]):
        """
        初始化加权轮询策略

        Args:
            weights: 数据源权重映射 {source_id: weight}
        """
        self.weights = weights
        self._current_weights = {}
        self._lock = threading.Lock()

    def select_data_source(self,
                           available_sources: List[str],
                           request: RoutingRequest,
                           metrics: Dict[str, DataSourceMetrics]) -> Optional[str]:
        if not available_sources:
            return None

        with self._lock:
            # 更新当前权重
            total_weight = 0
            for source in available_sources:
                weight = self.weights.get(source, 1.0)
                health_score = metrics.get(source, DataSourceMetrics()).health_score
                effective_weight = weight * health_score

                self._current_weights[source] = self._current_weights.get(source, 0) + effective_weight
                total_weight += effective_weight

            if total_weight == 0:
                return available_sources[0]

            # 选择当前权重最大的数据源
            selected = max(available_sources, key=lambda x: self._current_weights.get(x, 0))

            # 减少选中数据源的当前权重
            self._current_weights[selected] -= total_weight

            return selected


class HealthBasedRoutingStrategy(IRoutingStrategy):
    """基于健康状态的路由策略"""

    def select_data_source(self,
                           available_sources: List[str],
                           request: RoutingRequest,
                           metrics: Dict[str, DataSourceMetrics]) -> Optional[str]:
        if not available_sources:
            return None

        # 根据健康分数和响应时间选择最佳数据源
        def scoring_function(source_id: str) -> float:
            metric = metrics.get(source_id, DataSourceMetrics())
            # 综合健康分数、成功率和响应时间
            health_score = metric.health_score * 0.4
            success_rate_score = metric.success_rate * 0.4
            # 响应时间越低越好，转换为分数
            response_time_score = max(0, 1 - metric.avg_response_time_ms / 10000) * 0.2

            return health_score + success_rate_score + response_time_score

        return max(available_sources, key=scoring_function)


class CircuitBreaker:
    """熔断器实现"""

    def __init__(self, source_id: str, config: CircuitBreakerConfig):
        self.source_id = source_id
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0
        self.request_history = deque(maxlen=config.sliding_window_size)
        self._lock = threading.RLock()

    def can_execute(self) -> bool:
        """检查是否可以执行请求"""
        with self._lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            elif self.state == CircuitBreakerState.OPEN:
                # 检查是否应该进入半开状态
                if (self.last_failure_time and
                        (datetime.now() - self.last_failure_time).total_seconds() * 1000 > self.config.recovery_timeout_ms):
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 0
                    logger.info(f"熔断器 {self.source_id} 进入半开状态")
                    return True
                return False
            else:  # HALF_OPEN
                return self.half_open_calls < self.config.half_open_max_calls

    def record_success(self):
        """记录成功请求"""
        with self._lock:
            self.request_history.append(True)

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_max_calls:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    logger.info(f"熔断器 {self.source_id} 恢复到关闭状态")

            self._update_failure_count()

    def record_failure(self):
        """记录失败请求"""
        with self._lock:
            self.request_history.append(False)
            self.last_failure_time = datetime.now()

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"熔断器 {self.source_id} 重新开启")

            self._update_failure_count()

            # 检查是否应该开启熔断器
            if (self.state == CircuitBreakerState.CLOSED and
                    self._should_trip()):
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"熔断器 {self.source_id} 开启，失败次数: {self.failure_count}")

    def _update_failure_count(self):
        """更新失败计数"""
        recent_failures = sum(1 for success in self.request_history if not success)
        self.failure_count = recent_failures

    def _should_trip(self) -> bool:
        """判断是否应该开启熔断器"""
        if len(self.request_history) < self.config.sliding_window_size:
            return False

        failure_rate = self.failure_count / len(self.request_history)
        return (self.failure_count >= self.config.failure_threshold or
                failure_rate >= self.config.failure_rate_threshold)

    def force_open(self) -> None:
        """R277: 立即开启熔断（确定性故障如连接失败，不等滑动窗口统计）

        正常熔断需要 sliding_window_size 次请求后才评估失败率，单次连接失败
        永远不会触发（failure_count 最高=窗口大小 < threshold）。对"连接失败"
        这类确定性故障，直接置 OPEN 并填满失败历史，恢复期后进入 HALF_OPEN
        由实际请求验证是否恢复。
        """
        with self._lock:
            self.state = CircuitBreakerState.OPEN
            self.last_failure_time = datetime.now()
            for _ in range(self.config.sliding_window_size):
                self.request_history.append(False)
            logger.warning(f"熔断器 {self.source_id} 因确定性故障立即开启")


class DataSourceRouter:
    """
    数据源智能路由器

    实现多种路由策略，支持健康检查、负载均衡、故障切换等功能。
    基于Circuit Breaker模式确保系统高可用性。
    """

    def __init__(self,
                 default_strategy: RoutingStrategy = RoutingStrategy.PRIORITY,
                 circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
                 health_check_interval: int = 30):
        """
        初始化数据源路由器

        Args:
            default_strategy: 默认路由策略
            circuit_breaker_config: 熔断器配置
            health_check_interval: 健康检查间隔（秒）
        """
        self.default_strategy = default_strategy
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.health_check_interval = health_check_interval

        # 数据源管理
        self.data_sources: Dict[str, DataSourcePluginAdapter] = {}
        self.metrics: Dict[str, DataSourceMetrics] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}

        # R279 快速失败熔断：连续失败计数（无需等待统计型滑动窗口即熔断）
        self._consecutive_failures: Dict[str, int] = {}
        self._fast_fail_threshold = 3  # 连续失败 3 次即视为确定性故障，即时熔断

        # 路由策略
        self.routing_strategies: Dict[RoutingStrategy, IRoutingStrategy] = {}
        self._init_default_strategies()

        # 数据源优先级配置
        self.asset_priorities: Dict[AssetType, List[str]] = {}

        # 线程安全
        self._lock = threading.RLock()

        # 健康检查线程
        self._health_check_thread = None
        self._health_check_stop_event = threading.Event()

        # 事件回调
        self.on_source_health_changed: Optional[Callable[[str, bool], None]] = None
        self.on_routing_failed: Optional[Callable[[RoutingRequest, str], None]] = None

        logger.info("DataSourceRouter初始化完成")

    def _init_default_strategies(self):
        """初始化默认路由策略"""
        self.routing_strategies[RoutingStrategy.ROUND_ROBIN] = RoundRobinRoutingStrategy()
        self.routing_strategies[RoutingStrategy.HEALTH_BASED] = HealthBasedRoutingStrategy()

    def register_data_source(self,
                             source_id: str,
                             adapter: DataSourcePluginAdapter,
                             priority: int = 0,
                             weight: float = 1.0) -> bool:
        """
        注册数据源

        Args:
            source_id: 数据源ID
            adapter: 数据源适配器
            priority: 优先级（数字越小优先级越高）
            weight: 权重

        Returns:
            bool: 注册是否成功
        """
        try:
            with self._lock:
                if source_id in self.data_sources:
                    logger.warning(f"数据源 {source_id} 已存在，将被覆盖")

                self.data_sources[source_id] = adapter
                self.metrics[source_id] = DataSourceMetrics(weight=weight)
                # R279 修复：重复注册保留既有熔断器（含 OPEN/HALF_OPEN 状态与失败历史）。
                # 此前无条件新建 CircuitBreaker 会把已熔断的源重置为 CLOSED，
                # 插件加载/数据源同步/插件发现等重复注册点都会让熔断状态"切换后失效"。
                if source_id not in self.circuit_breakers:
                    self.circuit_breakers[source_id] = CircuitBreaker(source_id, self.circuit_breaker_config)

                # 创建优先级策略（如果不存在）
                if RoutingStrategy.PRIORITY not in self.routing_strategies:
                    priorities = {sid: 0 for sid in self.data_sources.keys()}
                    self.routing_strategies[RoutingStrategy.PRIORITY] = PriorityRoutingStrategy(priorities)

                # 创建加权轮询策略（如果不存在）
                if RoutingStrategy.WEIGHTED_ROUND_ROBIN not in self.routing_strategies:
                    weights = {sid: metrics.weight for sid, metrics in self.metrics.items()}
                    self.routing_strategies[RoutingStrategy.WEIGHTED_ROUND_ROBIN] = WeightedRoundRobinRoutingStrategy(weights)

                logger.info(f"数据源 {source_id} 注册成功，优先级: {priority}, 权重: {weight}")

                # 启动健康检查线程（如果尚未启动）
                if not self._health_check_thread or not self._health_check_thread.is_alive():
                    self._start_health_check()

                return True

        except Exception as e:
            logger.error(f"注册数据源 {source_id} 失败: {str(e)}")
            return False

    def unregister_data_source(self, source_id: str) -> bool:
        """
        注销数据源

        Args:
            source_id: 数据源ID

        Returns:
            bool: 注销是否成功
        """
        try:
            with self._lock:
                if source_id not in self.data_sources:
                    logger.warning(f"数据源 {source_id} 不存在")
                    return False

                # 移除数据源
                del self.data_sources[source_id]
                del self.metrics[source_id]
                del self.circuit_breakers[source_id]

                # 从优先级配置中移除
                for asset_type in self.asset_priorities:
                    if source_id in self.asset_priorities[asset_type]:
                        self.asset_priorities[asset_type].remove(source_id)

                logger.info(f"数据源 {source_id} 注销成功")
                return True

        except Exception as e:
            logger.error(f"注销数据源 {source_id} 失败: {str(e)}")
            return False

    def get_data_source(self, source_id: str) -> Optional[DataSourcePluginAdapter]:
        """
        获取指定ID的数据源

        Args:
            source_id: 数据源ID

        Returns:
            Optional[DataSourcePluginAdapter]: 数据源适配器，如果不存在则返回None
        """
        try:
            with self._lock:
                adapter = self.data_sources.get(source_id)
                if adapter:
                    logger.debug(f"获取数据源 {source_id} 成功")
                    return adapter
                else:
                    logger.debug(f"数据源 {source_id} 不存在")
                    return None
        except Exception as e:
            logger.error(f"获取数据源 {source_id} 失败: {str(e)}")
            return None

    def get_all_data_sources(self) -> Dict[str, DataSourcePluginAdapter]:
        """
        获取所有注册的数据源

        Returns:
            Dict[str, DataSourcePluginAdapter]: 所有数据源的字典
        """
        try:
            with self._lock:
                return self.data_sources.copy()
        except Exception as e:
            logger.error(f"获取所有数据源失败: {str(e)}")
            return {}

    def is_data_source_available(self, source_id: str) -> bool:
        """
        检查数据源是否可用

        Args:
            source_id: 数据源ID

        Returns:
            bool: 是否可用
        """
        try:
            with self._lock:
                if source_id not in self.data_sources:
                    return False

                circuit_breaker = self.circuit_breakers.get(source_id)
                if not circuit_breaker:
                    return False

                return circuit_breaker.can_execute()
        except Exception as e:
            logger.error(f"检查数据源 {source_id} 可用性失败: {str(e)}")
            return False

    def set_asset_priorities(self, asset_type: AssetType, priorities: List[str]) -> None:
        """
        设置资产类型的数据源优先级

        Args:
            asset_type: 资产类型
            priorities: 数据源ID列表，按优先级排序
        """
        with self._lock:
            # 验证数据源是否存在
            valid_priorities = [sid for sid in priorities if sid in self.data_sources]
            self.asset_priorities[asset_type] = valid_priorities

            # 更新优先级策略
            if RoutingStrategy.PRIORITY in self.routing_strategies:
                priority_map = {}
                for i, source_id in enumerate(valid_priorities):
                    priority_map[source_id] = i
                self.routing_strategies[RoutingStrategy.PRIORITY] = PriorityRoutingStrategy(priority_map)

            logger.info(f"设置 {asset_type.value} 数据源优先级: {valid_priorities}")

    def route_request(self,
                      request: RoutingRequest,
                      strategy: Optional[RoutingStrategy] = None) -> Optional[str]:
        """
        路由请求到合适的数据源

        Args:
            request: 路由请求
            strategy: 路由策略（可选，默认使用配置的策略）

        Returns:
            选中的数据源ID，如果没有可用数据源则返回None
        """
        try:
            with self._lock:
                # 获取支持该资产类型的数据源
                available_sources = self._get_available_sources(request.asset_type)

                if not available_sources:
                    logger.warning(f"没有支持 {request.asset_type.value} 的数据源")
                    return None

                # 过滤通过熔断器检查的数据源
                healthy_sources = [
                    source_id for source_id in available_sources
                    if self.circuit_breakers[source_id].can_execute()
                ]

                if not healthy_sources:
                    logger.warning(f"所有支持 {request.asset_type.value} 的数据源都不可用")
                    return None

                # 进一步过滤：只选择已就绪的数据源（支持异步插件）
                ready_sources = []
                for source_id in healthy_sources:
                    try:
                        adapter = self.data_sources.get(source_id)
                        if adapter and adapter.is_connected():
                            ready_sources.append(source_id)
                        else:
                            logger.debug(f"数据源 {source_id} 尚未就绪，跳过")
                    except Exception as e:
                        logger.warning(f"检查数据源 {source_id} 就绪状态失败: {e}")

                # 如果没有就绪的数据源，使用健康的数据源（兼容旧插件）
                if not ready_sources:
                    logger.debug(f"没有已就绪的数据源，使用健康数据源（可能需要等待连接）")
                    ready_sources = healthy_sources

                # 选择路由策略
                routing_strategy = strategy or self.default_strategy
                strategy_impl = self.routing_strategies.get(routing_strategy)

                if not strategy_impl:
                    # 回退到优先级策略
                    strategy_impl = self.routing_strategies.get(RoutingStrategy.PRIORITY)
                    if not strategy_impl:
                        # 简单选择第一个可用的
                        return ready_sources[0]

                # 执行路由选择（使用就绪的数据源）
                selected_source = strategy_impl.select_data_source(
                    ready_sources, request, self.metrics
                )

                if selected_source:
                    logger.debug(f"路由策略 {routing_strategy.value} 选择数据源: {selected_source}")

                return selected_source

        except Exception as e:
            logger.error(f"路由请求失败: {str(e)}")
            if self.on_routing_failed:
                self.on_routing_failed(request, str(e))
            return None

    def record_request_result(self,
                              source_id: str,
                              success: bool,
                              response_time_ms: float = 0,
                              error: Optional[str] = None,
                              from_health_check: bool = False) -> None:
        """
        记录请求结果

        Args:
            source_id: 数据源ID
            success: 是否成功
            response_time_ms: 响应时间（毫秒）
            error: 错误信息（可选）
            from_health_check: 是否为健康检查线程产生的探测结果（R283）
        """
        try:
            with self._lock:
                if source_id not in self.metrics:
                    return

                metrics = self.metrics[source_id]
                circuit_breaker = self.circuit_breakers[source_id]

                # 更新指标
                metrics.total_requests += 1
                metrics.last_request_time = datetime.now()

                if success:
                    metrics.successful_requests += 1
                    # R283: 健康检查成功不推进熔断状态机、不清零连续失败计数。
                    # 1) 不清零 _consecutive_failures：健康检查线程每 30s 探测成功会把
                    #    快速熔断计数永久清零，真实故障源的连续失败永远到不了阈值；
                    # 2) 不调 record_success：HALF_OPEN 下 3 次成功会将熔断器恢复 CLOSED，
                    #    30s 探测周期 + 60s 恢复期 ≈ 90s 内"治愈"已熔断源，导致切换股票
                    #    时已发现不可用的源再次全量扫描。熔断恢复只能由真实业务请求成功触发。
                    if not from_health_check:
                        circuit_breaker.record_success()
                        self._consecutive_failures[source_id] = 0
                else:
                    metrics.failed_requests += 1
                    circuit_breaker.record_failure()
                    # R279 快速失败熔断：连续失败达到阈值即视为确定性故障即时熔断。
                    # 统计型熔断需 sliding_window_size(10) 次请求后才评估失败率，
                    # 单次/数次失败（空数据、超时、连接后拉取失败被吞成空）永不触发，
                    # 导致"切换股票后仍遍历不可用数据源"。连续失败特征是确定性故障，
                    # 达到阈值直接 force_open，恢复期后由实际请求验证是否恢复。
                    consecutive = self._consecutive_failures.get(source_id, 0) + 1
                    self._consecutive_failures[source_id] = consecutive
                    if consecutive >= self._fast_fail_threshold:
                        logger.warning(
                            f"数据源 {source_id} 连续失败 {consecutive} 次，触发快速熔断")
                        circuit_breaker.force_open()
                        self._consecutive_failures[source_id] = 0

                # 更新平均响应时间
                if response_time_ms > 0:
                    current_avg = metrics.avg_response_time_ms
                    total_success = metrics.successful_requests
                    if total_success > 0:
                        metrics.avg_response_time_ms = (
                            (current_avg * (total_success - 1) + response_time_ms) / total_success
                        )

                # 更新健康分数
                self._update_health_score(source_id)

        except Exception as e:
            logger.error(f"记录请求结果失败: {str(e)}")

    def mark_unavailable(self, source_id: str) -> None:
        """R277: 标记数据源即时不可用（连接失败等确定性故障）

        TET failover 中数据源连接失败（RemoteDisconnected 等）属于确定性故障，
        不应等待滑动窗口统计熔断。此处直接开启熔断器并更新健康分数，
        后续 get_available_sources 的 can_execute 过滤将剔除该源。
        """
        try:
            with self._lock:
                breaker = self.circuit_breakers.get(source_id)
                if breaker is not None:
                    breaker.force_open()
                metrics = self.metrics.get(source_id)
                if metrics is not None:
                    metrics.total_requests += 1
                    metrics.failed_requests += 1
                    metrics.last_request_time = datetime.now()
                self._consecutive_failures[source_id] = 0  # R279: 已即时熔断，清零连续计数
                self._update_health_score(source_id)
                logger.warning(f"数据源 {source_id} 已标记不可用（确定性故障即时熔断）")
        except Exception as e:
            logger.error(f"标记数据源不可用失败 {source_id}: {e}")

    def get_source_metrics(self, source_id: str) -> Optional[DataSourceMetrics]:
        """获取数据源指标"""
        with self._lock:
            return self.metrics.get(source_id)

    def get_all_metrics(self) -> Dict[str, DataSourceMetrics]:
        """获取所有数据源指标"""
        with self._lock:
            return self.metrics.copy()

    def get_circuit_breaker_state(self, source_id: str) -> Optional[CircuitBreakerState]:
        """获取熔断器状态"""
        with self._lock:
            circuit_breaker = self.circuit_breakers.get(source_id)
            return circuit_breaker.state if circuit_breaker else None

    def get_available_sources(self, routing_request) -> List[str]:
        """
        获取可用的数据源列表（公共接口）

        Args:
            routing_request: 路由请求对象，包含asset_type、data_type等信息

        Returns:
            List[str]: 可用数据源ID列表
        """
        try:
            asset_type = routing_request.asset_type
            data_type = getattr(routing_request, 'data_type', None)
            sources = self._get_available_sources(asset_type, data_type)
            # R275 修复：健康检测未在 TET 主链路生效——熔断过滤此前只存在于
            # route_request（仅 deprecated GUI 使用），TET failover 走本方法时
            # 仍会把熔断/不健康的插件纳入候选尝试。此处统一过滤 can_execute。
            healthy_sources = [
                sid for sid in sources
                if self.circuit_breakers.get(sid) is not None
                and self.circuit_breakers[sid].can_execute()
            ]
            if healthy_sources:
                return healthy_sources
            if sources:
                logger.warning(f"数据源 {sources} 全部处于熔断状态，TET failover 将快速失败")
            return healthy_sources
        except Exception as e:
            logger.error(f"获取可用数据源失败: {e}")
            return []

    def get_prioritized_sources(self, routing_request) -> List[str]:
        """R286 修复1：获取按"健康度 + 质量画像"排序的数据源候选列表

        与 get_available_sources（仅熔断过滤、默认源恒第一）不同：
        候选源按 健康度(health_score/success_rate/response_time) 与
        DataQualityRiskManager.get_source_risk_profile 近 7 天平均质量分
        加权排序，质量/健康度高者优先尝试——failover 不再是"顺序碰运气"，
        而是"优先使用被验证过的优质数据源"。

        Args:
            routing_request: 路由请求对象，包含asset_type、data_type等信息

        Returns:
            List[str]: 按质量/健康度降序的可用数据源ID列表
        """
        try:
            asset_type = routing_request.asset_type
            data_type = getattr(routing_request, 'data_type', None)
            sources = self._get_available_sources(asset_type, data_type)
            healthy_sources = [
                sid for sid in sources
                if self.circuit_breakers.get(sid) is not None
                and self.circuit_breakers[sid].can_execute()
            ]
            if not healthy_sources:
                if sources:
                    logger.warning(f"数据源 {sources} 全部处于熔断状态，TET failover 将快速失败")
                return healthy_sources

            # 各源近 7 天平均质量分（0-1），无画像的源给中性分 0.5（不惩罚也不奖励）
            quality_scores = self._get_source_quality_scores()

            def sort_key(source_id: str) -> Tuple[float, float]:
                metric = self.metrics.get(source_id, DataSourceMetrics())
                # 健康度：health_score + success_rate + 响应时间（与 HealthBasedRoutingStrategy 同构）
                health = (metric.health_score * 0.4
                          + metric.success_rate * 0.4
                          + max(0.0, 1.0 - metric.avg_response_time_ms / 10000.0) * 0.2)
                quality = quality_scores.get(source_id, 0.5)
                # 综合分：健康度为主(0.6)，质量画像为辅(0.4)；tie-break 用健康度
                return (health * 0.6 + quality * 0.4, health)

            prioritized = sorted(healthy_sources, key=sort_key, reverse=True)
            if prioritized != healthy_sources:
                logger.debug(f"R286 数据源质量加权排序: {prioritized}")
            return prioritized
        except Exception as e:
            logger.error(f"获取优先级数据源失败: {e}")
            return []

    def _get_source_quality_scores(self) -> Dict[str, float]:
        """R286 修复1：各数据源近 7 天平均质量分（0-1 归一化）

        数据来源：DataQualityRiskManager.get_source_risk_profile 聚合的
        risk_history（由 EnhancedDataQualityMonitor.monitor_data_quality
        在 TET 主链路按真实数据源写入）。无画像/评估失败 → 中性 0.5。
        """
        scores: Dict[str, float] = {}
        try:
            from core.data_quality_risk_manager import DataQualityRiskManager
            risk_manager = getattr(self, '_quality_manager', None)
            if risk_manager is None:
                risk_manager = DataQualityRiskManager()
                self._quality_manager = risk_manager
            for sid in self.data_sources:
                try:
                    profile = risk_manager.get_source_risk_profile(sid, days=7)
                    avg = profile.get('average_quality_score')
                    if avg is not None:
                        scores[sid] = max(0.0, min(1.0, float(avg) / 100.0))
                except Exception as source_error:
                    logger.debug(f"获取数据源 {sid} 质量画像失败: {source_error}")
        except Exception as e:
            logger.debug(f"初始化质量画像管理器失败: {e}")
        return scores

    def _get_available_sources(self, asset_type: AssetType,
                               data_type: Optional[DataType] = None) -> List[str]:
        """获取支持指定资产类型（及数据能力）的数据源

        R275：原实现仅按 asset_type 过滤，导致"仅实时"插件（如 level2）被列入
        历史 K 线候选、以及"仅历史"插件进入实时行情候选，逐一尝试失败后不仅
        浪费 per_source_timeout，还被误记失败而熔断。此处增加数据能力维度过滤。
        """
        available = []

        # 首先尝试使用配置的优先级
        if asset_type in self.asset_priorities:
            for sid in self.asset_priorities[asset_type]:
                if data_type is None or self._supports_data_type(sid, data_type):
                    available.append(sid)

        # 然后检查其他支持该资产类型的数据源
        for source_id, adapter in self.data_sources.items():
            if source_id not in available:
                try:
                    logger.debug(f"正在检查数据源 {source_id} 的插件信息...")
                    plugin_info = adapter.get_plugin_info()
                    logger.debug(f"数据源 {source_id} 插件信息获取成功，支持的资产类型: {plugin_info.supported_asset_types}")
                    if asset_type in plugin_info.supported_asset_types:
                        if data_type is not None and not self._supports_data_type(source_id, data_type):
                            logger.debug(f"数据源 {source_id} 不支持数据类型 {data_type}，跳过")
                            continue
                        available.append(source_id)
                        logger.debug(f"数据源 {source_id} 支持资产类型 {asset_type}")
                except Exception as e:
                    # R280 修复：部分注册对象并非完整插件实现（如 Level2Config/MiniQMTConfig
                    # 配置类、CryptoSentimentPlugin/ExordeSentimentPlugin 缺 plugin_info），
                    # get_plugin_info 抛 AttributeError。此类源无法确认支持该资产类型 → 跳过。
                    # 此前此处打印完整 traceback + 适配器类型调试信息，每次请求刷屏 ERROR。
                    logger.debug(f"数据源 {source_id} 无法获取插件信息（视为不支持，跳过）: {e}")

        return available

    def _supports_data_type(self, source_id: str, data_type: DataType) -> bool:
        """判断数据源是否声明支持指定数据类型

        无法获取插件信息/声明缺失时保守返回 True（不过滤），避免误伤。
        """
        try:
            adapter = self.data_sources.get(source_id)
            if adapter is None:
                return True
            plugin_info = adapter.get_plugin_info()
            supported = getattr(plugin_info, 'supported_data_types', None)
            if not supported:
                return True
            if data_type in supported:
                return True
            # 兼容字符串声明（如 'historical_kline'）
            return any(str(dt).lower() == data_type.value.lower()
                       or (isinstance(dt, str) and dt.lower() == data_type.value.lower())
                       for dt in supported)
        except Exception:
            return True

    def has_data_source(self, source_id: str) -> bool:
        """
        检查是否存在指定的数据源

        Args:
            source_id: 数据源ID

        Returns:
            bool: 数据源是否存在
        """
        return source_id in self.data_sources

    def _update_health_score(self, source_id: str) -> None:
        """更新健康分数"""
        metrics = self.metrics[source_id]
        circuit_breaker = self.circuit_breakers[source_id]

        # 基于成功率和熔断器状态计算健康分数
        success_rate_score = metrics.success_rate

        # 熔断器状态影响
        if circuit_breaker.state == CircuitBreakerState.OPEN:
            circuit_breaker_score = 0.0
        elif circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
            circuit_breaker_score = 0.5
        else:
            circuit_breaker_score = 1.0

        # 响应时间影响（响应时间越短越好）
        response_time_score = max(0, 1 - metrics.avg_response_time_ms / 10000)

        # 综合计算健康分数
        metrics.health_score = (
            success_rate_score * 0.5 +
            circuit_breaker_score * 0.3 +
            response_time_score * 0.2
        )

    def _start_health_check(self) -> None:
        """启动健康检查线程"""
        if self._health_check_thread and self._health_check_thread.is_alive():
            return

        self._health_check_stop_event.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_worker,
            name="DataSourceRouter-HealthCheck",
            daemon=True
        )
        self._health_check_thread.start()
        logger.info("健康检查线程已启动")

    def _health_check_worker(self) -> None:
        """健康检查工作线程"""
        while not self._health_check_stop_event.wait(self.health_check_interval):
            try:
                with self._lock:
                    for source_id, adapter in self.data_sources.items():
                        try:
                            # 执行健康检查
                            start_time = time.time()
                            health_result = adapter.health_check()
                            response_time = (time.time() - start_time) * 1000

                            # 记录结果（R283: 标记为健康检查来源，成功不清零真实请求的连续失败计数）
                            self.record_request_result(
                                source_id,
                                health_result.is_healthy,
                                response_time,
                                health_result.message,
                                from_health_check=True
                            )

                            # 触发健康状态变化事件
                            if self.on_source_health_changed:
                                self.on_source_health_changed(source_id, health_result.is_healthy)

                        except Exception as e:
                            logger.error(f"数据源 {source_id} 健康检查失败: {str(e)}")
                            self.record_request_result(source_id, False, 0, str(e), from_health_check=True)

            except Exception as e:
                logger.error(f"健康检查工作线程异常: {str(e)}")

    def stop_health_check(self) -> None:
        """停止健康检查"""
        if self._health_check_thread:
            self._health_check_stop_event.set()
            self._health_check_thread.join(timeout=5)
            logger.info("健康检查线程已停止")

    def shutdown(self) -> None:
        """关闭路由器"""
        logger.info("DataSourceRouter正在关闭...")
        self.stop_health_check()

        with self._lock:
            self.data_sources.clear()
            self.metrics.clear()
            self.circuit_breakers.clear()

        logger.info("DataSourceRouter已关闭")


# 导出的公共接口
__all__ = [
    'DataSourceRouter',
    'RoutingStrategy',
    'CircuitBreakerState',
    'CircuitBreakerConfig',
    'RoutingRequest',
    'DataSourceMetrics',
    'IRoutingStrategy',
    'PriorityRoutingStrategy',
    'RoundRobinRoutingStrategy',
    'WeightedRoundRobinRoutingStrategy',
    'HealthBasedRoutingStrategy',
    'CircuitBreaker'
]
