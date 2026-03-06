#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
统一性能监控协调器

整合GPU、内存、线程等多种性能监控，提供统一的监控接口和数据分析

作者: Hikyuu UI系统
版本: 1.0
"""

import time
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import json

from loguru import logger

# 导入监控模块（已移除GPU监控）
try:
    from .memory_monitor import MemoryMonitor, MemoryMetrics, MemoryStatus  
    from .thread_monitor import ThreadMonitor, ThreadMetrics, ThreadStatus
except ImportError as e:
    logger.error(f"性能监控模块导入失败: {e}")
    # 为避免导入错误，创建模拟类
    class MemoryMetrics:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    
    class ThreadMetrics:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

class PerformanceCategory(Enum):
    """性能监控类别"""

    MEMORY = "memory"
    THREAD = "thread"
    RENDERING = "rendering"
    NETWORK = "network"
    ALL = "all"

class AlertSeverity(Enum):
    """告警严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class UnifiedPerformanceMetrics:
    """统一性能指标"""
    # GPU监控已移除
    
    # 内存指标
    memory_metrics: Optional[MemoryMetrics] = None
    
    # 线程指标
    thread_metrics: Optional[ThreadMetrics] = None
    
    # 渲染指标
    rendering_fps: float = 0.0
    rendering_latency_ms: float = 0.0
    rendering_queue_length: int = 0
    
    # 网络指标
    network_latency_ms: float = 0.0
    network_throughput_mbps: float = 0.0
    network_error_rate: float = 0.0
    
    # 综合指标
    overall_performance_score: float = 1.0
    system_health_score: float = 1.0
    optimization_potential: float = 0.0
    
    # 告警信息
    active_alerts: List[str] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

@dataclass
class PerformanceAlert:
    """性能告警"""
    alert_id: str
    category: PerformanceCategory
    severity: AlertSeverity
    title: str
    description: str
    current_value: float
    threshold_value: float
    timestamp: float
    resolved: bool = False
    resolution_time: Optional[float] = None
    metrics_data: Dict[str, Any] = field(default_factory=dict)

