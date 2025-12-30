from loguru import logger
"""
指标插件扩展接口
为指标系统插件化提供标准化的指标插件接口和适配器
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod
from core.network.universal_network_config import INetworkConfigurable
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime


class IndicatorCategory(Enum):
    """指标分类"""
    TREND = "trend"                    # 趋势指标
    MOMENTUM = "momentum"              # 动量指标
    VOLATILITY = "volatility"          # 波动率指标
    VOLUME = "volume"                  # 成交量指标
    OSCILLATOR = "oscillator"          # 震荡指标
    SUPPORT_RESISTANCE = "support_resistance"  # 支撑阻力指标
    CUSTOM = "custom"                  # 自定义指标

class ParameterType(Enum):
    """参数类型"""
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    STRING = "string"
    ENUM = "enum"

@dataclass
class ParameterDef:
    """参数定义"""
    name: str
    type: ParameterType
    default_value: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    description: str = ""
    enum_values: Optional[List[str]] = None
    required: bool = True

@dataclass
class IndicatorMetadata:
    """指标元数据"""
    name: str
    display_name: str
    description: str
    category: IndicatorCategory
    parameters: List[ParameterDef]
    output_columns: List[str]
    input_columns: List[str] = None
    min_periods: int = 1
    author: str = ""
    version: str = "1.0.0"
    tags: List[str] = None

    def __post_init__(self):
        if self.input_columns is None:
            self.input_columns = ["close"]
        if self.tags is None:
            self.tags = []

@dataclass
class StandardKlineData:
    """标准K线数据格式"""
    open: pd.Series
    high: pd.Series
    low: pd.Series
    close: pd.Series
    volume: pd.Series
    datetime_index: pd.DatetimeIndex

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> 'StandardKlineData':
        """从DataFrame创建标准K线数据"""
        logger.debug("开始从DataFrame创建StandardKlineData...")
        
        # 复制DataFrame以避免修改原始数据
        cleaned_df = df.copy()
        
        # 清理重复字符串
        cleaned_df = cls._clean_repeat_strings_in_dataframe(cleaned_df, "StandardKlineData")
        
        # 确保数值列是数值类型，处理重复字符串
        for col in ['open', 'high', 'low', 'close']:
            if col in cleaned_df.columns:
                cleaned_df[col] = cls._safe_convert_to_numeric_series(cleaned_df[col], col)
        
        if 'volume' in cleaned_df.columns:
            cleaned_df['volume'] = cls._safe_convert_to_numeric_series(cleaned_df['volume'], 'volume')
        
        logger.debug("StandardKlineData创建完成")
        
        return cls(
            open=cleaned_df['open'],
            high=cleaned_df['high'],
            low=cleaned_df['low'],
            close=cleaned_df['close'],
            volume=cleaned_df.get('volume', pd.Series(index=cleaned_df.index)),
            datetime_index=cleaned_df.index if isinstance(cleaned_df.index, pd.DatetimeIndex) else pd.to_datetime(cleaned_df.index)
        )
    
    @classmethod
    def _clean_repeat_strings_in_dataframe(cls, df: pd.DataFrame, context: str = "") -> pd.DataFrame:
        """清理DataFrame中的重复字符串"""
        try:
            cleaned_df = df.copy()
            repeat_count = 0
            
            for col in cleaned_df.columns:
                if cleaned_df[col].dtype == 'object':
                    repeat_mask = cleaned_df[col].astype(str).apply(cls._is_repeat_string)
                    if repeat_mask.any():
                        repeat_count += repeat_mask.sum()
                        cleaned_df.loc[repeat_mask, col] = np.nan
                        
                        # 记录检测到的重复字符串
                        repeat_strings = cleaned_df.loc[repeat_mask, col].unique()
                        logger.warning(f"{context}列{col}检测到{repeat_count}个重复字符串: {[s[:20]+'...' if len(str(s))>20 else s for s in repeat_strings[:3]]}")
            
            if repeat_count > 0:
                logger.info(f"{context}DataFrame清理完成: 共清理{repeat_count}个重复字符串")
            else:
                logger.debug(f"{context}DataFrame无需清理: 未检测到重复字符串")
                
            return cleaned_df
            
        except Exception as e:
            logger.error(f"{context}DataFrame字符串清理失败: {e}")
            return df
    
    @classmethod
    def _safe_convert_to_numeric_series(cls, series: pd.Series, col_name: str) -> pd.Series:
        """安全地转换Series为数值类型"""
        try:
            # 先检查重复字符串
            repeat_mask = series.astype(str).apply(cls._is_repeat_string)
            if repeat_mask.any():
                logger.warning(f"列{col_name}检测到{repeat_mask.sum()}个重复字符串，将转换为NaN")
                series = series.copy()
                series.loc[repeat_mask] = np.nan
            
            # 转换为数值类型
            numeric_series = pd.to_numeric(series, errors='coerce')
            return numeric_series
            
        except Exception as e:
            logger.error(f"列{col_name}数值转换失败: {e}")
            return series
    
    @classmethod
    def _is_repeat_string(cls, value: Any) -> bool:
        """检测是否为重复字符串模式"""
        try:
            if not isinstance(value, str):
                return False
                
            # 如果字符串长度小于等于10，不是重复模式
            if len(value) <= 10:
                return False
            
            # 检查是否为基础字符串的重复模式
            for i in range(1, min(len(value), 20)):
                unit = value[:i]
                if len(value) % len(unit) == 0:
                    repeated = unit * (len(value) // len(unit))
                    if value == repeated:
                        logger.debug(f"检测到重复字符串模式: 单元='{unit}', 长度={i}, 重复次数={len(value) // i}")
                        return True
            
            return False
            
        except Exception as e:
            logger.debug(f"重复字符串检测失败: {e}")
            return False

    def to_dataframe(self) -> pd.DataFrame:
        """转换为DataFrame"""
        return pd.DataFrame({
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }, index=self.datetime_index)

@dataclass
class StandardIndicatorResult:
    """标准指标结果格式"""
    data: pd.DataFrame
    metadata: Dict[str, Any]
    calculation_time_ms: float
    parameters: Dict[str, Any]
    indicator_name: str

    def get_column(self, column_name: str) -> pd.Series:
        """获取指定列"""
        return self.data.get(column_name, pd.Series())

    def get_all_columns(self) -> List[str]:
        """获取所有列名"""
        return list(self.data.columns)

@dataclass
class IndicatorCalculationContext:
    """指标计算上下文"""
    symbol: str
    timeframe: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    cache_enabled: bool = True
    parallel_enabled: bool = False
    extra_params: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra_params is None:
            self.extra_params = {}

class IIndicatorPlugin(ABC, INetworkConfigurable):
    """
    指标插件接口

    为指标系统插件化提供标准化的指标接口
    支持多种指标类型、参数验证、元数据管理等功能
    """

    @property
    @abstractmethod
    def plugin_info(self) -> Dict[str, Any]:
        """获取插件信息"""
        pass

    @abstractmethod
    def get_supported_indicators(self) -> List[str]:
        """
        获取支持的指标列表

        Returns:
            List[str]: 支持的指标名称列表
        """
        pass

    @abstractmethod
    def get_indicator_metadata(self, indicator_name: str) -> IndicatorMetadata:
        """
        获取指标元数据

        Args:
            indicator_name: 指标名称

        Returns:
            IndicatorMetadata: 指标元数据
        """
        pass

    @abstractmethod
    def validate_parameters(self, indicator_name: str, parameters: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证指标参数

        Args:
            indicator_name: 指标名称
            parameters: 参数字典

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        pass

    @abstractmethod
    def calculate_indicator(self,
                            indicator_name: str,
                            data: StandardKlineData,
                            parameters: Dict[str, Any],
                            context: Optional[IndicatorCalculationContext] = None) -> StandardIndicatorResult:
        """
        计算指标

        Args:
            indicator_name: 指标名称
            data: 标准K线数据
            parameters: 指标参数
            context: 计算上下文

        Returns:
            StandardIndicatorResult: 标准指标结果
        """
        pass

    def batch_calculate_indicators(self,
                                   indicators: List[Tuple[str, Dict[str, Any]]],
                                   data: StandardKlineData,
                                   context: Optional[IndicatorCalculationContext] = None) -> Dict[str, StandardIndicatorResult]:
        """
        批量计算指标（可选实现）

        Args:
            indicators: 指标列表 [(指标名称, 参数), ...]
            data: 标准K线数据
            context: 计算上下文

        Returns:
            Dict[str, StandardIndicatorResult]: 指标结果字典
        """
        results = {}
        for indicator_name, parameters in indicators:
            try:
                result = self.calculate_indicator(indicator_name, data, parameters, context)
                results[indicator_name] = result
            except Exception as e:
                logger.error(f"批量计算指标失败 {indicator_name}: {e}")
                # 创建空结果
                results[indicator_name] = StandardIndicatorResult(
                    data=pd.DataFrame(),
                    metadata={'error': str(e)},
                    calculation_time_ms=0.0,
                    parameters=parameters,
                    indicator_name=indicator_name
                )
        return results

    def get_indicator_categories(self) -> Dict[IndicatorCategory, List[str]]:
        """
        获取按类别分组的指标

        Returns:
            Dict[IndicatorCategory, List[str]]: 按类别分组的指标字典
        """
        categories = {}
        for indicator_name in self.get_supported_indicators():
            try:
                metadata = self.get_indicator_metadata(indicator_name)
                category = metadata.category
                if category not in categories:
                    categories[category] = []
                categories[category].append(indicator_name)
            except Exception as e:
                logger.warning(f"获取指标分类失败 {indicator_name}: {e}")
        return categories

    def get_indicator_parameters(self, indicator_name: str) -> Dict[str, Any]:
        """
        获取指标参数定义

        Args:
            indicator_name: 指标名称

        Returns:
            Dict[str, Any]: 参数定义字典
        """
        try:
            metadata = self.get_indicator_metadata(indicator_name)
            return {param.name: param.default_value for param in metadata.parameters}
        except Exception as e:
            logger.error(f"获取指标参数失败 {indicator_name}: {e}")
            return {}

    def test_indicator(self, indicator_name: str, parameters: Dict[str, Any] = None) -> bool:
        """
        测试指标计算

        Args:
            indicator_name: 指标名称
            parameters: 测试参数

        Returns:
            bool: 测试是否通过
        """
        try:
            # 创建测试数据
            dates = pd.date_range('2023-01-01', periods=100, freq='D')
            test_data = pd.DataFrame({
                'open': np.random.randn(100).cumsum() + 100,
                'high': np.random.randn(100).cumsum() + 105,
                'low': np.random.randn(100).cumsum() + 95,
                'close': np.random.randn(100).cumsum() + 100,
                'volume': np.random.randint(1000, 10000, 100)
            }, index=dates)

            kline_data = StandardKlineData.from_dataframe(test_data)

            # 使用默认参数或提供的参数
            if parameters is None:
                parameters = self.get_indicator_parameters(indicator_name)

            # 计算指标
            result = self.calculate_indicator(indicator_name, kline_data, parameters)

            # 检查结果
            return not result.data.empty and len(result.data.columns) > 0

        except Exception as e:
            logger.error(f"测试指标失败 {indicator_name}: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取插件统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "supported_indicators": len(self.get_supported_indicators()),
            "categories": len(self.get_indicator_categories()),
            "plugin_info": self.plugin_info
        }

class IndicatorPluginAdapter:
    """
    指标插件适配器

    将插件接口适配到现有的指标管理系统
    提供统一的访问接口和错误处理
    """

    def __init__(self, plugin: IIndicatorPlugin, plugin_id: str):
        """
        初始化适配器

        Args:
            plugin: 指标插件实例
            plugin_id: 插件唯一标识
        """
        self.plugin = plugin
        self.plugin_id = plugin_id
        self.logger = logger.bind(module=self.__class__.__name__)
        # 缓存
        self._metadata_cache = {}
        self._parameters_cache = {}

    def get_supported_indicators(self) -> List[str]:
        """获取支持的指标列表"""
        try:
            return self.plugin.get_supported_indicators()
        except Exception as e:
            self.logger.error(f"获取支持指标列表异常: {self.plugin_id} - {e}")
            return []

    def get_indicator_metadata(self, indicator_name: str) -> Optional[IndicatorMetadata]:
        """获取指标元数据"""
        try:
            # 检查缓存
            if indicator_name in self._metadata_cache:
                return self._metadata_cache[indicator_name]

            metadata = self.plugin.get_indicator_metadata(indicator_name)
            self._metadata_cache[indicator_name] = metadata
            return metadata

        except Exception as e:
            self.logger.error(f"获取指标元数据异常: {self.plugin_id}.{indicator_name} - {e}")
            return None

    def calculate_indicator(self,
                            indicator_name: str,
                            data: Union[pd.DataFrame, StandardKlineData],
                            parameters: Dict[str, Any],
                            context: Optional[IndicatorCalculationContext] = None) -> Optional[StandardIndicatorResult]:
        """计算指标"""
        try:
            # 转换数据格式
            if isinstance(data, pd.DataFrame):
                kline_data = StandardKlineData.from_dataframe(data)
            else:
                kline_data = data

            # 验证参数
            is_valid, error_msg = self.plugin.validate_parameters(indicator_name, parameters)
            if not is_valid:
                self.logger.error(f"指标参数验证失败: {indicator_name} - {error_msg}")
                return None

            # 计算指标
            result = self.plugin.calculate_indicator(indicator_name, kline_data, parameters, context)
            return result

        except Exception as e:
            self.logger.error(f"计算指标异常: {self.plugin_id}.{indicator_name} - {e}")
            return None

    def batch_calculate_indicators(self,
                                   indicators: List[Tuple[str, Dict[str, Any]]],
                                   data: Union[pd.DataFrame, StandardKlineData],
                                   context: Optional[IndicatorCalculationContext] = None) -> Dict[str, StandardIndicatorResult]:
        """批量计算指标"""
        try:
            # 转换数据格式
            if isinstance(data, pd.DataFrame):
                kline_data = StandardKlineData.from_dataframe(data)
            else:
                kline_data = data

            return self.plugin.batch_calculate_indicators(indicators, kline_data, context)

        except Exception as e:
            self.logger.error(f"批量计算指标异常: {self.plugin_id} - {e}")
            return {}

    def get_indicator_categories(self) -> Dict[IndicatorCategory, List[str]]:
        """获取指标分类"""
        try:
            return self.plugin.get_indicator_categories()
        except Exception as e:
            self.logger.error(f"获取指标分类异常: {self.plugin_id} - {e}")
            return {}

    def test_indicator(self, indicator_name: str, parameters: Dict[str, Any] = None) -> bool:
        """测试指标"""
        try:
            return self.plugin.test_indicator(indicator_name, parameters)
        except Exception as e:
            self.logger.error(f"测试指标异常: {self.plugin_id}.{indicator_name} - {e}")
            return False

    def get_plugin_info(self) -> Dict[str, Any]:
        """获取插件信息"""
        return self.plugin.plugin_info

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            return self.plugin.get_statistics()
        except Exception as e:
            self.logger.error(f"获取统计信息异常: {self.plugin_id} - {e}")
            return {}

    def clear_cache(self) -> None:
        """清理缓存"""
        self._metadata_cache.clear()
        self._parameters_cache.clear()
        self.logger.info(f"指标插件缓存已清理: {self.plugin_id}")

def validate_indicator_plugin_interface(plugin_instance) -> bool:
    """
    验证插件是否实现了必要的接口

    Args:
        plugin_instance: 插件实例

    Returns:
        bool: 是否符合接口要求
    """
    required_methods = [
        'get_supported_indicators', 'get_indicator_metadata',
        'validate_parameters', 'calculate_indicator'
    ]

    # 检查plugin_info属性（可以是属性或方法）
    if not hasattr(plugin_instance, 'plugin_info'):
        logger.error("指标插件缺少plugin_info属性")
        return False

    plugin_info = getattr(plugin_instance, 'plugin_info')
    if callable(plugin_info):
        # 如果是方法，尝试调用
        try:
            plugin_info()
        except Exception as e:
            logger.error(f"指标插件plugin_info方法调用失败: {e}")
            return False
    elif not isinstance(plugin_info, dict):
        logger.error("指标插件plugin_info必须是字典或返回字典的方法")
        return False

    # 检查必要方法
    for method_name in required_methods:
        if not hasattr(plugin_instance, method_name):
            logger.error(f"指标插件缺少必要方法: {method_name}")
            return False

        method = getattr(plugin_instance, method_name)
        if not callable(method):
            logger.error(f"指标插件方法不可调用: {method_name}")
            return False

    return True

def create_indicator_plugin_adapter(plugin_instance, plugin_id: str) -> Optional[IndicatorPluginAdapter]:
    """
    创建指标插件适配器

    Args:
        plugin_instance: 插件实例
        plugin_id: 插件标识

    Returns:
        Optional[IndicatorPluginAdapter]: 适配器实例或None
    """
    if not validate_indicator_plugin_interface(plugin_instance):
        logger.error(f"指标插件接口验证失败: {plugin_id}")
        return None

    try:
        adapter = IndicatorPluginAdapter(plugin_instance, plugin_id)
        logger.info(f"指标插件适配器创建成功: {plugin_id}")
        return adapter
    except Exception as e:
        logger.error(f"创建指标插件适配器失败: {plugin_id} - {e}")
        return None

# 工具函数
def convert_dataframe_to_standard_kline(df: pd.DataFrame) -> StandardKlineData:
    """将DataFrame转换为标准K线数据"""
    return StandardKlineData.from_dataframe(df)

def convert_standard_result_to_dataframe(result: StandardIndicatorResult) -> pd.DataFrame:
    """将标准指标结果转换为DataFrame"""
    return result.data

def merge_indicator_results(results: List[StandardIndicatorResult]) -> pd.DataFrame:
    """合并多个指标结果"""
    if not results:
        return pd.DataFrame()

    merged_df = results[0].data.copy()
    for result in results[1:]:
        merged_df = pd.concat([merged_df, result.data], axis=1)

    # 去重列名
    merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]
    return merged_df
