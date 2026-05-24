"""
指标依赖管理器

提供技术指标依赖关系分析、计算优化和增量更新功能。
支持复杂指标依赖图构建、循环依赖检测和计算路径优化。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import networkx as nx

from loguru import logger
from core.services.realtime_compute_engine import IndicatorType, IndicatorConfig, IndicatorValue

logger = logger.bind(module=__name__)


class DependencyType(Enum):
    """依赖类型"""
    DIRECT = "direct"           # 直接依赖
    INDIRECT = "indirect"       # 间接依赖
    CIRCULAR = "circular"       # 循环依赖
    CONDITIONAL = "conditional"  # 条件依赖


class ComputeStatus(Enum):
    """计算状态"""
    PENDING = "pending"         # 等待计算
    COMPUTING = "computing"     # 正在计算
    COMPLETED = "completed"     # 计算完成
    FAILED = "failed"          # 计算失败
    CACHED = "cached"          # 已缓存


@dataclass
class IndicatorDependency:
    """指标依赖关系"""
    source_indicator: str       # 源指标ID
    target_indicator: str       # 目标指标ID
    dependency_type: DependencyType

    # 依赖配置
    required_fields: List[str] = field(default_factory=list)  # 需要的字段
    lag_periods: int = 0        # 滞后期数
    condition: Optional[str] = None  # 依赖条件

    # 权重和优先级
    weight: float = 1.0         # 依赖权重
    priority: int = 100         # 优先级

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None


@dataclass
class ComputeNode:
    """计算节点"""
    indicator_id: str
    indicator_config: IndicatorConfig

    # 依赖信息
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

    # 计算状态
    status: ComputeStatus = ComputeStatus.PENDING
    last_computed: Optional[datetime] = None
    compute_duration: float = 0.0

    # 缓存信息
    cached_result: Optional[IndicatorValue] = None
    cache_expiry: Optional[datetime] = None

    # 统计信息
    compute_count: int = 0
    success_count: int = 0
    error_count: int = 0

    def is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self.cached_result or not self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry


@dataclass
class ComputeTask:
    """计算任务"""
    task_id: str
    indicator_id: str
    symbol: str
    data_point: Dict[str, Any]

    # 任务配置
    priority: int = 100
    force_recompute: bool = False

    # 任务状态
    status: ComputeStatus = ComputeStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 结果
    result: Optional[IndicatorValue] = None
    error: Optional[str] = None


class IndicatorDependencyManager:
    """
    指标依赖管理器

    提供指标依赖关系管理和计算优化：
    - 依赖关系图构建和维护
    - 循环依赖检测和处理
    - 计算顺序优化
    - 增量计算支持
    - 缓存管理和失效
    - 并行计算调度
    """

    def __init__(self, combination_manager: IndicatorCombinationManager):
        self.combination_manager = combination_manager

        # 依赖图管理
        self.dependency_graph = nx.DiGraph()
        self.compute_nodes: Dict[str, ComputeNode] = {}
        self.dependencies: Dict[str, List[IndicatorDependency]] = defaultdict(list)

        # 计算管理
        self.compute_queue: deque = deque()
        self.active_tasks: Dict[str, ComputeTask] = {}
        self.compute_cache: Dict[str, IndicatorValue] = {}

        # 配置
        self.max_concurrent_tasks = 10
        self.cache_ttl = timedelta(minutes=5)
        self.max_dependency_depth = 10

        # 状态管理
        self._computing_active = False
        self._compute_thread = None
        self._lock = threading.RLock()

        # 统计信息
        self.compute_stats = {
            'total_computations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'circular_dependencies_detected': 0,
            'avg_compute_time': 0.0
        }

        logger.info("指标依赖管理器初始化完成")

    def register_indicator(self, indicator_id: str, config: IndicatorConfig) -> bool:
        """注册指标"""
        try:
            with self._lock:
                # 创建计算节点
                node = ComputeNode(
                    indicator_id=indicator_id,
                    indicator_config=config
                )

                self.compute_nodes[indicator_id] = node

                # 添加到依赖图
                self.dependency_graph.add_node(indicator_id)

                # 分析依赖关系
                self._analyze_indicator_dependencies(indicator_id, config)

                logger.info(f"指标已注册: {indicator_id}")
                return True

        except Exception as e:
            logger.error(f"注册指标失败: {indicator_id}, {e}")
            return False

    def unregister_indicator(self, indicator_id: str) -> bool:
        """注销指标"""
        try:
            with self._lock:
                if indicator_id not in self.compute_nodes:
                    logger.warning(f"指标不存在: {indicator_id}")
                    return False

                # 移除依赖关系
                self._remove_indicator_dependencies(indicator_id)

                # 从依赖图中移除
                if self.dependency_graph.has_node(indicator_id):
                    self.dependency_graph.remove_node(indicator_id)

                # 移除计算节点
                del self.compute_nodes[indicator_id]

                # 清理缓存
                self._clear_indicator_cache(indicator_id)

                logger.info(f"指标已注销: {indicator_id}")
                return True

        except Exception as e:
            logger.error(f"注销指标失败: {indicator_id}, {e}")
            return False

    def add_dependency(self, source_indicator: str, target_indicator: str,
                       dependency_type: DependencyType = DependencyType.DIRECT,
                       required_fields: List[str] = None, lag_periods: int = 0) -> bool:
        """添加依赖关系"""
        try:
            with self._lock:
                # 检查指标是否存在
                if source_indicator not in self.compute_nodes or target_indicator not in self.compute_nodes:
                    logger.error(f"指标不存在: {source_indicator} -> {target_indicator}")
                    return False

                # 创建依赖对象
                dependency = IndicatorDependency(
                    source_indicator=source_indicator,
                    target_indicator=target_indicator,
                    dependency_type=dependency_type,
                    required_fields=required_fields or [],
                    lag_periods=lag_periods
                )

                # 添加到依赖列表
                self.dependencies[target_indicator].append(dependency)

                # 更新依赖图
                self.dependency_graph.add_edge(source_indicator, target_indicator)

                # 更新计算节点
                self.compute_nodes[source_indicator].dependents.append(target_indicator)
                self.compute_nodes[target_indicator].dependencies.append(source_indicator)

                # 检查循环依赖
                if self._has_circular_dependency():
                    logger.warning(f"检测到循环依赖: {source_indicator} -> {target_indicator}")
                    self.compute_stats['circular_dependencies_detected'] += 1

                logger.info(f"依赖关系已添加: {source_indicator} -> {target_indicator}")
                return True

        except Exception as e:
            logger.error(f"添加依赖关系失败: {e}")
            return False

    def remove_dependency(self, source_indicator: str, target_indicator: str) -> bool:
        """移除依赖关系"""
        try:
            with self._lock:
                # 移除依赖列表中的记录
                target_deps = self.dependencies.get(target_indicator, [])
                self.dependencies[target_indicator] = [
                    dep for dep in target_deps
                    if dep.source_indicator != source_indicator
                ]

                # 更新依赖图
                if self.dependency_graph.has_edge(source_indicator, target_indicator):
                    self.dependency_graph.remove_edge(source_indicator, target_indicator)

                # 更新计算节点
                if source_indicator in self.compute_nodes:
                    dependents = self.compute_nodes[source_indicator].dependents
                    if target_indicator in dependents:
                        dependents.remove(target_indicator)

                if target_indicator in self.compute_nodes:
                    dependencies = self.compute_nodes[target_indicator].dependencies
                    if source_indicator in dependencies:
                        dependencies.remove(source_indicator)

                logger.info(f"依赖关系已移除: {source_indicator} -> {target_indicator}")
                return True

        except Exception as e:
            logger.error(f"移除依赖关系失败: {e}")
            return False

    async def compute_indicator(self, indicator_id: str, symbol: str,
                                data_point: Dict[str, Any], force_recompute: bool = False) -> Optional[IndicatorValue]:
        """计算指标值"""
        try:
            # 检查缓存
            if not force_recompute:
                cached_result = self._get_cached_result(indicator_id, symbol)
                if cached_result:
                    self.compute_stats['cache_hits'] += 1
                    return cached_result

            self.compute_stats['cache_misses'] += 1

            # 创建计算任务
            task_id = f"{indicator_id}_{symbol}_{datetime.now().timestamp()}"
            task = ComputeTask(
                task_id=task_id,
                indicator_id=indicator_id,
                symbol=symbol,
                data_point=data_point,
                force_recompute=force_recompute
            )

            # 执行计算
            result = await self._execute_compute_task(task)

            # 缓存结果
            if result:
                self._cache_result(indicator_id, symbol, result)

            return result

        except Exception as e:
            logger.error(f"计算指标失败: {indicator_id}, {e}")
            return None

    async def compute_indicator_batch(self, requests: List[Dict[str, Any]]) -> Dict[str, IndicatorValue]:
        """批量计算指标"""
        try:
            results = {}

            # 分析依赖关系并排序
            compute_order = self._determine_compute_order(requests)

            # 按顺序执行计算
            for indicator_id, symbol, data_point in compute_order:
                result = await self.compute_indicator(indicator_id, symbol, data_point)
                if result:
                    results[f"{indicator_id}_{symbol}"] = result

            return results

        except Exception as e:
            logger.error(f"批量计算指标失败: {e}")
            return {}

    def _analyze_indicator_dependencies(self, indicator_id: str, config: IndicatorConfig):
        """分析指标依赖关系"""
        try:
            # 根据指标类型分析依赖
            if config.indicator_type == IndicatorType.EMA:
                # EMA可能依赖于价格数据或其他MA
                pass
            elif config.indicator_type == IndicatorType.MACD:
                # MACD依赖于EMA
                fast_ema_id = f"ema_{config.params.get('fast_period', 12)}_{config.symbol}"
                slow_ema_id = f"ema_{config.params.get('slow_period', 26)}_{config.symbol}"

                # 如果这些EMA指标存在，添加依赖
                if fast_ema_id in self.compute_nodes:
                    self.add_dependency(fast_ema_id, indicator_id)
                if slow_ema_id in self.compute_nodes:
                    self.add_dependency(slow_ema_id, indicator_id)

            # 可以根据需要添加更多指标类型的依赖分析

        except Exception as e:
            logger.error(f"分析指标依赖失败: {e}")

    def _remove_indicator_dependencies(self, indicator_id: str):
        """移除指标的所有依赖关系"""
        try:
            # 移除作为目标的依赖
            if indicator_id in self.dependencies:
                del self.dependencies[indicator_id]

            # 移除作为源的依赖
            for target_id, deps in self.dependencies.items():
                self.dependencies[target_id] = [
                    dep for dep in deps
                    if dep.source_indicator != indicator_id
                ]

        except Exception as e:
            logger.error(f"移除指标依赖失败: {e}")

    def _has_circular_dependency(self) -> bool:
        """检查是否存在循环依赖"""
        try:
            return not nx.is_directed_acyclic_graph(self.dependency_graph)
        except Exception as e:
            logger.error(f"检查循环依赖失败: {e}")
            return False

    def _get_cached_result(self, indicator_id: str, symbol: str) -> Optional[IndicatorValue]:
        """获取缓存结果"""
        try:
            cache_key = f"{indicator_id}_{symbol}"

            # 检查节点缓存
            if indicator_id in self.compute_nodes:
                node = self.compute_nodes[indicator_id]
                if node.is_cache_valid():
                    return node.cached_result

            # 检查全局缓存
            if cache_key in self.compute_cache:
                cached_result = self.compute_cache[cache_key]
                # 简单的时间检查（实际中可能需要更复杂的失效策略）
                if hasattr(cached_result, 'calculation_time'):
                    cache_age = datetime.now() - cached_result.calculation_time
                    if cache_age < self.cache_ttl:
                        return cached_result

            return None

        except Exception as e:
            logger.error(f"获取缓存结果失败: {e}")
            return None

    def _cache_result(self, indicator_id: str, symbol: str, result: IndicatorValue):
        """缓存计算结果"""
        try:
            cache_key = f"{indicator_id}_{symbol}"

            # 更新节点缓存
            if indicator_id in self.compute_nodes:
                node = self.compute_nodes[indicator_id]
                node.cached_result = result
                node.cache_expiry = datetime.now() + self.cache_ttl

            # 更新全局缓存
            self.compute_cache[cache_key] = result

        except Exception as e:
            logger.error(f"缓存结果失败: {e}")

    def _clear_indicator_cache(self, indicator_id: str):
        """清理指标缓存"""
        try:
            # 清理节点缓存
            if indicator_id in self.compute_nodes:
                node = self.compute_nodes[indicator_id]
                node.cached_result = None
                node.cache_expiry = None

            # 清理全局缓存
            keys_to_remove = [key for key in self.compute_cache.keys() if key.startswith(f"{indicator_id}_")]
            for key in keys_to_remove:
                del self.compute_cache[key]

        except Exception as e:
            logger.error(f"清理指标缓存失败: {e}")

    def _determine_compute_order(self, requests: List[Dict[str, Any]]) -> List[Tuple[str, str, Dict[str, Any]]]:
        """确定计算顺序"""
        try:
            # 提取请求的指标ID
            requested_indicators = set()
            request_map = {}

            for req in requests:
                indicator_id = req['indicator_id']
                symbol = req['symbol']
                data_point = req['data_point']

                requested_indicators.add(indicator_id)
                request_map[indicator_id] = (symbol, data_point)

            # 使用拓扑排序确定计算顺序
            try:
                # 创建子图，只包含请求的指标
                subgraph = self.dependency_graph.subgraph(requested_indicators)

                # 拓扑排序
                if nx.is_directed_acyclic_graph(subgraph):
                    topo_order = list(nx.topological_sort(subgraph))
                else:
                    # 如果有循环依赖，使用简单排序
                    logger.warning("存在循环依赖，使用简单排序")
                    topo_order = list(requested_indicators)

            except Exception:
                # 排序失败，使用原始顺序
                topo_order = list(requested_indicators)

            # 构建计算顺序
            compute_order = []
            for indicator_id in topo_order:
                if indicator_id in request_map:
                    symbol, data_point = request_map[indicator_id]
                    compute_order.append((indicator_id, symbol, data_point))

            return compute_order

        except Exception as e:
            logger.error(f"确定计算顺序失败: {e}")
            # 返回原始顺序
            return [(req['indicator_id'], req['symbol'], req['data_point']) for req in requests]

    async def _execute_compute_task(self, task: ComputeTask) -> Optional[IndicatorValue]:
        """执行计算任务"""
        try:
            start_time = datetime.now()
            task.status = ComputeStatus.COMPUTING
            task.started_at = start_time

            # 获取指标配置
            if task.indicator_id not in self.compute_nodes:
                raise Exception(f"指标不存在: {task.indicator_id}")

            node = self.compute_nodes[task.indicator_id]
            config = node.indicator_config

            # 检查依赖是否满足
            dependency_results = await self._resolve_dependencies(task.indicator_id, task.symbol, task.data_point)

            # 执行实际计算（这里需要集成实际的计算引擎）
            result = await self._perform_calculation(config, task.data_point, dependency_results)

            # 更新任务状态
            task.status = ComputeStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result

            # 更新节点统计
            node.compute_count += 1
            node.success_count += 1
            node.last_computed = datetime.now()
            node.compute_duration = (datetime.now() - start_time).total_seconds()

            # 更新全局统计
            self.compute_stats['total_computations'] += 1

            return result

        except Exception as e:
            # 更新错误状态
            task.status = ComputeStatus.FAILED
            task.error = str(e)

            if task.indicator_id in self.compute_nodes:
                self.compute_nodes[task.indicator_id].error_count += 1

            logger.error(f"执行计算任务失败: {task.task_id}, {e}")
            return None

    async def _resolve_dependencies(self, indicator_id: str, symbol: str,
                                    data_point: Dict[str, Any]) -> Dict[str, IndicatorValue]:
        """解析依赖关系"""
        try:
            dependency_results = {}

            # 获取依赖列表
            dependencies = self.dependencies.get(indicator_id, [])

            for dependency in dependencies:
                source_id = dependency.source_indicator

                # 递归计算依赖指标
                dep_result = await self.compute_indicator(source_id, symbol, data_point)

                if dep_result:
                    dependency_results[source_id] = dep_result
                else:
                    logger.warning(f"依赖指标计算失败: {source_id}")

            return dependency_results

        except Exception as e:
            logger.error(f"解析依赖关系失败: {e}")
            return {}

    async def _perform_calculation(self, config: IndicatorConfig, data_point: Dict[str, Any],
                                   dependencies: Dict[str, IndicatorValue]) -> Optional[IndicatorValue]:
        """执行实际计算"""
        try:
            # 这里应该集成实际的指标计算逻辑
            # 暂时返回模拟结果

            from core.services.realtime_compute_engine import IndicatorValue

            logger.warning("指标计算未集成实际计算引擎，返回NaN值")
            mock_values = {
                'value': np.nan,
                'signal': 'neutral'
            }

            result = IndicatorValue(
                symbol=config.symbol,
                indicator_type=config.indicator_type,
                timestamp=datetime.now(),
                values=mock_values,
                params=config.params,
                calculation_time=datetime.now()
            )

            return result

        except Exception as e:
            logger.error(f"执行计算失败: {e}")
            return None

    def get_dependency_graph_info(self) -> Dict[str, Any]:
        """获取依赖图信息"""
        try:
            info = {
                'total_nodes': self.dependency_graph.number_of_nodes(),
                'total_edges': self.dependency_graph.number_of_edges(),
                'is_acyclic': nx.is_directed_acyclic_graph(self.dependency_graph),
                'strongly_connected_components': len(list(nx.strongly_connected_components(self.dependency_graph))),
                'nodes': list(self.dependency_graph.nodes()),
                'edges': list(self.dependency_graph.edges())
            }

            # 计算每个节点的度数
            info['node_degrees'] = {
                node: {
                    'in_degree': self.dependency_graph.in_degree(node),
                    'out_degree': self.dependency_graph.out_degree(node)
                }
                for node in self.dependency_graph.nodes()
            }

            return info

        except Exception as e:
            logger.error(f"获取依赖图信息失败: {e}")
            return {}

    def get_compute_statistics(self) -> Dict[str, Any]:
        """获取计算统计信息"""
        try:
            stats = self.compute_stats.copy()

            # 添加节点统计
            node_stats = {}
            for indicator_id, node in self.compute_nodes.items():
                node_stats[indicator_id] = {
                    'compute_count': node.compute_count,
                    'success_count': node.success_count,
                    'error_count': node.error_count,
                    'success_rate': node.success_count / node.compute_count if node.compute_count > 0 else 0.0,
                    'avg_compute_duration': node.compute_duration,
                    'last_computed': node.last_computed.isoformat() if node.last_computed else None,
                    'cache_valid': node.is_cache_valid()
                }

            stats['node_statistics'] = node_stats
            stats['cache_size'] = len(self.compute_cache)
            stats['active_tasks'] = len(self.active_tasks)

            return stats

        except Exception as e:
            logger.error(f"获取计算统计失败: {e}")
            return {}

    def optimize_compute_order(self) -> List[str]:
        """优化计算顺序"""
        try:
            # 使用拓扑排序和启发式算法优化计算顺序
            if not nx.is_directed_acyclic_graph(self.dependency_graph):
                logger.warning("依赖图包含循环，无法完全优化")
                return list(self.compute_nodes.keys())

            # 拓扑排序
            topo_order = list(nx.topological_sort(self.dependency_graph))

            # 根据计算复杂度和频率进一步优化
            # 这里可以添加更复杂的优化逻辑

            return topo_order

        except Exception as e:
            logger.error(f"优化计算顺序失败: {e}")
            return list(self.compute_nodes.keys())

    def invalidate_cache(self, indicator_id: str = None, symbol: str = None):
        """使缓存失效"""
        try:
            if indicator_id and symbol:
                # 失效特定指标和股票的缓存
                cache_key = f"{indicator_id}_{symbol}"
                if cache_key in self.compute_cache:
                    del self.compute_cache[cache_key]

                if indicator_id in self.compute_nodes:
                    node = self.compute_nodes[indicator_id]
                    if node.cached_result and node.cached_result.symbol == symbol:
                        node.cached_result = None
                        node.cache_expiry = None

            elif indicator_id:
                # 失效特定指标的所有缓存
                self._clear_indicator_cache(indicator_id)

            else:
                # 失效所有缓存
                self.compute_cache.clear()
                for node in self.compute_nodes.values():
                    node.cached_result = None
                    node.cache_expiry = None

            logger.info(f"缓存已失效: indicator_id={indicator_id}, symbol={symbol}")

        except Exception as e:
            logger.error(f"使缓存失效失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            # 清理依赖图
            self.dependency_graph.clear()

            # 清理计算节点
            self.compute_nodes.clear()

            # 清理依赖关系
            self.dependencies.clear()

            # 清理缓存
            self.compute_cache.clear()

            # 清理任务队列
            self.compute_queue.clear()
            self.active_tasks.clear()

            logger.info("指标依赖管理器资源清理完成")

        except Exception as e:
            logger.error(f"资源清理失败: {e}")