class UnifiedPerformanceCoordinator:
    """统一性能监控协调器"""
    
    def __init__(self):
        # 监控实例（已移除GPU监控）
        self.memory_monitor = None
        self.thread_monitor = None
        
        # 监控状态
        self.unified_metrics = UnifiedPerformanceMetrics()
        self.metrics_history = deque(maxlen=2000)  # 保存最近2000条记录
        
        # 监控线程
        self.monitoring_active = False
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # 回调函数
        self.metrics_callbacks: List[Callable[[UnifiedPerformanceMetrics], None]] = []
        self.alert_callbacks: List[Callable[[PerformanceAlert], None]] = []
        
        # 告警管理
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_history: List[PerformanceAlert] = deque(maxlen=500)
        
        # 配置
        self.monitoring_interval = 1.0  # 监控间隔（秒）
        self.alert_cooldown = 60.0      # 告警冷却时间（秒）
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'total_collections': 0,
            'alerts_generated': 0,
            'alerts_resolved': 0,
            'error_count': 0,
            'last_system_health_score': 1.0
        }
        
        logger.info("统一性能监控协调器初始化完成")
    
    def initialize_monitors(self, enable_memory: bool = True, 
                          enable_thread: bool = True) -> bool:
        """初始化监控组件"""
        try:
            success = True
            
            # GPU监控功能已移除
            
            # 初始化内存监控
            if enable_memory:
                try:
                    from .memory_monitor import get_memory_monitor
                    self.memory_monitor = get_memory_monitor()
                    success &= True  # 内存监控无需额外初始化
                    logger.info("内存监控初始化成功")
                except Exception as e:
                    logger.error(f"内存监控初始化失败: {e}")
                    success = False
            
            # 初始化线程监控
            if enable_thread:
                try:
                    from .thread_monitor import get_thread_monitor
                    self.thread_monitor = get_thread_monitor()
                    success &= True  # 线程监控无需额外初始化
                    logger.info("线程监控初始化成功")
                except Exception as e:
                    logger.error(f"线程监控初始化失败: {e}")
                    success = False
            
            # 移除GPU监控回调函数
            
            if self.memory_monitor:
                self.memory_monitor.add_metrics_callback(self._on_memory_metrics)
                self.memory_monitor.add_alert_callback(self._on_memory_alert)
            
            if self.thread_monitor:
                self.thread_monitor.add_metrics_callback(self._on_thread_metrics)
                self.thread_monitor.add_alert_callback(self._on_thread_alert)
            
            # 添加统一回调
            self.add_metrics_callback(self._update_unified_metrics)
            
            logger.info(f"性能监控组件初始化完成，结果: {'成功' if success else '失败'}")
            return success
            
        except Exception as e:
            logger.error(f"初始化监控组件失败: {e}")
            self.stats['error_count'] += 1
            return False
    
    def _on_memory_metrics(self, memory_metrics):
        """内存指标回调"""
        self.unified_metrics.memory_metrics = memory_metrics
        logger.debug(f"收到内存指标: 使用率={memory_metrics.system_memory_usage_percent:.2%}")
    
    def _on_thread_metrics(self, thread_metrics):
        """线程指标回调"""
        self.unified_metrics.thread_metrics = thread_metrics
        logger.debug(f"收到线程指标: 活跃线程={thread_metrics.active_threads_count}")
    
    def _on_memory_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """内存告警回调"""
        alert = PerformanceAlert(
            alert_id=f"memory_{alert_type}_{int(time.time())}",
            category=PerformanceCategory.MEMORY,
            severity=AlertSeverity.ERROR if 'critical' in alert_type.lower() else AlertSeverity.WARNING,
            title=f"Memory {alert_type}",
            description=alert_data.get('description', f'Memory {alert_type} detected'),
            current_value=alert_data.get('current_value', 0),
            threshold_value=alert_data.get('threshold', 0),
            timestamp=time.time(),
            metrics_data=alert_data
        )
        self._handle_alert(alert)
    
    def _on_thread_alert(self, alert_type: str, alert_data: Dict[str, Any]):
        """线程告警回调"""
        alert = PerformanceAlert(
            alert_id=f"thread_{alert_type}_{int(time.time())}",
            category=PerformanceCategory.THREAD,
            severity=AlertSeverity.WARNING,
            title=f"Thread {alert_type}",
            description=alert_data.get('description', f'Thread {alert_type} detected'),
            current_value=alert_data.get('current_value', 0),
            threshold_value=alert_data.get('threshold', 0),
            timestamp=time.time(),
            metrics_data=alert_data
        )
        self._handle_alert(alert)
    
    def _handle_alert(self, alert: PerformanceAlert):
        """处理告警"""
        # 检查告警冷却时间
        recent_alert = self.active_alerts.get(alert.alert_id.split('_')[0])
        if (recent_alert and 
            time.time() - recent_alert.timestamp < self.alert_cooldown):
            return
        
        # 添加到活跃告警
        self.active_alerts[alert.alert_id] = alert
        self.stats['alerts_generated'] += 1
        
        # 更新统一指标的活跃告警
        self.unified_metrics.active_alerts.append(alert.alert_id)
        
        # 触发告警回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"告警回调执行失败: {e}")
        
        logger.warning(f"生成性能告警: {alert.title} - {alert.description}")
    
    def _update_unified_metrics(self, unified_metrics: UnifiedPerformanceMetrics):
        """更新统一指标"""
        try:
            # 计算综合性能评分
            scores = []
            

            
            if unified_metrics.memory_metrics:
                memory_score = 1.0 - unified_metrics.memory_metrics.memory_pressure_level
                scores.append(memory_score)
            
            if unified_metrics.thread_metrics:
                thread_score = unified_metrics.thread_metrics.thread_quality_score
                scores.append(thread_score)
            
            # 计算系统健康评分
            if scores:
                unified_metrics.overall_performance_score = sum(scores) / len(scores)
                self.stats['last_system_health_score'] = unified_metrics.overall_performance_score
            
            # 计算优化潜力
            optimization_potential = 0.0
            
            if unified_metrics.memory_metrics:
                if unified_metrics.memory_metrics.memory_fragmentation_rate > 0.2:
                    optimization_potential += 0.3
                if unified_metrics.memory_metrics.memory_leak_detection > 0.1:
                    optimization_potential += 0.2
            
            if unified_metrics.thread_metrics:
                if unified_metrics.thread_metrics.deadlock_risk_level > 0.5:
                    optimization_potential += 0.2
                if unified_metrics.thread_metrics.load_balancing_efficiency < 0.8:
                    optimization_potential += 0.1
            

            
            unified_metrics.optimization_potential = min(1.0, optimization_potential)
            
            # 检查关键问题
            critical_issues = []
            
            if (unified_metrics.memory_metrics and 
                unified_metrics.memory_metrics.memory_status == MemoryStatus.CRITICAL):
                critical_issues.append("critical_memory_usage")
            

            
            if (unified_metrics.thread_metrics and 
                unified_metrics.thread_metrics.thread_status == ThreadStatus.DEADLOCKED):
                critical_issues.append("thread_deadlock")
            
            unified_metrics.critical_issues = critical_issues
            
        except Exception as e:
            logger.error(f"更新统一指标失败: {e}")
            self.stats['error_count'] += 1
    
    def add_metrics_callback(self, callback: Callable[[UnifiedPerformanceMetrics], None]):
        """添加指标回调函数"""
        self.metrics_callbacks.append(callback)
        logger.debug(f"添加统一指标回调函数: {callback.__name__}")
    
    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """添加告警回调函数"""
        self.alert_callbacks.append(callback)
        logger.debug(f"添加告警回调函数: {callback.__name__}")
    
    def start_monitoring(self, interval: float = 1.0) -> bool:
        """开始统一监控"""
        if self.monitoring_active:
            logger.warning("统一性能监控已在运行")
            return True
        
        try:
            self.monitoring_interval = interval
            
            # 启动各个监控器（GPU监控已移除）
            if self.memory_monitor and not self.memory_monitor.monitoring_active:
                self.memory_monitor.start_monitoring(interval)
            
            if self.thread_monitor and not self.thread_monitor.monitoring_active:
                self.thread_monitor.start_monitoring(interval)
            
            # 启动统一监控循环
            logger.info(f"开始统一性能监控，间隔: {interval}秒")
            
            self.monitoring_active = True
            self.stop_event.clear()
            self.stats['start_time'] = time.time()
            
            def monitoring_loop():
                while self.monitoring_active and not self.stop_event.is_set():
                    try:
                        self.stats['total_collections'] += 1
                        
                        # 收集所有监控数据
                        self._collect_all_metrics()
                        
                        # 保存历史记录
                        self.metrics_history.append(self.unified_metrics)
                        
                        # 清理过期的告警
                        self._cleanup_expired_alerts()
                        
                        # 触发统一指标回调
                        for callback in self.metrics_callbacks:
                            try:
                                callback(self.unified_metrics)
                            except Exception as e:
                                logger.error(f"统一指标回调执行失败: {e}")
                        
                        time.sleep(interval)
                        
                    except Exception as e:
                        logger.error(f"统一监控循环异常: {e}")
                        self.stats['error_count'] += 1
                        time.sleep(interval)
            
            self.monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info("统一性能监控已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动统一性能监控失败: {e}")
            self.monitoring_active = False
            return False
    
    def _collect_all_metrics(self):
        """收集所有监控数据（已移除GPU监控）"""
        try:
            # 手动触发指标收集（如果监控器未运行）
            if self.memory_monitor and not self.memory_monitor.monitoring_active:
                self.memory_monitor.collect_all_metrics()
            
            if self.thread_monitor and not self.thread_monitor.monitoring_active:
                self.thread_monitor.collect_all_metrics()
            
        except Exception as e:
            logger.error(f"收集监控数据失败: {e}")
            self.stats['error_count'] += 1
    
    def _cleanup_expired_alerts(self):
        """清理过期的告警"""
        current_time = time.time()
        expired_alerts = []
        
        for alert_id, alert in self.active_alerts.items():
            # 清理1小时前的告警
            if current_time - alert.timestamp > 3600:
                expired_alerts.append(alert_id)
        
        for alert_id in expired_alerts:
            alert = self.active_alerts.pop(alert_id, None)
            if alert and not alert.resolved:
                alert.resolved = True
                alert.resolution_time = current_time
                self.stats['alerts_resolved'] += 1
                
                # 从统一指标中移除
                if alert_id in self.unified_metrics.active_alerts:
                    self.unified_metrics.active_alerts.remove(alert_id)
                
                # 添加到历史记录
                self.alert_history.append(alert)
                
                logger.info(f"告警已自动解决: {alert.title}")
    
    def stop_monitoring(self):
        """停止统一监控"""
        if not self.monitoring_active:
            logger.warning("统一性能监控未运行")
            return
        
        try:
            logger.info("停止统一性能监控...")
            
            self.monitoring_active = False
            self.stop_event.set()
            
            # 停止各个监控器（GPU监控已移除）
            if self.memory_monitor:
                self.memory_monitor.stop_monitoring()
            
            if self.thread_monitor:
                self.thread_monitor.stop_monitoring()
            
            # 停止监控线程
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=3.0)
            
            logger.info("统一性能监控已停止")
            
        except Exception as e:
            logger.error(f"停止统一性能监控失败: {e}")
    
    def is_monitoring(self) -> bool:
        """检查监控是否正在运行"""
        return self.monitoring_active
    
    def get_current_metrics(self) -> UnifiedPerformanceMetrics:
        """获取当前统一指标"""
        return self.unified_metrics
    
    def get_metrics_history(self, count: int = 100) -> List[UnifiedPerformanceMetrics]:
        """获取历史统一指标"""
        return list(self.metrics_history)[-count:]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        try:
            # 最近的指标
            recent_metrics = self.get_metrics_history(60)  # 最近1分钟
            
            if not recent_metrics:
                return {'status': 'no_data'}
            
            # 计算平均值（已移除GPU监控）
            avg_memory_usage = 0.0
            avg_cpu_util = 0.0
            avg_performance_score = 0.0
            
            memory_count = 0
            thread_count = 0
            
            for metrics in recent_metrics:
                if metrics.memory_metrics:
                    avg_memory_usage += metrics.memory_metrics.system_memory_usage_percent
                    memory_count += 1
                
                if metrics.thread_metrics:
                    avg_cpu_util += metrics.thread_metrics.cpu_utilization_percent
                    thread_count += 1
                
                avg_performance_score += metrics.overall_performance_score
            
            if memory_count > 0:
                avg_memory_usage /= memory_count
            if thread_count > 0:
                avg_cpu_util /= thread_count
            
            avg_performance_score /= len(recent_metrics)
            
            # 活跃告警统计
            alert_stats = {
                'total_active': len(self.active_alerts),
                'by_category': defaultdict(int),
                'by_severity': defaultdict(int)
            }
            
            for alert in self.active_alerts.values():
                alert_stats['by_category'][alert.category.value] += 1
                alert_stats['by_severity'][alert.severity.value] += 1
            
            return {
                'system_health': {
                    'overall_score': avg_performance_score,
                    'memory_usage': avg_memory_usage,
                    'cpu_utilization': avg_cpu_util
                },
                'alerts': dict(alert_stats),
                'performance_trends': {
                    'performance_score_trend': 'stable',  # 简化实现
                    'resource_usage_trend': 'normal'
                },
                'optimization_suggestions': self._generate_optimization_suggestions()
            }
            
        except Exception as e:
            logger.error(f"获取性能摘要失败: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _generate_optimization_suggestions(self) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        try:
            # 基于当前指标生成建议
            if self.unified_metrics.memory_metrics:
                if self.unified_metrics.memory_metrics.memory_fragmentation_rate > 0.2:
                    suggestions.append("考虑进行内存碎片整理以提高性能")
                
                if self.unified_metrics.memory_metrics.memory_leak_detection > 0.1:
                    suggestions.append("检测到内存泄漏，建议检查代码中的资源管理")
            
            if self.unified_metrics.thread_metrics:
                if self.unified_metrics.thread_metrics.deadlock_risk_level > 0.5:
                    suggestions.append("存在死锁风险，建议检查线程同步机制")
                
                if self.unified_metrics.thread_metrics.thread_starvation_level > 0.6:
                    suggestions.append("线程饥饿，建议增加线程池大小或优化任务分配")
            

            
            if not suggestions:
                suggestions.append("系统运行良好，当前无需特殊优化")
            
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            suggestions.append("无法生成优化建议")
        
        return suggestions
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """获取告警摘要"""
        try:
            return {
                'active_alerts': len(self.active_alerts),
                'recent_alerts': len([a for a in self.alert_history 
                                    if time.time() - a.timestamp < 3600]),
                'by_category': {cat.value: len([a for a in self.active_alerts.values() 
                                             if a.category == cat]) 
                               for cat in PerformanceCategory},
                'by_severity': {sev.value: len([a for a in self.active_alerts.values() 
                                              if a.severity == sev]) 
                              for sev in AlertSeverity}
            }
            
        except Exception as e:
            logger.error(f"获取告警摘要失败: {e}")
            return {'status': 'error'}
    
    def export_metrics(self, filepath: str, format_type: str = 'json') -> bool:
        """导出指标数据"""
        try:
            export_data = {
                'export_time': time.time(),
                'metrics_history': [
                    {
                        'timestamp': m.timestamp,

                        'memory_metrics': m.memory_metrics.__dict__ if m.memory_metrics else None,
                        'thread_metrics': m.thread_metrics.__dict__ if m.thread_metrics else None,
                        'overall_performance_score': m.overall_performance_score,
                        'active_alerts': m.active_alerts
                    }
                    for m in self.get_metrics_history()
                ],
                'alert_history': [
                    {
                        'alert_id': a.alert_id,
                        'category': a.category.value,
                        'severity': a.severity.value,
                        'title': a.title,
                        'timestamp': a.timestamp,
                        'resolved': a.resolved
                    }
                    for a in list(self.alert_history)
                ],
                'statistics': self.stats
            }
            
            if format_type.lower() == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                logger.info(f"指标数据已导出到: {filepath}")
                return True
            else:
                logger.error(f"不支持的导出格式: {format_type}")
                return False
                
        except Exception as e:
            logger.error(f"导出指标数据失败: {e}")
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            **self.stats,
            'monitoring_active': self.monitoring_active,

            'memory_monitor_active': self.memory_monitor.monitoring_active if self.memory_monitor else False,
            'thread_monitor_active': self.thread_monitor.monitoring_active if self.thread_monitor else False,
            'total_alerts': len(self.active_alerts) + len(self.alert_history),
            'monitoring_interval': self.monitoring_interval
        }

# 全局统一性能监控实例
_global_performance_coordinator = None

def get_unified_performance_coordinator() -> UnifiedPerformanceCoordinator:
    """获取全局统一性能监控实例"""
    global _global_performance_coordinator
    if _global_performance_coordinator is None:
        _global_performance_coordinator = UnifiedPerformanceCoordinator()
    return _global_performance_coordinator


# 兼容重定向：优先使用完整版（core/performance）
# 如果需要使用完整版，推荐直接导入:
# from core.performance.unified_performance_coordinator import get_performance_coordinator
def get_performance_coordinator():
    """
    获取统一性能协调器（兼容重定向）
    
    此函数保留用于向后兼容。
    推荐直接使用 core.performance.unified_performance_coordinator.get_performance_coordinator()
    """
    try:
        from core.performance.unified_performance_coordinator import get_performance_coordinator as _get_coord
        return _get_coord()
    except ImportError:
        # 降级到简化版
        return get_unified_performance_coordinator()