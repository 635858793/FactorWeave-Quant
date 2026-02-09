"""
股票基本面数据类

实现股票的基本面数据分析，包括估值、盈利能力、成长性、财务健康等指标
"""

from typing import Dict, Any, Optional, List
from datetime import date
import numpy as np
from loguru import logger

from .fundamental_data_base import (
    FundamentalDataBase,
    FundamentalScoreLevel,
    FundamentalIndicator,
    FundamentalScoreCategory
)


class StockFundamentalData(FundamentalDataBase):
    """
    股票基本面数据类

    功能：
    1. 计算估值指标（PE、PB等）
    2. 计算盈利能力指标（ROE、ROA等）
    3. 计算成长性指标（营收增长率、利润增长率等）
    4. 计算财务健康指标（资产负债率等）
    5. 综合评分和评级
    """

    def __init__(self, stock_code: str, raw_data: Dict[str, Any]):
        """
        初始化股票基本面数据

        Args:
            stock_code: 股票代码
            raw_data: 原始基本面数据
        """
        super().__init__(asset_type="stock", asset_code=stock_code, raw_data=raw_data)

        self.stock_code = stock_code
        self.company_name = raw_data.get('company_name', '')

        # 计算各项指标
        self._calculate_indicators()

    def _calculate_indicators(self):
        """计算所有基本面指标"""
        try:
            # 估值指标
            self._calculate_valuation_indicators()

            # 盈利能力指标
            self._calculate_profitability_indicators()

            # 成长性指标
            self._calculate_growth_indicators()

            # 财务健康指标
            self._calculate_financial_health_indicators()

            # 市值指标
            self._calculate_market_cap_indicators()

        except Exception as e:
            logger.error(f"计算基本面指标失败: {self.stock_code}, 错误: {e}")

    def _calculate_valuation_indicators(self):
        """计算估值指标"""
        try:
            # 市盈率 (PE)
            pe_ratio = float(self.raw_data.get('pe_ratio', 0))
            if pe_ratio > 0:
                self.add_indicator(FundamentalIndicator(
                    name="PE_RATIO",
                    value=pe_ratio,
                    weight=0.25,
                    min_value=5.0,
                    max_value=50.0,
                    description="市盈率：衡量股票估值水平，数值越低估值越合理",
                    is_reverse=True,
                    normalization_type="logarithmic"
                ))

            # 市净率 (PB)
            pb_ratio = float(self.raw_data.get('pb_ratio', 0))
            if pb_ratio > 0:
                self.add_indicator(FundamentalIndicator(
                    name="PB_RATIO",
                    value=pb_ratio,
                    weight=0.20,
                    min_value=0.5,
                    max_value=10.0,
                    description="市净率：衡量股票相对于净资产的估值水平",
                    is_reverse=True,
                    normalization_type="logarithmic"
                ))

            # 市销率 (PS)
            ps_ratio = float(self.raw_data.get('ps_ratio', 0))
            if ps_ratio > 0:
                self.add_indicator(FundamentalIndicator(
                    name="PS_RATIO",
                    value=ps_ratio,
                    weight=0.15,
                    min_value=0.5,
                    max_value=20.0,
                    description="市销率：衡量股票相对于销售额的估值水平",
                    is_reverse=True,
                    normalization_type="logarithmic"
                ))

        except Exception as e:
            logger.error(f"计算估值指标失败: {self.stock_code}, 错误: {e}")

    def _calculate_profitability_indicators(self):
        """计算盈利能力指标"""
        try:
            # 净资产收益率 (ROE)
            roe = float(self.raw_data.get('roe', 0))
            if roe > 0:
                self.add_indicator(FundamentalIndicator(
                    name="ROE",
                    value=roe,
                    weight=0.30,
                    min_value=0.0,
                    max_value=0.50,
                    description="净资产收益率：衡量公司盈利能力，数值越高盈利能力越强",
                    normalization_type="linear"
                ))

            # 总资产收益率 (ROA)
            roa = float(self.raw_data.get('roa', 0))
            if roa > 0:
                self.add_indicator(FundamentalIndicator(
                    name="ROA",
                    value=roa,
                    weight=0.20,
                    min_value=0.0,
                    max_value=15.0,
                    description="总资产收益率：衡量公司资产利用效率",
                    normalization_type="linear"
                ))

            # 毛利率
            gross_margin = float(self.raw_data.get('gross_margin', 0))
            if gross_margin > 0:
                self.add_indicator(FundamentalIndicator(
                    name="GROSS_MARGIN",
                    value=gross_margin,
                    weight=0.15,
                    min_value=0.0,
                    max_value=100.0,
                    description="毛利率：衡量产品盈利能力",
                    normalization_type="linear"
                ))

            # 净利率
            net_margin = float(self.raw_data.get('net_margin', 0))
            if net_margin > 0:
                self.add_indicator(FundamentalIndicator(
                    name="NET_MARGIN",
                    value=net_margin,
                    weight=0.10,
                    min_value=0.0,
                    max_value=30.0,
                    description="净利率：衡量公司整体盈利能力"
                ))

            revenue_growth = float(self.raw_data.get('revenue_growth', 0))
            if revenue_growth != 0:
                self.add_indicator(FundamentalIndicator(
                    name="REVENUE_GROWTH",
                    value=revenue_growth,
                    weight=0.15,
                    min_value=-20.0,
                    max_value=50.0,
                    description="营收增长率：衡量公司成长性"
                ))

            profit_growth = float(self.raw_data.get('profit_growth', 0))
            if profit_growth != 0:
                self.add_indicator(FundamentalIndicator(
                    name="PROFIT_GROWTH",
                    value=profit_growth,
                    weight=0.10,
                    min_value=-30.0,
                    max_value=100.0,
                    description="利润增长率：衡量公司盈利增长能力"
                ))

        except Exception as e:
            logger.error(f"计算盈利能力指标失败: {self.stock_code}, 错误: {e}")

    def _calculate_growth_indicators(self):
        """计算成长性指标"""
        try:
            # 营收增长率
            revenue_growth = float(self.raw_data.get('revenue_growth', 0))
            if revenue_growth != 0:
                self.add_indicator(FundamentalIndicator(
                    name="REVENUE_GROWTH",
                    value=revenue_growth,
                    weight=0.50,
                    min_value=-20.0,
                    max_value=50.0,
                    description="营收增长率：衡量公司成长性",
                    normalization_type="linear"
                ))

            # 利润增长率
            profit_growth = float(self.raw_data.get('profit_growth', 0))
            if profit_growth != 0:
                self.add_indicator(FundamentalIndicator(
                    name="PROFIT_GROWTH",
                    value=profit_growth,
                    weight=0.50,
                    min_value=-30.0,
                    max_value=100.0,
                    description="利润增长率：衡量公司盈利增长能力",
                    normalization_type="linear"
                ))

        except Exception as e:
            logger.error(f"计算成长性指标失败: {self.stock_code}, 错误: {e}")

    def _calculate_financial_health_indicators(self):
        """计算财务健康指标"""
        try:
            # 资产负债率
            debt_ratio = float(self.raw_data.get('debt_ratio', 0))
            if debt_ratio >= 0:
                self.add_indicator(FundamentalIndicator(
                    name="DEBT_RATIO",
                    value=debt_ratio,
                    weight=0.40,
                    min_value=0.0,
                    max_value=100.0,
                    description="资产负债率：衡量公司财务杠杆水平，数值越低财务越稳健",
                    is_reverse=True,
                    normalization_type="linear"
                ))

            # 流动比率
            current_ratio = float(self.raw_data.get('current_ratio', 0))
            if current_ratio > 0:
                self.add_indicator(FundamentalIndicator(
                    name="CURRENT_RATIO",
                    value=current_ratio,
                    weight=0.30,
                    min_value=0.5,
                    max_value=5.0,
                    description="流动比率：衡量公司短期偿债能力",
                    normalization_type="linear"
                ))

            # 速动比率
            quick_ratio = float(self.raw_data.get('quick_ratio', 0))
            if quick_ratio > 0:
                self.add_indicator(FundamentalIndicator(
                    name="QUICK_RATIO",
                    value=quick_ratio,
                    weight=0.30,
                    min_value=0.3,
                    max_value=3.0,
                    description="速动比率：衡量公司快速偿债能力",
                    normalization_type="linear"
                ))

        except Exception as e:
            logger.error(f"计算财务健康指标失败: {self.stock_code}, 错误: {e}")

    def _calculate_market_cap_indicators(self):
        """计算市值指标"""
        try:
            # 市值
            market_cap = float(self.raw_data.get('market_cap', 0))
            if market_cap > 0:
                self.add_indicator(FundamentalIndicator(
                    name="MARKET_CAP",
                    value=market_cap,
                    weight=1.0,
                    min_value=0.0,
                    max_value=1000000000000.0,  # 1万亿
                    description="市值：衡量公司规模",
                    normalization_type="logarithmic"
                ))

        except Exception as e:
            logger.error(f"计算市值指标失败: {self.stock_code}, 错误: {e}")

    def get_score(self) -> float:
        """获取基本面评分（0-100）"""
        if self._score is not None:
            return self._score

        if not self._indicators:
            self._score = 0.0
            return self._score

        # 计算加权平均分
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

    def get_category_score(self, category: FundamentalScoreCategory) -> float:
        """获取特定类别的评分"""
        category_indicators = {
            FundamentalScoreCategory.VALUATION: ['PE_RATIO', 'PB_RATIO', 'PS_RATIO'],
            FundamentalScoreCategory.PROFITABILITY: ['ROE', 'ROA', 'GROSS_MARGIN', 'NET_MARGIN'],
            FundamentalScoreCategory.GROWTH: ['REVENUE_GROWTH', 'PROFIT_GROWTH'],
            FundamentalScoreCategory.FINANCIAL_HEALTH: ['DEBT_RATIO', 'CURRENT_RATIO', 'QUICK_RATIO']
        }

        indicator_names = category_indicators.get(category, [])
        if not indicator_names:
            return 0.0

        total_weight = 0.0
        weighted_score = 0.0

        for name in indicator_names:
            if name in self._indicators:
                indicator = self._indicators[name]
                normalized_value = indicator.get_normalized_value()
                weighted_score += normalized_value * indicator.weight
                total_weight += indicator.weight

        if total_weight > 0:
            return weighted_score / total_weight * 100
        else:
            return 0.0

    def get_valuation_score(self) -> float:
        """获取估值评分（基于PE和PB）"""
        return self.get_category_score(FundamentalScoreCategory.VALUATION)

    def get_profitability_score(self) -> float:
        """获取盈利能力评分（基于ROE、ROA、毛利率、净利率）"""
        return self.get_category_score(FundamentalScoreCategory.PROFITABILITY)

    def get_growth_score(self) -> float:
        """获取成长性评分（基于营收增长率和利润增长率）"""
        return self.get_category_score(FundamentalScoreCategory.GROWTH)

    def get_financial_health_score(self) -> float:
        """获取财务健康评分（基于资产负债率）"""
        return self.get_category_score(FundamentalScoreCategory.FINANCIAL_HEALTH)

    def get_indicator_description(self, indicator_name: str) -> str:
        """获取指标描述"""
        indicator = self.get_indicator(indicator_name)
        if indicator:
            return indicator.description

        indicator_descriptions = {
            "PE_RATIO": "市盈率：衡量股票估值水平，数值越低估值越合理",
            "PB_RATIO": "市净率：衡量股票相对于净资产的估值水平",
            "ROE": "净资产收益率：衡量公司盈利能力，数值越高盈利能力越强",
            "DEBT_RATIO": "资产负债率：衡量公司财务杠杆水平，数值越低财务越稳健",
            "ROA": "总资产收益率：衡量公司资产利用效率",
            "GROSS_MARGIN": "毛利率：衡量产品盈利能力",
            "NET_MARGIN": "净利率：衡量公司整体盈利能力",
            "REVENUE_GROWTH": "营收增长率：衡量公司成长性",
            "PROFIT_GROWTH": "利润增长率：衡量公司盈利增长能力",
            "MARKET_CAP": "市值：衡量公司规模"
        }

        return indicator_descriptions.get(indicator_name, "")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = super().to_dict()

        data.update({
            'stock_code': self.stock_code,
            'company_name': self.company_name,
            'valuation_score': self.get_valuation_score(),
            'profitability_score': self.get_profitability_score(),
            'growth_score': self.get_growth_score(),
            'financial_health_score': self.get_financial_health_score()
        })

        return data

    def __str__(self) -> str:
        """字符串表示"""
        return f"StockFundamentalData(code={self.stock_code}, name={self.company_name}, score={self.get_score():.2f})"

    def __repr__(self) -> str:
        """对象表示"""
        return self.__str__()
