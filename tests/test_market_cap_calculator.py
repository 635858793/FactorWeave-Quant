"""
市值计算器单元测试

测试不同资产类型的市值计算逻辑。
"""

import pytest
from core.services.market_cap_calculator import (
    MarketCapResult,
    MarketCapCalculator,
    StockMarketCapCalculator,
    CryptoMarketCapCalculator,
    FundMarketCapCalculator,
    FuturesMarketCapCalculator,
    ForexMarketCapCalculator,
    IndexMarketCapCalculator,
    DefaultMarketCapCalculator,
    MarketCapCalculatorFactory
)
from core.plugin_types import AssetType


class TestMarketCapResult:
    """测试市值计算结果类"""
    
    def test_market_cap_result_with_value(self):
        """测试有市值的结果"""
        result = MarketCapResult(market_cap=1000000, unit="CNY")
        assert result.market_cap == 1000000
        assert result.unit == "CNY"
        assert result.alternative_metric is None
        
        result_dict = result.to_dict()
        assert result_dict['market_cap'] == 1000000
        assert result_dict['metric_type'] == 'market_cap'
        assert result_dict['unit'] == "CNY"
    
    def test_market_cap_result_with_alternative(self):
        """测试有替代指标的结果"""
        result = MarketCapResult(
            alternative_metric='open_interest',
            alternative_value=50000,
            unit="手"
        )
        assert result.market_cap is None
        assert result.alternative_metric == 'open_interest'
        assert result.alternative_value == 50000
        
        result_dict = result.to_dict()
        assert 'market_cap' not in result_dict
        assert result_dict['metric_type'] == 'open_interest'
        assert result_dict['open_interest'] == 50000
    
    def test_market_cap_result_repr(self):
        """测试结果字符串表示"""
        result1 = MarketCapResult(market_cap=1000000, unit="CNY")
        assert "1000000.00" in repr(result1)
        
        result2 = MarketCapResult(
            alternative_metric='open_interest',
            alternative_value=50000
        )
        assert "open_interest" in repr(result2)


