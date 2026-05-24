"""
模型性能评估模块

提供历史性能跟踪、实时性能监控、模型可靠性评估和预测准确率分析功能
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from collections import deque
import json
from loguru import logger

from .config.selector_config import PerformanceEvaluationConfig
from core.database.unified_sqlite_access import UnifiedSQLiteAccess

@dataclass
class ModelMetrics:
    """模型指标"""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    mape: float  # Mean Absolute Percentage Error
    sharpe_ratio: float
    timestamp: datetime


@dataclass
class ModelPerformance:
    """模型性能数据"""
    model_type: str
    metrics: ModelMetrics
    composite_score: float
    reliability_score: float
    sample_size: int
    evaluation_timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'model_type': self.model_type,
            'metrics': asdict(self.metrics),
            'composite_score': self.composite_score,
            'reliability_score': self.reliability_score,
            'sample_size': self.sample_size,
            'evaluation_timestamp': self.evaluation_timestamp.isoformat()
        }


class AccuracyCalculator:
    """准确率计算器"""
    
    def calculate(self, predictions: List[Dict[str, Any]], 
                  actuals: List[Dict[str, Any]]) -> float:
        """计算准确率"""
        try:
            if len(predictions) != len(actuals) or len(predictions) == 0:
                return 0.0
            
            correct = 0
            total = len(predictions)
            
            for i, (pred, actual) in enumerate(zip(predictions, actuals)):
                pred_value = pred.get('value', 0)
                actual_value = actual.get('value', 0)
                
                if len(predictions) > 1:
                    if i == 0:
                        continue
                    
                    prev_pred = predictions[i - 1].get('value', 0)
                    prev_actual = actuals[i - 1].get('value', 0)
                    
                    pred_direction = 1 if pred_value > prev_pred else (-1 if pred_value < prev_pred else 0)
                    actual_direction = 1 if actual_value > prev_actual else (-1 if actual_value < prev_actual else 0)
                    
                    if pred_direction == actual_direction and pred_direction != 0:
                        correct += 1
                else:
                    # 单点预测，计算误差阈值
                    error = abs(pred_value - actual_value)
                    if actual_value != 0:
                        error_rate = error / abs(actual_value)
                        if error_rate <= 0.05:  # 5%误差阈值
                            correct += 1
            
            return correct / total if total > 0 else 0.0
            
        except Exception as e:
            logger.error(f"准确率计算失败: {e}")
            return 0.0


class PrecisionCalculator:
    """精确率计算器"""
    
    def calculate(self, predictions: List[Dict[str, Any]], 
                  actuals: List[Dict[str, Any]]) -> float:
        """计算精确率"""
        try:
            if len(predictions) != len(actuals) or len(predictions) == 0:
                return 0.0
            
            # 假设这是一个回归问题，使用预测误差的倒数来模拟精确率
            errors = [
                abs(pred.get('value', 0) - actual.get('value', 0)) / abs(actual.get('value', 0))
                for pred, actual in zip(predictions, actuals)
                if actual.get('value', 0) != 0
            ]
            
            if not errors:
                return 0.0
            
            # 精确率 = 1 - 平均误差
            avg_error = np.mean(errors)
            precision = max(0, 1 - avg_error)
            
            return precision
            
        except Exception as e:
            logger.error(f"精确率计算失败: {e}")
            return 0.0


class RecallCalculator:
    """召回率计算器"""
    
    def calculate(self, predictions: List[Dict[str, Any]], 
                  actuals: List[Dict[str, Any]]) -> float:
        """计算召回率"""
        try:
            # 对于回归问题，召回率可以用预测覆盖度来模拟
            if len(predictions) == 0:
                return 0.0
            
            # 检查预测是否覆盖了重要的市场变化点
            coverage = min(len(predictions) / 100, 1.0)  # 假设理想情况下需要100个预测点
            
            return coverage
            
        except Exception as e:
            logger.error(f"召回率计算失败: {e}")
            return 0.0


class F1ScoreCalculator:
    """F1分数计算器"""
    
    def calculate(self, predictions: List[Dict[str, Any]], 
                  actuals: List[Dict[str, Any]]) -> float:
        """计算F1分数"""
        try:
            precision_calc = PrecisionCalculator()
            recall_calc = RecallCalculator()
            
            precision = precision_calc.calculate(predictions, actuals)
            recall = recall_calc.calculate(predictions, actuals)
            
            if precision + recall == 0:
                return 0.0
            
            f1_score = 2 * (precision * recall) / (precision + recall)
            return f1_score
            
        except Exception as e:
            logger.error(f"F1分数计算失败: {e}")
            return 0.0


class MAPECalculator:
    """平均绝对百分比误差计算器"""
    
    def calculate(self, predictions: List[Dict[str, Any]], 
                  actuals: List[Dict[str, Any]]) -> float:
        """计算MAPE"""
        try:
            if len(predictions) != len(actuals) or len(predictions) == 0:
                return 1.0  # 返回最差情况
            
            mape_sum = 0.0
            valid_count = 0
            
            for pred, actual in zip(predictions, actuals):
                pred_value = pred.get('value', 0)
                actual_value = actual.get('value', 0)
                
                if actual_value != 0:
                    ape = abs(pred_value - actual_value) / abs(actual_value)
                    mape_sum += ape
                    valid_count += 1
            
            if valid_count == 0:
                return 1.0
            
            mape = mape_sum / valid_count
            return mape
            
        except Exception as e:
            logger.error(f"MAPE计算失败: {e}")
            return 1.0


class SharpeRatioCalculator:
    """夏普比率计算器"""
    
    def calculate(self, predictions: List[Dict[str, Any]], 
                  actuals: List[Dict[str, Any]]) -> float:
        """计算夏普比率"""
        try:
            if len(predictions) < 2 or len(predictions) != len(actuals):
                return 0.0
            
            # 计算收益率
            returns = []
            for i in range(1, len(predictions)):
                pred_value = predictions[i].get('value', 0)
                prev_pred_value = predictions[i-1].get('value', 0)
                
                actual_value = actuals[i].get('value', 0)
                prev_actual_value = actuals[i-1].get('value', 0)
                
                if prev_pred_value != 0 and prev_actual_value != 0:
                    pred_return = (pred_value - prev_pred_value) / prev_pred_value
                    actual_return = (actual_value - prev_actual_value) / prev_actual_value
                    
                    # 计算预测收益与实际收益的匹配度
                    returns.append(abs(pred_return - actual_return))
            
            if not returns:
                return 0.0
            
            # 假设无风险收益率为0
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return == 0:
                return 0.0
            
            sharpe_ratio = mean_return / std_return
            return max(-2.0, min(2.0, sharpe_ratio))  # 限制在合理范围内
            
        except Exception as e:
            logger.error(f"夏普比率计算失败: {e}")
            return 0.0


class PerformanceDatabase:
    """性能数据库"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_path = config.get('path', 'data/performance.sqlite') if isinstance(config, dict) else 'data/performance.sqlite'
        self._init_database()
    
    def _get_db(self) -> UnifiedSQLiteAccess:
        return UnifiedSQLiteAccess.get_instance(self.db_path)
    
    def _init_database(self):
        """初始化数据库"""
        try:
            import os
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS model_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_type TEXT NOT NULL,
                        metrics TEXT NOT NULL,
                        composite_score REAL NOT NULL,
                        reliability_score REAL NOT NULL,
                        sample_size INTEGER NOT NULL,
                        evaluation_timestamp TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
    
    def save_performance(self, performance: ModelPerformance):
        """保存性能数据"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO model_performance 
                    (model_type, metrics, composite_score, reliability_score, sample_size, evaluation_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    performance.model_type,
                    json.dumps(asdict(performance.metrics), default=str),
                    performance.composite_score,
                    performance.reliability_score,
                    performance.sample_size,
                    performance.evaluation_timestamp.isoformat()
                ))
            
        except Exception as e:
            logger.error(f"保存性能数据失败: {e}")
    
    def get_performance_history(self, model_type: str, 
                               days: int = 30) -> List[ModelPerformance]:
        """获取历史性能数据"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                since_date = (datetime.now() - timedelta(days=days)).isoformat()
                
                cursor.execute('''
                    SELECT model_type, metrics, composite_score, reliability_score, 
                           sample_size, evaluation_timestamp
                    FROM model_performance
                    WHERE model_type = ? AND evaluation_timestamp >= ?
                    ORDER BY evaluation_timestamp DESC
                ''', (model_type, since_date))
                
                results = cursor.fetchall()
                
                performances = []
                for row in results:
                    metrics_dict = json.loads(row[1])
                    metrics = ModelMetrics(**metrics_dict)
                    
                    performance = ModelPerformance(
                        model_type=row[0],
                        metrics=metrics,
                        composite_score=row[2],
                        reliability_score=row[3],
                        sample_size=row[4],
                        evaluation_timestamp=datetime.fromisoformat(row[5])
                    )
                    performances.append(performance)
                
                return performances
            
        except Exception as e:
            logger.error(f"获取历史性能数据失败: {e}")
            return []


