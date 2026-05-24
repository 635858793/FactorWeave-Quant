import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import json
import pickle
from utils.safe_pickle import safe_load
from collections import deque
import statistics
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

from .advanced_risk_control_service import AdvancedRiskControlService, AdvancedRiskMetrics, MarketRegime, RiskLevel


class AdjustmentStrategy(Enum):
    """调整策略"""
    CONSERVATIVE = "conservative"  # 保守调整
    AGGRESSIVE = "aggressive"     # 激进调整
    ADAPTIVE = "adaptive"         # 自适应调整
    RULE_BASED = "rule_based"     # 基于规则
    ML_BASED = "ml_based"         # 基于机器学习


class AdjustmentTrigger(Enum):
    """调整触发条件"""
    TIME_BASED = "time_based"           # 基于时间
    RISK_THRESHOLD = "risk_threshold"   # 基于风险阈值
    MARKET_REGIME_CHANGE = "regime_change"  # 市场状态变化
    PERFORMANCE_DEGRADATION = "perf_degradation"  # 性能下降
    VOLATILITY_SPIKE = "volatility_spike"  # 波动率激增


@dataclass
class AdjustmentRule:
    """调整规则"""
    name: str
    trigger: AdjustmentTrigger
    condition: Callable[[Dict], bool]
    action: Callable[[Dict], Dict[str, float]]
    priority: int = 1
    enabled: bool = True
    cooldown_period: int = 300  # 冷却时间（秒）
    last_triggered: Optional[datetime] = None


@dataclass
class AdjustmentHistory:
    """调整历史记录"""
    timestamp: datetime
    strategy: AdjustmentStrategy
    trigger: AdjustmentTrigger
    before_params: Dict[str, float]
    after_params: Dict[str, float]
    market_conditions: Dict[str, Any]
    performance_impact: float
    success: bool
    notes: str = ""


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: datetime
    risk_score: float
    return_rate: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    avg_trade_return: float


