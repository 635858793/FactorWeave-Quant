"""
自动化修复动作服务
基于监控数据自动执行修复操作
"""

import asyncio
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

from .bettafish_advanced_monitoring_service import (
    BettaFishAdvancedMonitoringService, 
    PerformanceTrend, 
    AnomalyDetectionResult,
    AlertSeverity
)
from .bettafish_monitoring_service import Alert, ComponentStatus


class RemediationActionType(Enum):
    """修复动作类型"""
    RESTART_SERVICE = "restart_service"
    RESTART_AGENT = "restart_agent"
    SCALE_RESOURCES = "scale_resources"
    ADJUST_THRESHOLDS = "adjust_thresholds"
    CLEAR_CACHE = "clear_cache"
    RESTART_DATABASE = "restart_database"
    RESTART_EVENT_BUS = "restart_event_bus"
    RECONFIGURE_SERVICE = "reconfigure_service"
    TRIGGER_GARBAGE_COLLECTION = "trigger_gc"
    EXECUTE_SCRIPT = "execute_script"
    SEND_NOTIFICATION = "send_notification"
    ESCALATE_ALERT = "escalate_alert"


class RemediationStatus(Enum):
    """修复动作执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class RemediationSeverity(Enum):
    """修复动作严重性级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RemediationCondition:
    """修复动作触发条件"""
    metric_name: str
    component: str
    threshold_value: float
    comparison_operator: str  # ">", "<", ">=", "<=", "==", "!="
    duration_seconds: int  # 持续时间阈值
    severity: RemediationSeverity
    consecutive_count: int = 1  # 连续触发次数要求


@dataclass
class RemediationAction:
    """修复动作定义"""
    action_id: str
    name: str
    action_type: RemediationActionType
    target_component: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_delay_seconds: int = 10
    cooldown_seconds: int = 300  # 冷却时间，避免重复执行
    enabled: bool = True
    description: str = ""
    prerequisites: List[str] = field(default_factory=list)  # 前置条件动作ID列表


@dataclass
class RemediationExecution:
    """修复动作执行记录"""
    execution_id: str
    action: RemediationAction
    trigger_alert: Optional[Alert]
    trigger_trend: Optional[PerformanceTrend]
    trigger_anomaly: Optional[AnomalyDetectionResult]
    status: RemediationStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    execution_log: List[str] = field(default_factory=list)