class ModelPerformanceEvaluator:
    """模型性能评估器"""
    
    def __init__(self, config: PerformanceEvaluationConfig):
        self.config = config
        
        # 获取数据库配置
        db_config = config.database if config.database else {}
        self.performance_db = PerformanceDatabase(db_config)
        
        self.metric_calculators = {
            'accuracy': AccuracyCalculator(),
            'precision': PrecisionCalculator(),
            'recall': RecallCalculator(),
            'f1_score': F1ScoreCalculator(),
            'mape': MAPECalculator(),
            'sharpe_ratio': SharpeRatioCalculator()
        }
        
        # 缓存最近的结果
        self._recent_evaluations = deque(maxlen=100)
        
        logger.info("模型性能评估器初始化完成")
    
    def evaluate_model_performance(self,
                                 model_type: str,
                                 prediction_results: List[Dict[str, Any]],
                                 actual_results: List[Dict[str, Any]]) -> ModelPerformance:
        """评估模型性能"""
        
        try:
            if len(prediction_results) != len(actual_results):
                raise ValueError("预测结果与实际结果数量不匹配")
            
            if len(prediction_results) == 0:
                logger.warning("没有预测结果可评估")
                return self._get_default_performance(model_type)
            
            # 计算各项指标
            metrics = {}
            for metric_name, calculator in self.metric_calculators.items():
                try:
                    metrics[metric_name] = calculator.calculate(
                        prediction_results, actual_results
                    )
                except Exception as e:
                    logger.warning(f"计算{metric_name}指标失败: {e}")
                    metrics[metric_name] = 0.0
            
            # 计算综合评分
            composite_score = self._calculate_composite_score(metrics)
            
            # 评估可靠性
            reliability = self._assess_reliability(prediction_results, actual_results)
            
            performance = ModelPerformance(
                model_type=model_type,
                metrics=ModelMetrics(**metrics),
                composite_score=composite_score,
                reliability_score=reliability,
                sample_size=len(prediction_results),
                evaluation_timestamp=datetime.now()
            )
            
            # 保存性能数据
            self.performance_db.save_performance(performance)
            
            # 添加到缓存
            self._recent_evaluations.append(performance)
            
            logger.info(f"模型{model_type}性能评估完成: 综合评分={composite_score:.3f}, "
                       f"可靠性={reliability:.3f}, 样本数={len(prediction_results)}")
            
            return performance
            
        except Exception as e:
            logger.error(f"模型性能评估失败: {e}")
            return self._get_default_performance(model_type)
    
    def _calculate_composite_score(self, metrics: Dict[str, float]) -> float:
        """计算综合评分"""
        weights = getattr(self.config, 'metric_weights', {
            'accuracy': 0.3,
            'precision': 0.2,
            'recall': 0.2,
            'f1_score': 0.15,
            'mape': 0.1,
            'sharpe_ratio': 0.05
        })
        
        score = 0.0
        total_weight = 0.0
        
        for metric_name, weight in weights.items():
            if metric_name in metrics:
                # 标准化指标值
                normalized_value = self._normalize_metric(metric_name, metrics[metric_name])
                score += normalized_value * weight
                total_weight += weight
        
        return score / total_weight if total_weight > 0 else 0.0
    
    def _normalize_metric(self, metric_name: str, value: float) -> float:
        """标准化指标值"""
        if metric_name == 'mape':
            # MAPE越小越好，所以需要反转
            return max(0, 1 - value)
        elif metric_name == 'sharpe_ratio':
            # 夏普比率通常在-2到2之间
            return max(0, min(1, (value + 2) / 4))
        else:
            # 其他指标假设在0-1范围内
            return max(0, min(1, value))
    
    def _assess_reliability(self, predictions: List[Dict[str, Any]], 
                           actuals: List[Dict[str, Any]]) -> float:
        """评估可靠性"""
        try:
            if len(predictions) < 5:
                return 0.5  # 样本太少
            
            # 计算预测一致性
            consistency_score = self._calculate_consistency(predictions, actuals)
            
            # 计算稳定性
            stability_score = self._calculate_stability(predictions, actuals)
            
            # 综合评分
            reliability = (consistency_score * 0.6 + stability_score * 0.4)
            
            return max(0, min(1, reliability))
            
        except Exception as e:
            logger.error(f"可靠性评估失败: {e}")
            return 0.5
    
    def _calculate_consistency(self, predictions: List[Dict[str, Any]], 
                              actuals: List[Dict[str, Any]]) -> float:
        """计算预测一致性"""
        try:
            errors = [
                abs(pred.get('value', 0) - actual.get('value', 0)) / abs(actual.get('value', 0))
                for pred, actual in zip(predictions, actuals)
                if actual.get('value', 0) != 0
            ]
            
            if not errors:
                return 0.0
            
            # 一致性 = 1 - 误差变异系数
            mean_error = np.mean(errors)
            std_error = np.std(errors)
            
            if mean_error == 0:
                return 1.0
            
            cv = std_error / mean_error  # 变异系数
            consistency = max(0, 1 - cv)
            
            return consistency
            
        except Exception as e:
            logger.error(f"一致性计算失败: {e}")
            return 0.5
    
    def _calculate_stability(self, predictions: List[Dict[str, Any]], 
                            actuals: List[Dict[str, Any]]) -> float:
        """计算稳定性"""
        try:
            if len(predictions) < 3:
                return 0.5
            
            # 计算相邻预测的差异
            differences = []
            for i in range(1, len(predictions)):
                current_pred = predictions[i].get('value', 0)
                prev_pred = predictions[i-1].get('value', 0)
                
                current_actual = actuals[i].get('value', 0)
                prev_actual = actuals[i-1].get('value', 0)
                
                if prev_pred != 0 and prev_actual != 0:
                    pred_change = abs(current_pred - prev_pred) / abs(prev_pred)
                    actual_change = abs(current_actual - prev_actual) / abs(prev_actual)
                    
                    # 计算变化的一致性
                    change_consistency = 1 - abs(pred_change - actual_change)
                    differences.append(max(0, change_consistency))
            
            if not differences:
                return 0.5
            
            stability = np.mean(differences)
            return max(0, min(1, stability))
            
        except Exception as e:
            logger.error(f"稳定性计算失败: {e}")
            return 0.5
    
    def _get_default_performance(self, model_type: str) -> ModelPerformance:
        """获取默认性能数据"""
        default_metrics = ModelMetrics(
            accuracy=0.6,
            precision=0.6,
            recall=0.6,
            f1_score=0.6,
            mape=0.4,
            sharpe_ratio=0.0,
            timestamp=datetime.now()
        )
        
        return ModelPerformance(
            model_type=model_type,
            metrics=default_metrics,
            composite_score=0.6,
            reliability_score=0.5,
            sample_size=0,
            evaluation_timestamp=datetime.now()
        )
    
    def get_performance_summary(self, model_type: str) -> Dict[str, Any]:
        """获取性能摘要"""
        try:
            history = self.performance_db.get_performance_history(model_type, days=30)
            
            if not history:
                return {
                    'model_type': model_type,
                    'available': False,
                    'message': '暂无性能数据'
                }
            
            # 计算统计信息
            scores = [p.composite_score for p in history]
            reliabilities = [p.reliability_score for p in history]
            sample_sizes = [p.sample_size for p in history]
            
            summary = {
                'model_type': model_type,
                'available': True,
                'evaluation_count': len(history),
                'composite_score': {
                    'current': scores[0] if scores else 0.0,
                    'average': np.mean(scores) if scores else 0.0,
                    'best': max(scores) if scores else 0.0,
                    'worst': min(scores) if scores else 0.0,
                    'trend': 'improving' if len(scores) > 1 and scores[0] > scores[-1] else 'declining' if len(scores) > 1 and scores[0] < scores[-1] else 'stable'
                },
                'reliability': {
                    'current': reliabilities[0] if reliabilities else 0.0,
                    'average': np.mean(reliabilities) if reliabilities else 0.0
                },
                'sample_size': {
                    'total': sum(sample_sizes),
                    'average': np.mean(sample_sizes) if sample_sizes else 0.0,
                    'recent': sample_sizes[0] if sample_sizes else 0
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"获取性能摘要失败: {e}")
            return {
                'model_type': model_type,
                'available': False,
                'message': f'获取性能摘要失败: {e}'
            }