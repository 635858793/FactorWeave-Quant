"""
BettaFish风险评估Agent
专门处理股票风险评估和风险控制
"""

import asyncio
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from core.services.base_service import BaseService

class RiskLevel(Enum):
    """风险等级"""
    VERY_LOW = "very_low"        # 极低风险
    LOW = "low"                  # 低风险
    MEDIUM = "medium"            # 中等风险
    HIGH = "high"                # 高风险
    VERY_HIGH = "very_high"      # 极高风险

class RiskType(Enum):
    """风险类型"""
    MARKET_RISK = "market_risk"          # 市场风险
    VOLATILITY_RISK = "volatility_risk"  # 波动性风险
    LIQUIDITY_RISK = "liquidity_risk"    # 流动性风险
    CREDIT_RISK = "credit_risk"          # 信用风险
    OPERATIONAL_RISK = "operational_risk" # 操作风险
    CONCENTRATION_RISK = "concentration_risk" # 集中度风险

@dataclass
class RiskMetric:
    """风险指标"""
    name: str
    value: float
    risk_level: RiskLevel
    description: str
    threshold: float
    current_vs_threshold: float
    confidence: float = 1.0

@dataclass
class RiskAlert:
    """风险警报"""
    risk_type: RiskType
    level: RiskLevel
    message: str
    timestamp: datetime
    action_required: bool

@dataclass
class RiskAssessmentResult:
    """风险评估结果"""
    stock_code: str
    assessment_time: datetime
    overall_risk_level: RiskLevel
    risk_score: float  # 0-100, 越高风险越大
    risk_metrics: List[RiskMetric]
    risk_alerts: List[RiskAlert]
    risk_decomposition: Dict[str, float]
    var_estimate: Optional[float]  # Value at Risk
    recommendations: List[str]
    confidence: float