class RemediationActionHandler:
    """修复动作处理器基类"""
    
    def __init__(self, name: str):
        self.name = name
        self._executor = ThreadPoolExecutor(max_workers=2)
    
    async def execute(self, action: RemediationAction, context: Dict[str, Any]) -> tuple[bool, str]:
        """
        执行修复动作
        
        Args:
            action: 修复动作配置
            context: 执行上下文，包含监控数据和状态信息
            
        Returns:
            (success, message): 执行成功标志和结果消息
        """
        raise NotImplementedError
    
    def _log_execution(self, execution: RemediationExecution, message: str):
        """记录执行日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        execution.execution_log.append(log_entry)
        logger.info(f"Remediation {execution.execution_id}: {log_entry}")


class RestartServiceHandler(RemediationActionHandler):
    """重启服务处理器"""
    
    def __init__(self):
        super().__init__("RestartService")
    
    async def execute(self, action: RemediationAction, context: Dict[str, Any]) -> tuple[bool, str]:
        """执行服务重启"""
        execution = context.get("execution")
        service_name = action.target_component
        timeout = action.timeout_seconds
        
        self._log_execution(execution, f"Starting service restart for {service_name}")
        
        try:
            logger.warning("============================================")
            logger.warning(f"服务重启操作({service_name})为桩实现：")
            logger.warning(f"  1. 停止服务: 跳过（桩）")
            logger.warning(f"  2. 等待停止: 跳过（桩）")
            logger.warning(f"  3. 启动服务: 跳过（桩）")
            logger.warning(f"  4. 验证状态: 跳过（桩）")
            logger.warning(f"请配置真实的服务管理API以启用自动修复功能。")
            logger.warning("============================================")

            self._log_execution(execution, f"Service restart for {service_name} is a stub - no actual operations performed")
            return False, f"服务 {service_name} 重启为桩实现，未执行实际操作。请配置服务管理API。"
            
        except Exception as e:
            error_msg = f"Failed to restart service {service_name}: {str(e)}"
            self._log_execution(execution, error_msg)
            return False, error_msg


class RestartAgentHandler(RemediationActionHandler):
    """重启Agent处理器"""
    
    def __init__(self):
        super().__init__("RestartAgent")
    
    async def execute(self, action: RemediationAction, context: Dict[str, Any]) -> tuple[bool, str]:
        """执行Agent重启"""
        execution = context.get("execution")
        agent_name = action.target_component
        timeout = action.timeout_seconds
        
        self._log_execution(execution, f"Starting agent restart for {agent_name}")
        
        try:
            logger.warning("============================================")
            logger.warning(f"Agent重启操作({agent_name})为桩实现：")
            logger.warning(f"  1. 停止Agent: 跳过（桩）")
            logger.warning(f"  2. 清理Agent状态: 跳过（桩）")
            logger.warning(f"  3. 启动Agent: 跳过（桩）")
            logger.warning(f"  4. 验证Agent状态: 跳过（桩）")
            logger.warning(f"请配置真实的Agent管理API以启用自动修复功能。")
            logger.warning("============================================")

            self._log_execution(execution, f"Agent restart for {agent_name} is a stub - no actual operations performed")
            return False, f"Agent {agent_name} 重启为桩实现，未执行实际操作。请配置Agent管理API。"
            
        except Exception as e:
            error_msg = f"Failed to restart agent {agent_name}: {str(e)}"
            self._log_execution(execution, error_msg)
            return False, error_msg


class ScaleResourcesHandler(RemediationActionHandler):
    """资源扩展处理器"""
    
    def __init__(self):
        super().__init__("ScaleResources")
    
    async def execute(self, action: RemediationAction, context: Dict[str, Any]) -> tuple[bool, str]:
        """执行资源扩展"""
        execution = context.get("execution")
        target_component = action.target_component
        scale_factor = action.parameters.get("scale_factor", 2.0)
        resource_type = action.parameters.get("resource_type", "cpu")
        
        self._log_execution(execution, f"Scaling {resource_type} resources for {target_component} by factor {scale_factor}")
        
        try:
            logger.warning("============================================")
            logger.warning(f"资源扩展操作({target_component})为桩实现：")
            logger.warning(f"  类型: {resource_type}, 因子: {scale_factor}")
            logger.warning(f"  1. 检查当前使用情况: 跳过（桩）")
            logger.warning(f"  2. 计算新分配: 跳过（桩）")
            logger.warning(f"  3. 应用扩展: 跳过（桩）")
            logger.warning(f"  4. 验证效果: 跳过（桩）")
            logger.warning(f"请配置真实的资源管理API以启用自动扩展功能。")
            logger.warning("============================================")

            self._log_execution(execution, f"Resource scaling for {target_component} is a stub - no actual operations performed")
            return False, f"资源扩展({target_component})为桩实现，未执行实际操作。请配置资源管理API。"
            
        except Exception as e:
            error_msg = f"Failed to scale resources for {target_component}: {str(e)}"
            self._log_execution(execution, error_msg)
            return False, error_msg


class ClearCacheHandler(RemediationActionHandler):
    """清理缓存处理器"""
    
    def __init__(self):
        super().__init__("ClearCache")
    
    async def execute(self, action: RemediationAction, context: Dict[str, Any]) -> tuple[bool, str]:
        """执行缓存清理"""
        execution = context.get("execution")
        target_component = action.target_component
        cache_types = action.parameters.get("cache_types", ["memory", "disk"])
        
        self._log_execution(execution, f"Clearing cache for {target_component}, types: {cache_types}")
        
        try:
            logger.warning("============================================")
            logger.warning(f"缓存清理操作({target_component})为桩实现：")
            logger.warning(f"  缓存类型: {cache_types}")
            logger.warning(f"请配置真实的缓存管理API以启用自动清理功能。")
            logger.warning("============================================")

            self._log_execution(execution, f"Cache clearing for {target_component} is a stub - no actual operations performed")
            return False, f"缓存清理({target_component})为桩实现，未执行实际操作。请配置缓存管理API。"
            
        except Exception as e:
            error_msg = f"Failed to clear cache for {target_component}: {str(e)}"
            self._log_execution(execution, error_msg)
            return False, error_msg


class ExecuteScriptHandler(RemediationActionHandler):
    """执行脚本处理器"""
    
    def __init__(self):
        super().__init__("ExecuteScript")
    
    async def execute(self, action: RemediationAction, context: Dict[str, Any]) -> tuple[bool, str]:
        """执行自定义脚本"""
        execution = context.get("execution")
        script_path = action.parameters.get("script_path")
        script_args = action.parameters.get("script_args", [])
        
        if not script_path:
            return False, "Script path not specified"
        
        self._log_execution(execution, f"Executing script: {script_path} {' '.join(script_args)}")
        
        try:
            logger.warning("============================================")
            logger.warning(f"脚本执行操作({script_path})为桩实现：")
            logger.warning(f"  参数: {script_args}")
            logger.warning(f"请配置真实的脚本执行环境以启用自动修复功能。")
            logger.warning("============================================")

            self._log_execution(execution, f"Script execution for {script_path} is a stub - no actual operations performed")
            return False, f"脚本执行({script_path})为桩实现，未执行实际操作。请配置脚本执行环境。"
            
        except Exception as e:
            error_msg = f"Failed to execute script {script_path}: {str(e)}"
            self._log_execution(execution, error_msg)
            return False, error_msg


class SendNotificationHandler(RemediationActionHandler):
    """发送通知处理器"""
    
    def __init__(self):
        super().__init__("SendNotification")
    
    async def execute(self, action: RemediationAction, context: Dict[str, Any]) -> tuple[bool, str]:
        """发送通知"""
        execution = context.get("execution")
        notification_type = action.parameters.get("type", "email")
        recipients = action.parameters.get("recipients", [])
        message = action.parameters.get("message", "")
        
        self._log_execution(execution, f"Sending {notification_type} notification to {recipients}")
        
        try:
            logger.warning("============================================")
            logger.warning(f"通知发送操作({notification_type})为桩实现：")
            logger.warning(f"  收件人: {recipients}")
            logger.warning(f"  消息: {message}")
            logger.warning(f"请配置真实的通信服务API以启用自动通知功能。")
            logger.warning("============================================")

            self._log_execution(execution, f"Notification sending is a stub - no actual operations performed")
            return False, f"通知发送({notification_type})为桩实现，未执行实际操作。请配置通信服务API。"
            
        except Exception as e:
            error_msg = f"Failed to send notification: {str(e)}"
            self._log_execution(execution, error_msg)
            return False, error_msg


class AutomatedRemediationService:
    """自动化修复服务"""
    
    def __init__(self, monitoring_service: BettaFishAdvancedMonitoringService):
        self.monitoring_service = monitoring_service
        self.actions: Dict[str, RemediationAction] = {}
        self.conditions: Dict[str, RemediationCondition] = {}
        self.executions: Dict[str, RemediationExecution] = {}
        
        # 修复动作处理器
        self.action_handlers = {
            RemediationActionType.RESTART_SERVICE: RestartServiceHandler(),
            RemediationActionType.RESTART_AGENT: RestartAgentHandler(),
            RemediationActionType.SCALE_RESOURCES: ScaleResourcesHandler(),
            RemediationActionType.CLEAR_CACHE: ClearCacheHandler(),
            RemediationActionType.EXECUTE_SCRIPT: ExecuteScriptHandler(),
            RemediationActionType.SEND_NOTIFICATION: SendNotificationHandler(),
        }
        
        # 条件匹配状态跟踪
        self.condition_match_counts: Dict[str, int] = {}
        self.last_execution_times: Dict[str, datetime] = {}
        
        # 锁确保线程安全
        self._lock = threading.Lock()
        
        logger.info("AutomatedRemediationService initialized")

    def register_action(self, action: RemediationAction) -> None:
        """注册修复动作"""
        with self._lock:
            self.actions[action.action_id] = action
            logger.info(f"Registered remediation action: {action.action_id} - {action.name}")

    def register_condition(self, condition: RemediationCondition) -> None:
        """注册修复条件"""
        with self._lock:
            condition_key = f"{condition.component}_{condition.metric_name}"
            self.conditions[condition_key] = condition
            logger.info(f"Registered remediation condition: {condition_key}")

    def _should_execute_action(self, action: RemediationAction, current_time: datetime) -> tuple[bool, str]:
        """判断是否应该执行修复动作"""
        # 检查冷却时间
        if action.action_id in self.last_execution_times:
            last_execution = self.last_execution_times[action.action_id]
            if (current_time - last_execution).total_seconds() < action.cooldown_seconds:
                remaining_cooldown = action.cooldown_seconds - (current_time - last_execution).total_seconds()
                return False, f"Action in cooldown, {remaining_cooldown:.0f}s remaining"
        
        # 检查前置条件
        if action.prerequisites:
            for prereq_id in action.prerequisites:
                if prereq_id not in self.executions:
                    return False, f"Prerequisite action {prereq_id} not executed"
                
                prereq_execution = self.executions[prereq_id]
                if prereq_execution.status != RemediationStatus.SUCCESS:
                    return False, f"Prerequisite action {prereq_id} failed"
        
        return True, "Action can be executed"

    def _check_condition_match(self, condition: RemediationCondition, alert: Alert) -> bool:
        """检查条件是否匹配"""
        try:
            # 检查组件匹配
            if alert.component != condition.component:
                return False
            
            # 检查指标匹配
            if alert.metric_name != condition.metric_name:
                return False
            
            # 检查比较操作符
            current_value = alert.current_value
            threshold_value = condition.threshold_value
            
            if condition.comparison_operator == ">" and current_value <= threshold_value:
                return False
            elif condition.comparison_operator == "<" and current_value >= threshold_value:
                return False
            elif condition.comparison_operator == ">=" and current_value < threshold_value:
                return False
            elif condition.comparison_operator == "<=" and current_value > threshold_value:
                return False
            elif condition.comparison_operator == "==" and abs(current_value - threshold_value) > 0.001:
                return False
            elif condition.comparison_operator == "!=" and abs(current_value - threshold_value) <= 0.001:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking condition match: {e}")
            return False

    def _increment_condition_match(self, condition_key: str) -> int:
        """增加条件匹配计数"""
        with self._lock:
            current_count = self.condition_match_counts.get(condition_key, 0)
            self.condition_match_counts[condition_key] = current_count + 1
            return self.condition_match_counts[condition_key]

    def _reset_condition_match(self, condition_key: str) -> None:
        """重置条件匹配计数"""
        with self._lock:
            self.condition_match_counts[condition_key] = 0

    def _get_matching_actions(self, alert: Alert) -> List[RemediationAction]:
        """获取匹配的修复动作"""
        matching_actions = []
        
        # 遍历所有条件，寻找匹配的条件
        for condition_key, condition in self.conditions.items():
            if self._check_condition_match(condition, alert):
                # 检查连续触发次数要求
                match_count = self._increment_condition_match(condition_key)
                
                if match_count >= condition.consecutive_count:
                    # 找到匹配的修复动作
                    for action in self.actions.values():
                        if action.target_component == condition.component and action.enabled:
                            matching_actions.append(action)
                    
                    # 重置计数
                    self._reset_condition_match(condition_key)
            else:
                # 条件不匹配，重置计数
                self._reset_condition_match(condition_key)
        
        return matching_actions

    async def _execute_action(self, action: RemediationAction, alert: Alert, 
                            trend: Optional[PerformanceTrend] = None,
                            anomaly: Optional[AnomalyDetectionResult] = None) -> RemediationExecution:
        """执行修复动作"""
        execution_id = f"exec_{action.action_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        execution = RemediationExecution(
            execution_id=execution_id,
            action=action,
            trigger_alert=alert,
            trigger_trend=trend,
            trigger_anomaly=anomaly,
            status=RemediationStatus.PENDING,
            start_time=datetime.now()
        )
        
        # 记录执行
        with self._lock:
            self.executions[execution_id] = execution
            self.last_execution_times[action.action_id] = datetime.now()
        
        try:
            # 检查是否应该执行
            should_execute, reason = self._should_execute_action(action, datetime.now())
            if not should_execute:
                execution.status = RemediationStatus.CANCELLED
                execution.result = reason
                execution.end_time = datetime.now()
                self._log_execution(execution, f"Action cancelled: {reason}")
                return execution
            
            # 执行修复动作
            execution.status = RemediationStatus.RUNNING
            self._log_execution(execution, f"Starting execution of action: {action.name}")
            
            # 获取处理器
            handler = self.action_handlers.get(action.action_type)
            if not handler:
                raise ValueError(f"No handler found for action type: {action.action_type}")
            
            # 准备执行上下文
            context = {
                "execution": execution,
                "alert": alert,
                "trend": trend,
                "anomaly": anomaly,
                "monitoring_service": self.monitoring_service
            }
            
            # 执行动作
            success, message = await handler.execute(action, context)
            
            if success:
                execution.status = RemediationStatus.SUCCESS
                execution.result = message
                self._log_execution(execution, f"Action completed successfully: {message}")
            else:
                execution.status = RemediationStatus.FAILED
                execution.error_message = message
                self._log_execution(execution, f"Action failed: {message}")
            
        except Exception as e:
            execution.status = RemediationStatus.FAILED
            execution.error_message = str(e)
            self._log_execution(execution, f"Action execution error: {e}")
        
        execution.end_time = datetime.now()
        return execution

    async def process_alert(self, alert: Alert) -> List[RemediationExecution]:
        """处理告警，触发相应的修复动作"""
        logger.info(f"Processing alert for remediation: {alert.component} - {alert.metric_name}")
        
        # 获取匹配的修复动作
        matching_actions = self._get_matching_actions(alert)
        
        if not matching_actions:
            logger.debug(f"No matching remediation actions found for alert: {alert.alert_id}")
            return []
        
        # 执行修复动作
        executions = []
        for action in matching_actions:
            try:
                execution = await self._execute_action(action, alert)
                executions.append(execution)
                
                logger.info(f"Remediation action executed: {action.action_id} - {execution.status.value}")
                
            except Exception as e:
                logger.error(f"Failed to execute remediation action {action.action_id}: {e}")
        
        return executions

    async def process_trend_alert(self, trend: PerformanceTrend) -> List[RemediationExecution]:
        """处理趋势告警"""
        logger.info(f"Processing trend alert for remediation: {trend.component} - {trend.metric_name}")
        
        # 创建模拟告警用于条件匹配
        mock_alert = Alert(
            alert_id=f"trend_{trend.component}_{trend.metric_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            component=trend.component,
            metric_name=f"{trend.metric_name}_trend",
            current_value=abs(trend.change_rate),
            threshold_value=0.2,  # 默认趋势阈值
            severity=AlertSeverity.WARNING,
            message=f"Trend analysis: {trend.direction.value} trend detected",
            timestamp=trend.analysis_time
        )
        
        return await self.process_alert(mock_alert)

    async def process_anomaly_alert(self, anomaly: AnomalyDetectionResult) -> List[RemediationExecution]:
        """处理异常告警"""
        logger.info(f"Processing anomaly alert for remediation: {anomaly.component} - {anomaly.metric_name}")
        
        # 创建模拟告警用于条件匹配
        mock_alert = Alert(
            alert_id=f"anomaly_{anomaly.component}_{anomaly.metric_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            component=anomaly.component,
            metric_name=f"{anomaly.metric_name}_anomaly",
            current_value=anomaly.anomaly_score,
            threshold_value=0.7,  # 默认异常阈值
            severity=anomaly.severity,
            message=f"Anomaly detected with score: {anomaly.anomaly_score:.2f}",
            timestamp=anomaly.detection_time
        )
        
        return await self.process_alert(mock_alert)

    def get_action_status(self, action_id: str) -> Optional[Dict[str, Any]]:
        """获取修复动作状态"""
        if action_id not in self.actions:
            return None
        
        action = self.actions[action_id]
        
        # 获取最近的执行记录
        recent_executions = [
            exec for exec in self.executions.values()
            if exec.action.action_id == action_id
        ]
        
        # 按时间排序，取最近的5次
        recent_executions.sort(key=lambda x: x.start_time, reverse=True)
        recent_executions = recent_executions[:5]
        
        return {
            "action_id": action_id,
            "name": action.name,
            "enabled": action.enabled,
            "last_execution": self.last_execution_times.get(action_id),
            "recent_executions": [
                {
                    "execution_id": exec.execution_id,
                    "status": exec.status.value,
                    "start_time": exec.start_time,
                    "end_time": exec.end_time,
                    "duration": (exec.end_time - exec.start_time).total_seconds() if exec.end_time else None,
                    "result": exec.result,
                    "error_message": exec.error_message
                }
                for exec in recent_executions
            ]
        }

    def get_all_actions_status(self) -> Dict[str, Any]:
        """获取所有修复动作状态"""
        return {
            action_id: self.get_action_status(action_id)
            for action_id in self.actions.keys()
        }

    def cleanup_old_executions(self, older_than_hours: int = 24) -> int:
        """清理旧的执行记录"""
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
        executions_to_remove = []
        
        with self._lock:
            for execution_id, execution in self.executions.items():
                if execution.start_time < cutoff_time:
                    executions_to_remove.append(execution_id)
            
            for execution_id in executions_to_remove:
                del self.executions[execution_id]
        
        logger.info(f"Cleaned up {len(executions_to_remove)} old execution records")
        return len(executions_to_remove)

    def load_default_actions(self):
        """加载默认修复动作配置"""
        # 高响应时间修复动作
        high_response_time_action = RemediationAction(
            action_id="restart_bettafish_agent_high_response",
            name="重启BettaFish Agent（高响应时间）",
            action_type=RemediationActionType.RESTART_AGENT,
            target_component="bettafish_agent",
            parameters={"restart_timeout": 60},
            timeout_seconds=120,
            max_retries=2,
            cooldown_seconds=600,  # 10分钟冷却
            description="当BettaFish Agent响应时间过高时自动重启"
        )
        self.register_action(high_response_time_action)
        
        # 高错误率修复动作
        high_error_rate_action = RemediationAction(
            action_id="clear_cache_high_error_rate",
            name="清理缓存（高错误率）",
            action_type=RemediationActionType.CLEAR_CACHE,
            target_component="bettafish_agent",
            parameters={"cache_types": ["memory", "disk"]},
            timeout_seconds=60,
            max_retries=1,
            cooldown_seconds=300,  # 5分钟冷却
            description="当BettaFish Agent错误率过高时清理缓存"
        )
        self.register_action(high_error_rate_action)
        
        # 资源不足修复动作
        resource_scaling_action = RemediationAction(
            action_id="scale_resources_high_usage",
            name="扩展资源（高使用率）",
            action_type=RemediationActionType.SCALE_RESOURCES,
            target_component="bettafish_agent",
            parameters={"scale_factor": 1.5, "resource_type": "memory"},
            timeout_seconds=300,
            max_retries=1,
            cooldown_seconds=1800,  # 30分钟冷却
            description="当资源使用率过高时自动扩展资源"
        )
        self.register_action(resource_scaling_action)
        
        # 严重告警通知动作
        critical_alert_notification = RemediationAction(
            action_id="notify_critical_alert",
            name="严重告警通知",
            action_type=RemediationActionType.SEND_NOTIFICATION,
            target_component="system",
            parameters={
                "type": "email",
                "recipients": ["admin@example.com"],
                "message": "检测到严重系统告警，需要立即关注"
            },
            timeout_seconds=30,
            max_retries=3,
            cooldown_seconds=0,  # 无冷却时间
            description="严重告警时发送通知"
        )
        self.register_action(critical_alert_notification)

    def load_default_conditions(self):
        """加载默认修复条件配置"""
        # 高响应时间条件
        high_response_condition = RemediationCondition(
            metric_name="response_time",
            component="bettafish_agent",
            threshold_value=5.0,
            comparison_operator=">",
            duration_seconds=300,  # 5分钟
            severity=RemediationSeverity.MEDIUM,
            consecutive_count=2
        )
        self.register_condition(high_response_condition)
        
        # 高错误率条件
        high_error_condition = RemediationCondition(
            metric_name="error_rate",
            component="bettafish_agent",
            threshold_value=0.1,
            comparison_operator=">",
            duration_seconds=180,  # 3分钟
            severity=RemediationSeverity.HIGH,
            consecutive_count=1
        )
        self.register_condition(high_error_condition)
        
        # 极高响应时间条件（触发重启）
        critical_response_condition = RemediationCondition(
            metric_name="response_time",
            component="bettafish_agent",
            threshold_value=10.0,
            comparison_operator=">",
            duration_seconds=60,  # 1分钟
            severity=RemediationSeverity.CRITICAL,
            consecutive_count=1
        )
        self.register_condition(critical_response_condition)
        
        # 异常检测条件
        anomaly_condition = RemediationCondition(
            metric_name="response_time_anomaly",
            component="bettafish_agent",
            threshold_value=0.8,
            comparison_operator=">",
            duration_seconds=120,  # 2分钟
            severity=RemediationSeverity.HIGH,
            consecutive_count=1
        )
        self.register_condition(anomaly_condition)

    def enable_action(self, action_id: str) -> bool:
        """启用修复动作"""
        if action_id in self.actions:
            self.actions[action_id].enabled = True
            logger.info(f"Enabled remediation action: {action_id}")
            return True
        return False

    def disable_action(self, action_id: str) -> bool:
        """禁用修复动作"""
        if action_id in self.actions:
            self.actions[action_id].enabled = False
            logger.info(f"Disabled remediation action: {action_id}")
            return True
        return False

    def update_action(self, action_id: str, updates: Dict[str, Any]) -> bool:
        """更新修复动作配置"""
        if action_id not in self.actions:
            return False
        
        action = self.actions[action_id]
        
        for key, value in updates.items():
            if hasattr(action, key):
                setattr(action, key, value)
        
        logger.info(f"Updated remediation action: {action_id}")
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """获取修复服务统计信息"""
        with self._lock:
            total_actions = len(self.actions)
            enabled_actions = sum(1 for action in self.actions.values() if action.enabled)
            total_executions = len(self.executions)
            
            status_counts = {}
            for execution in self.executions.values():
                status = execution.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            return {
                "total_actions": total_actions,
                "enabled_actions": enabled_actions,
                "disabled_actions": total_actions - enabled_actions,
                "total_executions": total_executions,
                "execution_status_counts": status_counts,
                "active_conditions": len(self.conditions),
                "condition_match_counts": len(self.condition_match_counts)
            }