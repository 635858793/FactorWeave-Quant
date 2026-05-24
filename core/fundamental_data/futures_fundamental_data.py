"""
期货基本面数据类

实现期货类型的基本面数据处理，包括供需关系、库存数据、持仓量、基差等
作者：FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

from datetime import date
from typing import Dict, Any, Optional, List

from loguru import logger

from core.fundamental_data.fundamental_data_base import (
    FundamentalDataBase,
    FundamentalIndicator,
    FundamentalScoreLevel
)
from core.plugin_types import AssetType


class FuturesFundamentalData(FundamentalDataBase):
    """期货基本面数据类"""

    def __init__(self, symbol: str, data_date: date, raw_data: Dict[str, Any]):
        super().__init__(symbol, data_date, raw_data, AssetType.FUTURES)
        self._initialize_indicators()

    def _initialize_indicators(self):
        """初始化期货基本面指标"""
        logger.debug(f"初始化期货基本面指标: {self.symbol}")

        try:
            open_interest = float(self.raw_data.get('open_interest', 0))
            if open_interest > 0:
                self.add_indicator(FundamentalIndicator(
                    name="OPEN_INTEREST",
                    value=open_interest,
                    weight=0.20,
                    min_value=1000.0,
                    max_value=1000000.0,
                    description="持仓量：衡量市场参与度和资金关注度"
                ))

            volume = float(self.raw_data.get('volume', 0))
            if volume > 0:
                self.add_indicator(FundamentalIndicator(
                    name="VOLUME",
                    value=volume,
                    weight=0.15,
                    min_value=1000.0,
                    max_value=1000000.0,
                    description="成交量：衡量市场活跃度"
                ))

            inventory = float(self.raw_data.get('inventory', 0))
            if inventory >= 0:
                self.add_indicator(FundamentalIndicator(
                    name="INVENTORY",
                    value=inventory,
                    weight=0.25,
                    min_value=0.0,
                    max_value=1000000.0,
                    description="库存量：衡量供需关系，库存越高供应越充足"
                ))

            basis = float(self.raw_data.get('basis', 0))
            if basis != 0:
                self.add_indicator(FundamentalIndicator(
                    name="BASIS",
                    value=basis,
                    weight=0.20,
                    min_value=-100.0,
                    max_value=100.0,
                    description="基差：期货价格与现货价格的差值，反映市场预期"
                ))

            supply_demand_ratio = float(self.raw_data.get('supply_demand_ratio', 0))
            if supply_demand_ratio > 0:
                self.add_indicator(FundamentalIndicator(
                    name="SUPPLY_DEMAND_RATIO",
                    value=supply_demand_ratio,
                    weight=0.20,
                    min_value=0.5,
                    max_value=2.0,
                    description="供需比：衡量供需平衡状况，1为平衡，大于1供过于求，小于1供不应求"
                ))

            production = float(self.raw_data.get('production', 0))
            if production > 0:
                self.add_indicator(FundamentalIndicator(
                    name="PRODUCTION",
                    value=production,
                    weight=0.15,
                    min_value=1000.0,
                    max_value=10000000.0,
                    description="产量：衡量供应能力"
                ))

            consumption = float(self.raw_data.get('consumption', 0))
            if consumption > 0:
                self.add_indicator(FundamentalIndicator(
                    name="CONSUMPTION",
                    value=consumption,
                    weight=0.15,
                    min_value=1000.0,
                    max_value=10000000.0,
                    description="消费量：衡量需求水平"
                ))

            import_export = float(self.raw_data.get('import_export', 0))
            if import_export != 0:
                self.add_indicator(FundamentalIndicator(
                    name="IMPORT_EXPORT",
                    value=import_export,
                    weight=0.10,
                    min_value=-1000000.0,
                    max_value=1000000.0,
                    description="进出口量：衡量对外贸易对供需的影响"
                ))

            seasonal_factor = float(self.raw_data.get('seasonal_factor', 0))
            if seasonal_factor != 0:
                self.add_indicator(FundamentalIndicator(
                    name="SEASONAL_FACTOR",
                    value=seasonal_factor,
                    weight=0.10,
                    min_value=-1.0,
                    max_value=1.0,
                    description="季节性因子：衡量季节性对价格的影响"
                ))

            macro_indicator = float(self.raw_data.get('macro_indicator', 0))
            if macro_indicator != 0:
                self.add_indicator(FundamentalIndicator(
                    name="MACRO_INDICATOR",
                    value=macro_indicator,
                    weight=0.10,
                    min_value=-10.0,
                    max_value=10.0,
                    description="宏观指标：衡量宏观经济对期货价格的影响"
                ))

            logger.info(f"期货基本面指标初始化完成: {self.symbol}, 指标数量: {len(self._indicators)}")

        except Exception as e:
            logger.error(f"初始化期货基本面指标失败: {self.symbol}, 错误: {e}")
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

        logger.debug(f"期货基本面评分: {self.symbol} = {self._score:.2f}")
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
            logger.warning(f"期货基本面数据为空: {self.symbol}")
            return False

        if not self._indicators:
            logger.warning(f"期货基本面指标为空: {self.symbol}")
            return False

        required_indicators = ["OPEN_INTEREST", "INVENTORY"]
        for indicator_name in required_indicators:
            if indicator_name not in self._indicators:
                logger.warning(f"缺少关键指标: {indicator_name}, 期货: {self.symbol}")
                return False

        return True

    def get_indicator_description(self, indicator_name: str) -> str:
        """获取指标描述"""
        indicator = self.get_indicator(indicator_name)
        if indicator:
            return indicator.description

        indicator_descriptions = {
            "OPEN_INTEREST": "持仓量：衡量市场参与度和资金关注度",
            "VOLUME": "成交量：衡量市场活跃度",
            "INVENTORY": "库存量：衡量供需关系，库存越高供应越充足",
            "BASIS": "基差：期货价格与现货价格的差值，反映市场预期",
            "SUPPLY_DEMAND_RATIO": "供需比：衡量供需平衡状况，1为平衡，大于1供过于求，小于1供不应求",
            "PRODUCTION": "产量：衡量供应能力",
            "CONSUMPTION": "消费量：衡量需求水平",
            "IMPORT_EXPORT": "进出口量：衡量对外贸易对供需的影响",
            "SEASONAL_FACTOR": "季节性因子：衡量季节性对价格的影响",
            "MACRO_INDICATOR": "宏观指标：衡量宏观经济对期货价格的影响"
        }

        return indicator_descriptions.get(indicator_name, "未知指标")

    def get_liquidity_score(self) -> float:
        """获取流动性评分（基于持仓量和成交量）"""
        liquidity_indicators = ["OPEN_INTEREST", "VOLUME"]
        total_weight = 0.0
        weighted_score = 0.0

        for indicator_name in liquidity_indicators:
            indicator = self.get_indicator(indicator_name)
            if indicator:
                normalized_score = indicator.get_normalized_score()
                weighted_score += normalized_score * indicator.weight
                total_weight += indicator.weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def get_supply_demand_score(self) -> float:
        """获取供需评分（基于库存、供需比、产量、消费量）"""
        supply_demand_indicators = ["INVENTORY", "SUPPLY_DEMAND_RATIO", "PRODUCTION", "CONSUMPTION"]
        total_weight = 0.0
        weighted_score = 0.0

        for indicator_name in supply_demand_indicators:
            indicator = self.get_indicator(indicator_name)
            if indicator:
                normalized_score = indicator.get_normalized_score()
                weighted_score += normalized_score * indicator.weight
                total_weight += indicator.weight

        return weighted_score / total_weight if total_weight > 0 else 0.0

    def get_market_sentiment_score(self) -> float:
        """获取市场情绪评分（基于基差）"""
        indicator = self.get_indicator("BASIS")
        if indicator:
            return indicator.get_normalized_score()
        return 0.0

    def get_seasonal_score(self) -> float:
        """获取季节性评分"""
        indicator = self.get_indicator("SEASONAL_FACTOR")
        if indicator:
            return indicator.get_normalized_score()
        return 0.0

    def get_macro_score(self) -> float:
        """获取宏观评分"""
        indicator = self.get_indicator("MACRO_INDICATOR")
        if indicator:
            return indicator.get_normalized_score()
        return 0.0
