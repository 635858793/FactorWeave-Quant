"""
增强模型评估器

提供更全面的评估指标和可视化功能，扩展ModelPerformanceEvaluator的功能
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from collections import deque
import json
import sqlite3
import logging

try:
    from sklearn.metrics import (
        roc_curve, auc, precision_recall_curve,
        confusion_matrix, classification_report,
        r2_score, mean_squared_error, median_absolute_error,
        balanced_accuracy_score, matthews_corrcoef, cohen_kappa_score
    )
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import matplotlib
    matplotlib.use('Agg')
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from .performance_evaluator import ModelPerformanceEvaluator, ModelPerformance, ModelMetrics

logger = logging.getLogger(__name__)


@dataclass
class EnhancedModelMetrics:
    """增强模型指标"""
    basic_metrics: ModelMetrics
    classification_metrics: Optional[Dict[str, float]] = None
    regression_metrics: Optional[Dict[str, float]] = None
    roc_auc: Optional[float] = None
    pr_auc: Optional[float] = None
    best_threshold: Optional[float] = None
    timestamp: datetime = datetime.now()


@dataclass
class EnhancedModelPerformance:
    """增强模型性能数据"""
    model_type: str
    basic_performance: ModelPerformance
    enhanced_metrics: EnhancedModelMetrics
    evaluation_timestamp: datetime = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'model_type': self.model_type,
            'basic_performance': self.basic_performance.to_dict(),
            'enhanced_metrics': asdict(self.enhanced_metrics),
            'evaluation_timestamp': self.evaluation_timestamp.isoformat()
        }


class EnhancedModelEvaluator:
    """增强模型评估器"""
    
    def __init__(self, base_evaluator: ModelPerformanceEvaluator):
        """
        初始化增强模型评估器
        
        参数:
            base_evaluator: 基础模型评估器
        """
        self.base_evaluator = base_evaluator
        self.config = base_evaluator.config
        
        logger.info("增强模型评估器初始化完成")
    
    def evaluate_model_performance(
        self,
        model_type: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None,
        task_type: str = 'classification'
    ) -> EnhancedModelPerformance:
        """
        评估模型性能（增强版）
        
        参数:
            model_type: 模型类型
            y_true: 真实标签
            y_pred: 预测标签
            y_pred_proba: 预测概率（仅用于分类任务）
            task_type: 任务类型 ('classification' 或 'regression')
            
        返回:
            增强模型性能数据
        """
        try:
            logger.info(f"开始评估模型性能（增强版）: {model_type}")
            
            if not SKLEARN_AVAILABLE:
                logger.warning("sklearn未安装，无法进行增强评估")
                return self._get_default_enhanced_performance(model_type)
            
            # 转换为字典格式用于基础评估
            prediction_results = [{'value': pred} for pred in y_pred]
            actual_results = [{'value': actual} for actual in y_true]
            
            # 基础评估
            basic_performance = self.base_evaluator.evaluate_model_performance(
                model_type, prediction_results, actual_results
            )
            
            # 增强评估
            if task_type == 'classification':
                enhanced_metrics = self._evaluate_classification(
                    y_true, y_pred, y_pred_proba
                )
            else:
                enhanced_metrics = self._evaluate_regression(y_true, y_pred)
            
            enhanced_metrics.basic_metrics = basic_performance.metrics
            enhanced_metrics.timestamp = datetime.now()
            
            enhanced_performance = EnhancedModelPerformance(
                model_type=model_type,
                basic_performance=basic_performance,
                enhanced_metrics=enhanced_metrics,
                evaluation_timestamp=datetime.now()
            )
            
            logger.info(f"模型评估完成（增强版）: {model_type}")
            
            return enhanced_performance
            
        except Exception as e:
            logger.error(f"模型评估失败（增强版）: {e}")
            return self._get_default_enhanced_performance(model_type)
    
    def _evaluate_classification(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None
    ) -> EnhancedModelMetrics:
        """评估分类模型"""
        try:
            classification_metrics = {}
            
            # 混淆矩阵
            cm = confusion_matrix(y_true, y_pred)
            tn, fp, fn, tp = cm.ravel()
            
            # 计算分类指标
            classification_metrics['confusion_matrix'] = cm.tolist()
            classification_metrics['true_positive'] = int(tp)
            classification_metrics['true_negative'] = int(tn)
            classification_metrics['false_positive'] = int(fp)
            classification_metrics['false_negative'] = int(fn)
            
            # 特异性和敏感度
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            classification_metrics['specificity'] = float(specificity)
            classification_metrics['sensitivity'] = float(sensitivity)
            
            # 平衡准确率
            balanced_acc = balanced_accuracy_score(y_true, y_pred)
            classification_metrics['balanced_accuracy'] = float(balanced_acc)
            
            # 马修斯相关系数
            mcc = matthews_corrcoef(y_true, y_pred)
            classification_metrics['mcc'] = float(mcc)
            
            # Cohen's Kappa
            kappa = cohen_kappa_score(y_true, y_pred)
            classification_metrics['cohen_kappa'] = float(kappa)
            
            # ROC曲线和AUC
            roc_auc = None
            if y_pred_proba is not None:
                fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
                roc_auc = auc(fpr, tpr)
                classification_metrics['roc_auc'] = float(roc_auc)
                
                # PR曲线和AUC
                precision, recall, _ = precision_recall_curve(y_true, y_pred_proba)
                pr_auc = auc(recall, precision)
                classification_metrics['pr_auc'] = float(pr_auc)
                
                # 最佳阈值（Youden's J统计量）
                youden_j = tpr - fpr
                best_threshold_idx = np.argmax(youden_j)
                best_threshold = _[best_threshold_idx]
                classification_metrics['best_threshold_youden'] = float(best_threshold)
            
            # 基于F1分数的最佳阈值
            if y_pred_proba is not None:
                best_threshold_f1 = self._find_best_threshold_f1(y_true, y_pred_proba)
                classification_metrics['best_threshold_f1'] = float(best_threshold_f1)
            
            enhanced_metrics = EnhancedModelMetrics(
                basic_metrics=None,
                classification_metrics=classification_metrics,
                regression_metrics=None,
                roc_auc=roc_auc,
                pr_auc=classification_metrics.get('pr_auc'),
                best_threshold=classification_metrics.get('best_threshold_youden'),
                timestamp=datetime.now()
            )
            
            return enhanced_metrics
            
        except Exception as e:
            logger.error(f"分类模型评估失败: {e}")
            return EnhancedModelMetrics(
                basic_metrics=None,
                classification_metrics={},
                regression_metrics=None,
                timestamp=datetime.now()
            )
    
    def _evaluate_regression(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> EnhancedModelMetrics:
        """评估回归模型"""
        try:
            regression_metrics = {}
            
            # R²分数
            r2 = r2_score(y_true, y_pred)
            regression_metrics['r2_score'] = float(r2)
            
            # 调整R²分数
            n = len(y_true)
            p = 1  # 假设只有一个特征
            adjusted_r2 = 1 - (1 - r2) * (n - 1) / (n - p - 1) if n > p + 1 else r2
            regression_metrics['adjusted_r2_score'] = float(adjusted_r2)
            
            # 均方根误差
            mse = mean_squared_error(y_true, y_pred)
            rmse = np.sqrt(mse)
            regression_metrics['rmse'] = float(rmse)
            
            # 均方百分比误差
            mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
            regression_metrics['mape'] = float(mape)
            
            # 中位数绝对误差
            medae = median_absolute_error(y_true, y_pred)
            regression_metrics['medae'] = float(medae)
            
            enhanced_metrics = EnhancedModelMetrics(
                basic_metrics=None,
                classification_metrics=None,
                regression_metrics=regression_metrics,
                timestamp=datetime.now()
            )
            
            return enhanced_metrics
            
        except Exception as e:
            logger.error(f"回归模型评估失败: {e}")
            return EnhancedModelMetrics(
                basic_metrics=None,
                classification_metrics=None,
                regression_metrics={},
                timestamp=datetime.now()
            )
    
    def _find_best_threshold_f1(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray
    ) -> float:
        """基于F1分数找到最佳阈值"""
        try:
            thresholds = np.arange(0, 1, 0.01)
            best_f1 = 0.0
            best_threshold = 0.5
            
            for threshold in thresholds:
                y_pred_threshold = (y_pred_proba >= threshold).astype(int)
                
                if len(np.unique(y_pred_threshold)) < 2:
                    continue
                
                cm = confusion_matrix(y_true, y_pred_threshold)
                tn, fp, fn, tp = cm.ravel()
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                
                if precision + recall > 0:
                    f1 = 2 * precision * recall / (precision + recall)
                    if f1 > best_f1:
                        best_f1 = f1
                        best_threshold = threshold
            
            return best_threshold
            
        except Exception as e:
            logger.error(f"基于F1分数找最佳阈值失败: {e}")
            return 0.5
    
    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        title: str = "Confusion Matrix",
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制混淆矩阵热力图
        
        参数:
            y_true: 真实标签
            y_pred: 预测标签
            title: 图表标题
            save_path: 保存路径
            
        返回:
            保存的文件路径（如果保存成功）
        """
        try:
            if not MATPLOTLIB_AVAILABLE or not SKLEARN_AVAILABLE:
                logger.warning("matplotlib或sklearn未安装，无法绘制混淆矩阵")
                return None
            
            cm = confusion_matrix(y_true, y_pred)
            
            plt.figure(figsize=(8, 6))
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=True)
            plt.title(title)
            plt.ylabel('True Label')
            plt.xlabel('Predicted Label')
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                plt.close()
                logger.info(f"混淆矩阵已保存到: {save_path}")
                return save_path
            else:
                plt.show()
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制混淆矩阵失败: {e}")
            return None
    
    def plot_roc_curve(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        title: str = "ROC Curve",
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制ROC曲线
        
        参数:
            y_true: 真实标签
            y_pred_proba: 预测概率
            title: 图表标题
            save_path: 保存路径
            
        返回:
            保存的文件路径（如果保存成功）
        """
        try:
            if not MATPLOTLIB_AVAILABLE or not SKLEARN_AVAILABLE:
                logger.warning("matplotlib或sklearn未安装，无法绘制ROC曲线")
                return None
            
            fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
            roc_auc = auc(fpr, tpr)
            
            plt.figure(figsize=(8, 6))
            plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.2f})')
            plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('False Positive Rate')
            plt.ylabel('True Positive Rate')
            plt.title(title)
            plt.legend(loc="lower right")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                plt.close()
                logger.info(f"ROC曲线已保存到: {save_path}")
                return save_path
            else:
                plt.show()
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制ROC曲线失败: {e}")
            return None
    
    def plot_pr_curve(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        title: str = "Precision-Recall Curve",
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制PR曲线
        
        参数:
            y_true: 真实标签
            y_pred_proba: 预测概率
            title: 图表标题
            save_path: 保存路径
            
        返回:
            保存的文件路径（如果保存成功）
        """
        try:
            if not MATPLOTLIB_AVAILABLE or not SKLEARN_AVAILABLE:
                logger.warning("matplotlib或sklearn未安装，无法绘制PR曲线")
                return None
            
            precision, recall, _ = precision_recall_curve(y_true, y_pred_proba)
            pr_auc = auc(recall, precision)
            
            plt.figure(figsize=(8, 6))
            plt.plot(recall, precision, color='blue', lw=2, label=f'PR curve (AUC = {pr_auc:.2f})')
            plt.xlabel('Recall')
            plt.ylabel('Precision')
            plt.title(title)
            plt.legend(loc="lower left")
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                plt.close()
                logger.info(f"PR曲线已保存到: {save_path}")
                return save_path
            else:
                plt.show()
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制PR曲线失败: {e}")
            return None
    
    def plot_feature_importance(
        self,
        feature_names: List[str],
        importance_scores: np.ndarray,
        title: str = "Feature Importance",
        top_n: int = 20,
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制特征重要性图
        
        参数:
            feature_names: 特征名称列表
            importance_scores: 重要性分数
            title: 图表标题
            top_n: 显示前N个特征
            save_path: 保存路径
            
        返回:
            保存的文件路径（如果保存成功）
        """
        try:
            if not MATPLOTLIB_AVAILABLE:
                logger.warning("matplotlib未安装，无法绘制特征重要性图")
                return None
            
            # 按重要性排序
            indices = np.argsort(importance_scores)[::-1][:top_n]
            sorted_features = [feature_names[i] for i in indices]
            sorted_scores = importance_scores[indices]
            
            plt.figure(figsize=(10, 6))
            plt.barh(range(len(sorted_features)), sorted_scores, color='steelblue')
            plt.yticks(range(len(sorted_features)), sorted_features)
            plt.xlabel('Importance Score')
            plt.title(title)
            plt.gca().invert_yaxis()
            plt.grid(True, alpha=0.3, axis='x')
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                plt.close()
                logger.info(f"特征重要性图已保存到: {save_path}")
                return save_path
            else:
                plt.show()
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制特征重要性图失败: {e}")
            return None
    
    def plot_prediction_error(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        title: str = "Prediction Error",
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制预测误差图
        
        参数:
            y_true: 真实值
            y_pred: 预测值
            title: 图表标题
            save_path: 保存路径
            
        返回:
            保存的文件路径（如果保存成功）
        """
        try:
            if not MATPLOTLIB_AVAILABLE:
                logger.warning("matplotlib未安装，无法绘制预测误差图")
                return None
            
            errors = y_pred - y_true
            
            plt.figure(figsize=(10, 6))
            plt.scatter(y_true, errors, alpha=0.5, color='steelblue')
            plt.axhline(y=0, color='red', linestyle='--', linewidth=2)
            plt.xlabel('True Values')
            plt.ylabel('Prediction Errors')
            plt.title(title)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                plt.close()
                logger.info(f"预测误差图已保存到: {save_path}")
                return save_path
            else:
                plt.show()
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制预测误差图失败: {e}")
            return None
    
    def plot_residuals(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        title: str = "Residual Plot",
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        绘制残差图
        
        参数:
            y_true: 真实值
            y_pred: 预测值
            title: 图表标题
            save_path: 保存路径
            
        返回:
            保存的文件路径（如果保存成功）
        """
        try:
            if not MATPLOTLIB_AVAILABLE:
                logger.warning("matplotlib未安装，无法绘制残差图")
                return None
            
            residuals = y_true - y_pred
            
            plt.figure(figsize=(10, 6))
            plt.scatter(y_pred, residuals, alpha=0.5, color='steelblue')
            plt.axhline(y=0, color='red', linestyle='--', linewidth=2)
            plt.xlabel('Predicted Values')
            plt.ylabel('Residuals')
            plt.title(title)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                plt.close()
                logger.info(f"残差图已保存到: {save_path}")
                return save_path
            else:
                plt.show()
                plt.close()
                return None
                
        except Exception as e:
            logger.error(f"绘制残差图失败: {e}")
            return None
    
    def generate_evaluation_report(
        self,
        enhanced_performance: EnhancedModelPerformance,
        save_path: Optional[str] = None
    ) -> str:
        """
        生成评估报告
        
        参数:
            enhanced_performance: 增强模型性能数据
            save_path: 保存路径
            
        返回:
            报告文本
        """
        try:
            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("模型性能评估报告（增强版）")
            report_lines.append("=" * 80)
            report_lines.append(f"模型类型: {enhanced_performance.model_type}")
            report_lines.append(f"评估时间: {enhanced_performance.evaluation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("")
            
            # 基础指标
            report_lines.append("基础指标:")
            report_lines.append("-" * 40)
            basic_metrics = enhanced_performance.basic_performance.metrics
            report_lines.append(f"准确率: {basic_metrics.accuracy:.4f}")
            report_lines.append(f"精确率: {basic_metrics.precision:.4f}")
            report_lines.append(f"召回率: {basic_metrics.recall:.4f}")
            report_lines.append(f"F1分数: {basic_metrics.f1_score:.4f}")
            report_lines.append(f"MAPE: {basic_metrics.mape:.4f}")
            report_lines.append(f"夏普比率: {basic_metrics.sharpe_ratio:.4f}")
            report_lines.append("")
            
            # 增强指标
            enhanced_metrics = enhanced_performance.enhanced_metrics
            
            if enhanced_metrics.classification_metrics:
                report_lines.append("分类指标:")
                report_lines.append("-" * 40)
                cls_metrics = enhanced_metrics.classification_metrics
                
                if 'confusion_matrix' in cls_metrics:
                    cm = cls_metrics['confusion_matrix']
                    report_lines.append("混淆矩阵:")
                    report_lines.append(f"  真阳性 (TP): {cls_metrics.get('true_positive', 0)}")
                    report_lines.append(f"  真阴性 (TN): {cls_metrics.get('true_negative', 0)}")
                    report_lines.append(f"  假阳性 (FP): {cls_metrics.get('false_positive', 0)}")
                    report_lines.append(f"  假阴性 (FN): {cls_metrics.get('false_negative', 0)}")
                
                if 'specificity' in cls_metrics:
                    report_lines.append(f"特异性: {cls_metrics['specificity']:.4f}")
                if 'sensitivity' in cls_metrics:
                    report_lines.append(f"敏感度: {cls_metrics['sensitivity']:.4f}")
                if 'balanced_accuracy' in cls_metrics:
                    report_lines.append(f"平衡准确率: {cls_metrics['balanced_accuracy']:.4f}")
                if 'mcc' in cls_metrics:
                    report_lines.append(f"马修斯相关系数 (MCC): {cls_metrics['mcc']:.4f}")
                if 'cohen_kappa' in cls_metrics:
                    report_lines.append(f"Cohen's Kappa: {cls_metrics['cohen_kappa']:.4f}")
                if 'roc_auc' in cls_metrics:
                    report_lines.append(f"ROC AUC: {cls_metrics['roc_auc']:.4f}")
                if 'pr_auc' in cls_metrics:
                    report_lines.append(f"PR AUC: {cls_metrics['pr_auc']:.4f}")
                if 'best_threshold_youden' in cls_metrics:
                    report_lines.append(f"最佳阈值 (Youden's J): {cls_metrics['best_threshold_youden']:.4f}")
                if 'best_threshold_f1' in cls_metrics:
                    report_lines.append(f"最佳阈值 (F1): {cls_metrics['best_threshold_f1']:.4f}")
                
                report_lines.append("")
            
            if enhanced_metrics.regression_metrics:
                report_lines.append("回归指标:")
                report_lines.append("-" * 40)
                reg_metrics = enhanced_metrics.regression_metrics
                
                if 'r2_score' in reg_metrics:
                    report_lines.append(f"R²分数: {reg_metrics['r2_score']:.4f}")
                if 'adjusted_r2_score' in reg_metrics:
                    report_lines.append(f"调整R²分数: {reg_metrics['adjusted_r2_score']:.4f}")
                if 'rmse' in reg_metrics:
                    report_lines.append(f"均方根误差 (RMSE): {reg_metrics['rmse']:.4f}")
                if 'mape' in reg_metrics:
                    report_lines.append(f"均方百分比误差 (MAPE): {reg_metrics['mape']:.4f}%")
                if 'medae' in reg_metrics:
                    report_lines.append(f"中位数绝对误差 (MedAE): {reg_metrics['medae']:.4f}")
                
                report_lines.append("")
            
            # 综合评分
            report_lines.append("综合评分:")
            report_lines.append("-" * 40)
            report_lines.append(f"综合评分: {enhanced_performance.basic_performance.composite_score:.4f}")
            report_lines.append(f"可靠性评分: {enhanced_performance.basic_performance.reliability_score:.4f}")
            report_lines.append(f"样本数量: {enhanced_performance.basic_performance.sample_size}")
            report_lines.append("")
            
            report_lines.append("=" * 80)
            report_lines.append("报告结束")
            report_lines.append("=" * 80)
            
            report_text = "\n".join(report_lines)
            
            if save_path:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                logger.info(f"评估报告已保存到: {save_path}")
            
            return report_text
            
        except Exception as e:
            logger.error(f"生成评估报告失败: {e}")
            return ""
    
    def _get_default_enhanced_performance(self, model_type: str) -> EnhancedModelPerformance:
        """获取默认增强性能数据"""
        default_basic = self.base_evaluator._get_default_performance(model_type)
        default_enhanced_metrics = EnhancedModelMetrics(
            basic_metrics=default_basic.metrics,
            timestamp=datetime.now()
        )
        
        return EnhancedModelPerformance(
            model_type=model_type,
            basic_performance=default_basic,
            enhanced_metrics=default_enhanced_metrics,
            evaluation_timestamp=datetime.now()
        )
