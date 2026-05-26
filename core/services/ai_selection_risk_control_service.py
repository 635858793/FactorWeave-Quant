"""
AI选股风险控制和合规检查服务

基于现有风险控制组件，专门为AI选股系统提供风险评估、
合规检查、风险监控和报告功能。

整合现有的RiskControl、ComplianceAuditLogger等组件，
扩展AI选股特有的风险控制功能。

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2025-12-07
"""

from loguru import logger
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import traceback
import uuid
from collections import defaultdict

# 现有风险控制和合规组件
from ..risk.compliance_audit_logger import (
    ComplianceLevel, AuditLevel, AuditRecord, EventType, ComplianceFlag
)
from ..risk_control import (
    RiskMonitor, RiskReportGenerator, RiskControlStrategy
)

# AI选股相关服务
from .ai_selection_integration_service import (
    AISelectionIntegrationService, StockSelectionCriteria, SelectionStrategy,
    StockSelectionResult, SelectionPerformanceMetrics
)

# AI选股回测服务
from .ai_selection_backtest_service import (
    AISelectionBacktestService, AISelectionBacktestConfig, AISelectionBacktestResult,
    AISelectionBacktestSummary, BacktestReportType
)

# 数据库服务
from .database_service import DatabaseService

# 用户画像和个性化引擎
from ..ai.personalized_stock_selection_engine import (
    PersonalizedStockSelectionEngine, PersonalizedSelectionCriteria,
    InvestmentProfile, InvestmentExperience
)

# 指标计算服务
from .enhanced_indicator_service import EnhancedIndicatorService




class RiskControlLevel(Enum):
    """风险控制级别"""
    BASIC = "basic"              # 基础风险控制
    STANDARD = "standard"        # 标准风险控制
    ENHANCED = "enhanced"        # 增强风险控制
    INSTITUTIONAL = "institutional"  # 机构级风险控制


class RiskAssessmentType(Enum):
    """风险评估类型"""
    PRE_SELECTION = "pre_selection"    # 选股前风险评估
    POST_SELECTION = "post_selection"  # 选股后风险评估
    CONTINUOUS = "continuous"          # 持续风险监控
    BACKTEST = "backtest"              # 回测风险评估
    STRESS_TEST = "stress_test"        # 压力测试评估


class ComplianceCheckType(Enum):
    """合规检查类型"""
    REGULATORY = "regulatory"      # 监管合规检查
    INTERNAL = "internal"          # 内部合规检查
    OPERATIONAL = "operational"    # 操作合规检查
    ETHICAL = "ethical"           # 道德合规检查


class RiskAlertLevel(Enum):
    """风险预警级别"""
    INFO = "info"         # 信息
    LOW = "low"           # 低风险
    MEDIUM = "medium"     # 中风险
    HIGH = "high"         # 高风险
    CRITICAL = "critical" # 关键风险


@dataclass
class AIStockRiskMetrics:
    """AI选股风险指标"""
    
    # 基本风险指标
    overall_risk_score: float = 0.0  # 总体风险评分 (0-1)
    market_risk_score: float = 0.0  # 市场风险评分
    liquidity_risk_score: float = 0.0  # 流动性风险评分
    concentration_risk_score: float = 0.0  # 集中度风险评分
    
    # AI选股特有风险指标
    model_risk_score: float = 0.0  # 模型风险评分
    overfitting_risk_score: float = 0.0  # 过拟合风险评分
    bias_risk_score: float = 0.0  # 偏见风险评分
    data_quality_risk_score: float = 0.0  # 数据质量风险评分
    
    # 组合风险指标
    portfolio_var: float = 0.0  # 组合VaR
    portfolio_cvar: float = 0.0  # 组合条件VaR
    maximum_drawdown: float = 0.0  # 最大回撤
    correlation_risk: float = 0.0  # 相关性风险
    
    # 个性化风险指标
    personalization_appropriateness: float = 0.0  # 个性化适当性
    suitability_score: float = 0.0  # 适当性评分
    
    # 风险等级
    risk_level: str = "MEDIUM"  # 风险等级 (LOW, MEDIUM, HIGH, CRITICAL)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComplianceCheckResult:
    """合规检查结果"""
    
    # 检查信息
    check_type: ComplianceCheckType
    check_timestamp: datetime = field(default_factory=datetime.now)
    check_duration_ms: float = 0.0
    
    # 检查结果
    passed: bool = True
    compliance_score: float = 1.0  # 合规评分 (0-1)
    compliance_level: ComplianceLevel = ComplianceLevel.LOW
    
    # 检查详情
    checks_performed: List[str] = field(default_factory=list)
    issues_found: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    # 合规标志
    compliance_flags: List[ComplianceFlag] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'check_type': self.check_type.value,
            'check_timestamp': self.check_timestamp.isoformat(),
            'check_duration_ms': self.check_duration_ms,
            'passed': self.passed,
            'compliance_score': self.compliance_score,
            'compliance_level': self.compliance_level.value,
            'checks_performed': self.checks_performed,
            'issues_found': self.issues_found,
            'recommendations': self.recommendations,
            'compliance_flags': [flag.to_dict() for flag in self.compliance_flags]
        }


@dataclass
class RiskAlert:
    """风险预警"""
    
    # 预警信息
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alert_timestamp: datetime = field(default_factory=datetime.now)
    alert_level: RiskAlertLevel = RiskAlertLevel.INFO
    
    # 预警内容
    title: str = ""
    description: str = ""
    alert_type: str = ""
    
    # 预警数据
    risk_metrics: Optional[AIStockRiskMetrics] = None
    affected_stocks: List[str] = field(default_factory=list)
    affected_strategies: List[str] = field(default_factory=list)
    
    # 预警状态
    status: str = "ACTIVE"  # ACTIVE, ACKNOWLEDGED, RESOLVED, DISMISSED
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'alert_timestamp': self.alert_timestamp.isoformat(),
            'alert_level': self.alert_level.value,
            'title': self.title,
            'description': self.description,
            'alert_type': self.alert_type,
            'risk_metrics': self.risk_metrics.to_dict() if self.risk_metrics else None,
            'affected_stocks': self.affected_stocks,
            'affected_strategies': self.affected_strategies,
            'status': self.status,
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'acknowledged_by': self.acknowledged_by,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'resolved_by': self.resolved_by,
            'resolution_notes': self.resolution_notes
        }


@dataclass
class RiskControlReport:
    """风险控制报告"""
    
    # 报告信息
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    report_timestamp: datetime = field(default_factory=datetime.now)
    report_type: str = ""
    report_period: Optional[Tuple[datetime, datetime]] = None
    
    # 风险评估结果
    risk_metrics: Optional[AIStockRiskMetrics] = None
    risk_level: str = "MEDIUM"
    
    # 合规检查结果
    compliance_results: List[ComplianceCheckResult] = field(default_factory=list)
    overall_compliance_score: float = 1.0
    
    # 预警信息
    alerts: List[RiskAlert] = field(default_factory=list)
    active_alerts_count: int = 0
    
    # 风险建议
    recommendations: List[str] = field(default_factory=list)
    risk_mitigation_actions: List[Dict[str, Any]] = field(default_factory=list)
    
    # 报告内容
    executive_summary: str = ""
    detailed_analysis: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'report_id': self.report_id,
            'report_timestamp': self.report_timestamp.isoformat(),
            'report_type': self.report_type,
            'report_period': [
                self.report_period[0].isoformat(),
                self.report_period[1].isoformat()
            ] if self.report_period else None,
            'risk_metrics': self.risk_metrics.to_dict() if self.risk_metrics else None,
            'risk_level': self.risk_level,
            'compliance_results': [result.to_dict() for result in self.compliance_results],
            'overall_compliance_score': self.overall_compliance_score,
            'alerts': [alert.to_dict() for alert in self.alerts],
            'active_alerts_count': self.active_alerts_count,
            'recommendations': self.recommendations,
            'risk_mitigation_actions': self.risk_mitigation_actions,
            'executive_summary': self.executive_summary,
            'detailed_analysis': self.detailed_analysis
        }


