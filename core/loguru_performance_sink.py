"""
纯Loguru性能监控Sink
完全替代原有的性能监控集成，使用Loguru原生bind机制
"""

from loguru import logger
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import statistics

@dataclass
class PerformanceMetric:
    """性能指标数据"""
    timestamp: float
    category: str
    metric_type: str
    value: float
    service: str = ""
    operation: str = ""
    extra_data: Dict[str, Any] = field(default_factory=dict)

class PerformanceDataStore:
    """性能数据存储器"""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self.metrics = deque(maxlen=max_entries)
        self.lock = threading.RLock()
        
        # 分类统计
        self.category_stats = defaultdict(list)
        self.service_stats = defaultdict(list)
        
        # 警报阈值
        self.alert_thresholds = {
            "RESPONSE_TIME": 1000,    # ms
            "MEMORY_USAGE": 80,       # %
            "CPU_USAGE": 90,          # %
            "ERROR_RATE": 5,          # %
            "CACHE_MISS_RATE": 20     # %
        }
    
    def add_metric(self, metric: PerformanceMetric):
        """添加性能指标"""
        with self.lock:
            self.metrics.append(metric)
            
            # 更新分类统计
            self.category_stats[metric.category].append(metric.value)
            self.service_stats[metric.service].append(metric.value)
            
            # 限制统计数据大小
            if len(self.category_stats[metric.category]) > 1000:
                self.category_stats[metric.category] = self.category_stats[metric.category][-500:]
            if len(self.service_stats[metric.service]) > 1000:
                self.service_stats[metric.service] = self.service_stats[metric.service][-500:]
    
    def get_recent_metrics(self, seconds: int = 60) -> List[PerformanceMetric]:
        """获取最近的性能指标"""
        cutoff_time = time.time() - seconds
        with self.lock:
            return [m for m in self.metrics if m.timestamp >= cutoff_time]
    
    def get_category_stats(self, category: str) -> Dict[str, float]:
        """获取分类统计信息"""
        with self.lock:
            values = self.category_stats.get(category, [])
            if not values:
                return {}
            
            return {
                "count": len(values),
                "avg": statistics.mean(values),
                "min": min(values),
                "max": max(values),
                "median": statistics.median(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0
            }
    
    def check_alerts(self, metric: PerformanceMetric) -> Optional[str]:
        """检查是否需要发出警报"""
        threshold = self.alert_thresholds.get(metric.metric_type)
        if threshold is None:
            return None
        
        if metric.value > threshold:
            return (f"性能警报: {metric.service}.{metric.operation} "
                   f"{metric.metric_type}={metric.value} 超过阈值 {threshold}")
        
        return None

class LoguruPerformanceSink:
    """Loguru性能监控Sink"""
    
    def __init__(self):
        self.data_store = PerformanceDataStore()
        self.alert_callbacks: List[Callable[[str], None]] = []
        self._processing = False
        
        self.performance_categories = {
            "SYSTEM": ["CPU_USAGE", "MEMORY_USAGE", "DISK_IO", "NETWORK_IO"],
            "UI": ["RESPONSE_TIME", "RENDER_TIME", "EVENT_PROCESSING"],
            "STRATEGY": ["SIGNAL_PROCESSING", "CALCULATION_TIME", "BACKTEST_TIME"],
            "ALGORITHM": ["EXECUTION_TIME", "ACCURACY", "CONVERGENCE_TIME"],
            "TRADE": ["ORDER_LATENCY", "EXECUTION_TIME", "SLIPPAGE"],
            "CACHE": ["HIT_RATE", "MISS_RATE", "LOAD_TIME", "SIZE"]
        }
        
        self.setup_sink()
    
    def setup_sink(self):
        """设置Loguru性能监控sink"""
        _self = self
        
        def performance_sink(message):
            """性能监控专用sink"""
            if _self._processing:
                return
            _self._processing = True
            try:
                record = message.record
                extra = record.get("extra", {})
                
                if not extra.get("performance", False):
                    return
                
                metric = _self._extract_performance_metric(record, extra)
                if metric:
                    _self.data_store.add_metric(metric)
                    
                    alert_message = _self.data_store.check_alerts(metric)
                    if alert_message:
                        _self._trigger_alert(alert_message)
                    
                    _self._write_performance_log(metric)
            except Exception as e:
                import sys
                sys.stderr.write(f"[PerformanceSink] 错误: {e}\n")
                sys.stderr.flush()
            finally:
                _self._processing = False
        
        self.sink_id = logger.add(
            performance_sink,
            level="DEBUG",
            enqueue=True,
            catch=True
        )
    
    def _extract_performance_metric(self, record, extra: Dict[str, Any]) -> Optional[PerformanceMetric]:
        """从日志记录中提取性能指标"""
        try:
            category = extra.get("category", "UNKNOWN")
            metric_type = extra.get("metric_type", "UNKNOWN")
            value = extra.get("value")
            
            if value is None:
                return None
            
            service = extra.get("service", record.get("name", ""))
            operation = extra.get("operation", record.get("function", ""))
            
            return PerformanceMetric(
                timestamp=record["time"].timestamp(),
                category=category,
                metric_type=metric_type,
                value=float(value),
                service=service,
                operation=operation,
                extra_data={k: v for k, v in extra.items() 
                           if k not in ["performance", "category", "metric_type", "value", "service", "operation"]}
            )
        except Exception as e:
            import sys
            sys.stderr.write(f"[PerformanceSink] 提取性能指标失败: {e}\n")
            sys.stderr.flush()
            return None
    
    def _write_performance_log(self, metric: PerformanceMetric):
        """写入性能日志文件"""
        log_data = {
            "timestamp": datetime.fromtimestamp(metric.timestamp).isoformat(),
            "category": metric.category,
            "metric_type": metric.metric_type,
            "value": metric.value,
            "service": metric.service,
            "operation": metric.operation,
            "extra": metric.extra_data
        }
        
        # 使用独立的性能日志
        logger.bind(performance_log=True).info(json.dumps(log_data, ensure_ascii=False))
    
    def _trigger_alert(self, alert_message: str):
        """触发性能警报"""
        import sys
        sys.stderr.write(f"[PerformanceSink] 性能警报: {alert_message}\n")
        sys.stderr.flush()
        
        for callback in self.alert_callbacks:
            try:
                callback(alert_message)
            except Exception as e:
                sys.stderr.write(f"[PerformanceSink] 警报回调失败: {e}\n")
                sys.stderr.flush()
    
    def add_alert_callback(self, callback: Callable[[str], None]):
        """添加警报回调函数"""
        self.alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[str], None]):
        """移除警报回调函数"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    def get_performance_summary(self, minutes: int = 5) -> Dict[str, Any]:
        """获取性能摘要"""
        recent_metrics = self.data_store.get_recent_metrics(minutes * 60)
        
        summary = {
            "time_range": f"最近 {minutes} 分钟",
            "total_metrics": len(recent_metrics),
            "categories": {},
            "services": {},
            "alerts": []
        }
        
        # 按分类统计
        for category in self.performance_categories.keys():
            category_metrics = [m for m in recent_metrics if m.category == category]
            if category_metrics:
                summary["categories"][category] = {
                    "count": len(category_metrics),
                    "avg_value": statistics.mean(m.value for m in category_metrics),
                    "max_value": max(m.value for m in category_metrics)
                }
        
        # 按服务统计
        services = set(m.service for m in recent_metrics if m.service)
        for service in services:
            service_metrics = [m for m in recent_metrics if m.service == service]
            summary["services"][service] = {
                "count": len(service_metrics),
                "categories": list(set(m.category for m in service_metrics))
            }
        
        return summary
    
    def set_alert_threshold(self, metric_type: str, threshold: float):
        """设置警报阈值"""
        self.data_store.alert_thresholds[metric_type] = threshold
        logger.info(f"设置性能警报阈值: {metric_type} = {threshold}")
    
    def shutdown(self):
        """关闭性能监控sink"""
        if hasattr(self, 'sink_id'):
            logger.remove(self.sink_id)
        logger.info("性能监控Sink已关闭")

# 全局性能监控实例
performance_sink = LoguruPerformanceSink()

def get_performance_sink() -> LoguruPerformanceSink:
    """获取全局性能监控sink"""
    return performance_sink

def log_performance(category: str, metric_type: str, value: float, 
                   service: str = "", operation: str = "", **extra):
    """记录性能指标的便捷函数"""
    logger.bind(
        performance=True,
        category=category,
        metric_type=metric_type,
        value=value,
        service=service,
        operation=operation,
        **extra
    ).debug(f"性能指标: {category}.{metric_type} = {value}")

# 性能监控装饰器
class PerformanceTimer:
    """性能计时装饰器"""
    
    def __init__(self, category: str, service: str = "", operation: str = ""):
        self.category = category
        self.service = service
        self.operation = operation
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                execution_time = (time.perf_counter() - start_time) * 1000  # ms
                
                log_performance(
                    category=self.category,
                    metric_type="EXECUTION_TIME",
                    value=execution_time,
                    service=self.service or func.__module__,
                    operation=self.operation or func.__name__
                )
                
                return result
            except Exception as e:
                execution_time = (time.perf_counter() - start_time) * 1000
                log_performance(
                    category=self.category,
                    metric_type="ERROR_TIME",
                    value=execution_time,
                    service=self.service or func.__module__,
                    operation=self.operation or func.__name__,
                    error=str(e)
                )
                raise
        
        return wrapper

# 便捷的性能监控装饰器
def monitor_performance(category: str, service: str = "", operation: str = ""):
    """性能监控装饰器"""
    return PerformanceTimer(category, service, operation)