#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI驱动的智能图表推荐

基于用户行为的图表建议、智能推荐算法、个性化定制

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
import time
import json
import pickle
from typing import Dict, List, Optional, Tuple, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque, Counter
from datetime import datetime, timedelta
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
import warnings
warnings.filterwarnings('ignore')

class UserActivityType(Enum):
    """用户活动类型"""
    VIEW_CHART = "view_chart"
    CREATE_CHART = "create_chart"
    MODIFY_CHART = "modify_chart"
    DELETE_CHART = "delete_chart"
    EXPORT_CHART = "export_chart"
    SHARE_CHART = "share_chart"
    FAVORITE_CHART = "favorite_chart"

class ChartType(Enum):
    """图表类型"""
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    SCATTER_PLOT = "scatter_plot"
    CANDLESTICK = "candlestick"
    HEATMAP = "heatmap"
    PIE_CHART = "pie_chart"
    AREA_CHART = "area_chart"
    HISTOGRAM = "histogram"
    BOX_PLOT = "box_plot"
    SCATTER_3D = "scatter_3d"

class RecommendationStrategy(Enum):
    """推荐策略"""
    COLLABORATIVE_FILTERING = "collaborative"
    CONTENT_BASED = "content_based"
    HYBRID = "hybrid"
    TRENDING = "trending"
    PERSONALIZED = "personalized"

@dataclass
class UserBehavior:
    """用户行为数据"""
    user_id: str
    activity_type: UserActivityType
    chart_type: ChartType
    timestamp: float
    session_id: str
    context_data: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    satisfaction_score: float = 0.0  # 0-1评分

@dataclass
class ChartContext:
    """图表上下文"""
    chart_id: str
    chart_type: ChartType
    data_source: str
    data_size: int
    time_range: str
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    complexity_score: float = 0.0
    visual_elements: Dict[str, Any] = field(default_factory=dict)
    created_by: str = ""
    created_at: float = 0.0
    last_modified: float = 0.0
    view_count: int = 0
    rating: float = 0.0

@dataclass
class RecommendationResult:
    """推荐结果"""
    chart_type: ChartType
    confidence_score: float
    reasoning: str
    alternative_types: List[Tuple[ChartType, float]] = field(default_factory=list)
    expected_user_satisfaction: float = 0.0
    adaptation_suggestions: List[str] = field(default_factory=list)

