import asyncio
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import joblib
import json
import pickle
from utils.safe_pickle import safe_load
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')

from ..risk_control import RiskControlStrategy, RiskMonitor


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MarketRegime(Enum):
    """市场状态"""
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"
    VOLATILE = "volatile"


@dataclass
class AdvancedRiskMetrics:
    """高级风险指标"""
    # 基础风险指标
    var_1d: float = 0.0
    var_5d: float = 0.0
    var_10d: float = 0.0
    expected_shortfall_1d: float = 0.0
    expected_shortfall_5d: float = 0.0
    
    # 高级风险指标
    cvar: float = 0.0  # 条件VaR
    entropic_risk: float = 0.0  # 熵风险度量
    spectral_risk: float = 0.0  # 频谱风险度量
    drawdown_risk: float = 0.0  # 回撤风险
    tail_risk: float = 0.0  # 尾部风险
    
    # 相关性风险
    correlation_breakdown: float = 0.0  # 相关性破裂
    concentration_risk: float = 0.0  # 集中度风险
    
    # 流动性风险
    liquidity_at_risk: float = 0.0  # 流动性风险
    market_impact_cost: float = 0.0  # 市场冲击成本
    
    # 波动率风险
    volatility_forecast: float = 0.0  # 波动率预测
    volatility_skew: float = 0.0  # 波动率偏斜
    
    # 行为金融风险
    herding_risk: float = 0.0  # 羊群效应风险
    sentiment_risk: float = 0.0  # 情绪风险


@dataclass
class MLModelPrediction:
    """机器学习模型预测结果"""
    model_name: str
    prediction: Union[float, List[float]]
    confidence: float
    feature_importance: Optional[Dict[str, float]] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DynamicRiskAdjustment:
    """动态风险调整参数"""
    risk_budget_multiplier: float = 1.0
    position_limit_multiplier: float = 1.0
    stop_loss_adjustment: float = 0.0
    hedge_ratio_adjustment: float = 0.0
    market_regime_adjustment: float = 1.0
    confidence_threshold: float = 0.7


