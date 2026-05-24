"""
BettaFish信号融合引擎
负责整合多智能体分析结果，生成综合决策建议
"""

import asyncio
import time
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from .sentiment_agent import SentimentAnalysisAgent
from .news_agent import NewsAnalysisAgent, NewsImpact
from .technical_agent import TechnicalAnalysisAgent, TechnicalSignal, TrendDirection
from .risk_agent import RiskAssessmentAgent, RiskLevel

class FusionStrategy(Enum):
    """融合策略"""
    WEIGHTED_AVERAGE = "weighted_average"      # 加权平均
    VOTING = "voting"                          # 投票制
    CONFIDENCE_BASED = "confidence_based"      # 基于置信度
    ADAPTIVE = "adaptive"                      # 自适应
    CONSERVATIVE = "conservative"              # 保守型

class SignalStrength(Enum):
    """信号强度"""
    VERY_WEAK = "very_weak"      # 极弱
    WEAK = "weak"                # 弱
    MODERATE = "moderate"        # 中等
    STRONG = "strong"            # 强
    VERY_STRONG = "very_strong"  # 极强

@dataclass
class AgentSignal:
    """Agent信号"""
    agent_name: str
    signal_type: str
    signal_value: float  # -1 to 1, 负值看跌，正值看涨
    confidence: float    # 0 to 1
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FusionResult:
    """融合结果"""
    stock_code: str
    fusion_time: datetime
    final_signal: float           # 综合信号强度
    signal_strength: SignalStrength
    confidence: float            # 综合置信度
    agent_signals: List[AgentSignal]
    strategy_used: FusionStrategy
    consensus_level: float       # 一致性水平
    conflict_resolution: Dict[str, Any]
    recommendations: List[str]
    risk_warning: Optional[str] = None

