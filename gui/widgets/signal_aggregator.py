#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能信号聚合系统
结合技术分析、情绪分析等多种数据源，生成综合交易信号和提醒
"""

from PyQt5.QtCore import QObject, pyqtSignal
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime
import json

from loguru import logger

class SignalSourceType(Enum):
    """信号来源类型"""
    TECHNICAL = "technical"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"
    MONEY_FLOW = "money_flow"
    NEWS = "news"
    VOLUME = "volume"

class SignalStrength(Enum):
    """信号强度"""
    VERY_WEAK = 1
    WEAK = 2
    MODERATE = 3
    STRONG = 4
    VERY_STRONG = 5

class AlertLevel(Enum):
    """提醒级别"""
    INFO = "info"          # 信息提示
    WARNING = "warning"    # 警告
    DANGER = "danger"      # 危险
    SUCCESS = "success"    # 成功信号

@dataclass
class TradingSignal:
    """交易信号数据类"""
    signal_id: str
    signal_type: SignalSourceType
    direction: str  # "buy", "sell", "hold"
    strength: SignalStrength
    confidence: float  # 0-1
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    source_data: Dict[str, Any]

@dataclass
class AggregatedAlert:
    """聚合警报数据类"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    signals: List[TradingSignal]
    overall_confidence: float
    recommended_action: str
    timestamp: datetime
    expires_at: Optional[datetime] = None

