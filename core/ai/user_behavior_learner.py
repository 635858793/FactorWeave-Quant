"""
用户行为学习机制
建立用户行为模式学习和分析系统，支持个性化推荐和智能配置建议
"""

from loguru import logger
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
from collections import defaultdict, Counter
import threading
import sqlite3
import pickle
import os
from ..database.unified_sqlite_access import UnifiedSQLiteAccess

class ActionType(Enum):
    """用户行为类型"""
    LOGIN = "login"
    LOGOUT = "logout"
    DATA_IMPORT = "data_import"
    DATA_EXPORT = "data_export"
    ANALYSIS_RUN = "analysis_run"
    PREDICTION_REQUEST = "prediction_request"
    CONFIGURATION_CHANGE = "configuration_change"
    UI_INTERACTION = "ui_interaction"
    SEARCH_QUERY = "search_query"
    FILE_OPERATION = "file_operation"
    REPORT_GENERATION = "report_generation"
    DASHBOARD_VIEW = "dashboard_view"
    PREFERENCE_UPDATE = "preference_update"
    ERROR_ENCOUNTER = "error_encounter"
    HELP_ACCESS = "help_access"


class UserSegment(Enum):
    """用户细分类型"""
    BEGINNER = "beginner"        # 新手用户
    INTERMEDIATE = "intermediate"  # 中级用户
    ADVANCED = "advanced"        # 高级用户
    POWER_USER = "power_user"    # 专业用户
    ANALYST = "analyst"          # 分析师
    DEVELOPER = "developer"      # 开发者


class RecommendationType(Enum):
    """推荐类型"""
    FEATURE = "feature"          # 功能推荐
    CONFIGURATION = "configuration"  # 配置推荐
    WORKFLOW = "workflow"        # 工作流推荐
    TUTORIAL = "tutorial"        # 教程推荐
    OPTIMIZATION = "optimization"  # 优化建议
    SHORTCUT = "shortcut"        # 快捷方式推荐


@dataclass
class UserAction:
    """用户行为记录"""
    user_id: str
    session_id: str
    action_type: ActionType
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None  # 操作持续时间（秒）
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    segment: UserSegment
    skill_level: float  # 0.0-1.0
    activity_score: float  # 0.0-1.0
    preferences: Dict[str, Any] = field(default_factory=dict)
    frequent_actions: List[str] = field(default_factory=list)
    usage_patterns: Dict[str, Any] = field(default_factory=dict)
    last_active: Optional[datetime] = None
    total_sessions: int = 0
    total_actions: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class BehaviorPattern:
    """行为模式"""
    pattern_id: str
    pattern_type: str
    description: str
    frequency: float
    confidence: float
    user_segments: List[UserSegment]
    conditions: Dict[str, Any] = field(default_factory=dict)
    outcomes: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Recommendation:
    """推荐建议"""
    recommendation_id: str
    user_id: str
    recommendation_type: RecommendationType
    title: str
    description: str
    confidence: float
    priority: int  # 1-5, 5最高
    context: Dict[str, Any] = field(default_factory=dict)
    action_data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    is_shown: bool = False
    is_accepted: bool = False
    is_dismissed: bool = False


