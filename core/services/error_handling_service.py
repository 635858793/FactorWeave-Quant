"""
错误处理和容错机制服务
为BettaFish集成提供全面的错误处理和恢复机制
"""

import asyncio
import time
import traceback
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import json
import threading
from collections import defaultdict, deque
from loguru import logger


class ErrorSeverity(Enum):
    """错误严重性级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """错误类别"""
    NETWORK = "network"
    DATA = "data"
    PROCESSING = "processing"
    EXTERNAL_SERVICE = "external_service"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    """恢复动作类型"""
    RETRY = "retry"
    FALLBACK = "fallback"
    RESTART = "restart"
    ESCALATE = "escalate"
    IGNORE = "ignore"


@dataclass
class ErrorRecord:
    """错误记录数据类"""
    error_id: str
    timestamp: datetime
    service_name: str
    error_type: str
    severity: ErrorSeverity
    category: ErrorCategory
    message: str
    stack_trace: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_actions: List[RecoveryAction] = field(default_factory=list)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ErrorPattern:
    """错误模式"""
    pattern_id: str
    error_type: str
    category: ErrorCategory
    detection_rules: Dict[str, Any]
    recovery_strategy: List[RecoveryAction]
    cooldown_period: int = 300  # 5分钟冷却期
    last_occurrence: Optional[datetime] = None
    occurrence_count: int = 0


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self, max_errors_per_service: int = 100):
        self.max_errors_per_service = max_errors_per_service
        self.error_patterns: Dict[str, ErrorPattern] = {}
        self.error_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_errors_per_service))
        self.service_error_counts: Dict[str, int] = defaultdict(int)
        self.service_error_reset_time: Dict[str, datetime] = {}
        self.pattern_cooldowns: Dict[str, datetime] = {}
        self.lock = threading.Lock()
        
        # 注册默认错误模式
        self._register_default_patterns()
        
        # 错误恢复回调
        self.recovery_callbacks: Dict[str, Callable] = {}
    
    def _register_default_patterns(self):
        """注册默认错误模式"""
        # BettaFish相关错误模式
        self.register_error_pattern(
            "bettafish_connection_timeout",
            "ConnectionTimeout",
            ErrorCategory.NETWORK,
            {"timeout_threshold": 30.0, "service_name": "bettafish"},
            [RecoveryAction.RETRY, RecoveryAction.FALLBACK]
        )
        
        self.register_error_pattern(
            "bettafish_analysis_failure",
            "AnalysisFailed",
            ErrorCategory.PROCESSING,
            {"service_name": "bettafish", "agent_failure": True},
            [RecoveryAction.RETRY, RecoveryAction.ESCALATE]
        )
        
        # 数据服务错误模式
        self.register_error_pattern(
            "data_provider_failure",
            "DataProviderError",
            ErrorCategory.DATA,
            {"service_type": "data_provider"},
            [RecoveryAction.FALLBACK, RecoveryAction.IGNORE]
        )
        
        # 外部服务错误模式
        self.register_error_pattern(
            "external_api_failure",
            "ExternalAPIError",
            ErrorCategory.EXTERNAL_SERVICE,
            {"external_service": True},
            [RecoveryAction.RETRY, RecoveryAction.FALLBACK]
        )
        
        # 资源配置错误模式
        self.register_error_pattern(
            "resource_exhaustion",
            "ResourceExhaustion",
            ErrorCategory.RESOURCE,
            {"memory_usage": 95, "cpu_usage": 90},
            [RecoveryAction.RESTART, RecoveryAction.ESCALATE]
        )
    
    def register_error_pattern(self, pattern_id: str, error_type: str, category: ErrorCategory,
                              detection_rules: Dict[str, Any], 
                              recovery_strategy: List[RecoveryAction],
                              cooldown_period: int = 300):
        """注册错误模式"""
        pattern = ErrorPattern(
            pattern_id=pattern_id,
            error_type=error_type,
            category=category,
            detection_rules=detection_rules,
            recovery_strategy=recovery_strategy,
            cooldown_period=cooldown_period
        )
        
        self.error_patterns[pattern_id] = pattern
        logger.info(f"Registered error pattern: {pattern_id}")
    
    def register_recovery_callback(self, service_name: str, callback: Callable):
        """注册服务恢复回调"""
        self.recovery_callbacks[service_name] = callback
        logger.info(f"Registered recovery callback for service: {service_name}")
    
    def handle_error(self, service_name: str, error: Exception, 
                    context: Dict[str, Any] = None) -> ErrorRecord:
        """处理错误"""
        with self.lock:
            try:
                # 生成错误记录
                error_record = self._create_error_record(service_name, error, context or {})
                
                # 记录错误历史
                self.error_history[service_name].append(error_record)
                self.service_error_counts[service_name] += 1
                
                # 检查错误模式
                matched_patterns = self._match_error_patterns(error_record)
                
                # 执行恢复策略
                recovery_results = []
                for pattern in matched_patterns:
                    result = self._execute_recovery_strategy(pattern, error_record)
                    recovery_results.append(result)
                
                # 检查是否需要触发熔断器
                if self._should_trigger_circuit_breaker(service_name):
                    self._trigger_circuit_breaker(service_name, error_record)
                
                # 发送错误通知
                self._send_error_notification(error_record, matched_patterns)
                
                logger.error(f"Error handled for {service_name}: {error}")
                return error_record
                
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
                # 返回一个基本的错误记录
                return ErrorRecord(
                    error_id=f"handler_error_{time.time()}",
                    timestamp=datetime.now(),
                    service_name=service_name,
                    error_type="HandlerError",
                    severity=ErrorSeverity.CRITICAL,
                    category=ErrorCategory.UNKNOWN,
                    message=str(e),
                    stack_trace=traceback.format_exc()
                )
    
    def _create_error_record(self, service_name: str, error: Exception, 
                           context: Dict[str, Any]) -> ErrorRecord:
        """创建错误记录"""
        error_id = f"{service_name}_{error.__class__.__name__}_{time.time()}"
        
        # 分类错误
        error_category = self._categorize_error(error, context)
        error_severity = self._determine_severity(error, context)
        
        return ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(),
            service_name=service_name,
            error_type=error.__class__.__name__,
            severity=error_severity,
            category=error_category,
            message=str(error),
            stack_trace=traceback.format_exc(),
            context=context.copy(),
            max_retries=context.get("max_retries", 3)
        )
    
    def _categorize_error(self, error: Exception, context: Dict[str, Any]) -> ErrorCategory:
        """分类错误"""
        error_name = error.__class__.__name__.lower()
        
        if any(word in error_name for word in ["timeout", "connection", "network"]):
            return ErrorCategory.NETWORK
        elif any(word in error_name for word in ["data", "database", "sql"]):
            return ErrorCategory.DATA
        elif any(word in error_name for word in ["processing", "analysis", "calculation"]):
            return ErrorCategory.PROCESSING
        elif any(word in error_name for word in ["api", "external", "service"]):
            return ErrorCategory.EXTERNAL_SERVICE
        elif any(word in error_name for word in ["config", "setting", "parameter"]):
            return ErrorCategory.CONFIGURATION
        elif any(word in error_name for word in ["auth", "permission", "access"]):
            return ErrorCategory.AUTHENTICATION
        elif any(word in error_name for word in ["memory", "resource", "disk"]):
            return ErrorCategory.RESOURCE
        else:
            return ErrorCategory.UNKNOWN
    
    def _determine_severity(self, error: Exception, context: Dict[str, Any]) -> ErrorSeverity:
        """确定错误严重性"""
        error_name = error.__class__.__name__.lower()
        
        # 关键系统错误
        if any(word in error_name for word in ["system", "critical", "fatal"]):
            return ErrorSeverity.CRITICAL
        
        # 数据和业务逻辑错误
        if any(word in error_name for word in ["data", "validation", "business"]):
            return ErrorSeverity.HIGH
        
        # 网络和服务错误
        if any(word in error_name for word in ["timeout", "connection", "service"]):
            return ErrorSeverity.MEDIUM
        
        # 轻度警告
        return ErrorSeverity.LOW
    
    def _match_error_patterns(self, error_record: ErrorRecord) -> List[ErrorPattern]:
        """匹配错误模式"""
        matched_patterns = []
        
        for pattern in self.error_patterns.values():
            # 检查冷却期
            if (pattern.pattern_id in self.pattern_cooldowns and 
                datetime.now() < self.pattern_cooldowns[pattern.pattern_id]):
                continue
            
            # 匹配规则检查
            if self._pattern_matches(pattern, error_record):
                matched_patterns.append(pattern)
                pattern.last_occurrence = datetime.now()
                pattern.occurrence_count += 1
                
                # 设置冷却期
                self.pattern_cooldowns[pattern.pattern_id] = (
                    datetime.now() + timedelta(seconds=pattern.cooldown_period)
                )
        
        return matched_patterns
    
    def _pattern_matches(self, pattern: ErrorPattern, error_record: ErrorRecord) -> bool:
        """检查错误模式是否匹配"""
        # 基本属性匹配
        if pattern.error_type != error_record.error_type:
            return False
        
        if pattern.category != error_record.category:
            return False
        
        # 详细规则检查
        for rule_key, rule_value in pattern.detection_rules.items():
            if rule_key == "service_name":
                if error_record.context.get("service_name") != rule_value:
                    return False
            elif rule_key == "timeout_threshold":
                timeout = error_record.context.get("timeout", 0)
                if timeout < rule_value:
                    return False
            elif rule_key == "memory_usage":
                memory_usage = error_record.context.get("memory_usage", 0)
                if memory_usage < rule_value:
                    return False
            elif rule_key == "cpu_usage":
                cpu_usage = error_record.context.get("cpu_usage", 0)
                if cpu_usage < rule_value:
                    return False
        
        return True
    
    def _execute_recovery_strategy(self, pattern: ErrorPattern, 
                                 error_record: ErrorRecord) -> Dict[str, Any]:
        """执行恢复策略"""
        results = []
        
        for action in pattern.recovery_strategy:
            try:
                if action == RecoveryAction.RETRY:
                    result = self._execute_retry(error_record)
                elif action == RecoveryAction.FALLBACK:
                    result = self._execute_fallback(error_record)
                elif action == RecoveryAction.RESTART:
                    result = self._execute_restart(error_record)
                elif action == RecoveryAction.ESCALATE:
                    result = self._execute_escalation(error_record)
                elif action == RecoveryAction.IGNORE:
                    result = {"status": "ignored", "action": action.value}
                else:
                    result = {"status": "unknown_action", "action": action.value}
                
                results.append({
                    "action": action.value,
                    "result": result,
                    "timestamp": datetime.now()
                })

            except Exception as e:
                logger.error(f"Recovery action {action.value} failed: {e}")
                results.append({
                    "action": action.value,
                    "result": {"status": "failed", "error": str(e)},
                    "timestamp": datetime.now()
                })
        
        return {
            "pattern_id": pattern.pattern_id,
            "actions_executed": results,
            "timestamp": datetime.now()
        }
    
    def _execute_retry(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """执行重试操作"""
        if error_record.retry_count < error_record.max_retries:
            error_record.retry_count += 1
            return {
                "status": "retry_scheduled",
                "retry_count": error_record.retry_count,
                "max_retries": error_record.max_retries
            }
        else:
            return {
                "status": "max_retries_reached",
                "retry_count": error_record.retry_count
            }
    
    def _execute_fallback(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """执行降级操作"""
        service_name = error_record.service_name
        
        # 调用服务特定的降级回调
        if service_name in self.recovery_callbacks:
            try:
                callback_result = self.recovery_callbacks[service_name](
                    "fallback", error_record
                )
                return {
                    "status": "fallback_executed",
                    "callback_result": callback_result
                }
            except Exception as e:
                return {
                    "status": "fallback_failed",
                    "error": str(e)
                }
        else:
            return {
                "status": "no_fallback_available",
                "service": service_name
            }
    
    def _execute_restart(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """执行重启操作"""
        service_name = error_record.service_name
        
        # 调用服务重启逻辑
        if service_name in self.recovery_callbacks:
            try:
                callback_result = self.recovery_callbacks[service_name](
                    "restart", error_record
                )
                return {
                    "status": "restart_executed",
                    "callback_result": callback_result
                }
            except Exception as e:
                return {
                    "status": "restart_failed",
                    "error": str(e)
                }
        else:
            return {
                "status": "no_restart_available",
                "service": service_name
            }
    
    def _execute_escalation(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """执行升级操作"""
        # 发送告警通知
        notification = {
            "type": "error_escalation",
            "severity": error_record.severity.value,
            "service": error_record.service_name,
            "error": error_record.message,
            "timestamp": datetime.now()
        }
        
        # 这里应该集成告警系统
        logger.critical(f"Error escalation: {json.dumps(notification)}")

        return {
            "status": "escalated",
            "notification": notification
        }
    
    def _should_trigger_circuit_breaker(self, service_name: str) -> bool:
        """检查是否应该触发熔断器"""
        current_time = datetime.now()
        
        # 重置错误计数（每小时重置一次）
        reset_time = self.service_error_reset_time.get(service_name)
        if reset_time is None or (current_time - reset_time).total_seconds() > 3600:
            self.service_error_counts[service_name] = 0
            self.service_error_reset_time[service_name] = current_time
        
        # 如果错误计数超过阈值，触发熔断器
        error_threshold = 10  # 10次错误后触发熔断器
        return self.service_error_counts[service_name] >= error_threshold
    
    def _trigger_circuit_breaker(self, service_name: str, error_record: ErrorRecord):
        """触发熔断器"""
        logger.critical(f"Circuit breaker triggered for service: {service_name}")
        
        # 这里应该集成熔断器逻辑
        # 可以通过事件总线通知熔断器组件
        circuit_breaker_event = {
            "type": "circuit_breaker_triggered",
            "service_name": service_name,
            "trigger_time": datetime.now(),
            "error_record": asdict(error_record)
        }
        
        logger.critical(f"Circuit breaker event: {json.dumps(circuit_breaker_event)}")
    
    def _send_error_notification(self, error_record: ErrorRecord, patterns: List[ErrorPattern]):
        """发送错误通知"""
        if error_record.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            notification = {
                "type": "error_notification",
                "severity": error_record.severity.value,
                "service": error_record.service_name,
                "error_type": error_record.error_type,
                "message": error_record.message,
                "patterns_matched": len(patterns),
                "timestamp": error_record.timestamp
            }
            
            logger.warning(f"Error notification: {json.dumps(notification)}")
    
    def get_error_statistics(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """获取错误统计信息"""
        with self.lock:
            if service_name:
                error_history = list(self.error_history[service_name])
                total_errors = self.service_error_counts.get(service_name, 0)
            else:
                error_history = []
                total_errors = 0
                for history in self.error_history.values():
                    error_history.extend(list(history))
                total_errors = sum(self.service_error_counts.values())
            
            # 按类别统计
            category_counts = defaultdict(int)
            severity_counts = defaultdict(int)
            recent_errors = []
            
            for error in error_history:
                category_counts[error.category.value] += 1
                severity_counts[error.severity.value] += 1
                
                # 最近1小时的错误
                if (datetime.now() - error.timestamp).total_seconds() < 3600:
                    recent_errors.append(error)
            
            return {
                "total_errors": total_errors,
                "recent_errors": len(recent_errors),
                "category_distribution": dict(category_counts),
                "severity_distribution": dict(severity_counts),
                "active_patterns": len(self.error_patterns),
                "service_breakdown": dict(self.service_error_counts)
            }
    
    def resolve_error(self, error_id: str, service_name: str):
        """标记错误为已解决"""
        with self.lock:
            for error in self.error_history[service_name]:
                if error.error_id == error_id:
                    error.resolved = True
                    error.resolution_time = datetime.now()
                    break


class BettaFishErrorHandler:
    """BettaFish专用错误处理器"""
    
    def __init__(self, fallback_service, feature_control_service):
        self.fallback_service = fallback_service
        self.feature_control_service = feature_control_service
        self.error_handler = ErrorHandler()
        self.logger = logger
        
        # 注册BettaFish相关的恢复回调
        self._register_bettafish_callbacks()
        
        # 错误统计
        self.bettafish_error_stats = {
            "total_errors": 0,
            "resolved_errors": 0,
            "fallback_activations": 0,
            "circuit_breaker_trips": 0
        }
    
    def _register_bettafish_callbacks(self):
        """注册BettaFish相关的回调函数"""
        self.error_handler.register_recovery_callback("bettafish", self._handle_bettafish_error)
        self.error_handler.register_recovery_callback("sentiment_agent", self._handle_agent_error)
        self.error_handler.register_recovery_callback("news_agent", self._handle_agent_error)
        self.error_handler.register_recovery_callback("technical_agent", self._handle_agent_error)
        self.error_handler.register_recovery_callback("risk_agent", self._handle_agent_error)
    
    def handle_bettafish_error(self, service_name: str, error: Exception, 
                             context: Dict[str, Any] = None) -> Dict[str, Any]:
        """处理BettaFish相关错误"""
        try:
            # 记录错误
            error_record = self.error_handler.handle_error(service_name, error, context or {})
            self.bettafish_error_stats["total_errors"] += 1
            
            # 检查是否需要禁用BettaFish功能
            if self._should_disable_bettafish(error_record):
                self._disable_bettafish_feature()
                self.bettafish_error_stats["circuit_breaker_trips"] += 1
            
            # 尝试自动恢复
            recovery_result = self._attempt_auto_recovery(error_record)
            
            # 更新统计
            if error_record.resolved:
                self.bettafish_error_stats["resolved_errors"] += 1
            
            return {
                "error_record": error_record,
                "recovery_result": recovery_result,
                "bettafish_enabled": self.feature_control_service.is_feature_enabled("bettafish"),
                "fallback_activated": self._is_fallback_activated()
            }
            
        except Exception as e:
            self.logger.error(f"BettaFish error handling failed: {e}")
            return {
                "status": "error_handling_failed",
                "original_error": str(error),
                "handler_error": str(e)
            }
    
    def _should_disable_bettafish(self, error_record: ErrorRecord) -> bool:
        """判断是否应该禁用BettaFish功能"""
        # 关键错误或连续错误导致系统不稳定
        if error_record.severity == ErrorSeverity.CRITICAL:
            return True
        
        # 检查最近1小时内的高严重性错误数量
        recent_critical_errors = 0
        error_history = self.error_handler.error_history.get("bettafish", [])
        
        for error in error_history:
            if ((datetime.now() - error.timestamp).total_seconds() < 3600 and 
                error.severity == ErrorSeverity.CRITICAL):
                recent_critical_errors += 1
        
        # 如果1小时内有3个或以上关键错误，禁用功能
        return recent_critical_errors >= 3
    
    def _disable_bettafish_feature(self):
        """禁用BettaFish功能"""
        try:
            self.feature_control_service.disable_feature("bettafish")
            self.logger.warning("BettaFish feature disabled due to repeated critical errors")
        except Exception as e:
            self.logger.error(f"Failed to disable BettaFish feature: {e}")
    
    def _attempt_auto_recovery(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """尝试自动恢复"""
        try:
            # 根据错误类型尝试不同的恢复策略
            if error_record.category == ErrorCategory.NETWORK:
                return self._recover_from_network_error(error_record)
            elif error_record.category == ErrorCategory.PROCESSING:
                return self._recover_from_processing_error(error_record)
            elif error_record.category == ErrorCategory.EXTERNAL_SERVICE:
                return self._recover_from_external_service_error(error_record)
            else:
                return {"status": "no_recovery_strategy", "error_type": error_record.category.value}
                
        except Exception as e:
            self.logger.error(f"Auto recovery failed: {e}")
            return {"status": "recovery_failed", "error": str(e)}
    
    def _recover_from_network_error(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """从网络错误恢复"""
        # 重试连接
        if error_record.retry_count < error_record.max_retries:
            return {"status": "retry_scheduled", "retry_count": error_record.retry_count + 1}
        else:
            # 切换到降级模式
            self.bettafish_error_stats["fallback_activations"] += 1
            return {"status": "fallback_activated", "reason": "network_error_max_retries"}
    
    def _recover_from_processing_error(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """从处理错误恢复"""
        # 重启相关组件
        if error_record.service_name in self.error_handler.recovery_callbacks:
            try:
                self.error_handler.recovery_callbacks[error_record.service_name]("restart", error_record)
                return {"status": "component_restarted", "service": error_record.service_name}
            except Exception as e:
                return {"status": "restart_failed", "error": str(e)}
        else:
            return {"status": "no_restart_available", "service": error_record.service_name}
    
    def _recover_from_external_service_error(self, error_record: ErrorRecord) -> Dict[str, Any]:
        """从外部服务错误恢复"""
        # 尝试使用备用服务或降级到基本功能
        self.bettafish_error_stats["fallback_activations"] += 1
        return {"status": "fallback_to_basic_functionality", "reason": "external_service_error"}
    
    def _handle_bettafish_error(self, action: str, error_record: ErrorRecord) -> Any:
        """处理BettaFish错误的具体回调"""
        if action == "fallback":
            # 激活降级模式
            self.bettafish_error_stats["fallback_activations"] += 1
            return {"status": "fallback_activated", "service": "bettafish"}
        
        elif action == "restart":
            # 重启BettaFish服务
            return {"status": "restart_initiated", "service": "bettafish"}
        
        elif action == "escalate":
            # 升级到管理员通知
            return {"status": "escalated", "service": "bettafish"}
        
        return {"status": "unknown_action", "action": action}
    
    def _handle_agent_error(self, action: str, error_record: ErrorRecord) -> Any:
        """处理Agent错误的回调"""
        if action == "restart":
            # 重启特定的Agent
            agent_name = error_record.service_name
            return {"status": f"{agent_name}_restart_initiated"}
        
        elif action == "fallback":
            # Agent降级处理
            return {"status": f"{error_record.service_name}_fallback_activated"}
        
        return {"status": "unknown_agent_action", "action": action}
    
    def _is_fallback_activated(self) -> bool:
        """检查是否激活了降级模式"""
        return self.bettafish_error_stats["fallback_activations"] > 0
    
    def get_bettafish_error_status(self) -> Dict[str, Any]:
        """获取BettaFish错误状态"""
        return {
            **self.bettafish_error_stats,
            "feature_enabled": self.feature_control_service.is_feature_enabled("bettafish"),
            "system_status": self.fallback_service.get_system_status(),
            "error_statistics": self.error_handler.get_error_statistics("bettafish")
        }
    
    async def graceful_shutdown(self):
        """优雅关闭错误处理服务"""
        try:
            # 保存错误统计信息
            stats = self.get_bettafish_error_status()
            self.logger.info(f"BettaFish error handler shutting down with stats: {stats}")
            
            # 清理资源
            # 这里可以添加清理逻辑
            
        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")


# 全局错误处理服务实例
_bettafish_error_handler: Optional[BettaFishErrorHandler] = None


def get_bettafish_error_handler() -> Optional[BettaFishErrorHandler]:
    """获取全局BettaFish错误处理器"""
    return _bettafish_error_handler


def initialize_bettafish_error_handler(fallback_service, feature_control_service):
    """初始化BettaFish错误处理器"""
    global _bettafish_error_handler
    _bettafish_error_handler = BettaFishErrorHandler(fallback_service, feature_control_service)
    return _bettafish_error_handler