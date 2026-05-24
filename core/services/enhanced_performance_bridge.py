#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版性能数据桥接系统

在现有性能数据桥接基础上增加智能化功能：
1. 智能性能数据聚合和分析
2. 多源性能数据融合
3. 实时性能异常检测
4. 自适应性能阈值调整
5. 性能预测和趋势分析
6. 智能性能优化建议
7. 性能数据可视化支持
"""

import time
import threading
import json
import numpy as np
import pandas as pd
import psutil
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import statistics
from loguru import logger

from .performance_data_bridge import PerformanceDataBridge, get_performance_bridge
from .deep_analysis_service import DeepAnalysisService, get_deep_analysis_service
from ..performance.factorweave_performance_integration import FactorWeavePerformanceIntegrator, get_performance_integrator
from ..performance.unified_monitor import get_performance_monitor
from ..events import EventBus, get_event_bus


class PerformanceAnomalyType(Enum):
    """性能异常类型"""
    SPIKE = "spike"                    # 性能尖峰
    DEGRADATION = "degradation"        # 性能下降
    OSCILLATION = "oscillation"        # 性能振荡
    STAGNATION = "stagnation"         # 性能停滞
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # 资源耗尽


class PerformanceTrendType(Enum):
    """性能趋势类型"""
    IMPROVING = "improving"            # 改善中
    STABLE = "stable"                 # 稳定
    DEGRADING = "degrading"           # 恶化中
    VOLATILE = "volatile"             # 波动


@dataclass
class PerformanceAnomaly:
    """性能异常"""
    anomaly_id: str
    anomaly_type: PerformanceAnomalyType
    metric_name: str
    current_value: float
    expected_value: float
    deviation_percentage: float
    severity: str  # low, medium, high, critical
    description: str
    detected_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    auto_resolvable: bool = False
    suggested_actions: List[str] = field(default_factory=list)


@dataclass
class PerformanceTrend:
    """性能趋势"""
    metric_name: str
    trend_type: PerformanceTrendType
    trend_strength: float  # 0-1, 趋势强度
    slope: float          # 趋势斜率
    r_squared: float      # 拟合度
    prediction_confidence: float  # 预测置信度
    time_window: timedelta
    data_points: int


@dataclass
class PerformanceOptimizationSuggestion:
    """性能优化建议"""
    suggestion_id: str
    metric_name: str
    current_performance: float
    target_performance: float
    improvement_potential: float
    optimization_actions: List[str]
    estimated_impact: Dict[str, float]
    implementation_difficulty: str  # easy, medium, hard
    priority: str  # low, medium, high, critical
    created_at: datetime = field(default_factory=datetime.now)


class EnhancedPerformanceBridge:
    """增强版性能数据桥接器"""

    def __init__(self):
        # 基础组件
        self.base_bridge = get_performance_bridge()
        self.deep_analysis = get_deep_analysis_service()
        self.performance_integrator = get_performance_integrator()
        self.unified_monitor = get_performance_monitor()
        self.event_bus = get_event_bus()

        # 增强功能状态
        self.is_enhanced_running = False
        self.enhancement_thread = None

        # 数据存储
        self.performance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.anomalies: List[PerformanceAnomaly] = []
        self.trends: Dict[str, PerformanceTrend] = {}
        self.optimization_suggestions: List[PerformanceOptimizationSuggestion] = []

        # 配置参数
        self.analysis_interval = 60  # 60秒分析一次
        self.anomaly_detection_window = 300  # 5分钟检测窗口
        self.trend_analysis_window = 1800  # 30分钟趋势分析窗口
        self.optimization_check_interval = 600  # 10分钟优化检查间隔

        # 性能阈值（动态调整）
        self.adaptive_thresholds: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.threshold_learning_rate = 0.1

        # 预测模型缓存
        self.prediction_models: Dict[str, Any] = {}

        logger.info("增强版性能数据桥接器初始化完成")

    def start_enhanced_monitoring(self):
        """启动增强监控"""
        if self.is_enhanced_running:
            logger.warning("增强监控已在运行")
            return

        # 启动基础桥接器
        if not self.base_bridge._running:
            self.base_bridge.start_active_collection()

        # 启动性能集成器
        if not self.performance_integrator.is_running:
            self.performance_integrator.start_integration()

        # 启动增强功能
        self.is_enhanced_running = True
        self.enhancement_thread = threading.Thread(
            target=self._enhanced_monitoring_loop,
            name="EnhancedPerformanceMonitoring",
            daemon=True
        )
        self.enhancement_thread.start()

        logger.info("增强版性能监控已启动")

    def stop_enhanced_monitoring(self):
        """停止增强监控"""
        self.is_enhanced_running = False

        if self.enhancement_thread and self.enhancement_thread.is_alive():
            self.enhancement_thread.join(timeout=10)

        logger.info("增强版性能监控已停止")

    def _enhanced_monitoring_loop(self):
        """增强监控主循环"""
        last_analysis_time = datetime.now()
        last_optimization_check = datetime.now()

        while self.is_enhanced_running:
            try:
                current_time = datetime.now()

                # 收集和聚合性能数据
                self._collect_and_aggregate_performance_data()

                # 定期执行深度分析
                if (current_time - last_analysis_time).total_seconds() >= self.analysis_interval:
                    self._perform_deep_analysis()
                    last_analysis_time = current_time

                # 定期检查优化机会
                if (current_time - last_optimization_check).total_seconds() >= self.optimization_check_interval:
                    self._check_optimization_opportunities()
                    last_optimization_check = current_time

                # 更新自适应阈值
                self._update_adaptive_thresholds()

                time.sleep(10)  # 10秒循环间隔

            except Exception as e:
                logger.error(f"增强监控循环错误: {e}")
                time.sleep(30)  # 错误时延长等待

    def _collect_and_aggregate_performance_data(self):
        """收集和聚合性能数据"""
        try:
            current_time = datetime.now()

            # 从深度分析服务获取指标
            if hasattr(self.deep_analysis, 'metrics_history'):
                try:
                    # 确保metrics_history是可切片的序列
                    metrics_history = self.deep_analysis.metrics_history
                    if hasattr(metrics_history, '__getitem__') and hasattr(metrics_history, '__len__'):
                        # 安全地获取最近10个指标
                        recent_metrics = list(metrics_history)[-10:] if len(metrics_history) > 0 else []
                        for metric in recent_metrics:
                            if isinstance(metric, dict):
                                metric_name = metric.get('name', 'unknown')
                                metric_value = metric.get('value', 0)

                                self.performance_history[metric_name].append({
                                    'timestamp': current_time,
                                    'value': metric_value,
                                    'source': 'deep_analysis'
                                })
                except (TypeError, AttributeError, IndexError) as e:
                    logger.debug(f"深度分析指标历史访问失败: {e}")

            # 从统一监控器获取数据
            if hasattr(self.unified_monitor, 'stats'):
                for name, stats in self.unified_monitor.stats.items():
                    if hasattr(stats, 'avg_time') and stats.avg_time > 0:
                        self.performance_history[f"{name}_avg_time"].append({
                            'timestamp': current_time,
                            'value': stats.avg_time,
                            'source': 'unified_monitor'
                        })

                    if hasattr(stats, 'total_calls') and stats.total_calls > 0:
                        self.performance_history[f"{name}_call_count"].append({
                            'timestamp': current_time,
                            'value': stats.total_calls,
                            'source': 'unified_monitor'
                        })

            # 从性能集成器获取基准数据
            if hasattr(self.performance_integrator, 'benchmarks'):
                for metric_name, benchmark_config in self.performance_integrator.benchmarks.items():
                    current_value = self._get_current_benchmark_value(metric_name, benchmark_config)

                    if current_value is not None:
                        self.performance_history[metric_name].append({
                            'timestamp': current_time,
                            'value': current_value,
                            'source': 'performance_integrator'
                        })

        except Exception as e:
            logger.error(f"收集性能数据失败: {e}")

    def _get_current_benchmark_value(self, metric_name: str, benchmark_config: Dict[str, float]) -> Optional[float]:
        metric_lower = metric_name.lower()

        try:
            if 'cpu' in metric_lower:
                return psutil.cpu_percent(interval=0.1)
            elif 'memory' in metric_lower or 'ram' in metric_lower:
                return psutil.virtual_memory().percent
            elif 'disk' in metric_lower:
                return psutil.disk_usage('/').percent
            elif 'network' in metric_lower or 'net' in metric_lower:
                net_io = psutil.net_io_counters()
                return float(net_io.bytes_sent + net_io.bytes_recv) / (1024 * 1024)
            elif 'swap' in metric_lower:
                return psutil.swap_memory().percent
            else:
                logger.warning(f"无法获取指标 {metric_name} 的真实性能数据")
                return None
        except Exception as e:
            logger.error(f"获取性能基准值失败 ({metric_name}): {e}")
            return None

    def _perform_deep_analysis(self):
        """执行深度分析"""
        try:
            # 异常检测
            self._detect_performance_anomalies()

            # 趋势分析
            self._analyze_performance_trends()

            # 预测分析
            self._perform_predictive_analysis()

            logger.debug("深度性能分析完成")

        except Exception as e:
            logger.error(f"深度分析失败: {e}")

    def _detect_performance_anomalies(self):
        """检测性能异常"""
        try:
            current_time = datetime.now()
            detection_window = timedelta(seconds=self.anomaly_detection_window)

            for metric_name, history in self.performance_history.items():
                if len(history) < 10:  # 数据点不足
                    continue

                # 获取检测窗口内的数据
                window_data = [
                    point for point in history
                    if current_time - point['timestamp'] <= detection_window
                ]

                if len(window_data) < 5:
                    continue

                values = [point['value'] for point in window_data]
                current_value = values[-1]

                # 计算统计指标
                mean_value = statistics.mean(values[:-1])  # 排除当前值
                std_value = statistics.stdev(values[:-1]) if len(values) > 2 else 0

                # 异常检测逻辑
                anomalies_detected = []

                # 1. 尖峰检测（Z-score > 3）
                if std_value > 0:
                    z_score = abs(current_value - mean_value) / std_value
                    if z_score > 3:
                        anomalies_detected.append({
                            'type': PerformanceAnomalyType.SPIKE,
                            'severity': 'high' if z_score > 5 else 'medium',
                            'description': f"性能尖峰：Z-score = {z_score:.2f}"
                        })

                # 2. 性能下降检测
                if len(values) >= 5:
                    recent_avg = statistics.mean(values[-3:])
                    historical_avg = statistics.mean(values[:-3])

                    if historical_avg > 0:
                        degradation_pct = (recent_avg - historical_avg) / historical_avg

                        # 对于响应时间等指标，增加是恶化
                        if 'time' in metric_name.lower() or 'latency' in metric_name.lower():
                            if degradation_pct > 0.5:  # 增加50%以上
                                anomalies_detected.append({
                                    'type': PerformanceAnomalyType.DEGRADATION,
                                    'severity': 'high' if degradation_pct > 1.0 else 'medium',
                                    'description': f"性能下降：增加了 {degradation_pct:.1%}"
                                })
                        # 对于吞吐量等指标，减少是恶化
                        elif 'throughput' in metric_name.lower() or 'rate' in metric_name.lower():
                            if degradation_pct < -0.3:  # 减少30%以上
                                anomalies_detected.append({
                                    'type': PerformanceAnomalyType.DEGRADATION,
                                    'severity': 'high' if degradation_pct < -0.5 else 'medium',
                                    'description': f"性能下降：减少了 {abs(degradation_pct):.1%}"
                                })

                # 3. 振荡检测
                if len(values) >= 10:
                    # 计算变异系数
                    cv = std_value / mean_value if mean_value > 0 else 0
                    if cv > 0.5:  # 变异系数大于50%
                        anomalies_detected.append({
                            'type': PerformanceAnomalyType.OSCILLATION,
                            'severity': 'medium',
                            'description': f"性能振荡：变异系数 = {cv:.2f}"
                        })

                # 创建异常记录
                for anomaly_info in anomalies_detected:
                    anomaly = PerformanceAnomaly(
                        anomaly_id=f"{metric_name}_{current_time.strftime('%Y%m%d_%H%M%S')}",
                        anomaly_type=anomaly_info['type'],
                        metric_name=metric_name,
                        current_value=current_value,
                        expected_value=mean_value,
                        deviation_percentage=abs(current_value - mean_value) / mean_value * 100 if mean_value > 0 else 0,
                        severity=anomaly_info['severity'],
                        description=anomaly_info['description'],
                        auto_resolvable=anomaly_info['type'] in [PerformanceAnomalyType.SPIKE],
                        suggested_actions=self._generate_anomaly_actions(anomaly_info['type'], metric_name)
                    )

                    self.anomalies.append(anomaly)
                    logger.warning(f"检测到性能异常: {anomaly.description} ({metric_name})")

            # 清理旧异常（保留最近100个）
            self.anomalies = self.anomalies[-100:]

        except Exception as e:
            logger.error(f"异常检测失败: {e}")

    def _generate_anomaly_actions(self, anomaly_type: PerformanceAnomalyType, metric_name: str) -> List[str]:
        """生成异常处理建议"""
        actions = []

        if anomaly_type == PerformanceAnomalyType.SPIKE:
            actions = [
                "检查是否有异常的大数据量处理",
                "验证系统资源是否充足",
                "检查是否有并发冲突"
            ]
        elif anomaly_type == PerformanceAnomalyType.DEGRADATION:
            actions = [
                "检查系统资源使用情况",
                "分析是否有内存泄漏",
                "检查数据库连接和查询性能",
                "验证网络连接状态"
            ]
        elif anomaly_type == PerformanceAnomalyType.OSCILLATION:
            actions = [
                "检查是否有周期性的资源竞争",
                "分析负载均衡配置",
                "检查缓存策略是否合理"
            ]

        # 根据指标名称添加特定建议
        if 'memory' in metric_name.lower():
            actions.append("检查内存使用模式和垃圾回收")
        elif 'cpu' in metric_name.lower():
            actions.append("分析CPU密集型操作")
        elif 'query' in metric_name.lower():
            actions.append("优化数据库查询和索引")

        return actions

    def _analyze_performance_trends(self):
        """分析性能趋势"""
        try:
            current_time = datetime.now()
            trend_window = timedelta(seconds=self.trend_analysis_window)

            for metric_name, history in self.performance_history.items():
                if len(history) < 20:  # 数据点不足
                    continue

                # 获取趋势分析窗口内的数据
                window_data = [
                    point for point in history
                    if current_time - point['timestamp'] <= trend_window
                ]

                if len(window_data) < 10:
                    continue

                # 准备时间序列数据
                timestamps = [(point['timestamp'] - window_data[0]['timestamp']).total_seconds()
                              for point in window_data]
                values = [point['value'] for point in window_data]

                # 线性回归分析趋势
                trend_analysis = self._perform_linear_regression(timestamps, values)

                if trend_analysis:
                    slope = trend_analysis['slope']
                    r_squared = trend_analysis['r_squared']

                    # 确定趋势类型
                    if r_squared < 0.3:  # 拟合度低，认为是波动
                        trend_type = PerformanceTrendType.VOLATILE
                        trend_strength = r_squared
                    elif abs(slope) < 0.001:  # 斜率接近0，认为是稳定
                        trend_type = PerformanceTrendType.STABLE
                        trend_strength = 1 - abs(slope) * 1000
                    else:
                        # 根据指标类型判断趋势方向
                        if self._is_lower_better_metric(metric_name):
                            trend_type = PerformanceTrendType.IMPROVING if slope < 0 else PerformanceTrendType.DEGRADING
                        else:
                            trend_type = PerformanceTrendType.IMPROVING if slope > 0 else PerformanceTrendType.DEGRADING

                        trend_strength = min(1.0, abs(slope) * 100)

                    # 创建趋势记录
                    trend = PerformanceTrend(
                        metric_name=metric_name,
                        trend_type=trend_type,
                        trend_strength=trend_strength,
                        slope=slope,
                        r_squared=r_squared,
                        prediction_confidence=r_squared,
                        time_window=trend_window,
                        data_points=len(window_data)
                    )

                    self.trends[metric_name] = trend

                    if trend_type == PerformanceTrendType.DEGRADING and trend_strength > 0.7:
                        logger.warning(f"检测到性能恶化趋势: {metric_name} (强度: {trend_strength:.2f})")

        except Exception as e:
            logger.error(f"趋势分析失败: {e}")

    def _perform_linear_regression(self, x_values: List[float], y_values: List[float]) -> Optional[Dict[str, float]]:
        """执行线性回归分析"""
        try:
            if len(x_values) != len(y_values) or len(x_values) < 2:
                return None

            n = len(x_values)
            sum_x = sum(x_values)
            sum_y = sum(y_values)
            sum_xy = sum(x * y for x, y in zip(x_values, y_values))
            sum_x2 = sum(x * x for x in x_values)
            sum_y2 = sum(y * y for y in y_values)

            # 计算斜率和截距
            denominator = n * sum_x2 - sum_x * sum_x
            if abs(denominator) < 1e-10:
                return None

            slope = (n * sum_xy - sum_x * sum_y) / denominator
            intercept = (sum_y - slope * sum_x) / n

            # 计算R²
            y_mean = sum_y / n
            ss_tot = sum((y - y_mean) ** 2 for y in y_values)
            ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, y_values))

            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            return {
                'slope': slope,
                'intercept': intercept,
                'r_squared': max(0, r_squared)
            }

        except Exception as e:
            logger.error(f"线性回归分析失败: {e}")
            return None

    def _is_lower_better_metric(self, metric_name: str) -> bool:
        """判断是否是越低越好的指标"""
        lower_better_keywords = [
            'time', 'latency', 'delay', 'duration', 'error', 'failure',
            'cpu_usage', 'memory_usage', 'disk_usage', 'response_time'
        ]

        metric_lower = metric_name.lower()
        return any(keyword in metric_lower for keyword in lower_better_keywords)

    def _perform_predictive_analysis(self):
        """执行预测分析"""
        try:
            # 为有明显趋势的指标进行预测
            for metric_name, trend in self.trends.items():
                if (trend.trend_type in [PerformanceTrendType.IMPROVING, PerformanceTrendType.DEGRADING] and
                        trend.prediction_confidence > 0.6):

                    # 获取历史数据
                    history = list(self.performance_history[metric_name])
                    if len(history) < 10:
                        continue

                    # 预测未来30分钟的值
                    future_predictions = self._predict_future_values(history, trend, 30 * 60)  # 30分钟

                    if future_predictions:
                        # 检查是否需要预警
                        current_value = history[-1]['value']
                        predicted_value = future_predictions[-1]

                        change_percentage = abs(predicted_value - current_value) / current_value * 100 if current_value > 0 else 0

                        if change_percentage > 50:  # 预测变化超过50%
                            if trend.trend_type == PerformanceTrendType.DEGRADING:
                                logger.warning(f"性能预警: {metric_name} 预计30分钟后恶化 {change_percentage:.1f}%")
                            elif trend.trend_type == PerformanceTrendType.IMPROVING:
                                logger.info(f"性能预测: {metric_name} 预计30分钟后改善 {change_percentage:.1f}%")

        except Exception as e:
            logger.error(f"预测分析失败: {e}")

    def _predict_future_values(self, history: List[Dict], trend: PerformanceTrend,
                               prediction_seconds: int) -> Optional[List[float]]:
        """预测未来值"""
        try:
            if len(history) < 5:
                return None

            # 使用简单的线性外推
            recent_data = history[-10:]  # 使用最近10个数据点

            timestamps = [(point['timestamp'] - recent_data[0]['timestamp']).total_seconds()
                          for point in recent_data]
            values = [point['value'] for point in recent_data]

            # 线性回归
            regression = self._perform_linear_regression(timestamps, values)
            if not regression:
                return None

            # 预测未来值
            last_timestamp = timestamps[-1]
            predictions = []

            for i in range(1, prediction_seconds // 60 + 1):  # 每分钟一个预测点
                future_timestamp = last_timestamp + i * 60
                predicted_value = regression['slope'] * future_timestamp + regression['intercept']
                predictions.append(max(0, predicted_value))  # 确保非负

            return predictions

        except Exception as e:
            logger.error(f"预测未来值失败: {e}")
            return None

    def _check_optimization_opportunities(self):
        """检查优化机会"""
        try:
            current_time = datetime.now()

            for metric_name, history in self.performance_history.items():
                if len(history) < 20:
                    continue

                # 分析最近的性能表现
                recent_values = [point['value'] for point in history[-20:]]
                current_avg = statistics.mean(recent_values)

                # 获取基准值（如果有）
                baseline_value = self._get_baseline_value(metric_name)
                if not baseline_value:
                    continue

                # 计算改进潜力
                if self._is_lower_better_metric(metric_name):
                    # 越低越好的指标
                    if current_avg > baseline_value * 1.2:  # 超过基准20%
                        improvement_potential = (current_avg - baseline_value) / current_avg
                        target_performance = baseline_value

                        suggestion = self._generate_optimization_suggestion(
                            metric_name, current_avg, target_performance,
                            improvement_potential, "reduce"
                        )

                        if suggestion:
                            self.optimization_suggestions.append(suggestion)
                else:
                    # 越高越好的指标
                    if current_avg < baseline_value * 0.8:  # 低于基准20%
                        improvement_potential = (baseline_value - current_avg) / baseline_value
                        target_performance = baseline_value

                        suggestion = self._generate_optimization_suggestion(
                            metric_name, current_avg, target_performance,
                            improvement_potential, "increase"
                        )

                        if suggestion:
                            self.optimization_suggestions.append(suggestion)

            # 清理旧建议（保留最近50个）
            self.optimization_suggestions = self.optimization_suggestions[-50:]

        except Exception as e:
            logger.error(f"检查优化机会失败: {e}")

    def _get_baseline_value(self, metric_name: str) -> Optional[float]:
        """获取指标的基准值"""
        try:
            # 从性能集成器获取基准
            if hasattr(self.performance_integrator, 'benchmarks'):
                for benchmark_name, config in self.performance_integrator.benchmarks.items():
                    if benchmark_name in metric_name or metric_name in benchmark_name:
                        return config.get('target', config.get('baseline'))

            # 使用历史数据计算基准
            history = self.performance_history.get(metric_name, [])
            if len(history) > 100:
                # 使用历史最佳值作为基准
                values = [point['value'] for point in history]
                if self._is_lower_better_metric(metric_name):
                    return min(values)
                else:
                    return max(values)

            return None

        except Exception as e:
            logger.error(f"获取基准值失败: {e}")
            return None

    def _generate_optimization_suggestion(self, metric_name: str, current_performance: float,
                                          target_performance: float, improvement_potential: float,
                                          direction: str) -> Optional[PerformanceOptimizationSuggestion]:
        """生成优化建议"""
        try:
            # 生成优化动作
            optimization_actions = []
            estimated_impact = {}

            if 'cpu' in metric_name.lower():
                optimization_actions = [
                    "优化算法复杂度",
                    "减少不必要的计算",
                    "使用多线程并行处理",
                    "优化循环和递归"
                ]
                estimated_impact = {
                    'cpu_reduction': improvement_potential * 0.7,
                    'response_time_improvement': improvement_potential * 0.5
                }
            elif 'memory' in metric_name.lower():
                optimization_actions = [
                    "优化数据结构",
                    "实现对象池",
                    "减少内存分配",
                    "优化缓存策略"
                ]
                estimated_impact = {
                    'memory_reduction': improvement_potential * 0.8,
                    'gc_pressure_reduction': improvement_potential * 0.6
                }
            elif 'query' in metric_name.lower() or 'database' in metric_name.lower():
                optimization_actions = [
                    "优化SQL查询",
                    "添加数据库索引",
                    "实现查询缓存",
                    "优化数据库连接池"
                ]
                estimated_impact = {
                    'query_time_reduction': improvement_potential * 0.6,
                    'database_load_reduction': improvement_potential * 0.4
                }
            elif 'response_time' in metric_name.lower():
                optimization_actions = [
                    "实现响应缓存",
                    "优化网络请求",
                    "减少数据传输量",
                    "使用CDN加速"
                ]
                estimated_impact = {
                    'response_time_improvement': improvement_potential * 0.7,
                    'user_experience_improvement': improvement_potential * 0.8
                }
            else:
                optimization_actions = [
                    "分析性能瓶颈",
                    "优化关键路径",
                    "实现性能监控",
                    "定期性能评估"
                ]
                estimated_impact = {
                    'general_performance_improvement': improvement_potential * 0.5
                }

            # 确定优先级
            if improvement_potential > 0.5:
                priority = "critical"
                difficulty = "medium"
            elif improvement_potential > 0.3:
                priority = "high"
                difficulty = "medium"
            elif improvement_potential > 0.1:
                priority = "medium"
                difficulty = "easy"
            else:
                priority = "low"
                difficulty = "easy"

            suggestion = PerformanceOptimizationSuggestion(
                suggestion_id=f"{metric_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                metric_name=metric_name,
                current_performance=current_performance,
                target_performance=target_performance,
                improvement_potential=improvement_potential,
                optimization_actions=optimization_actions,
                estimated_impact=estimated_impact,
                implementation_difficulty=difficulty,
                priority=priority
            )

            return suggestion

        except Exception as e:
            logger.error(f"生成优化建议失败: {e}")
            return None

    def _update_adaptive_thresholds(self):
        """更新自适应阈值"""
        try:
            for metric_name, history in self.performance_history.items():
                if len(history) < 50:  # 数据不足
                    continue

                # deque不支持切片，需要先转换为列表
                history_list = list(history)
                recent_values = [point['value'] for point in history_list[-50:]]

                # 计算统计指标
                mean_val = statistics.mean(recent_values)
                std_val = statistics.stdev(recent_values) if len(recent_values) > 1 else 0

                # 更新阈值
                if metric_name not in self.adaptive_thresholds:
                    self.adaptive_thresholds[metric_name] = {}

                current_thresholds = self.adaptive_thresholds[metric_name]

                # 使用指数移动平均更新阈值
                alpha = self.threshold_learning_rate

                if 'warning_threshold' not in current_thresholds:
                    current_thresholds['warning_threshold'] = mean_val + 2 * std_val
                else:
                    new_threshold = mean_val + 2 * std_val
                    current_thresholds['warning_threshold'] = (
                        alpha * new_threshold + (1 - alpha) * current_thresholds['warning_threshold']
                    )

                if 'critical_threshold' not in current_thresholds:
                    current_thresholds['critical_threshold'] = mean_val + 3 * std_val
                else:
                    new_threshold = mean_val + 3 * std_val
                    current_thresholds['critical_threshold'] = (
                        alpha * new_threshold + (1 - alpha) * current_thresholds['critical_threshold']
                    )

        except Exception as e:
            logger.error(f"更新自适应阈值失败: {e}")

    # 公共API方法

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        try:
            current_time = datetime.now()

            # 基础统计
            total_metrics = len(self.performance_history)
            total_data_points = sum(len(history) for history in self.performance_history.values())

            # 异常统计
            recent_anomalies = [
                a for a in self.anomalies
                if (current_time - a.detected_at).total_seconds() < 3600  # 最近1小时
            ]

            anomaly_stats = {
                'total': len(recent_anomalies),
                'by_severity': {},
                'by_type': {}
            }

            for anomaly in recent_anomalies:
                # 按严重程度统计
                severity = anomaly.severity
                anomaly_stats['by_severity'][severity] = anomaly_stats['by_severity'].get(severity, 0) + 1

                # 按类型统计
                anomaly_type = anomaly.anomaly_type.value
                anomaly_stats['by_type'][anomaly_type] = anomaly_stats['by_type'].get(anomaly_type, 0) + 1

            # 趋势统计
            trend_stats = {
                'improving': 0,
                'stable': 0,
                'degrading': 0,
                'volatile': 0
            }

            for trend in self.trends.values():
                trend_stats[trend.trend_type.value] += 1

            # 优化建议统计
            optimization_stats = {
                'total': len(self.optimization_suggestions),
                'by_priority': {}
            }

            for suggestion in self.optimization_suggestions:
                priority = suggestion.priority
                optimization_stats['by_priority'][priority] = optimization_stats['by_priority'].get(priority, 0) + 1

            return {
                'timestamp': current_time.isoformat(),
                'monitoring_status': {
                    'enhanced_running': self.is_enhanced_running,
                    'base_bridge_running': self.base_bridge._running,
                    'integrator_running': self.performance_integrator.is_running
                },
                'data_statistics': {
                    'total_metrics': total_metrics,
                    'total_data_points': total_data_points,
                    'collection_window': f"{self.analysis_interval}s"
                },
                'anomaly_statistics': anomaly_stats,
                'trend_statistics': trend_stats,
                'optimization_statistics': optimization_stats,
                'adaptive_thresholds_count': len(self.adaptive_thresholds)
            }

        except Exception as e:
            logger.error(f"获取性能摘要失败: {e}")
            return {'error': str(e)}

    def get_recent_anomalies(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取最近的异常"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            recent_anomalies = [
                {
                    'anomaly_id': a.anomaly_id,
                    'type': a.anomaly_type.value,
                    'metric_name': a.metric_name,
                    'current_value': a.current_value,
                    'expected_value': a.expected_value,
                    'deviation_percentage': a.deviation_percentage,
                    'severity': a.severity,
                    'description': a.description,
                    'detected_at': a.detected_at.isoformat(),
                    'resolved_at': a.resolved_at.isoformat() if a.resolved_at else None,
                    'suggested_actions': a.suggested_actions
                }
                for a in self.anomalies
                if a.detected_at >= cutoff_time
            ]

            return sorted(recent_anomalies, key=lambda x: x['detected_at'], reverse=True)

        except Exception as e:
            logger.error(f"获取最近异常失败: {e}")
            return []

    def get_performance_trends(self) -> Dict[str, Dict[str, Any]]:
        """获取性能趋势"""
        try:
            trends_data = {}

            for metric_name, trend in self.trends.items():
                trends_data[metric_name] = {
                    'trend_type': trend.trend_type.value,
                    'trend_strength': trend.trend_strength,
                    'slope': trend.slope,
                    'r_squared': trend.r_squared,
                    'prediction_confidence': trend.prediction_confidence,
                    'time_window_seconds': trend.time_window.total_seconds(),
                    'data_points': trend.data_points
                }

            return trends_data

        except Exception as e:
            logger.error(f"获取性能趋势失败: {e}")
            return {}

    def get_optimization_suggestions(self, priority_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取优化建议"""
        try:
            suggestions = self.optimization_suggestions

            if priority_filter:
                suggestions = [s for s in suggestions if s.priority == priority_filter]

            return [
                {
                    'suggestion_id': s.suggestion_id,
                    'metric_name': s.metric_name,
                    'current_performance': s.current_performance,
                    'target_performance': s.target_performance,
                    'improvement_potential': s.improvement_potential,
                    'optimization_actions': s.optimization_actions,
                    'estimated_impact': s.estimated_impact,
                    'implementation_difficulty': s.implementation_difficulty,
                    'priority': s.priority,
                    'created_at': s.created_at.isoformat()
                }
                for s in sorted(suggestions, key=lambda x: x.created_at, reverse=True)
            ]

        except Exception as e:
            logger.error(f"获取优化建议失败: {e}")
            return []

    def get_metric_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """获取指标历史数据"""
        try:
            if metric_name not in self.performance_history:
                return []

            cutoff_time = datetime.now() - timedelta(hours=hours)

            history = [
                {
                    'timestamp': point['timestamp'].isoformat(),
                    'value': point['value'],
                    'source': point['source']
                }
                for point in self.performance_history[metric_name]
                if point['timestamp'] >= cutoff_time
            ]

            return sorted(history, key=lambda x: x['timestamp'])

        except Exception as e:
            logger.error(f"获取指标历史失败: {e}")
            return []

    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """标记异常为已解决"""
        try:
            for anomaly in self.anomalies:
                if anomaly.anomaly_id == anomaly_id:
                    anomaly.resolved_at = datetime.now()
                    logger.info(f"异常已标记为解决: {anomaly_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"解决异常失败: {e}")
            return False

    def apply_optimization_suggestion(self, suggestion_id: str) -> bool:
        """应用优化建议（标记为已应用）"""
        try:
            for i, suggestion in enumerate(self.optimization_suggestions):
                if suggestion.suggestion_id == suggestion_id:
                    # 从列表中移除已应用的建议
                    self.optimization_suggestions.pop(i)
                    logger.info(f"优化建议已应用: {suggestion_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"应用优化建议失败: {e}")
            return False


# 全局实例
_enhanced_performance_bridge = None


def get_enhanced_performance_bridge() -> EnhancedPerformanceBridge:
    """获取增强版性能数据桥接器实例"""
    global _enhanced_performance_bridge
    if _enhanced_performance_bridge is None:
        _enhanced_performance_bridge = EnhancedPerformanceBridge()
    return _enhanced_performance_bridge


def initialize_enhanced_performance_bridge(auto_start: bool = True) -> EnhancedPerformanceBridge:
    """初始化增强版性能数据桥接器"""
    bridge = get_enhanced_performance_bridge()

    if auto_start:
        bridge.start_enhanced_monitoring()

    logger.info("增强版性能数据桥接器初始化完成")
    return bridge


if __name__ == "__main__":
    # 测试代码
    bridge = initialize_enhanced_performance_bridge()

    # 等待一段时间让数据收集和分析
    time.sleep(120)  # 2分钟

    # 显示性能摘要
    summary = bridge.get_performance_summary()
    logger.info(f"性能摘要: {json.dumps(summary, indent=2, ensure_ascii=False)}")

    # 显示异常
    anomalies = bridge.get_recent_anomalies(1)
    logger.info(f"最近异常: {len(anomalies)} 个")

    # 显示趋势
    trends = bridge.get_performance_trends()
    logger.info(f"性能趋势: {len(trends)} 个指标")

    # 显示优化建议
    suggestions = bridge.get_optimization_suggestions()
    logger.info(f"优化建议: {len(suggestions)} 个")

    # 停止监控
    bridge.stop_enhanced_monitoring()