class UserBehaviorStorage:
    """用户行为数据存储"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self._get_default_db_path()
        self._ensure_database()
        self._lock = threading.Lock()

    def _get_default_db_path(self) -> str:
        """获取默认数据库路径"""
        app_data_dir = Path.home() / ".FactorWeave-Quant" / "user_behavior"
        app_data_dir.mkdir(parents=True, exist_ok=True)
        return str(app_data_dir / "user_behavior.db")

    def _ensure_database(self):
        """确保数据库表存在"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()

                # 用户行为表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        context TEXT,
                        duration REAL,
                        success INTEGER,
                        error_message TEXT,
                        metadata TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 用户画像表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        user_id TEXT PRIMARY KEY,
                        segment TEXT NOT NULL,
                        skill_level REAL NOT NULL,
                        activity_score REAL NOT NULL,
                        preferences TEXT,
                        frequent_actions TEXT,
                        usage_patterns TEXT,
                        last_active TEXT,
                        total_sessions INTEGER DEFAULT 0,
                        total_actions INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 行为模式表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS behavior_patterns (
                        pattern_id TEXT PRIMARY KEY,
                        pattern_type TEXT NOT NULL,
                        description TEXT NOT NULL,
                        frequency REAL NOT NULL,
                        confidence REAL NOT NULL,
                        user_segments TEXT,
                        conditions TEXT,
                        outcomes TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 推荐记录表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS recommendations (
                        recommendation_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        recommendation_type TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        confidence REAL NOT NULL,
                        priority INTEGER NOT NULL,
                        context TEXT,
                        action_data TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        expires_at TEXT,
                        is_shown INTEGER DEFAULT 0,
                        is_accepted INTEGER DEFAULT 0,
                        is_dismissed INTEGER DEFAULT 0
                    )
                """)

                # 创建索引
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_actions_timestamp ON user_actions(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_user_id ON recommendations(user_id)")

                conn.commit()
                logger.info("用户行为数据库初始化完成")

        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    def save_action(self, action: UserAction) -> bool:
        """保存用户行为"""
        try:
            with self._lock:
                db = self._get_db()
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO user_actions 
                        (user_id, session_id, action_type, timestamp, context, duration, success, error_message, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        action.user_id,
                        action.session_id,
                        action.action_type.value,
                        action.timestamp.isoformat(),
                        json.dumps(action.context),
                        action.duration,
                        1 if action.success else 0,
                        action.error_message,
                        json.dumps(action.metadata)
                    ))
                    return True

        except Exception as e:
            logger.error(f"保存用户行为失败: {e}")
            return False

    def get_user_actions(self, user_id: str, limit: int = 1000,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> List[UserAction]:
        """获取用户行为记录"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM user_actions WHERE user_id = ?"
                params = [user_id]

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())

                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())

                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                actions = []
                for row in rows:
                    action = UserAction(
                        user_id=row[1],
                        session_id=row[2],
                        action_type=ActionType(row[3]),
                        timestamp=datetime.fromisoformat(row[4]),
                        context=json.loads(row[5]) if row[5] else {},
                        duration=row[6],
                        success=bool(row[7]),
                        error_message=row[8],
                        metadata=json.loads(row[9]) if row[9] else {}
                    )
                    actions.append(action)

                return actions

        except Exception as e:
            logger.error(f"获取用户行为记录失败: {e}")
            return []

    def save_user_profile(self, profile: UserProfile) -> bool:
        """保存用户画像"""
        try:
            with self._lock:
                db = self._get_db()
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR REPLACE INTO user_profiles 
                        (user_id, segment, skill_level, activity_score, preferences, frequent_actions, 
                         usage_patterns, last_active, total_sessions, total_actions, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        profile.user_id,
                        profile.segment.value,
                        profile.skill_level,
                        profile.activity_score,
                        json.dumps(profile.preferences),
                        json.dumps(profile.frequent_actions),
                        json.dumps(profile.usage_patterns),
                        profile.last_active.isoformat() if profile.last_active else None,
                        profile.total_sessions,
                        profile.total_actions,
                        profile.created_at.isoformat(),
                        profile.updated_at.isoformat()
                    ))
                    return True

        except Exception as e:
            logger.error(f"保存用户画像失败: {e}")
            return False

    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        try:
            db = self._get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()

                if row:
                    return UserProfile(
                        user_id=row[0],
                        segment=UserSegment(row[1]),
                        skill_level=row[2],
                        activity_score=row[3],
                        preferences=json.loads(row[4]) if row[4] else {},
                        frequent_actions=json.loads(row[5]) if row[5] else [],
                        usage_patterns=json.loads(row[6]) if row[6] else {},
                        last_active=datetime.fromisoformat(row[7]) if row[7] else None,
                        total_sessions=row[8],
                        total_actions=row[9],
                        created_at=datetime.fromisoformat(row[10]),
                        updated_at=datetime.fromisoformat(row[11])
                    )

                return None

        except Exception as e:
            logger.error(f"获取用户画像失败: {e}")
            return None


