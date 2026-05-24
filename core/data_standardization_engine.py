"""
数据标准化引擎

负责将来自不同数据源的原始数据转换为标准格式，并存储到对应的资产数据库中。
实现多数据源的标准化存储机制，确保数据格式一致性和质量。

作者: FactorWeave-Quant团队
版本: 1.0
"""

import threading
import json
from typing import Dict, Any, Optional, List, Union, Callable, Tuple
from datetime import datetime, date
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from abc import ABC, abstractmethod

from loguru import logger
from .plugin_types import AssetType, DataType
from .asset_database_manager import get_asset_database_manager
from .data_router import DataSource
from .data_schemas import get_standard_schemas, get_schema_by_type, StandardDataSchema, FieldMapping

logger = logger.bind(module=__name__)


class DataFormat(Enum):
    """数据格式枚举"""
    PANDAS_DATAFRAME = "pandas_dataframe"
    JSON = "json"
    CSV = "csv"
    DICT = "dict"
    LIST = "list"
    NUMPY_ARRAY = "numpy_array"
    CUSTOM = "custom"


@dataclass
class FieldMapping:
    """字段映射配置"""
    source_field: str
    target_field: str
    data_type: str = "auto"  # auto, str, int, float, datetime, bool
    transform_func: Optional[Callable] = None
    default_value: Any = None
    is_required: bool = True
    validation_func: Optional[Callable] = None

    def apply_transform(self, value: Any) -> Any:
        """应用字段转换"""
        try:
            # 处理空值
            if pd.isna(value) or value is None:
                if self.default_value is not None:
                    return self.default_value
                elif self.is_required:
                    raise ValueError(f"Required field {self.source_field} is null")
                else:
                    return None

            # 应用自定义转换函数
            if self.transform_func:
                value = self.transform_func(value)

            # 数据类型转换
            if self.data_type == "str":
                value = str(value)
            elif self.data_type == "int":
                value = int(float(value))  # 先转float再转int，处理"10.0"这种情况
            elif self.data_type == "float":
                value = float(value)
            elif self.data_type == "datetime":
                if isinstance(value, str):
                    value = pd.to_datetime(value)
                elif isinstance(value, (int, float)):
                    value = pd.to_datetime(value, unit='s')
            elif self.data_type == "bool":
                value = bool(value)

            # 应用验证函数
            if self.validation_func and not self.validation_func(value):
                raise ValueError(f"Validation failed for field {self.source_field}")

            return value

        except Exception as e:
            logger.error(f"字段转换失败: {self.source_field} -> {self.target_field}, {e}")
            if self.is_required:
                raise
            return self.default_value


@dataclass
class StandardDataSchema:
    """标准数据模式定义"""
    name: str
    description: str
    fields: List[FieldMapping]
    primary_key: List[str]
    indexes: List[str] = field(default_factory=list)
    constraints: Dict[str, str] = field(default_factory=dict)

    def get_field_mapping(self, source_field: str) -> Optional[FieldMapping]:
        """获取字段映射"""
        for field in self.fields:
            if field.source_field == source_field:
                return field
        return None

    def get_target_fields(self) -> List[str]:
        """获取目标字段列表"""
        return [field.target_field for field in self.fields]


@dataclass
class StandardizationRule:
    """标准化规则"""
    source: DataSource
    data_type: DataType
    asset_type: AssetType
    schema: StandardDataSchema
    preprocessing_func: Optional[Callable] = None
    postprocessing_func: Optional[Callable] = None
    quality_checks: List[Callable] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def apply_preprocessing(self, raw_data: Any) -> Any:
        """应用预处理"""
        if self.preprocessing_func:
            return self.preprocessing_func(raw_data)
        return raw_data

    def apply_postprocessing(self, standardized_data: pd.DataFrame) -> pd.DataFrame:
        """应用后处理"""
        if self.postprocessing_func:
            return self.postprocessing_func(standardized_data)
        return standardized_data

    def check_quality(self, data: pd.DataFrame) -> List[str]:
        """质量检查"""
        issues = []
        for check_func in self.quality_checks:
            try:
                result = check_func(data)
                if isinstance(result, str):
                    issues.append(result)
                elif isinstance(result, list):
                    issues.extend(result)
                elif not result:  # False或空值表示检查不通过
                    issues.append(f"质量检查失败: {check_func.__name__}")
            except Exception as e:
                issues.append(f"质量检查异常: {check_func.__name__} - {e}")

        return issues


