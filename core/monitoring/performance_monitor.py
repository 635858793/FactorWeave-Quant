"""
综合性能监控系统

该模块提供全面的性能监控和分析功能，包括：
- 实时性能指标收集
- 性能瓶颈识别
- 自动性能调优建议
- 性能报告生成
"""

import time
from loguru import logger
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import numpy as np
import pandas as pd
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

# loguru logger 已在第12行导入

@dataclass
class PerformanceMetric:
    """性能指标数据结构"""
    timestamp: float
    metric_type: str  # 'render_time', 'memory_usage', 'gpu_usage', etc.
    value: float
    unit: str  # 'ms', 'MB', '%', etc.
    component: str  # 'volume', 'kline', 'chart', etc.
    additional_data: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.additional_data:
            data['additional_data'] = self.additional_data
        return data

@dataclass
class PerformanceAlert:
    """性能警报数据结构"""
    level: str  # 'info', 'warning', 'error', 'critical'
    message: str
    component: str
    metric_value: float
    threshold: float
    timestamp: float
    suggested_action: str = None

class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(self):
        self.metrics_history = defaultdict(lambda: deque(maxlen=1000))
        self.thresholds = {
            'render_time': {
                'volume': {'warning': 100, 'critical': 200},  # ms
                'kline': {'warning': 150, 'critical': 300},
                'chart': {'warning': 200, 'critical': 400}
            },
            'memory_usage': {
                'volume': {'warning': 500, 'critical': 1000},  # MB
                'kline': {'warning': 800, 'critical': 1500},
                'chart': {'warning': 1000, 'critical': 2000}
            },

        }
        
    def add_metric(self, metric: PerformanceMetric) -> List[PerformanceAlert]:
        """添加性能指标并检查是否触发警报"""
        self.metrics_history[metric.component].append(metric)
        return self._check_thresholds(metric)
    
    def _check_thresholds(self, metric: PerformanceMetric) -> List[PerformanceAlert]:
        """检查性能阈值是否超限"""
        alerts = []
        
        # 检查阈值
        if metric.metric_type in self.thresholds:
            component_thresholds = self.thresholds[metric.metric_type].get(metric.component, {})
            
            for level, threshold in component_thresholds.items():
                if metric.value > threshold:
                    alert = PerformanceAlert(
                        level=level,
                        message=f"{metric.component} {metric.metric_type} 超过阈值: {metric.value:.2f}{metric.unit} > {threshold}{metric.unit}",
                        component=metric.component,
                        metric_value=metric.value,
                        threshold=threshold,
                        timestamp=metric.timestamp,
                        suggested_action=self._get_suggested_action(metric.metric_type, metric.component, metric.value, threshold)
                    )
                    alerts.append(alert)
        
        return alerts
    
    def _get_suggested_action(self, metric_type: str, component: str, value: float, threshold: float) -> str:
        """获取性能优化建议"""
        suggestions = {
            ('render_time', 'volume'): "建议启用虚拟滚动或数据采样优化",
            ('render_time', 'kline'): "建议启用GPU加速或降低K线质量",
            ('memory_usage', 'volume'): "建议清理图表缓存或启用虚拟滚动"
        }
        return suggestions.get((metric_type, component), "建议进行性能分析和优化")
    
    def get_performance_summary(self, component: str = None, time_range_minutes: int = 10) -> Dict[str, Any]:
        """获取性能摘要"""
        now = time.time()
        cutoff_time = now - (time_range_minutes * 60)
        
        if component:
            relevant_metrics = [m for m in self.metrics_history[component] 
                             if m.timestamp > cutoff_time]
        else:
            relevant_metrics = []
            for comp_metrics in self.metrics_history.values():
                relevant_metrics.extend([m for m in comp_metrics if m.timestamp > cutoff_time])
        
        if not relevant_metrics:
            return {'status': 'no_data', 'message': '指定时间范围内没有性能数据'}
        
        # 计算统计信息
        summary = {
            'timestamp_range': {
                'start': min(m.timestamp for m in relevant_metrics),
                'end': max(m.timestamp for m in relevant_metrics),
                'duration_minutes': (max(m.timestamp for m in relevant_metrics) - min(m.timestamp for m in relevant_metrics)) / 60
            },
            'metrics_count': len(relevant_metrics),
            'components': list(set(m.component for m in relevant_metrics)),
            'metric_types': list(set(m.metric_type for m in relevant_metrics)),
            'statistics': {}
        }
        
        # 按指标类型分组计算统计信息
        for metric_type in set(m.metric_type for m in relevant_metrics):
            type_metrics = [m for m in relevant_metrics if m.metric_type == metric_type]
            values = [m.value for m in type_metrics]
            
            summary['statistics'][metric_type] = {
                'count': len(values),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'mean': float(np.mean(values)),
                'median': float(np.median(values)),
                'std': float(np.std(values)),
                'p95': float(np.percentile(values, 95)),
                'p99': float(np.percentile(values, 99))
            }
        
        return summary
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """获取性能优化建议"""
        recommendations = []
        
        # 分析最近10分钟的渲染时间
        volume_summary = self.get_performance_summary('volume', 10)
        if 'statistics' in volume_summary:
            volume_stats = volume_summary['statistics'].get('render_time', {})
            if volume_stats.get('p95', 0) > 100:  # 95%分位数超过100ms
                recommendations.append({
                    'priority': 'high',
                    'category': 'volume_rendering',
                    'issue': f'成交量渲染95%分位数达到 {volume_stats["p95"]:.1f}ms',
                    'recommendation': '启用虚拟滚动和数据采样优化',
                    'expected_improvement': '50-80%的性能提升'
                })
        
        # 分析内存使用
        chart_summary = self.get_performance_summary('chart', 10)
        if 'statistics' in chart_summary:
            memory_stats = chart_summary['statistics'].get('memory_usage', {})
            if memory_stats.get('max', 0) > 1000:  # 最大内存使用超过1GB
                recommendations.append({
                    'priority': 'medium',
                    'category': 'memory_management',
                    'issue': f'最大内存使用达到 {memory_stats["max"]:.0f}MB',
                    'recommendation': '启用图表缓存清理和内存优化',
                    'expected_improvement': '20-40%的内存节省'
                })
        
        return recommendations