class UserBehaviorAnalyzer:
    """用户行为分析器"""
    
    def __init__(self):
        self.user_profiles = {}
        self.behavior_history = defaultdict(deque)
        self.pattern_cache = {}
        self.satisfaction_predictor = None
        
    def record_behavior(self, behavior: UserBehavior):
        """记录用户行为"""
        user_id = behavior.user_id
        
        # 记录行为历史
        self.behavior_history[user_id].append(behavior)
        
        # 限制历史长度
        if len(self.behavior_history[user_id]) > 1000:
            self.behavior_history[user_id].popleft()
        
        # 更新用户画像
        self._update_user_profile(user_id, behavior)
    
    def _update_user_profile(self, user_id: str, behavior: UserBehavior):
        """更新用户画像"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'preferred_chart_types': Counter(),
                'activity_patterns': defaultdict(int),
                'session_durations': [],
                'satisfaction_scores': [],
                'last_active': time.time(),
                'total_activities': 0,
                'expertise_level': 0.5,  # 0-1, 0=新手, 1=专家
                'preferences': {
                    'visual_style': 'default',
                    'color_scheme': 'default',
                    'complexity_preference': 0.5
                }
            }
        
        profile = self.user_profiles[user_id]
        
        # 更新图表类型偏好
        profile['preferred_chart_types'][behavior.chart_type.value] += 1
        
        # 更新活动模式
        profile['activity_patterns'][behavior.activity_type.value] += 1
        
        # 更新会话持续时间
        if behavior.duration_seconds > 0:
            profile['session_durations'].append(behavior.duration_seconds)
            if len(profile['session_durations']) > 50:  # 限制数据长度
                profile['session_durations'].pop(0)
        
        # 更新满意度评分
        if behavior.satisfaction_score > 0:
            profile['satisfaction_scores'].append(behavior.satisfaction_score)
            if len(profile['satisfaction_scores']) > 50:
                profile['satisfaction_scores'].pop(0)
        
        # 更新专家等级（基于总活动数和满意度）
        profile['total_activities'] += 1
        profile['last_active'] = time.time()
        
        avg_satisfaction = np.mean(profile['satisfaction_scores']) if profile['satisfaction_scores'] else 0.5
        activity_score = min(profile['total_activities'] / 100, 1.0)  # 100次活动达到满级
        
        profile['expertise_level'] = (activity_score + avg_satisfaction) / 2
        
        # 更新偏好设置
        self._infer_preferences(user_id)
    
    def _infer_preferences(self, user_id: str):
        """推断用户偏好"""
        profile = self.user_profiles[user_id]
        
        # 基于历史行为推断偏好
        behavior_list = list(self.behavior_history[user_id])
        
        # 分析视觉风格偏好
        view_activities = [b for b in behavior_list if b.activity_type == UserActivityType.VIEW_CHART]
        if view_activities:
            # 假设复杂度可以从上下文数据推断
            complexity_scores = [b.context_data.get('complexity_score', 0.5) for b in view_activities]
            if complexity_scores:
                avg_complexity = np.mean(complexity_scores)
                if avg_complexity > 0.7:
                    profile['preferences']['visual_style'] = 'detailed'
                elif avg_complexity < 0.3:
                    profile['preferences']['visual_style'] = 'minimal'
        
        # 分析颜色偏好（基于用户选择的历史图表）
        chart_activities = [b for b in behavior_list if b.activity_type in [UserActivityType.CREATE_CHART, UserActivityType.MODIFY_CHART]]
        # 这里可以分析用户实际使用的颜色配置
        
        # 设置复杂度偏好
        if profile['expertise_level'] > 0.7:
            profile['preferences']['complexity_preference'] = 0.8
        elif profile['expertise_level'] < 0.3:
            profile['preferences']['complexity_preference'] = 0.2
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户画像"""
        return self.user_profiles.get(user_id)
    
    def find_similar_users(self, user_id: str, top_k: int = 10) -> List[str]:
        """找到相似用户"""
        if user_id not in self.user_profiles:
            return []
        
        target_profile = self.user_profiles[user_id]
        similarities = []
        
        for other_user, profile in self.user_profiles.items():
            if other_user == user_id:
                continue
            
            similarity = self._calculate_user_similarity(target_profile, profile)
            similarities.append((other_user, similarity))
        
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [user for user, _ in similarities[:top_k]]
    
    def _calculate_user_similarity(self, profile1: Dict[str, Any], profile2: Dict[str, Any]) -> float:
        """计算用户相似度"""
        # 基于图表类型偏好的相似度
        types1 = set(profile1['preferred_chart_types'].keys())
        types2 = set(profile2['preferred_chart_types'].keys())
        
        if not types1 or not types2:
            return 0.0
        
        intersection = len(types1.intersection(types2))
        union = len(types1.union(types2))
        type_similarity = intersection / union if union > 0 else 0.0
        
        # 基于活动模式的相似度
        activities1 = profile1['activity_patterns']
        activities2 = profile2['activity_patterns']
        
        activity_similarity = 0.0
        if activities1 and activities2:
            common_activities = set(activities1.keys()).intersection(set(activities2.keys()))
            if common_activities:
                activity_similarity = len(common_activities) / len(activities1.keys().union(activities2.keys()))
        
        # 基于专家等级的相似度
        expertise_diff = abs(profile1['expertise_level'] - profile2['expertise_level'])
        expertise_similarity = 1.0 - expertise_diff
        
        # 综合相似度
        total_similarity = (
            type_similarity * 0.4 +
            activity_similarity * 0.3 +
            expertise_similarity * 0.3
        )
        
        return total_similarity
    
    def analyze_behavior_patterns(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """分析行为模式"""
        if user_id not in self.behavior_history:
            return {}
        
        cutoff_time = time.time() - (days * 24 * 3600)
        recent_behaviors = [
            b for b in self.behavior_history[user_id]
            if b.timestamp > cutoff_time
        ]
        
        if not recent_behaviors:
            return {}
        
        # 分析活动频率
        daily_activity = defaultdict(int)
        hourly_activity = defaultdict(int)
        chart_type_usage = Counter()
        session_patterns = []
        
        current_session = []
        session_start = None
        
        for behavior in sorted(recent_behaviors, key=lambda x: x.timestamp):
            date = datetime.fromtimestamp(behavior.timestamp)
            daily_activity[date.strftime('%Y-%m-%d')] += 1
            hourly_activity[date.hour] += 1
            chart_type_usage[behavior.chart_type.value] += 1
            
            # 会话分析
            if session_start is None:
                session_start = behavior.timestamp
                current_session = [behavior]
            else:
                # 如果超过30分钟认为是新的会话
                if behavior.timestamp - session_start > 1800:
                    if current_session:
                        session_patterns.append({
                            'start': session_start,
                            'duration': session_start - current_session[0].timestamp,
                            'activities': len(current_session)
                        })
                    session_start = behavior.timestamp
                    current_session = [behavior]
                else:
                    current_session.append(behavior)
        
        # 最后一个会话
        if current_session and session_start:
            session_patterns.append({
                'start': session_start,
                'duration': recent_behaviors[-1].timestamp - current_session[0].timestamp,
                'activities': len(current_session)
            })
        
        return {
            'total_activities': len(recent_behaviors),
            'daily_activity': dict(daily_activity),
            'hourly_activity': dict(hourly_activity),
            'chart_type_usage': dict(chart_type_usage),
            'session_patterns': session_patterns,
            'most_active_day': max(daily_activity.items(), key=lambda x: x[1]) if daily_activity else None,
            'most_active_hour': max(hourly_activity.items(), key=lambda x: x[1]) if hourly_activity else None,
            'avg_session_duration': np.mean([s['duration'] for s in session_patterns]) if session_patterns else 0,
            'preferred_chart_types': chart_type_usage.most_common(5)
        }

class ContentBasedRecommender:
    """基于内容的推荐器"""
    
    def __init__(self):
        self.chart_features = {}
        self.feature_extractor = TfidfVectorizer(max_features=100, stop_words='english')
        self.similarity_matrix = None
        self.is_trained = False
    
    def add_chart(self, chart: ChartContext):
        """添加图表"""
        self.chart_features[chart.chart_id] = {
            'chart_type': chart.chart_type.value,
            'tags': ' '.join(chart.tags),
            'categories': ' '.join(chart.categories),
            'data_source': chart.data_source,
            'complexity': chart.complexity_score,
            'visual_elements': json.dumps(chart.visual_elements)
        }
    
    def train(self):
        """训练推荐模型"""
        if len(self.chart_features) < 2:
            return
        
        # 构建特征矩阵
        feature_matrix = []
        chart_ids = []
        
        for chart_id, features in self.chart_features.items():
            feature_vector = [
                features['chart_type'],
                features['tags'],
                features['categories'],
                features['data_source'],
                str(features['complexity']),
                features['visual_elements']
            ]
            feature_matrix.append(' '.join(feature_vector))
            chart_ids.append(chart_id)
        
        # TF-IDF向量化
        tfidf_matrix = self.feature_extractor.fit_transform(feature_matrix)
        
        # 计算相似度矩阵
        self.similarity_matrix = cosine_similarity(tfidf_matrix)
        self.chart_ids = chart_ids
        self._chart_id_index = {cid: idx for idx, cid in enumerate(chart_ids)}
        self.is_trained = True
    
    def get_similar_charts(self, chart_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """获取相似图表"""
        if not self.is_trained:
            return []

        chart_index = self._chart_id_index.get(chart_id)
        if chart_index is None:
            return []

        similarities = self.similarity_matrix[chart_index]
        
        # 获取相似度最高的图表
        similar_indices = np.argsort(similarities)[::-1][1:top_k+1]  # 排除自己
        
        similar_charts = []
        for idx in similar_indices:
            similar_chart_id = self.chart_ids[idx]
            similarity_score = similarities[idx]
            similar_charts.append((similar_chart_id, float(similarity_score)))
        
        return similar_charts
    
    def recommend_by_features(self, user_preferences: Dict[str, Any], 
                            data_characteristics: Dict[str, Any], 
                            top_k: int = 5) -> List[RecommendationResult]:
        """基于用户偏好和数据特征推荐图表"""
        recommendations = []
        
        # 数据特征分析
        data_size = data_characteristics.get('data_size', 100)
        categories_count = data_characteristics.get('categories_count', 0)
        has_time_series = data_characteristics.get('has_time_series', False)
        has_numeric_data = data_characteristics.get('has_numeric_data', True)
        
        # 用户偏好
        complexity_pref = user_preferences.get('complexity_preference', 0.5)
        expertise_level = user_preferences.get('expertise_level', 0.5)
        
        # 候选图表类型
        candidate_types = self._get_candidate_chart_types(
            data_size, categories_count, has_time_series, has_numeric_data
        )
        
        # 为每种候选类型计算推荐分数
        for chart_type_str, base_score in candidate_types:
            chart_type = ChartType(chart_type_str)
            
            # 基于复杂度和专业水平调整分数
            complexity_match = self._calculate_complexity_match(chart_type, complexity_pref)
            expertise_match = self._calculate_expertise_match(chart_type, expertise_level)
            
            final_score = base_score * complexity_match * expertise_match
            
            # 生成推荐理由
            reasoning = self._generate_reasoning(chart_type, data_characteristics, user_preferences)
            
            recommendation = RecommendationResult(
                chart_type=chart_type,
                confidence_score=final_score,
                reasoning=reasoning,
                expected_user_satisfaction=final_score,
                adaptation_suggestions=self._get_adaptation_suggestions(chart_type, user_preferences)
            )
            
            recommendations.append(recommendation)
        
        # 按分数排序
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        return recommendations[:top_k]
    
    def _get_candidate_chart_types(self, data_size: int, categories_count: int, 
                                 has_time_series: bool, has_numeric_data: bool) -> List[Tuple[str, float]]:
        """获取候选图表类型"""
        candidates = []
        
        # 时间序列数据
        if has_time_series and has_numeric_data:
            candidates.extend([
                (ChartType.LINE_CHART.value, 0.9),
                (ChartType.AREA_CHART.value, 0.8),
                (ChartType.CANDLESTICK.value, 0.7)
            ])
        
        # 分类数据
        if categories_count > 0 and has_numeric_data:
            if categories_count <= 10:  # 少类别适合饼图/柱状图
                candidates.extend([
                    (ChartType.PIE_CHART.value, 0.8),
                    (ChartType.BAR_CHART.value, 0.9),
                    (ChartType.HISTOGRAM.value, 0.7)
                ])
            else:  # 多类别适合柱状图/热力图
                candidates.extend([
                    (ChartType.BAR_CHART.value, 0.9),
                    (ChartType.HEATMAP.value, 0.8)
                ])
        
        # 数值数据
        if has_numeric_data:
            if data_size >= 1000:  # 大数据集
                candidates.extend([
                    (ChartType.SCATTER_PLOT.value, 0.8),
                    (ChartType.BOX_PLOT.value, 0.7)
                ])
            else:
                candidates.extend([
                    (ChartType.SCATTER_PLOT.value, 0.9),
                    (ChartType.BAR_CHART.value, 0.8)
                ])
        
        # 默认候选
        if not candidates:
            candidates = [
                (ChartType.BAR_CHART.value, 0.6),
                (ChartType.LINE_CHART.value, 0.6),
                (ChartType.SCATTER_PLOT.value, 0.6)
            ]
        
        return candidates
    
    def _calculate_complexity_match(self, chart_type: ChartType, complexity_pref: float) -> float:
        """计算复杂度匹配度"""
        complexity_scores = {
            ChartType.PIE_CHART: 0.3,
            ChartType.BAR_CHART: 0.4,
            ChartType.LINE_CHART: 0.5,
            ChartType.SCATTER_PLOT: 0.6,
            ChartType.AREA_CHART: 0.6,
            ChartType.HISTOGRAM: 0.7,
            ChartType.HEATMAP: 0.8,
            ChartType.BOX_PLOT: 0.8,
            ChartType.CANDLESTICK: 0.9,
            ChartType.SCATTER_3D: 0.9
        }
        
        chart_complexity = complexity_scores.get(chart_type, 0.5)
        return 1.0 - abs(chart_complexity - complexity_pref)
    
    def _calculate_expertise_match(self, chart_type: ChartType, expertise_level: float) -> float:
        """计算专业水平匹配度"""
        # 简单匹配：专家更喜欢复杂图表
        required_expertise = {
            ChartType.PIE_CHART: 0.2,
            ChartType.BAR_CHART: 0.3,
            ChartType.LINE_CHART: 0.4,
            ChartType.SCATTER_PLOT: 0.5,
            ChartType.AREA_CHART: 0.5,
            ChartType.HISTOGRAM: 0.6,
            ChartType.HEATMAP: 0.7,
            ChartType.BOX_PLOT: 0.7,
            ChartType.CANDLESTICK: 0.8,
            ChartType.SCATTER_3D: 0.9
        }
        
        required_exp = required_expertise.get(chart_type, 0.5)
        return 1.0 - max(0, required_exp - expertise_level)
    
    def _generate_reasoning(self, chart_type: ChartType, data_char: Dict[str, Any], 
                          user_pref: Dict[str, Any]) -> str:
        """生成推荐理由"""
        reasons = []
        
        # 基于数据特征的推荐理由
        if data_char.get('has_time_series'):
            reasons.append("数据包含时间序列信息")
        
        if data_char.get('categories_count', 0) > 0:
            reasons.append("数据包含分类信息")
        
        # 基于用户偏好的推荐理由
        complexity = user_pref.get('complexity_preference', 0.5)
        if complexity > 0.7:
            reasons.append("您偏好复杂的数据可视化")
        elif complexity < 0.3:
            reasons.append("您偏好简洁的图表展示")
        
        # 特定图表类型的推荐理由
        reasoning_map = {
            ChartType.LINE_CHART: "适合展示数据趋势变化",
            ChartType.BAR_CHART: "适合比较不同类别的数值",
            ChartType.PIE_CHART: "适合展示各部分占整体的比例",
            ChartType.SCATTER_PLOT: "适合展示两个数值变量的关系",
            ChartType.HEATMAP: "适合展示大量数据的密度分布",
            ChartType.CANDLESTICK: "特别适合金融时间序列分析",
            ChartType.HISTOGRAM: "适合展示数据的分布情况",
            ChartType.BOX_PLOT: "适合展示数据的统计特征",
            ChartType.AREA_CHART: "适合展示累积量的变化趋势",
            ChartType.SCATTER_3D: "适合展示三维数据的复杂关系"
        }
        
        specific_reason = reasoning_map.get(chart_type, "基于您的历史偏好推荐")
        reasons.append(specific_reason)
        
        return "；".join(reasons)
    
    def _get_adaptation_suggestions(self, chart_type: ChartType, 
                                  user_pref: Dict[str, Any]) -> List[str]:
        """获取适配建议"""
        suggestions = []
        
        expertise = user_pref.get('expertise_level', 0.5)
        complexity = user_pref.get('complexity_preference', 0.5)
        
        # 基于专业水平的建议
        if expertise < 0.3:
            if chart_type in [ChartType.CANDLESTICK, ChartType.HEATMAP, ChartType.BOX_PLOT]:
                suggestions.append("建议启用数据解读提示功能")
                suggestions.append("可使用简化的视图模式")
        elif expertise > 0.8:
            suggestions.append("可启用高级分析功能")
            suggestions.append("建议添加技术指标显示")
        
        # 基于复杂度偏好的建议
        if complexity < 0.3:
            suggestions.append("建议使用默认配色方案")
            suggestions.append("可隐藏非必要的数据标签")
        elif complexity > 0.8:
            suggestions.append("可启用详细数据提示")
            suggestions.append("建议添加交互式筛选功能")
        
        # 特定图表类型的建议
        if chart_type == ChartType.PIE_CHART:
            suggestions.append("建议限制类别数量不超过8个")
            suggestions.append("可考虑使用环形图提升视觉效果")
        elif chart_type == ChartType.LINE_CHART:
            suggestions.append("建议使用平滑曲线提升视觉效果")
            suggestions.append("可添加数据点标注功能")
        
        return suggestions

class SmartChartRecommender:
    """智能图表推荐主类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 配置
        default_config = {
            'strategy': RecommendationStrategy.HYBRID,
            'collaborative_weight': 0.4,
            'content_weight': 0.4,
            'trending_weight': 0.2,
            'min_user_activities': 5,
            'max_recommendations': 5,
            'cache_recommendations': True,
            'cache_ttl': 3600  # 1小时
        }
        self.config = {**default_config, **(config or {})}
        
        # 组件
        self.behavior_analyzer = UserBehaviorAnalyzer()
        self.content_recommender = ContentBasedRecommender()
        
        # 状态
        self.user_recommendations = {}
        self.chart_catalog = {}
        self.trending_charts = deque(maxlen=100)
        self.global_stats = {
            'total_users': 0,
            'total_charts': 0,
            'total_recommendations': 0,
            'recommendation_accuracy': 0.0
        }
        
        # 缓存
        if self.config['cache_recommendations']:
            self._start_cache_cleanup()
    
    def _start_cache_cleanup(self):
        """启动缓存清理"""
        def cleanup_task():
            while True:
                try:
                    time.sleep(300)  # 5分钟清理一次
                    self._cleanup_expired_cache()
                except Exception as e:
                    print(f"缓存清理错误: {e}")
        
        import threading
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    def record_user_activity(self, behavior: UserBehavior):
        """记录用户活动"""
        self.behavior_analyzer.record_behavior(behavior)
        
        # 更新全局统计
        if behavior.user_id not in [u['user_id'] for u in self.global_stats.get('active_users', [])]:
            self.global_stats['total_users'] += 1
        
        if behavior.activity_type in [UserActivityType.CREATE_CHART, UserActivityType.MODIFY_CHART]:
            self.trending_charts.append(behavior.chart_type)
        
        # 更新推荐缓存
        self._invalidate_user_cache(behavior.user_id)
    
    def add_chart_to_catalog(self, chart: ChartContext):
        """添加图表到目录"""
        self.chart_catalog[chart.chart_id] = chart
        
        # 更新内容推荐器
        self.content_recommender.add_chart(chart)
        
        # 更新全局统计
        self.global_stats['total_charts'] += 1
    
    def get_recommendations(self, user_id: str, data_context: Dict[str, Any], 
                          chart_context: Optional[ChartContext] = None) -> List[RecommendationResult]:
        """获取推荐"""
        # 检查缓存
        cache_key = f"{user_id}_{hash(str(data_context))}"
        if self.config['cache_recommendations'] and cache_key in self.user_recommendations:
            cached_result, timestamp = self.user_recommendations[cache_key]
            if time.time() - timestamp < self.config['cache_ttl']:
                return cached_result
        
        # 获取用户画像
        user_profile = self.behavior_analyzer.get_user_profile(user_id)
        
        # 检查用户是否足够活跃
        if not user_profile or user_profile['total_activities'] < self.config['min_user_activities']:
            # 新用户或活跃度不足，使用内容推荐
            recommendations = self._get_content_based_recommendations(user_id, data_context)
        else:
            # 活跃用户，使用混合推荐
            recommendations = self._get_hybrid_recommendations(user_id, data_context, user_profile)
        
        # 添加替代推荐
        self._add_alternative_recommendations(recommendations, data_context, user_profile)
        
        # 缓存结果
        if self.config['cache_recommendations']:
            self.user_recommendations[cache_key] = (recommendations, time.time())
        
        # 更新统计
        self.global_stats['total_recommendations'] += len(recommendations)
        
        return recommendations[:self.config['max_recommendations']]
    
    def _get_content_based_recommendations(self, user_id: str, 
                                         data_context: Dict[str, Any]) -> List[RecommendationResult]:
        """基于内容的推荐"""
        # 获取默认用户偏好
        default_preferences = {
            'complexity_preference': 0.5,
            'expertise_level': 0.5,
            'visual_style': 'default',
            'color_scheme': 'default'
        }
        
        user_profile = self.behavior_analyzer.get_user_profile(user_id)
        if user_profile:
            default_preferences.update(user_profile['preferences'])
        
        return self.content_recommender.recommend_by_features(
            default_preferences, data_context
        )
    
    def _get_hybrid_recommendations(self, user_id: str, 
                                  data_context: Dict[str, Any],
                                  user_profile: Dict[str, Any]) -> List[RecommendationResult]:
        """混合推荐"""
        recommendations = []
        
        # 1. 基于内容的推荐
        content_recommendations = self.content_recommender.recommend_by_features(
            user_profile['preferences'], data_context
        )
        
        # 2. 协同过滤推荐
        collaborative_recommendations = self._get_collaborative_recommendations(user_id, user_profile)
        
        # 3. 趋势推荐
        trending_recommendations = self._get_trending_recommendations(data_context)
        
        # 合并推荐结果
        all_recommendations = {}
        
        # 添加内容推荐
        for rec in content_recommendations:
            score = rec.confidence_score * self.config['content_weight']
            all_recommendations[rec.chart_type] = RecommendationResult(
                chart_type=rec.chart_type,
                confidence_score=score,
                reasoning=f"[内容推荐] {rec.reasoning}",
                adaptation_suggestions=rec.adaptation_suggestions
            )
        
        # 添加协同过滤推荐
        for rec in collaborative_recommendations:
            if rec.chart_type in all_recommendations:
                all_recommendations[rec.chart_type].confidence_score += rec.confidence_score * self.config['collaborative_weight']
                all_recommendations[rec.chart_type].reasoning += f" [协同推荐] {rec.reasoning}"
            else:
                all_recommendations[rec.chart_type] = RecommendationResult(
                    chart_type=rec.chart_type,
                    confidence_score=rec.confidence_score * self.config['collaborative_weight'],
                    reasoning=f"[协同推荐] {rec.reasoning}",
                    adaptation_suggestions=rec.adaptation_suggestions
                )
        
        # 添加趋势推荐
        for rec in trending_recommendations:
            if rec.chart_type in all_recommendations:
                all_recommendations[rec.chart_type].confidence_score += rec.confidence_score * self.config['trending_weight']
            else:
                all_recommendations[rec.chart_type] = RecommendationResult(
                    chart_type=rec.chart_type,
                    confidence_score=rec.confidence_score * self.config['trending_weight'],
                    reasoning=f"[趋势推荐] {rec.reasoning}",
                    adaptation_suggestions=rec.adaptation_suggestions
                )
        
        # 转换为列表并排序
        recommendations = list(all_recommendations.values())
        recommendations.sort(key=lambda x: x.confidence_score, reverse=True)
        
        return recommendations
    
    def _get_collaborative_recommendations(self, user_id: str, 
                                         user_profile: Dict[str, Any]) -> List[RecommendationResult]:
        """协同过滤推荐"""
        recommendations = []
        
        # 找到相似用户
        similar_users = self.behavior_analyzer.find_similar_users(user_id, top_k=5)
        
        if not similar_users:
            return recommendations
        
        # 分析相似用户的偏好
        similar_user_preferences = []
        for similar_user in similar_users:
            similar_profile = self.behavior_analyzer.get_user_profile(similar_user)
            if similar_profile:
                similar_user_preferences.append(similar_profile)
        
        if not similar_user_preferences:
            return recommendations
        
        # 聚合相似用户的图表类型偏好
        all_preferences = Counter()
        for profile in similar_user_preferences:
            for chart_type, count in profile['preferred_chart_types'].items():
                all_preferences[chart_type] += count
        
        # 生成推荐
        total_similar_users = len(similar_user_preferences)
        for chart_type_str, total_count in all_preferences.most_common(10):
            # 计算推荐分数
            score = (total_count / total_similar_users) / max(total_count, 1)
            
            recommendation = RecommendationResult(
                chart_type=ChartType(chart_type_str),
                confidence_score=score,
                reasoning=f"与{total_similar_users}位相似用户的选择",
                expected_user_satisfaction=score
            )
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def _get_trending_recommendations(self, data_context: Dict[str, Any]) -> List[RecommendationResult]:
        """趋势推荐"""
        recommendations = []
        
        if not self.trending_charts:
            return recommendations
        
        # 统计热门图表类型
        chart_type_counts = Counter(self.trending_charts)
        total_trends = len(self.trending_charts)
        
        # 生成趋势推荐
        for chart_type, count in chart_type_counts.most_common(5):
            trend_score = count / total_trends
            
            # 根据数据特征筛选合适的趋势图表
            if self._is_chart_suitable_for_data(chart_type, data_context):
                recommendation = RecommendationResult(
                    chart_type=chart_type,
                    confidence_score=trend_score,
                    reasoning=f"当前趋势图表，{count}次使用",
                    expected_user_satisfaction=trend_score * 0.8  # 趋势图表满意度略低
                )
                recommendations.append(recommendation)
        
        return recommendations
    
    def _is_chart_suitable_for_data(self, chart_type: ChartType, data_context: Dict[str, Any]) -> bool:
        """检查图表是否适合数据"""
        categories_count = data_context.get('categories_count', 0)
        has_time_series = data_context.get('has_time_series', False)
        
        # 简单的适配性检查
        if chart_type == ChartType.PIE_CHART and categories_count > 8:
            return False
        if chart_type == ChartType.CANDLESTICK and not has_time_series:
            return False
        
        return True
    
    def _add_alternative_recommendations(self, recommendations: List[RecommendationResult],
                                       data_context: Dict[str, Any],
                                       user_profile: Optional[Dict[str, Any]]):
        """添加替代推荐"""
        primary_types = {rec.chart_type for rec in recommendations}
        
        # 生成替代推荐
        alternative_candidates = [
            ChartType.BAR_CHART, ChartType.LINE_CHART, ChartType.SCATTER_PLOT,
            ChartType.AREA_CHART, ChartType.HISTOGRAM, ChartType.PIE_CHART
        ]
        
        alternatives = []
        for chart_type in alternative_candidates:
            if chart_type not in primary_types:
                # 计算适合度分数
                suitability_score = self._calculate_data_suitability(chart_type, data_context)
                alternatives.append((chart_type, suitability_score))
        
        # 按适合度排序，取前3个
        alternatives.sort(key=lambda x: x[1], reverse=True)
        top_alternatives = alternatives[:3]
        
        # 为主要推荐添加替代选项
        for i, rec in enumerate(recommendations):
            for alt_type, alt_score in top_alternatives[:2]:  # 每个推荐最多2个替代
                rec.alternative_types.append((alt_type, alt_score))
    
    def _calculate_data_suitability(self, chart_type: ChartType, data_context: Dict[str, Any]) -> float:
        """计算数据适配度"""
        suitability_scores = {
            ChartType.LINE_CHART: 0.8 if data_context.get('has_time_series') else 0.3,
            ChartType.BAR_CHART: 0.9 if data_context.get('categories_count', 0) > 0 else 0.5,
            ChartType.PIE_CHART: 0.7 if 0 < data_context.get('categories_count', 0) <= 8 else 0.2,
            ChartType.SCATTER_PLOT: 0.9 if data_context.get('has_numeric_data') else 0.1,
            ChartType.AREA_CHART: 0.7 if data_context.get('has_time_series') else 0.3,
            ChartType.HISTOGRAM: 0.8 if data_context.get('has_numeric_data') else 0.2
        }
        
        return suitability_scores.get(chart_type, 0.5)
    
    def _invalidate_user_cache(self, user_id: str):
        """使用户缓存失效"""
        keys_to_remove = []
        for cache_key in self.user_recommendations.keys():
            if cache_key.startswith(f"{user_id}_"):
                keys_to_remove.append(cache_key)
        
        for key in keys_to_remove:
            del self.user_recommendations[key]
    
    def _cleanup_expired_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = []
        
        for cache_key, (result, timestamp) in self.user_recommendations.items():
            if current_time - timestamp > self.config['cache_ttl']:
                expired_keys.append(cache_key)
        
        for key in expired_keys:
            del self.user_recommendations[key]
    
    def get_recommendation_statistics(self) -> Dict[str, Any]:
        """获取推荐统计信息"""
        user_profiles = self.behavior_analyzer.user_profiles
        
        return {
            'global_stats': self.global_stats,
            'active_users': len(user_profiles),
            'cached_recommendations': len(self.user_recommendations),
            'chart_catalog_size': len(self.chart_catalog),
            'trending_charts_count': len(self.trending_charts),
            'average_user_activities': np.mean([p['total_activities'] for p in user_profiles.values()]) if user_profiles else 0,
            'top_chart_types': dict(Counter(self.trending_charts).most_common(10))
        }
    
    def export_user_insights(self, user_id: str) -> Dict[str, Any]:
        """导出用户洞察"""
        user_profile = self.behavior_analyzer.get_user_profile(user_id)
        if not user_profile:
            return {}
        
        behavior_patterns = self.behavior_analyzer.analyze_behavior_patterns(user_id)
        
        return {
            'user_profile': user_profile,
            'behavior_patterns': behavior_patterns,
            'insights': self._generate_user_insights(user_profile, behavior_patterns)
        }
    
    def _generate_user_insights(self, user_profile: Dict[str, Any], 
                              behavior_patterns: Dict[str, Any]) -> List[str]:
        """生成用户洞察"""
        insights = []
        
        # 基于专业水平的洞察
        expertise = user_profile['expertise_level']
        if expertise > 0.8:
            insights.append("您是高级用户，建议使用专业图表功能")
        elif expertise < 0.3:
            insights.append("您可以尝试更简单直观的图表类型")
        
        # 基于活动模式的洞察
        if behavior_patterns:
            most_active_day = behavior_patterns.get('most_active_day')
            if most_active_day:
                insights.append(f"您最活跃的日期是{most_active_day[0]}")
            
            avg_session = behavior_patterns.get('avg_session_duration', 0)
            if avg_session > 3600:  # 1小时
                insights.append("您倾向于进行长时间的深度分析")
            elif avg_session < 600:  # 10分钟
                insights.append("您偏好快速查看和操作")
        
        # 基于图表偏好的洞察
        preferred_types = user_profile['preferred_chart_types'].most_common(3)
        if preferred_types:
            type_names = [t[0] for t in preferred_types]
            insights.append(f"您最常使用{', '.join(type_names)}类型的图表")
        
        return insights

# 便捷函数
def create_smart_recommender(**kwargs) -> SmartChartRecommender:
    """创建智能推荐器"""
    return SmartChartRecommender(kwargs)

def create_sample_user_behavior(user_id: str, chart_type: ChartType, 
                              activity_type: UserActivityType) -> UserBehavior:
    """创建示例用户行为"""
    return UserBehavior(
        user_id=user_id,
        activity_type=activity_type,
        chart_type=chart_type,
        timestamp=time.time(),
        session_id=f"session_{int(time.time())}",
        duration_seconds=60.0,
        satisfaction_score=0.7,
        context_data={
            'complexity_score': 0.5,
            'data_size': 1000
        }
    )

def create_sample_chart_context(chart_id: str, chart_type: ChartType) -> ChartContext:
    """创建示例图表上下文"""
    return ChartContext(
        chart_id=chart_id,
        chart_type=chart_type,
        data_source="sample_data",
        data_size=1000,
        time_range="2023-01-01 to 2023-12-31",
        categories=["Category_1", "Category_2", "Category_3", "Category_4", "Category_5"],
        tags=["sample", "demo", chart_type.value],
        complexity_score=0.5,
        visual_elements={
            'color_scheme': 'default',
            'show_legend': True,
            'interactive': True
        },
        created_by="demo_user",
        created_at=time.time(),
        last_modified=time.time(),
        view_count=100,
        rating=4.0
    )