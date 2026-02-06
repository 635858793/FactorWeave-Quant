"""
基本面数据抽象基类

定义所有基本面数据类必须实现的接口，提供统一的基本面数据处理能力
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from loguru import logger

from core.plugin_types import AssetType


class FundamentalScoreLevel(Enum):
    """基本面评分等级"""
    EXCELLENT = "excellent"
    GOOD = "good"
    MODERATE = "moderate"
    POOR = "poor"
    VERY_POOR = "very_poor"


class FundamentalScoreCategory(Enum):
    """基本面评分类别"""
    VALUATION = "valuation"  # 估值
    PROFITABILITY = "profitability"  # 盈利能力
    GROWTH = "growth"  # 成长性
    FINANCIAL_HEALTH = "financial_health"  # 财务健康


@dataclass
class FundamentalIndicator:
    """基本面指标"""
    name: str  # 指标名称
    value: float  # 指标值
    weight: float = 1.0  # 权重
    min_value: float = 0.0  # 最小值
    max_value: float = 100.0  # 最大值
    description: str = ""  # 描述
    is_reverse: bool = False  # 是否反向指标（值越小越好）
    normalization_type: str = "linear"  # 归一化类型：linear, logarithmic

    def get_normalized_value(self) -> float:
        """获取归一化后的值（0-1）"""
        try:
            if self.max_value <= self.min_value:
                return 0.0

            normalized = (self.value - self.min_value) / (self.max_value - self.min_value)
            normalized = max(0.0, min(1.0, normalized))

            if self.is_reverse:
                normalized = 1.0 - normalized

            if self.normalization_type == "logarithmic":
                if normalized > 0:
                    normalized = np.log(normalized + 1) / np.log(2)

            return normalized
        except Exception as e:
            logger.error(f"归一化指标失败: {self.name}, 错误: {e}")
            return 0.0


class FundamentalDataBase(ABC):
    """基本面数据抽象基类"""

    def __init__(self, asset_type: str, asset_code: str, raw_data: Dict[str, Any]):
        """
        初始化基本面数据

        Args:
            asset_type: 资产类型
            asset_code: 资产代码
            raw_data: 原始数据
        """
        self.asset_type = asset_type
        self.asset_code = asset_code
        self.raw_data = raw_data
        self._indicators: Dict[str, FundamentalIndicator] = {}
        self._score: Optional[float] = None

    @abstractmethod
    def _calculate_indicators(self):
        """计算基本面指标（子类实现）"""
        pass

    def add_indicator(self, indicator: FundamentalIndicator):
        """添加指标"""
        self._indicators[indicator.name] = indicator

    def get_indicator(self, name: str) -> Optional[FundamentalIndicator]:
        """获取指标"""
        return self._indicators.get(name)

    def get_all_indicators(self) -> Dict[str, FundamentalIndicator]:
        """获取所有指标"""
        return self._indicators.copy()

    def get_score(self) -> float:
        """获取基本面评分（0-100）"""
        if self._score is not None:
            return self._score

        if not self._indicators:
            self._score = 0.0
            return self._score

        total_weight = 0.0
        weighted_score = 0.0

        for indicator in self._indicators.values():
            normalized_value = indicator.get_normalized_value()
            weighted_score += normalized_value * indicator.weight
            total_weight += indicator.weight

        if total_weight > 0:
            self._score = weighted_score / total_weight * 100
        else:
            self._score = 0.0

        return self._score

    def get_score_level(self) -> FundamentalScoreLevel:
        """获取基本面评分等级"""
        score = self.get_score()

        if score >= 80:
            return FundamentalScoreLevel.EXCELLENT
        elif score >= 60:
            return FundamentalScoreLevel.GOOD
        elif score >= 40:
            return FundamentalScoreLevel.MODERATE
        elif score >= 20:
            return FundamentalScoreLevel.POOR
        else:
            return FundamentalScoreLevel.VERY_POOR

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'asset_type': self.asset_type,
            'asset_code': self.asset_code,
            'score': self.get_score(),
            'score_level': self.get_score_level().value,
            'indicators': {
                name: {
                    'value': indicator.value,
                    'normalized_value': indicator.get_normalized_value(),
                    'weight': indicator.weight,
                    'description': indicator.description
                }
                for name, indicator in self._indicators.items()
            }
        }

    def __str__(self) -> str:
        """字符串表示"""
        return f"FundamentalData(type={self.asset_type}, code={self.asset_code}, score={self.get_score():.2f})"

    def __repr__(self) -> str:
        """对象表示"""
        return self.__str__()
