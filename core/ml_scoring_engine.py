#!/usr/bin/env python3
"""
机器学习评分引擎

基于机器学习的智能插件评分和预测系统
作者: FactorWeave-Quant团队
版本: 2.0 (专业化优化版本)
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pickle
from utils.safe_pickle import safe_load
import json
from pathlib import Path
import statistics
import math

from loguru import logger


class PredictionModel(Enum):
    """预测模型类型"""
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    MOVING_AVERAGE = "moving_average"
    BAYESIAN_INFERENCE = "bayesian_inference"
    MULTI_ARMED_BANDIT = "multi_armed_bandit"
    ENSEMBLE = "ensemble"


@dataclass
class FeatureVector:
    """特征向量"""
    plugin_id: str
    timestamp: datetime
    success_rate: float
    avg_response_time: float
    failure_count: int
    consecutive_failures: int
    time_since_last_failure: float  # 秒
    request_volume: int
    data_quality_score: float
    network_latency: float
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_io: float = 0.0
    hour_of_day: int = 0
    day_of_week: int = 0
    is_weekend: bool = False
    market_volatility: float = 0.0  # 市场波动性
    seasonal_factor: float = 1.0  # 季节性因子


@dataclass
class PredictionResult:
    """预测结果"""
    plugin_id: str
    predicted_score: float
    confidence_interval: Tuple[float, float]
    prediction_confidence: float
    model_used: PredictionModel
    feature_importance: Dict[str, float] = field(default_factory=dict)
    prediction_horizon: int = 300  # 预测时间窗口(秒)


@dataclass
class BayesianPrior:
    """贝叶斯先验"""
    alpha: float = 1.0  # 成功次数先验
    beta: float = 1.0   # 失败次数先验

    def update(self, successes: int, failures: int):
        """更新先验"""
        self.alpha += successes
        self.beta += failures

    @property
    def mean(self) -> float:
        """后验均值"""
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        """后验方差"""
        return (self.alpha * self.beta) / ((self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1))


class MultiArmedBandit:
    """多臂老虎机算法"""

    def __init__(self, epsilon: float = 0.1, decay_rate: float = 0.99, min_epsilon: float = 0.01):
        self.epsilon = epsilon
        self.decay_rate = decay_rate
        self.min_epsilon = min_epsilon
        self.arm_rewards: Dict[str, List[float]] = {}
        self.arm_counts: Dict[str, int] = {}
        self.total_plays = 0

    def select_arm(self, available_arms: List[str]) -> str:
        """选择臂"""
        current_epsilon = max(self.epsilon, self.min_epsilon)
        if np.random.random() < current_epsilon:
            # 探索：随机选择
            return np.random.choice(available_arms)
        else:
            # 利用：选择最优臂
            arm_values = {}
            for arm in available_arms:
                if arm in self.arm_rewards and self.arm_rewards[arm]:
                    arm_values[arm] = np.mean(self.arm_rewards[arm])
                else:
                    arm_values[arm] = 0.5  # 未知臂给予中等分数

            return max(arm_values.items(), key=lambda x: x[1])[0]

    def update_reward(self, arm: str, reward: float):
        """更新奖励"""
        if arm not in self.arm_rewards:
            self.arm_rewards[arm] = []
            self.arm_counts[arm] = 0

        self.arm_rewards[arm].append(reward)
        self.arm_counts[arm] += 1
        self.total_plays += 1

        # 应用衰减（保持不低于下限）
        self.epsilon = max(self.epsilon * self.decay_rate, self.min_epsilon)

        # 保持历史记录在合理范围内
        if len(self.arm_rewards[arm]) > 1000:
            self.arm_rewards[arm] = self.arm_rewards[arm][-500:]


class MLScoringEngine:
    """机器学习评分引擎"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 特征历史数据
        self.feature_history: Dict[str, List[FeatureVector]] = {}

        # 贝叶斯先验
        self.bayesian_priors: Dict[str, BayesianPrior] = {}

        # 多臂老虎机
        self.bandit = MultiArmedBandit(
            epsilon=self.config.get('bandit_epsilon', 0.1),
            decay_rate=self.config.get('bandit_decay', 0.99),
            min_epsilon=self.config.get('bandit_min_epsilon', 0.01)
        )

        # 模型参数
        self.smoothing_alpha = self.config.get('smoothing_alpha', 0.3)
        self.ma_window = self.config.get('ma_window', 10)
        self.feature_weights = self.config.get('feature_weights', {
            'success_rate': 0.25,
            'avg_response_time': 0.20,
            'failure_count': 0.15,
            'time_since_last_failure': 0.10,
            'data_quality_score': 0.10,
            'network_latency': 0.08,
            'request_volume': 0.07,
            'seasonal_factor': 0.05
        })

        # 数据保存路径
        self.model_save_path = Path(self.config.get('model_save_path', 'models'))
        self.model_save_path.mkdir(exist_ok=True)

        # 加载已保存的模型
        self._load_models()

        logger.info("机器学习评分引擎初始化完成")

    def add_feature_observation(self, plugin_id: str, features: FeatureVector):
        """添加特征观测"""
        if plugin_id not in self.feature_history:
            self.feature_history[plugin_id] = []

        self.feature_history[plugin_id].append(features)

        # 保持历史数据在合理范围内
        max_history = self.config.get('max_history_size', 1000)
        if len(self.feature_history[plugin_id]) > max_history:
            self.feature_history[plugin_id] = self.feature_history[plugin_id][-max_history//2:]

        # 更新贝叶斯先验
        self._update_bayesian_prior(plugin_id, features)

        logger.debug(f" 插件 {plugin_id} 特征观测已添加")

    def predict_plugin_score(
        self,
        plugin_id: str,
        model: PredictionModel = PredictionModel.ENSEMBLE
    ) -> PredictionResult:
        """预测插件分数"""

        if plugin_id not in self.feature_history or not self.feature_history[plugin_id]:
            # 没有历史数据，返回默认预测
            return PredictionResult(
                plugin_id=plugin_id,
                predicted_score=0.5,
                confidence_interval=(0.3, 0.7),
                prediction_confidence=0.3,
                model_used=model
            )

        if model == PredictionModel.EXPONENTIAL_SMOOTHING:
            return self._exponential_smoothing_prediction(plugin_id)
        elif model == PredictionModel.MOVING_AVERAGE:
            return self._moving_average_prediction(plugin_id)
        elif model == PredictionModel.BAYESIAN_INFERENCE:
            return self._bayesian_prediction(plugin_id)
        elif model == PredictionModel.MULTI_ARMED_BANDIT:
            return self._bandit_prediction(plugin_id)
        elif model == PredictionModel.ENSEMBLE:
            return self._ensemble_prediction(plugin_id)
        else:
            return self._ensemble_prediction(plugin_id)

    def _exponential_smoothing_prediction(self, plugin_id: str) -> PredictionResult:
        """指数平滑预测"""
        history = self.feature_history[plugin_id]

        if len(history) < 2:
            return PredictionResult(
                plugin_id=plugin_id,
                predicted_score=0.5,
                confidence_interval=(0.3, 0.7),
                prediction_confidence=0.3,
                model_used=PredictionModel.EXPONENTIAL_SMOOTHING
            )

        # 计算综合分数历史
        scores = [self._calculate_composite_score(f) for f in history]

        # 指数平滑
        smoothed_score = scores[0]
        for score in scores[1:]:
            smoothed_score = self.smoothing_alpha * score + (1 - self.smoothing_alpha) * smoothed_score

        # 计算预测区间
        recent_scores = scores[-min(10, len(scores)):]
        std_dev = np.std(recent_scores) if len(recent_scores) > 1 else 0.1
        confidence_interval = (
            max(0.0, smoothed_score - 1.96 * std_dev),
            min(1.0, smoothed_score + 1.96 * std_dev)
        )

        # 计算置信度
        prediction_confidence = max(0.1, 1.0 - std_dev)

        return PredictionResult(
            plugin_id=plugin_id,
            predicted_score=smoothed_score,
            confidence_interval=confidence_interval,
            prediction_confidence=prediction_confidence,
            model_used=PredictionModel.EXPONENTIAL_SMOOTHING
        )

    def _moving_average_prediction(self, plugin_id: str) -> PredictionResult:
        """移动平均预测"""
        history = self.feature_history[plugin_id]

        if not history:
            return PredictionResult(
                plugin_id=plugin_id,
                predicted_score=0.5,
                confidence_interval=(0.3, 0.7),
                prediction_confidence=0.3,
                model_used=PredictionModel.MOVING_AVERAGE
            )

        # 计算综合分数历史
        scores = [self._calculate_composite_score(f) for f in history]

        # 移动平均
        window_size = min(self.ma_window, len(scores))
        recent_scores = scores[-window_size:]
        predicted_score = np.mean(recent_scores)

        # 计算预测区间
        std_dev = np.std(recent_scores) if len(recent_scores) > 1 else 0.1
        confidence_interval = (
            max(0.0, predicted_score - 1.96 * std_dev),
            min(1.0, predicted_score + 1.96 * std_dev)
        )

        # 计算置信度
        prediction_confidence = max(0.1, 1.0 - std_dev)

        return PredictionResult(
            plugin_id=plugin_id,
            predicted_score=predicted_score,
            confidence_interval=confidence_interval,
            prediction_confidence=prediction_confidence,
            model_used=PredictionModel.MOVING_AVERAGE
        )

    def _bayesian_prediction(self, plugin_id: str) -> PredictionResult:
        """贝叶斯预测"""
        if plugin_id not in self.bayesian_priors:
            self.bayesian_priors[plugin_id] = BayesianPrior()

        prior = self.bayesian_priors[plugin_id]
        predicted_score = prior.mean
        variance = prior.variance

        # 计算置信区间
        std_dev = math.sqrt(variance)
        confidence_interval = (
            max(0.0, predicted_score - 1.96 * std_dev),
            min(1.0, predicted_score + 1.96 * std_dev)
        )

        # 计算置信度（基于观测数量）
        total_observations = prior.alpha + prior.beta - 2  # 减去初始先验
        prediction_confidence = min(0.95, total_observations / (total_observations + 10))

        return PredictionResult(
            plugin_id=plugin_id,
            predicted_score=predicted_score,
            confidence_interval=confidence_interval,
            prediction_confidence=prediction_confidence,
            model_used=PredictionModel.BAYESIAN_INFERENCE
        )

    def _bandit_prediction(self, plugin_id: str) -> PredictionResult:
        """多臂老虎机预测"""
        if plugin_id in self.bandit.arm_rewards and self.bandit.arm_rewards[plugin_id]:
            rewards = self.bandit.arm_rewards[plugin_id]
            predicted_score = np.mean(rewards)
            std_dev = np.std(rewards) if len(rewards) > 1 else 0.1

            confidence_interval = (
                max(0.0, predicted_score - 1.96 * std_dev),
                min(1.0, predicted_score + 1.96 * std_dev)
            )

            # 基于观测数量的置信度
            prediction_confidence = min(0.95, len(rewards) / (len(rewards) + 5))
        else:
            predicted_score = 0.5
            confidence_interval = (0.2, 0.8)
            prediction_confidence = 0.2

        return PredictionResult(
            plugin_id=plugin_id,
            predicted_score=predicted_score,
            confidence_interval=confidence_interval,
            prediction_confidence=prediction_confidence,
            model_used=PredictionModel.MULTI_ARMED_BANDIT
        )

    def _ensemble_prediction(self, plugin_id: str) -> PredictionResult:
        """集成预测"""
        # 获取各个模型的预测
        predictions = [
            self._exponential_smoothing_prediction(plugin_id),
            self._moving_average_prediction(plugin_id),
            self._bayesian_prediction(plugin_id),
            self._bandit_prediction(plugin_id)
        ]

        # 加权平均（基于置信度）
        total_weight = sum(p.prediction_confidence for p in predictions)
        if total_weight == 0:
            weighted_score = 0.5
            avg_confidence = 0.3
        else:
            weighted_score = sum(p.predicted_score * p.prediction_confidence for p in predictions) / total_weight
            avg_confidence = total_weight / len(predictions)

        # 计算集成置信区间
        lower_bounds = [p.confidence_interval[0] for p in predictions]
        upper_bounds = [p.confidence_interval[1] for p in predictions]
        confidence_interval = (
            np.mean(lower_bounds),
            np.mean(upper_bounds)
        )

        # 计算特征重要性
        feature_importance = self._calculate_feature_importance(plugin_id)

        return PredictionResult(
            plugin_id=plugin_id,
            predicted_score=weighted_score,
            confidence_interval=confidence_interval,
            prediction_confidence=avg_confidence,
            model_used=PredictionModel.ENSEMBLE,
            feature_importance=feature_importance
        )

    def _calculate_composite_score(self, features: FeatureVector) -> float:
        """计算综合分数"""
        score = 0.0

        # 成功率分数
        score += features.success_rate * self.feature_weights.get('success_rate', 0.25)

        # 响应时间分数（越低越好）
        response_score = max(0.0, 1.0 - features.avg_response_time / 10.0)
        score += response_score * self.feature_weights.get('avg_response_time', 0.20)

        # 失败计数分数（越低越好）
        failure_score = max(0.0, 1.0 - features.failure_count / 100.0)
        score += failure_score * self.feature_weights.get('failure_count', 0.15)

        # 距离上次失败时间分数（越长越好）
        time_score = min(1.0, features.time_since_last_failure / 3600.0)  # 1小时为满分
        score += time_score * self.feature_weights.get('time_since_last_failure', 0.10)

        # 数据质量分数
        score += features.data_quality_score * self.feature_weights.get('data_quality_score', 0.10)

        # 网络延迟分数（越低越好）
        latency_score = max(0.0, 1.0 - features.network_latency / 5000.0)  # 5秒为基准
        score += latency_score * self.feature_weights.get('network_latency', 0.08)

        # 请求量分数（适中为好）
        volume_score = 1.0 - abs(features.request_volume - 50) / 50.0  # 50为理想值
        volume_score = max(0.0, volume_score)
        score += volume_score * self.feature_weights.get('request_volume', 0.07)

        # 季节性因子
        score *= features.seasonal_factor

        return max(0.0, min(1.0, score))

    def _calculate_feature_importance(self, plugin_id: str) -> Dict[str, float]:
        """计算特征重要性"""
        if plugin_id not in self.feature_history or len(self.feature_history[plugin_id]) < 5:
            return {}

        history = self.feature_history[plugin_id]
        scores = [self._calculate_composite_score(f) for f in history]

        # 计算各特征与分数的相关性
        feature_importance = {}

        try:
            # 提取特征数据
            success_rates = [f.success_rate for f in history]
            response_times = [f.avg_response_time for f in history]
            failure_counts = [f.failure_count for f in history]

            # 计算相关系数
            if len(set(success_rates)) > 1:
                feature_importance['success_rate'] = abs(np.corrcoef(success_rates, scores)[0, 1])

            if len(set(response_times)) > 1:
                feature_importance['avg_response_time'] = abs(np.corrcoef(response_times, scores)[0, 1])

            if len(set(failure_counts)) > 1:
                feature_importance['failure_count'] = abs(np.corrcoef(failure_counts, scores)[0, 1])

        except Exception as e:
            logger.warning(f"计算特征重要性时出错: {e}")

        return feature_importance

    def _update_bayesian_prior(self, plugin_id: str, features: FeatureVector):
        """更新贝叶斯先验"""
        if plugin_id not in self.bayesian_priors:
            self.bayesian_priors[plugin_id] = BayesianPrior()

        # 基于成功率更新先验
        if features.success_rate > 0.8:
            self.bayesian_priors[plugin_id].update(1, 0)
        elif features.success_rate < 0.5:
            self.bayesian_priors[plugin_id].update(0, 1)

    def update_bandit_reward(self, plugin_id: str, reward: float):
        """更新多臂老虎机奖励"""
        self.bandit.update_reward(plugin_id, reward)

    def select_plugin_with_bandit(self, available_plugins: List[str]) -> str:
        """使用多臂老虎机选择插件"""
        return self.bandit.select_arm(available_plugins)

    def get_plugin_insights(self, plugin_id: str) -> Dict[str, Any]:
        """获取插件洞察"""
        if plugin_id not in self.feature_history:
            return {"error": "没有历史数据"}

        history = self.feature_history[plugin_id]
        if not history:
            return {"error": "历史数据为空"}

        # 计算趋势
        recent_scores = [self._calculate_composite_score(f) for f in history[-10:]]
        trend = "stable"
        if len(recent_scores) >= 3:
            if recent_scores[-1] > recent_scores[-3] * 1.1:
                trend = "improving"
            elif recent_scores[-1] < recent_scores[-3] * 0.9:
                trend = "declining"

        # 计算统计信息
        all_scores = [self._calculate_composite_score(f) for f in history]

        insights = {
            "plugin_id": plugin_id,
            "total_observations": len(history),
            "current_score": recent_scores[-1] if recent_scores else 0.5,
            "average_score": np.mean(all_scores),
            "score_std": np.std(all_scores),
            "trend": trend,
            "best_score": max(all_scores),
            "worst_score": min(all_scores),
            "score_stability": 1.0 - (np.std(all_scores) if all_scores else 0.5),
            "recent_performance": {
                "last_7_days_avg": np.mean(recent_scores) if recent_scores else 0.5,
                "improvement_rate": (recent_scores[-1] - recent_scores[0]) / len(recent_scores) if len(recent_scores) > 1 else 0.0
            }
        }

        return insights

    def _save_models(self):
        """保存模型"""
        try:
            # 保存贝叶斯先验
            bayesian_file = self.model_save_path / 'bayesian_priors.pkl'
            with open(bayesian_file, 'wb') as f:
                pickle.dump(self.bayesian_priors, f)

            # 保存多臂老虎机
            bandit_file = self.model_save_path / 'bandit_model.pkl'
            with open(bandit_file, 'wb') as f:
                pickle.dump(self.bandit, f)

            # 保存特征历史（最近的数据）
            history_file = self.model_save_path / 'feature_history.json'
            simplified_history = {}
            for plugin_id, features in self.feature_history.items():
                # 只保存最近100条记录
                recent_features = features[-100:] if len(features) > 100 else features
                simplified_history[plugin_id] = [
                    {
                        'timestamp': f.timestamp.isoformat(),
                        'success_rate': f.success_rate,
                        'avg_response_time': f.avg_response_time,
                        'failure_count': f.failure_count
                    }
                    for f in recent_features
                ]

            with open(history_file, 'w') as f:
                json.dump(simplified_history, f, indent=2)

            logger.info("机器学习模型已保存")

        except Exception as e:
            logger.error(f"保存模型失败: {e}")

    def _load_models(self):
        """加载模型"""
        try:
            # 加载贝叶斯先验
            bayesian_file = self.model_save_path / 'bayesian_priors.pkl'
            if bayesian_file.exists():
                with open(bayesian_file, 'rb') as f:
                    self.bayesian_priors = safe_load(f)
                logger.info("贝叶斯先验模型已加载")

            # 加载多臂老虎机
            bandit_file = self.model_save_path / 'bandit_model.pkl'
            if bandit_file.exists():
                with open(bandit_file, 'rb') as f:
                    self.bandit = safe_load(f)
                logger.info("多臂老虎机模型已加载")

        except Exception as e:
            logger.warning(f"加载模型失败: {e}")

    def shutdown(self):
        """关闭引擎"""
        self._save_models()
        logger.info("机器学习评分引擎已关闭")