@dataclass
class StandardizationResult:
    """标准化结果"""
    success: bool
    data: Optional[pd.DataFrame] = None
    original_count: int = 0
    standardized_count: int = 0
    quality_score: float = 0.0
    quality_issues: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'original_count': self.original_count,
            'standardized_count': self.standardized_count,
            'quality_score': self.quality_score,
            'quality_issues': self.quality_issues,
            'metadata': self.metadata,
            'processing_time_ms': self.processing_time_ms
        }


class DataStandardizationEngine:
    """
    数据标准化引擎

    核心功能：
    1. 多数据源格式识别和解析
    2. 字段映射和数据类型转换
    3. 数据质量检查和验证
    4. 标准化数据存储
    5. 处理统计和监控
    """

    def __init__(self):
        """初始化数据标准化引擎"""
        # 核心组件
        self.asset_db_manager = get_asset_database_manager()

        # 获取全局标准数据模式
        self.standard_schemas = get_standard_schemas()

        # 标准化规则注册表
        self._standardization_rules: Dict[str, StandardizationRule] = {}

        # 处理统计
        self._processing_stats: Dict[str, Dict[str, Any]] = {}

        # 数据质量统计
        self._quality_stats: Dict[str, Dict[str, Any]] = {}

        # 线程锁
        self._engine_lock = threading.RLock()

        # 初始化内置规则
        self._initialize_builtin_rules()

        logger.info("DataStandardizationEngine 初始化完成，加载了 {} 个标准数据模式".format(
            len(self.standard_schemas.list_schemas())
        ))

    def _initialize_builtin_rules(self):
        """初始化内置标准化规则"""
        # 获取标准K线数据模式
        kline_schema = self.standard_schemas.get_schema("standard_kline")
        quote_schema = self.standard_schemas.get_schema("standard_quote")
        stock_info_schema = self.standard_schemas.get_schema("standard_stock_info")

        if not kline_schema:
            logger.error("未找到standard_kline数据模式")
            return

        # 通达信K线数据规则
        self.register_standardization_rule(
            source=DataSource.TONGDAXIN,
            data_type=DataType.HISTORICAL_KLINE,
            asset_type=AssetType.STOCK_A,
            schema=kline_schema,
            preprocessing_func=self._preprocess_tongdaxin_kline,
            quality_checks=[self._check_kline_price_validity, self._check_kline_completeness]
        )

        # 东方财富K线数据规则
        self.register_standardization_rule(
            source=DataSource.EASTMONEY,
            data_type=DataType.HISTORICAL_KLINE,
            asset_type=AssetType.STOCK_A,
            schema=kline_schema,
            preprocessing_func=self._preprocess_eastmoney_kline,
            quality_checks=[self._check_kline_price_validity, self._check_kline_completeness]
        )

        # 币安K线数据规则
        self.register_standardization_rule(
            source=DataSource.BINANCE,
            data_type=DataType.HISTORICAL_KLINE,
            asset_type=AssetType.CRYPTO,
            schema=kline_schema,
            preprocessing_func=self._preprocess_binance_kline,
            quality_checks=[self._check_kline_price_validity, self._check_kline_completeness]
        )

        # 实时行情规则
        if quote_schema:
            self.register_standardization_rule(
                source=DataSource.EASTMONEY,
                data_type=DataType.REAL_TIME_QUOTE,
                asset_type=AssetType.STOCK_A,
                schema=quote_schema,
                preprocessing_func=self._preprocess_eastmoney_quote,
                quality_checks=[self._check_quote_validity]
            )

        # 股票基本信息规则
        if stock_info_schema:
            self.register_standardization_rule(
                source=DataSource.EASTMONEY,
                data_type=DataType.FUNDAMENTAL,
                asset_type=AssetType.STOCK_A,
                schema=stock_info_schema,
                preprocessing_func=self._preprocess_stock_info,
                quality_checks=[self._check_stock_info_validity]
            )

        logger.info(f"初始化了 {len(self._standardization_rules)} 个内置标准化规则")

    def _preprocess_tongdaxin_kline(self, raw_data: Any) -> pd.DataFrame:
        """预处理通达信K线数据"""
        if isinstance(raw_data, pd.DataFrame):
            df = raw_data.copy()

            # 通达信字段映射
            column_mapping = {
                'Datetime': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume',
                'Amount': 'amount'
            }

            # 重命名列
            df = df.rename(columns=column_mapping)

            # 添加数据源信息
            df['data_source'] = 'tongdaxin'
            df['frequency'] = '1d'  # 默认日线

            return df

        return pd.DataFrame()

    def _preprocess_eastmoney_kline(self, raw_data: Any) -> pd.DataFrame:
        """预处理东方财富K线数据"""
        if isinstance(raw_data, pd.DataFrame):
            df = raw_data.copy()

            # 东方财富字段映射
            column_mapping = {
                'f51': 'timestamp',  # 日期
                'f52': 'open',       # 开盘价
                'f53': 'close',      # 收盘价
                'f54': 'high',       # 最高价
                'f55': 'low',        # 最低价
                'f56': 'volume',     # 成交量
                'f57': 'amount',     # 成交额
            }

            # 重命名列
            df = df.rename(columns=column_mapping)

            # 添加数据源信息
            df['data_source'] = 'eastmoney'
            df['frequency'] = '1d'

            return df

        return pd.DataFrame()

    def _preprocess_binance_kline(self, raw_data: Any) -> pd.DataFrame:
        """预处理币安K线数据"""
        if isinstance(raw_data, list):
            # 币安返回的是嵌套列表格式
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume',
                       'close_time', 'quote_volume', 'count', 'taker_buy_volume',
                       'taker_buy_quote_volume', 'ignore']

            df = pd.DataFrame(raw_data, columns=columns)

            # 只保留需要的列
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]

            # 时间戳转换（币安返回毫秒时间戳）
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            # 添加数据源信息
            df['data_source'] = 'binance'
            df['frequency'] = '1d'
            df['amount'] = 0.0  # 币安不直接提供成交额

            return df
        elif isinstance(raw_data, pd.DataFrame):
            df = raw_data.copy()
            df['data_source'] = 'binance'
            return df

        return pd.DataFrame()

    def _preprocess_eastmoney_quote(self, raw_data: Any) -> pd.DataFrame:
        """预处理东方财富实时行情数据"""
        if isinstance(raw_data, pd.DataFrame):
            df = raw_data.copy()

            # 东方财富实时行情字段映射
            field_map = {
                'f43': 'current_price',    # 最新价
                'f44': 'high',             # 最高价
                'f45': 'low',              # 最低价
                'f46': 'open',             # 开盘价
                'f60': 'close',            # 昨收价
                'f47': 'volume',           # 成交量
                'f48': 'amount',           # 成交额
                'f169': 'change_percent',  # 涨跌幅
                'f170': 'change',          # 涨跌额
                'f19': 'bid_price',        # 买一价
                'f20': 'ask_price',        # 卖一价
                'f21': 'bid_volume',       # 买一量
                'f22': 'ask_volume',       # 卖一量
            }

            # 重命名字段
            for old_col, new_col in field_map.items():
                if old_col in df.columns:
                    df[new_col] = df[old_col]

            # 添加时间戳
            df['timestamp'] = datetime.now()

            return df

        return pd.DataFrame()

    def _preprocess_stock_info(self, raw_data: Any) -> pd.DataFrame:
        """预处理股票基本信息数据"""
        if isinstance(raw_data, pd.DataFrame):
            df = raw_data.copy()

            # 字段映射和数据清理
            if 'total_mv' in df.columns:
                df['market_cap'] = df['total_mv']  # 总市值
            if 'circulate_mv' in df.columns:
                df['float_market_cap'] = df['circulate_mv']  # 流通市值
            if 'total_share' in df.columns:
                df['total_shares'] = df['total_share']  # 总股本
            if 'float_share' in df.columns:
                df['float_shares'] = df['float_share']  # 流通股本

            # 添加更新时间
            df['updated_time'] = datetime.now()

            return df

        return pd.DataFrame()

    def _check_quote_validity(self, data: pd.DataFrame) -> List[str]:
        """检查实时行情有效性"""
        issues = []

        if data.empty:
            return ["数据为空"]

        # 检查必要字段
        required_fields = ['current_price', 'timestamp']
        for field in required_fields:
            if field not in data.columns:
                issues.append(f"缺少必要字段: {field}")
            elif data[field].isnull().sum() > 0:
                issues.append(f"字段 {field} 存在空值")

        # 检查价格合理性
        if 'current_price' in data.columns:
            negative_prices = (data['current_price'] <= 0).sum()
            if negative_prices > 0:
                issues.append(f"发现 {negative_prices} 条记录的价格不合理(<=0)")

        return issues

    def _check_stock_info_validity(self, data: pd.DataFrame) -> List[str]:
        """检查股票基本信息有效性"""
        issues = []

        if data.empty:
            return ["数据为空"]

        # 检查必要字段
        required_fields = ['code', 'name']
        for field in required_fields:
            if field not in data.columns:
                issues.append(f"缺少必要字段: {field}")
            elif data[field].isnull().sum() > 0:
                issues.append(f"字段 {field} 存在空值")

        # 检查股票代码格式
        if 'code' in data.columns:
            invalid_codes = data[~data['code'].str.match(r'^\d{6}$|^[A-Z]{1,5}$', na=False)]
            if len(invalid_codes) > 0:
                issues.append(f"发现 {len(invalid_codes)} 条记录的股票代码格式不正确")

        return issues

    def _check_kline_price_validity(self, data: pd.DataFrame) -> List[str]:
        """检查K线价格有效性"""
        issues = []

        if data.empty:
            return ["数据为空"]

        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            issues.append(f"缺少必要的价格列: {missing_columns}")
            return issues

        # 检查价格逻辑关系: high >= max(open, close), low <= min(open, close)
        invalid_high = (data['high'] < data[['open', 'close']].max(axis=1)).sum()
        invalid_low = (data['low'] > data[['open', 'close']].min(axis=1)).sum()

        if invalid_high > 0:
            issues.append(f"发现 {invalid_high} 条记录的最高价不合理")

        if invalid_low > 0:
            issues.append(f"发现 {invalid_low} 条记录的最低价不合理")

        # 检查负价格
        negative_prices = (data[required_columns] < 0).any(axis=1).sum()
        if negative_prices > 0:
            issues.append(f"发现 {negative_prices} 条记录存在负价格")

        # 检查异常波动（单日涨跌超过30%）
        if len(data) > 1:
            price_change = (data['close'] / data['close'].shift(1) - 1).abs()
            extreme_changes = (price_change > 0.3).sum()
            if extreme_changes > 0:
                issues.append(f"发现 {extreme_changes} 条记录存在异常价格波动（>30%）")

        return issues

    def _check_kline_completeness(self, data: pd.DataFrame) -> List[str]:
        """检查K线数据完整性"""
        issues = []

        if data.empty:
            return ["数据为空"]

        # 检查必要字段的缺失情况
        required_fields = ['symbol', 'timestamp', 'open', 'high', 'low', 'close']
        for field in required_fields:
            if field in data.columns:
                null_count = data[field].isnull().sum()
                if null_count > 0:
                    issues.append(f"字段 {field} 有 {null_count} 个缺失值")
            else:
                issues.append(f"缺少必要字段: {field}")

        # 检查时间序列连续性（日线数据）
        if 'timestamp' in data.columns and len(data) > 1:
            timestamps = pd.to_datetime(data['timestamp']).sort_values()
            gaps = (timestamps.diff() > pd.Timedelta(days=7)).sum()  # 超过7天的间隔认为是缺失
            if gaps > 0:
                issues.append(f"时间序列存在 {gaps} 个较大间隔（>7天）")

        return issues

    def register_standardization_rule(self, source: DataSource, data_type: DataType,
                                      asset_type: AssetType, schema: StandardDataSchema,
                                      preprocessing_func: Optional[Callable] = None,
                                      postprocessing_func: Optional[Callable] = None,
                                      quality_checks: Optional[List[Callable]] = None):
        """注册标准化规则"""
        rule_key = f"{source.value}_{data_type.value}_{asset_type.value}"

        rule = StandardizationRule(
            source=source,
            data_type=data_type,
            asset_type=asset_type,
            schema=schema,
            preprocessing_func=preprocessing_func,
            postprocessing_func=postprocessing_func,
            quality_checks=quality_checks or []
        )

        with self._engine_lock:
            self._standardization_rules[rule_key] = rule

        logger.info(f"注册标准化规则: {rule_key}")

    def standardize_data(self, raw_data: Any, source: DataSource, data_type: DataType,
                         asset_type: AssetType, symbol: str = "") -> StandardizationResult:
        """
        标准化数据

        Args:
            raw_data: 原始数据
            source: 数据源
            data_type: 数据类型
            asset_type: 资产类型
            symbol: 交易符号

        Returns:
            标准化结果
        """
        start_time = datetime.now()

        try:
            # 查找标准化规则
            rule_key = f"{source.value}_{data_type.value}_{asset_type.value}"

            with self._engine_lock:
                rule = self._standardization_rules.get(rule_key)

            if not rule:
                logger.warning(f"未找到标准化规则: {rule_key}")
                return StandardizationResult(
                    success=False,
                    metadata={'error': f'未找到标准化规则: {rule_key}'}
                )

            # 记录原始数据信息
            original_count = len(raw_data) if hasattr(raw_data, '__len__') else 1

            # 预处理
            preprocessed_data = rule.apply_preprocessing(raw_data)

            # 数据格式标准化
            standardized_df = self._apply_schema_mapping(preprocessed_data, rule.schema, symbol)

            if standardized_df.empty:
                return StandardizationResult(
                    success=False,
                    original_count=original_count,
                    metadata={'error': '数据标准化后为空'}
                )

            # 后处理
            final_df = rule.apply_postprocessing(standardized_df)

            # 质量检查
            quality_issues = rule.check_quality(final_df)
            quality_score = max(0.0, 1.0 - len(quality_issues) * 0.1)

            # 计算处理时间
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # 更新统计
            self._update_processing_stats(rule_key, True, processing_time, quality_score)

            return StandardizationResult(
                success=True,
                data=final_df,
                original_count=original_count,
                standardized_count=len(final_df),
                quality_score=quality_score,
                quality_issues=quality_issues,
                processing_time_ms=processing_time,
                metadata={
                    'rule_key': rule_key,
                    'source': source.value,
                    'data_type': data_type.value,
                    'asset_type': asset_type.value
                }
            )

        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"数据标准化失败: {rule_key}, {e}")

            # 更新失败统计
            if 'rule_key' in locals():
                self._update_processing_stats(rule_key, False, processing_time, 0.0)

            return StandardizationResult(
                success=False,
                original_count=original_count if 'original_count' in locals() else 0,
                processing_time_ms=processing_time,
                metadata={'error': str(e)}
            )

    def _apply_schema_mapping(self, data: Any, schema: StandardDataSchema, symbol: str) -> pd.DataFrame:
        """应用模式映射"""
        try:
            # 转换为DataFrame
            if isinstance(data, pd.DataFrame):
                df = data.copy()
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                raise ValueError(f"不支持的数据类型: {type(data)}")

            if df.empty:
                return pd.DataFrame()

            # 应用字段映射
            result_data = {}

            for field_mapping in schema.fields:
                try:
                    if field_mapping.source_field in df.columns:
                        # 应用字段转换
                        transformed_values = []
                        for value in df[field_mapping.source_field]:
                            transformed_value = field_mapping.apply_transform(value)
                            transformed_values.append(transformed_value)

                        result_data[field_mapping.target_field] = transformed_values

                    elif field_mapping.source_field == 'symbol' and symbol:
                        # 使用提供的symbol
                        result_data[field_mapping.target_field] = [symbol] * len(df)

                    elif field_mapping.default_value is not None:
                        # 使用默认值
                        result_data[field_mapping.target_field] = [field_mapping.default_value] * len(df)

                    elif field_mapping.is_required:
                        raise ValueError(f"必要字段 {field_mapping.source_field} 缺失且无默认值")

                except Exception as e:
                    logger.error(f"字段映射失败: {field_mapping.source_field} -> {field_mapping.target_field}, {e}")
                    if field_mapping.is_required:
                        raise

            # 创建结果DataFrame
            result_df = pd.DataFrame(result_data)

            # 应用数据类型转换
            for field_mapping in schema.fields:
                if field_mapping.target_field in result_df.columns:
                    if field_mapping.data_type == "datetime":
                        result_df[field_mapping.target_field] = pd.to_datetime(result_df[field_mapping.target_field])
                    elif field_mapping.data_type == "int":
                        result_df[field_mapping.target_field] = pd.to_numeric(result_df[field_mapping.target_field], errors='coerce').astype('Int64')
                    elif field_mapping.data_type == "float":
                        result_df[field_mapping.target_field] = pd.to_numeric(result_df[field_mapping.target_field], errors='coerce')

            return result_df

        except Exception as e:
            logger.error(f"模式映射失败: {e}")
            return pd.DataFrame()

    def standardize_and_store(self, raw_data: Any, source: DataSource, data_type: DataType,
                              asset_type: AssetType, symbol: str) -> StandardizationResult:
        """标准化数据并存储到数据库"""
        try:
            # 标准化数据
            result = self.standardize_data(raw_data, source, data_type, asset_type, symbol)

            if not result.success or result.data is None or result.data.empty:
                return result

            # 存储到数据库
            storage_success = self._store_standardized_data(result.data, asset_type, data_type, source)

            if storage_success:
                result.metadata['stored'] = True
                logger.info(f"数据标准化并存储成功: {symbol}, {len(result.data)} 条记录")
            else:
                result.metadata['stored'] = False
                result.metadata['storage_error'] = "存储失败"
                logger.error(f"数据存储失败: {symbol}")

            return result

        except Exception as e:
            logger.error(f"标准化和存储失败: {symbol}, {e}")
            return StandardizationResult(
                success=False,
                metadata={'error': str(e)}
            )

    def _store_standardized_data(self, data: pd.DataFrame, asset_type: AssetType,
                                 data_type: DataType, source: DataSource) -> bool:
        """存储标准化数据"""
        try:
            with self.asset_db_manager.get_connection(asset_type) as conn:
                if data_type == DataType.HISTORICAL_KLINE:
                    # 存储K线数据
                    required_cols = ['symbol', 'data_source', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'amount', 'frequency']
                    records = [
                        (row.symbol, row.data_source, row.timestamp,
                         row.open, row.high, row.low, row.close,
                         row.volume, row.amount, row.frequency)
                        for row in data[required_cols].itertuples(index=False)
                    ]
                    conn.executemany("""
                        INSERT OR REPLACE INTO historical_kline_data 
                        (symbol, data_source, timestamp, open, high, low, close, volume, amount, frequency)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, records)

                    # 记录数据源记录
                    record_id = f"{data.iloc[0]['symbol']}_{source.value}_{datetime.now().strftime('%Y%m%d')}"
                    conn.execute("""
                        INSERT OR REPLACE INTO data_source_records 
                        (record_id, symbol, data_source, data_type, start_date, end_date, record_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, [
                        record_id,
                        data.iloc[0]['symbol'],
                        source.value,
                        data_type.value,
                        data['timestamp'].min().date(),
                        data['timestamp'].max().date(),
                        len(data)
                    ])

                return True

        except Exception as e:
            logger.error(f"存储标准化数据失败: {e}")
            return False

    def _update_processing_stats(self, rule_key: str, success: bool,
                                 processing_time_ms: float, quality_score: float):
        """更新处理统计"""
        with self._engine_lock:
            if rule_key not in self._processing_stats:
                self._processing_stats[rule_key] = {
                    'total_requests': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'avg_processing_time_ms': 0.0,
                    'avg_quality_score': 0.0,
                    'last_processed': None
                }

            stats = self._processing_stats[rule_key]
            stats['total_requests'] += 1

            if success:
                stats['successful_requests'] += 1

                # 更新平均处理时间（指数移动平均）
                alpha = 0.1
                stats['avg_processing_time_ms'] = (
                    alpha * processing_time_ms +
                    (1 - alpha) * stats['avg_processing_time_ms']
                )

                # 更新平均质量分数
                stats['avg_quality_score'] = (
                    alpha * quality_score +
                    (1 - alpha) * stats['avg_quality_score']
                )
            else:
                stats['failed_requests'] += 1

            stats['last_processed'] = datetime.now().isoformat()

    def get_processing_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        with self._engine_lock:
            return {
                'rules_count': len(self._standardization_rules),
                'schemas_count': len(self._builtin_schemas),
                'processing_stats': dict(self._processing_stats),
                'success_rate': self._calculate_overall_success_rate()
            }

    def _calculate_overall_success_rate(self) -> float:
        """计算总体成功率"""
        total_requests = 0
        successful_requests = 0

        for stats in self._processing_stats.values():
            total_requests += stats['total_requests']
            successful_requests += stats['successful_requests']

        return successful_requests / total_requests if total_requests > 0 else 0.0

    def get_supported_combinations(self) -> List[Dict[str, str]]:
        """获取支持的数据源、数据类型、资产类型组合"""
        with self._engine_lock:
            combinations = []
            for rule_key, rule in self._standardization_rules.items():
                combinations.append({
                    'source': rule.source.value,
                    'data_type': rule.data_type.value,
                    'asset_type': rule.asset_type.value,
                    'schema': rule.schema.name
                })

            return combinations


# 全局实例
_standardization_engine: Optional[DataStandardizationEngine] = None
_engine_lock = threading.Lock()


def get_data_standardization_engine() -> DataStandardizationEngine:
    """获取全局数据标准化引擎实例"""
    global _standardization_engine

    with _engine_lock:
        if _standardization_engine is None:
            _standardization_engine = DataStandardizationEngine()

        return _standardization_engine


def initialize_data_standardization_engine() -> DataStandardizationEngine:
    """初始化数据标准化引擎"""
    global _standardization_engine

    with _engine_lock:
        _standardization_engine = DataStandardizationEngine()
        logger.info("DataStandardizationEngine 已初始化")

        return _standardization_engine