class AISelectionRiskControlService:
    """
    AI选股风险控制和合规检查服务
    
    专门为AI选股系统提供风险评估、合规检查、风险监控和报告功能
    """
    
    def __init__(self, 
                 database_service: Optional[DatabaseService] = None,
                 ai_selection_service: Optional[AISelectionIntegrationService] = None,
                 ai_backtest_service: Optional[AISelectionBacktestService] = None,
                 personalization_engine: Optional[PersonalizedStockSelectionEngine] = None,
                 indicator_service: Optional[EnhancedIndicatorService] = None,
                 risk_control_level: RiskControlLevel = RiskControlLevel.STANDARD):
        """
        初始化AI选股风险控制服务
        
        Args:
            database_service: 数据库服务
            ai_selection_service: AI选股集成服务
            ai_backtest_service: AI选股回测服务
            personalization_engine: 个性化引擎
            indicator_service: 指标计算服务
            risk_control_level: 风险控制级别
        """
        self._database_service = database_service
        self._ai_selection_service = ai_selection_service
        self._ai_backtest_service = ai_backtest_service
        self._personalization_engine = personalization_engine
        self._indicator_service = indicator_service
        self._risk_control_level = risk_control_level
        
        # 风险监控器
        self._risk_monitor = RiskMonitor()
        
        # 风险报告生成器
        self._report_generator = RiskReportGenerator()
        
        # 风险控制管理器
        self._risk_control_manager = RiskControlStrategy()
        
        # 风险历史记录
        self._risk_history: List[AIStockRiskMetrics] = []
        self._risk_history_lock = threading.Lock()
        
        # 合规检查历史
        self._compliance_history: List[ComplianceCheckResult] = []
        self._compliance_history_lock = threading.Lock()
        
        # 预警历史
        self._alerts_history: List[RiskAlert] = []
        self._alerts_history_lock = threading.Lock()
        
        # 报告历史
        self._reports_history: List[RiskControlReport] = []
        self._reports_history_lock = threading.Lock()
        
        # 线程池用于异步风险评估
        self._executor = ThreadPoolExecutor(
            max_workers=4, 
            thread_name_prefix="AI_Risk_Control"
        )
        
        # 风险控制配置
        self._risk_thresholds = self._initialize_risk_thresholds()
        
        # 合规检查配置
        self._compliance_config = self._initialize_compliance_config()
        
        logger.info("AI选股风险控制服务初始化完成")
    
    def _initialize_risk_thresholds(self) -> Dict[str, Any]:
        """初始化风险阈值配置"""
        # 基于风险控制级别设置不同的阈值
        if self._risk_control_level == RiskControlLevel.BASIC:
            return {
                'overall_risk_score': 0.7,
                'market_risk_score': 0.6,
                'liquidity_risk_score': 0.5,
                'concentration_risk_score': 0.6,
                'model_risk_score': 0.7,
                'overfitting_risk_score': 0.7,
                'bias_risk_score': 0.7,
                'data_quality_risk_score': 0.6,
                'portfolio_var': -0.1,
                'portfolio_cvar': -0.15,
                'maximum_drawdown': 0.2
            }
        elif self._risk_control_level == RiskControlLevel.STANDARD:
            return {
                'overall_risk_score': 0.6,
                'market_risk_score': 0.5,
                'liquidity_risk_score': 0.4,
                'concentration_risk_score': 0.5,
                'model_risk_score': 0.6,
                'overfitting_risk_score': 0.6,
                'bias_risk_score': 0.6,
                'data_quality_risk_score': 0.5,
                'portfolio_var': -0.08,
                'portfolio_cvar': -0.12,
                'maximum_drawdown': 0.15
            }
        elif self._risk_control_level == RiskControlLevel.ENHANCED:
            return {
                'overall_risk_score': 0.5,
                'market_risk_score': 0.4,
                'liquidity_risk_score': 0.3,
                'concentration_risk_score': 0.4,
                'model_risk_score': 0.5,
                'overfitting_risk_score': 0.5,
                'bias_risk_score': 0.5,
                'data_quality_risk_score': 0.4,
                'portfolio_var': -0.06,
                'portfolio_cvar': -0.09,
                'maximum_drawdown': 0.12
            }
        else:  # INSTITUTIONAL
            return {
                'overall_risk_score': 0.4,
                'market_risk_score': 0.3,
                'liquidity_risk_score': 0.2,
                'concentration_risk_score': 0.3,
                'model_risk_score': 0.4,
                'overfitting_risk_score': 0.4,
                'bias_risk_score': 0.4,
                'data_quality_risk_score': 0.3,
                'portfolio_var': -0.04,
                'portfolio_cvar': -0.06,
                'maximum_drawdown': 0.08
            }
    
    def _initialize_compliance_config(self) -> Dict[str, Any]:
        """初始化合规检查配置"""
        return {
            ComplianceCheckType.REGULATORY: {
                'enabled': True,
                'checks': [
                    'market_manipulation_check',
                    'insider_trading_check',
                    'disclosure_check',
                    'position_limit_check',
                    'liquidity_check'
                ],
                'min_compliance_score': 0.8
            },
            ComplianceCheckType.INTERNAL: {
                'enabled': True,
                'checks': [
                    'strategy_approval_check',
                    'risk_limit_check',
                    'position_concentration_check',
                    'investment_policy_check',
                    'client_suitability_check'
                ],
                'min_compliance_score': 0.85
            },
            ComplianceCheckType.OPERATIONAL: {
                'enabled': True,
                'checks': [
                    'data_quality_check',
                    'model_validation_check',
                    'performance_attribution_check',
                    'calculation_accuracy_check',
                    'system_reliability_check'
                ],
                'min_compliance_score': 0.9
            },
            ComplianceCheckType.ETHICAL: {
                'enabled': True,
                'checks': [
                    'bias_detection_check',
                    'fairness_check',
                    'transparency_check',
                    'explainability_check',
                    'stakeholder_interest_check'
                ],
                'min_compliance_score': 0.75
            }
        }
    
    def assess_risk(self,
                    user_id: str,
                    selection_criteria: StockSelectionCriteria,
                    strategy: SelectionStrategy,
                    selected_stocks: List[str],
                    assessment_type: RiskAssessmentType = RiskAssessmentType.PRE_SELECTION,
                    user_profile: Optional[InvestmentProfile] = None) -> AIStockRiskMetrics:
        """
        评估AI选股风险
        
        Args:
            user_id: 用户ID
            selection_criteria: 选股标准
            strategy: 选股策略
            selected_stocks: 选中的股票列表
            assessment_type: 评估类型
            user_profile: 用户画像
            
        Returns:
            AI选股风险指标
        """
        try:
            start_time = datetime.now()
            logger.info(f"开始风险评估 - 用户: {user_id}, 策略: {strategy.value}, 类型: {assessment_type.value}")
            
            # 创建基础风险指标
            risk_metrics = AIStockRiskMetrics()
            
            # 1. 市场风险评估
            market_risk_score = self._assess_market_risk(selected_stocks, selection_criteria)
            risk_metrics.market_risk_score = market_risk_score
            
            # 2. 流动性风险评估
            liquidity_risk_score = self._assess_liquidity_risk(selected_stocks, selection_criteria)
            risk_metrics.liquidity_risk_score = liquidity_risk_score
            
            # 3. 集中度风险评估
            concentration_risk_score = self._assess_concentration_risk(selected_stocks, selection_criteria)
            risk_metrics.concentration_risk_score = concentration_risk_score
            
            # 4. 模型风险评估
            model_risk_score = self._assess_model_risk(strategy, selection_criteria)
            risk_metrics.model_risk_score = model_risk_score
            
            # 5. 过拟合风险评估
            overfitting_risk_score = self._assess_overfitting_risk(strategy, selected_stocks)
            risk_metrics.overfitting_risk_score = overfitting_risk_score
            
            # 6. 偏见风险评估
            bias_risk_score = self._assess_bias_risk(selected_stocks, user_profile)
            risk_metrics.bias_risk_score = bias_risk_score
            
            # 7. 数据质量风险评估
            data_quality_risk_score = self._assess_data_quality_risk(selected_stocks, selection_criteria)
            risk_metrics.data_quality_risk_score = data_quality_risk_score
            
            # 8. 组合风险指标计算
            portfolio_var, portfolio_cvar = self._calculate_portfolio_var_cvar(selected_stocks)
            risk_metrics.portfolio_var = portfolio_var
            risk_metrics.portfolio_cvar = portfolio_cvar
            
            # 9. 最大回撤评估
            maximum_drawdown = self._calculate_maximum_drawdown(selected_stocks)
            risk_metrics.maximum_drawdown = maximum_drawdown
            
            # 10. 相关性风险评估
            correlation_risk = self._assess_correlation_risk(selected_stocks)
            risk_metrics.correlation_risk = correlation_risk
            
            # 11. 个性化适当性评估
            if user_profile:
                personalization_appropriateness = self._assess_personalization_appropriateness(
                    user_profile, selected_stocks
                )
                suitability_score = self._assess_suitability(user_profile, selection_criteria, strategy)
                risk_metrics.personalization_appropriateness = personalization_appropriateness
                risk_metrics.suitability_score = suitability_score
            
            # 计算总体风险评分
            risk_metrics.overall_risk_score = self._calculate_overall_risk_score(risk_metrics)
            
            # 确定风险等级
            risk_metrics.risk_level = self._determine_risk_level(risk_metrics.overall_risk_score)
            
            # 记录评估时间
            end_time = datetime.now()
            duration_ms = (end_time - start_time).total_seconds() * 1000
            logger.info(f"风险评估完成 - 用时: {duration_ms:.2f}ms")
            
            # 保存到历史记录
            with self._risk_history_lock:
                self._risk_history.append(risk_metrics)
                # 保留最近100条记录
                if len(self._risk_history) > 100:
                    self._risk_history.pop(0)
            
            return risk_metrics
            
        except Exception as e:
            logger.error(f"风险评估失败: {e}")
            logger.error(traceback.format_exc())
            # 返回默认风险指标
            return AIStockRiskMetrics()
    
    def _assess_market_risk(self, selected_stocks: List[str], 
                            selection_criteria: StockSelectionCriteria) -> float:
        """评估市场风险"""
        try:
            if not selected_stocks:
                return 0.5  # 默认中等风险
            
            # 获取市场风险数据
            market_data = self._get_market_risk_data(selected_stocks)
            
            # 计算市场风险指标
            volatility_risk = 0.0
            beta_risk = 0.0
            market_cap_risk = 0.0
            
            if market_data:
                # 波动率风险
                volatilities = [data.get('volatility', 0) for data in market_data]
                if volatilities:
                    avg_volatility = np.mean(volatilities)
                    volatility_risk = min(1.0, avg_volatility / 0.3)  # 标准化到0-1
                
                # Beta风险
                betas = [data.get('beta', 1.0) for data in market_data]
                if betas:
                    avg_beta = np.mean(betas)
                    beta_risk = min(1.0, abs(avg_beta - 1.0) / 0.5)  # 标准化到0-1
                
                # 市值风险
                market_caps = [data.get('market_cap', 0) for data in market_data]
                if market_caps:
                    small_cap_ratio = sum(1 for cap in market_caps if cap < 1e10) / len(market_caps)
                    market_cap_risk = small_cap_ratio  # 小市值股票比例越高，市场风险越大
            
            # 综合市场风险
            market_risk = (volatility_risk + beta_risk + market_cap_risk) / 3
            
            return market_risk
            
        except Exception as e:
            logger.error(f"评估市场风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _get_market_risk_data(self, selected_stocks: List[str]) -> List[Dict[str, Any]]:
        """获取市场风险数据"""
        try:
            if not self._database_service:
                return []
            
            # 获取股票市场数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, volatility, beta, market_cap
            FROM stock_market_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM stock_market_data WHERE symbol IN ({placeholders}))
            """
            
            results = self._database_service.execute_query(query, selected_stocks + selected_stocks)
            
            return [
                {
                    'symbol': row[0],
                    'volatility': row[1] if row[1] else 0.2,
                    'beta': row[2] if row[2] else 1.0,
                    'market_cap': row[3] if row[3] else 0
                }
                for row in results
            ] if results else []
            
        except Exception as e:
            logger.error(f"获取市场风险数据失败: {e}")
            return []
    
    def _assess_liquidity_risk(self, selected_stocks: List[str], 
                               selection_criteria: StockSelectionCriteria) -> float:
        """评估流动性风险"""
        try:
            if not selected_stocks:
                return 0.5  # 默认中等风险
            
            # 获取流动性数据
            liquidity_data = self._get_liquidity_data(selected_stocks)
            
            # 计算流动性风险指标
            avg_daily_volume_risk = 0.0
            bid_ask_spread_risk = 0.0
            market_impact_risk = 0.0
            
            if liquidity_data:
                # 日均成交量风险
                volumes = [data.get('avg_daily_volume', 0) for data in liquidity_data]
                if volumes:
                    min_volume = min(volumes)
                    avg_volume = np.mean(volumes)
                    volume_ratio = min_volume / avg_volume if avg_volume > 0 else 0
                    avg_daily_volume_risk = 1.0 - volume_ratio  # 成交量差异越大，流动性风险越高
                
                # 买卖价差风险
                spreads = [data.get('bid_ask_spread', 0) for data in liquidity_data]
                if spreads:
                    max_spread = max(spreads)
                    avg_spread = np.mean(spreads)
                    spread_ratio = max_spread / avg_spread if avg_spread > 0 else 1.0
                    bid_ask_spread_risk = min(1.0, spread_ratio - 1.0)
                
                # 市场冲击风险
                # 基于股票数量和平均成交量估算市场冲击风险
                market_impact_risk = min(1.0, len(selected_stocks) / 20)  # 股票数量越多，市场冲击风险越高
            
            # 综合流动性风险
            liquidity_risk = (avg_daily_volume_risk + bid_ask_spread_risk + market_impact_risk) / 3
            
            return liquidity_risk
            
        except Exception as e:
            logger.error(f"评估流动性风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _get_liquidity_data(self, selected_stocks: List[str]) -> List[Dict[str, Any]]:
        """获取流动性数据"""
        try:
            if not self._database_service:
                return []
            
            # 获取股票流动性数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, avg_daily_volume, bid_ask_spread
            FROM stock_liquidity_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM stock_liquidity_data WHERE symbol IN ({placeholders}))
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            return [
                {
                    'symbol': row[0],
                    'avg_daily_volume': row[1] if row[1] else 0,
                    'bid_ask_spread': row[2] if row[2] else 0.001
                }
                for row in results
            ] if results else []
            
        except Exception as e:
            logger.error(f"获取流动性数据失败: {e}")
            return []
    
    def _assess_concentration_risk(self, selected_stocks: List[str], 
                                   selection_criteria: StockSelectionCriteria) -> float:
        """评估集中度风险"""
        try:
            if not selected_stocks:
                return 0.5  # 默认中等风险
            
            # 计算行业集中度风险
            sector_data = self._get_sector_data(selected_stocks)
            
            # 计算集中度指标
            sector_concentration = 0.0
            single_stock_concentration = 0.0
            sector_count = len(sector_data) if sector_data else 0
            
            if sector_data:
                # 行业集中度
                sector_weights = [data.get('weight', 0) for data in sector_data]
                if sector_weights:
                    # 使用赫芬达尔指数(HHI)衡量集中度
                    sector_concentration = sum(weight ** 2 for weight in sector_weights)
                
                # 单只股票集中度
                if len(selected_stocks) > 0:
                    single_stock_concentration = 1.0 / len(selected_stocks)
            
            # 综合集中度风险
            concentration_risk = (sector_concentration * 0.7 + (1.0 - single_stock_concentration) * 0.3)
            
            return min(1.0, concentration_risk)
            
        except Exception as e:
            logger.error(f"评估集中度风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _get_sector_data(self, selected_stocks: List[str]) -> List[Dict[str, Any]]:
        """获取行业分布数据"""
        try:
            if not self._database_service:
                return []
            
            # 获取股票行业数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, sector, weight
            FROM stock_sector_data
            WHERE symbol IN ({placeholders})
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            # 按行业汇总权重
            sector_weights = {}
            for row in results:
                symbol, sector, weight = row[0], row[1], row[2] if row[2] else 0
                sector_weights[sector] = sector_weights.get(sector, 0) + weight
            
            # 转换为列表格式
            total_weight = sum(sector_weights.values())
            if total_weight > 0:
                # 归一化权重
                sector_data = [
                    {'sector': sector, 'weight': weight / total_weight}
                    for sector, weight in sector_weights.items()
                ]
                return sector_data
            else:
                return []
            
        except Exception as e:
            logger.error(f"获取行业分布数据失败: {e}")
            return []
    
    def _assess_model_risk(self, strategy: SelectionStrategy, 
                           selection_criteria: StockSelectionCriteria) -> float:
        """评估模型风险"""
        try:
            # 根据策略类型评估模型风险
            model_risk_scores = {
                SelectionStrategy.FUNDAMENTAL: 0.4,
                SelectionStrategy.TECHNICAL: 0.5,
                SelectionStrategy.MACRO: 0.6,
                SelectionStrategy.QUANTITATIVE: 0.7,
                SelectionStrategy.HYBRID: 0.5,
                SelectionStrategy.AI_ENHANCED: 0.6,
                SelectionStrategy.CUSTOM: 0.7
            }
            
            base_risk = model_risk_scores.get(strategy, 0.5)
            
            # 考虑选股标准的复杂性
            complexity_factor = self._calculate_criteria_complexity(selection_criteria)
            model_risk = base_risk * (0.5 + complexity_factor * 0.5)
            
            return min(1.0, model_risk)
            
        except Exception as e:
            logger.error(f"评估模型风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _calculate_criteria_complexity(self, selection_criteria: StockSelectionCriteria) -> float:
        """计算选股标准的复杂性"""
        try:
            # 基于指标数量和权重分布评估复杂性
            indicator_count = len(selection_criteria.indicators)
            weight_distribution = np.array(list(selection_criteria.weights.values()))
            
            # 标准化指标数量
            indicator_complexity = min(1.0, indicator_count / 10)
            
            # 计算权重分布的熵（权重越均匀，复杂性越高）
            if np.sum(weight_distribution) > 0:
                normalized_weights = weight_distribution / np.sum(weight_distribution)
                entropy = -np.sum([p * np.log(p) for p in normalized_weights if p > 0])
                max_entropy = np.log(len(normalized_weights))
                weight_complexity = entropy / max_entropy if max_entropy > 0 else 0
            else:
                weight_complexity = 0
            
            # 综合复杂性
            complexity = (indicator_complexity + weight_complexity) / 2
            
            return complexity
            
        except Exception as e:
            logger.error(f"计算选股标准复杂性失败: {e}")
            return 0.5  # 返回默认中等复杂性
    
    def _assess_overfitting_risk(self, strategy: SelectionStrategy, 
                                 selected_stocks: List[str]) -> float:
        """评估过拟合风险"""
        try:
            if not selected_stocks:
                return 0.5  # 默认中等风险
            
            # 样本数量与特征数量的比例
            # 假设特征数量约为策略相关参数数量
            feature_count = len(selected_stocks)  # 简化处理，使用股票数量作为特征数量
            sample_count = len(selected_stocks)
            
            ratio = sample_count / feature_count if feature_count > 0 else 0
            
            # 过拟合风险与样本/特征比例成反比
            if ratio >= 5:
                overfitting_risk = 0.2
            elif ratio >= 2:
                overfitting_risk = 0.4
            elif ratio >= 1:
                overfitting_risk = 0.6
            else:
                overfitting_risk = 0.8
            
            # 根据策略类型调整
            if strategy in [SelectionStrategy.QUANTITATIVE, SelectionStrategy.AI_ENHANCED]:
                overfitting_risk *= 1.2  # 这些策略更容易过拟合
            
            return min(1.0, overfitting_risk)
            
        except Exception as e:
            logger.error(f"评估过拟合风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _assess_bias_risk(self, selected_stocks: List[str], 
                          user_profile: Optional[InvestmentProfile]) -> float:
        """评估偏见风险"""
        try:
            if not selected_stocks:
                return 0.5  # 默认中等风险
            
            bias_indicators = []
            
            # 1. 行业偏见
            sector_data = self._get_sector_data(selected_stocks)
            if sector_data:
                sector_weights = [data.get('weight', 0) for data in sector_data]
                max_sector_weight = max(sector_weights) if sector_weights else 0
                sector_bias = max(0, max_sector_weight - 0.3)  # 超过30%认为是偏见
                bias_indicators.append(sector_bias)
            
            # 2. 市值偏见
            market_cap_data = self._get_market_cap_data(selected_stocks)
            if market_cap_data:
                market_caps = [data.get('market_cap', 0) for data in market_cap_data]
                small_cap_ratio = sum(1 for cap in market_caps if cap < 1e10) / len(market_caps)
                large_cap_ratio = sum(1 for cap in market_caps if cap > 1e11) / len(market_caps)
                
                # 过于偏向小盘或大盘都是偏见
                market_cap_bias = abs(small_cap_ratio - large_cap_ratio)
                bias_indicators.append(market_cap_bias)
            
            # 3. 个性化偏见（如果有用户画像）
            if user_profile:
                preference_bias = self._assess_preference_bias(selected_stocks, user_profile)
                bias_indicators.append(preference_bias)
            
            # 综合偏见风险
            if bias_indicators:
                bias_risk = np.mean(bias_indicators)
            else:
                bias_risk = 0.5
            
            return min(1.0, bias_risk)
            
        except Exception as e:
            logger.error(f"评估偏见风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _get_market_cap_data(self, selected_stocks: List[str]) -> List[Dict[str, Any]]:
        """获取市值数据"""
        try:
            if not self._database_service:
                return []
            
            # 获取股票市值数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, market_cap
            FROM stock_market_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM stock_market_data WHERE symbol IN ({placeholders}))
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            return [
                {
                    'symbol': row[0],
                    'market_cap': row[1] if row[1] else 0
                }
                for row in results
            ] if results else []
            
        except Exception as e:
            logger.error(f"获取市值数据失败: {e}")
            return []
    
    def _assess_preference_bias(self, selected_stocks: List[str], 
                               user_profile: InvestmentProfile) -> float:
        """评估偏好偏见"""
        try:
            # 基于用户画像评估选股结果的偏好偏见
            bias_score = 0.0
            
            # 1. 风格偏好偏见
            if user_profile.investment_style:
                style_based_selection = self._check_style_based_selection(selected_stocks, user_profile.investment_style)
                bias_score += style_based_selection * 0.4
            
            # 2. 风险偏好偏见
            if user_profile.risk_tolerance:
                risk_based_selection = self._check_risk_based_selection(selected_stocks, user_profile.risk_tolerance)
                bias_score += risk_based_selection * 0.3
            
            # 3. 行业偏好偏见
            if user_profile.preferred_sectors:
                sector_based_selection = self._check_sector_based_selection(selected_stocks, user_profile.preferred_sectors)
                bias_score += sector_based_selection * 0.3
            
            return min(1.0, bias_score)
            
        except Exception as e:
            logger.error(f"评估偏好偏见失败: {e}")
            return 0.5  # 返回默认中等偏见
    
    def _check_style_based_selection(self, selected_stocks: List[str], 
                                    investment_style: str) -> float:
        """检查基于风格的选股偏见"""
        try:
            # 获取股票风格数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, style
            FROM stock_style_data
            WHERE symbol IN ({placeholders})
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.5
            
            # 计算风格匹配度
            style_matches = sum(1 for row in results if row[1] == investment_style)
            style_match_ratio = style_matches / len(results)
            
            # 如果风格匹配度太高，可能存在偏见
            bias = min(1.0, style_match_ratio)
            
            return bias
            
        except Exception as e:
            logger.error(f"检查基于风格的选股偏见失败: {e}")
            return 0.5
    
    def _check_risk_based_selection(self, selected_stocks: List[str], 
                                   risk_tolerance: str) -> float:
        """检查基于风险的选股偏见"""
        try:
            # 获取股票风险数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, volatility, beta
            FROM stock_market_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM stock_market_data WHERE symbol IN ({placeholders}))
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.5
            
            # 基于风险偏好分类
            risk_profiles = {
                'CONSERVATIVE': {'max_volatility': 0.2, 'max_beta': 1.0},
                'MODERATE': {'max_volatility': 0.3, 'max_beta': 1.2},
                'AGGRESSIVE': {'max_volatility': 0.5, 'max_beta': 1.5}
            }
            
            profile = risk_profiles.get(risk_tolerance, risk_profiles['MODERATE'])
            
            # 计算风险匹配度
            matches = sum(1 for row in results 
                         if row[1] <= profile['max_volatility'] and row[2] <= profile['max_beta'])
            match_ratio = matches / len(results)
            
            # 如果风险匹配度太高，可能存在偏见
            bias = min(1.0, match_ratio)
            
            return bias
            
        except Exception as e:
            logger.error(f"检查基于风险的选股偏见失败: {e}")
            return 0.5
    
    def _check_sector_based_selection(self, selected_stocks: List[str], 
                                     preferred_sectors: List[str]) -> float:
        """检查基于行业的选股偏见"""
        try:
            if not preferred_sectors:
                return 0.5
            
            # 获取股票行业数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, sector
            FROM stock_sector_data
            WHERE symbol IN ({placeholders})
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.5
            
            # 计算偏好行业匹配度
            sector_matches = sum(1 for row in results if row[1] in preferred_sectors)
            sector_match_ratio = sector_matches / len(results)
            
            # 如果偏好行业匹配度太高，可能存在偏见
            bias = min(1.0, sector_match_ratio)
            
            return bias
            
        except Exception as e:
            logger.error(f"检查基于行业的选股偏见失败: {e}")
            return 0.5
    
    def _assess_data_quality_risk(self, selected_stocks: List[str], 
                                  selection_criteria: StockSelectionCriteria) -> float:
        """评估数据质量风险"""
        try:
            if not selected_stocks:
                return 0.5  # 默认中等风险
            
            # 检查数据完整性和质量
            data_quality_issues = 0
            total_checks = 0
            
            # 1. 检查价格数据完整性
            price_data_completeness = self._check_price_data_completeness(selected_stocks)
            data_quality_issues += (1.0 - price_data_completeness)
            total_checks += 1
            
            # 2. 检查基本面数据完整性
            fundamental_data_completeness = self._check_fundamental_data_completeness(selected_stocks)
            data_quality_issues += (1.0 - fundamental_data_completeness)
            total_checks += 1
            
            # 3. 检查技术指标数据完整性
            technical_data_completeness = self._check_technical_data_completeness(selected_stocks)
            data_quality_issues += (1.0 - technical_data_completeness)
            total_checks += 1
            
            # 4. 检查数据时效性
            data_timeliness = self._check_data_timeliness(selected_stocks)
            data_quality_issues += (1.0 - data_timeliness)
            total_checks += 1
            
            # 计算数据质量风险
            if total_checks > 0:
                data_quality_risk = data_quality_issues / total_checks
            else:
                data_quality_risk = 0.5
            
            return min(1.0, data_quality_risk)
            
        except Exception as e:
            logger.error(f"评估数据质量风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _check_price_data_completeness(self, selected_stocks: List[str]) -> float:
        """检查价格数据完整性"""
        try:
            if not self._database_service or not selected_stocks:
                return 0.5
            
            # 检查最近30天价格数据完整性
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, COUNT(*) as data_points
            FROM daily_price_data
            WHERE symbol IN ({placeholders})
            AND date BETWEEN ? AND ?
            GROUP BY symbol
            """
            
            results = self._database_service.execute_query(
                query, 
                selected_stocks + [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
            )
            
            if not results:
                return 0.3  # 没有数据，低完整度
            
            # 计算完整度
            expected_data_points = 30  # 期望30天的数据
            completeness_scores = []
            
            for row in results:
                symbol, data_points = row[0], row[1]
                completeness = min(1.0, data_points / expected_data_points)
                completeness_scores.append(completeness)
            
            return np.mean(completeness_scores)
            
        except Exception as e:
            logger.error(f"检查价格数据完整性失败: {e}")
            return 0.5
    
    def _check_fundamental_data_completeness(self, selected_stocks: List[str]) -> float:
        """检查基本面数据完整性"""
        try:
            if not self._database_service or not selected_stocks:
                return 0.5
            
            # 检查关键基本面指标
            key_indicators = ['pe_ratio', 'pb_ratio', 'roe', 'debt_to_equity', 'revenue_growth']
            
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, 
                   SUM(CASE WHEN pe_ratio IS NOT NULL THEN 1 ELSE 0 END) as pe_count,
                   SUM(CASE WHEN pb_ratio IS NOT NULL THEN 1 ELSE 0 END) as pb_count,
                   SUM(CASE WHEN roe IS NOT NULL THEN 1 ELSE 0 END) as roe_count,
                   SUM(CASE WHEN debt_to_equity IS NOT NULL THEN 1 ELSE 0 END) as debt_count,
                   SUM(CASE WHEN revenue_growth IS NOT NULL THEN 1 ELSE 0 END) as revenue_count
            FROM fundamental_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM fundamental_data WHERE symbol IN ({placeholders}))
            GROUP BY symbol
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.3  # 没有数据，低完整度
            
            # 计算完整度
            completeness_scores = []
            
            for row in results:
                _, pe_count, pb_count, roe_count, debt_count, revenue_count = row
                total_indicators = len(key_indicators)
                total_available = sum([pe_count, pb_count, roe_count, debt_count, revenue_count])
                completeness = min(1.0, total_available / (total_indicators * len(selected_stocks)))
                completeness_scores.append(completeness)
            
            return np.mean(completeness_scores)
            
        except Exception as e:
            logger.error(f"检查基本面数据完整性失败: {e}")
            return 0.5
    
    def _check_technical_data_completeness(self, selected_stocks: List[str]) -> float:
        """检查技术指标数据完整性"""
        try:
            if not self._database_service or not selected_stocks:
                return 0.5
            
            # 检查关键技术指标
            key_indicators = ['rsi', 'macd', 'bollinger_upper', 'bollinger_lower', 'moving_avg_20']
            
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol,
                   SUM(CASE WHEN rsi IS NOT NULL THEN 1 ELSE 0 END) as rsi_count,
                   SUM(CASE WHEN macd IS NOT NULL THEN 1 ELSE 0 END) as macd_count,
                   SUM(CASE WHEN bollinger_upper IS NOT NULL THEN 1 ELSE 0 END) as upper_count,
                   SUM(CASE WHEN bollinger_lower IS NOT NULL THEN 1 ELSE 0 END) as lower_count,
                   SUM(CASE WHEN moving_avg_20 IS NOT NULL THEN 1 ELSE 0 END) as ma_count
            FROM technical_indicators_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM technical_indicators_data WHERE symbol IN ({placeholders}))
            GROUP BY symbol
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.3  # 没有数据，低完整度
            
            # 计算完整度
            completeness_scores = []
            
            for row in results:
                _, rsi_count, macd_count, upper_count, lower_count, ma_count = row
                total_indicators = len(key_indicators)
                total_available = sum([rsi_count, macd_count, upper_count, lower_count, ma_count])
                completeness = min(1.0, total_available / (total_indicators * len(selected_stocks)))
                completeness_scores.append(completeness)
            
            return np.mean(completeness_scores)
            
        except Exception as e:
            logger.error(f"检查技术指标数据完整性失败: {e}")
            return 0.5
    
    def _check_data_timeliness(self, selected_stocks: List[str]) -> float:
        """检查数据时效性"""
        try:
            if not self._database_service or not selected_stocks:
                return 0.5
            
            # 检查数据最新更新日期
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, MAX(date) as latest_date
            FROM daily_price_data
            WHERE symbol IN ({placeholders})
            GROUP BY symbol
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.3  # 没有数据，低时效性
            
            # 计算时效性
            current_date = datetime.now().date()
            timeliness_scores = []
            
            for row in results:
                symbol, latest_date = row[0], row[1]
                if latest_date:
                    latest_date = datetime.strptime(latest_date, '%Y-%m-%d').date()
                    days_diff = (current_date - latest_date).days
                    # 超过5天的数据认为不够及时
                    timeliness = max(0, 1.0 - (days_diff / 5.0))
                    timeliness_scores.append(timeliness)
            
            return np.mean(timeliness_scores) if timeliness_scores else 0.5
            
        except Exception as e:
            logger.error(f"检查数据时效性失败: {e}")
            return 0.5
    
    def _calculate_portfolio_var_cvar(self, selected_stocks: List[str]) -> Tuple[float, float]:
        """计算组合VaR和条件VaR"""
        try:
            if not selected_stocks:
                return 0.0, 0.0
            
            # 获取历史收益率数据
            returns_data = self._get_historical_returns(selected_stocks)
            
            if not returns_data or len(returns_data) < 30:
                # 数据不足，返回默认值
                return -0.05, -0.07
            
            # 计算组合收益率（等权重）
            returns_df = pd.DataFrame(returns_data)
            portfolio_returns = returns_df.mean(axis=1)
            
            # 计算VaR (95%置信水平)
            var_95 = np.percentile(portfolio_returns, 5)
            
            # 计算条件VaR (CVaR)
            var_95_value = np.percentile(portfolio_returns, 5)
            cvar_95 = portfolio_returns[portfolio_returns <= var_95_value].mean()
            
            return var_95, cvar_95
            
        except Exception as e:
            logger.error(f"计算组合VaR和条件VaR失败: {e}")
            return -0.05, -0.07  # 返回默认值
    
    def _get_historical_returns(self, selected_stocks: List[str], 
                               days: int = 252) -> Dict[str, List[float]]:
        """获取历史收益率数据"""
        try:
            if not self._database_service or not selected_stocks:
                return {}
            
            # 获取最近N天的价格数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days * 2)  # 获取更多数据以计算收益率
            
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, date, close
            FROM daily_price_data
            WHERE symbol IN ({placeholders})
            AND date BETWEEN ? AND ?
            ORDER BY symbol, date
            """
            
            results = self._database_service.execute_query(
                query, 
                selected_stocks + [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
            )
            
            if not results:
                return {}
            
            # 转换为DataFrame
            df = pd.DataFrame(results, columns=['symbol', 'date', 'close'])
            df['date'] = pd.to_datetime(df['date'])
            
            # 计算收益率
            returns_data = {}
            for symbol in selected_stocks:
                symbol_data = df[df['symbol'] == symbol].sort_values('date')
                if len(symbol_data) > 1:
                    prices = symbol_data['close'].values
                    returns = np.diff(prices) / prices[:-1]
                    # 只取最近N天的收益率
                    returns_data[symbol] = returns[-days:].tolist()
            
            return returns_data
            
        except Exception as e:
            logger.error(f"获取历史收益率数据失败: {e}")
            return {}
    
    def _calculate_maximum_drawdown(self, selected_stocks: List[str]) -> float:
        """计算最大回撤"""
        try:
            if not selected_stocks:
                return 0.0
            
            # 获取历史价格数据
            prices_data = self._get_historical_prices(selected_stocks)
            
            if not prices_data:
                return 0.0
            
            # 计算组合价格（等权重）
            prices_df = pd.DataFrame(prices_data)
            portfolio_prices = prices_df.mean(axis=1)
            
            # 计算最大回撤
            cumulative = (1 + portfolio_prices.pct_change()).cumprod()
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = abs(drawdown.min())
            
            return max_drawdown
            
        except Exception as e:
            logger.error(f"计算最大回撤失败: {e}")
            return 0.1  # 返回默认值
    
    def _get_historical_prices(self, selected_stocks: List[str], 
                               days: int = 252) -> Dict[str, List[float]]:
        """获取历史价格数据"""
        try:
            if not self._database_service or not selected_stocks:
                return {}
            
            # 获取最近N天的价格数据
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days * 2)
            
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, date, close
            FROM daily_price_data
            WHERE symbol IN ({placeholders})
            AND date BETWEEN ? AND ?
            ORDER BY symbol, date
            """
            
            results = self._database_service.execute_query(
                query, 
                selected_stocks + [start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]
            )
            
            if not results:
                return {}
            
            # 转换为DataFrame
            df = pd.DataFrame(results, columns=['symbol', 'date', 'close'])
            df['date'] = pd.to_datetime(df['date'])
            
            # 转换为字典格式
            prices_data = {}
            for symbol in selected_stocks:
                symbol_data = df[df['symbol'] == symbol].sort_values('date')
                if len(symbol_data) > 0:
                    prices_data[symbol] = symbol_data['close'].tolist()
            
            return prices_data
            
        except Exception as e:
            logger.error(f"获取历史价格数据失败: {e}")
            return {}
    
    def _assess_correlation_risk(self, selected_stocks: List[str]) -> float:
        """评估相关性风险"""
        try:
            if not selected_stocks or len(selected_stocks) < 2:
                return 0.0
            
            # 获取历史收益率数据
            returns_data = self._get_historical_returns(selected_stocks)
            
            if not returns_data or len(returns_data) < 2:
                return 0.5  # 数据不足，返回中等风险
            
            # 计算相关性矩阵
            returns_df = pd.DataFrame(returns_data)
            correlation_matrix = returns_df.corr()
            
            # 计算平均相关性
            # 去除对角线元素
            mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
            correlations = correlation_matrix.where(mask).stack().values
            
            if len(correlations) == 0:
                return 0.5
            
            avg_correlation = np.mean(np.abs(correlations))
            
            # 相关性风险与平均相关性成正比
            return min(1.0, avg_correlation)
            
        except Exception as e:
            logger.error(f"评估相关性风险失败: {e}")
            return 0.5  # 返回默认中等风险
    
    def _assess_personalization_appropriateness(self, user_profile: InvestmentProfile, 
                                                selected_stocks: List[str]) -> float:
        """评估个性化适当性"""
        try:
            if not user_profile or not selected_stocks:
                return 0.5
            
            # 1. 风格适当性
            style_appropriateness = self._assess_style_appropriateness(user_profile, selected_stocks)
            
            # 2. 风险适当性
            risk_appropriateness = self._assess_risk_appropriateness(user_profile, selected_stocks)
            
            # 3. 行业适当性
            sector_appropriateness = self._assess_sector_appropriateness(user_profile, selected_stocks)
            
            # 4. 市值适当性
            market_cap_appropriateness = self._assess_market_cap_appropriateness(user_profile, selected_stocks)
            
            # 综合适当性
            appropriateness = (
                style_appropriateness * 0.3 +
                risk_appropriateness * 0.3 +
                sector_appropriateness * 0.2 +
                market_cap_appropriateness * 0.2
            )
            
            return appropriateness
            
        except Exception as e:
            logger.error(f"评估个性化适当性失败: {e}")
            return 0.5  # 返回默认中等适当性
    
    def _assess_style_appropriateness(self, user_profile: InvestmentProfile, 
                                     selected_stocks: List[str]) -> float:
        """评估风格适当性"""
        try:
            if not user_profile.investment_style:
                return 0.5
            
            # 获取股票风格数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, style
            FROM stock_style_data
            WHERE symbol IN ({placeholders})
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.5
            
            # 计算风格匹配度
            style_matches = sum(1 for row in results if row[1] == user_profile.investment_style)
            style_match_ratio = style_matches / len(results)
            
            # 适当的匹配度应该在0.6-0.8之间
            if 0.6 <= style_match_ratio <= 0.8:
                return 1.0
            elif style_match_ratio < 0.3:
                return 0.3  # 匹配度过低
            elif style_match_ratio > 0.9:
                return 0.5  # 匹配度过高，可能存在偏见
            else:
                return style_match_ratio
            
        except Exception as e:
            logger.error(f"评估风格适当性失败: {e}")
            return 0.5
    
    def _assess_risk_appropriateness(self, user_profile: InvestmentProfile, 
                                    selected_stocks: List[str]) -> float:
        """评估风险适当性"""
        try:
            if not user_profile.risk_tolerance:
                return 0.5
            
            # 获取股票风险数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, volatility, beta
            FROM stock_market_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM stock_market_data WHERE symbol IN ({placeholders}))
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.5
            
            # 定义风险偏好对应的风险参数
            risk_profiles = {
                'CONSERVATIVE': {'max_volatility': 0.2, 'max_beta': 1.0},
                'MODERATE': {'max_volatility': 0.3, 'max_beta': 1.2},
                'AGGRESSIVE': {'max_volatility': 0.5, 'max_beta': 1.5}
            }
            
            profile = risk_profiles.get(user_profile.risk_tolerance, risk_profiles['MODERATE'])
            
            # 计算风险适当性
            appropriate_stocks = sum(1 for row in results 
                                   if row[1] <= profile['max_volatility'] and row[2] <= profile['max_beta'])
            appropriateness = appropriate_stocks / len(results)
            
            return appropriateness
            
        except Exception as e:
            logger.error(f"评估风险适当性失败: {e}")
            return 0.5
    
    def _assess_sector_appropriateness(self, user_profile: InvestmentProfile, 
                                      selected_stocks: List[str]) -> float:
        """评估行业适当性"""
        try:
            if not user_profile.preferred_sectors:
                return 0.5
            
            # 获取股票行业数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, sector
            FROM stock_sector_data
            WHERE symbol IN ({placeholders})
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.5
            
            # 计算行业匹配度
            sector_matches = sum(1 for row in results if row[1] in user_profile.preferred_sectors)
            sector_match_ratio = sector_matches / len(results)
            
            # 适当的匹配度应该在0.4-0.7之间
            if 0.4 <= sector_match_ratio <= 0.7:
                return 1.0
            elif sector_match_ratio < 0.2:
                return 0.3  # 匹配度过低
            elif sector_match_ratio > 0.8:
                return 0.5  # 匹配度过高，可能存在偏见
            else:
                return sector_match_ratio / 0.7  # 标准化到0-1
                
        except Exception as e:
            logger.error(f"评估行业适当性失败: {e}")
            return 0.5
    
    def _assess_market_cap_appropriateness(self, user_profile: InvestmentProfile, 
                                          selected_stocks: List[str]) -> float:
        """评估市值适当性"""
        try:
            # 获取股票市值数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, market_cap
            FROM stock_market_data
            WHERE symbol IN ({placeholders})
            AND date = (SELECT MAX(date) FROM stock_market_data WHERE symbol IN ({placeholders}))
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            if not results:
                return 0.5
            
            # 分类股票
            large_cap = sum(1 for row in results if row[1] and row[1] > 1e11)
            mid_cap = sum(1 for row in results if row[1] and 1e10 <= row[1] <= 1e11)
            small_cap = sum(1 for row in results if row[1] and row[1] < 1e10)
            
            total_stocks = len(results)
            large_cap_ratio = large_cap / total_stocks
            mid_cap_ratio = mid_cap / total_stocks
            small_cap_ratio = small_cap / total_stocks
            
            # 根据用户偏好计算适当性
            # 这里简化处理，假设用户偏好平衡配置
            target_ratios = {'large': 0.5, 'mid': 0.3, 'small': 0.2}
            
            # 计算偏差
            large_deviation = abs(large_cap_ratio - target_ratios['large'])
            mid_deviation = abs(mid_cap_ratio - target_ratios['mid'])
            small_deviation = abs(small_cap_ratio - target_ratios['small'])
            
            avg_deviation = (large_deviation + mid_deviation + small_deviation) / 3
            
            # 适当性与偏差成反比
            appropriateness = max(0, 1.0 - avg_deviation * 2)
            
            return appropriateness
            
        except Exception as e:
            logger.error(f"评估市值适当性失败: {e}")
            return 0.5
    
    def _assess_suitability(self, user_profile: InvestmentProfile, 
                           selection_criteria: StockSelectionCriteria,
                           strategy: SelectionStrategy) -> float:
        """评估适当性"""
        try:
            if not user_profile:
                return 0.5
            
            suitability_factors = []
            
            # 1. 风险承受力与策略风险匹配
            risk_match = self._check_risk_tolerance_match(user_profile, strategy)
            suitability_factors.append(risk_match)
            
            # 2. 投资经验与策略复杂度匹配
            experience_match = self._check_experience_match(user_profile, strategy)
            suitability_factors.append(experience_match)
            
            # 3. 投资目标与策略收益预期匹配
            goal_match = self._check_investment_goal_match(user_profile, selection_criteria)
            suitability_factors.append(goal_match)
            
            # 综合适当性
            suitability = np.mean(suitability_factors) if suitability_factors else 0.5
            
            return suitability
            
        except Exception as e:
            logger.error(f"评估适当性失败: {e}")
            return 0.5  # 返回默认中等适当性
    
    def _check_risk_tolerance_match(self, user_profile: InvestmentProfile, 
                                   strategy: SelectionStrategy) -> float:
        """检查风险承受力与策略匹配"""
        try:
            # 定义策略风险等级
            strategy_risk_levels = {
                SelectionStrategy.FUNDAMENTAL: 0.4,
                SelectionStrategy.TECHNICAL: 0.5,
                SelectionStrategy.MACRO: 0.6,
                SelectionStrategy.QUANTITATIVE: 0.7,
                SelectionStrategy.HYBRID: 0.5,
                SelectionStrategy.AI_ENHANCED: 0.6,
                SelectionStrategy.CUSTOM: 0.7
            }
            
            strategy_risk = strategy_risk_levels.get(strategy, 0.5)
            
            # 定义用户风险承受能力数值
            risk_tolerance_values = {
                'CONSERVATIVE': 0.3,
                'MODERATE': 0.5,
                'AGGRESSIVE': 0.7
            }
            
            user_risk = risk_tolerance_values.get(user_profile.risk_tolerance, 0.5)
            
            # 计算匹配度
            risk_diff = abs(strategy_risk - user_risk)
            match_score = max(0, 1.0 - risk_diff * 2)
            
            return match_score
            
        except Exception as e:
            logger.error(f"检查风险承受力与策略匹配失败: {e}")
            return 0.5
    
    def _check_experience_match(self, user_profile: InvestmentProfile, 
                               strategy: SelectionStrategy) -> float:
        """检查投资经验与策略复杂度匹配"""
        try:
            if not user_profile.investment_experience:
                return 0.5
            
            # 定义策略复杂度等级
            strategy_complexity_levels = {
                SelectionStrategy.FUNDAMENTAL: 0.3,
                SelectionStrategy.TECHNICAL: 0.4,
                SelectionStrategy.MACRO: 0.5,
                SelectionStrategy.QUANTITATIVE: 0.7,
                SelectionStrategy.HYBRID: 0.6,
                SelectionStrategy.AI_ENHANCED: 0.6,
                SelectionStrategy.CUSTOM: 0.7
            }
            
            strategy_complexity = strategy_complexity_levels.get(strategy, 0.5)
            
            # 定义投资经验等级
            experience_levels = {
                InvestmentExperience.BEGINNER: 0.2,
                InvestmentExperience.INTERMEDIATE: 0.5,
                InvestmentExperience.ADVANCED: 0.8,
                InvestmentExperience.EXPERT: 1.0
            }
            
            user_experience = experience_levels.get(user_profile.investment_experience, 0.5)
            
            # 计算匹配度
            complexity_diff = strategy_complexity - user_experience
            if complexity_diff <= 0:
                match_score = 1.0  # 用户经验足够
            else:
                match_score = max(0, 1.0 - complexity_diff * 2)
            
            return match_score
            
        except Exception as e:
            logger.error(f"检查投资经验与策略复杂度匹配失败: {e}")
            return 0.5
    
    def _check_investment_goal_match(self, user_profile: InvestmentProfile, 
                                    selection_criteria: StockSelectionCriteria) -> float:
        """检查投资目标与选股标准匹配"""
        try:
            if not user_profile.investment_goals:
                return 0.5
            
            # 这里简化处理，假设选股标准的目标是增长
            criteria_goal = 'GROWTH'  # 默认目标
            
            # 定义目标匹配度
            goal_compatibility = {
                'GROWTH': {
                    'CAPITAL_PRESERVATION': 0.3,
                    'INCOME': 0.4,
                    'BALANCED_GROWTH': 0.7,
                    'AGGRESSIVE_GROWTH': 0.9,
                    'SPECULATION': 0.8
                },
                'INCOME': {
                    'CAPITAL_PRESERVATION': 0.8,
                    'INCOME': 0.9,
                    'BALANCED_GROWTH': 0.7,
                    'AGGRESSIVE_GROWTH': 0.4,
                    'SPECULATION': 0.3
                },
                'BALANCED': {
                    'CAPITAL_PRESERVATION': 0.6,
                    'INCOME': 0.8,
                    'BALANCED_GROWTH': 0.9,
                    'AGGRESSIVE_GROWTH': 0.6,
                    'SPECULATION': 0.5
                }
            }
            
            # 计算目标匹配度
            if criteria_goal in goal_compatibility and user_goal in goal_compatibility[criteria_goal]:
                match_score = goal_compatibility[criteria_goal][user_goal]
            else:
                match_score = 0.5
                
            return match_score
            
        except Exception as e:
            logger.error(f"检查投资目标与选股标准匹配失败: {e}")
            return 0.5
    
    def check_compliance(self,
                        selected_stocks: List[str],
                        regulations: Optional[List[str]] = None,
                        check_types: Optional[List[ComplianceCheckType]] = None) -> ComplianceCheckResult:
        """
        检查AI选股结果的合规性
        
        Args:
            selected_stocks: 选中的股票列表
            regulations: 监管规定列表
            check_types: 合规检查类型列表
            
        Returns:
            合规检查结果
        """
        try:
            start_time = datetime.now()
            logger.info(f"开始合规检查 - 股票数量: {len(selected_stocks)}")
            
            # 默认检查所有类型
            if check_types is None:
                check_types = list(ComplianceCheckType)
            
            # 默认监管规定
            if regulations is None:
                regulations = [
                    'market_manipulation_regulation',
                    'insider_trading_regulation', 
                    'disclosure_requirements',
                    'position_limits',
                    'liquidity_requirements'
                ]
            
            compliance_result = ComplianceCheckResult(
                check_type=ComplianceCheckType.REGULATORY,  # 主检查类型
                checks_performed=[],
                issues_found=[],
                recommendations=[],
                compliance_flags=[]
            )
            
            total_checks = 0
            passed_checks = 0
            
            # 执行各类合规检查
            for check_type in check_types:
                if check_type not in self._compliance_config or not self._compliance_config[check_type]['enabled']:
                    continue
                
                type_config = self._compliance_config[check_type]
                checks = type_config['checks']
                
                logger.info(f"执行 {check_type.value} 合规检查...")
                
                for check_name in checks:
                    total_checks += 1
                    check_result = self._execute_compliance_check(check_name, selected_stocks, regulations)
                    
                    if check_result['passed']:
                        passed_checks += 1
                        logger.info(f"  {check_name}: 通过")
                    else:
                        logger.warning(f"  ❌ {check_name}: 失败 - {check_result['issue']}")
                        compliance_result.issues_found.append({
                            'check_name': check_name,
                            'issue': check_result['issue'],
                            'severity': check_result.get('severity', 'medium'),
                            'affected_stocks': check_result.get('affected_stocks', [])
                        })
                    
                    compliance_result.checks_performed.append(check_name)
            
            # 计算合规评分
            if total_checks > 0:
                compliance_score = passed_checks / total_checks
            else:
                compliance_score = 1.0
            
            compliance_result.compliance_score = compliance_score
            compliance_result.passed = compliance_score >= type_config.get('min_compliance_score', 0.8)
            
            # 确定合规等级
            if compliance_score >= 0.95:
                compliance_result.compliance_level = ComplianceLevel.HIGH
            elif compliance_score >= 0.85:
                compliance_result.compliance_level = ComplianceLevel.MEDIUM
            elif compliance_score >= 0.70:
                compliance_result.compliance_level = ComplianceLevel.LOW
            else:
                compliance_result.compliance_level = ComplianceLevel.CRITICAL
            
            # 生成合规建议
            if not compliance_result.passed:
                compliance_result.recommendations = self._generate_compliance_recommendations(
                    compliance_result.issues_found
                )
            
            # 计算检查耗时
            end_time = datetime.now()
            compliance_result.check_duration_ms = (end_time - start_time).total_seconds() * 1000
            
            # 记录合规检查历史
            with self._compliance_history_lock:
                self._compliance_history.append(compliance_result)
                # 保持历史记录在合理范围内
                if len(self._compliance_history) > 1000:
                    self._compliance_history = self._compliance_history[-1000:]
            
            logger.info(f"合规检查完成 - 评分: {compliance_score:.3f}, 通过率: {passed_checks}/{total_checks}")
            
            return compliance_result
            
        except Exception as e:
            logger.error(f"合规检查失败: {e}")
            logger.error(traceback.format_exc())
            
            # 返回失败结果
            return ComplianceCheckResult(
                check_type=ComplianceCheckType.REGULATORY,
                passed=False,
                compliance_score=0.0,
                compliance_level=ComplianceLevel.CRITICAL,
                issues_found=[{'check_name': 'system_error', 'issue': str(e), 'severity': 'critical'}],
                recommendations=['系统错误，请联系技术支持']
            )
    
    def _execute_compliance_check(self, check_name: str, selected_stocks: List[str], 
                                 regulations: List[str]) -> Dict[str, Any]:
        """
        执行具体的合规检查
        
        Args:
            check_name: 检查名称
            selected_stocks: 选中的股票列表
            regulations: 监管规定列表
            
        Returns:
            检查结果字典
        """
        try:
            # 根据检查名称执行相应的检查
            if check_name == 'market_manipulation_check':
                return self._check_market_manipulation(selected_stocks)
            elif check_name == 'insider_trading_check':
                return self._check_insider_trading(selected_stocks)
            elif check_name == 'disclosure_check':
                return self._check_disclosure_compliance(selected_stocks)
            elif check_name == 'position_limit_check':
                return self._check_position_limits(selected_stocks)
            elif check_name == 'liquidity_check':
                return self._check_liquidity_requirements(selected_stocks)
            elif check_name == 'strategy_approval_check':
                return self._check_strategy_approval(selected_stocks)
            elif check_name == 'risk_limit_check':
                return self._check_risk_limits(selected_stocks)
            elif check_name == 'position_concentration_check':
                return self._check_position_concentration(selected_stocks)
            elif check_name == 'investment_policy_check':
                return self._check_investment_policy(selected_stocks)
            elif check_name == 'client_suitability_check':
                return self._check_client_suitability(selected_stocks)
            elif check_name == 'data_quality_check':
                return self._check_data_quality_compliance(selected_stocks)
            elif check_name == 'model_validation_check':
                return self._check_model_validation(selected_stocks)
            elif check_name == 'performance_attribution_check':
                return self._check_performance_attribution(selected_stocks)
            elif check_name == 'calculation_accuracy_check':
                return self._check_calculation_accuracy(selected_stocks)
            elif check_name == 'system_reliability_check':
                return self._check_system_reliability(selected_stocks)
            elif check_name == 'bias_detection_check':
                return self._check_bias_detection(selected_stocks)
            elif check_name == 'fairness_check':
                return self._check_fairness(selected_stocks)
            elif check_name == 'transparency_check':
                return self._check_transparency(selected_stocks)
            elif check_name == 'explainability_check':
                return self._check_explainability(selected_stocks)
            elif check_name == 'stakeholder_interest_check':
                return self._check_stakeholder_interest(selected_stocks)
            else:
                # 未知的检查，默认通过
                return {
                    'passed': True,
                    'issue': None,
                    'severity': 'low',
                    'affected_stocks': []
                }
                
        except Exception as e:
            logger.error(f"执行合规检查 {check_name} 失败: {e}")
            return {
                'passed': False,
                'issue': f"检查执行失败: {str(e)}",
                'severity': 'medium',
                'affected_stocks': selected_stocks
            }
    
    def _check_market_manipulation(self, selected_stocks: List[str]) -> Dict[str, Any]:
        """检查市场操纵风险"""
        try:
            if not selected_stocks:
                return {'passed': True, 'issue': None, 'severity': 'low', 'affected_stocks': []}
            
            # 检查是否存在价格操纵迹象
            # 1. 检查异常交易量
            volume_anomalies = self._detect_volume_anomalies(selected_stocks)
            
            # 2. 检查异常价格波动
            price_anomalies = self._detect_price_anomalies(selected_stocks)
            
            # 3. 检查关联账户交易模式
            correlation_anomalies = self._detect_correlation_anomalies(selected_stocks)
            
            issues = []
            affected_stocks = []
            
            if volume_anomalies['detected']:
                issues.append(f"检测到异常交易量: {volume_anomalies['details']}")
                affected_stocks.extend(volume_anomalies['stocks'])
            
            if price_anomalies['detected']:
                issues.append(f"检测到异常价格波动: {price_anomalies['details']}")
                affected_stocks.extend(price_anomalies['stocks'])
            
            if correlation_anomalies['detected']:
                issues.append(f"检测到异常相关性模式: {correlation_anomalies['details']}")
            
            passed = len(issues) == 0
            severity = 'high' if len(issues) > 2 else 'medium' if len(issues) > 0 else 'low'
            
            return {
                'passed': passed,
                'issue': '; '.join(issues) if issues else None,
                'severity': severity,
                'affected_stocks': list(set(affected_stocks))
            }
            
        except Exception as e:
            logger.error(f"检查市场操纵风险失败: {e}")
            return {
                'passed': False,
                'issue': f"检查执行错误: {str(e)}",
                'severity': 'medium',
                'affected_stocks': selected_stocks
            }
    
    def _detect_volume_anomalies(self, selected_stocks: List[str]) -> Dict[str, Any]:
        """检测异常交易量"""
        try:
            if not self._database_service or not selected_stocks:
                return {'detected': False, 'stocks': [], 'details': ''}
            
            # 获取近期交易量数据
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, AVG(volume) as avg_volume, STDDEV(volume) as volume_std
            FROM daily_trading_data
            WHERE symbol IN ({placeholders})
            AND date >= date('now', '-30 days')
            GROUP BY symbol
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            anomalies = []
            anomaly_stocks = []
            
            for row in results:
                symbol, avg_volume, volume_std = row[0], row[1], row[2]
                if volume_std and volume_std > 0:
                    # 检查最近几天的交易量是否异常高
                    recent_query = f"""
                    SELECT volume FROM daily_trading_data
                    WHERE symbol = ? AND date >= date('now', '-7 days')
                    ORDER BY date DESC LIMIT 5
                    """
                    
                    recent_data = self._database_service.execute_query(recent_query, [symbol])
                    
                    if recent_data:
                        recent_volumes = [row[0] for row in recent_data]
                        max_recent = max(recent_volumes)
                        
                        # 如果最近最大交易量超过平均值3个标准差
                        if max_recent > avg_volume + 3 * volume_std:
                            anomalies.append(f"{symbol}: 最近交易量异常高 ({max_recent:.0f} vs 平均 {avg_volume:.0f})")
                            anomaly_stocks.append(symbol)
            
            return {
                'detected': len(anomalies) > 0,
                'stocks': anomaly_stocks,
                'details': '; '.join(anomalies)
            }
            
        except Exception as e:
            logger.error(f"检测异常交易量失败: {e}")
            return {'detected': False, 'stocks': [], 'details': ''}
    
    def _detect_price_anomalies(self, selected_stocks: List[str]) -> Dict[str, Any]:
        """检测异常价格波动"""
        try:
            if not self._database_service or not selected_stocks:
                return {'detected': False, 'stocks': [], 'details': ''}
            
            # 检查日收益率异常
            placeholders = ','.join(['?' for _ in selected_stocks])
            query = f"""
            SELECT symbol, date, close, LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close
            FROM daily_price_data
            WHERE symbol IN ({placeholders})
            AND date >= date('now', '-30 days')
            ORDER BY symbol, date
            """
            
            results = self._database_service.execute_query(query, selected_stocks)
            
            anomalies = []
            anomaly_stocks = []
            
            daily_returns = defaultdict(list)
            
            for row in results:
                symbol, date, close, prev_close = row[0], row[1], row[2], row[3]
                if prev_close and prev_close != 0:
                    daily_return = (close - prev_close) / prev_close
                    daily_returns[symbol].append(daily_return)
            
            # 检查每个股票的收益率分布
            for symbol, returns in daily_returns.items():
                if len(returns) >= 10:
                    mean_return = np.mean(returns)
                    std_return = np.std(returns)
                    
                    # 检查极端收益率
                    extreme_returns = [r for r in returns if abs(r - mean_return) > 3 * std_return]
                    
                    if len(extreme_returns) > len(returns) * 0.1:  # 超过10%的极端值
                        anomalies.append(f"{symbol}: 存在异常价格波动 ({len(extreme_returns)}/{len(returns)} 个极端值)")
                        anomaly_stocks.append(symbol)
            
            return {
                'detected': len(anomalies) > 0,
                'stocks': anomaly_stocks,
                'details': '; '.join(anomalies)
            }
            
        except Exception as e:
            logger.error(f"检测异常价格波动失败: {e}")
            return {'detected': False, 'stocks': [], 'details': ''}
    
    def _detect_correlation_anomalies(self, selected_stocks: List[str]) -> Dict[str, Any]:
        """检测关联账户交易模式"""
        try:
            if len(selected_stocks) < 2:
                return {'detected': False, 'stocks': [], 'details': ''}
            
            # 检查股票间的异常相关性
            returns_data = self._get_historical_returns(selected_stocks, days=30)
            
            if not returns_data or len(returns_data) < 2:
                return {'detected': False, 'stocks': [], 'details': ''}
            
            returns_df = pd.DataFrame(returns_data)
            correlation_matrix = returns_df.corr()
            
            cols = correlation_matrix.columns
            corr_values = correlation_matrix.values
            n = len(cols)
            
            i_idx, j_idx = np.triu_indices(n, k=1)
            high_corr_mask = np.abs(corr_values[i_idx, j_idx]) > 0.9
            
            high_correlations = []
            for ii, jj, mask in zip(i_idx, j_idx, high_corr_mask):
                if mask:
                    high_correlations.append(f"{cols[ii]}-{cols[jj]}: {corr_values[ii, jj]:.3f}")
            
            detected = len(high_correlations) > len(selected_stocks) * 0.3  # 超过30%的股票对有高相关性
            
            return {
                'detected': detected,
                'stocks': selected_stocks if detected else [],
                'details': '; '.join(high_correlations) if high_correlations else ''
            }
            
        except Exception as e:
            logger.error(f"检测关联账户交易模式失败: {e}")
            return {'detected': False, 'stocks': [], 'details': ''}

    def generate_risk_mitigation_recommendations(self,
                                               risk_metrics: AIStockRiskMetrics,
                                               selected_stocks: List[str],
                                               selection_criteria: Optional[StockSelectionCriteria] = None,
                                               investment_profile: Optional[InvestmentProfile] = None) -> List[Dict[str, Any]]:
        """
        生成风险缓解建议

        Args:
            risk_metrics: 风险评估结果
            selected_stocks: 选中的股票列表
            selection_criteria: 选股标准（可选）
            investment_profile: 投资画像（可选）

        Returns:
            风险缓解建议列表
        """
        try:
            start_time = datetime.now()
            logger.info(f"开始生成风险缓解建议 - 股票数量: {len(selected_stocks)}")

            recommendations = []

            # 基于总体风险评分生成建议
            if risk_metrics.overall_risk_score > 0.7:
                recommendations.append({
                    'category': 'overall_risk',
                    'priority': 'high',
                    'title': '总体风险过高',
                    'description': '当前投资组合总体风险评分过高，建议采取综合性风险缓解措施',
                    'actions': [
                        '降低单只股票仓位',
                        '增加股票数量，分散投资',
                        '考虑引入风险对冲工具',
                        '重新评估选股标准'
                    ],
                    'expected_risk_reduction': 0.3
                })

            # 基于市场风险生成建议
            if risk_metrics.market_risk_score > 0.6:
                recommendations.append({
                    'category': 'market_risk',
                    'priority': 'medium',
                    'title': '市场风险偏高',
                    'description': '投资组合对市场波动较为敏感，建议采取市场风险缓解措施',
                    'actions': [
                        '增加防御性股票配置',
                        '考虑市场中性策略',
                        '使用指数期权进行对冲',
                        '降低股票仓位比例'
                    ],
                    'expected_risk_reduction': 0.25
                })

            # 基于流动性风险生成建议
            if risk_metrics.liquidity_risk_score > 0.5:
                recommendations.append({
                    'category': 'liquidity_risk',
                    'priority': 'high',
                    'title': '流动性风险较高',
                    'description': '投资组合包含流动性较差的股票，存在退出困难风险',
                    'actions': [
                        '减少小市值股票配置',
                        '选择流动性更好的股票',
                        '预留更多现金缓冲',
                        '建立分批退出机制'
                    ],
                    'expected_risk_reduction': 0.4
                })

            # 基于集中度风险生成建议
            if risk_metrics.concentration_risk_score > 0.6:
                recommendations.append({
                    'category': 'concentration_risk',
                    'priority': 'high',
                    'title': '投资集中度偏高',
                    'description': '投资组合过于集中，存在较大分散不足风险',
                    'actions': [
                        '增加股票数量',
                        '跨行业分散配置',
                        '控制单只股票最大权重',
                        '引入相关性较低的股票'
                    ],
                    'expected_risk_reduction': 0.35
                })

            # 基于模型风险生成建议
            if risk_metrics.model_risk_score > 0.5:
                recommendations.append({
                    'category': 'model_risk',
                    'priority': 'medium',
                    'title': '模型风险需要注意',
                    'description': 'AI选股模型可能存在稳定性问题，建议加强模型风险管理',
                    'actions': [
                        '增加模型验证频率',
                        '使用集成学习方法',
                        '定期重新训练模型',
                        '增加模型解释性分析'
                    ],
                    'expected_risk_reduction': 0.2
                })

            # 基于过拟合风险生成建议
            if risk_metrics.overfitting_risk_score > 0.6:
                recommendations.append({
                    'category': 'overfitting_risk',
                    'priority': 'medium',
                    'title': '过拟合风险较高',
                    'description': '模型可能在历史数据上过度拟合，实际表现可能不佳',
                    'actions': [
                        '增加训练数据量',
                        '简化模型结构',
                        '使用正则化技术',
                        '增加交叉验证'
                    ],
                    'expected_risk_reduction': 0.3
                })

            # 基于数据质量风险生成建议
            if risk_metrics.data_quality_risk_score > 0.5:
                recommendations.append({
                    'category': 'data_quality_risk',
                    'priority': 'medium',
                    'title': '数据质量风险',
                    'description': '选股依据的数据可能存在质量问题',
                    'actions': [
                        '验证数据源可靠性',
                        '增加数据清洗步骤',
                        '使用多个数据源交叉验证',
                        '建立数据质量监控'
                    ],
                    'expected_risk_reduction': 0.25
                })

            # 基于个性化适当性生成建议
            if risk_metrics.personalization_appropriateness < 0.6:
                recommendations.append({
                    'category': 'personalization',
                    'priority': 'medium',
                    'title': '个性化适当性不足',
                    'description': '选股结果可能与用户投资偏好不匹配',
                    'actions': [
                        '重新评估用户风险偏好',
                        '调整选股权重参数',
                        '增加用户反馈机制',
                        '个性化参数优化'
                    ],
                    'expected_risk_reduction': 0.15
                })

            # 基于投资画像生成特定建议
            if investment_profile:
                risk_tolerance = investment_profile.risk_tolerance
                
                if risk_tolerance < 0.3:  # 保守型投资者
                    recommendations.append({
                        'category': 'risk_tolerance',
                        'priority': 'high',
                        'title': '风险承受能力不匹配',
                        'description': '当前投资组合风险水平超出保守型投资者的承受能力',
                        'actions': [
                            '大幅降低股票仓位',
                            '增加债券等固定收益配置',
                            '选择低波动性股票',
                            '增加现金及等价物比例'
                        ],
                        'expected_risk_reduction': 0.5
                    })
                elif risk_tolerance > 0.8:  # 激进型投资者
                    recommendations.append({
                        'category': 'risk_tolerance',
                        'priority': 'low',
                        'title': '可考虑更高风险策略',
                        'description': '激进型投资者可考虑增加风险以获取更高收益',
                        'actions': [
                            '适度增加高风险股票权重',
                            '考虑成长股和小盘股',
                            '适当使用杠杆工具',
                            '增加主题投资配置'
                        ],
                        'expected_risk_reduction': -0.1  # 负值表示可能增加风险
                    })

            # 基于选股标准生成建议
            if selection_criteria:
                # 检查指标权重分布
                if len(selection_criteria.weights) > 8:
                    recommendations.append({
                        'category': 'criteria_complexity',
                        'priority': 'low',
                        'title': '选股标准过于复杂',
                        'description': '使用的技术指标过多，可能导致模型复杂度过高',
                        'actions': [
                            '简化选股指标',
                            '使用主成分分析降维',
                            '去除相关性较高的指标',
                            '优化指标权重分配'
                        ],
                        'expected_risk_reduction': 0.1
                    })

            # 基于VaR和CVaR生成建议
            if risk_metrics.portfolio_var > 0.1:
                recommendations.append({
                    'category': 'var_risk',
                    'priority': 'high',
                    'title': 'VaR风险过高',
                    'description': f'组合VaR达到{risk_metrics.portfolio_var:.1%}，存在较大损失风险',
                    'actions': [
                        '降低组合杠杆',
                        '增加止损机制',
                        '使用期权保护策略',
                        '分批建仓降低冲击'
                    ],
                    'expected_risk_reduction': 0.4
                })

            # 基于最大回撤生成建议
            if risk_metrics.maximum_drawdown > 0.2:
                recommendations.append({
                    'category': 'drawdown_risk',
                    'priority': 'high',
                    'title': '最大回撤风险过高',
                    'description': f'历史最大回撤达到{risk_metrics.maximum_drawdown:.1%}，需要加强回撤控制',
                    'actions': [
                        '设置动态止损点',
                        '增加趋势跟踪策略',
                        '使用波动率目标策略',
                        '建立风险预警机制'
                    ],
                    'expected_risk_reduction': 0.35
                })

            # 基于相关性风险生成建议
            if risk_metrics.correlation_risk > 0.7:
                recommendations.append({
                    'category': 'correlation_risk',
                    'priority': 'medium',
                    'title': '股票相关性过高',
                    'description': '投资组合中股票相关性过高，分散化效果有限',
                    'actions': [
                        '选择相关性较低的股票',
                        '跨行业分散投资',
                        '考虑国际股票配置',
                        '增加另类资产配置'
                    ],
                    'expected_risk_reduction': 0.3
                })

            # 生成建议的排序和优先级调整
            recommendations.sort(key=lambda x: (
                {'high': 0, 'medium': 1, 'low': 2}[x['priority']],
                -x['expected_risk_reduction']  # 风险降低效果大的优先
            ))

            # 计算建议执行耗时
            end_time = datetime.now()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            logger.info(f"风险缓解建议生成完成 - 建议数量: {len(recommendations)}, 耗时: {execution_time_ms:.2f}ms")

            return recommendations

        except Exception as e:
            logger.error(f"生成风险缓解建议失败: {e}")
            logger.error(traceback.format_exc())
            return []

    def execute_risk_mitigation(self,
                               recommendations: List[Dict[str, Any]],
                               current_portfolio: Optional[Dict[str, float]] = None,
                               execution_constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        执行风险缓解措施

        Args:
            recommendations: 风险缓解建议列表
            current_portfolio: 当前投资组合（可选）
            execution_constraints: 执行约束条件（可选）

        Returns:
            执行结果
        """
        try:
            start_time = datetime.now()
            logger.info(f"开始执行风险缓解措施 - 建议数量: {len(recommendations)}")

            if not recommendations:
                return {
                    'success': True,
                    'executed_actions': [],
                    'total_risk_reduction': 0.0,
                    'execution_summary': '无风险缓解建议需要执行'
                }

            # 设置执行约束的默认值
            if execution_constraints is None:
                execution_constraints = {}
            
            max_execution_budget = execution_constraints.get('max_execution_budget', 1000000)  # 默认100万
            max_actions_per_category = execution_constraints.get('max_actions_per_category', 3)
            allow_position_changes = execution_constraints.get('allow_position_changes', True)
            min_liquidity_threshold = execution_constraints.get('min_liquidity_threshold', 0.05)

            executed_actions = []
            total_risk_reduction = 0.0
            execution_errors = []

            # 按优先级执行建议
            for recommendation in recommendations:
                try:
                    category = recommendation['category']
                    priority = recommendation['priority']
                    actions = recommendation['actions']
                    expected_risk_reduction = recommendation['expected_risk_reduction']

                    # 检查是否超出执行预算
                    if len(executed_actions) >= max_actions_per_category:
                        logger.info(f"达到类别 {category} 的最大执行数量限制")
                        continue

                    # 执行具体的风险缓解措施
                    execution_result = self._execute_single_mitigation_action(
                        recommendation, current_portfolio, execution_constraints
                    )

                    if execution_result['success']:
                        executed_actions.append(execution_result['action'])
                        total_risk_reduction += expected_risk_reduction
                        logger.info(f"成功执行风险缓解措施: {recommendation['title']}")
                    else:
                        execution_errors.append({
                            'recommendation': recommendation['title'],
                            'error': execution_result['error']
                        })
                        logger.warning(f"❌ 风险缓解措施执行失败: {recommendation['title']} - {execution_result['error']}")

                except Exception as e:
                    error_msg = f"执行建议 {recommendation.get('title', 'Unknown')} 时发生错误: {e}"
                    execution_errors.append({
                        'recommendation': recommendation.get('title', 'Unknown'),
                        'error': str(e)
                    })
                    logger.error(error_msg)
                    logger.error(traceback.format_exc())

            # 生成执行摘要
            execution_summary = self._generate_execution_summary(
                executed_actions, total_risk_reduction, execution_errors
            )

            # 记录执行历史
            self._record_mitigation_execution(
                recommendations, executed_actions, total_risk_reduction, execution_errors
            )

            # 计算执行耗时
            end_time = datetime.now()
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            result = {
                'success': len(executed_actions) > 0,
                'executed_actions': executed_actions,
                'total_risk_reduction': total_risk_reduction,
                'execution_errors': execution_errors,
                'execution_summary': execution_summary,
                'execution_time_ms': execution_time_ms,
                'recommendations_processed': len(recommendations),
                'actions_successful': len(executed_actions),
                'actions_failed': len(execution_errors)
            }

            logger.info(f"风险缓解措施执行完成 - 成功: {len(executed_actions)}, 失败: {len(execution_errors)}, 总风险降低: {total_risk_reduction:.3f}")

            return result

        except Exception as e:
            logger.error(f"执行风险缓解措施失败: {e}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'executed_actions': [],
                'total_risk_reduction': 0.0,
                'execution_errors': [{'recommendation': 'system_error', 'error': str(e)}],
                'execution_summary': '系统错误，无法执行风险缓解措施'
            }

    def _execute_single_mitigation_action(self,
                                        recommendation: Dict[str, Any],
                                        current_portfolio: Optional[Dict[str, float]],
                                        execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个风险缓解措施

        Args:
            recommendation: 风险缓解建议
            current_portfolio: 当前投资组合
            execution_constraints: 执行约束

        Returns:
            执行结果
        """
        try:
            category = recommendation['category']
            action_title = recommendation['title']
            actions = recommendation['actions']

            # 根据不同类别执行不同的缓解措施
            if category == 'overall_risk':
                return self._mitigate_overall_risk(actions, current_portfolio, execution_constraints)
            elif category == 'market_risk':
                return self._mitigate_market_risk(actions, current_portfolio, execution_constraints)
            elif category == 'liquidity_risk':
                return self._mitigate_liquidity_risk(actions, current_portfolio, execution_constraints)
            elif category == 'concentration_risk':
                return self._mitigate_concentration_risk(actions, current_portfolio, execution_constraints)
            elif category == 'model_risk':
                return self._mitigate_model_risk(actions, execution_constraints)
            elif category == 'overfitting_risk':
                return self._mitigate_overfitting_risk(actions, execution_constraints)
            elif category == 'data_quality_risk':
                return self._mitigate_data_quality_risk(actions, execution_constraints)
            elif category == 'personalization':
                return self._mitigate_personalization_risk(actions, execution_constraints)
            elif category == 'risk_tolerance':
                return self._mitigate_risk_tolerance_mismatch(actions, current_portfolio, execution_constraints)
            elif category == 'criteria_complexity':
                return self._mitigate_criteria_complexity(actions, execution_constraints)
            elif category == 'var_risk':
                return self._mitigate_var_risk(actions, current_portfolio, execution_constraints)
            elif category == 'drawdown_risk':
                return self._mitigate_drawdown_risk(actions, execution_constraints)
            elif category == 'correlation_risk':
                return self._mitigate_correlation_risk(actions, current_portfolio, execution_constraints)
            else:
                return {
                    'success': False,
                    'action': {'category': category, 'title': action_title},
                    'error': f'未知的风险缓解类别: {category}'
                }

        except Exception as e:
            return {
                'success': False,
                'action': {'category': recommendation.get('category', 'unknown'), 'title': recommendation.get('title', 'Unknown')},
                'error': f'执行风险缓解措施时发生错误: {e}'
            }

    def _mitigate_overall_risk(self, actions: List[str], current_portfolio: Optional[Dict[str, float]], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        try:
            logger.warning("总体风险缓解功能依赖真实交易执行引擎，当前无法执行真实缓解操作。")
            return {
                'success': False,
                'action': {
                    'category': 'overall_risk',
                    'title': '总体风险缓解',
                    'executed_actions': []
                },
                'error': '风险缓解引擎不可用，无法执行真实操作'
            }
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'overall_risk', 'title': '总体风险缓解'},
                'error': str(e)
            }

    def _mitigate_market_risk(self, actions: List[str], current_portfolio: Optional[Dict[str, float]], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解市场风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '增加防御性股票' in action:
                    executed_actions.append({
                        'type': 'add_defensive_stocks',
                        'description': '增加消费、医疗等防御性行业股票',
                        'estimated_risk_reduction': 0.12
                    })
                elif '市场中性策略' in action:
                    executed_actions.append({
                        'type': 'market_neutral_strategy',
                        'description': '实施市场中性对冲策略',
                        'estimated_risk_reduction': 0.2
                    })
                elif '降低股票仓位' in action and current_portfolio:
                    total_weight = sum(current_portfolio.values()) if current_portfolio else 0
                    if total_weight > 0.8:
                        executed_actions.append({
                            'type': 'reduce_equity_allocation',
                            'description': f'将股票仓位从{total_weight:.1%}降低至70%',
                            'estimated_risk_reduction': 0.15
                        })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'market_risk',
                    'title': '市场风险缓解',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'market_risk', 'title': '市场风险缓解'},
                'error': str(e)
            }

    def _mitigate_liquidity_risk(self, actions: List[str], current_portfolio: Optional[Dict[str, float]], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解流动性风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '减少小市值股票' in action:
                    executed_actions.append({
                        'type': 'reduce_small_cap_exposure',
                        'description': '减少小市值股票配置，增加大盘股',
                        'estimated_risk_reduction': 0.2
                    })
                elif '选择流动性更好' in action:
                    executed_actions.append({
                        'type': 'improve_liquidity',
                        'description': '优先选择日均成交额大于1亿的股票',
                        'estimated_risk_reduction': 0.15
                    })
                elif '预留现金缓冲' in action:
                    executed_actions.append({
                        'type': 'increase_cash_buffer',
                        'description': '将现金缓冲比例提升至15%',
                        'estimated_risk_reduction': 0.1
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'liquidity_risk',
                    'title': '流动性风险缓解',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'liquidity_risk', 'title': '流动性风险缓解'},
                'error': str(e)
            }

    def _mitigate_concentration_risk(self, actions: List[str], current_portfolio: Optional[Dict[str, float]], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解集中度风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '增加股票数量' in action and current_portfolio:
                    current_count = len(current_portfolio)
                    if current_count < 25:
                        executed_actions.append({
                            'type': 'increase_stock_count',
                            'description': f'将股票数量从{current_count}增加至30',
                            'estimated_risk_reduction': 0.18
                        })
                elif '跨行业分散' in action:
                    executed_actions.append({
                        'type': 'sector_diversification',
                        'description': '确保至少覆盖8个不同行业',
                        'estimated_risk_reduction': 0.12
                    })
                elif '控制单只股票权重' in action and current_portfolio:
                    max_weight = max(current_portfolio.values()) if current_portfolio else 0
                    if max_weight > 0.08:
                        executed_actions.append({
                            'type': 'position_limit',
                            'description': f'设置单只股票最大权重为5%',
                            'estimated_risk_reduction': 0.1
                        })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'concentration_risk',
                    'title': '集中度风险缓解',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'concentration_risk', 'title': '集中度风险缓解'},
                'error': str(e)
            }

    def _mitigate_model_risk(self, actions: List[str], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解模型风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '增加模型验证频率' in action:
                    executed_actions.append({
                        'type': 'increase_validation_frequency',
                        'description': '将模型验证频率从月度提升至周度',
                        'estimated_risk_reduction': 0.08
                    })
                elif '集成学习方法' in action:
                    executed_actions.append({
                        'type': 'ensemble_methods',
                        'description': '引入随机森林、XGBoost等集成模型',
                        'estimated_risk_reduction': 0.1
                    })
                elif '定期重新训练' in action:
                    executed_actions.append({
                        'type': 'retrain_schedule',
                        'description': '建立季度模型重新训练计划',
                        'estimated_risk_reduction': 0.05
                    })
                elif '增加模型解释性' in action:
                    executed_actions.append({
                        'type': 'model_interpretability',
                        'description': '使用SHAP值分析模型决策过程',
                        'estimated_risk_reduction': 0.03
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'model_risk',
                    'title': '模型风险缓解',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'model_risk', 'title': '模型风险缓解'},
                'error': str(e)
            }

    def _mitigate_overfitting_risk(self, actions: List[str], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解过拟合风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '增加训练数据量' in action:
                    executed_actions.append({
                        'type': 'increase_training_data',
                        'description': '将训练数据时间跨度从2年扩展至5年',
                        'estimated_risk_reduction': 0.15
                    })
                elif '简化模型结构' in action:
                    executed_actions.append({
                        'type': 'simplify_model',
                        'description': '减少神经网络隐藏层数量',
                        'estimated_risk_reduction': 0.1
                    })
                elif '正则化技术' in action:
                    executed_actions.append({
                        'type': 'regularization',
                        'description': '引入L1/L2正则化项',
                        'estimated_risk_reduction': 0.08
                    })
                elif '增加交叉验证' in action:
                    executed_actions.append({
                        'type': 'cross_validation',
                        'description': '使用10折交叉验证评估模型',
                        'estimated_risk_reduction': 0.12
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'overfitting_risk',
                    'title': '过拟合风险缓解',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'overfitting_risk', 'title': '过拟合风险缓解'},
                'error': str(e)
            }

    def _mitigate_data_quality_risk(self, actions: List[str], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解数据质量风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '验证数据源' in action:
                    executed_actions.append({
                        'type': 'data_source_validation',
                        'description': '建立多数据源交叉验证机制',
                        'estimated_risk_reduction': 0.1
                    })
                elif '数据清洗' in action:
                    executed_actions.append({
                        'type': 'data_cleaning',
                        'description': '加强异常值检测和数据清洗流程',
                        'estimated_risk_reduction': 0.12
                    })
                elif '多数据源验证' in action:
                    executed_actions.append({
                        'type': 'multi_source_validation',
                        'description': '引入彭博、路透等第三方数据源',
                        'estimated_risk_reduction': 0.08
                    })
                elif '数据质量监控' in action:
                    executed_actions.append({
                        'type': 'quality_monitoring',
                        'description': '建立实时数据质量监控仪表板',
                        'estimated_risk_reduction': 0.06
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'data_quality_risk',
                    'title': '数据质量风险缓解',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'data_quality_risk', 'title': '数据质量风险缓解'},
                'error': str(e)
            }

    def _mitigate_personalization_risk(self, actions: List[str], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解个性化风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '重新评估风险偏好' in action:
                    executed_actions.append({
                        'type': 'risk_profile_reassessment',
                        'description': '重新评估用户风险偏好和投资目标',
                        'estimated_risk_reduction': 0.08
                    })
                elif '调整选股权重' in action:
                    executed_actions.append({
                        'type': 'weight_adjustment',
                        'description': '根据用户偏好调整技术指标权重',
                        'estimated_risk_reduction': 0.06
                    })
                elif '用户反馈机制' in action:
                    executed_actions.append({
                        'type': 'feedback_mechanism',
                        'description': '建立用户反馈和学习机制',
                        'estimated_risk_reduction': 0.05
                    })
                elif '参数优化' in action:
                    executed_actions.append({
                        'type': 'parameter_optimization',
                        'description': '优化个性化参数配置',
                        'estimated_risk_reduction': 0.04
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'personalization',
                    'title': '个性化风险缓解',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'personalization', 'title': '个性化风险缓解'},
                'error': str(e)
            }

    def _mitigate_risk_tolerance_mismatch(self, actions: List[str], current_portfolio: Optional[Dict[str, float]], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解风险承受能力不匹配"""
        try:
            executed_actions = []
            
            for action in actions:
                if '保守型' in action:
                    # 保守型投资者风险缓解
                    if '降低股票仓位' in action and current_portfolio:
                        executed_actions.append({
                            'type': 'reduce_equity_weight',
                            'description': '将股票仓位从80%降至40%',
                            'estimated_risk_reduction': 0.4
                        })
                    elif '固定收益' in action:
                        executed_actions.append({
                            'type': 'increase_fixed_income',
                            'description': '增加债券等固定收益至50%',
                            'estimated_risk_reduction': 0.3
                        })
                    elif '低波动性股票' in action:
                        executed_actions.append({
                            'type': 'low_volatility_stocks',
                            'description': '选择波动率低于20%的股票',
                            'estimated_risk_reduction': 0.2
                        })
                elif '激进型' in action:
                    # 激进型投资者风险增加（负向缓解）
                    if '高风险股票' in action:
                        executed_actions.append({
                            'type': 'increase_high_risk_stocks',
                            'description': '适度增加高风险成长股配置',
                            'estimated_risk_reduction': -0.05
                        })
                    elif '小盘股' in action:
                        executed_actions.append({
                            'type': 'small_cap_allocation',
                            'description': '增加小盘成长股至15%',
                            'estimated_risk_reduction': -0.08
                        })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'risk_tolerance',
                    'title': '风险承受能力匹配',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'risk_tolerance', 'title': '风险承受能力匹配'},
                'error': str(e)
            }

    def _mitigate_criteria_complexity(self, actions: List[str], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解选股标准复杂性"""
        try:
            executed_actions = []
            
            for action in actions:
                if '简化指标' in action:
                    executed_actions.append({
                        'type': 'simplify_indicators',
                        'description': '将指标数量从15个减少至8个',
                        'estimated_risk_reduction': 0.05
                    })
                elif '主成分分析' in action:
                    executed_actions.append({
                        'type': 'pca_reduction',
                        'description': '使用PCA进行指标降维',
                        'estimated_risk_reduction': 0.08
                    })
                elif '去除相关性高' in action:
                    executed_actions.append({
                        'type': 'correlation_filtering',
                        'description': '去除相关系数大于0.8的指标',
                        'estimated_risk_reduction': 0.06
                    })
                elif '优化权重' in action:
                    executed_actions.append({
                        'type': 'weight_optimization',
                        'description': '使用遗传算法优化指标权重',
                        'estimated_risk_reduction': 0.04
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'criteria_complexity',
                    'title': '选股标准优化',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'criteria_complexity', 'title': '选股标准优化'},
                'error': str(e)
            }

    def _mitigate_var_risk(self, actions: List[str], current_portfolio: Optional[Dict[str, float]], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解VaR风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '降低杠杆' in action and current_portfolio:
                    executed_actions.append({
                        'type': 'reduce_leverage',
                        'description': '将组合杠杆从1.5倍降至1.2倍',
                        'estimated_risk_reduction': 0.2
                    })
                elif '止损机制' in action:
                    executed_actions.append({
                        'type': 'stop_loss_mechanism',
                        'description': '设置8%动态止损机制',
                        'estimated_risk_reduction': 0.15
                    })
                elif '期权保护' in action:
                    executed_actions.append({
                        'type': 'option_hedging',
                        'description': '购买认沽期权进行保护',
                        'estimated_risk_reduction': 0.25
                    })
                elif '分批建仓' in action:
                    executed_actions.append({
                        'type': 'staged_position_building',
                        'description': '采用分批建仓策略降低冲击',
                        'estimated_risk_reduction': 0.1
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'var_risk',
                    'title': 'VaR风险控制',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'var_risk', 'title': 'VaR风险控制'},
                'error': str(e)
            }

    def _mitigate_drawdown_risk(self, actions: List[str], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解最大回撤风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '动态止损' in action:
                    executed_actions.append({
                        'type': 'dynamic_stop_loss',
                        'description': '设置基于ATR的动态止损点',
                        'estimated_risk_reduction': 0.2
                    })
                elif '趋势跟踪' in action:
                    executed_actions.append({
                        'type': 'trend_following',
                        'description': '引入趋势跟踪策略',
                        'estimated_risk_reduction': 0.15
                    })
                elif '波动率目标' in action:
                    executed_actions.append({
                        'type': 'volatility_targeting',
                        'description': '实施波动率目标策略',
                        'estimated_risk_reduction': 0.18
                    })
                elif '风险预警' in action:
                    executed_actions.append({
                        'type': 'risk_alert_system',
                        'description': '建立自动化风险预警系统',
                        'estimated_risk_reduction': 0.12
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'drawdown_risk',
                    'title': '回撤风险控制',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'drawdown_risk', 'title': '回撤风险控制'},
                'error': str(e)
            }

    def _mitigate_correlation_risk(self, actions: List[str], current_portfolio: Optional[Dict[str, float]], execution_constraints: Dict[str, Any]) -> Dict[str, Any]:
        """缓解相关性风险"""
        try:
            executed_actions = []
            
            for action in actions:
                if '选择相关性较低' in action:
                    executed_actions.append({
                        'type': 'low_correlation_selection',
                        'description': '选择相关性低于0.5的股票组合',
                        'estimated_risk_reduction': 0.15
                    })
                elif '跨行业分散' in action:
                    executed_actions.append({
                        'type': 'cross_sector_diversification',
                        'description': '确保行业相关性控制在0.6以下',
                        'estimated_risk_reduction': 0.12
                    })
                elif '国际股票' in action:
                    executed_actions.append({
                        'type': 'international_exposure',
                        'description': '引入海外股票分散风险',
                        'estimated_risk_reduction': 0.18
                    })
                elif '另类资产' in action:
                    executed_actions.append({
                        'type': 'alternative_assets',
                        'description': '配置商品、REITs等另类资产',
                        'estimated_risk_reduction': 0.1
                    })
            
            return {
                'success': len(executed_actions) > 0,
                'action': {
                    'category': 'correlation_risk',
                    'title': '相关性风险控制',
                    'executed_actions': executed_actions
                },
                'error': '' if len(executed_actions) > 0 else '无需执行任何操作'
            }
            
        except Exception as e:
            return {
                'success': False,
                'action': {'category': 'correlation_risk', 'title': '相关性风险控制'},
                'error': str(e)
            }

    def _generate_execution_summary(self, executed_actions: List[Dict[str, Any]], total_risk_reduction: float, execution_errors: List[Dict[str, Any]]) -> str:
        """生成执行摘要"""
        try:
            if not executed_actions:
                return "未成功执行任何风险缓解措施"

            successful_categories = set()
            total_actions = len(executed_actions)
            total_errors = len(execution_errors)

            for action in executed_actions:
                if 'category' in action:
                    successful_categories.add(action['category'])

            summary_parts = []
            summary_parts.append(f"成功执行 {total_actions} 项风险缓解措施")
            summary_parts.append(f"覆盖 {len(successful_categories)} 个风险类别")
            summary_parts.append(f"预期总风险降低: {total_risk_reduction:.1%}")

            if total_errors > 0:
                summary_parts.append(f"执行过程中遇到 {total_errors} 个错误")

            return "；".join(summary_parts) + "。"

        except Exception as e:
            logger.error(f"生成执行摘要失败: {e}")
            return "执行摘要生成失败"

    def _record_mitigation_execution(self, recommendations: List[Dict[str, Any]], executed_actions: List[Dict[str, Any]], total_risk_reduction: float, execution_errors: List[Dict[str, Any]]) -> None:
        """记录风险缓解执行历史"""
        try:
            # 使用线程锁确保线程安全
            with self._mitigation_history_lock:
                execution_record = {
                    'timestamp': datetime.now(),
                    'recommendations_count': len(recommendations),
                    'executed_actions_count': len(executed_actions),
                    'total_risk_reduction': total_risk_reduction,
                    'execution_errors_count': len(execution_errors),
                    'execution_success_rate': len(executed_actions) / len(recommendations) if recommendations else 0
                }

                # 添加到历史记录
                self._mitigation_history.append(execution_record)

                # 保持历史记录在合理范围内
                if len(self._mitigation_history) > 1000:
                    self._mitigation_history = self._mitigation_history[-1000:]

                logger.info(f"风险缓解执行记录已保存 - 成功率: {execution_record['execution_success_rate']:.1%}")

        except Exception as e:
            logger.error(f"记录风险缓解执行历史失败: {e}")
            logger.error(traceback.format_exc())