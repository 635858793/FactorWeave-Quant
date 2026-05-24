from loguru import logger
#!/usr/bin/env python3
"""
风险评估模块

提供全面的风险评估功能，包括：
- 市场风险评估
- 信用风险评估
- 流动性风险评估
- 操作风险评估
- 综合风险评估
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from core.database.unified_sqlite_access import UnifiedSQLiteAccess
import json
from dataclasses import dataclass
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"           # 低风险
    MEDIUM = "medium"     # 中等风险
    HIGH = "high"         # 高风险
    EXTREME = "extreme"   # 极高风险

class RiskType(Enum):
    """风险类型"""
    MARKET = "market"         # 市场风险
    CREDIT = "credit"         # 信用风险
    LIQUIDITY = "liquidity"   # 流动性风险
    OPERATIONAL = "operational"  # 操作风险
    CONCENTRATION = "concentration"  # 集中度风险

@dataclass
class RiskMetric:
    """风险指标数据类"""
    name: str
    value: float
    level: RiskLevel
    type: RiskType
    description: str
    threshold: Optional[float] = None
    recommendation: Optional[str] = None

class RiskEvaluator:
    """风险评估器"""

    def __init__(self, db_path: str = 'data/factorweave_system.sqlite'):
        """
        初始化风险评估器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.risk_thresholds = self._load_risk_thresholds()

    def _load_risk_thresholds(self) -> Dict[str, Dict[str, float]]:
        """加载风险阈值配置"""
        return {
            'var_95': {'low': 0.02, 'medium': 0.05, 'high': 0.1},
            'var_99': {'low': 0.03, 'medium': 0.08, 'high': 0.15},
            'max_drawdown': {'low': 0.05, 'medium': 0.15, 'high': 0.3},
            'volatility': {'low': 0.15, 'medium': 0.25, 'high': 0.4},
            'beta': {'low': 0.8, 'medium': 1.2, 'high': 1.8},
            'concentration': {'low': 0.2, 'medium': 0.4, 'high': 0.6},
            'liquidity_ratio': {'low': 0.1, 'medium': 0.05, 'high': 0.02}
        }

    def evaluate_market_risk(self,
                             returns: pd.Series,
                             benchmark_returns: Optional[pd.Series] = None,
                             confidence_levels: List[float] = [0.95, 0.99]) -> Dict[str, RiskMetric]:
        """
        评估市场风险

        Args:
            returns: 收益率序列
            benchmark_returns: 基准收益率序列
            confidence_levels: 置信水平列表

        Returns:
            市场风险指标字典
        """
        metrics = {}

        # VaR计算
        for confidence in confidence_levels:
            var_value = np.percentile(returns, (1 - confidence) * 100)
            var_key = f'var_{int(confidence * 100)}'

            level = self._determine_risk_level(
                abs(var_value), self.risk_thresholds[var_key])

            metrics[var_key] = RiskMetric(
                name=f"VaR ({confidence:.0%})",
                value=var_value,
                level=level,
                type=RiskType.MARKET,
                description=f"{confidence:.0%}置信水平下的在险价值",
                threshold=self.risk_thresholds[var_key]['high'],
                recommendation=self._get_var_recommendation(level)
            )

        # CVaR计算
        for confidence in confidence_levels:
            var_percentile = (1 - confidence) * 100
            var_value = abs(np.percentile(returns, var_percentile))
            cvar_value = returns[returns <= -var_value].mean()

            cvar_key = f'cvar_{int(confidence * 100)}'

            level = self._determine_risk_level(
                abs(cvar_value), self.risk_thresholds[f'var_{int(confidence * 100)}'])

            metrics[cvar_key] = RiskMetric(
                name=f"CVaR ({confidence:.0%})",
                value=cvar_value,
                level=level,
                type=RiskType.MARKET,
                description=f"{confidence:.0%}置信水平下的条件在险价值",
                threshold=self.risk_thresholds[f'var_{int(confidence * 100)}']['high'],
                recommendation=self._get_var_recommendation(level)
            )

        # 波动率
        volatility = returns.std() * np.sqrt(252)
        level = self._determine_risk_level(
            volatility, self.risk_thresholds['volatility'])

        metrics['volatility'] = RiskMetric(
            name="年化波动率",
            value=volatility,
            level=level,
            type=RiskType.MARKET,
            description="收益率的年化标准差",
            threshold=self.risk_thresholds['volatility']['high'],
            recommendation=self._get_volatility_recommendation(level)
        )

        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(returns)
        level = self._determine_risk_level(
            abs(max_drawdown), self.risk_thresholds['max_drawdown'])

        metrics['max_drawdown'] = RiskMetric(
            name="最大回撤",
            value=max_drawdown,
            level=level,
            type=RiskType.MARKET,
            description="历史最大回撤幅度",
            threshold=self.risk_thresholds['max_drawdown']['high'],
            recommendation=self._get_drawdown_recommendation(level)
        )

        # Beta系数（如果有基准）
        if benchmark_returns is not None and len(benchmark_returns) == len(returns):
            beta = self._calculate_beta(returns, benchmark_returns)
            level = self._determine_beta_risk_level(beta)

            metrics['beta'] = RiskMetric(
                name="Beta系数",
                value=beta,
                level=level,
                type=RiskType.MARKET,
                description="相对基准的系统性风险",
                threshold=self.risk_thresholds['beta']['high'],
                recommendation=self._get_beta_recommendation(level, beta)
            )

        return metrics

    def evaluate_concentration_risk(self,
                                    portfolio_weights: Dict[str, float]) -> Dict[str, RiskMetric]:
        """
        评估集中度风险

        Args:
            portfolio_weights: 投资组合权重字典

        Returns:
            集中度风险指标字典
        """
        metrics = {}

        if not portfolio_weights:
            return metrics

        weights = np.array(list(portfolio_weights.values()))

        # 赫芬达尔指数
        hhi = np.sum(weights ** 2)
        level = self._determine_risk_level(
            hhi, self.risk_thresholds['concentration'])

        metrics['hhi'] = RiskMetric(
            name="赫芬达尔指数",
            value=hhi,
            level=level,
            type=RiskType.CONCENTRATION,
            description="投资组合集中度指标",
            threshold=self.risk_thresholds['concentration']['high'],
            recommendation=self._get_concentration_recommendation(level)
        )

        # 最大权重
        max_weight = np.max(weights)
        level = self._determine_risk_level(
            max_weight, self.risk_thresholds['concentration'])

        metrics['max_weight'] = RiskMetric(
            name="最大持仓权重",
            value=max_weight,
            level=level,
            type=RiskType.CONCENTRATION,
            description="单一资产最大权重",
            threshold=self.risk_thresholds['concentration']['high'],
            recommendation=self._get_max_weight_recommendation(level)
        )

        # 有效资产数量
        effective_assets = 1 / hhi

        metrics['effective_assets'] = RiskMetric(
            name="有效资产数量",
            value=effective_assets,
            level=RiskLevel.LOW if effective_assets > 10 else RiskLevel.MEDIUM if effective_assets > 5 else RiskLevel.HIGH,
            type=RiskType.CONCENTRATION,
            description="等权重下的有效资产数量",
            recommendation="建议保持充分的资产分散化"
        )

        return metrics

    def evaluate_liquidity_risk(self,
                                trading_volumes: pd.Series,
                                market_cap: Optional[float] = None) -> Dict[str, RiskMetric]:
        """
        评估流动性风险

        Args:
            trading_volumes: 交易量序列
            market_cap: 市值

        Returns:
            流动性风险指标字典
        """
        metrics = {}

        if trading_volumes.empty:
            return metrics

        # 平均日交易量
        avg_volume = trading_volumes.mean()

        # 交易量波动率
        volume_volatility = trading_volumes.std() / avg_volume if avg_volume > 0 else 0

        # 流动性比率（基于交易量稳定性）
        liquidity_ratio = 1 / \
            (1 + volume_volatility) if volume_volatility > 0 else 1
        level = self._determine_risk_level(
            1 - liquidity_ratio, self.risk_thresholds['liquidity_ratio'])

        metrics['liquidity_ratio'] = RiskMetric(
            name="流动性比率",
            value=liquidity_ratio,
            level=level,
            type=RiskType.LIQUIDITY,
            description="基于交易量稳定性的流动性指标",
            threshold=self.risk_thresholds['liquidity_ratio']['low'],
            recommendation=self._get_liquidity_recommendation(level)
        )

        # 零交易日比例
        zero_volume_ratio = (trading_volumes == 0).mean()
        level = RiskLevel.LOW if zero_volume_ratio < 0.05 else RiskLevel.MEDIUM if zero_volume_ratio < 0.15 else RiskLevel.HIGH

        metrics['zero_volume_ratio'] = RiskMetric(
            name="零交易日比例",
            value=zero_volume_ratio,
            level=level,
            type=RiskType.LIQUIDITY,
            description="无交易日占比",
            recommendation=self._get_zero_volume_recommendation(level)
        )

        return metrics

    def evaluate_operational_risk(self,
                                  system_metrics: Optional[Dict[str, float]] = None) -> Dict[str, RiskMetric]:
        """
        评估操作风险

        Args:
            system_metrics: 系统性能指标

        Returns:
            操作风险指标字典
        """
        metrics = {}

        if system_metrics:
            # 系统稳定性风险
            if 'uptime' in system_metrics:
                uptime = system_metrics['uptime']
                level = RiskLevel.LOW if uptime > 0.99 else RiskLevel.MEDIUM if uptime > 0.95 else RiskLevel.HIGH

                metrics['system_stability'] = RiskMetric(
                    name="系统稳定性",
                    value=uptime,
                    level=level,
                    type=RiskType.OPERATIONAL,
                    description="系统正常运行时间比例",
                    recommendation=self._get_stability_recommendation(level)
                )

            # 数据质量风险
            if 'data_quality' in system_metrics:
                data_quality = system_metrics['data_quality']
                level = RiskLevel.LOW if data_quality > 0.98 else RiskLevel.MEDIUM if data_quality > 0.95 else RiskLevel.HIGH

                metrics['data_quality'] = RiskMetric(
                    name="数据质量",
                    value=data_quality,
                    level=level,
                    type=RiskType.OPERATIONAL,
                    description="数据完整性和准确性指标",
                    recommendation=self._get_data_quality_recommendation(level)
                )

        # 模型风险（基于历史表现）
        try:
            model_performance = self._evaluate_model_performance()
            if model_performance:
                level = RiskLevel.LOW if model_performance > 0.8 else RiskLevel.MEDIUM if model_performance > 0.6 else RiskLevel.HIGH

                metrics['model_risk'] = RiskMetric(
                    name="模型风险",
                    value=1 - model_performance,
                    level=level,
                    type=RiskType.OPERATIONAL,
                    description="模型预测准确性风险",
                    recommendation=self._get_model_risk_recommendation(level)
                )
        except Exception as e:
            logger.info(f"评估模型风险失败: {e}")

        return metrics

    def generate_comprehensive_risk_report(self,
                                           returns: Optional[pd.Series] = None,
                                           portfolio_weights: Optional[Dict[str,
                                                                            float]] = None,
                                           trading_volumes: Optional[pd.Series] = None,
                                           system_metrics: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """
        生成综合风险报告

        Args:
            returns: 收益率序列
            portfolio_weights: 投资组合权重
            trading_volumes: 交易量序列
            system_metrics: 系统性能指标

        Returns:
            综合风险报告
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'risk_metrics': {},
            'risk_summary': {},
            'recommendations': [],
            'overall_risk_level': RiskLevel.LOW.value
        }

        all_metrics = {}

        # 市场风险评估
        if returns is not None and not returns.empty:
            market_risk = self.evaluate_market_risk(returns)
            all_metrics.update(market_risk)
            report['risk_metrics']['market'] = {
                k: self._metric_to_dict(v) for k, v in market_risk.items()}

        # 集中度风险评估
        if portfolio_weights:
            concentration_risk = self.evaluate_concentration_risk(
                portfolio_weights)
            all_metrics.update(concentration_risk)
            report['risk_metrics']['concentration'] = {
                k: self._metric_to_dict(v) for k, v in concentration_risk.items()}

        # 流动性风险评估
        if trading_volumes is not None and not trading_volumes.empty:
            liquidity_risk = self.evaluate_liquidity_risk(trading_volumes)
            all_metrics.update(liquidity_risk)
            report['risk_metrics']['liquidity'] = {
                k: self._metric_to_dict(v) for k, v in liquidity_risk.items()}

        # 操作风险评估
        operational_risk = self.evaluate_operational_risk(system_metrics)
        all_metrics.update(operational_risk)
        report['risk_metrics']['operational'] = {
            k: self._metric_to_dict(v) for k, v in operational_risk.items()}

        # 生成风险总结
        report['risk_summary'] = self._generate_risk_summary(all_metrics)
        report['recommendations'] = self._generate_risk_recommendations(
            all_metrics)
        report['overall_risk_level'] = self._calculate_overall_risk_level(
            all_metrics)

        return report

    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """计算最大回撤"""
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        return drawdown.min()

    def _calculate_beta(self, returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """计算Beta系数"""
        covariance = np.cov(returns, benchmark_returns)[0, 1]
        benchmark_variance = np.var(benchmark_returns)
        return covariance / benchmark_variance if benchmark_variance > 0 else 0

    def _determine_risk_level(self, value: float, thresholds: Dict[str, float]) -> RiskLevel:
        """确定风险等级"""
        if value <= thresholds['low']:
            return RiskLevel.LOW
        elif value <= thresholds['medium']:
            return RiskLevel.MEDIUM
        elif value <= thresholds['high']:
            return RiskLevel.HIGH
        else:
            return RiskLevel.EXTREME

    def _determine_beta_risk_level(self, beta: float) -> RiskLevel:
        """确定Beta风险等级"""
        abs_beta = abs(beta - 1)
        if abs_beta <= 0.2:
            return RiskLevel.LOW
        elif abs_beta <= 0.5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.HIGH

    def _evaluate_model_performance(self) -> Optional[float]:
        """评估模型性能"""
        try:
            db = UnifiedSQLiteAccess.get_instance(self.db_path)
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 查询最近的模型性能数据
                cursor.execute("""
                    SELECT AVG(CASE WHEN is_successful = 1 THEN 1.0 ELSE 0.0 END) as success_rate
                    FROM pattern_history 
                    WHERE trigger_date >= date('now', '-30 days')
                """)

                result = cursor.fetchone()

                return result[0] if result and result[0] is not None else None

        except Exception:
            return None

    def _metric_to_dict(self, metric: RiskMetric) -> Dict[str, Any]:
        """将风险指标转换为字典"""
        return {
            'name': metric.name,
            'value': metric.value,
            'level': metric.level.value,
            'type': metric.type.value,
            'description': metric.description,
            'threshold': metric.threshold,
            'recommendation': metric.recommendation
        }

    def _generate_risk_summary(self, metrics: Dict[str, RiskMetric]) -> Dict[str, Any]:
        """生成风险总结"""
        summary = {
            'total_metrics': len(metrics),
            'risk_distribution': {level.value: 0 for level in RiskLevel},
            'high_risk_metrics': [],
            'key_concerns': []
        }

        for name, metric in metrics.items():
            summary['risk_distribution'][metric.level.value] += 1

            if metric.level in [RiskLevel.HIGH, RiskLevel.EXTREME]:
                summary['high_risk_metrics'].append({
                    'name': metric.name,
                    'value': metric.value,
                    'level': metric.level.value
                })

        return summary

    def _generate_risk_recommendations(self, metrics: Dict[str, RiskMetric]) -> List[str]:
        """生成风险建议"""
        recommendations = []

        for metric in metrics.values():
            if metric.level in [RiskLevel.HIGH, RiskLevel.EXTREME] and metric.recommendation:
                recommendations.append(
                    f"{metric.name}: {metric.recommendation}")

        # 通用建议
        high_risk_count = sum(1 for m in metrics.values() if m.level in [
                              RiskLevel.HIGH, RiskLevel.EXTREME])
        if high_risk_count > len(metrics) * 0.3:
            recommendations.append("整体风险水平较高，建议全面审查风险管理策略")

        return recommendations

    def _calculate_overall_risk_level(self, metrics: Dict[str, RiskMetric]) -> str:
        """计算整体风险等级"""
        if not metrics:
            return RiskLevel.LOW.value

        risk_scores = {
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.EXTREME: 4
        }

        total_score = sum(risk_scores[metric.level]
                          for metric in metrics.values())
        avg_score = total_score / len(metrics)

        if avg_score <= 1.5:
            return RiskLevel.LOW.value
        elif avg_score <= 2.5:
            return RiskLevel.MEDIUM.value
        elif avg_score <= 3.5:
            return RiskLevel.HIGH.value
        else:
            return RiskLevel.EXTREME.value

    # 建议生成方法
    def _get_var_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "VaR水平正常，继续监控",
            RiskLevel.MEDIUM: "VaR水平偏高，建议适当降低仓位",
            RiskLevel.HIGH: "VaR水平过高，建议大幅降低风险敞口",
            RiskLevel.EXTREME: "VaR水平极高，建议立即减仓或停止交易"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_volatility_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "波动率正常，风险可控",
            RiskLevel.MEDIUM: "波动率偏高，建议加强风险管理",
            RiskLevel.HIGH: "波动率过高，建议降低仓位或使用对冲策略",
            RiskLevel.EXTREME: "波动率极高，建议暂停交易"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_drawdown_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "回撤控制良好",
            RiskLevel.MEDIUM: "回撤偏大，建议优化止损策略",
            RiskLevel.HIGH: "回撤过大，建议重新评估策略有效性",
            RiskLevel.EXTREME: "回撤极大，建议暂停策略并进行全面检讨"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_beta_recommendation(self, level: RiskLevel, beta: float) -> str:
        if beta > 1.5:
            return "Beta过高，投资组合系统性风险较大，建议降低高Beta资产配置"
        elif beta < 0.5:
            return "Beta过低，可能错失市场机会，建议适当增加市场敞口"
        else:
            return "Beta水平合理，系统性风险可控"

    def _get_concentration_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "投资组合分散度良好",
            RiskLevel.MEDIUM: "投资组合集中度偏高，建议增加分散化",
            RiskLevel.HIGH: "投资组合过度集中，建议大幅增加分散化",
            RiskLevel.EXTREME: "投资组合极度集中，存在重大风险"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_max_weight_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "单一持仓权重合理",
            RiskLevel.MEDIUM: "单一持仓权重偏高，建议控制在合理范围",
            RiskLevel.HIGH: "单一持仓权重过高，建议立即降低",
            RiskLevel.EXTREME: "单一持仓权重极高，存在重大集中度风险"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_liquidity_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "流动性充足，交易风险较低",
            RiskLevel.MEDIUM: "流动性一般，建议关注交易成本",
            RiskLevel.HIGH: "流动性不足，建议谨慎交易或寻找替代品",
            RiskLevel.EXTREME: "流动性极差，建议避免大额交易"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_zero_volume_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "交易活跃度正常",
            RiskLevel.MEDIUM: "存在一定比例的无交易日，需要关注流动性",
            RiskLevel.HIGH: "无交易日比例过高，流动性风险较大"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_stability_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "系统稳定性良好",
            RiskLevel.MEDIUM: "系统稳定性一般，建议加强监控",
            RiskLevel.HIGH: "系统稳定性较差，建议立即优化"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_data_quality_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "数据质量良好",
            RiskLevel.MEDIUM: "数据质量一般，建议加强数据验证",
            RiskLevel.HIGH: "数据质量较差，建议立即改进数据处理流程"
        }
        return recommendations.get(level, "需要进一步评估")

    def _get_model_risk_recommendation(self, level: RiskLevel) -> str:
        recommendations = {
            RiskLevel.LOW: "模型表现良好，风险可控",
            RiskLevel.MEDIUM: "模型表现一般，建议优化模型参数",
            RiskLevel.HIGH: "模型表现较差，建议重新训练或更换模型"
        }
        return recommendations.get(level, "需要进一步评估")

def create_risk_evaluator(db_path: str = 'data/factorweave_system.sqlite') -> RiskEvaluator:
    """
    创建风险评估器实例

    Args:
        db_path: 数据库路径

    Returns:
        风险评估器实例
    """
    return RiskEvaluator(db_path)

if __name__ == "__main__":
    # 测试代码
    evaluator = create_risk_evaluator()

    # 生成模拟数据
    returns = pd.Series(np.random.normal(0.001, 0.02, 252))
    portfolio_weights = {'AAPL': 0.3, 'GOOGL': 0.25,
                         'MSFT': 0.2, 'TSLA': 0.15, 'AMZN': 0.1}
    trading_volumes = pd.Series(np.random.lognormal(10, 1, 252))

    # 生成风险报告
    report = evaluator.generate_comprehensive_risk_report(
        returns=returns,
        portfolio_weights=portfolio_weights,
        trading_volumes=trading_volumes
    )

    logger.info("风险评估报告:")
    logger.info("=" * 50)
    logger.info(f"整体风险等级: {report['overall_risk_level']}")
    logger.info(f"生成时间: {report['timestamp']}")

    if report['recommendations']:
        logger.info("\n风险建议:")
        for i, rec in enumerate(report['recommendations'], 1):
            logger.info(f"{i}. {rec}")