class TestStockMarketCapCalculator:
    """测试股票市值计算器"""
    
    def test_calculate_with_total_shares(self):
        """测试使用总股本计算市值"""
        calculator = StockMarketCapCalculator()
        price = 10.5
        additional_data = {'total_shares': 1000000000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap == 10500000000.0
        assert result.unit == "CNY"
    
    def test_calculate_with_circulating_shares(self):
        """测试使用流通股本计算市值"""
        calculator = StockMarketCapCalculator()
        price = 20.0
        additional_data = {'circulating_shares': 500000000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap == 10000000000.0
        assert result.unit == "CNY"
    
    def test_calculate_with_both_shares(self):
        """测试优先使用总股本"""
        calculator = StockMarketCapCalculator()
        price = 15.0
        additional_data = {
            'total_shares': 1000000000,
            'circulating_shares': 500000000
        }
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap == 15000000000.0
    
    def test_calculate_without_shares(self):
        """测试缺少股本数据"""
        calculator = StockMarketCapCalculator()
        price = 10.0
        additional_data = {}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap is None
    
    def test_calculate_with_zero_price(self):
        """测试价格为0的情况"""
        calculator = StockMarketCapCalculator()
        price = 0
        additional_data = {'total_shares': 1000000000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap is None
    
    def test_get_required_fields(self):
        """测试获取所需字段"""
        calculator = StockMarketCapCalculator()
        fields = calculator.get_required_fields()
        
        assert 'total_shares' in fields
        assert 'circulating_shares' in fields
    
    def test_supports_asset_type(self):
        """测试支持的资产类型"""
        calculator = StockMarketCapCalculator()
        
        assert calculator.supports_asset_type(AssetType.STOCK_A) is True
        assert calculator.supports_asset_type(AssetType.STOCK_B) is True
        assert calculator.supports_asset_type(AssetType.STOCK_H) is True
        assert calculator.supports_asset_type(AssetType.STOCK_US) is True
        assert calculator.supports_asset_type(AssetType.STOCK_HK) is True
        assert calculator.supports_asset_type(AssetType.CRYPTO) is False


class TestCryptoMarketCapCalculator:
    """测试加密货币市值计算器"""
    
    def test_calculate_with_total_supply(self):
        """测试使用总供应量计算市值"""
        calculator = CryptoMarketCapCalculator()
        price = 50000.0
        additional_data = {'total_supply': 21000000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap == 1050000000000.0
        assert result.unit == "USD"
    
    def test_calculate_with_circulating_supply(self):
        """测试使用流通供应量计算市值"""
        calculator = CryptoMarketCapCalculator()
        price = 3000.0
        additional_data = {'circulating_supply': 100000000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap == 300000000000.0
        assert result.unit == "USD"
    
    def test_calculate_without_supply(self):
        """测试缺少供应量数据"""
        calculator = CryptoMarketCapCalculator()
        price = 1000.0
        additional_data = {}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap is None
    
    def test_supports_asset_type(self):
        """测试支持的资产类型"""
        calculator = CryptoMarketCapCalculator()
        
        assert calculator.supports_asset_type(AssetType.CRYPTO) is True
        assert calculator.supports_asset_type(AssetType.STOCK_A) is False


class TestFundMarketCapCalculator:
    """测试基金市值计算器"""
    
    def test_calculate_with_units(self):
        """测试使用份额计算市值"""
        calculator = FundMarketCapCalculator()
        nav = 2.5
        additional_data = {'total_units': 1000000000}
        
        result = calculator.calculate(nav, additional_data)
        
        assert result.market_cap == 2500000000.0
        assert result.unit == "CNY"
    
    def test_calculate_without_units(self):
        """测试缺少份额数据"""
        calculator = FundMarketCapCalculator()
        nav = 1.5
        additional_data = {}
        
        result = calculator.calculate(nav, additional_data)
        
        assert result.market_cap is None
    
    def test_supports_asset_type(self):
        """测试支持的资产类型"""
        calculator = FundMarketCapCalculator()
        
        assert calculator.supports_asset_type(AssetType.FUND) is True
        assert calculator.supports_asset_type(AssetType.STOCK_A) is False


class TestFuturesMarketCapCalculator:
    """测试期货市值计算器"""
    
    def test_calculate_with_open_interest(self):
        """测试返回持仓量"""
        calculator = FuturesMarketCapCalculator()
        price = 4000.0
        additional_data = {'open_interest': 100000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap is None
        assert result.alternative_metric == 'open_interest'
        assert result.alternative_value == 100000
        assert result.unit == "手"
    
    def test_calculate_without_open_interest(self):
        """测试缺少持仓量数据"""
        calculator = FuturesMarketCapCalculator()
        price = 4000.0
        additional_data = {}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.alternative_value == 0
    
    def test_supports_asset_type(self):
        """测试支持的资产类型"""
        calculator = FuturesMarketCapCalculator()
        
        assert calculator.supports_asset_type(AssetType.FUTURES) is True
        assert calculator.supports_asset_type(AssetType.OPTION) is True
        assert calculator.supports_asset_type(AssetType.WARRANT) is True
        assert calculator.supports_asset_type(AssetType.STOCK_A) is False


class TestForexMarketCapCalculator:
    """测试外汇市值计算器"""
    
    def test_calculate_with_volume(self):
        """测试返回交易量"""
        calculator = ForexMarketCapCalculator()
        price = 7.2
        additional_data = {'volume': 50000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap is None
        assert result.alternative_metric == 'volume'
        assert result.alternative_value == 50000
        assert result.unit == "手"
    
    def test_calculate_without_volume(self):
        """测试缺少交易量数据"""
        calculator = ForexMarketCapCalculator()
        price = 7.2
        additional_data = {}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.alternative_value == 0
    
    def test_supports_asset_type(self):
        """测试支持的资产类型"""
        calculator = ForexMarketCapCalculator()
        
        assert calculator.supports_asset_type(AssetType.FOREX) is True
        assert calculator.supports_asset_type(AssetType.STOCK_A) is False


class TestIndexMarketCapCalculator:
    """测试指数市值计算器"""
    
    def test_calculate_with_market_cap(self):
        """测试返回成分股总市值"""
        calculator = IndexMarketCapCalculator()
        price = 3000.0
        additional_data = {'total_market_cap': 50000000000000}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap == 50000000000000
        assert result.unit == "CNY"
    
    def test_calculate_without_market_cap(self):
        """测试缺少成分股市值数据"""
        calculator = IndexMarketCapCalculator()
        price = 3000.0
        additional_data = {}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap is None
    
    def test_supports_asset_type(self):
        """测试支持的资产类型"""
        calculator = IndexMarketCapCalculator()
        
        assert calculator.supports_asset_type(AssetType.INDEX) is True
        assert calculator.supports_asset_type(AssetType.STOCK_A) is False


class TestDefaultMarketCapCalculator:
    """测试默认市值计算器"""
    
    def test_calculate(self):
        """测试默认计算器返回空结果"""
        calculator = DefaultMarketCapCalculator()
        price = 100.0
        additional_data = {}
        
        result = calculator.calculate(price, additional_data)
        
        assert result.market_cap is None
        assert result.alternative_metric is None
    
    def test_supports_asset_type(self):
        """测试支持所有资产类型"""
        calculator = DefaultMarketCapCalculator()
        
        assert calculator.supports_asset_type(AssetType.STOCK_A) is True
        assert calculator.supports_asset_type(AssetType.CRYPTO) is True
        assert calculator.supports_asset_type(AssetType.FUTURES) is True


class TestMarketCapCalculatorFactory:
    """测试市值计算器工厂"""
    
    def test_get_stock_calculator(self):
        """测试获取股票计算器"""
        factory = MarketCapCalculatorFactory()
        
        calculator = factory.get_calculator(AssetType.STOCK_A)
        assert isinstance(calculator, StockMarketCapCalculator)
        
        calculator = factory.get_calculator(AssetType.STOCK_HK)
        assert isinstance(calculator, StockMarketCapCalculator)
    
    def test_get_crypto_calculator(self):
        """测试获取加密货币计算器"""
        factory = MarketCapCalculatorFactory()
        
        calculator = factory.get_calculator(AssetType.CRYPTO)
        assert isinstance(calculator, CryptoMarketCapCalculator)
    
    def test_get_fund_calculator(self):
        """测试获取基金计算器"""
        factory = MarketCapCalculatorFactory()
        
        calculator = factory.get_calculator(AssetType.FUND)
        assert isinstance(calculator, FundMarketCapCalculator)
    
    def test_get_futures_calculator(self):
        """测试获取期货计算器"""
        factory = MarketCapCalculatorFactory()
        
        calculator = factory.get_calculator(AssetType.FUTURES)
        assert isinstance(calculator, FuturesMarketCapCalculator)
        
        calculator = factory.get_calculator(AssetType.OPTION)
        assert isinstance(calculator, FuturesMarketCapCalculator)
    
    def test_get_forex_calculator(self):
        """测试获取外汇计算器"""
        factory = MarketCapCalculatorFactory()
        
        calculator = factory.get_calculator(AssetType.FOREX)
        assert isinstance(calculator, ForexMarketCapCalculator)
    
    def test_get_index_calculator(self):
        """测试获取指数计算器"""
        factory = MarketCapCalculatorFactory()
        
        calculator = factory.get_calculator(AssetType.INDEX)
        assert isinstance(calculator, IndexMarketCapCalculator)
    
    def test_get_default_calculator(self):
        """测试获取默认计算器"""
        factory = MarketCapCalculatorFactory()
        
        calculator = factory.get_calculator(AssetType.BOND)
        assert isinstance(calculator, DefaultMarketCapCalculator)
    
    def test_register_custom_calculator(self):
        """测试注册自定义计算器"""
        factory = MarketCapCalculatorFactory()
        
        custom_calculator = DefaultMarketCapCalculator()
        factory.register_calculator('custom', custom_calculator)
        
        assert factory._calculators['custom'] is custom_calculator


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
