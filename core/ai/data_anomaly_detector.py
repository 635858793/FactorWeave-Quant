#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据异常检测和自动修复系统

实现高级的数据异常检测和自动修复功能：
1. 多维度异常检测算法
2. 智能异常分类和严重程度评估
3. 自动修复策略和机制
4. 异常模式学习和预测
5. 数据质量监控和报告
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
from pathlib import Path
from loguru import logger
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
import warnings
from ..database.unified_sqlite_access import UnifiedSQLiteAccess
warnings.filterwarnings('ignore')

class AnomalyType(Enum):
    """异常类型"""
    MISSING_DATA = "missing_data"           # 数据缺失
    OUTLIER = "outlier"                     # 异常值
    DUPLICATE = "duplicate"                 # 重复数据
    INCONSISTENT = "inconsistent"           # 数据不一致
    FORMAT_ERROR = "format_error"           # 格式错误
    TEMPORAL_ANOMALY = "temporal_anomaly"   # 时间异常
    STATISTICAL_ANOMALY = "statistical_anomaly"  # 统计异常
    PATTERN_BREAK = "pattern_break"         # 模式中断
    CORRELATION_ANOMALY = "correlation_anomaly"  # 相关性异常
    VOLUME_ANOMALY = "volume_anomaly"       # 数据量异常

class AnomalySeverity(Enum):
    """异常严重程度"""
    LOW = "low"           # 低
    MEDIUM = "medium"     # 中等
    HIGH = "high"         # 高
    CRITICAL = "critical" # 严重

class RepairAction(Enum):
    """修复动作"""
    INTERPOLATE = "interpolate"         # 插值
    REMOVE = "remove"                   # 删除
    REPLACE = "replace"                 # 替换
    CORRECT = "correct"                 # 纠正
    IGNORE = "ignore"                   # 忽略
    MANUAL_REVIEW = "manual_review"     # 人工审核
    ROLLBACK = "rollback"               # 回滚
    ALERT_ONLY = "alert_only"           # 仅告警

@dataclass
class AnomalyDetectionConfig:
    """异常检测配置"""
    enable_outlier_detection: bool = True
    enable_missing_data_detection: bool = True
    enable_duplicate_detection: bool = True
    enable_temporal_detection: bool = True
    enable_pattern_detection: bool = True
    
    outlier_threshold: float = 0.1          # 异常值阈值
    missing_threshold: float = 0.05         # 缺失数据阈值
    duplicate_threshold: float = 0.02       # 重复数据阈值
    pattern_sensitivity: float = 0.8        # 模式敏感度
    
    auto_repair_enabled: bool = True        # 启用自动修复
    max_repair_attempts: int = 3            # 最大修复尝试次数
    repair_confidence_threshold: float = 0.8  # 修复置信度阈值
    
    learning_enabled: bool = True           # 启用学习
    model_update_interval: int = 3600       # 模型更新间隔（秒）
    history_retention_days: int = 30        # 历史记录保留天数

@dataclass
class AnomalyRecord:
    """异常记录"""
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    description: str
    data_source: str
    symbol: str
    data_type: str
    affected_fields: List[str]
    anomaly_score: float
    detection_time: datetime
    raw_data: Dict[str, Any]
    context_data: Dict[str, Any] = field(default_factory=dict)
    repair_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    repair_history: List[Dict[str, Any]] = field(default_factory=list)
    is_resolved: bool = False
    resolution_time: Optional[datetime] = None

@dataclass
class RepairSuggestion:
    """修复建议"""
    suggestion_id: str
    action: RepairAction
    confidence: float
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    risk_level: str = "low"
    estimated_time: float = 0.0  # 预计修复时间（秒）

@dataclass
class RepairResult:
    """修复结果"""
    repair_id: str
    anomaly_id: str
    action_taken: RepairAction
    success: bool
    description: str
    before_data: Dict[str, Any]
    after_data: Dict[str, Any]
    repair_time: datetime
    confidence: float
    side_effects: List[str] = field(default_factory=list)

