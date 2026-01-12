"""
推荐理由生成器

为智能推荐系统生成个性化的推荐理由，根据推荐内容、股票特征、技术指标等生成详细的推荐理由。
"""

from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from loguru import logger

from core.plugin_types import AssetType
from core.services.smart_recommendation_engine import Recommendation, RecommendationReason


class ExplanationLevel(Enum):
    """解释级别"""
    SIMPLE = "simple"
    DETAILED = "detailed"
    EXPERT = "expert"


class RecommendationExplanationGenerator:
    """
    推荐理由生成器
    
    根据推荐内容、股票特征、技术指标等生成个性化的推荐理由。
    支持多种推荐类型和资产类型。
    """

    def __init__(self):
        self._explanation_templates = {
            RecommendationReason.SIMILAR_USERS: {
                "stock_a": "基于协同过滤算法，发现与您兴趣相似的用户也关注了{stock_name}({stock_code})。该股票在{industry}行业中表现突出，当前{technical_feature}，适合您的投资偏好。",
                "stock_b": "基于协同过滤算法，发现与您兴趣相似的用户也关注了{stock_name}({stock_code})。该股票在{industry}行业中表现突出，当前{technical_feature}，适合您的投资偏好。",
                "crypto": "基于协同过滤算法，发现与您兴趣相似的用户也关注了{coin_name}({coin_code})。该加密货币在{category}类别中表现突出，当前{technical_feature}，适合您的投资偏好。",
                "futures": "基于协同过滤算法，发现与您兴趣相似的用户也关注了{contract_name}({contract_code})。该合约在{category}类别中表现突出，当前{technical_feature}，适合您的投资偏好。",
                "sector": "基于协同过滤算法，发现与您兴趣相似的用户也关注了{sector_name}({sector_code})。该板块在近期表现突出，当前{technical_feature}，适合您的投资偏好。",
            },
            RecommendationReason.CONTENT_SIMILARITY: {
                "stock_a": "基于内容相似度分析，{stock_name}({stock_code})与您历史关注的股票在{similarity_aspect}方面高度相似。该股票{fundamental_feature}，符合您的投资风格。",
                "stock_b": "基于内容相似度分析，{stock_name}({stock_code})与您历史关注的股票在{similarity_aspect}方面高度相似。该股票{fundamental_feature}，符合您的投资风格。",
                "crypto": "基于内容相似度分析，{coin_name}({coin_code})与您历史关注的加密货币在{similarity_aspect}方面高度相似。该加密货币{fundamental_feature}，符合您的投资风格。",
                "futures": "基于内容相似度分析，{contract_name}({contract_code})与您历史关注的合约在{similarity_aspect}方面高度相似。该合约{fundamental_feature}，符合您的投资风格。",
                "sector": "基于内容相似度分析，{sector_name}({sector_code})与您历史关注的板块在{similarity_aspect}方面高度相似。该板块{fundamental_feature}，符合您的投资风格。",
            },
            RecommendationReason.TRENDING: {
                "stock_a": "{stock_name}({stock_code})近期市场热度持续上升，{trend_feature}。该股票在{time_period}内获得了{interaction_count}次用户关注，{market_feature}，值得重点关注。",
                "stock_b": "{stock_name}({stock_code})近期市场热度持续上升，{trend_feature}。该股票在{time_period}内获得了{interaction_count}次用户关注，{market_feature}，值得重点关注。",
                "crypto": "{coin_name}({coin_code})近期市场热度持续上升，{trend_feature}。该加密货币在{time_period}内获得了{interaction_count}次用户关注，{market_feature}，值得重点关注。",
                "futures": "{contract_name}({contract_code})近期市场热度持续上升，{trend_feature}。该合约在{time_period}内获得了{interaction_count}次用户关注，{market_feature}，值得重点关注。",
                "sector": "{sector_name}({sector_code})近期市场热度持续上升，{trend_feature}。该板块在{time_period}内获得了{interaction_count}次用户关注，{market_feature}，值得重点关注。",
            },
        }

    def generate_explanation(self, 
                         recommendation: Recommendation,
                         level: ExplanationLevel = ExplanationLevel.DETAILED) -> str:
        """
        生成推荐理由
        
        Args:
            recommendation: 推荐对象
            level: 解释级别
            
        Returns:
            推荐理由文本
        """
        try:
            if not recommendation:
                return "系统推荐"

            asset_type = recommendation.asset_type
            if not asset_type:
                asset_type = AssetType.STOCK_A

            asset_type_str = asset_type.value if isinstance(asset_type, AssetType) else str(asset_type)
            
            reason = recommendation.reason
            if not reason:
                reason = RecommendationReason.TRENDING

            template = self._explanation_templates.get(reason, {}).get(asset_type_str)
            
            if not template:
                return self._generate_default_explanation(recommendation, level)

            explanation = self._fill_template(template, recommendation, level)
            
            return explanation

        except Exception as e:
            logger.error(f"生成推荐理由失败: {e}")
            return self._generate_default_explanation(recommendation, level)

    def _fill_template(self, template: str, recommendation: Recommendation, level: ExplanationLevel) -> str:
        """
        填充模板
        
        Args:
            template: 模板字符串
            recommendation: 推荐对象
            level: 解释级别
            
        Returns:
            填充后的文本
        """
        metadata = recommendation.metadata if hasattr(recommendation, 'metadata') else {}
        
        replacements = {
            "stock_name": recommendation.title or "未知股票",
            "stock_code": recommendation.item_id or "未知代码",
            "coin_name": recommendation.title or "未知加密货币",
            "coin_code": recommendation.item_id or "未知代码",
            "contract_name": recommendation.title or "未知合约",
            "contract_code": recommendation.item_id or "未知代码",
            "sector_name": recommendation.title or "未知板块",
            "sector_code": recommendation.item_id or "未知代码",
            "industry": metadata.get('industry', '未知行业'),
            "category": metadata.get('category', '未知类别'),
            "technical_feature": self._get_technical_feature(metadata, level),
            "fundamental_feature": self._get_fundamental_feature(metadata, level),
            "trend_feature": self._get_trend_feature(metadata, level),
            "market_feature": self._get_market_feature(metadata, level),
            "similarity_aspect": self._get_similarity_aspect(metadata, level),
            "time_period": metadata.get('time_period', '近期'),
            "interaction_count": metadata.get('interaction_count', 0),
        }
        
        explanation = template
        for key, value in replacements.items():
            explanation = explanation.replace(f"{{{key}}}", str(value))
        
        return explanation

    def _get_technical_feature(self, metadata: Dict[str, Any], level: ExplanationLevel) -> str:
        """获取技术特征描述"""
        technical = metadata.get('technical_indicators', {})
        
        if level == ExplanationLevel.SIMPLE:
            return "技术指标表现良好"
        
        features = []
        
        if technical.get('rsi'):
            rsi = technical['rsi']
            if rsi < 30:
                features.append("RSI指标显示超卖")
            elif rsi > 70:
                features.append("RSI指标显示超买")
            else:
                features.append("RSI指标处于正常区间")
        
        if technical.get('macd'):
            macd = technical['macd']
            if macd > 0:
                features.append("MACD金叉向上")
            else:
                features.append("MACD死叉向下")
        
        if technical.get('bollinger'):
            features.append("布林带指标稳定")
        
        if technical.get('volume'):
            volume = technical['volume']
            if volume > 0:
                features.append(f"成交量{volume}")
        
        if not features:
            return "技术指标表现平稳"
        
        return "、".join(features[:3])

    def _get_fundamental_feature(self, metadata: Dict[str, Any], level: ExplanationLevel) -> str:
        """获取基本面特征描述"""
        fundamental = metadata.get('fundamental_data', {})
        
        if level == ExplanationLevel.SIMPLE:
            return "基本面数据健康"
        
        features = []
        
        if fundamental.get('pe_ratio'):
            pe = fundamental['pe_ratio']
            if pe < 20:
                features.append("市盈率较低")
            elif pe > 50:
                features.append("市盈率较高")
            else:
                features.append("市盈率适中")
        
        if fundamental.get('pb_ratio'):
            pb = fundamental['pb_ratio']
            if pb < 2:
                features.append("市净率较低")
            elif pb > 5:
                features.append("市净率较高")
            else:
                features.append("市净率适中")
        
        if fundamental.get('roe'):
            roe = fundamental['roe']
            if roe > 15:
                features.append("净资产收益率优秀")
            elif roe > 10:
                features.append("净资产收益率良好")
            else:
                features.append("净资产收益率一般")
        
        if not features:
            return "基本面数据稳定"
        
        return "、".join(features[:3])

    def _get_trend_feature(self, metadata: Dict[str, Any], level: ExplanationLevel) -> str:
        """获取趋势特征描述"""
        market = metadata.get('market_data', {})
        
        if level == ExplanationLevel.SIMPLE:
            return "市场表现活跃"
        
        features = []
        
        if market.get('view_count'):
            view_count = market['view_count']
            if view_count > 1000:
                features.append("浏览量高")
            elif view_count > 500:
                features.append("浏览量中等")
            else:
                features.append("浏览量适中")
        
        if market.get('like_count'):
            like_count = market['like_count']
            if like_count > 100:
                features.append("点赞数多")
            elif like_count > 50:
                features.append("点赞数中等")
            else:
                features.append("点赞数适中")
        
        if market.get('share_count'):
            share_count = market['share_count']
            if share_count > 50:
                features.append("分享数多")
            elif share_count > 20:
                features.append("分享数中等")
            else:
                features.append("分享数适中")
        
        if not features:
            return "市场关注度一般"
        
        return "、".join(features[:3])

    def _get_market_feature(self, metadata: Dict[str, Any], level: ExplanationLevel) -> str:
        """获取市场特征描述"""
        market = metadata.get('market_data', {})
        
        if level == ExplanationLevel.SIMPLE:
            return "市场表现良好"
        
        features = []
        
        if market.get('market_cap'):
            market_cap = market['market_cap']
            if market_cap > 100000000000:
                features.append("大盘股")
            elif market_cap > 50000000000:
                features.append("中盘股")
            else:
                features.append("小盘股")
        
        if market.get('turnover_rate'):
            turnover = market['turnover_rate']
            if turnover > 10:
                features.append("换手率高")
            elif turnover > 5:
                features.append("换手率中等")
            else:
                features.append("换手率低")
        
        if not features:
            return "市场表现稳定"
        
        return "、".join(features[:2])

    def _get_similarity_aspect(self, metadata: Dict[str, Any], level: ExplanationLevel) -> str:
        """获取相似度方面描述"""
        if level == ExplanationLevel.SIMPLE:
            return "多个维度"
        
        aspects = metadata.get('similarity_aspects', [])
        
        if not aspects:
            return "投资风格"
        
        return "、".join(aspects[:3])

    def _generate_default_explanation(self, recommendation: Recommendation, level: ExplanationLevel) -> str:
        """
        生成默认推荐理由
        
        Args:
            recommendation: 推荐对象
            level: 解释级别
            
        Returns:
            默认推荐理由文本
        """
        if level == ExplanationLevel.SIMPLE:
            return f"{recommendation.title or '推荐项'} 是系统为您推荐的内容，基于您的投资偏好和历史行为分析。"
        
        explanation_parts = []
        
        if recommendation.title:
            explanation_parts.append(f"推荐内容：{recommendation.title}")
        
        if recommendation.description:
            explanation_parts.append(f"描述：{recommendation.description}")
        
        if recommendation.score:
            score_desc = "高" if recommendation.score > 0.7 else "中" if recommendation.score > 0.4 else "低"
            explanation_parts.append(f"推荐分数：{recommendation.score:.2f}（{score_desc}）")
        
        if recommendation.confidence:
            confidence_desc = "高" if recommendation.confidence > 0.7 else "中" if recommendation.confidence > 0.4 else "低"
            explanation_parts.append(f"置信度：{recommendation.confidence:.2f}（{confidence_desc}）")
        
        if recommendation.asset_type:
            explanation_parts.append(f"资产类型：{recommendation.asset_type.value if isinstance(recommendation.asset_type, AssetType) else str(recommendation.asset_type)}")
        
        if not explanation_parts:
            return "系统推荐"
        
        return "；".join(explanation_parts)


def get_recommendation_explanation_generator() -> RecommendationExplanationGenerator:
    """
    获取推荐理由生成器实例
    
    Returns:
        推荐理由生成器实例
    """
    return RecommendationExplanationGenerator()
