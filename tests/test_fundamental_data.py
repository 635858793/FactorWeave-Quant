"""
基本面数据抽象接口单元测试

测试基本面数据抽象层的所有功能，包括：
1. 基本面数据基类
2. 股票基本面数据类
3. 期货基本面数据类
4. 加密货币基本面数据类
5. 基本面数据工厂类

作者: FactorWeave-Quant团队
版本: 1.0
日期: 2024-09-19
"""

import sys
from datetime import date
from typing import Dict, Any

import pytest

from core.fundamental_data.fundamental_data_base import (
    FundamentalData,
    FundamentalIndicator,
    FundamentalScoreLevel
)
from core.fundamental_data.stock_fundamental_data import StockFundamentalData
from core.fundamental_data.futures_fundamental_data import FuturesFundamentalData
from core.fundamental_data.crypto_fundamental_data import CryptoFundamentalData
from core.fundamental_data.fundamental_data_factory import FundamentalDataFactory
from core.plugin_types import AssetType


class TestFundamentalIndicator:
    """测试基本面指标类"""

    def test_indicator_creation(self):
        """测试指标创建"""
        indicator = FundamentalIndicator(
            name="TEST_INDICATOR",
            value=50.0,
            weight=1.0,
            min_value=0.0,
            max_value=100.0,
            description="测试指标"
        )

        assert indicator.name == "TEST_INDICATOR"
        assert indicator.value == 50.0
        assert indicator.weight == 1.0
        assert indicator.min_value == 0.0
        assert indicator.max_value == 100.0
        assert indicator.description == "测试指标"

    def test_normalized_score_middle(self):
        """测试归一化评分（中间值）"""
        indicator = FundamentalIndicator(
            name="TEST_INDICATOR",
            value=50.0,
            weight=1.0,
            min_value=0.0,
            max_value=100.0,
            description="测试指标"
        )

        score = indicator.get_normalized_score()
        assert score == 50.0

    def test_normalized_score_min(self):
        """测试归一化评分（最小值）"""
        indicator = FundamentalIndicator(
            name="TEST_INDICATOR",
            value=0.0,
            weight=1.0,
            min_value=0.0,
            max_value=100.0,
            description="测试指标"
        )

        score = indicator.get_normalized_score()
        assert score == 0.0

    def test_normalized_score_max(self):
        """测试归一化评分（最大值）"""
        indicator = FundamentalIndicator(
            name="TEST_INDICATOR",
            value=100.0,
            weight=1.0,
            min_value=0.0,
            max_value=100.0,
            description="测试指标"
        )

        score = indicator.get_normalized_score()
        assert score == 100.0

    def test_normalized_score_clamp(self):
        """测试归一化评分（超出范围）"""
        indicator = FundamentalIndicator(
            name="TEST_INDICATOR",
            value=150.0,
            weight=1.0,
            min_value=0.0,
            max_value=100.0,
            description="测试指标"
        )

        score = indicator.get_normalized_score()
        assert score == 100.0

    def test_normalized_score_no_bounds(self):
        """测试归一化评分（无边界）"""
        indicator = FundamentalIndicator(
            name="TEST_INDICATOR",
            value=50.0,
            weight=1.0,
            description="测试指标"
        )

        score = indicator.get_normalized_score()
        assert score == 50.0


