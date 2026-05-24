"""
数据库连接池监控和性能分析服务

提供实时连接池监控、查询性能分析、异常检测等功能。
增强现有的 DatabaseService 监控能力。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2025-12-07
"""

import asyncio
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import json
import statistics
import numpy as np
from loguru import logger

from .base_service import BaseService
from .database_service import DatabaseService, ConnectionMetrics, QueryMetrics, DatabaseMetrics


@dataclass
class PoolMonitoringData:
    """连接池监控数据"""
    pool_name: str
    timestamp: datetime
    active_connections: int
    total_connections: int
    connection_utilization: float
    avg_wait_time: float
    error_rate: float
    query_performance: Dict[str, float]  # P50, P95, P99 查询延迟


@dataclass
class PerformanceAlert:
    """性能告警"""
    alert_id: str
    timestamp: datetime
    severity: str  # low, medium, high, critical
    component: str  # pool_name, query_type
    metric: str  # utilization, latency, error_rate
    current_value: float
    threshold: float
    message: str
    resolved: bool = False


@dataclass
class SystemPerformanceReport:
    """系统性能报告"""
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    
    # 连接池状态摘要
    pool_summary: Dict[str, Dict[str, Any]]
    
    # 性能指标
    performance_summary: Dict[str, Any]
    
    # 告警统计
    alert_summary: Dict[str, int]
    
    # 优化建议
    recommendations: List[str]


