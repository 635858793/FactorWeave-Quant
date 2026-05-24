"""
数据质量监控器

实现专业级的数据质量监控和验证，确保交易系统中数据的
完整性、准确性、时效性和一致性。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-17
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import statistics
from collections import deque

from loguru import logger

class QualityLevel(Enum):
    """数据质量等级"""
    EXCELLENT = "excellent"  # 优秀 (>= 0.95)
    GOOD = "good"           # 良好 (>= 0.85) 
    FAIR = "fair"           # 一般 (>= 0.70)
    POOR = "poor"           # 较差 (>= 0.50)
    CRITICAL = "critical"   # 严重 (< 0.50)

class QualityMetric(Enum):
    """质量指标类型"""
    COMPLETENESS = "completeness"    # 完整性
    ACCURACY = "accuracy"            # 准确性
    TIMELINESS = "timeliness"        # 时效性
    CONSISTENCY = "consistency"      # 一致性
    VALIDITY = "validity"            # 有效性
    UNIQUENESS = "uniqueness"        # 唯一性

@dataclass
class QualityIssue:
    """质量问题"""
    metric: QualityMetric
    severity: str  # "critical", "high", "medium", "low"
    description: str
    value: float
    threshold: float
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class QualityReport:
    """数据质量报告"""
    overall_score: float
    quality_level: QualityLevel
    metrics: Dict[str, float]
    issues: List[QualityIssue]
    recommendations: List[str]
    data_info: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "overall_score": self.overall_score,
            "quality_level": self.quality_level.value,
            "metrics": self.metrics,
            "issues": [
                {
                    "metric": issue.metric.value,
                    "severity": issue.severity,
                    "description": issue.description,
                    "value": issue.value,
                    "threshold": issue.threshold,
                    "recommendation": issue.recommendation,
                    "timestamp": issue.timestamp.isoformat()
                }
                for issue in self.issues
            ],
            "recommendations": self.recommendations,
            "data_info": self.data_info,
            "timestamp": self.timestamp.isoformat()
        }

class DataQualityThresholds:
    """数据质量阈值配置"""
    
    def __init__(self):
        # 完整性阈值
        self.completeness_excellent = 0.98
        self.completeness_good = 0.90
        self.completeness_fair = 0.75
        self.completeness_critical = 0.50
        
        # 准确性阈值
        self.accuracy_excellent = 0.99
        self.accuracy_good = 0.95
        self.accuracy_fair = 0.85
        self.accuracy_critical = 0.70
        
        # 时效性阈值（秒）
        self.timeliness_excellent = 30
        self.timeliness_good = 120
        self.timeliness_fair = 300
        self.timeliness_critical = 600
        
        # 一致性阈值
        self.consistency_excellent = 0.95
        self.consistency_good = 0.85
        self.consistency_fair = 0.70
        self.consistency_critical = 0.50
        
        # 异常值检测阈值
        self.outlier_ratio_threshold = 0.05  # 5%异常值
        self.price_change_threshold = 0.20   # 20%价格变化
        self.volume_spike_threshold = 5.0    # 5倍成交量激增

class DataQualityMonitor:
    """
    数据质量监控器
    
    提供全面的数据质量评估和监控功能
    """
    
    def __init__(self, thresholds: DataQualityThresholds = None):
        """
        初始化数据质量监控器
        
        Args:
            thresholds: 质量阈值配置
        """
        self.thresholds = thresholds or DataQualityThresholds()
        self.logger = logger.bind(module="DataQualityMonitor")
        
        # 历史质量记录
        self.quality_history: Dict[str, deque] = {}
        self.max_history_size = 1000
        
        # 质量统计
        self.quality_stats = {
            "total_evaluations": 0,
            "excellent_count": 0,
            "good_count": 0,
            "fair_count": 0,
            "poor_count": 0,
            "critical_count": 0
        }
        
        self.logger.info("数据质量监控器初始化完成")
    
    def evaluate_data_quality(self, data: Any, data_type: str = "unknown", 
                            context: Dict[str, Any] = None) -> QualityReport:
        """
        评估数据质量
        
        Args:
            data: 要评估的数据
            data_type: 数据类型
            context: 额外上下文信息
            
        Returns:
            QualityReport: 质量评估报告
        """
        try:
            context = context or {}
            
            if isinstance(data, pd.DataFrame):
                return self._evaluate_dataframe_quality(data, data_type, context)
            elif isinstance(data, list):
                return self._evaluate_list_quality(data, data_type, context)
            elif isinstance(data, dict):
                return self._evaluate_dict_quality(data, data_type, context)
            else:
                return self._evaluate_generic_quality(data, data_type, context)
                
        except Exception as e:
            self.logger.error(f"数据质量评估失败: {e}")
            return self._create_error_report(str(e), data_type)
    
    def _evaluate_dataframe_quality(self, df: pd.DataFrame, data_type: str, 
                                   context: Dict[str, Any]) -> QualityReport:
        """评估DataFrame数据质量"""
        metrics = {}
        issues = []
        recommendations = []
        
        # 基本信息
        data_info = {
            "type": "DataFrame",
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": df.dtypes.to_dict(),
            "memory_usage": df.memory_usage(deep=True).sum(),
            "data_type": data_type
        }
        
        if df.empty:
            return QualityReport(
                overall_score=0.0,
                quality_level=QualityLevel.CRITICAL,
                metrics={"completeness": 0.0},
                issues=[QualityIssue(
                    QualityMetric.COMPLETENESS, "critical",
                    "DataFrame为空", 0.0, 0.5,
                    "检查数据源连接和查询条件"
                )],
                recommendations=["检查数据源连接", "验证查询参数"],
                data_info=data_info
            )
        
        # 1. 完整性评估
        completeness_score = self._assess_completeness(df)
        metrics["completeness"] = completeness_score
        
        if completeness_score < self.thresholds.completeness_critical:
            issues.append(QualityIssue(
                QualityMetric.COMPLETENESS, "critical",
                f"数据完整性严重不足: {completeness_score:.2%}",
                completeness_score, self.thresholds.completeness_critical,
                "检查数据源质量，考虑更换数据提供商"
            ))
        elif completeness_score < self.thresholds.completeness_fair:
            issues.append(QualityIssue(
                QualityMetric.COMPLETENESS, "high",
                f"数据完整性较低: {completeness_score:.2%}",
                completeness_score, self.thresholds.completeness_fair,
                "增加数据清洗和补全机制"
            ))
        
        # 2. 准确性评估
        accuracy_score = self._assess_accuracy(df, data_type)
        metrics["accuracy"] = accuracy_score
        
        if accuracy_score < self.thresholds.accuracy_critical:
            issues.append(QualityIssue(
                QualityMetric.ACCURACY, "critical",
                f"数据准确性存在严重问题: {accuracy_score:.2%}",
                accuracy_score, self.thresholds.accuracy_critical,
                "立即检查数据来源和处理逻辑"
            ))
        
        # 3. 一致性评估
        consistency_score = self._assess_consistency(df, data_type)
        metrics["consistency"] = consistency_score
        
        if consistency_score < self.thresholds.consistency_critical:
            issues.append(QualityIssue(
                QualityMetric.CONSISTENCY, "high",
                f"数据一致性问题: {consistency_score:.2%}",
                consistency_score, self.thresholds.consistency_critical,
                "检查数据格式和字段映射"
            ))
        
        # 4. 时效性评估
        timeliness_score = self._assess_timeliness(df, context)
        metrics["timeliness"] = timeliness_score
        
        # 5. 有效性评估
        validity_score = self._assess_validity(df, data_type)
        metrics["validity"] = validity_score
        
        # 6. 异常检测
        anomaly_score = self._detect_anomalies(df, data_type)
        metrics["anomaly_score"] = anomaly_score
        
        if anomaly_score > self.thresholds.outlier_ratio_threshold:
            issues.append(QualityIssue(
                QualityMetric.VALIDITY, "medium",
                f"检测到异常数据: {anomaly_score:.2%}",
                anomaly_score, self.thresholds.outlier_ratio_threshold,
                "进行异常值处理和数据清洗"
            ))
        
        # 计算综合评分
        overall_score = self._calculate_overall_score(metrics)
        quality_level = self._determine_quality_level(overall_score)
        
        # 生成建议
        recommendations = self._generate_recommendations(metrics, issues, data_type)
        
        # 更新统计
        self._update_quality_stats(quality_level)
        
        report = QualityReport(
            overall_score=overall_score,
            quality_level=quality_level,
            metrics=metrics,
            issues=issues,
            recommendations=recommendations,
            data_info=data_info
        )
        
        # 记录历史
        self._record_quality_history(data_type, report)
        
        return report
    
    def _assess_completeness(self, df: pd.DataFrame) -> float:
        """评估数据完整性"""
        if df.empty:
            return 0.0
        
        total_cells = df.shape[0] * df.shape[1]
        non_null_cells = df.count().sum()
        
        return non_null_cells / total_cells if total_cells > 0 else 0.0
    
    def _assess_accuracy(self, df: pd.DataFrame, data_type: str) -> float:
        """评估数据准确性"""
        accuracy_score = 1.0
        
        try:
            # 根据数据类型进行特定的准确性检查
            if data_type.lower() in ["kline", "ohlc", "kdata"]:
                accuracy_score = self._assess_kline_accuracy(df)
            elif data_type.lower() in ["quote", "real_time"]:
                accuracy_score = self._assess_quote_accuracy(df)
            else:
                # 通用准确性检查
                accuracy_score = self._assess_generic_accuracy(df)
                
        except Exception as e:
            self.logger.warning(f"准确性评估失败: {e}")
            accuracy_score = 0.8  # 默认分数
        
        return accuracy_score
    
    def _assess_kline_accuracy(self, df: pd.DataFrame) -> float:
        """评估K线数据准确性"""
        accuracy_issues = 0
        total_checks = 0
        
        # 检查必需字段
        required_fields = ['open', 'high', 'low', 'close']
        available_fields = [col for col in required_fields if col in df.columns]
        
        if len(available_fields) < len(required_fields):
            return 0.5  # 缺少必需字段
        
        total_checks = len(df)

        nan_mask = df[available_fields].isna().any(axis=1)
        accuracy_issues += nan_mask.sum()

        valid_mask = ~nan_mask
        if valid_mask.any():
            max_oc = df.loc[valid_mask, ['open', 'close']].max(axis=1)
            min_oc = df.loc[valid_mask, ['open', 'close']].min(axis=1)
            ohlc_issue = (df.loc[valid_mask, 'high'] < max_oc) | (df.loc[valid_mask, 'low'] > min_oc)
            accuracy_issues += ohlc_issue.sum()

            neg_price = (df.loc[valid_mask, available_fields] < 0).any(axis=1)
            accuracy_issues += neg_price.sum()

        return 1.0 - (accuracy_issues / total_checks) if total_checks > 0 else 1.0
    
    def _assess_quote_accuracy(self, df: pd.DataFrame) -> float:
        """评估行情数据准确性"""
        accuracy_issues = 0
        total_checks = len(df)
        
        if 'price' in df.columns:
            price_issue = df['price'].isna() | (df['price'] <= 0)
        else:
            price_issue = pd.Series(True, index=df.index)
        accuracy_issues += price_issue.sum()

        valid_price_mask = ~price_issue
        if valid_price_mask.any() and 'change_pct' in df.columns:
            change_pct = df.loc[valid_price_mask, 'change_pct']
            change_issue = change_pct.notna() & (change_pct.abs() > 20)
            accuracy_issues += change_issue.sum()

        return 1.0 - (accuracy_issues / total_checks) if total_checks > 0 else 1.0
    
    def _assess_generic_accuracy(self, df: pd.DataFrame) -> float:
        """通用准确性评估"""
        accuracy_score = 1.0
        
        # 检查数值列的合理性
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_columns:
            # 检查无穷大和NaN
            inf_count = np.isinf(df[col]).sum()
            if inf_count > 0:
                accuracy_score *= 0.9
            
            # 检查负数（对于应该为正数的字段）
            if col.lower() in ['volume', 'amount', 'quantity']:
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    accuracy_score *= 0.9
        
        return accuracy_score
    
    def _assess_consistency(self, df: pd.DataFrame, data_type: str) -> float:
        """评估数据一致性"""
        consistency_score = 1.0
        
        try:
            # 检查数据类型一致性
            for col in df.columns:
                if df[col].dtype == 'object':
                    # 检查字符串长度一致性
                    if col.lower() in ['symbol', 'code']:
                        lengths = df[col].str.len()
                        length_std = lengths.std()
                        if length_std > 2:  # 长度标准差过大
                            consistency_score *= 0.9
            
            # 检查时间序列一致性
            if 'datetime' in df.columns or df.index.name == 'datetime':
                time_col = df.index if df.index.name == 'datetime' else df['datetime']
                if len(time_col) > 1:
                    # 检查时间间隔一致性
                    time_diffs = time_col.diff().dropna()
                    if len(time_diffs) > 1:
                        diff_std = time_diffs.std()
                        diff_mean = time_diffs.mean()
                        if diff_std > diff_mean * 0.5:  # 时间间隔不一致
                            consistency_score *= 0.8
            
        except Exception as e:
            self.logger.warning(f"一致性评估失败: {e}")
            consistency_score = 0.8
        
        return consistency_score
    
    def _assess_timeliness(self, df: pd.DataFrame, context: Dict[str, Any]) -> float:
        """评估数据时效性"""
        try:
            current_time = datetime.now()
            
            # 从上下文获取数据时间戳
            data_timestamp = context.get('timestamp')
            if data_timestamp:
                if isinstance(data_timestamp, str):
                    data_timestamp = pd.to_datetime(data_timestamp)
                
                time_diff = (current_time - data_timestamp).total_seconds()
                
                if time_diff <= self.thresholds.timeliness_excellent:
                    return 1.0
                elif time_diff <= self.thresholds.timeliness_good:
                    return 0.9
                elif time_diff <= self.thresholds.timeliness_fair:
                    return 0.7
                elif time_diff <= self.thresholds.timeliness_critical:
                    return 0.5
                else:
                    return 0.2
            
            # 检查DataFrame中的时间字段
            time_columns = ['datetime', 'timestamp', 'time']
            for col in time_columns:
                if col in df.columns:
                    latest_time = df[col].max()
                    if pd.notna(latest_time):
                        time_diff = (current_time - pd.to_datetime(latest_time)).total_seconds()
                        return 1.0 - min(time_diff / self.thresholds.timeliness_critical, 1.0)
            
            # 默认时效性评分
            return 0.8
            
        except Exception as e:
            self.logger.warning(f"时效性评估失败: {e}")
            return 0.7
    
    def _assess_validity(self, df: pd.DataFrame, data_type: str) -> float:
        """评估数据有效性"""
        validity_score = 1.0
        validity_issues = 0
        total_checks = 0
        
        try:
            # 根据数据类型进行特定的有效性检查
            if data_type.lower() in ["kline", "ohlc", "kdata"]:
                total_checks = len(df)

                price_cols = [col for col in ['open', 'high', 'low', 'close'] if col in df.columns]
                if price_cols:
                    price_issue = pd.Series(False, index=df.index)
                    for col in price_cols:
                        col_issue = df[col].notna() & ((df[col] <= 0) | (df[col] > 10000))
                        price_issue = price_issue | col_issue
                    validity_issues += price_issue.sum()

                if 'volume' in df.columns:
                    volume_issue = df['volume'].notna() & (df['volume'] < 0)
                    validity_issues += volume_issue.sum()
            
            elif data_type.lower() in ["quote", "real_time"]:
                total_checks = len(df)

                if 'symbol' in df.columns:
                    combined_pattern = r'^(\d{6}\.(SH|SZ|BJ)|\d{1,5}\.HK|[A-Z]{1,5}\.US)$'
                    symbol_series = df['symbol'].astype(str)
                    non_empty = symbol_series != ''
                    if non_empty.any():
                        invalid_symbol = non_empty & ~symbol_series.str.match(combined_pattern).fillna(False)
                        validity_issues += invalid_symbol.sum()

                if 'price' in df.columns:
                    price_issue = df['price'].notna() & ((df['price'] <= 0) | (df['price'] > 10000))
                    validity_issues += price_issue.sum()
            
            validity_score = 1.0 - (validity_issues / max(total_checks, 1))
            
        except Exception as e:
            self.logger.warning(f"有效性评估失败: {e}")
            validity_score = 0.8
        
        return validity_score
    
    def _detect_anomalies(self, df: pd.DataFrame, data_type: str) -> float:
        """检测异常数据"""
        try:
            total_anomalies = 0
            total_data_points = len(df)
            
            if total_data_points == 0:
                return 0.0
            
            # 检测数值列的异常值
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            
            for col in numeric_columns:
                series = df[col].dropna()
                if len(series) < 3:
                    continue
                
                # 使用IQR方法检测异常值
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                
                if IQR > 0:
                    lower_bound = Q1 - 1.5 * IQR
                    upper_bound = Q3 + 1.5 * IQR
                    
                    outliers = series[(series < lower_bound) | (series > upper_bound)]
                    total_anomalies += len(outliers)
            
            # 特定于K线数据的异常检测
            if data_type.lower() in ["kline", "ohlc", "kdata"]:
                total_anomalies += self._detect_kline_anomalies(df)
            
            return total_anomalies / (total_data_points * len(numeric_columns)) if numeric_columns.any() else 0.0
            
        except Exception as e:
            self.logger.warning(f"异常检测失败: {e}")
            return 0.0
    
    def _detect_kline_anomalies(self, df: pd.DataFrame) -> int:
        """检测K线数据特有的异常"""
        anomaly_count = 0
        
        try:
            # 检查价格跳跃异常
            if 'close' in df.columns and len(df) > 1:
                df_sorted = df.sort_index()
                price_changes = df_sorted['close'].pct_change().abs()
                
                # 检查单日涨跌幅超过阈值的情况
                extreme_changes = price_changes > self.thresholds.price_change_threshold
                anomaly_count += extreme_changes.sum()
            
            # 检查成交量异常
            if 'volume' in df.columns and len(df) > 1:
                volumes = df['volume']
                volume_mean = volumes.mean()
                
                if volume_mean > 0:
                    volume_spikes = volumes > volume_mean * self.thresholds.volume_spike_threshold
                    anomaly_count += volume_spikes.sum()
                    
        except Exception as e:
            self.logger.warning(f"K线异常检测失败: {e}")
        
        return anomaly_count
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        """验证股票代码格式"""
        import re
        
        # A股代码格式：6位数字.市场
        a_stock_pattern = r'^\d{6}\.(SH|SZ|BJ)$'
        
        # 港股代码格式：数字.HK  
        hk_stock_pattern = r'^\d{1,5}\.HK$'
        
        # 美股代码格式：字母.US
        us_stock_pattern = r'^[A-Z]{1,5}\.US$'
        
        return (re.match(a_stock_pattern, symbol) or 
                re.match(hk_stock_pattern, symbol) or
                re.match(us_stock_pattern, symbol)) is not None
    
    def _calculate_overall_score(self, metrics: Dict[str, float]) -> float:
        """计算综合质量评分"""
        # 权重配置
        weights = {
            'completeness': 0.25,
            'accuracy': 0.30,
            'consistency': 0.20,
            'timeliness': 0.15,
            'validity': 0.10
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for metric, weight in weights.items():
            if metric in metrics:
                total_score += metrics[metric] * weight
                total_weight += weight
        
        # 异常值惩罚
        if 'anomaly_score' in metrics:
            anomaly_penalty = metrics['anomaly_score'] * 0.1
            total_score = max(0.0, total_score - anomaly_penalty)
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _determine_quality_level(self, score: float) -> QualityLevel:
        """确定质量等级"""
        if score >= 0.95:
            return QualityLevel.EXCELLENT
        elif score >= 0.85:
            return QualityLevel.GOOD
        elif score >= 0.70:
            return QualityLevel.FAIR
        elif score >= 0.50:
            return QualityLevel.POOR
        else:
            return QualityLevel.CRITICAL
    
    def _generate_recommendations(self, metrics: Dict[str, float], 
                                issues: List[QualityIssue], data_type: str) -> List[str]:
        """生成质量改进建议"""
        recommendations = []
        
        # 基于指标的建议
        if metrics.get('completeness', 1.0) < 0.8:
            recommendations.append("增加数据完整性检查和补全机制")
        
        if metrics.get('accuracy', 1.0) < 0.9:
            recommendations.append("加强数据源验证和准确性校验")
        
        if metrics.get('timeliness', 1.0) < 0.8:
            recommendations.append("优化数据获取频率和延迟处理")
        
        if metrics.get('consistency', 1.0) < 0.8:
            recommendations.append("标准化数据格式和字段映射")
        
        # 基于数据类型的建议
        if data_type.lower() in ["kline", "ohlc"]:
            if metrics.get('accuracy', 1.0) < 0.9:
                recommendations.append("检查K线数据的OHLC逻辑关系")
        
        # 基于问题严重性的建议
        critical_issues = [issue for issue in issues if issue.severity == "critical"]
        if critical_issues:
            recommendations.append("立即处理关键质量问题，考虑暂停使用该数据源")
        
        # 通用建议
        if not recommendations:
            recommendations.append("数据质量良好，继续监控和维护")
        
        return recommendations
    
    def _update_quality_stats(self, quality_level: QualityLevel) -> None:
        """更新质量统计"""
        self.quality_stats["total_evaluations"] += 1
        
        level_key = f"{quality_level.value}_count"
        if level_key in self.quality_stats:
            self.quality_stats[level_key] += 1
    
    def _record_quality_history(self, data_type: str, report: QualityReport) -> None:
        """记录质量历史"""
        if data_type not in self.quality_history:
            self.quality_history[data_type] = deque(maxlen=self.max_history_size)
        
        self.quality_history[data_type].append({
            "timestamp": report.timestamp,
            "score": report.overall_score,
            "level": report.quality_level.value,
            "metrics": report.metrics
        })
    
    def _evaluate_list_quality(self, data: List, data_type: str, 
                             context: Dict[str, Any]) -> QualityReport:
        """评估列表数据质量"""
        if not data:
            return QualityReport(
                overall_score=0.0,
                quality_level=QualityLevel.CRITICAL,
                metrics={"completeness": 0.0},
                issues=[QualityIssue(
                    QualityMetric.COMPLETENESS, "critical",
                    "列表为空", 0.0, 0.5,
                    "检查数据源和查询条件"
                )],
                recommendations=["检查数据源连接", "验证查询参数"],
                data_info={"type": "List", "length": 0, "data_type": data_type}
            )
        
        # 转换为DataFrame进行详细分析
        try:
            if all(isinstance(item, dict) for item in data):
                df = pd.DataFrame(data)
                return self._evaluate_dataframe_quality(df, data_type, context)
            else:
                # 简单列表质量评估
                non_none_count = sum(1 for item in data if item is not None)
                completeness = non_none_count / len(data)
                
                return QualityReport(
                    overall_score=completeness * 0.8,
                    quality_level=self._determine_quality_level(completeness * 0.8),
                    metrics={"completeness": completeness},
                    issues=[],
                    recommendations=["将数据结构化以获得更详细的质量评估"],
                    data_info={"type": "List", "length": len(data), "data_type": data_type}
                )
                
        except Exception as e:
            return self._create_error_report(str(e), data_type)
    
    def _evaluate_dict_quality(self, data: Dict, data_type: str, 
                             context: Dict[str, Any]) -> QualityReport:
        """评估字典数据质量"""
        if not data:
            return QualityReport(
                overall_score=0.0,
                quality_level=QualityLevel.CRITICAL,
                metrics={"completeness": 0.0},
                issues=[QualityIssue(
                    QualityMetric.COMPLETENESS, "critical",
                    "字典为空", 0.0, 0.5,
                    "检查数据源"
                )],
                recommendations=["检查数据源连接"],
                data_info={"type": "Dict", "keys": 0, "data_type": data_type}
            )
        
        # 计算完整性
        non_none_values = sum(1 for value in data.values() if value is not None)
        completeness = non_none_values / len(data)
        
        # 简单的质量评估
        overall_score = completeness * 0.8
        
        return QualityReport(
            overall_score=overall_score,
            quality_level=self._determine_quality_level(overall_score),
            metrics={"completeness": completeness},
            issues=[],
            recommendations=["转换为结构化数据以获得更详细的质量分析"],
            data_info={
                "type": "Dict", 
                "keys": len(data), 
                "data_type": data_type,
                "key_names": list(data.keys())
            }
        )
    
    def _evaluate_generic_quality(self, data: Any, data_type: str, 
                                 context: Dict[str, Any]) -> QualityReport:
        """评估通用数据质量"""
        if data is None:
            return QualityReport(
                overall_score=0.0,
                quality_level=QualityLevel.CRITICAL,
                metrics={"completeness": 0.0},
                issues=[QualityIssue(
                    QualityMetric.COMPLETENESS, "critical",
                    "数据为空", 0.0, 0.5,
                    "检查数据源"
                )],
                recommendations=["检查数据获取逻辑"],
                data_info={"type": str(type(data)), "data_type": data_type}
            )
        
        # 基本质量评估
        return QualityReport(
            overall_score=0.7,
            quality_level=QualityLevel.FAIR,
            metrics={"completeness": 1.0},
            issues=[],
            recommendations=["提供更结构化的数据以获得准确的质量评估"],
            data_info={"type": str(type(data)), "data_type": data_type}
        )
    
    def _create_error_report(self, error_message: str, data_type: str) -> QualityReport:
        """创建错误报告"""
        return QualityReport(
            overall_score=0.0,
            quality_level=QualityLevel.CRITICAL,
            metrics={},
            issues=[QualityIssue(
                QualityMetric.VALIDITY, "critical",
                f"质量评估错误: {error_message}",
                0.0, 1.0,
                "检查数据格式和评估逻辑"
            )],
            recommendations=["修复数据质量评估错误"],
            data_info={"type": "error", "data_type": data_type}
        )
    
    def get_quality_statistics(self) -> Dict[str, Any]:
        """获取质量统计信息"""
        total = self.quality_stats["total_evaluations"]
        
        if total == 0:
            return self.quality_stats
        
        stats = self.quality_stats.copy()
        stats.update({
            "excellent_rate": stats["excellent_count"] / total,
            "good_rate": stats["good_count"] / total,
            "fair_rate": stats["fair_count"] / total,
            "poor_rate": stats["poor_count"] / total,
            "critical_rate": stats["critical_count"] / total
        })
        
        return stats
    
    def get_quality_trends(self, data_type: str = None, days: int = 7) -> Dict[str, Any]:
        """获取质量趋势分析"""
        trends = {}
        cutoff_time = datetime.now() - timedelta(days=days)
        
        if data_type:
            if data_type in self.quality_history:
                recent_records = [
                    record for record in self.quality_history[data_type]
                    if record["timestamp"] >= cutoff_time
                ]
                trends[data_type] = self._analyze_trend(recent_records)
        else:
            for dt, history in self.quality_history.items():
                recent_records = [
                    record for record in history
                    if record["timestamp"] >= cutoff_time
                ]
                trends[dt] = self._analyze_trend(recent_records)
        
        return trends
    
    def _analyze_trend(self, records: List[Dict]) -> Dict[str, Any]:
        """分析质量趋势"""
        if not records:
            return {"trend": "no_data", "message": "没有足够的历史数据"}
        
        scores = [record["score"] for record in records]
        
        if len(scores) < 2:
            return {"trend": "insufficient_data", "current_score": scores[0]}
        
        # 计算趋势
        recent_avg = statistics.mean(scores[-3:]) if len(scores) >= 3 else scores[-1]
        earlier_avg = statistics.mean(scores[:3]) if len(scores) >= 3 else scores[0]
        
        trend_direction = "stable"
        if recent_avg > earlier_avg + 0.05:
            trend_direction = "improving"
        elif recent_avg < earlier_avg - 0.05:
            trend_direction = "degrading"
        
        return {
            "trend": trend_direction,
            "current_score": scores[-1],
            "average_score": statistics.mean(scores),
            "score_range": (min(scores), max(scores)),
            "data_points": len(scores),
            "recent_average": recent_avg,
            "earlier_average": earlier_avg
        }
