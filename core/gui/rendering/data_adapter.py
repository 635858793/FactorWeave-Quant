#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据格式适配器

统一不同数据源的数据格式，为图表渲染提供标准化数据接口

作者: FactorWeave-Quant团队
版本: 1.0
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import warnings
from loguru import logger

from .pyqtgraph_engine import ChartType
from ...events.event_bus import EventBus


class DataFormat(Enum):
    """数据格式枚举"""
    OHLC = "ohlc"  # 开高低收
    OHLCV = "ohlcv"  # 开高低收量
    TIME_SERIES = "time_series"  # 时间序列
    NUMERICAL = "numerical"  # 数值
    CATEGORICAL = "categorical"  # 分类
    MATRIX = "matrix"  # 矩阵
    NETWORK = "network"  # 网络图
    GEOMETRIC = "geometric"  # 几何数据


class DataValidationLevel(Enum):
    """数据验证级别"""
    STRICT = "strict"  # 严格验证
    MODERATE = "moderate"  # 中等验证
    RELAXED = "relaxed"  # 宽松验证
    NONE = "none"  # 无验证


@dataclass
class DataSchema:
    """数据模式定义"""
    name: str
    format: DataFormat
    required_columns: List[str]
    optional_columns: List[str] = field(default_factory=list)
    data_types: Dict[str, str] = field(default_factory=dict)
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    sample_data: Optional[Any] = None


@dataclass
class DataQualityReport:
    """数据质量报告"""
    is_valid: bool
    score: float  # 0-1质量分数
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    statistics: Dict[str, Any] = field(default_factory=dict)
    completeness: float = 0.0
    consistency: float = 0.0
    accuracy: float = 0.0
    timeliness: float = 0.0