class TechnicalSignalDetector:
    """技术信号检测器"""

    def __init__(self):
        self.name = "技术信号检测器"
        self._prev_macd_state = None

    def detect_signals(self, kdata: pd.DataFrame, technical_indicators: Dict[str, Any]) -> List[TradingSignal]:
        """检测技术信号"""
        signals = []

        try:
            if kdata.empty:
                return signals

            current_time = datetime.now()

            # RSI信号检测
            if 'rsi' in technical_indicators:
                rsi_value = float(technical_indicators['rsi'])
                rsi_signal = self._detect_rsi_signal(rsi_value, current_time)
                if rsi_signal:
                    signals.append(rsi_signal)

            # MACD信号检测
            if 'macd' in technical_indicators:
                macd_data = technical_indicators['macd']
                macd_signal = self._detect_macd_signal(macd_data, current_time)
                if macd_signal:
                    signals.append(macd_signal)

            # 均线信号检测
            if 'ma' in technical_indicators:
                ma_data = technical_indicators['ma']
                ma_signal = self._detect_ma_signal(kdata, ma_data, current_time)
                if ma_signal:
                    signals.append(ma_signal)

            # 价格突破信号
            price_signal = self._detect_price_breakthrough(kdata, current_time)
            if price_signal:
                signals.append(price_signal)

        except Exception as e:
            logger.info(f"技术信号检测错误: {e}")

        return signals

    def _detect_rsi_signal(self, rsi_value: float, timestamp: datetime) -> Optional[TradingSignal]:
        """检测RSI信号"""
        if rsi_value >= 80:
            return TradingSignal(
                signal_id=f"rsi_overbought_{timestamp.timestamp()}",
                signal_type=SignalSourceType.TECHNICAL,
                direction="sell",
                strength=SignalStrength.STRONG if rsi_value >= 85 else SignalStrength.MODERATE,
                confidence=min(0.95, (rsi_value - 70) / 30),
                message=f"RSI严重超买 ({rsi_value:.1f})",
                details={"rsi_value": rsi_value, "threshold": 80},
                timestamp=timestamp,
                source_data={"indicator": "RSI", "value": rsi_value}
            )
        elif rsi_value <= 20:
            return TradingSignal(
                signal_id=f"rsi_oversold_{timestamp.timestamp()}",
                signal_type=SignalSourceType.TECHNICAL,
                direction="buy",
                strength=SignalStrength.STRONG if rsi_value <= 15 else SignalStrength.MODERATE,
                confidence=min(0.95, (30 - rsi_value) / 30),
                message=f"RSI严重超卖 ({rsi_value:.1f})",
                details={"rsi_value": rsi_value, "threshold": 20},
                timestamp=timestamp,
                source_data={"indicator": "RSI", "value": rsi_value}
            )
        return None

    def _detect_macd_signal(self, macd_data: Dict[str, Any], timestamp: datetime) -> Optional[TradingSignal]:
        """检测MACD信号 - 仅金叉/死叉时刻触发"""
        try:
            if 'dif' in macd_data and 'dea' in macd_data:
                dif = float(macd_data['dif'])
                dea = float(macd_data['dea'])

                curr_state = dif > dea

                if self._prev_macd_state is not None and abs(dif - dea) > 0.01:
                    if curr_state and not self._prev_macd_state:
                        self._prev_macd_state = curr_state
                        return TradingSignal(
                            signal_id=f"macd_golden_cross_{timestamp.timestamp()}",
                            signal_type=SignalSourceType.TECHNICAL,
                            direction="buy",
                            strength=SignalStrength.MODERATE,
                            confidence=0.7,
                            message="MACD金叉信号",
                            details={"dif": dif, "dea": dea},
                            timestamp=timestamp,
                            source_data=macd_data
                        )
                    elif not curr_state and self._prev_macd_state:
                        self._prev_macd_state = curr_state
                        return TradingSignal(
                            signal_id=f"macd_death_cross_{timestamp.timestamp()}",
                            signal_type=SignalSourceType.TECHNICAL,
                            direction="sell",
                            strength=SignalStrength.MODERATE,
                            confidence=0.7,
                            message="MACD死叉信号",
                            details={"dif": dif, "dea": dea},
                            timestamp=timestamp,
                            source_data=macd_data
                        )

                self._prev_macd_state = curr_state
        except Exception as e:
            logger.info(f"MACD信号检测错误: {e}")

        return None

    def _detect_ma_signal(self, kdata: pd.DataFrame, ma_data: Dict[str, Any], timestamp: datetime) -> Optional[TradingSignal]:
        """检测均线信号"""
        try:
            if len(kdata) < 2:
                return None

            current_price = float(kdata.iloc[-1]['close'])

            if 'ma5' in ma_data and 'ma20' in ma_data:
                ma5 = float(ma_data['ma5'])
                ma20 = float(ma_data['ma20'])

                # 价格突破均线
                if current_price > ma5 > ma20:
                    return TradingSignal(
                        signal_id=f"ma_breakthrough_{timestamp.timestamp()}",
                        signal_type=SignalSourceType.TECHNICAL,
                        direction="buy",
                        strength=SignalStrength.MODERATE,
                        confidence=0.65,
                        message="价格突破短期均线",
                        details={"price": current_price, "ma5": ma5, "ma20": ma20},
                        timestamp=timestamp,
                        source_data=ma_data
                    )
                elif current_price < ma5 < ma20:
                    return TradingSignal(
                        signal_id=f"ma_breakdown_{timestamp.timestamp()}",
                        signal_type=SignalSourceType.TECHNICAL,
                        direction="sell",
                        strength=SignalStrength.MODERATE,
                        confidence=0.65,
                        message="价格跌破短期均线",
                        details={"price": current_price, "ma5": ma5, "ma20": ma20},
                        timestamp=timestamp,
                        source_data=ma_data
                    )
        except Exception as e:
            logger.info(f"均线信号检测错误: {e}")

        return None

    def _detect_price_breakthrough(self, kdata: pd.DataFrame, timestamp: datetime) -> Optional[TradingSignal]:
        """检测价格突破信号"""
        try:
            if len(kdata) < 20:
                return None

            recent_data = kdata.tail(20)
            current_price = float(recent_data.iloc[-1]['close'])
            recent_high = float(recent_data['high'].max())
            recent_low = float(recent_data['low'].min())

            # 突破近期高点
            if current_price >= recent_high * 1.02:  # 2%的突破确认
                return TradingSignal(
                    signal_id=f"price_breakthrough_high_{timestamp.timestamp()}",
                    signal_type=SignalSourceType.TECHNICAL,
                    direction="buy",
                    strength=SignalStrength.STRONG,
                    confidence=0.8,
                    message=f"突破近期高点 ({recent_high:.2f})",
                    details={"current_price": current_price, "recent_high": recent_high},
                    timestamp=timestamp,
                    source_data={"breakthrough_type": "high"}
                )
            # 跌破近期低点
            elif current_price <= recent_low * 0.98:  # 2%的跌破确认
                return TradingSignal(
                    signal_id=f"price_breakdown_low_{timestamp.timestamp()}",
                    signal_type=SignalSourceType.TECHNICAL,
                    direction="sell",
                    strength=SignalStrength.STRONG,
                    confidence=0.8,
                    message=f"跌破近期低点 ({recent_low:.2f})",
                    details={"current_price": current_price, "recent_low": recent_low},
                    timestamp=timestamp,
                    source_data={"breakdown_type": "low"}
                )
        except Exception as e:
            logger.info(f"价格突破信号检测错误: {e}")

        return None

