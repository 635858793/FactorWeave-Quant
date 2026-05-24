"""
增强指标服务 - TA-Lib完全集成版本
完全脱离hikyuu依赖，使用TA-Lib进行技术指标计算
"""

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    talib = None
    TALIB_AVAILABLE = False
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
from collections import defaultdict, deque
import warnings

from loguru import logger
from ..utils.data_standardizer import DataStandardizer, IndicatorDataPreparer


class IndicatorCategory(Enum):
    """指标类别"""
    TREND = "trend"                  # 趋势指标
    MOMENTUM = "momentum"            # 动量指标  
    VOLATILITY = "volatility"        # 波动率指标
    VOLUME = "volume"                # 成交量指标
    OSCILLATOR = "oscillator"        # 振荡指标
    PRICE_ACTION = "price_action"    # 价格行为指标
    CUSTOM = "custom"                # 自定义指标


class IndicatorStatus(Enum):
    """指标状态"""
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    DEPENDENCY_MISSING = "dependency_missing"


@dataclass
class IndicatorDefinition:
    """指标定义"""
    name: str
    category: IndicatorCategory
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    required_columns: List[str] = field(default_factory=list)
    output_columns: List[str] = field(default_factory=list)
    talib_function: Optional[str] = None
    custom_function: Optional[callable] = None
    status: IndicatorStatus = IndicatorStatus.ENABLED