class SignalFusionEngine:
    """信号融合引擎"""
    
    def __init__(self):
        # 融合配置
        self.config = {
            "default_weights": {
                "sentiment": 0.25,    # 舆情分析权重
                "news": 0.20,         # 新闻分析权重
                "technical": 0.30,    # 技术分析权重
                "risk": 0.25          # 风险评估权重
            },
            "confidence_thresholds": {
                "high": 0.8,
                "medium": 0.6,
                "low": 0.4
            },
            "consensus_threshold": 0.7,  # 一致性阈值
            "conflict_resolution": {
                "risk_priority": True,  # 风险优先
                "technical_priority": False,
                "sentiment_priority": False
            },
            "signal_strength_thresholds": {
                "very_strong": 0.7,
                "strong": 0.5,
                "moderate": 0.3,
                "weak": 0.1
            },
            "decision_thresholds": {
                "strong_buy": 0.5,
                "mild_buy": 0.2,
                "strong_sell": -0.5,
                "mild_sell": -0.2
            },
            "conflict_thresholds": {
                "significant_divergence": 0.8,
                "extreme_divergence": 1.0
            },
            "risk_warning_thresholds": {
                "high_risk": -0.6,
                "low_consensus": 0.3,
                "extreme_signal": 0.8
            },
            "adaptive_thresholds": {
                "high_consensus": 0.8,
                "low_consensus": 0.4
            }
        }
        
        # 动态权重调整
        self._adaptive_weights = self.config["default_weights"].copy()
        self._weight_history = []
        
        # 性能统计
        self._stats = {
            "total_fusions": 0,
            "avg_processing_time": 0.0,
            "strategy_usage": {strategy.value: 0 for strategy in FusionStrategy},
            "consensus_distribution": {"high": 0, "medium": 0, "low": 0}
        }

    async def fuse_signals(self, stock_code: str, 
                          agent_results: Dict[str, Any],
                          strategy: FusionStrategy = FusionStrategy.ADAPTIVE,
                          custom_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """融合多Agent信号"""
        start_time = time.time()
        
        try:
            logger.debug(f"开始信号融合: {stock_code}, 策略: {strategy.value}")
            
            # 提取Agent信号
            agent_signals = self._extract_agent_signals(agent_results)
            
            if not agent_signals:
                logger.warning(f"没有有效的Agent信号: {stock_code}")
                return {
                    "status": "no_signals",
                    "message": "没有有效的分析信号",
                    "stock_code": stock_code
                }
            
            # 应用融合策略
            if strategy == FusionStrategy.ADAPTIVE:
                fusion_result = await self._adaptive_fusion(stock_code, agent_signals)
            elif strategy == FusionStrategy.WEIGHTED_AVERAGE:
                fusion_result = await self._weighted_average_fusion(stock_code, agent_signals, custom_weights)
            elif strategy == FusionStrategy.VOTING:
                fusion_result = await self._voting_fusion(stock_code, agent_signals)
            elif strategy == FusionStrategy.CONFIDENCE_BASED:
                fusion_result = await self._confidence_based_fusion(stock_code, agent_signals)
            elif strategy == FusionStrategy.CONSERVATIVE:
                fusion_result = await self._conservative_fusion(stock_code, agent_signals)
            else:
                fusion_result = await self._weighted_average_fusion(stock_code, agent_signals, custom_weights)
            
            # 更新统计
            self._stats["total_fusions"] += 1
            self._stats["strategy_usage"][strategy.value] += 1
            
            # 分类一致性水平
            consensus_level = fusion_result.consensus_level
            if consensus_level > 0.8:
                self._stats["consensus_distribution"]["high"] += 1
            elif consensus_level > 0.5:
                self._stats["consensus_distribution"]["medium"] += 1
            else:
                self._stats["consensus_distribution"]["low"] += 1
            
            processing_time = time.time() - start_time
            self._update_processing_stats(processing_time)
            
            logger.info(f"信号融合完成: {stock_code}, 最终信号: {fusion_result.final_signal:.3f}, 耗时: {processing_time:.2f}s")
            
            return {
                "status": "success",
                "fusion_result": fusion_result,
                "processing_time": processing_time,
                "strategy_used": strategy.value
            }
            
        except Exception as e:
            logger.error(f"信号融合失败: {stock_code}, 错误: {str(e)}")
            return {
                "status": "error",
                "message": f"信号融合失败: {str(e)}",
                "stock_code": stock_code
            }

    def _normalize_key_names(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """标准化bettafish_agent传入的短键名为融合引擎期望的长键名"""
        key_mapping = {
            "sentiment": "sentiment_analysis",
            "news": "news_analysis",
            "technical": "technical_analysis",
            "risk": "risk_assessment",
        }
        normalized = {}
        for key, value in agent_results.items():
            mapped_key = key_mapping.get(key, key)
            normalized[mapped_key] = value
        return normalized

    def _normalize_agent_output(self, agent_name: str, output: dict) -> dict:
        """标准化不同agent的输出键名"""
        key_mapping = {
            "sentiment": {"sentiment": "signal_type", "score": "confidence"},
            "news": {"sentiment": "signal_type", "score": "confidence"},
            "technical": {"signal": "signal_type", "strength": "confidence"},
            "risk": {"risk_score": "signal_type", "risk_level": "confidence"},
        }
        mapping = key_mapping.get(agent_name, {})
        return {mapping.get(k, k): v for k, v in output.items()}

    def _extract_agent_signals(self, agent_results: Dict[str, Any]) -> List[AgentSignal]:
        """提取Agent信号"""
        signals = []

        try:
            agent_results = self._normalize_key_names(agent_results)

            # 舆情分析信号
            if "sentiment_analysis" in agent_results:
                sentiment_entry = agent_results["sentiment_analysis"]
                if isinstance(sentiment_entry, dict):
                    if sentiment_entry.get("status") == "success" and "analysis_result" in sentiment_entry:
                        sentiment_data = sentiment_entry["analysis_result"]
                    else:
                        sentiment_data = sentiment_entry
                else:
                    sentiment_data = sentiment_entry

                if hasattr(sentiment_data, 'sentiment_score'):
                    sentiment_score = sentiment_data.sentiment_score
                    sentiment_confidence = sentiment_data.confidence
                    news_count = getattr(sentiment_data, 'news_count', 0)
                    key_themes = getattr(sentiment_data, 'key_themes', [])
                elif isinstance(sentiment_data, dict):
                    sentiment_score = sentiment_data.get('sentiment_score', 0.0)
                    sentiment_confidence = sentiment_data.get('confidence', 0.5)
                    news_count = sentiment_data.get('news_count', sentiment_data.get('source_count', 0))
                    key_themes = sentiment_data.get('key_themes', sentiment_data.get('keyword_analysis', []))
                else:
                    sentiment_score = 0.0
                    sentiment_confidence = 0.5
                    news_count = 0
                    key_themes = []

                signals.append(AgentSignal(
                    agent_name="sentiment",
                    signal_type="sentiment",
                    signal_value=sentiment_score,
                    confidence=sentiment_confidence,
                    timestamp=datetime.now(),
                    metadata={
                        "news_count": news_count,
                        "key_themes": key_themes
                    }
                ))

            # 新闻分析信号
            if "news_analysis" in agent_results:
                news_entry = agent_results["news_analysis"]
                if isinstance(news_entry, dict):
                    if news_entry.get("status") == "success" and "analysis_result" in news_entry:
                        news_data = news_entry["analysis_result"]
                    else:
                        news_data = news_entry
                else:
                    news_data = news_entry

                if hasattr(news_data, 'sentiment_score'):
                    news_sentiment = news_data.sentiment_score
                    news_confidence = news_data.confidence
                    news_count = getattr(news_data, 'news_count', 0)
                    impact_analysis = getattr(news_data, 'impact_analysis', [])
                elif isinstance(news_data, dict):
                    news_sentiment = news_data.get('sentiment_score', 0.0)
                    news_confidence = news_data.get('confidence', 0.5)
                    news_count = news_data.get('news_count', 0)
                    impact_analysis = news_data.get('impact_analysis', [])
                else:
                    news_sentiment = 0.0
                    news_confidence = 0.5
                    news_count = 0
                    impact_analysis = []

                signals.append(AgentSignal(
                    agent_name="news",
                    signal_type="news",
                    signal_value=news_sentiment,
                    confidence=news_confidence,
                    timestamp=datetime.now(),
                    metadata={
                        "news_count": news_count,
                        "impact_analysis": impact_analysis
                    }
                ))

            # 技术分析信号
            if "technical_analysis" in agent_results:
                tech_entry = agent_results["technical_analysis"]
                if isinstance(tech_entry, dict):
                    if tech_entry.get("status") == "success" and "analysis_result" in tech_entry:
                        tech_data = tech_entry["analysis_result"]
                    else:
                        tech_data = tech_entry
                else:
                    tech_data = tech_entry

                if hasattr(tech_data, 'overall_signal'):
                    tech_signal_value = self._technical_signal_to_value(tech_data.overall_signal)
                    tech_confidence = tech_data.confidence
                    trend_direction = tech_data.trend_direction.value
                    indicators_count = len(tech_data.indicators)
                    patterns_count = len(tech_data.patterns)
                elif isinstance(tech_data, dict):
                    tech_signal_value = tech_data.get('signal_value', tech_data.get('overall_signal', 0.0))
                    if isinstance(tech_signal_value, str):
                        tech_signal_value = 0.0
                    tech_confidence = tech_data.get('confidence', 0.5)
                    trend_direction = tech_data.get('trend_direction', 'unknown')
                    indicators_count = tech_data.get('indicators_count', 0)
                    patterns_count = tech_data.get('patterns_count', 0)
                else:
                    tech_signal_value = 0.0
                    tech_confidence = 0.5
                    trend_direction = 'unknown'
                    indicators_count = 0
                    patterns_count = 0

                signals.append(AgentSignal(
                    agent_name="technical",
                    signal_type="technical",
                    signal_value=tech_signal_value,
                    confidence=tech_confidence,
                    timestamp=datetime.now(),
                    metadata={
                        "trend_direction": trend_direction,
                        "indicators_count": indicators_count,
                        "patterns_count": patterns_count
                    }
                ))

            # 风险评估信号（风险评估的信号是反向的）
            if "risk_assessment" in agent_results:
                risk_entry = agent_results["risk_assessment"]
                if isinstance(risk_entry, dict):
                    if risk_entry.get("status") == "success":
                        if "assessment_result" in risk_entry:
                            risk_data = risk_entry["assessment_result"]
                        else:
                            risk_data = risk_entry
                    else:
                        risk_data = risk_entry
                else:
                    risk_data = risk_entry

                if hasattr(risk_data, 'overall_risk_level'):
                    risk_signal_value = self._risk_level_to_signal(risk_data.overall_risk_level)
                    risk_confidence = risk_data.confidence
                    risk_score = risk_data.risk_score
                    risk_level = risk_data.overall_risk_level.value
                    alerts_count = len(risk_data.risk_alerts)
                elif isinstance(risk_data, dict):
                    risk_level_str = risk_data.get('risk_level', 'MEDIUM')
                    risk_level_enum = getattr(RiskLevel, risk_level_str.upper(), RiskLevel.MEDIUM)
                    risk_signal_value = self._risk_level_to_signal(risk_level_enum)
                    risk_confidence = risk_data.get('confidence', 0.5)
                    risk_score = risk_data.get('risk_score', 50.0)
                    risk_level = risk_level_str
                    alerts_count = risk_data.get('alerts_count', len(risk_data.get('risk_alerts', [])))
                else:
                    risk_signal_value = 0.0
                    risk_confidence = 0.5
                    risk_score = 50.0
                    risk_level = 'MEDIUM'
                    alerts_count = 0

                signals.append(AgentSignal(
                    agent_name="risk",
                    signal_type="risk",
                    signal_value=risk_signal_value,
                    confidence=risk_confidence,
                    timestamp=datetime.now(),
                    metadata={
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "alerts_count": alerts_count
                    }
                ))

            logger.debug(f"提取了{len(signals)}个Agent信号")
            return signals

        except Exception as e:
            logger.error(f"提取Agent信号失败: {str(e)}")
            return []

    def _technical_signal_to_value(self, signal: TechnicalSignal) -> float:
        """将技术信号转换为数值"""
        mapping = {
            TechnicalSignal.STRONG_BUY: 0.8,
            TechnicalSignal.BUY: 0.4,
            TechnicalSignal.HOLD: 0.0,
            TechnicalSignal.SELL: -0.4,
            TechnicalSignal.STRONG_SELL: -0.8
        }
        return mapping.get(signal, 0.0)

    def _risk_level_to_signal(self, risk_level: RiskLevel) -> float:
        """将风险等级转换为信号（高风险 -> 负信号）"""
        mapping = {
            RiskLevel.VERY_LOW: 0.6,    # 低风险 -> 正信号
            RiskLevel.LOW: 0.3,
            RiskLevel.MEDIUM: 0.0,      # 中等风险 -> 中性
            RiskLevel.HIGH: -0.5,       # 高风险 -> 负信号
            RiskLevel.VERY_HIGH: -0.8   # 极高风险 -> 强负信号
        }
        return mapping.get(risk_level, 0.0)

    async def _adaptive_fusion(self, stock_code: str, 
                             agent_signals: List[AgentSignal]) -> FusionResult:
        """自适应融合"""
        try:
            base_weights = self.config["default_weights"]
            current_weights = dict(base_weights)
            
            consensus = self._calculate_consensus(agent_signals)
            
            at = self.config["adaptive_thresholds"]

            if consensus["level"] > at["high_consensus"]:
                for agent in current_weights:
                    current_weights[agent] *= 1.1
            elif consensus["level"] < at["low_consensus"]:
                if self.config["conflict_resolution"]["risk_priority"]:
                    current_weights["risk"] *= 1.2
                    current_weights["technical"] *= 0.9
                    current_weights["sentiment"] *= 0.9
                    current_weights["news"] *= 0.9
            
            total_weight = sum(current_weights.values())
            if total_weight > 0:
                for agent in current_weights:
                    current_weights[agent] /= total_weight
            
            self._adaptive_weights = current_weights
            
            final_signal, confidence = self._apply_weighted_fusion(agent_signals, current_weights)
            
            # 冲突解决
            conflict_resolution = self._resolve_conflicts(agent_signals)
            
            # 生成建议
            recommendations = self._generate_fusion_recommendations(agent_signals, final_signal, consensus)
            
            return FusionResult(
                stock_code=stock_code,
                fusion_time=datetime.now(),
                final_signal=final_signal,
                signal_strength=self._determine_signal_strength(final_signal),
                confidence=confidence,
                agent_signals=agent_signals,
                strategy_used=FusionStrategy.ADAPTIVE,
                consensus_level=consensus["level"],
                conflict_resolution=conflict_resolution,
                recommendations=recommendations,
                risk_warning=self._generate_risk_warning(agent_signals, consensus)
            )
            
        except Exception as e:
            logger.error(f"自适应融合失败: {str(e)}")
            raise

    async def _weighted_average_fusion(self, stock_code: str, 
                                     agent_signals: List[AgentSignal],
                                     custom_weights: Optional[Dict[str, float]] = None) -> FusionResult:
        """加权平均融合"""
        try:
            # 使用自定义权重或默认权重
            weights = custom_weights or self.config["default_weights"]
            
            # 应用加权平均
            final_signal, confidence = self._apply_weighted_fusion(agent_signals, weights)
            
            # 计算一致性
            consensus = self._calculate_consensus(agent_signals)
            
            # 冲突解决
            conflict_resolution = self._resolve_conflicts(agent_signals)
            
            # 生成建议
            recommendations = self._generate_fusion_recommendations(agent_signals, final_signal, consensus)
            
            return FusionResult(
                stock_code=stock_code,
                fusion_time=datetime.now(),
                final_signal=final_signal,
                signal_strength=self._determine_signal_strength(final_signal),
                confidence=confidence,
                agent_signals=agent_signals,
                strategy_used=FusionStrategy.WEIGHTED_AVERAGE,
                consensus_level=consensus["level"],
                conflict_resolution=conflict_resolution,
                recommendations=recommendations,
                risk_warning=self._generate_risk_warning(agent_signals, consensus)
            )
            
        except Exception as e:
            logger.error(f"加权平均融合失败: {str(e)}")
            raise

    async def _voting_fusion(self, stock_code: str, 
                           agent_signals: List[AgentSignal]) -> FusionResult:
        """投票制融合"""
        try:
            # 统计投票结果
            votes = {"positive": 0, "negative": 0, "neutral": 0}
            total_confidence = 0
            
            for signal in agent_signals:
                confidence_weight = signal.confidence
                total_confidence += confidence_weight
                
                if signal.signal_value > 0.1:
                    votes["positive"] += confidence_weight
                elif signal.signal_value < -0.1:
                    votes["negative"] += confidence_weight
                else:
                    votes["neutral"] += confidence_weight
            
            # 确定最终信号
            if votes["positive"] > votes["negative"] and votes["positive"] > votes["neutral"]:
                final_signal = votes["positive"] / total_confidence
            elif votes["negative"] > votes["positive"] and votes["negative"] > votes["neutral"]:
                final_signal = -votes["negative"] / total_confidence
            else:
                final_signal = 0.0
            
            # 计算置信度
            confidence = max(votes.values()) / total_confidence if total_confidence > 0 else 0.5
            
            # 计算一致性
            consensus = self._calculate_consensus(agent_signals)
            
            # 冲突解决
            conflict_resolution = self._resolve_conflicts(agent_signals)
            
            # 生成建议
            recommendations = self._generate_fusion_recommendations(agent_signals, final_signal, consensus)
            
            return FusionResult(
                stock_code=stock_code,
                fusion_time=datetime.now(),
                final_signal=final_signal,
                signal_strength=self._determine_signal_strength(final_signal),
                confidence=confidence,
                agent_signals=agent_signals,
                strategy_used=FusionStrategy.VOTING,
                consensus_level=consensus["level"],
                conflict_resolution=conflict_resolution,
                recommendations=recommendations,
                risk_warning=self._generate_risk_warning(agent_signals, consensus)
            )
            
        except Exception as e:
            logger.error(f"投票制融合失败: {str(e)}")
            raise

    async def _confidence_based_fusion(self, stock_code: str, 
                                     agent_signals: List[AgentSignal]) -> FusionResult:
        """基于置信度的融合"""
        try:
            # 按置信度排序信号
            sorted_signals = sorted(agent_signals, key=lambda x: x.confidence, reverse=True)
            
            # 优先考虑高置信度信号
            high_conf_signals = [s for s in sorted_signals if s.confidence > self.config["confidence_thresholds"]["high"]]
            
            if high_conf_signals:
                # 只使用高置信度信号
                final_signal = np.mean([s.signal_value for s in high_conf_signals])
                confidence = np.mean([s.confidence for s in high_conf_signals])
            else:
                # 使用所有信号，但给予更高置信度信号更多权重
                weights = [s.confidence**2 for s in agent_signals]  # 平方提高高置信度信号权重
                final_signal = np.average([s.signal_value for s in agent_signals], weights=weights)
                confidence = np.mean([s.confidence for s in agent_signals])
            
            # 计算一致性
            consensus = self._calculate_consensus(agent_signals)
            
            # 冲突解决
            conflict_resolution = self._resolve_conflicts(agent_signals)
            
            # 生成建议
            recommendations = self._generate_fusion_recommendations(agent_signals, final_signal, consensus)
            
            return FusionResult(
                stock_code=stock_code,
                fusion_time=datetime.now(),
                final_signal=final_signal,
                signal_strength=self._determine_signal_strength(final_signal),
                confidence=confidence,
                agent_signals=agent_signals,
                strategy_used=FusionStrategy.CONFIDENCE_BASED,
                consensus_level=consensus["level"],
                conflict_resolution=conflict_resolution,
                recommendations=recommendations,
                risk_warning=self._generate_risk_warning(agent_signals, consensus)
            )
            
        except Exception as e:
            logger.error(f"基于置信度的融合失败: {str(e)}")
            raise

    async def _conservative_fusion(self, stock_code: str, 
                                 agent_signals: List[AgentSignal]) -> FusionResult:
        """保守型融合"""
        try:
            # 保守型融合：取最保守的信号（倾向于中性）
            signals = [s.signal_value for s in agent_signals]
            
            # 计算中位数（更保守）
            final_signal = np.median(signals)
            
            # 置信度降低（保守）
            confidence = np.mean([s.confidence for s in agent_signals]) * 0.8
            
            # 检查是否有强烈冲突
            max_signal = max(signals)
            min_signal = min(signals)
            
            if abs(max_signal - min_signal) > self.config["conflict_thresholds"]["extreme_divergence"]:  # 信号差异过大
                final_signal = 0.0  # 趋于中性
                confidence *= 0.5   # 降低置信度
            
            # 计算一致性
            consensus = self._calculate_consensus(agent_signals)
            
            # 冲突解决
            conflict_resolution = self._resolve_conflicts(agent_signals)
            
            # 生成建议
            recommendations = self._generate_fusion_recommendations(agent_signals, final_signal, consensus)
            
            return FusionResult(
                stock_code=stock_code,
                fusion_time=datetime.now(),
                final_signal=final_signal,
                signal_strength=self._determine_signal_strength(final_signal),
                confidence=confidence,
                agent_signals=agent_signals,
                strategy_used=FusionStrategy.CONSERVATIVE,
                consensus_level=consensus["level"],
                conflict_resolution=conflict_resolution,
                recommendations=recommendations,
                risk_warning=self._generate_risk_warning(agent_signals, consensus)
            )
            
        except Exception as e:
            logger.error(f"保守型融合失败: {str(e)}")
            raise

    def _apply_weighted_fusion(self, agent_signals: List[AgentSignal], 
                             weights: Dict[str, float]) -> Tuple[float, float]:
        """应用加权融合"""
        try:
            if not agent_signals:
                return 0.0, 0.0
            
            total_weighted_signal = 0.0
            total_weight = 0.0
            total_confidence = 0.0
            
            for signal in agent_signals:
                agent_name = signal.agent_name
                weight = weights.get(agent_name, 0.25)  # 默认权重
                
                weighted_signal = signal.signal_value * weight
                total_weighted_signal += weighted_signal
                total_weight += weight
                total_confidence += signal.confidence
            
            if total_weight > 0:
                final_signal = total_weighted_signal / total_weight
            else:
                final_signal = 0.0
            
            confidence = total_confidence / len(agent_signals)
            
            return final_signal, confidence
            
        except Exception as e:
            logger.error(f"应用加权融合失败: {str(e)}")
            return 0.0, 0.0

    def _calculate_consensus(self, agent_signals: List[AgentSignal]) -> Dict[str, Any]:
        """计算信号一致性"""
        try:
            if len(agent_signals) < 2:
                return {"level": 1.0, "agreement": "complete"}
            
            signals = [s.signal_value for s in agent_signals]
            
            # 计算信号标准差
            signal_std = np.std(signals)
            
            # 一致性水平（标准差越小，一致性越高）
            consensus_level = max(0.0, 1.0 - signal_std)
            
            # 确定一致性等级
            if consensus_level > 0.8:
                agreement = "high"
            elif consensus_level > 0.5:
                agreement = "medium"
            else:
                agreement = "low"
            
            return {
                "level": consensus_level,
                "agreement": agreement,
                "signal_std": signal_std,
                "signal_range": max(signals) - min(signals)
            }
            
        except Exception as e:
            logger.error(f"计算一致性失败: {str(e)}")
            return {"level": 0.5, "agreement": "medium", "signal_std": 0.5, "signal_range": 1.0}

    def _resolve_conflicts(self, agent_signals: List[AgentSignal]) -> Dict[str, Any]:
        """解决信号冲突"""
        try:
            signals = [s.signal_value for s in agent_signals]
            max_signal = max(signals)
            min_signal = min(signals)
            signal_range = max_signal - min_signal
            
            conflicts = []
            resolution_strategy = None
            
            if signal_range > self.config["conflict_thresholds"]["significant_divergence"]:  # 信号差异较大
                conflicts.append("Agent信号存在显著分歧")
                
                # 找出最积极和最消极的信号
                most_positive = max(agent_signals, key=lambda x: x.signal_value)
                most_negative = min(agent_signals, key=lambda x: x.signal_value)
                
                conflicts.append(f"最乐观: {most_positive.agent_name}({most_positive.signal_value:.2f})")
                conflicts.append(f"最悲观: {most_negative.agent_name}({most_negative.signal_value:.2f})")
                
                # 应用冲突解决策略
                if self.config["conflict_resolution"]["risk_priority"]:
                    risk_signal = next((s for s in agent_signals if s.agent_name == "risk"), None)
                    if risk_signal:
                        resolution_strategy = "risk_priority"
                        conflicts.append(f"采用风险优先策略: {risk_signal.signal_value:.2f}")
                
                elif self.config["conflict_resolution"]["technical_priority"]:
                    tech_signal = next((s for s in agent_signals if s.agent_name == "technical"), None)
                    if tech_signal:
                        resolution_strategy = "technical_priority"
                        conflicts.append(f"采用技术优先策略: {tech_signal.signal_value:.2f}")
            
            return {
                "has_conflicts": len(conflicts) > 0,
                "conflicts": conflicts,
                "resolution_strategy": resolution_strategy,
                "signal_range": signal_range
            }
            
        except Exception as e:
            logger.error(f"解决冲突失败: {str(e)}")
            return {"has_conflicts": False, "conflicts": [], "resolution_strategy": None, "signal_range": 0.0}

    def _determine_signal_strength(self, final_signal: float) -> SignalStrength:
        """确定信号强度"""
        abs_signal = abs(final_signal)
        thresholds = self.config["signal_strength_thresholds"]

        if abs_signal > thresholds["very_strong"]:
            return SignalStrength.VERY_STRONG
        elif abs_signal > thresholds["strong"]:
            return SignalStrength.STRONG
        elif abs_signal > thresholds["moderate"]:
            return SignalStrength.MODERATE
        elif abs_signal > thresholds["weak"]:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK

    def _generate_fusion_recommendations(self, agent_signals: List[AgentSignal],
                                       final_signal: float,
                                       consensus: Dict[str, Any]) -> List[str]:
        """生成融合建议"""
        recommendations = []

        try:
            dt = self.config["decision_thresholds"]

            if final_signal > dt["strong_buy"]:
                recommendations.append("综合分析显示积极信号，可考虑买入")
            elif final_signal > dt["mild_buy"]:
                recommendations.append("综合分析偏向积极，可适度关注")
            elif final_signal < dt["strong_sell"]:
                recommendations.append("综合分析显示消极信号，建议减仓或观望")
            elif final_signal < dt["mild_sell"]:
                recommendations.append("综合分析偏向消极，需谨慎操作")
            else:
                recommendations.append("信号不明确，建议等待更明确信号")
            
            # 基于一致性的建议
            if consensus["agreement"] == "low":
                recommendations.append("Agent间存在分歧，建议谨慎决策")
                recommendations.append("可考虑分批建仓或等待信号明确")
            elif consensus["agreement"] == "high":
                recommendations.append("Agent间高度一致，信号可靠性较高")
            
            # 基于风险Agent的建议
            risk_signal = next((s for s in agent_signals if s.agent_name == "risk"), None)
            if risk_signal and risk_signal.signal_value < -0.3:
                recommendations.append("风险评估显示较高风险，请注意风险控制")
            
            # 基于技术分析的建议
            tech_signal = next((s for s in agent_signals if s.agent_name == "technical"), None)
            if tech_signal and abs(tech_signal.signal_value) > 0.6:
                recommendations.append("技术分析信号较强，可作为重要参考")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"生成融合建议失败: {str(e)}")
            return ["融合建议生成失败，请谨慎操作"]

    def _generate_risk_warning(self, agent_signals: List[AgentSignal],
                             consensus: Dict[str, Any]) -> Optional[str]:
        """生成风险警告"""
        try:
            warnings = []
            rwt = self.config["risk_warning_thresholds"]

            # 检查风险Agent警告
            risk_signal = next((s for s in agent_signals if s.agent_name == "risk"), None)
            if risk_signal and risk_signal.signal_value < rwt["high_risk"]:
                warnings.append("风险评估显示极高风险")

            # 检查一致性警告
            if consensus["level"] < rwt["low_consensus"]:
                warnings.append("Agent信号分歧极大，决策风险较高")

            # 检查信号强度警告
            final_signal = np.mean([s.signal_value for s in agent_signals])
            if abs(final_signal) > rwt["extreme_signal"]:
                warnings.append("信号强度极高，需谨防过度乐观或悲观")

            if warnings:
                return "⚠️ " + "; ".join(warnings)
            else:
                return None

        except Exception as e:
            logger.error(f"生成风险警告失败: {str(e)}")
            return None

    def _update_processing_stats(self, processing_time: float):
        """更新处理统计"""
        current_avg = self._stats["avg_processing_time"]
        total_fusions = self._stats["total_fusions"]
        
        # 移动平均
        self._stats["avg_processing_time"] = (current_avg * (total_fusions - 1) + processing_time) / total_fusions

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            "total_fusions": self._stats["total_fusions"],
            "avg_processing_time": self._stats["avg_processing_time"],
            "strategy_usage": self._stats["strategy_usage"].copy(),
            "consensus_distribution": self._stats["consensus_distribution"].copy(),
            "current_weights": self._adaptive_weights.copy()
        }

    def reset_adaptive_weights(self):
        """重置自适应权重"""
        self._adaptive_weights = self.config["default_weights"].copy()
        logger.info("自适应权重已重置")