class TestStockFundamentalData:
    """测试股票基本面数据类"""

    def test_stock_creation(self):
        """测试股票基本面数据创建"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0,
            'roa': 10.0,
            'gross_margin': 30.0,
            'net_margin': 15.0,
            'revenue_growth': 10.0,
            'profit_growth': 15.0,
            'market_cap': 1000.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        assert stock_data.symbol == "000001"
        assert stock_data.asset_type == AssetType.STOCK_A
        assert len(stock_data._indicators) > 0

    def test_stock_to_dict(self):
        """测试股票基本面数据转换为字典"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        data_dict = stock_data.to_dict()

        assert data_dict['symbol'] == "000001"
        assert data_dict['asset_type'] == AssetType.STOCK_A.value
        assert 'score' in data_dict
        assert 'score_level' in data_dict
        assert 'indicators' in data_dict
        assert 'raw_data' in data_dict

    def test_stock_get_key_indicators(self):
        """测试获取股票关键指标"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        indicators = stock_data.get_key_indicators()

        assert 'PE_RATIO' in indicators
        assert 'PB_RATIO' in indicators
        assert 'ROE' in indicators
        assert 'DEBT_RATIO' in indicators
        assert indicators['PE_RATIO'] == 15.0
        assert indicators['PB_RATIO'] == 2.5
        assert indicators['ROE'] == 20.0
        assert indicators['DEBT_RATIO'] == 40.0

    def test_stock_get_score(self):
        """测试获取股票基本面评分"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        score = stock_data.get_score()

        assert 0.0 <= score <= 100.0

    def test_stock_get_score_level(self):
        """测试获取股票基本面评分等级"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        score_level = stock_data.get_score_level()

        assert isinstance(score_level, FundamentalScoreLevel)

    def test_stock_validate(self):
        """测试验证股票基本面数据"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        assert stock_data.validate() is True

    def test_stock_validate_empty(self):
        """测试验证空股票基本面数据"""
        raw_data = {}

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        assert stock_data.validate() is False

    def test_stock_get_indicator_description(self):
        """测试获取股票指标描述"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        description = stock_data.get_indicator_description("PE_RATIO")

        assert "市盈率" in description

    def test_stock_get_valuation_score(self):
        """测试获取股票估值评分"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        valuation_score = stock_data.get_valuation_score()

        assert 0.0 <= valuation_score <= 100.0

    def test_stock_get_profitability_score(self):
        """测试获取股票盈利能力评分"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0,
            'roa': 10.0,
            'gross_margin': 30.0,
            'net_margin': 15.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        profitability_score = stock_data.get_profitability_score()

        assert 0.0 <= profitability_score <= 100.0

    def test_stock_get_growth_score(self):
        """测试获取股票成长性评分"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0,
            'revenue_growth': 10.0,
            'profit_growth': 15.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        growth_score = stock_data.get_growth_score()

        assert 0.0 <= growth_score <= 100.0

    def test_stock_get_financial_health_score(self):
        """测试获取股票财务健康评分"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        stock_data = StockFundamentalData(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data
        )

        financial_health_score = stock_data.get_financial_health_score()

        assert 0.0 <= financial_health_score <= 100.0


class TestFuturesFundamentalData:
    """测试期货基本面数据类"""

    def test_futures_creation(self):
        """测试期货基本面数据创建"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0,
            'basis': 10.0,
            'supply_demand_ratio': 1.2,
            'production': 1000000.0,
            'consumption': 900000.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )

        assert futures_data.symbol == "CU2401"
        assert futures_data.asset_type == AssetType.FUTURES
        assert len(futures_data._indicators) > 0

    def test_futures_to_dict(self):
        """测试期货基本面数据转换为字典"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )

        data_dict = futures_data.to_dict()

        assert data_dict['symbol'] == "CU2401"
        assert data_dict['asset_type'] == AssetType.FUTURES.value
        assert 'score' in data_dict
        assert 'score_level' in data_dict
        assert 'indicators' in data_dict
        assert 'raw_data' in data_dict

    def test_futures_get_key_indicators(self):
        """测试获取期货关键指标"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )

        indicators = futures_data.get_key_indicators()

        assert 'OPEN_INTEREST' in indicators
        assert 'VOLUME' in indicators
        assert 'INVENTORY' in indicators

    def test_futures_get_score(self):
        """测试获取期货基本面评分"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )

        score = futures_data.get_score()

        assert 0.0 <= score <= 100.0

    def test_futures_validate(self):
        """测试验证期货基本面数据"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )

        assert futures_data.validate() is True

    def test_futures_get_liquidity_score(self):
        """测试获取期货流动性评分"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )

        liquidity_score = futures_data.get_liquidity_score()

        assert 0.0 <= liquidity_score <= 100.0

    def test_futures_get_supply_demand_score(self):
        """测试获取期货供需评分"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0,
            'supply_demand_ratio': 1.2,
            'production': 1000000.0,
            'consumption': 900000.0
        }

        futures_data = FuturesFundamentalData(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data
        )

        supply_demand_score = futures_data.get_supply_demand_score()

        assert 0.0 <= supply_demand_score <= 100.0


