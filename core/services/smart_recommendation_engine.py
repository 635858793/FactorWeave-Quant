"""
智能推荐引擎

提供基于用户行为分析和内容特征的个性化推荐功能。
支持协同过滤、内容推荐、混合推荐等多种推荐算法。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
import threading
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
import pickle

from loguru import logger
from ..plugin_types import AssetType

logger = logger.bind(module=__name__)


class RecommendationType(Enum):
    """推荐类型（与资产类型一致）"""
    # 股票类型
    STOCK_A = "stock_a"                      # A股推荐
    STOCK_B = "stock_b"                      # B股推荐
    STOCK_H = "stock_h"                      # H股推荐
    STOCK_US = "stock_us"                    # 美股推荐
    STOCK_HK = "stock_hk"                    # 港股推荐
    
    # 其他资产类型
    FUTURES = "futures"                      # 期货推荐
    CRYPTO = "crypto"                        # 加密货币推荐
    FOREX = "forex"                          # 外汇推荐
    BOND = "bond"                            # 债券推荐
    COMMODITY = "commodity"                  # 商品推荐
    INDEX = "index"                          # 指数推荐
    FUND = "fund"                            # 基金推荐
    OPTION = "option"                        # 期权推荐
    WARRANT = "warrant"                      # 权证推荐
    
    # 板块相关
    SECTOR = "sector"                        # 板块推荐
    INDUSTRY_SECTOR = "industry_sector"      # 行业板块推荐
    CONCEPT_SECTOR = "concept_sector"        # 概念板块推荐
    STYLE_SECTOR = "style_sector"            # 风格板块推荐
    THEME_SECTOR = "theme_sector"            # 主题板块推荐
    
    # 宏观经济
    MACRO = "macro"                          # 宏观经济推荐
    
    # 传统推荐类型（保持向下兼容）
    STOCK = "stock"                         # 股票推荐（通用）
    INDICATOR = "indicator"                  # 指标推荐
    STRATEGY = "strategy"                    # 策略推荐


def asset_type_to_recommendation_type(asset_type: AssetType) -> RecommendationType:
    """
    将资产类型转换为推荐类型
    
    Args:
        asset_type: 资产类型
        
    Returns:
        推荐类型
    """
    mapping = {
        AssetType.STOCK_A: RecommendationType.STOCK_A,
        AssetType.STOCK_B: RecommendationType.STOCK_B,
        AssetType.STOCK_H: RecommendationType.STOCK_H,
        AssetType.STOCK_US: RecommendationType.STOCK_US,
        AssetType.STOCK_HK: RecommendationType.STOCK_HK,
        AssetType.FUTURES: RecommendationType.FUTURES,
        AssetType.CRYPTO: RecommendationType.CRYPTO,
        AssetType.FOREX: RecommendationType.FOREX,
        AssetType.BOND: RecommendationType.BOND,
        AssetType.COMMODITY: RecommendationType.COMMODITY,
        AssetType.INDEX: RecommendationType.INDEX,
        AssetType.FUND: RecommendationType.FUND,
        AssetType.OPTION: RecommendationType.OPTION,
        AssetType.WARRANT: RecommendationType.WARRANT,
        AssetType.SECTOR: RecommendationType.SECTOR,
        AssetType.INDUSTRY_SECTOR: RecommendationType.INDUSTRY_SECTOR,
        AssetType.CONCEPT_SECTOR: RecommendationType.CONCEPT_SECTOR,
        AssetType.STYLE_SECTOR: RecommendationType.STYLE_SECTOR,
        AssetType.THEME_SECTOR: RecommendationType.THEME_SECTOR,
        AssetType.MACRO: RecommendationType.MACRO,
    }
    
    return mapping.get(asset_type, RecommendationType.STOCK_A)


def recommendation_type_to_asset_type(recommendation_type: RecommendationType) -> AssetType:
    """
    将推荐类型转换为资产类型
    
    Args:
        recommendation_type: 推荐类型
        
    Returns:
        资产类型
    """
    mapping = {
        RecommendationType.STOCK_A: AssetType.STOCK_A,
        RecommendationType.STOCK_B: AssetType.STOCK_B,
        RecommendationType.STOCK_H: AssetType.STOCK_H,
        RecommendationType.STOCK_US: AssetType.STOCK_US,
        RecommendationType.STOCK_HK: AssetType.STOCK_HK,
        RecommendationType.FUTURES: AssetType.FUTURES,
        RecommendationType.CRYPTO: AssetType.CRYPTO,
        RecommendationType.FOREX: AssetType.FOREX,
        RecommendationType.BOND: AssetType.BOND,
        RecommendationType.COMMODITY: AssetType.COMMODITY,
        RecommendationType.INDEX: AssetType.INDEX,
        RecommendationType.FUND: AssetType.FUND,
        RecommendationType.OPTION: AssetType.OPTION,
        RecommendationType.WARRANT: AssetType.WARRANT,
        RecommendationType.SECTOR: AssetType.SECTOR,
        RecommendationType.INDUSTRY_SECTOR: AssetType.INDUSTRY_SECTOR,
        RecommendationType.CONCEPT_SECTOR: AssetType.CONCEPT_SECTOR,
        RecommendationType.STYLE_SECTOR: AssetType.STYLE_SECTOR,
        RecommendationType.THEME_SECTOR: AssetType.THEME_SECTOR,
        RecommendationType.MACRO: AssetType.MACRO,
    }
    
    return mapping.get(recommendation_type, AssetType.STOCK_A)


class RecommendationReason(Enum):
    """推荐原因"""
    SIMILAR_USERS = "similar_users"         # 相似用户喜欢
    CONTENT_SIMILARITY = "content_similarity"  # 内容相似
    TRENDING = "trending"                   # 热门趋势
    HISTORICAL_PREFERENCE = "historical_preference"  # 历史偏好
    PERFORMANCE_BASED = "performance_based"  # 基于表现
    COLLABORATIVE = "collaborative"         # 协同过滤
    HYBRID = "hybrid"                      # 混合推荐


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str

    # 基本信息
    registration_date: datetime
    last_active: datetime
    activity_level: str = "medium"  # low, medium, high

    # 偏好特征
    preferred_stocks: List[str] = field(default_factory=list)
    preferred_sectors: List[str] = field(default_factory=list)
    preferred_indicators: List[str] = field(default_factory=list)
    preferred_timeframes: List[str] = field(default_factory=list)

    # 行为特征
    view_history: List[Dict[str, Any]] = field(default_factory=list)
    search_history: List[str] = field(default_factory=list)
    interaction_patterns: Dict[str, int] = field(default_factory=dict)

    # 风险偏好
    risk_tolerance: str = "medium"  # conservative, medium, aggressive
    investment_horizon: str = "medium"  # short, medium, long

    # 特征向量
    feature_vector: Optional[np.ndarray] = None
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ContentItem:
    """内容项"""
    item_id: str
    item_type: RecommendationType
    title: str
    description: str = ""

    # 内容特征
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    # 统计信息
    view_count: int = 0
    like_count: int = 0
    share_count: int = 0
    rating: float = 0.0

    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # 特征向量
    feature_vector: Optional[np.ndarray] = None

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserInteraction:
    """用户交互记录"""
    user_id: str
    item_id: str
    interaction_type: str  # view, like, share, comment, bookmark
    timestamp: datetime
    duration: Optional[float] = None  # 交互持续时间（秒）
    rating: Optional[float] = None    # 用户评分
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    """推荐结果"""
    user_id: str
    item_id: str
    item_type: RecommendationType
    score: float
    reason: RecommendationReason

    # 推荐内容
    title: str
    description: str = ""
    thumbnail: str = ""

    # 推荐解释
    explanation: str = ""
    confidence: float = 0.0

    # 资产类型
    asset_type: Optional[AssetType] = None

    # 元数据
    generated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SmartRecommendationEngine:
    """
    智能推荐引擎

    提供个性化推荐功能：
    - 用户行为分析和画像构建
    - 内容特征提取和相似度计算
    - 协同过滤推荐
    - 内容基础推荐
    - 混合推荐算法
    - 实时推荐更新
    """

    def __init__(self):
        # 数据存储
        self.user_profiles: Dict[str, UserProfile] = {}
        self.content_items: Dict[str, ContentItem] = {}
        self.interactions: List[UserInteraction] = []

        # 推荐模型
        self.user_item_matrix: Optional[pd.DataFrame] = None
        self.content_similarity_matrix: Optional[np.ndarray] = None
        self.user_similarity_matrix: Optional[np.ndarray] = None

        # 特征提取器
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.svd_model = TruncatedSVD(n_components=50, random_state=42)

        # 推荐理由生成器
        self.explanation_generator = None

        # 缓存
        self.recommendation_cache: Dict[str, List[Recommendation]] = {}
        self.cache_ttl = timedelta(hours=1)

        # 配置
        self.min_interactions_for_cf = 5  # 协同过滤最小交互数
        self.max_recommendations = 20     # 最大推荐数量
        self.similarity_threshold = 0.1   # 相似度阈值

        # 状态管理
        self._model_trained = False
        self._training_active = False
        self._training_thread = None
        self._lock = threading.RLock()

        # 统计信息
        self.recommendation_stats = {
            'total_recommendations': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_recommendation_time': 0.0
        }

        logger.info("智能推荐引擎初始化完成")

    def add_user_interaction(self, interaction: UserInteraction):
        """添加用户交互记录"""
        try:
            with self._lock:
                self.interactions.append(interaction)

                # 更新用户画像
                self._update_user_profile(interaction)

                # 更新内容统计
                self._update_content_stats(interaction)

                # 标记需要重新训练
                self._model_trained = False

            logger.debug(f"用户交互已记录: {interaction.user_id} - {interaction.item_id}")

        except Exception as e:
            logger.error(f"添加用户交互失败: {e}")

    def add_content_item(self, item: ContentItem):
        """添加内容项"""
        try:
            with self._lock:
                self.content_items[item.item_id] = item

                # 提取内容特征
                self._extract_content_features(item)

                # 标记需要重新训练
                self._model_trained = False

            # logger.info(f"内容项已添加: {item.item_id}")

        except Exception as e:
            logger.error(f"添加内容项失败: {e}")

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        try:
            return self.user_profiles.get(user_id)
        except Exception as e:
            logger.error(f"获取用户画像失败: {e}")
            return None

    def set_explanation_generator(self, generator):
        """
        设置推荐理由生成器
        
        Args:
            generator: 推荐理由生成器实例
        """
        self.explanation_generator = generator
        logger.info("推荐理由生成器已设置")

    def update_user_profile(self, user_id: str, updates: Dict[str, Any]):
        """更新用户画像"""
        try:
            with self._lock:
                if user_id not in self.user_profiles:
                    self.user_profiles[user_id] = UserProfile(
                        user_id=user_id,
                        registration_date=datetime.now(),
                        last_active=datetime.now()
                    )

                profile = self.user_profiles[user_id]

                # 更新字段
                for field, value in updates.items():
                    if hasattr(profile, field):
                        setattr(profile, field, value)

                profile.last_updated = datetime.now()

                # 重新计算特征向量
                self._compute_user_features(profile)

            logger.info(f"用户画像已更新: {user_id}")

        except Exception as e:
            logger.error(f"更新用户画像失败: {e}")

    async def get_recommendations(self, user_id: str, recommendation_type: RecommendationType = None,
                                  count: int = 10, asset_type: AssetType = None) -> List[Recommendation]:
        """获取推荐结果（支持资产类型）"""
        try:
            import time
            start_time = time.time()

            # 如果没有指定推荐类型，但指定了资产类型，则转换
            if recommendation_type is None and asset_type is not None:
                recommendation_type = asset_type_to_recommendation_type(asset_type)

            # 检查缓存
            cache_key = f"{user_id}_{recommendation_type}_{count}"
            cached_recommendations = self._get_cached_recommendations(cache_key)

            if cached_recommendations:
                self.recommendation_stats['cache_hits'] += 1
                return cached_recommendations

            self.recommendation_stats['cache_misses'] += 1

            # 确保模型已训练
            if not self._model_trained:
                await self._train_models()

            # 生成推荐
            recommendations = await self._generate_recommendations(user_id, recommendation_type, count)

            # 缓存结果
            self._cache_recommendations(cache_key, recommendations)

            # 更新统计
            recommendation_time = time.time() - start_time
            self._update_recommendation_stats(recommendation_time)

            logger.info(f"为用户 {user_id} 生成了 {len(recommendations)} 个推荐")
            return recommendations

        except Exception as e:
            logger.error(f"获取推荐失败: {e}")
            return []

    async def _generate_recommendations(self, user_id: str, recommendation_type: RecommendationType = None,
                                        count: int = 10) -> List[Recommendation]:
        """生成推荐结果"""
        try:
            recommendations = []

            logger.info(f"开始生成推荐 - 用户: {user_id}, 类型: {recommendation_type}, 数量: {count}")

            # 获取用户画像
            user_profile = self.user_profiles.get(user_id)
            logger.info(f"用户画像存在: {user_profile is not None}")

            if not user_profile:
                # 为新用户生成基于热门内容的推荐
                logger.info("用户无画像，使用热门推荐策略")
                return await self._generate_popular_recommendations(user_id, recommendation_type, count)

            # 协同过滤推荐
            cf_recommendations = await self._collaborative_filtering_recommendations(user_id, recommendation_type, count // 2)
            recommendations.extend(cf_recommendations)
            logger.info(f"协同过滤推荐数量: {len(cf_recommendations)}")

            # 内容基础推荐
            content_recommendations = await self._content_based_recommendations(user_id, recommendation_type, count // 2)
            recommendations.extend(content_recommendations)
            logger.info(f"内容基础推荐数量: {len(content_recommendations)}")

            # ✅ 修复：如果协同过滤和内容推荐都没有结果，降级到热门推荐
            if len(recommendations) == 0:
                logger.warning("协同过滤和内容推荐均无结果，降级到热门推荐")
                return await self._generate_popular_recommendations(user_id, recommendation_type, count)

            # 去重和排序
            recommendations = self._deduplicate_and_rank_recommendations(recommendations)
            logger.info(f"去重后推荐数量: {len(recommendations)}")

            # 限制数量
            recommendations = recommendations[:count]
            logger.info(f"最终推荐数量: {len(recommendations)}")

            return recommendations

        except Exception as e:
            logger.error(f"生成推荐失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def _collaborative_filtering_recommendations(self, user_id: str, recommendation_type: RecommendationType = None,
                                                       count: int = 10) -> List[Recommendation]:
        """协同过滤推荐"""
        try:
            recommendations = []

            if self.user_item_matrix is None or user_id not in self.user_item_matrix.index:
                return recommendations

            # 获取用户相似度
            user_similarities = self._get_user_similarities(user_id)

            # 获取相似用户喜欢的内容
            similar_users = user_similarities.head(10).index.tolist()

            for similar_user in similar_users:
                if similar_user == user_id:
                    continue

                # 获取相似用户的高评分项目
                user_ratings = self.user_item_matrix.loc[similar_user]
                high_rated_items = user_ratings[user_ratings > 0.7].index.tolist()

                for item_id in high_rated_items:
                    # 检查用户是否已经交互过
                    if self.user_item_matrix.loc[user_id, item_id] == 0:
                        item = self.content_items.get(item_id)
                        if item and (not recommendation_type or item.item_type == recommendation_type):
                            similarity_score = user_similarities[similar_user]

                            # 转换推荐类型为资产类型
                            asset_type = recommendation_type_to_asset_type(item.item_type)
                            
                            # 生成推荐理由
                            if self.explanation_generator:
                                explanation = self.explanation_generator.generate_explanation(
                                    Recommendation(
                                        user_id=user_id,
                                        item_id=item_id,
                                        item_type=item.item_type,
                                        score=similarity_score * user_ratings[item_id],
                                        reason=RecommendationReason.SIMILAR_USERS,
                                        title=item.title,
                                        description=item.description,
                                        confidence=similarity_score,
                                        asset_type=asset_type
                                    )
                                )
                            else:
                                explanation = f"与您兴趣相似的用户也喜欢这个内容"
                            
                            recommendation = Recommendation(
                                user_id=user_id,
                                item_id=item_id,
                                item_type=item.item_type,
                                score=similarity_score * user_ratings[item_id],
                                reason=RecommendationReason.SIMILAR_USERS,
                                title=item.title,
                                description=item.description,
                                explanation=explanation,
                                confidence=similarity_score,
                                asset_type=asset_type
                            )

                            recommendations.append(recommendation)

            return recommendations

        except Exception as e:
            logger.error(f"协同过滤推荐失败: {e}")
            return []

    async def _content_based_recommendations(self, user_id: str, recommendation_type: RecommendationType = None,
                                             count: int = 10) -> List[Recommendation]:
        """内容基础推荐"""
        try:
            recommendations = []

            user_profile = self.user_profiles.get(user_id)
            if not user_profile:
                return recommendations

            # 获取用户历史偏好
            user_preferences = self._get_user_content_preferences(user_id)

            # 计算内容相似度
            for item_id, item in self.content_items.items():
                if recommendation_type and item.item_type != recommendation_type:
                    continue

                # 检查用户是否已经交互过
                if self._has_user_interacted(user_id, item_id):
                    continue

                # 计算相似度分数
                similarity_score = self._calculate_content_similarity(user_preferences, item)

                if similarity_score > self.similarity_threshold:
                    # 转换推荐类型为资产类型
                    asset_type = recommendation_type_to_asset_type(item.item_type)

                    recommendation = Recommendation(
                        user_id=user_id,
                        item_id=item_id,
                        item_type=item.item_type,
                        score=similarity_score,
                        reason=RecommendationReason.CONTENT_SIMILARITY,
                        title=item.title,
                        description=item.description,
                        explanation=f"基于您的历史偏好推荐",
                        confidence=similarity_score,
                        asset_type=asset_type
                    )

                    recommendations.append(recommendation)

            return recommendations

        except Exception as e:
            logger.error(f"内容基础推荐失败: {e}")
            return []

    async def _generate_popular_recommendations(self, user_id: str, recommendation_type: RecommendationType = None,
                                                count: int = 10) -> List[Recommendation]:
        """生成热门推荐（用于新用户）"""
        try:
            recommendations = []

            logger.info(f"生成热门推荐 - 用户: {user_id}, 类型: {recommendation_type}, 数量: {count}")
            logger.info(f"当前内容项总数: {len(self.content_items)}")

            # 按热度排序内容
            # ✅ 修复：如果所有热度都是0，使用创建时间作为次要排序条件
            popular_items = sorted(
                self.content_items.values(),
                key=lambda x: (x.view_count + x.like_count * 2 + x.share_count * 3, x.created_at),
                reverse=True
            )

            logger.info(f"排序后内容项数量: {len(popular_items)}")

            for item in popular_items[:count]:
                if recommendation_type and item.item_type != recommendation_type:
                    continue

                # ✅ 修复：计算热度分数，如果热度为0则使用基础分数0.5
                heat_value = item.view_count + item.like_count * 2 + item.share_count * 3
                if heat_value > 0:
                    popularity_score = heat_value / 100
                    popularity_score = min(1.0, popularity_score)
                else:
                    # 所有新内容给予基础分数0.5
                    popularity_score = 0.5

                # 转换推荐类型为资产类型
                asset_type = recommendation_type_to_asset_type(item.item_type)

                recommendation = Recommendation(
                    user_id=user_id,
                    item_id=item.item_id,
                    item_type=item.item_type,
                    score=popularity_score,
                    reason=RecommendationReason.TRENDING,
                    title=item.title,
                    description=item.description,
                    explanation="热门内容推荐" if heat_value > 0 else "新内容推荐",
                    confidence=0.7,
                    asset_type=asset_type,
                    metadata=item.metadata
                )

                recommendations.append(recommendation)

            logger.info(f"生成了 {len(recommendations)} 个热门推荐")
            return recommendations

        except Exception as e:
            logger.error(f"生成热门推荐失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    def _update_user_profile(self, interaction: UserInteraction):
        """更新用户画像"""
        try:
            user_id = interaction.user_id

            if user_id not in self.user_profiles:
                self.user_profiles[user_id] = UserProfile(
                    user_id=user_id,
                    registration_date=datetime.now(),
                    last_active=interaction.timestamp
                )

            profile = self.user_profiles[user_id]
            profile.last_active = interaction.timestamp

            # 更新交互模式
            interaction_key = f"{interaction.interaction_type}_{interaction.item_id}"
            profile.interaction_patterns[interaction_key] = profile.interaction_patterns.get(interaction_key, 0) + 1

            # 更新偏好
            item = self.content_items.get(interaction.item_id)
            if item:
                # 更新标签偏好
                for tag in item.tags:
                    if tag not in profile.preferred_stocks:  # 这里应该根据实际情况调整
                        profile.preferred_stocks.append(tag)

                # 更新分类偏好
                for category in item.categories:
                    if category not in profile.preferred_sectors:
                        profile.preferred_sectors.append(category)

            # 重新计算特征向量
            self._compute_user_features(profile)

        except Exception as e:
            logger.error(f"更新用户画像失败: {e}")

    def _update_content_stats(self, interaction: UserInteraction):
        """更新内容统计"""
        try:
            item_id = interaction.item_id

            if item_id in self.content_items:
                item = self.content_items[item_id]

                if interaction.interaction_type == 'view':
                    item.view_count += 1
                elif interaction.interaction_type == 'like':
                    item.like_count += 1
                elif interaction.interaction_type == 'share':
                    item.share_count += 1

                item.updated_at = datetime.now()

        except Exception as e:
            logger.error(f"更新内容统计失败: {e}")

    def _extract_content_features(self, item: ContentItem):
        """提取内容特征"""
        try:
            # 过滤None值并合并文本特征
            valid_tags = [str(tag) for tag in item.tags if tag is not None and tag != '']
            valid_keywords = [str(kw) for kw in item.keywords if kw is not None and kw != '']
            valid_categories = [str(cat) for cat in item.categories if cat is not None and cat != '']

            text_features = f"{item.title} {item.description} {' '.join(valid_tags)} {' '.join(valid_keywords)}"

            # 使用TF-IDF提取特征（这里需要先训练vectorizer）
            # 暂时使用简单的特征表示
            feature_dict = {}

            # 标签特征
            for tag in valid_tags:
                if tag:  # 再次确保非空
                    feature_dict[f"tag_{tag}"] = 1

            # 分类特征
            for category in valid_categories:
                if category:  # 再次确保非空
                    feature_dict[f"category_{category}"] = 1

            # 关键词特征
            for keyword in valid_keywords:
                if keyword:  # 再次确保非空
                    feature_dict[f"keyword_{keyword}"] = 1

            # 转换为向量（简化实现）
            # 如果没有特征，创建一个默认的零向量
            if feature_dict:
                item.feature_vector = np.array(list(feature_dict.values()))
            else:
                item.feature_vector = np.array([0.0])  # 默认零向量

        except Exception as e:
            logger.error(f"提取内容特征失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

    def _compute_user_features(self, profile: UserProfile):
        """计算用户特征向量"""
        try:
            feature_dict = {}

            # 偏好特征
            for stock in profile.preferred_stocks:
                feature_dict[f"stock_{stock}"] = 1

            for sector in profile.preferred_sectors:
                feature_dict[f"sector_{sector}"] = 1

            for indicator in profile.preferred_indicators:
                feature_dict[f"indicator_{indicator}"] = 1

            # 行为特征
            for pattern, count in profile.interaction_patterns.items():
                feature_dict[f"pattern_{pattern}"] = count

            # 转换为向量（简化实现）
            profile.feature_vector = np.array(list(feature_dict.values()))

        except Exception as e:
            logger.error(f"计算用户特征失败: {e}")

    async def _train_models(self):
        """训练推荐模型"""
        try:
            if self._training_active:
                return

            self._training_active = True

            logger.info("开始训练推荐模型...")

            # 构建用户-物品矩阵
            await self._build_user_item_matrix()

            # 计算相似度矩阵
            await self._compute_similarity_matrices()

            # 训练SVD模型
            await self._train_svd_model()

            self._model_trained = True
            self._training_active = False

            logger.info("推荐模型训练完成")

        except Exception as e:
            logger.error(f"训练推荐模型失败: {e}")
            self._training_active = False

    async def _build_user_item_matrix(self):
        """构建用户-物品矩阵"""
        try:
            # 收集所有用户和物品
            users = set()
            items = set()

            for interaction in self.interactions:
                users.add(interaction.user_id)
                items.add(interaction.item_id)

            # 创建矩阵
            matrix_data = defaultdict(lambda: defaultdict(float))

            for interaction in self.interactions:
                user_id = interaction.user_id
                item_id = interaction.item_id

                # 计算评分（基于交互类型和频率）
                score = 0.0
                if interaction.interaction_type == 'view':
                    score = 0.5
                elif interaction.interaction_type == 'like':
                    score = 1.0
                elif interaction.interaction_type == 'share':
                    score = 1.5
                elif interaction.interaction_type == 'bookmark':
                    score = 1.2

                # 考虑交互时长
                if interaction.duration:
                    score *= min(2.0, interaction.duration / 60)  # 最多2倍权重

                matrix_data[user_id][item_id] += score

            # 转换为DataFrame
            self.user_item_matrix = pd.DataFrame(matrix_data).fillna(0).T

            logger.info(f"用户-物品矩阵构建完成: {self.user_item_matrix.shape}")

        except Exception as e:
            logger.error(f"构建用户-物品矩阵失败: {e}")

    async def _compute_similarity_matrices(self):
        """计算相似度矩阵"""
        try:
            if self.user_item_matrix is None or self.user_item_matrix.empty:
                return

            # 计算用户相似度
            user_similarity = cosine_similarity(self.user_item_matrix)
            self.user_similarity_matrix = pd.DataFrame(
                user_similarity,
                index=self.user_item_matrix.index,
                columns=self.user_item_matrix.index
            )

            # 计算物品相似度
            item_similarity = cosine_similarity(self.user_item_matrix.T)
            self.content_similarity_matrix = pd.DataFrame(
                item_similarity,
                index=self.user_item_matrix.columns,
                columns=self.user_item_matrix.columns
            )

            logger.info("相似度矩阵计算完成")

        except Exception as e:
            logger.error(f"计算相似度矩阵失败: {e}")

    async def _train_svd_model(self):
        """训练SVD模型"""
        try:
            if self.user_item_matrix is None or self.user_item_matrix.empty:
                return

            # 训练SVD模型进行降维
            self.svd_model.fit(self.user_item_matrix)

            logger.info("SVD模型训练完成")

        except Exception as e:
            logger.error(f"训练SVD模型失败: {e}")

    def _get_user_similarities(self, user_id: str) -> pd.Series:
        """获取用户相似度"""
        try:
            if self.user_similarity_matrix is None or user_id not in self.user_similarity_matrix.index:
                return pd.Series()

            similarities = self.user_similarity_matrix.loc[user_id]
            return similarities.sort_values(ascending=False)

        except Exception as e:
            logger.error(f"获取用户相似度失败: {e}")
            return pd.Series()

    def _get_user_content_preferences(self, user_id: str) -> Dict[str, float]:
        """获取用户内容偏好"""
        try:
            preferences = defaultdict(float)

            # 基于历史交互计算偏好
            user_interactions = [i for i in self.interactions if i.user_id == user_id]

            for interaction in user_interactions:
                item = self.content_items.get(interaction.item_id)
                if item:
                    weight = 1.0
                    if interaction.interaction_type == 'like':
                        weight = 2.0
                    elif interaction.interaction_type == 'share':
                        weight = 3.0

                    # 更新标签偏好
                    for tag in item.tags:
                        preferences[f"tag_{tag}"] += weight

                    # 更新分类偏好
                    for category in item.categories:
                        preferences[f"category_{category}"] += weight

            return dict(preferences)

        except Exception as e:
            logger.error(f"获取用户内容偏好失败: {e}")
            return {}

    def _calculate_content_similarity(self, user_preferences: Dict[str, float], item: ContentItem) -> float:
        """计算内容相似度"""
        try:
            similarity_score = 0.0
            total_weight = 0.0

            # 标签相似度
            for tag in item.tags:
                tag_key = f"tag_{tag}"
                if tag_key in user_preferences:
                    similarity_score += user_preferences[tag_key]
                    total_weight += user_preferences[tag_key]

            # 分类相似度
            for category in item.categories:
                category_key = f"category_{category}"
                if category_key in user_preferences:
                    similarity_score += user_preferences[category_key]
                    total_weight += user_preferences[category_key]

            # 归一化
            if total_weight > 0:
                similarity_score = similarity_score / total_weight
                similarity_score = min(1.0, similarity_score / 10)  # 缩放到0-1范围

            return similarity_score

        except Exception as e:
            logger.error(f"计算内容相似度失败: {e}")
            return 0.0

    def _has_user_interacted(self, user_id: str, item_id: str) -> bool:
        """检查用户是否已经与内容交互过"""
        try:
            for interaction in self.interactions:
                if interaction.user_id == user_id and interaction.item_id == item_id:
                    return True
            return False
        except Exception as e:
            logger.error(f"检查用户交互失败: {e}")
            return False

    def _deduplicate_and_rank_recommendations(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """去重和排序推荐结果"""
        try:
            # 去重
            seen_items = set()
            unique_recommendations = []

            for rec in recommendations:
                if rec.item_id not in seen_items:
                    seen_items.add(rec.item_id)
                    unique_recommendations.append(rec)

            # 按分数排序
            unique_recommendations.sort(key=lambda x: x.score, reverse=True)

            return unique_recommendations

        except Exception as e:
            logger.error(f"去重和排序推荐失败: {e}")
            return recommendations

    def _get_cached_recommendations(self, cache_key: str) -> Optional[List[Recommendation]]:
        """获取缓存的推荐结果"""
        try:
            if cache_key in self.recommendation_cache:
                recommendations = self.recommendation_cache[cache_key]

                # 检查是否过期
                if recommendations and recommendations[0].expires_at:
                    if datetime.now() < recommendations[0].expires_at:
                        return recommendations
                    else:
                        del self.recommendation_cache[cache_key]

            return None

        except Exception as e:
            logger.error(f"获取缓存推荐失败: {e}")
            return None

    def _cache_recommendations(self, cache_key: str, recommendations: List[Recommendation]):
        """缓存推荐结果"""
        try:
            # 设置过期时间
            expires_at = datetime.now() + self.cache_ttl
            for rec in recommendations:
                rec.expires_at = expires_at

            self.recommendation_cache[cache_key] = recommendations

        except Exception as e:
            logger.error(f"缓存推荐失败: {e}")

    def _update_recommendation_stats(self, recommendation_time: float):
        """更新推荐统计"""
        try:
            self.recommendation_stats['total_recommendations'] += 1

            # 更新平均推荐时间
            total_recs = self.recommendation_stats['total_recommendations']
            current_avg = self.recommendation_stats['avg_recommendation_time']
            self.recommendation_stats['avg_recommendation_time'] = (current_avg * (total_recs - 1) + recommendation_time) / total_recs

        except Exception as e:
            logger.error(f"更新推荐统计失败: {e}")

    def get_recommendation_stats(self) -> Dict[str, Any]:
        """获取推荐统计信息"""
        try:
            stats = self.recommendation_stats.copy()

            # 添加额外统计
            stats['total_users'] = len(self.user_profiles)
            stats['total_items'] = len(self.content_items)
            stats['total_interactions'] = len(self.interactions)
            stats['cache_size'] = len(self.recommendation_cache)
            stats['model_trained'] = self._model_trained

            # 计算缓存命中率
            total_requests = stats['cache_hits'] + stats['cache_misses']
            if total_requests > 0:
                stats['cache_hit_rate'] = stats['cache_hits'] / total_requests
            else:
                stats['cache_hit_rate'] = 0.0

            return stats

        except Exception as e:
            logger.error(f"获取推荐统计失败: {e}")
            return {}

    def clear_cache(self):
        """清除推荐缓存"""
        try:
            self.recommendation_cache.clear()
            logger.info("推荐缓存已清除")
        except Exception as e:
            logger.error(f"清除缓存失败: {e}")

    def save_model(self, file_path: str):
        """保存推荐模型"""
        try:
            model_data = {
                'user_item_matrix': self.user_item_matrix,
                'user_similarity_matrix': self.user_similarity_matrix,
                'content_similarity_matrix': self.content_similarity_matrix,
                'svd_model': self.svd_model,
                'tfidf_vectorizer': self.tfidf_vectorizer
            }

            with open(file_path, 'wb') as f:
                pickle.dump(model_data, f)

            logger.info(f"推荐模型已保存: {file_path}")

        except Exception as e:
            logger.error(f"保存推荐模型失败: {e}")

    def load_model(self, file_path: str):
        """加载推荐模型"""
        try:
            with open(file_path, 'rb') as f:
                model_data = pickle.load(f)

            self.user_item_matrix = model_data.get('user_item_matrix')
            self.user_similarity_matrix = model_data.get('user_similarity_matrix')
            self.content_similarity_matrix = model_data.get('content_similarity_matrix')
            self.svd_model = model_data.get('svd_model')
            self.tfidf_vectorizer = model_data.get('tfidf_vectorizer')

            self._model_trained = True

            logger.info(f"推荐模型已加载: {file_path}")

        except Exception as e:
            logger.error(f"加载推荐模型失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            # 清理缓存
            self.clear_cache()

            # 清理数据
            self.user_profiles.clear()
            self.content_items.clear()
            self.interactions.clear()

            # 重置状态
            self._model_trained = False

            logger.info("智能推荐引擎资源清理完成")

        except Exception as e:
            logger.error(f"资源清理失败: {e}")