class SentimentSignalDetector:
    """情绪信号检测器"""

    def __init__(self):
        self.name = "情绪信号检测器"

    def detect_signals(self, sentiment_data: Dict[str, Any]) -> List[TradingSignal]:
        """检测情绪信号"""
        signals = []
        current_time = datetime.now()

        try:
            # 恐贪指数信号
            if 'fear_greed_index' in sentiment_data:
                fear_greed_signal = self._detect_fear_greed_signal(
                    float(sentiment_data['fear_greed_index']), current_time
                )
                if fear_greed_signal:
                    signals.append(fear_greed_signal)

            # 新闻情绪信号
            if 'news_sentiment' in sentiment_data:
                news_signal = self._detect_news_sentiment_signal(
                    float(sentiment_data['news_sentiment']), current_time
                )
                if news_signal:
                    signals.append(news_signal)

            # 资金流向信号
            if 'money_flow' in sentiment_data:
                money_flow_signal = self._detect_money_flow_signal(
                    float(sentiment_data['money_flow']), current_time
                )
                if money_flow_signal:
                    signals.append(money_flow_signal)

        except Exception as e:
            logger.info(f"情绪信号检测错误: {e}")

        return signals

    def _detect_fear_greed_signal(self, fear_greed_index: float, timestamp: datetime) -> Optional[TradingSignal]:
        """检测恐贪指数信号"""
        if fear_greed_index >= 85:
            return TradingSignal(
                signal_id=f"fear_greed_extreme_greed_{timestamp.timestamp()}",
                signal_type=SignalSourceType.SENTIMENT,
                direction="sell",
                strength=SignalStrength.VERY_STRONG,
                confidence=0.9,
                message=f"极度贪婪警告 ({fear_greed_index:.0f}/100)",
                details={"fear_greed_index": fear_greed_index},
                timestamp=timestamp,
                source_data={"indicator": "fear_greed_index", "value": fear_greed_index}
            )
        elif fear_greed_index <= 15:
            return TradingSignal(
                signal_id=f"fear_greed_extreme_fear_{timestamp.timestamp()}",
                signal_type=SignalSourceType.SENTIMENT,
                direction="buy",
                strength=SignalStrength.VERY_STRONG,
                confidence=0.9,
                message=f"极度恐惧机会 ({fear_greed_index:.0f}/100)",
                details={"fear_greed_index": fear_greed_index},
                timestamp=timestamp,
                source_data={"indicator": "fear_greed_index", "value": fear_greed_index}
            )
        return None

    def _detect_news_sentiment_signal(self, news_sentiment: float, timestamp: datetime) -> Optional[TradingSignal]:
        """检测新闻情绪信号"""
        # 转换为0-100范围
        sentiment_score = news_sentiment * 100

        if sentiment_score >= 80:
            return TradingSignal(
                signal_id=f"news_very_positive_{timestamp.timestamp()}",
                signal_type=SignalSourceType.NEWS,
                direction="buy",
                strength=SignalStrength.MODERATE,
                confidence=0.6,
                message=f"新闻情绪极度乐观 ({sentiment_score:.0f}/100)",
                details={"news_sentiment": sentiment_score},
                timestamp=timestamp,
                source_data={"indicator": "news_sentiment", "value": news_sentiment}
            )
        elif sentiment_score <= 20:
            return TradingSignal(
                signal_id=f"news_very_negative_{timestamp.timestamp()}",
                signal_type=SignalSourceType.NEWS,
                direction="sell",
                strength=SignalStrength.MODERATE,
                confidence=0.6,
                message=f"新闻情绪极度悲观 ({sentiment_score:.0f}/100)",
                details={"news_sentiment": sentiment_score},
                timestamp=timestamp,
                source_data={"indicator": "news_sentiment", "value": news_sentiment}
            )
        return None

    def _detect_money_flow_signal(self, money_flow: float, timestamp: datetime) -> Optional[TradingSignal]:
        """检测资金流向信号"""
        if money_flow >= 0.8:
            return TradingSignal(
                signal_id=f"money_flow_strong_inflow_{timestamp.timestamp()}",
                signal_type=SignalSourceType.MONEY_FLOW,
                direction="buy",
                strength=SignalStrength.STRONG,
                confidence=0.75,
                message=f"大量资金流入 ({money_flow:.2f})",
                details={"money_flow": money_flow},
                timestamp=timestamp,
                source_data={"indicator": "money_flow", "value": money_flow}
            )
        elif money_flow <= -0.8:
            return TradingSignal(
                signal_id=f"money_flow_strong_outflow_{timestamp.timestamp()}",
                signal_type=SignalSourceType.MONEY_FLOW,
                direction="sell",
                strength=SignalStrength.STRONG,
                confidence=0.75,
                message=f"大量资金流出 ({money_flow:.2f})",
                details={"money_flow": money_flow},
                timestamp=timestamp,
                source_data={"indicator": "money_flow", "value": money_flow}
            )
        return None