class AdvancedRiskControlService:
    """高级风险控制服务"""
    
    def __init__(self, service_container=None):
        self.service_container = service_container
        self.risk_strategy = RiskControlStrategy()
        self.risk_monitor = RiskMonitor()
        
        # 机器学习模型
        self.ml_models = {}
        self.scalers = {}
        self.model_performance = {}
        
        # 风险数据存储
        self.risk_data_history = []
        self.ml_predictions_cache = {}
        
        # 动态调整参数
        self.dynamic_adjustment = DynamicRiskAdjustment()
        
        # 监控参数
        self.monitoring_interval = 30  # 秒
        self.data_retention_days = 30
        self.alert_thresholds = {
            'risk_score': 0.8,
            'volatility': 0.3,
            'drawdown': 0.15,
            'correlation_breakdown': 0.7
        }
        
        # 初始化机器学习模型
        self._initialize_ml_models()
        
        # 异步监控任务
        self._monitoring_task = None
        self._stop_event = asyncio.Event()
    
    def _initialize_ml_models(self):
        """初始化机器学习模型"""
        try:
            # 1. 异常检测模型 - 用于识别异常市场条件
            self.ml_models['anomaly_detection'] = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_estimators=100
            )
            
            # 2. 风险预测模型 - 用于预测未来风险水平
            self.ml_models['risk_prediction'] = RandomForestRegressor(
                n_estimators=100,
                random_state=42,
                max_depth=10
            )
            
            # 3. 波动率预测模型 - 用于预测波动率
            self.ml_models['volatility_forecast'] = RandomForestRegressor(
                n_estimators=50,
                random_state=42,
                max_depth=8
            )
            
            # 4. 相关性预测模型 - 用于预测相关性变化
            self.ml_models['correlation_forecast'] = RandomForestRegressor(
                n_estimators=50,
                random_state=42,
                max_depth=8
            )
            
            # 5. 数据标准化器
            self.scalers['risk_features'] = StandardScaler()
            self.scalers['market_features'] = StandardScaler()
            
            logger.info("机器学习模型初始化完成")
            
        except Exception as e:
            logger.error(f"初始化机器学习模型失败: {e}")
    
    async def start_monitoring(self):
        """启动异步风险监控"""
        try:
            if self._monitoring_task is None:
                self._stop_event.clear()
                self._monitoring_task = asyncio.create_task(self._monitoring_loop())
                logger.info("高级风险控制监控已启动")
                
        except Exception as e:
            logger.error(f"启动风险监控失败: {e}")
    
    async def stop_monitoring(self):
        """停止异步风险监控"""
        try:
            if self._monitoring_task:
                self._stop_event.set()
                await self._monitoring_task
                self._monitoring_task = None
                logger.info("高级风险控制监控已停止")
                
        except Exception as e:
            logger.error(f"停止风险监控失败: {e}")
    
    async def _monitoring_loop(self):
        """监控循环"""
        while not self._stop_event.is_set():
            try:
                # 执行风险数据收集和处理
                await self._collect_and_process_risk_data()
                
                # 更新机器学习模型
                await self._update_ml_models()
                
                # 执行动态风险调整
                await self._perform_dynamic_adjustments()
                
                # 检查风险告警
                await self._check_risk_alerts()
                
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"风险监控循环异常: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _collect_and_process_risk_data(self):
        try:
            market_data = await self._get_market_data()

            if market_data is None:
                logger.warning("市场数据不可用，跳过本轮风险数据收集")
                return

            basic_risk_metrics = await self._calculate_basic_risk_metrics(market_data)
            
            # 计算高级风险指标
            advanced_risk_metrics = await self._calculate_advanced_risk_metrics(
                market_data, basic_risk_metrics
            )
            
            # 检测市场状态
            market_regime = self._detect_market_regime(market_data, advanced_risk_metrics)
            
            # 组合风险数据
            risk_data = {
                'timestamp': datetime.now(),
                'market_data': market_data,
                'basic_risk_metrics': basic_risk_metrics,
                'advanced_risk_metrics': advanced_risk_metrics,
                'market_regime': market_regime,
                'risk_score': self._calculate_overall_risk_score(advanced_risk_metrics)
            }
            
            # 保存到历史数据
            self.risk_data_history.append(risk_data)
            
            # 清理过期数据
            cutoff_date = datetime.now() - timedelta(days=self.data_retention_days)
            self.risk_data_history = [
                data for data in self.risk_data_history 
                if data['timestamp'] > cutoff_date
            ]
            
        except Exception as e:
            logger.error(f"收集风险数据失败: {e}")
    
    async def _get_market_data(self) -> Optional[Dict[str, Any]]:
        try:
            if self.service_container and hasattr(self.service_container, 'get_market_data_service'):
                market_service = self.service_container.get_market_data_service()
                if market_service and hasattr(market_service, 'get_current_market_data'):
                    data = await market_service.get_current_market_data()
                    if data:
                        return data

            if self.service_container and hasattr(self.service_container, 'data_provider'):
                provider = self.service_container.data_provider
                if hasattr(provider, 'get_realtime_quotes'):
                    quotes = await provider.get_realtime_quotes()
                    if quotes:
                        return self._transform_quotes_to_market_data(quotes)

            logger.warning("无法获取真实市场数据，跳过本轮风险分析")
            return None

        except Exception as e:
            logger.error(f"获取市场数据失败: {e}")
            return None

    def _transform_quotes_to_market_data(self, quotes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        prices = [q.get('price', 0.0) for q in quotes if q.get('price') is not None]
        volumes = [q.get('volume', 0.0) for q in quotes if q.get('volume') is not None]
        volatilities = [q.get('volatility', q.get('amplitude', 0.0)) for q in quotes]

        if not prices:
            return None

        return {
            'timestamp': datetime.now(),
            'prices': prices,
            'volumes': volumes if volumes else [0.0] * len(prices),
            'volatilities': volatilities if volatilities else [0.0] * len(prices),
            'indices': {}
        }
    
    async def _calculate_basic_risk_metrics(self, market_data: Dict[str, Any]) -> Dict[str, float]:
        """计算基础风险指标"""
        try:
            prices = market_data.get('prices', [])
            if not prices:
                return {}
            
            # 计算收益率
            returns = np.diff(np.log(prices))
            
            # 计算VaR
            var_1d = np.percentile(returns, 5)
            var_5d = np.percentile(returns, 5) * np.sqrt(5)
            var_10d = np.percentile(returns, 5) * np.sqrt(10)
            
            # 计算ES (Expected Shortfall)
            es_1d = returns[returns <= var_1d].mean()
            es_5d = returns[returns <= var_5d].mean()
            
            basic_metrics = {
                'var_1d': var_1d,
                'var_5d': var_5d,
                'var_10d': var_10d,
                'expected_shortfall_1d': es_1d,
                'expected_shortfall_5d': es_5d,
                'volatility': np.std(returns),
                'skewness': float(pd.Series(returns).skew()),
                'kurtosis': float(pd.Series(returns).kurtosis())
            }
            
            return basic_metrics
            
        except Exception as e:
            logger.error(f"计算基础风险指标失败: {e}")
            return {}
    
    async def _calculate_advanced_risk_metrics(self, market_data: Dict[str, Any], 
                                             basic_metrics: Dict[str, float]) -> AdvancedRiskMetrics:
        """计算高级风险指标"""
        try:
            prices = market_data.get('prices', [])
            returns = np.diff(np.log(prices)) if len(prices) > 1 else [0]
            
            advanced_metrics = AdvancedRiskMetrics()
            
            # CVaR (条件VaR)
            var_1d = basic_metrics.get('var_1d', 0)
            tail_returns = returns[returns <= var_1d]
            advanced_metrics.cvar = tail_returns.mean() if len(tail_returns) > 0 else 0
            
            # 熵风险度量
            returns_series = pd.Series(returns)
            prob_dist = returns_series.value_counts(normalize=True).sort_index()
            if len(prob_dist) > 0:
                entropy = -sum(p * np.log(p + 1e-10) for p in prob_dist)
                advanced_metrics.entropic_risk = entropy
            else:
                advanced_metrics.entropic_risk = 0
            
            # 频谱风险度量
            weights = np.linspace(0.1, 1.0, len(returns))
            sorted_returns = np.sort(returns)
            advanced_metrics.spectral_risk = np.sum(weights * sorted_returns) / np.sum(weights)
            
            # 回撤风险
            cumulative_returns = np.cumprod(1 + returns)
            peak = np.maximum.accumulate(cumulative_returns)
            drawdown = (cumulative_returns - peak) / peak
            advanced_metrics.drawdown_risk = np.min(drawdown)
            
            # 尾部风险
            tail_5pct = np.percentile(returns, 5)
            tail_returns = returns[returns <= tail_5pct]
            advanced_metrics.tail_risk = np.std(tail_returns)
            
            # 相关性破裂
            if len(prices) > 2:
                try:
                    correlation_matrix = np.corrcoef(np.array(prices).reshape(-1, 1).T)
                    avg_correlation = np.mean(correlation_matrix[np.triu_indices_from(correlation_matrix, k=1)])
                    advanced_metrics.correlation_breakdown = 1 - avg_correlation
                except Exception:
                    advanced_metrics.correlation_breakdown = 0
            else:
                advanced_metrics.correlation_breakdown = 0
            
            # 流动性风险
            volumes = market_data.get('volumes', [])
            if volumes:
                avg_volume = np.mean(volumes)
                volume_volatility = np.std(volumes) / avg_volume
                advanced_metrics.liquidity_at_risk = volume_volatility
            
            # 市场冲击成本
            if len(volumes) > 0 and len(prices) > 1:
                price_changes = np.abs(np.diff(prices))
                avg_volume = np.mean(volumes)
                advanced_metrics.market_impact_cost = np.mean(price_changes) / avg_volume
            
            # 波动率预测
            volatility = basic_metrics.get('volatility', 0)
            advanced_metrics.volatility_forecast = volatility * 1.1  # 简单的预测
            
            # 波动率偏斜
            returns_df = pd.DataFrame({'returns': returns})
            if len(returns_df) > 10:
                skew_left = returns_df[returns_df['returns'] < 0]['returns'].skew()
                skew_right = returns_df[returns_df['returns'] > 0]['returns'].skew()
                advanced_metrics.volatility_skew = abs(skew_left - skew_right)
            else:
                advanced_metrics.volatility_skew = 0
            
            # 行为金融风险指标
            advanced_metrics.herding_risk = self._calculate_herding_risk(market_data)
            advanced_metrics.sentiment_risk = self._calculate_sentiment_risk(market_data)
            
            return advanced_metrics
            
        except Exception as e:
            logger.error(f"计算高级风险指标失败: {e}")
            return AdvancedRiskMetrics()
    
    def _calculate_herding_risk(self, market_data: Dict[str, Any]) -> float:
        """计算羊群效应风险"""
        try:
            prices = market_data.get('prices', [])
            volumes = market_data.get('volumes', [])
            
            if len(prices) < 2 or len(volumes) < 2:
                return 0.0
            
            # 计算价格和成交量的相关性
            try:
                correlation = np.corrcoef(prices[:-1], volumes[1:])[0, 1]
                # 羊群效应：价格变动与成交量高度相关
                herding_indicator = abs(correlation)
                return min(herding_indicator, 1.0)
            except Exception:
                return 0.0
            
        except Exception as e:
            logger.error(f"计算羊群效应风险失败: {e}")
            return 0.0
    
    def _calculate_sentiment_risk(self, market_data: Dict[str, Any]) -> float:
        """计算情绪风险"""
        try:
            prices = market_data.get('prices', [])
            volatilities = market_data.get('volatilities', [])
            
            if len(prices) < 3 or len(volatilities) < 3:
                return 0.0
            
            # 价格动量
            momentum = (prices[-1] - prices[-3]) / prices[-3]
            
            # 波动率变化
            vol_change = (volatilities[-1] - volatilities[-3]) / volatilities[-3]
            
            # 情绪指标：动量与波动率变化的组合
            sentiment_indicator = abs(momentum * vol_change)
            
            return min(sentiment_indicator, 1.0)
            
        except Exception as e:
            logger.error(f"计算情绪风险失败: {e}")
            return 0.0
    
    def _detect_market_regime(self, market_data: Dict[str, Any], 
                            advanced_metrics: AdvancedRiskMetrics) -> MarketRegime:
        """检测市场状态"""
        try:
            volatility = advanced_metrics.volatility_forecast
            drawdown = advanced_metrics.drawdown_risk
            correlation_breakdown = advanced_metrics.correlation_breakdown
            
            # 基于多个指标判断市场状态
            if volatility > 0.3 or drawdown < -0.1:
                return MarketRegime.VOLATILE
            elif drawdown < -0.05:
                return MarketRegime.BEAR
            elif correlation_breakdown > 0.7:
                return MarketRegime.BEAR
            elif volatility < 0.15 and drawdown > -0.02:
                return MarketRegime.BULL
            else:
                return MarketRegime.NEUTRAL
                
        except Exception as e:
            logger.error(f"检测市场状态失败: {e}")
            return MarketRegime.NEUTRAL
    
    def _calculate_overall_risk_score(self, advanced_metrics: AdvancedRiskMetrics) -> float:
        """计算综合风险评分"""
        try:
            # 各风险指标的权重
            weights = {
                'cvar': 0.15,
                'drawdown_risk': 0.15,
                'tail_risk': 0.10,
                'correlation_breakdown': 0.10,
                'liquidity_at_risk': 0.10,
                'volatility_forecast': 0.10,
                'herding_risk': 0.10,
                'sentiment_risk': 0.10,
                'entropic_risk': 0.05,
                'spectral_risk': 0.05
            }
            
            # 归一化风险指标
            risk_values = {
                'cvar': abs(advanced_metrics.cvar),
                'drawdown_risk': abs(advanced_metrics.drawdown_risk),
                'tail_risk': advanced_metrics.tail_risk,
                'correlation_breakdown': advanced_metrics.correlation_breakdown,
                'liquidity_at_risk': advanced_metrics.liquidity_at_risk,
                'volatility_forecast': advanced_metrics.volatility_forecast,
                'herding_risk': advanced_metrics.herding_risk,
                'sentiment_risk': advanced_metrics.sentiment_risk,
                'entropic_risk': advanced_metrics.entropic_risk,
                'spectral_risk': abs(advanced_metrics.spectral_risk)
            }
            
            # 计算加权风险评分
            total_score = sum(weights[key] * min(risk_values[key], 1.0) 
                            for key in weights.keys())
            
            return min(total_score, 1.0)
            
        except Exception as e:
            logger.error(f"计算综合风险评分失败: {e}")
            return 0.5
    
    async def _update_ml_models(self):
        """更新机器学习模型"""
        try:
            # 只有当有足够的历史数据时才更新模型
            if len(self.risk_data_history) < 50:
                return
            
            # 准备训练数据
            X, y = self._prepare_training_data()
            
            if len(X) < 20:  # 需要足够的训练样本
                return
            
            # 分割训练和测试数据
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # 标准化特征
            X_train_scaled = self.scalers['risk_features'].fit_transform(X_train)
            X_test_scaled = self.scalers['risk_features'].transform(X_test)
            
            # 更新风险预测模型
            if 'risk_prediction' in self.ml_models:
                self.ml_models['risk_prediction'].fit(X_train_scaled, y_train)
                
                # 评估模型性能
                train_score = self.ml_models['risk_prediction'].score(X_train_scaled, y_train)
                test_score = self.ml_models['risk_prediction'].score(X_test_scaled, y_test)
                
                self.model_performance['risk_prediction'] = {
                    'train_score': train_score,
                    'test_score': test_score
                }
            
            # 更新波动率预测模型
            volatility_y = [data['advanced_risk_metrics'].volatility_forecast 
                           for data in self.risk_data_history[-50:]]
            if len(volatility_y) > 20:
                self.ml_models['volatility_forecast'].fit(X_train_scaled, volatility_y[:len(X_train)])
            
            logger.info("机器学习模型更新完成")
            
        except Exception as e:
            logger.error(f"更新机器学习模型失败: {e}")
    
    def _prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """准备训练数据"""
        try:
            features = []
            targets = []
            
            # 使用最近的数据点
            recent_data = self.risk_data_history[-100:]
            
            for data in recent_data:
                feature_vector = [
                    data['basic_risk_metrics'].get('volatility', 0),
                    data['basic_risk_metrics'].get('var_1d', 0),
                    data['basic_risk_metrics'].get('skewness', 0),
                    data['basic_risk_metrics'].get('kurtosis', 0),
                    data['advanced_risk_metrics'].drawdown_risk,
                    data['advanced_risk_metrics'].correlation_breakdown,
                    data['advanced_risk_metrics'].liquidity_at_risk,
                    data['advanced_risk_metrics'].herding_risk,
                    data['advanced_risk_metrics'].sentiment_risk
                ]
                
                features.append(feature_vector)
                
                # 目标变量：下一期的综合风险评分
                # 这里简化为当前的风险评分
                targets.append(data['risk_score'])
            
            return np.array(features), np.array(targets)
            
        except Exception as e:
            logger.error(f"准备训练数据失败: {e}")
            return np.array([]), np.array([])
    
    async def _perform_dynamic_adjustments(self):
        """执行动态风险调整"""
        try:
            if not self.risk_data_history:
                return
            
            latest_data = self.risk_data_history[-1]
            risk_score = latest_data['risk_score']
            market_regime = latest_data['market_regime']
            advanced_metrics = latest_data['advanced_risk_metrics']
            
            # 基于风险评分调整参数
            if risk_score > 0.8:  # 高风险
                self.dynamic_adjustment.risk_budget_multiplier = 0.7
                self.dynamic_adjustment.position_limit_multiplier = 0.8
                self.dynamic_adjustment.stop_loss_adjustment = 0.02  # 收紧2%
            elif risk_score > 0.6:  # 中等风险
                self.dynamic_adjustment.risk_budget_multiplier = 0.85
                self.dynamic_adjustment.position_limit_multiplier = 0.9
                self.dynamic_adjustment.stop_loss_adjustment = 0.01  # 收紧1%
            elif risk_score < 0.3:  # 低风险
                self.dynamic_adjustment.risk_budget_multiplier = 1.2
                self.dynamic_adjustment.position_limit_multiplier = 1.1
                self.dynamic_adjustment.stop_loss_adjustment = -0.01  # 放宽1%
            else:  # 正常风险
                self.dynamic_adjustment.risk_budget_multiplier = 1.0
                self.dynamic_adjustment.position_limit_multiplier = 1.0
                self.dynamic_adjustment.stop_loss_adjustment = 0.0
            
            # 基于市场状态调整参数
            if market_regime == MarketRegime.VOLATILE:
                self.dynamic_adjustment.market_regime_adjustment = 0.6
                self.dynamic_adjustment.hedge_ratio_adjustment = 0.2
            elif market_regime == MarketRegime.BEAR:
                self.dynamic_adjustment.market_regime_adjustment = 0.8
                self.dynamic_adjustment.hedge_ratio_adjustment = 0.1
            elif market_regime == MarketRegime.BULL:
                self.dynamic_adjustment.market_regime_adjustment = 1.1
                self.dynamic_adjustment.hedge_ratio_adjustment = -0.1
            else:  # NEUTRAL
                self.dynamic_adjustment.market_regime_adjustment = 1.0
                self.dynamic_adjustment.hedge_ratio_adjustment = 0.0
            
            # 基于流动性风险调整
            if advanced_metrics.liquidity_at_risk > 0.3:
                self.dynamic_adjustment.position_limit_multiplier *= 0.9
            
            logger.info(f"动态风险调整完成: 风险评分={risk_score:.3f}, 市场状态={market_regime.value}")
            
        except Exception as e:
            logger.error(f"执行动态风险调整失败: {e}")
    
    async def _check_risk_alerts(self):
        """检查风险告警"""
        try:
            if not self.risk_data_history:
                return
            
            latest_data = self.risk_data_history[-1]
            risk_score = latest_data['risk_score']
            advanced_metrics = latest_data['advanced_risk_metrics']
            
            alerts = []
            
            # 检查综合风险评分
            if risk_score > self.alert_thresholds['risk_score']:
                alerts.append({
                    'type': 'high_risk_score',
                    'level': 'critical' if risk_score > 0.9 else 'high',
                    'message': f'综合风险评分过高: {risk_score:.3f}',
                    'value': risk_score,
                    'threshold': self.alert_thresholds['risk_score']
                })
            
            # 检查波动率
            if advanced_metrics.volatility_forecast > self.alert_thresholds['volatility']:
                alerts.append({
                    'type': 'high_volatility',
                    'level': 'high',
                    'message': f'预测波动率过高: {advanced_metrics.volatility_forecast:.3f}',
                    'value': advanced_metrics.volatility_forecast,
                    'threshold': self.alert_thresholds['volatility']
                })
            
            # 检查回撤风险
            if advanced_metrics.drawdown_risk < -self.alert_thresholds['drawdown']:
                alerts.append({
                    'type': 'high_drawdown',
                    'level': 'critical',
                    'message': f'回撤风险过高: {advanced_metrics.drawdown_risk:.3f}',
                    'value': advanced_metrics.drawdown_risk,
                    'threshold': -self.alert_thresholds['drawdown']
                })
            
            # 检查相关性破裂
            if advanced_metrics.correlation_breakdown > self.alert_thresholds['correlation_breakdown']:
                alerts.append({
                    'type': 'correlation_breakdown',
                    'level': 'high',
                    'message': f'相关性破裂风险过高: {advanced_metrics.correlation_breakdown:.3f}',
                    'value': advanced_metrics.correlation_breakdown,
                    'threshold': self.alert_thresholds['correlation_breakdown']
                })
            
            # 记录告警
            for alert in alerts:
                logger.warning(f"风险告警: {alert['message']}")
            
        except Exception as e:
            logger.error(f"检查风险告警失败: {e}")
    
    def get_current_risk_assessment(self) -> Dict[str, Any]:
        """获取当前风险评估"""
        try:
            if not self.risk_data_history:
                return {'status': 'no_data'}
            
            latest_data = self.risk_data_history[-1]
            
            assessment = {
                'status': 'success',
                'timestamp': latest_data['timestamp'].isoformat(),
                'risk_score': latest_data['risk_score'],
                'risk_level': self._get_risk_level(latest_data['risk_score']),
                'market_regime': latest_data['market_regime'].value,
                'dynamic_adjustments': {
                    'risk_budget_multiplier': self.dynamic_adjustment.risk_budget_multiplier,
                    'position_limit_multiplier': self.dynamic_adjustment.position_limit_multiplier,
                    'stop_loss_adjustment': self.dynamic_adjustment.stop_loss_adjustment,
                    'hedge_ratio_adjustment': self.dynamic_adjustment.hedge_ratio_adjustment,
                    'market_regime_adjustment': self.dynamic_adjustment.market_regime_adjustment
                },
                'advanced_metrics': {
                    'cvar': latest_data['advanced_risk_metrics'].cvar,
                    'drawdown_risk': latest_data['advanced_risk_metrics'].drawdown_risk,
                    'tail_risk': latest_data['advanced_risk_metrics'].tail_risk,
                    'correlation_breakdown': latest_data['advanced_risk_metrics'].correlation_breakdown,
                    'liquidity_at_risk': latest_data['advanced_risk_metrics'].liquidity_at_risk,
                    'volatility_forecast': latest_data['advanced_risk_metrics'].volatility_forecast,
                    'herding_risk': latest_data['advanced_risk_metrics'].herding_risk,
                    'sentiment_risk': latest_data['advanced_risk_metrics'].sentiment_risk
                },
                'model_performance': self.model_performance
            }
            
            return assessment
            
        except Exception as e:
            logger.error(f"获取当前风险评估失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _get_risk_level(self, risk_score: float) -> str:
        """根据风险评分确定风险等级"""
        if risk_score >= 0.8:
            return RiskLevel.CRITICAL.value
        elif risk_score >= 0.6:
            return RiskLevel.HIGH.value
        elif risk_score >= 0.3:
            return RiskLevel.MEDIUM.value
        else:
            return RiskLevel.LOW.value
    
    async def predict_risk_level(self, time_horizon: int = 1) -> Optional[MLModelPrediction]:
        """预测未来风险水平"""
        try:
            if 'risk_prediction' not in self.ml_models or len(self.risk_data_history) < 20:
                return None
            
            # 准备预测数据
            latest_data = self.risk_data_history[-1]
            feature_vector = [
                latest_data['basic_risk_metrics'].get('volatility', 0),
                latest_data['basic_risk_metrics'].get('var_1d', 0),
                latest_data['basic_risk_metrics'].get('skewness', 0),
                latest_data['basic_risk_metrics'].get('kurtosis', 0),
                latest_data['advanced_risk_metrics'].drawdown_risk,
                latest_data['advanced_risk_metrics'].correlation_breakdown,
                latest_data['advanced_risk_metrics'].liquidity_at_risk,
                latest_data['advanced_risk_metrics'].herding_risk,
                latest_data['advanced_risk_metrics'].sentiment_risk
            ]
            
            # 标准化特征
            X_scaled = self.scalers['risk_features'].transform([feature_vector])
            
            # 进行预测
            prediction = self.ml_models['risk_prediction'].predict(X_scaled)[0]
            
            # 计算置信度
            train_score = self.model_performance.get('risk_prediction', {}).get('test_score', 0.5)
            confidence = max(0.1, min(0.95, train_score))
            
            # 获取特征重要性
            feature_importance = dict(zip(
                ['volatility', 'var_1d', 'skewness', 'kurtosis', 'drawdown_risk', 
                 'correlation_breakdown', 'liquidity_risk', 'herding_risk', 'sentiment_risk'],
                self.ml_models['risk_prediction'].feature_importances_
            ))
            
            return MLModelPrediction(
                model_name='risk_prediction',
                prediction=prediction,
                confidence=confidence,
                feature_importance=feature_importance
            )
            
        except Exception as e:
            logger.error(f"预测风险水平失败: {e}")
            return None
    
    def export_risk_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """导出风险数据"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            exported_data = []
            for data in self.risk_data_history:
                if data['timestamp'] >= cutoff_time:
                    exported_data.append({
                        'timestamp': data['timestamp'].isoformat(),
                        'risk_score': data['risk_score'],
                        'market_regime': data['market_regime'].value,
                        'basic_metrics': data['basic_risk_metrics'],
                        'advanced_metrics': {
                            'cvar': data['advanced_risk_metrics'].cvar,
                            'drawdown_risk': data['advanced_risk_metrics'].drawdown_risk,
                            'tail_risk': data['advanced_risk_metrics'].tail_risk,
                            'correlation_breakdown': data['advanced_risk_metrics'].correlation_breakdown,
                            'liquidity_at_risk': data['advanced_risk_metrics'].liquidity_at_risk,
                            'volatility_forecast': data['advanced_risk_metrics'].volatility_forecast,
                            'herding_risk': data['advanced_risk_metrics'].herding_risk,
                            'sentiment_risk': data['advanced_risk_metrics'].sentiment_risk
                        }
                    })
            
            return exported_data
            
        except Exception as e:
            logger.error(f"导出风险数据失败: {e}")
            return []
    
    def update_alert_thresholds(self, new_thresholds: Dict[str, float]):
        """更新告警阈值"""
        try:
            for key, value in new_thresholds.items():
                if key in self.alert_thresholds:
                    self.alert_thresholds[key] = value
                    logger.info(f"更新告警阈值 {key}: {value}")
            
        except Exception as e:
            logger.error(f"更新告警阈值失败: {e}")
    
    def get_model_performance(self) -> Dict[str, Any]:
        """获取模型性能"""
        return self.model_performance.copy()
    
    def save_models(self, filepath: str):
        """保存机器学习模型"""
        try:
            model_data = {
                'models': self.ml_models,
                'scalers': self.scalers,
                'model_performance': self.model_performance,
                'dynamic_adjustment': self.dynamic_adjustment
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"机器学习模型已保存到: {filepath}")
            
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
    
    def load_models(self, filepath: str):
        """加载机器学习模型"""
        try:
            with open(filepath, 'rb') as f:
                model_data = safe_load(f)
            
            self.ml_models = model_data.get('models', {})
            self.scalers = model_data.get('scalers', {})
            self.model_performance = model_data.get('model_performance', {})
            self.dynamic_adjustment = model_data.get('dynamic_adjustment', DynamicRiskAdjustment())
            
            logger.info(f"机器学习模型已从 {filepath} 加载")
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")