class DatabaseMonitoringService(BaseService):
    """数据库监控服务"""
    
    def __init__(self, database_service: DatabaseService):
        """
        初始化数据库监控服务
        
        Args:
            database_service: 数据库服务实例
        """
        super().__init__()
        self.service_name = "DatabaseMonitoringService"
        
        # 依赖
        self._database_service = database_service
        
        # 监控数据存储
        self._monitoring_history: deque = deque(maxlen=10000)  # 保留最近10000条记录
        self._performance_alerts: List[PerformanceAlert] = []
        self._alert_lock = threading.RLock()
        
        # 性能阈值配置
        self._thresholds = {
            "connection_utilization_high": 0.85,    # 连接池利用率超过85%告警
            "connection_utilization_critical": 0.95, # 95%严重告警
            "query_latency_p95": 5.0,               # P95查询延迟超过5秒告警
            "query_latency_p99": 10.0,              # P99查询延迟超过10秒严重告警
            "error_rate_high": 0.05,                # 错误率超过5%告警
            "error_rate_critical": 0.10             # 错误率超过10%严重告警
        }
        
        # 监控任务控制
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_event = threading.Event()
        self._monitoring_interval = 30  # 30秒监控一次
        
        # 性能统计
        self._performance_stats = defaultdict(lambda: {
            "query_count": 0,
            "total_time": 0.0,
            "latencies": deque(maxlen=1000),
            "errors": 0
        })
        
        logger.info("数据库监控服务初始化完成")
    
    def start_monitoring(self) -> bool:
        """启动监控"""
        try:
            if self._monitoring_task and not self._monitoring_task.done():
                logger.warning("监控任务已在运行中")
                return True
            
            self._stop_event.clear()
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info(f"数据库监控服务已启动，监控间隔: {self._monitoring_interval}秒")
            return True
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """停止监控"""
        try:
            self._stop_event.set()
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                logger.info("数据库监控服务已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止监控失败: {e}")
            return False
    
    async def _monitoring_loop(self) -> None:
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                await self._collect_performance_data()
                await self._check_alert_conditions()
                await asyncio.sleep(self._monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(self._monitoring_interval)
    
    async def _collect_performance_data(self) -> None:
        """收集性能数据"""
        try:
            current_time = datetime.now()
            
            # 获取所有连接池的指标
            for pool_name in self._database_service._connection_pools.keys():
                pool_metrics = self._database_service.get_pool_metrics(pool_name)
                if pool_metrics:
                    # 计算连接池利用率
                    active_connections = pool_metrics.active_connections
                    total_connections = pool_metrics.total_connections
                    utilization = active_connections / max(total_connections, 1)
                    
                    # 计算查询性能指标
                    query_performance = self._calculate_query_performance(pool_name)
                    
                    # 创建监控数据
                    monitoring_data = PoolMonitoringData(
                        pool_name=pool_name,
                        timestamp=current_time,
                        active_connections=active_connections,
                        total_connections=total_connections,
                        connection_utilization=utilization,
                        avg_wait_time=pool_metrics.avg_connection_time,
                        error_rate=self._calculate_error_rate(pool_name),
                        query_performance=query_performance
                    )
                    
                    self._monitoring_history.append(monitoring_data)
                    
                    # 更新性能统计
                    self._update_performance_stats(pool_name, query_performance)
                    
        except Exception as e:
            logger.error(f"收集性能数据失败: {e}")
    
    def _calculate_query_performance(self, pool_name: str) -> Dict[str, float]:
        """计算查询性能指标"""
        try:
            # 获取最近的查询记录
            recent_queries = [
                q for q in self._database_service._query_metrics.values()
                if q.end_time and (datetime.now() - q.end_time).total_seconds() < 300  # 最近5分钟
            ]
            
            if not recent_queries:
                return {"P50": 0.0, "P95": 0.0, "P99": 0.0, "avg": 0.0}
            
            latencies = [q.execution_time for q in recent_queries if q.success]
            
            if not latencies:
                return {"P50": 0.0, "P95": 0.0, "P99": 0.0, "avg": 0.0}
            
            return {
                "P50": statistics.median(latencies),
                "P95": float(np.percentile(latencies, 95)),
                "P99": float(np.percentile(latencies, 99)),
                "avg": statistics.mean(latencies)
            }
            
        except Exception as e:
            logger.error(f"计算查询性能失败 {pool_name}: {e}")
            return {"P50": 0.0, "P95": 0.0, "P99": 0.0, "avg": 0.0}
    
    def _calculate_error_rate(self, pool_name: str) -> float:
        """计算错误率"""
        try:
            recent_queries = [
                q for q in self._database_service._query_metrics.values()
                if q.end_time and (datetime.now() - q.end_time).total_seconds() < 300
            ]
            
            if not recent_queries:
                return 0.0
            
            error_count = sum(1 for q in recent_queries if not q.success)
            return error_count / len(recent_queries)
            
        except Exception as e:
            logger.error(f"计算错误率失败 {pool_name}: {e}")
            return 0.0
    
    def _update_performance_stats(self, pool_name: str, query_performance: Dict[str, float]) -> None:
        """更新性能统计"""
        stats = self._performance_stats[pool_name]
        stats["query_count"] += 1
        stats["total_time"] += query_performance["avg"]
        stats["latencies"].append(query_performance["avg"])
    
    async def _check_alert_conditions(self) -> None:
        """检查告警条件"""
        try:
            # 获取最新的监控数据
            if not self._monitoring_history:
                return
            
            latest_data = list(self._monitoring_history)[-10:]  # 最近10条记录
            
            for data in latest_data:
                # 检查连接池利用率
                if data.connection_utilization >= self._thresholds["connection_utilization_critical"]:
                    await self._create_alert(
                        "critical", data.pool_name, "utilization",
                        data.connection_utilization, self._thresholds["connection_utilization_critical"],
                        f"连接池 {data.pool_name} 利用率达到 {data.connection_utilization:.2%}，超过严重阈值"
                    )
                elif data.connection_utilization >= self._thresholds["connection_utilization_high"]:
                    await self._create_alert(
                        "high", data.pool_name, "utilization",
                        data.connection_utilization, self._thresholds["connection_utilization_high"],
                        f"连接池 {data.pool_name} 利用率达到 {data.connection_utilization:.2%}，超过警告阈值"
                    )
                
                # 检查查询延迟
                if data.query_performance["P99"] >= self._thresholds["query_latency_p99"]:
                    await self._create_alert(
                        "critical", data.pool_name, "latency",
                        data.query_performance["P99"], self._thresholds["query_latency_p99"],
                        f"连接池 {data.pool_name} P99查询延迟 {data.query_performance['P99']:.2f}s，超过严重阈值"
                    )
                elif data.query_performance["P95"] >= self._thresholds["query_latency_p95"]:
                    await self._create_alert(
                        "high", data.pool_name, "latency",
                        data.query_performance["P95"], self._thresholds["query_latency_p95"],
                        f"连接池 {data.pool_name} P95查询延迟 {data.query_performance['P95']:.2f}s，超过警告阈值"
                    )
                
                # 检查错误率
                if data.error_rate >= self._thresholds["error_rate_critical"]:
                    await self._create_alert(
                        "critical", data.pool_name, "error_rate",
                        data.error_rate, self._thresholds["error_rate_critical"],
                        f"连接池 {data.pool_name} 错误率达到 {data.error_rate:.2%}，超过严重阈值"
                    )
                elif data.error_rate >= self._thresholds["error_rate_high"]:
                    await self._create_alert(
                        "high", data.pool_name, "error_rate",
                        data.error_rate, self._thresholds["error_rate_high"],
                        f"连接池 {data.pool_name} 错误率达到 {data.error_rate:.2%}，超过警告阈值"
                    )
                    
        except Exception as e:
            logger.error(f"检查告警条件失败: {e}")
    
    async def _create_alert(self, severity: str, component: str, metric: str,
                           current_value: float, threshold: float, message: str) -> None:
        """创建告警"""
        try:
            alert = PerformanceAlert(
                alert_id=f"{int(time.time())}_{component}_{metric}",
                timestamp=datetime.now(),
                severity=severity,
                component=component,
                metric=metric,
                current_value=current_value,
                threshold=threshold,
                message=message
            )
            
            with self._alert_lock:
                self._performance_alerts.append(alert)
                
            logger.warning(f"性能告警 [{severity.upper()}]: {message}")
            
        except Exception as e:
            logger.error(f"创建告警失败: {e}")
    
    def get_current_pool_status(self) -> Dict[str, Dict[str, Any]]:
        """获取当前连接池状态"""
        try:
            status = {}
            
            for pool_name in self._database_service._connection_pools.keys():
                # 获取最新的监控数据
                recent_data = [
                    d for d in self._monitoring_history
                    if d.pool_name == pool_name
                ]
                
                if recent_data:
                    latest = max(recent_data, key=lambda x: x.timestamp)
                    
                    status[pool_name] = {
                        "active_connections": latest.active_connections,
                        "total_connections": latest.total_connections,
                        "utilization": latest.connection_utilization,
                        "avg_latency": latest.query_performance.get("avg", 0.0),
                        "p95_latency": latest.query_performance.get("P95", 0.0),
                        "error_rate": latest.error_rate,
                        "last_update": latest.timestamp.isoformat(),
                        "status": self._get_pool_status(latest)
                    }
                else:
                    # 如果没有监控数据，显示基本信息
                    pool_metrics = self._database_service.get_pool_metrics(pool_name)
                    if pool_metrics:
                        status[pool_name] = {
                            "active_connections": pool_metrics.active_connections,
                            "total_connections": pool_metrics.total_connections,
                            "utilization": pool_metrics.active_connections / max(pool_metrics.total_connections, 1),
                            "status": "unknown"
                        }
                    else:
                        status[pool_name] = {"status": "no_data"}
            
            return status
            
        except Exception as e:
            logger.error(f"获取连接池状态失败: {e}")
            return {}
    
    def _get_pool_status(self, data: PoolMonitoringData) -> str:
        """获取连接池状态"""
        if data.connection_utilization >= self._thresholds["connection_utilization_critical"]:
            return "critical"
        elif data.connection_utilization >= self._thresholds["connection_utilization_high"]:
            return "warning"
        elif data.error_rate >= self._thresholds["error_rate_high"]:
            return "warning"
        else:
            return "healthy"
    
    def get_performance_alerts(self, severity: Optional[str] = None, 
                              unresolved_only: bool = False) -> List[Dict[str, Any]]:
        """获取性能告警"""
        with self._alert_lock:
            alerts = self._performance_alerts.copy()
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        return [
            {
                "alert_id": a.alert_id,
                "timestamp": a.timestamp.isoformat(),
                "severity": a.severity,
                "component": a.component,
                "metric": a.metric,
                "current_value": a.current_value,
                "threshold": a.threshold,
                "message": a.message,
                "resolved": a.resolved
            }
            for a in sorted(alerts, key=lambda x: x.timestamp, reverse=True)
        ]
    
    def generate_performance_report(self, hours: int = 1) -> SystemPerformanceReport:
        """生成性能报告"""
        try:
            period_end = datetime.now()
            period_start = period_end - timedelta(hours=hours)
            
            # 收集期间内的监控数据
            period_data = [
                d for d in self._monitoring_history
                if period_start <= d.timestamp <= period_end
            ]
            
            # 生成连接池摘要
            pool_summary = {}
            for pool_name in set(d.pool_name for d in period_data):
                pool_data = [d for d in period_data if d.pool_name == pool_name]
                if pool_data:
                    pool_summary[pool_name] = {
                        "avg_utilization": statistics.mean(d.connection_utilization for d in pool_data),
                        "max_utilization": max(d.connection_utilization for d in pool_data),
                        "avg_latency": statistics.mean(d.query_performance.get("avg", 0) for d in pool_data),
                        "avg_error_rate": statistics.mean(d.error_rate for d in pool_data),
                        "data_points": len(pool_data)
                    }
            
            # 生成性能摘要
            all_latencies = []
            all_utilizations = []
            for d in period_data:
                all_latencies.extend(list(d.query_performance.values()))
                all_utilizations.append(d.connection_utilization)
            
            performance_summary = {
                "total_data_points": len(period_data),
                "avg_system_utilization": statistics.mean(all_utilizations) if all_utilizations else 0,
                "avg_query_latency": statistics.mean(all_latencies) if all_latencies else 0,
                "peak_utilization": max(all_utilizations) if all_utilizations else 0
            }
            
            # 生成告警摘要
            period_alerts = [
                a for a in self._performance_alerts
                if period_start <= a.timestamp <= period_end
            ]
            
            alert_summary = {
                "total": len(period_alerts),
                "critical": len([a for a in period_alerts if a.severity == "critical"]),
                "high": len([a for a in period_alerts if a.severity == "high"]),
                "medium": len([a for a in period_alerts if a.severity == "medium"]),
                "low": len([a for a in period_alerts if a.severity == "low"])
            }
            
            # 生成优化建议
            recommendations = self._generate_recommendations(period_data, alert_summary)
            
            report = SystemPerformanceReport(
                report_id=f"report_{int(time.time())}",
                generated_at=period_end,
                period_start=period_start,
                period_end=period_end,
                pool_summary=pool_summary,
                performance_summary=performance_summary,
                alert_summary=alert_summary,
                recommendations=recommendations
            )
            
            logger.info(f"生成性能报告: {report.report_id}")
            return report
            
        except Exception as e:
            logger.error(f"生成性能报告失败: {e}")
            raise
    
    def _generate_recommendations(self, period_data: List[PoolMonitoringData],
                                 alert_summary: Dict[str, int]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        try:
            # 基于告警生成建议
            if alert_summary["critical"] > 0:
                recommendations.append("存在严重性能问题，建议立即检查系统负载和数据库配置")
            
            if alert_summary["high"] > 3:
                recommendations.append("高频性能告警，建议增加连接池大小或优化查询性能")
            
            # 基于利用率生成建议
            high_util_pools = [
                d.pool_name for d in period_data
                if d.connection_utilization > 0.8
            ]
            
            if high_util_pools:
                unique_pools = list(set(high_util_pools))
                recommendations.append(f"连接池 {', '.join(unique_pools)} 利用率较高，建议增加连接池大小")
            
            # 基于查询延迟生成建议
            high_latency_data = [
                d for d in period_data
                if d.query_performance.get("P95", 0) > 5.0
            ]
            
            if high_latency_data:
                recommendations.append("查询延迟较高，建议优化SQL查询或增加数据库索引")
            
            if not recommendations:
                recommendations.append("系统运行正常，暂无优化建议")
                
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            recommendations.append("无法生成优化建议，请检查系统日志")
        
        return recommendations
    
    def get_historical_data(self, hours: int = 1) -> List[Dict[str, Any]]:
        """获取历史监控数据"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            historical_data = [
                {
                    "pool_name": d.pool_name,
                    "timestamp": d.timestamp.isoformat(),
                    "active_connections": d.active_connections,
                    "total_connections": d.total_connections,
                    "utilization": d.connection_utilization,
                    "avg_wait_time": d.avg_wait_time,
                    "error_rate": d.error_rate,
                    "query_performance": d.query_performance
                }
                for d in self._monitoring_history
                if d.timestamp >= cutoff_time
            ]
            
            return sorted(historical_data, key=lambda x: x["timestamp"])
            
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return []
    
    def update_thresholds(self, new_thresholds: Dict[str, float]) -> bool:
        """更新告警阈值"""
        try:
            for key, value in new_thresholds.items():
                if key in self._thresholds:
                    self._thresholds[key] = value
                    logger.info(f"更新阈值 {key}: {value}")
                else:
                    logger.warning(f"未知的阈值配置: {key}")
            
            return True
            
        except Exception as e:
            logger.error(f"更新阈值失败: {e}")
            return False