class PerformanceMonitor(QObject):
    """综合性能监控主类"""
    
    # 信号定义
    metric_recorded = pyqtSignal(object)  # PerformanceMetric
    alert_raised = pyqtSignal(object)     # PerformanceAlert
    recommendation_updated = pyqtSignal(object)  # List[Dict]
    performance_summary_updated = pyqtSignal(object)  # Dict
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        
        self.config = config or {}
        self.analyzer = PerformanceAnalyzer()
        self.monitoring_enabled = True
        self.auto_report_enabled = self.config.get('auto_report', True)

        # R78 幂等规范 (HVD-241-P0-C-1): 显式初始化, 与 dispose() 的 _disposed 短路对齐
        self._disposed = False
        
        # 告警规则引擎
        self.alert_rule_engine = None
        self._connect_alert_system()
        
        # 实时监控
        self.monitoring_timer = QTimer()
        self.monitoring_timer.timeout.connect(self._periodic_monitoring)
        self.monitoring_timer.start(5000)  # 每5秒监控一次
        
        # 性能报告定时器
        if self.auto_report_enabled:
            self.report_timer = QTimer()
            self.report_timer.timeout.connect(self._generate_periodic_report)
            self.report_timer.start(300000)  # 每5分钟生成报告
        
        # 性能统计
        self.session_stats = {
            'start_time': time.time(),
            'total_metrics': 0,
            'alerts_raised': 0,
            'optimizations_applied': 0
        }
        
        # 性能回调函数
        self.performance_callbacks = []
        
        logger.info("综合性能监控系统已启动")
    
    def start_monitoring(self) -> None:
        """开始性能监控"""
        self.monitoring_enabled = True
        logger.info("性能监控已启用")
    
    def stop_monitoring(self) -> None:
        """停止性能监控"""
        self.monitoring_enabled = False
        logger.info("性能监控已禁用")

    def dispose(self) -> None:
        """释放资源 (R239-P0-004, 2026-08-02)

        Why: QObject, 2 个 QTimer (monitoring_timer L210-212 每 5 秒 +
             report_timer L216-218 每 5 分钟) 启动后永不停 → 线程/定时器泄漏
             (子智能体 A 交叉验证确认 P0)
        Fix: R78 4 链标准 — _disposed 幂等短路 + 停 QTimer + 置监控标志
             + 清空回调/统计 + 解除告警引擎引用
        TDD: tests/test_r239_p0_dispose_chains.py
        """
        if getattr(self, '_disposed', False):
            return
        try:
            self.monitoring_enabled = False

            # 1. 停止 QTimer (getattr 防御 __new__ 构造场景)
            for timer_name in ('monitoring_timer', 'report_timer'):
                timer = getattr(self, timer_name, None)
                if timer is not None and getattr(timer, 'isActive', lambda: False)():
                    try:
                        timer.stop()
                    except Exception:
                        pass

            # 2. 清空回调与统计
            callbacks = getattr(self, 'performance_callbacks', None)
            if callbacks is not None:
                self.performance_callbacks = []

            stats = getattr(self, 'session_stats', None)
            if stats is not None:
                self.session_stats = {}

            # 3. 解除引用
            self.alert_rule_engine = None

            self._disposed = True
            logger.info("PerformanceMonitor disposed")

        except Exception as e:
            logger.warning(f"PerformanceMonitor dispose 失败: {e}")
            self._disposed = True
    
    def _connect_alert_system(self) -> None:
        """连接告警系统"""
        try:
            from core.services.alert_rule_engine import AlertRuleEngine
            from core.services.alert_deduplication_service import AlertDeduplicationService
            
            dedup_service = AlertDeduplicationService()
            self.alert_rule_engine = AlertRuleEngine(dedup_service)
            
            # 连接告警信号
            self.alert_raised.connect(self._on_alert_raised)
            
            logger.info("PerformanceMonitor 已与 AlertRuleEngine 集成")
            
        except Exception as e:
            logger.error(f"连接告警系统失败: {e}")
    
    def _on_alert_raised(self, alert: PerformanceAlert) -> None:
        """处理告警信号"""
        if self.alert_rule_engine:
            try:
                # 将 PerformanceAlert 转换为指标数据
                metrics = {
                    "alert_level": alert.level,
                    "alert_category": "performance",
                    "alert_message": alert.message,
                    "metric_name": alert.component,
                    "metric_value": alert.metric_value,
                    "threshold": alert.threshold,
                    "timestamp": alert.timestamp
                }
                
                # 评估规则
                import asyncio
                loop = asyncio.get_event_loop()
                loop.create_task(self.alert_rule_engine.evaluate_rules(metrics))
                
            except Exception as e:
                logger.error(f"处理告警信号失败: {e}")
    
    def record_metric(self, metric_type: str, value: float, unit: str, 
                     component: str, additional_data: Dict[str, Any] = None) -> List[PerformanceAlert]:
        """记录性能指标"""
        if not self.monitoring_enabled:
            return []
        
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_type=metric_type,
            value=value,
            unit=unit,
            component=component,
            additional_data=additional_data or {}
        )
        
        # 添加指标
        alerts = self.analyzer.add_metric(metric)
        
        # 更新统计
        self.session_stats['total_metrics'] += 1
        self.session_stats['alerts_raised'] += len(alerts)
        
        # 发送信号
        self.metric_recorded.emit(metric)
        for alert in alerts:
            self.alert_raised.emit(alert)
        
        # 调用性能回调
        for callback in self.performance_callbacks:
            try:
                callback(metric, alerts)
            except Exception as e:
                logger.warning(f"性能回调执行失败: {e}")
        
        return alerts
    
    def record_render_time(self, component: str, render_time_ms: float, 
                          additional_data: Dict[str, Any] = None) -> List[PerformanceAlert]:
        """记录渲染时间"""
        return self.record_metric(
            metric_type='render_time',
            value=render_time_ms,
            unit='ms',
            component=component,
            additional_data=additional_data
        )
    
    def record_memory_usage(self, component: str, memory_mb: float, 
                           additional_data: Dict[str, Any] = None) -> List[PerformanceAlert]:
        """记录内存使用量"""
        return self.record_metric(
            metric_type='memory_usage',
            value=memory_mb,
            unit='MB',
            component=component,
            additional_data=additional_data
        )
    

    
    def add_performance_callback(self, callback: Callable) -> None:
        """添加性能监控回调函数"""
        self.performance_callbacks.append(callback)
        logger.info("性能监控回调已添加")
    
    def remove_performance_callback(self, callback: Callable) -> None:
        """移除性能监控回调函数"""
        if callback in self.performance_callbacks:
            self.performance_callbacks.remove(callback)
            logger.info("性能监控回调已移除")
    
    def get_performance_summary(self, component: str = None, time_range_minutes: int = 10) -> Dict[str, Any]:
        """获取性能摘要"""
        return self.analyzer.get_performance_summary(component, time_range_minutes)
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """获取优化建议"""
        return self.analyzer.get_optimization_recommendations()
    
    def _periodic_monitoring(self) -> None:
        """周期性监控"""
        try:
            # 更新性能摘要
            summary = self.get_performance_summary()
            self.performance_summary_updated.emit(summary)
            
            # 更新优化建议
            recommendations = self.get_optimization_recommendations()
            self.recommendation_updated.emit(recommendations)
            
            # 检查会话统计
            session_duration = time.time() - self.session_stats['start_time']
            if session_duration > 3600:  # 每小时重置一次会话统计
                self._reset_session_stats()
                
        except Exception as e:
            logger.error(f"周期性监控执行失败: {e}")
    
    def _generate_periodic_report(self) -> None:
        """生成周期性性能报告"""
        try:
            report = self.generate_performance_report()
            self._save_report_to_file(report)
            
        except Exception as e:
            logger.error(f"生成周期性报告失败: {e}")
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """生成完整的性能报告"""
        session_duration = time.time() - self.session_stats['start_time']
        
        report = {
            'report_timestamp': datetime.now().isoformat(),
            'session_info': {
                'duration_minutes': session_duration / 60,
                'total_metrics': self.session_stats['total_metrics'],
                'alerts_raised': self.session_stats['alerts_raised'],
                'optimizations_applied': self.session_stats['optimizations_applied']
            },
            'performance_summary': self.get_performance_summary(),
            'optimization_recommendations': self.get_optimization_recommendations(),
            'alerts': []  # 最近10分钟的警报
        }
        
        # 添加最近的警报
        now = time.time()
        cutoff_time = now - 600  # 最近10分钟
        for component_metrics in self.analyzer.metrics_history.values():
            for metric in component_metrics:
                if metric.timestamp > cutoff_time and metric.additional_data:
                    # 这里可以提取相关的警报信息
                    pass
        
        return report
    
    def _save_report_to_file(self, report: Dict[str, Any]) -> None:
        """保存报告到文件"""
        try:
            reports_dir = Path('performance_reports')
            reports_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = reports_dir / f'performance_report_{timestamp}.json'
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"性能报告已保存到: {report_file}")
            
        except Exception as e:
            logger.error(f"保存性能报告失败: {e}")
    
    def _reset_session_stats(self) -> None:
        """重置会话统计"""
        self.session_stats = {
            'start_time': time.time(),
            'total_metrics': 0,
            'alerts_raised': 0,
            'optimizations_applied': 0
        }
        logger.info("会话统计已重置")
    
    def export_metrics_to_csv(self, component: str = None, time_range_minutes: int = 60, 
                             output_file: str = None) -> bool:
        """导出性能指标到CSV文件"""
        try:
            summary = self.get_performance_summary(component, time_range_minutes)
            if not summary.get('statistics'):
                logger.warning("没有数据可供导出")
                return False
            
            # 构建数据
            data_rows = []
            for component_name, metrics in self.analyzer.metrics_history.items():
                if component and component_name != component:
                    continue
                    
                for metric in metrics:
                    if metric.timestamp > time.time() - time_range_minutes * 60:
                        data_rows.append({
                            'timestamp': datetime.fromtimestamp(metric.timestamp).isoformat(),
                            'component': metric.component,
                            'metric_type': metric.metric_type,
                            'value': metric.value,
                            'unit': metric.unit,
                            **metric.additional_data
                        })
            
            if not data_rows:
                logger.warning("指定时间范围内没有数据")
                return False
            
            # 创建DataFrame并保存
            df = pd.DataFrame(data_rows)
            if not output_file:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_file = f'performance_metrics_{timestamp}.csv'
            
            df.to_csv(output_file, index=False, encoding='utf-8')
            logger.info(f"性能指标已导出到: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"导出性能指标失败: {e}")
            return False

# 全局性能监控实例
_global_monitor = None

def get_performance_monitor() -> Optional[PerformanceMonitor]:
    """获取全局性能监控实例"""
    return _global_monitor

def init_performance_monitor(config: Dict[str, Any] = None) -> PerformanceMonitor:
    """初始化全局性能监控实例"""
    global _global_monitor
    _global_monitor = PerformanceMonitor(config)
    return _global_monitor