"""
AI 选股模型可解释性增强模块

提供 SHAP、LIME 等可解释性工具，增强模型的可解释性
"""

from loguru import logger
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from pathlib import Path
import json


class ExplainabilityMethod(Enum):
    """可解释性方法"""
    FEATURE_IMPORTANCE = "feature_importance"
    SHAP = "shap"
    LIME = "lime"
    PERMUTATION = "permutation"
    PARTIAL_DEPENDENCE = "partial_dependence"


@dataclass
class FeatureExplanation:
    """特征解释"""
    feature_name: str
    feature_value: float
    importance: float
    direction: str  # "positive" 或 "negative"
    contribution: float  # 对预测的贡献
    description: str


@dataclass
class ModelExplanation:
    """模型解释结果"""
    method: str
    prediction: float
    base_value: float
    feature_explanations: List[FeatureExplanation]
    top_features: List[str]
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class ModelExplainer:
    """模型解释器
    
    提供多种可解释性方法，包括：
    - 特征重要性
    - SHAP 值
    - LIME 解释
    - 置换重要性
    - 偏依赖图
    """
    
    def __init__(self, model: Any, feature_names: List[str]):
        """初始化模型解释器
        
        Args:
            model: 要解释的模型
            feature_names: 特征名称列表
        """
        self._model = model
        self._feature_names = feature_names
        
        # 检查可用的可解释性库
        self._shap_available = self._check_shap()
        self._lime_available = self._check_lime()
        
        # 缓存解释结果
        self._explanation_cache: Dict[str, ModelExplanation] = {}
        
        logger.info(f"模型解释器初始化完成: SHAP={self._shap_available}, LIME={self._lime_available}")
    
    def _check_shap(self) -> bool:
        """检查 SHAP 是否可用"""
        try:
            import shap
            return True
        except ImportError:
            logger.warning("SHAP 库未安装，SHAP 解释功能不可用")
            return False
    
    def _check_lime(self) -> bool:
        """检查 LIME 是否可用"""
        try:
            import lime
            import lime.lime_tabular
            return True
        except ImportError:
            logger.warning("LIME 库未安装，LIME 解释功能不可用")
            return False
    
    def explain_with_feature_importance(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None
    ) -> ModelExplanation:
        """使用特征重要性解释模型
        
        Args:
            X: 特征数据
            y: 标签数据（可选）
            
        Returns:
            模型解释结果
        """
        try:
            feature_importance = None
            
            # 从模型中提取特征重要性
            if hasattr(self._model, 'feature_importances_'):
                feature_importance = self._model.feature_importances_
            elif hasattr(self._model, 'coef_'):
                feature_importance = np.abs(self._model.coef_).flatten()
            elif hasattr(self._model, 'get_feature_importance'):
                feature_importance = self._model.get_feature_importance()
            
            if feature_importance is None:
                logger.warning("无法从模型中提取特征重要性")
                return ModelExplanation(
                    method=ExplainabilityMethod.FEATURE_IMPORTANCE.value,
                    prediction=0.0,
                    base_value=0.0,
                    feature_explanations=[],
                    top_features=[],
                    summary="无法提取特征重要性"
                )
            
            # 创建特征解释
            feature_explanations = []
            for i, (name, importance) in enumerate(zip(self._feature_names, feature_importance)):
                direction = "positive" if importance > 0 else "negative"
                feature_explanations.append(FeatureExplanation(
                    feature_name=name,
                    feature_value=0.0,
                    importance=float(importance),
                    direction=direction,
                    contribution=float(importance),
                    description=f"特征重要性: {importance:.4f}"
                ))
            
            # 按重要性排序
            feature_explanations.sort(key=lambda x: abs(x.importance), reverse=True)
            top_features = [f.feature_name for f in feature_explanations[:10]]
            
            # 生成摘要
            summary = f"基于特征重要性的模型解释：最重要的特征是 {', '.join(top_features[:5])}"
            
            return ModelExplanation(
                method=ExplainabilityMethod.FEATURE_IMPORTANCE.value,
                prediction=0.0,
                base_value=0.0,
                feature_explanations=feature_explanations,
                top_features=top_features,
                summary=summary,
                metadata={'importance_values': feature_importance.tolist()}
            )
            
        except Exception as e:
            logger.error(f"特征重要性解释失败: {e}")
            return ModelExplanation(
                method=ExplainabilityMethod.FEATURE_IMPORTANCE.value,
                prediction=0.0,
                base_value=0.0,
                feature_explanations=[],
                top_features=[],
                summary=f"解释失败: {str(e)}"
            )
    
    def explain_with_shap(
        self,
        X: pd.DataFrame,
        background_samples: Optional[pd.DataFrame] = None,
        max_samples: int = 100
    ) -> ModelExplanation:
        """使用 SHAP 值解释模型
        
        Args:
            X: 特征数据
            background_samples: 背景样本（用于 TreeSHAP）
            max_samples: 最大样本数
            
        Returns:
            模型解释结果
        """
        if not self._shap_available:
            logger.warning("SHAP 不可用，回退到特征重要性")
            return self.explain_with_feature_importance(X)
        
        try:
            import shap
            
            # 选择解释器
            if hasattr(self._model, 'predict_proba'):
                predict_fn = self._model.predict_proba
            else:
                predict_fn = self._model.predict
            
            # 创建 SHAP 解释器
            if hasattr(self._model, 'estimators_') or 'forest' in str(type(self._model)).lower():
                # 树模型使用 TreeExplainer
                explainer = shap.TreeExplainer(self._model)
            else:
                # 其他模型使用 KernelExplainer
                if background_samples is None:
                    background_samples = shap.sample(X, max_samples)
                explainer = shap.KernelExplainer(predict_fn, background_samples)
            
            # 计算 SHAP 值
            shap_values = explainer.shap_values(X)
            
            # 如果是二分类，取正类的 SHAP 值
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            
            # 计算平均 SHAP 值
            mean_shap_values = np.mean(np.abs(shap_values), axis=0)
            
            # 创建特征解释
            feature_explanations = []
            for i, (name, shap_value) in enumerate(zip(self._feature_names, mean_shap_values)):
                direction = "positive" if shap_value > 0 else "negative"
                feature_explanations.append(FeatureExplanation(
                    feature_name=name,
                    feature_value=0.0,
                    importance=float(shap_value),
                    direction=direction,
                    contribution=float(shap_value),
                    description=f"SHAP 值: {shap_value:.4f}"
                ))
            
            # 按 SHAP 值排序
            feature_explanations.sort(key=lambda x: abs(x.importance), reverse=True)
            top_features = [f.feature_name for f in feature_explanations[:10]]
            
            # 生成摘要
            summary = f"基于 SHAP 值的模型解释：最重要的特征是 {', '.join(top_features[:5])}"
            
            return ModelExplanation(
                method=ExplainabilityMethod.SHAP.value,
                prediction=0.0,
                base_value=0.0,
                feature_explanations=feature_explanations,
                top_features=top_features,
                summary=summary,
                metadata={'shap_values': shap_values.tolist()}
            )
            
        except Exception as e:
            logger.error(f"SHAP 解释失败: {e}")
            return self.explain_with_feature_importance(X)
    
    def explain_with_lime(
        self,
        X: pd.DataFrame,
        instance: Optional[pd.Series] = None,
        num_features: int = 10
    ) -> ModelExplanation:
        """使用 LIME 解释模型
        
        Args:
            X: 特征数据
            instance: 要解释的实例
            num_features: 要解释的特征数量
            
        Returns:
            模型解释结果
        """
        if not self._lime_available:
            logger.warning("LIME 不可用，回退到特征重要性")
            return self.explain_with_feature_importance(X)
        
        try:
            from lime.lime_tabular import LimeTabularExplainer
            
            # 如果没有指定实例，使用第一个样本
            if instance is None:
                instance = X.iloc[0]
            
            # 创建 LIME 解释器
            if hasattr(self._model, 'predict_proba'):
                predict_fn = self._model.predict_proba
            else:
                predict_fn = self._model.predict
            
            explainer = LimeTabularExplainer(
                X.values,
                feature_names=self._feature_names,
                class_names=['不买入', '买入'],
                mode='classification'
            )
            
            # 解释实例
            exp = explainer.explain_instance(
                instance.values,
                predict_fn,
                num_features=num_features
            )
            
            # 创建特征解释
            feature_explanations = []
            for feature, importance in exp.as_list():
                direction = "positive" if importance > 0 else "negative"
                feature_explanations.append(FeatureExplanation(
                    feature_name=feature,
                    feature_value=0.0,
                    importance=float(importance),
                    direction=direction,
                    contribution=float(importance),
                    description=f"LIME 权重: {importance:.4f}"
                ))
            
            # 按 LIME 权重排序
            feature_explanations.sort(key=lambda x: abs(x.importance), reverse=True)
            top_features = [f.feature_name for f in feature_explanations[:10]]
            
            # 生成摘要
            summary = f"基于 LIME 的模型解释：最重要的特征是 {', '.join(top_features[:5])}"
            
            return ModelExplanation(
                method=ExplainabilityMethod.LIME.value,
                prediction=0.0,
                base_value=0.0,
                feature_explanations=feature_explanations,
                top_features=top_features,
                summary=summary,
                metadata={'lime_weights': [f.importance for f in feature_explanations]}
            )
            
        except Exception as e:
            logger.error(f"LIME 解释失败: {e}")
            return self.explain_with_feature_importance(X)
    
    def explain_with_permutation(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_repeats: int = 10
    ) -> ModelExplanation:
        """使用置换重要性解释模型
        
        Args:
            X: 特征数据
            y: 标签数据
            n_repeats: 重复次数
            
        Returns:
            模型解释结果
        """
        try:
            from sklearn.inspection import permutation_importance
            
            # 计算置换重要性
            result = permutation_importance(
                self._model, X, y,
                n_repeats=n_repeats,
                random_state=42
            )
            
            # 创建特征解释
            feature_explanations = []
            for i, name in enumerate(self._feature_names):
                importance = result.importances_mean[i]
                std = result.importances_std[i]
                direction = "positive" if importance > 0 else "negative"
                feature_explanations.append(FeatureExplanation(
                    feature_name=name,
                    feature_value=0.0,
                    importance=float(importance),
                    direction=direction,
                    contribution=float(importance),
                    description=f"置换重要性: {importance:.4f} (±{std:.4f})"
                ))
            
            # 按重要性排序
            feature_explanations.sort(key=lambda x: abs(x.importance), reverse=True)
            top_features = [f.feature_name for f in feature_explanations[:10]]
            
            # 生成摘要
            summary = f"基于置换重要性的模型解释：最重要的特征是 {', '.join(top_features[:5])}"
            
            return ModelExplanation(
                method=ExplainabilityMethod.PERMUTATION.value,
                prediction=0.0,
                base_value=0.0,
                feature_explanations=feature_explanations,
                top_features=top_features,
                summary=summary,
                metadata={
                    'importance_values': result.importances_mean.tolist(),
                    'importance_std': result.importances_std.tolist()
                }
            )
            
        except Exception as e:
            logger.error(f"置换重要性解释失败: {e}")
            return self.explain_with_feature_importance(X)
    
    def explain_instance(
        self,
        instance: pd.Series,
        method: str = ExplainabilityMethod.SHAP.value
    ) -> ModelExplanation:
        """解释单个实例
        
        Args:
            instance: 要解释的实例
            method: 解释方法
            
        Returns:
            模型解释结果
        """
        try:
            # 转换为 DataFrame
            X = pd.DataFrame([instance])
            
            # 根据方法选择解释器
            if method == ExplainabilityMethod.SHAP.value:
                return self.explain_with_shap(X)
            elif method == ExplainabilityMethod.LIME.value:
                return self.explain_with_lime(X, instance)
            elif method == ExplainabilityMethod.FEATURE_IMPORTANCE.value:
                return self.explain_with_feature_importance(X)
            else:
                logger.warning(f"未知的解释方法: {method}，使用特征重要性")
                return self.explain_with_feature_importance(X)
                
        except Exception as e:
            logger.error(f"实例解释失败: {e}")
            return ModelExplanation(
                method=method,
                prediction=0.0,
                base_value=0.0,
                feature_explanations=[],
                top_features=[],
                summary=f"解释失败: {str(e)}"
            )
    
    def get_feature_ranking(
        self,
        X: pd.DataFrame,
        y: Optional[pd.Series] = None,
        method: str = ExplainabilityMethod.FEATURE_IMPORTANCE.value
    ) -> List[Tuple[str, float]]:
        """获取特征排名
        
        Args:
            X: 特征数据
            y: 标签数据（可选）
            method: 解释方法
            
        Returns:
            特征排名列表 [(特征名, 重要性), ...]
        """
        explanation = self.explain_instance(X.iloc[0], method)
        
        ranking = [(f.feature_name, f.importance) for f in explanation.feature_explanations]
        ranking.sort(key=lambda x: abs(x[1]), reverse=True)
        
        return ranking
    
    def plot_feature_importance(
        self,
        explanation: ModelExplanation,
        save_path: Optional[str] = None
    ):
        """绘制特征重要性图
        
        Args:
            explanation: 模型解释结果
            save_path: 保存路径（可选）
        """
        try:
            import matplotlib.pyplot as plt
            
            # 提取前 20 个特征
            top_features = explanation.feature_explanations[:20]
            
            # 准备数据
            features = [f.feature_name for f in top_features]
            importances = [f.importance for f in top_features]
            
            # 绘制水平条形图
            plt.figure(figsize=(10, 8))
            plt.barh(range(len(features)), importances, align='center')
            plt.yticks(range(len(features)), features)
            plt.xlabel('重要性')
            plt.ylabel('特征')
            plt.title(f'特征重要性 ({explanation.method})')
            plt.tight_layout()
            
            # 保存或显示
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"特征重要性图已保存: {save_path}")
            else:
                plt.show()
            
            plt.close()
            
        except Exception as e:
            logger.error(f"绘制特征重要性图失败: {e}")
    
    def save_explanation(
        self,
        explanation: ModelExplanation,
        file_path: str
    ):
        """保存解释结果
        
        Args:
            explanation: 模型解释结果
            file_path: 保存路径
        """
        try:
            # 转换为可序列化的格式
            explanation_dict = {
                'method': explanation.method,
                'prediction': explanation.prediction,
                'base_value': explanation.base_value,
                'feature_explanations': [
                    {
                        'feature_name': f.feature_name,
                        'feature_value': f.feature_value,
                        'importance': f.importance,
                        'direction': f.direction,
                        'contribution': f.contribution,
                        'description': f.description
                    }
                    for f in explanation.feature_explanations
                ],
                'top_features': explanation.top_features,
                'summary': explanation.summary,
                'metadata': explanation.metadata
            }
            
            # 保存为 JSON
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(explanation_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"解释结果已保存: {file_path}")
            
        except Exception as e:
            logger.error(f"保存解释结果失败: {e}")


# 便捷函数
def create_model_explainer(
    model: Any,
    feature_names: List[str]
) -> ModelExplainer:
    """创建模型解释器
    
    Args:
        model: 要解释的模型
        feature_names: 特征名称列表
        
    Returns:
        模型解释器实例
    """
    return ModelExplainer(model, feature_names)


def explain_model(
    model: Any,
    X: pd.DataFrame,
    y: Optional[pd.Series] = None,
    method: str = ExplainabilityMethod.SHAP.value
) -> ModelExplanation:
    """解释模型（便捷函数）
    
    Args:
        model: 要解释的模型
        X: 特征数据
        y: 标签数据（可选）
        method: 解释方法
        
    Returns:
        模型解释结果
    """
    explainer = ModelExplainer(model, X.columns.tolist())
    return explainer.explain_instance(X.iloc[0], method)
