#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
内存性能监控系统

提供详细的内存监控指标，包括系统内存、JavaScript堆内存、WebGPU内存等

作者: Hikyuu UI系统
版本: 1.0
"""

import time
import threading
import copy
import gc
import psutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import numpy as np

from loguru import logger

# GPU监控功能已移除
# WebGPU模块不可用，内存监控功能已简化

class MemoryStatus(Enum):
    """内存状态"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    OUT_OF_MEMORY = "out_of_memory"

@dataclass
class MemoryMetrics:
    """内存监控指标"""
    # 系统内存指标
    system_memory_total_mb: float = 0.0
    system_memory_used_mb: float = 0.0
    system_memory_available_mb: float = 0.0
    system_memory_usage_percent: float = 0.0
    system_memory_swap_total_mb: float = 0.0
    system_memory_swap_used_mb: float = 0.0
    
    # 进程内存指标
    process_memory_rss_mb: float = 0.0
    process_memory_vms_mb: float = 0.0
    process_memory_percent: float = 0.0
    process_memory_heap_mb: float = 0.0
    process_memory_stack_mb: float = 0.0
    
    # GPU内存指标已移除
    
    # 内存效率指标
    memory_efficiency: float = 1.0
    garbage_collection_frequency: float = 0.0
    memory_leak_detection: float = 0.0
    memory_pressure_level: float = 0.0
    
    # 内存分配统计
    memory_allocations_per_second: float = 0.0
    memory_deallocations_per_second: float = 0.0
    memory_fragmentation_rate: float = 0.0
    memory_cache_hit_rate: float = 0.0
    
    # 内存池统计
    memory_pool_allocations: int = 0
    memory_pool_releases: int = 0
    memory_pool_reuse_rate: float = 0.0
    memory_pool_efficiency: float = 1.0
    
    # 错误统计
    memory_errors_count: int = 0
    memory_allocation_failures: int = 0
    last_memory_error_time: float = 0.0
    
    # 状态信息
    memory_status: MemoryStatus = MemoryStatus.NORMAL
    memory_alerts_active: List[str] = field(default_factory=list)
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

