#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能配置管理器

在现有ImportConfigManager基础上增加智能化功能：
1. 自适应配置优化
2. 智能配置推荐
3. 配置模板学习
4. 环境感知配置调整
5. 配置冲突检测和解决
6. 智能配置验证
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import sqlite3
import threading
from loguru import logger

from .import_config_manager import (
    ImportConfigManager, ImportTaskConfig, DataSourceConfig,
    ImportProgress, ImportStatus, DataFrequency, ImportMode
)
from ..services.ai_prediction_service import AIPredictionService, PredictionType


class ConfigOptimizationLevel(Enum):
    """配置优化级别"""
    CONSERVATIVE = "conservative"  # 保守优化
    BALANCED = "balanced"         # 平衡优化
    AGGRESSIVE = "aggressive"     # 激进优化


class ConfigRecommendationType(Enum):
    """配置推荐类型"""
    PERFORMANCE = "performance"   # 性能优化
    RELIABILITY = "reliability"   # 可靠性优化
    COST = "cost"                # 成本优化
    BALANCED = "balanced"         # 平衡优化


@dataclass
class ConfigTemplate:
    """配置模板"""
    template_id: str
    name: str
    description: str
    data_source: str
    asset_type: str
    frequency: DataFrequency
    base_config: Dict[str, Any]
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            'template_id': self.template_id,
            'name': self.name,
            'description': self.description,
            'data_source': self.data_source,
            'asset_type': self.asset_type,
            'frequency': self.frequency.value,
            'base_config': self.base_config,
            'performance_metrics': self.performance_metrics,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigTemplate':
        """从字典创建"""
        data['frequency'] = DataFrequency(data['frequency'])
        return cls(**data)


@dataclass
class ConfigRecommendation:
    """配置推荐"""
    recommendation_id: str
    config_id: str
    recommendation_type: ConfigRecommendationType
    recommended_changes: Dict[str, Any]
    expected_improvement: Dict[str, float]
    confidence_score: float
    reasoning: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConfigConflict:
    """配置冲突"""
    conflict_id: str
    config_ids: List[str]
    conflict_type: str
    description: str
    severity: str  # low, medium, high, critical
    suggested_resolution: Dict[str, Any]
    auto_resolvable: bool = False


