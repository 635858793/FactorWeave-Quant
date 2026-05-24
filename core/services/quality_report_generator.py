"""
数据质量报告生成器

提供数据质量分析报告生成功能，包括质量趋势分析、可视化图表和自动化报告。
支持多种报告格式和定制化配置。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
import json
import base64
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.figure import Figure
import seaborn as sns
from scipy import stats

from loguru import logger
from core.services.enhanced_data_quality_monitor import EnhancedDataQualityMonitor, QualityMetrics, DataAnomaly

logger = logger.bind(module=__name__)


class ReportFormat(Enum):
    """报告格式"""
    HTML = "html"
    PDF = "pdf"
    JSON = "json"
    EXCEL = "excel"
    MARKDOWN = "markdown"


class ReportType(Enum):
    """报告类型"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM = "custom"


@dataclass
class ReportConfig:
    """报告配置"""
    report_type: ReportType
    format: ReportFormat
    include_charts: bool = True
    include_trends: bool = True
    include_anomalies: bool = True
    include_recommendations: bool = True

    # 时间范围配置
    time_range_days: int = 7
    custom_start_date: Optional[datetime] = None
    custom_end_date: Optional[datetime] = None

    # 过滤配置
    data_sources: List[str] = field(default_factory=list)
    data_types: List[str] = field(default_factory=list)
    min_quality_score: float = 0.0

    # 输出配置
    output_path: Optional[str] = None
    template_path: Optional[str] = None

    # 可视化配置
    chart_style: str = "seaborn"
    color_palette: str = "viridis"
    figure_size: Tuple[int, int] = (12, 8)
    dpi: int = 300


@dataclass
class QualityTrend:
    """质量趋势数据"""
    data_source: str
    data_type: str
    time_series: List[datetime]
    quality_scores: List[float]
    completeness_scores: List[float]
    accuracy_scores: List[float]
    timeliness_scores: List[float]

    # 趋势分析结果
    trend_direction: str  # "improving", "declining", "stable"
    trend_strength: float  # 0-1
    correlation_with_overall: float

    # 统计信息
    mean_score: float
    std_score: float
    min_score: float
    max_score: float

    # 预测信息
    predicted_next_score: Optional[float] = None
    confidence_interval: Optional[Tuple[float, float]] = None


