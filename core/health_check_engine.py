#!/usr/bin/env python3
"""
增强健康检查引擎

实现多层次、全方位的插件健康检查机制
作者: FactorWeave-Quant团队
版本: 2.0 (专业化优化版本)
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
import socket
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from loguru import logger
from core.enums import HealthStatus


class CheckType(Enum):
    """检查类型枚举"""
    CONNECTIVITY = "connectivity"
    APPLICATION = "application"
    DATA_QUALITY = "data_quality"
    PERFORMANCE = "performance"


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    plugin_id: str
    check_type: CheckType
    status: HealthStatus
    score: float  # 0.0-1.0
    response_time: float  # 毫秒
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


@dataclass
class PluginHealthProfile:
    """插件健康档案"""
    plugin_id: str
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    overall_score: float = 0.0
    last_check_time: datetime = field(default_factory=datetime.now)
    check_results: Dict[CheckType, HealthCheckResult] = field(default_factory=dict)
    historical_scores: List[Tuple[datetime, float]] = field(default_factory=list)
    failure_count: int = 0
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    recovery_time: Optional[datetime] = None


class EnhancedHealthCheckEngine:
    """增强健康检查引擎"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.health_profiles: Dict[str, PluginHealthProfile] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)

        # 配置参数
        self.connectivity_timeout = self.config.get('connectivity_timeout', 5.0)
        self.application_timeout = self.config.get('application_timeout', 10.0)
        self.performance_timeout = self.config.get('performance_timeout', 15.0)
        self.data_quality_timeout = self.config.get('data_quality_timeout', 20.0)

        # 评分权重
        self.check_weights = {
            CheckType.CONNECTIVITY: 0.3,
            CheckType.APPLICATION: 0.3,
            CheckType.DATA_QUALITY: 0.25,
            CheckType.PERFORMANCE: 0.15
        }

        # 历史数据保留期
        self.history_retention_days = self.config.get('history_retention_days', 7)

        logger.info("增强健康检查引擎初始化完成")

    async def perform_comprehensive_health_check(self, plugin_id: str, plugin_instance: Any) -> PluginHealthProfile:
        """执行全面健康检查"""
        logger.info(f"🏥 开始对插件 {plugin_id} 执行全面健康检查")

        # 获取或创建健康档案
        profile = self.health_profiles.get(plugin_id, PluginHealthProfile(plugin_id=plugin_id))

        # 并行执行所有检查
        check_tasks = [
            self._check_connectivity(plugin_id, plugin_instance),
            self._check_application_health(plugin_id, plugin_instance),
            self._check_data_quality(plugin_id, plugin_instance),
            self._check_performance(plugin_id, plugin_instance)
        ]

        try:
            results = await asyncio.gather(*check_tasks, return_exceptions=True)

            # 处理检查结果
            for i, result in enumerate(results):
                check_type = list(CheckType)[i]

                if isinstance(result, Exception):
                    logger.error(f"[ERROR] 插件 {plugin_id} 的 {check_type.value} 检查失败: {result}")
                    result = HealthCheckResult(
                        plugin_id=plugin_id,
                        check_type=check_type,
                        status=HealthStatus.UNHEALTHY,
                        score=0.0,
                        response_time=float('inf'),
                        error_message=str(result)
                    )

                profile.check_results[check_type] = result

            # 计算综合健康分数
            profile.overall_score = self._calculate_overall_score(profile.check_results)
            profile.overall_status = self._determine_overall_status(profile.overall_score)
            profile.last_check_time = datetime.now()

            # 更新历史记录
            self._update_historical_data(profile)

            # 更新故障统计
            self._update_failure_statistics(profile)

            # 保存档案
            self.health_profiles[plugin_id] = profile

            logger.info(f"插件 {plugin_id} 健康检查完成 - 状态: {profile.overall_status.value}, 分数: {profile.overall_score:.3f}")

            return profile

        except Exception as e:
            logger.error(f"[ERROR] 插件 {plugin_id} 健康检查异常: {e}")
            profile.overall_status = HealthStatus.UNKNOWN
            profile.overall_score = 0.0
            return profile

    async def _check_connectivity(self, plugin_id: str, plugin_instance: Any) -> HealthCheckResult:
        """检查网络连通性"""
        start_time = time.time()

        try:
            # 1. 基础连接检查
            if hasattr(plugin_instance, 'is_connected'):
                is_connected = plugin_instance.is_connected()
                if not is_connected:
                    return HealthCheckResult(
                        plugin_id=plugin_id,
                        check_type=CheckType.CONNECTIVITY,
                        status=HealthStatus.UNHEALTHY,
                        score=0.0,
                        response_time=(time.time() - start_time) * 1000,
                        error_message="插件报告未连接"
                    )

            # 2. 网络延迟检查
            if hasattr(plugin_instance, 'get_endpoint_url'):
                url = plugin_instance.get_endpoint_url()
                if url:
                    latency = await self._measure_network_latency(url)
                    if latency > 5000:  # 5秒超时
                        return HealthCheckResult(
                            plugin_id=plugin_id,
                            check_type=CheckType.CONNECTIVITY,
                            status=HealthStatus.DEGRADED,
                            score=0.5,
                            response_time=latency,
                            details={"latency_ms": latency}
                        )

            # 3. 端口连通性检查
            if hasattr(plugin_instance, 'get_host_port'):
                host, port = plugin_instance.get_host_port()
                if host and port:
                    is_reachable = await self._check_port_connectivity(host, port)
                    if not is_reachable:
                        return HealthCheckResult(
                            plugin_id=plugin_id,
                            check_type=CheckType.CONNECTIVITY,
                            status=HealthStatus.UNHEALTHY,
                            score=0.0,
                            response_time=(time.time() - start_time) * 1000,
                            error_message=f"无法连接到 {host}:{port}"
                        )

            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.CONNECTIVITY,
                status=HealthStatus.HEALTHY,
                score=1.0,
                response_time=response_time,
                details={"connectivity_ok": True}
            )

        except Exception as e:
            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.CONNECTIVITY,
                status=HealthStatus.UNHEALTHY,
                score=0.0,
                response_time=(time.time() - start_time) * 1000,
                error_message=str(e)
            )

    async def _check_application_health(self, plugin_id: str, plugin_instance: Any) -> HealthCheckResult:
        """检查应用层健康状态"""
        start_time = time.time()

        try:
            # 1. 健康检查端点
            if hasattr(plugin_instance, 'health_check'):
                health_result = plugin_instance.health_check()
                if hasattr(health_result, 'is_healthy') and not health_result.is_healthy:
                    return HealthCheckResult(
                        plugin_id=plugin_id,
                        check_type=CheckType.APPLICATION,
                        status=HealthStatus.UNHEALTHY,
                        score=0.0,
                        response_time=(time.time() - start_time) * 1000,
                        error_message="应用健康检查失败"
                    )

            # 2. 基础功能测试
            if hasattr(plugin_instance, 'get_plugin_info'):
                plugin_info = plugin_instance.get_plugin_info()
                if not plugin_info:
                    return HealthCheckResult(
                        plugin_id=plugin_id,
                        check_type=CheckType.APPLICATION,
                        status=HealthStatus.DEGRADED,
                        score=0.6,
                        response_time=(time.time() - start_time) * 1000,
                        details={"plugin_info_available": False}
                    )

            # 3. 资源使用情况检查
            resource_score = await self._check_resource_usage(plugin_instance)

            response_time = (time.time() - start_time) * 1000
            final_score = min(1.0, resource_score)

            status = HealthStatus.HEALTHY if final_score > 0.8 else \
                HealthStatus.DEGRADED if final_score > 0.5 else \
                HealthStatus.UNHEALTHY

            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.APPLICATION,
                status=status,
                score=final_score,
                response_time=response_time,
                details={"resource_score": resource_score}
            )

        except Exception as e:
            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.APPLICATION,
                status=HealthStatus.UNHEALTHY,
                score=0.0,
                response_time=(time.time() - start_time) * 1000,
                error_message=str(e)
            )

    async def _check_data_quality(self, plugin_id: str, plugin_instance: Any) -> HealthCheckResult:
        """检查数据质量"""
        start_time = time.time()

        try:
            quality_scores = []

            # 1. 数据完整性检查
            if hasattr(plugin_instance, 'get_sample_data'):
                sample_data = plugin_instance.get_sample_data()
                if sample_data:
                    completeness_score = self._assess_data_completeness(sample_data)
                    quality_scores.append(completeness_score)

            # 2. 数据时效性检查
            if hasattr(plugin_instance, 'get_last_update_time'):
                last_update = plugin_instance.get_last_update_time()
                if last_update:
                    timeliness_score = self._assess_data_timeliness(last_update)
                    quality_scores.append(timeliness_score)

            # 3. 数据一致性检查
            if hasattr(plugin_instance, 'validate_data_consistency'):
                consistency_result = plugin_instance.validate_data_consistency()
                if consistency_result:
                    quality_scores.append(consistency_result)

            # 计算综合质量分数
            if quality_scores:
                avg_score = statistics.mean(quality_scores)
            else:
                # 如果没有质量检查方法，给予中等分数
                avg_score = 0.7

            response_time = (time.time() - start_time) * 1000

            status = HealthStatus.HEALTHY if avg_score > 0.8 else \
                HealthStatus.DEGRADED if avg_score > 0.5 else \
                HealthStatus.UNHEALTHY

            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.DATA_QUALITY,
                status=status,
                score=avg_score,
                response_time=response_time,
                details={"quality_scores": quality_scores, "avg_score": avg_score}
            )

        except Exception as e:
            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.DATA_QUALITY,
                status=HealthStatus.UNHEALTHY,
                score=0.0,
                response_time=(time.time() - start_time) * 1000,
                error_message=str(e)
            )

    async def _check_performance(self, plugin_id: str, plugin_instance: Any) -> HealthCheckResult:
        """检查性能指标"""
        start_time = time.time()

        try:
            performance_metrics = {}

            # 1. 响应时间基准测试
            if hasattr(plugin_instance, 'get_plugin_info'):
                response_times = []
                for _ in range(3):  # 执行3次测试
                    test_start = time.time()
                    plugin_instance.get_plugin_info()
                    response_times.append((time.time() - test_start) * 1000)

                avg_response_time = statistics.mean(response_times)
                performance_metrics['avg_response_time'] = avg_response_time
                performance_metrics['response_time_std'] = statistics.stdev(response_times) if len(response_times) > 1 else 0

            # 2. 吞吐量测试
            if hasattr(plugin_instance, 'get_sample_data'):
                throughput_score = await self._measure_throughput(plugin_instance)
                performance_metrics['throughput_score'] = throughput_score

            # 3. 资源消耗评估
            resource_efficiency = await self._assess_resource_efficiency(plugin_instance)
            performance_metrics['resource_efficiency'] = resource_efficiency

            # 计算综合性能分数
            score_components = []

            # 响应时间评分 (越低越好)
            if 'avg_response_time' in performance_metrics:
                rt = performance_metrics['avg_response_time']
                rt_score = max(0, 1.0 - (rt / 5000))  # 5秒为基准
                score_components.append(rt_score)

            # 吞吐量评分
            if 'throughput_score' in performance_metrics:
                score_components.append(performance_metrics['throughput_score'])

            # 资源效率评分
            if 'resource_efficiency' in performance_metrics:
                score_components.append(performance_metrics['resource_efficiency'])

            final_score = statistics.mean(score_components) if score_components else 0.5

            response_time = (time.time() - start_time) * 1000

            status = HealthStatus.HEALTHY if final_score > 0.8 else \
                HealthStatus.DEGRADED if final_score > 0.5 else \
                HealthStatus.UNHEALTHY

            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.PERFORMANCE,
                status=status,
                score=final_score,
                response_time=response_time,
                details=performance_metrics
            )

        except Exception as e:
            return HealthCheckResult(
                plugin_id=plugin_id,
                check_type=CheckType.PERFORMANCE,
                status=HealthStatus.UNHEALTHY,
                score=0.0,
                response_time=(time.time() - start_time) * 1000,
                error_message=str(e)
            )

    async def _measure_network_latency(self, url: str) -> float:
        """测量网络延迟"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                start_time = time.time()
                async with session.get(url) as response:
                    await response.read()
                return (time.time() - start_time) * 1000
        except Exception:
            return float('inf')

    async def _check_port_connectivity(self, host: str, port: int) -> bool:
        """检查端口连通性"""
        try:
            future = self.executor.submit(self._sync_port_check, host, port)
            return await asyncio.wrap_future(future)
        except Exception:
            return False

    def _sync_port_check(self, host: str, port: int) -> bool:
        """同步端口检查"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    async def _check_resource_usage(self, plugin_instance: Any) -> float:
        """检查资源使用情况"""
        try:
            # 这里可以集成系统监控工具
            # 暂时返回默认分数
            return 0.8
        except Exception:
            return 0.5

    def _assess_data_completeness(self, data: Any) -> float:
        """评估数据完整性"""
        try:
            if not data:
                return 0.0

            # 简单的完整性检查
            if hasattr(data, '__len__'):
                return 1.0 if len(data) > 0 else 0.0

            return 0.8  # 默认分数
        except Exception:
            return 0.0

    def _assess_data_timeliness(self, last_update: datetime) -> float:
        """评估数据时效性"""
        try:
            now = datetime.now()
            time_diff = (now - last_update).total_seconds()

            # 1小时内为满分，超过24小时为0分
            if time_diff <= 3600:  # 1小时
                return 1.0
            elif time_diff <= 86400:  # 24小时
                return max(0, 1.0 - (time_diff - 3600) / (86400 - 3600))
            else:
                return 0.0
        except Exception:
            return 0.5

    async def _measure_throughput(self, plugin_instance: Any) -> float:
        """测量吞吐量"""
        try:
            # 简单的吞吐量测试
            start_time = time.time()
            for _ in range(10):
                if hasattr(plugin_instance, 'get_sample_data'):
                    plugin_instance.get_sample_data()

            elapsed = time.time() - start_time
            # 10次调用在1秒内完成为满分
            return min(1.0, 1.0 / elapsed) if elapsed > 0 else 1.0
        except Exception:
            return 0.5

    async def _assess_resource_efficiency(self, plugin_instance: Any) -> float:
        """评估资源效率"""
        try:
            # 这里可以集成更复杂的资源监控
            return 0.8
        except Exception:
            return 0.5

    def _calculate_overall_score(self, check_results: Dict[CheckType, HealthCheckResult]) -> float:
        """计算综合健康分数"""
        weighted_scores = []

        for check_type, weight in self.check_weights.items():
            if check_type in check_results:
                result = check_results[check_type]
                weighted_scores.append(result.score * weight)
            else:
                # 如果某项检查缺失，给予0分
                weighted_scores.append(0.0)

        return sum(weighted_scores)

    def _determine_overall_status(self, overall_score: float) -> HealthStatus:
        """确定综合健康状态"""
        if overall_score >= 0.8:
            return HealthStatus.HEALTHY
        elif overall_score >= 0.5:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNHEALTHY

    def _update_historical_data(self, profile: PluginHealthProfile):
        """更新历史数据"""
        now = datetime.now()
        profile.historical_scores.append((now, profile.overall_score))

        # 清理过期数据
        cutoff_time = now - timedelta(days=self.history_retention_days)
        profile.historical_scores = [
            (timestamp, score) for timestamp, score in profile.historical_scores
            if timestamp > cutoff_time
        ]

    def _update_failure_statistics(self, profile: PluginHealthProfile):
        """更新故障统计"""
        if profile.overall_status == HealthStatus.UNHEALTHY:
            profile.failure_count += 1
            profile.consecutive_failures += 1
            profile.last_failure_time = datetime.now()
            profile.recovery_time = None
        else:
            if profile.consecutive_failures > 0:
                profile.recovery_time = datetime.now()
            profile.consecutive_failures = 0

    def get_plugin_health_profile(self, plugin_id: str) -> Optional[PluginHealthProfile]:
        """获取插件健康档案"""
        return self.health_profiles.get(plugin_id)

    def get_healthy_plugins(self) -> List[str]:
        """获取健康的插件列表"""
        return [
            plugin_id for plugin_id, profile in self.health_profiles.items()
            if profile.overall_status == HealthStatus.HEALTHY
        ]

    def get_plugin_health_trend(self, plugin_id: str, hours: int = 24) -> List[Tuple[datetime, float]]:
        """获取插件健康趋势"""
        profile = self.health_profiles.get(plugin_id)
        if not profile:
            return []

        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            (timestamp, score) for timestamp, score in profile.historical_scores
            if timestamp > cutoff_time
        ]

    async def cleanup(self):
        """清理资源"""
        self.executor.shutdown(wait=True)
        logger.info("增强健康检查引擎已清理完成")