class TestCryptoFundamentalData:
    """测试加密货币基本面数据类"""

    def test_crypto_creation(self):
        """测试加密货币基本面数据创建"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'active_addresses': 100000.0,
            'transactions_per_day': 500000.0,
            'hashrate': 1000000000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        assert crypto_data.symbol == "BTC"
        assert crypto_data.asset_type == AssetType.CRYPTO
        assert len(crypto_data._indicators) > 0

    def test_crypto_to_dict(self):
        """测试加密货币基本面数据转换为字典"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        data_dict = crypto_data.to_dict()

        assert data_dict['symbol'] == "BTC"
        assert data_dict['asset_type'] == AssetType.CRYPTO.value
        assert 'score' in data_dict
        assert 'score_level' in data_dict
        assert 'indicators' in data_dict
        assert 'raw_data' in data_dict

    def test_crypto_get_key_indicators(self):
        """测试获取加密货币关键指标"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        indicators = crypto_data.get_key_indicators()

        assert 'MARKET_CAP' in indicators
        assert 'VOLUME_24H' in indicators
        assert 'CIRCULATING_SUPPLY' in indicators

    def test_crypto_get_score(self):
        """测试获取加密货币基本面评分"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        score = crypto_data.get_score()

        assert 0.0 <= score <= 100.0

    def test_crypto_validate(self):
        """测试验证加密货币基本面数据"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'active_addresses': 100000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        assert crypto_data.validate() is True

    def test_crypto_get_market_score(self):
        """测试获取加密货币市场评分"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        market_score = crypto_data.get_market_score()

        assert 0.0 <= market_score <= 100.0

    def test_crypto_get_network_health_score(self):
        """测试获取加密货币网络健康评分"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'active_addresses': 100000.0,
            'transactions_per_day': 500000.0,
            'hashrate': 1000000000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        network_health_score = crypto_data.get_network_health_score()

        assert 0.0 <= network_health_score <= 100.0

    def test_crypto_get_development_score(self):
        """测试获取加密货币开发评分"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'active_addresses': 100000.0,
            'developer_activity': 100.0,
            'github_commits': 1000.0
        }

        crypto_data = CryptoFundamentalData(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data
        )

        development_score = crypto_data.get_development_score()

        assert 0.0 <= development_score <= 100.0