class QualityReportGenerator:
    """
    数据质量报告生成器

    提供全面的数据质量报告生成功能：
    - 质量趋势分析和预测
    - 可视化图表生成
    - 多格式报告输出
    - 自动化报告调度
    - 定制化报告模板
    """

    def __init__(self, quality_monitor: EnhancedDataQualityMonitor):
        self.quality_monitor = quality_monitor

        # 报告配置
        self.default_config = ReportConfig(
            report_type=ReportType.WEEKLY,
            format=ReportFormat.HTML
        )

        # 模板配置
        self.templates = {
            ReportFormat.HTML: self._get_html_template(),
            ReportFormat.MARKDOWN: self._get_markdown_template()
        }

        # 图表配置
        plt.style.use('seaborn-v0_8')
        sns.set_palette("viridis")

        # 调度配置
        self._scheduler_active = False
        self._scheduler_thread = None
        self.scheduled_reports: Dict[str, Dict[str, Any]] = {}

        logger.info("数据质量报告生成器初始化完成")

    async def generate_report(self, config: ReportConfig = None) -> Dict[str, Any]:
        """
        生成数据质量报告

        Args:
            config: 报告配置，如果为None则使用默认配置

        Returns:
            Dict[str, Any]: 报告内容和元数据
        """
        try:
            if not config:
                config = self.default_config

            logger.info(f"开始生成数据质量报告: {config.report_type.value} - {config.format.value}")

            # 确定时间范围
            start_date, end_date = self._determine_time_range(config)

            # 获取质量数据
            quality_metrics = self._get_quality_metrics(config, start_date, end_date)

            if not quality_metrics:
                logger.warning("没有找到质量数据，生成空报告")
                return self._generate_empty_report(config)

            # 分析质量趋势
            quality_trends = await self._analyze_quality_trends(quality_metrics, config)

            # 生成可视化图表
            charts = {}
            if config.include_charts:
                charts = await self._generate_charts(quality_metrics, quality_trends, config)

            # 检测异常
            anomalies = []
            if config.include_anomalies:
                anomalies = await self._detect_quality_anomalies(quality_metrics, config)

            # 生成建议
            recommendations = []
            if config.include_recommendations:
                recommendations = await self._generate_recommendations(quality_metrics, quality_trends, anomalies)

            # 构建报告数据
            report_data = {
                'metadata': {
                    'generated_at': datetime.now(),
                    'report_type': config.report_type.value,
                    'format': config.format.value,
                    'time_range': {'start': start_date, 'end': end_date},
                    'data_sources_count': len(set(m.data_source for m in quality_metrics)),
                    'total_metrics': len(quality_metrics)
                },
                'summary': self._generate_summary(quality_metrics, quality_trends),
                'quality_metrics': quality_metrics,
                'quality_trends': quality_trends,
                'charts': charts,
                'anomalies': anomalies,
                'recommendations': recommendations
            }

            # 根据格式生成最终报告
            formatted_report = await self._format_report(report_data, config)

            # 保存报告
            if config.output_path:
                await self._save_report(formatted_report, config)

            logger.info(f"数据质量报告生成完成: {len(quality_metrics)} 个指标")
            return formatted_report

        except Exception as e:
            logger.error(f"生成数据质量报告失败: {e}")
            return {'error': f'报告生成失败: {e}'}

    def _determine_time_range(self, config: ReportConfig) -> Tuple[datetime, datetime]:
        """确定报告时间范围"""
        try:
            if config.custom_start_date and config.custom_end_date:
                return config.custom_start_date, config.custom_end_date

            end_date = datetime.now()

            if config.report_type == ReportType.DAILY:
                start_date = end_date - timedelta(days=1)
            elif config.report_type == ReportType.WEEKLY:
                start_date = end_date - timedelta(days=7)
            elif config.report_type == ReportType.MONTHLY:
                start_date = end_date - timedelta(days=30)
            elif config.report_type == ReportType.QUARTERLY:
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=config.time_range_days)

            return start_date, end_date

        except Exception as e:
            logger.error(f"确定时间范围失败: {e}")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            return start_date, end_date

    def _get_quality_metrics(self, config: ReportConfig, start_date: datetime, end_date: datetime) -> List[QualityMetrics]:
        """获取质量指标数据"""
        try:
            # 从质量监控器获取数据
            all_metrics = self.quality_monitor.get_quality_metrics()

            # 过滤时间范围
            filtered_metrics = [
                metric for metric in all_metrics
                if start_date <= metric.measurement_time <= end_date
            ]

            # 应用过滤条件
            if config.data_sources:
                filtered_metrics = [
                    metric for metric in filtered_metrics
                    if metric.data_source in config.data_sources
                ]

            if config.data_types:
                filtered_metrics = [
                    metric for metric in filtered_metrics
                    if metric.data_type in config.data_types
                ]

            if config.min_quality_score > 0:
                filtered_metrics = [
                    metric for metric in filtered_metrics
                    if metric.overall_score >= config.min_quality_score
                ]

            return filtered_metrics

        except Exception as e:
            logger.error(f"获取质量指标数据失败: {e}")
            return []

    async def _analyze_quality_trends(self, quality_metrics: List[QualityMetrics], config: ReportConfig) -> List[QualityTrend]:
        """分析质量趋势"""
        try:
            trends = []

            # 按数据源和类型分组
            grouped_metrics = {}
            for metric in quality_metrics:
                key = (metric.data_source, metric.data_type)
                if key not in grouped_metrics:
                    grouped_metrics[key] = []
                grouped_metrics[key].append(metric)

            # 分析每组的趋势
            for (data_source, data_type), metrics in grouped_metrics.items():
                if len(metrics) < 3:  # 至少需要3个数据点
                    continue

                # 按时间排序
                sorted_metrics = sorted(metrics, key=lambda x: x.measurement_time)

                # 提取时间序列数据
                time_series = [m.measurement_time for m in sorted_metrics]
                quality_scores = [m.overall_score for m in sorted_metrics]
                completeness_scores = [m.completeness_score for m in sorted_metrics]
                accuracy_scores = [m.accuracy_score for m in sorted_metrics]
                timeliness_scores = [m.timeliness_score for m in sorted_metrics]

                # 趋势分析
                trend_direction, trend_strength = self._calculate_trend(quality_scores)

                # 统计信息
                mean_score = np.mean(quality_scores)
                std_score = np.std(quality_scores)
                min_score = np.min(quality_scores)
                max_score = np.max(quality_scores)

                # 预测下一个值
                predicted_score, confidence_interval = self._predict_next_score(quality_scores)

                # 与整体趋势的相关性
                overall_scores = [m.overall_score for m in quality_metrics]
                correlation = np.corrcoef(quality_scores, overall_scores[:len(quality_scores)])[0, 1] if len(overall_scores) >= len(quality_scores) else 0.0

                trend = QualityTrend(
                    data_source=data_source,
                    data_type=data_type,
                    time_series=time_series,
                    quality_scores=quality_scores,
                    completeness_scores=completeness_scores,
                    accuracy_scores=accuracy_scores,
                    timeliness_scores=timeliness_scores,
                    trend_direction=trend_direction,
                    trend_strength=trend_strength,
                    correlation_with_overall=correlation,
                    mean_score=mean_score,
                    std_score=std_score,
                    min_score=min_score,
                    max_score=max_score,
                    predicted_next_score=predicted_score,
                    confidence_interval=confidence_interval
                )

                trends.append(trend)

            return trends

        except Exception as e:
            logger.error(f"分析质量趋势失败: {e}")
            return []

    def _calculate_trend(self, values: List[float]) -> Tuple[str, float]:
        """计算趋势方向和强度"""
        try:
            if len(values) < 2:
                return "stable", 0.0

            # 使用线性回归计算趋势
            x = np.arange(len(values))
            y = np.array(values)

            # 计算斜率
            slope = np.polyfit(x, y, 1)[0]

            # 计算相关系数作为趋势强度
            correlation = np.corrcoef(x, y)[0, 1]
            trend_strength = abs(correlation)

            # 确定趋势方向
            if abs(slope) < 0.001:  # 阈值可调整
                trend_direction = "stable"
            elif slope > 0:
                trend_direction = "improving"
            else:
                trend_direction = "declining"

            return trend_direction, trend_strength

        except Exception as e:
            logger.error(f"计算趋势失败: {e}")
            return "stable", 0.0

    def _predict_next_score(self, values: List[float]) -> Tuple[Optional[float], Optional[Tuple[float, float]]]:
        """预测下一个质量分数"""
        try:
            if len(values) < 3:
                return None, None

            # 简单的线性预测
            x = np.arange(len(values))
            y = np.array(values)

            # 线性回归
            coeffs = np.polyfit(x, y, 1)

            # 预测下一个值
            next_x = len(values)
            predicted_score = np.polyval(coeffs, next_x)

            # 计算置信区间（基于历史标准差）
            residuals = y - np.polyval(coeffs, x)
            std_error = np.std(residuals)

            confidence_interval = (
                predicted_score - stats.norm.ppf(0.975) * std_error,
                predicted_score + stats.norm.ppf(0.975) * std_error
            )

            # 确保预测值在合理范围内
            predicted_score = max(0.0, min(1.0, predicted_score))
            confidence_interval = (
                max(0.0, min(1.0, confidence_interval[0])),
                max(0.0, min(1.0, confidence_interval[1]))
            )

            return predicted_score, confidence_interval

        except Exception as e:
            logger.error(f"预测质量分数失败: {e}")
            return None, None

    async def _generate_charts(self, quality_metrics: List[QualityMetrics], quality_trends: List[QualityTrend], config: ReportConfig) -> Dict[str, str]:
        """生成可视化图表"""
        try:
            charts = {}

            # 设置图表样式
            plt.style.use(config.chart_style if config.chart_style in plt.style.available else 'seaborn-v0_8')

            # 1. 整体质量分数趋势图
            charts['overall_trend'] = await self._create_overall_trend_chart(quality_metrics, config)

            # 2. 数据源质量对比图
            charts['data_source_comparison'] = await self._create_data_source_comparison_chart(quality_metrics, config)

            # 3. 质量维度分布图
            charts['quality_dimensions'] = await self._create_quality_dimensions_chart(quality_metrics, config)

            # 4. 质量分数分布直方图
            charts['score_distribution'] = await self._create_score_distribution_chart(quality_metrics, config)

            # 5. 异常检测图
            if quality_trends:
                charts['anomaly_detection'] = await self._create_anomaly_detection_chart(quality_trends, config)

            return charts

        except Exception as e:
            logger.error(f"生成可视化图表失败: {e}")
            return {}

    async def _create_overall_trend_chart(self, quality_metrics: List[QualityMetrics], config: ReportConfig) -> str:
        """创建整体质量趋势图"""
        try:
            fig, ax = plt.subplots(figsize=config.figure_size)

            # 按时间排序
            sorted_metrics = sorted(quality_metrics, key=lambda x: x.measurement_time)

            if not sorted_metrics:
                return ""

            # 提取数据
            times = [m.measurement_time for m in sorted_metrics]
            scores = [m.overall_score for m in sorted_metrics]

            # 绘制趋势线
            ax.plot(times, scores, marker='o', linewidth=2, markersize=4, alpha=0.8)

            # 添加移动平均线
            if len(scores) >= 5:
                window_size = min(5, len(scores) // 3)
                moving_avg = pd.Series(scores).rolling(window=window_size, center=False).mean()
                ax.plot(times, moving_avg, '--', alpha=0.7, label=f'{window_size}期移动平均')

            # 设置图表
            ax.set_title('数据质量整体趋势', fontsize=14, fontweight='bold')
            ax.set_xlabel('时间')
            ax.set_ylabel('质量分数')
            ax.grid(True, alpha=0.3)
            ax.legend()

            # 格式化时间轴
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, len(times) // 10)))
            plt.xticks(rotation=45)

            # 设置y轴范围
            ax.set_ylim(0, 1)

            plt.tight_layout()

            # 转换为base64字符串
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=config.dpi, bbox_inches='tight')
            buffer.seek(0)
            chart_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return chart_data

        except Exception as e:
            logger.error(f"创建整体趋势图失败: {e}")
            return ""

    async def _create_data_source_comparison_chart(self, quality_metrics: List[QualityMetrics], config: ReportConfig) -> str:
        """创建数据源质量对比图"""
        try:
            # 按数据源分组计算平均质量分数
            source_scores = {}
            for metric in quality_metrics:
                if metric.data_source not in source_scores:
                    source_scores[metric.data_source] = []
                source_scores[metric.data_source].append(metric.overall_score)

            if not source_scores:
                return ""

            # 计算平均分数
            sources = list(source_scores.keys())
            avg_scores = [np.mean(scores) for scores in source_scores.values()]

            fig, ax = plt.subplots(figsize=config.figure_size)

            # 创建柱状图
            bars = ax.bar(sources, avg_scores, alpha=0.8)

            # 添加数值标签
            for bar, score in zip(bars, avg_scores):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                        f'{score:.3f}', ha='center', va='bottom')

            # 设置图表
            ax.set_title('数据源质量对比', fontsize=14, fontweight='bold')
            ax.set_xlabel('数据源')
            ax.set_ylabel('平均质量分数')
            ax.set_ylim(0, 1)
            ax.grid(True, alpha=0.3, axis='y')

            plt.xticks(rotation=45)
            plt.tight_layout()

            # 转换为base64字符串
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=config.dpi, bbox_inches='tight')
            buffer.seek(0)
            chart_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return chart_data

        except Exception as e:
            logger.error(f"创建数据源对比图失败: {e}")
            return ""

    async def _create_quality_dimensions_chart(self, quality_metrics: List[QualityMetrics], config: ReportConfig) -> str:
        """创建质量维度分布图"""
        try:
            if not quality_metrics:
                return ""

            # 计算各维度平均分数
            dimensions = ['完整性', '准确性', '及时性', '一致性', '有效性', '唯一性']
            avg_scores = [
                np.mean([m.completeness_score for m in quality_metrics]),
                np.mean([m.accuracy_score for m in quality_metrics]),
                np.mean([m.timeliness_score for m in quality_metrics]),
                np.mean([m.consistency_score for m in quality_metrics]),
                np.mean([m.validity_score for m in quality_metrics]),
                np.mean([m.uniqueness_score for m in quality_metrics])
            ]

            fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))

            # 添加第一个点到末尾以闭合雷达图
            angles = np.linspace(0, 2 * np.pi, len(dimensions), endpoint=False).tolist()
            avg_scores += avg_scores[:1]
            angles += angles[:1]

            # 绘制雷达图
            ax.plot(angles, avg_scores, 'o-', linewidth=2, alpha=0.8)
            ax.fill(angles, avg_scores, alpha=0.25)

            # 设置标签
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(dimensions)
            ax.set_ylim(0, 1)
            ax.set_title('数据质量维度分析', fontsize=14, fontweight='bold', pad=20)

            # 添加网格
            ax.grid(True)

            plt.tight_layout()

            # 转换为base64字符串
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=config.dpi, bbox_inches='tight')
            buffer.seek(0)
            chart_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return chart_data

        except Exception as e:
            logger.error(f"创建质量维度图失败: {e}")
            return ""

    async def _create_score_distribution_chart(self, quality_metrics: List[QualityMetrics], config: ReportConfig) -> str:
        """创建质量分数分布直方图"""
        try:
            if not quality_metrics:
                return ""

            scores = [m.overall_score for m in quality_metrics]

            fig, ax = plt.subplots(figsize=config.figure_size)

            # 创建直方图
            n, bins, patches = ax.hist(scores, bins=20, alpha=0.7, edgecolor='black')

            # 添加统计信息
            mean_score = np.mean(scores)
            std_score = np.std(scores)

            ax.axvline(mean_score, color='red', linestyle='--', linewidth=2,
                       label=f'平均值: {mean_score:.3f}')
            ax.axvline(mean_score + std_score, color='orange', linestyle=':',
                       label=f'+1σ: {mean_score + std_score:.3f}')
            ax.axvline(mean_score - std_score, color='orange', linestyle=':',
                       label=f'-1σ: {mean_score - std_score:.3f}')

            # 设置图表
            ax.set_title('质量分数分布', fontsize=14, fontweight='bold')
            ax.set_xlabel('质量分数')
            ax.set_ylabel('频次')
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()

            # 转换为base64字符串
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=config.dpi, bbox_inches='tight')
            buffer.seek(0)
            chart_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return chart_data

        except Exception as e:
            logger.error(f"创建分数分布图失败: {e}")
            return ""

    async def _create_anomaly_detection_chart(self, quality_trends: List[QualityTrend], config: ReportConfig) -> str:
        """创建异常检测图"""
        try:
            if not quality_trends:
                return ""

            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            axes = axes.flatten()

            for i, trend in enumerate(quality_trends[:4]):  # 最多显示4个趋势
                if i >= len(axes):
                    break

                ax = axes[i]

                # 绘制质量分数
                ax.plot(trend.time_series, trend.quality_scores, 'b-', alpha=0.7, label='质量分数')

                # 计算异常阈值
                mean_score = trend.mean_score
                std_score = trend.std_score
                upper_threshold = mean_score + 2 * std_score
                lower_threshold = mean_score - 2 * std_score

                # 绘制阈值线
                ax.axhline(upper_threshold, color='red', linestyle='--', alpha=0.7, label='上阈值')
                ax.axhline(lower_threshold, color='red', linestyle='--', alpha=0.7, label='下阈值')
                ax.axhline(mean_score, color='green', linestyle='-', alpha=0.7, label='均值')

                # 标记异常点
                for j, (time, score) in enumerate(zip(trend.time_series, trend.quality_scores)):
                    if score > upper_threshold or score < lower_threshold:
                        ax.scatter(time, score, color='red', s=50, zorder=5)

                ax.set_title(f'{trend.data_source} - {trend.data_type}')
                ax.set_ylabel('质量分数')
                ax.grid(True, alpha=0.3)
                ax.legend()

                # 格式化时间轴
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            # 隐藏多余的子图
            for i in range(len(quality_trends), len(axes)):
                axes[i].set_visible(False)

            plt.suptitle('异常检测分析', fontsize=16, fontweight='bold')
            plt.tight_layout()

            # 转换为base64字符串
            buffer = BytesIO()
            plt.savefig(buffer, format='png', dpi=config.dpi, bbox_inches='tight')
            buffer.seek(0)
            chart_data = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return chart_data

        except Exception as e:
            logger.error(f"创建异常检测图失败: {e}")
            return ""

    async def _detect_quality_anomalies(self, quality_metrics: List[QualityMetrics], config: ReportConfig) -> List[Dict[str, Any]]:
        """检测质量异常"""
        try:
            anomalies = []

            # 按数据源分组
            grouped_metrics = {}
            for metric in quality_metrics:
                key = metric.data_source
                if key not in grouped_metrics:
                    grouped_metrics[key] = []
                grouped_metrics[key].append(metric)

            # 检测每个数据源的异常
            for data_source, metrics in grouped_metrics.items():
                if len(metrics) < 3:
                    continue

                scores = [m.overall_score for m in metrics]
                mean_score = np.mean(scores)
                std_score = np.std(scores)

                # 使用2σ规则检测异常
                for metric in metrics:
                    if abs(metric.overall_score - mean_score) > 2 * std_score:
                        anomaly = {
                            'data_source': data_source,
                            'data_type': metric.data_type,
                            'timestamp': metric.measurement_time,
                            'score': metric.overall_score,
                            'expected_range': (mean_score - 2 * std_score, mean_score + 2 * std_score),
                            'severity': 'high' if abs(metric.overall_score - mean_score) > 3 * std_score else 'medium',
                            'description': f'质量分数异常: {metric.overall_score:.3f} (期望范围: {mean_score - 2 * std_score:.3f} - {mean_score + 2 * std_score:.3f})'
                        }
                        anomalies.append(anomaly)

            return anomalies

        except Exception as e:
            logger.error(f"检测质量异常失败: {e}")
            return []

    async def _generate_recommendations(self, quality_metrics: List[QualityMetrics], quality_trends: List[QualityTrend], anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成改进建议"""
        try:
            recommendations = []

            # 基于整体质量分数的建议
            if quality_metrics:
                avg_score = np.mean([m.overall_score for m in quality_metrics])

                if avg_score < 0.7:
                    recommendations.append({
                        'type': 'quality_improvement',
                        'priority': 'high',
                        'title': '整体数据质量需要改进',
                        'description': f'当前平均质量分数为 {avg_score:.3f}，建议重点关注数据源配置和数据处理流程',
                        'actions': [
                            '检查数据源连接稳定性',
                            '优化数据验证规则',
                            '增强数据清洗流程'
                        ]
                    })

                # 基于质量维度的建议
                avg_completeness = np.mean([m.completeness_score for m in quality_metrics])
                avg_accuracy = np.mean([m.accuracy_score for m in quality_metrics])
                avg_timeliness = np.mean([m.timeliness_score for m in quality_metrics])

                if avg_completeness < 0.8:
                    recommendations.append({
                        'type': 'completeness_improvement',
                        'priority': 'medium',
                        'title': '数据完整性需要提升',
                        'description': f'数据完整性分数为 {avg_completeness:.3f}，存在较多缺失数据',
                        'actions': [
                            '检查数据获取流程',
                            '增加数据源备份',
                            '实施数据补全策略'
                        ]
                    })

                if avg_accuracy < 0.8:
                    recommendations.append({
                        'type': 'accuracy_improvement',
                        'priority': 'high',
                        'title': '数据准确性需要改进',
                        'description': f'数据准确性分数为 {avg_accuracy:.3f}，可能存在数据质量问题',
                        'actions': [
                            '加强数据验证规则',
                            '实施异常值检测',
                            '优化数据清洗算法'
                        ]
                    })

                if avg_timeliness < 0.8:
                    recommendations.append({
                        'type': 'timeliness_improvement',
                        'priority': 'medium',
                        'title': '数据时效性需要优化',
                        'description': f'数据时效性分数为 {avg_timeliness:.3f}，数据更新可能存在延迟',
                        'actions': [
                            '优化数据获取频率',
                            '检查网络连接质量',
                            '实施数据预加载机制'
                        ]
                    })

            # 基于趋势的建议
            for trend in quality_trends:
                if trend.trend_direction == 'declining' and trend.trend_strength > 0.5:
                    recommendations.append({
                        'type': 'trend_alert',
                        'priority': 'high',
                        'title': f'{trend.data_source} 质量趋势下降',
                        'description': f'{trend.data_source} - {trend.data_type} 的质量分数呈下降趋势',
                        'actions': [
                            '立即检查数据源状态',
                            '分析质量下降原因',
                            '实施紧急修复措施'
                        ]
                    })

            # 基于异常的建议
            if anomalies:
                high_severity_anomalies = [a for a in anomalies if a['severity'] == 'high']
                if high_severity_anomalies:
                    recommendations.append({
                        'type': 'anomaly_alert',
                        'priority': 'critical',
                        'title': '检测到严重数据质量异常',
                        'description': f'发现 {len(high_severity_anomalies)} 个严重质量异常',
                        'actions': [
                            '立即调查异常数据源',
                            '暂停受影响的数据处理',
                            '启动数据恢复程序'
                        ]
                    })

            return recommendations

        except Exception as e:
            logger.error(f"生成改进建议失败: {e}")
            return []

    def _generate_summary(self, quality_metrics: List[QualityMetrics], quality_trends: List[QualityTrend]) -> Dict[str, Any]:
        """生成报告摘要"""
        try:
            if not quality_metrics:
                return {'message': '无质量数据'}

            # 基本统计
            overall_scores = [m.overall_score for m in quality_metrics]
            avg_score = np.mean(overall_scores)
            min_score = np.min(overall_scores)
            max_score = np.max(overall_scores)

            # 数据源统计
            data_sources = list(set(m.data_source for m in quality_metrics))
            data_types = list(set(m.data_type for m in quality_metrics))

            # 质量等级分布
            excellent_count = len([s for s in overall_scores if s >= 0.9])
            good_count = len([s for s in overall_scores if 0.8 <= s < 0.9])
            fair_count = len([s for s in overall_scores if 0.7 <= s < 0.8])
            poor_count = len([s for s in overall_scores if s < 0.7])

            # 趋势统计
            improving_trends = len([t for t in quality_trends if t.trend_direction == 'improving'])
            declining_trends = len([t for t in quality_trends if t.trend_direction == 'declining'])
            stable_trends = len([t for t in quality_trends if t.trend_direction == 'stable'])

            summary = {
                'total_metrics': len(quality_metrics),
                'data_sources_count': len(data_sources),
                'data_types_count': len(data_types),
                'average_quality_score': avg_score,
                'min_quality_score': min_score,
                'max_quality_score': max_score,
                'quality_distribution': {
                    'excellent': excellent_count,
                    'good': good_count,
                    'fair': fair_count,
                    'poor': poor_count
                },
                'trend_analysis': {
                    'improving': improving_trends,
                    'declining': declining_trends,
                    'stable': stable_trends
                },
                'data_sources': data_sources,
                'data_types': data_types
            }

            return summary

        except Exception as e:
            logger.error(f"生成报告摘要失败: {e}")
            return {'error': f'摘要生成失败: {e}'}

    async def _format_report(self, report_data: Dict[str, Any], config: ReportConfig) -> Dict[str, Any]:
        """格式化报告输出"""
        try:
            if config.format == ReportFormat.HTML:
                return await self._format_html_report(report_data, config)
            elif config.format == ReportFormat.JSON:
                return await self._format_json_report(report_data, config)
            elif config.format == ReportFormat.MARKDOWN:
                return await self._format_markdown_report(report_data, config)
            else:
                logger.warning(f"不支持的报告格式: {config.format}")
                return report_data

        except Exception as e:
            logger.error(f"格式化报告失败: {e}")
            return report_data

    async def _format_html_report(self, report_data: Dict[str, Any], config: ReportConfig) -> Dict[str, Any]:
        """格式化HTML报告"""
        try:
            template = self.templates[ReportFormat.HTML]

            # 准备模板变量
            template_vars = {
                'title': f"数据质量报告 - {report_data['metadata']['report_type']}",
                'generated_at': report_data['metadata']['generated_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'summary': report_data['summary'],
                'charts': report_data['charts'],
                'anomalies': report_data['anomalies'],
                'recommendations': report_data['recommendations'],
                'quality_trends': report_data['quality_trends']
            }

            # 渲染模板（简化实现）
            html_content = template.format(**template_vars)

            return {
                'format': 'html',
                'content': html_content,
                'metadata': report_data['metadata']
            }

        except Exception as e:
            logger.error(f"格式化HTML报告失败: {e}")
            return report_data

    async def _format_json_report(self, report_data: Dict[str, Any], config: ReportConfig) -> Dict[str, Any]:
        """格式化JSON报告"""
        try:
            # 转换不可序列化的对象
            serializable_data = self._make_serializable(report_data)

            return {
                'format': 'json',
                'content': json.dumps(serializable_data, indent=2, ensure_ascii=False),
                'metadata': report_data['metadata']
            }

        except Exception as e:
            logger.error(f"格式化JSON报告失败: {e}")
            return report_data

    async def _format_markdown_report(self, report_data: Dict[str, Any], config: ReportConfig) -> Dict[str, Any]:
        """格式化Markdown报告"""
        try:
            template = self.templates[ReportFormat.MARKDOWN]

            # 准备模板变量
            template_vars = {
                'title': f"数据质量报告 - {report_data['metadata']['report_type']}",
                'generated_at': report_data['metadata']['generated_at'].strftime('%Y-%m-%d %H:%M:%S'),
                'summary': report_data['summary'],
                'anomalies_count': len(report_data['anomalies']),
                'recommendations_count': len(report_data['recommendations'])
            }

            # 渲染模板
            markdown_content = template.format(**template_vars)

            return {
                'format': 'markdown',
                'content': markdown_content,
                'metadata': report_data['metadata']
            }

        except Exception as e:
            logger.error(f"格式化Markdown报告失败: {e}")
            return report_data

    def _make_serializable(self, obj: Any) -> Any:
        """将对象转换为可序列化格式"""
        try:
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            elif isinstance(obj, dict):
                return {k: self._make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [self._make_serializable(item) for item in obj]
            elif hasattr(obj, '__dict__'):
                return self._make_serializable(obj.__dict__)
            else:
                return obj
        except Exception as e:
            logger.error(f"序列化对象失败: {e}")
            return str(obj)

    def _generate_empty_report(self, config: ReportConfig) -> Dict[str, Any]:
        """生成空报告"""
        return {
            'format': config.format.value,
            'content': '暂无数据质量信息',
            'metadata': {
                'generated_at': datetime.now(),
                'report_type': config.report_type.value,
                'format': config.format.value,
                'message': '没有找到质量数据'
            }
        }

    async def _save_report(self, report: Dict[str, Any], config: ReportConfig):
        """保存报告到文件"""
        try:
            if not config.output_path:
                return

            content = report.get('content', '')

            with open(config.output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"报告已保存到: {config.output_path}")

        except Exception as e:
            logger.error(f"保存报告失败: {e}")

    def _get_html_template(self) -> str:
        """获取HTML报告模板"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .summary {{ margin: 20px 0; }}
                .chart {{ margin: 20px 0; text-align: center; }}
                .chart img {{ max-width: 100%; }}
                .anomaly {{ background-color: #ffe6e6; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                .recommendation {{ background-color: #e6f3ff; padding: 10px; margin: 10px 0; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{title}</h1>
                <p>生成时间: {generated_at}</p>
            </div>
            
            <div class="summary">
                <h2>报告摘要</h2>
                <p>总指标数: {summary[total_metrics]}</p>
                <p>平均质量分数: {summary[average_quality_score]:.3f}</p>
            </div>
            
            <div class="charts">
                <h2>质量分析图表</h2>
                <!-- 图表将在这里插入 -->
            </div>
            
            <div class="anomalies">
                <h2>异常检测</h2>
                <!-- 异常信息将在这里插入 -->
            </div>
            
            <div class="recommendations">
                <h2>改进建议</h2>
                <!-- 建议将在这里插入 -->
            </div>
        </body>
        </html>
        """

    def _get_markdown_template(self) -> str:
        """获取Markdown报告模板"""
        return """
# {title}

**生成时间**: {generated_at}

## 报告摘要

- 总指标数: {summary[total_metrics]}
- 数据源数量: {summary[data_sources_count]}
- 平均质量分数: {summary[average_quality_score]:.3f}

## 质量分布

- 优秀 (≥0.9): {summary[quality_distribution][excellent]}
- 良好 (0.8-0.9): {summary[quality_distribution][good]}
- 一般 (0.7-0.8): {summary[quality_distribution][fair]}
- 较差 (<0.7): {summary[quality_distribution][poor]}

## 异常检测

检测到 {anomalies_count} 个异常

## 改进建议

共 {recommendations_count} 条建议
        """

    def schedule_report(self, report_id: str, config: ReportConfig, schedule: str):
        """调度定期报告生成"""
        try:
            self.scheduled_reports[report_id] = {
                'config': config,
                'schedule': schedule,
                'last_run': None,
                'next_run': self._calculate_next_run(schedule)
            }

            if not self._scheduler_active:
                self.start_scheduler()

            logger.info(f"报告调度已设置: {report_id} - {schedule}")

        except Exception as e:
            logger.error(f"设置报告调度失败: {e}")

    def start_scheduler(self):
        """启动报告调度器"""
        try:
            if self._scheduler_active:
                return

            self._scheduler_active = True
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._scheduler_thread.start()

            logger.info("报告调度器已启动")

        except Exception as e:
            logger.error(f"启动报告调度器失败: {e}")

    def stop_scheduler(self):
        """停止报告调度器"""
        try:
            self._scheduler_active = False
            if self._scheduler_thread:
                self._scheduler_thread.join(timeout=5)

            logger.info("报告调度器已停止")

        except Exception as e:
            logger.error(f"停止报告调度器失败: {e}")

    def _scheduler_loop(self):
        """调度器循环"""
        while self._scheduler_active:
            try:
                current_time = datetime.now()

                for report_id, schedule_info in self.scheduled_reports.items():
                    next_run = schedule_info['next_run']

                    if current_time >= next_run:
                        from utils.async_utils import run_async_safe
                        run_async_safe(self.generate_report(schedule_info['config']))

                        # 更新调度信息
                        schedule_info['last_run'] = current_time
                        schedule_info['next_run'] = self._calculate_next_run(schedule_info['schedule'])

                # 等待下一次检查
                threading.Event().wait(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"报告调度循环异常: {e}")
                threading.Event().wait(10)

    def _calculate_next_run(self, schedule: str) -> datetime:
        """计算下次运行时间"""
        try:
            current_time = datetime.now()

            if schedule == 'daily':
                return current_time + timedelta(days=1)
            elif schedule == 'weekly':
                return current_time + timedelta(weeks=1)
            elif schedule == 'monthly':
                return current_time + timedelta(days=30)
            else:
                return current_time + timedelta(hours=1)  # 默认1小时

        except Exception as e:
            logger.error(f"计算下次运行时间失败: {e}")
            return datetime.now() + timedelta(hours=1)

    def cleanup(self):
        """清理资源"""
        try:
            self.stop_scheduler()
            self.scheduled_reports.clear()
            plt.close('all')  # 关闭所有matplotlib图形
            logger.info("数据质量报告生成器资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