class SignalAggregator(QObject):
    """
    信号聚合器 - 核心组件

    负责多源信号(TECHNICAL/SENTIMENT/FUNDAMENTAL/MONEY_FLOW)的聚合、加权评分与警报生成。

    优先级规则:
    - 信号优先级: 时间维度(最新信号) > 信号强度(SignalStrength) > 信号源可信度
    - 评分权重: 技术类(0.4) > 情绪类(0.3) > 基本面(0.2) > 资金流向(0.1)
    - 冲突处理: 同一方向至少2个信号才触发聚合警报，看涨/看跌分别独立聚合
    - 综合置信度: Σ(置信度 × 权重 × 强度系数) / Σ(权重)，强度系数 = SignalStrength.value / 5.0
    - 警报级别: confidence >= 0.8 → SUCCESS/DANGER, >= 0.6 → WARNING, < 0.6 → INFO
    - 特殊组合: 技术超买 + 情绪贪婪 → DANGER(0.9), 技术突破 + 情绪恐惧 → WARNING(0.7)
    """

    # 信号
    alert_generated = pyqtSignal(AggregatedAlert)  # 生成聚合警报
    signal_detected = pyqtSignal(TradingSignal)    # 检测到单个信号

    def __init__(self):
        super().__init__()
        self.technical_detector = TechnicalSignalDetector()
        self.sentiment_detector = SentimentSignalDetector()

        # 信号权重配置
        self.signal_weights = {
            SignalSourceType.TECHNICAL: 0.4,
            SignalSourceType.SENTIMENT: 0.3,
            SignalSourceType.FUNDAMENTAL: 0.2,
            SignalSourceType.MONEY_FLOW: 0.1
        }

        # 信号历史记录
        self.signal_history: List[TradingSignal] = []
        self.alert_history: List[AggregatedAlert] = []

    def _deduplicate_signals(self, signals: List[TradingSignal]) -> List[TradingSignal]:
        from datetime import timedelta

        if not signals:
            return signals

        groups: Dict[SignalSourceType, List[TradingSignal]] = {}
        for signal in signals:
            signal_type = signal.signal_type
            if signal_type not in groups:
                groups[signal_type] = []
            groups[signal_type].append(signal)

        deduplicated: List[TradingSignal] = []
        time_window = timedelta(minutes=5)

        for signal_type, group_signals in groups.items():
            sorted_signals = sorted(group_signals, key=lambda s: s.timestamp)
            if not sorted_signals:
                continue
            current_group = [sorted_signals[0]]
            for sig in sorted_signals[1:]:
                if sig.timestamp - current_group[-1].timestamp <= time_window:
                    current_group.append(sig)
                else:
                    latest = current_group[-1]
                    if len(current_group) > 1:
                        latest.message = "; ".join(s.message for s in current_group)
                    deduplicated.append(latest)
                    current_group = [sig]
            latest = current_group[-1]
            if len(current_group) > 1:
                latest.message = "; ".join(s.message for s in current_group)
            deduplicated.append(latest)

        return deduplicated

    def process_data(self,
                     kdata: pd.DataFrame,
                     technical_indicators: Dict[str, Any],
                     sentiment_data: Dict[str, Any],
                     fundamental_data: Optional[Dict[str, Any]] = None) -> List[AggregatedAlert]:
        """处理多源数据并生成聚合警报"""

        all_signals = []

        # 检测技术信号 - 趋势类/反转类信号
        technical_signals = self.technical_detector.detect_signals(kdata, technical_indicators)
        all_signals.extend(technical_signals)

        # 检测情绪信号 - 成交量类/情绪类信号
        sentiment_signals = self.sentiment_detector.detect_signals(sentiment_data)
        all_signals.extend(sentiment_signals)

        all_signals = self._deduplicate_signals(all_signals)

        # 发射单个信号
        for signal in all_signals:
            self.signal_detected.emit(signal)

        # 存储信号历史（未去重的原始信号）
        self.signal_history.extend(all_signals)

        # 生成聚合警报 - 按方向分组，每方向至少2个信号触发
        alerts = self._generate_aggregated_alerts(all_signals)

        # 发射聚合警报
        for alert in alerts:
            self.alert_generated.emit(alert)
            self.alert_history.append(alert)

        return alerts

    def _generate_aggregated_alerts(self, signals: List[TradingSignal]) -> List[AggregatedAlert]:
        """
        生成聚合警报

        聚合规则:
        1. 按方向分组(buy/sell)，每组独立聚合，不混合
        2. 同一方向至少2个信号才触发聚合警报（避免单一误报）
        3. 冲突处理: 看涨/看跌信号同时存在时，分别独立生成各自方向的警报
        4. 特殊组合检测: 跨信号类型的组合信号（如技术超买+情绪贪婪）具有更高权重
        """
        alerts = []
        current_time = datetime.now()

        if not signals:
            return alerts

        # 按方向分组信号 - 看涨/看跌分别独立聚合，互不干扰
        buy_signals = [s for s in signals if s.direction == "buy"]
        sell_signals = [s for s in signals if s.direction == "sell"]

        # 生成买入警报 - 至少2个同向信号触发
        if len(buy_signals) >= 2:
            alert = self._create_multi_signal_alert(buy_signals, "buy", current_time)
            if alert:
                alerts.append(alert)

        # 生成卖出警报 - 至少2个同向信号触发
        if len(sell_signals) >= 2:
            alert = self._create_multi_signal_alert(sell_signals, "sell", current_time)
            if alert:
                alerts.append(alert)

        # 检测特殊组合信号 - 跨类型的信号叠加具有更高的预测价值
        special_alerts = self._detect_special_combinations(signals, current_time)
        alerts.extend(special_alerts)

        return alerts

    def _create_multi_signal_alert(self, signals: List[TradingSignal], direction: str, timestamp: datetime) -> Optional[AggregatedAlert]:
        """
        创建多信号聚合警报

        加权评分公式:
        综合置信度 = Σ(信号置信度 × 信号源权重 × 强度系数) / Σ(信号源权重)
        - 信号源权重: TECHNICAL(0.4) > SENTIMENT(0.3) > FUNDAMENTAL(0.2) > MONEY_FLOW(0.1)
        - 强度系数: SignalStrength.value / 5.0，将1-5的强度映射到0.2-1.0
        """
        if not signals:
            return None

        # 计算综合置信度 - 加权平均，考虑信号源类型权重和信号强度
        weighted_confidence = 0
        total_weight = 0

        for signal in signals:
            # 获取信号源权重: 技术类(0.4) > 情绪类(0.3) > 基本面(0.2) > 资金流向(0.1)
            weight = self.signal_weights.get(signal.signal_type, 0.1)
            # 强度系数: 将SignalStrength(1-5)映射到0.2-1.0范围
            strength_multiplier = signal.strength.value / 5.0
            weighted_confidence += signal.confidence * weight * strength_multiplier
            total_weight += weight

        if total_weight > 0:
            overall_confidence = weighted_confidence / total_weight
        else:
            overall_confidence = 0.5

        # 根据综合置信度划分警报级别
        # confidence >= 0.8: 高置信度 → SUCCESS(buy) / DANGER(sell)
        # confidence >= 0.6: 中等置信度 → WARNING
        # confidence < 0.6: 低置信度 → INFO
        if overall_confidence >= 0.8:
            level = AlertLevel.SUCCESS if direction == "buy" else AlertLevel.DANGER
        elif overall_confidence >= 0.6:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.INFO

        # 生成消息
        signal_types = list(set(s.signal_type.value for s in signals))
        title = f"{'买入' if direction == 'buy' else '卖出'}信号聚合"
        message = f"检测到 {len(signals)} 个{direction}信号 ({', '.join(signal_types)})"

        return AggregatedAlert(
            alert_id=f"multi_signal_{direction}_{timestamp.timestamp()}",
            level=level,
            title=title,
            message=message,
            signals=signals,
            overall_confidence=overall_confidence,
            recommended_action=f"建议{direction}",
            timestamp=timestamp
        )

    def _detect_special_combinations(self, signals: List[TradingSignal], timestamp: datetime) -> List[AggregatedAlert]:
        """
        检测特殊信号组合

        跨类型信号的叠加具有更高的预测价值。
        冲突处理规则: 当同类方向信号与异类情绪信号叠加时，以特殊组合为准，因为它综合了技术面和情绪面。
        """
        alerts = []

        # 检测"技术超买 + 情绪贪婪"组合 - 双重看空确认，置信度0.9
        technical_overbought = any(
            s.signal_type == SignalSourceType.TECHNICAL and
            s.direction == "sell" and
            "超买" in s.message
            for s in signals
        )

        sentiment_greed = any(
            s.signal_type == SignalSourceType.SENTIMENT and
            s.direction == "sell" and
            "贪婪" in s.message
            for s in signals
        )

        if technical_overbought and sentiment_greed:
            relevant_signals = [s for s in signals if
                                (s.signal_type == SignalSourceType.TECHNICAL and "超买" in s.message) or
                                (s.signal_type == SignalSourceType.SENTIMENT and "贪婪" in s.message)]

            alert = AggregatedAlert(
                alert_id=f"overbought_greed_combo_{timestamp.timestamp()}",
                level=AlertLevel.DANGER,
                title=" 强烈卖出信号",
                message="技术面超买 + 市场极度贪婪，建议谨慎或减仓",
                signals=relevant_signals,
                overall_confidence=0.9,
                recommended_action="强烈建议卖出或减仓",
                timestamp=timestamp
            )
            alerts.append(alert)

        # 检测"技术突破 + 情绪恐惧"组合（逆向思维机会）- 技术面向好但市场恐惧，置信度0.7
        technical_breakthrough = any(
            s.signal_type == SignalSourceType.TECHNICAL and
            s.direction == "buy" and
            "突破" in s.message
            for s in signals
        )

        sentiment_fear = any(
            s.signal_type == SignalSourceType.SENTIMENT and
            "恐惧" in s.message
            for s in signals
        )

        if technical_breakthrough and sentiment_fear:
            relevant_signals = [s for s in signals if
                                (s.signal_type == SignalSourceType.TECHNICAL and "突破" in s.message) or
                                (s.signal_type == SignalSourceType.SENTIMENT and "恐惧" in s.message)]

            alert = AggregatedAlert(
                alert_id=f"breakthrough_fear_combo_{timestamp.timestamp()}",
                level=AlertLevel.WARNING,
                title=" 谨慎乐观信号",
                message="技术面突破 + 市场恐惧，可能存在逆向投资机会",
                signals=relevant_signals,
                overall_confidence=0.7,
                recommended_action="谨慎买入，密切关注",
                timestamp=timestamp
            )
            alerts.append(alert)

        return alerts

    def get_signal_statistics(self) -> Dict[str, Any]:
        """获取信号统计信息"""
        recent_signals = [s for s in self.signal_history if
                          (datetime.now() - s.timestamp).seconds < 3600]  # 最近1小时

        return {
            "total_signals": len(self.signal_history),
            "recent_signals": len(recent_signals),
            "buy_signals": len([s for s in recent_signals if s.direction == "buy"]),
            "sell_signals": len([s for s in recent_signals if s.direction == "sell"]),
            "average_confidence": np.mean([s.confidence for s in recent_signals]) if recent_signals else 0,
            "signal_types": list(set(s.signal_type.value for s in recent_signals))
        }
