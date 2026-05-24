"""
情绪数据源插件接口定义

此模块定义了情绪数据源插件的标准接口和数据结构，
为创建情绪数据源插件提供了规范的基础架构。

主要组件：
- SentimentData: 单个情绪数据点的数据结构
- SentimentResponse: 情绪数据查询响应的数据结构
- ISentimentDataSource: 情绪数据源插件的抽象接口
- BaseSentimentPlugin: 提供通用功能的基础插件类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import json
import hashlib
from enum import Enum
from core.plugin_types import PluginType, PluginCategory

class SentimentStatus(Enum):
    """情绪状态枚举"""
    EXTREMELY_BULLISH = "极度看涨"
    BULLISH = "看涨"
    NEUTRAL = "中性"
    BEARISH = "看跌"
    EXTREMELY_BEARISH = "极度看跌"
    UNKNOWN = "未知"

class TradingSignal(Enum):
    """交易信号枚举"""
    STRONG_BUY = "强烈买入"
    BUY = "买入"
    HOLD = "持有"
    SELL = "卖出"
    STRONG_SELL = "强烈卖出"
    NO_SIGNAL = "无信号"

@dataclass
class SentimentData:
    """情绪数据点结构"""
    indicator_name: str  # 指标名称
    value: float  # 数值
    status: str  # 状态描述
    change: float  # 变化量
    signal: str  # 交易信号
    suggestion: str  # 投资建议
    timestamp: datetime  # 时间戳
    source: str  # 数据源
    confidence: float = 0.0  # 置信度 (0-1)
    color: str = "#808080"  # 显示颜色
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

@dataclass
class SentimentResponse:
    """情绪数据查询响应"""
    success: bool  # 是否成功
    data: List[SentimentData] = field(default_factory=list)  # 情绪数据列表
    composite_score: float = 0.0  # 综合情绪评分 (-1到1)
    error_message: str = ""  # 错误信息
    data_quality: str = "unknown"  # 数据质量评级
    update_time: datetime = field(default_factory=datetime.now)  # 更新时间
    cache_used: bool = False  # 是否使用了缓存
    has_real_data: bool = False  # 是否包含真实数据（非模拟/假数据）

class ISentimentDataSource(ABC):
    """情绪数据源插件接口"""

    @abstractmethod
    def fetch_sentiment_data(self) -> SentimentResponse:
        """
        获取情绪数据

        Returns:
            SentimentResponse: 包含情绪数据的响应对象
        """
        pass

    @abstractmethod
    def get_available_indicators(self) -> List[str]:
        """
        获取可用的情绪指标列表

        Returns:
            List[str]: 指标名称列表
        """
        pass

    @abstractmethod
    def validate_data_quality(self, data: List[SentimentData]) -> str:
        """
        验证数据质量

        Args:
            data: 待验证的情绪数据

        Returns:
            str: 数据质量评级 ('excellent', 'good', 'fair', 'poor')
        """
        pass

    def calculate_composite_sentiment(self,
                                      data: List[SentimentData],
                                      weights: Optional[Dict[str, float]] = None) -> float:
        """
        计算综合情绪评分

        Args:
            data: 情绪数据列表
            weights: 各指标权重，如果为None则使用默认权重

        Returns:
            float: 综合评分 (-1到1)
        """
        if not data:
            return 0.0

        # 默认权重
        default_weights = {
            '新闻情绪': 0.3,
            '微博情绪': 0.2,
            'VIX指数': 0.25,
            '消费者信心': 0.15,
            '外汇情绪': 0.1
        }

        if weights is None:
            weights = default_weights

        total_score = 0.0
        total_weight = 0.0

        for sentiment in data:
            indicator_name = sentiment.indicator_name
            weight = weights.get(indicator_name, 0.1)  # 默认权重

            # 标准化情绪值到-1到1范围
            normalized_value = self._normalize_sentiment_value(sentiment.value, indicator_name)

            # 考虑置信度
            confidence_factor = max(0.1, sentiment.confidence)
            weighted_score = normalized_value * weight * confidence_factor

            total_score += weighted_score
            total_weight += weight * confidence_factor

        # 避免除零错误
        if total_weight == 0:
            return 0.0

        # 归一化到-1到1范围
        composite_score = total_score / total_weight
        return max(-1.0, min(1.0, composite_score))

    def _normalize_sentiment_value(self, value: float, indicator_name: str) -> float:
        """
        将情绪值标准化到-1到1范围

        Args:
            value: 原始值
            indicator_name: 指标名称

        Returns:
            float: 标准化后的值
        """
        # 根据不同指标类型进行标准化
        if 'VIX' in indicator_name or '恐慌' in indicator_name:
            # VIX类指标：高值表示恐慌（负面）
            if value >= 30:
                return -0.8  # 极度恐慌
            elif value >= 20:
                return -0.4  # 恐慌
            elif value <= 10:
                return 0.6   # 乐观
            else:
                return 0.2   # 中性偏乐观

        elif '消费者信心' in indicator_name:
            # 消费者信心指数：通常在80-120范围
            if value >= 110:
                return 0.8   # 非常乐观
            elif value >= 100:
                return 0.4   # 乐观
            elif value <= 80:
                return -0.6  # 悲观
            else:
                return 0.0   # 中性

        elif '情绪' in indicator_name:
            # 情绪指标：通常已经在0-100范围
            return (value - 50) / 50  # 转换到-1到1范围

        else:
            # 默认处理：假设值在0-100范围
            return (value - 50) / 50

    def get_sentiment_status(self, composite_score: float) -> str:
        """根据综合评分获取情绪状态"""
        if composite_score >= 0.6:
            return SentimentStatus.EXTREMELY_BULLISH.value
        elif composite_score >= 0.2:
            return SentimentStatus.BULLISH.value
        elif composite_score >= -0.2:
            return SentimentStatus.NEUTRAL.value
        elif composite_score >= -0.6:
            return SentimentStatus.BEARISH.value
        else:
            return SentimentStatus.EXTREMELY_BEARISH.value

    def get_trading_signal(self, composite_score: float) -> str:
        """根据综合评分获取交易信号"""
        if composite_score >= 0.7:
            return TradingSignal.STRONG_BUY.value
        elif composite_score >= 0.3:
            return TradingSignal.BUY.value
        elif composite_score >= -0.3:
            return TradingSignal.HOLD.value
        elif composite_score >= -0.7:
            return TradingSignal.SELL.value
        else:
            return TradingSignal.STRONG_SELL.value

    def get_investment_suggestion(self, composite_score: float) -> str:
        """根据综合评分获取投资建议"""
        if composite_score >= 0.6:
            return "市场情绪极度乐观，建议适当获利了结，防范风险"
        elif composite_score >= 0.2:
            return "市场情绪乐观，可考虑适度加仓"
        elif composite_score >= -0.2:
            return "市场情绪中性，建议保持现有仓位"
        elif composite_score >= -0.6:
            return "市场情绪悲观，建议减仓观望"
        else:
            return "市场情绪极度悲观，建议空仓或考虑抄底机会"

    def get_status_color(self, composite_score: float) -> str:
        """根据综合评分获取状态颜色"""
        if composite_score >= 0.6:
            return "#FF4444"  # 红色：极度乐观（警示）
        elif composite_score >= 0.2:
            return "#FF8800"  # 橙色：乐观
        elif composite_score >= -0.2:
            return "#FFAA00"  # 黄色：中性
        elif composite_score >= -0.6:
            return "#88AA00"  # 绿色：悲观
        else:
            return "#00AA44"  # 深绿色：极度悲观（可能是机会）

class BaseSentimentPlugin(ISentimentDataSource):
    """情绪数据源插件基础类"""

    def __init__(self):
        super().__init__()
        self._cache: Dict[str, Any] = {}
        self._cache_duration = timedelta(minutes=5)  # 默认缓存5分钟
        self._last_fetch_time: Optional[datetime] = None

    def initialize(self, config: dict = None) -> bool:
        """初始化插件"""
        return True

    def cleanup(self) -> None:
        """清理插件资源"""
        self._cache.clear()

    def fetch_sentiment_data(self) -> SentimentResponse:
        """
        获取情绪数据（带缓存）

        Returns:
            SentimentResponse: 情绪数据响应
        """
        try:
            # 检查缓存是否有效
            if self._is_cache_valid():
                cached_response = self._cache.get('sentiment_data')
                if cached_response:
                    cached_response.cache_used = True
                    return cached_response

            # 获取新数据
            response = self._fetch_raw_sentiment_data()

            # 计算综合评分
            if response.success and response.data:
                response.composite_score = self.calculate_composite_sentiment(response.data)
                response.data_quality = self.validate_data_quality(response.data)

            # 缓存结果
            self._cache['sentiment_data'] = response
            self._last_fetch_time = datetime.now()

            return response

        except Exception as e:
            return SentimentResponse(
                success=False,
                error_message=f"获取情绪数据失败: {str(e)}",
                update_time=datetime.now()
            )

    @abstractmethod
    def _fetch_raw_sentiment_data(self) -> SentimentResponse:
        """
        获取原始情绪数据（子类实现）

        Returns:
            SentimentResponse: 原始情绪数据响应
        """
        pass

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._last_fetch_time is None:
            return False

        return datetime.now() - self._last_fetch_time < self._cache_duration

    def get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'cache_duration_minutes': 5,
            'retry_attempts': 3,
            'timeout_seconds': 30,
            'enabled': True
        }

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置有效性"""
        required_keys = ['enabled']
        for key in required_keys:
            if key not in config:
                return False
        return True
