"""
BettaFish性能监控和告警服务
专门为BettaFish多智能体系统设计的性能监控和告警机制
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import statistics
import json
from loguru import logger


class AlertSeverity(Enum):
    """告警严重性级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    RATE = "rate"


class ComponentStatus(Enum):
    """组件状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: datetime
    component: str
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """性能告警"""
    alert_id: str
    severity: AlertSeverity
    component: str
    metric_name: str
    current_value: float
    threshold_value: float
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    acknowledged: bool = False
    actions_taken: List[str] = field(default_factory=list)


@dataclass
class ComponentHealth:
    """组件健康状态"""
    component_name: str
    status: ComponentStatus
    last_check_time: datetime
    response_time: float
    error_count: int
    success_count: int
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BettaFishMonitoringService:
    """BettaFish性能监控和告警服务"""
    
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.logger = logger
        
        # 监控配置
        self.monitoring_config = {
            "check_interval": 30,  # 秒
            "metrics_retention_hours": 24,
            "alert_cooldown_minutes": 5,
            "health_check_timeout": 10,
            "enable_auto_recovery": True
        }
        
        # 性能阈值配置
        self.performance_thresholds = {
            "bettafish_agent": {
                "response_time": {"warning": 5.0, "critical": 15.0},
                "error_rate": {"warning": 0.05, "critical": 0.15},
                "cpu_usage": {"warning": 70.0, "critical": 90.0},
                "memory_usage": {"warning": 80.0, "critical": 95.0}
            },
            "sentiment_agent": {
                "response_time": {"warning": 3.0, "critical": 10.0},
                "error_rate": {"warning": 0.03, "critical": 0.10},
                "processing_latency": {"warning": 2.0, "critical": 5.0}
            },
            "news_agent": {
                "response_time": {"warning": 4.0, "critical": 12.0},
                "error_rate": {"warning": 0.04, "critical": 0.12},
                "data_freshness": {"warning": 300, "critical": 600}  # 秒
            },
            "technical_agent": {
                "response_time": {"warning": 2.0, "critical": 8.0},
                "error_rate": {"warning": 0.02, "critical": 0.08},
                "calculation_accuracy": {"warning": 0.95, "critical": 0.90}
            },
            "risk_agent": {
                "response_time": {"warning": 3.0, "critical": 10.0},
                "error_rate": {"warning": 0.01, "critical": 0.05},
                "risk_assessment_accuracy": {"warning": 0.98, "critical": 0.95}
            },
            "fusion_engine": {
                "response_time": {"warning": 1.0, "critical": 3.0},
                "error_rate": {"warning": 0.02, "critical": 0.06},
                "fusion_accuracy": {"warning": 0.90, "critical": 0.80}
            }
        }
        
        # 监控数据存储
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.component_health: Dict[str, ComponentHealth] = {}
        
        # 线程管理
        self._monitoring_active = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # 告警回调
        self.alert_callbacks: Dict[str, Callable] = {}
        
        # 性能统计
        self.performance_stats = {
            "total_checks": 0,
            "successful_checks": 0,
            "failed_checks": 0,
            "alerts_generated": 0,
            "alerts_resolved": 0,
            "components_monitored": 0
        }
        
        self.logger.info("BettaFishMonitoringService initialized")
    
    def start_monitoring(self):
        """启动性能监控"""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._shutdown_event.clear()
        
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="BettaFishMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        self.logger.info("BettaFish performance monitoring started")
    
    def stop_monitoring(self):
        """停止性能监控"""
        if not self._monitoring_active:
            return
        
        self._monitoring_active = False
        self._shutdown_event.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=10)
        
        self.logger.info("BettaFish performance monitoring stopped")
    
    def _monitoring_loop(self):
        """监控主循环"""
        while self._monitoring_active and not self._shutdown_event.is_set():
            try:
                start_time = time.time()
                
                # 检查各个组件健康状态
                self._check_all_components_sync()
                
                # 收集性能指标
                self._collect_performance_metrics_sync()
                
                # 检查性能阈值
                self._check_performance_thresholds_sync()
                
                # 清理过期告警
                self._cleanup_expired_alerts_sync()
                
                # 生成定期报告
                self._generate_periodic_report_sync()
                
                # 计算循环时间
                loop_time = time.time() - start_time
                sleep_time = max(0, self.monitoring_config["check_interval"] - loop_time)
                
                time.sleep(sleep_time)
                
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                time.sleep(5)  # 错误后短暂等待
    
    def _check_all_components_sync(self):
        """同步版本：检查所有组件健康状态"""
        try:
            # 模拟组件检查（在实际实现中应该调用真实的组件健康检查）
            components = ["bettafish_agent", "sentiment_agent", "news_agent", 
                         "technical_agent", "risk_agent", "fusion_engine"]
            
            for component in components:
                try:
                    health = self._check_component_health_sync(component)
                    self._record_health_metric(component, health)
                except Exception as e:
                    self.logger.error(f"检查组件 {component} 健康状态失败: {e}")
        except Exception as e:
            self.logger.error(f"同步检查所有组件失败: {e}")

    async def _check_all_components(self):
        """检查所有组件健康状态"""
        try:
            for component in self.monitoring_config.get("components", []):
                try:
                    health = await self._check_component_health(component)
                    await self._record_health_metric(component, health)
                except Exception as e:
                    self.logger.error(f"检查组件 {component} 健康状态失败: {e}")
        except Exception as e:
            self.logger.error(f"检查所有组件失败: {e}")

    def _check_component_health_sync(self, component_name: str) -> ComponentHealth:
        """同步版本：检查单个组件健康状态"""
        try:
            logger.warning(f"组件健康检查({component_name})使用真实检测逻辑，无法获取真实状态，返回未知")
            return ComponentHealth(
                component_name=component_name,
                status=ComponentStatus.UNKNOWN,
                last_check_time=datetime.now(),
                response_time=0.0,
                error_count=0,
                success_count=0,
                metadata={"warning": "健康检查结果不可用，组件状态未知"}
            )
        except Exception as e:
            self.logger.error(f"同步检查组件 {component_name} 失败: {e}")
            return ComponentHealth(
                component_name=component_name,
                status=ComponentStatus.FAILED,
                last_check_time=datetime.now(),
                response_time=0.0,
                error_count=1,
                success_count=0,
                metadata={"error": str(e)}
            )

    def _collect_performance_metrics_sync(self):
        """同步版本：收集性能指标"""
        try:
            # 模拟性能指标收集
            pass
        except Exception as e:
            self.logger.error(f"同步收集性能指标失败: {e}")

    def _check_performance_thresholds_sync(self):
        """同步版本：检查性能阈值"""
        try:
            # 模拟阈值检查
            pass
        except Exception as e:
            self.logger.error(f"同步检查性能阈值失败: {e}")

    def _cleanup_expired_alerts_sync(self):
        """同步版本：清理过期告警"""
        try:
            # 模拟过期告警清理
            current_time = datetime.now()
            expired_alerts = []
            expiry_threshold = current_time - timedelta(hours=self.monitoring_config.get("metrics_retention_hours", 24))

            for alert_id, alert in self.active_alerts.items():
                if alert.resolved or alert.timestamp < expiry_threshold:
                    expired_alerts.append(alert_id)
            
            for alert_id in expired_alerts:
                del self.active_alerts[alert_id]
                
        except Exception as e:
            self.logger.error(f"同步清理过期告警失败: {e}")

    def _generate_periodic_report_sync(self):
        """同步版本：生成定期报告"""
        try:
            # 模拟定期报告生成
            pass
        except Exception as e:
            self.logger.error(f"同步生成定期报告失败: {e}")
    
    async def _check_component_health(self, component_name: str) -> ComponentHealth:
        """检查单个组件健康状态"""
        start_time = time.time()
        
        try:
            # 根据组件类型执行不同的健康检查
            if component_name == "bettafish_agent":
                health_result = await self._check_bettafish_agent_health()
            elif component_name == "sentiment_agent":
                health_result = await self._check_sentiment_agent_health()
            elif component_name == "news_agent":
                health_result = await self._check_news_agent_health()
            elif component_name == "technical_agent":
                health_result = await self._check_technical_agent_health()
            elif component_name == "risk_agent":
                health_result = await self._check_risk_agent_health()
            elif component_name == "fusion_engine":
                health_result = await self._check_fusion_engine_health()
            else:
                raise Exception(f"Unknown component: {component_name}")
            
            response_time = time.time() - start_time
            
            # 确定组件状态
            status = ComponentStatus.HEALTHY
            if not health_result.get("healthy", True):
                status = ComponentStatus.FAILED
            elif health_result.get("degraded", False):
                status = ComponentStatus.DEGRADED
            
            return ComponentHealth(
                component_name=component_name,
                status=status,
                last_check_time=datetime.now(),
                response_time=response_time,
                error_count=health_result.get("error_count", 0),
                success_count=health_result.get("success_count", 1),
                metrics=health_result.get("metrics", {}),
                metadata=health_result.get("metadata", {})
            )
            
        except Exception as e:
            self.logger.error(f"Health check failed for {component_name}: {e}")
            return ComponentHealth(
                component_name=component_name,
                status=ComponentStatus.FAILED,
                last_check_time=datetime.now(),
                response_time=time.time() - start_time,
                error_count=1,
                success_count=0,
                metadata={"error": str(e)}
            )
    
    async def _check_bettafish_agent_health(self) -> Dict[str, Any]:
        """检查BettaFish Agent健康状态"""
        try:
            # 检查BettaFishAgent是否可用
            from core.agents.bettafish_agent import BettaFishAgent
            
            # 创建测试实例并检查基本方法
            test_agent = BettaFishAgent()
            
            if hasattr(test_agent, '_initialized'):
                return {
                    "healthy": True,
                    "metrics": {"agent_available": 1.0, "initialization_status": 1.0},
                    "metadata": {"agent_class": "BettaFishAgent"}
                }
            else:
                return {
                    "healthy": False,
                    "metrics": {"agent_available": 0.0, "initialization_status": 0.0},
                    "metadata": {"error": "Agent initialization failed"}
                }
                
        except Exception as e:
            return {
                "healthy": False,
                "error_count": 1,
                "metrics": {"agent_available": 0.0},
                "metadata": {"error": str(e)}
            }
    
    async def _check_sentiment_agent_health(self) -> Dict[str, Any]:
        """检查情绪分析Agent健康状态"""
        try:
            from core.agents.sentiment_agent import SentimentAnalysisAgent
            
            test_agent = SentimentAnalysisAgent()
            
            return {
                "healthy": True,
                "metrics": {"agent_available": 1.0},
                "metadata": {"agent_class": "SentimentAnalysisAgent"}
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error_count": 1,
                "metrics": {"agent_available": 0.0},
                "metadata": {"error": str(e)}
            }
    
    async def _check_news_agent_health(self) -> Dict[str, Any]:
        """检查新闻分析Agent健康状态"""
        try:
            from core.agents.news_agent import NewsAnalysisAgent
            
            test_agent = NewsAnalysisAgent()
            
            return {
                "healthy": True,
                "metrics": {"agent_available": 1.0},
                "metadata": {"agent_class": "NewsAnalysisAgent"}
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error_count": 1,
                "metrics": {"agent_available": 0.0},
                "metadata": {"error": str(e)}
            }
    
    async def _check_technical_agent_health(self) -> Dict[str, Any]:
        """检查技术分析Agent健康状态"""
        try:
            from core.agents.technical_agent import TechnicalAnalysisAgent
            
            test_agent = TechnicalAnalysisAgent()
            
            return {
                "healthy": True,
                "metrics": {"agent_available": 1.0},
                "metadata": {"agent_class": "TechnicalAnalysisAgent"}
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error_count": 1,
                "metrics": {"agent_available": 0.0},
                "metadata": {"error": str(e)}
            }
    
    async def _check_risk_agent_health(self) -> Dict[str, Any]:
        """检查风险评估Agent健康状态"""
        try:
            from core.agents.risk_agent import RiskAssessmentAgent
            
            test_agent = RiskAssessmentAgent()
            
            return {
                "healthy": True,
                "metrics": {"agent_available": 1.0},
                "metadata": {"agent_class": "RiskAssessmentAgent"}
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error_count": 1,
                "metrics": {"agent_available": 0.0},
                "metadata": {"error": str(e)}
            }
    
    async def _check_fusion_engine_health(self) -> Dict[str, Any]:
        """检查融合引擎健康状态"""
        try:
            from core.agents.fusion_engine import SignalFusionEngine
            
            test_engine = SignalFusionEngine()
            
            return {
                "healthy": True,
                "metrics": {"engine_available": 1.0},
                "metadata": {"engine_class": "SignalFusionEngine"}
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error_count": 1,
                "metrics": {"engine_available": 0.0},
                "metadata": {"error": str(e)}
            }
    
    async def _record_health_metric(self, component_name: str, health: ComponentHealth):
        """记录健康指标"""
        metric = PerformanceMetric(
            name=f"{component_name}_health_status",
            value=1.0 if health.status == ComponentStatus.HEALTHY else 0.0,
            metric_type=MetricType.GAUGE,
            timestamp=datetime.now(),
            component=component_name,
            tags={"component": component_name, "status": health.status.value}
        )
        
        self._store_metric(metric)
        
        # 记录响应时间指标
        response_time_metric = PerformanceMetric(
            name=f"{component_name}_response_time",
            value=health.response_time,
            metric_type=MetricType.GAUGE,
            timestamp=datetime.now(),
            component=component_name,
            tags={"component": component_name}
        )
        
        self._store_metric(response_time_metric)
    
    async def _collect_performance_metrics(self):
        """收集性能指标"""
        try:
            # 收集系统资源指标
            system_metrics = self._collect_system_metrics()
            for metric_name, value in system_metrics.items():
                metric = PerformanceMetric(
                    name=metric_name,
                    value=value,
                    metric_type=MetricType.GAUGE,
                    timestamp=datetime.now(),
                    component="system",
                    tags={"metric_type": "system"}
                )
                self._store_metric(metric)
            
            # 收集应用特定指标
            app_metrics = self._collect_application_metrics()
            for metric_name, value in app_metrics.items():
                metric = PerformanceMetric(
                    name=metric_name,
                    value=value,
                    metric_type=MetricType.GAUGE,
                    timestamp=datetime.now(),
                    component="bettafish_app",
                    tags={"metric_type": "application"}
                )
                self._store_metric(metric)
                
        except Exception as e:
            self.logger.error(f"Failed to collect performance metrics: {e}")
    
    def _collect_system_metrics(self) -> Dict[str, float]:
        """收集系统资源指标"""
        try:
            import psutil
            
            return {
                "cpu_usage": psutil.cpu_percent(interval=1),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "network_io": psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
            }
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return {}
    
    def _collect_application_metrics(self) -> Dict[str, float]:
        """收集应用特定指标"""
        try:
            # 计算活跃组件数量
            healthy_components = sum(1 for health in self.component_health.values() 
                                   if health.status == ComponentStatus.HEALTHY)
            total_components = len(self.component_health)
            
            # 计算平均响应时间
            response_times = [health.response_time for health in self.component_health.values() 
                            if health.response_time > 0]
            avg_response_time = statistics.mean(response_times) if response_times else 0
            
            # 计算错误率
            total_requests = sum(health.success_count + health.error_count 
                               for health in self.component_health.values())
            total_errors = sum(health.error_count for health in self.component_health.values())
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "healthy_components": healthy_components,
                "total_components": total_components,
                "component_health_ratio": (healthy_components / total_components * 100) if total_components > 0 else 0,
                "average_response_time": avg_response_time,
                "total_error_rate": error_rate,
                "active_alerts": len([a for a in self.active_alerts.values() if not a.resolved])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to collect application metrics: {e}")
            return {}
    
    async def _check_performance_thresholds(self):
        """检查性能阈值"""
        try:
            for component_name, thresholds in self.performance_thresholds.items():
                if component_name in self.component_health:
                    await self._check_component_thresholds(component_name, thresholds)
                    
        except Exception as e:
            self.logger.error(f"Failed to check performance thresholds: {e}")
    
    async def _check_component_thresholds(self, component_name: str, thresholds: Dict[str, Dict[str, float]]):
        """检查单个组件的阈值"""
        health = self.component_health[component_name]
        
        # 检查响应时间阈值
        if "response_time" in thresholds:
            warning_threshold = thresholds["response_time"]["warning"]
            critical_threshold = thresholds["response_time"]["critical"]
            
            if health.response_time >= critical_threshold:
                await self._create_alert(
                    component_name, "response_time", health.response_time, critical_threshold,
                    AlertSeverity.CRITICAL, f"响应时间严重超标: {health.response_time:.2f}s"
                )
            elif health.response_time >= warning_threshold:
                await self._create_alert(
                    component_name, "response_time", health.response_time, warning_threshold,
                    AlertSeverity.WARNING, f"响应时间超过警告阈值: {health.response_time:.2f}s"
                )
        
        # 检查错误率阈值
        if "error_rate" in thresholds and health.success_count + health.error_count > 0:
            error_rate = health.error_count / (health.success_count + health.error_count)
            warning_threshold = thresholds["error_rate"]["warning"]
            critical_threshold = thresholds["error_rate"]["critical"]
            
            if error_rate >= critical_threshold:
                await self._create_alert(
                    component_name, "error_rate", error_rate * 100, critical_threshold * 100,
                    AlertSeverity.CRITICAL, f"错误率严重超标: {error_rate:.2%}"
                )
            elif error_rate >= warning_threshold:
                await self._create_alert(
                    component_name, "error_rate", error_rate * 100, warning_threshold * 100,
                    AlertSeverity.WARNING, f"错误率超过警告阈值: {error_rate:.2%}"
                )
    
    async def _create_alert(self, component: str, metric_name: str, current_value: float, 
                          threshold_value: float, severity: AlertSeverity, message: str):
        """创建性能告警"""
        try:
            # 检查是否在冷却期内
            alert_key = f"{component}_{metric_name}_{severity.value}"
            
            # 创建告警
            alert_id = f"alert_{int(time.time())}_{hash(alert_key) % 10000}"
            alert = Alert(
                alert_id=alert_id,
                severity=severity,
                component=component,
                metric_name=metric_name,
                current_value=current_value,
                threshold_value=threshold_value,
                message=message
            )
            
            # 检查是否已存在相同的未解决告警
            existing_alert = self._find_similar_active_alert(alert)
            if existing_alert:
                return  # 不创建重复告警
            
            # 添加到活跃告警列表
            self.active_alerts[alert_id] = alert
            self.alert_history.append(alert)
            self.performance_stats["alerts_generated"] += 1
            
            # 触发告警回调
            await self._trigger_alert_callbacks(alert)
            
            # 发送告警通知
            await self._send_alert_notification(alert)
            
            self.logger.warning(f"Performance alert created: {alert.message}")
            
        except Exception as e:
            self.logger.error(f"Failed to create alert: {e}")
    
    def _find_similar_active_alert(self, alert: Alert) -> Optional[Alert]:
        """查找相似的活跃告警"""
        for existing_alert in self.active_alerts.values():
            if (existing_alert.component == alert.component and
                existing_alert.metric_name == alert.metric_name and
                existing_alert.severity == alert.severity and
                not existing_alert.resolved):
                
                # 检查是否在冷却期内
                time_diff = (datetime.now() - existing_alert.timestamp).total_seconds()
                if time_diff < (self.monitoring_config["alert_cooldown_minutes"] * 60):
                    return existing_alert
        
        return None
    
    async def _trigger_alert_callbacks(self, alert: Alert):
        """触发告警回调"""
        try:
            callback_key = f"{alert.component}_{alert.severity.value}"
            if callback_key in self.alert_callbacks:
                await self.alert_callbacks[callback_key](alert)
                
        except Exception as e:
            self.logger.error(f"Alert callback failed: {e}")
    
    async def _send_alert_notification(self, alert: Alert):
        """发送告警通知"""
        try:
            notification = {
                "type": "performance_alert",
                "alert_id": alert.alert_id,
                "severity": alert.severity.value,
                "component": alert.component,
                "metric": alert.metric_name,
                "current_value": alert.current_value,
                "threshold": alert.threshold_value,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat()
            }
            
            # 发送到事件总线
            if self.event_bus:
                self.event_bus.publish("performance.alert", notification)
            
            # 记录到日志
            if alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
                self.logger.error(f"Performance Alert: {json.dumps(notification)}")
            else:
                self.logger.warning(f"Performance Alert: {json.dumps(notification)}")
                
        except Exception as e:
            self.logger.error(f"Failed to send alert notification: {e}")
    
    async def _cleanup_expired_alerts(self):
        """清理过期告警"""
        try:
            current_time = datetime.now()
            retention_hours = self.monitoring_config["metrics_retention_hours"]
            cutoff_time = current_time - timedelta(hours=retention_hours)
            
            # 清理过期的历史告警
            self.alert_history = [
                alert for alert in self.alert_history 
                if alert.timestamp > cutoff_time
            ]
            
            # 标记已恢复的告警为已解决
            for alert in self.active_alerts.values():
                if not alert.resolved:
                    # 检查是否应该自动解决
                    if await self._should_resolve_alert(alert):
                        alert.resolved = True
                        alert.resolution_time = current_time
                        self.performance_stats["alerts_resolved"] += 1
                        
                        self.logger.info(f"Alert automatically resolved: {alert.alert_id}")
                        
        except Exception as e:
            self.logger.error(f"Failed to cleanup expired alerts: {e}")
    
    async def _should_resolve_alert(self, alert: Alert) -> bool:
        """判断是否应该自动解决告警"""
        try:
            # 获取相关组件的最新健康状态
            component_name = alert.component
            
            if component_name in self.component_health:
                health = self.component_health[component_name]
                
                # 检查指标是否恢复正常
                if alert.metric_name == "response_time":
                    # 响应时间恢复正常
                    thresholds = self.performance_thresholds.get(component_name, {}).get("response_time", {})
                    warning_threshold = thresholds.get("warning", float('inf'))
                    return health.response_time < warning_threshold
                
                elif alert.metric_name == "error_rate":
                    # 错误率恢复正常
                    thresholds = self.performance_thresholds.get(component_name, {}).get("error_rate", {})
                    warning_threshold = thresholds.get("warning", float('inf'))
                    
                    if health.success_count + health.error_count > 0:
                        current_error_rate = health.error_count / (health.success_count + health.error_count)
                        return current_error_rate < warning_threshold
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to check alert resolution: {e}")
            return False
    
    async def _generate_periodic_report(self):
        """生成定期报告"""
        try:
            # 每小时生成一次报告
            current_minute = datetime.now().minute
            if current_minute == 0:  # 每小时开始时
                report = self.generate_performance_report()
                
                # 发送报告
                if self.event_bus:
                    self.event_bus.publish("performance.periodic_report", report)
                
                self.logger.info("Periodic performance report generated")
                
        except Exception as e:
            self.logger.error(f"Failed to generate periodic report: {e}")
    
    def _store_metric(self, metric: PerformanceMetric):
        """存储性能指标"""
        try:
            metric_key = f"{metric.component}_{metric.name}"
            self.metrics_history[metric_key].append(metric)
            
            # 保持历史数据在合理范围内
            max_items = self.monitoring_config["metrics_retention_hours"] * 60 * 60 // self.monitoring_config["check_interval"]
            if len(self.metrics_history[metric_key]) > max_items:
                # 保留最新的数据
                self.metrics_history[metric_key] = deque(
                    list(self.metrics_history[metric_key])[-max_items:],
                    maxlen=max_items
                )
                
        except Exception as e:
            self.logger.error(f"Failed to store metric: {e}")
    
    def register_alert_callback(self, component: str, severity: AlertSeverity, callback: Callable):
        """注册告警回调"""
        callback_key = f"{component}_{severity.value}"
        self.alert_callbacks[callback_key] = callback
        self.logger.info(f"Registered alert callback for {callback_key}")
    
    def acknowledge_alert(self, alert_id: str, user: str = None) -> bool:
        """确认告警"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.acknowledged = True
                alert.actions_taken.append(f"acknowledged_by_{user or 'system'}")
                self.logger.info(f"Alert {alert_id} acknowledged by {user or 'system'}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False
    
    def resolve_alert(self, alert_id: str, resolution_note: str = None) -> bool:
        """手动解决告警"""
        try:
            if alert_id in self.active_alerts:
                alert = self.active_alerts[alert_id]
                alert.resolved = True
                alert.resolution_time = datetime.now()
                if resolution_note:
                    alert.actions_taken.append(f"manual_resolution: {resolution_note}")
                
                self.performance_stats["alerts_resolved"] += 1
                self.logger.info(f"Alert {alert_id} manually resolved")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False
    
    def get_active_alerts(self, component: Optional[str] = None, 
                         severity: Optional[AlertSeverity] = None) -> List[Alert]:
        """获取活跃告警"""
        alerts = list(self.active_alerts.values())
        
        # 过滤组件
        if component:
            alerts = [alert for alert in alerts if alert.component == component]
        
        # 过滤严重性
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        # 排除已解决的告警
        alerts = [alert for alert in alerts if not alert.resolved]
        
        return alerts
    
    def get_component_health(self, component_name: str) -> Optional[ComponentHealth]:
        """获取组件健康状态"""
        return self.component_health.get(component_name)
    
    def get_all_component_health(self) -> Dict[str, ComponentHealth]:
        """获取所有组件健康状态"""
        return self.component_health.copy()
    
    def get_performance_metrics(self, component: str, metric_name: str, 
                              hours: int = 1) -> List[PerformanceMetric]:
        """获取性能指标历史数据"""
        try:
            metric_key = f"{component}_{metric_name}"
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            metrics = [
                metric for metric in self.metrics_history[metric_key]
                if metric.timestamp > cutoff_time
            ]
            
            return sorted(metrics, key=lambda m: m.timestamp)
            
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return []
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        try:
            report_time = datetime.now()
            
            # 组件健康摘要
            component_summary = {}
            for component_name, health in self.component_health.items():
                component_summary[component_name] = {
                    "status": health.status.value,
                    "response_time": health.response_time,
                    "success_rate": (health.success_count / (health.success_count + health.error_count) * 100) 
                                  if (health.success_count + health.error_count) > 0 else 0,
                    "last_check": health.last_check_time.isoformat()
                }
            
            # 告警摘要
            active_alerts = self.get_active_alerts()
            alert_summary = {
                "total_active": len(active_alerts),
                "by_severity": {
                    severity.value: len([a for a in active_alerts if a.severity == severity])
                    for severity in AlertSeverity
                },
                "by_component": {}
            }
            
            for alert in active_alerts:
                component = alert.component
                if component not in alert_summary["by_component"]:
                    alert_summary["by_component"][component] = 0
                alert_summary["by_component"][component] += 1
            
            # 性能统计
            uptime_hours = (report_time - datetime.fromtimestamp(time.time() - self.performance_stats["total_checks"] * self.monitoring_config["check_interval"])).total_seconds() / 3600
            
            performance_summary = {
                "total_checks": self.performance_stats["total_checks"],
                "success_rate": (self.performance_stats["successful_checks"] / self.performance_stats["total_checks"] * 100) 
                               if self.performance_stats["total_checks"] > 0 else 0,
                "uptime_hours": uptime_hours,
                "alerts_generated": self.performance_stats["alerts_generated"],
                "alerts_resolved": self.performance_stats["alerts_resolved"]
            }
            
            return {
                "report_time": report_time.isoformat(),
                "components": component_summary,
                "alerts": alert_summary,
                "performance": performance_summary,
                "system_status": "healthy" if len(active_alerts) == 0 else "degraded"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to generate performance report: {e}")
            return {"error": str(e), "report_time": datetime.now().isoformat()}
    
    async def shutdown(self):
        """关闭监控服务"""
        try:
            self.logger.info("Shutting down BettaFish monitoring service...")
            
            # 停止监控
            self.stop_monitoring()
            
            # 生成最终报告
            final_report = self.generate_performance_report()
            self.logger.info(f"Final performance report: {json.dumps(final_report, indent=2)}")
            
            # 清理资源
            self.metrics_history.clear()
            self.active_alerts.clear()
            self.component_health.clear()
            
            self.logger.info("BettaFish monitoring service shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")


# 全局监控服务实例
_bettafish_monitoring_service: Optional[BettaFishMonitoringService] = None


def get_bettafish_monitoring_service() -> Optional[BettaFishMonitoringService]:
    """获取全局BettaFish监控服务"""
    return _bettafish_monitoring_service


def initialize_bettafish_monitoring_service(event_bus=None) -> BettaFishMonitoringService:
    """初始化BettaFish监控服务"""
    global _bettafish_monitoring_service
    _bettafish_monitoring_service = BettaFishMonitoringService(event_bus)
    return _bettafish_monitoring_service