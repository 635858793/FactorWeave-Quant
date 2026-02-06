"""
加密货币成长策略

基于市场、网络健康、开发、社区、情绪和增长指标选择加密货币，重点关注高成长性的加密货币。
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
from core.fundamental_data.crypto_fundamental_data import CryptoFundamentalData
from core.plugin_types import AssetType


class CryptoGrowthStrategy(SelectionStrategyBase):
    """加密货币成长策略"""

    def __init__(self):
        super().__init__(AssetType.CRYPTO, StrategyType.GROWTH)
        self._market_weight = 0.2
        self._network_health_weight = 0.25
        self._development_weight = 0.2
        self._community_weight = 0.15
        self._sentiment_weight = 0.1
        self._growth_weight = 0.1

    def calculate_score(self, fundamental_data: CryptoFundamentalData) -> float:
        """计算加密货币评分

        评分基于：
        - 市场评分（20%）：市值、成交量、流通供应量（越高越好）
        - 网络健康评分（25%）：活跃地址、交易数、算力（越高越好）
        - 开发评分（20%）：开发者活动、GitHub提交数（越高越好）
        - 社区评分（15%）：社区评分（越高越好）
        - 情绪评分（10%）：社交媒体情绪（正向越好）
        - 增长评分（10%）：网络增长率（越高越好）

        Args:
            fundamental_data: 加密货币基本面数据

        Returns:
            float: 评分（0-100）
        """
        try:
            market_score = fundamental_data.get_market_score()
            network_health_score = fundamental_data.get_network_health_score()
            development_score = fundamental_data.get_development_score()
            community_score = fundamental_data.get_community_score()
            sentiment_score = fundamental_data.get_sentiment_score()
            growth_score = fundamental_data.get_growth_score()

            total_score = (
                market_score * self._market_weight +
                network_health_score * self._network_health_weight +
                development_score * self._development_weight +
                community_score * self._community_weight +
                sentiment_score * self._sentiment_weight +
                growth_score * self._growth_weight
            )

            logger.debug(
                f"加密货币成长评分: {fundamental_data.symbol} = {total_score:.2f} "
                f"(市场={market_score:.2f}, 网络={network_health_score:.2f}, "
                f"开发={development_score:.2f}, 社区={community_score:.2f}, "
                f"情绪={sentiment_score:.2f}, 增长={growth_score:.2f})"
            )

            return total_score

        except Exception as e:
            logger.error(f"计算加密货币成长评分失败: {fundamental_data.symbol}, 错误: {e}")
            return 0.0

    def select_assets(
        self,
        fundamental_data_list: List[CryptoFundamentalData],
        criteria: SelectionCriteria
    ) -> SelectionResult:
        """选择加密货币

        Args:
            fundamental_data_list: 加密货币基本面数据列表
            criteria: 选股标准

        Returns:
            SelectionResult: 选股结果
        """
        logger.info(f"开始加密货币成长选股: {len(fundamental_data_list)}个加密货币")

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
                    "market_weight": self._market_weight,
                    "network_health_weight": self._network_health_weight,
                    "development_weight": self._development_weight,
                    "community_weight": self._community_weight,
                    "sentiment_weight": self._sentiment_weight,
                    "growth_weight": self._growth_weight
                }
            )

            logger.info(
                f"加密货币成长选股完成: 总计={len(fundamental_data_list)}, "
                f"过滤={len(filtered_scores)}, 选中={len(selected_assets)}"
            )

            return result

        except Exception as e:
            logger.error(f"加密货币成长选股失败: {e}")
            raise

    def validate_criteria(self, criteria: SelectionCriteria) -> bool:
        """验证选股标准是否有效

        Args:
            criteria: 选股标准

        Returns:
            bool: 是否有效
        """
        if criteria.asset_type != AssetType.CRYPTO:
            logger.error(f"资产类型不匹配: 期望{AssetType.CRYPTO.value}, 实际{criteria.asset_type.value}")
            return False

        if criteria.strategy_type != StrategyType.GROWTH:
            logger.error(f"策略类型不匹配: 期望{StrategyType.GROWTH.value}, 实际{criteria.strategy_type.value}")
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
            "加密货币成长策略：基于市场、网络健康、开发、社区、情绪和增长指标选择加密货币。"
            "重点关注高成长性的加密货币。"
            f"市场权重={self._market_weight:.0%}, "
            f"网络健康权重={self._network_health_weight:.0%}, "
            f"开发权重={self._development_weight:.0%}, "
            f"社区权重={self._community_weight:.0%}, "
            f"情绪权重={self._sentiment_weight:.0%}, "
            f"增长权重={self._growth_weight:.0%}"
        )

    def set_weights(
        self,
        market_weight: float = 0.2,
        network_health_weight: float = 0.25,
        development_weight: float = 0.2,
        community_weight: float = 0.15,
        sentiment_weight: float = 0.1,
        growth_weight: float = 0.1
    ):
        """设置评分权重

        Args:
            market_weight: 市场权重
            network_health_weight: 网络健康权重
            development_weight: 开发权重
            community_weight: 社区权重
            sentiment_weight: 情绪权重
            growth_weight: 增长权重
        """
        total_weight = (
            market_weight + network_health_weight + development_weight +
            community_weight + sentiment_weight + growth_weight
        )

        if abs(total_weight - 1.0) > 0.01:
            logger.warning(f"权重总和不为1: {total_weight:.2f}，将自动归一化")

        self._market_weight = market_weight / total_weight
        self._network_health_weight = network_health_weight / total_weight
        self._development_weight = development_weight / total_weight
        self._community_weight = community_weight / total_weight
        self._sentiment_weight = sentiment_weight / total_weight
        self._growth_weight = growth_weight / total_weight

        logger.info(
            f"设置评分权重: 市场={self._market_weight:.0%}, "
            f"网络健康={self._network_health_weight:.0%}, "
            f"开发={self._development_weight:.0%}, "
            f"社区={self._community_weight:.0%}, "
            f"情绪={self._sentiment_weight:.0%}, "
            f"增长={self._growth_weight:.0%}"
        )

    def get_custom_criteria(self) -> Dict[str, Any]:
        """获取自定义选股标准

        Returns:
            Dict[str, Any]: 自定义选股标准
        """
        return {
            "min_market_cap": 10000000.0,
            "min_volume_24h": 1000000.0,
            "min_active_addresses": 10000.0,
            "min_transactions_per_day": 50000.0,
            "min_developer_activity": 10.0,
            "min_community_score": 50.0,
            "min_social_sentiment": 0.0,
            "min_network_growth": 0.0
        }

    def apply_custom_criteria(
        self,
        fundamental_data: CryptoFundamentalData,
        custom_criteria: Dict[str, Any]
    ) -> bool:
        """应用自定义选股标准

        Args:
            fundamental_data: 加密货币基本面数据
            custom_criteria: 自定义选股标准

        Returns:
            bool: 是否符合标准
        """
        indicators = fundamental_data.get_key_indicators()

        if 'min_market_cap' in custom_criteria and 'MARKET_CAP' in indicators:
            if indicators['MARKET_CAP'] < custom_criteria['min_market_cap']:
                return False

        if 'min_volume_24h' in custom_criteria and 'VOLUME_24H' in indicators:
            if indicators['VOLUME_24H'] < custom_criteria['min_volume_24h']:
                return False

        if 'min_active_addresses' in custom_criteria and 'ACTIVE_ADDRESSES' in indicators:
            if indicators['ACTIVE_ADDRESSES'] < custom_criteria['min_active_addresses']:
                return False

        if 'min_transactions_per_day' in custom_criteria and 'TRANSACTIONS_PER_DAY' in indicators:
            if indicators['TRANSACTIONS_PER_DAY'] < custom_criteria['min_transactions_per_day']:
                return False

        if 'min_developer_activity' in custom_criteria and 'DEVELOPER_ACTIVITY' in indicators:
            if indicators['DEVELOPER_ACTIVITY'] < custom_criteria['min_developer_activity']:
                return False

        if 'min_community_score' in custom_criteria and 'COMMUNITY_SCORE' in indicators:
            if indicators['COMMUNITY_SCORE'] < custom_criteria['min_community_score']:
                return False

        if 'min_social_sentiment' in custom_criteria and 'SOCIAL_SENTIMENT' in indicators:
            if indicators['SOCIAL_SENTIMENT'] < custom_criteria['min_social_sentiment']:
                return False

        if 'min_network_growth' in custom_criteria and 'NETWORK_GROWTH' in indicators:
            if indicators['NETWORK_GROWTH'] < custom_criteria['min_network_growth']:
                return False

        return True
