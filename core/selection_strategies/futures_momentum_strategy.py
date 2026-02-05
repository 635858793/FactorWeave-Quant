"""
期货动量策略

基于流动性、供需关系和市场情绪选择期货合约，重点关注高流动性、供需平衡的合约。
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from typing import Dict, Any, List

from loguru import logger

from core.selection_strategies.selection_strategy_base import (
    SelectionStrategyBase,
    SelectionCriteria,
    SelectionResult,
    StrategyType
)
from core.fundamental_data.futures_fundamental_data import FuturesFundamentalData
from core.plugin_types import AssetType


class FuturesMomentumStrategy(SelectionStrategyBase):
    """期货动量策略"""

    def __init__(self):
        super().__init__(AssetType.FUTURES, StrategyType.MOMENTUM)
        self._liquidity_weight = 0.4
        self._supply_demand_weight = 0.4
        self._sentiment_weight = 0.2

    def calculate_score(self, fundamental_data: FuturesFundamentalData) -> float:
        """计算期货评分

        评分基于：
        - 流动性评分（40%）：持仓量、成交量（越高越好）
        - 供需评分（40%）：库存、供需比、产量、消费量（供需平衡最好）
        - 市场情绪评分（20%）：基差（正基差表示看涨）

        Args:
            fundamental_data: 期货基本面数据

        Returns:
            float: 评分（0-100）
        """
        try:
            liquidity_score = fundamental_data.get_liquidity_score()
            supply_demand_score = fundamental_data.get_supply_demand_score()
            sentiment_score = fundamental_data.get_market_sentiment_score()

            total_score = (
                liquidity_score * self._liquidity_weight +
                supply_demand_score * self._supply_demand_weight +
                sentiment_score * self._sentiment_weight
            )

            logger.debug(
                f"期货动量评分: {fundamental_data.symbol} = {total_score:.2f} "
                f"(流动性={liquidity_score:.2f}, 供需={supply_demand_score:.2f}, 情绪={sentiment_score:.2f})"
            )

            return total_score

        except Exception as e:
            logger.error(f"计算期货动量评分失败: {fundamental_data.symbol}, 错误: {e}")
            return 0.0

    def select_assets(
        self,
        fundamental_data_list: List[FuturesFundamentalData],
        criteria: SelectionCriteria
    ) -> SelectionResult:
        """选择期货

        Args:
            fundamental_data_list: 期货基本面数据列表
            criteria: 选股标准

        Returns:
            SelectionResult: 选股结果
        """
        logger.info(f"开始期货动量选股: {len(fundamental_data_list)}个合约")

        try:
            if not self.validate_criteria(criteria):
                raise ValueError("选股标准无效")

            scores = self.calculate_scores(fundamental_data_list)
            filtered_scores = self.filter_by_score(scores, criteria.min_score)
            selected_assets = self.select_top_assets(filtered_scores, criteria.max_assets)

            result = SelectionResult(
                asset_type=self.asset_type,
                strategy_type=self.strategy_type,
                selection_date=criteria.selection_date,
                selected_assets=selected_assets,
                scores=filtered_scores,
                metadata={
                    "total_assets": len(fundamental_data_list),
                    "filtered_assets": len(filtered_scores),
                    "selected_assets": len(selected_assets),
                    "liquidity_weight": self._liquidity_weight,
                    "supply_demand_weight": self._supply_demand_weight,
                    "sentiment_weight": self._sentiment_weight
                }
            )

            logger.info(
                f"期货动量选股完成: 总计={len(fundamental_data_list)}, "
                f"过滤={len(filtered_scores)}, 选中={len(selected_assets)}"
            )

            return result

        except Exception as e:
            logger.error(f"期货动量选股失败: {e}")
            raise

    def validate_criteria(self, criteria: SelectionCriteria) -> bool:
        """验证选股标准是否有效

        Args:
            criteria: 选股标准

        Returns:
            bool: 是否有效
        """
        if criteria.asset_type != AssetType.FUTURES:
            logger.error(f"资产类型不匹配: 期望{AssetType.FUTURES.value}, 实际{criteria.asset_type.value}")
            return False

        if criteria.strategy_type != StrategyType.MOMENTUM:
            logger.error(f"策略类型不匹配: 期望{StrategyType.MOMENTUM.value}, 实际{criteria.strategy_type.value}")
            return False

        if criteria.max_assets <= 0:
            logger.error(f"最大资产数量必须大于0: {criteria.max_assets}")
            return False

        if criteria.min_score < 0 or criteria.min_score > 100:
            logger.error(f"最小评分必须在0-100之间: {criteria.min_score}")
            return False

        return True

    def get_description(self) -> str:
        """获取策略描述"""
        return (
            "期货动量策略：基于流动性、供需关系和市场情绪选择期货合约。"
            "重点关注高流动性、供需平衡的合约。"
            f"流动性权重={self._liquidity_weight:.0%}, "
            f"供需权重={self._supply_demand_weight:.0%}, "
            f"情绪权重={self._sentiment_weight:.0%}"
        )

    def set_weights(
        self,
        liquidity_weight: float = 0.4,
        supply_demand_weight: float = 0.4,
        sentiment_weight: float = 0.2
    ):
        """设置评分权重

        Args:
            liquidity_weight: 流动性权重
            supply_demand_weight: 供需权重
            sentiment_weight: 情绪权重
        """
        total_weight = liquidity_weight + supply_demand_weight + sentiment_weight

        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"权重总和不为1: {total_weight:.2f}，将自动归一化")

        self._liquidity_weight = liquidity_weight / total_weight
        self._supply_demand_weight = supply_demand_weight / total_weight
        self._sentiment_weight = sentiment_weight / total_weight

        logger.info(
            f"设置评分权重: 流动性={self._liquidity_weight:.0%}, "
            f"供需={self._supply_demand_weight:.0%}, "
            f"情绪={self._sentiment_weight:.0%}"
        )

    def get_custom_criteria(self) -> Dict[str, Any]:
        """获取自定义选股标准

        Returns:
            Dict[str, Any]: 自定义选股标准
        """
        return {
            "min_open_interest": 10000.0,
            "min_volume": 50000.0,
            "max_inventory": 1000000.0,
            "min_supply_demand_ratio": 0.8,
            "max_supply_demand_ratio": 1.2,
            "min_basis": -50.0,
            "max_basis": 50.0
        }

    def apply_custom_criteria(
        self,
        fundamental_data: FuturesFundamentalData,
        custom_criteria: Dict[str, Any]
    ) -> bool:
        """应用自定义选股标准

        Args:
            fundamental_data: 期货基本面数据
            custom_criteria: 自定义选股标准

        Returns:
            bool: 是否符合标准
        """
        indicators = fundamental_data.get_key_indicators()

        if 'min_open_interest' in custom_criteria and 'OPEN_INTEREST' in indicators:
            if indicators['OPEN_INTEREST'] < custom_criteria['min_open_interest']:
                return False

        if 'min_volume' in custom_criteria and 'VOLUME' in indicators:
            if indicators['VOLUME'] < custom_criteria['min_volume']:
                return False

        if 'max_inventory' in custom_criteria and 'INVENTORY' in indicators:
            if indicators['INVENTORY'] > custom_criteria['max_inventory']:
                return False

        if 'min_supply_demand_ratio' in custom_criteria and 'SUPPLY_DEMAND_RATIO' in indicators:
            if indicators['SUPPLY_DEMAND_RATIO'] < custom_criteria['min_supply_demand_ratio']:
                return False

        if 'max_supply_demand_ratio' in custom_criteria and 'SUPPLY_DEMAND_RATIO' in indicators:
            if indicators['SUPPLY_DEMAND_RATIO'] > custom_criteria['max_supply_demand_ratio']:
                return False

        if 'min_basis' in custom_criteria and 'BASIS' in indicators:
            if indicators['BASIS'] < custom_criteria['min_basis']:
                return False

        if 'max_basis' in custom_criteria and 'BASIS' in indicators:
            if indicators['BASIS'] > custom_criteria['max_basis']:
                return False

        return True
