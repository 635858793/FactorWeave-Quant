"""
故障容错管理器
提供高级的故障检测和自动恢复机制，支持节点健康监控和故障转移
"""

import asyncio
from loguru import logger
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Set
from threading import Lock, Event
import threading

from core.enums import HealthStatus



class RecoveryAction(Enum):
    """恢复动作枚举"""
    RESTART_SERVICE = "restart_service"
    FAILOVER_NODE = "failover_node"
    SCALE_UP = "scale_up"
    ISOLATE_NODE = "isolate_node"
    NOTIFY_ADMIN = "notify_admin"
    AUTO_HEAL = "auto_heal"

@dataclass
class HealthMetrics:
    """健康指标数据类"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_latency: float = 0.0
    error_rate: float = 0.0
    response_time: float = 0.0
    active_connections: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class FailureEvent:
    """故障事件数据类"""
    node_id: str
    failure_type: str
    severity: str
    timestamp: datetime
    description: str
    metrics: Optional[HealthMetrics] = None
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    resolved: bool = False
    resolution_time: Optional[datetime] = None

@dataclass
class RecoveryPlan:
    """恢复计划数据类"""
    failure_event: FailureEvent
    actions: List[RecoveryAction]
    estimated_duration: float
    priority: int
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

class HealthMonitor:
    """健康监控器"""
    
    def __init__(self, check_interval: float = 30.0):
        self.check_interval = check_interval
        self.health_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.health_thresholds = {
            'cpu_usage': {'warning': 70.0, 'critical': 90.0},
            'memory_usage': {'warning': 80.0, 'critical': 95.0},
            'disk_usage': {'warning': 85.0, 'critical': 95.0},
            'network_latency': {'warning': 1000.0, 'critical': 5000.0},
            'error_rate': {'warning': 0.05, 'critical': 0.15},
            'response_time': {'warning': 2000.0, 'critical': 10000.0}
        }
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = Event()
        self.health_callbacks: List[Callable] = []
        
    def add_health_callback(self, callback: Callable[[str, HealthStatus, HealthMetrics], None]):
        """添加健康状态变化回调"""
        self.health_callbacks.append(callback)
    
    def start_monitoring(self):
        """开始健康监控"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("健康监控已启动")
    
    def stop_monitoring(self):
        """停止健康监控"""
        if not self.monitoring_active:
            return
            
        self.monitoring_active = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("健康监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring_active and not self.stop_event.is_set():
            try:
                self._collect_health_metrics()
                
            except Exception as e:
                logger.error(f"健康监控循环出错: {e}")
            
            self.stop_event.wait(self.check_interval)
    
    def _collect_health_metrics(self):
        """收集健康指标（模拟实现）"""
        # 这里应该实现实际的指标收集逻辑
        # 例如从系统API、监控代理或节点状态接口获取数据
        pass
    
    def update_health_metrics(self, node_id: str, metrics: HealthMetrics):
        """更新节点健康指标"""
        try:
            # 记录历史数据
            self.health_history[node_id].append(metrics)
            
            # 评估健康状态
            health_status = self._evaluate_health_status(metrics)
            
            # 触发回调
            for callback in self.health_callbacks:
                try:
                    callback(node_id, health_status, metrics)
                except Exception as e:
                    logger.error(f"健康状态回调执行失败: {e}")
            
            logger.debug(f"节点 {node_id} 健康状态: {health_status.value}")
            
        except Exception as e:
            logger.error(f"更新健康指标失败: {e}")
    
    def _evaluate_health_status(self, metrics: HealthMetrics) -> HealthStatus:
        """评估健康状态"""
        try:
            critical_count = 0
            warning_count = 0
            
            # 检查各项指标
            for metric_name, thresholds in self.health_thresholds.items():
                value = getattr(metrics, metric_name, 0)
                
                if value >= thresholds['critical']:
                    critical_count += 1
                elif value >= thresholds['warning']:
                    warning_count += 1
            
            # 判断整体状态
            if critical_count > 0:
                return HealthStatus.CRITICAL
            elif warning_count >= 2:  # 多个警告指标
                return HealthStatus.WARNING
            elif warning_count > 0:
                return HealthStatus.WARNING
            else:
                return HealthStatus.HEALTHY
                
        except Exception as e:
            logger.error(f"评估健康状态失败: {e}")
            return HealthStatus.UNKNOWN
    
    def get_node_health_trend(self, node_id: str, duration_minutes: int = 30) -> Dict[str, Any]:
        """获取节点健康趋势"""
        try:
            history = list(self.health_history[node_id])
            if not history:
                return {'status': 'no_data'}
            
            # 过滤指定时间范围内的数据
            cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
            recent_metrics = [m for m in history if m.timestamp >= cutoff_time]
            
            if not recent_metrics:
                return {'status': 'insufficient_data'}
            
            # 计算趋势
            trend_data = {
                'total_samples': len(recent_metrics),
                'time_range': duration_minutes,
                'avg_cpu': sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics),
                'avg_memory': sum(m.memory_usage for m in recent_metrics) / len(recent_metrics),
                'avg_response_time': sum(m.response_time for m in recent_metrics) / len(recent_metrics),
                'avg_error_rate': sum(m.error_rate for m in recent_metrics) / len(recent_metrics),
                'status': 'healthy'
            }
            
            # 判断趋势状态
            latest_metrics = recent_metrics[-1]
            current_status = self._evaluate_health_status(latest_metrics)
            trend_data['current_status'] = current_status.value
            
            return trend_data
            
        except Exception as e:
            logger.error(f"获取健康趋势失败: {e}")
            return {'status': 'error', 'error': str(e)}