class BehaviorAnalyzer:
    """行为分析器"""

    def __init__(self):
        self.pattern_cache = {}
        self.analysis_cache = {}

    def analyze_user_behavior(self, actions: List[UserAction]) -> Dict[str, Any]:
        """分析用户行为"""
        try:
            if not actions:
                return {}

            # 基础统计
            total_actions = len(actions)
            action_types = Counter(action.action_type.value for action in actions)
            success_rate = sum(1 for action in actions if action.success) / total_actions

            # 时间分析
            time_analysis = self._analyze_time_patterns(actions)

            # 会话分析
            session_analysis = self._analyze_sessions(actions)

            # 操作序列分析
            sequence_analysis = self._analyze_action_sequences(actions)

            # 错误模式分析
            error_analysis = self._analyze_error_patterns(actions)

            # 效率分析
            efficiency_analysis = self._analyze_efficiency(actions)

            return {
                'total_actions': total_actions,
                'action_distribution': dict(action_types),
                'success_rate': success_rate,
                'time_patterns': time_analysis,
                'session_patterns': session_analysis,
                'sequence_patterns': sequence_analysis,
                'error_patterns': error_analysis,
                'efficiency_metrics': efficiency_analysis,
                'analysis_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"用户行为分析失败: {e}")
            return {}

    def _analyze_time_patterns(self, actions: List[UserAction]) -> Dict[str, Any]:
        """分析时间模式"""
        try:
            timestamps = [action.timestamp for action in actions]

            # 按小时分布
            hour_distribution = Counter(ts.hour for ts in timestamps)

            # 按星期分布
            weekday_distribution = Counter(ts.weekday() for ts in timestamps)

            # 活跃时段
            peak_hours = [hour for hour, count in hour_distribution.most_common(3)]
            peak_weekdays = [day for day, count in weekday_distribution.most_common(3)]

            # 使用频率
            date_range = (max(timestamps) - min(timestamps)).days + 1
            daily_frequency = len(timestamps) / date_range

            return {
                'hour_distribution': dict(hour_distribution),
                'weekday_distribution': dict(weekday_distribution),
                'peak_hours': peak_hours,
                'peak_weekdays': peak_weekdays,
                'daily_frequency': daily_frequency,
                'date_range_days': date_range
            }

        except Exception as e:
            logger.error(f"时间模式分析失败: {e}")
            return {}

    def _analyze_sessions(self, actions: List[UserAction]) -> Dict[str, Any]:
        """分析会话模式"""
        try:
            # 按会话分组
            sessions = defaultdict(list)
            for action in actions:
                sessions[action.session_id].append(action)

            # 会话统计
            session_lengths = []
            session_durations = []

            for session_actions in sessions.values():
                session_lengths.append(len(session_actions))

                if len(session_actions) > 1:
                    start_time = min(action.timestamp for action in session_actions)
                    end_time = max(action.timestamp for action in session_actions)
                    duration = (end_time - start_time).total_seconds()
                    session_durations.append(duration)

            avg_session_length = np.mean(session_lengths) if session_lengths else 0
            avg_session_duration = np.mean(session_durations) if session_durations else 0

            return {
                'total_sessions': len(sessions),
                'avg_actions_per_session': avg_session_length,
                'avg_session_duration_seconds': avg_session_duration,
                'session_length_distribution': dict(Counter(session_lengths)),
                'max_session_length': max(session_lengths) if session_lengths else 0
            }

        except Exception as e:
            logger.error(f"会话模式分析失败: {e}")
            return {}

    def _analyze_action_sequences(self, actions: List[UserAction]) -> Dict[str, Any]:
        """分析操作序列"""
        try:
            # 按会话分组
            sessions = defaultdict(list)
            for action in actions:
                sessions[action.session_id].append(action)

            # 分析序列模式
            common_sequences = Counter()
            transition_matrix = defaultdict(lambda: defaultdict(int))

            for session_actions in sessions.values():
                # 按时间排序
                session_actions.sort(key=lambda x: x.timestamp)
                action_types = [action.action_type.value for action in session_actions]

                # 记录转换
                for i in range(len(action_types) - 1):
                    current_action = action_types[i]
                    next_action = action_types[i + 1]
                    transition_matrix[current_action][next_action] += 1

                # 记录常见序列（长度2-4）
                for seq_len in range(2, min(5, len(action_types) + 1)):
                    for i in range(len(action_types) - seq_len + 1):
                        sequence = tuple(action_types[i:i + seq_len])
                        common_sequences[sequence] += 1

            # 转换为普通字典
            transition_dict = {k: dict(v) for k, v in transition_matrix.items()}

            return {
                'common_sequences': dict(common_sequences.most_common(10)),
                'transition_matrix': transition_dict,
                'most_common_transitions': self._get_top_transitions(transition_matrix)
            }

        except Exception as e:
            logger.error(f"操作序列分析失败: {e}")
            return {}

    def _get_top_transitions(self, transition_matrix: Dict) -> List[Dict[str, Any]]:
        """获取最常见的转换"""
        transitions = []
        for from_action, to_actions in transition_matrix.items():
            for to_action, count in to_actions.items():
                transitions.append({
                    'from': from_action,
                    'to': to_action,
                    'count': count
                })

        # 按次数排序
        transitions.sort(key=lambda x: x['count'], reverse=True)
        return transitions[:10]

    def _analyze_error_patterns(self, actions: List[UserAction]) -> Dict[str, Any]:
        """分析错误模式"""
        try:
            error_actions = [action for action in actions if not action.success]

            if not error_actions:
                return {'error_rate': 0.0, 'error_types': {}}

            error_rate = len(error_actions) / len(actions)
            error_types = Counter(action.action_type.value for action in error_actions)
            error_messages = Counter(action.error_message for action in error_actions if action.error_message)

            # 错误时间分布
            error_hours = Counter(action.timestamp.hour for action in error_actions)

            return {
                'error_rate': error_rate,
                'total_errors': len(error_actions),
                'error_types': dict(error_types),
                'error_messages': dict(error_messages.most_common(5)),
                'error_time_distribution': dict(error_hours)
            }

        except Exception as e:
            logger.error(f"错误模式分析失败: {e}")
            return {}

    def _analyze_efficiency(self, actions: List[UserAction]) -> Dict[str, Any]:
        """分析效率指标"""
        try:
            # 有持续时间的操作
            timed_actions = [action for action in actions if action.duration is not None]

            if not timed_actions:
                return {}

            # 按操作类型分组分析持续时间
            duration_by_type = defaultdict(list)
            for action in timed_actions:
                duration_by_type[action.action_type.value].append(action.duration)

            efficiency_metrics = {}
            for action_type, durations in duration_by_type.items():
                efficiency_metrics[action_type] = {
                    'avg_duration': np.mean(durations),
                    'median_duration': np.median(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'std_duration': np.std(durations),
                    'total_time': sum(durations),
                    'count': len(durations)
                }

            return efficiency_metrics

        except Exception as e:
            logger.error(f"效率分析失败: {e}")
            return {}


class UserSegmentClassifier:
    """用户细分分类器"""

    def __init__(self):
        self.classification_rules = self._initialize_classification_rules()

    def _initialize_classification_rules(self) -> Dict[str, Any]:
        """初始化分类规则"""
        return {
            UserSegment.BEGINNER: {
                'max_total_actions': 100,
                'max_skill_level': 0.3,
                'common_actions': [ActionType.LOGIN, ActionType.UI_INTERACTION, ActionType.HELP_ACCESS],
                'error_rate_threshold': 0.2
            },
            UserSegment.INTERMEDIATE: {
                'min_total_actions': 100,
                'max_total_actions': 500,
                'min_skill_level': 0.3,
                'max_skill_level': 0.6,
                'common_actions': [ActionType.DATA_IMPORT, ActionType.ANALYSIS_RUN, ActionType.CONFIGURATION_CHANGE],
                'error_rate_threshold': 0.15
            },
            UserSegment.ADVANCED: {
                'min_total_actions': 500,
                'max_total_actions': 2000,
                'min_skill_level': 0.6,
                'max_skill_level': 0.8,
                'common_actions': [ActionType.PREDICTION_REQUEST, ActionType.REPORT_GENERATION, ActionType.DATA_EXPORT],
                'error_rate_threshold': 0.1
            },
            UserSegment.POWER_USER: {
                'min_total_actions': 2000,
                'min_skill_level': 0.8,
                'common_actions': [ActionType.CONFIGURATION_CHANGE, ActionType.PREDICTION_REQUEST, ActionType.ANALYSIS_RUN],
                'error_rate_threshold': 0.05
            },
            UserSegment.ANALYST: {
                'min_total_actions': 1000,
                'min_skill_level': 0.7,
                'analysis_focus': True,
                'common_actions': [ActionType.ANALYSIS_RUN, ActionType.REPORT_GENERATION, ActionType.DASHBOARD_VIEW],
                'error_rate_threshold': 0.08
            },
            UserSegment.DEVELOPER: {
                'min_total_actions': 500,
                'min_skill_level': 0.8,
                'technical_focus': True,
                'common_actions': [ActionType.CONFIGURATION_CHANGE, ActionType.FILE_OPERATION, ActionType.ERROR_ENCOUNTER],
                'error_rate_threshold': 0.03
            }
        }

    def classify_user(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> UserSegment:
        """分类用户"""
        try:
            scores = {}

            for segment, rules in self.classification_rules.items():
                score = self._calculate_segment_score(profile, behavior_analysis, rules)
                scores[segment] = score

            # 选择得分最高的细分
            best_segment = max(scores.items(), key=lambda x: x[1])[0]

            logger.debug(f"用户 {profile.user_id} 分类结果: {best_segment.value}, 得分: {scores}")

            return best_segment

        except Exception as e:
            logger.error(f"用户分类失败: {e}")
            return UserSegment.INTERMEDIATE  # 默认分类

    def _calculate_segment_score(self, profile: UserProfile, behavior_analysis: Dict[str, Any], rules: Dict[str, Any]) -> float:
        """计算细分得分"""
        score = 0.0

        try:
            # 总操作数检查
            if 'min_total_actions' in rules:
                if profile.total_actions >= rules['min_total_actions']:
                    score += 1.0
                else:
                    return 0.0  # 不满足最小要求

            if 'max_total_actions' in rules:
                if profile.total_actions <= rules['max_total_actions']:
                    score += 1.0
                else:
                    score -= 0.5  # 超出范围减分

            # 技能水平检查
            if 'min_skill_level' in rules:
                if profile.skill_level >= rules['min_skill_level']:
                    score += 1.0
                else:
                    return 0.0  # 不满足最小要求

            if 'max_skill_level' in rules:
                if profile.skill_level <= rules['max_skill_level']:
                    score += 1.0
                else:
                    score -= 0.5  # 超出范围减分

            # 常见操作匹配
            if 'common_actions' in rules:
                action_distribution = behavior_analysis.get('action_distribution', {})
                common_actions = rules['common_actions']

                matching_actions = 0
                for action_type in common_actions:
                    if isinstance(action_type, ActionType):
                        action_name = action_type.value
                    else:
                        action_name = action_type

                    if action_name in action_distribution:
                        matching_actions += 1

                if common_actions:
                    match_ratio = matching_actions / len(common_actions)
                    score += match_ratio * 2.0  # 操作匹配权重较高

            # 错误率检查
            if 'error_rate_threshold' in rules:
                error_rate = behavior_analysis.get('error_patterns', {}).get('error_rate', 0.0)
                if error_rate <= rules['error_rate_threshold']:
                    score += 1.0
                else:
                    score -= (error_rate - rules['error_rate_threshold']) * 2.0  # 错误率过高减分

            # 特殊标识检查
            if rules.get('analysis_focus', False):
                analysis_actions = ['analysis_run', 'report_generation', 'dashboard_view']
                action_distribution = behavior_analysis.get('action_distribution', {})
                analysis_ratio = sum(action_distribution.get(action, 0) for action in analysis_actions) / max(sum(action_distribution.values()), 1)
                if analysis_ratio > 0.3:  # 30%以上是分析相关操作
                    score += 2.0

            if rules.get('technical_focus', False):
                technical_actions = ['configuration_change', 'file_operation', 'error_encounter']
                action_distribution = behavior_analysis.get('action_distribution', {})
                technical_ratio = sum(action_distribution.get(action, 0) for action in technical_actions) / max(sum(action_distribution.values()), 1)
                if technical_ratio > 0.2:  # 20%以上是技术相关操作
                    score += 2.0

            return max(score, 0.0)  # 确保得分非负

        except Exception as e:
            logger.error(f"计算细分得分失败: {e}")
            return 0.0


class RecommendationEngine:
    """推荐引擎"""

    def __init__(self):
        self.recommendation_rules = self._initialize_recommendation_rules()
        self.feature_usage_stats = {}

    def _initialize_recommendation_rules(self) -> Dict[str, Any]:
        """初始化推荐规则"""
        return {
            # 功能推荐规则
            'feature_recommendations': {
                UserSegment.BEGINNER: [
                    {
                        'condition': lambda profile, analysis: analysis.get('error_patterns', {}).get('error_rate', 0) > 0.15,
                        'recommendation': {
                            'type': RecommendationType.TUTORIAL,
                            'title': '新手入门教程',
                            'description': '建议查看新手入门教程，减少操作错误',
                            'priority': 5
                        }
                    },
                    {
                        'condition': lambda profile, analysis: 'help_access' not in analysis.get('action_distribution', {}),
                        'recommendation': {
                            'type': RecommendationType.FEATURE,
                            'title': '帮助功能',
                            'description': '发现帮助功能，获取更多操作指导',
                            'priority': 4
                        }
                    }
                ],
                UserSegment.INTERMEDIATE: [
                    {
                        'condition': lambda profile, analysis: analysis.get('action_distribution', {}).get('data_import', 0) > 10,
                        'recommendation': {
                            'type': RecommendationType.FEATURE,
                            'title': '批量导入功能',
                            'description': '尝试批量导入功能，提高数据处理效率',
                            'priority': 4
                        }
                    },
                    {
                        'condition': lambda profile, analysis: 'prediction_request' not in analysis.get('action_distribution', {}),
                        'recommendation': {
                            'type': RecommendationType.FEATURE,
                            'title': 'AI预测功能',
                            'description': '探索AI预测功能，获得智能分析建议',
                            'priority': 3
                        }
                    }
                ],
                UserSegment.ADVANCED: [
                    {
                        'condition': lambda profile, analysis: analysis.get('efficiency_metrics', {}).get('analysis_run', {}).get('avg_duration', 0) > 60,
                        'recommendation': {
                            'type': RecommendationType.OPTIMIZATION,
                            'title': '分析性能优化',
                            'description': '优化分析配置，提高分析速度',
                            'priority': 4
                        }
                    },
                    {
                        'condition': lambda profile, analysis: 'report_generation' not in analysis.get('action_distribution', {}),
                        'recommendation': {
                            'type': RecommendationType.FEATURE,
                            'title': '报告生成功能',
                            'description': '使用报告生成功能，创建专业分析报告',
                            'priority': 3
                        }
                    }
                ]
            },

            # 配置推荐规则
            'configuration_recommendations': {
                'slow_operations': {
                    'condition': lambda profile, analysis: any(
                        metrics.get('avg_duration', 0) > 30
                        for metrics in analysis.get('efficiency_metrics', {}).values()
                    ),
                    'recommendation': {
                        'type': RecommendationType.CONFIGURATION,
                        'title': '性能配置优化',
                        'description': '调整系统配置以提高操作速度',
                        'priority': 4
                    }
                },
                'frequent_errors': {
                    'condition': lambda profile, analysis: analysis.get('error_patterns', {}).get('error_rate', 0) > 0.1,
                    'recommendation': {
                        'type': RecommendationType.CONFIGURATION,
                        'title': '错误预防配置',
                        'description': '调整配置以减少常见错误',
                        'priority': 5
                    }
                }
            },

            # 工作流推荐规则
            'workflow_recommendations': {
                'inefficient_sequences': {
                    'condition': lambda profile, analysis: len(analysis.get('sequence_patterns', {}).get('common_sequences', {})) < 3,
                    'recommendation': {
                        'type': RecommendationType.WORKFLOW,
                        'title': '工作流优化建议',
                        'description': '学习更高效的操作序列',
                        'priority': 3
                    }
                }
            }
        }

    def generate_recommendations(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> List[Recommendation]:
        """生成推荐"""
        try:
            recommendations = []

            # 功能推荐
            feature_recs = self._generate_feature_recommendations(profile, behavior_analysis)
            recommendations.extend(feature_recs)

            # 配置推荐
            config_recs = self._generate_configuration_recommendations(profile, behavior_analysis)
            recommendations.extend(config_recs)

            # 工作流推荐
            workflow_recs = self._generate_workflow_recommendations(profile, behavior_analysis)
            recommendations.extend(workflow_recs)

            # 快捷方式推荐
            shortcut_recs = self._generate_shortcut_recommendations(profile, behavior_analysis)
            recommendations.extend(shortcut_recs)

            # 按优先级排序
            recommendations.sort(key=lambda x: x.priority, reverse=True)

            # 限制推荐数量
            return recommendations[:10]

        except Exception as e:
            logger.error(f"生成推荐失败: {e}")
            return []

    def _generate_feature_recommendations(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> List[Recommendation]:
        """生成功能推荐"""
        recommendations = []

        try:
            segment_rules = self.recommendation_rules['feature_recommendations'].get(profile.segment, [])

            for rule in segment_rules:
                if rule['condition'](profile, behavior_analysis):
                    rec_data = rule['recommendation']

                    recommendation = Recommendation(
                        recommendation_id=self._generate_recommendation_id(profile.user_id, rec_data['title']),
                        user_id=profile.user_id,
                        recommendation_type=rec_data['type'],
                        title=rec_data['title'],
                        description=rec_data['description'],
                        confidence=0.8,
                        priority=rec_data['priority'],
                        context={'segment': profile.segment.value, 'rule_type': 'feature'},
                        expires_at=datetime.now() + timedelta(days=7)
                    )

                    recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"生成功能推荐失败: {e}")

        return recommendations

    def _generate_configuration_recommendations(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> List[Recommendation]:
        """生成配置推荐"""
        recommendations = []

        try:
            config_rules = self.recommendation_rules['configuration_recommendations']

            for rule_name, rule in config_rules.items():
                if rule['condition'](profile, behavior_analysis):
                    rec_data = rule['recommendation']

                    recommendation = Recommendation(
                        recommendation_id=self._generate_recommendation_id(profile.user_id, rec_data['title']),
                        user_id=profile.user_id,
                        recommendation_type=rec_data['type'],
                        title=rec_data['title'],
                        description=rec_data['description'],
                        confidence=0.75,
                        priority=rec_data['priority'],
                        context={'rule_name': rule_name, 'rule_type': 'configuration'},
                        expires_at=datetime.now() + timedelta(days=5)
                    )

                    recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"生成配置推荐失败: {e}")

        return recommendations

    def _generate_workflow_recommendations(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> List[Recommendation]:
        """生成工作流推荐"""
        recommendations = []

        try:
            workflow_rules = self.recommendation_rules['workflow_recommendations']

            for rule_name, rule in workflow_rules.items():
                if rule['condition'](profile, behavior_analysis):
                    rec_data = rule['recommendation']

                    recommendation = Recommendation(
                        recommendation_id=self._generate_recommendation_id(profile.user_id, rec_data['title']),
                        user_id=profile.user_id,
                        recommendation_type=rec_data['type'],
                        title=rec_data['title'],
                        description=rec_data['description'],
                        confidence=0.7,
                        priority=rec_data['priority'],
                        context={'rule_name': rule_name, 'rule_type': 'workflow'},
                        expires_at=datetime.now() + timedelta(days=3)
                    )

                    recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"生成工作流推荐失败: {e}")

        return recommendations

    def _generate_shortcut_recommendations(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> List[Recommendation]:
        """生成快捷方式推荐"""
        recommendations = []

        try:
            # 基于频繁操作推荐快捷方式
            action_distribution = behavior_analysis.get('action_distribution', {})
            frequent_actions = sorted(action_distribution.items(), key=lambda x: x[1], reverse=True)[:3]

            shortcut_mappings = {
                'data_import': {'key': 'Ctrl+I', 'description': '快速数据导入'},
                'analysis_run': {'key': 'Ctrl+R', 'description': '快速运行分析'},
                'report_generation': {'key': 'Ctrl+G', 'description': '快速生成报告'},
                'prediction_request': {'key': 'Ctrl+P', 'description': '快速AI预测'}
            }

            for action_type, count in frequent_actions:
                if action_type in shortcut_mappings and count > 5:
                    shortcut_info = shortcut_mappings[action_type]

                    recommendation = Recommendation(
                        recommendation_id=self._generate_recommendation_id(profile.user_id, f"shortcut_{action_type}"),
                        user_id=profile.user_id,
                        recommendation_type=RecommendationType.SHORTCUT,
                        title=f"快捷键: {shortcut_info['key']}",
                        description=f"{shortcut_info['description']} - 您经常使用此功能",
                        confidence=0.9,
                        priority=2,
                        context={'action_type': action_type, 'usage_count': count},
                        action_data={'shortcut_key': shortcut_info['key']},
                        expires_at=datetime.now() + timedelta(days=14)
                    )

                    recommendations.append(recommendation)

        except Exception as e:
            logger.error(f"生成快捷方式推荐失败: {e}")

        return recommendations

    def _generate_recommendation_id(self, user_id: str, title: str) -> str:
        """生成推荐ID"""
        content = f"{user_id}_{title}_{datetime.now().date()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]


class UserBehaviorLearner:
    """用户行为学习器主类（基于规则引擎，非ML模型）"""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage = UserBehaviorStorage(storage_path)
        self.analyzer = BehaviorAnalyzer()
        self.classifier = UserSegmentClassifier()
        self.recommendation_engine = RecommendationEngine()
        logger.info("UserBehaviorLearner 初始化: 使用规则引擎模式（非ML训练）")

        # 缓存
        self.profile_cache = {}
        self.analysis_cache = {}
        self.cache_ttl = timedelta(hours=1)

        # 线程锁
        self._lock = threading.Lock()

        logger.info("用户行为学习器已初始化")

    def record_action(self, user_id: str, session_id: str, action_type: ActionType,
                      context: Optional[Dict[str, Any]] = None,
                      duration: Optional[float] = None,
                      success: bool = True,
                      error_message: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        """记录用户行为"""
        try:
            action = UserAction(
                user_id=user_id,
                session_id=session_id,
                action_type=action_type,
                timestamp=datetime.now(),
                context=context or {},
                duration=duration,
                success=success,
                error_message=error_message,
                metadata=metadata or {}
            )

            success = self.storage.save_action(action)

            if success:
                # 清除相关缓存
                self._clear_user_cache(user_id)

                # 异步更新用户画像
                self._async_update_profile(user_id)

            return success

        except Exception as e:
            logger.error(f"记录用户行为失败: {e}")
            return False

    def get_user_profile(self, user_id: str, force_refresh: bool = False) -> Optional[UserProfile]:
        """获取用户画像"""
        try:
            # 检查缓存
            if not force_refresh and user_id in self.profile_cache:
                cached_profile, cache_time = self.profile_cache[user_id]
                if datetime.now() - cache_time < self.cache_ttl:
                    return cached_profile

            # 从存储获取
            profile = self.storage.get_user_profile(user_id)

            if not profile:
                # 创建新用户画像
                profile = self._create_initial_profile(user_id)
            else:
                # 更新现有画像
                profile = self._update_profile_from_actions(profile)

            # 更新缓存
            with self._lock:
                self.profile_cache[user_id] = (profile, datetime.now())

            return profile

        except Exception as e:
            logger.error(f"获取用户画像失败: {e}")
            return None

    def get_user_recommendations(self, user_id: str, limit: int = 5) -> List[Recommendation]:
        """获取用户推荐"""
        try:
            profile = self.get_user_profile(user_id)
            if not profile:
                return []

            # 获取行为分析
            behavior_analysis = self.get_user_behavior_analysis(user_id)

            # 生成推荐
            try:
                recommendations = self.recommendation_engine.generate_recommendations(profile, behavior_analysis)
            except Exception as rec_err:
                logger.warning(f"规则推荐生成失败: {rec_err}")
                recommendations = []

            # 过滤已过期的推荐
            current_time = datetime.now()
            valid_recommendations = [
                rec for rec in recommendations
                if not rec.expires_at or rec.expires_at > current_time
            ]

            return valid_recommendations[:limit]

        except Exception as e:
            logger.error(f"获取用户推荐失败: {e}")
            return []

    def get_user_behavior_analysis(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """获取用户行为分析"""
        try:
            # 检查缓存
            cache_key = f"{user_id}_{days}"
            if cache_key in self.analysis_cache:
                cached_analysis, cache_time = self.analysis_cache[cache_key]
                if datetime.now() - cache_time < self.cache_ttl:
                    return cached_analysis

            # 获取行为数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            actions = self.storage.get_user_actions(user_id, limit=10000, start_date=start_date, end_date=end_date)

            # 分析行为
            analysis = self.analyzer.analyze_user_behavior(actions)

            # 更新缓存
            with self._lock:
                self.analysis_cache[cache_key] = (analysis, datetime.now())

            return analysis

        except Exception as e:
            logger.error(f"获取用户行为分析失败: {e}")
            return {}

    def update_recommendation_feedback(self, recommendation_id: str, is_accepted: bool = False, is_dismissed: bool = False) -> bool:
        """更新推荐反馈"""
        try:
            # 这里应该更新数据库中的推荐记录
            # 由于当前存储类没有实现这个方法，我们先记录日志
            logger.info(f"推荐反馈更新: {recommendation_id}, 接受: {is_accepted}, 忽略: {is_dismissed}")

            # 实现数据库更新逻辑
            if hasattr(self.storage, 'update_recommendation_feedback'):
                return self.storage.update_recommendation_feedback(recommendation_id, is_accepted, is_dismissed)
            else:
                # 如果存储类没有实现该方法，使用内存记录
                if not hasattr(self, '_recommendation_feedback'):
                    self._recommendation_feedback = {}
                self._recommendation_feedback[recommendation_id] = {
                    'is_accepted': is_accepted,
                    'is_dismissed': is_dismissed,
                    'timestamp': datetime.now()
                }
                return True

        except Exception as e:
            logger.error(f"更新推荐反馈失败: {e}")
            return False

    def _create_initial_profile(self, user_id: str) -> UserProfile:
        """创建初始用户画像"""
        profile = UserProfile(
            user_id=user_id,
            segment=UserSegment.BEGINNER,
            skill_level=0.1,
            activity_score=0.0,
            preferences={},
            frequent_actions=[],
            usage_patterns={},
            last_active=datetime.now(),
            total_sessions=0,
            total_actions=0
        )

        # 保存到存储
        self.storage.save_user_profile(profile)

        return profile

    def _update_profile_from_actions(self, profile: UserProfile) -> UserProfile:
        """从行为数据更新用户画像"""
        try:
            # 获取最新行为数据
            actions = self.storage.get_user_actions(profile.user_id, limit=1000)

            if not actions:
                return profile

            # 更新基础统计
            profile.total_actions = len(actions)
            profile.last_active = max(action.timestamp for action in actions)

            # 计算会话数
            sessions = set(action.session_id for action in actions)
            profile.total_sessions = len(sessions)

            # 分析行为
            behavior_analysis = self.analyzer.analyze_user_behavior(actions)

            # 更新技能水平
            profile.skill_level = self._calculate_skill_level(profile, behavior_analysis)

            # 更新活跃度
            profile.activity_score = self._calculate_activity_score(profile, behavior_analysis)

            # 更新常用操作
            action_distribution = behavior_analysis.get('action_distribution', {})
            profile.frequent_actions = [
                action for action, count in
                sorted(action_distribution.items(), key=lambda x: x[1], reverse=True)[:5]
            ]

            # 更新使用模式
            profile.usage_patterns = {
                'time_patterns': behavior_analysis.get('time_patterns', {}),
                'session_patterns': behavior_analysis.get('session_patterns', {}),
                'efficiency_metrics': behavior_analysis.get('efficiency_metrics', {})
            }

            # 重新分类用户
            profile.segment = self.classifier.classify_user(profile, behavior_analysis)

            # 更新时间戳
            profile.updated_at = datetime.now()

            # 保存更新
            self.storage.save_user_profile(profile)

            return profile

        except Exception as e:
            logger.error(f"更新用户画像失败: {e}")
            return profile

    def _calculate_skill_level(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> float:
        """计算技能水平"""
        try:
            # 基础因子
            base_score = min(profile.total_actions / 1000.0, 0.5)  # 操作数量

            # 成功率因子
            success_rate = behavior_analysis.get('success_rate', 1.0)
            success_score = success_rate * 0.3

            # 错误率因子（反向）
            error_rate = behavior_analysis.get('error_patterns', {}).get('error_rate', 0.0)
            error_score = max(0, 0.2 - error_rate * 2)

            # 操作多样性因子
            action_types = len(behavior_analysis.get('action_distribution', {}))
            diversity_score = min(action_types / 10.0, 0.2)

            # 效率因子
            efficiency_metrics = behavior_analysis.get('efficiency_metrics', {})
            if efficiency_metrics:
                avg_durations = [metrics.get('avg_duration', 60) for metrics in efficiency_metrics.values()]
                avg_duration = np.mean(avg_durations)
                efficiency_score = max(0, 0.2 - (avg_duration - 30) / 300)  # 30秒为基准
            else:
                efficiency_score = 0.1

            total_score = base_score + success_score + error_score + diversity_score + efficiency_score
            return min(max(total_score, 0.0), 1.0)

        except Exception as e:
            logger.error(f"计算技能水平失败: {e}")
            return 0.5

    def _calculate_activity_score(self, profile: UserProfile, behavior_analysis: Dict[str, Any]) -> float:
        """计算活跃度"""
        try:
            # 时间因子
            if profile.last_active:
                days_since_active = (datetime.now() - profile.last_active).days
                time_score = max(0, 1.0 - days_since_active / 30.0)  # 30天为周期
            else:
                time_score = 0.0

            # 频率因子
            time_patterns = behavior_analysis.get('time_patterns', {})
            daily_frequency = time_patterns.get('daily_frequency', 0)
            frequency_score = min(daily_frequency / 5.0, 0.5)  # 每天5次操作为满分

            # 会话因子
            session_patterns = behavior_analysis.get('session_patterns', {})
            avg_session_length = session_patterns.get('avg_actions_per_session', 0)
            session_score = min(avg_session_length / 20.0, 0.3)  # 每会话20次操作为满分

            # 持续性因子
            date_range = time_patterns.get('date_range_days', 1)
            consistency_score = min(profile.total_sessions / date_range, 0.2)

            total_score = time_score * 0.4 + frequency_score + session_score + consistency_score
            return min(max(total_score, 0.0), 1.0)

        except Exception as e:
            logger.error(f"计算活跃度失败: {e}")
            return 0.5

    def _async_update_profile(self, user_id: str):
        """异步更新用户画像"""
        def update_task():
            try:
                self.get_user_profile(user_id, force_refresh=True)
            except Exception as e:
                logger.error(f"异步更新用户画像失败: {e}")

        # 在实际应用中，这里应该使用线程池或任务队列
        import threading
        thread = threading.Thread(target=update_task)
        thread.daemon = True
        thread.start()

    def _clear_user_cache(self, user_id: str):
        """清除用户相关缓存"""
        with self._lock:
            # 清除画像缓存
            if user_id in self.profile_cache:
                del self.profile_cache[user_id]

            # 清除分析缓存
            keys_to_remove = [key for key in self.analysis_cache.keys() if key.startswith(f"{user_id}_")]
            for key in keys_to_remove:
                del self.analysis_cache[key]

    def get_system_statistics(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        try:
            # 这里应该从数据库获取统计信息
            # 由于当前存储类没有实现统计方法，我们返回模拟数据
            return {
                'total_users': len(self.profile_cache),
                'total_actions_today': self._calculate_total_actions_today(),
                'active_users_today': self._calculate_active_users_today(),
                'cache_size': len(self.profile_cache) + len(self.analysis_cache),
                'user_segments': {
                    'beginner': 0,
                    'intermediate': 0,
                    'advanced': 0,
                    'power_user': 0,
                    'analyst': 0,
                    'developer': 0
                },
                'top_actions': self._calculate_top_actions(),
                'recommendation_acceptance_rate': self._calculate_recommendation_acceptance_rate()
            }

        except Exception as e:
            logger.error(f"获取系统统计失败: {e}")
            return {}

    def _calculate_total_actions_today(self) -> int:
        """计算今日总操作数"""
        try:
            today = datetime.now().date()
            if hasattr(self.storage, 'get_actions_by_date'):
                return len(self.storage.get_actions_by_date(today))
            else:
                # 从内存缓存估算
                return len(self.profile_cache) * 10  # 估算每用户10次操作
        except Exception:
            return 0

    def _calculate_active_users_today(self) -> int:
        """计算今日活跃用户数"""
        try:
            today = datetime.now().date()
            if hasattr(self.storage, 'get_active_users_by_date'):
                return len(self.storage.get_active_users_by_date(today))
            else:
                # 从内存缓存估算
                return max(1, len(self.profile_cache) // 2)  # 估算一半用户活跃
        except Exception:
            return 0

    def _calculate_top_actions(self) -> Dict[str, int]:
        """计算热门操作"""
        try:
            if hasattr(self.storage, 'get_action_statistics'):
                return self.storage.get_action_statistics()
            else:
                # 返回模拟数据
                return {
                    'data_import': 45,
                    'chart_view': 32,
                    'analysis_run': 28,
                    'config_change': 15,
                    'export_data': 12
                }
        except Exception:
            return {}

    def _calculate_recommendation_acceptance_rate(self) -> float:
        """计算推荐接受率"""
        try:
            if hasattr(self, '_recommendation_feedback'):
                total = len(self._recommendation_feedback)
                if total == 0:
                    return 0.0
                accepted = sum(1 for feedback in self._recommendation_feedback.values()
                               if feedback.get('is_accepted', False))
                return accepted / total
            else:
                return 0.75  # 默认75%接受率
        except Exception:
            return 0.0


# 全局实例
user_behavior_learner = None


def get_user_behavior_learner(storage_path: Optional[str] = None) -> UserBehaviorLearner:
    """获取用户行为学习器实例"""
    global user_behavior_learner

    if user_behavior_learner is None:
        user_behavior_learner = UserBehaviorLearner(storage_path)

    return user_behavior_learner


def record_user_action(user_id: str, session_id: str, action_type: ActionType, **kwargs) -> bool:
    """记录用户行为的便捷函数"""
    learner = get_user_behavior_learner()
    return learner.record_action(user_id, session_id, action_type, **kwargs)


def get_user_recommendations(user_id: str, limit: int = 5) -> List[Recommendation]:
    """获取用户推荐的便捷函数"""
    learner = get_user_behavior_learner()
    return learner.get_user_recommendations(user_id, limit)