class DataAnomalyDetector:
    """
    数据异常检测和自动修复系统
    
    提供全面的数据质量监控、异常检测和自动修复功能
    """

    def __init__(self, config: Optional[AnomalyDetectionConfig] = None, db_path: str = "data/factorweave_system.sqlite"):
        self.config = config or AnomalyDetectionConfig()
        self.db_path = db_path
        
        self.outlier_detectors: Dict[str, Any] = {}
        self.pattern_models: Dict[str, Any] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.anomaly_records: Dict[str, AnomalyRecord] = {}
        self.detection_statistics: Dict[str, List[float]] = {
            'detection_rates': [],
            'false_positive_rates': [],
            'repair_success_rates': [],
            'processing_times': []
        }
        self.pattern_history: Dict[str, List[Dict[str, Any]]] = {}
        self.repair_feedback: Dict[str, List[Dict[str, Any]]] = {}
        
        self.detection_lock = threading.RLock()
        self.repair_lock = threading.RLock()
        self.learning_lock = threading.RLock()
        
        self._init_database()
        self._load_models()
        self._load_historical_data()
        
        logger.info("数据异常检测和自动修复系统初始化完成")

    def _get_db(self) -> UnifiedSQLiteAccess:
        return UnifiedSQLiteAccess.get_instance(self.db_path)

    def _init_database(self):
        """初始化数据库表"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 异常记录表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS anomaly_records (
                        anomaly_id TEXT PRIMARY KEY,
                        anomaly_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        description TEXT NOT NULL,
                        data_source TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        affected_fields TEXT NOT NULL,
                        anomaly_score REAL NOT NULL,
                        detection_time TEXT NOT NULL,
                        raw_data TEXT NOT NULL,
                        context_data TEXT,
                        is_resolved BOOLEAN DEFAULT FALSE,
                        resolution_time TEXT,
                        created_at TEXT NOT NULL
                    )
                """)
                
                # 修复记录表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS repair_records (
                        repair_id TEXT PRIMARY KEY,
                        anomaly_id TEXT NOT NULL,
                        action_taken TEXT NOT NULL,
                        success BOOLEAN NOT NULL,
                        description TEXT NOT NULL,
                        before_data TEXT NOT NULL,
                        after_data TEXT NOT NULL,
                        repair_time TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        side_effects TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (anomaly_id) REFERENCES anomaly_records (anomaly_id)
                    )
                """)
                
                # 检测模型表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS detection_models (
                        model_id TEXT PRIMARY KEY,
                        model_type TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        model_data BLOB NOT NULL,
                        performance_metrics TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                # 模式历史表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pattern_history (
                        pattern_id TEXT PRIMARY KEY,
                        data_source TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        data_type TEXT NOT NULL,
                        pattern_data TEXT NOT NULL,
                        frequency_score REAL NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                
                logger.info("异常检测数据库表初始化完成")
                
        except Exception as e:
            logger.error(f"初始化数据库表失败: {e}")

    def _load_models(self):
        """加载检测模型"""
        try:
            # 初始化默认的异常检测模型
            default_models = ['historical_kline_data', 'index_kline', 'fund_nav', 'realtime_quote']
            
            for model_type in default_models:
                # 异常值检测器（带降级保护）
                try:
                    self.outlier_detectors[model_type] = IsolationForest(
                    contamination=self.config.outlier_threshold,
                    random_state=42,
                        n_estimators=100
                    )
                except Exception as init_err:
                    logger.warning(f"初始化 {model_type} 异常检测器失败: {init_err}")
                    self.outlier_detectors[model_type] = None
                
                # 数据标准化器
                self.scalers[model_type] = StandardScaler()
                
                # 模式检测器（DBSCAN聚类）
                try:
                    self.pattern_models[model_type] = DBSCAN(
                    eps=0.5,
                    min_samples=5
                    )
                except Exception as init_err:
                    logger.warning(f"初始化 {model_type} 模式检测器失败: {init_err}")
                    self.pattern_models[model_type] = None
            
            logger.info(f"加载检测模型: {len(self.outlier_detectors)}个")
            
        except Exception as e:
            logger.error(f"加载检测模型失败: {e}")

    def _load_historical_data(self):
        """加载历史数据"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # 加载异常记录
                cursor.execute("""
                    SELECT anomaly_id, anomaly_type, severity, description, data_source, 
                           symbol, data_type, affected_fields, anomaly_score, detection_time,
                           raw_data, context_data, is_resolved, resolution_time
                    FROM anomaly_records
                    WHERE detection_time >= datetime('now', '-30 days')
                    ORDER BY detection_time DESC
                """)
                
                for row in cursor.fetchall():
                    try:
                        anomaly_record = AnomalyRecord(
                            anomaly_id=row[0],
                            anomaly_type=AnomalyType(row[1]),
                            severity=AnomalySeverity(row[2]),
                            description=row[3],
                            data_source=row[4],
                            symbol=row[5],
                            data_type=row[6],
                            affected_fields=json.loads(row[7]),
                            anomaly_score=row[8],
                            detection_time=datetime.fromisoformat(row[9]),
                            raw_data=json.loads(row[10]),
                            context_data=json.loads(row[11]) if row[11] else {},
                            is_resolved=row[12],
                            resolution_time=datetime.fromisoformat(row[13]) if row[13] else None
                        )
                        self.anomaly_records[row[0]] = anomaly_record
                    except Exception as e:
                        logger.warning(f"加载异常记录失败 {row[0]}: {e}")
                
                logger.info(f"加载历史异常记录: {len(self.anomaly_records)}条")
                
        except Exception as e:
            logger.error(f"加载历史数据失败: {e}")

    def detect_anomalies(self, data: pd.DataFrame, data_source: str, symbol: str, data_type: str) -> List[AnomalyRecord]:
        """
        检测数据异常
        
        Args:
            data: 待检测的数据
            data_source: 数据源
            symbol: 标的代码
            data_type: 数据类型
            
        Returns:
            检测到的异常记录列表
        """
        try:
            with self.detection_lock:
                start_time = datetime.now()
                detected_anomalies = []
                
                if data.empty:
                    return detected_anomalies
                
                # 数据缺失检测
                if self.config.enable_missing_data_detection:
                    missing_anomalies = self._detect_missing_data(data, data_source, symbol, data_type)
                    detected_anomalies.extend(missing_anomalies)
                
                # 重复数据检测
                if self.config.enable_duplicate_detection:
                    duplicate_anomalies = self._detect_duplicates(data, data_source, symbol, data_type)
                    detected_anomalies.extend(duplicate_anomalies)
                
                # 异常值检测
                if self.config.enable_outlier_detection:
                    outlier_anomalies = self._detect_outliers(data, data_source, symbol, data_type)
                    detected_anomalies.extend(outlier_anomalies)
                
                # 时间序列异常检测
                if self.config.enable_temporal_detection:
                    temporal_anomalies = self._detect_temporal_anomalies(data, data_source, symbol, data_type)
                    detected_anomalies.extend(temporal_anomalies)
                
                # 模式异常检测
                if self.config.enable_pattern_detection:
                    pattern_anomalies = self._detect_pattern_anomalies(data, data_source, symbol, data_type)
                    detected_anomalies.extend(pattern_anomalies)
                
                # 保存检测结果
                for anomaly in detected_anomalies:
                    self.anomaly_records[anomaly.anomaly_id] = anomaly
                    self._save_anomaly_record(anomaly)
                
                # 记录检测统计
                detection_time = (datetime.now() - start_time).total_seconds()
                self.detection_statistics['processing_times'].append(detection_time)
                self.detection_statistics['detection_rates'].append(len(detected_anomalies) / len(data))
                
                # 保持统计数据在合理范围内
                for key in self.detection_statistics:
                    if len(self.detection_statistics[key]) > 1000:
                        self.detection_statistics[key] = self.detection_statistics[key][-1000:]
                
                if detected_anomalies:
                    logger.info(f"检测到异常: {len(detected_anomalies)}个 ({data_source}/{symbol}/{data_type})")
                
                return detected_anomalies
                
        except Exception as e:
            logger.error(f"异常检测失败: {e}")
            return []

    def _detect_missing_data(self, data: pd.DataFrame, data_source: str, symbol: str, data_type: str) -> List[AnomalyRecord]:
        """检测数据缺失"""
        try:
            anomalies = []
            
            for column in data.columns:
                missing_ratio = data[column].isnull().sum() / len(data)
                
                if missing_ratio > self.config.missing_threshold:
                    anomaly_id = f"missing_{data_source}_{symbol}_{column}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    severity = AnomalySeverity.CRITICAL if missing_ratio > 0.5 else \
                              AnomalySeverity.HIGH if missing_ratio > 0.2 else \
                              AnomalySeverity.MEDIUM
                    
                    anomaly = AnomalyRecord(
                        anomaly_id=anomaly_id,
                        anomaly_type=AnomalyType.MISSING_DATA,
                        severity=severity,
                        description=f"字段 {column} 缺失率过高: {missing_ratio:.2%}",
                        data_source=data_source,
                        symbol=symbol,
                        data_type=data_type,
                        affected_fields=[column],
                        anomaly_score=missing_ratio,
                        detection_time=datetime.now(),
                        raw_data={
                            'column': column,
                            'missing_count': int(data[column].isnull().sum()),
                            'total_count': len(data),
                            'missing_ratio': missing_ratio
                        }
                    )
                    
                    # 生成修复建议
                    anomaly.repair_suggestions = self._generate_missing_data_repair_suggestions(data, column, missing_ratio)
                    anomalies.append(anomaly)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"检测数据缺失失败: {e}")
            return []

    def _detect_duplicates(self, data: pd.DataFrame, data_source: str, symbol: str, data_type: str) -> List[AnomalyRecord]:
        """检测重复数据"""
        try:
            anomalies = []
            
            # 检测完全重复的行
            duplicate_rows = data.duplicated()
            duplicate_ratio = duplicate_rows.sum() / len(data)
            
            if duplicate_ratio > self.config.duplicate_threshold:
                anomaly_id = f"duplicate_{data_source}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                
                severity = AnomalySeverity.HIGH if duplicate_ratio > 0.1 else \
                          AnomalySeverity.MEDIUM if duplicate_ratio > 0.05 else \
                          AnomalySeverity.LOW
                
                anomaly = AnomalyRecord(
                    anomaly_id=anomaly_id,
                    anomaly_type=AnomalyType.DUPLICATE,
                    severity=severity,
                    description=f"重复数据比例过高: {duplicate_ratio:.2%}",
                    data_source=data_source,
                    symbol=symbol,
                    data_type=data_type,
                    affected_fields=list(data.columns),
                    anomaly_score=duplicate_ratio,
                    detection_time=datetime.now(),
                    raw_data={
                        'duplicate_count': int(duplicate_rows.sum()),
                        'total_count': len(data),
                        'duplicate_ratio': duplicate_ratio,
                        'duplicate_indices': duplicate_rows[duplicate_rows].index.tolist()
                    }
                )
                
                # 生成修复建议
                anomaly.repair_suggestions = self._generate_duplicate_repair_suggestions(data, duplicate_rows)
                anomalies.append(anomaly)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"检测重复数据失败: {e}")
            return []

    def _detect_outliers(self, data: pd.DataFrame, data_source: str, symbol: str, data_type: str) -> List[AnomalyRecord]:
        """检测异常值"""
        try:
            anomalies = []
            
            # 选择数值列进行异常值检测
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            if len(numeric_columns) == 0:
                return anomalies
            
            # 准备数据
            numeric_data = data[numeric_columns].fillna(data[numeric_columns].median())
            
            # 获取或创建模型
            model_key = f"{data_source}_{data_type}"
            if model_key not in self.outlier_detectors:
                self.outlier_detectors[model_key] = IsolationForest(
                    contamination=self.config.outlier_threshold,
                    random_state=42
                )
                self.scalers[model_key] = StandardScaler()
            
            # 标准化数据
            scaled_data = self.scalers[model_key].fit_transform(numeric_data)
            
            # 检测异常值
            outlier_labels = self.outlier_detectors[model_key].fit_predict(scaled_data)
            outlier_scores = self.outlier_detectors[model_key].decision_function(scaled_data)
            
            # 找出异常值
            outlier_indices = np.where(outlier_labels == -1)[0]
            
            if len(outlier_indices) > 0:
                outlier_ratio = len(outlier_indices) / len(data)
                
                if outlier_ratio > self.config.outlier_threshold:
                    anomaly_id = f"outlier_{data_source}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    severity = AnomalySeverity.HIGH if outlier_ratio > 0.2 else \
                              AnomalySeverity.MEDIUM if outlier_ratio > 0.1 else \
                              AnomalySeverity.LOW
                    
                    anomaly = AnomalyRecord(
                        anomaly_id=anomaly_id,
                        anomaly_type=AnomalyType.OUTLIER,
                        severity=severity,
                        description=f"异常值比例过高: {outlier_ratio:.2%}",
                        data_source=data_source,
                        symbol=symbol,
                        data_type=data_type,
                        affected_fields=list(numeric_columns),
                        anomaly_score=outlier_ratio,
                        detection_time=datetime.now(),
                        raw_data={
                            'outlier_count': len(outlier_indices),
                            'total_count': len(data),
                            'outlier_ratio': outlier_ratio,
                            'outlier_indices': outlier_indices.tolist(),
                            'outlier_scores': outlier_scores[outlier_indices].tolist()
                        }
                    )
                    
                    # 生成修复建议
                    anomaly.repair_suggestions = self._generate_outlier_repair_suggestions(data, outlier_indices, outlier_scores)
                    anomalies.append(anomaly)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"检测异常值失败: {e}")
            return []

    def _detect_temporal_anomalies(self, data: pd.DataFrame, data_source: str, symbol: str, data_type: str) -> List[AnomalyRecord]:
        """检测时间序列异常"""
        try:
            anomalies = []
            
            # 检查是否有时间列
            time_columns = []
            for col in data.columns:
                if 'time' in col.lower() or 'date' in col.lower() or data[col].dtype == 'datetime64[ns]':
                    time_columns.append(col)
            
            if not time_columns:
                return anomalies
            
            for time_col in time_columns:
                try:
                    # 转换为datetime
                    if data[time_col].dtype != 'datetime64[ns]':
                        time_series = pd.to_datetime(data[time_col])
                    else:
                        time_series = data[time_col]
                    
                    # 检测时间间隔异常
                    time_diffs = time_series.diff().dropna()
                    
                    if len(time_diffs) > 1:
                        # 计算标准时间间隔
                        median_interval = time_diffs.median()
                        std_interval = time_diffs.std()
                        
                        # 检测异常间隔
                        anomalous_intervals = time_diffs[
                            (time_diffs > median_interval + 3 * std_interval) |
                            (time_diffs < median_interval - 3 * std_interval)
                        ]
                        
                        if len(anomalous_intervals) > 0:
                            anomaly_ratio = len(anomalous_intervals) / len(time_diffs)
                            
                            if anomaly_ratio > 0.05:  # 超过5%的时间间隔异常
                                anomaly_id = f"temporal_{data_source}_{symbol}_{time_col}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                                
                                severity = AnomalySeverity.HIGH if anomaly_ratio > 0.2 else \
                                          AnomalySeverity.MEDIUM if anomaly_ratio > 0.1 else \
                                          AnomalySeverity.LOW
                                
                                anomaly = AnomalyRecord(
                                    anomaly_id=anomaly_id,
                                    anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                                    severity=severity,
                                    description=f"时间序列 {time_col} 间隔异常: {anomaly_ratio:.2%}",
                                    data_source=data_source,
                                    symbol=symbol,
                                    data_type=data_type,
                                    affected_fields=[time_col],
                                    anomaly_score=anomaly_ratio,
                                    detection_time=datetime.now(),
                                    raw_data={
                                        'time_column': time_col,
                                        'anomalous_intervals_count': len(anomalous_intervals),
                                        'total_intervals': len(time_diffs),
                                        'anomaly_ratio': anomaly_ratio,
                                        'median_interval_seconds': median_interval.total_seconds(),
                                        'std_interval_seconds': std_interval.total_seconds()
                                    }
                                )
                                
                                # 生成修复建议
                                anomaly.repair_suggestions = self._generate_temporal_repair_suggestions(time_series, anomalous_intervals)
                                anomalies.append(anomaly)
                
                except Exception as e:
                    logger.warning(f"检测时间列 {time_col} 异常失败: {e}")
            
            return anomalies
            
        except Exception as e:
            logger.error(f"检测时间序列异常失败: {e}")
            return []

    def _detect_pattern_anomalies(self, data: pd.DataFrame, data_source: str, symbol: str, data_type: str) -> List[AnomalyRecord]:
        """检测模式异常"""
        try:
            anomalies = []
            
            # 选择数值列进行模式检测
            numeric_columns = data.select_dtypes(include=[np.number]).columns
            
            if len(numeric_columns) < 2:
                return anomalies
            
            # 准备数据
            numeric_data = data[numeric_columns].fillna(data[numeric_columns].median())
            
            # 获取或创建模型
            model_key = f"{data_source}_{data_type}"
            if model_key not in self.pattern_models:
                self.pattern_models[model_key] = DBSCAN(eps=0.5, min_samples=5)
            
            # 标准化数据
            if model_key not in self.scalers:
                self.scalers[model_key] = StandardScaler()
            
            scaled_data = self.scalers[model_key].fit_transform(numeric_data)
            
            # 聚类分析
            cluster_labels = self.pattern_models[model_key].fit_predict(scaled_data)
            
            # 检测噪声点（异常模式）
            noise_points = np.where(cluster_labels == -1)[0]
            
            if len(noise_points) > 0:
                noise_ratio = len(noise_points) / len(data)
                
                if noise_ratio > 0.1:  # 超过10%的噪声点
                    anomaly_id = f"pattern_{data_source}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    severity = AnomalySeverity.HIGH if noise_ratio > 0.3 else \
                              AnomalySeverity.MEDIUM if noise_ratio > 0.2 else \
                              AnomalySeverity.LOW
                    
                    anomaly = AnomalyRecord(
                        anomaly_id=anomaly_id,
                        anomaly_type=AnomalyType.PATTERN_BREAK,
                        severity=severity,
                        description=f"模式异常点比例过高: {noise_ratio:.2%}",
                        data_source=data_source,
                        symbol=symbol,
                        data_type=data_type,
                        affected_fields=list(numeric_columns),
                        anomaly_score=noise_ratio,
                        detection_time=datetime.now(),
                        raw_data={
                            'noise_points_count': len(noise_points),
                            'total_points': len(data),
                            'noise_ratio': noise_ratio,
                            'noise_indices': noise_points.tolist(),
                            'cluster_count': len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
                        }
                    )
                    
                    # 生成修复建议
                    anomaly.repair_suggestions = self._generate_pattern_repair_suggestions(data, noise_points, cluster_labels)
                    anomalies.append(anomaly)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"检测模式异常失败: {e}")
            return []

    def _generate_missing_data_repair_suggestions(self, data: pd.DataFrame, column: str, missing_ratio: float) -> List[RepairSuggestion]:
        """生成数据缺失修复建议"""
        suggestions = []
        
        try:
            if missing_ratio < 0.1:
                # 少量缺失，建议插值
                suggestions.append(RepairSuggestion(
                    suggestion_id=f"interpolate_{column}",
                    action=RepairAction.INTERPOLATE,
                    confidence=0.9,
                    description=f"对字段 {column} 进行插值填充",
                    parameters={'method': 'linear', 'limit': 5},
                    expected_outcome="填充缺失值，保持数据连续性",
                    risk_level="low",
                    estimated_time=1.0
                ))
            elif missing_ratio < 0.3:
                # 中等缺失，建议多种方法
                suggestions.extend([
                    RepairSuggestion(
                        suggestion_id=f"interpolate_advanced_{column}",
                        action=RepairAction.INTERPOLATE,
                        confidence=0.7,
                        description=f"对字段 {column} 进行高级插值填充",
                        parameters={'method': 'spline', 'order': 2},
                        expected_outcome="使用样条插值填充缺失值",
                        risk_level="medium",
                        estimated_time=2.0
                    ),
                    RepairSuggestion(
                        suggestion_id=f"replace_median_{column}",
                        action=RepairAction.REPLACE,
                        confidence=0.6,
                        description=f"用中位数替换字段 {column} 的缺失值",
                        parameters={'value': data[column].median()},
                        expected_outcome="用统计值填充缺失值",
                        risk_level="medium",
                        estimated_time=0.5
                    )
                ])
            else:
                # 大量缺失，建议人工审核
                suggestions.append(RepairSuggestion(
                    suggestion_id=f"manual_review_{column}",
                    action=RepairAction.MANUAL_REVIEW,
                    confidence=0.9,
                    description=f"字段 {column} 缺失率过高，需要人工审核",
                    parameters={'missing_ratio': missing_ratio},
                    expected_outcome="人工确定处理策略",
                    risk_level="high",
                    estimated_time=300.0
                ))
            
        except Exception as e:
            logger.error(f"生成缺失数据修复建议失败: {e}")
        
        return suggestions

    def _generate_duplicate_repair_suggestions(self, data: pd.DataFrame, duplicate_mask: pd.Series) -> List[RepairSuggestion]:
        """生成重复数据修复建议"""
        suggestions = []
        
        try:
            duplicate_count = duplicate_mask.sum()
            
            suggestions.extend([
                RepairSuggestion(
                    suggestion_id="remove_duplicates",
                    action=RepairAction.REMOVE,
                    confidence=0.95,
                    description=f"删除 {duplicate_count} 条重复记录",
                    parameters={'keep': 'first'},
                    expected_outcome="保留第一条记录，删除后续重复记录",
                    risk_level="low",
                    estimated_time=0.5
                ),
                RepairSuggestion(
                    suggestion_id="review_duplicates",
                    action=RepairAction.MANUAL_REVIEW,
                    confidence=0.8,
                    description="人工审核重复记录的处理方式",
                    parameters={'duplicate_indices': duplicate_mask[duplicate_mask].index.tolist()},
                    expected_outcome="确认重复记录的处理策略",
                    risk_level="low",
                    estimated_time=60.0
                )
            ])
            
        except Exception as e:
            logger.error(f"生成重复数据修复建议失败: {e}")
        
        return suggestions

    def _generate_outlier_repair_suggestions(self, data: pd.DataFrame, outlier_indices: np.ndarray, outlier_scores: np.ndarray) -> List[RepairSuggestion]:
        """生成异常值修复建议"""
        suggestions = []
        
        try:
            # 根据异常程度生成不同建议
            severe_outliers = outlier_indices[outlier_scores < -0.5]
            mild_outliers = outlier_indices[outlier_scores >= -0.5]
            
            if len(severe_outliers) > 0:
                suggestions.append(RepairSuggestion(
                    suggestion_id="remove_severe_outliers",
                    action=RepairAction.REMOVE,
                    confidence=0.8,
                    description=f"删除 {len(severe_outliers)} 个严重异常值",
                    parameters={'indices': severe_outliers.tolist()},
                    expected_outcome="删除明显的异常数据点",
                    risk_level="medium",
                    estimated_time=1.0
                ))
            
            if len(mild_outliers) > 0:
                suggestions.extend([
                    RepairSuggestion(
                        suggestion_id="cap_mild_outliers",
                        action=RepairAction.CORRECT,
                        confidence=0.7,
                        description=f"对 {len(mild_outliers)} 个轻微异常值进行截断处理",
                        parameters={'method': 'winsorize', 'limits': (0.05, 0.05)},
                        expected_outcome="将异常值调整到合理范围",
                        risk_level="low",
                        estimated_time=1.5
                    ),
                    RepairSuggestion(
                        suggestion_id="review_mild_outliers",
                        action=RepairAction.MANUAL_REVIEW,
                        confidence=0.9,
                        description="人工审核轻微异常值",
                        parameters={'indices': mild_outliers.tolist()},
                        expected_outcome="确认异常值的处理方式",
                        risk_level="low",
                        estimated_time=120.0
                    )
                ])
            
        except Exception as e:
            logger.error(f"生成异常值修复建议失败: {e}")
        
        return suggestions

    def _generate_temporal_repair_suggestions(self, time_series: pd.Series, anomalous_intervals: pd.Series) -> List[RepairSuggestion]:
        """生成时间异常修复建议"""
        suggestions = []
        
        try:
            suggestions.extend([
                RepairSuggestion(
                    suggestion_id="interpolate_time_gaps",
                    action=RepairAction.INTERPOLATE,
                    confidence=0.8,
                    description="对时间间隔异常进行插值修复",
                    parameters={'method': 'time_interpolation'},
                    expected_outcome="填补时间序列中的异常间隔",
                    risk_level="medium",
                    estimated_time=3.0
                ),
                RepairSuggestion(
                    suggestion_id="alert_time_anomaly",
                    action=RepairAction.ALERT_ONLY,
                    confidence=0.95,
                    description="仅对时间异常进行告警，不自动修复",
                    parameters={'anomaly_count': len(anomalous_intervals)},
                    expected_outcome="通知相关人员关注时间序列异常",
                    risk_level="low",
                    estimated_time=0.1
                )
            ])
            
        except Exception as e:
            logger.error(f"生成时间异常修复建议失败: {e}")
        
        return suggestions

    def _generate_pattern_repair_suggestions(self, data: pd.DataFrame, noise_indices: np.ndarray, cluster_labels: np.ndarray) -> List[RepairSuggestion]:
        """生成模式异常修复建议"""
        suggestions = []
        
        try:
            suggestions.extend([
                RepairSuggestion(
                    suggestion_id="isolate_pattern_anomalies",
                    action=RepairAction.MANUAL_REVIEW,
                    confidence=0.9,
                    description=f"隔离 {len(noise_indices)} 个模式异常点进行审核",
                    parameters={'noise_indices': noise_indices.tolist()},
                    expected_outcome="人工确认模式异常的处理方式",
                    risk_level="medium",
                    estimated_time=180.0
                ),
                RepairSuggestion(
                    suggestion_id="alert_pattern_break",
                    action=RepairAction.ALERT_ONLY,
                    confidence=0.95,
                    description="对模式中断进行告警",
                    parameters={'cluster_count': len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)},
                    expected_outcome="通知相关人员关注数据模式变化",
                    risk_level="low",
                    estimated_time=0.1
                )
            ])
            
        except Exception as e:
            logger.error(f"生成模式异常修复建议失败: {e}")
        
        return suggestions

    def auto_repair_anomaly(self, anomaly_id: str) -> Optional[RepairResult]:
        """
        自动修复异常
        
        Args:
            anomaly_id: 异常ID
            
        Returns:
            修复结果
        """
        try:
            if not self.config.auto_repair_enabled:
                logger.info("自动修复功能未启用")
                return None
                
            if anomaly_id not in self.anomaly_records:
                logger.error(f"异常记录不存在: {anomaly_id}")
                return None
            
            with self.repair_lock:
                anomaly = self.anomaly_records[anomaly_id]
                
                if anomaly.is_resolved:
                    logger.info(f"异常已解决: {anomaly_id}")
                    return None
                
                # 选择最佳修复建议
                best_suggestion = self._select_best_repair_suggestion(anomaly)
                
                if not best_suggestion:
                    logger.warning(f"没有找到合适的修复建议: {anomaly_id}")
                    return None
                
                if best_suggestion.confidence < self.config.repair_confidence_threshold:
                    logger.info(f"修复置信度不足: {best_suggestion.confidence} < {self.config.repair_confidence_threshold}")
                    return None
                
                # 执行修复
                repair_result = self._execute_repair(anomaly, best_suggestion)
                
                if repair_result and repair_result.success:
                    # 更新异常状态
                    anomaly.is_resolved = True
                    anomaly.resolution_time = datetime.now()
                    anomaly.repair_history.append({
                        'repair_id': repair_result.repair_id,
                        'action': repair_result.action_taken.value,
                        'success': repair_result.success,
                        'timestamp': repair_result.repair_time.isoformat()
                    })
                    
                    # 保存修复结果
                    self._save_repair_result(repair_result)
                    self._update_anomaly_record(anomaly)
                    
                    logger.info(f"异常修复成功: {anomaly_id}")
                
                return repair_result
                
        except Exception as e:
            logger.error(f"自动修复异常失败: {e}")
            return None

    def _select_best_repair_suggestion(self, anomaly: AnomalyRecord) -> Optional[RepairSuggestion]:
        """选择最佳修复建议"""
        try:
            if not anomaly.repair_suggestions:
                return None
            
            # 过滤掉需要人工审核的建议（自动修复时）
            auto_suggestions = [s for s in anomaly.repair_suggestions 
                              if s.action not in [RepairAction.MANUAL_REVIEW, RepairAction.ALERT_ONLY]]
            
            if not auto_suggestions:
                return None
            
            # 按置信度和风险等级排序
            def suggestion_score(suggestion: RepairSuggestion) -> float:
                confidence_score = suggestion.confidence
                risk_penalty = {'low': 0, 'medium': 0.1, 'high': 0.3}.get(suggestion.risk_level, 0.2)
                time_penalty = min(suggestion.estimated_time / 300.0, 0.2)  # 5分钟以上有时间惩罚
                
                return confidence_score - risk_penalty - time_penalty
            
            best_suggestion = max(auto_suggestions, key=suggestion_score)
            return best_suggestion
            
        except Exception as e:
            logger.error(f"选择最佳修复建议失败: {e}")
            return None

    def _execute_repair(self, anomaly: AnomalyRecord, suggestion: RepairSuggestion) -> Optional[RepairResult]:
        """执行修复操作"""
        try:
            repair_id = f"repair_{anomaly.anomaly_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            start_time = datetime.now()
            
            # 备份原始数据
            before_data = anomaly.raw_data.copy()
            
            # 根据修复动作执行相应操作
            success = False
            after_data = {}
            side_effects = []
            
            if suggestion.action == RepairAction.INTERPOLATE:
                success, after_data, side_effects = self._perform_interpolation(anomaly, suggestion)
            elif suggestion.action == RepairAction.REMOVE:
                success, after_data, side_effects = self._perform_removal(anomaly, suggestion)
            elif suggestion.action == RepairAction.REPLACE:
                success, after_data, side_effects = self._perform_replacement(anomaly, suggestion)
            elif suggestion.action == RepairAction.CORRECT:
                success, after_data, side_effects = self._perform_correction(anomaly, suggestion)
            elif suggestion.action == RepairAction.IGNORE:
                success = True
                after_data = before_data
                side_effects = ["异常被标记为忽略"]
            else:
                logger.warning(f"不支持的修复动作: {suggestion.action}")
                return None
            
            repair_result = RepairResult(
                repair_id=repair_id,
                anomaly_id=anomaly.anomaly_id,
                action_taken=suggestion.action,
                success=success,
                description=f"执行修复动作: {suggestion.description}",
                before_data=before_data,
                after_data=after_data,
                repair_time=datetime.now(),
                confidence=suggestion.confidence,
                side_effects=side_effects
            )
            
            # 记录修复统计
            self.detection_statistics['repair_success_rates'].append(1.0 if success else 0.0)
            
            return repair_result
            
        except Exception as e:
            logger.error(f"执行修复操作失败: {e}")
            return None

    def _perform_interpolation(self, anomaly: AnomalyRecord, suggestion: RepairSuggestion) -> Tuple[bool, Dict[str, Any], List[str]]:
        """执行插值修复"""
        try:
            method = suggestion.parameters.get('method', 'linear')
            limit = suggestion.parameters.get('limit', None)
            order = suggestion.parameters.get('order', 1)
            raw_data = anomaly.raw_data
            context_data = anomaly.context_data
            side_effects = []

            if 'data_series' in context_data and context_data['data_series'] is not None:
                series_data = context_data['data_series']
            elif 'column_values' in context_data and context_data['column_values'] is not None:
                series_data = context_data['column_values']
            elif raw_data.get('outlier_indices') is not None:
                series_data = None
            elif raw_data.get('missing_count', 0) > 0:
                series_data = None
            else:
                series_data = None

            if series_data is not None and isinstance(series_data, (list, np.ndarray)):
                series = pd.Series(series_data, dtype=float)

                if 'missing_indices' in raw_data:
                    missing_idx = raw_data['missing_indices']
                    for idx in missing_idx:
                        if 0 <= idx < len(series):
                            series.iloc[idx] = np.nan

                if 'outlier_indices' in raw_data:
                    outlier_idx = raw_data['outlier_indices']
                    for idx in outlier_idx:
                        if 0 <= idx < len(series):
                            series.iloc[idx] = np.nan

                if method == 'linear':
                    interpolated = series.interpolate(method='linear', limit=limit, limit_direction='both')
                elif method == 'spline':
                    interpolated = series.interpolate(method='spline', order=min(order, 5), limit=limit, limit_direction='both')
                elif method == 'time_interpolation':
                    interpolated = series.interpolate(method='time', limit=limit, limit_direction='both')
                elif method in ('polynomial', 'quadratic', 'cubic'):
                    poly_order = {'polynomial': 2, 'quadratic': 2, 'cubic': 3}.get(method, 2)
                    interpolated = series.interpolate(method='polynomial', order=poly_order, limit=limit, limit_direction='both')
                elif method in ('akima', 'pchip', 'barycentric', 'krogh'):
                    interpolated = series.interpolate(method=method, limit=limit, limit_direction='both')
                else:
                    interpolated = series.interpolate(method='linear', limit=limit, limit_direction='both')
                    side_effects.append(f"不支持的插值方法 '{method}'，回退为 linear")

                still_nan = interpolated.isna().sum()
                if still_nan > 0:
                    interpolated = interpolated.fillna(method='ffill').fillna(method='bfill')
                    side_effects.append(f"边界处仍有 {still_nan} 个缺失值，使用前后向填充补齐")

                filled_count = int(series.isna().sum() - interpolated.isna().sum()) if series.isna().any() else 0
                after_data = {
                    'original_series': series.tolist(),
                    'interpolated_series': interpolated.tolist(),
                    'filled_count': max(filled_count, 0),
                    'method': method,
                    'anomaly_id': anomaly.anomaly_id
                }
                logger.info(
                    f"插值修复成功，异常ID: {anomaly.anomaly_id}, "
                    f"方法: {method}, 填充点数: {max(filled_count, 0)}"
                )
                return True, after_data, side_effects

            if 'column' in raw_data and 'missing_count' in raw_data:
                column = raw_data['column']
                missing_count = raw_data['missing_count']
                total_count = raw_data.get('total_count', 0)

                after_data = {
                    'column': column,
                    'method': method,
                    'message': f"对字段 '{column}' 计划使用 {method} 插值填充 {missing_count}/{total_count} 个缺失值",
                    'estimated_fill_count': missing_count
                }
                side_effects.append("插值标记已记录，实际插值将在下次数据加载时执行")
                logger.info(
                    f"插值修复标记成功（延迟执行），异常ID: {anomaly.anomaly_id}, "
                    f"字段: {column}, 方法: {method}"
                )
                return True, after_data, side_effects

            after_data = {
                'method': method,
                'message': '插值标记已生成，等待数据源提供完整序列后执行'
            }
            side_effects.append("无可用序列数据，插值操作仅记录标记")
            logger.warning(
                f"插值修复未能找到可用序列数据，仅生成标记。"
                f"异常ID: {anomaly.anomaly_id}"
            )
            return True, after_data, side_effects

        except Exception as e:
            logger.error(f"执行插值修复失败: {e}")
            return False, {}, [f"插值修复执行异常: {str(e)}"]

    def _perform_removal(self, anomaly: AnomalyRecord, suggestion: RepairSuggestion) -> Tuple[bool, Dict[str, Any], List[str]]:
        """执行删除修复"""
        logger.warning(
            f"删除修复需要真实数据源支持，当前无法执行。"
            f"异常ID: {anomaly.anomaly_id}, 建议删除数量: {len(suggestion.parameters.get('indices', []))}"
        )
        # TODO: 实现删除修复
        # 1. 从 suggestion.parameters 获取待删除的 indices 列表
        # 2. 对 data_series 中对应索引的行/值标记为删除
        # 3. 检查删除后数据集的统计特性是否保持稳定
        # 4. 返回 (success, after_data, side_effects)
        return False, {}, ["删除修复需要真实数据源支持，当前数据不足无法执行"]

    def _perform_replacement(self, anomaly: AnomalyRecord, suggestion: RepairSuggestion) -> Tuple[bool, Dict[str, Any], List[str]]:
        """执行替换修复"""
        logger.warning(
            f"替换修复需要真实数据源支持，当前无法执行。"
            f"异常ID: {anomaly.anomaly_id}"
        )
        # TODO: 实现替换修复
        # 1. 从 suggestion.parameters 获取替换值（如中位数、均值等统计值）
        # 2. 在 context_data 或 raw_data 中定位异常索引位置
        # 3. 用统计值替换异常点，保留替换记录到 after_data
        # 4. 返回 (success, after_data, side_effects)
        return False, {}, ["替换修复需要真实数据源支持，当前数据不足无法执行"]

    def _perform_correction(self, anomaly: AnomalyRecord, suggestion: RepairSuggestion) -> Tuple[bool, Dict[str, Any], List[str]]:
        """执行纠正修复"""
        logger.warning(
            f"纠正修复需要真实数据源支持，当前无法执行。"
            f"异常ID: {anomaly.anomaly_id}, 方法: {suggestion.parameters.get('method', 'winsorize')}"
        )
        # TODO: 实现纠正修复
        # 1. 从 suggestion.parameters 读取纠正方法（winsorize/clip/zscore等）
        # 2. winsorize: 将超出分位数边界的值截断到边界值
        # 3. clip: 按参数指定的上下界截断所有异常值
        # 4. zscore: 基于z-score识别并替换异常值
        # 5. 返回 (success, after_data, side_effects)
        return False, {}, ["纠正修复需要真实数据源支持，当前数据不足无法执行"]

    def _save_anomaly_record(self, anomaly: AnomalyRecord):
        """保存异常记录"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO anomaly_records
                    (anomaly_id, anomaly_type, severity, description, data_source, symbol, data_type,
                     affected_fields, anomaly_score, detection_time, raw_data, context_data,
                     is_resolved, resolution_time, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    anomaly.anomaly_id,
                    anomaly.anomaly_type.value,
                    anomaly.severity.value,
                    anomaly.description,
                    anomaly.data_source,
                    anomaly.symbol,
                    anomaly.data_type,
                    json.dumps(anomaly.affected_fields),
                    anomaly.anomaly_score,
                    anomaly.detection_time.isoformat(),
                    json.dumps(anomaly.raw_data),
                    json.dumps(anomaly.context_data),
                    anomaly.is_resolved,
                    anomaly.resolution_time.isoformat() if anomaly.resolution_time else None,
                    datetime.now().isoformat()
                ))
        except Exception as e:
            logger.error(f"保存异常记录失败: {e}")

    def _save_repair_result(self, repair_result: RepairResult):
        """保存修复结果"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO repair_records
                    (repair_id, anomaly_id, action_taken, success, description, before_data,
                     after_data, repair_time, confidence, side_effects, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    repair_result.repair_id,
                    repair_result.anomaly_id,
                    repair_result.action_taken.value,
                    repair_result.success,
                    repair_result.description,
                    json.dumps(repair_result.before_data),
                    json.dumps(repair_result.after_data),
                    repair_result.repair_time.isoformat(),
                    repair_result.confidence,
                    json.dumps(repair_result.side_effects),
                    datetime.now().isoformat()
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存修复结果失败: {e}")

    def _update_anomaly_record(self, anomaly: AnomalyRecord):
        """更新异常记录"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE anomaly_records 
                    SET is_resolved = ?, resolution_time = ?
                    WHERE anomaly_id = ?
                """, (
                    anomaly.is_resolved,
                    anomaly.resolution_time.isoformat() if anomaly.resolution_time else None,
                    anomaly.anomaly_id
                ))
        except Exception as e:
            logger.error(f"更新异常记录失败: {e}")

    def get_anomaly_statistics(self) -> Dict[str, Any]:
        """获取异常统计信息"""
        try:
            stats = {
                'total_anomalies': len(self.anomaly_records),
                'resolved_anomalies': sum(1 for a in self.anomaly_records.values() if a.is_resolved),
                'anomaly_types': {},
                'severity_distribution': {},
                'detection_performance': {},
                'repair_performance': {}
            }
            
            # 按类型统计
            for anomaly in self.anomaly_records.values():
                anomaly_type = anomaly.anomaly_type.value
                severity = anomaly.severity.value
                
                stats['anomaly_types'][anomaly_type] = stats['anomaly_types'].get(anomaly_type, 0) + 1
                stats['severity_distribution'][severity] = stats['severity_distribution'].get(severity, 0) + 1
            
            # 检测性能统计
            if self.detection_statistics['detection_rates']:
                stats['detection_performance'] = {
                    'avg_detection_rate': np.mean(self.detection_statistics['detection_rates']),
                    'avg_processing_time': np.mean(self.detection_statistics['processing_times']),
                    'total_detections': len(self.detection_statistics['detection_rates'])
                }
            
            # 修复性能统计
            if self.detection_statistics['repair_success_rates']:
                stats['repair_performance'] = {
                    'repair_success_rate': np.mean(self.detection_statistics['repair_success_rates']),
                    'total_repairs': len(self.detection_statistics['repair_success_rates'])
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"获取异常统计信息失败: {e}")
            return {}

    def get_recent_anomalies(self, hours: int = 24, limit: int = 100) -> List[AnomalyRecord]:
        """获取最近的异常记录"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_anomalies = [
                anomaly for anomaly in self.anomaly_records.values()
                if anomaly.detection_time >= cutoff_time
            ]
            
            # 按检测时间排序
            recent_anomalies.sort(key=lambda x: x.detection_time, reverse=True)
            
            return recent_anomalies[:limit]
            
        except Exception as e:
            logger.error(f"获取最近异常记录失败: {e}")
            return []

    def cleanup_old_records(self, days: int = None):
        """清理旧记录"""
        try:
            days = days or self.config.history_retention_days
            cutoff_time = datetime.now() - timedelta(days=days)
            
            old_anomaly_ids = [
                anomaly_id for anomaly_id, anomaly in self.anomaly_records.items()
                if anomaly.detection_time < cutoff_time
            ]
            
            for anomaly_id in old_anomaly_ids:
                del self.anomaly_records[anomaly_id]
            
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM anomaly_records 
                    WHERE detection_time < ?
                """, (cutoff_time.isoformat(),))
                
                cursor.execute("""
                    DELETE FROM repair_records 
                    WHERE repair_time < ?
                """, (cutoff_time.isoformat(),))
                
                conn.commit()
            
            logger.info(f"清理旧记录完成: 删除 {len(old_anomaly_ids)} 条异常记录")
            
        except Exception as e:
            logger.error(f"清理旧记录失败: {e}")

