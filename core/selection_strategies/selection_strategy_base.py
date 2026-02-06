"""
选股策略抽象基类

定义所有选股策略必须实现的接口，提供统一的选股策略能力。
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from core.fundamental_data.fundamental_data_base import FundamentalData
from core.plugin_types import AssetType


class StrategyType(Enum):
    """策略类型"""
    VALUE = "value"
    MOMENTUM = "momentum"
    GROWTH = "growth"
    QUALITY = "quality"
    TECHNICAL = "technical"
    QUANTITATIVE = "quantitative"
    HYBRID = "hybrid"


@dataclass
class SelectionCriteria:
    """选股标准"""
    asset_type: AssetType
    strategy_type: StrategyType
    selection_date: datetime = field(default_factory=datetime.now)
    max_assets: int = 50
    min_score: float = 0.0
    custom_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "asset_type": self.asset_type.value,
            "strategy_type": self.strategy_type.value,
            "selection_date": self.selection_date.isoformat(),
            "max_assets": self.max_assets,
            "min_score": self.min_score,
            "custom_params": self.custom_params
        }


@dataclass
class SelectionResult:
    """选股结果"""
    asset_type: AssetType
    strategy_type: StrategyType
    selection_date: datetime
    selected_assets: List[str]
    scores: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "asset_type": self.asset_type.value,
            "strategy_type": self.strategy_type.value,
            "selection_date": self.selection_date.isoformat(),
            "selected_assets": self.selected_assets,
            "scores": self.scores,
            "metadata": self.metadata
        }


class SelectionStrategyBase(ABC):
    """选股策略抽象基类"""

    def __init__(self, asset_type: AssetType, strategy_type: StrategyType):
        self.asset_type = asset_type
        self.strategy_type = strategy_type
        self._fundamental_data_cache: Dict[str, FundamentalData] = {}

    @abstractmethod
    def calculate_score(self, fundamental_data: FundamentalData) -> float:
        """计算资产评分

        Args:
            fundamental_data: 基本面数据

        Returns:
            float: 评分（0-100）
        """
        pass

    @abstractmethod
    def select_assets(
        self,
        fundamental_data_list: List[FundamentalData],
        criteria: SelectionCriteria
    ) -> SelectionResult:
        """选择资产

        Args:
            fundamental_data_list: 基本面数据列表
            criteria: 选股标准

        Returns:
            SelectionResult: 选股结果
        """
        pass

    @abstractmethod
    def validate_criteria(self, criteria: SelectionCriteria) -> bool:
        """验证选股标准是否有效

        Args:
            criteria: 选股标准

        Returns:
            bool: 是否有效
        """
        pass

    def cache_fundamental_data(self, fundamental_data: FundamentalData):
        """缓存基本面数据

        Args:
            fundamental_data: 基本面数据
        """
        self._fundamental_data_cache[fundamental_data.symbol] = fundamental_data
        logger.debug(f"缓存基本面数据: {fundamental_data.symbol}")

    def get_cached_fundamental_data(self, symbol: str) -> Optional[FundamentalData]:
        """获取缓存的基本面数据

        Args:
            symbol: 标的代码

        Returns:
            Optional[FundamentalData]: 基本面数据，如果不存在则返回None
        """
        return self._fundamental_data_cache.get(symbol)

    def clear_cache(self):
        """清空缓存"""
        self._fundamental_data_cache.clear()
        logger.debug("清空基本面数据缓存")

    def calculate_scores(
        self,
        fundamental_data_list: List[FundamentalData]
    ) -> Dict[str, float]:
        """批量计算评分

        Args:
            fundamental_data_list: 基本面数据列表

        Returns:
            Dict[str, float]: 评分字典
        """
        scores = {}
        for fundamental_data in fundamental_data_list:
            try:
                score = self.calculate_score(fundamental_data)
                scores[fundamental_data.symbol] = score
                logger.debug(f"计算评分: {fundamental_data.symbol} = {score:.2f}")
            except Exception as e:
                logger.error(f"计算评分失败: {fundamental_data.symbol}, 错误: {e}")
                scores[fundamental_data.symbol] = 0.0

        return scores

    def filter_by_score(
        self,
        scores: Dict[str, float],
        min_score: float
    ) -> Dict[str, float]:
        """根据评分过滤

        Args:
            scores: 评分字典
            min_score: 最小评分

        Returns:
            Dict[str, float]: 过滤后的评分字典
        """
        return {
            symbol: score
            for symbol, score in scores.items()
            if score >= min_score
        }

    def select_top_assets(
        self,
        scores: Dict[str, float],
        max_assets: int
    ) -> List[str]:
        """选择评分最高的资产

        Args:
            scores: 评分字典
            max_assets: 最大资产数量

        Returns:
            List[str]: 选中的资产列表
        """
        sorted_assets = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        selected_assets = [
            symbol for symbol, score in sorted_assets[:max_assets]
        ]

        logger.info(f"选择前{max_assets}个资产: {selected_assets}")
        return selected_assets

    def get_strategy_info(self) -> Dict[str, Any]:
        """获取策略信息

        Returns:
            Dict[str, Any]: 策略信息
        """
        return {
            "asset_type": self.asset_type.value,
            "strategy_type": self.strategy_type.value,
            "strategy_name": self.__class__.__name__,
            "description": self.get_description()
        }

    @abstractmethod
    def get_description(self) -> str:
        """获取策略描述

        Returns:
            str: 策略描述
        """
        pass

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}("
                f"asset_type={self.asset_type.value}, "
                f"strategy_type={self.strategy_type.value})")