class TestFundamentalDataFactory:
    """测试基本面数据工厂类"""

    def test_create_stock(self):
        """测试创建股票基本面数据"""
        raw_data = {
            'pe_ratio': 15.0,
            'pb_ratio': 2.5,
            'roe': 20.0,
            'debt_ratio': 40.0
        }

        fundamental_data = FundamentalDataFactory.create(
            symbol="000001",
            data_date=date.today(),
            raw_data=raw_data,
            asset_type=AssetType.STOCK_A
        )

        assert isinstance(fundamental_data, StockFundamentalData)
        assert fundamental_data.symbol == "000001"
        assert fundamental_data.asset_type == AssetType.STOCK_A

    def test_create_futures(self):
        """测试创建期货基本面数据"""
        raw_data = {
            'open_interest': 100000.0,
            'volume': 500000.0,
            'inventory': 50000.0
        }

        fundamental_data = FundamentalDataFactory.create(
            symbol="CU2401",
            data_date=date.today(),
            raw_data=raw_data,
            asset_type=AssetType.FUTURES
        )

        assert isinstance(fundamental_data, FuturesFundamentalData)
        assert fundamental_data.symbol == "CU2401"
        assert fundamental_data.asset_type == AssetType.FUTURES

    def test_create_crypto(self):
        """测试创建加密货币基本面数据"""
        raw_data = {
            'market_cap': 1000000000.0,
            'volume_24h': 50000000.0,
            'circulating_supply': 100000000.0,
            'active_addresses': 100000.0
        }

        fundamental_data = FundamentalDataFactory.create(
            symbol="BTC",
            data_date=date.today(),
            raw_data=raw_data,
            asset_type=AssetType.CRYPTO
        )

        assert isinstance(fundamental_data, CryptoFundamentalData)
        assert fundamental_data.symbol == "BTC"
        assert fundamental_data.asset_type == AssetType.CRYPTO

    def test_create_from_dict(self):
        """测试从字典创建基本面数据"""
        data_dict = {
            'symbol': '000001',
            'asset_type': AssetType.STOCK_A.value,
            'data_date': date.today().isoformat(),
            'raw_data': {
                'pe_ratio': 15.0,
                'pb_ratio': 2.5,
                'roe': 20.0,
                'debt_ratio': 40.0
            }
        }

        fundamental_data = FundamentalDataFactory.create_from_dict(data_dict)

        assert isinstance(fundamental_data, StockFundamentalData)
        assert fundamental_data.symbol == "000001"
        assert fundamental_data.asset_type == AssetType.STOCK_A

    def test_create_from_dict_missing_field(self):
        """测试从字典创建基本面数据（缺少字段）"""
        data_dict = {
            'symbol': '000001',
            'asset_type': AssetType.STOCK_A.value,
            'raw_data': {
                'pe_ratio': 15.0,
                'pb_ratio': 2.5,
                'roe': 20.0,
                'debt_ratio': 40.0
            }
        }

        with pytest.raises(ValueError):
            FundamentalDataFactory.create_from_dict(data_dict)

    def test_create_unsupported_asset_type(self):
        """测试创建不支持的资产类型"""
        raw_data = {
            'test_field': 100.0
        }

        with pytest.raises(ValueError):
            FundamentalDataFactory.create(
                symbol="TEST",
                data_date=date.today(),
                raw_data=raw_data,
                asset_type=AssetType.BOND
            )

    def test_get_supported_asset_types(self):
        """测试获取支持的资产类型"""
        supported_types = FundamentalDataFactory.get_supported_asset_types()

        assert AssetType.STOCK_A in supported_types
        assert AssetType.FUTURES in supported_types
        assert AssetType.CRYPTO in supported_types

    def test_is_supported(self):
        """测试检查资产类型是否支持"""
        assert FundamentalDataFactory.is_supported(AssetType.STOCK_A) is True
        assert FundamentalDataFactory.is_supported(AssetType.FUTURES) is True
        assert FundamentalDataFactory.is_supported(AssetType.CRYPTO) is True
        assert FundamentalDataFactory.is_supported(AssetType.BOND) is False

    def test_get_fundamental_data_class(self):
        """测试获取基本面数据类"""
        stock_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.STOCK_A)
        assert stock_class == StockFundamentalData

        futures_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.FUTURES)
        assert futures_class == FuturesFundamentalData

        crypto_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.CRYPTO)
        assert crypto_class == CryptoFundamentalData

        bond_class = FundamentalDataFactory.get_fundamental_data_class(AssetType.BOND)
        assert bond_class is None

    def test_create_batch(self):
        """测试批量创建基本面数据"""
        data_list = [
            {
                'symbol': '000001',
                'asset_type': AssetType.STOCK_A.value,
                'data_date': date.today().isoformat(),
                'raw_data': {
                    'pe_ratio': 15.0,
                    'pb_ratio': 2.5,
                    'roe': 20.0,
                    'debt_ratio': 40.0
                }
            },
            {
                'symbol': '000002',
                'asset_type': AssetType.STOCK_A.value,
                'data_date': date.today().isoformat(),
                'raw_data': {
                    'pe_ratio': 20.0,
                    'pb_ratio': 3.0,
                    'roe': 15.0,
                    'debt_ratio': 50.0
                }
            }
        ]

        fundamental_data_list = FundamentalDataFactory.create_batch(data_list)

        assert len(fundamental_data_list) == 2
        assert all(isinstance(fd, StockFundamentalData) for fd in fundamental_data_list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
