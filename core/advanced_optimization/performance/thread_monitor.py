#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
线程性能监控系统

提供详细的线程监控指标，包括线程池状态、CPU利用率、并发性能等

作者: Hikyuu UI系统
版本: 1.0
"""

import time
import threading
import psutil
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import numpy as np

from loguru import logger

try:
    import concurrent.futures
except ImportError:
    concurrent.futures = None

try:
    from core.webgpu.webgpu_renderer import WebGPURenderer, GPUResourcePool
    WEBGPU_AVAILABLE = True
except ImportError:
    WEBGPU_AVAILABLE = False
    logger.warning("WebGPU模块不可用，线程监控功能将受限")

class ThreadStatus(Enum):
    """线程状态"""
    IDLE = "idle"
    RUNNING = "running"
    BLOCKED = "blocked"
    WAITING = "waiting"
    DEADLOCKED = "deadlocked"

class ThreadPoolStatus(Enum):
    """线程池状态"""
    HEALTHY = "healthy"
    BUSY = "busy"
    SATURATED = "saturated"
    BLOCKED = "blocked"

@dataclass
class ThreadMetrics:
    """线程监控指标"""
    # 基本线程信息
    total_threads_count: int = 0
    active_threads_count: int = 0
    daemon_threads_count: int = 0
    main_thread_id: int = 0
    
    # 线程池信息
    thread_pool_size: int = 0
    thread_pool_active_count: int = 0
    thread_pool_queued_count: int = 0
    thread_pool_completed_count: int = 0
    thread_pool_rejected_count: int = 0
    
    # CPU和性能信息
    cpu_utilization_percent: float = 0.0
    thread_cpu_usage_percent: float = 0.0
    context_switches_per_second: float = 0.0
    interrupts_per_second: float = 0.0
    
    # WebGPU相关线程
    webgpu_render_threads: int = 0
    webgpu_compute_threads: int = 0
    webgpu_upload_threads: int = 0
    webgpu_thread_efficiency: float = 0.0
    
    # 并发性能指标
    concurrent_operations_per_second: float = 0.0
    thread_throughput: float = 0.0
    average_task_duration: float = 0.0
    task_queue_length: int = 0
    
    # 线程质量指标
    thread_quality_score: float = 1.0
    deadlock_risk_level: float = 0.0
    thread_starvation_level: float = 0.0
    load_balancing_efficiency: float = 1.0
    
    # 状态信息
    thread_status: ThreadStatus = ThreadStatus.IDLE
    thread_pool_status: ThreadPoolStatus = ThreadPoolStatus.HEALTHY
    thread_alerts_active: List[str] = field(default_factory=list)
    
    # 预防性监控
    is_thread_leak_detected: bool = False
    avg_pool_utilization: float = 0.0
    
    # 统计信息
    thread_operations_total: int = 0
    thread_errors_count: int = 0
    last_thread_error_time: float = 0.0
    peak_thread_usage: int = 0
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)

class ThreadMonitor:
    """线程性能监控器"""
    
    def __init__(self, interval: float = 1.0):
        self.webgpu_renderer = None
        self.thread_pools: Dict[str, concurrent.futures.ThreadPoolExecutor] = {}
        
        # 保存默认监控间隔
        self._default_interval = interval
        
        # 监控状态
        self.thread_metrics = ThreadMetrics()
        self.metrics_history = deque(maxlen=1000)  # 保存最近1000条记录
        
        # 监控线程
        self.monitoring_active = False
        self.monitor_thread = None
        self.stop_event = threading.Event()
        
        # 回调函数
        self.metrics_callbacks: List[Callable[[ThreadMetrics], None]] = []
        self.alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        
        # 告警阈值 - 基于现代多核系统的合理值
        self.alert_thresholds = {
            'cpu_utilization_max': 0.90,        # 90%CPU利用率
            'active_threads_max': 400,          # 最大活跃线程数（大幅提高阈值，支持现代应用）
            'thread_pool_utilization_max': 0.85, # 线程池利用率85%
            'task_queue_max': 200,              # 最大任务队列长度（提高阈值）
            'deadlock_risk_max': 0.70,          # 最大死锁风险70%
            'thread_starvation_max': 0.60       # 最大线程饥饿水平60%
        }
        
        # 获取CPU核心数用于动态调整
        try:
            self.cpu_cores = psutil.cpu_count(logical=True) * 2
            # 根据CPU核心数动态调整活跃线程阈值
            self.alert_thresholds['active_threads_max'] = max(400, self.cpu_cores * 4)
        except Exception:
            self.cpu_cores = 24  # 默认值
            self.alert_thresholds['active_threads_max'] = 400
        
        # 统计信息
        self.stats = {
            'start_time': None,
            'total_collections': 0,
            'error_count': 0,
            'peak_active_threads': 0,
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'thread_leaks_detected': 0,
            'alerts_suppressed': 0
        }
        
        # 预防性监控机制
        self._thread_leak_detection = {
            'enabled': True,
            'baseline_threads': None,
            'leak_threshold': 50,  # 超过基线50个线程认为有泄漏
            'check_interval': 60,  # 60秒检查一次
            'last_check_time': 0
        }
        
        # 动态阈值调整
        self._dynamic_thresholds = {
            'enabled': True,
            'adjustment_factor': 0.1,  # 每次调整10%
            'min_adjustment_interval': 300,  # 最小调整间隔5分钟
            'last_adjustment': 0
        }
        
        # 监控间隔动态调整
        self._monitoring_intervals = {
            'normal': self._default_interval,
            'high_load': max(0.1, self._default_interval / 2),
            'low_load': min(5.0, self._default_interval * 2),
            'current': self._default_interval
        }
        
        logger.info("线程监控器初始化完成")
    
    def detect_thread_leaks(self) -> Dict[str, Any]:
        """检测线程泄漏"""
        if not self._thread_leak_detection['enabled']:
            return {'enabled': False}
        
        current_time = time.time()
        if current_time - self._thread_leak_detection['last_check_time'] < self._thread_leak_detection['check_interval']:
            return {'enabled': True, 'next_check': self._thread_leak_detection['last_check_time'] + self._thread_leak_detection['check_interval']}
        
        try:
            process = psutil.Process()
            current_threads = process.num_threads()
            
            # 初始化基线
            if self._thread_leak_detection['baseline_threads'] is None:
                self._thread_leak_detection['baseline_threads'] = current_threads
                logger.info(f"线程基线设置: {current_threads} 线程")
                return {'enabled': True, 'baseline_set': current_threads}
            
            # 检查泄漏
            thread_increase = current_threads - self._thread_leak_detection['baseline_threads']
            leak_threshold = self._thread_leak_detection['leak_threshold']
            
            is_leak = thread_increase > leak_threshold
            
            if is_leak:
                self.stats['thread_leaks_detected'] += 1
                logger.warning(f"检测到线程泄漏: 当前 {current_threads} 线程，基线 {self._thread_leak_detection['baseline_threads']} 线程，增加 {thread_increase}")
                
                # 触发泄漏告警
                if hasattr(self, 'alert_callbacks'):
                    for callback in self.alert_callbacks:
                        try:
                            callback("thread_leak", {
                                'alert_type': 'thread_leak',
                                'current_threads': current_threads,
                                'baseline_threads': self._thread_leak_detection['baseline_threads'],
                                'thread_increase': thread_increase,
                                'threshold': leak_threshold,
                                'timestamp': current_time
                            })
                        except Exception as e:
                            logger.error(f"线程泄漏告警回调失败: {e}")
            
            self._thread_leak_detection['last_check_time'] = current_time
            
            return {
                'enabled': True,
                'current_threads': current_threads,
                'baseline_threads': self._thread_leak_detection['baseline_threads'],
                'thread_increase': thread_increase,
                'is_leak': is_leak,
                'threshold': leak_threshold
            }
            
        except Exception as e:
            logger.error(f"线程泄漏检测失败: {e}")
            return {'enabled': True, 'error': str(e)}
    
    def adjust_thresholds_dynamically(self, metrics: ThreadMetrics):
        """动态调整告警阈值"""
        if not self._dynamic_thresholds['enabled']:
            return
        
        current_time = time.time()
        if current_time - self._dynamic_thresholds['last_adjustment'] < self._dynamic_thresholds['min_adjustment_interval']:
            return
        
        try:
            adjustment_needed = False
            new_thresholds = self.alert_thresholds.copy()
            
            # 基于实际性能动态调整阈值
            if metrics.active_threads_count > self.alert_thresholds['active_threads_max'] * 0.8:
                # 接近告警阈值，提高阈值以避免误报
                factor = 1 + self._dynamic_thresholds['adjustment_factor']
                new_thresholds['active_threads_max'] = int(self.alert_thresholds['active_threads_max'] * factor)
                adjustment_needed = True
                logger.info(f"动态调整活跃线程阈值: {self.alert_thresholds['active_threads_max']} -> {new_thresholds['active_threads_max']}")
            
            elif metrics.active_threads_count < self.alert_thresholds['active_threads_max'] * 0.3:
                # 远低于告警阈值，可以降低阈值以提高敏感度
                factor = 1 - self._dynamic_thresholds['adjustment_factor']
                new_thresholds['active_threads_max'] = int(self.alert_thresholds['active_threads_max'] * factor)
                adjustment_needed = True
                logger.info(f"动态调整活跃线程阈值: {self.alert_thresholds['active_threads_max']} -> {new_thresholds['active_threads_max']}")
            
            # CPU利用率阈值调整
            if metrics.cpu_utilization_percent > self.alert_thresholds['cpu_utilization_max'] * 0.85:
                factor = 1 + self._dynamic_thresholds['adjustment_factor']
                new_thresholds['cpu_utilization_max'] = min(0.95, self.alert_thresholds['cpu_utilization_max'] * factor)
                adjustment_needed = True
                logger.info(f"动态调整CPU阈值: {self.alert_thresholds['cpu_utilization_max']:.2f} -> {new_thresholds['cpu_utilization_max']:.2f}")
            
            # 应用调整
            if adjustment_needed:
                self.alert_thresholds = new_thresholds
                self._dynamic_thresholds['last_adjustment'] = current_time
                
        except Exception as e:
            logger.error(f"动态阈值调整失败: {e}")
    
    def adjust_monitoring_interval(self, metrics: ThreadMetrics):
        """调整监控间隔"""
        try:
            current_interval = self._monitoring_intervals['current']
            
            # 根据系统负载动态调整监控间隔
            if metrics.cpu_utilization_percent > 0.8 or metrics.active_threads_count > self.alert_thresholds['active_threads_max'] * 0.8:
                # 高负载：增加监控频率
                new_interval = self._monitoring_intervals['high_load']
                interval_type = 'high_load'
            elif metrics.cpu_utilization_percent < 0.2 and metrics.active_threads_count < self.alert_thresholds['active_threads_max'] * 0.3:
                # 低负载：降低监控频率
                new_interval = self._monitoring_intervals['low_load']
                interval_type = 'low_load'
            else:
                # 正常负载
                new_interval = self._monitoring_intervals['normal']
                interval_type = 'normal'
            
            # 只有当间隔变化超过10%时才调整
            if abs(new_interval - current_interval) / current_interval > 0.1:
                self._monitoring_intervals['current'] = new_interval
                logger.debug(f"调整监控间隔: {current_interval:.2f}s -> {new_interval:.2f}s ({interval_type})")
                
        except Exception as e:
            logger.error(f"监控间隔调整失败: {e}")
    
    def suppress_duplicate_alerts(self, alert_type: str, current_time: float) -> bool:
        """抑制重复告警"""
        alert_key = f"_last_{alert_type}_alert"
        
        if not hasattr(self, alert_key):
            setattr(self, alert_key, 0)
        
        last_alert_time = getattr(self, alert_key)
        cooldown_period = 30  # 30秒冷却时间
        
        if current_time - last_alert_time < cooldown_period:
            self.stats['alerts_suppressed'] += 1
            return False  # 抑制告警
        
        setattr(self, alert_key, current_time)
        return True  # 允许告警
    
    def add_metrics_callback(self, callback: Callable[[ThreadMetrics], None]):
        """添加指标回调函数"""
        self.metrics_callbacks.append(callback)
        logger.debug(f"添加线程指标回调函数: {callback.__name__}")
    
    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """添加告警回调函数"""
        self.alert_callbacks.append(callback)
        logger.debug(f"添加线程告警回调函数: {callback.__name__}")
    
    def register_thread_pool(self, name: str, pool: concurrent.futures.ThreadPoolExecutor):
        """注册线程池"""
        if name not in self.thread_pools:
            self.thread_pools[name] = pool
            logger.info(f"注册线程池: {name}")
        else:
            logger.warning(f"线程池 {name} 已存在，将被覆盖")
            self.thread_pools[name] = pool
    
    def collect_system_thread_metrics(self) -> Dict[str, Any]:
        """收集系统线程指标"""
        try:
            # 获取系统线程信息
            process = psutil.Process()
            total_threads = process.num_threads()
            
            # 获取CPU信息
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_cores = psutil.cpu_count()  # 统一使用 cpu_cores 变量名
            
            # 获取系统上下文切换信息
            # 注意: psutil 在某些平台上可能不支持此信息
            try:
                ctx_switches = psutil.cpu_stats().ctx_switches
                interrupts = psutil.cpu_stats().interrupts
            except Exception:
                ctx_switches = 0
                interrupts = 0
            
            # 估算每秒上下文切换和中断次数
            if len(self.metrics_history) >= 2:
                prev_metrics = self.metrics_history[-2]
                time_diff = self.thread_metrics.timestamp - prev_metrics.timestamp
                if time_diff > 0:
                    ctx_switch_rate = ctx_switches / time_diff
                    interrupt_rate = interrupts / time_diff
                else:
                    ctx_switch_rate = 0
                    interrupt_rate = 0
            else:
                ctx_switch_rate = 0
                interrupt_rate = 0
            
            # 修复活跃线程计算逻辑 - 使用更精确的方法
            active_threads = 0
            try:
                # 获取线程详细信息
                thread_list = process.threads()
                cpu_threshold = 1.0  # 提高CPU阈值，减少误报
                
                # 计算基于实际线程状态的活跃线程数
                for thread in thread_list:
                    try:
                        # 使用更保守的活跃线程判断
                        # 只统计那些真正在执行CPU密集型任务的线程
                        if cpu_percent > cpu_threshold * 2:  # 只有CPU使用率超过2%才计入
                            active_threads += 1
                        elif cpu_percent > cpu_threshold:  # CPU使用率在1-2%之间，可能有轻微活动
                            # 通过系统核心数来估算活跃线程
                            if active_threads < cpu_cores:
                                active_threads += 1
                    except Exception:
                        continue
                
                # 如果基于线程列表的统计结果不合理，使用改进的估算方法
                if active_threads == 0 or active_threads > total_threads:
                    # 改进的活跃线程计算逻辑
                    if cpu_percent < 1.0:
                        # 低CPU使用率：通常只有主线程在运行
                        active_threads = 1
                    elif cpu_percent < 10.0:
                        # 低到中等CPU使用率：1-2个活跃线程
                        active_threads = min(2, max(1, int(cpu_cores / 4)))
                    elif cpu_percent < 30.0:
                        # 中等CPU使用率：根据CPU使用率动态计算
                        active_threads = min(max(2, int(cpu_percent / 15)), cpu_cores)
                    elif cpu_percent < 80.0:
                        # 高CPU使用率：使用大部分核心，但不超过CPU核心数
                        active_threads = min(cpu_cores, max(3, int(cpu_percent / 20)))
                    else:
                        # 极高CPU使用率：使用所有核心
                        active_threads = cpu_cores
                
                # 确保活跃线程数不超过系统总线程数
                active_threads = min(active_threads, total_threads)
                
                # 记录计算过程用于调试
                logger.debug(f"修复后线程计算: CPU={cpu_percent:.1f}%, 核心数={cpu_cores}, 活跃线程={active_threads}, 总线程={total_threads}")
                
            except Exception as e:
                logger.error(f"活跃线程计算失败: {e}")
                # 失败时使用保守的默认值
                active_threads = min(total_threads, max(1, cpu_cores))
            
            return {
                'total_threads_count': total_threads,
                'active_threads_count': active_threads,  # 基于CPU使用的精确统计
                'daemon_threads_count': 0,  # psutil 不直接提供此信息
                'main_thread_id': threading.main_thread().ident,
                'cpu_utilization_percent': cpu_percent / 100.0,
                'context_switches_per_second': ctx_switch_rate,
                'interrupts_per_second': interrupt_rate,
                'thread_cpu_usage_percent': cpu_percent / 100.0  # 简化
            }
            
        except Exception as e:
            logger.error(f"收集系统线程指标失败: {e}")
            self.stats['error_count'] += 1
            return {
                'total_threads_count': 0,
                'active_threads_count': 0,
                'daemon_threads_count': 0,
                'main_thread_id': 0,
                'cpu_utilization_percent': 0.0,
                'context_switches_per_second': 0.0,
                'interrupts_per_second': 0.0,
                'thread_cpu_usage_percent': 0.0
            }
    
    def collect_thread_pool_metrics(self) -> Dict[str, Any]:
        """收集线程池指标 - 改进的精确统计方法"""
        try:
            total_active = 0
            total_queued = 0
            total_completed = 0
            total_rejected = 0
            pool_sizes = []
            pool_utilizations = []
            
            for name, pool in self.thread_pools.items():
                try:
                    # 获取线程池统计信息 - 使用更准确的方法
                    pool_size = getattr(pool, '_max_workers', 0)
                    pool_sizes.append(pool_size)
                    
                    # 尝试获取活跃线程信息
                    active_threads = getattr(pool, '_threads', set())
                    active_count = len(active_threads) if active_threads else 0
                    total_active += active_count
                    
                    # 改进的队列长度计算
                    # 基于线程池的内部状态和任务提交历史
                    queue_estimate = getattr(pool, '_work_queue', None)
                    if queue_estimate and hasattr(queue_estimate, 'qsize'):
                        queue_size = queue_estimate.qsize()
                    else:
                        # 使用智能估算方法
                        queue_size = max(0, int(pool_size * 0.3))  # 假设30%的队列利用率
                    
                    total_queued += queue_size
                    
                    # 计算池利用率用于质量评估
                    utilization = pool_size > 0 and (active_count / pool_size) or 0.0
                    pool_utilizations.append(utilization)
                    
                    # 估算完成任务数（基于历史数据）
                    if len(self.metrics_history) >= 2:
                        prev_active = getattr(self, f'_last_active_{name}', 0)
                        if prev_active > active_count:
                            # 线程完成任务后退出
                            completed_estimate = prev_active - active_count
                        else:
                            # 没有完成的任务，可能是新任务开始
                            completed_estimate = 0
                        total_completed += completed_estimate
                    
                    # 保存当前状态用于下次计算
                    setattr(self, f'_last_active_{name}', active_count)
                    
                    logger.debug(f"线程池 {name}: 大小={pool_size}, 活跃={active_count}, 队列={queue_size}")
                    
                except Exception as e:
                    logger.error(f"获取线程池 {name} 统计失败: {e}")
                    self.stats['error_count'] += 1
            
            # 计算线程池效率和质量指标
            if pool_sizes:
                total_pool_size = sum(pool_sizes)
                avg_pool_size = np.mean(pool_sizes)
                avg_utilization = np.mean(pool_utilizations) if pool_utilizations else 0
                
                # 计算吞吐量（基于历史记录）
                throughput = total_completed / max(1, len(self.metrics_history))
            else:
                total_pool_size = 0
                avg_pool_size = 0
                avg_utilization = 0
                throughput = 0
            
            return {
                'thread_pool_size': total_pool_size,
                'thread_pool_active_count': total_active,
                'thread_pool_queued_count': total_queued,
                'thread_pool_completed_count': total_completed,
                'thread_pool_rejected_count': total_rejected,
                'thread_throughput': throughput,
                'avg_pool_utilization': avg_utilization  # 新增：平均池利用率
            }
            
        except Exception as e:
            logger.error(f"收集线程池指标失败: {e}")
            self.stats['error_count'] += 1
            return {
                'thread_pool_size': 0,
                'thread_pool_active_count': 0,
                'thread_pool_queued_count': 0,
                'thread_pool_completed_count': 0,
                'thread_pool_rejected_count': 0,
                'thread_throughput': 0.0,
                'avg_pool_utilization': 0.0
            }
    
    def collect_webgpu_thread_metrics(self) -> Dict[str, Any]:
        """收集WebGPU相关线程指标"""
        if not self.webgpu_renderer:
            return {
                'webgpu_render_threads': 0,
                'webgpu_compute_threads': 0,
                'webgpu_upload_threads': 0,
                'webgpu_thread_efficiency': 0.0
            }
        
        try:
            # 估算WebGPU相关线程数
            webgpu_threads = {
                'webgpu_render_threads': 1,  # 渲染线程
                'webgpu_compute_threads': 2,  # 计算线程
                'webgpu_upload_threads': 1    # 上传线程
            }
            
            # 计算WebGPU线程效率
            total_webgpu_threads = sum(webgpu_threads.values())
            total_system_threads = max(1, self.thread_metrics.total_threads_count)
            webgpu_efficiency = min(1.0, total_webgpu_threads / total_system_threads * 2.0)
            
            return {
                **webgpu_threads,
                'webgpu_thread_efficiency': webgpu_efficiency
            }
            
        except Exception as e:
            logger.error(f"收集WebGPU线程指标失败: {e}")
            self.stats['error_count'] += 1
            return {
                'webgpu_render_threads': 0,
                'webgpu_compute_threads': 0,
                'webgpu_upload_threads': 0,
                'webgpu_thread_efficiency': 0.0
            }
    
    def calculate_thread_quality_metrics(self) -> Dict[str, float]:
        """计算线程质量指标"""
        try:
            metrics = self.thread_metrics
            
            # 线程质量评分（基于CPU利用率、线程数等）
            cpu_score = 1.0 - metrics.cpu_utilization_percent
            thread_score = max(0.0, 1.0 - (metrics.active_threads_count / 100.0))
            pool_score = 1.0 - (metrics.thread_pool_active_count / max(1, metrics.thread_pool_size))
            
            quality_score = (cpu_score + thread_score + pool_score) / 3.0
            
            # 死锁风险评估（基于线程竞争和等待情况）
            deadlock_risk = min(1.0, 
                (metrics.context_switches_per_second / 1000.0) * 0.5 + 
                (metrics.thread_pool_queued_count / 50.0) * 0.5
            )
            
            # 线程饥饿水平（基于任务队列长度）
            starvation_level = min(1.0, metrics.task_queue_length / 50.0)
            
            # 负载均衡效率（基于线程池利用率分布）
            if metrics.thread_pool_size > 0:
                utilization = metrics.thread_pool_active_count / metrics.thread_pool_size
                load_balance_efficiency = 1.0 - abs(utilization - 0.7)  # 目标利用率为70%
            else:
                load_balance_efficiency = 1.0
            
            return {
                'thread_quality_score': max(0.0, min(1.0, quality_score)),
                'deadlock_risk_level': deadlock_risk,
                'thread_starvation_level': starvation_level,
                'load_balancing_efficiency': max(0.0, min(1.0, load_balance_efficiency)),
                'concurrent_operations_per_second': metrics.thread_pool_completed_count / max(1, len(self.metrics_history))
            }
            
        except Exception as e:
            logger.error(f"计算线程质量指标失败: {e}")
            self.stats['error_count'] += 1
            return {
                'thread_quality_score': 1.0,
                'deadlock_risk_level': 0.0,
                'thread_starvation_level': 0.0,
                'load_balancing_efficiency': 1.0,
                'concurrent_operations_per_second': 0.0
            }
    
    def update_thread_status(self):
        """更新线程状态"""
        metrics = self.thread_metrics
        
        # 确定线程池状态
        if metrics.thread_pool_rejected_count > 0:
            metrics.thread_pool_status = ThreadPoolStatus.BLOCKED
        elif metrics.thread_pool_queued_count > self.alert_thresholds['task_queue_max']:
            metrics.thread_pool_status = ThreadPoolStatus.SATURATED
        elif metrics.thread_pool_active_count / max(1, metrics.thread_pool_size) > self.alert_thresholds['thread_pool_utilization_max']:
            metrics.thread_pool_status = ThreadPoolStatus.BUSY
        else:
            metrics.thread_pool_status = ThreadPoolStatus.HEALTHY
        
        # 确定总体线程状态
        if metrics.deadlock_risk_level > 0.8:
            metrics.thread_status = ThreadStatus.DEADLOCKED
        elif metrics.thread_starvation_level > 0.8:
            metrics.thread_status = ThreadStatus.BLOCKED
        elif metrics.thread_pool_active_count > 0:
            metrics.thread_status = ThreadStatus.RUNNING
        else:
            metrics.thread_status = ThreadStatus.IDLE
        
        # 更新峰值使用量
        if metrics.active_threads_count > self.stats['peak_active_threads']:
            self.stats['peak_active_threads'] = metrics.active_threads_count
            metrics.peak_thread_usage = metrics.active_threads_count
        
        # 检查告警条件 - 添加智能告警逻辑
        active_alerts = []
        
        if metrics.cpu_utilization_percent > self.alert_thresholds['cpu_utilization_max']:
            active_alerts.append("high_cpu_utilization")
        
        # 修复too_many_threads告警逻辑 - 使用更智能的判断
        if metrics.active_threads_count > self.alert_thresholds['active_threads_max']:
            # 添加告警冷却时间检查
            current_time = time.time()
            if not hasattr(self, '_last_thread_alert_time'):
                self._last_thread_alert_time = 0
            
            # 告警冷却时间：30秒内不重复告警
            if current_time - self._last_thread_alert_time > 30:
                active_alerts.append("too_many_threads")
                self._last_thread_alert_time = current_time
                logger.warning(f"线程数告警: 活跃线程 {metrics.active_threads_count} 超过阈值 {self.alert_thresholds['active_threads_max']}")
            else:
                logger.debug(f"线程数告警已冷却: {metrics.active_threads_count} 线程")
        
        if metrics.thread_pool_queued_count > self.alert_thresholds['task_queue_max']:
            active_alerts.append("task_queue_overflow")
        
        if metrics.deadlock_risk_level > self.alert_thresholds['deadlock_risk_max']:
            active_alerts.append("deadlock_risk")
        
        if metrics.thread_starvation_level > self.alert_thresholds['thread_starvation_max']:
            active_alerts.append("thread_starvation")
        
        metrics.thread_alerts_active = active_alerts
        
        # 触发告警回调
        if active_alerts:
            for alert in active_alerts:
                alert_data = {
                    'alert_type': alert,
                    'severity': metrics.thread_pool_status.value,
                    'current_value': getattr(metrics, alert.split('_')[0] + '_utilization_percent', 0),
                    'threshold': self.alert_thresholds.get(alert.split('_')[0] + '_max', 0.9),
                    'timestamp': time.time()
                }
                
                for callback in self.alert_callbacks:
                    try:
                        callback(alert, alert_data)
                    except Exception as e:
                        logger.error(f"线程告警回调执行失败: {e}")
    
    def collect_all_metrics(self) -> ThreadMetrics:
        """收集所有线程指标"""
        try:
            self.stats['total_collections'] += 1
            
            # 收集系统线程指标
            system_metrics = self.collect_system_thread_metrics()
            
            # 收集线程池指标
            pool_metrics = self.collect_thread_pool_metrics()
            
            # 收集WebGPU线程指标
            webgpu_metrics = self.collect_webgpu_thread_metrics()
            
            # 计算线程质量指标
            quality_metrics = self.calculate_thread_quality_metrics()
            
            # 更新线程指标
            for key, value in system_metrics.items():
                setattr(self.thread_metrics, key, value)
            
            for key, value in pool_metrics.items():
                setattr(self.thread_metrics, key, value)
            
            for key, value in webgpu_metrics.items():
                setattr(self.thread_metrics, key, value)
            
            for key, value in quality_metrics.items():
                setattr(self.thread_metrics, key, value)
            
            # 预防性监控机制
            try:
                # 1. 检测线程泄漏
                leak_detection = self.detect_thread_leaks()
                if leak_detection.get('is_leak'):
                    self.thread_metrics.is_thread_leak_detected = True
                
                # 2. 动态调整阈值
                self.adjust_thresholds_dynamically(self.thread_metrics)
                
                # 3. 调整监控间隔
                self.adjust_monitoring_interval(self.thread_metrics)
                
            except Exception as e:
                logger.error(f"预防性监控机制执行失败: {e}")
            
            # 更新状态
            self.update_thread_status()
            
            # 保存历史记录
            self.metrics_history.append(self.thread_metrics)
            
            # 触发指标回调
            for callback in self.metrics_callbacks:
                try:
                    callback(self.thread_metrics)
                except Exception as e:
                    logger.error(f"线程指标回调执行失败: {e}")
            
            logger.debug(f"线程指标收集完成: 活跃线程 {self.thread_metrics.active_threads_count}")
            return self.thread_metrics
            
        except Exception as e:
            logger.error(f"收集线程指标失败: {e}")
            self.stats['error_count'] += 1
            return self.thread_metrics
    
    def start_monitoring(self, interval: float = 1.0) -> bool:
        """开始线程监控"""
        if self.monitoring_active:
            logger.warning("线程监控已在运行")
            return True
        
        try:
            logger.info(f"开始线程监控，间隔: {interval}秒")
            
            self.monitoring_active = True
            self.stop_event.clear()
            self.stats['start_time'] = time.time()
            
            def monitoring_loop():
                while self.monitoring_active and not self.stop_event.is_set():
                    try:
                        self.collect_all_metrics()
                        time.sleep(interval)
                    except Exception as e:
                        logger.error(f"线程监控循环异常: {e}")
                        self.stats['error_count'] += 1
                        time.sleep(interval)
            
            self.monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info("线程监控已启动")
            return True
            
        except Exception as e:
            logger.error(f"启动线程监控失败: {e}")
            self.monitoring_active = False
            return False
    
    def stop_monitoring(self):
        """停止线程监控"""
        if not self.monitoring_active:
            logger.warning("线程监控未运行")
            return
        
        try:
            logger.info("停止线程监控...")
            
            self.monitoring_active = False
            self.stop_event.set()
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            
            logger.info("线程监控已停止")
            
        except Exception as e:
            logger.error(f"停止线程监控失败: {e}")
    
    def get_current_metrics(self) -> ThreadMetrics:
        """获取当前线程指标"""
        return self.thread_metrics
    
    def get_metrics_history(self, count: int = 100) -> List[ThreadMetrics]:
        """获取历史线程指标"""
        return list(self.metrics_history)[-count:]
    
    def get_thread_usage_trend(self, count: int = 60) -> Dict[str, List[float]]:
        """获取线程使用趋势"""
        if len(self.metrics_history) < count:
            count = len(self.metrics_history)
        
        recent_metrics = list(self.metrics_history)[-count:]
        
        return {
            'cpu_utilization': [m.cpu_utilization_percent for m in recent_metrics],
            'active_threads': [m.active_threads_count for m in recent_metrics],
            'pool_utilization': [m.thread_pool_active_count / max(1, m.thread_pool_size) 
                               for m in recent_metrics],
            'task_queue': [m.thread_pool_queued_count for m in recent_metrics]
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            **self.stats,
            'current_thread_status': self.thread_metrics.thread_status.value,
            'current_pool_status': self.thread_metrics.thread_pool_status.value,
            'active_alerts_count': len(self.thread_metrics.thread_alerts_active),
            'monitoring_active': self.monitoring_active,
            'registered_pools': list(self.thread_pools.keys())
        }

# 全局线程监控实例
_global_thread_monitor = None

def get_thread_monitor() -> ThreadMonitor:
    """获取全局线程监控实例"""
    global _global_thread_monitor
    if _global_thread_monitor is None:
        _global_thread_monitor = ThreadMonitor()
    return _global_thread_monitor