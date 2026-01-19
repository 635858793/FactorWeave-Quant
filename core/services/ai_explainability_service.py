"""
AI选股可解释性服务

提供AI选股结果的可视化解释和决策透明度
集成因子贡献分析、自然语言解释生成、可视化数据生成等功能
"""

import json
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

from loguru import logger

from .base_service import BaseService
from .database_service import DatabaseService
from ..containers import ServiceContainer, get_service_container
from ..events import EventBus, get_event_bus


class ExplanationLevel(Enum):
    """解释级别"""
    SIMPLE = "simple"          # 简单解释
    DETAILED = "detailed"      # 详细解释
    TECHNICAL = "technical"    # 技术解释


class FactorCategory(Enum):
    """因子类别"""
    TECHNICAL = "technical"           # 技术指标
    FUNDAMENTAL = "fundamental"       # 基本面
    MARKET = "market"                 # 市场因子
    RISK = "risk"                     # 风险因子
    SENTIMENT = "sentiment"           # 情绪因子


@dataclass
class FactorContribution:
    """因子贡献"""
    factor_name: str
    category: FactorCategory
    value: float
    normalized_value: float
    contribution_score: float
    importance_rank: int
    weight: float
    description: str


@dataclass
class ExplanationData:
    """解释数据"""
    stock_code: str
    stock_name: str
    selection_score: float
    explanation_level: ExplanationLevel
    factors: List[FactorContribution]
    summary_text: str
    detailed_analysis: str
    visualization_data: Dict[str, Any]
    confidence_score: float
    created_at: datetime