class RiskAssessmentAgent(BaseService):
    """风险评估Agent"""
    
    def __init__(self, event_bus: Optional[Any] = None):
        super().__init__(event_bus)
        
        # 风险评估配置
        self.config = {
            "var_confidence_level": 0.95,  # VaR置信水平
            "volatility_window": 30,        # 波动率计算窗口
            "correlation_window": 60,       # 相关性计算窗口
            "min_data_points": 100,         # 最少数据点
            "risk_thresholds": {
                "volatility": 0.03,        # 3%日波动率阈值
                "beta": 1.5,                # Beta阈值
                "sharpe_ratio": 0.5,        # 夏普比率阈值
                "max_drawdown": 0.2,        # 最大回撤阈值
                "var_threshold": 0.05       # VaR阈值
            }
        }
        
        # 缓存
        self._risk_cache = {}
        self._cache_ttl = 1800  # 30分钟

        # 数据状态
        self.has_real_data = False
        
        # 性能统计
        self._stats = {
            "total_assessments": 0,
            "cache_hits": 0,
            "avg_processing_time": 0.0,
            "high_risk_alerts": 0
        }

    async def assess_stock_risk(self, stock_code: str, 
                              context: Dict[str, Any] = None) -> Dict[str, Any]:
        """评估指定股票的风险"""
        start_time = time.time()
        context = context or {}
        
        try:
            logger.debug(f"开始风险评估: {stock_code}")
            
            # 检查缓存
            cache_key = f"risk_assessment_{stock_code}_{int(time.time() // self._cache_ttl)}"
            if cache_key in self._risk_cache:
                self._stats["cache_hits"] += 1
                logger.debug(f"风险评估缓存命中: {stock_code}")
                return self._risk_cache[cache_key]
            
            # 获取价格和基本面数据
            price_data = await self._get_price_data(stock_code, context)
            fundamental_data = await self._get_fundamental_data(stock_code, context)
            
            if price_data is None or len(price_data) < self.config["min_data_points"]:
                logger.warning(f"{stock_code}价格数据不足，无法进行风险评估")
                return {
                    "status": "insufficient_data",
                    "message": "价格数据不足，无法进行风险评估",
                    "stock_code": stock_code
                }
            
            # 计算各类风险指标
            risk_metrics = await self._calculate_risk_metrics(price_data, fundamental_data)
            
            # 识别风险警报
            risk_alerts = self._identify_risk_alerts(risk_metrics)
            
            # 分解风险来源
            risk_decomposition = self._decompose_risks(risk_metrics)
            
            # 计算VaR
            var_estimate = await self._calculate_var(price_data)
            
            # 确定总体风险等级
            overall_risk_level = self._determine_overall_risk(risk_metrics, risk_alerts)
            risk_score = self._calculate_risk_score(risk_metrics)
            
            # 生成建议
            recommendations = self._generate_risk_recommendations(risk_metrics, risk_alerts, overall_risk_level)
            
            # 构建评估结果
            assessment_result = RiskAssessmentResult(
                stock_code=stock_code,
                assessment_time=datetime.now(),
                overall_risk_level=overall_risk_level,
                risk_score=risk_score,
                risk_metrics=risk_metrics,
                risk_alerts=risk_alerts,
                risk_decomposition=risk_decomposition,
                var_estimate=var_estimate,
                recommendations=recommendations,
                confidence=min(0.9, self._calculate_confidence(risk_metrics))
            )
            
            # 更新统计
            self._stats["total_assessments"] += 1
            self._stats["high_risk_alerts"] += len([alert for alert in risk_alerts 
                                                  if alert.level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]])
            
            # 缓存结果
            self._risk_cache[cache_key] = {
                "status": "success",
                "assessment_result": assessment_result
            }
            
            processing_time = time.time() - start_time
            self._update_processing_stats(processing_time)
            
            logger.info(f"风险评估完成: {stock_code}, 风险等级: {overall_risk_level.value}, 耗时: {processing_time:.2f}s")
            
            return self._risk_cache[cache_key]
            
        except Exception as e:
            logger.error(f"风险评估失败: {stock_code}, 错误: {str(e)}")
            return {
                "status": "error",
                "message": f"风险评估失败: {str(e)}",
                "stock_code": stock_code
            }

    async def analyze_stock(self, stock_code: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """分析单只股票的风险 - 兼容BettaFish Agent调用接口"""
        try:
            result = await self.assess_stock_risk(stock_code, context)
            if result.get("status") == "success" and "assessment_result" in result:
                assessment = result["assessment_result"]
                return {
                    "status": "success",
                    "stock_code": stock_code,
                    "risk_level": assessment.overall_risk_level.value,
                    "risk_score": assessment.risk_score,
                    "confidence": assessment.confidence,
                    "assessment_result": assessment,
                    "recommendations": assessment.recommendations,
                    "var_estimate": assessment.var_estimate,
                    "risk_alerts": assessment.risk_alerts
                }
            return result
        except Exception as e:
            logger.error(f"风险分析失败: {stock_code}, 错误: {str(e)}")
            return {
                "stock_code": stock_code,
                "risk_level": "UNKNOWN",
                "error": str(e),
                "status": "error"
            }

    async def _get_price_data(self, stock_code: str, 
                            context: Dict[str, Any] = None) -> Optional[pd.DataFrame]:
        """获取价格数据 - 仅从真实数据源获取"""
        try:
            df = await self._fetch_real_price_data(stock_code)
            if df is not None and not df.empty and len(df) >= self.config["min_data_points"]:
                self.has_real_data = True
                logger.info(f"成功从真实数据源获取{stock_code}风险价格数据: {len(df)}条")
                return df
            self.has_real_data = False
            logger.warning(f"真实数据源无{stock_code}数据或数据不足(需要>={self.config['min_data_points']}条)，跳过风险评估")
            return None
        except Exception as e:
            self.has_real_data = False
            logger.warning(f"获取价格数据失败({stock_code}): {str(e)}")
            return None

    async def _fetch_real_price_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """从真实数据源获取K线价格数据"""
        df = None
        try:
            from core.services.unified_data_manager import get_unified_data_manager
            data_manager = get_unified_data_manager()
            if data_manager:
                df = data_manager.get_kdata(stock_code, period='D', count=self.config["min_data_points"] + 100)
                if df is not None and not df.empty:
                    expected_cols = {'open', 'high', 'low', 'close', 'volume'}
                    if expected_cols.issubset(set(col.lower() for col in df.columns)):
                        rename_map = {col: col.lower() for col in df.columns}
                        df = df.rename(columns=rename_map)
                    return df
        except ImportError:
            logger.debug("UnifiedDataManager 不可用，尝试 StockService")
        except Exception as e:
            logger.debug(f"UnifiedDataManager 获取数据失败: {e}")

        try:
            from core.services.stock_service import StockService
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container:
                stock_service = container.resolve(StockService)
            else:
                stock_service = None
            if stock_service and hasattr(stock_service, 'get_kdata'):
                df = stock_service.get_kdata(stock_code, period='D', count=self.config["min_data_points"] + 100)
                if df is not None and not df.empty:
                    expected_cols = {'open', 'high', 'low', 'close', 'volume'}
                    if expected_cols.issubset(set(col.lower() for col in df.columns)):
                        rename_map = {col: col.lower() for col in df.columns}
                        df = df.rename(columns=rename_map)
                    return df
        except ImportError:
            logger.debug("StockService 不可用")
        except Exception as e:
            logger.debug(f"StockService 获取数据失败: {e}")

        return df

    async def _get_fundamental_data(self, stock_code: str, 
                                  context: Dict[str, Any] = None) -> Dict[str, Any]:
        """获取基本面数据"""
        try:
            from core.services.stock_service import StockService
            from core.containers.service_container import get_service_container
            container = get_service_container()
            if container:
                stock_service = container.resolve(StockService)
                if stock_service and hasattr(stock_service, 'get_stock_info'):
                    info = stock_service.get_stock_info(stock_code)
                    if info and isinstance(info, dict):
                        return {
                            "market_cap": info.get("market_cap"),
                            "pe_ratio": info.get("pe_ratio"),
                            "pb_ratio": info.get("pb_ratio"),
                            "debt_ratio": info.get("debt_ratio"),
                            "current_ratio": info.get("current_ratio"),
                            "roe": info.get("roe"),
                            "revenue_growth": info.get("revenue_growth"),
                            "profit_growth": info.get("profit_growth"),
                            "industry": info.get("industry", "unknown"),
                            "listing_age": info.get("listing_age")
                        }
        except ImportError:
            logger.debug("StockService 不可用，无法获取基本面数据")
        except Exception as e:
            logger.debug(f"获取基本面数据失败: {e}")
        
        logger.warning(f"{stock_code}: 无法从真实数据源获取基本面数据")
        return {}

    async def _calculate_risk_metrics(self, price_data: pd.DataFrame, 
                                    fundamental_data: Dict[str, Any]) -> List[RiskMetric]:
        """计算风险指标"""
        metrics = []
        
        try:
            close = price_data['close']
            returns = close.pct_change().dropna()
            
            # 1. 波动率风险
            volatility = returns.std() * np.sqrt(252)  # 年化波动率
            volatility_metric = self._create_volatility_metric(volatility)
            metrics.append(volatility_metric)
            
            # 2. Beta风险
            beta = await self._calculate_beta(returns)
            beta_metric = self._create_beta_metric(beta)
            metrics.append(beta_metric)
            
            # 3. 最大回撤
            max_drawdown = self._calculate_max_drawdown(close)
            drawdown_metric = self._create_drawdown_metric(max_drawdown)
            metrics.append(drawdown_metric)
            
            # 4. 夏普比率
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            sharpe_metric = self._create_sharpe_metric(sharpe_ratio)
            metrics.append(sharpe_metric)
            
            # 5. 流动性风险
            liquidity_metric = self._calculate_liquidity_risk(price_data)
            metrics.append(liquidity_metric)
            
            # 6. 集中度风险
            concentration_metric = self._calculate_concentration_risk(fundamental_data)
            metrics.append(concentration_metric)
            
            # 7. 信用风险（基于基本面）
            credit_metric = self._calculate_credit_risk(fundamental_data)
            metrics.append(credit_metric)
            
            # 8. 市场风险
            market_metric = self._calculate_market_risk(returns, fundamental_data)
            metrics.append(market_metric)
            
            logger.debug(f"计算了{len(metrics)}个风险指标")
            return metrics
            
        except Exception as e:
            logger.error(f"计算风险指标失败: {str(e)}")
            return []

    def _create_volatility_metric(self, volatility: float) -> RiskMetric:
        """创建波动率风险指标"""
        threshold = self.config["risk_thresholds"]["volatility"]
        
        if volatility < threshold * 0.5:
            level = RiskLevel.LOW
        elif volatility < threshold:
            level = RiskLevel.MEDIUM
        elif volatility < threshold * 1.5:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.VERY_HIGH
        
        return RiskMetric(
            name="Volatility",
            value=volatility,
            risk_level=level,
            description=f"年化波动率: {volatility:.2%}",
            threshold=threshold,
            current_vs_threshold=volatility / threshold
        )

    def _create_beta_metric(self, beta: float) -> RiskMetric:
        """创建Beta风险指标"""
        threshold = self.config["risk_thresholds"]["beta"]
        
        if beta < 0.8:
            level = RiskLevel.LOW
        elif beta < threshold:
            level = RiskLevel.MEDIUM
        elif beta < 1.8:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.VERY_HIGH
        
        return RiskMetric(
            name="Beta",
            value=beta,
            risk_level=level,
            description=f"Beta系数: {beta:.2f}",
            threshold=threshold,
            current_vs_threshold=beta / threshold
        )

    def _create_drawdown_metric(self, max_drawdown: float) -> RiskMetric:
        """创建最大回撤风险指标"""
        threshold = self.config["risk_thresholds"]["max_drawdown"]
        
        if max_drawdown < threshold * 0.5:
            level = RiskLevel.LOW
        elif max_drawdown < threshold:
            level = RiskLevel.MEDIUM
        elif max_drawdown < threshold * 1.3:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.VERY_HIGH
        
        return RiskMetric(
            name="MaxDrawdown",
            value=max_drawdown,
            risk_level=level,
            description=f"最大回撤: {max_drawdown:.2%}",
            threshold=threshold,
            current_vs_threshold=max_drawdown / threshold
        )

    def _create_sharpe_metric(self, sharpe_ratio: float) -> RiskMetric:
        """创建夏普比率风险指标"""
        threshold = self.config["risk_thresholds"]["sharpe_ratio"]
        
        if sharpe_ratio > threshold * 2:
            level = RiskLevel.LOW
        elif sharpe_ratio > threshold:
            level = RiskLevel.MEDIUM
        elif sharpe_ratio > 0:
            level = RiskLevel.HIGH
        else:
            level = RiskLevel.VERY_HIGH
        
        return RiskMetric(
            name="SharpeRatio",
            value=sharpe_ratio,
            risk_level=level,
            description=f"夏普比率: {sharpe_ratio:.2f}",
            threshold=threshold,
            current_vs_threshold=threshold / max(sharpe_ratio, 0.01)
        )

    async def _calculate_beta(self, returns: pd.Series) -> float:
        """计算Beta系数"""
        try:
            market_returns = await self._fetch_market_returns(len(returns))
            if market_returns is None or len(market_returns) < 30:
                logger.warning("无法获取市场指数收益率数据，使用默认Beta=1.0")
                return 1.0

            min_len = min(len(returns), len(market_returns))
            aligned_returns = returns.iloc[-min_len:]
            aligned_market = market_returns.iloc[-min_len:]

            covariance = np.cov(aligned_returns, aligned_market)[0, 1]
            market_variance = np.var(aligned_market)

            beta = covariance / market_variance if market_variance > 0 else 1.0
            return beta

        except Exception as e:
            logger.warning(f"计算Beta失败: {str(e)}，使用默认Beta=1.0")
            return 1.0

    async def _fetch_market_returns(self, count: int) -> Optional[pd.Series]:
        """获取市场指数收益率"""
        try:
            from core.services.unified_data_manager import get_unified_data_manager
            data_manager = get_unified_data_manager()
            if data_manager:
                df = data_manager.get_kdata('000001', period='D', count=count + 30)
                if df is not None and not df.empty:
                    close_col = 'close' if 'close' in df.columns else df.columns[3]
                    close = df[close_col]
                    return close.pct_change().dropna()
        except ImportError:
            logger.debug("UnifiedDataManager 不可用，无法获取市场指数")
        except Exception as e:
            logger.debug(f"获取市场指数收益率失败: {e}")
        return None

    def _calculate_max_drawdown(self, prices: pd.Series) -> float:
        """计算最大回撤"""
        try:
            peak = prices.expanding().max()
            drawdown = (prices - peak) / peak
            max_drawdown = drawdown.min()
            return abs(max_drawdown)
            
        except Exception as e:
            logger.error(f"计算最大回撤失败: {str(e)}")
            return 0.0

    def _calculate_sharpe_ratio(self, returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """计算夏普比率"""
        try:
            excess_returns = returns - risk_free_rate / 252  # 日化无风险利率
            if excess_returns.std() == 0:
                return 0.0
            
            sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)
            return sharpe
            
        except Exception as e:
            logger.error(f"计算夏普比率失败: {str(e)}")
            return 0.0

    def _calculate_liquidity_risk(self, price_data: pd.DataFrame) -> RiskMetric:
        """计算流动性风险"""
        try:
            volume = price_data['volume']
            prices = price_data['close']
            
            # 计算成交金额
            turnover = volume * prices
            
            # 流动性指标：平均日成交金额的变异系数
            avg_turnover = turnover.mean()
            turnover_std = turnover.std()
            liquidity_ratio = turnover_std / avg_turnover if avg_turnover > 0 else 1
            
            # 流动性风险等级
            if liquidity_ratio < 0.3:
                level = RiskLevel.LOW
            elif liquidity_ratio < 0.6:
                level = RiskLevel.MEDIUM
            elif liquidity_ratio < 1.0:
                level = RiskLevel.HIGH
            else:
                level = RiskLevel.VERY_HIGH
            
            return RiskMetric(
                name="LiquidityRisk",
                value=liquidity_ratio,
                risk_level=level,
                description=f"流动性比率: {liquidity_ratio:.2f}",
                threshold=0.6,
                current_vs_threshold=liquidity_ratio / 0.6
            )
            
        except Exception as e:
            logger.error(f"计算流动性风险失败: {str(e)}")
            return RiskMetric("LiquidityRisk", 1.0, RiskLevel.MEDIUM, "流动性风险计算失败", 0.6, 1.67)

    def _calculate_concentration_risk(self, fundamental_data: Dict[str, Any]) -> RiskMetric:
        """计算集中度风险"""
        try:
            # 基于市值、行业分布等计算集中度风险
            market_cap = fundamental_data.get("market_cap", 1e9)
            
            # 小市值股票风险更高
            if market_cap < 1e9:  # 小于100亿
                level = RiskLevel.HIGH
                concentration_ratio = 0.8
            elif market_cap < 5e9:  # 100-500亿
                level = RiskLevel.MEDIUM
                concentration_ratio = 0.6
            else:  # 大于500亿
                level = RiskLevel.LOW
                concentration_ratio = 0.3
            
            return RiskMetric(
                name="ConcentrationRisk",
                value=concentration_ratio,
                risk_level=level,
                description=f"市值: {market_cap/1e8:.1f}亿",
                threshold=0.6,
                current_vs_threshold=concentration_ratio / 0.6
            )
            
        except Exception as e:
            logger.error(f"计算集中度风险失败: {str(e)}")
            return RiskMetric("ConcentrationRisk", 0.6, RiskLevel.MEDIUM, "集中度风险计算失败", 0.6, 1.0)

    def _calculate_credit_risk(self, fundamental_data: Dict[str, Any]) -> RiskMetric:
        """计算信用风险"""
        try:
            debt_ratio = fundamental_data.get("debt_ratio", 0.3)
            current_ratio = fundamental_data.get("current_ratio", 1.5)
            
            # 信用风险评分
            credit_score = 0
            
            # 负债率评分
            if debt_ratio < 0.3:
                credit_score += 30
            elif debt_ratio < 0.5:
                credit_score += 20
            elif debt_ratio < 0.7:
                credit_score += 10
            else:
                credit_score += 0
            
            # 流动比率评分
            if current_ratio > 2:
                credit_score += 30
            elif current_ratio > 1.5:
                credit_score += 20
            elif current_ratio > 1:
                credit_score += 10
            else:
                credit_score += 0
            
            # ROE评分
            roe = fundamental_data.get("roe", 0.1)
            if roe > 0.15:
                credit_score += 40
            elif roe > 0.1:
                credit_score += 30
            elif roe > 0.05:
                credit_score += 20
            else:
                credit_score += 0
            
            credit_risk_level = (100 - credit_score) / 100
            
            if credit_risk_level < 0.3:
                level = RiskLevel.LOW
            elif credit_risk_level < 0.6:
                level = RiskLevel.MEDIUM
            elif credit_risk_level < 0.8:
                level = RiskLevel.HIGH
            else:
                level = RiskLevel.VERY_HIGH
            
            return RiskMetric(
                name="CreditRisk",
                value=credit_risk_level,
                risk_level=level,
                description=f"信用风险评分: {credit_score}/100",
                threshold=0.6,
                current_vs_threshold=credit_risk_level / 0.6
            )
            
        except Exception as e:
            logger.error(f"计算信用风险失败: {str(e)}")
            return RiskMetric("CreditRisk", 0.6, RiskLevel.MEDIUM, "信用风险计算失败", 0.6, 1.0)

    def _calculate_market_risk(self, returns: pd.Series, fundamental_data: Dict[str, Any]) -> RiskMetric:
        """计算市场风险"""
        try:
            # 基于行业、市值等计算市场风险
            industry = fundamental_data.get("industry", "unknown")
            market_cap = fundamental_data.get("market_cap", 1e9)
            
            # 行业风险系数
            industry_risk_map = {
                "technology": 1.2,
                "finance": 1.0,
                "consumer": 0.9,
                "energy": 1.1,
                "healthcare": 1.0,
                "unknown": 1.0
            }
            
            industry_factor = industry_risk_map.get(industry, 1.0)
            
            # 市值风险系数
            if market_cap < 1e9:
                size_factor = 1.3
            elif market_cap < 5e9:
                size_factor = 1.1
            else:
                size_factor = 0.9
            
            market_risk_score = industry_factor * size_factor
            
            if market_risk_score < 1.0:
                level = RiskLevel.LOW
            elif market_risk_score < 1.2:
                level = RiskLevel.MEDIUM
            elif market_risk_score < 1.4:
                level = RiskLevel.HIGH
            else:
                level = RiskLevel.VERY_HIGH
            
            return RiskMetric(
                name="MarketRisk",
                value=market_risk_score,
                risk_level=level,
                description=f"市场风险系数: {market_risk_score:.2f}",
                threshold=1.2,
                current_vs_threshold=market_risk_score / 1.2
            )
            
        except Exception as e:
            logger.error(f"计算市场风险失败: {str(e)}")
            return RiskMetric("MarketRisk", 1.0, RiskLevel.MEDIUM, "市场风险计算失败", 1.2, 0.83)

    def _identify_risk_alerts(self, risk_metrics: List[RiskMetric]) -> List[RiskAlert]:
        """识别风险警报"""
        alerts = []
        
        try:
            for metric in risk_metrics:
                if metric.risk_level == RiskLevel.HIGH:
                    alert = RiskAlert(
                        risk_type=self._map_metric_to_risk_type(metric.name),
                        level=RiskLevel.HIGH,
                        message=f"{metric.name}风险较高: {metric.description}",
                        timestamp=datetime.now(),
                        action_required=True
                    )
                    alerts.append(alert)
                
                elif metric.risk_level == RiskLevel.VERY_HIGH:
                    alert = RiskAlert(
                        risk_type=self._map_metric_to_risk_type(metric.name),
                        level=RiskLevel.VERY_HIGH,
                        message=f"{metric.name}风险极高: {metric.description}，需要立即关注",
                        timestamp=datetime.now(),
                        action_required=True
                    )
                    alerts.append(alert)
            
            logger.debug(f"识别出{len(alerts)}个风险警报")
            return alerts
            
        except Exception as e:
            logger.error(f"识别风险警报失败: {str(e)}")
            return []

    def _map_metric_to_risk_type(self, metric_name: str) -> RiskType:
        """将指标名称映射到风险类型"""
        mapping = {
            "Volatility": RiskType.VOLATILITY_RISK,
            "Beta": RiskType.MARKET_RISK,
            "MaxDrawdown": RiskType.VOLATILITY_RISK,
            "SharpeRatio": RiskType.MARKET_RISK,
            "LiquidityRisk": RiskType.LIQUIDITY_RISK,
            "ConcentrationRisk": RiskType.CONCENTRATION_RISK,
            "CreditRisk": RiskType.CREDIT_RISK,
            "MarketRisk": RiskType.MARKET_RISK
        }
        return mapping.get(metric_name, RiskType.OPERATIONAL_RISK)

    def _decompose_risks(self, risk_metrics: List[RiskMetric]) -> Dict[str, float]:
        """分解风险来源"""
        try:
            decomposition = {}
            total_risk = 0
            
            for metric in risk_metrics:
                # 将风险水平转换为数值
                risk_value = {
                    RiskLevel.VERY_LOW: 0.1,
                    RiskLevel.LOW: 0.3,
                    RiskLevel.MEDIUM: 0.6,
                    RiskLevel.HIGH: 0.8,
                    RiskLevel.VERY_HIGH: 1.0
                }.get(metric.risk_level, 0.5)
                
                decomposition[metric.name] = risk_value
                total_risk += risk_value
            
            # 归一化
            if total_risk > 0:
                for key in decomposition:
                    decomposition[key] = decomposition[key] / total_risk
            
            return decomposition
            
        except Exception as e:
            logger.error(f"分解风险失败: {str(e)}")
            return {}

    async def _calculate_var(self, price_data: pd.DataFrame) -> Optional[float]:
        """计算VaR (Value at Risk)"""
        try:
            close = price_data['close']
            returns = close.pct_change().dropna()
            
            if len(returns) < 30:
                return None
            
            # 历史模拟法计算VaR
            confidence_level = self.config["var_confidence_level"]
            var_percentile = (1 - confidence_level) * 100
            
            # 按收益率排序
            sorted_returns = returns.sort_values()
            
            # 计算VaR
            var_index = int(len(sorted_returns) * var_percentile / 100)
            var = abs(sorted_returns.iloc[var_index])
            
            return var
            
        except Exception as e:
            logger.error(f"计算VaR失败: {str(e)}")
            return None

    def _determine_overall_risk(self, risk_metrics: List[RiskMetric], 
                              risk_alerts: List[RiskAlert]) -> RiskLevel:
        """确定总体风险等级"""
        try:
            # 统计各风险等级的数量
            risk_counts = {
                RiskLevel.VERY_LOW: 0,
                RiskLevel.LOW: 0,
                RiskLevel.MEDIUM: 0,
                RiskLevel.HIGH: 0,
                RiskLevel.VERY_HIGH: 0
            }
            
            for metric in risk_metrics:
                risk_counts[metric.risk_level] += 1
            
            # 考虑风险警报
            high_alert_count = len([alert for alert in risk_alerts 
                                  if alert.level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]])
            
            # 确定总体风险等级
            if high_alert_count > 0 or risk_counts[RiskLevel.VERY_HIGH] > 0:
                return RiskLevel.VERY_HIGH
            elif risk_counts[RiskLevel.HIGH] > 2 or high_alert_count > 0:
                return RiskLevel.HIGH
            elif risk_counts[RiskLevel.MEDIUM] > 4:
                return RiskLevel.MEDIUM
            elif risk_counts[RiskLevel.LOW] > 5:
                return RiskLevel.LOW
            else:
                return RiskLevel.VERY_LOW
                
        except Exception as e:
            logger.error(f"确定总体风险等级失败: {str(e)}")
            return RiskLevel.MEDIUM

    def _calculate_risk_score(self, risk_metrics: List[RiskMetric]) -> float:
        """计算风险评分 (0-100)"""
        try:
            if not risk_metrics:
                return 50.0
            
            # 风险等级映射到分数
            risk_score_map = {
                RiskLevel.VERY_LOW: 10,
                RiskLevel.LOW: 30,
                RiskLevel.MEDIUM: 50,
                RiskLevel.HIGH: 75,
                RiskLevel.VERY_HIGH: 90
            }
            
            # 加权平均计算风险评分
            total_score = 0
            total_weight = 0
            
            for metric in risk_metrics:
                score = risk_score_map.get(metric.risk_level, 50)
                weight = metric.confidence  # 使用置信度作为权重
                total_score += score * weight
                total_weight += weight
            
            if total_weight > 0:
                return total_score / total_weight
            else:
                return 50.0
                
        except Exception as e:
            logger.error(f"计算风险评分失败: {str(e)}")
            return 50.0

    def _generate_risk_recommendations(self, risk_metrics: List[RiskMetric], 
                                     risk_alerts: List[RiskAlert],
                                     overall_risk: RiskLevel) -> List[str]:
        """生成风险控制建议"""
        recommendations = []
        
        try:
            # 基于总体风险等级的建议
            if overall_risk == RiskLevel.VERY_HIGH:
                recommendations.append("⚠️ 极高风险！建议立即减仓或清仓")
                recommendations.append("加强止损设置，严格控制风险")
            elif overall_risk == RiskLevel.HIGH:
                recommendations.append("高风险状态，建议降低仓位")
                recommendations.append("密切关注市场变化，及时调整策略")
            elif overall_risk == RiskLevel.MEDIUM:
                recommendations.append("中等风险，可适度参与但需控制仓位")
                recommendations.append("建议设置合理止损位")
            else:
                recommendations.append("风险相对较低，可正常参与交易")
                recommendations.append("保持良好的风险控制习惯")
            
            # 基于具体风险指标的建议
            for metric in risk_metrics:
                if metric.name == "Volatility" and metric.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                    recommendations.append("波动率过高，建议减小仓位或选择更稳定的投资标的")
                elif metric.name == "Beta" and metric.value > 1.5:
                    recommendations.append("Beta系数较高，系统性风险较大，注意市场整体走势")
                elif metric.name == "LiquidityRisk" and metric.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                    recommendations.append("流动性风险较高，谨防无法及时止损的风险")
                elif metric.name == "CreditRisk" and metric.risk_level in [RiskLevel.HIGH, RiskLevel.VERY_HIGH]:
                    recommendations.append("信用风险较高，建议关注公司基本面变化")
            
            # 基于VaR的建议
            var_metric = next((m for m in risk_metrics if m.name == "VaR"), None)
            if var_metric and var_metric.value > 0.05:
                recommendations.append(f"VaR较高({var_metric.value:.2%})，建议控制单笔交易风险")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成风险建议失败: {str(e)}")
            return ["风险建议生成失败，请谨慎操作"]

    def _calculate_confidence(self, risk_metrics: List[RiskMetric]) -> float:
        """计算评估置信度"""
        try:
            if not risk_metrics:
                return 0.5
            
            avg_confidence = np.mean([metric.confidence for metric in risk_metrics])
            return min(0.9, avg_confidence)
            
        except Exception as e:
            logger.error(f"计算置信度失败: {str(e)}")
            return 0.5

    def _update_processing_stats(self, processing_time: float):
        """更新处理统计"""
        current_avg = self._stats["avg_processing_time"]
        total_assessments = self._stats["total_assessments"]
        
        # 移动平均
        self._stats["avg_processing_time"] = (current_avg * (total_assessments - 1) + processing_time) / total_assessments

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "total_assessments": self._stats["total_assessments"],
            "cache_hits": self._stats["cache_hits"],
            "cache_hit_rate": self._stats["cache_hits"] / max(1, self._stats["total_assessments"]),
            "avg_processing_time": self._stats["avg_processing_time"],
            "high_risk_alerts": self._stats["high_risk_alerts"],
            "cache_size": len(self._risk_cache)
        }

    async def cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self._risk_cache.items()
            if isinstance(value, dict) and "assessment_time" in value
            and isinstance(value["assessment_time"], datetime)
            and (current_time - value["assessment_time"].timestamp()) > self._cache_ttl
        ]
        
        for key in expired_keys:
            del self._risk_cache[key]
        
        logger.debug(f"清理了{len(expired_keys)}个过期缓存项")