class DataAdapter:
    """数据适配器"""
    
    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus
        
        # 数据模式注册
        self.schemas: Dict[str, DataSchema] = {}
        
        # 数据质量监控
        self.validation_level = DataValidationLevel.MODERATE
        self.quality_reports: Dict[str, DataQualityReport] = {}
        
        # 适配器缓存
        self.cache: Dict[str, Any] = {}
        
        # 初始化预定义数据模式
        self._register_default_schemas()
        
        logger.info("数据适配器初始化完成")
        
    def _register_default_schemas(self):
        """注册预定义数据模式"""
        try:
            # OHLC模式
            ohlc_schema = DataSchema(
                name="ohlc",
                format=DataFormat.OHLC,
                required_columns=["open", "high", "low", "close"],
                data_types={
                    "open": "float64",
                    "high": "float64",
                    "low": "float64",
                    "close": "float64"
                }
            )
            self.schemas["ohlc"] = ohlc_schema
            
            # OHLCV模式
            ohlcv_schema = DataSchema(
                name="ohlcv",
                format=DataFormat.OHLCV,
                required_columns=["open", "high", "low", "close", "volume"],
                data_types={
                    "open": "float64",
                    "high": "float64",
                    "low": "float64",
                    "close": "float64",
                    "volume": "float64"
                }
            )
            self.schemas["ohlcv"] = ohlcv_schema
            
            # 时间序列模式
            time_series_schema = DataSchema(
                name="time_series",
                format=DataFormat.TIME_SERIES,
                required_columns=["timestamp", "value"],
                optional_columns=["symbol", "category"],
                data_types={
                    "timestamp": "datetime64[ns]",
                    "value": "float64",
                    "symbol": "object",
                    "category": "object"
                }
            )
            self.schemas["time_series"] = time_series_schema
            
            # 数值数据模式
            numerical_schema = DataSchema(
                name="numerical",
                format=DataFormat.NUMERICAL,
                required_columns=["x", "y"],
                data_types={
                    "x": "float64",
                    "y": "float64"
                }
            )
            self.schemas["numerical"] = numerical_schema
            
            # 混合推荐数据模式
            hybrid_recommendation_schema = DataSchema(
                name="hybrid_recommendation",
                format=DataFormat.NUMERICAL,
                required_columns=["stock_code", "score", "confidence", "recommendation_type"],
                optional_columns=["reason", "metadata"],
                data_types={
                    "stock_code": "object",
                    "score": "float64",
                    "confidence": "float64", 
                    "recommendation_type": "object",
                    "reason": "object",
                    "metadata": "object"
                },
                validation_rules={
                    "score": {"min": 0.0, "max": 1.0},
                    "confidence": {"min": 0.0, "max": 1.0},
                    "recommendation_type": {"choices": ["BUY", "SELL", "HOLD"]}
                }
            )
            self.schemas["hybrid_recommendation"] = hybrid_recommendation_schema
            
            # 传统推荐数据模式
            traditional_recommendation_schema = DataSchema(
                name="traditional_recommendation",
                format=DataFormat.NUMERICAL,
                required_columns=["stock_code", "score", "confidence", "recommendation_type"],
                optional_columns=["reason", "metadata"],
                data_types={
                    "stock_code": "object",
                    "score": "float64",
                    "confidence": "float64",
                    "recommendation_type": "object", 
                    "reason": "object",
                    "metadata": "object"
                },
                validation_rules={
                    "score": {"min": 0.0, "max": 1.0},
                    "confidence": {"min": 0.0, "max": 1.0},
                    "recommendation_type": {"choices": ["BUY", "SELL", "HOLD"]}
                }
            )
            self.schemas["traditional_recommendation"] = traditional_recommendation_schema
            
            # BettaFish信号数据模式
            bettafish_signal_schema = DataSchema(
                name="bettafish_signal",
                format=DataFormat.NUMERICAL,
                required_columns=["stock_code", "strength", "signal_type"],
                optional_columns=["confidence", "reasoning", "risk_level", "agents_consensus"],
                data_types={
                    "stock_code": "object",
                    "strength": "float64",
                    "signal_type": "object",
                    "confidence": "float64",
                    "reasoning": "object",
                    "risk_level": "object",
                    "agents_consensus": "object"
                },
                validation_rules={
                    "strength": {"min": 0.0, "max": 1.0},
                    "confidence": {"min": 0.0, "max": 1.0},
                    "signal_type": {"choices": ["BUY", "SELL", "HOLD"]},
                    "risk_level": {"choices": ["LOW", "MEDIUM", "HIGH"]}
                }
            )
            self.schemas["bettafish_signal"] = bettafish_signal_schema
            
            logger.debug("预定义数据模式注册完成")
            
        except Exception as e:
            logger.error(f"注册预定义数据模式失败: {e}")
            
    def register_schema(self, schema: DataSchema):
        """注册自定义数据模式"""
        try:
            self.schemas[schema.name] = schema
            logger.debug(f"注册数据模式: {schema.name}")
            
        except Exception as e:
            logger.error(f"注册数据模式失败: {e}")
            
    def normalize_data(self, data: Any, target_schema: str) -> Optional[pd.DataFrame]:
        """标准化数据"""
        try:
            if target_schema not in self.schemas:
                logger.error(f"未知的目标数据模式: {target_schema}")
                return None
                
            # 检查缓存
            if hasattr(data, 'to_numpy'):
                cache_key = f"normalize_{hash(data.to_numpy().tobytes())}_{target_schema}"
            else:
                cache_key = f"normalize_{hash(str(data))}_{target_schema}"
            if cache_key in self.cache:
                logger.debug("从缓存获取标准化数据")
                return self.cache[cache_key]
                
            schema = self.schemas[target_schema]
            
            # 根据数据类型处理
            if isinstance(data, pd.DataFrame):
                normalized_df = self._normalize_dataframe(data, schema)
            elif isinstance(data, dict):
                normalized_df = self._normalize_dict(data, schema)
            elif isinstance(data, (list, np.ndarray)):
                normalized_df = self._normalize_array(data, schema)
            else:
                logger.error(f"不支持的数据类型: {type(data)}")
                return None
                
            # 数据质量验证
            if normalized_df is not None:
                quality_report = self.validate_data(normalized_df, schema)
                self.quality_reports[cache_key] = quality_report
                
                # 缓存结果
                if quality_report.is_valid:
                    self.cache[cache_key] = normalized_df
                else:
                    logger.warning(f"数据标准化后验证失败: {quality_report.errors}")
                    
            return normalized_df
            
        except Exception as e:
            logger.error(f"标准化数据失败: {e}")
            return None
            
    def _normalize_dataframe(self, df: pd.DataFrame, schema: DataSchema) -> Optional[pd.DataFrame]:
        """标准化DataFrame数据"""
        try:
            # 检查必需字段
            missing_required = set(schema.required_columns) - set(df.columns)
            if missing_required:
                logger.error(f"DataFrame缺少必需字段: {missing_required}")
                return None
                
            # 选择需要的列
            all_columns = schema.required_columns + schema.optional_columns
            available_columns = [col for col in all_columns if col in df.columns]
            normalized_df = df[available_columns].copy()
            
            # 类型转换
            for col, dtype in schema.data_types.items():
                if col in normalized_df.columns:
                    try:
                        if dtype == "datetime64[ns]":
                            normalized_df[col] = pd.to_datetime(normalized_df[col])
                        else:
                            normalized_df[col] = normalized_df[col].astype(dtype)
                    except Exception as e:
                        logger.warning(f"列 {col} 类型转换失败: {e}")
                        
            # 添加默认时间戳
            if "timestamp" in schema.required_columns and "timestamp" not in normalized_df.columns:
                normalized_df["timestamp"] = pd.date_range(
                    start=datetime.now() - timedelta(days=len(normalized_df)),
                    periods=len(normalized_df),
                    freq='D'
                )
                
            logger.debug(f"DataFrame标准化完成: {len(normalized_df)} 行")
            return normalized_df
            
        except Exception as e:
            logger.error(f"标准化DataFrame失败: {e}")
            return None
            
    def _normalize_dict(self, data: Dict, schema: DataSchema) -> Optional[pd.DataFrame]:
        """标准化字典数据"""
        try:
            if isinstance(data, dict):
                if all(isinstance(v, (int, float)) for v in data.values()):
                    # 简单的键值对
                    return pd.DataFrame([
                        {'x': k, 'y': v} for k, v in data.items()
                    ])
                elif 'data' in data:
                    # 嵌套结构
                    inner_data = data['data']
                    if isinstance(inner_data, list):
                        return pd.DataFrame(inner_data)
                    elif isinstance(inner_data, dict):
                        return pd.DataFrame([inner_data])
                        
            # 默认情况：直接转换为DataFrame
            return pd.DataFrame([data])
            
        except Exception as e:
            logger.error(f"标准化字典数据失败: {e}")
            return None
            
    def _normalize_array(self, data: Union[List, np.ndarray], schema: DataSchema) -> Optional[pd.DataFrame]:
        """标准化数组数据"""
        try:
            if isinstance(data, list):
                data = np.array(data)
                
            if data.ndim == 1:
                # 一维数组：创建时间序列
                return pd.DataFrame({
                    'timestamp': pd.date_range(
                        start=datetime.now() - timedelta(days=len(data)),
                        periods=len(data),
                        freq='D'
                    ),
                    'value': data
                })
            elif data.ndim == 2:
                # 二维数组：转换为DataFrame
                columns = [f'col_{i}' for i in range(data.shape[1])]
                return pd.DataFrame(data, columns=columns)
            else:
                logger.error(f"不支持的数组维度: {data.ndim}")
                return None
                
        except Exception as e:
            logger.error(f"标准化数组数据失败: {e}")
            return None
            
    def validate_data(self, data: pd.DataFrame, schema: DataSchema) -> DataQualityReport:
        """验证数据质量"""
        try:
            errors = []
            warnings = []
            statistics = {}
            
            # 验证规则检查
            validation_errors, validation_warnings = self._validate_field_rules(data, schema)
            errors.extend(validation_errors)
            warnings.extend(validation_warnings)
            
            # 完整性检查
            completeness = self._calculate_completeness(data, schema)
            statistics['completeness'] = completeness
            
            # 一致性检查
            consistency = self._calculate_consistency(data, schema)
            statistics['consistency'] = consistency
            
            # 准确性检查
            accuracy = self._calculate_accuracy(data, schema)
            statistics['accuracy'] = accuracy
            
            # 时效性检查
            timeliness = self._calculate_timeliness(data)
            statistics['timeliness'] = timeliness
            
            # 总体质量分数
            score = (completeness * 0.25 + consistency * 0.25 + 
                    accuracy * 0.25 + timeliness * 0.15 + (1.0 - len(errors) * 0.1) * 0.1)
            
            # 根据验证级别调整检查严格程度
            if self.validation_level == DataValidationLevel.STRICT:
                if completeness < 0.95:
                    errors.append(f"完整性不足: {completeness:.2%}")
                if consistency < 0.90:
                    errors.append(f"一致性不足: {consistency:.2%}")
                    
            elif self.validation_level == DataValidationLevel.MODERATE:
                if completeness < 0.80:
                    errors.append(f"完整性不足: {completeness:.2%}")
                if consistency < 0.75:
                    warnings.append(f"一致性较低: {consistency:.2%}")
                    
            elif self.validation_level == DataValidationLevel.RELAXED:
                if completeness < 0.60:
                    warnings.append(f"完整性较低: {completeness:.2%}")
                    
            # 综合判断
            is_valid = len(errors) == 0
            
            return DataQualityReport(
                is_valid=is_valid,
                score=score,
                errors=errors,
                warnings=warnings,
                statistics=statistics,
                completeness=completeness,
                consistency=consistency,
                accuracy=accuracy,
                timeliness=timeliness
            )
            
        except Exception as e:
            logger.error(f"验证数据质量失败: {e}")
            return DataQualityReport(
                is_valid=False,
                score=0.0,
                errors=[f"验证过程异常: {str(e)}"]
            )
            
    def _calculate_completeness(self, data: pd.DataFrame, schema: DataSchema) -> float:
        """计算数据完整性"""
        try:
            if data.empty:
                return 0.0

            required_cols = [col for col in schema.required_columns if col in data.columns]
            if not required_cols:
                return 0.0

            complete_rows = data[required_cols].notna().all(axis=1).sum()
            return float(complete_rows) / len(data)

        except Exception as e:
            logger.error(f"计算完整性失败: {e}")
            return 0.0
            
    def _calculate_consistency(self, data: pd.DataFrame, schema: DataSchema) -> float:
        """计算数据一致性"""
        try:
            if data.empty:
                return 1.0
                
            consistency_scores = []
            
            for col in schema.required_columns:
                if col in data.columns:
                    # 检查数据类型一致性
                    if col in schema.data_types:
                        expected_type = schema.data_types[col]
                        try:
                            if expected_type == "float64":
                                numeric_count = pd.to_numeric(data[col], errors='coerce').notna().sum()
                            elif expected_type == "datetime64[ns]":
                                date_count = pd.to_datetime(data[col], errors='coerce').notna().sum()
                            else:
                                # 其他类型检查
                                non_null_count = data[col].notna().sum()
                                numeric_count = non_null_count
                                
                            consistency_score = numeric_count / len(data)
                            consistency_scores.append(consistency_score)
                            
                        except Exception:
                            consistency_scores.append(0.0)
                            
            return np.mean(consistency_scores) if consistency_scores else 1.0
            
        except Exception as e:
            logger.error(f"计算一致性失败: {e}")
            return 0.0
            
    def _calculate_accuracy(self, data: pd.DataFrame, schema: DataSchema) -> float:
        """计算数据准确性"""
        try:
            if data.empty:
                return 1.0
                
            accuracy_scores = []
            
            # OHLC数据准确性检查
            if all(col in data.columns for col in ['open', 'high', 'low', 'close']):
                # 高价应该 >= 开盘价、收盘价、最低价
                high_valid = (data['high'] >= data['open']) & \
                           (data['high'] >= data['close']) & \
                           (data['high'] >= data['low'])
                accuracy_scores.append(high_valid.mean())
                
                # 低价应该 <= 开盘价、收盘价、最高价
                low_valid = (data['low'] <= data['open']) & \
                          (data['low'] <= data['close']) & \
                          (data['low'] <= data['high'])
                accuracy_scores.append(low_valid.mean())
                
                # 收盘价应该在开盘价和最高价/最低价之间
                close_valid = (data['close'] >= data['low']) & (data['close'] <= data['high'])
                accuracy_scores.append(close_valid.mean())
                
            # 数值范围检查
            for col in data.select_dtypes(include=[np.number]).columns:
                if not data[col].empty:
                    # 检查无穷大值
                    inf_count = np.isinf(data[col]).sum()
                    if len(data) > 0:
                        inf_score = 1.0 - (inf_count / len(data))
                        accuracy_scores.append(inf_score)
                        
            return np.mean(accuracy_scores) if accuracy_scores else 1.0
            
        except Exception as e:
            logger.error(f"计算准确性失败: {e}")
            return 0.0
            
    def _calculate_timeliness(self, data: pd.DataFrame) -> float:
        """计算数据时效性"""
        try:
            # 检查是否有时间戳列
            time_columns = ['timestamp', 'datetime', 'date', 'time']
            time_col = None
            
            for col in data.columns:
                if col.lower() in [tc.lower() for tc in time_columns]:
                    time_col = col
                    break
                    
            if time_col is None:
                # 没有时间戳，假设数据是当前的
                return 1.0
                
            try:
                if data[time_col].dtype == 'object':
                    # 尝试转换时间戳
                    time_data = pd.to_datetime(data[time_col], errors='coerce')
                else:
                    time_data = data[time_col]
                    
                if time_data.empty or time_data.isna().all():
                    return 0.5  # 时间戳无效
                    
                # 计算数据的新鲜程度
                latest_time = time_data.max()
                current_time = pd.Timestamp.now()
                
                # 时间差（小时）
                time_diff_hours = (current_time - latest_time).total_seconds() / 3600
                
                # 根据时间差计算时效性分数
                if time_diff_hours <= 1:
                    timeliness = 1.0
                elif time_diff_hours <= 24:
                    timeliness = 0.9
                elif time_diff_hours <= 168:  # 一周
                    timeliness = 0.7
                else:
                    timeliness = 0.5
                    
                return timeliness
                
            except Exception:
                return 0.5
                
        except Exception as e:
            logger.error(f"计算时效性失败: {e}")
            return 0.5
            
    def _validate_field_rules(self, data: pd.DataFrame, schema: DataSchema) -> tuple[list[str], list[str]]:
        """验证字段级别的验证规则"""
        errors = []
        warnings = []
        
        try:
            # 如果没有验证规则，直接返回
            if not schema.validation_rules:
                return errors, warnings
                
            for field_name, rules in schema.validation_rules.items():
                if field_name not in data.columns:
                    continue
                    
                field_data = data[field_name]
                
                # 最小/最大值验证
                if 'min' in rules:
                    min_value = rules['min']
                    if field_data.dtype in ['float64', 'int64']:
                        invalid_count = (field_data < min_value).sum()
                        if invalid_count > 0:
                            errors.append(f"字段 {field_name} 有 {invalid_count} 个值小于最小值 {min_value}")
                    else:
                        # 字符串字段的长度检查
                        invalid_count = (field_data.str.len() < min_value).sum()
                        if invalid_count > 0:
                            warnings.append(f"字段 {field_name} 有 {invalid_count} 个值长度小于最小值 {min_value}")
                            
                if 'max' in rules:
                    max_value = rules['max']
                    if field_data.dtype in ['float64', 'int64']:
                        invalid_count = (field_data > max_value).sum()
                        if invalid_count > 0:
                            errors.append(f"字段 {field_name} 有 {invalid_count} 个值大于最大值 {max_value}")
                    else:
                        # 字符串字段的长度检查
                        invalid_count = (field_data.str.len() > max_value).sum()
                        if invalid_count > 0:
                            warnings.append(f"字段 {field_name} 有 {invalid_count} 个值长度大于最大值 {max_value}")
                            
                # 选择值验证
                if 'choices' in rules:
                    valid_choices = set(rules['choices'])
                    # 移除空值进行验证
                    non_null_data = field_data.dropna()
                    if len(non_null_data) > 0:
                        invalid_choices = set(non_null_data.astype(str)) - valid_choices
                        if invalid_choices:
                            errors.append(f"字段 {field_name} 包含无效值: {list(invalid_choices)[:5]}")
                            
                # 范围验证（特殊格式）
                if 'range' in rules:
                    range_config = rules['range']
                    if isinstance(range_config, dict) and 'min' in range_config and 'max' in range_config:
                        min_val, max_val = range_config['min'], range_config['max']
                        if field_data.dtype in ['float64', 'int64']:
                            invalid_count = ((field_data < min_val) | (field_data > max_val)).sum()
                            if invalid_count > 0:
                                errors.append(f"字段 {field_name} 有 {invalid_count} 个值超出范围 [{min_val}, {max_val}]")
                                
                # 正则表达式验证
                if 'pattern' in rules:
                    import re
                    pattern = rules['pattern']
                    try:
                        # 编译正则表达式
                        regex = re.compile(pattern)
                        # 检查非空值
                        non_null_data = field_data.dropna().astype(str)
                        if len(non_null_data) > 0:
                            invalid_count = (~non_null_data.str.match(regex)).sum()
                            if invalid_count > 0:
                                errors.append(f"字段 {field_name} 有 {invalid_count} 个值不符合模式 {pattern}")
                    except re.error as e:
                        errors.append(f"字段 {field_name} 正则表达式模式错误: {e}")
                        
                # 自定义验证函数
                if 'custom_validator' in rules:
                    try:
                        validator_func = rules['custom_validator']
                        if callable(validator_func):
                            validation_result = validator_func(field_data)
                            if not validation_result:
                                errors.append(f"字段 {field_name} 自定义验证失败")
                    except Exception as e:
                        errors.append(f"字段 {field_name} 自定义验证执行失败: {e}")
                        
        except Exception as e:
            logger.error(f"验证字段规则失败: {e}")
            errors.append(f"验证过程异常: {str(e)}")
            
        return errors, warnings
            
    def get_data_statistics(self, data: pd.DataFrame) -> Dict[str, Any]:
        """获取数据统计信息"""
        try:
            stats = {
                'shape': data.shape,
                'columns': list(data.columns),
                'dtypes': data.dtypes.to_dict(),
                'memory_usage': data.memory_usage(deep=True).sum(),
                'null_counts': data.isnull().sum().to_dict()
            }
            
            # 数值列统计
            numeric_stats = {}
            for col in data.select_dtypes(include=[np.number]).columns:
                numeric_stats[col] = {
                    'mean': data[col].mean(),
                    'std': data[col].std(),
                    'min': data[col].min(),
                    'max': data[col].max(),
                    'median': data[col].median()
                }
            stats['numeric_stats'] = numeric_stats
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据统计失败: {e}")
            return {}
            
    def clean_data(self, data: pd.DataFrame, strategy: str = 'drop') -> pd.DataFrame:
        """数据清洗"""
        try:
            cleaned_data = data.copy()
            
            if strategy == 'drop':
                # 删除包含缺失值的行
                cleaned_data = cleaned_data.dropna()
            elif strategy == 'fill_forward':
                # 前向填充
                cleaned_data = cleaned_data.fillna(method='ffill')
            elif strategy == 'fill_mean':
                # 均值填充（数值列）
                numeric_cols = cleaned_data.select_dtypes(include=[np.number]).columns
                for col in numeric_cols:
                    cleaned_data[col].fillna(cleaned_data[col].mean(), inplace=True)
            elif strategy == 'interpolate':
                # 插值填充
                cleaned_data = cleaned_data.interpolate()
            else:
                logger.warning(f"未知的数据清洗策略: {strategy}")
                
            logger.debug(f"数据清洗完成: {len(cleaned_data)} 行 (原始: {len(data)} 行)")
            return cleaned_data
            
        except Exception as e:
            logger.error(f"数据清洗失败: {e}")
            return data
            
    def convert_chart_data(self, data: pd.DataFrame, chart_type: ChartType) -> Dict[str, Any]:
        """转换为图表数据格式"""
        try:
            chart_data = {}
            
            if chart_type == ChartType.LINE_CHART:
                chart_data = self._convert_line_data(data)
            elif chart_type == ChartType.CANDLESTICK:
                chart_data = self._convert_candlestick_data(data)
            elif chart_type == ChartType.BAR:
                chart_data = self._convert_bar_data(data)
            elif chart_type == ChartType.SCATTER:
                chart_data = self._convert_scatter_data(data)
            elif chart_type == ChartType.HEATMAP:
                chart_data = self._convert_heatmap_data(data)
            else:
                logger.warning(f"不支持的图表类型转换: {chart_type}")
                chart_data = {'x': [], 'y': []}
                
            return chart_data
            
        except Exception as e:
            logger.error(f"转换图表数据失败: {e}")
            return {'x': [], 'y': []}
            
    def _convert_line_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """转换为线图数据"""
        try:
            if 'timestamp' in data.columns and 'value' in data.columns:
                return {
                    'x': data['timestamp'].values,
                    'y': data['value'].values
                }
            elif len(data.columns) >= 2:
                return {
                    'x': data.iloc[:, 0].values,
                    'y': data.iloc[:, 1].values
                }
            else:
                return {
                    'x': list(range(len(data))),
                    'y': data.iloc[:, 0].values if len(data.columns) > 0 else []
                }
                
        except Exception as e:
            logger.error(f"转换线图数据失败: {e}")
            return {'x': [], 'y': []}
            
    def _convert_candlestick_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """转换为K线图数据"""
        try:
            required_cols = ['open', 'high', 'low', 'close']
            if all(col in data.columns for col in required_cols):
                return {
                    'timestamp': data.index.values if data.index.name else list(range(len(data))),
                    'open': data['open'].values,
                    'high': data['high'].values,
                    'low': data['low'].values,
                    'close': data['close'].values,
                    'volume': data['volume'].values if 'volume' in data.columns else [0] * len(data)
                }
            else:
                logger.warning("K线图数据缺少必要字段")
                return {'timestamp': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': []}
                
        except Exception as e:
            logger.error(f"转换K线图数据失败: {e}")
            return {'timestamp': [], 'open': [], 'high': [], 'low': [], 'close': [], 'volume': []}
            
    def _convert_bar_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """转换为柱状图数据"""
        try:
            if len(data.columns) >= 2:
                return {
                    'x': data.iloc[:, 0].values,
                    'y': data.iloc[:, 1].values
                }
            else:
                return {
                    'x': list(range(len(data))),
                    'y': data.iloc[:, 0].values if len(data.columns) > 0 else []
                }
                
        except Exception as e:
            logger.error(f"转换柱状图数据失败: {e}")
            return {'x': [], 'y': []}
            
    def _convert_scatter_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """转换为散点图数据"""
        try:
            if len(data.columns) >= 2:
                return {
                    'x': data.iloc[:, 0].values,
                    'y': data.iloc[:, 1].values
                }
            else:
                return {'x': [], 'y': []}
                
        except Exception as e:
            logger.error(f"转换散点图数据失败: {e}")
            return {'x': [], 'y': []}
            
    def _convert_heatmap_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """转换为热力图数据"""
        try:
            numeric_data = data.select_dtypes(include=[np.number])
            if not numeric_data.empty:
                return {
                    'matrix': numeric_data.values,
                    'x_labels': list(numeric_data.columns),
                    'y_labels': list(numeric_data.index)
                }
            else:
                return {'matrix': [], 'x_labels': [], 'y_labels': []}
                
        except Exception as e:
            logger.error(f"转换热力图数据失败: {e}")
            return {'matrix': [], 'x_labels': [], 'y_labels': []}
            
    def get_schema_list(self) -> List[str]:
        """获取已注册的模式列表"""
        return list(self.schemas.keys())
        
    def get_quality_report(self, data_key: str) -> Optional[DataQualityReport]:
        """获取数据质量报告"""
        return self.quality_reports.get(data_key)
        
    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()
        self.quality_reports.clear()
        logger.info("数据适配器缓存已清空")


# 导出的公共接口
__all__ = [
    'DataAdapter',
    'DataSchema',
    'DataQualityReport',
    'DataFormat',
    'DataValidationLevel'
]