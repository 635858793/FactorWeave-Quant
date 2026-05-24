"""
个性化AI选股引擎

基于用户行为学习和画像分析，提供个性化的AI选股推荐和策略调整
"""

from loguru import logger
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import threading
from concurrent.futures import ThreadPoolExecutor

from ..database.unified_sqlite_access import UnifiedSQLiteAccess

# 现有用户行为学习系统
from .user_behavior_learner import (
    UserBehaviorLearner, UserProfile, UserSegment, ActionType, 
    UserBehaviorStorage, BehaviorPattern, RecommendationType
)

# AI选股相关
from ..services.ai_selection_integration_service import (
    AISelectionIntegrationService, StockSelectionCriteria, SelectionStrategy
)


class SelectionPreferenceType(Enum):
    """选股偏好类型"""
    INDUSTRY_PREFERENCE = "industry_preference"      # 行业偏好
    STYLE_PREFERENCE = "style_preference"            # 投资风格偏好
    RISK_TOLERANCE = "risk_tolerance"               # 风险承受能力
    HOLDING_PERIOD = "holding_period"               # 持有期偏好
    POSITION_SIZE = "position_size"                 # 仓位大小偏好
    REBALANCE_FREQUENCY = "rebalance_frequency"     # 调仓频率
    STRATEGY_PREFERENCE = "strategy_preference"     # 策略偏好
    EXPLANATION_DEPTH = "explanation_depth"         # 解释深度偏好


class InvestmentExperience(Enum):
    """投资经验水平"""
    BEGINNER = "beginner"          # 新手
    INTERMEDIATE = "intermediate"  # 中级
    ADVANCED = "advanced"          # 高级
    PROFESSIONAL = "professional"  # 专业


@dataclass
class InvestmentProfile:
    """投资画像"""
    user_id: str
    investment_experience: InvestmentExperience
    risk_tolerance_score: float  # 0.0-1.0
    investment_horizon: int      # 投资期限（天）
    preferred_industries: List[str]
    excluded_industries: List[str]
    investment_style: str        # "价值", "成长", "动量", "质量", "小盘股", "大盘股"
    preferred_stock_count: int   # 偏好的持股数量
    max_position_size: float     # 最大单股仓位比例
    rebalance_frequency: str     # 调仓频率
    performance_history: Dict[str, Any]
    feedback_history: List[Dict[str, Any]]
    learning_progress: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PersonalizedSelectionCriteria:
    """个性化选股标准"""
    base_criteria: StockSelectionCriteria
    personalized_weights: Dict[str, float]
    preferred_stocks: List[str]
    excluded_stocks: List[str]
    industry_adjustments: Dict[str, float]  # 行业权重调整
    risk_adjustments: Dict[str, float]      # 风险权重调整
    experience_level: InvestmentExperience
    confidence_threshold: float


@dataclass
class SelectionFeedback:
    """选股反馈"""
    feedback_id: str
    user_id: str
    selection_session_id: str
    stock_code: str
    feedback_type: str  # "accepted", "rejected", "hold", "sold", "performance_rating"
    rating: Optional[float]  # 1-5星评分
    comment: Optional[str]
    performance_data: Optional[Dict[str, float]]
    timestamp: datetime = field(default_factory=datetime.now)


