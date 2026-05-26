#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强版风险监控和预警系统

集成了AI预测、智能化分析和实时监控功能：
1. 智能风险预测和早期预警
2. 多维度风险指标监控
3. 自适应阈值调整
4. 风险传播分析
5. 智能风险控制建议
6. 实时风险仪表板

作者: FactorWeave-Quant团队
版本: 2.0 (增强智能化功能)
"""

import asyncio
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import time

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import joblib

from core.database.unified_sqlite_access import UnifiedSQLiteAccess

try:
    from core.risk_control import RiskMonitor
    from core.risk_alert import RiskAlertSystem
    from core.services.ai_prediction_service import AIPredictionService, PredictionType
    from core.services.enhanced_performance_bridge import EnhancedPerformanceBridge
    CORE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"核心组件不可用: {e}")
    CORE_AVAILABLE = False


class RiskLevel(Enum):
    """风险级别"""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EXTREME = "extreme"


class RiskCategory(Enum):
    """风险类别"""
    MARKET_RISK = "market_risk"
    CREDIT_RISK = "credit_risk"
    LIQUIDITY_RISK = "liquidity_risk"
    OPERATIONAL_RISK = "operational_risk"
    MODEL_RISK = "model_risk"
    CONCENTRATION_RISK = "concentration_risk"
    SYSTEMIC_RISK = "systemic_risk"
    SYSTEM_RISK = "system_risk"


class AlertPriority(Enum):
    """预警优先级"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class RiskMetric:
    """风险指标"""
    name: str
    value: float
    threshold: float
    level: RiskLevel
    category: RiskCategory
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    trend: str = "stable"  # increasing, decreasing, stable
    prediction: Optional[float] = None


@dataclass
class RiskAlert:
    """风险预警"""
    id: str
    title: str
    message: str
    level: RiskLevel
    priority: AlertPriority
    category: RiskCategory
    metrics: List[RiskMetric]
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    resolution_action: Optional[str] = None
    impact_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)


@dataclass
class RiskScenario:
    """风险情景"""
    name: str
    description: str
    probability: float
    impact: float
    risk_score: float
    affected_metrics: List[str]
    mitigation_strategies: List[str]
    timestamp: datetime = field(default_factory=datetime.now)