@dataclass
class IndicatorResult:
    """指标计算结果"""
    name: str
    timestamp: datetime
    data: Union[np.ndarray, Dict[str, np.ndarray]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    computation_time: float = 0.0
    error_message: Optional[str] = None


class EnhancedIndicatorService:
    """TA-Lib指标服务
    
    提供完整的技术指标计算功能，完全脱离hikyuu
    """
    
    def __init__(self):
        """初始化TA-Lib指标服务"""
        self._lock = threading.RLock()
        self._indicators: Dict[str, IndicatorDefinition] = {}
        self._results_cache: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._error_counters: Dict[str, int] = defaultdict(int)
        
        # 初始化指标定义
        self._initialize_indicators()
        
    def _initialize_indicators(self):
        """初始化所有支持的指标"""
        
        # 趋势指标
        self.register_indicator(IndicatorDefinition(
            name="SMA",
            category=IndicatorCategory.TREND,
            description="简单移动平均线",
            parameters={"timeperiod": 20},
            required_columns=["close"],
            output_columns=["SMA"],
            talib_function="SMA"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="EMA", 
            category=IndicatorCategory.TREND,
            description="指数移动平均线",
            parameters={"timeperiod": 20},
            required_columns=["close"],
            output_columns=["EMA"],
            talib_function="EMA"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="MACD",
            category=IndicatorCategory.TREND, 
            description="MACD指标",
            parameters={"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
            required_columns=["close"],
            output_columns=["MACD", "MACDsignal", "MACDhist"],
            talib_function="MACD"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="ADX",
            category=IndicatorCategory.TREND,
            description="平均趋向指数",
            parameters={"timeperiod": 14},
            required_columns=["high", "low", "close"],
            output_columns=["ADX", "PLUS_DI", "MINUS_DI"],
            talib_function="ADX"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="AROON",
            category=IndicatorCategory.TREND,
            description="Aroon指标",
            parameters={"timeperiod": 14},
            required_columns=["high", "low"],
            output_columns=["AROON_up", "AROON_down", "AROON_ind"],
            talib_function="AROON"
        ))
        
        # 动量指标
        self.register_indicator(IndicatorDefinition(
            name="RSI",
            category=IndicatorCategory.MOMENTUM,
            description="相对强弱指数",
            parameters={"timeperiod": 14},
            required_columns=["close"],
            output_columns=["RSI"],
            talib_function="RSI"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="STOCH",
            category=IndicatorCategory.MOMENTUM,
            description="随机指标",
            parameters={"fastk_period": 5, "slowk_period": 3, "slowd_period": 3},
            required_columns=["high", "low", "close"],
            output_columns=["STOCH_k", "STOCH_d"],
            talib_function="STOCH"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="WILLR",
            category=IndicatorCategory.MOMENTUM,
            description="威廉指标",
            parameters={"timeperiod": 14},
            required_columns=["high", "low", "close"],
            output_columns=["WILLR"],
            talib_function="WILLR"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="CCI",
            category=IndicatorCategory.MOMENTUM,
            description="商品通道指数",
            parameters={"timeperiod": 14},
            required_columns=["high", "low", "close"],
            output_columns=["CCI"],
            talib_function="CCI"
        ))
        
        # 波动率指标
        self.register_indicator(IndicatorDefinition(
            name="ATR",
            category=IndicatorCategory.VOLATILITY,
            description="真实波动范围",
            parameters={"timeperiod": 14},
            required_columns=["high", "low", "close"],
            output_columns=["ATR"],
            talib_function="ATR"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="BBANDS",
            category=IndicatorCategory.VOLATILITY,
            description="布林带",
            parameters={"timeperiod": 20, "nbdevup": 2, "nbdevdn": 2},
            required_columns=["close"],
            output_columns=["BB_upper", "BB_middle", "BB_lower"],
            talib_function="BBANDS"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="NATR",
            category=IndicatorCategory.VOLATILITY,
            description="标准化ATR",
            parameters={"timeperiod": 14},
            required_columns=["high", "low", "close"],
            output_columns=["NATR"],
            talib_function="NATR"
        ))
        
        # 成交量指标
        self.register_indicator(IndicatorDefinition(
            name="OBV",
            category=IndicatorCategory.VOLUME,
            description="能量潮",
            parameters={},
            required_columns=["close", "volume"],
            output_columns=["OBV"],
            talib_function="OBV"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="AD",
            category=IndicatorCategory.VOLUME,
            description="集散指标",
            parameters={},
            required_columns=["high", "low", "close", "volume"],
            output_columns=["AD"],
            talib_function="AD"
        ))
        
        # 价格行为指标
        self.register_indicator(IndicatorDefinition(
            name="SAR",
            category=IndicatorCategory.PRICE_ACTION,
            description="抛物线SAR",
            parameters={"acceleration": 0.02, "maximum": 0.2},
            required_columns=["high", "low"],
            output_columns=["SAR"],
            talib_function="SAR"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="DEMA",
            category=IndicatorCategory.TREND,
            description="双指数移动平均",
            parameters={"timeperiod": 30},
            required_columns=["close"],
            output_columns=["DEMA"],
            talib_function="DEMA"
        ))
        
        self.register_indicator(IndicatorDefinition(
            name="TEMA",
            category=IndicatorCategory.TREND,
            description="三指数移动平均",
            parameters={"timeperiod": 30},
            required_columns=["close"],
            output_columns=["TEMA"],
            talib_function="TEMA"
        ))
        
        logger.info(f"初始化了 {len(self._indicators)} 个技术指标")
        
    def register_indicator(self, definition: IndicatorDefinition):
        """注册指标定义"""
        with self._lock:
            self._indicators[definition.name] = definition
            
    def get_indicator_definitions(self, category: Optional[IndicatorCategory] = None) -> List[IndicatorDefinition]:
        """获取指标定义"""
        with self._lock:
            indicators = list(self._indicators.values())
            if category:
                indicators = [ind for ind in indicators if ind.category == category]
            return indicators
            
    def calculate_indicator(self, 
                          indicator_name: str,
                          data: Union[pd.DataFrame, Dict[str, np.ndarray]],
                          parameters: Optional[Dict[str, Any]] = None) -> IndicatorResult:
        """计算单个指标
        
        Args:
            indicator_name: 指标名称
            data: 输入数据 (DataFrame或numpy数组字典)
            parameters: 指标参数
            
        Returns:
            指标计算结果
        """
        start_time = datetime.now()
        
        try:
            # 验证指标是否存在
            if indicator_name not in self._indicators:
                raise ValueError(f"未知指标: {indicator_name}")
                
            definition = self._indicators[indicator_name]
            
            if definition.status != IndicatorStatus.ENABLED:
                raise ValueError(f"指标 {indicator_name} 已禁用")
                
            # 准备数据
            if isinstance(data, pd.DataFrame):
                arrays = IndicatorDataPreparer.prepare_talib_inputs(data)
            else:
                arrays = data
                
            # 获取指标参数
            params = {**definition.parameters}
            if parameters:
                params.update(parameters)
                
            # 计算指标
            if definition.talib_function:
                result = self._calculate_talib_indicator(definition, arrays, params)
            elif definition.custom_function:
                result = self._calculate_custom_indicator(definition, arrays, params)
            else:
                raise ValueError(f"指标 {indicator_name} 没有配置计算函数")
                
            # 计算执行时间
            computation_time = (datetime.now() - start_time).total_seconds()
            
            # 构建结果
            indicator_result = IndicatorResult(
                name=indicator_name,
                timestamp=datetime.now(),
                data=result,
                computation_time=computation_time
            )
            
            # 缓存结果
            cache_key = f"{indicator_name}_{hash(str(sorted(params.items())))}"
            self._results_cache[cache_key].append(indicator_result)
            
            # 重置错误计数
            self._error_counters[indicator_name] = 0
            
            return indicator_result
            
        except Exception as e:
            # 增加错误计数
            self._error_counters[indicator_name] += 1
            
            computation_time = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"计算指标 {indicator_name} 失败: {e}")
            
            return IndicatorResult(
                name=indicator_name,
                timestamp=datetime.now(),
                data=None,
                computation_time=computation_time,
                error_message=str(e)
            )
            
    def _calculate_talib_indicator(self, 
                                 definition: IndicatorDefinition,
                                 data: Dict[str, np.ndarray],
                                 parameters: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """计算TA-Lib指标"""
        func_name = definition.talib_function
        required_columns = definition.required_columns
        
        # 检查必需的数据列
        missing_columns = set(required_columns) - set(data.keys())
        if missing_columns:
            raise ValueError(f"缺少必需数据列: {missing_columns}")
            
        # 获取数据数组
        inputs = {col: data[col] for col in required_columns}
        
        # 调用TA-Lib函数
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning)
            
            try:
                if func_name == "SMA":
                    result = talib.SMA(inputs['close'], **parameters)
                    return {"SMA": result}
                    
                elif func_name == "EMA":
                    result = talib.EMA(inputs['close'], **parameters)
                    return {"EMA": result}
                    
                elif func_name == "MACD":
                    macd, signal, hist = talib.MACD(inputs['close'], **parameters)
                    return {
                        "MACD": macd,
                        "MACDsignal": signal, 
                        "MACDhist": hist
                    }
                    
                elif func_name == "ADX":
                    adx, plus_di, minus_di = talib.ADX(inputs['high'], inputs['low'], inputs['close'], **parameters)
                    return {
                        "ADX": adx,
                        "PLUS_DI": plus_di,
                        "MINUS_DI": minus_di
                    }
                    
                elif func_name == "AROON":
                    aroon_up, aroon_down = talib.AROON(inputs['high'], inputs['low'], **parameters)
                    # 计算AROON指示器
                    aroon_ind = aroon_up - aroon_down
                    return {
                        "AROON_up": aroon_up,
                        "AROON_down": aroon_down,
                        "AROON_ind": aroon_ind
                    }
                    
                elif func_name == "RSI":
                    result = talib.RSI(inputs['close'], **parameters)
                    return {"RSI": result}
                    
                elif func_name == "STOCH":
                    slowk, slowd = talib.STOCH(inputs['high'], inputs['low'], inputs['close'], **parameters)
                    return {
                        "STOCH_k": slowk,
                        "STOCH_d": slowd
                    }
                    
                elif func_name == "WILLR":
                    result = talib.WILLR(inputs['high'], inputs['low'], inputs['close'], **parameters)
                    return {"WILLR": result}
                    
                elif func_name == "CCI":
                    result = talib.CCI(inputs['high'], inputs['low'], inputs['close'], **parameters)
                    return {"CCI": result}
                    
                elif func_name == "ATR":
                    result = talib.ATR(inputs['high'], inputs['low'], inputs['close'], **parameters)
                    return {"ATR": result}
                    
                elif func_name == "BBANDS":
                    upper, middle, lower = talib.BBANDS(inputs['close'], **parameters)
                    return {
                        "BB_upper": upper,
                        "BB_middle": middle,
                        "BB_lower": lower
                    }
                    
                elif func_name == "NATR":
                    result = talib.NATR(inputs['high'], inputs['low'], inputs['close'], **parameters)
                    return {"NATR": result}
                    
                elif func_name == "OBV":
                    result = talib.OBV(inputs['close'], inputs['volume'])
                    return {"OBV": result}
                    
                elif func_name == "AD":
                    result = talib.AD(inputs['high'], inputs['low'], inputs['close'], inputs['volume'])
                    return {"AD": result}
                    
                elif func_name == "SAR":
                    result = talib.SAR(inputs['high'], inputs['low'], **parameters)
                    return {"SAR": result}
                    
                elif func_name == "DEMA":
                    result = talib.DEMA(inputs['close'], **parameters)
                    return {"DEMA": result}
                    
                elif func_name == "TEMA":
                    result = talib.TEMA(inputs['close'], **parameters)
                    return {"TEMA": result}
                    
                else:
                    raise ValueError(f"不支持的TA-Lib函数: {func_name}")
                    
            except Exception as e:
                logger.error(f"TA-Lib函数 {func_name} 执行失败: {e}")
                raise
                
    def _calculate_custom_indicator(self,
                                  definition: IndicatorDefinition,
                                  data: Dict[str, np.ndarray],
                                  parameters: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """计算自定义指标"""
        if not definition.custom_function:
            raise ValueError("自定义指标函数未定义")
            
        try:
            result = definition.custom_function(data, parameters)
            return result
        except Exception as e:
            logger.error(f"自定义指标 {definition.name} 计算失败: {e}")
            raise
            
    def batch_calculate_indicators(self,
                                 indicator_names: List[str],
                                 data: Union[pd.DataFrame, Dict[str, np.ndarray]],
                                 parameters: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, IndicatorResult]:
        """批量计算指标
        
        Args:
            indicator_names: 指标名称列表
            data: 输入数据
            parameters: 各项指标参数
            
        Returns:
            指标计算结果字典
        """
        results = {}
        
        # 准备参数
        param_dict = parameters or {}
        
        for indicator_name in indicator_names:
            indicator_params = param_dict.get(indicator_name, {})
            
            try:
                result = self.calculate_indicator(indicator_name, data, indicator_params)
                results[indicator_name] = result
                
                if result.error_message:
                    logger.warning(f"指标 {indicator_name} 计算出现错误: {result.error_message}")
                    
            except Exception as e:
                logger.error(f"批量计算指标 {indicator_name} 失败: {e}")
                results[indicator_name] = IndicatorResult(
                    name=indicator_name,
                    timestamp=datetime.now(),
                    data=None,
                    error_message=str(e)
                )
                
        return results
        
    def get_indicator_history(self, indicator_name: str, limit: int = 50) -> List[IndicatorResult]:
        """获取指标计算历史"""
        cache_key_prefix = f"{indicator_name}_"
        
        with self._lock:
            matching_results = []
            
            for cache_key, result_queue in self._results_cache.items():
                if cache_key.startswith(cache_key_prefix):
                    matching_results.extend(list(result_queue))
                    
            # 按时间排序，取最新的limit个
            matching_results.sort(key=lambda x: x.timestamp, reverse=True)
            return matching_results[:limit]
            
    def get_error_statistics(self) -> Dict[str, int]:
        """获取错误统计"""
        with self._lock:
            return dict(self._error_counters)
            
    def clear_cache(self):
        """清空缓存"""
        with self._lock:
            self._results_cache.clear()
            logger.info("指标计算缓存已清空")

    def get_all_indicators(self) -> List[Dict[str, Any]]:
        """获取所有指标信息
        
        Returns:
            指标信息列表，每个指标包含：
            - name: 指标名称
            - category: 指标类别
            - description: 指标描述
            - parameters: 默认参数
            - status: 指标状态
        """
        with self._lock:
            indicators = []
            for name, definition in self._indicators.items():
                indicators.append({
                    'name': name,
                    'category': definition.category.value,
                    'description': definition.description,
                    'parameters': definition.parameters,
                    'status': definition.status.value,
                    'required_columns': definition.required_columns,
                    'output_columns': definition.output_columns
                })
            return indicators


# 便利函数
def calculate_talib_indicators(data: Union[pd.DataFrame, Dict[str, np.ndarray]], 
                             indicators: List[str]) -> Dict[str, Any]:
    """便利函数：计算多个技术指标
    
    Args:
        data: 输入数据
        indicators: 指标名称列表
        
    Returns:
        计算结果字典
    """
    service = EnhancedIndicatorService()
    results = service.batch_calculate_indicators(indicators, data)
    
    # 提取成功的结果
    successful_results = {}
    for name, result in results.items():
        if not result.error_message and result.data is not None:
            successful_results[name] = result.data
            
    return successful_results


def add_indicators_to_dataframe(df: pd.DataFrame, 
                              indicators: List[str],
                              parameters: Optional[Dict[str, Dict[str, Any]]] = None) -> pd.DataFrame:
    """便利函数：将技术指标添加到DataFrame
    
    Args:
        df: 原始DataFrame
        indicators: 要添加的指标列表
        parameters: 指标参数
        
    Returns:
        包含技术指标的DataFrame
    """
    service = TalibIndicatorService()
    results = service.batch_calculate_indicators(indicators, df, parameters)
    
    # 创建结果DataFrame的副本
    result_df = df.copy()
    
    for indicator_name, result in results.items():
        if not result.error_message and result.data is not None:
            # 添加指标数据到DataFrame
            for column_name, values in result.data.items():
                result_df[column_name] = values
                
    return result_df


# FAKE_DATA_EXCLUSION: 以下为测试/演示代码，位于 if __name__ == "__main__" 块中，使用随机数据进行演示，应从虚假数据扫描中排除
if __name__ == "__main__":
    # 创建测试数据
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    np.random.seed(42)
    
    test_data = pd.DataFrame({
        'datetime': dates,
        'open': 100 + np.cumsum(np.random.randn(100) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(100) * 0.5) + np.random.rand(100) * 2,
        'low': 100 + np.cumsum(np.random.randn(100) * 0.5) - np.random.rand(100) * 2,
        'close': 100 + np.cumsum(np.random.randn(100) * 0.5),
        'volume': np.zeros(100)
    })
    
    test_data.set_index('datetime', inplace=True)
    
    # 标准化数据
    validated_data = DataStandardizer.validate_dataframe(test_data)
    print("数据标准化成功")
    
    # 测试指标计算
    service = TalibIndicatorService()
    
    # 测试单个指标
    rsi_result = service.calculate_indicator("RSI", validated_data, {"timeperiod": 14})
    print(f"RSI计算成功: {rsi_result.data['RSI'][:5]}")
    
    # 测试批量计算
    indicators = ["SMA", "EMA", "MACD", "RSI", "BBANDS"]
    batch_results = service.batch_calculate_indicators(indicators, validated_data)
    
    print(f"批量计算完成，成功计算 {sum(1 for r in batch_results.values() if not r.error_message)}/{len(indicators)} 个指标")
    
    # 测试便利函数
    result_df = add_indicators_to_dataframe(validated_data, ["SMA", "RSI", "MACD"])
    print(f"添加指标后的DataFrame列数: {len(result_df.columns)}")
    print("列名:", list(result_df.columns))