class PersonalizedStockSelectionEngine:
    """个性化AI选股引擎"""
    
    def __init__(self, 
                 behavior_learner: UserBehaviorLearner,
                 ai_selection_service: AISelectionIntegrationService,
                 db_path: Optional[str] = None):
        """
        初始化个性化选股引擎
        
        Args:
            behavior_learner: 用户行为学习器
            ai_selection_service: AI选股服务
            db_path: 数据库路径
        """
        self.behavior_learner = behavior_learner
        self.ai_selection_service = ai_selection_service
        self.db_path = db_path or self._get_default_db_path()
        self._db_instance = UnifiedSQLiteAccess.get_instance(self.db_path)
        self.storage = UserBehaviorStorage(self.db_path)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="Personalized_Selection")
        
        # 缓存
        self._investment_profiles: Dict[str, InvestmentProfile] = {}
        self._selection_history: Dict[str, List[Dict]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # 初始化数据库表
        self._init_database()
        
        logger.info("个性化AI选股引擎初始化完成")
        
    def _get_default_db_path(self) -> str:
        """获取默认数据库路径"""
        import os
        from pathlib import Path
        app_data_dir = Path.home() / ".FactorWeave-Quant" / "personalized_selection"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return str(app_data_dir / "personalized_selection.db")
        
    def _init_database(self):
        """初始化数据库表"""
        try:
            with self._db_instance.get_connection() as conn:
                cursor = conn.cursor()
                
                # 投资画像表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS investment_profiles (
                        user_id TEXT PRIMARY KEY,
                        investment_experience TEXT NOT NULL,
                        risk_tolerance_score REAL NOT NULL,
                        investment_horizon INTEGER NOT NULL,
                        preferred_industries TEXT,
                        excluded_industries TEXT,
                        investment_style TEXT NOT NULL,
                        preferred_stock_count INTEGER,
                        max_position_size REAL,
                        rebalance_frequency TEXT,
                        performance_history TEXT,
                        feedback_history TEXT,
                        learning_progress TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                # 选股反馈表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS selection_feedback (
                        feedback_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        selection_session_id TEXT NOT NULL,
                        stock_code TEXT NOT NULL,
                        feedback_type TEXT NOT NULL,
                        rating REAL,
                        comment TEXT,
                        performance_data TEXT,
                        timestamp TEXT NOT NULL
                    )
                """)
                
                # 个性化权重历史表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS weight_adjustment_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        adjustment_type TEXT NOT NULL,
                        old_weights TEXT,
                        new_weights TEXT,
                        adjustment_reason TEXT,
                        success_rate_before REAL,
                        success_rate_after REAL,
                        timestamp TEXT NOT NULL
                    )
                """)
                
                logger.info("个性化选股引擎数据库表初始化完成")
                
        except Exception as e:
            logger.error(f"初始化数据库失败: {e}")
            
    def get_investment_profile(self, user_id: str) -> Optional[InvestmentProfile]:
        """获取用户投资画像"""
        try:
            # 先检查缓存
            if user_id in self._investment_profiles:
                return self._investment_profiles[user_id]
                
            # 从数据库加载
            with self._db_instance.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM investment_profiles WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    profile = InvestmentProfile(
                        user_id=row[0],
                        investment_experience=InvestmentExperience(row[1]),
                        risk_tolerance_score=row[2],
                        investment_horizon=row[3],
                        preferred_industries=json.loads(row[4]) if row[4] else [],
                        excluded_industries=json.loads(row[5]) if row[5] else [],
                        investment_style=row[6],
                        preferred_stock_count=row[7],
                        max_position_size=row[8],
                        rebalance_frequency=row[9],
                        performance_history=json.loads(row[10]) if row[10] else {},
                        feedback_history=json.loads(row[11]) if row[11] else [],
                        learning_progress=json.loads(row[12]) if row[12] else {},
                        created_at=datetime.fromisoformat(row[13]),
                        updated_at=datetime.fromisoformat(row[14])
                    )
                    
                    # 缓存到内存
                    self._investment_profiles[user_id] = profile
                    return profile
                    
            # 如果不存在，创建默认画像
            return self._create_default_profile(user_id)
            
        except Exception as e:
            logger.error(f"获取投资画像失败: {e}")
            return None
            
    def _create_default_profile(self, user_id: str) -> InvestmentProfile:
        """创建默认投资画像"""
        # 基于用户行为学习器的用户细分来推断投资经验
        user_profile = self.behavior_learner.get_user_profile(user_id)
        
        if user_profile:
            # 基于用户细分映射到投资经验
            experience_mapping = {
                UserSegment.BEGINNER: InvestmentExperience.BEGINNER,
                UserSegment.INTERMEDIATE: InvestmentExperience.INTERMEDIATE,
                UserSegment.ADVANCED: InvestmentExperience.ADVANCED,
                UserSegment.POWER_USER: InvestmentExperience.PROFESSIONAL,
                UserSegment.ANALYST: InvestmentExperience.PROFESSIONAL
            }
            
            investment_experience = experience_mapping.get(
                user_profile.segment, InvestmentExperience.INTERMEDIATE
            )
            
            # 基于技能水平和活跃度推断风险承受能力
            risk_tolerance = (user_profile.skill_level * 0.6 + user_profile.activity_score * 0.4)
            
        else:
            investment_experience = InvestmentExperience.INTERMEDIATE
            risk_tolerance = 0.5
            
        default_profile = InvestmentProfile(
            user_id=user_id,
            investment_experience=investment_experience,
            risk_tolerance_score=risk_tolerance,
            investment_horizon=180,  # 默认6个月
            preferred_industries=[],
            excluded_industries=[],
            investment_style="综合",
            preferred_stock_count=20,
            max_position_size=0.1,  # 10%
            rebalance_frequency="monthly",
            performance_history={},
            feedback_history=[],
            learning_progress={}
        )
        
        # 保存到数据库和缓存
        self.save_investment_profile(default_profile)
        return default_profile
        
    def save_investment_profile(self, profile: InvestmentProfile) -> bool:
        """保存投资画像"""
        try:
            with self._db_instance.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO investment_profiles 
                    (user_id, investment_experience, risk_tolerance_score, investment_horizon,
                     preferred_industries, excluded_industries, investment_style, preferred_stock_count,
                     max_position_size, rebalance_frequency, performance_history, feedback_history,
                     learning_progress, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    profile.user_id,
                    profile.investment_experience.value,
                    profile.risk_tolerance_score,
                    profile.investment_horizon,
                    json.dumps(profile.preferred_industries),
                    json.dumps(profile.excluded_industries),
                    profile.investment_style,
                    profile.preferred_stock_count,
                    profile.max_position_size,
                    profile.rebalance_frequency,
                    json.dumps(profile.performance_history),
                    json.dumps(profile.feedback_history),
                    json.dumps(profile.learning_progress),
                    profile.created_at.isoformat(),
                    datetime.now().isoformat()
                ))
                
                # 更新缓存
                self._investment_profiles[profile.user_id] = profile
                logger.info(f"投资画像已保存: {profile.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"保存投资画像失败: {e}")
            return False
            
    def update_investment_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """更新投资画像"""
        try:
            profile = self.get_investment_profile(user_id)
            if not profile:
                logger.error(f"用户投资画像不存在: {user_id}")
                return False
                
            # 更新字段
            for key, value in updates.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
                    
            profile.updated_at = datetime.now()
            
            # 记录学习进度
            if 'learning_progress' not in profile.learning_progress:
                profile.learning_progress = {}
            profile.learning_progress[f'update_{datetime.now().isoformat()}'] = {
                'updated_fields': list(updates.keys()),
                'timestamp': datetime.now().isoformat()
            }
            
            return self.save_investment_profile(profile)
            
        except Exception as e:
            logger.error(f"更新投资画像失败: {e}")
            return False
            
    def create_personalized_criteria(self, 
                                   user_id: str,
                                   base_criteria: StockSelectionCriteria,
                                   session_id: Optional[str] = None) -> PersonalizedSelectionCriteria:
        """创建个性化选股标准"""
        try:
            # 获取用户投资画像
            profile = self.get_investment_profile(user_id)
            if not profile:
                logger.warning(f"用户投资画像不存在，使用默认配置: {user_id}")
                profile = self._create_default_profile(user_id)
                
            # 基于画像调整权重
            personalized_weights = self._calculate_personalized_weights(profile, base_criteria)
            
            # 计算行业和风险调整
            industry_adjustments = self._calculate_industry_adjustments(profile)
            risk_adjustments = self._calculate_risk_adjustments(profile)
            
            # 确定置信度阈值
            confidence_threshold = self._calculate_confidence_threshold(profile)
            
            # 创建个性化标准
            personalized_criteria = PersonalizedSelectionCriteria(
                base_criteria=base_criteria,
                personalized_weights=personalized_weights,
                preferred_stocks=self._get_preferred_stocks(user_id, profile),
                excluded_stocks=profile.excluded_industries,
                industry_adjustments=industry_adjustments,
                risk_adjustments=risk_adjustments,
                experience_level=profile.investment_experience,
                confidence_threshold=confidence_threshold
            )
            
            # 记录这次个性化过程
            if session_id:
                self._record_personalization_session(
                    user_id, session_id, base_criteria, personalized_criteria
                )
                
            logger.info(f"为用户 {user_id} 创建了个性化选股标准")
            return personalized_criteria
            
        except Exception as e:
            logger.error(f"创建个性化选股标准失败: {e}")
            # 返回基础标准
            return PersonalizedSelectionCriteria(
                base_criteria=base_criteria,
                personalized_weights={},
                preferred_stocks=[],
                excluded_stocks=[],
                industry_adjustments={},
                risk_adjustments={},
                experience_level=InvestmentExperience.INTERMEDIATE,
                confidence_threshold=0.7
            )
            
    def _calculate_personalized_weights(self, 
                                      profile: InvestmentProfile,
                                      base_criteria: StockSelectionCriteria) -> Dict[str, float]:
        """计算个性化权重"""
        try:
            weights = {}
            
            # 基于投资风格调整权重
            style_adjustments = {
                "价值": {"pe_ratio": 0.3, "pb_ratio": 0.3, "roe": 0.2, "debt_ratio": -0.2},
                "成长": {"revenue_growth": 0.3, "profit_growth": 0.3, "pe_ratio": -0.1},
                "动量": {"price_momentum": 0.4, "volume_momentum": 0.2, "technical_score": 0.3},
                "质量": {"roe": 0.3, "roa": 0.2, "debt_ratio": -0.2, "profit_margin": 0.2},
                "大盘股": {"market_cap": 0.2, "liquidity": 0.2},
                "小盘股": {"market_cap": -0.2, "growth_potential": 0.3},
                "综合": {}
            }
            
            adjustment = style_adjustments.get(profile.investment_style, {})
            
            # 基于风险承受能力调整
            risk_factor = profile.risk_tolerance_score
            
            # 基于投资期限调整
            horizon_factor = min(profile.investment_horizon / 365.0, 2.0)  # 最多2倍
            
            # 组合调整
            for factor, base_weight in base_criteria.technical_indicators.items():
                adjusted_weight = base_weight
                
                # 应用风格调整
                if factor in adjustment:
                    adjusted_weight += adjustment[factor] * 0.1
                    
                # 应用风险调整
                if risk_factor > 0.7:  # 高风险承受能力
                    if factor in ["volatility", "beta"]:
                        adjusted_weight *= 1.2
                elif risk_factor < 0.3:  # 低风险承受能力
                    if factor in ["volatility", "beta"]:
                        adjusted_weight *= 0.5
                        
                # 应用期限调整
                if profile.investment_horizon > 365:  # 长期投资
                    if factor in ["dividend_yield", "earnings_stability"]:
                        adjusted_weight *= 1.3
                        
                weights[factor] = max(0.0, min(1.0, adjusted_weight))
                
            # 归一化权重
            total_weight = sum(weights.values())
            if total_weight > 0:
                weights = {k: v/total_weight for k, v in weights.items()}
                
            return weights
            
        except Exception as e:
            logger.error(f"计算个性化权重失败: {e}")
            return base_criteria.technical_indicators if base_criteria else {}
            
    def _calculate_industry_adjustments(self, profile: InvestmentProfile) -> Dict[str, float]:
        """计算行业权重调整"""
        adjustments = {}
        
        # 优先行业权重提升
        for industry in profile.preferred_industries:
            adjustments[industry] = 1.5  # 提升50%
            
        # 排除行业权重降低
        for industry in profile.excluded_industries:
            adjustments[industry] = 0.1  # 降低90%
            
        # 基于投资风格的行业偏好
        style_industry_preferences = {
            "价值": {"银行": 1.3, "房地产": 1.2, "公用事业": 1.2},
            "成长": {"科技": 1.4, "医药": 1.3, "新能源": 1.3},
            "动量": {"券商": 1.3, "有色金属": 1.2, "军工": 1.2},
            "质量": {"消费": 1.2, "医药": 1.2, "食品饮料": 1.2}
        }
        
        style_prefs = style_industry_preferences.get(profile.investment_style, {})
        for industry, adjustment in style_prefs.items():
            adjustments[industry] = adjustments.get(industry, 1.0) * adjustment
            
        return adjustments
        
    def _calculate_risk_adjustments(self, profile: InvestmentProfile) -> Dict[str, float]:
        """计算风险权重调整"""
        adjustments = {}
        
        # 基于风险承受能力
        if profile.risk_tolerance_score < 0.3:  # 保守型
            adjustments.update({
                "volatility": 0.3,
                "beta": 0.3,
                "max_drawdown": 0.4,
                "debt_ratio": 0.6
            })
        elif profile.risk_tolerance_score > 0.7:  # 激进型
            adjustments.update({
                "volatility": 1.4,
                "beta": 1.3,
                "max_drawdown": 1.2,
                "growth_potential": 1.5
            })
        else:  # 稳健型
            adjustments.update({
                "volatility": 1.0,
                "beta": 1.0,
                "max_drawdown": 1.0
            })
            
        return adjustments
        
    def _calculate_confidence_threshold(self, profile: InvestmentProfile) -> float:
        """计算置信度阈值"""
        # 基于经验水平调整阈值
        experience_thresholds = {
            InvestmentExperience.BEGINNER: 0.8,      # 新手需要更高的置信度
            InvestmentExperience.INTERMEDIATE: 0.7,  # 中级用户
            InvestmentExperience.ADVANCED: 0.6,      # 高级用户
            InvestmentExperience.PROFESSIONAL: 0.5   # 专业用户
        }
        
        base_threshold = experience_thresholds.get(profile.investment_experience, 0.7)
        
        # 基于历史表现调整
        if profile.performance_history:
            success_rate = profile.performance_history.get("success_rate", 0.5)
            if success_rate > 0.8:
                base_threshold *= 0.9  # 表现好的用户可以降低阈值
            elif success_rate < 0.3:
                base_threshold *= 1.1  # 表现差的用户需要提高阈值
                
        return max(0.3, min(0.9, base_threshold))
        
    def _get_preferred_stocks(self, user_id: str, profile: InvestmentProfile) -> List[str]:
        """获取用户偏好股票"""
        # 基于历史反馈找出表现好的股票
        preferred_stocks = []
        
        try:
            # 从反馈历史中查找高评分股票
            for feedback in profile.feedback_history:
                if (feedback.get('rating', 0) >= 4 and 
                    feedback.get('feedback_type') == 'performance_rating'):
                    stock_code = feedback.get('stock_code')
                    if stock_code and stock_code not in preferred_stocks:
                        preferred_stocks.append(stock_code)
                        
            # 从用户行为中分析偏好的股票
            if self.behavior_learner:
                recent_behavior = self.behavior_learner.get_recent_behavior(user_id, days=30)
                if recent_behavior:
                    # 分析用户经常查看或操作的股票
                    stock_interactions = []
                    for action in recent_behavior:
                        if action.get('action_type') == ActionType.DASHBOARD_VIEW:
                            context = action.get('context', {})
                            if 'stock_code' in context:
                                stock_interactions.append(context['stock_code'])
                                
                    # 统计最常交互的股票
                    stock_counter = Counter(stock_interactions)
                    for stock_code, count in stock_counter.most_common(10):
                        if count >= 3 and stock_code not in preferred_stocks:
                            preferred_stocks.append(stock_code)
                            
        except Exception as e:
            logger.error(f"获取偏好股票失败: {e}")
            
        return preferred_stocks[:20]  # 最多返回20只
        
    def _record_personalization_session(self, 
                                      user_id: str,
                                      session_id: str,
                                      base_criteria: StockSelectionCriteria,
                                      personalized_criteria: PersonalizedSelectionCriteria):
        """记录个性化会话"""
        try:
            session_data = {
                'session_id': session_id,
                'user_id': user_id,
                'base_criteria': asdict(base_criteria) if base_criteria else {},
                'personalized_weights': personalized_criteria.personalized_weights,
                'industry_adjustments': personalized_criteria.industry_adjustments,
                'risk_adjustments': personalized_criteria.risk_adjustments,
                'confidence_threshold': personalized_criteria.confidence_threshold,
                'timestamp': datetime.now().isoformat()
            }
            
            self._selection_history[user_id].append(session_data)
            
            # 记录到用户行为学习器
            if self.behavior_learner:
                self.behavior_learner.record_action(
                    user_id=user_id,
                    session_id=session_id,
                    action_type=ActionType.PREDICTION_REQUEST,
                    context={'action': 'personalized_stock_selection'},
                    metadata={'personalization_data': session_data}
                )
                
        except Exception as e:
            logger.error(f"记录个性化会话失败: {e}")
            
    def apply_feedback(self, feedback: SelectionFeedback) -> bool:
        """应用用户反馈"""
        try:
            # 保存反馈到数据库
            with self._db_instance.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO selection_feedback 
                    (feedback_id, user_id, selection_session_id, stock_code, feedback_type,
                     rating, comment, performance_data, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback.feedback_id,
                    feedback.user_id,
                    feedback.selection_session_id,
                    feedback.stock_code,
                    feedback.feedback_type,
                    feedback.rating,
                    feedback.comment,
                    json.dumps(feedback.performance_data) if feedback.performance_data else None,
                    feedback.timestamp.isoformat()
                ))
                
            # 更新用户投资画像
            self._update_profile_with_feedback(feedback)
            
            # 触发学习和优化
            self._trigger_learning_update(feedback.user_id)
            
            logger.info(f"已应用用户反馈: {feedback.feedback_id}")
            return True
            
        except Exception as e:
            logger.error(f"应用反馈失败: {e}")
            return False
            
    def _update_profile_with_feedback(self, feedback: SelectionFeedback):
        """基于反馈更新投资画像"""
        try:
            profile = self.get_investment_profile(feedback.user_id)
            if not profile:
                return
                
            # 添加反馈历史
            feedback_data = {
                'feedback_id': feedback.feedback_id,
                'stock_code': feedback.stock_code,
                'feedback_type': feedback.feedback_type,
                'rating': feedback.rating,
                'comment': feedback.comment,
                'timestamp': feedback.timestamp.isoformat()
            }
            
            if feedback.performance_data:
                feedback_data['performance_data'] = feedback.performance_data
                
            profile.feedback_history.append(feedback_data)
            
            # 保持历史记录在合理范围内
            if len(profile.feedback_history) > 1000:
                profile.feedback_history = profile.feedback_history[-500:]
                
            # 基于反馈调整投资风格
            if feedback.feedback_type == 'accepted' and feedback.rating:
                # 用户接受且评分高，强化当前偏好
                if feedback.rating >= 4:
                    # 记录成功的特征
                    if 'successful_styles' not in profile.learning_progress:
                        profile.learning_progress['successful_styles'] = []
                    profile.learning_progress['successful_styles'].append({
                        'style': profile.investment_style,
                        'rating': feedback.rating,
                        'timestamp': feedback.timestamp.isoformat()
                    })
                    
            elif feedback.feedback_type == 'rejected':
                # 用户拒绝，考虑调整偏好
                if 'rejected_styles' not in profile.learning_progress:
                    profile.learning_progress['rejected_styles'] = []
                profile.learning_progress['rejected_styles'].append({
                    'style': profile.investment_style,
                    'timestamp': feedback.timestamp.isoformat()
                })
                
            # 更新投资画像
            self.save_investment_profile(profile)
            
        except Exception as e:
            logger.error(f"基于反馈更新画像失败: {e}")
            
    def _trigger_learning_update(self, user_id: str):
        """触发学习更新"""
        try:
            # 异步执行学习更新
            self.executor.submit(self._perform_learning_update, user_id)
        except Exception as e:
            logger.error(f"触发学习更新失败: {e}")
            
    def _perform_learning_update(self, user_id: str):
        """执行学习更新"""
        try:
            profile = self.get_investment_profile(user_id)
            if not profile:
                return
                
            # 分析反馈模式
            feedback_analysis = self._analyze_feedback_patterns(profile)
            
            # 更新投资风格偏好
            if feedback_analysis['preferred_styles']:
                preferred_style = feedback_analysis['preferred_styles'][0]
                if preferred_style != profile.investment_style:
                    logger.info(f"建议用户 {user_id} 调整投资风格: {profile.investment_style} -> {preferred_style}")
                    # 可以选择自动调整或建议用户调整
                    
            # 更新行业偏好
            if feedback_analysis['preferred_industries']:
                # 计算行业偏好得分
                industry_scores = {}
                for industry in profile.preferred_industries + profile.excluded_industries:
                    industry_scores[industry] = 0
                    
                for feedback in profile.feedback_history:
                    if feedback.get('rating', 0) >= 4:
                        stock_code = feedback.get('stock_code')
                        # 这里需要根据股票代码获取行业信息
                        # industry = self._get_stock_industry(stock_code)
                        # industry_scores[industry] = industry_scores.get(industry, 0) + 1
                        
                # 更新偏好行业列表
                new_preferred = [ind for ind, score in industry_scores.items() if score >= 2]
                if new_preferred != profile.preferred_industries:
                    profile.preferred_industries = new_preferred
                    logger.info(f"更新用户 {user_id} 的偏好行业: {new_preferred}")
                    
            # 重新保存画像
            self.save_investment_profile(profile)
            
        except Exception as e:
            logger.error(f"执行学习更新失败: {e}")
            
    def _analyze_feedback_patterns(self, profile: InvestmentProfile) -> Dict[str, List[str]]:
        """分析反馈模式"""
        try:
            analysis = {
                'preferred_styles': [],
                'preferred_industries': [],
                'performance_trends': []
            }
            
            # 分析投资风格偏好
            style_ratings = defaultdict(list)
            for feedback in profile.feedback_history:
                if feedback.get('feedback_type') == 'performance_rating' and feedback.get('rating'):
                    # 这里需要关联股票和投资风格
                    # style = self._infer_stock_style(feedback.get('stock_code'))
                    style_ratings[profile.investment_style].append(feedback.get('rating', 0))
                    
            # 计算平均评分
            style_avg_ratings = {
                style: np.mean(ratings) for style, ratings in style_ratings.items()
            }
            
            if style_avg_ratings:
                best_style = max(style_avg_ratings.items(), key=lambda x: x[1])[0]
                analysis['preferred_styles'] = [best_style]
                
            return analysis
            
        except Exception as e:
            logger.error(f"分析反馈模式失败: {e}")
            return {'preferred_styles': [], 'preferred_industries': [], 'performance_trends': []}
            
    def get_personalized_recommendations(self, 
                                       user_id: str,
                                       limit: int = 10) -> List[Dict[str, Any]]:
        """获取个性化推荐"""
        try:
            profile = self.get_investment_profile(user_id)
            if not profile:
                return []
                
            recommendations = []
            
            # 基于学习进度生成建议
            learning_progress = profile.learning_progress
            
            # 投资风格优化建议
            if 'successful_styles' in learning_progress:
                successful_styles = learning_progress['successful_styles']
                if len(successful_styles) >= 3:
                    recent_styles = [s for s in successful_styles 
                                   if (datetime.now() - datetime.fromisoformat(s['timestamp'])).days <= 30]
                    if recent_styles:
                        avg_rating = np.mean([s['rating'] for s in recent_styles])
                        if avg_rating >= 4.0:
                            recommendations.append({
                                'type': 'style_optimization',
                                'title': '投资风格优化建议',
                                'description': f'您的{profile.investment_style}风格表现优秀，建议继续保持',
                                'priority': 2,
                                'action_data': {'maintain_style': True}
                            })
                            
            # 行业分散建议
            if len(profile.preferred_industries) <= 2:
                recommendations.append({
                    'type': 'diversification',
                    'title': '增加行业分散度',
                    'description': '建议关注更多行业以降低风险',
                    'priority': 3,
                    'action_data': {'suggested_industries': ['科技', '医药', '消费']}
                })
                
            # 仓位管理建议
            if profile.preferred_stock_count < 10:
                recommendations.append({
                    'type': 'position_management',
                    'title': '增加持仓数量',
                    'description': '适当增加持仓数量可以提高分散化效果',
                    'priority': 2,
                    'action_data': {'suggested_count': min(profile.preferred_stock_count + 5, 30)}
                })
                
            # 基于风险承受能力的建议
            if profile.risk_tolerance_score < 0.4:
                recommendations.append({
                    'type': 'risk_management',
                    'title': '风险控制优化',
                    'description': '建议加强风险控制，选择更稳健的投资策略',
                    'priority': 4,
                    'action_data': {'suggested_adjustments': ['降低波动性权重', '增加防御性行业']}
                })
                
            # 排序并返回
            recommendations.sort(key=lambda x: x['priority'], reverse=True)
            return recommendations[:limit]
            
        except Exception as e:
            logger.error(f"获取个性化推荐失败: {e}")
            return []
            
    def generate_explanation_adaptation(self, 
                                      user_id: str,
                                      explanation_content: str,
                                      explanation_level: str) -> str:
        """生成适应性解释"""
        try:
            profile = self.get_investment_profile(user_id)
            if not profile:
                return explanation_content
                
            adapted_explanation = explanation_content
            
            # 基于经验水平调整解释深度
            if profile.investment_experience == InvestmentExperience.BEGINNER:
                # 新手用户：添加更多基础概念解释
                adapted_explanation = self._add_beginner_explanations(adapted_explanation)
            elif profile.investment_experience == InvestmentExperience.PROFESSIONAL:
                # 专业用户：简化基础概念，专注核心要点
                adapted_explanation = self._simplify_for_professionals(adapted_explanation)
                
            # 基于投资风格调整解释重点
            if profile.investment_style == "价值":
                adapted_explanation = self._emphasize_value_factors(adapted_explanation)
            elif profile.investment_style == "成长":
                adapted_explanation = self._emphasize_growth_factors(adapted_explanation)
            elif profile.investment_style == "动量":
                adapted_explanation = self._emphasize_momentum_factors(adapted_explanation)
                
            return adapted_explanation
            
        except Exception as e:
            logger.error(f"生成适应性解释失败: {e}")
            return explanation_content
            
    def _add_beginner_explanations(self, explanation: str) -> str:
        """为新手添加基础概念解释"""
        additions = {
            "PE比率": "PE比率（市盈率）：股价与每股收益的比率，反映市场对公司未来盈利的预期。",
            "PB比率": "PB比率（市净率）：股价与每股净资产的比率，反映市场对公司资产价值的评估。",
            "ROE": "ROE（净资产收益率）：净利润与股东权益的比率，反映公司的盈利能力。",
            "MACD": "MACD（指数平滑异同移动平均线）：技术指标，用于判断股价趋势的变化。",
            "RSI": "RSI（相对强弱指数）：技术指标，用于判断股票是否超买或超卖。",
            "BOLL": "BOLL（布林线）：技术指标，显示股价的波动区间。"
        }
        
        adapted = explanation
        for term, definition in additions.items():
            if term in explanation and f"({definition.split('：')[0]})" not in explanation:
                # 避免重复定义
                term_with_definition = f"{term}（{definition}）"
                adapted = adapted.replace(term, term_with_definition)
                
        return adapted
        
    def _simplify_for_professionals(self, explanation: str) -> str:
        """为专业用户简化解释"""
        # 移除基础概念解释，保留核心要点
        lines = explanation.split('\n')
        simplified_lines = []
        
        for line in lines:
            if any(indicator in line for indicator in ["PE比率", "PB比率", "ROE", "MACD", "RSI", "BOLL"]):
                # 对于专业用户，简化技术指标的描述
                if "（" in line and "）" in line:
                    # 移除括号内的解释
                    line = line.split('（')[0]
            simplified_lines.append(line)
            
        return '\n'.join(simplified_lines)
        
    def _emphasize_value_factors(self, explanation: str) -> str:
        """强调价值投资因素"""
        value_terms = ["PE", "PB", "ROE", "股息率", "账面价值"]
        emphasis = "（价值投资重点关注）"
        
        lines = explanation.split('\n')
        emphasized_lines = []
        
        for line in lines:
            if any(term in line for term in value_terms):
                if emphasis not in line:
                    line += f" {emphasis}"
            emphasized_lines.append(line)
            
        return '\n'.join(emphasized_lines)
        
    def _emphasize_growth_factors(self, explanation: str) -> str:
        """强调成长投资因素"""
        growth_terms = ["增长率", "营收增长", "利润增长", "市场份额", "创新能力"]
        emphasis = "（成长投资重点关注）"
        
        lines = explanation.split('\n')
        emphasized_lines = []
        
        for line in lines:
            if any(term in line for term in growth_terms):
                if emphasis not in line:
                    line += f" {emphasis}"
            emphasized_lines.append(line)
            
        return '\n'.join(emphasized_lines)
        
    def _emphasize_momentum_factors(self, explanation: str) -> str:
        """强调动量投资因素"""
        momentum_terms = ["MACD", "RSI", "动量", "趋势", "成交量"]
        emphasis = "（动量投资重点关注）"
        
        lines = explanation.split('\n')
        emphasized_lines = []
        
        for line in lines:
            if any(term in line for term in momentum_terms):
                if emphasis not in line:
                    line += f" {emphasis}"
            emphasized_lines.append(line)
            
        return '\n'.join(emphasized_lines)
        
    def get_selection_statistics(self, user_id: str) -> Dict[str, Any]:
        """获取选股统计信息"""
        try:
            profile = self.get_investment_profile(user_id)
            if not profile:
                return {}
                
            # 计算各种统计指标
            stats = {
                'total_selections': len(profile.feedback_history),
                'acceptance_rate': 0.0,
                'average_rating': 0.0,
                'top_performing_industries': [],
                'style_performance': {},
                'learning_progress': profile.learning_progress,
                'profile_updated': profile.updated_at.isoformat()
            }
            
            if profile.feedback_history:
                # 计算接受率
                accepted = sum(1 for f in profile.feedback_history 
                             if f.get('feedback_type') == 'accepted')
                stats['acceptance_rate'] = accepted / len(profile.feedback_history)
                
                # 计算平均评分
                ratings = [f.get('rating', 0) for f in profile.feedback_history 
                          if f.get('rating') is not None]
                if ratings:
                    stats['average_rating'] = np.mean(ratings)
                    
            return stats
            
        except Exception as e:
            logger.error(f"获取选股统计失败: {e}")
            return {}
            
    def cleanup_old_data(self, days_to_keep: int = 365):
        """清理旧数据"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.isoformat()
            
            with self._db_instance.get_connection() as conn:
                cursor = conn.cursor()
                
                # 清理旧的反馈数据
                cursor.execute("""
                    DELETE FROM selection_feedback 
                    WHERE timestamp < ?
                """, (cutoff_str,))
                
                deleted_count = cursor.rowcount
                
                logger.info(f"已清理 {deleted_count} 条旧的反馈记录")
                
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
            
    def shutdown(self):
        """关闭引擎"""
        try:
            # 关闭线程池
            self.executor.shutdown(wait=True)
            
            # 清理缓存
            self._investment_profiles.clear()
            self._selection_history.clear()
            
            logger.info("个性化AI选股引擎已关闭")
            
        except Exception as e:
            logger.error(f"关闭引擎失败: {e}")


def create_personalized_selection_engine(behavior_learner: UserBehaviorLearner,
                                       ai_selection_service: AISelectionIntegrationService,
                                       db_path: Optional[str] = None) -> PersonalizedStockSelectionEngine:
    """创建个性化选股引擎"""
    return PersonalizedStockSelectionEngine(
        behavior_learner=behavior_learner,
        ai_selection_service=ai_selection_service,
        db_path=db_path
    )