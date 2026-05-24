#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
高级性能分析引擎
实现性能趋势分析、瓶颈预测、智能优化建议等功能

作者: Hikyuu UI系统
版本: 1.0
"""

import time
import numpy as np
import math
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
from scipy import stats
from scipy.signal import find_peaks
import warnings
warnings.filterwarnings('ignore')

from loguru import logger

from .unified_performance_coordinator import (
    UnifiedPerformanceCoordinator, UnifiedPerformanceMetrics, 
    PerformanceAlert, AlertSeverity, PerformanceCategory
)
from .enhanced_realtime_monitor import (
    EnhancedRealtimeMonitor, AnomalyDetectionResult, 
    TrendAnalysis, TrendDirection
)

class BottleneckType(Enum):
    """瓶颈类型"""
    CPU_BOUND = "cpu_bound"         # CPU限制
    MEMORY_BOUND = "memory_bound"    # 内存限制
    GPU_BOUND = "gpu_bound"          # GPU限制
    IO_BOUND = "io_bound"            # IO限制
    THREADING_BOUND = "threading_bound"  # 线程限制
    NETWORK_BOUND = "network_bound"  # 网络限制
    RENDERING_BOUND = "rendering_bound"  # 渲染限制

class OptimizationPriority(Enum):
    """优化优先级"""
    CRITICAL = "critical"     # 关键
    HIGH = "high"            # 高
    MEDIUM = "medium"        # 中
    LOW = "low"             # 低

class PerformancePattern(Enum):
    """性能模式"""
    STABLE = "stable"        # 稳定
    CYCLIC = "cyclic"        # 周期性
    TRENDING_UP = "trending_up"      # 上升趋势
    TRENDING_DOWN = "trending_down"  # 下降趋势
    SPIKY = "spiky"          # 波动剧烈
    DEGRADING = "degrading"  # 退化

@dataclass
class BottleneckAnalysis:
    """瓶颈分析结果"""
    bottleneck_type: BottleneckType
    severity: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    affected_metrics: List[str]
    description: str
    root_causes: List[str]
    impact_assessment: Dict[str, float]
    suggested_solutions: List[str]
    estimated_improvement: float

@dataclass
class PerformanceForecast:
    """性能预测结果"""
    metric_name: str
    forecast_horizon: float  # 预测时间范围（秒）
    predicted_values: List[float]
    confidence_intervals: List[Tuple[float, float]]
    trend_direction: TrendDirection
    change_probability: float
    risk_level: float
    forecast_accuracy: float

@dataclass
class OptimizationRecommendation:
    """优化建议"""
    recommendation_id: str
    priority: OptimizationPriority
    category: str
    title: str
    description: str
    impact_score: float
    implementation_effort: float
    estimated_improvement: Dict[str, float]
    implementation_steps: List[str]
    prerequisites: List[str]
    risks: List[str]
    monitoring_requirements: List[str]
    confidence: float

@dataclass
class PerformancePatternAnalysis:
    """性能模式分析"""
    metric_name: str
    pattern_type: PerformancePattern
    confidence: float
    pattern_parameters: Dict[str, float]
    cyclical_period: Optional[float] = None
    seasonality_strength: float = 0.0
    noise_level: float = 0.0
    trend_strength: float = 0.0

class TrendPredictor:
    """趋势预测器"""
    
    def __init__(self, forecast_horizons: List[int] = [60, 300, 900]):
        self.forecast_horizons = forecast_horizons  # 预测时间范围（秒）
        self.models_cache: Dict[str, Dict] = {}
        
        logger.info(f"趋势预测器初始化完成，预测范围: {forecast_horizons}")
    
    def predict_trend(self, metric_name: str, values: List[float], 
                     timestamps: List[float], 
                     horizon: int = 300) -> Optional[PerformanceForecast]:
        """预测趋势"""
        if len(values) < 10:
            return None
        
        try:
            # 数据预处理
            clean_values = self._preprocess_data(values)
            clean_timestamps = timestamps[-len(clean_values):]
            
            # 选择合适的预测模型
            model_type = self._select_prediction_model(clean_values)
            
            if model_type == "linear":
                return self._linear_prediction(metric_name, clean_values, clean_timestamps, horizon)
            elif model_type == "polynomial":
                return self._polynomial_prediction(metric_name, clean_values, clean_timestamps, horizon)
            elif model_type == "exponential":
                return self._exponential_prediction(metric_name, clean_values, clean_timestamps, horizon)
            elif model_type == "seasonal":
                return self._seasonal_prediction(metric_name, clean_values, clean_timestamps, horizon)
            else:
                return self._moving_average_prediction(metric_name, clean_values, clean_timestamps, horizon)
            
        except Exception as e:
            logger.error(f"趋势预测失败 {metric_name}: {e}")
            return None
    
    def _preprocess_data(self, values: List[float]) -> List[float]:
        """数据预处理"""
        # 移除异常值
        values_array = np.array(values)
        q75, q25 = np.percentile(values_array, [75, 25])
        iqr = q75 - q25
        lower_bound = q25 - 1.5 * iqr
        upper_bound = q75 + 1.5 * iqr
        
        clean_values = [v for v in values if lower_bound <= v <= upper_bound]
        
        # 确保有足够数据
        return clean_values[-50:] if len(clean_values) > 10 else clean_values
    
    def _select_prediction_model(self, values: List[float]) -> str:
        """选择预测模型"""
        if len(values) < 20:
            return "moving_average"
        
        # 检测趋势强度
        x = np.arange(len(values))
        slope, _, r_value, _, _ = stats.linregress(x, values)
        
        # 检测周期性
        try:
            fft = np.fft.fft(values)
            frequencies = np.fft.fftfreq(len(values))
            power_spectrum = np.abs(fft) ** 2
            
            # 查找主频率
            max_freq_idx = np.argmax(power_spectrum[1:len(values)//2]) + 1
            dominant_freq = frequencies[max_freq_idx]
            cyclical_strength = power_spectrum[max_freq_idx] / np.sum(power_spectrum)
        except Exception:
            cyclical_strength = 0
        
        # 模型选择逻辑
        if cyclical_strength > 0.3:
            return "seasonal"
        elif abs(slope) > np.std(values) * 0.01:
            return "polynomial" if abs(r_value) > 0.8 else "linear"
        elif len(values) < 30:
            return "moving_average"
        else:
            return "exponential"
    
    def _linear_prediction(self, metric_name: str, values: List[float], 
                          timestamps: List[float], horizon: int) -> PerformanceForecast:
        """线性预测"""
        x = np.array(range(len(values)))
        y = np.array(values)
        
        # 拟合线性模型
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        # 预测值
        forecast_x = np.arange(len(values), len(values) + 10)
        predicted_values = slope * forecast_x + intercept
        
        # 置信区间
        prediction_std = np.std(values) * 0.5  # 简化的不确定性估计
        confidence_intervals = [
            (pred - stats.norm.ppf(0.975) * prediction_std, pred + stats.norm.ppf(0.975) * prediction_std)
            for pred in predicted_values
        ]
        
        # 趋势方向
        trend_dir = TrendDirection.DECLINING if slope < 0 else TrendDirection.IMPROVING
        if abs(slope) < std_err:
            trend_dir = TrendDirection.STABLE
        
        return PerformanceForecast(
            metric_name=metric_name,
            forecast_horizon=horizon,
            predicted_values=predicted_values.tolist(),
            confidence_intervals=confidence_intervals,
            trend_direction=trend_dir,
            change_probability=abs(r_value),
            risk_level=abs(slope) / (np.mean(values) + 1e-8),
            forecast_accuracy=r_value ** 2
        )
    
    def _polynomial_prediction(self, metric_name: str, values: List[float], 
                              timestamps: List[float], horizon: int) -> PerformanceForecast:
        """多项式预测"""
        x = np.array(range(len(values)))
        y = np.array(values)
        
        # 二次多项式拟合
        coeffs = np.polyfit(x, y, 2)
        
        # 预测值
        forecast_x = np.arange(len(values), len(values) + 10)
        predicted_values = np.polyval(coeffs, forecast_x)
        
        # 置信区间
        residual = np.sum((y - np.polyval(coeffs, x)) ** 2)
        mse = residual / (len(y) - 3)
        prediction_std = np.sqrt(mse)
        
        confidence_intervals = [
            (pred - stats.norm.ppf(0.975) * prediction_std, pred + stats.norm.ppf(0.975) * prediction_std)
            for pred in predicted_values
        ]
        
        # 计算趋势方向
        trend_slope = 2 * coeffs[0] * (len(values) - 1) + coeffs[1]
        trend_dir = TrendDirection.DECLINING if trend_slope < 0 else TrendDirection.IMPROVING
        
        return PerformanceForecast(
            metric_name=metric_name,
            forecast_horizon=horizon,
            predicted_values=predicted_values.tolist(),
            confidence_intervals=confidence_intervals,
            trend_direction=trend_dir,
            change_probability=0.8,  # 多项式模型一般有较高置信度
            risk_level=abs(trend_slope) / (np.mean(values) + 1e-8),
            forecast_accuracy=0.7
        )
    
    def _exponential_prediction(self, metric_name: str, values: List[float], 
                               timestamps: List[float], horizon: int) -> PerformanceForecast:
        """指数预测"""
        # 转换为对数空间进行线性拟合
        log_values = np.log(np.array(values) + 1e-8)
        x = np.array(range(len(log_values)))
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, log_values)
        
        # 预测值（转换回原空间）
        forecast_x = np.arange(len(values), len(values) + 10)
        log_predictions = slope * forecast_x + intercept
        predicted_values = np.exp(log_predictions)
        
        # 置信区间
        prediction_std = np.std(values) * 0.3
        confidence_intervals = [
            (pred - stats.norm.ppf(0.975) * prediction_std, pred + stats.norm.ppf(0.975) * prediction_std)
            for pred in predicted_values
        ]
        
        # 趋势方向
        trend_dir = TrendDirection.DECLINING if slope < 0 else TrendDirection.IMPROVING
        return PerformanceForecast(
            metric_name=metric_name,
            forecast_horizon=horizon,
            predicted_values=predicted_values.tolist(),
            confidence_intervals=confidence_intervals,
            trend_direction=trend_dir,
            change_probability=abs(r_value),
            risk_level=abs(slope),
            forecast_accuracy=r_value ** 2
        )
    
    def _seasonal_prediction(self, metric_name: str, values: List[float], 
                            timestamps: List[float], horizon: int) -> PerformanceForecast:
        """季节性预测"""
        # 简化的季节性预测
        period = self._detect_cyclical_period(values)
        
        # 提取趋势和季节性
        trend = self._extract_trend(values)
        seasonal = self._extract_seasonality(values, period)
        
        # 预测值
        predicted_values = []
        confidence_intervals = []
        
        for i in range(10):
            future_step = len(values) + i
            trend_pred = trend[-1] + (future_step - len(trend)) * (trend[-1] - trend[0]) / len(trend)
            
            if period > 0:
                seasonal_pred = seasonal[future_step % period]
            else:
                seasonal_pred = 0
            
            prediction = trend_pred + seasonal_pred
            predicted_values.append(prediction)
            
            # 置信区间
            std_dev = np.std(values) * 0.4
            confidence_intervals.append((prediction - stats.norm.ppf(0.975) * std_dev, prediction + stats.norm.ppf(0.975) * std_dev))
        
        # 趋势方向
        recent_trend = (trend[-1] - trend[-min(5, len(trend)):][0]) / min(5, len(trend))
        trend_dir = TrendDirection.DECLINING if recent_trend < 0 else TrendDirection.IMPROVING
        
        return PerformanceForecast(
            metric_name=metric_name,
            forecast_horizon=horizon,
            predicted_values=predicted_values,
            confidence_intervals=confidence_intervals,
            trend_direction=trend_dir,
            change_probability=0.75,
            risk_level=0.5,  # 季节性预测中等风险
            forecast_accuracy=0.6
        )
    
    def _moving_average_prediction(self, metric_name: str, values: List[float], 
                                  timestamps: List[float], horizon: int) -> PerformanceForecast:
        """移动平均预测"""
        window_size = min(10, len(values))
        
        # 移动平均
        recent_avg = np.mean(values[-window_size:])
        predicted_values = [recent_avg] * 10
        
        # 置信区间
        std_dev = np.std(values[-window_size:])
        confidence_intervals = [
            (recent_avg - stats.norm.ppf(0.975) * std_dev, recent_avg + stats.norm.ppf(0.975) * std_dev)
            for _ in range(10)
        ]
        
        return PerformanceForecast(
            metric_name=metric_name,
            forecast_horizon=horizon,
            predicted_values=predicted_values,
            confidence_intervals=confidence_intervals,
            trend_direction=TrendDirection.STABLE,
            change_probability=0.3,
            risk_level=0.2,
            forecast_accuracy=0.4
        )
    
    def _detect_cyclical_period(self, values: List[float]) -> float:
        """检测循环周期"""
        try:
            fft = np.fft.fft(values)
            frequencies = np.fft.fftfreq(len(values))
            power_spectrum = np.abs(fft) ** 2
            
            # 查找主频率
            max_freq_idx = np.argmax(power_spectrum[1:len(values)//2]) + 1
            dominant_freq = abs(frequencies[max_freq_idx])
            
            if dominant_freq > 0:
                return 1.0 / dominant_freq
            else:
                return 0
        except Exception:
            return 0
    
    def _extract_trend(self, values: List[float]) -> List[float]:
        """提取趋势"""
        x = np.arange(len(values))
        slope, intercept, _, _, _ = stats.linregress(x, values)
        return [slope * i + intercept for i in range(len(values))]
    
    def _extract_seasonality(self, values: List[float], period: float) -> List[float]:
        """提取季节性 (numpy向量化)"""
        if period <= 0:
            return [0] * len(values)
        
        n = len(values)
        trend = self._extract_trend(values)
        detrended = np.array(values) - np.array(trend)
        
        int_period = int(period)
        phases = np.arange(n) % int_period
        
        phase_means = np.array([detrended[phases == p].mean() for p in range(int_period)])
        seasonal = phase_means[phases]
        
        return seasonal.tolist()

class BottleneckAnalyzer:
    """瓶颈分析器"""
    
    def __init__(self):
        self.analysis_history: List[BottleneckAnalysis] = []
        self.correlation_cache: Dict[str, float] = {}
        
        logger.info("瓶颈分析器初始化完成")
    
    def analyze_bottlenecks(self, metrics_history: List[UnifiedPerformanceMetrics]) -> List[BottleneckAnalysis]:
        """分析性能瓶颈"""
        if len(metrics_history) < 10:
            logger.warning("数据不足，无法进行瓶颈分析")
            return []
        
        bottlenecks = []
        
        try:

            
            # 内存瓶颈分析
            memory_bottleneck = self._analyze_memory_bottleneck(metrics_history)
            if memory_bottleneck:
                bottlenecks.append(memory_bottleneck)
            
            # 线程瓶颈分析
            thread_bottleneck = self._analyze_threading_bottleneck(metrics_history)
            if thread_bottleneck:
                bottlenecks.append(thread_bottleneck)
            
            # CPU瓶颈分析
            cpu_bottleneck = self._analyze_cpu_bottleneck(metrics_history)
            if cpu_bottleneck:
                bottlenecks.append(cpu_bottleneck)
            
            # 渲染瓶颈分析
            rendering_bottleneck = self._analyze_rendering_bottleneck(metrics_history)
            if rendering_bottleneck:
                bottlenecks.append(rendering_bottleneck)
            
            # 综合瓶颈分析
            overall_bottleneck = self._analyze_overall_bottleneck(metrics_history, bottlenecks)
            if overall_bottleneck:
                bottlenecks.append(overall_bottleneck)
            
            # 保存分析结果
            self.analysis_history.extend(bottlenecks)
            
            logger.info(f"瓶颈分析完成，发现 {len(bottlenecks)} 个潜在瓶颈")
            
        except Exception as e:
            logger.error(f"瓶颈分析失败: {e}")
        
        return bottlenecks
    

    
    def _analyze_memory_bottleneck(self, metrics_history: List[UnifiedPerformanceMetrics]) -> Optional[BottleneckAnalysis]:
        """分析内存瓶颈"""
        memory_metrics = [m.memory_metrics for m in metrics_history if m.memory_metrics]
        
        if not memory_metrics:
            return None
        
        memory_usages = [m.system_memory_usage_percent for m in memory_metrics]
        memory_leaks = [m.memory_leak_detection for m in memory_metrics if m.memory_leak_detection > 0]
        fragmentations = [m.memory_fragmentation_rate for m in memory_metrics if m.memory_fragmentation_rate > 0]
        
        # 内存使用瓶颈
        avg_memory_usage = np.mean(memory_usages)
        max_memory_usage = np.max(memory_usages)
        
        # 内存泄漏检测
        memory_leak_trend = self._calculate_trend(memory_leaks) if memory_leaks else 0
        
        # 内存碎片检测
        avg_fragmentation = np.mean(fragmentations) if fragmentations else 0
        
        severity_score = 0.0
        
        if max_memory_usage > 0.95:
            severity_score += 0.4
        elif max_memory_usage > 0.85:
            severity_score += 0.2
        
        if avg_memory_usage > 0.8:
            severity_score += 0.3
        
        if memory_leak_trend > 0.05:
            severity_score += 0.3
        
        if avg_fragmentation > 0.3:
            severity_score += 0.2
        
        if severity_score > 0.4:
            solutions = []
            if max_memory_usage > 0.9:
                solutions.extend([
                    "释放不必要的内存分配",
                    "优化数据结构",
                    "实现内存池",
                    "增加虚拟内存"
                ])
            
            if memory_leak_trend > 0.05:
                solutions.extend([
                    "修复内存泄漏",
                    "实施正确的资源管理",
                    "使用智能指针"
                ])
            
            if avg_fragmentation > 0.2:
                solutions.extend([
                    "执行内存碎片整理",
                    "优化内存分配策略",
                    "使用内存压缩"
                ])
            
            return BottleneckAnalysis(
                bottleneck_type=BottleneckType.MEMORY_BOUND,
                severity=min(1.0, severity_score),
                confidence=0.85,
                affected_metrics=["system_memory_usage", "memory_leak_detection", "memory_fragmentation"],
                description=f"内存使用压力较大，当前平均: {avg_memory_usage:.2%}",
                root_causes=[
                    "内存分配过多",
                    "内存泄漏",
                    "内存碎片化",
                    "数据结构效率低"
                ],
                impact_assessment={
                    "performance_loss": min(0.6, severity_score * 0.9),
                    "stability": min(0.8, severity_score)
                },
                suggested_solutions=solutions,
                estimated_improvement=min(0.5, severity_score * 0.7)
            )
        
        return None
    
    def _analyze_threading_bottleneck(self, metrics_history: List[UnifiedPerformanceMetrics]) -> Optional[BottleneckAnalysis]:
        """分析线程瓶颈"""
        thread_metrics = [m.thread_metrics for m in metrics_history if m.thread_metrics]
        
        if not thread_metrics:
            return None
        
        thread_counts = [m.total_threads_count for m in thread_metrics]
        cpu_utils = [m.cpu_utilization_percent for m in thread_metrics if m.cpu_utilization_percent > 0]
        deadlocks = [m.deadlock_risk_level for m in thread_metrics if m.deadlock_risk_level > 0]
        context_switches = [m.context_switches_per_second for m in thread_metrics if m.context_switches_per_second > 0]
        
        avg_thread_count = np.mean(thread_counts)
        avg_cpu_util = np.mean(cpu_utils) if cpu_utils else 0
        avg_deadlock_risk = np.mean(deadlocks) if deadlocks else 0
        avg_context_switches = np.mean(context_switches) if context_switches else 0
        
        severity_score = 0.0
        
        if avg_thread_count > 100:
            severity_score += 0.3
        elif avg_thread_count > 50:
            severity_score += 0.1
        
        if avg_cpu_util > 0.9:
            severity_score += 0.2
        
        if avg_deadlock_risk > 0.7:
            severity_score += 0.4
        
        if avg_context_switches > 1000:  # 上下文切换过多
            severity_score += 0.2
        
        if severity_score > 0.3:
            solutions = []
            if avg_thread_count > 80:
                solutions.extend([
                    "减少线程数量",
                    "优化线程池大小",
                    "使用异步编程"
                ])
            
            if avg_deadlock_risk > 0.5:
                solutions.extend([
                    "修复死锁问题",
                    "优化锁的使用",
                    "使用无锁数据结构"
                ])
            
            if avg_context_switches > 500:
                solutions.extend([
                    "减少锁竞争",
                    "优化线程调度",
                    "使用线程本地存储"
                ])
            
            return BottleneckAnalysis(
                bottleneck_type=BottleneckType.THREADING_BOUND,
                severity=min(1.0, severity_score),
                confidence=0.75,
                affected_metrics=["thread_count", "cpu_utilization", "deadlock_risk", "context_switches"],
                description=f"线程管理问题，线程数: {avg_thread_count:.0f}, 死锁风险: {avg_deadlock_risk:.2f}",
                root_causes=[
                    "线程创建过多",
                    "死锁问题",
                    "上下文切换频繁",
                    "锁竞争激烈"
                ],
                impact_assessment={
                    "performance_loss": min(0.4, severity_score * 0.6),
                    "stability": min(0.7, severity_score * 0.9)
                },
                suggested_solutions=solutions,
                estimated_improvement=min(0.3, severity_score * 0.5)
            )
        
        return None
    
    def _analyze_cpu_bottleneck(self, metrics_history: List[UnifiedPerformanceMetrics]) -> Optional[BottleneckAnalysis]:
        """分析CPU瓶颈"""
        thread_metrics = [m.thread_metrics for m in metrics_history if m.thread_metrics]
        
        if not thread_metrics:
            return None
        
        cpu_utils = [m.cpu_utilization_percent for m in thread_metrics if m.cpu_utilization_percent > 0]
        
        if not cpu_utils:
            return None
        
        avg_cpu_util = np.mean(cpu_utils)
        max_cpu_util = np.max(cpu_utils)
        cpu_trend = self._calculate_trend(cpu_utils)
        
        severity_score = 0.0
        
        if max_cpu_util > 0.95:
            severity_score += 0.4
        elif max_cpu_util > 0.85:
            severity_score += 0.2
        
        if avg_cpu_util > 0.8:
            severity_score += 0.3
        
        if cpu_trend > 0.1:
            severity_score += 0.2
        
        if severity_score > 0.4:
            return BottleneckAnalysis(
                bottleneck_type=BottleneckType.CPU_BOUND,
                severity=min(1.0, severity_score),
                confidence=0.8,
                affected_metrics=["cpu_utilization"],
                description=f"CPU使用率过高，当前平均: {avg_cpu_util:.2%}",
                root_causes=[
                    "计算密集型任务",
                    "算法效率低",
                    "CPU核心不足"
                ],
                impact_assessment={
                    "performance_loss": min(0.5, severity_score * 0.8),
                    "responsiveness": min(0.6, severity_score)
                },
                suggested_solutions=[
                    "优化算法复杂度",
                    "使用并行计算",
                    "CPU核心调优",
                    "减少CPU密集型操作"
                ],
                estimated_improvement=min(0.4, severity_score * 0.6)
            )
        
        return None
    
    def _analyze_rendering_bottleneck(self, metrics_history: List[UnifiedPerformanceMetrics]) -> Optional[BottleneckAnalysis]:
        """分析渲染瓶颈"""
        # 渲染指标
        fps_values = [m.rendering_fps for m in metrics_history if m.rendering_fps > 0]
        latency_values = [m.rendering_latency_ms for m in metrics_history if m.rendering_latency_ms > 0]
        
        if not fps_values and not latency_values:
            return None
        
        severity_score = 0.0
        
        if fps_values:
            avg_fps = np.mean(fps_values)
            min_fps = np.min(fps_values)
            
            if min_fps < 30:
                severity_score += 0.4
            elif min_fps < 45:
                severity_score += 0.2
            
            if avg_fps < 45:
                severity_score += 0.2
        
        if latency_values:
            avg_latency = np.mean(latency_values)
            
            if avg_latency > 50:
                severity_score += 0.3
            elif avg_latency > 33:
                severity_score += 0.1
        
        if severity_score > 0.3:
            return BottleneckAnalysis(
                bottleneck_type=BottleneckType.RENDERING_BOUND,
                severity=min(1.0, severity_score),
                confidence=0.85,
                affected_metrics=["rendering_fps", "rendering_latency"],
                description=f"渲染性能问题，FPS: {np.mean(fps_values):.1f}" if fps_values else "渲染指标异常",
                root_causes=[
                    "渲染管线瓶颈",
                    "GPU资源不足",
                    "WebGL/WebGPU性能问题"
                ],
                impact_assessment={
                    "user_experience": min(0.8, severity_score),
                    "performance_loss": min(0.6, severity_score * 0.8)
                },
                suggested_solutions=[
                    "优化渲染管线",
                    "降低渲染质量",
                    "使用WebGPU优化",
                    "实现LOD系统"
                ],
                estimated_improvement=min(0.5, severity_score * 0.7)
            )
        
        return None
    
    def _analyze_overall_bottleneck(self, metrics_history: List[UnifiedPerformanceMetrics], 
                                   specific_bottlenecks: List[BottleneckAnalysis]) -> Optional[BottleneckAnalysis]:
        """分析整体瓶颈"""
        # 计算整体性能指标
        performance_scores = [m.overall_performance_score for m in metrics_history]
        
        if not performance_scores:
            return None
        
        avg_performance = np.mean(performance_scores)
        performance_trend = self._calculate_trend(performance_scores)
        
        # 整体性能退化
        if avg_performance < 0.7 or performance_trend < -0.1:
            # 找到最严重的具体瓶颈
            most_severe = max(specific_bottlenecks, key=lambda x: x.severity, default=None)
            
            root_causes = [
                "多系统组件协同问题",
                "整体架构瓶颈",
                "系统资源竞争"
            ]
            
            if most_severe:
                root_causes.append(f"主要瓶颈: {most_severe.bottleneck_type.value}")
            
            return BottleneckAnalysis(
                bottleneck_type=BottleneckType.CPU_BOUND,  # 通用类型
                severity=max(0.3, 1.0 - avg_performance),
                confidence=0.7,
                affected_metrics=["overall_performance_score"],
                description=f"整体性能下降，平均评分: {avg_performance:.2f}",
                root_causes=root_causes,
                impact_assessment={
                    "performance_loss": 1.0 - avg_performance,
                    "user_experience": max(0.4, 1.0 - avg_performance)
                },
                suggested_solutions=[
                    "系统性性能优化",
                    "架构重构",
                    "资源重新分配",
                    "负载均衡优化"
                ],
                estimated_improvement=min(0.6, 1.0 - avg_performance)
            )
        
        return None
    
    def _calculate_trend(self, values: List[float]) -> float:
        """计算趋势斜率"""
        if len(values) < 3:
            return 0.0
        
        x = np.arange(len(values))
        slope, _, _, _, _ = stats.linregress(x, values)
        return slope

class OptimizationRecommender:
    """优化建议生成器"""
    
    def __init__(self):
        self.recommendation_cache: Dict[str, OptimizationRecommendation] = {}
        self.implementation_history: List[Dict] = []
        
        logger.info("优化建议生成器初始化完成")
    
    def generate_recommendations(self, 
                                bottlenecks: List[BottleneckAnalysis],
                                forecasts: List[PerformanceForecast],
                                patterns: List[PerformancePatternAnalysis]) -> List[OptimizationRecommendation]:
        """生成优化建议"""
        recommendations = []
        
        try:
            # 基于瓶颈分析的建议
            for bottleneck in bottlenecks:
                bottleneck_recs = self._generate_bottleneck_recommendations(bottleneck)
                recommendations.extend(bottleneck_recs)
            
            # 基于预测的建议
            for forecast in forecasts:
                if forecast.risk_level > 0.5:
                    forecast_recs = self._generate_forecast_recommendations(forecast)
                    recommendations.extend(forecast_recs)
            
            # 基于性能模式的建议
            for pattern in patterns:
                if pattern.confidence > 0.7:
                    pattern_recs = self._generate_pattern_recommendations(pattern)
                    recommendations.extend(pattern_recs)
            
            # 优先级排序和去重
            recommendations = self._deduplicate_and_prioritize(recommendations)
            
            logger.info(f"生成了 {len(recommendations)} 条优化建议")
            
        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
        
        return recommendations
    
    def _generate_bottleneck_recommendations(self, bottleneck: BottleneckAnalysis) -> List[OptimizationRecommendation]:
        """生成基于瓶颈的建议"""
        recommendations = []
        
        if bottleneck.bottleneck_type == BottleneckType.GPU_BOUND:
            recommendations.append(OptimizationRecommendation(
                recommendation_id=f"gpu_optimization_{int(time.time())}",
                priority=OptimizationPriority.HIGH if bottleneck.severity > 0.7 else OptimizationPriority.MEDIUM,
                category="GPU优化",
                title="GPU性能优化",
                description=f"解决GPU瓶颈问题，预计提升 {bottleneck.estimated_improvement:.1%} 性能",
                impact_score=bottleneck.severity * 0.9,
                implementation_effort=0.6,
                estimated_improvement={"gpu_utilization": -0.3, "rendering_performance": 0.4},
                implementation_steps=[
                    "分析GPU内核性能",
                    "优化着色器代码",
                    "减少GPU内存分配",
                    "启用GPU缓存"
                ],
                prerequisites=["GPU性能分析工具"],
                risks=["可能需要重新设计渲染管线"],
                monitoring_requirements=["GPU利用率监控", "GPU内存使用监控"],
                confidence=bottleneck.confidence
            ))
        
        elif bottleneck.bottleneck_type == BottleneckType.MEMORY_BOUND:
            recommendations.append(OptimizationRecommendation(
                recommendation_id=f"memory_optimization_{int(time.time())}",
                priority=OptimizationPriority.CRITICAL if bottleneck.severity > 0.8 else OptimizationPriority.HIGH,
                category="内存优化",
                title="内存使用优化",
                description=f"解决内存瓶颈，释放 {bottleneck.estimated_improvement:.1%} 内存使用",
                impact_score=bottleneck.severity * 0.8,
                implementation_effort=0.7,
                estimated_improvement={"memory_usage": -0.4, "system_stability": 0.3},
                implementation_steps=[
                    "分析内存分配模式",
                    "实施内存池",
                    "修复内存泄漏",
                    "优化数据结构"
                ],
                prerequisites=["内存分析工具", "代码审查"],
                risks=["可能影响现有功能"],
                monitoring_requirements=["内存使用监控", "内存泄漏检测"],
                confidence=bottleneck.confidence
            ))
        
        # 添加其他瓶颈类型的建议...
        
        return recommendations
    
    def _generate_forecast_recommendations(self, forecast: PerformanceForecast) -> List[OptimizationRecommendation]:
        """生成基于预测的建议"""
        if forecast.risk_level < 0.5:
            return []
        
        recommendations = []
        
        if forecast.trend_direction == TrendDirection.DECLINING:
            recommendations.append(OptimizationRecommendation(
                recommendation_id=f"preventive_{forecast.metric_name}_{int(time.time())}",
                priority=OptimizationPriority.HIGH,
                category="预防性优化",
                title=f"预防{forecast.metric_name}性能下降",
                description=f"预测{forecast.metric_name}将下降，建议提前优化",
                impact_score=forecast.risk_level * 0.7,
                implementation_effort=0.4,
                estimated_improvement={forecast.metric_name: forecast.change_probability * 0.5},
                implementation_steps=[
                    f"监控{forecast.metric_name}趋势",
                    "实施预防性措施",
                    "调整资源配置"
                ],
                prerequisites=["趋势监控工具"],
                risks=["可能过度优化"],
                monitoring_requirements=[f"{forecast.metric_name}持续监控"],
                confidence=forecast.forecast_accuracy
            ))
        
        return recommendations
    
    def _generate_pattern_recommendations(self, pattern: PerformancePatternAnalysis) -> List[OptimizationRecommendation]:
        """生成基于性能模式的建议"""
        recommendations = []
        
        if pattern.pattern_type == PerformancePattern.SPIKY:
            recommendations.append(OptimizationRecommendation(
                recommendation_id=f"stabilize_{pattern.metric_name}_{int(time.time())}",
                priority=OptimizationPriority.MEDIUM,
                category="性能稳定性",
                title=f"稳定{pattern.metric_name}性能",
                description=f"减少{pattern.metric_name}的波动性",
                impact_score=pattern.confidence * 0.6,
                implementation_effort=0.5,
                estimated_improvement={f"{pattern.metric_name}_stability": 0.4},
                implementation_steps=[
                    "分析性能波动原因",
                    "实施性能缓冲",
                    "优化任务调度"
                ],
                prerequisites=["性能分析工具"],
                risks=["可能增加平均延迟"],
                monitoring_requirements=[f"{pattern.metric_name}波动监控"],
                confidence=pattern.confidence
            ))
        
        elif pattern.pattern_type == PerformancePattern.CYCLIC:
            recommendations.append(OptimizationRecommendation(
                recommendation_id=f"optimize_cyclic_{pattern.metric_name}_{int(time.time())}",
                priority=OptimizationPriority.LOW,
                category="循环优化",
                title=f"优化{pattern.metric_name}循环模式",
                description=f"利用{pattern.metric_name}的周期性进行优化",
                impact_score=pattern.confidence * 0.4,
                implementation_effort=0.6,
                estimated_improvement={f"{pattern.metric_name}_efficiency": 0.3},
                implementation_steps=[
                    "预测周期性峰值",
                    "预分配资源",
                    "实施负载均衡"
                ],
                prerequisites=["周期分析工具"],
                risks=["预测不准确的风险"],
                monitoring_requirements=[f"{pattern.metric_name}周期性监控"],
                confidence=pattern.confidence
            ))
        
        return recommendations
    
    def _deduplicate_and_prioritize(self, recommendations: List[OptimizationRecommendation]) -> List[OptimizationRecommendation]:
        """去重和优先级排序"""
        # 按优先级排序
        priority_order = {
            OptimizationPriority.CRITICAL: 4,
            OptimizationPriority.HIGH: 3,
            OptimizationPriority.MEDIUM: 2,
            OptimizationPriority.LOW: 1
        }
        
        recommendations.sort(key=lambda x: priority_order[x.priority], reverse=True)
        
        # 简化的去重逻辑（实际实现中可能需要更复杂的相似度检测）
        unique_recommendations = []
        seen_categories = set()
        
        for rec in recommendations:
            if rec.category not in seen_categories:
                unique_recommendations.append(rec)
                seen_categories.add(rec.category)
        
        return unique_recommendations

class PerformancePatternAnalyzer:
    """性能模式分析器"""
    
    def __init__(self):
        self.pattern_cache: Dict[str, PerformancePatternAnalysis] = {}
        
        logger.info("性能模式分析器初始化完成")
    
    def analyze_patterns(self, metrics_history: List[UnifiedPerformanceMetrics]) -> List[PerformancePatternAnalysis]:
        """分析性能模式"""
        patterns = []
        
        try:
            # 提取所有数值指标
            metric_data = self._extract_metric_data(metrics_history)
            
            for metric_name, values in metric_data.items():
                if len(values) < 20:  # 需要足够数据
                    continue
                
                pattern = self._analyze_single_metric_pattern(metric_name, values)
                if pattern:
                    patterns.append(pattern)
                    self.pattern_cache[metric_name] = pattern
            
            logger.info(f"性能模式分析完成，分析了 {len(patterns)} 个指标")
            
        except Exception as e:
            logger.error(f"性能模式分析失败: {e}")
        
        return patterns
    
    def _extract_metric_data(self, metrics_history: List[UnifiedPerformanceMetrics]) -> Dict[str, List[float]]:
        """提取指标数据"""
        metric_data = defaultdict(list)
        
        for metrics in metrics_history:
            timestamp = metrics.timestamp
            
            # GPU指标
            if metrics.gpu_metrics:
                for attr_name in ['gpu_utilization_percent', 'gpu_memory_utilization', 'gpu_compute_utilization']:
                    if hasattr(metrics.gpu_metrics, attr_name):
                        value = getattr(metrics.gpu_metrics, attr_name)
                        if isinstance(value, (int, float)) and value > 0:
                            metric_data[f"gpu_{attr_name}"].append(value)
            
            # 内存指标
            if metrics.memory_metrics:
                for attr_name in ['system_memory_usage_percent', 'memory_fragmentation_rate', 'memory_leak_detection']:
                    if hasattr(metrics.memory_metrics, attr_name):
                        value = getattr(metrics.memory_metrics, attr_name)
                        if isinstance(value, (int, float)) and value >= 0:
                            metric_data[f"memory_{attr_name}"].append(value)
            
            # 线程指标
            if metrics.thread_metrics:
                for attr_name in ['cpu_utilization_percent', 'total_threads_count', 'context_switches_per_second']:
                    if hasattr(metrics.thread_metrics, attr_name):
                        value = getattr(metrics.thread_metrics, attr_name)
                        if isinstance(value, (int, float)) and value >= 0:
                            metric_data[f"thread_{attr_name}"].append(value)
            
            # 渲染指标
            if metrics.rendering_fps > 0:
                metric_data["rendering_fps"].append(metrics.rendering_fps)
            
            if metrics.rendering_latency_ms > 0:
                metric_data["rendering_latency"].append(metrics.rendering_latency_ms)
        
        return dict(metric_data)
    
    def _analyze_single_metric_pattern(self, metric_name: str, values: List[float]) -> Optional[PerformancePatternAnalysis]:
        """分析单个指标的模式"""
        if len(values) < 20:
            return None
        
        try:
            values_array = np.array(values)
            
            # 1. 检测趋势
            trend_strength = self._detect_trend_strength(values_array)
            
            # 2. 检测周期性
            cyclical_strength, cyclical_period = self._detect_cyclical_pattern(values_array)
            
            # 3. 检测噪声水平
            noise_level = self._detect_noise_level(values_array)
            
            # 4. 检测波动性
            spikiness = self._detect_spikiness(values_array)
            
            # 确定主要模式
            pattern_type = PerformancePattern.STABLE
            confidence = 0.5
            
            if cyclical_strength > 0.3:
                pattern_type = PerformancePattern.CYCLIC
                confidence = cyclical_strength
            elif spikiness > 0.5:
                pattern_type = PerformancePattern.SPIKY
                confidence = spikiness
            elif trend_strength > 0.6:
                if self._is_positive_trend(values_array):
                    pattern_type = PerformancePattern.TRENDING_UP
                else:
                    pattern_type = PerformancePattern.TRENDING_DOWN
                confidence = trend_strength
            elif noise_level > 0.4:
                pattern_type = PerformancePattern.SPIKY
                confidence = noise_level
            
            # 计算额外的模式参数
            pattern_params = {
                'trend_strength': trend_strength,
                'cyclical_strength': cyclical_strength,
                'noise_level': noise_level,
                'spikiness': spikiness,
                'variance': np.var(values_array),
                'mean': np.mean(values_array),
                'coefficient_of_variation': np.std(values_array) / (np.mean(values_array) + 1e-8)
            }
            
            return PerformancePatternAnalysis(
                metric_name=metric_name,
                pattern_type=pattern_type,
                confidence=confidence,
                pattern_parameters=pattern_params,
                cyclical_period=cyclical_period if cyclical_strength > 0.3 else None,
                seasonality_strength=cyclical_strength,
                noise_level=noise_level,
                trend_strength=trend_strength
            )
            
        except Exception as e:
            logger.error(f"分析指标{metric_name}模式失败: {e}")
            return None
    
    def _detect_trend_strength(self, values: np.ndarray) -> float:
        """检测趋势强度"""
        if len(values) < 3:
            return 0.0
        
        x = np.arange(len(values))
        slope, _, r_value, _, _ = stats.linregress(x, values)
        
        # R-squared表示趋势的强度
        return abs(r_value)
    
    def _detect_cyclical_pattern(self, values: np.ndarray) -> Tuple[float, float]:
        """检测周期性模式"""
        try:
            # 使用FFT检测周期性
            fft = np.fft.fft(values)
            frequencies = np.fft.fftfreq(len(values))
            power_spectrum = np.abs(fft) ** 2
            
            # 找到主频率（排除直流分量）
            max_freq_idx = np.argmax(power_spectrum[1:len(values)//2]) + 1
            dominant_freq = abs(frequencies[max_freq_idx])
            cyclical_strength = power_spectrum[max_freq_idx] / np.sum(power_spectrum)
            
            if dominant_freq > 0:
                period = 1.0 / dominant_freq
                return cyclical_strength, period
            else:
                return 0.0, 0.0
                
        except Exception:
            return 0.0, 0.0
    
    def _detect_noise_level(self, values: np.ndarray) -> float:
        """检测噪声水平"""
        # 计算相邻值的差异
        diff = np.diff(values)
        noise_level = np.std(diff) / (np.std(values) + 1e-8)
        return min(1.0, noise_level)
    
    def _detect_spikiness(self, values: np.ndarray) -> float:
        """检测波动性"""
        # 使用IQR来检测异常值
        q75, q25 = np.percentile(values, [75, 25])
        iqr = q75 - q25
        
        # 计算离群值比例
        outlier_threshold = 1.5 * iqr
        outliers = np.sum((values < q25 - outlier_threshold) | (values > q75 + outlier_threshold))
        spikiness = outliers / len(values)
        
        return spikiness
    
    def _is_positive_trend(self, values: np.ndarray) -> bool:
        """判断是否为正向趋势"""
        if len(values) < 3:
            return True
        
        x = np.arange(len(values))
        slope, _, _, _, _ = stats.linregress(x, values)
        return slope > 0

class AdvancedPerformanceAnalytics:
    """高级性能分析引擎"""
    
    def __init__(self, coordinator: UnifiedPerformanceCoordinator):
        self.coordinator = coordinator
        self.trend_predictor = TrendPredictor()
        self.bottleneck_analyzer = BottleneckAnalyzer()
        self.optimization_recommender = OptimizationRecommender()
        self.pattern_analyzer = PerformancePatternAnalyzer()
        
        # 分析结果缓存
        self.analysis_cache: Dict[str, Any] = {}
        self.last_analysis_time: Dict[str, float] = {}
        
        # 分析配置
        self.analysis_interval = 300  # 5分钟分析一次
        self.forecast_horizons = [60, 300, 900]  # 1分钟、5分钟、15分钟
        
        logger.info("高级性能分析引擎初始化完成")
    
    def _recommendation_to_dict(self, recommendation: OptimizationRecommendation) -> Dict[str, Any]:
        """转换优化建议为字典"""
        return {
            'recommendation_id': recommendation.recommendation_id,
            'priority': recommendation.priority.value,
            'category': recommendation.category,
            'title': recommendation.title,
            'description': recommendation.description,
            'impact_score': recommendation.impact_score,
            'implementation_effort': recommendation.implementation_effort,
            'estimated_improvement': recommendation.estimated_improvement,
            'implementation_steps': recommendation.implementation_steps,
            'prerequisites': recommendation.prerequisites,
            'risks': recommendation.risks,
            'monitoring_requirements': recommendation.monitoring_requirements,
            'confidence': recommendation.confidence
        }
    
    def get_analysis_status(self) -> Dict[str, Any]:
        """获取分析状态"""
        return {
            'last_analysis_time': self.last_analysis_time.get('comprehensive', 0),
            'analysis_interval': self.analysis_interval,
            'forecast_horizons': self.forecast_horizons,
            'cache_size': len(self.analysis_cache),
            'supported_analyses': [
                'trend_prediction',
                'bottleneck_analysis', 
                'pattern_analysis',
                'optimization_recommendations'
            ]
        }

# 全局高级分析实例
_global_analytics_engine = None

def get_advanced_performance_analytics() -> AdvancedPerformanceAnalytics:
    """获取全局高级性能分析实例"""
    global _global_analytics_engine
    if _global_analytics_engine is None:
        from .unified_performance_coordinator import get_unified_performance_coordinator
        coordinator = get_unified_performance_coordinator()
        _global_analytics_engine = AdvancedPerformanceAnalytics(coordinator)
    return _global_analytics_engine