class IntelligentConfigManager(ImportConfigManager):
    """
    智能配置管理器

    在原有配置管理基础上增加智能化功能
    """

    def __init__(self, db_path: str = "data/factorweave_system.sqlite"):
        super().__init__(db_path)

        try:
            from core.containers import get_service_container
            container = get_service_container()
            self.ai_service = container.resolve(AIPredictionService)
        except Exception:
            self.ai_service = None

        # 智能配置相关数据
        self._config_templates: Dict[str, ConfigTemplate] = {}
        self._config_recommendations: Dict[str, List[ConfigRecommendation]] = {}
        self._config_conflicts: List[ConfigConflict] = []

        # 配置学习数据
        self._performance_history: List[Dict[str, Any]] = []
        self._optimization_cache: Dict[str, Dict[str, Any]] = {}

        # 自动配置能力扩展
        self._auto_config_enabled: bool = True
        self._auto_optimization_interval: int = 3600  # 1小时
        self._auto_conflict_resolution: bool = True
        self._auto_template_learning: bool = True
        self._config_adaptation_rules: Dict[str, Any] = {}
        self._environment_profiles: Dict[str, Dict[str, Any]] = {}
        self._performance_baselines: Dict[str, float] = {}

        # 自动配置线程锁
        self._auto_config_lock = threading.Lock()
        self._last_auto_optimization = datetime.now()

        # 初始化智能功能
        self._init_intelligent_tables()
        self._load_intelligent_data()
        self._init_auto_config_capabilities()

        logger.info("智能配置管理器初始化完成")

    def _init_intelligent_tables(self):
        """初始化智能配置相关数据表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 配置模板表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_templates (
                    template_id TEXT PRIMARY KEY,
                    template_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 配置推荐表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_recommendations (
                    recommendation_id TEXT PRIMARY KEY,
                    config_id TEXT NOT NULL,
                    recommendation_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    applied BOOLEAN DEFAULT FALSE
                )
            """)

            # 配置性能历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_performance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_hash TEXT NOT NULL,
                    performance_data TEXT NOT NULL,
                    execution_time REAL,
                    success_rate REAL,
                    error_rate REAL,
                    throughput REAL,
                    created_at TEXT NOT NULL
                )
            """)

            # 配置冲突表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    conflict_data TEXT NOT NULL,
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
            """)

            # 自动配置规则表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_config_rules (
                    rule_id TEXT PRIMARY KEY,
                    rule_name TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    conditions TEXT NOT NULL,
                    actions TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT TRUE,
                    priority INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 环境配置文件表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS environment_profiles (
                    profile_id TEXT PRIMARY KEY,
                    profile_name TEXT NOT NULL,
                    environment_data TEXT NOT NULL,
                    baseline_metrics TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # 自动优化日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auto_optimization_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_id TEXT NOT NULL,
                    optimization_type TEXT NOT NULL,
                    original_config TEXT NOT NULL,
                    optimized_config TEXT NOT NULL,
                    performance_improvement REAL,
                    success BOOLEAN DEFAULT TRUE,
                    created_at TEXT NOT NULL
                )
            """)

            conn.commit()

    def _load_intelligent_data(self):
        """加载智能配置数据"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 加载配置模板
            cursor.execute("SELECT template_id, template_data FROM config_templates")
            for template_id, template_json in cursor.fetchall():
                try:
                    template_data = json.loads(template_json)
                    self._config_templates[template_id] = ConfigTemplate.from_dict(template_data)
                except Exception as e:
                    logger.error(f"加载配置模板失败 {template_id}: {e}")

            # 加载性能历史
            cursor.execute("""
                SELECT config_hash, performance_data, execution_time, success_rate, 
                       error_rate, throughput, created_at 
                FROM config_performance_history 
                ORDER BY created_at DESC LIMIT 2000
            """)

            for row in cursor.fetchall():
                try:
                    performance_data = json.loads(row[1])
                    self._performance_history.append({
                        'config_hash': row[0],
                        'performance_data': performance_data,
                        'execution_time': row[2],
                        'success_rate': row[3],
                        'error_rate': row[4],
                        'throughput': row[5],
                        'created_at': row[6]
                    })
                except Exception as e:
                    logger.error(f"加载性能历史失败: {e}")

    def _init_auto_config_capabilities(self):
        """初始化自动配置能力"""
        try:
            # 加载自动配置规则
            self._load_auto_config_rules()

            # 加载环境配置文件
            self._load_environment_profiles()

            # 初始化默认配置适应规则
            self._init_default_adaptation_rules()

            # 建立性能基线
            self._establish_performance_baselines()

            logger.info("自动配置能力初始化完成")

        except Exception as e:
            logger.error(f"初始化自动配置能力失败: {e}")

    def _load_auto_config_rules(self):
        """加载自动配置规则"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT rule_id, rule_name, rule_type, conditions, actions, enabled, priority
                    FROM auto_config_rules WHERE enabled = TRUE
                    ORDER BY priority DESC
                """)

                for row in cursor.fetchall():
                    rule_id, rule_name, rule_type, conditions, actions, enabled, priority = row
                    self._config_adaptation_rules[rule_id] = {
                        'name': rule_name,
                        'type': rule_type,
                        'conditions': json.loads(conditions),
                        'actions': json.loads(actions),
                        'enabled': enabled,
                        'priority': priority
                    }

                logger.info(f"加载自动配置规则: {len(self._config_adaptation_rules)}条")

        except Exception as e:
            logger.error(f"加载自动配置规则失败: {e}")

    def _load_environment_profiles(self):
        """加载环境配置文件"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT profile_id, profile_name, environment_data, baseline_metrics
                    FROM environment_profiles
                """)

                for row in cursor.fetchall():
                    profile_id, profile_name, env_data, baseline_metrics = row
                    self._environment_profiles[profile_id] = {
                        'name': profile_name,
                        'environment_data': json.loads(env_data),
                        'baseline_metrics': json.loads(baseline_metrics)
                    }

                logger.info(f"加载环境配置文件: {len(self._environment_profiles)}个")

        except Exception as e:
            logger.error(f"加载环境配置文件失败: {e}")

    def _init_default_adaptation_rules(self):
        """初始化默认配置适应规则"""
        default_rules = [
            {
                'rule_id': 'auto_scale_workers',
                'name': '自动调整工作线程数',
                'type': 'performance_optimization',
                'conditions': {
                    'cpu_utilization': {'operator': '<', 'value': 0.6},
                    'success_rate': {'operator': '>', 'value': 0.9}
                },
                'actions': {
                    'max_workers': {'operation': 'multiply', 'factor': 1.5, 'max': 16}
                },
                'priority': 10
            },
            {
                'rule_id': 'auto_reduce_batch_on_error',
                'name': '错误率高时自动减少批次大小',
                'type': 'reliability_optimization',
                'conditions': {
                    'error_rate': {'operator': '>', 'value': 0.1},
                    'execution_time': {'operator': '>', 'value': 300}
                },
                'actions': {
                    'batch_size': {'operation': 'multiply', 'factor': 0.7, 'min': 100}
                },
                'priority': 20
            },
            {
                'rule_id': 'auto_optimize_memory',
                'name': '内存使用率高时自动优化',
                'type': 'resource_optimization',
                'conditions': {
                    'memory_utilization': {'operator': '>', 'value': 0.8}
                },
                'actions': {
                    'batch_size': {'operation': 'multiply', 'factor': 0.8, 'min': 100},
                    'max_workers': {'operation': 'subtract', 'value': 1, 'min': 1}
                },
                'priority': 15
            }
        ]

        # 保存默认规则到数据库（如果不存在）
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for rule in default_rules:
                    cursor.execute("SELECT COUNT(*) FROM auto_config_rules WHERE rule_id = ?", (rule['rule_id'],))
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("""
                            INSERT INTO auto_config_rules
                            (rule_id, rule_name, rule_type, conditions, actions, enabled, priority, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rule['rule_id'],
                            rule['name'],
                            rule['type'],
                            json.dumps(rule['conditions']),
                            json.dumps(rule['actions']),
                            True,
                            rule['priority'],
                            datetime.now().isoformat(),
                            datetime.now().isoformat()
                        ))

                        # 添加到内存中
                        self._config_adaptation_rules[rule['rule_id']] = {
                            'name': rule['name'],
                            'type': rule['type'],
                            'conditions': rule['conditions'],
                            'actions': rule['actions'],
                            'enabled': True,
                            'priority': rule['priority']
                        }

                conn.commit()
                logger.info("初始化默认配置适应规则完成")

        except Exception as e:
            logger.error(f"初始化默认配置适应规则失败: {e}")

    def _establish_performance_baselines(self):
        """建立性能基线"""
        try:
            if not self._performance_history:
                # 设置默认基线
                self._performance_baselines = {
                    'success_rate': 0.95,
                    'error_rate': 0.05,
                    'avg_execution_time': 60.0,
                    'throughput': 1000.0
                }
                return

            # 基于历史数据计算基线
            df = pd.DataFrame(self._performance_history)

            self._performance_baselines = {
                'success_rate': df['success_rate'].quantile(0.8),  # 80分位数作为基线
                'error_rate': df['error_rate'].quantile(0.2),     # 20分位数作为基线
                'avg_execution_time': df['execution_time'].median(),
                'throughput': df['throughput'].quantile(0.8)
            }

            logger.info(f"建立性能基线: {self._performance_baselines}")

        except Exception as e:
            logger.error(f"建立性能基线失败: {e}")
            # 使用默认基线
            self._performance_baselines = {
                'success_rate': 0.95,
                'error_rate': 0.05,
                'avg_execution_time': 60.0,
                'throughput': 1000.0
            }

    def generate_intelligent_config(self,
                                    base_config: ImportTaskConfig,
                                    optimization_level: ConfigOptimizationLevel = ConfigOptimizationLevel.BALANCED,
                                    target_metrics: Optional[Dict[str, float]] = None) -> ImportTaskConfig:
        """
        生成智能优化的配置

        Args:
            base_config: 基础配置
            optimization_level: 优化级别
            target_metrics: 目标性能指标

        Returns:
            优化后的配置
        """
        logger.info(f"开始生成智能配置，优化级别: {optimization_level.value}")

        try:
            # 1. 分析历史性能数据
            historical_insights = self._analyze_historical_performance(base_config)

            # 2. 获取AI推荐的参数
            ai_recommendations = self._get_ai_parameter_recommendations(base_config)

            # 3. 应用配置模板
            template_config = self._apply_best_template(base_config)

            # 4. 环境感知调整
            environment_adjustments = self._get_environment_adjustments(base_config)

            # 5. 合并所有优化建议
            optimized_config = self._merge_optimization_suggestions(
                base_config,
                historical_insights,
                ai_recommendations,
                template_config,
                environment_adjustments,
                optimization_level
            )

            # 6. 验证配置合理性
            validation_result = self._validate_intelligent_config(optimized_config)
            if not validation_result['is_valid']:
                logger.warning(f"配置验证失败: {validation_result['issues']}")
                # 回退到更保守的配置
                optimized_config = self._apply_conservative_fallback(base_config)

            # 7. 记录优化过程
            self._record_optimization_process(base_config, optimized_config, {
                'historical_insights': historical_insights,
                'ai_recommendations': ai_recommendations,
                'template_config': template_config,
                'environment_adjustments': environment_adjustments,
                'optimization_level': optimization_level.value
            })

            logger.info("智能配置生成完成")
            return optimized_config

        except Exception as e:
            logger.error(f"生成智能配置失败: {e}")
            return base_config

    def _analyze_historical_performance(self, config: ImportTaskConfig) -> Dict[str, Any]:
        """分析历史性能数据"""
        try:
            # 查找相似配置的历史性能
            similar_configs = []
            config_key = f"{config.data_source}_{config.asset_type}_{config.frequency.value}"

            for history in self._performance_history:
                perf_data = history['performance_data']
                if (perf_data.get('data_source') == config.data_source and
                    perf_data.get('asset_type') == config.asset_type and
                        perf_data.get('frequency') == config.frequency.value):
                    similar_configs.append(history)

            if not similar_configs:
                return {'insights': 'no_historical_data', 'recommendations': {}}

            # 分析性能趋势
            df = pd.DataFrame(similar_configs)

            insights = {
                'total_samples': len(similar_configs),
                'avg_execution_time': df['execution_time'].mean(),
                'avg_success_rate': df['success_rate'].mean(),
                'avg_error_rate': df['error_rate'].mean(),
                'avg_throughput': df['throughput'].mean(),
                'performance_trend': self._calculate_performance_trend(df),
                'optimal_parameters': self._find_optimal_parameters(similar_configs)
            }

            return insights

        except Exception as e:
            logger.error(f"分析历史性能失败: {e}")
            return {'insights': 'analysis_failed', 'recommendations': {}}

    def _get_ai_parameter_recommendations(self, config: ImportTaskConfig) -> Dict[str, Any]:
        """获取AI参数推荐"""
        try:
            # 准备历史数据
            historical_data = pd.DataFrame(self._performance_history)

            if len(historical_data) < 10:
                return {'recommendations': {}, 'confidence': 0.0}

            # 使用AI服务进行参数优化
            ai_result = self.ai_service.predict(
                prediction_type=PredictionType.PARAMETER_OPTIMIZATION,
                task_config=config,
                historical_data=historical_data
            )

            if ai_result:
                return {
                    'recommendations': ai_result,
                    'confidence': ai_result.get('confidence', 0.5)
                }
            else:
                return {'recommendations': {}, 'confidence': 0.0}

        except Exception as e:
            logger.error(f"获取AI参数推荐失败: {e}")
            return {'recommendations': {}, 'confidence': 0.0}

    def _apply_best_template(self, config: ImportTaskConfig) -> Optional[ImportTaskConfig]:
        """应用最佳配置模板"""
        try:
            # 查找匹配的模板
            matching_templates = []

            for template in self._config_templates.values():
                if (template.data_source == config.data_source and
                    template.asset_type == config.asset_type and
                        template.frequency == config.frequency):
                    matching_templates.append(template)

            if not matching_templates:
                return None

            # 选择最佳模板（基于成功率和使用次数）
            best_template = max(matching_templates,
                                key=lambda t: t.success_rate * 0.7 + (t.usage_count / 100) * 0.3)

            # 应用模板配置
            template_config = ImportTaskConfig(
                task_id=config.task_id,
                name=config.name,
                data_source=config.data_source,
                asset_type=config.asset_type,
                data_type=config.data_type,
                symbols=config.symbols,
                frequency=config.frequency,
                mode=config.mode,
                start_date=config.start_date,
                end_date=config.end_date,
                schedule_cron=config.schedule_cron,
                enabled=config.enabled,
                max_workers=best_template.base_config.get('max_workers', config.max_workers),
                batch_size=best_template.base_config.get('batch_size', config.batch_size),
                created_at=config.created_at,
                updated_at=datetime.now().isoformat()
            )

            logger.info(f"应用配置模板: {best_template.name}")
            return template_config

        except Exception as e:
            logger.error(f"应用配置模板失败: {e}")
            return None

    def _get_environment_adjustments(self, config: ImportTaskConfig) -> Dict[str, Any]:
        """获取环境感知调整"""
        try:
            adjustments = {}

            # 1. 系统资源感知
            import psutil

            # CPU调整
            cpu_count = psutil.cpu_count()
            cpu_usage = psutil.cpu_percent(interval=1)

            if cpu_usage > 80:
                # 高CPU使用率，减少并发
                adjustments['max_workers'] = min(config.max_workers, max(1, cpu_count // 2))
            elif cpu_usage < 30:
                # 低CPU使用率，可以增加并发
                adjustments['max_workers'] = min(config.max_workers * 2, cpu_count)

            # 内存调整
            memory = psutil.virtual_memory()
            if memory.percent > 80:
                # 高内存使用率，减少批次大小
                adjustments['batch_size'] = max(100, config.batch_size // 2)
            elif memory.percent < 50:
                # 低内存使用率，可以增加批次大小
                adjustments['batch_size'] = min(config.batch_size * 2, 5000)

            # 2. 网络状况感知
            network_latency = self._measure_network_latency(config.data_source)
            if network_latency > 1000:  # 高延迟
                adjustments['timeout'] = 60
                adjustments['retry_count'] = 5
            elif network_latency < 100:  # 低延迟
                adjustments['timeout'] = 15
                adjustments['retry_count'] = 2

            # 3. 时间感知调整
            current_hour = datetime.now().hour
            if 9 <= current_hour <= 15:  # 交易时间
                # 交易时间可能网络繁忙，采用保守配置
                adjustments['rate_limit'] = adjustments.get('rate_limit', 50)
            else:
                # 非交易时间，可以更激进
                adjustments['rate_limit'] = adjustments.get('rate_limit', 200)

            return adjustments

        except Exception as e:
            logger.error(f"获取环境调整失败: {e}")
            return {}

    def _merge_optimization_suggestions(self,
                                        base_config: ImportTaskConfig,
                                        historical_insights: Dict[str, Any],
                                        ai_recommendations: Dict[str, Any],
                                        template_config: Optional[ImportTaskConfig],
                                        environment_adjustments: Dict[str, Any],
                                        optimization_level: ConfigOptimizationLevel) -> ImportTaskConfig:
        """合并所有优化建议"""

        # 创建优化后的配置副本
        optimized = ImportTaskConfig(
            task_id=base_config.task_id,
            name=base_config.name,
            data_source=base_config.data_source,
            asset_type=base_config.asset_type,
            data_type=base_config.data_type,
            symbols=base_config.symbols,
            frequency=base_config.frequency,
            mode=base_config.mode,
            start_date=base_config.start_date,
            end_date=base_config.end_date,
            schedule_cron=base_config.schedule_cron,
            enabled=base_config.enabled,
            max_workers=base_config.max_workers,
            batch_size=base_config.batch_size,
            created_at=base_config.created_at,
            updated_at=datetime.now().isoformat()
        )

        # 权重配置（根据优化级别调整）
        if optimization_level == ConfigOptimizationLevel.CONSERVATIVE:
            weights = {'historical': 0.5, 'ai': 0.2, 'template': 0.2, 'environment': 0.1}
        elif optimization_level == ConfigOptimizationLevel.BALANCED:
            weights = {'historical': 0.3, 'ai': 0.3, 'template': 0.2, 'environment': 0.2}
        else:  # AGGRESSIVE
            weights = {'historical': 0.2, 'ai': 0.4, 'template': 0.2, 'environment': 0.2}

        # 合并max_workers建议
        workers_suggestions = []

        if historical_insights.get('optimal_parameters', {}).get('max_workers'):
            workers_suggestions.append((
                historical_insights['optimal_parameters']['max_workers'],
                weights['historical']
            ))

        if ai_recommendations.get('recommendations', {}).get('max_workers'):
            workers_suggestions.append((
                ai_recommendations['recommendations']['max_workers'],
                weights['ai']
            ))

        if template_config and template_config.max_workers:
            workers_suggestions.append((
                template_config.max_workers,
                weights['template']
            ))

        if environment_adjustments.get('max_workers'):
            workers_suggestions.append((
                environment_adjustments['max_workers'],
                weights['environment']
            ))

        if workers_suggestions:
            weighted_workers = sum(value * weight for value, weight in workers_suggestions)
            total_weight = sum(weight for _, weight in workers_suggestions)
            optimized.max_workers = max(1, int(weighted_workers / total_weight))

        # 合并batch_size建议
        batch_suggestions = []

        if historical_insights.get('optimal_parameters', {}).get('batch_size'):
            batch_suggestions.append((
                historical_insights['optimal_parameters']['batch_size'],
                weights['historical']
            ))

        if ai_recommendations.get('recommendations', {}).get('batch_size'):
            batch_suggestions.append((
                ai_recommendations['recommendations']['batch_size'],
                weights['ai']
            ))

        if template_config and template_config.batch_size:
            batch_suggestions.append((
                template_config.batch_size,
                weights['template']
            ))

        if environment_adjustments.get('batch_size'):
            batch_suggestions.append((
                environment_adjustments['batch_size'],
                weights['environment']
            ))

        if batch_suggestions:
            weighted_batch = sum(value * weight for value, weight in batch_suggestions)
            total_weight = sum(weight for _, weight in batch_suggestions)
            optimized.batch_size = max(100, int(weighted_batch / total_weight))

        return optimized

    def _validate_intelligent_config(self, config: ImportTaskConfig) -> Dict[str, Any]:
        """验证智能配置的合理性"""
        issues = []

        # 基本范围检查
        if config.max_workers < 1 or config.max_workers > 32:
            issues.append(f"max_workers超出合理范围: {config.max_workers}")

        if config.batch_size < 10 or config.batch_size > 10000:
            issues.append(f"batch_size超出合理范围: {config.batch_size}")

        # 资源合理性检查
        import psutil
        cpu_count = psutil.cpu_count()
        if config.max_workers > cpu_count * 2:
            issues.append(f"max_workers过高，可能导致资源竞争: {config.max_workers} > {cpu_count * 2}")

        # 数据源特定检查
        if config.data_source == "tongdaxin" and config.batch_size > 2000:
            issues.append("通达信数据源建议batch_size不超过2000")

        return {
            'is_valid': len(issues) == 0,
            'issues': issues
        }

    def _apply_conservative_fallback(self, base_config: ImportTaskConfig) -> ImportTaskConfig:
        """应用保守的回退配置"""
        fallback = ImportTaskConfig(
            task_id=base_config.task_id,
            name=base_config.name,
            data_source=base_config.data_source,
            asset_type=base_config.asset_type,
            data_type=base_config.data_type,
            symbols=base_config.symbols,
            frequency=base_config.frequency,
            mode=base_config.mode,
            start_date=base_config.start_date,
            end_date=base_config.end_date,
            schedule_cron=base_config.schedule_cron,
            enabled=base_config.enabled,
            max_workers=min(base_config.max_workers, 2),  # 保守的并发数
            batch_size=min(base_config.batch_size, 500),  # 保守的批次大小
            created_at=base_config.created_at,
            updated_at=datetime.now().isoformat()
        )

        logger.info("应用保守回退配置")
        return fallback

    def _record_optimization_process(self,
                                     original_config: ImportTaskConfig,
                                     optimized_config: ImportTaskConfig,
                                     optimization_details: Dict[str, Any]):
        """记录优化过程"""
        try:
            optimization_record = {
                'original_config': original_config.to_dict(),
                'optimized_config': optimized_config.to_dict(),
                'optimization_details': optimization_details,
                'timestamp': datetime.now().isoformat()
            }

            # 缓存优化结果
            config_key = f"{original_config.data_source}_{original_config.asset_type}_{original_config.frequency.value}"
            self._optimization_cache[config_key] = optimization_record

            logger.info(f"记录配置优化过程: {original_config.task_id}")

        except Exception as e:
            logger.error(f"记录优化过程失败: {e}")

    def generate_config_recommendations(self,
                                        config_id: str,
                                        recommendation_type: ConfigRecommendationType = ConfigRecommendationType.BALANCED) -> List[ConfigRecommendation]:
        """生成配置推荐"""
        try:
            config = self.get_import_task(config_id)
            if not config:
                logger.error(f"配置不存在: {config_id}")
                return []

            recommendations = []

            # 1. 性能优化推荐
            if recommendation_type in [ConfigRecommendationType.PERFORMANCE, ConfigRecommendationType.BALANCED]:
                perf_recommendations = self._generate_performance_recommendations(config)
                recommendations.extend(perf_recommendations)

            # 2. 可靠性优化推荐
            if recommendation_type in [ConfigRecommendationType.RELIABILITY, ConfigRecommendationType.BALANCED]:
                reliability_recommendations = self._generate_reliability_recommendations(config)
                recommendations.extend(reliability_recommendations)

            # 3. 成本优化推荐
            if recommendation_type in [ConfigRecommendationType.COST, ConfigRecommendationType.BALANCED]:
                cost_recommendations = self._generate_cost_recommendations(config)
                recommendations.extend(cost_recommendations)

            # 保存推荐到数据库
            self._save_recommendations(config_id, recommendations)

            logger.info(f"生成配置推荐完成: {len(recommendations)}条")
            return recommendations

        except Exception as e:
            logger.error(f"生成配置推荐失败: {e}")
            return []

    def _generate_performance_recommendations(self, config: ImportTaskConfig) -> List[ConfigRecommendation]:
        """生成性能优化推荐"""
        recommendations = []

        try:
            # 分析当前配置的性能瓶颈
            current_performance = self._estimate_config_performance(config)

            # 推荐1: 优化并发数
            if current_performance.get('cpu_utilization', 0) < 0.6:
                recommendations.append(ConfigRecommendation(
                    recommendation_id=f"perf_workers_{config.task_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    config_id=config.task_id,
                    recommendation_type=ConfigRecommendationType.PERFORMANCE,
                    recommended_changes={'max_workers': min(config.max_workers * 2, 8)},
                    expected_improvement={'execution_time_reduction': 0.3, 'throughput_increase': 0.4},
                    confidence_score=0.8,
                    reasoning="CPU利用率较低，可以增加并发数提升性能"
                ))

            # 推荐2: 优化批次大小
            if current_performance.get('memory_utilization', 0) < 0.7:
                recommendations.append(ConfigRecommendation(
                    recommendation_id=f"perf_batch_{config.task_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    config_id=config.task_id,
                    recommendation_type=ConfigRecommendationType.PERFORMANCE,
                    recommended_changes={'batch_size': min(config.batch_size * 2, 3000)},
                    expected_improvement={'execution_time_reduction': 0.2, 'throughput_increase': 0.3},
                    confidence_score=0.7,
                    reasoning="内存利用率较低，可以增加批次大小减少网络请求次数"
                ))

        except Exception as e:
            logger.error(f"生成性能推荐失败: {e}")

        return recommendations

    def _generate_reliability_recommendations(self, config: ImportTaskConfig) -> List[ConfigRecommendation]:
        """生成可靠性优化推荐"""
        recommendations = []

        try:
            # 分析历史失败率
            failure_rate = self._calculate_config_failure_rate(config)

            if failure_rate > 0.1:  # 失败率超过10%
                recommendations.append(ConfigRecommendation(
                    recommendation_id=f"rel_retry_{config.task_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    config_id=config.task_id,
                    recommendation_type=ConfigRecommendationType.RELIABILITY,
                    recommended_changes={
                        'max_workers': max(1, config.max_workers // 2),
                        'batch_size': max(100, config.batch_size // 2)
                    },
                    expected_improvement={'failure_rate_reduction': 0.5, 'success_rate_increase': 0.3},
                    confidence_score=0.9,
                    reasoning=f"当前失败率较高({failure_rate:.1%})，建议降低并发和批次大小提升稳定性"
                ))

        except Exception as e:
            logger.error(f"生成可靠性推荐失败: {e}")

        return recommendations

    def _generate_cost_recommendations(self, config: ImportTaskConfig) -> List[ConfigRecommendation]:
        """生成成本优化推荐"""
        recommendations = []

        try:
            # 分析资源使用成本
            resource_cost = self._estimate_resource_cost(config)

            if resource_cost.get('cpu_cost', 0) > 0.8:
                recommendations.append(ConfigRecommendation(
                    recommendation_id=f"cost_cpu_{config.task_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    config_id=config.task_id,
                    recommendation_type=ConfigRecommendationType.COST,
                    recommended_changes={'max_workers': max(1, config.max_workers - 1)},
                    expected_improvement={'cpu_cost_reduction': 0.2, 'total_cost_reduction': 0.15},
                    confidence_score=0.7,
                    reasoning="CPU成本较高，建议适当降低并发数"
                ))

        except Exception as e:
            logger.error(f"生成成本推荐失败: {e}")

        return recommendations

    def detect_config_conflicts(self) -> List[ConfigConflict]:
        """检测配置冲突"""
        conflicts = []

        try:
            all_tasks = self.get_all_import_tasks()
            task_list = list(all_tasks.values())

            # 检测资源冲突
            conflicts.extend(self._detect_resource_conflicts(task_list))

            # 检测时间冲突
            conflicts.extend(self._detect_schedule_conflicts(task_list))

            # 检测数据源冲突
            conflicts.extend(self._detect_datasource_conflicts(task_list))

            # 保存冲突到数据库
            self._save_conflicts(conflicts)

            logger.info(f"检测到配置冲突: {len(conflicts)}个")
            return conflicts

        except Exception as e:
            logger.error(f"检测配置冲突失败: {e}")
            return []

    def _detect_resource_conflicts(self, tasks: List[ImportTaskConfig]) -> List[ConfigConflict]:
        """检测资源冲突"""
        conflicts = []

        try:
            import psutil
            total_cpu = psutil.cpu_count()

            # 计算同时运行任务的总资源需求
            running_tasks = [task for task in tasks if task.enabled]
            total_workers = sum(task.max_workers for task in running_tasks)

            if total_workers > total_cpu * 2:  # 超过CPU核心数的2倍
                conflict_ids = [task.task_id for task in running_tasks]
                conflicts.append(ConfigConflict(
                    conflict_id=f"resource_cpu_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    config_ids=conflict_ids,
                    conflict_type="resource_overcommit",
                    description=f"总工作线程数({total_workers})超过系统CPU容量({total_cpu * 2})",
                    severity="high",
                    suggested_resolution={
                        'action': 'reduce_workers',
                        'target_workers': total_cpu * 2,
                        'distribution': 'proportional'
                    },
                    auto_resolvable=True
                ))

        except Exception as e:
            logger.error(f"检测资源冲突失败: {e}")

        return conflicts

    def _detect_schedule_conflicts(self, tasks: List[ImportTaskConfig]) -> List[ConfigConflict]:
        """检测调度冲突"""
        conflicts = []

        try:
            scheduled_tasks = [task for task in tasks
                               if task.mode == ImportMode.SCHEDULED and task.schedule_cron]

            # 简单的时间冲突检测（可以扩展为更复杂的cron解析）
            schedule_groups = {}
            for task in scheduled_tasks:
                cron = task.schedule_cron
                if cron in schedule_groups:
                    schedule_groups[cron].append(task)
                else:
                    schedule_groups[cron] = [task]

            for cron, group_tasks in schedule_groups.items():
                if len(group_tasks) > 1:
                    conflict_ids = [task.task_id for task in group_tasks]
                    conflicts.append(ConfigConflict(
                        conflict_id=f"schedule_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        config_ids=conflict_ids,
                        conflict_type="schedule_overlap",
                        description=f"多个任务使用相同的调度时间: {cron}",
                        severity="medium",
                        suggested_resolution={
                            'action': 'stagger_schedules',
                            'interval_minutes': 5
                        },
                        auto_resolvable=True
                    ))

        except Exception as e:
            logger.error(f"检测调度冲突失败: {e}")

        return conflicts

    def _detect_datasource_conflicts(self, tasks: List[ImportTaskConfig]) -> List[ConfigConflict]:
        """检测数据源冲突"""
        conflicts = []

        try:
            # 按数据源分组
            datasource_groups = {}
            for task in tasks:
                if task.enabled:
                    ds = task.data_source
                    if ds in datasource_groups:
                        datasource_groups[ds].append(task)
                    else:
                        datasource_groups[ds] = [task]

            # 检测每个数据源的负载
            for datasource, ds_tasks in datasource_groups.items():
                total_requests = sum(len(task.symbols) * (task.batch_size or 1000) for task in ds_tasks)

                # 假设每个数据源有请求限制
                datasource_limits = {
                    'tongdaxin': 10000,
                    'akshare': 5000,
                    'tushare': 8000
                }

                limit = datasource_limits.get(datasource, 5000)
                if total_requests > limit:
                    conflict_ids = [task.task_id for task in ds_tasks]
                    conflicts.append(ConfigConflict(
                        conflict_id=f"datasource_{datasource}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        config_ids=conflict_ids,
                        conflict_type="datasource_overload",
                        description=f"数据源{datasource}请求量({total_requests})超过限制({limit})",
                        severity="high",
                        suggested_resolution={
                            'action': 'reduce_batch_size',
                            'target_requests': limit,
                            'distribution': 'proportional'
                        },
                        auto_resolvable=True
                    ))

        except Exception as e:
            logger.error(f"检测数据源冲突失败: {e}")

        return conflicts

    def auto_resolve_conflicts(self, conflicts: List[ConfigConflict]) -> Dict[str, Any]:
        """自动解决配置冲突"""
        resolution_results = {
            'resolved': 0,
            'failed': 0,
            'details': []
        }

        for conflict in conflicts:
            if not conflict.auto_resolvable:
                continue

            try:
                if conflict.conflict_type == "resource_overcommit":
                    success = self._resolve_resource_conflict(conflict)
                elif conflict.conflict_type == "schedule_overlap":
                    success = self._resolve_schedule_conflict(conflict)
                elif conflict.conflict_type == "datasource_overload":
                    success = self._resolve_datasource_conflict(conflict)
                else:
                    success = False

                if success:
                    resolution_results['resolved'] += 1
                    resolution_results['details'].append({
                        'conflict_id': conflict.conflict_id,
                        'status': 'resolved',
                        'action': conflict.suggested_resolution.get('action')
                    })
                else:
                    resolution_results['failed'] += 1
                    resolution_results['details'].append({
                        'conflict_id': conflict.conflict_id,
                        'status': 'failed',
                        'reason': 'resolution_failed'
                    })

            except Exception as e:
                logger.error(f"解决冲突失败 {conflict.conflict_id}: {e}")
                resolution_results['failed'] += 1
                resolution_results['details'].append({
                    'conflict_id': conflict.conflict_id,
                    'status': 'failed',
                    'reason': str(e)
                })

        logger.info(f"冲突解决完成: 成功{resolution_results['resolved']}个, 失败{resolution_results['failed']}个")
        return resolution_results

    def _resolve_resource_conflict(self, conflict: ConfigConflict) -> bool:
        """解决资源冲突"""
        try:
            resolution = conflict.suggested_resolution
            target_workers = resolution['target_workers']

            # 按比例分配工作线程
            affected_tasks = []
            total_current_workers = 0

            for config_id in conflict.config_ids:
                task = self.get_import_task(config_id)
                if task:
                    affected_tasks.append(task)
                    total_current_workers += task.max_workers

            if total_current_workers == 0:
                return False

            # 按比例调整
            for task in affected_tasks:
                proportion = task.max_workers / total_current_workers
                new_workers = max(1, int(target_workers * proportion))

                self.update_import_task(task.task_id, max_workers=new_workers)
                logger.info(f"调整任务 {task.task_id} 工作线程: {task.max_workers} -> {new_workers}")

            return True

        except Exception as e:
            logger.error(f"解决资源冲突失败: {e}")
            return False

    def _resolve_schedule_conflict(self, conflict: ConfigConflict) -> bool:
        """解决调度冲突"""
        try:
            resolution = conflict.suggested_resolution
            interval_minutes = resolution['interval_minutes']

            # 错开调度时间
            for i, config_id in enumerate(conflict.config_ids[1:], 1):  # 跳过第一个
                task = self.get_import_task(config_id)
                if task and task.schedule_cron:
                    # 简单的时间错开（实际应该解析cron表达式）
                    # 这里只是示例实现
                    new_cron = self._adjust_cron_schedule(task.schedule_cron, i * interval_minutes)
                    self.update_import_task(config_id, schedule_cron=new_cron)
                    logger.info(f"调整任务 {config_id} 调度时间: {task.schedule_cron} -> {new_cron}")

            return True

        except Exception as e:
            logger.error(f"解决调度冲突失败: {e}")
            return False

    def _resolve_datasource_conflict(self, conflict: ConfigConflict) -> bool:
        """解决数据源冲突"""
        try:
            resolution = conflict.suggested_resolution
            target_requests = resolution['target_requests']

            # 按比例减少批次大小
            affected_tasks = []
            total_current_requests = 0

            for config_id in conflict.config_ids:
                task = self.get_import_task(config_id)
                if task:
                    affected_tasks.append(task)
                    total_current_requests += len(task.symbols) * task.batch_size

            if total_current_requests == 0:
                return False

            # 按比例调整批次大小
            for task in affected_tasks:
                current_requests = len(task.symbols) * task.batch_size
                proportion = current_requests / total_current_requests
                target_task_requests = target_requests * proportion
                new_batch_size = max(100, int(target_task_requests / len(task.symbols)))

                self.update_import_task(task.task_id, batch_size=new_batch_size)
                logger.info(f"调整任务 {task.task_id} 批次大小: {task.batch_size} -> {new_batch_size}")

            return True

        except Exception as e:
            logger.error(f"解决数据源冲突失败: {e}")
            return False

    # 辅助方法
    def _calculate_performance_trend(self, df: pd.DataFrame) -> str:
        """计算性能趋势"""
        if len(df) < 2:
            return "insufficient_data"

        df_sorted = df.sort_values('created_at')
        recent_performance = df_sorted.tail(10)['success_rate'].mean()
        older_performance = df_sorted.head(10)['success_rate'].mean()

        if recent_performance > older_performance * 1.1:
            return "improving"
        elif recent_performance < older_performance * 0.9:
            return "declining"
        else:
            return "stable"

    def _find_optimal_parameters(self, similar_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """查找最优参数"""
        if not similar_configs:
            return {}

        # 按成功率排序，取前20%的配置
        sorted_configs = sorted(similar_configs, key=lambda x: x['success_rate'], reverse=True)
        top_configs = sorted_configs[:max(1, len(sorted_configs) // 5)]

        # 计算最优参数的平均值
        optimal_params = {}

        batch_sizes = []
        max_workers = []

        for config in top_configs:
            perf_data = config['performance_data']
            if 'batch_size' in perf_data:
                batch_sizes.append(perf_data['batch_size'])
            if 'max_workers' in perf_data:
                max_workers.append(perf_data['max_workers'])

        if batch_sizes:
            optimal_params['batch_size'] = int(np.median(batch_sizes))
        if max_workers:
            optimal_params['max_workers'] = int(np.median(max_workers))

        return optimal_params

    def _measure_network_latency(self, data_source: str) -> float:
        """测量网络延迟"""
        try:
            import ping3

            # 数据源对应的测试主机
            test_hosts = {
                'tongdaxin': 'www.10jqka.com.cn',
                'akshare': 'www.akshare.xyz',
                'tushare': 'tushare.pro'
            }

            host = test_hosts.get(data_source, 'www.baidu.com')
            latency = ping3.ping(host, timeout=2)

            return latency * 1000 if latency else 1000  # 转换为毫秒

        except Exception:
            return 500  # 默认延迟

    def _estimate_config_performance(self, config: ImportTaskConfig) -> Dict[str, float]:
        """估算配置性能"""
        # 简化的性能估算模型
        return {
            'cpu_utilization': min(0.9, config.max_workers * 0.15),
            'memory_utilization': min(0.9, config.batch_size * 0.0001),
            'network_utilization': min(0.9, len(config.symbols) * 0.01)
        }

    def _calculate_config_failure_rate(self, config: ImportTaskConfig) -> float:
        """计算配置失败率"""
        # 从历史数据中计算失败率
        similar_configs = [
            h for h in self._performance_history
            if (h['performance_data'].get('data_source') == config.data_source and
                h['performance_data'].get('asset_type') == config.asset_type)
        ]

        if not similar_configs:
            return 0.1  # 默认失败率

        total_runs = len(similar_configs)
        failed_runs = sum(1 for h in similar_configs if h['success_rate'] < 0.8)

        return failed_runs / total_runs if total_runs > 0 else 0.1

    def _estimate_resource_cost(self, config: ImportTaskConfig) -> Dict[str, float]:
        """估算资源成本"""
        return {
            'cpu_cost': config.max_workers * 0.1,
            'memory_cost': config.batch_size * 0.00001,
            'network_cost': len(config.symbols) * 0.001
        }

    def _adjust_cron_schedule(self, cron_expr: str, offset_minutes: int) -> str:
        """调整cron调度表达式"""
        # 简化实现，实际应该使用cron解析库
        parts = cron_expr.split()
        if len(parts) >= 2:
            try:
                minute = int(parts[1])
                new_minute = (minute + offset_minutes) % 60
                parts[1] = str(new_minute)
                return ' '.join(parts)
            except ValueError:
                pass

        return cron_expr

    def _save_recommendations(self, config_id: str, recommendations: List[ConfigRecommendation]):
        """保存推荐到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for rec in recommendations:
                    cursor.execute("""
                        INSERT OR REPLACE INTO config_recommendations
                        (recommendation_id, config_id, recommendation_data, created_at, applied)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        rec.recommendation_id,
                        config_id,
                        json.dumps({
                            'recommendation_type': rec.recommendation_type.value,
                            'recommended_changes': rec.recommended_changes,
                            'expected_improvement': rec.expected_improvement,
                            'confidence_score': rec.confidence_score,
                            'reasoning': rec.reasoning,
                            'created_at': rec.created_at
                        }, ensure_ascii=False),
                        rec.created_at,
                        False
                    ))

                conn.commit()

        except Exception as e:
            logger.error(f"保存推荐失败: {e}")

    def _save_conflicts(self, conflicts: List[ConfigConflict]):
        """保存冲突到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for conflict in conflicts:
                    cursor.execute("""
                        INSERT OR REPLACE INTO config_conflicts
                        (conflict_id, conflict_data, resolved, created_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        conflict.conflict_id,
                        json.dumps({
                            'config_ids': conflict.config_ids,
                            'conflict_type': conflict.conflict_type,
                            'description': conflict.description,
                            'severity': conflict.severity,
                            'suggested_resolution': conflict.suggested_resolution,
                            'auto_resolvable': conflict.auto_resolvable
                        }, ensure_ascii=False),
                        False,
                        datetime.now().isoformat()
                    ))

                conn.commit()

        except Exception as e:
            logger.error(f"保存冲突失败: {e}")

    def record_performance_feedback(self,
                                    config: ImportTaskConfig,
                                    execution_time: float,
                                    success_rate: float,
                                    error_rate: float,
                                    throughput: float):
        """记录性能反馈"""
        try:
            import hashlib

            # 生成配置哈希
            config_str = f"{config.data_source}_{config.asset_type}_{config.frequency.value}_{config.max_workers}_{config.batch_size}"
            config_hash = hashlib.md5(config_str.encode()).hexdigest()

            # 保存性能数据
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO config_performance_history
                    (config_hash, performance_data, execution_time, success_rate, error_rate, throughput, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    config_hash,
                    json.dumps({
                        'data_source': config.data_source,
                        'asset_type': config.asset_type,
                        'frequency': config.frequency.value,
                        'max_workers': config.max_workers,
                        'batch_size': config.batch_size,
                        'symbols_count': len(config.symbols)
                    }, ensure_ascii=False),
                    execution_time,
                    success_rate,
                    error_rate,
                    throughput,
                    datetime.now().isoformat()
                ))

                conn.commit()

            # 更新内存中的性能历史
            self._performance_history.append({
                'config_hash': config_hash,
                'performance_data': {
                    'data_source': config.data_source,
                    'asset_type': config.asset_type,
                    'frequency': config.frequency.value,
                    'max_workers': config.max_workers,
                    'batch_size': config.batch_size,
                    'symbols_count': len(config.symbols)
                },
                'execution_time': execution_time,
                'success_rate': success_rate,
                'error_rate': error_rate,
                'throughput': throughput,
                'created_at': datetime.now().isoformat()
            })

            # 保持历史记录在合理范围内
            if len(self._performance_history) > 2000:
                self._performance_history = self._performance_history[-1000:]

            logger.info(f"记录配置性能反馈: {config.task_id}")

        except Exception as e:
            logger.error(f"记录性能反馈失败: {e}")

    def auto_optimize_config(self, config_id: str, current_metrics: Dict[str, float]) -> Optional[ImportTaskConfig]:
        """
        自动优化配置

        Args:
            config_id: 配置ID
            current_metrics: 当前性能指标

        Returns:
            优化后的配置，如果无需优化则返回None
        """
        if not self._auto_config_enabled:
            return None

        with self._auto_config_lock:
            try:
                config = self.get_import_task(config_id)
                if not config:
                    logger.error(f"配置不存在: {config_id}")
                    return None

                # 检查是否需要优化
                if not self._should_auto_optimize(config, current_metrics):
                    return None

                # 应用自动配置规则
                optimized_config = self._apply_auto_config_rules(config, current_metrics)

                if optimized_config and self._is_config_different(config, optimized_config):
                    # 验证优化后的配置
                    validation_result = self._validate_intelligent_config(optimized_config)
                    if validation_result['is_valid']:
                        # 更新配置
                        self.update_import_task(
                            config_id,
                            max_workers=optimized_config.max_workers,
                            batch_size=optimized_config.batch_size
                        )

                        # 记录自动优化日志
                        self._log_auto_optimization(config, optimized_config, current_metrics)

                        logger.info(f"自动优化配置完成: {config_id}")
                        return optimized_config
                    else:
                        logger.warning(f"自动优化配置验证失败: {validation_result['issues']}")

                return None

            except Exception as e:
                logger.error(f"自动优化配置失败: {e}")
                return None

    def _should_auto_optimize(self, config: ImportTaskConfig, current_metrics: Dict[str, float]) -> bool:
        """检查是否应该自动优化"""
        try:
            # 检查优化间隔
            if (datetime.now() - self._last_auto_optimization).total_seconds() < self._auto_optimization_interval:
                return False

            # 检查性能是否低于基线
            baseline_checks = [
                current_metrics.get('success_rate', 1.0) < self._performance_baselines.get('success_rate', 0.95) * 0.9,
                current_metrics.get('error_rate', 0.0) > self._performance_baselines.get('error_rate', 0.05) * 1.5,
                current_metrics.get('execution_time', 0.0) > self._performance_baselines.get('avg_execution_time', 60.0) * 1.3
            ]

            return any(baseline_checks)

        except Exception as e:
            logger.error(f"检查自动优化条件失败: {e}")
            return False

    def _apply_auto_config_rules(self, config: ImportTaskConfig, current_metrics: Dict[str, float]) -> Optional[ImportTaskConfig]:
        """应用自动配置规则"""
        try:
            # 创建配置副本
            optimized_config = ImportTaskConfig(
                task_id=config.task_id,
                name=config.name,
                data_source=config.data_source,
                asset_type=config.asset_type,
                data_type=config.data_type,
                symbols=config.symbols,
                frequency=config.frequency,
                mode=config.mode,
                start_date=config.start_date,
                end_date=config.end_date,
                schedule_cron=config.schedule_cron,
                enabled=config.enabled,
                max_workers=config.max_workers,
                batch_size=config.batch_size,
                created_at=config.created_at,
                updated_at=datetime.now().isoformat()
            )

            # 获取当前环境信息
            environment_info = self._get_current_environment_info()

            # 按优先级排序规则
            sorted_rules = sorted(
                self._config_adaptation_rules.items(),
                key=lambda x: x[1]['priority'],
                reverse=True
            )

            # 应用匹配的规则
            applied_rules = []
            for rule_id, rule in sorted_rules:
                if self._rule_matches_conditions(rule, current_metrics, environment_info):
                    optimized_config = self._apply_rule_actions(optimized_config, rule['actions'])
                    applied_rules.append(rule_id)
                    logger.info(f"应用自动配置规则: {rule['name']}")

            if applied_rules:
                logger.info(f"共应用 {len(applied_rules)} 条自动配置规则")
                return optimized_config
            else:
                return None

        except Exception as e:
            logger.error(f"应用自动配置规则失败: {e}")
            return None

    def _rule_matches_conditions(self, rule: Dict[str, Any], current_metrics: Dict[str, float], environment_info: Dict[str, Any]) -> bool:
        """检查规则条件是否匹配"""
        try:
            conditions = rule['conditions']

            for metric_name, condition in conditions.items():
                operator = condition['operator']
                threshold = condition['value']

                # 获取当前值
                if metric_name in current_metrics:
                    current_value = current_metrics[metric_name]
                elif metric_name in environment_info:
                    current_value = environment_info[metric_name]
                else:
                    continue  # 跳过无法获取的指标

                # 检查条件
                if operator == '>':
                    if not (current_value > threshold):
                        return False
                elif operator == '<':
                    if not (current_value < threshold):
                        return False
                elif operator == '>=':
                    if not (current_value >= threshold):
                        return False
                elif operator == '<=':
                    if not (current_value <= threshold):
                        return False
                elif operator == '==':
                    if not (current_value == threshold):
                        return False
                elif operator == '!=':
                    if not (current_value != threshold):
                        return False

            return True

        except Exception as e:
            logger.error(f"检查规则条件失败: {e}")
            return False

    def _apply_rule_actions(self, config: ImportTaskConfig, actions: Dict[str, Any]) -> ImportTaskConfig:
        """应用规则动作"""
        try:
            for param_name, action in actions.items():
                operation = action['operation']

                if param_name == 'max_workers':
                    current_value = config.max_workers
                elif param_name == 'batch_size':
                    current_value = config.batch_size
                else:
                    continue

                # 执行操作
                if operation == 'multiply':
                    new_value = int(current_value * action['factor'])
                elif operation == 'add':
                    new_value = current_value + action['value']
                elif operation == 'subtract':
                    new_value = current_value - action['value']
                elif operation == 'set':
                    new_value = action['value']
                else:
                    continue

                # 应用限制
                if 'min' in action:
                    new_value = max(new_value, action['min'])
                if 'max' in action:
                    new_value = min(new_value, action['max'])

                # 更新配置
                if param_name == 'max_workers':
                    config.max_workers = new_value
                elif param_name == 'batch_size':
                    config.batch_size = new_value

            return config

        except Exception as e:
            logger.error(f"应用规则动作失败: {e}")
            return config

    def _get_current_environment_info(self) -> Dict[str, Any]:
        """获取当前环境信息"""
        try:
            import psutil

            return {
                'cpu_utilization': psutil.cpu_percent(interval=1) / 100.0,
                'memory_utilization': psutil.virtual_memory().percent / 100.0,
                'disk_utilization': psutil.disk_usage('/').percent / 100.0,
                'cpu_count': psutil.cpu_count(),
                'available_memory_gb': psutil.virtual_memory().available / (1024**3),
                'current_hour': datetime.now().hour,
                'is_business_hours': 9 <= datetime.now().hour <= 17
            }

        except Exception as e:
            logger.error(f"获取环境信息失败: {e}")
            return {}

    def _is_config_different(self, config1: ImportTaskConfig, config2: ImportTaskConfig) -> bool:
        """检查两个配置是否不同"""
        return (config1.max_workers != config2.max_workers or
                config1.batch_size != config2.batch_size)

    def _log_auto_optimization(self, original_config: ImportTaskConfig, optimized_config: ImportTaskConfig, metrics: Dict[str, float]):
        """记录自动优化日志"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 计算性能改进估算
                performance_improvement = self._estimate_performance_improvement(original_config, optimized_config, metrics)

                cursor.execute("""
                    INSERT INTO auto_optimization_logs
                    (config_id, optimization_type, original_config, optimized_config, performance_improvement, success, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    original_config.task_id,
                    'auto_rule_based',
                    json.dumps(original_config.to_dict()),
                    json.dumps(optimized_config.to_dict()),
                    performance_improvement,
                    True,
                    datetime.now().isoformat()
                ))

                conn.commit()

        except Exception as e:
            logger.error(f"记录自动优化日志失败: {e}")

    def _estimate_performance_improvement(self, original: ImportTaskConfig, optimized: ImportTaskConfig, metrics: Dict[str, float]) -> float:
        """估算性能改进"""
        try:
            # 简化的性能改进估算
            worker_improvement = (optimized.max_workers - original.max_workers) / original.max_workers * 0.3
            batch_improvement = (optimized.batch_size - original.batch_size) / original.batch_size * 0.2

            total_improvement = worker_improvement + batch_improvement
            return max(-0.5, min(0.5, total_improvement))  # 限制在-50%到+50%之间

        except Exception as e:
            logger.error(f"估算性能改进失败: {e}")
            return 0.0

    def create_environment_profile(self, profile_name: str, environment_data: Dict[str, Any], baseline_metrics: Dict[str, float]) -> str:
        """创建环境配置文件"""
        try:
            profile_id = f"env_profile_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO environment_profiles
                    (profile_id, profile_name, environment_data, baseline_metrics, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    profile_id,
                    profile_name,
                    json.dumps(environment_data),
                    json.dumps(baseline_metrics),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                conn.commit()

            # 添加到内存
            self._environment_profiles[profile_id] = {
                'name': profile_name,
                'environment_data': environment_data,
                'baseline_metrics': baseline_metrics
            }

            logger.info(f"创建环境配置文件: {profile_name}")
            return profile_id

        except Exception as e:
            logger.error(f"创建环境配置文件失败: {e}")
            return ""

    def create_auto_config_rule(self, rule_name: str, rule_type: str, conditions: Dict[str, Any], actions: Dict[str, Any], priority: int = 0) -> str:
        """创建自动配置规则"""
        try:
            rule_id = f"auto_rule_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO auto_config_rules
                    (rule_id, rule_name, rule_type, conditions, actions, enabled, priority, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rule_id,
                    rule_name,
                    rule_type,
                    json.dumps(conditions),
                    json.dumps(actions),
                    True,
                    priority,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                conn.commit()

            # 添加到内存
            self._config_adaptation_rules[rule_id] = {
                'name': rule_name,
                'type': rule_type,
                'conditions': conditions,
                'actions': actions,
                'enabled': True,
                'priority': priority
            }

            logger.info(f"创建自动配置规则: {rule_name}")
            return rule_id

        except Exception as e:
            logger.error(f"创建自动配置规则失败: {e}")
            return ""

    def enable_auto_config(self, enabled: bool = True):
        """启用/禁用自动配置"""
        self._auto_config_enabled = enabled
        logger.info(f"自动配置{'启用' if enabled else '禁用'}")

    def set_auto_optimization_interval(self, interval_seconds: int):
        """设置自动优化间隔"""
        self._auto_optimization_interval = interval_seconds
        logger.info(f"设置自动优化间隔: {interval_seconds}秒")

    def get_auto_optimization_logs(self, config_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """获取自动优化日志"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if config_id:
                    cursor.execute("""
                        SELECT log_id, config_id, optimization_type, original_config, optimized_config, 
                               performance_improvement, success, created_at
                        FROM auto_optimization_logs 
                        WHERE config_id = ?
                        ORDER BY created_at DESC 
                        LIMIT ?
                    """, (config_id, limit))
                else:
                    cursor.execute("""
                        SELECT log_id, config_id, optimization_type, original_config, optimized_config, 
                               performance_improvement, success, created_at
                        FROM auto_optimization_logs 
                        ORDER BY created_at DESC 
                        LIMIT ?
                    """, (limit,))

                logs = []
                for row in cursor.fetchall():
                    logs.append({
                        'log_id': row[0],
                        'config_id': row[1],
                        'optimization_type': row[2],
                        'original_config': json.loads(row[3]),
                        'optimized_config': json.loads(row[4]),
                        'performance_improvement': row[5],
                        'success': row[6],
                        'created_at': row[7]
                    })

                return logs

        except Exception as e:
            logger.error(f"获取自动优化日志失败: {e}")
            return []

    def get_intelligent_statistics(self) -> Dict[str, Any]:
        """获取智能配置统计信息"""
        try:
            base_stats = self.get_statistics()

            # 添加智能配置相关统计
            intelligent_stats = {
                'config_templates': len(self._config_templates),
                'performance_history_records': len(self._performance_history),
                'optimization_cache_entries': len(self._optimization_cache),
                'active_recommendations': self._count_active_recommendations(),
                'resolved_conflicts': self._count_resolved_conflicts(),
                'average_optimization_improvement': self._calculate_average_improvement(),
                'auto_config_enabled': self._auto_config_enabled,
                'auto_config_rules': len(self._config_adaptation_rules),
                'environment_profiles': len(self._environment_profiles),
                'auto_optimization_interval_hours': self._auto_optimization_interval / 3600,
                'total_auto_optimizations': self._count_auto_optimizations(),
                'successful_auto_optimizations': self._count_successful_auto_optimizations(),
                'auto_optimization_success_rate': self._calculate_auto_optimization_success_rate()
            }

            # 合并统计信息
            base_stats['intelligent_features'] = intelligent_stats

            return base_stats

        except Exception as e:
            logger.error(f"获取智能统计失败: {e}")
            return self.get_statistics()

    def _count_active_recommendations(self) -> int:
        """统计活跃推荐数量"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM config_recommendations WHERE applied = FALSE")
                return cursor.fetchone()[0]
        except:
            return 0

    def _count_resolved_conflicts(self) -> int:
        """统计已解决冲突数量"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM config_conflicts WHERE resolved = TRUE")
                return cursor.fetchone()[0]
        except:
            return 0

    def _calculate_average_improvement(self) -> float:
        """计算平均优化改进"""
        try:
            if not self._performance_history:
                return 0.0

            recent_performance = [h for h in self._performance_history
                                  if datetime.fromisoformat(h['created_at']) > datetime.now() - timedelta(days=30)]

            if len(recent_performance) < 2:
                return 0.0

            success_rates = [h['success_rate'] for h in recent_performance]
            return np.mean(success_rates) if success_rates else 0.0

        except:
            return 0.0

    def _count_auto_optimizations(self) -> int:
        """统计自动优化总数"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM auto_optimization_logs")
                return cursor.fetchone()[0]
        except:
            return 0

    def _count_successful_auto_optimizations(self) -> int:
        """统计成功的自动优化数量"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM auto_optimization_logs WHERE success = TRUE")
                return cursor.fetchone()[0]
        except:
            return 0

    def _calculate_auto_optimization_success_rate(self) -> float:
        """计算自动优化成功率"""
        try:
            total = self._count_auto_optimizations()
            successful = self._count_successful_auto_optimizations()
            return successful / total if total > 0 else 0.0
        except:
            return 0.0


def main():
    """测试智能配置管理器"""
    # 创建智能配置管理器
    manager = IntelligentConfigManager()

    # 创建测试配置
    test_config = ImportTaskConfig(
        task_id="intelligent_test_001",
        name="智能配置测试",
        data_source="tongdaxin",
        asset_type="stock",
        data_type="kline",
        symbols=["000001", "000002", "000858"],
        frequency=DataFrequency.DAILY,
        mode=ImportMode.BATCH,
        max_workers=4,
        batch_size=1000
    )

    # 添加配置
    manager.add_import_task(test_config)

    # 生成智能配置
    optimized_config = manager.generate_intelligent_config(
        test_config,
        ConfigOptimizationLevel.BALANCED
    )

    logger.info(f"原始配置: workers={test_config.max_workers}, batch={test_config.batch_size}")
    logger.info(f"优化配置: workers={optimized_config.max_workers}, batch={optimized_config.batch_size}")

    # 生成推荐
    recommendations = manager.generate_config_recommendations(
        test_config.task_id,
        ConfigRecommendationType.PERFORMANCE
    )

    logger.info(f"生成推荐数量: {len(recommendations)}")

    # 检测冲突
    conflicts = manager.detect_config_conflicts()
    logger.info(f"检测到冲突: {len(conflicts)}个")

    # 测试自动配置能力
    logger.info("=== 测试自动配置能力 ===")

    # 创建自定义自动配置规则
    rule_id = manager.create_auto_config_rule(
        rule_name="测试自动扩展规则",
        rule_type="performance_test",
        conditions={
            'success_rate': {'operator': '>', 'value': 0.95},
            'cpu_utilization': {'operator': '<', 'value': 0.5}
        },
        actions={
            'max_workers': {'operation': 'add', 'value': 2, 'max': 8}
        },
        priority=25
    )
    logger.info(f"创建自动配置规则: {rule_id}")

    # 创建环境配置文件
    profile_id = manager.create_environment_profile(
        profile_name="测试环境",
        environment_data={
            'cpu_cores': 8,
            'memory_gb': 16,
            'network_type': 'high_speed'
        },
        baseline_metrics={
            'success_rate': 0.98,
            'avg_execution_time': 45.0,
            'throughput': 1500.0
        }
    )
    logger.info(f"创建环境配置文件: {profile_id}")

    # 测试自动优化
    test_metrics = {
        'success_rate': 0.85,  # 低于基线，触发优化
        'error_rate': 0.12,    # 高于基线，触发优化
        'execution_time': 90.0,  # 高于基线，触发优化
        'cpu_utilization': 0.4,
        'memory_utilization': 0.6
    }

    auto_optimized = manager.auto_optimize_config(test_config.task_id, test_metrics)
    if auto_optimized:
        logger.info(f"自动优化成功: workers={auto_optimized.max_workers}, batch={auto_optimized.batch_size}")
    else:
        logger.info("未触发自动优化")

    # 获取自动优化日志
    auto_logs = manager.get_auto_optimization_logs(test_config.task_id, 5)
    logger.info(f"自动优化日志数量: {len(auto_logs)}")

    # 获取扩展统计信息
    stats = manager.get_intelligent_statistics()
    logger.info(f"智能统计: {json.dumps(stats, ensure_ascii=False, indent=2)}")

    # 测试自动配置开关
    manager.enable_auto_config(False)
    logger.info("禁用自动配置")

    # 再次尝试自动优化（应该不会执行）
    auto_optimized2 = manager.auto_optimize_config(test_config.task_id, test_metrics)
    logger.info(f"禁用后自动优化结果: {auto_optimized2 is not None}")

    # 重新启用
    manager.enable_auto_config(True)
    manager.set_auto_optimization_interval(1800)  # 30分钟
    logger.info("重新启用自动配置，设置优化间隔为30分钟")


if __name__ == "__main__":
    main()