class MemoryMonitor:
    """内存性能监控器"""
    
    def __init__(self):
        # WebGPU监控功能已移除
        self.resource_pool = None
        
        # 监控状态
        self.memory_metrics = MemoryMetrics()
        self.metrics_history = deque(maxlen=1000)  # 保存最近1000条记录
        
        # 监控线程
        self.monitoring_active = False
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # 回调函数
        self.metrics_callbacks: List[Callable[[MemoryMetrics], None]] = []
        self.alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # 告警阈值
        self.alert_thresholds = {
            'system_memory_usage_max': 0.80,  # 80%系统内存使用率
            'process_memory_usage_max': 0.85, # 85%进程内存使用率
            'webgpu_memory_usage_max': 0.90,  # 90%WebGPU内存使用率
            'memory_fragmentation_max': 0.30, # 30%最大内存碎片率
            'memory_leak_threshold': 0.10,    # 10%内存泄漏阈值
            'memory_pressure_max': 0.75       # 75%最大内存压力
        }
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'total_collections': 0,
            'error_count': 0,
            'gc_runs': 0,
            'allocation_count': 0,
            'deallocation_count': 0
        }
        
        logger.info("内存监控器初始化完成")
    
    def add_metrics_callback(self, callback: Callable[[MemoryMetrics], None]):
        """添加指标回调函数"""
        self.metrics_callbacks.append(callback)
        logger.debug(f"添加内存指标回调函数: {callback.__name__}")
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """添加告警回调函数"""
        self.alert_callbacks.append(callback)
        logger.debug(f"添加内存告警回调函数: {callback.__name__}")
    

    
    def collect_system_memory_metrics(self) -> Dict[str, float]:
        """收集系统内存指标"""
        try:
            # 获取系统内存信息
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # 获取进程内存信息
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # 转换为MB
            total_mb = memory.total / (1024 * 1024)
            used_mb = memory.used / (1024 * 1024)
            available_mb = memory.available / (1024 * 1024)
            swap_total_mb = swap.total / (1024 * 1024)
            swap_used_mb = swap.used / (1024 * 1024)
            
            process_rss_mb = process_memory.rss / (1024 * 1024)
            process_vms_mb = process_memory.vms / (1024 * 1024)
            process_percent = process.memory_percent()
            
            return {
                'system_memory_total_mb': total_mb,
                'system_memory_used_mb': used_mb,
                'system_memory_available_mb': available_mb,
                'system_memory_usage_percent': memory.percent / 100.0,
                'system_memory_swap_total_mb': swap_total_mb,
                'system_memory_swap_used_mb': swap_used_mb,
                'process_memory_rss_mb': process_rss_mb,
                'process_memory_vms_mb': process_vms_mb,
                'process_memory_percent': process_percent / 100.0
            }
            
        except Exception as e:
            logger.error(f"收集系统内存指标失败: {e}")
            self.stats['error_count'] += 1
            return {}
    

    
    def collect_memory_efficiency_metrics(self) -> Dict[str, float]:
        """收集内存效率指标"""
        try:
            # 垃圾回收统计
            gc_stats = gc.get_stats()
            gc_frequency = len(gc_stats) if gc_stats else 0.0
            
            # 估算内存泄漏（基于内存增长趋势）
            memory_growth_rate = 0.0
            if len(self.metrics_history) >= 10:
                recent_metrics = list(self.metrics_history)[-10:]
                memory_values = [m.system_memory_used_mb for m in recent_metrics]
                if len(memory_values) > 1:
                    # 简单的线性趋势分析
                    x = np.arange(len(memory_values))
                    memory_growth_rate = np.polyfit(x, memory_values, 1)[0]  # 斜率
            
            # 计算内存压力水平
            current_metrics = self.memory_metrics
            memory_pressure = max(
                current_metrics.system_memory_usage_percent,
                current_metrics.process_memory_percent * 0.8  # 进程内存权重稍低
            )
            
            return {
                'memory_efficiency': 1.0 - memory_pressure,
                'garbage_collection_frequency': gc_frequency,
                'memory_leak_detection': memory_growth_rate,
                'memory_pressure_level': min(1.0, memory_pressure)
            }
            
        except Exception as e:
            logger.error(f"收集内存效率指标失败: {e}")
            self.stats['error_count'] += 1
            return {
                'memory_efficiency': 1.0,
                'garbage_collection_frequency': 0.0,
                'memory_leak_detection': 0.0,
                'memory_pressure_level': 0.0
            }
    
    def update_memory_status(self):
        """更新内存状态"""
        metrics = self.memory_metrics
        
        # 确定内存状态
        if (metrics.system_memory_usage_percent > 0.95 or 
            metrics.process_memory_percent > 0.95):
            metrics.memory_status = MemoryStatus.OUT_OF_MEMORY
        elif (metrics.system_memory_usage_percent > 0.85 or 
              metrics.process_memory_percent > 0.85 or
              metrics.memory_pressure_level > 0.85):
            metrics.memory_status = MemoryStatus.CRITICAL
        elif (metrics.system_memory_usage_percent > 0.70 or 
              metrics.process_memory_percent > 0.75 or
              metrics.memory_pressure_level > 0.65):
            metrics.memory_status = MemoryStatus.WARNING
        else:
            metrics.memory_status = MemoryStatus.NORMAL
        
        # 检查告警条件
        active_alerts = []
        
        if metrics.system_memory_usage_percent > self.alert_thresholds['system_memory_usage_max']:
            active_alerts.append("high_system_memory_usage")
        
        if metrics.process_memory_percent > self.alert_thresholds['process_memory_usage_max']:
            active_alerts.append("high_process_memory_usage")
        

        
        if metrics.memory_leak_detection > self.alert_thresholds['memory_leak_threshold']:
            active_alerts.append("memory_leak_detected")
        
        if metrics.memory_pressure_level > self.alert_thresholds['memory_pressure_max']:
            active_alerts.append("high_memory_pressure")
        
        metrics.memory_alerts_active = active_alerts
        
        # 触发告警回调
        if active_alerts:
            for alert in active_alerts:
                alert_data = {
                    'alert_type': alert,
                    'severity': metrics.memory_status.value,
                    'current_usage': metrics.system_memory_usage_percent,
                    'threshold': self.alert_thresholds.get(alert.split('_')[0] + '_usage_max', 0.8),
                    'timestamp': time.time()
                }
                
                for callback in self.alert_callbacks:
                    try:
                        callback(alert, alert_data)
                    except Exception as e:
                        logger.error(f"内存告警回调执行失败: {e}")
    
    def collect_all_metrics(self) -> MemoryMetrics:
        """收集所有内存指标"""
        try:
            self.stats['total_collections'] += 1
            
            # 收集系统内存指标
            system_metrics = self.collect_system_memory_metrics()
            
            # WebGPU内存监控已移除
            
            # 收集内存效率指标
            efficiency_metrics = self.collect_memory_efficiency_metrics()
            
            # 更新内存指标
            for key, value in system_metrics.items():
                setattr(self.memory_metrics, key, value)
            

            
            for key, value in efficiency_metrics.items():
                setattr(self.memory_metrics, key, value)
            
            # 更新状态
            self.update_memory_status()
            
            # 保存历史记录
            self.metrics_history.append(copy.deepcopy(self.memory_metrics))
            
            # 触发指标回调
            for callback in self.metrics_callbacks:
                try:
                    callback(self.memory_metrics)
                except Exception as e:
                    logger.error(f"内存指标回调执行失败: {e}")
            
            logger.debug(f"内存指标收集完成: 使用率 {self.memory_metrics.system_memory_usage_percent:.2%}")
            return self.memory_metrics
            
        except Exception as e:
            logger.error(f"收集内存指标失败: {e}")
            self.stats['error_count'] += 1
            return self.memory_metrics
    
    def start_monitoring(self, interval: float = 1.0) -> bool:
        """开始内存监控"""
        if self.monitoring_active:
            logger.warning("内存监控已在运行")
            return True
        
        try:
            logger.info(f"开始内存监控，间隔: {interval}秒")
            
            self.monitoring_active = True
            self.stop_event.clear()
            self.stats['start_time'] = time.time()
            
            def monitoring_loop():
                while self.monitoring_active and not self.stop_event.is_set():
                    try:
                        self.collect_all_metrics()
                        time.sleep(interval)
                    except Exception as e:
                        logger.error(f"内存监控循环异常: {e}")
                        self.stats['error_count'] += 1
                        time.sleep(interval)
            
            self.monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info("内存监控已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动内存监控失败: {e}")
            self.monitoring_active = False
            return False
    
    def stop_monitoring(self):
        """停止内存监控"""
        if not self.monitoring_active:
            logger.warning("内存监控未运行")
            return
        
        try:
            logger.info("停止内存监控...")
            
            self.monitoring_active = False
            self.stop_event.set()
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            
            logger.info("内存监控已停止")
            
        except Exception as e:
            logger.error(f"停止内存监控失败: {e}")
    
    def get_current_metrics(self) -> MemoryMetrics:
        """获取当前内存指标"""
        return self.memory_metrics
    
    def get_metrics_history(self, count: int = 100) -> List[MemoryMetrics]:
        """获取历史内存指标"""
        return list(self.metrics_history)[-count:]
    
    def get_memory_usage_trend(self, count: int = 60) -> Dict[str, List[float]]:
        """获取内存使用趋势"""
        if len(self.metrics_history) < count:
            count = len(self.metrics_history)
        
        recent_metrics = list(self.metrics_history)[-count:]
        
        return {
            'system_usage': [m.system_memory_usage_percent for m in recent_metrics],
            'process_usage': [m.process_memory_percent for m in recent_metrics],
            'webgpu_usage': [
                getattr(m, 'webgpu_memory_used_mb', 0)
                / max(1, getattr(m, 'webgpu_memory_pool_size_mb', 1))
                for m in recent_metrics
            ],
            'pressure_level': [m.memory_pressure_level for m in recent_metrics]
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            **self.stats,
            'current_memory_status': self.memory_metrics.memory_status.value,
            'active_alerts_count': len(self.memory_metrics.memory_alerts_active),
            'monitoring_active': self.monitoring_active
        }
    
    def force_garbage_collection(self) -> Dict[str, int]:
        """强制垃圾回收"""
        try:
            gc.collect()
            self.stats['gc_runs'] += 1
            
            return {
                'gc_runs': self.stats['gc_runs'],
                'gc_objects_collected': gc.get_stats()[-1]['collected'] if gc.get_stats() else 0,
                'current_memory_usage': self.memory_metrics.system_memory_used_mb
            }
            
        except Exception as e:
            logger.error(f"强制垃圾回收失败: {e}")
            return {'gc_runs': 0, 'gc_objects_collected': 0, 'error': str(e)}

# 全局内存监控实例
_global_memory_monitor = None

def get_memory_monitor() -> MemoryMonitor:
    """获取全局内存监控实例"""
    global _global_memory_monitor
    if _global_memory_monitor is None:
        _global_memory_monitor = MemoryMonitor()
    return _global_memory_monitor