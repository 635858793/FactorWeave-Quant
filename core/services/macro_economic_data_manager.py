"""
宏观经济数据管理器

提供宏观经济指标数据的获取、存储、分析和相关性计算功能。
支持GDP、CPI、PMI、利率等核心经济指标的管理。

作者: FactorWeave-Quant增强团队
版本: 1.0
日期: 2025-09-21
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
import numpy as np
from collections import defaultdict

from loguru import logger
from core.database.duckdb_manager import DuckDBConnectionManager
import duckdb
from core.data_source_extensions import IDataSourcePlugin
from core.data_standardization_engine import DataStandardizationEngine
from core.data_validator import DataValidator

logger = logger.bind(module=__name__)


class SimpleDuckDBManager:
    """简单的DuckDB管理器包装器"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)

    def execute(self, query: str, params=None):
        """执行SQL语句"""
        return self.conn.execute(query, params or [])

    def query(self, query: str, params=None) -> pd.DataFrame:
        """执行查询并返回DataFrame"""
        return self.conn.execute(query, params or []).df()

    def copy_from_dataframe(self, df: pd.DataFrame, table_name: str):
        """从DataFrame复制数据到表"""
        self.conn.register(f"temp_{table_name}", df)
        self.conn.execute(f"INSERT INTO {table_name} SELECT * FROM temp_{table_name}")
        self.conn.unregister(f"temp_{table_name}")


class EconomicIndicatorType(Enum):
    """经济指标类型"""
    GDP = "gdp"                          # 国内生产总值
    CPI = "cpi"                          # 消费者价格指数
    PPI = "ppi"                          # 生产者价格指数
    PMI = "pmi"                          # 采购经理指数
    UNEMPLOYMENT_RATE = "unemployment"    # 失业率
    INTEREST_RATE = "interest_rate"      # 利率
    MONEY_SUPPLY = "money_supply"        # 货币供应量
    EXCHANGE_RATE = "exchange_rate"      # 汇率
    TRADE_BALANCE = "trade_balance"      # 贸易平衡
    FISCAL_BALANCE = "fiscal_balance"    # 财政平衡
    INDUSTRIAL_PRODUCTION = "industrial_production"  # 工业生产指数
    RETAIL_SALES = "retail_sales"        # 零售销售
    HOUSING_STARTS = "housing_starts"    # 新屋开工
    CONSUMER_CONFIDENCE = "consumer_confidence"  # 消费者信心指数


