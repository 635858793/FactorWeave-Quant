"""
智能数据路由器

提供智能数据源选择、负载均衡、故障转移等功能。
根据数据质量、响应时间、可用性等因素智能选择最优数据源。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd

from loguru import logger
from core.plugin_types import AssetType, DataType
from core.data_source_extensions import IDataSourcePlugin, HealthCheckResult
from core.tet_data_pipeline import StandardQuery, StandardData

logger = logger.bind(module=__name__)


class RoutingStrategy(Enum):
    """路由策略"""
    QUALITY_FIRST = "quality_first"        # 质量优先
    SPEED_FIRST = "speed_first"            # 速度优先
    BALANCED = "balanced"                  # 平衡策略
    ROUND_ROBIN = "round_robin"            # 轮询
    FAILOVER = "failover"                  # 故障转移
    COST_OPTIMIZED = "cost_optimized"      # 成本优化


@dataclass
class DataSourceMetrics:
    """数据源性能指标"""
    plugin_id: str

    # 性能指标
    avg_response_time: float = 0.0      # 平均响应时间(秒)
    success_rate: float = 1.0           # 成功率
    data_quality_score: float = 1.0     # 数据质量分数
    availability: float = 1.0           # 可用性

    # 统计信息
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # 时间信息
    last_request_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None

    # 健康状态
    is_healthy: bool = True
    health_check_time: Optional[datetime] = None

    # 负载信息
    current_load: int = 0               # 当前并发请求数
    max_concurrent_requests: int = 10   # 最大并发请求数

    # 成本信息（可选）
    cost_per_request: float = 0.0       # 每请求成本
    rate_limit: Optional[int] = None    # 速率限制（请求/分钟）

    def update_metrics(self, response_time: float, success: bool, quality_score: float = None):
        """更新性能指标"""
        self.total_requests += 1
        self.last_request_time = datetime.now()

        if success:
            self.successful_requests += 1
            self.last_success_time = datetime.now()

            # 更新平均响应时间（指数移动平均）
            alpha = 0.1  # 平滑因子
            if self.avg_response_time == 0:
                self.avg_response_time = response_time
            else:
                self.avg_response_time = alpha * response_time + (1 - alpha) * self.avg_response_time

            # 更新数据质量分数
            if quality_score is not None:
                if self.data_quality_score == 1.0:
                    self.data_quality_score = quality_score
                else:
                    self.data_quality_score = alpha * quality_score + (1 - alpha) * self.data_quality_score
        else:
            self.failed_requests += 1
            self.last_failure_time = datetime.now()

        # 更新成功率
        self.success_rate = self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0


@dataclass
class RoutingRule:
    """路由规则"""
    data_type: DataType
    asset_type: AssetType
    preferred_sources: List[str] = field(default_factory=list)
    fallback_sources: List[str] = field(default_factory=list)
    strategy: RoutingStrategy = RoutingStrategy.BALANCED

    # 条件配置
    min_quality_score: float = 0.8
    max_response_time: float = 5.0
    min_success_rate: float = 0.95

    # 权重配置
    quality_weight: float = 0.4
    speed_weight: float = 0.3
    availability_weight: float = 0.3


class IntelligentDataRouter:
    """
    智能数据路由器

    提供智能数据源选择功能：
    - 基于性能指标的智能路由
    - 负载均衡和故障转移
    - 动态健康检查
    - 路由规则配置
    - 性能监控和优化
    """

    def __init__(self):
        # 数据源管理
        self.registered_plugins: Dict[str, IDataSourcePlugin] = {}
        self.plugin_metrics: Dict[str, DataSourceMetrics] = {}

        # 路由配置
        self.routing_rules: Dict[Tuple[DataType, AssetType], RoutingRule] = {}
        self.default_strategy = RoutingStrategy.BALANCED

        # 监控状态
        self._monitoring_active = False
        self._monitor_thread = None
        self._lock = threading.RLock()

        # 性能统计
        self.routing_stats = {
            'total_routes': 0,
            'successful_routes': 0,
            'failed_routes': 0,
            'avg_routing_time': 0.0
        }

        logger.info("智能数据路由器初始化完成")

    def register_plugin(self, plugin_id: str, plugin: IDataSourcePlugin):
        """注册数据源插件"""
        try:
            with self._lock:
                self.registered_plugins[plugin_id] = plugin
                self.plugin_metrics[plugin_id] = DataSourceMetrics(plugin_id=plugin_id)

            logger.info(f"数据源插件已注册: {plugin_id}")

        except Exception as e:
            logger.error(f"注册数据源插件失败: {plugin_id}, {e}")

    def unregister_plugin(self, plugin_id: str):
        """注销数据源插件"""
        try:
            with self._lock:
                if plugin_id in self.registered_plugins:
                    del self.registered_plugins[plugin_id]
                if plugin_id in self.plugin_metrics:
                    del self.plugin_metrics[plugin_id]

            logger.info(f"数据源插件已注销: {plugin_id}")

        except Exception as e:
            logger.error(f"注销数据源插件失败: {plugin_id}, {e}")

    def add_routing_rule(self, data_type: DataType, asset_type: AssetType, rule: RoutingRule):
        """添加路由规则"""
        try:
            key = (data_type, asset_type)
            self.routing_rules[key] = rule

            logger.info(f"路由规则已添加: {data_type.value} - {asset_type.value}")

        except Exception as e:
            logger.error(f"添加路由规则失败: {e}")

    def start_monitoring(self):
        """启动健康监控"""
        try:
            if self._monitoring_active:
                logger.warning("数据路由监控已在运行")
                return

            self._monitoring_active = True
            self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitor_thread.start()

            logger.info("数据路由监控已启动")

        except Exception as e:
            logger.error(f"启动数据路由监控失败: {e}")

    def stop_monitoring(self):
        """停止健康监控"""
        try:
            self._monitoring_active = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)

            logger.info("数据路由监控已停止")

        except Exception as e:
            logger.error(f"停止数据路由监控失败: {e}")

    def _monitoring_loop(self):
        """监控循环"""
        while self._monitoring_active:
            try:
                # 执行健康检查
                self._perform_health_checks()

                # 更新可用性指标
                self._update_availability_metrics()

                # 清理过期统计
                self._cleanup_old_stats()

                # 等待下一轮检查
                threading.Event().wait(30)  # 每30秒检查一次

            except Exception as e:
                logger.error(f"路由监控循环异常: {e}")
                threading.Event().wait(10)

    async def route_data_request(self, query: StandardQuery) -> Tuple[str, IDataSourcePlugin]:
        """
        智能路由数据请求

        Args:
            query: 标准查询对象

        Returns:
            Tuple[str, IDataSourcePlugin]: (插件ID, 插件实例)

        Raises:
            Exception: 无可用数据源时抛出异常
        """
        start_time = time.time()

        try:
            # 获取路由规则
            rule = self._get_routing_rule(query.data_type, query.asset_type)

            # 获取候选数据源
            candidates = self._get_candidate_plugins(query, rule)

            if not candidates:
                raise Exception(f"无可用数据源: {query.data_type.value} - {query.asset_type.value}")

            # 根据策略选择最优数据源
            selected_plugin_id = self._select_optimal_plugin(candidates, rule)
            selected_plugin = self.registered_plugins[selected_plugin_id]

            # 更新负载计数
            with self._lock:
                self.plugin_metrics[selected_plugin_id].current_load += 1

            # 更新统计
            routing_time = time.time() - start_time
            self._update_routing_stats(True, routing_time)

            logger.debug(f"数据请求路由完成: {selected_plugin_id} (耗时: {routing_time:.3f}s)")
            return selected_plugin_id, selected_plugin

        except Exception as e:
            routing_time = time.time() - start_time
            self._update_routing_stats(False, routing_time)
            logger.error(f"数据请求路由失败: {e}")
            raise

    def report_request_result(self, plugin_id: str, response_time: float, success: bool, quality_score: float = None):
        """报告请求结果"""
        try:
            with self._lock:
                if plugin_id in self.plugin_metrics:
                    metrics = self.plugin_metrics[plugin_id]
                    metrics.update_metrics(response_time, success, quality_score)

                    # 减少负载计数
                    metrics.current_load = max(0, metrics.current_load - 1)

                    logger.debug(f"请求结果已记录: {plugin_id} - 成功: {success}, 响应时间: {response_time:.3f}s")

        except Exception as e:
            logger.error(f"报告请求结果失败: {plugin_id}, {e}")

    def _get_routing_rule(self, data_type: DataType, asset_type: AssetType) -> RoutingRule:
        """获取路由规则"""
        key = (data_type, asset_type)

        if key in self.routing_rules:
            return self.routing_rules[key]

        # 返回默认规则
        return RoutingRule(
            data_type=data_type,
            asset_type=asset_type,
            strategy=self.default_strategy
        )

    def _get_candidate_plugins(self, query: StandardQuery, rule: RoutingRule) -> List[str]:
        """获取候选插件列表"""
        candidates = []

        with self._lock:
            # 首先检查首选数据源
            for plugin_id in rule.preferred_sources:
                if self._is_plugin_suitable(plugin_id, query, rule):
                    candidates.append(plugin_id)

            # 如果首选数据源不够，检查所有注册的插件
            if len(candidates) < 2:
                for plugin_id in self.registered_plugins.keys():
                    if plugin_id not in candidates and self._is_plugin_suitable(plugin_id, query, rule):
                        candidates.append(plugin_id)

            # 最后检查备用数据源
            for plugin_id in rule.fallback_sources:
                if plugin_id not in candidates and self._is_plugin_suitable(plugin_id, query, rule):
                    candidates.append(plugin_id)

        return candidates

    def _is_plugin_suitable(self, plugin_id: str, query: StandardQuery, rule: RoutingRule) -> bool:
        """检查插件是否适合处理查询"""
        try:
            if plugin_id not in self.registered_plugins:
                return False

            plugin = self.registered_plugins[plugin_id]
            metrics = self.plugin_metrics.get(plugin_id)

            if not metrics:
                return True  # 新插件，给予机会

            # 检查健康状态
            if not metrics.is_healthy:
                return False

            # 检查性能指标
            if metrics.data_quality_score < rule.min_quality_score:
                return False

            if metrics.avg_response_time > rule.max_response_time:
                return False

            if metrics.success_rate < rule.min_success_rate:
                return False

            # 检查负载
            if metrics.current_load >= metrics.max_concurrent_requests:
                return False

            # 检查插件能力（这里需要根据实际插件接口实现）
            # plugin_info = plugin.get_plugin_info()
            # if query.data_type not in plugin_info.capabilities.get('data_types', []):
            #     return False

            return True

        except Exception as e:
            logger.error(f"检查插件适用性失败: {plugin_id}, {e}")
            return False

    def _select_optimal_plugin(self, candidates: List[str], rule: RoutingRule) -> str:
        """选择最优插件"""
        try:
            if not candidates:
                raise Exception("无候选插件")

            if len(candidates) == 1:
                return candidates[0]

            strategy = rule.strategy

            if strategy == RoutingStrategy.QUALITY_FIRST:
                return self._select_by_quality(candidates)

            elif strategy == RoutingStrategy.SPEED_FIRST:
                return self._select_by_speed(candidates)

            elif strategy == RoutingStrategy.BALANCED:
                return self._select_by_balanced_score(candidates, rule)

            elif strategy == RoutingStrategy.ROUND_ROBIN:
                return self._select_by_round_robin(candidates)

            elif strategy == RoutingStrategy.FAILOVER:
                return self._select_by_failover(candidates)

            elif strategy == RoutingStrategy.COST_OPTIMIZED:
                return self._select_by_cost(candidates)

            else:
                # 默认使用平衡策略
                return self._select_by_balanced_score(candidates, rule)

        except Exception as e:
            logger.error(f"选择最优插件失败: {e}")
            return candidates[0]  # 返回第一个候选插件

    def _select_by_quality(self, candidates: List[str]) -> str:
        """按质量选择"""
        best_plugin = candidates[0]
        best_score = 0.0

        with self._lock:
            for plugin_id in candidates:
                metrics = self.plugin_metrics.get(plugin_id)
                if metrics and metrics.data_quality_score > best_score:
                    best_score = metrics.data_quality_score
                    best_plugin = plugin_id

        return best_plugin

    def _select_by_speed(self, candidates: List[str]) -> str:
        """按速度选择"""
        best_plugin = candidates[0]
        best_time = float('inf')

        with self._lock:
            for plugin_id in candidates:
                metrics = self.plugin_metrics.get(plugin_id)
                if metrics and metrics.avg_response_time < best_time:
                    best_time = metrics.avg_response_time
                    best_plugin = plugin_id

        return best_plugin

    def _select_by_balanced_score(self, candidates: List[str], rule: RoutingRule) -> str:
        """按平衡分数选择"""
        best_plugin = candidates[0]
        best_score = -1.0

        with self._lock:
            for plugin_id in candidates:
                metrics = self.plugin_metrics.get(plugin_id)
                if not metrics:
                    continue

                # 计算综合分数
                quality_score = metrics.data_quality_score * rule.quality_weight

                # 速度分数（响应时间越小分数越高）
                speed_score = (1.0 / (1.0 + metrics.avg_response_time)) * rule.speed_weight

                # 可用性分数
                availability_score = metrics.success_rate * rule.availability_weight

                total_score = quality_score + speed_score + availability_score

                if total_score > best_score:
                    best_score = total_score
                    best_plugin = plugin_id

        return best_plugin

    def _select_by_round_robin(self, candidates: List[str]) -> str:
        """轮询选择"""
        # 简单的轮询实现
        current_time = int(time.time())
        index = current_time % len(candidates)
        return candidates[index]

    def _select_by_failover(self, candidates: List[str]) -> str:
        """故障转移选择"""
        # 选择成功率最高的
        best_plugin = candidates[0]
        best_success_rate = 0.0

        with self._lock:
            for plugin_id in candidates:
                metrics = self.plugin_metrics.get(plugin_id)
                if metrics and metrics.success_rate > best_success_rate:
                    best_success_rate = metrics.success_rate
                    best_plugin = plugin_id

        return best_plugin

    def _select_by_cost(self, candidates: List[str]) -> str:
        """按成本选择"""
        best_plugin = candidates[0]
        best_cost = float('inf')

        with self._lock:
            for plugin_id in candidates:
                metrics = self.plugin_metrics.get(plugin_id)
                if metrics and metrics.cost_per_request < best_cost:
                    best_cost = metrics.cost_per_request
                    best_plugin = plugin_id

        return best_plugin

    def _perform_health_checks(self):
        """执行健康检查"""
        try:
            for plugin_id, plugin in self.registered_plugins.items():
                try:
                    from utils.async_utils import run_async_blocking
                    health_result = run_async_blocking(plugin.health_check())

                    with self._lock:
                        if plugin_id in self.plugin_metrics:
                            metrics = self.plugin_metrics[plugin_id]
                            metrics.is_healthy = health_result.is_healthy
                            metrics.health_check_time = datetime.now()

                            if not health_result.is_healthy:
                                logger.warning(f"插件健康检查失败: {plugin_id} - {health_result.message}")

                except Exception as e:
                    logger.error(f"插件健康检查异常: {plugin_id}, {e}")
                    with self._lock:
                        if plugin_id in self.plugin_metrics:
                            self.plugin_metrics[plugin_id].is_healthy = False

        except Exception as e:
            logger.error(f"执行健康检查失败: {e}")

    def _update_availability_metrics(self):
        """更新可用性指标"""
        try:
            current_time = datetime.now()

            with self._lock:
                for plugin_id, metrics in self.plugin_metrics.items():
                    # 计算最近1小时的可用性
                    if metrics.last_request_time:
                        time_diff = (current_time - metrics.last_request_time).total_seconds()

                        # 如果超过1小时没有请求，重置一些指标
                        if time_diff > 3600:
                            metrics.current_load = 0

        except Exception as e:
            logger.error(f"更新可用性指标失败: {e}")

    def _cleanup_old_stats(self):
        """清理过期统计"""
        try:
            # 这里可以添加清理逻辑，比如清理过期的性能统计
            pass
        except Exception as e:
            logger.error(f"清理过期统计失败: {e}")

    def _update_routing_stats(self, success: bool, routing_time: float):
        """更新路由统计"""
        try:
            self.routing_stats['total_routes'] += 1

            if success:
                self.routing_stats['successful_routes'] += 1
            else:
                self.routing_stats['failed_routes'] += 1

            # 更新平均路由时间
            total_routes = self.routing_stats['total_routes']
            current_avg = self.routing_stats['avg_routing_time']
            self.routing_stats['avg_routing_time'] = (current_avg * (total_routes - 1) + routing_time) / total_routes

        except Exception as e:
            logger.error(f"更新路由统计失败: {e}")

    def get_plugin_metrics(self, plugin_id: str = None) -> Union[DataSourceMetrics, Dict[str, DataSourceMetrics]]:
        """获取插件性能指标"""
        try:
            with self._lock:
                if plugin_id:
                    return self.plugin_metrics.get(plugin_id)
                else:
                    return self.plugin_metrics.copy()

        except Exception as e:
            logger.error(f"获取插件性能指标失败: {e}")
            return {} if not plugin_id else None

    def get_routing_stats(self) -> Dict[str, Any]:
        """获取路由统计"""
        try:
            stats = self.routing_stats.copy()

            # 计算成功率
            total_routes = stats['total_routes']
            if total_routes > 0:
                stats['success_rate'] = stats['successful_routes'] / total_routes
                stats['failure_rate'] = stats['failed_routes'] / total_routes
            else:
                stats['success_rate'] = 0.0
                stats['failure_rate'] = 0.0

            return stats

        except Exception as e:
            logger.error(f"获取路由统计失败: {e}")
            return {}

    def generate_routing_report(self) -> Dict[str, Any]:
        """生成路由报告"""
        try:
            report = {
                'generated_at': datetime.now().isoformat(),
                'routing_statistics': self.get_routing_stats(),
                'plugin_metrics': {},
                'routing_rules_count': len(self.routing_rules),
                'registered_plugins_count': len(self.registered_plugins)
            }

            # 添加插件指标
            with self._lock:
                for plugin_id, metrics in self.plugin_metrics.items():
                    report['plugin_metrics'][plugin_id] = {
                        'avg_response_time': metrics.avg_response_time,
                        'success_rate': metrics.success_rate,
                        'data_quality_score': metrics.data_quality_score,
                        'availability': metrics.availability,
                        'total_requests': metrics.total_requests,
                        'current_load': metrics.current_load,
                        'is_healthy': metrics.is_healthy,
                        'last_request_time': metrics.last_request_time.isoformat() if metrics.last_request_time else None
                    }

            return report

        except Exception as e:
            logger.error(f"生成路由报告失败: {e}")
            return {'error': f'生成报告失败: {e}'}

    def cleanup(self):
        """清理资源"""
        try:
            self.stop_monitoring()
            with self._lock:
                self.registered_plugins.clear()
                self.plugin_metrics.clear()
                self.routing_rules.clear()
            logger.info("智能数据路由器资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
