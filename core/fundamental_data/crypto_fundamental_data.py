"""
加密货币基本面数据类

实现加密货币类型的基本面数据处理，包括网络指标、开发者活动、市场指标等
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from datetime import date
from typing import Dict, Any, Optional, List

from loguru import logger

from core.fundamental_data.fundamental_data_base import (
    FundamentalData,
    FundamentalIndicator,
    FundamentalScoreLevel
)
from core.plugin_types import AssetType


class CryptoFundamentalData(FundamentalData):
    """加密货币基本面数据类"""

    def __init__(self, symbol: str, data_date: date, raw_data: Dict[str, Any]):
        super().__init__(symbol, data_date, raw_data, AssetType.CRYPTO)
        self._initialize_indicators()

    def _initialize_indicators(self):
        """初始化加密货币基本面指标"""
        logger.debug(f"初始化加密货币基本面指标: {self.symbol}")

        try:
            market_cap = float(self.raw_data.get('market_cap', 0))
            if market_cap > 0:
                self.add_indicator(FundamentalIndicator(
                    name="MARKET_CAP",
                    value=market_cap,
                    weight=0.15,
                    min_value=1000000.0,
                    max_value=1000000000000.0,
                    description="市值：衡量加密货币的市场规模和影响力"
                ))

            volume_24h = float(self.raw_data.get('volume_24h', 0))
            if volume_24h > 0:
                self.add_indicator(FundamentalIndicator(
                    name="VOLUME_24H",
                    value=volume_24h,
                    weight=0.10,
                    min_value=100000.0,
                    max_value=100000000000.0,
                    description="24小时成交量：衡量市场活跃度和流动性"
                ))

            circulating_supply = float(self.raw_data.get('circulating_supply', 0))
            if circulating_supply > 0:
                self.add_indicator(FundamentalIndicator(
                    name="CIRCULATING_SUPPLY",
                    value=circulating_supply,
                    weight=0.10,
                    min_value=1000000.0,
                    max_value=1000000000000.0,
                    description="流通供应量：衡量市场流通的代币数量"
                ))

            total_supply = float(self.raw_data.get('total_supply', 0))
            if total_supply > 0:
                self.add_indicator(FundamentalIndicator(
                    name="TOTAL_SUPPLY",
                    value=total_supply,
                    weight=0.05,
                    min_value=1000000.0,
                    max_value=1000000000000.0,
                    description="总供应量：衡量代币的总发行量"
                ))

            max_supply = float(self.raw_data.get('max_supply', 0))
            if max_supply > 0:
                self.add_indicator(FundamentalIndicator(
                    name="MAX_SUPPLY",
                    value=max_supply,
                    weight=0.05,
                    min_value=1000000.0,
                    max_value=1000000000000.0,
                    description="最大供应量：衡量代币的发行上限"
                ))

            active_addresses = float(self.raw_data.get('active_addresses', 0))
            if active_addresses > 0:
                self.add_indicator(FundamentalIndicator(
                    name="ACTIVE_ADDRESSES",
                    value=active_addresses,
                    weight=0.20,
                    min_value=1000.0,
                    max_value=10000000.0,
                    description="活跃地址数：衡量网络用户活跃度"
                ))

            transactions_per_day = float(self.raw_data.get('transactions_per_day', 0))
            if transactions_per_day > 0:
                self.add_indicator(FundamentalIndicator(
                    name="TRANSACTIONS_PER_DAY",
                    value=transactions_per_day,
                    weight=0.15,
                    min_value=1000.0,
                    max_value=10000000.0,
                    description="每日交易数：衡量网络使用频率"
                ))

            hashrate = float(self.raw_data.get('hashrate', 0))
            if hashrate > 0:
                self.add_indicator(FundamentalIndicator(
                    name="HASHRATE",
                    value=hashrate,
                    weight=0.15,
                    min_value=1000000.0,
                    max_value=1000000000000.0,
                    description="算力：衡量网络安全性和挖矿难度"
                ))

            difficulty = float(self.raw_data.get('difficulty', 0))
            if difficulty > 0:
                self.add_indicator(FundamentalIndicator(
                    name="DIFFICULTY",
                    value=difficulty,
                    weight=0.10,
                    min_value=1000.0,
                    max_value=1000000000000.0,
                    description="难度：衡量挖矿难度"
                ))

            block_height = float(self.raw_data.get('block_height', 0))
            if block_height > 0:
                self.add_indicator(FundamentalIndicator(
                    name="BLOCK_HEIGHT",
                    value=block_height,
                    weight=0.05,
                    min_value=0.0,
                    max_value=10000000.0,
                    description="区块高度：衡量区块链的发展程度"
                ))

            developer_activity = float(self.raw_data.get('developer_activity', 0))
            if developer_activity > 0:
                self.add_indicator(FundamentalIndicator(
                    name="DEVELOPER_ACTIVITY",
                    value=developer_activity,
                    weight=0.15,
                    min_value=0.0,
                    max_value=1000.0,
                    description="开发者活动：衡量项目开发活跃度"
                ))

            github_commits = float(self.raw_data.get('github_commits', 0))
            if github_commits > 0:
                self.add_indicator(FundamentalIndicator(
                    name="GITHUB_COMMITS",
                    value=github_commits,
                    weight=0.10,
                    min_value=0.0,
                    max_value=10000.0,
                    description="GitHub提交数：衡量代码开发活跃度"
                ))

            community_score = float(self.raw_data.get('community_score', 0))
            if community_score > 0:
                self.add_indicator(FundamentalIndicator(
                    name="COMMUNITY_SCORE",
                    value=community_score,
                    weight=0.15,
                    min_value=0.0,
                    max_value=100.0,
                    description="社区评分：衡量社区活跃度和影响力"
                ))

            social_sentiment = float(self.raw_data.get('social_sentiment', 0))
            if social_sentiment != 0:
                self.add_indicator(FundamentalIndicator(
                    name="SOCIAL_SENTIMENT",
                    value=social_sentiment,
                    weight=0.10,
                    min_value=-1.0,
                    max_value=1.0,
                    description="社交媒体情绪：衡量市场情绪倾向"
                ))

            network_growth = float(self.raw_data.get('network_growth', 0))
            if network_growth != 0:
                self.add_indicator(FundamentalIndicator(
                    name="NETWORK_GROWTH",
                    value=network_growth,
                    weight=0.15,
                    min_value=-10.0,
                    max_value=50.0,
                    description="网络增长率：衡量网络扩张速度"
                ))

            whale_activity = float(self.raw_data.get('whale_activity', 0))
            if whale_activity > 0:
                self.add_indicator(FundamentalIndicator(
                    name="WHALE_ACTIVITY",
                    value=whale_activity,
                    weight=0.10,
                    min_value=0.0,
                    max_value=100.0,
                    description="鲸鱼活动：衡量大户交易活跃度"
                ))

            logger.info(f"加密货币基本面指标初始化完成: {self.symbol}, 指标数量: {len(self._indicators)}")

        except Exception as e:
            logger.error(f"初始化加密货币基本面指标失败: {self.symbol}, 错误: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "asset_type": self.asset_type.value,
            "data_date": self.data_date.isoformat(),
            "score": self.get_score(),
            "score_level": self.get_score_level().value,
            "indicators": self.get_key_indicators(),
            "raw_data": self.raw_data
        }

    def get_key_indicators(self) -> Dict[str, float]:
        """获取关键指标"""
        return {
            name: indicator.value
            for name, indicator in self._indicators.items()
        }

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
            normalized_score = indicator.get_normalized_score()
            weighted_score += normalized_score * indicator.weight
            total_weight += indicator.weight

        if total_weight > 0:
            self._score = weighted_score / total_weight
        else:
            self._score = 0.0

        logger.debug(f"加密货币基本面评分: {self.symbol} = {self._score:.2f}")
        return self._score

    def get_score_level(self) -> FundamentalScoreLevel:
        """获取基本面评分等级"""
        if self._score_level is not None:
            return self._score_level

        score = self.get_score()

        if score >= 80:
            self._score_level = FundamentalScoreLevel.EXCELLENT
        elif score >= 60:
            self._score_level = FundamentalScoreLevel.GOOD
        elif score >= 40:
            self._score_level = FundamentalScoreLevel.MODERATE
        elif score >= 20:
            self._score_level = FundamentalScoreLevel.POOR
        else:
            self._score_level = FundamentalScoreLevel.VERY_POOR

        return self._score_level

    def validate(self) -> bool:
        """验证基本面数据是否有效"""
        if not self.raw_data:
            logger.warning(f"加密货币基本面数据为空: {self.symbol}")
            return False

        if not self._indicators:
            logger.warning(f"加密货币基本面指标为空: {self.symbol}")
            return False

        required_indicators = ["MARKET_CAP", "ACTIVE_ADDRESSES"]
        for indicator_name in required_indicators:
            if indicator_name not in self._indicators:
                logger.warning(f"缺少关键指标: {indicator_name}, 加密货币: {self.symbol}")
                return False

        return True

    def get_indicator_description(self, indicator_name: str) -> str:
        """获取指标描述"""
        indicator = self.get_indicator(indicator_name)
        if indicator:
            return indicator.description

        indicator_descriptions = {
            "MARKET_CAP": "市值：衡量加密货币的市场规模和影响力",
            "VOLUME_24H": "24小时成交量：衡量市场活跃度和流动性",
            "CIRCULATING_SUPPLY": "流通供应量：衡量市场流通的代币数量",
            "TOTAL_SUPPLY": "总供应量：衡量代币的总发行量",
            "MAX_SUPPLY": "最大供应量：衡量代币的发行上限",
            "ACTIVE_ADDRESSES": "活跃地址数：衡量网络用户活跃度",
            "TRANSACTIONS_PER_DAY": "每日交易数：衡量网络使用频率",
            "HASHRATE": "算力：衡量网络安全性和挖矿难度",
            "DIFFICULTY": "难度：衡量挖矿难度",
            "BLOCK_HEIGHT": "区块高度：衡量区块链的发展程度",
            "DEVELOPER_ACTIVITY": "开发者活动：衡量项目开发活跃度",
            "GITHUB_COMMITS": "GitHub提交数：衡量代码开发活跃度",
            "COMMUNITY_SCORE": "社区评分：衡量社区活跃度和影响力",
            "SOCIAL_SENTIMENT": "社交媒体情绪：衡量市场情绪倾向",
            "NETWORK_GROWTH": "网络增长率：衡量网络扩张速度",
            "WHALE_ACTIVITY": "鲸鱼活动：衡量大户交易活跃度"
        }

        return indicator_descriptions.get(indicator_name, "未知指标")

    def get_market_score(self) -> float:
        """获取市场评分（基于市值、成交量、供应量）"""
        market_indicators = ["MARKET_CAP", "VOLUME_24H", "CIRCULATING_SUPPLY"]
        total_weight = 0.0
        weighted_score = 0.0

        for indicator_name in market_indicators:
            indicator = self.get_indicator(indicator_name)
            if indicator:
                normalized_score = indicator.get_normalized_score()
                weighted_score += normalized_score * indicator.weight
                total_weight += indicator.weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def get_network_health_score(self) -> float:
        """获取网络健康评分（基于活跃地址、交易数、算力）"""
        network_health_indicators = ["ACTIVE_ADDRESSES", "TRANSACTIONS_PER_DAY", "HASHRATE"]
        total_weight = 0.0
        weighted_score = 0.0

        for indicator_name in network_health_indicators:
            indicator = self.get_indicator(indicator_name)
            if indicator:
                normalized_score = indicator.get_normalized_score()
                weighted_score += normalized_score * indicator.weight
                total_weight += indicator.weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def get_development_score(self) -> float:
        """获取开发评分（基于开发者活动、GitHub提交数）"""
        development_indicators = ["DEVELOPER_ACTIVITY", "GITHUB_COMMITS"]
        total_weight = 0.0
        weighted_score = 0.0

        for indicator_name in development_indicators:
            indicator = self.get_indicator(indicator_name)
            if indicator:
                normalized_score = indicator.get_normalized_score()
                weighted_score += normalized_score * indicator.weight
                total_weight += indicator.weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def get_community_score(self) -> float:
        """获取社区评分"""
        indicator = self.get_indicator("COMMUNITY_SCORE")
        if indicator:
            return indicator.get_normalized_score()
        return 0.0

    def get_sentiment_score(self) -> float:
        """获取情绪评分"""
        indicator = self.get_indicator("SOCIAL_SENTIMENT")
        if indicator:
            return indicator.get_normalized_score()
        return 0.0

    def get_growth_score(self) -> float:
        """获取增长评分"""
        indicator = self.get_indicator("NETWORK_GROWTH")
        if indicator:
            return indicator.get_normalized_score()
        return 0.0