class IndicatorFrequency(Enum):
    """指标频率"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"


@dataclass
class EconomicIndicator:
    """经济指标数据结构"""
    indicator_type: EconomicIndicatorType
    country: str                         # 国家/地区
    value: float                         # 指标值
    period: str                          # 时间周期 (YYYY-MM-DD, YYYY-MM, YYYY-Q1, YYYY)
    frequency: IndicatorFrequency        # 数据频率

    # 元数据
    unit: str = ""                       # 单位
    source: str = ""                     # 数据源
    release_date: Optional[datetime] = None  # 发布日期
    revision: int = 0                    # 修订次数

    # 质量信息
    is_preliminary: bool = False         # 是否为初值
    is_revised: bool = False             # 是否为修订值
    confidence_level: float = 1.0        # 置信度

    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class IndicatorCorrelation:
    """指标相关性"""
    indicator1: EconomicIndicatorType
    indicator2: EconomicIndicatorType
    correlation_coefficient: float       # 相关系数
    p_value: float                      # p值
    sample_size: int                    # 样本数量
    time_period: Tuple[datetime, datetime]  # 时间范围

    # 相关性类型
    correlation_type: str = "pearson"    # pearson, spearman, kendall
    lag_periods: int = 0                # 滞后期数

    # 统计信息
    is_significant: bool = False         # 是否显著
    confidence_interval: Tuple[float, float] = (0.0, 0.0)  # 置信区间

    calculated_at: datetime = field(default_factory=datetime.now)


class MacroEconomicDataManager:
    """
    宏观经济数据管理器

    提供宏观经济数据管理功能：
    - 经济指标数据获取和存储
    - 数据标准化和验证
    - 指标相关性分析
    - 数据更新和同步
    - 历史数据查询
    """

    def __init__(self, data_standardizer: DataStandardizationEngine, data_validator: DataValidator, db_path: str = "data/macro_economic.db"):
        self.duckdb_manager = SimpleDuckDBManager(db_path)
        self.data_standardizer = data_standardizer
        self.data_validator = data_validator

        # 数据源管理
        self.macro_plugins: Dict[str, IDataSourcePlugin] = {}

        # 缓存管理
        self._indicator_cache: Dict[str, List[EconomicIndicator]] = {}
        self._correlation_cache: Dict[str, IndicatorCorrelation] = {}

        # 配置
        self.supported_countries = ["CN", "US", "EU", "JP", "UK", "DE", "FR"]
        self.cache_ttl = timedelta(hours=6)  # 缓存6小时

        # 初始化数据库表
        self._initialize_database()

        logger.info("宏观经济数据管理器初始化完成")

    def _initialize_database(self):
        """初始化数据库表"""
        try:
            # 创建经济指标表
            create_indicators_table = """
            CREATE TABLE IF NOT EXISTS economic_indicators (
                id INTEGER PRIMARY KEY,
                indicator_type VARCHAR(50) NOT NULL,
                country VARCHAR(10) NOT NULL,
                value DOUBLE NOT NULL,
                period VARCHAR(20) NOT NULL,
                frequency VARCHAR(20) NOT NULL,
                unit VARCHAR(50),
                source VARCHAR(100),
                release_date TIMESTAMP,
                revision INTEGER DEFAULT 0,
                is_preliminary BOOLEAN DEFAULT FALSE,
                is_revised BOOLEAN DEFAULT FALSE,
                confidence_level DOUBLE DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(indicator_type, country, period, revision)
            );
            """

            # 创建指标相关性表
            create_correlations_table = """
            CREATE TABLE IF NOT EXISTS indicator_correlations (
                id INTEGER PRIMARY KEY,
                indicator1 VARCHAR(50) NOT NULL,
                indicator2 VARCHAR(50) NOT NULL,
                correlation_coefficient DOUBLE NOT NULL,
                p_value DOUBLE NOT NULL,
                sample_size INTEGER NOT NULL,
                start_date TIMESTAMP NOT NULL,
                end_date TIMESTAMP NOT NULL,
                correlation_type VARCHAR(20) DEFAULT 'pearson',
                lag_periods INTEGER DEFAULT 0,
                is_significant BOOLEAN DEFAULT FALSE,
                confidence_interval_lower DOUBLE,
                confidence_interval_upper DOUBLE,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(indicator1, indicator2, correlation_type, lag_periods, start_date, end_date)
            );
            """

            # 创建索引
            create_indicators_index = """
            CREATE INDEX IF NOT EXISTS idx_indicators_type_country_period 
            ON economic_indicators(indicator_type, country, period);
            """

            create_correlations_index = """
            CREATE INDEX IF NOT EXISTS idx_correlations_indicators 
            ON indicator_correlations(indicator1, indicator2);
            """

            # 执行SQL
            self.duckdb_manager.execute(create_indicators_table)
            self.duckdb_manager.execute(create_correlations_table)
            self.duckdb_manager.execute(create_indicators_index)
            self.duckdb_manager.execute(create_correlations_index)

            logger.info("宏观经济数据库表初始化完成")

        except Exception as e:
            logger.error(f"初始化宏观经济数据库表失败: {e}")

    async def register_macro_plugin(self, plugin_id: str, plugin: IDataSourcePlugin):
        """注册宏观数据源插件"""
        try:
            self.macro_plugins[plugin_id] = plugin
            logger.info(f"宏观数据源插件已注册: {plugin_id}")
        except Exception as e:
            logger.error(f"注册宏观数据源插件失败: {plugin_id}, {e}")

    async def get_economic_indicator(self, indicator_type: EconomicIndicatorType, country: str,
                                     start_date: datetime, end_date: datetime,
                                     frequency: IndicatorFrequency = None) -> List[EconomicIndicator]:
        """
        获取经济指标数据

        Args:
            indicator_type: 指标类型
            country: 国家代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率（可选）

        Returns:
            List[EconomicIndicator]: 经济指标数据列表
        """
        try:
            logger.info(f"获取经济指标: {indicator_type.value} - {country} ({start_date} 到 {end_date})")

            # 首先尝试从缓存获取
            cache_key = f"{indicator_type.value}_{country}_{start_date.date()}_{end_date.date()}"
            if cache_key in self._indicator_cache:
                logger.debug(f"从缓存获取经济指标: {cache_key}")
                return self._indicator_cache[cache_key]

            # 从数据库查询
            indicators = await self._query_indicators_from_db(indicator_type, country, start_date, end_date, frequency)

            # 如果数据库中没有足够的数据，尝试从数据源获取
            if not indicators or self._need_data_update(indicators, end_date):
                logger.info(f"从数据源获取最新经济指标: {indicator_type.value} - {country}")
                new_indicators = await self._fetch_indicators_from_sources(indicator_type, country, start_date, end_date, frequency)

                if new_indicators:
                    # 保存到数据库
                    await self._save_indicators_to_db(new_indicators)
                    indicators.extend(new_indicators)

            # 去重和排序
            indicators = self._deduplicate_and_sort_indicators(indicators)

            # 更新缓存
            self._indicator_cache[cache_key] = indicators

            logger.info(f"经济指标获取完成: {len(indicators)} 条数据")
            return indicators

        except Exception as e:
            logger.error(f"获取经济指标失败: {indicator_type.value} - {country}, {e}")
            return []

    async def _query_indicators_from_db(self, indicator_type: EconomicIndicatorType, country: str,
                                        start_date: datetime, end_date: datetime,
                                        frequency: IndicatorFrequency = None) -> List[EconomicIndicator]:
        """从数据库查询指标数据"""
        try:
            query = """
            SELECT indicator_type, country, value, period, frequency, unit, source,
                   release_date, revision, is_preliminary, is_revised, confidence_level,
                   created_at, updated_at
            FROM economic_indicators
            WHERE indicator_type = ? AND country = ?
            AND period >= ? AND period <= ?
            """

            params = [indicator_type.value, country, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]

            if frequency:
                query += " AND frequency = ?"
                params.append(frequency.value)

            query += " ORDER BY period ASC"

            result = self.duckdb_manager.query(query, params)

            indicators = []
            for row in result:
                indicator = EconomicIndicator(
                    indicator_type=EconomicIndicatorType(row[0]),
                    country=row[1],
                    value=float(row[2]),
                    period=row[3],
                    frequency=IndicatorFrequency(row[4]),
                    unit=row[5] or "",
                    source=row[6] or "",
                    release_date=row[7],
                    revision=int(row[8]) if row[8] else 0,
                    is_preliminary=bool(row[9]) if row[9] is not None else False,
                    is_revised=bool(row[10]) if row[10] is not None else False,
                    confidence_level=float(row[11]) if row[11] else 1.0,
                    created_at=row[12] if row[12] else datetime.now(),
                    updated_at=row[13] if row[13] else datetime.now()
                )
                indicators.append(indicator)

            return indicators

        except Exception as e:
            logger.error(f"从数据库查询经济指标失败: {e}")
            return []

    async def _fetch_indicators_from_sources(self, indicator_type: EconomicIndicatorType, country: str,
                                             start_date: datetime, end_date: datetime,
                                             frequency: IndicatorFrequency = None) -> List[EconomicIndicator]:
        """从数据源获取指标数据"""
        try:
            indicators = []

            for plugin_id, plugin in self.macro_plugins.items():
                try:
                    # 这里需要根据实际插件接口调用
                    # 假设插件有get_economic_indicator方法
                    raw_data = await plugin.get_economic_indicator(
                        indicator_type.value, country, start_date, end_date, frequency.value if frequency else None
                    )

                    if raw_data:
                        # 标准化数据
                        standardized_data = self.data_standardizer.standardize_macro_data(raw_data, plugin_id)

                        # 验证数据
                        if self.data_validator.validate_macro_data(standardized_data):
                            # 转换为EconomicIndicator对象
                            plugin_indicators = self._convert_to_indicators(standardized_data, indicator_type, country)
                            indicators.extend(plugin_indicators)
                        else:
                            logger.warning(f"宏观数据验证失败，插件: {plugin_id}")

                except Exception as e:
                    logger.error(f"从插件获取宏观数据失败: {plugin_id}, {e}")

            return indicators

        except Exception as e:
            logger.error(f"从数据源获取经济指标失败: {e}")
            return []

    def _convert_to_indicators(self, data: List[Dict], indicator_type: EconomicIndicatorType, country: str) -> List[EconomicIndicator]:
        """将原始数据转换为EconomicIndicator对象"""
        try:
            indicators = []

            for item in data:
                indicator = EconomicIndicator(
                    indicator_type=indicator_type,
                    country=country,
                    value=float(item.get('value', 0)),
                    period=item.get('period', ''),
                    frequency=IndicatorFrequency(item.get('frequency', 'monthly')),
                    unit=item.get('unit', ''),
                    source=item.get('source', ''),
                    release_date=item.get('release_date'),
                    revision=int(item.get('revision', 0)),
                    is_preliminary=bool(item.get('is_preliminary', False)),
                    is_revised=bool(item.get('is_revised', False)),
                    confidence_level=float(item.get('confidence_level', 1.0))
                )
                indicators.append(indicator)

            return indicators

        except Exception as e:
            logger.error(f"转换经济指标数据失败: {e}")
            return []

    async def _save_indicators_to_db(self, indicators: List[EconomicIndicator]):
        """保存指标数据到数据库"""
        try:
            if not indicators:
                return

            # 批量插入
            insert_query = """
            INSERT OR REPLACE INTO economic_indicators 
            (indicator_type, country, value, period, frequency, unit, source, 
             release_date, revision, is_preliminary, is_revised, confidence_level, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            data_to_insert = []
            for indicator in indicators:
                data_to_insert.append([
                    indicator.indicator_type.value,
                    indicator.country,
                    indicator.value,
                    indicator.period,
                    indicator.frequency.value,
                    indicator.unit,
                    indicator.source,
                    indicator.release_date,
                    indicator.revision,
                    indicator.is_preliminary,
                    indicator.is_revised,
                    indicator.confidence_level,
                    datetime.now()
                ])

            self.duckdb_manager.execute_many(insert_query, data_to_insert)
            logger.info(f"保存 {len(indicators)} 条经济指标到数据库")

        except Exception as e:
            logger.error(f"保存经济指标到数据库失败: {e}")

    def _need_data_update(self, indicators: List[EconomicIndicator], end_date: datetime) -> bool:
        """检查是否需要更新数据"""
        try:
            if not indicators:
                return True

            # 检查最新数据的时间
            latest_indicator = max(indicators, key=lambda x: x.updated_at)
            time_diff = datetime.now() - latest_indicator.updated_at

            # 如果最后更新时间超过缓存TTL，需要更新
            if time_diff > self.cache_ttl:
                return True

            # 检查数据是否覆盖到结束日期
            latest_period = max(indicators, key=lambda x: x.period).period
            if latest_period < end_date.strftime('%Y-%m-%d'):
                return True

            return False

        except Exception as e:
            logger.error(f"检查数据更新需求失败: {e}")
            return True

    def _deduplicate_and_sort_indicators(self, indicators: List[EconomicIndicator]) -> List[EconomicIndicator]:
        """去重和排序指标数据"""
        try:
            # 按照指标类型、国家、周期、修订版本去重，保留最新的
            unique_indicators = {}

            for indicator in indicators:
                key = (indicator.indicator_type, indicator.country, indicator.period)
                if key not in unique_indicators or indicator.revision > unique_indicators[key].revision:
                    unique_indicators[key] = indicator

            # 按周期排序
            sorted_indicators = sorted(unique_indicators.values(), key=lambda x: x.period)

            return sorted_indicators

        except Exception as e:
            logger.error(f"去重和排序指标数据失败: {e}")
            return indicators

    async def calculate_indicator_correlation(self, indicator1: EconomicIndicatorType, indicator2: EconomicIndicatorType,
                                              country: str, start_date: datetime, end_date: datetime,
                                              correlation_type: str = "pearson", lag_periods: int = 0) -> Optional[IndicatorCorrelation]:
        """
        计算指标相关性

        Args:
            indicator1: 第一个指标
            indicator2: 第二个指标
            country: 国家代码
            start_date: 开始日期
            end_date: 结束日期
            correlation_type: 相关性类型 (pearson, spearman, kendall)
            lag_periods: 滞后期数

        Returns:
            IndicatorCorrelation: 相关性结果
        """
        try:
            logger.info(f"计算指标相关性: {indicator1.value} vs {indicator2.value} ({country})")

            # 检查缓存
            cache_key = f"{indicator1.value}_{indicator2.value}_{country}_{correlation_type}_{lag_periods}_{start_date.date()}_{end_date.date()}"
            if cache_key in self._correlation_cache:
                return self._correlation_cache[cache_key]

            # 获取两个指标的数据
            data1 = await self.get_economic_indicator(indicator1, country, start_date, end_date)
            data2 = await self.get_economic_indicator(indicator2, country, start_date, end_date)

            if not data1 or not data2:
                logger.warning(f"指标数据不足，无法计算相关性")
                return None

            # 转换为DataFrame进行计算
            df1 = pd.DataFrame([{'period': ind.period, 'value': ind.value} for ind in data1])
            df2 = pd.DataFrame([{'period': ind.period, 'value': ind.value} for ind in data2])

            # 合并数据
            merged_df = pd.merge(df1, df2, on='period', suffixes=('_1', '_2'))

            if len(merged_df) < 3:
                logger.warning(f"有效数据点不足，无法计算相关性")
                return None

            # 应用滞后
            if lag_periods > 0:
                merged_df['value_2'] = merged_df['value_2'].shift(-lag_periods)
                merged_df = merged_df.dropna()

            if len(merged_df) < 3:
                logger.warning(f"应用滞后后数据点不足，无法计算相关性")
                return None

            # 计算相关性
            values1 = merged_df['value_1'].values
            values2 = merged_df['value_2'].values

            if correlation_type == "pearson":
                correlation_coef, p_value = self._calculate_pearson_correlation(values1, values2)
            elif correlation_type == "spearman":
                correlation_coef, p_value = self._calculate_spearman_correlation(values1, values2)
            elif correlation_type == "kendall":
                correlation_coef, p_value = self._calculate_kendall_correlation(values1, values2)
            else:
                logger.error(f"不支持的相关性类型: {correlation_type}")
                return None

            # 计算置信区间
            confidence_interval = self._calculate_confidence_interval(correlation_coef, len(merged_df))

            # 创建相关性对象
            correlation = IndicatorCorrelation(
                indicator1=indicator1,
                indicator2=indicator2,
                correlation_coefficient=correlation_coef,
                p_value=p_value,
                sample_size=len(merged_df),
                time_period=(start_date, end_date),
                correlation_type=correlation_type,
                lag_periods=lag_periods,
                is_significant=p_value < 0.05,
                confidence_interval=confidence_interval
            )

            # 保存到数据库
            await self._save_correlation_to_db(correlation)

            # 更新缓存
            self._correlation_cache[cache_key] = correlation

            logger.info(f"相关性计算完成: {correlation_coef:.4f} (p={p_value:.4f})")
            return correlation

        except Exception as e:
            logger.error(f"计算指标相关性失败: {e}")
            return None

    def _calculate_pearson_correlation(self, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """计算皮尔逊相关系数"""
        try:
            from scipy.stats import pearsonr
            correlation, p_value = pearsonr(x, y)
            return float(correlation), float(p_value)
        except ImportError:
            correlation = np.corrcoef(x, y)[0, 1]
            n = len(x)
            from scipy.stats import t
            t_stat = correlation * np.sqrt((n - 2) / (1 - correlation**2))
            p_value = 2 * t.sf(abs(t_stat), df=n - 2)
            return float(correlation), float(p_value)

    def _calculate_spearman_correlation(self, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """计算斯皮尔曼相关系数"""
        try:
            from scipy.stats import spearmanr
            correlation, p_value = spearmanr(x, y)
            return float(correlation), float(p_value)
        except ImportError:
            # 简化实现：使用排名后的皮尔逊相关
            from scipy.stats import rankdata
            rank_x = rankdata(x)
            rank_y = rankdata(y)
            return self._calculate_pearson_correlation(rank_x, rank_y)

    def _calculate_kendall_correlation(self, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """计算肯德尔相关系数"""
        try:
            from scipy.stats import kendalltau
            correlation, p_value = kendalltau(x, y)
            return float(correlation), float(p_value)
        except ImportError:
            # 简化实现
            logger.warning("scipy未安装，使用简化的Kendall相关计算")
            return self._calculate_pearson_correlation(x, y)

    def _calculate_confidence_interval(self, correlation: float, sample_size: int, confidence_level: float = 0.95) -> Tuple[float, float]:
        """计算相关系数的置信区间"""
        try:
            if sample_size < 4:
                return (correlation, correlation)

            # Fisher变换
            z = 0.5 * np.log((1 + correlation) / (1 - correlation))
            se = 1 / np.sqrt(sample_size - 3)

            # 置信区间
            alpha = 1 - confidence_level
            from scipy.stats import norm
            z_critical = norm.ppf(1 - alpha / 2)

            z_lower = z - z_critical * se
            z_upper = z + z_critical * se

            # 反Fisher变换
            r_lower = (np.exp(2 * z_lower) - 1) / (np.exp(2 * z_lower) + 1)
            r_upper = (np.exp(2 * z_upper) - 1) / (np.exp(2 * z_upper) + 1)

            return (float(r_lower), float(r_upper))

        except Exception as e:
            logger.error(f"计算置信区间失败: {e}")
            return (correlation, correlation)

    async def _save_correlation_to_db(self, correlation: IndicatorCorrelation):
        """保存相关性到数据库"""
        try:
            insert_query = """
            INSERT OR REPLACE INTO indicator_correlations
            (indicator1, indicator2, correlation_coefficient, p_value, sample_size,
             start_date, end_date, correlation_type, lag_periods, is_significant,
             confidence_interval_lower, confidence_interval_upper, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = [
                correlation.indicator1.value,
                correlation.indicator2.value,
                correlation.correlation_coefficient,
                correlation.p_value,
                correlation.sample_size,
                correlation.time_period[0],
                correlation.time_period[1],
                correlation.correlation_type,
                correlation.lag_periods,
                correlation.is_significant,
                correlation.confidence_interval[0],
                correlation.confidence_interval[1],
                correlation.calculated_at
            ]

            self.duckdb_manager.execute(insert_query, params)
            logger.debug(f"相关性已保存到数据库")

        except Exception as e:
            logger.error(f"保存相关性到数据库失败: {e}")

    def get_indicator_summary(self, country: str = None) -> Dict[str, Any]:
        """获取指标数据摘要"""
        try:
            query = """
            SELECT indicator_type, country, COUNT(*) as count,
                   MIN(period) as earliest_period, MAX(period) as latest_period,
                   AVG(value) as avg_value, MIN(value) as min_value, MAX(value) as max_value
            FROM economic_indicators
            """

            params = []
            if country:
                query += " WHERE country = ?"
                params.append(country)

            query += " GROUP BY indicator_type, country ORDER BY indicator_type, country"

            result = self.duckdb_manager.query(query, params)

            summary = {
                'total_indicators': len(result),
                'indicators_by_type': defaultdict(list),
                'countries': set(),
                'date_range': {'earliest': None, 'latest': None}
            }

            for row in result:
                indicator_type, country_code, count, earliest, latest, avg_val, min_val, max_val = row

                summary['indicators_by_type'][indicator_type].append({
                    'country': country_code,
                    'count': count,
                    'earliest_period': earliest,
                    'latest_period': latest,
                    'avg_value': avg_val,
                    'min_value': min_val,
                    'max_value': max_val
                })

                summary['countries'].add(country_code)

                # 更新全局日期范围
                if not summary['date_range']['earliest'] or earliest < summary['date_range']['earliest']:
                    summary['date_range']['earliest'] = earliest
                if not summary['date_range']['latest'] or latest > summary['date_range']['latest']:
                    summary['date_range']['latest'] = latest

            summary['countries'] = list(summary['countries'])
            summary['indicators_by_type'] = dict(summary['indicators_by_type'])

            return summary

        except Exception as e:
            logger.error(f"获取指标摘要失败: {e}")
            return {}

    def cleanup_cache(self):
        """清理缓存"""
        try:
            self._indicator_cache.clear()
            self._correlation_cache.clear()
            logger.info("宏观经济数据缓存已清理")
        except Exception as e:
            logger.error(f"清理缓存失败: {e}")

    def cleanup(self):
        """清理资源"""
        try:
            self.cleanup_cache()
            logger.info("宏观经济数据管理器资源清理完成")
        except Exception as e:
            logger.error(f"资源清理失败: {e}")