class DynamicRiskAdjustmentEngine:
    """动态风险参数调整引擎"""
    
    def __init__(self, initial_params: Dict[str, float] = None):
        # 初始参数
        self.base_params = initial_params or {
            'risk_budget_multiplier': 1.0,
            'position_limit_multiplier': 1.0,
            'stop_loss_adjustment': 0.0,
            'hedge_ratio_adjustment': 0.0,
            'market_regime_adjustment': 1.0,
            'volatility_threshold': 0.2,
            'correlation_threshold': 0.7,
            'liquidity_threshold': 0.1
        }
        
        # 当前参数
        self.current_params = self.base_params.copy()
        
        # 调整历史
        self.adjustment_history = deque(maxlen=1000)
        
        # 性能指标历史
        self.performance_history = deque(maxlen=500)
        
        # 调整规则
        self.adjustment_rules = []
        
        # 调整策略
        self.current_strategy = AdjustmentStrategy.ADAPTIVE
        
        # 机器学习模型
        self.ml_models = {}
        self.scalers = {}
        
        # 反馈学习
        self.learning_rate = 0.01
        self.adaptation_window = 100  # 适应窗口大小
        
        # 冷却管理
        self.cooldown_tracker = {}
        
        # 初始化默认规则
        self._initialize_default_rules()
        
        # 初始化机器学习模型
        self._initialize_ml_models()
    
    def _initialize_default_rules(self):
        """初始化默认调整规则"""
        
        # 规则1: 高风险时降低风险预算
        def high_risk_rule(market_conditions):
            risk_score = market_conditions.get('risk_score', 0)
            return risk_score > 0.8
        
        def high_risk_action(market_conditions):
            return {
                'risk_budget_multiplier': max(0.5, self.current_params['risk_budget_multiplier'] * 0.8),
                'position_limit_multiplier': max(0.6, self.current_params['position_limit_multiplier'] * 0.85),
                'stop_loss_adjustment': self.current_params['stop_loss_adjustment'] + 0.02
            }
        
        self.adjustment_rules.append(AdjustmentRule(
            name="high_risk_reduction",
            trigger=AdjustmentTrigger.RISK_THRESHOLD,
            condition=high_risk_rule,
            action=high_risk_action,
            priority=1,
            cooldown_period=600
        ))
        
        # 规则2: 波动率激增时调整
        def volatility_spike_rule(market_conditions):
            current_vol = market_conditions.get('volatility', 0)
            historical_vol = market_conditions.get('historical_volatility', 0.2)
            return current_vol > historical_vol * 1.5
        
        def volatility_spike_action(market_conditions):
            return {
                'volatility_threshold': min(0.4, self.current_params['volatility_threshold'] * 1.2),
                'stop_loss_adjustment': self.current_params['stop_loss_adjustment'] + 0.015
            }
        
        self.adjustment_rules.append(AdjustmentRule(
            name="volatility_spike_adjustment",
            trigger=AdjustmentTrigger.VOLATILITY_SPIKE,
            condition=volatility_spike_rule,
            action=volatility_spike_action,
            priority=2,
            cooldown_period=300
        ))
        
        # 规则3: 市场状态变化时调整
        def regime_change_rule(market_conditions):
            current_regime = market_conditions.get('market_regime')
            previous_regime = market_conditions.get('previous_market_regime')
            return current_regime != previous_regime and previous_regime is not None
        
        def regime_change_action(market_conditions):
            regime = market_conditions.get('market_regime')
            adjustments = {}
            
            if regime == MarketRegime.VOLATILE.value:
                adjustments = {
                    'risk_budget_multiplier': 0.7,
                    'position_limit_multiplier': 0.8,
                    'hedge_ratio_adjustment': 0.15
                }
            elif regime == MarketRegime.BEAR.value:
                adjustments = {
                    'risk_budget_multiplier': 0.8,
                    'position_limit_multiplier': 0.9,
                    'hedge_ratio_adjustment': 0.1
                }
            elif regime == MarketRegime.BULL.value:
                adjustments = {
                    'risk_budget_multiplier': 1.1,
                    'position_limit_multiplier': 1.05,
                    'hedge_ratio_adjustment': -0.05
                }
            
            return adjustments
        
        self.adjustment_rules.append(AdjustmentRule(
            name="regime_change_adjustment",
            trigger=AdjustmentTrigger.MARKET_REGIME_CHANGE,
            condition=regime_change_rule,
            action=regime_change_action,
            priority=3,
            cooldown_period=1800
        ))
        
        # 规则4: 性能下降时调整
        def performance_degradation_rule(market_conditions):
            if len(self.performance_history) < 10:
                return False
            
            recent_returns = [p.return_rate for p in list(self.performance_history)[-5:]]
            historical_returns = [p.return_rate for p in list(self.performance_history)[-20:-5]]
            
            if not historical_returns:
                return False
            
            avg_recent = statistics.mean(recent_returns)
            avg_historical = statistics.mean(historical_returns)
            
            return avg_recent < avg_historical * 0.8  # 最近表现比历史差20%
        
        def performance_degradation_action(market_conditions):
            return {
                'risk_budget_multiplier': max(0.6, self.current_params['risk_budget_multiplier'] * 0.9),
                'position_limit_multiplier': max(0.7, self.current_params['position_limit_multiplier'] * 0.95)
            }
        
        self.adjustment_rules.append(AdjustmentRule(
            name="performance_degradation_adjustment",
            trigger=AdjustmentTrigger.PERFORMANCE_DEGRADATION,
            condition=performance_degradation_rule,
            action=performance_degradation_action,
            priority=4,
            cooldown_period=900
        ))
        
        logger.info(f"初始化了 {len(self.adjustment_rules)} 个调整规则")
    
    def _initialize_ml_models(self):
        """初始化机器学习模型"""
        try:
            # 参数调整预测模型
            self.ml_models['param_adjustment'] = RandomForestRegressor(
                n_estimators=100,
                random_state=42,
                max_depth=8
            )
            
            # 性能预测模型
            self.ml_models['performance_prediction'] = RandomForestRegressor(
                n_estimators=50,
                random_state=42,
                max_depth=6
            )
            
            # 参数标准化器
            self.scalers['market_features'] = StandardScaler()
            self.scalers['param_features'] = StandardScaler()
            
            logger.info("机器学习模型初始化完成")
            
        except Exception as e:
            logger.error(f"初始化机器学习模型失败: {e}")
    
    def evaluate_adjustment_need(self, market_conditions: Dict[str, Any], 
                               performance_metrics: Optional[PerformanceMetrics] = None) -> Tuple[bool, List[AdjustmentRule]]:
        """评估是否需要调整参数"""
        try:
            triggered_rules = []
            current_time = datetime.now()
            
            for rule in self.adjustment_rules:
                if not rule.enabled:
                    continue
                
                # 检查冷却时间
                if rule.last_triggered:
                    time_since_last = (current_time - rule.last_triggered).total_seconds()
                    if time_since_last < rule.cooldown_period:
                        continue
                
                # 检查触发条件
                if rule.condition(market_conditions):
                    triggered_rules.append(rule)
            
            # 按优先级排序
            triggered_rules.sort(key=lambda r: r.priority)
            
            # 检查基于时间的调整
            if self._should_time_based_adjust(market_conditions):
                time_rule = AdjustmentRule(
                    name="time_based_adjustment",
                    trigger=AdjustmentTrigger.TIME_BASED,
                    condition=lambda x: True,
                    action=lambda x: self._get_time_based_adjustment(),
                    priority=99
                )
                triggered_rules.append(time_rule)
            
            return len(triggered_rules) > 0, triggered_rules
            
        except Exception as e:
            logger.error(f"评估调整需求失败: {e}")
            return False, []
    
    def _should_time_based_adjust(self, market_conditions: Dict[str, Any]) -> bool:
        """判断是否应该进行基于时间的调整"""
        if not self.adjustment_history:
            return False
        
        last_adjustment = max(self.adjustment_history, key=lambda x: x.timestamp)
        time_since_last = (datetime.now() - last_adjustment.timestamp).total_seconds()
        
        # 每4小时至少评估一次
        return time_since_last > 4 * 3600
    
    def _get_time_based_adjustment(self) -> Dict[str, float]:
        """获取基于时间的调整"""
        adjustments = {}
        
        # 基于当前策略进行调整
        if self.current_strategy == AdjustmentStrategy.CONSERVATIVE:
            adjustments = {
                'risk_budget_multiplier': 0.95,
                'position_limit_multiplier': 0.98
            }
        elif self.current_strategy == AdjustmentStrategy.AGGRESSIVE:
            adjustments = {
                'risk_budget_multiplier': 1.05,
                'position_limit_multiplier': 1.02
            }
        elif self.current_strategy == AdjustmentStrategy.ADAPTIVE:
            # 基于历史性能调整
            if len(self.performance_history) >= 20:
                recent_performance = list(self.performance_history)[-10:]
                avg_return = statistics.mean([p.return_rate for p in recent_performance])
                
                if avg_return > 0.02:  # 最近表现良好
                    adjustments = {
                        'risk_budget_multiplier': 1.02,
                        'position_limit_multiplier': 1.01
                    }
                elif avg_return < -0.01:  # 最近表现较差
                    adjustments = {
                        'risk_budget_multiplier': 0.98,
                        'position_limit_multiplier': 0.99
                    }
        
        return adjustments
    
    def execute_adjustment(self, triggered_rules: List[AdjustmentRule], 
                          market_conditions: Dict[str, Any],
                          performance_metrics: Optional[PerformanceMetrics] = None) -> bool:
        """执行参数调整"""
        try:
            if not triggered_rules:
                return False
            
            # 保存调整前参数
            before_params = self.current_params.copy()
            
            # 执行调整
            total_adjustments = {}
            successful_adjustments = 0
            
            for rule in triggered_rules:
                try:
                    # 执行调整动作
                    rule_adjustments = rule.action(market_conditions)
                    
                    # 应用调整
                    for param, value in rule_adjustments.items():
                        if param in self.current_params:
                            self.current_params[param] *= value if isinstance(value, (int, float)) and value != 1 else value
                    
                    total_adjustments.update(rule_adjustments)
                    
                    # 更新规则状态
                    rule.last_triggered = datetime.now()
                    successful_adjustments += 1
                    
                    logger.info(f"执行调整规则: {rule.name}, 调整: {rule_adjustments}")
                    
                except Exception as e:
                    logger.error(f"执行调整规则 {rule.name} 失败: {e}")
            
            # 记录调整历史
            performance_impact = self._calculate_performance_impact(performance_metrics)
            success = successful_adjustments > 0
            
            history_record = AdjustmentHistory(
                timestamp=datetime.now(),
                strategy=self.current_strategy,
                trigger=triggered_rules[0].trigger,
                before_params=before_params,
                after_params=self.current_params.copy(),
                market_conditions=market_conditions.copy(),
                performance_impact=performance_impact,
                success=success,
                notes=f"成功执行 {successful_adjustments}/{len(triggered_rules)} 个规则"
            )
            
            self.adjustment_history.append(history_record)
            
            # 反馈学习
            if success:
                self._feedback_learning(history_record)
            
            logger.info(f"参数调整完成: 成功 {successful_adjustments}/{len(triggered_rules)} 个规则")
            return success
            
        except Exception as e:
            logger.error(f"执行参数调整失败: {e}")
            return False
    
    def _calculate_performance_impact(self, performance_metrics: Optional[PerformanceMetrics]) -> float:
        """计算调整的性能影响"""
        try:
            if not performance_metrics or len(self.performance_history) < 2:
                return 0.0
            
            # 计算最近的性能变化
            recent_metrics = list(self.performance_history)[-5:]
            if len(recent_metrics) < 2:
                return 0.0
            
            # 简单的影响评估：基于夏普比率变化
            current_sharpe = performance_metrics.sharpe_ratio
            previous_sharpe = recent_metrics[-2].sharpe_ratio
            
            impact = (current_sharpe - previous_sharpe) / abs(previous_sharpe) if previous_sharpe != 0 else 0
            
            return impact
            
        except Exception as e:
            logger.error(f"计算性能影响失败: {e}")
            return 0.0
    
    def _feedback_learning(self, adjustment_record: AdjustmentHistory):
        """反馈学习机制"""
        try:
            # 基于调整结果调整学习参数
            if adjustment_record.performance_impact > 0.1:  # 调整效果良好
                self.learning_rate = min(0.05, self.learning_rate * 1.1)
            elif adjustment_record.performance_impact < -0.1:  # 调整效果较差
                self.learning_rate = max(0.005, self.learning_rate * 0.9)
            
            # 更新规则优先级（简化版）
            for rule in self.adjustment_rules:
                if rule.name in adjustment_record.notes:
                    # 根据成功与否调整冷却时间
                    if adjustment_record.success:
                        rule.cooldown_period = max(60, int(rule.cooldown_period * 0.95))
                    else:
                        rule.cooldown_period = min(3600, int(rule.cooldown_period * 1.05))
            
        except Exception as e:
            logger.error(f"反馈学习失败: {e}")
    
    def predict_optimal_adjustment(self, market_conditions: Dict[str, Any]) -> Optional[Dict[str, float]]:
        """使用机器学习预测最优调整"""
        try:
            if 'param_adjustment' not in self.ml_models or len(self.adjustment_history) < 20:
                return None
            
            # 准备特征数据
            features = self._prepare_ml_features(market_conditions)
            if not features:
                return None
            
            # 标准化特征
            features_scaled = self.scalers['param_features'].transform([features])
            
            # 进行预测
            predictions = self.ml_models['param_adjustment'].predict(features_scaled)[0]
            
            # 将预测结果转换为参数调整
            optimal_adjustments = {}
            param_names = list(self.current_params.keys())
            
            for i, param_name in enumerate(param_names):
                if i < len(predictions):
                    # 预测值代表调整幅度
                    adjustment = predictions[i]
                    optimal_adjustments[param_name] = max(0.1, min(10.0, 1.0 + adjustment))
            
            return optimal_adjustments
            
        except Exception as e:
            logger.error(f"预测最优调整失败: {e}")
            return None
    
    def _prepare_ml_features(self, market_conditions: Dict[str, Any]) -> List[float]:
        """准备机器学习特征"""
        try:
            features = [
                market_conditions.get('risk_score', 0),
                market_conditions.get('volatility', 0.2),
                market_conditions.get('drawdown', 0),
                market_conditions.get('correlation_breakdown', 0),
                market_conditions.get('liquidity_risk', 0),
                len(self.performance_history),
                statistics.mean([p.return_rate for p in list(self.performance_history)[-10:]]) if self.performance_history else 0,
                statistics.stdev([p.return_rate for p in list(self.performance_history)[-10:]]) if len(self.performance_history) >= 2 else 0,
            ]
            
            return features
            
        except Exception as e:
            logger.error(f"准备机器学习特征失败: {e}")
            return []
    
    def add_performance_metric(self, metrics: PerformanceMetrics):
        """添加性能指标"""
        try:
            self.performance_history.append(metrics)
            
            # 清理过期数据
            cutoff_time = datetime.now() - timedelta(days=7)
            self.performance_history = deque(
                [m for m in self.performance_history if m.timestamp > cutoff_time],
                maxlen=500
            )
            
        except Exception as e:
            logger.error(f"添加性能指标失败: {e}")
    
    def get_adjustment_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """获取调整统计信息"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_adjustments = [
                adj for adj in self.adjustment_history 
                if adj.timestamp > cutoff_time
            ]
            
            if not recent_adjustments:
                return {'status': 'no_data'}
            
            # 统计信息
            total_adjustments = len(recent_adjustments)
            successful_adjustments = len([adj for adj in recent_adjustments if adj.success])
            avg_impact = statistics.mean([adj.performance_impact for adj in recent_adjustments])
            
            # 触发原因统计
            trigger_counts = {}
            for adj in recent_adjustments:
                trigger = adj.trigger.value
                trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
            
            # 策略统计
            strategy_counts = {}
            for adj in recent_adjustments:
                strategy = adj.strategy.value
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
            
            # 参数变化统计
            param_changes = {}
            for param in self.base_params.keys():
                param_changes[param] = {
                    'current': self.current_params.get(param, 0),
                    'base': self.base_params.get(param, 0),
                    'change_ratio': (self.current_params.get(param, 0) / self.base_params.get(param, 1)) - 1
                }
            
            return {
                'total_adjustments': total_adjustments,
                'successful_adjustments': successful_adjustments,
                'success_rate': successful_adjustments / total_adjustments if total_adjustments > 0 else 0,
                'avg_performance_impact': avg_impact,
                'trigger_distribution': trigger_counts,
                'strategy_distribution': strategy_counts,
                'param_changes': param_changes,
                'current_strategy': self.current_strategy.value,
                'learning_rate': self.learning_rate
            }
            
        except Exception as e:
            logger.error(f"获取调整统计信息失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def set_adjustment_strategy(self, strategy: AdjustmentStrategy):
        """设置调整策略"""
        self.current_strategy = strategy
        logger.info(f"调整策略已设置为: {strategy.value}")
    
    def add_custom_rule(self, rule: AdjustmentRule):
        """添加自定义规则"""
        self.adjustment_rules.append(rule)
        logger.info(f"添加自定义规则: {rule.name}")
    
    def enable_rule(self, rule_name: str, enabled: bool = True):
        """启用/禁用规则"""
        for rule in self.adjustment_rules:
            if rule.name == rule_name:
                rule.enabled = enabled
                logger.info(f"规则 {rule_name} 已{'启用' if enabled else '禁用'}")
                break
    
    def reset_to_base_params(self):
        """重置为基准参数"""
        self.current_params = self.base_params.copy()
        logger.info("参数已重置为基准值")
    
    def export_adjustment_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """导出调整历史"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            exported_history = []
            for adj in self.adjustment_history:
                if adj.timestamp > cutoff_time:
                    exported_history.append({
                        'timestamp': adj.timestamp.isoformat(),
                        'strategy': adj.strategy.value,
                        'trigger': adj.trigger.value,
                        'before_params': adj.before_params,
                        'after_params': adj.after_params,
                        'performance_impact': adj.performance_impact,
                        'success': adj.success,
                        'notes': adj.notes
                    })
            
            return exported_history
            
        except Exception as e:
            logger.error(f"导出调整历史失败: {e}")
            return []
    
    def save_state(self, filepath: str):
        """保存状态"""
        try:
            state_data = {
                'base_params': self.base_params,
                'current_params': self.current_params,
                'current_strategy': self.current_strategy.value,
                'learning_rate': self.learning_rate,
                'adjustment_history': list(self.adjustment_history),
                'performance_history': [
                    {
                        'timestamp': m.timestamp.isoformat(),
                        'risk_score': m.risk_score,
                        'return_rate': m.return_rate,
                        'volatility': m.volatility,
                        'sharpe_ratio': m.sharpe_ratio,
                        'max_drawdown': m.max_drawdown,
                        'win_rate': m.win_rate,
                        'avg_trade_return': m.avg_trade_return
                    }
                    for m in self.performance_history
                ],
                'ml_models': self.ml_models,
                'scalers': self.scalers
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(state_data, f)
            
            logger.info(f"动态风险调整状态已保存到: {filepath}")
            
        except Exception as e:
            logger.error(f"保存状态失败: {e}")
    
    def load_state(self, filepath: str):
        """加载状态"""
        try:
            with open(filepath, 'rb') as f:
                state_data = safe_load(f)
            
            self.base_params = state_data.get('base_params', self.base_params)
            self.current_params = state_data.get('current_params', self.current_params)
            self.current_strategy = AdjustmentStrategy(state_data.get('current_strategy', 'adaptive'))
            self.learning_rate = state_data.get('learning_rate', 0.01)
            
            # 重建历史记录
            self.adjustment_history = deque(maxlen=1000)
            for adj_data in state_data.get('adjustment_history', []):
                adj = AdjustmentHistory(
                    timestamp=datetime.fromisoformat(adj_data['timestamp']),
                    strategy=AdjustmentStrategy(adj_data['strategy']),
                    trigger=AdjustmentTrigger(adj_data['trigger']),
                    before_params=adj_data['before_params'],
                    after_params=adj_data['after_params'],
                    market_conditions=adj_data['market_conditions'],
                    performance_impact=adj_data['performance_impact'],
                    success=adj_data['success'],
                    notes=adj_data['notes']
                )
                self.adjustment_history.append(adj)
            
            # 重建性能历史
            self.performance_history = deque(maxlen=500)
            for perf_data in state_data.get('performance_history', []):
                perf = PerformanceMetrics(
                    timestamp=datetime.fromisoformat(perf_data['timestamp']),
                    risk_score=perf_data['risk_score'],
                    return_rate=perf_data['return_rate'],
                    volatility=perf_data['volatility'],
                    sharpe_ratio=perf_data['sharpe_ratio'],
                    max_drawdown=perf_data['max_drawdown'],
                    win_rate=perf_data['win_rate'],
                    avg_trade_return=perf_data['avg_trade_return']
                )
                self.performance_history.append(perf)
            
            self.ml_models = state_data.get('ml_models', {})
            self.scalers = state_data.get('scalers', {})
            
            logger.info(f"动态风险调整状态已从 {filepath} 加载")
            
        except Exception as e:
            logger.error(f"加载状态失败: {e}")


class DynamicRiskAdjustmentService:
    """动态风险调整服务"""
    
    def __init__(self, service_container=None):
        self.service_container = service_container
        self.adjustment_engine = DynamicRiskAdjustmentEngine()
        
        # 服务状态
        self.is_running = False
        self.monitoring_task = None
        self._stop_event = asyncio.Event()
        
        # 监控参数
        self.monitoring_interval = 60  # 秒
        self.evaluation_window = 300   # 评估窗口（秒）
        
        # 集成的高级风险控制服务
        self.advanced_risk_service = None
        
        # 如果有服务容器，尝试获取高级风险控制服务
        if self.service_container:
            try:
                self.advanced_risk_service = self.service_container.get('AdvancedRiskControlService')
            except Exception as e:
                logger.debug(f"获取AdvancedRiskControlService失败: {e}")
    
    async def start_monitoring(self):
        """启动动态风险调整监控"""
        try:
            if not self.is_running:
                self.is_running = True
                self._stop_event.clear()
                self.monitoring_task = asyncio.create_task(self._monitoring_loop())
                logger.info("动态风险调整监控已启动")
                
        except Exception as e:
            logger.error(f"启动动态风险调整监控失败: {e}")
    
    async def stop_monitoring(self):
        """停止动态风险调整监控"""
        try:
            if self.is_running:
                self.is_running = False
                self._stop_event.set()
                if self.monitoring_task:
                    await self.monitoring_task
                    self.monitoring_task = None
                logger.info("动态风险调整监控已停止")
                
        except Exception as e:
            logger.error(f"停止动态风险调整监控失败: {e}")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                # 获取当前市场条件
                market_conditions = await self._get_current_market_conditions()
                
                # 获取性能指标
                performance_metrics = await self._get_current_performance_metrics()
                
                # 评估是否需要调整
                need_adjustment, triggered_rules = self.adjustment_engine.evaluate_adjustment_need(
                    market_conditions, performance_metrics
                )
                
                # 如果需要调整，执行调整
                if need_adjustment:
                    success = self.adjustment_engine.execute_adjustment(
                        triggered_rules, market_conditions, performance_metrics
                    )
                    
                    if success:
                        logger.info(f"执行了 {len(triggered_rules)} 个风险参数调整")
                
                # 添加性能指标到历史
                if performance_metrics:
                    self.adjustment_engine.add_performance_metric(performance_metrics)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"动态风险调整监控循环异常: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _get_current_market_conditions(self) -> Dict[str, Any]:
        """获取当前市场条件"""
        try:
            # 如果有高级风险控制服务，获取其数据
            if self.advanced_risk_service:
                risk_assessment = self.advanced_risk_service.get_current_risk_assessment()
                
                if risk_assessment.get('status') == 'success':
                    market_conditions = {
                        'risk_score': risk_assessment.get('risk_score', 0),
                        'market_regime': risk_assessment.get('market_regime', 'neutral'),
                        'volatility': risk_assessment.get('advanced_metrics', {}).get('volatility_forecast', 0.2),
                        'drawdown': risk_assessment.get('advanced_metrics', {}).get('drawdown_risk', 0),
                        'correlation_breakdown': risk_assessment.get('advanced_metrics', {}).get('correlation_breakdown', 0),
                        'liquidity_risk': risk_assessment.get('advanced_metrics', {}).get('liquidity_at_risk', 0),
                        'herding_risk': risk_assessment.get('advanced_metrics', {}).get('herding_risk', 0),
                        'sentiment_risk': risk_assessment.get('advanced_metrics', {}).get('sentiment_risk', 0),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # 获取历史数据用于比较
                    historical_data = self.advanced_risk_service.export_risk_data(hours=24)
                    if historical_data:
                        market_conditions['historical_volatility'] = statistics.mean([
                            data['advanced_metrics']['volatility_forecast'] 
                            for data in historical_data[-10:]
                        ])
                    
                    return market_conditions
            
            # 如果没有高级风险控制服务，返回默认条件
            return {
                'risk_score': 0.5,
                'market_regime': 'neutral',
                'volatility': 0.2,
                'drawdown': 0,
                'correlation_breakdown': 0,
                'liquidity_risk': 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取市场条件失败: {e}")
            return {}
    
    async def _get_current_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """获取当前性能指标（优先使用回测结果管理器中的真实交易指标）"""
        market_conditions = await self._get_current_market_conditions()
        risk_score = market_conditions.get('risk_score', 0.5)

        try:
            from core.services.backtest_result_manager import BacktestResultManager
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container and container.is_registered(BacktestResultManager):
                result_mgr = container.resolve(BacktestResultManager)
                if result_mgr:
                    latest_results = result_mgr.query_results(page=1, page_size=1)
                    if latest_results and latest_results[0]:
                        result = latest_results[0][0] if isinstance(latest_results[0], list) else latest_results[0]
                        perf = result.backtest_results.get('performance', {})
                        risk = result.backtest_results.get('risk_metrics', {})
                        if perf or risk:
                            current_time = datetime.now()
                            return_rate = perf.get('total_return', perf.get('cumulative_return', 0.0))
                            sharpe_ratio = perf.get('sharpe_ratio', risk.get('sharpe_ratio', 0.0))
                            max_drawdown = perf.get('max_drawdown', risk.get('max_drawdown', 0.0))
                            win_rate = perf.get('win_rate', risk.get('win_rate', 0.0))
                            volatility = perf.get('volatility', perf.get('annual_volatility', 0.0))
                            avg_trade_return = perf.get('avg_trade_return', perf.get('avg_return', 0.0))

                            return PerformanceMetrics(
                                timestamp=current_time,
                                risk_score=risk_score,
                                return_rate=return_rate,
                                volatility=volatility,
                                sharpe_ratio=sharpe_ratio,
                                max_drawdown=max_drawdown,
                                win_rate=win_rate,
                                avg_trade_return=avg_trade_return
                            )
        except ImportError:
            logger.debug("BacktestResultManager 不可用")
        except Exception as e:
            logger.debug(f"通过 BacktestResultManager 获取性能指标失败: {e}")

        try:
            from core.services.performance_service import PerformanceService
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container:
                perf_service = container.resolve(PerformanceService)
                if perf_service and hasattr(perf_service, 'get_trading_metrics'):
                    metrics = perf_service.get_trading_metrics()
                    if metrics:
                        current_time = datetime.now()

                        return PerformanceMetrics(
                            timestamp=current_time,
                            risk_score=risk_score,
                            return_rate=metrics.get('total_return', 0.0),
                            volatility=metrics.get('annual_volatility', 0.0),
                            sharpe_ratio=metrics.get('sharpe_ratio', 0.0),
                            max_drawdown=metrics.get('max_drawdown', 0.0),
                            win_rate=metrics.get('win_rate', 0.0),
                            avg_trade_return=metrics.get('avg_trade_return', 0.0)
                        )
        except ImportError:
            logger.debug("PerformanceService 不可用")
        except Exception as e:
            logger.debug(f"通过 PerformanceService 获取性能指标失败: {e}")

        logger.warning("无法获取真实性能指标数据，跳过动态风险调整的性能评估")
        return None
    
    def get_current_adjustment_status(self) -> Dict[str, Any]:
        """获取当前调整状态"""
        try:
            status = {
                'is_running': self.is_running,
                'current_params': self.adjustment_engine.current_params.copy(),
                'current_strategy': self.adjustment_engine.current_strategy.value,
                'adjustment_statistics': self.adjustment_engine.get_adjustment_statistics(hours=24),
                'recent_adjustments': len(self.adjustment_engine.adjustment_history),
                'performance_history_size': len(self.adjustment_engine.performance_history)
            }
            
            return status
            
        except Exception as e:
            logger.error(f"获取调整状态失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def force_adjustment(self, adjustments: Dict[str, float], reason: str = "手动调整") -> bool:
        """强制执行参数调整"""
        try:
            # 保存调整前参数
            before_params = self.adjustment_engine.current_params.copy()
            
            # 应用调整
            for param, value in adjustments.items():
                if param in self.adjustment_engine.current_params:
                    self.adjustment_engine.current_params[param] = value
            
            # 记录调整历史
            adjustment_record = AdjustmentHistory(
                timestamp=datetime.now(),
                strategy=AdjustmentStrategy.CONSERVATIVE,  # 手动调整视为保守策略
                trigger=AdjustmentTrigger.TIME_BASED,
                before_params=before_params,
                after_params=self.adjustment_engine.current_params.copy(),
                market_conditions={'reason': reason},
                performance_impact=0.0,
                success=True,
                notes=f"手动调整: {reason}"
            )
            
            self.adjustment_engine.adjustment_history.append(adjustment_record)
            
            logger.info(f"手动参数调整完成: {adjustments}")
            return True
            
        except Exception as e:
            logger.error(f"手动调整失败: {e}")
            return False