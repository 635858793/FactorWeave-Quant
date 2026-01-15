#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推荐理由生成器

为智能推荐引擎生成推荐理由，支持多种推荐类型。
"""

from typing import Optional
from loguru import logger


class RecommendationExplanationGenerator:
    """推荐理由生成器"""
    
    def __init__(self):
        """初始化推荐理由生成器"""
        self.ai_explainability_service = None
        
        try:
            from .ai_explainability_service import AIExplainabilityService
            from ..containers import get_service_container
            
            self.ai_explainability_service = get_service_container().resolve(AIExplainabilityService)
            logger.info("推荐理由生成器已初始化，AI可解释性服务已连接")
        except Exception as e:
            logger.warning(f"无法加载AI可解释性服务: {e}")
    
    def generate_explanation(self, recommendation) -> str:
        """
        生成推荐理由
        
        Args:
            recommendation: 推荐对象
            
        Returns:
            str: 推荐理由文本
        """
        try:
            # 如果有AI可解释性服务且是股票类型，使用AI生成解释
            if self.ai_explainability_service and recommendation.asset_type:
                return self._generate_ai_explanation(recommendation)
            else:
                return self._generate_generic_explanation(recommendation)
        except Exception as e:
            logger.error(f"生成推荐理由失败: {e}")
            return self._generate_generic_explanation(recommendation)
    
    def _generate_ai_explanation(self, recommendation) -> str:
        """
        使用AI可解释性服务生成解释
        
        Args:
            recommendation: 推荐对象
            
        Returns:
            str: AI生成的解释
        """
        try:
            from .ai_explainability_service import ExplanationLevel
            
            # 获取股票数据（这里简化处理，实际应该从数据库获取）
            stock_data = {}
            selection_data = {
                'score': recommendation.score,
                'confidence': recommendation.confidence
            }
            
            # 生成解释
            explanation_data = self.ai_explainability_service.generate_explanation(
                stock_code=recommendation.item_id,
                stock_data=stock_data,
                selection_data=selection_data,
                explanation_level=ExplanationLevel.SIMPLE
            )
            
            return explanation_data.summary_text
            
        except Exception as e:
            logger.warning(f"AI解释生成失败，使用通用解释: {e}")
            return self._generate_generic_explanation(recommendation)
    
    def _generate_generic_explanation(self, recommendation) -> str:
        """
        生成通用推荐理由
        
        Args:
            recommendation: 推荐对象
            
        Returns:
            str: 通用解释文本
        """
        reason_map = {
            'similar_users': "与您兴趣相似的用户也喜欢这个内容",
            'content_similarity': "此内容与您历史偏好高度相似",
            'trending': "此内容目前非常热门",
            'historical_preference': "基于您的历史偏好推荐",
            'performance_based': "基于历史表现推荐",
            'collaborative': "基于协同过滤算法推荐",
            'hybrid': "综合多种算法为您推荐"
        }
        
        reason_key = recommendation.reason.value if hasattr(recommendation.reason, 'value') else str(recommendation.reason)
        base_reason = reason_map.get(reason_key, "为您推荐此内容")
        
        # 添加置信度信息
        if recommendation.confidence > 0.8:
            confidence_text = "（高置信度）"
        elif recommendation.confidence > 0.6:
            confidence_text = "（中等置信度）"
        else:
            confidence_text = "（低置信度）"
        
        explanation = f"{base_reason}{confidence_text}"
        
        # 如果有描述，添加到解释中
        if recommendation.description:
            explanation += f"\n{recommendation.description}"
        
        return explanation