class AIExplainabilityService(BaseService):
    """AI选股可解释性服务"""
    
    def __init__(self, service_container: Optional[ServiceContainer] = None):
        """初始化可解释性服务
        
        Args:
            service_container: 服务容器，用于解析依赖服务
        """
        self._container = service_container or get_service_container()
        if not self._container:
            raise ValueError("无法获取服务容器，请确保服务容器已初始化")
            
        # 延迟解析依赖服务，在 _do_initialize 中解析
        self._database_service = None
        self._event_bus = None
        
        # 因子权重配置
        self._factor_weights = {
            FactorCategory.TECHNICAL: 0.35,
            FactorCategory.FUNDAMENTAL: 0.25,
            FactorCategory.MARKET: 0.20,
            FactorCategory.RISK: 0.15,
            FactorCategory.SENTIMENT: 0.05
        }
        
        # 因子描述配置
        self._factor_descriptions = {
            'RSI': '相对强弱指数，衡量股价动量',
            'MACD': '移动平均收敛发散指标，判断趋势变化',
            'BOLL': '布林带指标，分析价格波动范围',
            'MA': '移动平均线，反映价格趋势',
            'VOLUME': '成交量指标，反映市场活跃度',
            'PE_RATIO': '市盈率，评估股票估值水平',
            'PB_RATIO': '市净率，衡量账面价值',
            'ROE': '净资产收益率，反映盈利能力',
            'ROA': '总资产收益率，评估资产效率',
            'DEBT_RATIO': '负债率，评估财务风险',
            'MARKET_CAP': '市值，反映公司规模',
            'TURNOVER': '换手率，衡量交易活跃度',
            'VOLATILITY': '波动率，评估价格波动风险',
            'BETA': '贝塔系数，衡量系统性风险',
            'SHARPE': '夏普比率，风险调整后收益',
            'SENTIMENT_SCORE': '情绪评分，市场情绪指标'
        }
        
        # 因子阈值配置
        self._factor_thresholds = {
            'RSI': {'buy': 30, 'sell': 70},
            'MACD': {'bullish': 0, 'bearish': 0},
            'BOLL': {'upper': 0.8, 'lower': 0.2},
            'PE_RATIO': {'reasonable': 20, 'expensive': 40},
            'PB_RATIO': {'reasonable': 3, 'expensive': 5},
            'ROE': {'good': 0.15, 'excellent': 0.25},
            'VOLATILITY': {'low': 0.15, 'medium': 0.3, 'high': 0.5}
        }

        super().__init__()

    def _do_initialize(self) -> None:
        """执行初始化逻辑"""
        try:
            logger.info("Initializing AI Explainability Service...")
            
            # 解析依赖服务
            self._database_service = self._container.resolve(DatabaseService)
            self._event_bus = get_event_bus()
            
            # 验证依赖服务
            self._validate_dependencies()
            
            logger.info("✓ AI Explainability Service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize AI Explainability Service: {e}")
            raise

    def _validate_dependencies(self) -> None:
        """验证依赖服务"""
        if not self._database_service:
            raise ValueError("DatabaseService is required")
        
        # 测试数据库连接
        try:
            self._database_service.get_connection("analytics_duckdb")
        except Exception as e:
            raise ValueError(f"Database connection failed: {e}")

    def generate_explanation(self, 
                           stock_code: str, 
                           stock_data: Dict[str, Any],
                           selection_data: Dict[str, Any],
                           explanation_level: ExplanationLevel = ExplanationLevel.DETAILED,
                           selection_result_id: Optional[str] = None) -> ExplanationData:
        """
        生成选股解释
        
        Args:
            stock_code: 股票代码
            stock_data: 股票数据
            selection_data: 选股数据
            explanation_level: 解释级别
            selection_result_id: 选股结果ID（用于关联到ai_selection_results表）
            
        Returns:
            解释数据
        """
        try:
            logger.info(f"Generating explanation for {stock_code}")
            
            # 提取因子数据
            factors = self._extract_factors(stock_data, selection_data)
            
            # 计算因子贡献
            contributions = self._calculate_factor_contributions(factors)
            
            # 生成解释文本
            summary_text = self._generate_summary_text(stock_code, contributions, explanation_level)
            detailed_analysis = self._generate_detailed_analysis(stock_code, contributions, explanation_level)
            
            # 创建可视化数据
            visualization_data = self._create_visualization_data(contributions)
            
            # 计算置信度
            confidence_score = self._calculate_confidence_score(contributions)
            
            explanation_data = ExplanationData(
                stock_code=stock_code,
                stock_name=stock_data.get('name', ''),
                selection_score=selection_data.get('score', 0.0),
                explanation_level=explanation_level,
                factors=contributions,
                summary_text=summary_text,
                detailed_analysis=detailed_analysis,
                visualization_data=visualization_data,
                confidence_score=confidence_score,
                created_at=datetime.now()
            )
            
            # 保存解释数据到数据库
            self._save_explanation_to_db(explanation_data, selection_result_id)
            
            logger.info(f"Generated explanation for {stock_code} with confidence {confidence_score:.2f}")
            return explanation_data
            
        except Exception as e:
            logger.error(f"Failed to generate explanation for {stock_code}: {e}")
            raise

    def _extract_factors(self, stock_data: Dict[str, Any], selection_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """提取因子数据"""
        factors = {}
        
        # 技术指标因子
        technical_indicators = stock_data.get('technical_indicators', {})
        technical_factors = {
            'RSI': technical_indicators.get('rsi'),
            'MACD': technical_indicators.get('macd'),
            'MACD_SIGNAL': technical_indicators.get('macd_signal'),
            'MA5': technical_indicators.get('ma5'),
            'MA10': technical_indicators.get('ma10'),
            'MA20': technical_indicators.get('ma20'),
            'MA50': technical_indicators.get('ma50'),
            'BOLL_UPPER': technical_indicators.get('boll_upper'),
            'BOLL_MIDDLE': technical_indicators.get('boll_middle'),
            'BOLL_LOWER': technical_indicators.get('boll_lower'),
            'VOLUME': stock_data.get('volume', 0)
        }
        
        # 基本面因子
        fundamental_data = stock_data.get('fundamental_data', {})
        fundamental_factors = {
            'PE_RATIO': fundamental_data.get('pe_ratio'),
            'PB_RATIO': fundamental_data.get('pb_ratio'),
            'ROE': fundamental_data.get('roe'),
            'ROA': fundamental_data.get('roa'),
            'DEBT_RATIO': fundamental_data.get('debt_ratio')
        }
        
        # 市场因子
        market_data = stock_data.get('market_data', {})
        market_factors = {
            'MARKET_CAP': market_data.get('market_cap'),
            'TURNOVER': market_data.get('turnover_rate'),
            'SECTOR': market_data.get('sector')
        }
        
        # 风险因子
        risk_metrics = stock_data.get('risk_metrics', {})
        risk_factors = {
            'VOLATILITY': risk_metrics.get('volatility'),
            'BETA': risk_metrics.get('beta'),
            'SHARPE': risk_metrics.get('sharpe_ratio')
        }
        
        # 情绪因子
        sentiment_data = stock_data.get('sentiment_data', {})
        sentiment_factors = {
            'SENTIMENT_SCORE': sentiment_data.get('sentiment_score')
        }
        
        # 合并所有因子
        all_factors = {}
        all_factors.update({k: {'value': v, 'category': FactorCategory.TECHNICAL} for k, v in technical_factors.items() if v is not None})
        all_factors.update({k: {'value': v, 'category': FactorCategory.FUNDAMENTAL} for k, v in fundamental_factors.items() if v is not None})
        all_factors.update({k: {'value': v, 'category': FactorCategory.MARKET} for k, v in market_factors.items() if v is not None})
        all_factors.update({k: {'value': v, 'category': FactorCategory.RISK} for k, v in risk_factors.items() if v is not None})
        all_factors.update({k: {'value': v, 'category': FactorCategory.SENTIMENT} for k, v in sentiment_factors.items() if v is not None})
        
        return all_factors

    def _calculate_factor_contributions(self, factors: Dict[str, Dict[str, Any]]) -> List[FactorContribution]:
        """计算因子贡献"""
        contributions = []
        
        for factor_name, factor_data in factors.items():
            value = factor_data['value']
            category = factor_data['category']
            
            # 标准化因子值
            normalized_value = self._normalize_factor_value(factor_name, value)
            
            # 计算权重
            weight = self._factor_weights.get(category, 0.1)
            
            # 计算贡献分数
            contribution_score = normalized_value * weight
            
            # 获取描述
            description = self._factor_descriptions.get(factor_name, f'{factor_name}指标')
            
            contribution = FactorContribution(
                factor_name=factor_name,
                category=category,
                value=value,
                normalized_value=normalized_value,
                contribution_score=contribution_score,
                importance_rank=0,  # 稍后排序
                weight=weight,
                description=description
            )
            contributions.append(contribution)
        
        # 按贡献分数排序并设置排名
        contributions.sort(key=lambda x: x.contribution_score, reverse=True)
        for i, contribution in enumerate(contributions):
            contribution.importance_rank = i + 1
            
        return contributions

    def _normalize_factor_value(self, factor_name: str, value: float) -> float:
        """标准化因子值"""
        if value is None:
            return 0.0
            
        # 根据不同因子使用不同的标准化方法
        normalization_rules = {
            'RSI': lambda x: (100 - x) / 100 if x <= 50 else (x - 50) / 50,  # 中性化RSI
            'MACD': lambda x: 1 / (1 + math.exp(-x)),  # Sigmoid函数
            'PE_RATIO': lambda x: 1 / (1 + x/20) if x > 0 else 0,  # PE倒数标准化
            'PB_RATIO': lambda x: 1 / (1 + x/3) if x > 0 else 0,  # PB倒数标准化
            'ROE': lambda x: min(x, 0.5) / 0.5,  # ROE标准化到0-1
            'VOLATILITY': lambda x: 1 - min(x, 1),  # 波动率越低越好
            'BETA': lambda x: 1 - abs(x - 1),  # 接近1的Beta值更好
            'SHARPE': lambda x: max(0, min(x/2, 1)),  # 夏普比率标准化
            'SENTIMENT_SCORE': lambda x: (x + 1) / 2  # 情绪分数标准化到0-1
        }
        
        normalize_func = normalization_rules.get(factor_name, lambda x: x)
        return max(0, min(1, normalize_func(value)))

    def _generate_summary_text(self, stock_code: str, contributions: List[FactorContribution], 
                             level: ExplanationLevel) -> str:
        """生成总结文本"""
        top_factors = contributions[:3]  # 取前3个重要因子
        
        factor_descriptions = []
        for factor in top_factors:
            if factor.contribution_score > 0:
                direction = "正面影响" if factor.contribution_score > 0 else "负面影响"
                factor_descriptions.append(f"{factor.factor_name}({direction})")
        
        if not factor_descriptions:
            return f"{stock_code}: 各项因子表现一般，建议进一步分析"
        
        summary = f"{stock_code}的选股理由主要基于："
        summary += "、".join(factor_descriptions)
        
        if level == ExplanationLevel.SIMPLE:
            summary += "。综合评估显示该股票具有良好的投资潜力。"
        elif level == ExplanationLevel.DETAILED:
            summary += f"。其中{top_factors[0].factor_name}贡献最大，权重为{top_factors[0].weight:.2f}。"
        else:  # TECHNICAL
            summary += f"。技术分析显示因子贡献度分布为：{[(f.factor_name, f.contribution_score) for f in top_factors[:3]]}。"
        
        return summary

    def _generate_detailed_analysis(self, stock_code: str, contributions: List[FactorContribution], 
                                  level: ExplanationLevel) -> str:
        """生成详细分析"""
        analysis = f"详细分析 - {stock_code}\n\n"
        
        # 按类别分组分析
        categories = {}
        for contribution in contributions:
            category = contribution.category
            if category not in categories:
                categories[category] = []
            categories[category].append(contribution)
        
        for category, factors in categories.items():
            if not factors:
                continue
                
            analysis += f"{category.value.upper()}因子分析：\n"
            for factor in factors:
                analysis += f"  • {factor.factor_name}: {factor.description}\n"
                analysis += f"    数值: {factor.value:.4f}, 贡献: {factor.contribution_score:.4f}\n"
                
                if level == ExplanationLevel.TECHNICAL:
                    # 技术级别提供更详细的分析
                    analysis += f"    标准化值: {factor.normalized_value:.4f}, 权重: {factor.weight:.4f}\n"
                    analysis += f"    重要性排名: {factor.importance_rank}\n"
            
            analysis += "\n"
        
        # 总体评估
        total_contribution = sum(f.contribution_score for f in contributions)
        positive_factors = len([f for f in contributions if f.contribution_score > 0])
        negative_factors = len([f for f in contributions if f.contribution_score < 0])
        
        analysis += f"总体评估：\n"
        analysis += f"• 总贡献度: {total_contribution:.4f}\n"
        analysis += f"• 正面因子: {positive_factors}个\n"
        analysis += f"• 负面因子: {negative_factors}个\n"
        
        if total_contribution > 0.1:
            analysis += "• 投资建议: 积极看好，建议重点关注\n"
        elif total_contribution > 0:
            analysis += "• 投资建议: 谨慎乐观，建议持续观察\n"
        else:
            analysis += "• 投资建议: 暂不建议，建议等待更好的入场时机\n"
        
        return analysis

    def _create_visualization_data(self, contributions: List[FactorContribution]) -> Dict[str, Any]:
        """创建可视化数据"""
        # 因子贡献度图表数据
        factor_data = {
            'factors': [
                {
                    'name': f.factor_name,
                    'value': f.contribution_score,
                    'category': f.category.value,
                    'weight': f.weight,
                    'importance_rank': f.importance_rank
                }
                for f in contributions
            ]
        }
        
        # 类别贡献饼图数据
        category_data = {}
        for contribution in contributions:
            category = contribution.category.value
            if category not in category_data:
                category_data[category] = 0
            category_data[category] += contribution.contribution_score
        
        pie_data = {
            'categories': [
                {'name': k, 'value': v} for k, v in category_data.items()
            ]
        }
        
        # 重要性排名条形图数据
        ranking_data = {
            'rankings': [
                {
                    'rank': f.importance_rank,
                    'name': f.factor_name,
                    'score': f.contribution_score
                }
                for f in sorted(contributions, key=lambda x: x.importance_rank)[:10]
            ]
        }
        
        # 综合评分雷达图数据
        radar_data = {
            'dimensions': [
                {
                    'axis': category.value,
                    'score': sum(f.contribution_score for f in contributions if f.category == category) / len([f for f in contributions if f.category == category]) if any(f.category == category for f in contributions) else 0
                }
                for category in FactorCategory
            ]
        }
        
        return {
            'factor_contribution': factor_data,
            'category_distribution': pie_data,
            'importance_ranking': ranking_data,
            'radar_chart': radar_data,
            'chart_configs': {
                'factor_contribution': {
                    'type': 'bar',
                    'title': '因子贡献度分析',
                    'x_axis': '因子名称',
                    'y_axis': '贡献度'
                },
                'category_distribution': {
                    'type': 'pie',
                    'title': '类别贡献分布',
                    'show_legend': True
                },
                'importance_ranking': {
                    'type': 'bar',
                    'title': '因子重要性排名',
                    'x_axis': '排名',
                    'y_axis': '因子名称'
                },
                'radar_chart': {
                    'type': 'radar',
                    'title': '综合评分雷达图',
                    'max_value': 1.0
                }
            }
        }

    def _calculate_confidence_score(self, contributions: List[FactorContribution]) -> float:
        """计算置信度分数"""
        if not contributions:
            return 0.0
        
        # 因子数量置信度
        factor_count_score = min(len(contributions) / 10, 1.0)
        
        # 因子一致性置信度 - 优化版本
        positive_contributions = [f for f in contributions if f.contribution_score > 0]
        negative_contributions = [f for f in contributions if f.contribution_score < 0]
        
        # 1. 基础一致性：正向因子占比
        base_consistency = len(positive_contributions) / len(contributions) if contributions else 0
        
        # 2. 加权一致性：考虑因子权重
        if contributions:
            weighted_positive = sum(f.contribution_score * f.weight for f in positive_contributions)
            weighted_negative = sum(abs(f.contribution_score) * f.weight for f in negative_contributions)
            total_weighted = weighted_positive + weighted_negative
            weighted_consistency = weighted_positive / total_weighted if total_weighted > 0 else 0
        else:
            weighted_consistency = 0
        
        # 3. 类别一致性：检查同一类别因子的一致性
        category_consistency = self._calculate_category_consistency(contributions)
        
        # 综合一致性得分
        consistency_score = (base_consistency * 0.4 + 
                          weighted_consistency * 0.4 + 
                          category_consistency * 0.2)
        
        # 因子重要性置信度（Top 3因子占总贡献的比例）
        top_3_contributions = sum(f.contribution_score for f in contributions[:3])
        total_contribution = sum(abs(f.contribution_score) for f in contributions)
        importance_score = top_3_contributions / total_contribution if total_contribution > 0 else 0
        
        # 综合置信度
        confidence_score = (factor_count_score * 0.3 + 
                          consistency_score * 0.4 + 
                          importance_score * 0.3)
        
        return max(0, min(1, confidence_score))
    
    def _calculate_category_consistency(self, contributions: List[FactorContribution]) -> float:
        """计算类别一致性"""
        if not contributions:
            return 0.0
        
        # 按类别分组
        from collections import defaultdict
        category_scores = defaultdict(list)
        
        for factor in contributions:
            category_scores[factor.category].append(factor.contribution_score)
        
        # 计算每个类别的一致性
        category_consistencies = []
        for category, scores in category_scores.items():
            if len(scores) > 1:
                # 计算同一类别因子的一致性
                positive_count = sum(1 for s in scores if s > 0)
                category_consistency = positive_count / len(scores)
                category_consistencies.append(category_consistency)
        
        # 返回平均类别一致性
        if category_consistencies:
            return sum(category_consistencies) / len(category_consistencies)
        else:
            # 如果只有一个类别或每个类别只有一个因子，返回中等一致性
            return 0.5

    def _save_explanation_to_db(self, explanation_data: ExplanationData, selection_result_id: Optional[str] = None) -> None:
        """保存解释数据到数据库
        
        Args:
            explanation_data: 解释数据
            selection_result_id: 选股结果ID（用于关联到ai_selection_results表）
        """
        try:
            # 如果没有提供 selection_result_id，则尝试查询或创建
            if selection_result_id is None:
                selection_result_id = self._get_or_create_selection_result_id(
                    explanation_data.stock_code,
                    explanation_data.created_at
                )
            
            # 如果仍然没有有效的 selection_result_id，则跳过保存
            if selection_result_id is None:
                logger.warning(f"无法获取有效的 selection_result_id，跳过保存解释数据: {explanation_data.stock_code}")
                return
            
            explanations = []
            
            # 为每个因子创建解释记录
            for factor in explanation_data.factors:
                explanation = {
                    'selection_result_id': selection_result_id,
                    'explanation_type': 'factor_analysis',
                    'factor_name': factor.factor_name,
                    'factor_value': factor.value,
                    'contribution_score': factor.contribution_score,
                    'importance_rank': factor.importance_rank,
                    'explanation_text': f"{factor.factor_name}对选股决策的贡献为{factor.contribution_score:.4f}",
                    'visualization_data': {
                        'category': factor.category.value,
                        'weight': factor.weight,
                        'normalized_value': factor.normalized_value
                    }
                }
                explanations.append(explanation)
            
            # 保存到数据库
            if explanations:
                self._database_service.save_ai_explanations(explanations)
                
        except Exception as e:
            logger.error(f"Failed to save explanation to database: {e}")
            # 不抛出异常，避免影响主流程

    def _get_or_create_selection_result_id(self, stock_code: str, created_at: datetime) -> Optional[str]:
        """获取或创建选股结果ID
        
        Args:
            stock_code: 股票代码
            created_at: 创建时间
            
        Returns:
            选股结果ID，如果无法创建则返回None
        """
        try:
            import uuid
            
            # 尝试查询匹配的选股结果记录
            selection_date = created_at.date()
            sql = """
            SELECT id FROM ai_selection_results 
            WHERE stock_code = ? AND selection_date = ?
            ORDER BY created_at DESC
            LIMIT 1
            """
            
            with self._database_service.get_connection("analytics_duckdb") as conn:
                rows = conn.execute(sql, (stock_code, selection_date)).fetchall()
                
                if rows:
                    return rows[0][0]
            
            # 如果没有找到匹配的记录，创建一条新的记录
            logger.info(f"为股票 {stock_code} 创建新的选股结果记录")
            
            # 生成新的 result_id（UUID）
            new_result_id = str(uuid.uuid4())
            # 使用 {result_id}_{stock_code} 作为唯一ID
            unique_id = f"{new_result_id}_{stock_code}"
            
            insert_sql = """
            INSERT INTO ai_selection_results (
                id, strategy_id, selection_date, stock_code, 
                score, weight, confidence, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            with self._database_service.get_connection("analytics_duckdb") as conn:
                conn.execute(insert_sql, (
                    unique_id,
                    str(uuid.uuid4()),  # 策略ID（临时生成）
                    selection_date,
                    stock_code,
                    0.0,  # 评分
                    0.0,  # 权重
                    0.0,  # 置信度
                    created_at
                ))
            
            logger.info(f"成功创建选股结果记录: {unique_id}")
            return unique_id
            
        except Exception as e:
            logger.error(f"获取或创建选股结果ID失败: {e}")
            return None

    def get_explanation_history(self, stock_code: str, days: int = 30) -> List[Dict[str, Any]]:
        """获取解释历史"""
        try:
            sql = """
            SELECT * FROM ai_explanations 
            WHERE selection_result_id LIKE ? 
            AND created_at >= ?
            ORDER BY created_at DESC
            """
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with self._database_service.get_connection("analytics_duckdb") as conn:
                rows = conn.execute(sql, (f"{stock_code}_%", cutoff_date)).fetchall()
                
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get explanation history for {stock_code}: {e}")
            return []

    def _do_health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        try:
            # 检查数据库连接
            with self._database_service.get_connection("analytics_duckdb") as conn:
                conn.execute("SELECT 1")
            
            return {
                "status": "healthy",
                "service": "AIExplainabilityService",
                "timestamp": datetime.now().isoformat(),
                "dependencies": {
                    "database": "ok",
                    "event_bus": "ok" if self._event_bus else "not_available"
                }
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "service": "AIExplainabilityService",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _do_dispose(self) -> None:
        """清理资源"""
        try:
            logger.info("Disposing AI Explainability Service...")
            # 清理缓存等资源
            logger.info("AI Explainability Service disposed successfully")
            
        except Exception as e:
            logger.error(f"Error disposing AI Explainability Service: {e}")