class FailureDetector:
    """故障检测器"""
    
    def __init__(self):
        self.failure_patterns = {
            'high_error_rate': {'threshold': 0.1, 'duration': 300},  # 5分钟内错误率>10%
            'slow_response': {'threshold': 5000, 'duration': 180},   # 3分钟内响应时间>5秒
            'resource_exhaustion': {'cpu': 95, 'memory': 98, 'duration': 120},  # 2分钟内资源耗尽
            'connection_failure': {'threshold': 3, 'duration': 60}   # 1分钟内连接失败3次
        }
        self.detection_history: Dict[str, List[FailureEvent]] = defaultdict(list)
        self.active_failures: Dict[str, Set[str]] = defaultdict(set)
        self.lock = Lock()
    
    def detect_failures(self, node_id: str, metrics: HealthMetrics) -> List[FailureEvent]:
        """检测故障"""
        detected_failures = []
        
        try:
            with self.lock:
                # 检查各种故障模式
                failures = []
                
                # 高错误率检测
                if metrics.error_rate > self.failure_patterns['high_error_rate']['threshold']:
                    failures.append(self._create_failure_event(
                        node_id, 'high_error_rate', 'critical',
                        f"错误率过高: {metrics.error_rate:.2%}", metrics
                    ))
                
                # 响应时间过慢检测
                if metrics.response_time > self.failure_patterns['slow_response']['threshold']:
                    failures.append(self._create_failure_event(
                        node_id, 'slow_response', 'warning',
                        f"响应时间过慢: {metrics.response_time:.0f}ms", metrics
                    ))
                
                # 资源耗尽检测
                if (metrics.cpu_usage > self.failure_patterns['resource_exhaustion']['cpu'] or
                    metrics.memory_usage > self.failure_patterns['resource_exhaustion']['memory']):
                    failures.append(self._create_failure_event(
                        node_id, 'resource_exhaustion', 'critical',
                        f"资源耗尽: CPU {metrics.cpu_usage:.1f}%, 内存 {metrics.memory_usage:.1f}%", metrics
                    ))
                
                # 过滤重复故障
                for failure in failures:
                    failure_key = f"{failure.failure_type}_{failure.severity}"
                    if failure_key not in self.active_failures[node_id]:
                        self.active_failures[node_id].add(failure_key)
                        self.detection_history[node_id].append(failure)
                        detected_failures.append(failure)
                
                return detected_failures
                
        except Exception as e:
            logger.error(f"故障检测失败: {e}")
            return []
    
    def _create_failure_event(self, node_id: str, failure_type: str, severity: str, 
                            description: str, metrics: HealthMetrics) -> FailureEvent:
        """创建故障事件"""
        return FailureEvent(
            node_id=node_id,
            failure_type=failure_type,
            severity=severity,
            timestamp=datetime.now(),
            description=description,
            metrics=metrics
        )
    
    def resolve_failure(self, node_id: str, failure_type: str, severity: str):
        """标记故障已解决"""
        try:
            with self.lock:
                failure_key = f"{failure_type}_{severity}"
                self.active_failures[node_id].discard(failure_key)
                
                # 更新历史记录中的解决状态
                for failure in self.detection_history[node_id]:
                    if (failure.failure_type == failure_type and 
                        failure.severity == severity and 
                        not failure.resolved):
                        failure.resolved = True
                        failure.resolution_time = datetime.now()
                        break
                        
                logger.info(f"故障已解决: 节点 {node_id}, 类型 {failure_type}")
                
        except Exception as e:
            logger.error(f"标记故障解决失败: {e}")
    
    def get_failure_statistics(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        """获取故障统计信息"""
        try:
            with self.lock:
                if node_id:
                    failures = self.detection_history[node_id]
                    active = len(self.active_failures[node_id])
                else:
                    failures = []
                    for node_failures in self.detection_history.values():
                        failures.extend(node_failures)
                    active = sum(len(af) for af in self.active_failures.values())
                
                total_failures = len(failures)
                resolved_failures = sum(1 for f in failures if f.resolved)
                
                # 按类型统计
                failure_types = defaultdict(int)
                for failure in failures:
                    failure_types[failure.failure_type] += 1
                
                return {
                    'total_failures': total_failures,
                    'active_failures': active,
                    'resolved_failures': resolved_failures,
                    'resolution_rate': resolved_failures / total_failures if total_failures > 0 else 0,
                    'failure_types': dict(failure_types),
                    'node_id': node_id
                }
                
        except Exception as e:
            logger.error(f"获取故障统计失败: {e}")
            return {'error': str(e)}

class RecoveryEngine:
    """恢复引擎"""
    
    def __init__(self):
        self.recovery_strategies = {
            'high_error_rate': [RecoveryAction.RESTART_SERVICE, RecoveryAction.FAILOVER_NODE],
            'slow_response': [RecoveryAction.SCALE_UP, RecoveryAction.AUTO_HEAL],
            'resource_exhaustion': [RecoveryAction.SCALE_UP, RecoveryAction.ISOLATE_NODE],
            'connection_failure': [RecoveryAction.RESTART_SERVICE, RecoveryAction.NOTIFY_ADMIN]
        }
        self.recovery_history: List[RecoveryPlan] = []
        self.active_recoveries: Dict[str, RecoveryPlan] = {}
        self.recovery_callbacks: Dict[RecoveryAction, Callable] = {}
        self.lock = Lock()
    
    def register_recovery_callback(self, action: RecoveryAction, callback: Callable):
        """注册恢复动作回调"""
        self.recovery_callbacks[action] = callback
    
    def create_recovery_plan(self, failure_event: FailureEvent) -> RecoveryPlan:
        """创建恢复计划"""
        try:
            # 根据故障类型选择恢复策略
            actions = self.recovery_strategies.get(
                failure_event.failure_type, 
                [RecoveryAction.NOTIFY_ADMIN]
            )
            
            # 根据严重程度调整优先级
            priority = 1 if failure_event.severity == 'critical' else 2
            
            # 估算恢复时间
            estimated_duration = self._estimate_recovery_duration(actions)
            
            recovery_plan = RecoveryPlan(
                failure_event=failure_event,
                actions=actions,
                estimated_duration=estimated_duration,
                priority=priority
            )
            
            return recovery_plan
            
        except Exception as e:
            logger.error(f"创建恢复计划失败: {e}")
            # 返回默认的通知管理员计划
            return RecoveryPlan(
                failure_event=failure_event,
                actions=[RecoveryAction.NOTIFY_ADMIN],
                estimated_duration=60.0,
                priority=3
            )
    
    def execute_recovery_plan(self, recovery_plan: RecoveryPlan) -> bool:
        """执行恢复计划"""
        try:
            with self.lock:
                plan_id = f"{recovery_plan.failure_event.node_id}_{recovery_plan.failure_event.timestamp.timestamp()}"
                self.active_recoveries[plan_id] = recovery_plan
                self.recovery_history.append(recovery_plan)
            
            logger.info(f"开始执行恢复计划: {plan_id}")
            
            success = True
            for action in recovery_plan.actions:
                try:
                    if action in self.recovery_callbacks:
                        callback_success = self.recovery_callbacks[action](recovery_plan.failure_event)
                        if not callback_success:
                            success = False
                            logger.warning(f"恢复动作失败: {action.value}")
                    else:
                        logger.warning(f"未找到恢复动作回调: {action.value}")
                        success = False
                        
                except Exception as e:
                    logger.error(f"执行恢复动作 {action.value} 失败: {e}")
                    success = False
            
            # 清理活跃恢复记录
            with self.lock:
                self.active_recoveries.pop(plan_id, None)
            
            if success:
                logger.info(f"恢复计划执行成功: {plan_id}")
            else:
                logger.error(f"恢复计划执行失败: {plan_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"执行恢复计划失败: {e}")
            return False
    
    def _estimate_recovery_duration(self, actions: List[RecoveryAction]) -> float:
        """估算恢复时间（秒）"""
        duration_map = {
            RecoveryAction.RESTART_SERVICE: 30.0,
            RecoveryAction.FAILOVER_NODE: 120.0,
            RecoveryAction.SCALE_UP: 180.0,
            RecoveryAction.ISOLATE_NODE: 60.0,
            RecoveryAction.NOTIFY_ADMIN: 5.0,
            RecoveryAction.AUTO_HEAL: 90.0
        }
        
        return sum(duration_map.get(action, 60.0) for action in actions)
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """获取恢复统计信息"""
        try:
            with self.lock:
                total_plans = len(self.recovery_history)
                active_plans = len(self.active_recoveries)
                
                # 统计恢复动作使用频率
                action_usage = defaultdict(int)
                for plan in self.recovery_history:
                    for action in plan.actions:
                        action_usage[action.value] += 1
                
                return {
                    'total_recovery_plans': total_plans,
                    'active_recovery_plans': active_plans,
                    'action_usage': dict(action_usage),
                    'average_duration': sum(p.estimated_duration for p in self.recovery_history) / total_plans if total_plans > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"获取恢复统计失败: {e}")
            return {'error': str(e)}

class FaultToleranceManager:
    """故障容错管理器主类"""
    
    def __init__(self, check_interval: float = 30.0):
        self.health_monitor = HealthMonitor(check_interval)
        self.failure_detector = FailureDetector()
        self.recovery_engine = RecoveryEngine()
        
        # 注册健康监控回调
        self.health_monitor.add_health_callback(self._on_health_status_change)
        
        # 注册默认恢复回调
        self._register_default_recovery_callbacks()
        
        self.enabled = False
        logger.info("故障容错管理器已初始化")
    
    def start(self):
        """启动故障容错管理"""
        try:
            self.enabled = True
            self.health_monitor.start_monitoring()
            logger.info("故障容错管理已启动")
            
        except Exception as e:
            logger.error(f"启动故障容错管理失败: {e}")
            self.enabled = False
    
    def stop(self):
        """停止故障容错管理"""
        try:
            self.enabled = False
            self.health_monitor.stop_monitoring()
            logger.info("故障容错管理已停止")
            
        except Exception as e:
            logger.error(f"停止故障容错管理失败: {e}")
    
    def update_node_health(self, node_id: str, metrics: HealthMetrics):
        """更新节点健康状态"""
        if not self.enabled:
            return
            
        self.health_monitor.update_health_metrics(node_id, metrics)
    
    def _on_health_status_change(self, node_id: str, status: HealthStatus, metrics: HealthMetrics):
        """健康状态变化回调"""
        try:
            if status in [HealthStatus.WARNING, HealthStatus.CRITICAL, HealthStatus.FAILED]:
                # 检测具体故障
                failures = self.failure_detector.detect_failures(node_id, metrics)
                
                # 为每个故障创建和执行恢复计划
                for failure in failures:
                    recovery_plan = self.recovery_engine.create_recovery_plan(failure)
                    
                    # 异步执行恢复计划
                    threading.Thread(
                        target=self.recovery_engine.execute_recovery_plan,
                        args=(recovery_plan,),
                        daemon=True
                    ).start()
            
        except Exception as e:
            logger.error(f"处理健康状态变化失败: {e}")
    
    def _register_default_recovery_callbacks(self):
        """注册默认恢复回调"""
        
        def restart_service_callback(failure_event: FailureEvent) -> bool:
            """重启服务回调"""
            logger.info(f"执行服务重启: 节点 {failure_event.node_id}")
            # 这里应该实现实际的服务重启逻辑
            return True
        
        def failover_node_callback(failure_event: FailureEvent) -> bool:
            """节点故障转移回调"""
            logger.info(f"执行节点故障转移: 节点 {failure_event.node_id}")
            # 这里应该实现实际的故障转移逻辑
            return True
        
        def scale_up_callback(failure_event: FailureEvent) -> bool:
            """扩容回调"""
            logger.info(f"执行系统扩容: 节点 {failure_event.node_id}")
            # 这里应该实现实际的扩容逻辑
            return True
        
        def isolate_node_callback(failure_event: FailureEvent) -> bool:
            """隔离节点回调"""
            logger.info(f"执行节点隔离: 节点 {failure_event.node_id}")
            # 这里应该实现实际的节点隔离逻辑
            return True
        
        def notify_admin_callback(failure_event: FailureEvent) -> bool:
            """通知管理员回调"""
            logger.warning(f"通知管理员: 节点 {failure_event.node_id} 发生故障 - {failure_event.description}")
            # 这里应该实现实际的通知逻辑（邮件、短信、钉钉等）
            return True
        
        def auto_heal_callback(failure_event: FailureEvent) -> bool:
            """自动修复回调"""
            logger.info(f"执行自动修复: 节点 {failure_event.node_id}")
            # 这里应该实现实际的自动修复逻辑
            return True
        
        # 注册回调
        self.recovery_engine.register_recovery_callback(RecoveryAction.RESTART_SERVICE, restart_service_callback)
        self.recovery_engine.register_recovery_callback(RecoveryAction.FAILOVER_NODE, failover_node_callback)
        self.recovery_engine.register_recovery_callback(RecoveryAction.SCALE_UP, scale_up_callback)
        self.recovery_engine.register_recovery_callback(RecoveryAction.ISOLATE_NODE, isolate_node_callback)
        self.recovery_engine.register_recovery_callback(RecoveryAction.NOTIFY_ADMIN, notify_admin_callback)
        self.recovery_engine.register_recovery_callback(RecoveryAction.AUTO_HEAL, auto_heal_callback)
    
    def register_custom_recovery_callback(self, action: RecoveryAction, callback: Callable):
        """注册自定义恢复回调"""
        self.recovery_engine.register_recovery_callback(action, callback)
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统整体状态"""
        try:
            failure_stats = self.failure_detector.get_failure_statistics()
            recovery_stats = self.recovery_engine.get_recovery_statistics()
            
            return {
                'enabled': self.enabled,
                'monitoring_active': self.health_monitor.monitoring_active,
                'failure_statistics': failure_stats,
                'recovery_statistics': recovery_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取系统状态失败: {e}")
            return {'error': str(e)}
    
    def get_node_status(self, node_id: str) -> Dict[str, Any]:
        """获取特定节点状态"""
        try:
            health_trend = self.health_monitor.get_node_health_trend(node_id)
            failure_stats = self.failure_detector.get_failure_statistics(node_id)
            
            return {
                'node_id': node_id,
                'health_trend': health_trend,
                'failure_statistics': failure_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取节点状态失败: {e}")
            return {'error': str(e)}

# 全局实例
fault_tolerance_manager = FaultToleranceManager()

def get_fault_tolerance_manager() -> FaultToleranceManager:
    """获取故障容错管理器实例"""
    return fault_tolerance_manager
