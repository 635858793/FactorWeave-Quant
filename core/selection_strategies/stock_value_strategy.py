"""
股票价值策略

基于估值指标和盈利能力指标选择股票，重点关注低估值、高盈利能力的股票。
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from typing import Dict, Any, List, Optional

from loguru import logger

from core.selection_strategies.selection_strategy_base import (
    SelectionStrategyBase,
    SelectionCriteria,
    SelectionResult,
    StrategyType
)
from core.fundamental_data.stock_fundamental_data import StockFundamentalData
from core.plugin_types import AssetType


class StockValueStrategy(SelectionStrategyBase):
    """股票价值策略"""

    def __init__(self):
        super().__init__(AssetType.STOCK_A, StrategyType.VALUE)
        self._valuation_weight = 0.4
        self._profitability_weight = 0.4
        self._growth_weight = 0.2

    def calculate_score(self, fundamental_data: StockFundamentalData) -> float:
        """计算股票评分

        评分基于：
        - 估值评分（40%）：PE比率、PB比率（越低越好）
        - 盈利能力评分（40%）：ROE、ROA、毛利率、净利率（越高越好）
        - 成长性评分（20%）：营收增长率、利润增长率（越高越好）

        Args:
            fundamental_data: 股票基本面数据

        Returns:
            float: 评分（0-100）
        """
        try:
            valuation_score = fundamental_data.get_valuation_score()
            profitability_score = fundamental_data.get_profitability_score()
            growth_score = fundamental_data.get_growth_score()

            total_score = (
                valuation_score * self._valuation_weight +
                profitability_score * self._profitability_weight +
                growth_score * self._growth_weight
            )

            logger.debug(
                f"股票价值评分: {fundamental_data.symbol} = {total_score:.2f} "
                f"(估值={valuation_score:.2f}, 盈利={profitability_score:.2f}, 成长={growth_score:.2f})"
            )

            return total_score

        except Exception as e:
            logger.error(f"计算股票价值评分失败: {fundamental_data.symbol}, 错误: {e}")
            return 0.0

    def select_assets(
        self,
        fundamental_data_list: List[StockFundamentalData],
        criteria: SelectionCriteria
    ) -> SelectionResult:
        """选择股票

        Args:
            fundamental_data_list: 股票基本面数据列表
            criteria: 选股标准

        Returns:
            SelectionResult: 选股结果
        """
        logger.info(f"开始股票价值选股: {len(fundamental_data_list)}只股票")

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
                    "valuation_weight": self._valuation_weight,
                    "profitability_weight": self._profitability_weight,
                    "growth_weight": self._growth_weight
                }
            )

            logger.info(
                f"股票价值选股完成: 总计={len(fundamental_data_list)}, "
                f"过滤={len(filtered_scores)}, 选中={len(selected_assets)}"
            )

            return result

        except Exception as e:
            logger.error(f"股票价值选股失败: {e}")
            raise

    def validate_criteria(self, criteria: SelectionCriteria) -> bool:
        """验证选股标准是否有效

        Args:
            criteria: 选股标准

        Returns:
            bool: 是否有效
        """
        if criteria.asset_type != AssetType.STOCK_A:
            logger.error(f"资产类型不匹配: 期望{AssetType.STOCK_A.value}, 实际{criteria.asset_type.value}")
            return False

        if criteria.strategy_type != StrategyType.VALUE:
            logger.error(f"策略类型不匹配: 期望{StrategyType.VALUE.value}, 实际{criteria.strategy_type.value}")
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
            "股票价值策略：基于估值指标和盈利能力指标选择股票。"
            "重点关注低估值、高盈利能力的股票。"
            f"估值权重={self._valuation_weight:.0%}, "
            f"盈利能力权重={self._profitability_weight:.0%}, "
            f"成长性权重={self._growth_weight:.0%}"
        )

    def set_weights(
        self,
        valuation_weight: float = 0.4,
        profitability_weight: float = 0.4,
        growth_weight: float = 0.2
    ):
        """设置评分权重

        Args:
            valuation_weight: 估值权重
            profitability_weight: 盈利能力权重
            growth_weight: 成长性权重
        """
        total_weight = valuation_weight + profitability_weight + growth_weight

        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"权重总和不为1: {total_weight:.2f}，将自动归一化")

        self._valuation_weight = valuation_weight / total_weight
        self._profitability_weight = profitability_weight / total_weight
        self._growth_weight = growth_weight / total_weight

        logger.info(
            f"设置评分权重: 估值={self._valuation_weight:.0%}, "
            f"盈利能力={self._profitability_weight:.0%}, "
            f"成长={self._growth_weight:.0%}"
        )

    def get_custom_criteria(self) -> Dict[str, Any]:
        """获取自定义选股标准

        Returns:
            Dict[str, Any]: 自定义选股标准
        """
        return {
            "min_pe_ratio": 5.0,
            "max_pe_ratio": 30.0,
            "min_pb_ratio": 0.5,
            "max_pb_ratio": 5.0,
            "min_roe": 10.0,
            "max_debt_ratio": 70.0,
            "min_revenue_growth": 0.0,
            "min_profit_growth": 0.0
        }

    def apply_custom_criteria(
        self,
        fundamental_data: StockFundamentalData,
        custom_criteria: Dict[str, Any]
    ) -> bool:
        """应用自定义选股标准

        Args:
            fundamental_data: 股票基本面数据
            custom_criteria: 自定义选股标准

        Returns:
            bool: 是否符合标准
        """
        indicators = fundamental_data.get_key_indicators()

        if 'min_pe_ratio' in custom_criteria and 'PE_RATIO' in indicators:
            if indicators['PE_RATIO'] < custom_criteria['min_pe_ratio']:
                return False

        if 'max_pe_ratio' in custom_criteria and 'PE_RATIO' in indicators:
            if indicators['PE_RATIO'] > custom_criteria['max_pe_ratio']:
                return False

        if 'min_pb_ratio' in custom_criteria and 'PB_RATIO' in indicators:
            if indicators['PB_RATIO'] < custom_criteria['min_pb_ratio']:
                return False

        if 'max_pb_ratio' in custom_criteria and 'PB_RATIO' in indicators:
            if indicators['PB_RATIO'] > custom_criteria['max_pb_ratio']:
                return False

        if 'min_roe' in custom_criteria and 'ROE' in indicators:
            if indicators['ROE'] < custom_criteria['min_roe']:
                return False

        if 'max_debt_ratio' in custom_criteria and 'DEBT_RATIO' in indicators:
            if indicators['DEBT_RATIO'] > custom_criteria['max_debt_ratio']:
                return False

        if 'min_revenue_growth' in custom_criteria and 'REVENUE_GROWTH' in indicators:
            if indicators['REVENUE_GROWTH'] < custom_criteria['min_revenue_growth']:
                return False

        if 'min_profit_growth' in custom_criteria and 'PROFIT_GROWTH' in indicators:
            if indicators['PROFIT_GROWTH'] < custom_criteria['min_profit_growth']:
                return False

        return True
