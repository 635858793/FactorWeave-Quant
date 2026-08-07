from loguru import logger
"""
智能字段映射引擎

提供智能字段映射功能，包括：
- 精确匹配和模糊匹配
- 基于数据内容的字段类型推断
- 映射结果验证
- 自定义映射规则支持
- 高性能处理大数据集

作者: FactorWeave-Quant团队
版本: 1.0
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import difflib
from datetime import datetime, date
from decimal import Decimal

from ..plugin_types import DataType



class FieldType(Enum):
    """字段类型枚举"""
    NUMERIC = "numeric"          # 数值类型
    PERCENTAGE = "percentage"    # 百分比类型
    CURRENCY = "currency"        # 货币类型
    DATE = "date"               # 日期类型
    DATETIME = "datetime"       # 日期时间类型
    STRING = "string"           # 字符串类型
    BOOLEAN = "boolean"         # 布尔类型
    RATIO = "ratio"             # 比率类型
    VOLUME = "volume"           # 成交量类型
    PRICE = "price"             # 价格类型


@dataclass
class FieldMappingRule:
    """字段映射规则"""
    source_patterns: List[str]           # 源字段匹配模式
    target_field: str                    # 目标字段名
    field_type: FieldType               # 字段类型
    priority: int = 0                   # 优先级（数值越大优先级越高）
    validation_rules: List[str] = field(default_factory=list)  # 验证规则
    transformation_func: Optional[str] = None  # 转换函数名


@dataclass
class MappingResult:
    """映射结果"""
    source_field: str
    target_field: str
    confidence: float                   # 匹配置信度 (0-1)
    match_type: str                     # 匹配类型: exact, fuzzy, inferred
    field_type: FieldType
    validation_passed: bool = True
    error_message: Optional[str] = None


class FuzzyMatcher:
    """模糊匹配器"""

    def __init__(self, similarity_threshold: float = 0.8):
        self.similarity_threshold = similarity_threshold

    def find_best_match(self, target: str, candidates: List[str]) -> Optional[Tuple[str, float]]:
        """
        找到最佳匹配

        Args:
            target: 目标字符串
            candidates: 候选字符串列表

        Returns:
            最佳匹配结果 (匹配字符串, 相似度)
        """
        if not candidates:
            return None

        # 使用difflib进行序列匹配
        matches = difflib.get_close_matches(
            target, candidates, n=1, cutoff=0.6  # 降低阈值以提高匹配率
        )

        if matches:
            best_match = matches[0]
            similarity = difflib.SequenceMatcher(None, target, best_match).ratio()
            return best_match, similarity

        # 如果没有找到匹配，尝试部分匹配
        best_score = 0.0
        best_candidate = None

        for candidate in candidates:
            # 计算Jaccard相似度
            target_set = set(target.lower().split('_'))
            candidate_set = set(candidate.lower().split('_'))

            if target_set and candidate_set:
                intersection = len(target_set.intersection(candidate_set))
                union = len(target_set.union(candidate_set))
                jaccard_score = intersection / union

                if jaccard_score > best_score and jaccard_score >= 0.3:  # 降低阈值
                    best_score = jaccard_score
                    best_candidate = candidate

            # 检查子字符串匹配
            if target.lower() in candidate.lower() or candidate.lower() in target.lower():
                substring_score = min(len(target), len(candidate)) / max(len(target), len(candidate))
                if substring_score > best_score and substring_score >= 0.5:
                    best_score = substring_score
                    best_candidate = candidate

        if best_candidate:
            return best_candidate, best_score

        return None


class FieldTypeDetector:
    """字段类型检测器"""

    def __init__(self):
        # 预定义的字段类型模式
        self.type_patterns = {
            FieldType.PRICE: [
                r'price', r'价格', r'open', r'high', r'low', r'close', r'收盘', r'开盘'
            ],
            FieldType.VOLUME: [
                r'volume', r'vol', r'成交量', r'交易量', r'amount', r'成交额'
            ],
            FieldType.PERCENTAGE: [
                r'pct', r'percent', r'rate', r'ratio', r'比率', r'百分比', r'增长率', r'涨跌幅'
            ],
            FieldType.CURRENCY: [
                r'revenue', r'profit', r'assets', r'liabilities', r'equity',
                r'收入', r'利润', r'资产', r'负债', r'权益', r'现金'
            ],
            FieldType.DATE: [
                r'date', r'time', r'日期', r'时间', r'报告期'
            ],
            FieldType.RATIO: [
                r'roe', r'roa', r'ratio', r'margin', r'比率', r'率'
            ]
        }

    def detect_field_type(self, column_name: str, sample_data: pd.Series) -> FieldType:
        """
        检测字段类型

        Args:
            column_name: 列名
            sample_data: 样本数据

        Returns:
            检测到的字段类型
        """
        column_lower = column_name.lower()

        # 1. 基于列名模式匹配
        for field_type, patterns in self.type_patterns.items():
            for pattern in patterns:
                if re.search(pattern, column_lower):
                    return field_type

        # 2. 基于数据内容推断
        if len(sample_data.dropna()) == 0:
            return FieldType.STRING

        sample_values = sample_data.dropna().head(100)  # 取前100个非空值

        # 检查是否为日期类型
        if self._is_date_like(sample_values):
            return FieldType.DATE

        # 检查是否为数值类型
        if self._is_numeric_like(sample_values):
            # 进一步判断数值类型
            if self._is_percentage_like(sample_values, column_name):
                return FieldType.PERCENTAGE
            elif self._is_currency_like(sample_values, column_name):
                return FieldType.CURRENCY
            elif self._is_volume_like(sample_values, column_name):
                return FieldType.VOLUME
            elif self._is_price_like(sample_values, column_name):
                return FieldType.PRICE
            else:
                return FieldType.NUMERIC

        # 检查是否为布尔类型
        if self._is_boolean_like(sample_values):
            return FieldType.BOOLEAN

        return FieldType.STRING

    def _is_date_like(self, sample_values: pd.Series) -> bool:
        """检查是否为日期类型"""
        try:
            # 尝试转换为日期
            pd.to_datetime(sample_values.head(10))
            return True
        except Exception:
            return False

    def _is_numeric_like(self, sample_values: pd.Series) -> bool:
        """检查是否为数值类型"""
        try:
            pd.to_numeric(sample_values.head(10))
            return True
        except Exception:
            return False

    def _is_percentage_like(self, sample_values: pd.Series, column_name: str) -> bool:
        """检查是否为百分比类型"""
        # 检查列名
        if any(keyword in column_name.lower() for keyword in ['pct', 'percent', '百分比', '率', 'ratio']):
            return True

        # 检查数值范围（百分比通常在-100到100之间，或0到1之间）
        try:
            numeric_values = pd.to_numeric(sample_values.head(20))
            if all(abs(val) <= 100 for val in numeric_values if not pd.isna(val)):
                return True
        except Exception:
            pass

        return False

    def _is_currency_like(self, sample_values: pd.Series, column_name: str) -> bool:
        """检查是否为货币类型"""
        currency_keywords = ['revenue', 'profit', 'assets', 'cash', '收入', '利润', '资产', '现金']
        return any(keyword in column_name.lower() for keyword in currency_keywords)

    def _is_volume_like(self, sample_values: pd.Series, column_name: str) -> bool:
        """检查是否为成交量类型"""
        volume_keywords = ['volume', 'vol', '成交量', '交易量']
        return any(keyword in column_name.lower() for keyword in volume_keywords)

    def _is_price_like(self, sample_values: pd.Series, column_name: str) -> bool:
        """检查是否为价格类型"""
        price_keywords = ['price', 'open', 'high', 'low', 'close', '价格', '开盘', '收盘']
        return any(keyword in column_name.lower() for keyword in price_keywords)

    def _is_boolean_like(self, sample_values: pd.Series) -> bool:
        """检查是否为布尔类型"""
        unique_values = set(str(val).lower() for val in sample_values.unique() if pd.notna(val))
        boolean_values = {'true', 'false', '1', '0', 'yes', 'no', 'y', 'n', '是', '否'}
        return unique_values.issubset(boolean_values)


class FieldMappingEngine:
    """智能字段映射引擎"""

    def __init__(self, field_mappings: Dict[DataType, Dict[str, str]] = None):
        """
        初始化字段映射引擎

        Args:
            field_mappings: 预定义的字段映射配置
        """
        self.logger = logger.bind(module=self.__class__.__name__)
        # 基础映射规则
        self.base_mappings = field_mappings or {}

        # 自定义映射规则
        self.custom_rules: Dict[DataType, List[FieldMappingRule]] = {}

        # 工具组件
        self.fuzzy_matcher = FuzzyMatcher(similarity_threshold=0.7)
        self.type_detector = FieldTypeDetector()

        # 缓存
        self._mapping_cache: Dict[str, MappingResult] = {}

        # 统计信息
        self.stats = {
            "total_mappings": 0,
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "inferred_matches": 0,
            "failed_matches": 0
        }

    def add_custom_mapping(self, data_type: DataType, mappings: Dict[str, List[str]]):
        """
        添加自定义映射规则

        Args:
            data_type: 数据类型
            mappings: 映射规则字典 {target_field: [source_patterns]}
        """
        if data_type not in self.custom_rules:
            self.custom_rules[data_type] = []

        for target_field, source_patterns in mappings.items():
            rule = FieldMappingRule(
                source_patterns=source_patterns,
                target_field=target_field,
                field_type=FieldType.STRING,  # 默认类型，后续可以推断
                priority=100  # 自定义规则优先级较高
            )
            self.custom_rules[data_type].append(rule)

        self.logger.info(f"添加了 {len(mappings)} 个自定义映射规则到 {data_type}")

    def map_fields(self, raw_data: pd.DataFrame, data_type: DataType) -> pd.DataFrame:
        """
        智能字段映射

        Args:
            raw_data: 原始数据
            data_type: 数据类型

        Returns:
            映射后的数据
        """
        if raw_data.empty:
            return raw_data

        self.logger.info(f"开始映射 {data_type} 类型的数据，原始字段数: {len(raw_data.columns)}")

        mapped_data = raw_data.copy()
        mapping_results = []

        # 获取映射规则
        base_mapping = self.base_mappings.get(data_type, {})
        custom_rules = self.custom_rules.get(data_type, [])

        # 对每个字段进行映射
        for column in raw_data.columns:
            result = self._map_single_field(column, raw_data[column], base_mapping, custom_rules)
            mapping_results.append(result)

            # 应用映射结果
            if result.target_field != result.source_field:
                # 目标列已存在时跳过 rename, 避免产生重复列:
                # 多个源字段(如 adj_type/adj_source)被模糊匹配到同一目标字段
                # (如 adj_close) 时, pandas rename 允许目标列已存在,
                # 会直接生成重复标签; 此处保留源列名并告警
                if result.target_field in mapped_data.columns:
                    self.logger.warning(
                        f"字段映射冲突: {result.source_field} -> {result.target_field} "
                        f"目标列已存在, 保留原列名以规避重复列"
                    )
                    continue
                mapped_data = mapped_data.rename(columns={result.source_field: result.target_field})

        # 更新统计信息
        self._update_stats(mapping_results)

        # 验证映射结果
        validation_passed = self.validate_mapping_result(mapped_data, data_type)

        self.logger.info(f"字段映射完成，映射后字段数: {len(mapped_data.columns)}, 验证通过: {validation_passed}")

        return mapped_data

    def _map_single_field(self, column_name: str, column_data: pd.Series,
                          base_mapping: Dict[str, str],
                          custom_rules: List[FieldMappingRule]) -> MappingResult:
        """
        映射单个字段

        Args:
            column_name: 字段名
            column_data: 字段数据
            base_mapping: 基础映射规则
            custom_rules: 自定义映射规则

        Returns:
            映射结果
        """
        # 检查缓存
        cache_key = f"{column_name}_{len(column_data)}"
        if cache_key in self._mapping_cache:
            return self._mapping_cache[cache_key]

        # 1. 精确匹配（基础映射）
        if column_name in base_mapping:
            result = MappingResult(
                source_field=column_name,
                target_field=base_mapping[column_name],
                confidence=1.0,
                match_type="exact",
                field_type=self.type_detector.detect_field_type(column_name, column_data)
            )
            self._mapping_cache[cache_key] = result
            return result

        # 2. 自定义规则匹配
        for rule in custom_rules:
            for pattern in rule.source_patterns:
                if re.search(pattern, column_name, re.IGNORECASE):
                    result = MappingResult(
                        source_field=column_name,
                        target_field=rule.target_field,
                        confidence=0.9,
                        match_type="custom",
                        field_type=rule.field_type
                    )
                    self._mapping_cache[cache_key] = result
                    return result

        # 3. 模糊匹配
        candidates = list(base_mapping.keys())
        fuzzy_match = self.fuzzy_matcher.find_best_match(column_name, candidates)

        if fuzzy_match:
            matched_field, confidence = fuzzy_match
            target_field = base_mapping[matched_field]
            result = MappingResult(
                source_field=column_name,
                target_field=target_field,
                confidence=confidence,
                match_type="fuzzy",
                field_type=self.type_detector.detect_field_type(column_name, column_data)
            )
            self._mapping_cache[cache_key] = result
            return result

        # 4. 基于数据内容推断
        field_type = self.type_detector.detect_field_type(column_name, column_data)
        inferred_target = self._infer_target_field(column_name, field_type)

        result = MappingResult(
            source_field=column_name,
            target_field=inferred_target,
            confidence=0.6,
            match_type="inferred",
            field_type=field_type
        )

        self._mapping_cache[cache_key] = result
        return result

    def _infer_target_field(self, column_name: str, field_type: FieldType) -> str:
        """
        基于字段类型推断目标字段名

        Args:
            column_name: 原始字段名
            field_type: 字段类型

        Returns:
            推断的目标字段名
        """
        # 简单的推断逻辑，可以根据需要扩展
        column_lower = column_name.lower()

        if field_type == FieldType.PRICE:
            if 'open' in column_lower or '开盘' in column_lower:
                return 'open'
            elif 'high' in column_lower or '最高' in column_lower:
                return 'high'
            elif 'low' in column_lower or '最低' in column_lower:
                return 'low'
            elif 'close' in column_lower or '收盘' in column_lower:
                return 'close'

        elif field_type == FieldType.VOLUME:
            return 'volume'

        elif field_type == FieldType.DATE:
            return 'datetime'

        # 如果无法推断，保持原字段名
        return column_name

    def validate_mapping_result(self, mapped_data: pd.DataFrame, data_type: DataType) -> bool:
        """
        验证映射结果

        Args:
            mapped_data: 映射后的数据
            data_type: 数据类型

        Returns:
            验证是否通过
        """
        try:
            # 基本验证：检查必需字段
            required_fields = self._get_required_fields(data_type)
            missing_fields = set(required_fields) - set(mapped_data.columns)

            if missing_fields:
                self.logger.warning(f"缺少必需字段: {missing_fields}")
                return False

            # 检查重复列: 多个源字段映射到同一目标字段时会生成重复标签,
            # 必需字段存在性校验(set 差集)无法发现, 此处显式拦截
            column_list = list(mapped_data.columns)
            duplicate_fields = [c for c in set(column_list) if column_list.count(c) > 1]
            if duplicate_fields:
                self.logger.warning(f"存在重复列: {duplicate_fields}")
                return False

            # 数据类型验证
            for column in mapped_data.columns:
                if not self._validate_column_data(mapped_data[column], column):
                    self.logger.warning(f"字段 {column} 数据验证失败")
                    return False

            return True

        except Exception as e:
            self.logger.error(f"映射结果验证失败: {e}")
            return False

    def _get_required_fields(self, data_type: DataType) -> List[str]:
        """获取必需字段列表"""
        required_fields_map = {
            DataType.HISTORICAL_KLINE: ['open', 'high', 'low', 'close', 'volume'],
            DataType.REAL_TIME_QUOTE: ['current_price', 'volume'],
            DataType.FINANCIAL_STATEMENT: ['symbol', 'report_date', 'report_type'],
            DataType.MACRO_ECONOMIC: ['indicator_code', 'value', 'data_date']
        }

        return required_fields_map.get(data_type, [])

    def _validate_column_data(self, column_data: pd.Series, column_name: str) -> bool:
        """验证列数据"""
        try:
            # 检查数据长度
            if len(column_data) == 0:
                return False

            # 检查空值比例（确保结果是标量）
            null_count = int(column_data.isnull().sum())
            total_count = len(column_data)
            null_ratio = null_count / total_count if total_count > 0 else 1.0

            if null_ratio > 0.8:  # 如果空值超过80%，认为数据质量有问题
                return False

            # 检查数据类型一致性
            non_null_data = column_data.dropna()
            if len(non_null_data) == 0:
                return False

            # 对于数值字段，检查是否包含有效数值
            if column_name in ['open', 'high', 'low', 'close', 'volume', 'value',
                               'main_net_inflow', 'change_percent', 'market_value']:
                try:
                    numeric_data = pd.to_numeric(non_null_data.head(10), errors='coerce')
                    # 检查转换后是否有有效的数值（确保结果是标量）
                    valid_count = int(numeric_data.notna().sum())
                    return valid_count > 0
                except Exception:
                    return False

            return True

        except Exception as e:
            self.logger.debug(f"列数据验证异常: {column_name}, {e}")
            return True  # 验证异常时认为数据有效，避免过于严格

    def _update_stats(self, mapping_results: List[MappingResult]):
        """更新统计信息"""
        self.stats["total_mappings"] += len(mapping_results)

        for result in mapping_results:
            if result.match_type == "exact":
                self.stats["exact_matches"] += 1
            elif result.match_type == "fuzzy":
                self.stats["fuzzy_matches"] += 1
            elif result.match_type == "inferred":
                self.stats["inferred_matches"] += 1
            else:
                self.stats["failed_matches"] += 1

    def get_mapping_stats(self) -> Dict[str, Any]:
        """获取映射统计信息"""
        stats = self.stats.copy()
        if stats["total_mappings"] > 0:
            stats["exact_match_rate"] = stats["exact_matches"] / stats["total_mappings"]
            stats["fuzzy_match_rate"] = stats["fuzzy_matches"] / stats["total_mappings"]
            stats["success_rate"] = (stats["exact_matches"] + stats["fuzzy_matches"]) / stats["total_mappings"]

        return stats

    def clear_cache(self):
        """清空缓存"""
        self._mapping_cache.clear()
        self.logger.info("映射缓存已清空")
