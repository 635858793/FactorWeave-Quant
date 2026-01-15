"""
市值计算器模块

提供不同资产类型的市值计算策略，支持股票、加密货币、期货、外汇等多种资产类型。
使用策略模式实现灵活的扩展机制。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from enum import Enum

from loguru import logger

from core.plugin_types import AssetType


class MarketCapResult:
    """市值计算结果"""
    
    def __init__(self, market_cap: Optional[float] = None, 
                 alternative_metric: Optional[str] = None,
                 alternative_value: Optional[float] = None,
                 unit: str = "CNY"):
        """
        初始化市值计算结果
        
        Args:
            market_cap: 市值（如果有）
            alternative_metric: 替代指标名称（如果没有市值概念）
            alternative_value: 替代指标值
            unit: 单位（CNY/USD等）
        """
        self.market_cap = market_cap
        self.alternative_metric = alternative_metric
        self.alternative_value = alternative_value
        self.unit = unit
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {'unit': self.unit}
        if self.market_cap is not None:
            result['market_cap'] = self.market_cap
            result['metric_type'] = 'market_cap'
        else:
            result['metric_type'] = self.alternative_metric
            result[self.alternative_metric] = self.alternative_value
        return result
    
    def __repr__(self) -> str:
        if self.market_cap is not None:
            return f"MarketCapResult({self.market_cap:.2f} {self.unit})"
        else:
            return f"MarketCapResult({self.alternative_metric}={self.alternative_value:.2f})"


class MarketCapCalculator(ABC):
    """市值计算器基类"""
    
    @abstractmethod
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """
        计算市值
        
        Args:
            price: 当前价格
            additional_data: 额外数据（如股本、供应量等）
            
        Returns:
            MarketCapResult: 计算结果
        """
        pass
    
    @abstractmethod
    def get_required_fields(self) -> list:
        """
        获取计算所需的额外数据字段
        
        Returns:
            list: 所需字段列表
        """
        pass
    
    @abstractmethod
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        """
        判断是否支持该资产类型
        
        Args:
            asset_type: 资产类型
            
        Returns:
            bool: 是否支持
        """
        pass


class StockMarketCapCalculator(MarketCapCalculator):
    """股票市值计算器"""
    
    def __init__(self):
        self.supported_types = [
            AssetType.STOCK_A, AssetType.STOCK_B, 
            AssetType.STOCK_H, AssetType.STOCK_US, AssetType.STOCK_HK
        ]
    
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """
        计算股票市值
        
        公式：市值 = 股价 × 股本
        
        Args:
            price: 股价
            additional_data: 包含total_shares（总股本）或circulating_shares（流通股本）
            
        Returns:
            MarketCapResult: 市值计算结果
        """
        try:
            if price <= 0:
                return MarketCapResult()
            
            total_shares = additional_data.get('total_shares')
            circulating_shares = additional_data.get('circulating_shares')
            
            if total_shares and total_shares > 0:
                market_cap = price * total_shares
                logger.debug(f"股票市值计算: {price} × {total_shares} = {market_cap}")
                return MarketCapResult(market_cap=market_cap, unit="CNY")
            elif circulating_shares and circulating_shares > 0:
                market_cap = price * circulating_shares
                logger.debug(f"股票流通市值计算: {price} × {circulating_shares} = {market_cap}")
                return MarketCapResult(market_cap=market_cap, unit="CNY")
            else:
                logger.warning("缺少股本数据，无法计算股票市值")
                return MarketCapResult()
                
        except Exception as e:
            logger.error(f"股票市值计算失败: {e}")
            return MarketCapResult()
    
    def get_required_fields(self) -> list:
        return ['total_shares', 'circulating_shares']
    
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        return asset_type in self.supported_types


class CryptoMarketCapCalculator(MarketCapCalculator):
    """加密货币市值计算器"""
    
    def __init__(self):
        self.supported_types = [AssetType.CRYPTO]
    
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """
        计算加密货币市值
        
        公式：市值 = 价格 × 总供应量
        
        Args:
            price: 当前价格
            additional_data: 包含total_supply（总供应量）或circulating_supply（流通供应量）
            
        Returns:
            MarketCapResult: 市值计算结果
        """
        try:
            if price <= 0:
                return MarketCapResult()
            
            total_supply = additional_data.get('total_supply')
            circulating_supply = additional_data.get('circulating_supply')
            
            if total_supply and total_supply > 0:
                market_cap = price * total_supply
                logger.debug(f"加密货币市值计算: {price} × {total_supply} = {market_cap}")
                return MarketCapResult(market_cap=market_cap, unit="USD")
            elif circulating_supply and circulating_supply > 0:
                market_cap = price * circulating_supply
                logger.debug(f"加密货币流通市值计算: {price} × {circulating_supply} = {market_cap}")
                return MarketCapResult(market_cap=market_cap, unit="USD")
            else:
                logger.warning("缺少供应量数据，无法计算加密货币市值")
                return MarketCapResult()
                
        except Exception as e:
            logger.error(f"加密货币市值计算失败: {e}")
            return MarketCapResult()
    
    def get_required_fields(self) -> list:
        return ['total_supply', 'circulating_supply']
    
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        return asset_type in self.supported_types


class FundMarketCapCalculator(MarketCapCalculator):
    """基金市值计算器"""
    
    def __init__(self):
        self.supported_types = [AssetType.FUND]
    
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """
        计算基金市值
        
        公式：市值 = 净值 × 份额
        
        Args:
            price: 基金净值（NAV）
            additional_data: 包含total_units（总份额）
            
        Returns:
            MarketCapResult: 市值计算结果
        """
        try:
            if price <= 0:
                return MarketCapResult()
            
            total_units = additional_data.get('total_units')
            
            if total_units and total_units > 0:
                market_cap = price * total_units
                logger.debug(f"基金市值计算: {price} × {total_units} = {market_cap}")
                return MarketCapResult(market_cap=market_cap, unit="CNY")
            else:
                logger.warning("缺少份额数据，无法计算基金市值")
                return MarketCapResult()
                
        except Exception as e:
            logger.error(f"基金市值计算失败: {e}")
            return MarketCapResult()
    
    def get_required_fields(self) -> list:
        return ['total_units']
    
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        return asset_type in self.supported_types


class FuturesMarketCapCalculator(MarketCapCalculator):
    """期货市值计算器（返回持仓量）"""
    
    def __init__(self):
        self.supported_types = [AssetType.FUTURES, AssetType.OPTION, AssetType.WARRANT]
    
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """
        计算期货持仓量（期货没有市值概念）
        
        Args:
            price: 当前价格
            additional_data: 包含open_interest（持仓量）
            
        Returns:
            MarketCapResult: 返回持仓量作为替代指标
        """
        try:
            open_interest = additional_data.get('open_interest', 0)
            logger.debug(f"期货持仓量: {open_interest}")
            return MarketCapResult(
                alternative_metric='open_interest',
                alternative_value=open_interest,
                unit="手"
            )
                
        except Exception as e:
            logger.error(f"期货持仓量获取失败: {e}")
            return MarketCapResult()
    
    def get_required_fields(self) -> list:
        return ['open_interest']
    
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        return asset_type in self.supported_types


class ForexMarketCapCalculator(MarketCapCalculator):
    """外汇市值计算器（返回交易量）"""
    
    def __init__(self):
        self.supported_types = [AssetType.FOREX]
    
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """
        计算外汇交易量（外汇没有市值概念）
        
        Args:
            price: 当前汇率
            additional_data: 包含volume（交易量）
            
        Returns:
            MarketCapResult: 返回交易量作为替代指标
        """
        try:
            volume = additional_data.get('volume', 0)
            logger.debug(f"外汇交易量: {volume}")
            return MarketCapResult(
                alternative_metric='volume',
                alternative_value=volume,
                unit="手"
            )
                
        except Exception as e:
            logger.error(f"外汇交易量获取失败: {e}")
            return MarketCapResult()
    
    def get_required_fields(self) -> list:
        return ['volume']
    
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        return asset_type in self.supported_types


class IndexMarketCapCalculator(MarketCapCalculator):
    """指数市值计算器（返回成分股总市值）"""
    
    def __init__(self):
        self.supported_types = [AssetType.INDEX]
    
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """
        计算指数成分股总市值
        
        Args:
            price: 指数点位
            additional_data: 包含total_market_cap（成分股总市值）
            
        Returns:
            MarketCapResult: 返回成分股总市值
        """
        try:
            total_market_cap = additional_data.get('total_market_cap')
            
            if total_market_cap and total_market_cap > 0:
                logger.debug(f"指数成分股总市值: {total_market_cap}")
                return MarketCapResult(
                    market_cap=total_market_cap,
                    unit="CNY"
                )
            else:
                logger.warning("缺少成分股市值数据")
                return MarketCapResult()
                
        except Exception as e:
            logger.error(f"指数市值计算失败: {e}")
            return MarketCapResult()
    
    def get_required_fields(self) -> list:
        return ['total_market_cap']
    
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        return asset_type in self.supported_types


class DefaultMarketCapCalculator(MarketCapCalculator):
    """默认市值计算器（返回None）"""
    
    def calculate(self, price: float, additional_data: Dict[str, Any]) -> MarketCapResult:
        """默认实现，返回空结果"""
        logger.warning(f"不支持的资产类型，无法计算市值")
        return MarketCapResult()
    
    def get_required_fields(self) -> list:
        return []
    
    def supports_asset_type(self, asset_type: AssetType) -> bool:
        return True


class MarketCapCalculatorFactory:
    """市值计算器工厂"""
    
    def __init__(self):
        self._calculators = {
            'stock': StockMarketCapCalculator(),
            'crypto': CryptoMarketCapCalculator(),
            'fund': FundMarketCapCalculator(),
            'futures': FuturesMarketCapCalculator(),
            'forex': ForexMarketCapCalculator(),
            'index': IndexMarketCapCalculator(),
            'default': DefaultMarketCapCalculator()
        }
    
    def get_calculator(self, asset_type: AssetType) -> MarketCapCalculator:
        """
        根据资产类型获取对应的计算器
        
        Args:
            asset_type: 资产类型
            
        Returns:
            MarketCapCalculator: 市值计算器
        """
        asset_type_str = asset_type.value if isinstance(asset_type, AssetType) else str(asset_type)
        
        if 'stock' in asset_type_str:
            return self._calculators['stock']
        elif asset_type_str == 'crypto':
            return self._calculators['crypto']
        elif asset_type_str == 'fund':
            return self._calculators['fund']
        elif asset_type_str in ('futures', 'option', 'warrant'):
            return self._calculators['futures']
        elif asset_type_str == 'forex':
            return self._calculators['forex']
        elif asset_type_str == 'index':
            return self._calculators['index']
        else:
            logger.warning(f"未知的资产类型: {asset_type_str}，使用默认计算器")
            return self._calculators['default']
    
    def register_calculator(self, key: str, calculator: MarketCapCalculator):
        """
        注册自定义计算器
        
        Args:
            key: 计算器键
            calculator: 计算器实例
        """
        self._calculators[key] = calculator
        logger.info(f"已注册自定义市值计算器: {key}")


_global_factory = None


def get_market_cap_calculator_factory() -> MarketCapCalculatorFactory:
    """获取全局市值计算器工厂实例"""
    global _global_factory
    if _global_factory is None:
        _global_factory = MarketCapCalculatorFactory()
    return _global_factory