def main():
    """测试数据异常检测和自动修复系统"""
    # 创建检测器
    detector = DataAnomalyDetector()
    
    # 创建测试数据
    np.random.seed(42)
    
    # 正常数据
    normal_data = pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='D'),
        'price': 100 + np.random.normal(0, 5, 100),
        'volume': 1000 + np.random.normal(0, 100, 100),
        'high': 105 + np.random.normal(0, 3, 100),
        'low': 95 + np.random.normal(0, 3, 100)
    })
    
    # 注入异常
    # 缺失数据
    normal_data.loc[10:15, 'price'] = np.nan
    
    # 异常值
    normal_data.loc[20, 'price'] = 200  # 明显异常值
    normal_data.loc[21, 'volume'] = 5000  # 异常交易量
    
    # 重复数据
    normal_data.loc[30] = normal_data.loc[29]
    normal_data.loc[31] = normal_data.loc[29]
    
    logger.info("=== 开始异常检测测试 ===")
    
    # 检测异常
    anomalies = detector.detect_anomalies(
        data=normal_data,
        data_source="test_source",
        symbol="TEST001",
        data_type="kline"
    )
    
    logger.info(f"检测到异常数量: {len(anomalies)}")
    
    # 显示检测结果
    for anomaly in anomalies:
        logger.info(f"异常类型: {anomaly.anomaly_type.value}")
        logger.info(f"严重程度: {anomaly.severity.value}")
        logger.info(f"描述: {anomaly.description}")
        logger.info(f"异常分数: {anomaly.anomaly_score:.3f}")
        logger.info(f"修复建议数量: {len(anomaly.repair_suggestions)}")
        
        # 显示修复建议
        for suggestion in anomaly.repair_suggestions:
            logger.info(f"  建议: {suggestion.description} (置信度: {suggestion.confidence:.2f})")
        
        logger.info("---")
    
    # 测试自动修复
    logger.info("\n=== 开始自动修复测试 ===")
    
    for anomaly in anomalies[:3]:  # 只修复前3个异常
        repair_result = detector.auto_repair_anomaly(anomaly.anomaly_id)
        
        if repair_result:
            logger.info(f"修复结果: {repair_result.description}")
            logger.info(f"修复成功: {repair_result.success}")
            logger.info(f"修复动作: {repair_result.action_taken.value}")
            logger.info(f"副作用: {repair_result.side_effects}")
        else:
            logger.info(f"异常 {anomaly.anomaly_id} 未能自动修复")
        
        logger.info("---")
    
    # 获取统计信息
    logger.info("\n=== 异常检测统计 ===")
    stats = detector.get_anomaly_statistics()
    
    logger.info(f"总异常数: {stats['total_anomalies']}")
    logger.info(f"已解决异常数: {stats['resolved_anomalies']}")
    logger.info(f"异常类型分布: {stats['anomaly_types']}")
    logger.info(f"严重程度分布: {stats['severity_distribution']}")
    
    if stats['detection_performance']:
        perf = stats['detection_performance']
        logger.info(f"平均检测率: {perf['avg_detection_rate']:.3f}")
        logger.info(f"平均处理时间: {perf['avg_processing_time']:.3f}秒")
    
    if stats['repair_performance']:
        repair_perf = stats['repair_performance']
        logger.info(f"修复成功率: {repair_perf['repair_success_rate']:.3f}")
    
    # 获取最近异常
    recent_anomalies = detector.get_recent_anomalies(hours=1)
    logger.info(f"\n最近1小时异常数量: {len(recent_anomalies)}")

if __name__ == "__main__":
    main()