class EnhancedRiskMonitor:
    """增强版风险监控系统"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

        # 基础组件
        self.risk_monitor = RiskMonitor() if CORE_AVAILABLE else None
        self.alert_system = RiskAlertSystem() if CORE_AVAILABLE else None
        try:
            if CORE_AVAILABLE:
                from core.containers import get_service_container
                container = get_service_container()
                self.ai_service = container.resolve(AIPredictionService)
            else:
                self.ai_service = None
        except Exception:
            self.ai_service = None

        # 智能化组件
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self._anomaly_detector_fitted = False
        self._anomaly_detector_call_count = 0
        self._anomaly_detector_retrain_interval = 50
        self.risk_classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self._scaler_window: List[np.ndarray] = []
        self._scaler_window_size = 100
        self._scaler_retrain_interval = 20
        self._scaler_call_count = 0

        # 数据存储
        self.db_path = Path(self.config.get('db_path', 'data/enhanced_risk_monitor.sqlite'))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

        # 监控状态
        self.is_monitoring = False

        # 预测缓存
        self._prediction_cache = {}  # 预测结果缓存
        self._cache_ttl = 300  # 缓存有效期（秒）
        self.monitoring_thread = None
        self.alert_queue = queue.Queue()

        self._current_positions = []

        self._alert_history = {}
        self._alert_history_lock = threading.Lock()
        self.metrics_history = []
        self.alerts_history = []

        # 自适应阈值
        self.adaptive_thresholds = {}
        self.threshold_update_interval = 3600  # 1小时更新一次阈值
        self.last_threshold_update = datetime.now()

        # 风险模型
        self.risk_models = {}
        self.model_performance = {}

        # 配置参数
        self.monitoring_interval = self.config.get('monitoring_interval', 30)  # 30秒
        self.alert_cooldown = self.config.get('alert_cooldown', 300)  # 5分钟冷却
        self.max_alerts_per_hour = self.config.get('max_alerts_per_hour', 10)

        logger.info("增强版风险监控系统初始化完成")

    def _init_database(self):
        """初始化数据库"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 风险指标表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS risk_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        value REAL NOT NULL,
                        threshold REAL NOT NULL,
                        level TEXT NOT NULL,
                        category TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        trend TEXT DEFAULT 'stable',
                        prediction REAL
                    )
                ''')

                # 风险预警表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS risk_alerts (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        level TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        category TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        resolved BOOLEAN DEFAULT FALSE,
                        resolution_time DATETIME,
                        resolution_action TEXT,
                        impact_score REAL DEFAULT 0.0
                    )
                ''')

                # 风险情景表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS risk_scenarios (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        probability REAL NOT NULL,
                        impact REAL NOT NULL,
                        risk_score REAL NOT NULL,
                        affected_metrics TEXT,
                        mitigation_strategies TEXT,
                        timestamp DATETIME NOT NULL
                    )
                ''')

                # 自适应阈值表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS adaptive_thresholds (
                        metric_name TEXT PRIMARY KEY,
                        threshold_value REAL NOT NULL,
                        confidence_interval REAL NOT NULL,
                        last_updated DATETIME NOT NULL,
                        update_count INTEGER DEFAULT 1
                    )
                ''')

            logger.info("风险监控数据库初始化完成")

        except Exception as e:
            logger.error(f"初始化数据库失败: {e}")

    def start_monitoring(self):
        """启动风险监控"""
        if self.is_monitoring:
            logger.warning("风险监控已在运行")
            return

        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

        logger.info("增强版风险监控已启动")

    def stop_monitoring(self):
        """停止风险监控 - 非阻塞方式"""
        self.is_monitoring = False
        # 不等待线程结束，因为线程是 daemon=True，会自动清理
        # 如果使用 join() 会阻塞主线程，导致UI卡顿
        logger.info("增强版风险监控已停止（非阻塞）")

    def _monitoring_loop(self):
        """监控主循环"""
        while self.is_monitoring:
            try:
                # 收集风险指标
                risk_metrics = self._collect_risk_metrics()

                # 调用 RiskAlertSystem 进行独立的业务风险检查
                if self.alert_system and risk_metrics:
                    try:
                        system_alerts = self.alert_system.check_risk_alerts(risk_metrics)
                        if system_alerts:
                            logger.info(f"RiskAlertSystem 检测到 {len(system_alerts)} 个业务风险预警")
                    except Exception as alert_error:
                        logger.warning(f"RiskAlertSystem 检查失败: {alert_error}")

                # 智能分析风险
                analyzed_metrics = self._analyze_risk_metrics(risk_metrics)

                # 预测风险趋势
                predicted_risks = self._predict_risk_trends(analyzed_metrics)

                # 检测异常
                anomalies = self._detect_risk_anomalies(analyzed_metrics)

                # 生成预警
                alerts = self._generate_intelligent_alerts(
                    analyzed_metrics, predicted_risks, anomalies
                )

                # 更新自适应阈值
                if self._should_update_thresholds():
                    self._update_adaptive_thresholds(analyzed_metrics)

                # 保存数据
                self._save_metrics(analyzed_metrics)
                self._save_alerts(alerts)

                # 处理预警
                for alert in alerts:
                    self.alert_queue.put(alert)

                time.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"风险监控循环出错: {e}")
                time.sleep(self.monitoring_interval)

    def _collect_risk_metrics(self) -> Dict[str, Any]:
        """收集风险指标"""
        try:
            base_metrics = {}

            if self.risk_monitor:
                try:
                    raw_risk_data = self.risk_monitor.get_risk_metrics()
                    if raw_risk_data:
                        base_metrics = {
                            'market_risk': {
                                'volatility': raw_risk_data.get('volatility', 0),
                                'beta': raw_risk_data.get('beta', 0),
                                'var_95': raw_risk_data.get('var_95', 0),
                                'es_95': raw_risk_data.get('es_95', 0)
                            },
                            'liquidity_risk': {
                                'bid_ask_spread': raw_risk_data.get('bid_ask_spread', 0),
                                'turnover_ratio': raw_risk_data.get('turnover_ratio', 0),
                                'market_impact': raw_risk_data.get('market_impact', 0)
                            },
                            'concentration_risk': {
                                'herfindahl_index': raw_risk_data.get('herfindahl_index', 0),
                                'max_position_weight': raw_risk_data.get('max_position_weight', 0),
                                'sector_concentration': raw_risk_data.get('sector_concentration', 0)
                            }
                        }
                    else:
                        logger.warning("risk_monitor.get_risk_metrics() 返回空数据，风险指标不可用")
                except Exception as rm_error:
                    logger.warning(f"从risk_monitor获取风险指标失败: {rm_error}")
            else:
                logger.warning("risk_monitor未初始化，无法获取真实风险指标")

            system_metrics = {}
            try:
                import psutil
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                system_metrics = {
                    'system_risk': {
                        'cpu_usage': round(cpu_percent / 100.0, 4),
                        'memory_usage': round(memory.percent / 100.0, 4),
                        'disk_usage': round(disk.percent / 100.0, 4),
                        'network_latency': 0
                    }
                }
            except ImportError:
                logger.warning("psutil不可用，无法获取系统性能指标")
            except Exception as sys_error:
                logger.warning(f"获取系统性能指标失败: {sys_error}")

            base_metrics.update(system_metrics)
            return base_metrics

        except Exception as e:
            logger.error(f"收集风险指标失败: {e}")
            return {}

    def _analyze_risk_metrics(self, raw_metrics: Dict[str, Any]) -> List[RiskMetric]:
        """分析风险指标"""
        analyzed_metrics = []

        try:
            for category, metrics in raw_metrics.items():
                for metric_name, value in metrics.items():
                    # 获取自适应阈值
                    threshold = self._get_adaptive_threshold(metric_name, value)

                    # 计算风险级别
                    risk_level = self._calculate_risk_level(value, threshold)

                    # 计算趋势
                    trend = self._calculate_trend(metric_name, value)

                    # 计算置信度
                    confidence = self._calculate_confidence(metric_name, value)

                    metric = RiskMetric(
                        name=metric_name,
                        value=value,
                        threshold=threshold,
                        level=risk_level,
                        category=RiskCategory(category.replace('_risk', '_risk')),
                        confidence=confidence,
                        trend=trend
                    )

                    analyzed_metrics.append(metric)

            return analyzed_metrics

        except Exception as e:
            logger.error(f"分析风险指标失败: {e}")
            return []

    def _get_cached_prediction(self, prediction_type: str, cache_key: str):
        """获取缓存的预测结果"""
        import time
        current_time = time.time()

        if cache_key in self._prediction_cache:
            cached_result, timestamp = self._prediction_cache[cache_key]
            if current_time - timestamp < self._cache_ttl:
                return cached_result

        return None

    def _cache_prediction(self, cache_key: str, result):
        """缓存预测结果"""
        import time
        self._prediction_cache[cache_key] = (result, time.time())

    def _predict_risk_trends(self, metrics: List[RiskMetric]) -> Dict[str, float]:
        """预测风险趋势"""
        predictions = {}

        try:
            if not self.ai_service:
                return predictions

            for metric in metrics:
                # 使用AI服务预测未来风险值

                # 生成缓存键
                cache_key = f"risk_forecast_{metric.name}_{metric.value}"

                # 尝试从缓存获取结果
                prediction_result = self._get_cached_prediction("RISK_FORECAST", cache_key)

                if prediction_result is None:
                    # 缓存未命中，进行预测
                    prediction_result = self.ai_service.predict(
                        PredictionType.RISK_FORECAST,
                        {
                            'metric_name': metric.name,
                            'current_value': metric.value,
                            'historical_data': self._get_metric_history(metric.name),
                            'market_conditions': self._get_market_conditions()
                        }
                    )

                    # 缓存结果
                    if prediction_result:
                        self._cache_prediction(cache_key, prediction_result)
                else:
                    # 使用缓存结果
                    pass  # prediction_result already set

                if prediction_result and prediction_result.get('success'):
                    predicted_value = prediction_result.get('predicted_value', metric.value)
                    predictions[metric.name] = predicted_value
                    metric.prediction = predicted_value

            return predictions

        except Exception as e:
            logger.error(f"预测风险趋势失败: {e}")
            return predictions

    def _detect_risk_anomalies(self, metrics: List[RiskMetric]) -> List[RiskMetric]:
        """检测风险异常"""
        anomalies = []

        try:
            if len(metrics) < 2:
                return anomalies

            # 准备数据
            metric_values = np.array([[m.value, m.confidence] for m in metrics])

            # 标准化 - 滚动窗口重新拟合，避免跨调用数据分布不一致
            self._scaler_call_count += 1
            for mv in metric_values:
                self._scaler_window.append(mv.copy())
            if len(self._scaler_window) > self._scaler_window_size:
                self._scaler_window = self._scaler_window[-self._scaler_window_size:]

            if (self._scaler_call_count % self._scaler_retrain_interval == 0
                    and len(self._scaler_window) >= self._scaler_retrain_interval):
                self.scaler.fit(np.array(self._scaler_window))
                normalized_values = self.scaler.transform(metric_values)
            elif hasattr(self.scaler, 'mean_'):
                normalized_values = self.scaler.transform(metric_values)
            else:
                self.scaler.fit(np.array(self._scaler_window))
                normalized_values = self.scaler.transform(metric_values)

            # 异常检测 - 定期重新训练避免检测退化
            self._anomaly_detector_call_count += 1
            if (self._anomaly_detector_call_count % self._anomaly_detector_retrain_interval == 0
                    and len(self._scaler_window) >= 10):
                anomaly_scores = self.anomaly_detector.fit_predict(normalized_values)
                logger.info(f"IsolationForest定期重新训练，调用次数: {self._anomaly_detector_call_count}")
            elif self._anomaly_detector_fitted:
                anomaly_scores = self.anomaly_detector.predict(normalized_values)
            else:
                anomaly_scores = self.anomaly_detector.fit_predict(normalized_values)
                self._anomaly_detector_fitted = True

            # 收集异常指标
            for i, score in enumerate(anomaly_scores):
                if score == -1:  # 异常
                    anomalies.append(metrics[i])

            return anomalies

        except Exception as e:
            logger.error(f"检测风险异常失败: {e}")
            return []

    def _generate_intelligent_alerts(self, metrics: List[RiskMetric],
                                     predictions: Dict[str, float],
                                     anomalies: List[RiskMetric]) -> List[RiskAlert]:
        """生成智能预警"""
        alerts = []

        try:
            # 高风险指标预警
            high_risk_metrics = [m for m in metrics if m.level in [RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.EXTREME]]

            if high_risk_metrics:
                alert = self._create_high_risk_alert(high_risk_metrics)
                if alert:
                    alerts.append(alert)

            # 异常检测预警
            if anomalies:
                alert = self._create_anomaly_alert(anomalies)
                if alert:
                    alerts.append(alert)

            # 趋势预警
            trend_alerts = self._create_trend_alerts(metrics, predictions)
            alerts.extend(trend_alerts)

            # 组合风险预警
            portfolio_alert = self._create_portfolio_risk_alert(metrics)
            if portfolio_alert:
                alerts.append(portfolio_alert)

            return alerts

        except Exception as e:
            logger.error(f"生成智能预警失败: {e}")
            return []

    def _create_high_risk_alert(self, high_risk_metrics: List[RiskMetric]) -> Optional[RiskAlert]:
        """创建高风险预警"""
        try:
            if not high_risk_metrics:
                return None

            # 计算综合风险分数
            risk_score = np.mean([self._metric_to_score(m) for m in high_risk_metrics])

            # 确定预警级别
            if risk_score > 0.9:
                priority = AlertPriority.EMERGENCY
                level = RiskLevel.EXTREME
            elif risk_score > 0.7:
                priority = AlertPriority.CRITICAL
                level = RiskLevel.CRITICAL
            else:
                priority = AlertPriority.WARNING
                level = RiskLevel.HIGH

            # 生成建议
            recommendations = self._generate_risk_recommendations(high_risk_metrics)

            for metric in high_risk_metrics:
                level = self._check_alert_escalation(metric.name, level)

            alert = RiskAlert(
                id=f"high_risk_{int(datetime.now().timestamp())}",
                title="高风险指标预警",
                message=f"检测到 {len(high_risk_metrics)} 个高风险指标，综合风险分数: {risk_score:.2f}",
                level=level,
                priority=priority,
                category=RiskCategory.SYSTEMIC_RISK,
                metrics=high_risk_metrics,
                impact_score=risk_score,
                recommendations=recommendations
            )

            return alert

        except Exception as e:
            logger.error(f"创建高风险预警失败: {e}")
            return None

    def _create_anomaly_alert(self, anomalies: List[RiskMetric]) -> Optional[RiskAlert]:
        """创建异常检测预警"""
        try:
            if not anomalies:
                return None

            alert = RiskAlert(
                id=f"anomaly_{int(datetime.now().timestamp())}",
                title="风险异常检测预警",
                message=f"检测到 {len(anomalies)} 个异常风险指标",
                level=RiskLevel.HIGH,
                priority=AlertPriority.WARNING,
                category=RiskCategory.MODEL_RISK,
                metrics=anomalies,
                impact_score=0.7,
                recommendations=[
                    "立即检查异常指标的数据来源",
                    "验证风险模型的准确性",
                    "考虑调整风险阈值",
                    "加强对异常指标的监控频率"
                ]
            )

            return alert

        except Exception as e:
            logger.error(f"创建异常检测预警失败: {e}")
            return None

    def _create_trend_alerts(self, metrics: List[RiskMetric],
                             predictions: Dict[str, float]) -> List[RiskAlert]:
        """创建趋势预警"""
        alerts = []

        try:
            for metric in metrics:
                if metric.name in predictions:
                    predicted_value = predictions[metric.name]
                    current_value = metric.value

                    # 计算变化幅度
                    change_rate = abs(predicted_value - current_value) / current_value if current_value != 0 else 0

                    # 如果预测变化幅度超过30%，生成预警
                    if change_rate > 0.3:
                        direction = "上升" if predicted_value > current_value else "下降"

                        alert = RiskAlert(
                            id=f"trend_{metric.name}_{int(datetime.now().timestamp())}",
                            title=f"{metric.name}风险趋势预警",
                            message=f"预测{metric.name}将{direction} {change_rate:.1%}",
                            level=RiskLevel.MEDIUM,
                            priority=AlertPriority.WARNING,
                            category=metric.category,
                            metrics=[metric],
                            impact_score=change_rate,
                            recommendations=[
                                f"密切关注{metric.name}的变化",
                                "考虑提前采取风险控制措施",
                                "评估对投资组合的潜在影响"
                            ]
                        )

                        alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"创建趋势预警失败: {e}")
            return []

    def _create_portfolio_risk_alert(self, metrics: List[RiskMetric]) -> Optional[RiskAlert]:
        """创建组合风险预警"""
        try:
            # 计算组合整体风险分数
            total_score = sum(self._metric_to_score(m) for m in metrics)
            avg_score = total_score / len(metrics) if metrics else 0

            # 只有当平均风险分数较高时才生成预警
            if avg_score > 0.6:
                alert = RiskAlert(
                    id=f"portfolio_{int(datetime.now().timestamp())}",
                    title="投资组合整体风险预警",
                    message=f"投资组合整体风险水平较高，平均风险分数: {avg_score:.2f}",
                    level=RiskLevel.HIGH if avg_score > 0.8 else RiskLevel.MEDIUM,
                    priority=AlertPriority.CRITICAL if avg_score > 0.8 else AlertPriority.WARNING,
                    category=RiskCategory.SYSTEMIC_RISK,
                    metrics=metrics,
                    impact_score=avg_score,
                    recommendations=[
                        "考虑降低整体仓位",
                        "增加对冲策略",
                        "重新平衡投资组合",
                        "加强风险监控频率"
                    ]
                )

                return alert

            return None

        except Exception as e:
            logger.error(f"创建组合风险预警失败: {e}")
            return None

    def _get_adaptive_threshold(self, metric_name: str, current_value: float) -> float:
        """获取自适应阈值"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT threshold_value FROM adaptive_thresholds WHERE metric_name = ?",
                    (metric_name,)
                )
                result = cursor.fetchone()

                if result:
                    return result[0]
                else:
                    # 使用默认阈值
                    default_threshold = self._get_default_threshold(metric_name)
                    self._save_adaptive_threshold(metric_name, default_threshold)
                    return default_threshold

        except Exception as e:
            logger.error(f"获取自适应阈值失败: {e}")
            return self._get_default_threshold(metric_name)

    def _get_default_threshold(self, metric_name: str) -> float:
        """获取默认阈值"""
        default_thresholds = {
            'volatility': 0.3,
            'beta': 1.5,
            'var_95': 0.05,
            'es_95': 0.08,
            'bid_ask_spread': 0.005,
            'turnover_ratio': 0.5,
            'market_impact': 0.02,
            'herfindahl_index': 0.3,
            'max_position_weight': 0.2,
            'sector_concentration': 0.5,
            'cpu_usage': 0.8,
            'memory_usage': 0.8,
            'disk_usage': 0.9,
            'network_latency': 100
        }

        return default_thresholds.get(metric_name, 0.5)

    def _calculate_risk_level(self, value: float, threshold: float) -> RiskLevel:
        """计算风险级别"""
        ratio = value / threshold if threshold != 0 else 0

        if ratio >= 2.0:
            return RiskLevel.EXTREME
        elif ratio >= 1.5:
            return RiskLevel.CRITICAL
        elif ratio >= 1.2:
            return RiskLevel.HIGH
        elif ratio >= 1.0:
            return RiskLevel.MEDIUM
        elif ratio >= 0.7:
            return RiskLevel.LOW
        else:
            return RiskLevel.VERY_LOW

    def _calculate_trend(self, metric_name: str, current_value: float) -> str:
        """计算趋势"""
        try:
            history = self._get_metric_history(metric_name, limit=5)
            if len(history) < 2:
                return "stable"

            recent_values = [h['value'] for h in history[-3:]]
            if len(recent_values) < 2:
                return "stable"

            # 简单趋势计算
            if recent_values[-1] > recent_values[0] * 1.1:
                return "increasing"
            elif recent_values[-1] < recent_values[0] * 0.9:
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"计算趋势失败: {e}")
            return "stable"

    def _calculate_confidence(self, metric_name: str, value: float) -> float:
        """计算置信度"""
        try:
            # 基于历史数据的方差计算置信度
            history = self._get_metric_history(metric_name, limit=20)
            if len(history) < 5:
                return 0.8  # 默认置信度

            values = [h['value'] for h in history]
            std_dev = np.std(values)
            mean_val = np.mean(values)

            # 标准化偏差，计算置信度
            if mean_val != 0:
                normalized_std = std_dev / abs(mean_val)
                confidence = max(0.1, 1.0 - normalized_std)
            else:
                confidence = 0.5

            return min(1.0, confidence)

        except Exception as e:
            logger.error(f"计算置信度失败: {e}")
            return 0.8

    def _metric_to_score(self, metric: RiskMetric) -> float:
        """将风险指标转换为分数"""
        level_scores = {
            RiskLevel.VERY_LOW: 0.1,
            RiskLevel.LOW: 0.3,
            RiskLevel.MEDIUM: 0.5,
            RiskLevel.HIGH: 0.7,
            RiskLevel.CRITICAL: 0.9,
            RiskLevel.EXTREME: 1.0
        }

        return level_scores.get(metric.level, 0.5) * metric.confidence


    def _check_alert_escalation(self, metric_name: str, current_level: RiskLevel) -> RiskLevel:
        risk_order = [RiskLevel.VERY_LOW, RiskLevel.LOW, RiskLevel.MEDIUM,
                      RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.EXTREME]
        with self._alert_history_lock:
            history = list(self._alert_history.get(metric_name, []))
        if len(history) >= 3:
            last_three = history[-3:]
            if all(h['level'] == current_level for h in last_three):
                current_idx = risk_order.index(current_level)
                escalated_idx = min(current_idx + 1, len(risk_order) - 1)
                return risk_order[escalated_idx]
        return current_level


    def _generate_risk_recommendations(self, metrics: List[RiskMetric]) -> List[str]:
        """生成风险建议"""
        recommendations = []

        try:
            # 基于风险类别生成建议
            categories = set(m.category for m in metrics)

            for category in categories:
                if category == RiskCategory.MARKET_RISK:
                    recommendations.extend([
                        "考虑增加对冲策略",
                        "降低Beta敞口",
                        "分散投资到不同市场"
                    ])
                elif category == RiskCategory.LIQUIDITY_RISK:
                    recommendations.extend([
                        "增加现金储备",
                        "避免流动性差的资产",
                        "设置流动性缓冲"
                    ])
                elif category == RiskCategory.CONCENTRATION_RISK:
                    recommendations.extend([
                        "增加投资组合分散度",
                        "限制单一资产权重",
                        "平衡行业配置"
                    ])

            # 去重
            recommendations = list(set(recommendations))

            return recommendations[:5]  # 最多返回5个建议

        except Exception as e:
            logger.error(f"生成风险建议失败: {e}")
            return ["建议咨询风险管理专家"]

    def _should_update_thresholds(self) -> bool:
        """判断是否应该更新阈值"""
        return (datetime.now() - self.last_threshold_update).total_seconds() > self.threshold_update_interval

    def _update_adaptive_thresholds(self, metrics: List[RiskMetric]):
        """更新自适应阈值"""
        try:
            for metric in metrics:
                # 获取历史数据
                history = self._get_metric_history(metric.name, limit=100)
                if len(history) < 10:
                    continue

                values = [h['value'] for h in history]

                # 计算新阈值（使用95分位数）
                new_threshold = np.percentile(values, 95)

                # 保存新阈值
                self._save_adaptive_threshold(metric.name, new_threshold)

            self.last_threshold_update = datetime.now()
            logger.info("自适应阈值更新完成")

        except Exception as e:
            logger.error(f"更新自适应阈值失败: {e}")

    def _save_adaptive_threshold(self, metric_name: str, threshold: float):
        """保存自适应阈值"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO adaptive_thresholds 
                    (metric_name, threshold_value, confidence_interval, last_updated, update_count)
                    VALUES (?, ?, ?, ?, 
                        COALESCE((SELECT update_count FROM adaptive_thresholds WHERE metric_name = ?) + 1, 1))
                ''', (metric_name, threshold, 0.95, datetime.now(), metric_name))

        except Exception as e:
            logger.error(f"保存自适应阈值失败: {e}")

    def _get_metric_history(self, metric_name: str, limit: int = 50) -> List[Dict]:
        """获取指标历史数据"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT value, timestamp FROM risk_metrics 
                    WHERE name = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (metric_name, limit))

                results = cursor.fetchall()
                return [{'value': r[0], 'timestamp': r[1]} for r in results]

        except Exception as e:
            logger.error(f"获取指标历史失败: {e}")
            return []

    def _get_market_conditions(self) -> Dict[str, Any]:
        """获取市场条件"""
        logger.warning("市场条件数据不可用，返回空值。请配置市场数据源以获取真实数据。")
        return {
            'market_volatility': None,
            'market_trend': 'unknown',
            'economic_indicators': {
                'gdp_growth': None,
                'inflation_rate': None,
                'interest_rate': None
            }
        }

    def _save_metrics(self, metrics: List[RiskMetric]):
        """保存风险指标"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for metric in metrics:
                    cursor.execute('''
                        INSERT INTO risk_metrics 
                        (name, value, threshold, level, category, timestamp, confidence, trend, prediction)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metric.name, metric.value, metric.threshold, metric.level.value,
                        metric.category.value, metric.timestamp, metric.confidence,
                        metric.trend, metric.prediction
                    ))

        except Exception as e:
            logger.error(f"保存风险指标失败: {e}")

    def _save_alerts(self, alerts: List[RiskAlert]):
        """保存风险预警"""
        try:
            with self._alert_history_lock:
                for alert in alerts:
                    for metric in alert.metrics:
                        history = self._alert_history.get(metric.name, [])
                        history.append({
                            'level': alert.level,
                            'timestamp': alert.timestamp,
                            'metric_value': metric.value
                        })
                        if len(history) > 10:
                            history = history[-10:]
                        self._alert_history[metric.name] = history

            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                for alert in alerts:
                    cursor.execute('''
                        INSERT OR REPLACE INTO risk_alerts 
                        (id, title, message, level, priority, category, timestamp, impact_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        alert.id, alert.title, alert.message, alert.level.value,
                        alert.priority.value, alert.category.value, alert.timestamp,
                        alert.impact_score
                    ))

        except Exception as e:
            logger.error(f"保存风险预警失败: {e}")

    def get_current_risk_status(self) -> Dict[str, Any]:
        """获取当前风险状态"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 获取最新指标
                cursor.execute('''
                    SELECT name, value, level, category, timestamp 
                    FROM risk_metrics 
                    WHERE timestamp > datetime('now', '-1 hour')
                    ORDER BY timestamp DESC
                ''')
                recent_metrics = cursor.fetchall()

                # 获取未解决的预警
                cursor.execute('''
                    SELECT COUNT(*) FROM risk_alerts 
                    WHERE resolved = FALSE AND timestamp > datetime('now', '-24 hours')
                ''')
                active_alerts = cursor.fetchone()[0]

                # 计算风险分布
                risk_distribution = {}
                for metric in recent_metrics:
                    level = metric[2]
                    risk_distribution[level] = risk_distribution.get(level, 0) + 1

                return {
                    'monitoring_status': 'active' if self.is_monitoring else 'inactive',
                    'total_metrics': len(recent_metrics),
                    'active_alerts': active_alerts,
                    'risk_distribution': risk_distribution,
                    'last_update': datetime.now().isoformat(),
                    'adaptive_thresholds_count': len(self.adaptive_thresholds)
                }

        except Exception as e:
            logger.error(f"获取风险状态失败: {e}")
            return {'error': str(e)}

    def get_latest_risk_metrics(self) -> Dict[str, float]:
        """获取最新风险指标数值"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, value FROM risk_metrics
                    WHERE timestamp > datetime('now', '-1 hour')
                    ORDER BY timestamp DESC
                ''')
                metrics = {}
                for row in cursor.fetchall():
                    name = row[0]
                    value = row[1]
                    if name not in metrics:
                        metrics[name] = value
                return metrics
        except Exception as e:
            logger.error(f"获取最新风险指标失败: {e}")
            return {}

    def get_risk_alerts(self, hours: int = 24, resolved: bool = False) -> List[Dict[str, Any]]:
        """获取风险预警"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, title, message, level, priority, category, timestamp, 
                           resolved, impact_score
                    FROM risk_alerts 
                    WHERE timestamp > datetime('now', '-{} hours') AND resolved = ?
                    ORDER BY timestamp DESC
                '''.format(hours), (resolved,))

                results = cursor.fetchall()
                return [{
                    'id': r[0], 'title': r[1], 'message': r[2], 'level': r[3],
                    'priority': r[4], 'category': r[5], 'timestamp': r[6],
                    'resolved': r[7], 'impact_score': r[8]
                } for r in results]

        except Exception as e:
            logger.error(f"获取风险预警失败: {e}")
            return []

    def resolve_alert(self, alert_id: str, resolution_action: str = "") -> bool:
        """解决预警"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE risk_alerts 
                    SET resolved = TRUE, resolution_time = ?, resolution_action = ?
                    WHERE id = ?
                ''', (datetime.now(), resolution_action, alert_id))

                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"解决预警失败: {e}")
            return False

    def get_risk_scenarios(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取风险情景"""
        try:
            db = UnifiedSQLiteAccess.get_instance(str(self.db_path))
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name, description, probability, impact, risk_score, 
                           affected_metrics, mitigation_strategies, timestamp
                    FROM risk_scenarios 
                    ORDER BY risk_score DESC 
                    LIMIT ?
                ''', (limit,))

                results = cursor.fetchall()
                return [{
                    'name': r[0], 'description': r[1], 'probability': r[2],
                    'impact': r[3], 'risk_score': r[4], 'affected_metrics': r[5],
                    'mitigation_strategies': r[6], 'timestamp': r[7]
                } for r in results]

        except Exception as e:
            logger.error(f"获取风险情景失败: {e}")
            return []

    def assess_portfolio_risk(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估投资组合风险

        Args:
            portfolio_data: 投资组合数据，包含portfolio_value和positions

        Returns:
            风险评估结果
        """
        try:
            portfolio_value = portfolio_data.get('portfolio_value', 0)
            positions = portfolio_data.get('positions', [])

            # 计算基本风险指标
            total_position_value = sum(pos['quantity'] * pos['price'] for pos in positions)
            concentration_risk = self._calculate_concentration_risk(positions)
            volatility_risk = self._calculate_volatility_risk(positions)
            liquidity_risk = self._calculate_liquidity_risk(positions)

            # 计算综合风险评分
            risk_score = (concentration_risk * 0.3 + volatility_risk * 0.4 + liquidity_risk * 0.3)

            # 确定风险等级
            if risk_score >= 0.8:
                risk_level = "HIGH"
            elif risk_score >= 0.5:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            return {
                'risk_score': risk_score,
                'risk_level': risk_level,
                'portfolio_value': portfolio_value,
                'total_position_value': total_position_value,
                'concentration_risk': concentration_risk,
                'volatility_risk': volatility_risk,
                'liquidity_risk': liquidity_risk,
                'recommendations': self._generate_portfolio_recommendations(risk_score, positions)
            }

        except Exception as e:
            logger.error(f"投资组合风险评估失败: {e}")
            return {
                'risk_score': 0.5,
                'risk_level': "UNKNOWN",
                'error': str(e)
            }

    def _calculate_concentration_risk(self, positions: List[Dict]) -> float:
        """计算集中度风险"""
        if not positions:
            return 0.0

        total_value = sum(pos['quantity'] * pos['price'] for pos in positions)
        if total_value == 0:
            return 0.0

        # 计算最大持仓比例
        max_position_ratio = max(pos['quantity'] * pos['price'] / total_value for pos in positions)

        # 集中度风险评分（最大持仓比例越高，风险越大）
        return min(max_position_ratio * 2, 1.0)

    def _calculate_volatility_risk(self, positions: List[Dict]) -> float:
        """计算波动性风险（基于价格收益率）"""
        if len(positions) <= 1:
            return 1.0

        prices = []
        for pos in positions:
            if 'price' in pos and 'daily_return' in pos:
                prices.append(pos['daily_return'])
            elif 'price' in pos:
                prices.append(pos['price'])

        if len(prices) <= 1:
            return 1.0

        if any(isinstance(p, (int, float)) and abs(p) < 0.5 for p in prices):
            returns = np.array(prices, dtype=float)
        else:
            price_arr = np.array(prices, dtype=float)
            returns = np.diff(price_arr) / (price_arr[:-1] + 1e-10)
            if len(returns) < 2:
                return 1.0

        volatility = float(np.std(returns, ddof=1))
        return min(volatility / 0.02, 1.0)

    def _calculate_liquidity_risk(self, positions: List[Dict]) -> float:
        """计算流动性风险

        基于持仓数据的流动性风险评估：
        - 优先使用 turnover_ratio 等真实流动性指标
        - 若无真实指标，使用持仓数量作为代理变量（数量越大流动性风险越高）
        - 限制：此简化方法不能完全替代真实的市场流动性数据
        """
        if not positions:
            return 0.0

        for pos in positions:
            if 'turnover_ratio' in pos:
                avg_turnover = np.mean([p.get('turnover_ratio', 0) for p in positions])
                return max(0.0, min(1.0, 1.0 - avg_turnover))

            if 'volume' in pos:
                avg_volume = np.mean([p.get('volume', 0) for p in positions])
                if avg_volume > 0:
                    return max(0.0, min(1.0, 1.0 - avg_volume / 1e8))

        total_quantity = sum(pos['quantity'] for pos in positions)
        avg_quantity = total_quantity / len(positions)
        return min(avg_quantity / 10000, 1.0)

    def _generate_portfolio_recommendations(self, risk_score: float, positions: List[Dict]) -> List[str]:
        """生成投资组合建议"""
        recommendations = []

        if risk_score >= 0.8:
            recommendations.append("风险过高，建议减少高风险持仓")
            recommendations.append("考虑增加防御性资产配置")
        elif risk_score >= 0.5:
            recommendations.append("风险适中，建议定期监控")
            recommendations.append("可考虑适度分散投资")
        else:
            recommendations.append("风险较低，可考虑适度增加收益性资产")

        if len(positions) < 3:
            recommendations.append("建议增加投资品种以分散风险")

        return recommendations

    def check_risk_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查风险规则

        Args:
            data: 要检查的数据

        Returns:
            风险规则检查结果
        """
        try:
            violations = []
            warnings = []

            # 检查投资组合价值规则
            portfolio_value = data.get('portfolio_value', 0)
            if portfolio_value > 10000000:  # 1000万以上高风险
                violations.append({
                    'rule': 'portfolio_value_limit',
                    'message': '投资组合价值过高',
                    'severity': 'HIGH'
                })
            elif portfolio_value > 5000000:  # 500万以上中风险
                warnings.append({
                    'rule': 'portfolio_value_warning',
                    'message': '投资组合价值较高，建议关注',
                    'severity': 'MEDIUM'
                })

            # 检查持仓集中度规则
            positions = data.get('positions', [])
            if positions:
                total_value = sum(pos['quantity'] * pos['price'] for pos in positions)
                if total_value > 0:
                    max_position_ratio = max(pos['quantity'] * pos['price'] / total_value for pos in positions)
                    if max_position_ratio > 0.5:  # 单一持仓超过50%
                        violations.append({
                            'rule': 'concentration_limit',
                            'message': f'单一持仓比例过高: {max_position_ratio:.1%}',
                            'severity': 'HIGH'
                        })
                    elif max_position_ratio > 0.3:  # 单一持仓超过30%
                        warnings.append({
                            'rule': 'concentration_warning',
                            'message': f'单一持仓比例较高: {max_position_ratio:.1%}',
                            'severity': 'MEDIUM'
                        })

            # 检查持仓数量规则
            if len(positions) < 3:
                warnings.append({
                    'rule': 'diversification_warning',
                    'message': '持仓品种过少，建议增加分散投资',
                    'severity': 'LOW'
                })

            return {
                'violations': violations,
                'warnings': warnings,
                'total_violations': len(violations),
                'total_warnings': len(warnings),
                'risk_score': len(violations) * 0.7 + len(warnings) * 0.3,
                'status': 'VIOLATION' if violations else ('WARNING' if warnings else 'PASS')
            }

        except Exception as e:
            logger.error(f"风险规则检查失败: {e}")
            return {
                'violations': [],
                'warnings': [],
                'total_violations': 0,
                'total_warnings': 0,
                'risk_score': 0.0,
                'status': 'ERROR',
                'error': str(e)
            }


    def check_order_risk(self, order) -> Dict[str, Any]:
        """
        检查订单风险

        Args:
            order: 订单对象（Order dataclass 或 dict）

        Returns:
            Dict with keys: passed (bool), risk_level (str), violations (list),
            warnings (list), error_code (str)
        """
        try:
            violations = []
            warnings = []

            if isinstance(order, dict):
                stock_code = order.get('stock_code', order.get('symbol', ''))
                price = order.get('order_price', order.get('price', 0))
                quantity = order.get('order_quantity', order.get('quantity', 0))
            else:
                stock_code = getattr(order, 'stock_code', getattr(order, 'symbol', ''))
                price = getattr(order, 'order_price', getattr(order, 'price', 0))
                quantity = getattr(order, 'order_quantity', getattr(order, 'quantity', 0))

            if not stock_code:
                violations.append({
                    'rule': 'missing_stock_code',
                    'message': '订单缺少股票代码',
                    'severity': 'HIGH'
                })

            if price <= 0:
                violations.append({
                    'rule': 'invalid_price',
                    'message': '订单价格无效: {}'.format(price),
                    'severity': 'HIGH'
                })

            if quantity <= 0:
                violations.append({
                    'rule': 'invalid_quantity',
                    'message': '订单数量无效: {}'.format(quantity),
                    'severity': 'HIGH'
                })

            if stock_code and quantity > 0 and price > 0:
                order_value = price * quantity
                current_positions = self._current_positions or []
                total_current_value = sum(
                    p.get('quantity', 0) * p.get('price', 0)
                    for p in current_positions
                )

                if total_current_value > 0:
                    new_position_value = order_value
                    for p in current_positions:
                        pos_code = p.get('stock_code', p.get('symbol', ''))
                        if pos_code == stock_code:
                            new_position_value = p.get('quantity', 0) * p.get('price', 0) + order_value
                            break

                    total_after = total_current_value + order_value
                    concentration_ratio = new_position_value / total_after if total_after > 0 else 1.0

                    MAX_CONCENTRATION = self.config.get('max_concentration', 0.5)
                    CONCENTRATION_WARN = self.config.get('concentration_warn', 0.3)

                    if concentration_ratio > MAX_CONCENTRATION:
                        violations.append({
                            'rule': 'concentration_limit',
                            'message': '单一持仓集中度过高: {:.1%}'.format(concentration_ratio),
                            'severity': 'HIGH'
                        })
                    elif concentration_ratio > CONCENTRATION_WARN:
                        warnings.append({
                            'rule': 'concentration_warning',
                            'message': '单一持仓集中度较高: {:.1%}'.format(concentration_ratio),
                            'severity': 'MEDIUM'
                        })

                MAX_SINGLE_ORDER_VALUE = self.config.get('max_single_order_value', 10_000_000)
                ORDER_VALUE_WARN = self.config.get('order_value_warn', 5_000_000)

                if order_value > MAX_SINGLE_ORDER_VALUE:
                    violations.append({
                        'rule': 'order_value_limit',
                        'message': '单笔交易金额过大: {:.2f}'.format(order_value),
                        'severity': 'HIGH'
                    })
                elif order_value > ORDER_VALUE_WARN:
                    warnings.append({
                        'rule': 'order_value_warning',
                        'message': '单笔交易金额较大: {:.2f}'.format(order_value),
                        'severity': 'MEDIUM'
                    })

            if violations:
                risk_level = 'HIGH'
            elif warnings:
                risk_level = 'MEDIUM'
            else:
                risk_level = 'LOW'

            return {
                'passed': len(violations) == 0,
                'risk_level': risk_level,
                'violations': violations,
                'warnings': warnings,
                'error_code': ''
            }

        except Exception as e:
            logger.critical("增强版风控检查异常，订单被拒绝: {}".format(e))
            return {
                'passed': False,
                'risk_level': 'CRITICAL',
                'violations': [{'rule': 'internal_error', 'message': str(e), 'severity': 'CRITICAL'}],
                'warnings': [],
                'error_code': 'ENHANCED_RISK_CHECK_FAILED'
            }

    def update_portfolio_positions(self, positions: list) -> None:
        self._current_positions = positions


    def cleanup(self):
        """清理资源"""
        try:
            self.stop_monitoring()
            logger.info("增强版风险监控系统清理完成")
        except Exception as e:
            logger.error(f"清理风险监控系统失败: {e}")


# 全局实例
_enhanced_risk_monitor = None


def get_enhanced_risk_monitor(config: Optional[Dict] = None) -> EnhancedRiskMonitor:
    """获取增强版风险监控实例"""
    global _enhanced_risk_monitor
    if _enhanced_risk_monitor is None:
        _enhanced_risk_monitor = EnhancedRiskMonitor(config)
    return _enhanced_risk_monitor


if __name__ == "__main__":
    # 测试代码
    monitor = get_enhanced_risk_monitor()
    monitor.start_monitoring()

    try:
        time.sleep(60)  # 运行1分钟
        status = monitor.get_current_risk_status()
        print(f"风险状态: {json.dumps(status, indent=2, ensure_ascii=False)}")

        alerts = monitor.get_risk_alerts()
        print(f"预警数量: {len(alerts)}")

    finally:
        monitor.cleanup()
