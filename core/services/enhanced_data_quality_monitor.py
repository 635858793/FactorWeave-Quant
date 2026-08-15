"""
增强数据质量监控器

提供多维度数据质量评分、异常检测、告警机制等功能。
支持实时监控数据完整性、准确性、及时性、一致性等指标。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

# 延迟导入pandas和numpy，避免在模块级别导入时调用matplotlib.get_backend()
pd = None
np = None

def _import_pandas_numpy():
    """延迟导入pandas和numpy"""
    global pd, np
    if pd is None:
        import pandas as pd
    if np is None:
        import numpy as np
    return pd, np

# 导入数据质量风险管理器和告警规则引擎
from ..data_quality_risk_manager import DataQualityRiskManager
from .alert_rule_engine import (
    AlertRuleEngine, AlertRule, RuleCondition,
    RuleConditionType, RuleAction, RuleActionType,
)
from .alert_deduplication_service import AlertLevel

logger = logger.bind(module=__name__)


class QualityDimension(Enum):
    """数据质量维度"""
    COMPLETENESS = "completeness"  # 完整性
    ACCURACY = "accuracy"          # 准确性
    TIMELINESS = "timeliness"      # 及时性
    CONSISTENCY = "consistency"    # 一致性
    VALIDITY = "validity"          # 有效性
    UNIQUENESS = "uniqueness"      # 唯一性


@dataclass
class QualityMetrics:
    """数据质量指标"""
    data_source: str
    data_type: str
    symbol: Optional[str] = None

    # 质量评分 (0-1)
    completeness_score: float = 0.0
    accuracy_score: float = 0.0
    timeliness_score: float = 0.0
    consistency_score: float = 0.0
    validity_score: float = 0.0
    uniqueness_score: float = 0.0

    # 综合评分
    overall_score: float = 0.0

    # 统计信息
    total_records: int = 0
    missing_records: int = 0
    invalid_records: int = 0
    duplicate_records: int = 0

    # 时间信息
    measurement_time: datetime = field(default_factory=datetime.now)
    data_timestamp: Optional[datetime] = None

    # 元数据
    quality_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class DataAnomaly:
    """数据异常"""
    anomaly_id: str
    data_source: str
    data_type: str
    anomaly_type: str
    severity: str      # 'low', 'medium', 'high', 'critical'
    description: str
    symbol: Optional[str] = None

    # 异常详情
    affected_records: int = 0
    expected_value: Any = None
    actual_value: Any = None

    # 时间信息
    detected_time: datetime = field(default_factory=datetime.now)
    first_occurrence: Optional[datetime] = None

    # 处理状态
    status: str = "detected"  # 'detected', 'investigating', 'resolved', 'ignored'
    resolution: str = ""


class EnhancedDataQualityMonitor:
    """
    增强数据质量监控器

    提供全面的数据质量监控功能：
    - 多维度质量评分
    - 实时异常检测
    - 智能告警机制
    - 质量趋势分析
    - 自动化质量报告
    """

    def __init__(self, risk_manager: DataQualityRiskManager, alert_engine: AlertRuleEngine):
        self.risk_manager = risk_manager
        self.alert_engine = alert_engine

        # 质量指标存储
        self._quality_metrics: Dict[str, QualityMetrics] = {}
        self._anomalies: Dict[str, DataAnomaly] = {}
        self._quality_history: List[QualityMetrics] = []

        # 监控配置
        self.quality_thresholds = {
            QualityDimension.COMPLETENESS: 0.95,
            QualityDimension.ACCURACY: 0.98,
            QualityDimension.TIMELINESS: 0.90,
            QualityDimension.CONSISTENCY: 0.95,
            QualityDimension.VALIDITY: 0.97,
            QualityDimension.UNIQUENESS: 0.99
        }

        # 异常检测配置
        self.anomaly_rules = {
            'missing_data_threshold': 0.05,      # 缺失数据超过5%
            'delay_threshold_minutes': 10,       # 数据延迟超过10分钟
            'outlier_std_threshold': 3.0,        # 超过3个标准差
            'duplicate_threshold': 0.01          # 重复数据超过1%
        }

        # 监控状态
        self._monitoring_active = False
        self._monitor_thread = None
        self._lock = threading.RLock()

        # R286 修复2：预注册数据质量告警规则（此前 alert_engine 仅存不用，告警链路断）
        self._register_quality_alerts()

        logger.info("增强数据质量监控器初始化完成")

    def start_monitoring(self):
        """启动质量监控"""
        try:
            if self._monitoring_active:
                logger.warning("数据质量监控已在运行")
                return

            self._monitoring_active = True
            self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitor_thread.start()

            logger.info("数据质量监控已启动")

        except Exception as e:
            logger.error(f"启动数据质量监控失败: {e}")

    def stop_monitoring(self):
        """停止质量监控"""
        try:
            self._monitoring_active = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)

            logger.info("数据质量监控已停止")

        except Exception as e:
            logger.error(f"停止数据质量监控失败: {e}")

    def _monitoring_loop(self):
        """监控循环"""
        while self._monitoring_active:
            try:
                # 执行质量检查
                self._perform_quality_checks()

                # 检测异常
                self._detect_anomalies()

                # 发送告警
                self._process_alerts()

                # 清理过期数据
                self._cleanup_old_data()

                # 等待下一轮检查
                threading.Event().wait(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"质量监控循环异常: {e}")
                threading.Event().wait(10)  # 异常时等待10秒

    def monitor_data_quality(self, data_source: str, data_type: str, data: 'pd.DataFrame',
                             symbol: str = None) -> QualityMetrics:
        """
        监控数据质量

        Args:
            data_source: 数据源标识
            data_type: 数据类型
            data: 数据DataFrame
            symbol: 股票代码（可选）

        Returns:
            QualityMetrics: 质量评估结果
        """
        try:
            # 延迟导入pandas和numpy
            _import_pandas_numpy()
            
            logger.debug(f"监控数据质量: {data_source} - {data_type} - {symbol}")

            # 计算各维度质量分数
            completeness = self._calculate_completeness(data)
            accuracy = self._calculate_accuracy(data, data_source, data_type)
            timeliness = self._calculate_timeliness(data, data_type)
            consistency = self._calculate_consistency(data, data_source, data_type)
            validity = self._calculate_validity(data, data_type)
            uniqueness = self._calculate_uniqueness(data)

            # 计算综合评分
            overall_score = self._calculate_overall_score({
                QualityDimension.COMPLETENESS: completeness,
                QualityDimension.ACCURACY: accuracy,
                QualityDimension.TIMELINESS: timeliness,
                QualityDimension.CONSISTENCY: consistency,
                QualityDimension.VALIDITY: validity,
                QualityDimension.UNIQUENESS: uniqueness
            })

            # 统计信息
            total_records = len(data)
            missing_records = data.isnull().sum().sum()
            duplicate_records = data.duplicated().sum()

            # 生成质量问题和建议
            quality_issues, recommendations = self._analyze_quality_issues({
                QualityDimension.COMPLETENESS: completeness,
                QualityDimension.ACCURACY: accuracy,
                QualityDimension.TIMELINESS: timeliness,
                QualityDimension.CONSISTENCY: consistency,
                QualityDimension.VALIDITY: validity,
                QualityDimension.UNIQUENESS: uniqueness
            })

            # 创建质量指标对象
            metrics = QualityMetrics(
                data_source=data_source,
                data_type=data_type,
                symbol=symbol,
                completeness_score=completeness,
                accuracy_score=accuracy,
                timeliness_score=timeliness,
                consistency_score=consistency,
                validity_score=validity,
                uniqueness_score=uniqueness,
                overall_score=overall_score,
                total_records=total_records,
                missing_records=missing_records,
                duplicate_records=duplicate_records,
                quality_issues=quality_issues,
                recommendations=recommendations
            )

            # 存储质量指标
            with self._lock:
                key = f"{data_source}_{data_type}_{symbol or 'all'}"
                self._quality_metrics[key] = metrics
                self._quality_history.append(metrics)

            # R286 修复1：把本次质量评估写入 DataQualityRiskManager 风险历史，
            # 使 get_source_risk_profile 具备按数据源聚合的真实质量画像，
            # 供 TET failover 质量加权排序使用（此前 risk_history 仅插件模板写入，
            # 生产 K 线链路完全没数据 → get_source_risk_profile 0 生产调用）。
            # backfill=True：与落库评估一致，K 线最新交易日早于当天属正常场景，
            # 避免 timeliness 把历史回填当质量缺陷惩罚。
            try:
                self.risk_manager.assess_risk(
                    data, data_source, data_type,
                    {'backfill': True, 'source': data_source}
                )
            except Exception as risk_error:
                logger.debug(f"写入数据源质量画像失败: {data_source} - {risk_error}")

            # 检查是否需要告警
            if overall_score < 0.8:  # 质量分数低于80%
                self._trigger_quality_alert(metrics)

            logger.info(f"数据质量监控完成: {data_source} - 综合评分: {overall_score:.3f}")
            return metrics

        except Exception as e:
            logger.error(f"监控数据质量失败: {data_source} - {data_type}, {e}")
            return QualityMetrics(
                data_source=data_source,
                data_type=data_type,
                symbol=symbol,
                quality_issues=[f"质量监控异常: {e}"]
            )

    def _calculate_completeness(self, data: 'pd.DataFrame') -> float:
        """计算完整性分数"""
        try:
            # 延迟导入pandas和numpy
            _import_pandas_numpy()
            
            if data.empty:
                return 0.0

            total_cells = data.size
            missing_cells = data.isnull().sum().sum()

            completeness = 1.0 - (missing_cells / total_cells)
            return max(0.0, min(1.0, completeness))

        except Exception as e:
            logger.error(f"计算完整性分数失败: {e}")
            return 0.0

    def _calculate_accuracy(self, data: 'pd.DataFrame', data_source: str, data_type: str) -> float:
        """计算准确性分数"""
        try:
            # 延迟导入pandas和numpy
            _import_pandas_numpy()
            
            if data.empty:
                return 0.0

            accuracy_score = 1.0

            # 检查数值列的合理性
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                if col in ['price', 'volume', 'amount']:
                    # 价格、成交量、金额应为正数
                    negative_count = (data[col] < 0).sum()
                    if negative_count > 0:
                        accuracy_score -= (negative_count / len(data)) * 0.5

                # 检查异常值（超过3个标准差）
                if len(data[col].dropna()) > 10:
                    std = data[col].std()
                    mean = data[col].mean()
                    outliers = ((data[col] - mean).abs() > 3 * std).sum()
                    if outliers > 0:
                        accuracy_score -= (outliers / len(data)) * 0.3

            return max(0.0, min(1.0, accuracy_score))

        except Exception as e:
            logger.error(f"计算准确性分数失败: {e}")
            return 0.5

    def _calculate_timeliness(self, data: 'pd.DataFrame', data_type: str) -> float:
        """计算及时性分数"""
        try:
            # 延迟导入pandas和numpy
            _import_pandas_numpy()
            
            if data.empty:
                return 0.0

            # 查找时间戳列
            timestamp_cols = ['trade_date', 'datetime', 'timestamp', 'time', 'date']
            timestamp_col = None

            for col in timestamp_cols:
                if col in data.columns:
                    timestamp_col = col
                    break

            if not timestamp_col:
                return 0.8  # 无时间戳信息，给予中等分数

            # 计算数据延迟
            latest_time = pd.to_datetime(data[timestamp_col]).max()
            current_time = datetime.now()

            if pd.isna(latest_time):
                return 0.0

            delay_minutes = (current_time - latest_time).total_seconds() / 60

            # 根据数据类型设置不同的延迟容忍度
            if data_type in ['realtime_quote', 'tick_data']:
                max_delay = 5  # 实时数据最多延迟5分钟
            elif data_type in ['kline_data']:
                max_delay = 60  # K线数据最多延迟1小时
            else:
                max_delay = 1440  # 其他数据最多延迟1天

            timeliness = max(0.0, 1.0 - (delay_minutes / max_delay))
            return min(1.0, timeliness)

        except Exception as e:
            logger.error(f"计算及时性分数失败: {e}")
            return 0.5

    def _calculate_consistency(self, data: 'pd.DataFrame', data_source: str, data_type: str) -> float:
        """计算一致性分数"""
        try:
            # 延迟导入pandas和numpy
            _import_pandas_numpy()
            
            if data.empty:
                return 0.0

            consistency_score = 1.0

            # 检查数据格式一致性
            for col in data.columns:
                if data[col].dtype == 'object':
                    # 字符串列格式一致性检查
                    unique_formats = data[col].dropna().map(lambda x: type(x).__name__).nunique()
                    if unique_formats > 1:
                        consistency_score -= 0.1

                # 检查数值范围一致性
                elif np.issubdtype(data[col].dtype, np.number):
                    if col in ['price', 'volume']:
                        # 价格和成交量应该在合理范围内
                        q99 = data[col].quantile(0.99)
                        q01 = data[col].quantile(0.01)
                        if q99 / q01 > 1000:  # 极值比例过大
                            consistency_score -= 0.1

            return max(0.0, min(1.0, consistency_score))

        except Exception as e:
            logger.error(f"计算一致性分数失败: {e}")
            return 0.5

    def _calculate_validity(self, data: 'pd.DataFrame', data_type: str) -> float:
        """计算有效性分数"""
        try:
            # 延迟导入pandas和numpy
            _import_pandas_numpy()
            
            if data.empty:
                return 0.0

            validity_score = 1.0
            invalid_count = 0
            total_count = len(data)

            # 根据数据类型进行有效性检查
            if data_type in ['stock_list', 'realtime_quote']:
                # 股票代码格式检查
                if 'symbol' in data.columns:
                    invalid_symbols = data['symbol'].apply(
                        lambda x: not (isinstance(x, str) and len(x) == 6 and x.isdigit())
                    ).sum()
                    invalid_count += invalid_symbols

                # 价格有效性检查
                if 'price' in data.columns:
                    invalid_prices = ((data['price'] <= 0) | (data['price'] > 10000)).sum()
                    invalid_count += invalid_prices

            elif data_type == 'kline_data':
                # K线数据有效性检查
                required_cols = ['open', 'high', 'low', 'close', 'volume']
                for col in required_cols:
                    if col in data.columns:
                        if col == 'volume':
                            invalid_count += (data[col] < 0).sum()
                        else:
                            invalid_count += (data[col] <= 0).sum()

                # 价格关系检查 (high >= low, high >= open, high >= close, low <= open, low <= close)
                if all(col in data.columns for col in ['open', 'high', 'low', 'close']):
                    invalid_ohlc = (
                        (data['high'] < data['low']) |
                        (data['high'] < data['open']) |
                        (data['high'] < data['close']) |
                        (data['low'] > data['open']) |
                        (data['low'] > data['close'])
                    ).sum()
                    invalid_count += invalid_ohlc

            validity_score = 1.0 - (invalid_count / total_count) if total_count > 0 else 0.0
            return max(0.0, min(1.0, validity_score))

        except Exception as e:
            logger.error(f"计算有效性分数失败: {e}")
            return 0.5

    def _calculate_uniqueness(self, data: 'pd.DataFrame') -> float:
        """计算唯一性分数"""
        try:
            # 延迟导入pandas和numpy
            _import_pandas_numpy()
            
            if data.empty:
                return 0.0

            total_records = len(data)
            duplicate_records = data.duplicated().sum()

            uniqueness = 1.0 - (duplicate_records / total_records)
            return max(0.0, min(1.0, uniqueness))

        except Exception as e:
            logger.error(f"计算唯一性分数失败: {e}")
            return 0.5

    def _calculate_overall_score(self, dimension_scores: Dict[QualityDimension, float]) -> float:
        """计算综合质量分数"""
        try:
            # 权重配置
            weights = {
                QualityDimension.COMPLETENESS: 0.25,
                QualityDimension.ACCURACY: 0.25,
                QualityDimension.TIMELINESS: 0.20,
                QualityDimension.CONSISTENCY: 0.15,
                QualityDimension.VALIDITY: 0.10,
                QualityDimension.UNIQUENESS: 0.05
            }

            weighted_sum = sum(
                dimension_scores.get(dim, 0.0) * weight
                for dim, weight in weights.items()
            )

            return max(0.0, min(1.0, weighted_sum))

        except Exception as e:
            logger.error(f"计算综合质量分数失败: {e}")
            return 0.0

    def _analyze_quality_issues(self, dimension_scores: Dict[QualityDimension, float]) -> Tuple[List[str], List[str]]:
        """分析质量问题并生成建议"""
        try:
            issues = []
            recommendations = []

            for dimension, score in dimension_scores.items():
                threshold = self.quality_thresholds.get(dimension, 0.8)

                if score < threshold:
                    if dimension == QualityDimension.COMPLETENESS:
                        issues.append(f"数据完整性不足: {score:.1%}")
                        recommendations.append("检查数据源连接，确保数据完整获取")

                    elif dimension == QualityDimension.ACCURACY:
                        issues.append(f"数据准确性问题: {score:.1%}")
                        recommendations.append("验证数据源质量，检查异常值处理逻辑")

                    elif dimension == QualityDimension.TIMELINESS:
                        issues.append(f"数据时效性延迟: {score:.1%}")
                        recommendations.append("优化数据获取频率，检查网络连接")

                    elif dimension == QualityDimension.CONSISTENCY:
                        issues.append(f"数据一致性问题: {score:.1%}")
                        recommendations.append("标准化数据格式，统一数据处理流程")

                    elif dimension == QualityDimension.VALIDITY:
                        issues.append(f"数据有效性问题: {score:.1%}")
                        recommendations.append("加强数据验证规则，过滤无效数据")

                    elif dimension == QualityDimension.UNIQUENESS:
                        issues.append(f"数据重复问题: {score:.1%}")
                        recommendations.append("实施去重机制，检查数据获取逻辑")

            return issues, recommendations

        except Exception as e:
            logger.error(f"分析质量问题失败: {e}")
            return [], []

    def _perform_quality_checks(self):
        """执行质量检查"""
        try:
            # 这里可以添加定期质量检查逻辑
            pass
        except Exception as e:
            logger.error(f"执行质量检查失败: {e}")

    def _detect_anomalies(self):
        """检测异常"""
        try:
            # 这里可以添加异常检测逻辑
            pass
        except Exception as e:
            logger.error(f"检测异常失败: {e}")

    def _register_quality_alerts(self):
        """R286 修复2：预注册数据质量告警规则到 AlertRuleEngine（幂等）

        此前 AlertRuleEngine 在 service_bootstrap 注册时已注入 EnhancedDataQualityMonitor，
        但从未被使用——_trigger_quality_alert 只写日志，告警规则引擎形同虚设。
        此处注册一条综合质量分过低规则，由 alert_engine 冷却/限频/去重机制接管。
        """
        try:
            if self.alert_engine is None:
                return
            if self.alert_engine.get_rule('data_quality_low_score') is not None:
                return
            rule = AlertRule(
                rule_id='data_quality_low_score',
                name='数据质量综合评分过低',
                description='数据源返回的数据综合质量评分低于 80%',
                conditions=[
                    RuleCondition(
                        condition_type=RuleConditionType.THRESHOLD,
                        metric_name='quality_overall_score',
                        operator='<',
                        threshold_value=0.8,
                        time_window_minutes=5,
                    )
                ],
                actions=[
                    RuleAction(
                        action_type=RuleActionType.LOG,
                        target='data_quality_log',
                        template='数据质量告警[{rule_name}]: 源={quality_source} 类型={quality_type} '
                                 '标的={quality_symbol} 综合评分={quality_overall_score:.1%}',
                    ),
                ],
                level=AlertLevel.WARNING,
                category='data_quality',
                cooldown_minutes=5,
                max_executions_per_hour=10,
                tags=['data_quality', 'monitor'],
            )
            self.alert_engine.add_rule(rule)
            logger.info("数据质量告警规则已注册: data_quality_low_score")
        except Exception as e:
            logger.debug(f"注册数据质量告警规则失败: {e}")

    def _feed_alert_engine(self, metrics: QualityMetrics):
        """R286 修复2：把质量指标灌入 AlertRuleEngine 并触发规则评估

        evaluate_rules 为 async 接口，同步上下文通过独立事件循环桥接。
        """
        if self.alert_engine is None:
            return
        try:
            self.alert_engine.update_metrics({
                'quality_overall_score': metrics.overall_score,
                'quality_completeness': metrics.completeness_score,
                'quality_accuracy': metrics.accuracy_score,
                'quality_timeliness': metrics.timeliness_score,
                'quality_consistency': metrics.consistency_score,
                'quality_validity': metrics.validity_score,
                'quality_uniqueness': metrics.uniqueness_score,
                'quality_missing_records': metrics.missing_records,
                'quality_duplicate_records': metrics.duplicate_records,
                'quality_source': metrics.data_source,
                'quality_type': metrics.data_type,
                'quality_symbol': metrics.symbol or 'all',
            })
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.alert_engine.evaluate_rules())
            finally:
                loop.close()
        except Exception as engine_error:
            logger.debug(f"告警规则引擎评估失败: {engine_error}")

    def _process_alerts(self):
        """处理告警——将最近一次质量监控结果灌入告警规则引擎评估

        R286 修复2：此前为 pass 空实现，监控循环每分钟空转。现在由
        AlertRuleEngine 的冷却/限频机制（cooldown_minutes/max_executions_per_hour）
        自动节流，避免重复告警。
        """
        try:
            if self.alert_engine is None:
                return
            with self._lock:
                if not self._quality_metrics:
                    return
                latest = list(self._quality_metrics.values())[-1]
            self._feed_alert_engine(latest)
        except Exception as e:
            logger.error(f"处理告警失败: {e}")

    def _cleanup_old_data(self):
        """清理过期数据"""
        try:
            # 清理7天前的历史数据
            cutoff_time = datetime.now() - timedelta(days=7)
            self._quality_history = [
                metrics for metrics in self._quality_history
                if metrics.measurement_time > cutoff_time
            ]
        except Exception as e:
            logger.error(f"清理过期数据失败: {e}")

    def _trigger_quality_alert(self, metrics: QualityMetrics):
        """触发质量告警

        R286 修复2：保留日志的同时接通 AlertRuleEngine（_feed_alert_engine），
        结束此前"仅 logger.warning、AlertRuleEngine 存而不用"的断链状态。
        """
        try:
            alert_message = f"数据质量告警: {metrics.data_source} - {metrics.data_type}"
            if metrics.symbol:
                alert_message += f" - {metrics.symbol}"
            alert_message += f", 质量分数: {metrics.overall_score:.1%}"

            # 发送告警（这里可以集成实际的告警系统）
            logger.warning(alert_message)

            # R286 修复2：同步灌入告警规则引擎（内部容错，失败不影响主链路）
            self._feed_alert_engine(metrics)

        except Exception as e:
            logger.error(f"触发质量告警失败: {e}")

    def get_quality_metrics(self, data_source: str = None, data_type: str = None) -> List[QualityMetrics]:
        """获取质量指标"""
        try:
            with self._lock:
                if data_source and data_type:
                    # 获取特定数据源和类型的指标
                    return [
                        metrics for key, metrics in self._quality_metrics.items()
                        if metrics.data_source == data_source and metrics.data_type == data_type
                    ]
                elif data_source:
                    # 获取特定数据源的所有指标
                    return [
                        metrics for metrics in self._quality_metrics.values()
                        if metrics.data_source == data_source
                    ]
                else:
                    # 获取所有指标
                    return list(self._quality_metrics.values())

        except Exception as e:
            logger.error(f"获取质量指标失败: {e}")
            return []

    def get_quality_trends(self, data_source: str, days: int = 7) -> Dict[str, List[float]]:
        """获取质量趋势"""
        try:
            cutoff_time = datetime.now() - timedelta(days=days)

            # 过滤指定时间范围和数据源的历史数据
            filtered_history = [
                metrics for metrics in self._quality_history
                if metrics.data_source == data_source and metrics.measurement_time > cutoff_time
            ]

            # 按时间排序
            filtered_history.sort(key=lambda x: x.measurement_time)

            # 提取趋势数据
            trends = {
                'timestamps': [m.measurement_time.isoformat() for m in filtered_history],
                'overall_scores': [m.overall_score for m in filtered_history],
                'completeness_scores': [m.completeness_score for m in filtered_history],
                'accuracy_scores': [m.accuracy_score for m in filtered_history],
                'timeliness_scores': [m.timeliness_score for m in filtered_history]
            }

            return trends

        except Exception as e:
            logger.error(f"获取质量趋势失败: {e}")
            return {}

    def generate_quality_report(self, time_range: Tuple[datetime, datetime] = None) -> Dict[str, Any]:
        """生成质量报告"""
        try:
            if not time_range:
                end_time = datetime.now()
                start_time = end_time - timedelta(days=1)
                time_range = (start_time, end_time)

            start_time, end_time = time_range

            # 过滤时间范围内的数据
            filtered_metrics = [
                metrics for metrics in self._quality_history
                if start_time <= metrics.measurement_time <= end_time
            ]

            if not filtered_metrics:
                return {'message': '指定时间范围内无质量数据'}

            # 统计分析
            avg_overall_score = np.mean([m.overall_score for m in filtered_metrics])

            # 按数据源分组统计
            source_stats = {}
            for metrics in filtered_metrics:
                source = metrics.data_source
                if source not in source_stats:
                    source_stats[source] = {
                        'count': 0,
                        'avg_score': 0.0,
                        'issues': []
                    }

                source_stats[source]['count'] += 1
                source_stats[source]['avg_score'] += metrics.overall_score
                source_stats[source]['issues'].extend(metrics.quality_issues)

            # 计算平均分数
            for source, stats in source_stats.items():
                stats['avg_score'] /= stats['count']

            report = {
                'report_period': {
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat()
                },
                'summary': {
                    'total_measurements': len(filtered_metrics),
                    'average_quality_score': avg_overall_score,
                    'data_sources_count': len(source_stats)
                },
                'data_source_analysis': source_stats,
                'quality_distribution': {
                    'excellent': len([m for m in filtered_metrics if m.overall_score >= 0.9]),
                    'good': len([m for m in filtered_metrics if 0.8 <= m.overall_score < 0.9]),
                    'fair': len([m for m in filtered_metrics if 0.7 <= m.overall_score < 0.8]),
                    'poor': len([m for m in filtered_metrics if m.overall_score < 0.7])
                },
                'generated_at': datetime.now().isoformat()
            }

            return report

        except Exception as e:
            logger.error(f"生成质量报告失败: {e}")
            return {'error': f'生成报告失败: {e}'}

    def cleanup(self):
        """清理资源"""
        try:
            self.stop_monitoring()
            with self._lock:
                self._quality_metrics.clear()
                self._anomalies.clear()
                self._quality_history.clear()
            logger.info("增强数据质量监控器资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")

